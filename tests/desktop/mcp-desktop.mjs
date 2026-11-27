import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import path from 'node:path'
import { execFileSync } from 'node:child_process'
import { createHash } from 'node:crypto'
import { createRequire } from 'node:module'
import { python, root, skill } from '../../scripts/paths.mjs'

const require = createRequire(path.join(skill, 'assets/viewer/package.json'))
const { _electron } = require('playwright')
const packaged = process.env.NBTCREATOR_TEST_EXE
const executablePath = packaged || require(path.join(root, 'node_modules/electron'))
const build = path.join(root, 'build')
await fs.mkdir(build, { recursive: true })
const output = await fs.mkdtemp(path.join(build, 'mcp-desktop-'))
const workspace = path.join(output, '合成 工作区 一')
const next = path.join(output, '合成 工作区 二')
for (const dir of [workspace, next]) {
  execFileSync(python, ['-B', path.join(root, 'tests/support/make_fixture.py'), path.join(dir, 'nbt_models', '合成 建筑')],
    { encoding: 'utf8', windowsHide: true })
}
const env = { ...process.env, NBTCREATOR_AUTOMATION: '1' }
delete env.ELECTRON_RUN_AS_NODE
const app = await _electron.launch({ executablePath, env, timeout: 60000,
  args: [...(packaged ? [] : [root]), '--workspace', workspace, '--user-data-dir', path.join(output, '用户 配置')] })
try {
  app.process().stderr?.on('data', chunk => process.stderr.write(chunk))
  const page = await app.firstWindow()
  await page.waitForFunction(async () => (await window.nbtDesktop?.mcp.status())?.state === 'ready')
  const initial = await page.evaluate(async () => {
    const mcp = window.nbtDesktop.mcp
    const tools = await mcp.listTools()
    return { info: await window.nbtDesktop.info(), tools: tools.data.map(tool => tool.name),
      invalid: await mcp.callTool({ name: 'shell.exec', requestId: 'forbidden', arguments: {} }),
      injected: await mcp.callTool({ name: 'tasks.list', requestId: 'workspace-escape', arguments: { workspace: 'C:/' } }),
      artifact: await mcp.readArtifact('file:///C:/Windows/not-allowed'),
      candidate: await mcp.callTool({ name: 'candidate.validate', requestId: 'geometry',
        arguments: { mode: 'structure', result: {}, context: {} } }),
      crossFrame: document.querySelector('#viewer')?.contentWindow?.nbtDesktop !== undefined }
  })
  assert.equal(initial.info.workspace, workspace)
  assert.equal(initial.info.frontend, 'production')
  assert.ok(initial.tools.includes('candidate.validate'))
  assert.equal(initial.tools.includes('tasks.create'), false)
  assert.equal(initial.invalid.error.code, 'INVALID_ARGUMENTS')
  assert.equal(initial.injected.error.code, 'INVALID_ARGUMENTS')
  assert.equal(initial.artifact.error.code, 'INVALID_ARGUMENTS')
  assert.equal(initial.candidate.data.nbt_exported, false)
  const model = path.join(workspace, 'nbt_models', '合成 建筑')
  const source = path.join(model, 'synthetic.master.json.gz')
  const cameras = path.join(model, '实图 机位.json')
  const sha = value => createHash('sha256').update(value).digest('hex')
  await fs.writeFile(cameras, JSON.stringify([{ id: 'overview', eye: [70, 42, -20], target: [24, 7, 24] }]))
  const rendered = await page.evaluate(async args => {
    const mcp = window.nbtDesktop.mcp
    const output = await mcp.callTool({ requestId: 'real-render', name: 'render.model', arguments: args })
    if (!output.ok) return output
    const ref = output.data.artifacts.find(item => item.name === 'overview.png')
    return { ref, image: await mcp.readArtifact(ref.uri) }
  }, { source, cameras, source_sha256: sha(await fs.readFile(source)), cameras_sha256: sha(await fs.readFile(cameras)),
    width: 320, height: 200 })
  assert.equal(rendered.image?.ok, true, JSON.stringify(rendered.error ?? rendered.image?.error))
  assert.equal(sha(Buffer.from(rendered.image.data.blob, 'base64')), rendered.ref.sha256)
  if (initial.tools.includes('render.candidate')) {
    const evidence = await page.evaluate(async () => {
      const mcp = window.nbtDesktop.mcp
      const model = { size: [8, 6, 8], kind: 'component', actions: [{ method: 'patch', changes: [
        { pos: [1, 1, 1], before: ['minecraft:air', false], after: ['minecraft:stone_bricks', true] }
      ] }] }
      const candidate = await mcp.callTool({ requestId: 'model-candidate', name: 'model.candidate', arguments: { model } })
      if (!candidate.ok) return candidate
      const candidate_sha256 = candidate.data.candidate_sha256
      const preview = await mcp.callTool({ requestId: 'render-candidate', name: 'render.candidate', arguments: {
        model, candidate_sha256, request_id: crypto.randomUUID(), width: 320, height: 200,
        cameras: [{ id: 'overview', eye: [10, 7, 10], target: [2, 1, 2] }]
      } })
      return { preview, candidate_sha256 }
    })
    assert.equal(evidence.preview?.ok, true, JSON.stringify(evidence.error ?? evidence.preview?.error))
    assert.equal(evidence.preview.data.preview.candidate_sha256, evidence.candidate_sha256)
    assert.equal(evidence.preview.data.preview.approval_created, false)
  }
  // Even if preload is instantiated for a same-origin frame, main rejects it.
  if (initial.crossFrame) {
    const frame = page.frames().find(child => child !== page.mainFrame())
    assert.ok(frame)
    await assert.rejects(frame.evaluate(() => window.nbtDesktop.mcp.listTools()), /Unexpected IPC sender/)
  }
  const cancelled = await page.evaluate(async () => {
    const mcp = window.nbtDesktop.mcp
    const pending = mcp.callTool({ name: 'tasks.list', requestId: 'cancel-me', arguments: {} })
    const requested = await mcp.cancel('cancel-me')
    return { requested, response: await pending }
  })
  assert.equal(cancelled.requested, true)
  assert.equal(cancelled.response.error.code, 'CANCELLED')
  await app.evaluate(({ dialog }, destination) => {
    dialog.showOpenDialog = async () => ({ canceled: false, filePaths: [destination] })
    dialog.showMessageBox = async () => ({ response: 0 })
  }, next)
  const originalUrl = page.url()
  await Promise.all([
    page.waitForURL(url => url.origin !== new URL(originalUrl).origin),
    page.evaluate(() => { void window.nbtDesktop.chooseWorkspace() })
  ])
  await page.waitForFunction(async expected => (await window.nbtDesktop?.info())?.workspace === expected &&
    (await window.nbtDesktop?.mcp.status())?.state === 'ready', next)
  const result = await page.evaluate(async source => window.nbtDesktop.mcp.callTool({ name: 'render.model', requestId: 'old-source',
    arguments: { source, cameras: source, source_sha256: '0'.repeat(64), cameras_sha256: '0'.repeat(64) } }),
  path.join(workspace, 'nbt_models', '合成 建筑', 'synthetic.master.json.gz'))
  assert.equal(result.error.code, 'WORKSPACE_ACCESS_DENIED')
  const oldArtifact = await page.evaluate(uri => window.nbtDesktop.mcp.readArtifact(uri), rendered.ref.uri)
  assert.equal(oldArtifact.error.code, 'ARTIFACT_NOT_FOUND')
  console.log(JSON.stringify({ passed: true, packaged: Boolean(packaged), workspace, switched_to: next }))
} finally { await app.close() }
