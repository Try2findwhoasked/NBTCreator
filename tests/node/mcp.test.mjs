import assert from 'node:assert/strict'
import { execFileSync, spawn } from 'node:child_process'
import { createHash, randomUUID } from 'node:crypto'
import fs from 'node:fs/promises'
import os from 'node:os'
import path from 'node:path'
import { test } from 'node:test'
import { setTimeout as delay } from 'node:timers/promises'
import { pathToFileURL } from 'node:url'
import { python, root } from '../../scripts/paths.mjs'
import { createMcpClient } from '../../scripts/mcp/client.mjs'
import { lines, maxResponse, send, maxRequest } from '../../scripts/mcp/stdio.mjs'

const integrationEntry = process.env.NBTCREATOR_TEST_MCP_ENTRY
const sourceEntry = integrationEntry || path.join(root, 'scripts/mcp/server.mjs')
const archive = process.env.NBTCREATOR_TEST_AGENT_ARCHIVE
const sha = bytes => createHash('sha256').update(bytes).digest('hex')
const settings = { encoding: 'utf8', windowsHide: true }
const version = 'test'
const requestId = () => randomUUID()
const call = async (client, name, args = {}, options) =>
  (await client.request('tools/call', { name, arguments: args }, options)).structuredContent

async function until(condition, attempts = 100) {
  for (let i = 0; i < attempts; i++) {
    if (await condition()) return
    await delay(50)
  }
  assert.fail('Condition did not become true')
}

async function workspace(t) {
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), 'NBTCreator MCP 空格-'))
  t.after(() => fs.rm(dir, { recursive: true, force: true }))
  const model = path.join(dir, 'nbt_models', '合成 建筑')
  execFileSync(python, ['-B', path.join(root, 'tests/support/make_fixture.py'), model], settings)
  return { dir, model, source: path.join(model, 'synthetic.master.json.gz') }
}

function connect(t, dir, flags = [], overrides = {}) {
  const client = createMcpClient({ executable: process.execPath, args: [sourceEntry, '--workspace', dir, ...flags],
    cwd: root, version, ...overrides })
  t.after(() => client.close())
  return client
}

test('stdio lifecycle, declared capabilities, bounded tools and workload isolation', { skip: Boolean(archive) }, async t => {
  const a = await workspace(t), b = await workspace(t)
  const readOnly = connect(t, a.dir)
  const writer = connect(t, a.dir, ['--allow-write'])
  const other = connect(t, b.dir, ['--allow-write'])
  const hello = await readOnly.start()
  assert.equal(hello.protocolVersion, '2025-11-25')
  assert.equal(hello.serverInfo.name, 'nbtcreator')
  const list = await readOnly.request('tools/list')
  assert.ok(list.tools.some(item => item.name === 'tasks.list'))
  assert.ok(!list.tools.some(item => item.name === 'tasks.create'))
  assert.equal((await call(readOnly, 'tasks.create')).error.code, 'TOOL_UNAVAILABLE')
  assert.equal((await call(readOnly, 'shell.exec')).error.code, 'TOOL_UNAVAILABLE')
  assert.equal((await call(readOnly, 'tasks.list', { workspace: b.dir })).error.code, 'INVALID_ARGUMENTS')
  assert.equal((await call(readOnly, 'retrieve.research')).error.code, 'TOOL_UNAVAILABLE')
  assert.equal((await call(readOnly, 'retrieve.search', { request: { workflow: 'workbench', query: '楼梯' } })).ok, true)
  const args = { source: a.source, source_sha256: sha(await fs.readFile(a.source)), name: '模型修改 测试', request_id: requestId() }
  assert.equal((await call(other, 'tasks.create', args)).ok, false)
  const task = await call(writer, 'tasks.create', args)
  assert.equal(task.ok, true, JSON.stringify(task.error))
  assert.equal(task.data.name, args.name)
  assert.deepEqual(await call(writer, 'tasks.create', args), task)
  assert.equal((await call(writer, 'tasks.create', { ...args, name: '不匹配' })).error.code, 'IDEMPOTENCY_CONFLICT')
  const claim = { id: task.data.id, owner: '试验进程', ttl_seconds: 120, request_id: requestId() }
  const lease = await call(writer, 'tasks.claim', claim)
  assert.equal(lease.ok, true, JSON.stringify(lease.error))
  assert.deepEqual(await call(writer, 'tasks.claim', claim), lease)
  assert.equal((await call(writer, 'tasks.claim', { ...claim, owner: 'second', request_id: requestId() })).ok, false)
  const { fence } = lease.data.lease
  const { lease_token } = lease.data
  assert.equal((await call(writer, 'tasks.release', { id: task.data.id, lease_token, fence, request_id: requestId() })).ok, true)
  assert.equal((await call(other, 'tasks.get', { id: task.data.id })).ok, false)
  assert.equal((await call(readOnly, 'candidate.validate', { mode: 'structure', result: {}, context: {} })).data.nbt_exported, false)
  const missing = connect(t, a.dir, [], { env: { ...process.env, NBTCREATOR_PYTHON: path.join(a.dir, 'missing.exe') } })
  await assert.rejects(missing.start(), error => error.code === 'ENGINE_UNAVAILABLE')
  assert.equal(missing.status().state, 'unavailable')
})

test('MCP handshake and stdio framing negotiate versions and exit on EOF', { skip: Boolean(archive) }, async t => {
  const { dir } = await workspace(t)
  const child = spawn(process.execPath, [sourceEntry, '--workspace', dir], { windowsHide: true })
  const stopped = new Promise(resolve => child.once('close', resolve))
  child.stderr.on('data', chunk => process.stderr.write(chunk))
  t.after(() => { if (child.exitCode === null) child.kill() })
  const frames = lines(child.stdout, maxResponse)
  send(child.stdin, { method: 'tools/list', id: 1 }, maxRequest)
  let msg = JSON.parse((await frames.next()).value)
  assert.equal(msg.error.code, -32001)
  send(child.stdin, { method: 'initialize', id: 2, params: { protocolVersion: '2025-06-18', capabilities: {},
    clientInfo: { name: 'fixture', version } } }, maxRequest)
  msg = JSON.parse((await frames.next()).value)
  assert.equal(msg.result.protocolVersion, '2025-06-18')
  send(child.stdin, { method: 'notifications/initialized' }, maxRequest)
  send(child.stdin, { method: 'ping', id: 3 }, maxRequest)
  assert.deepEqual(JSON.parse((await frames.next()).value).result, {})
  child.stdin.end()
  assert.equal(await stopped, 0)
  assert.equal((await frames.next()).done, true)
})

test('host-held invitation exposes only tools for its role and binds the claimed lease', { skip: Boolean(archive) }, async t => {
  const { dir } = await workspace(t)
  const session = path.join(dir, '工作包 邀请.json')
  const fixture = [
    'import json, sys',
    'from pathlib import Path',
    'sys.path.insert(0, sys.argv[1])',
    'from authoring_fixture import Inn',
    'inn = Inn()',
    'inn.workspace_folder = Path(sys.argv[2])',
    'inn.setUp()',
    '_, _, leaf, _ = inn.delegate()',
    'Path(sys.argv[3]).write_text(json.dumps(inn.invitations[leaf["id"]]), encoding="utf8")'
  ].join('\n')
  const engine = path.resolve(path.dirname(sourceEntry), '../../.agents/skills/minecraft-nbt-modeler/scripts')
  execFileSync(python, ['-B', '-c', fixture, path.join(root, 'tests/support'), dir, session],
    { ...settings, env: { ...process.env, NBTCREATOR_TEST_ENGINE_SCRIPTS: engine } })
  const client = connect(t, dir, ['--package-session', session, '--allow-write'])
  const hello = await client.start()
  assert.equal(hello.capabilities.resources, undefined)
  const list = await client.request('tools/list')
  assert.deepEqual(list.tools.map(tool => tool.name).sort(),
    ['block_state', 'brief', 'claim', 'context', 'heartbeat', 'release', 'submit'].map(name => 'authoring.' + name))
  assert.equal((await call(client, 'authoring.claim', { package_id: 'another', owner: '代理', request_id: requestId() })).error.code, 'INVALID_ARGUMENTS')
  const claimed = await call(client, 'authoring.claim', { owner: '代理', request_id: requestId() })
  assert.equal(claimed.ok, true, JSON.stringify(claimed.error))
  const invitation = JSON.parse(await fs.readFile(session, 'utf8'))
  await fs.writeFile(session, JSON.stringify({ ...invitation, lease_token: claimed.data.lease_token, fence: claimed.data.lease.fence }))
  const brief = await call(client, 'authoring.brief')
  assert.equal(brief.data.role, 'component')
  assert.equal((await call(client, 'render.model')).error.code, 'TOOL_UNAVAILABLE')
})

test('the model candidate has real review evidence before any production version is saved',
  { skip: Boolean(archive), timeout: 240000 }, async t => {
    const { dir } = await workspace(t)
    const client = connect(t, dir, ['--allow-write'])
    const readOnly = connect(t, dir)
    const tools = (await client.request('tools/list')).tools.map(tool => tool.name)
    if (!tools.includes('render.candidate') && !integrationEntry) return t.skip('This machine catalogue predates model.preview')
    assert.ok(tools.includes('render.candidate'))
    assert.ok(!(await readOnly.request('tools/list')).tools.some(tool => ['model.preview', 'model.commit', 'render.candidate'].includes(tool.name)))
    const model = { size: [8, 6, 8], kind: 'component', actions: [{ method: 'patch', changes: [
      { pos: [1, 1, 1], before: ['minecraft:air', false], after: ['minecraft:stone_bricks', true] }
    ] }] }
    const candidate = await call(readOnly, 'model.candidate', { model })
    assert.equal(candidate.ok, true, JSON.stringify(candidate.error))
    assert.equal(candidate.data.diff.changed_positions, 1)
    const { candidate_sha256 } = candidate.data
    const args = { model, candidate_sha256, width: 320, height: 200, request_id: requestId(),
      cameras: [{ id: 'overview', eye: [10, 7, 10], target: [2, 1, 2] }] }
    assert.equal((await call(client, 'render.candidate', { ...args, candidate_sha256: '0'.repeat(64) })).error.code, 'STALE_CANDIDATE')
    const review = await call(client, 'render.candidate', { ...args, request_id: requestId() }, { timeout: 140000 })
    assert.equal(review.ok, true, JSON.stringify(review.error))
    assert.equal(review.data.preview.candidate_sha256, candidate_sha256)
    assert.equal(review.data.preview.model_sha256, candidate.data.model.model_sha256)
    assert.equal(review.data.preview.visual_review, 'pending')
    assert.equal(review.data.preview.approval_created, false)
    assert.equal(review.data.preview.nbt_exported, false)
    assert.equal(review.data.source_sha256, review.data.preview.source_sha256)
    assert.equal(review.data.cameras_sha256, review.data.preview.cameras_sha256)
    const image = review.data.artifacts.find(item => item.name === 'overview.png')
    const packet = await client.request('resources/read', { uri: image.uri })
    assert.equal(sha(Buffer.from(packet.contents[0].blob, 'base64')), image.sha256)
    assert.deepEqual((await fs.readdir(path.join(dir, 'nbt_models'))).sort(), ['_workspaces', '合成 建筑'])
    const save = { model, candidate_sha256, save: { name_zh: '审阅前后 版本' }, request_id: requestId() }
    const saved = await call(client, 'model.commit', save)
    assert.equal(saved.ok, true, JSON.stringify(saved.error))
    assert.equal(saved.data.nbt_exported, false)
    assert.equal(saved.data.approval_created, false)
    assert.deepEqual(await call(client, 'model.commit', save), saved)
    const inspected = await call(readOnly, 'model.inspect',
      { model: { source: saved.data.source, source_sha256: saved.data.source_sha256 } })
    assert.equal(inspected.data.source.revision, saved.data.revision)
  })

test('real texture render, verified artifact, restart and cancellation', { timeout: 240000 }, async t => {
  const a = await workspace(t), b = await workspace(t)
  const entry = archive ? await extractAgent(archive, a.dir) : sourceEntry
  const directory = path.dirname(entry)
  const wrapper = path.join(a.dir, '启动探针.mjs'), pidFile = path.join(a.dir, 'pid')
  await fs.writeFile(wrapper, 'import fs from "node:fs"; fs.writeFileSync(' + JSON.stringify(pidFile) +
    ', String(process.pid)); await import(' + JSON.stringify(pathToFileURL(entry).href) + ');')
  const env = { ...process.env }
  if (archive) {
    // Exercise resolution from the extracted package instead of developer machine bindings.
    for (const key of Object.keys(env)) {
      if (key.startsWith('NBTCREATOR_RENDER_') || ['ELECTRON_RUN_AS_NODE', 'NBTCREATOR_NODE', 'NBTCREATOR_NODE_IS_ELECTRON',
        'NBTCREATOR_BROWSER', 'NBTCREATOR_PLAYWRIGHT_MODULE', 'PLAYWRIGHT_BROWSERS_PATH'].includes(key)) delete env[key]
    }
    const launcher = path.resolve(directory, '../..', 'NBTCreator-MCP.cmd')
    const command = '"' + launcher + '" --workspace "' + a.dir + '"'
    const launch = spawn(process.env.ComSpec || 'cmd.exe', ['/d', '/s', '/c', '"' + command + '"'],
      { windowsVerbatimArguments: true, windowsHide: true, env, cwd: b.dir })
    const exit = new Promise(resolve => launch.once('close', resolve))
    t.after(() => { if (launch.exitCode === null) launch.kill() })
    launch.stderr.on('data', chunk => process.stderr.write(chunk))
    const frames = lines(launch.stdout, maxResponse)
    send(launch.stdin, { id: 1, method: 'initialize', params: { protocolVersion: '2025-11-25', capabilities: {},
      clientInfo: { name: 'windows-entry-test', version } } }, maxRequest)
    assert.equal(JSON.parse((await frames.next()).value).result.serverInfo.name, 'nbtcreator')
    launch.stdin.end()
    assert.equal(await exit, 0)
  }
  const client = connect(t, a.dir, [], { args: [wrapper, '--workspace', a.dir], env,
    onDiagnostic: chunk => process.stderr.write(chunk) })
  const other = connect(t, b.dir, [], { args: [entry, '--workspace', b.dir], env })
  const cameras = path.join(a.model, '审阅 机位.json')
  const views = [{ id: 'overview', role: 'whole', eye: [70, 42, -20], target: [24, 7, 24] }]
  const raw = JSON.stringify(views)
  await fs.writeFile(cameras, raw, 'utf8')
  const args = { source: path.relative(a.dir, a.source), source_sha256: sha(await fs.readFile(a.source)),
    cameras: path.relative(a.dir, cameras), cameras_sha256: sha(raw), width: 320, height: 200 }
  assert.equal((await call(client, 'render.model', { ...args, cameras_sha256: '0'.repeat(64) })).error.code, 'INPUT_CHANGED')
  assert.equal((await call(other, 'render.model', { ...args, source: a.source, cameras })).error.code, 'WORKSPACE_ACCESS_DENIED')
  const longCameras = path.join(a.model, '取消 机位.json')
  const longViews = JSON.stringify(Array.from({ length: 24 }, (_, index) => ({ ...views[0], id: 'view_' + index })))
  await fs.writeFile(longCameras, longViews)
  const cancelled = new AbortController()
  let settled
  const receipt = call(client, 'render.model', {
    ...args, cameras: longCameras, cameras_sha256: sha(longViews)
  }, { signal: cancelled.signal, timeout: 140000 }).then(
    value => { settled = { value }; return settled },
    error => { settled = { error }; return settled }
  )
  const renderRoot = path.join(a.dir, 'nbt_models/_workspaces/mcp/renders')
  let rendererPid
  try {
    await until(async () => {
      if (settled) throw Error('Render stopped before cancellation: ' + JSON.stringify(settled.value ?? settled.error?.message))
      const directories = await fs.readdir(renderRoot).catch(() => [])
      for (const directory of directories) {
        const output = path.join(renderRoot, directory)
        const pid = await fs.readFile(path.join(output, '.render.lock'), 'utf8').catch(() => '')
        if (pid) { rendererPid = Number(pid); return true }
      }
      return false
    }, 500)
  } finally {
    cancelled.abort(new Error('fixture cancellation'))
    await receipt
  }
  assert.match(settled.error?.message ?? '', /fixture cancellation/)
  await until(() => {
    try { process.kill(rendererPid, 0); return false } catch (error) { return error.code === 'ESRCH' }
  })
  assert.deepEqual(await client.request('ping'), {})
  const result = await call(client, 'render.model', args, { timeout: 140000 })
  assert.equal(result.ok, true, JSON.stringify(result.error))
  const image = result.data.artifacts.find(item => item.name === 'overview.png')
  const manifest = result.data.artifacts.find(item => item.name === 'render_manifest.json')
  assert.equal(result.data.source_sha256, args.source_sha256)
  assert.equal(result.data.cameras_sha256, args.cameras_sha256)
  const read = async (artifact, conn = client) => (await conn.request('resources/read', { uri: artifact.uri })).contents[0]
  const page = await read(image)
  const png = Buffer.from(page.blob, 'base64')
  assert.equal(sha(png), image.sha256)
  assert.equal(png.readUInt32BE(16), 320)
  assert.equal(png.readUInt32BE(20), 200)
  const report = JSON.parse((await read(manifest)).text)
  assert.equal(report.status, 'complete')
  assert.ok(report.frontend_sha256)
  assert.ok(report.browser_version)
  assert.deepEqual(report.cleanup, { browser_closed: true, server_closed: true })
  await assert.rejects(read(image, other), { code: 'ARTIFACT_NOT_FOUND' })
  process.kill(Number(await fs.readFile(pidFile, 'utf8')))
  await until(() => client.status().state === 'unavailable')
  assert.deepEqual(await read(image), page)
  assert.equal(client.status().generation, 2)
  assert.equal(sha(await fs.readFile(a.source)), args.source_sha256)
  await fs.appendFile(path.join(a.dir, image.path), 'changed')
  await assert.rejects(read(image), { code: 'ARTIFACT_CHANGED' })
  await client.close()
  await other.close()
})

async function extractAgent(file, dir) {
  const verify = execFileSync(python, [path.join(root, 'scripts/release/portable-archive.py'), 'unpack',
    '--source', path.resolve(file), '--output', path.join(dir, '外部发布 介质')], settings)
  const installed = JSON.parse(verify).directory
  assert.equal((await fs.readdir(installed)).includes('NBTCreator.exe'), false)
  const viewer = path.join(installed, '.agents/skills/minecraft-nbt-modeler/assets/viewer')
  assert.deepEqual((await fs.readdir(path.join(viewer, 'node_modules'))).sort(), ['playwright', 'playwright-core'])
  return path.join(installed, 'scripts/mcp/server.mjs')
}
