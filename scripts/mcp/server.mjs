import fs from 'node:fs/promises'
import path from 'node:path'
import { parseArgs } from 'node:util'
import { root } from '../paths.mjs'
import runtime from '../../desktop/python-runtime.cjs'
import { readArtifact } from './artifacts.mjs'
import { createTools } from './tools.mjs'
import { errorCode, failure, isId, isObject, lines, maxPending, maxRequest, maxResponse, protocolVersions, send } from './stdio.mjs'

const input = process.stdin
const output = process.stdout
const shutdown = new AbortController()
const current = new Map()
const active = new Set()
let stage = 'starting'
let tools
let workspace
let version
let settings
const metadata = JSON.parse(await fs.readFile(path.join(root, 'package.json'), 'utf8'))
runtime.configureRenderRuntime(root, null)
process.env.NBTCREATOR_NODE ??= process.execPath
if (metadata.agentRuntime === true) {
  const viewer = new URL('../../.agents/skills/minecraft-nbt-modeler/assets/viewer/package.json', import.meta.url)
  const pkg = JSON.parse(await fs.readFile(viewer, 'utf8'))
  process.env.NBTCREATOR_PINNED_RENDER = '1'
  process.env.NBTCREATOR_PLAYWRIGHT_VERSION = pkg.dependencies.playwright
}

function close() {
  if (shutdown.signal.aborted) return
  shutdown.abort(failure('TRANSPORT_CLOSED', 'MCP 服务已结束'))
  for (const task of current.values()) task.controller.abort(shutdown.signal.reason)
  input.destroy()
}
process.once('SIGTERM', close)
process.once('SIGINT', close)
output.once('error', close)

function write(id, response) {
  if (shutdown.signal.aborted) return
  try { send(output, { id, ...response }, maxResponse) } catch (error) {
    if (error.code !== 'FRAME_TOO_LARGE') return close()
    try { send(output, { id, error: { code: -32000, message: 'MCP 返回超过 32 MiB' } }, maxResponse) }
    catch { close() }
  }
}
const result = (id, value) => write(id, { result: value })
const rpcError = (id, code, message, data) => write(id, { error: { code, message, data } })

function envelope(value, error, resourceLinks) {
  const content = [{ type: 'text', text: JSON.stringify(value) }]
  if (resourceLinks) for (const { uri, name, mimeType } of resourceLinks) {
    content.push({ type: 'resource_link', uri, name, mimeType })
  }
  return { content, structuredContent: value, isError: error }
}

async function initialize(params) {
  const { values } = parseArgs({ options: {
    workspace: { type: 'string' }, 'allow-write': { type: 'boolean' },
    'package-session': { type: 'string' }, desktop: { type: 'boolean' }
  } })
  if (!values.workspace || (values.desktop && (values['package-session'] || values['allow-write']))) {
    throw failure('INVALID_STARTUP_CONFIG', '使用 --workspace <目录>，可选 --allow-write 或 --package-session <可信 JSON>')
  }
  const workspaceAlias = path.resolve(values.workspace)
  workspace = await fs.realpath(workspaceAlias).catch(() => null)
  if (!workspace || !(await fs.stat(workspace)).isDirectory()) throw failure('INVALID_WORKSPACE', 'MCP 工作区须为已有目录')
  const installation = root.endsWith(path.join('resources', 'app')) ? path.resolve(root, '../..') : root
  if (!path.relative(workspace, root) || !path.relative(workspace, installation)) {
    throw failure('INVALID_WORKSPACE', '请选择独立于程序目录的创作工作区')
  }
  const sessionPath = values['package-session'] ? path.resolve(values['package-session']) : null
  settings = { profile: values.desktop ? 'desktop' : 'agent', allowWrite: Boolean(values['allow-write']), sessionPath }
  tools = await createTools({ workspace, workspaceAlias, ...settings,
    startupSignal: AbortSignal.any([shutdown.signal, AbortSignal.timeout(15000)]) })
  version = protocolVersions.includes(params.protocolVersion) ? params.protocolVersion : protocolVersions[0]
  stage = 'initialized'
  return { protocolVersion: version, serverInfo: { name: 'nbtcreator', version: metadata.version },
    capabilities: { tools: {}, ...(sessionPath ? {} : { resources: {} }) } }
}

async function callTool(params, signal) {
  try {
    const tool = tools.index.get(params.name)
    if (!tool) throw failure('TOOL_UNAVAILABLE', '本会话未开放此工具')
    const { data, ...meta } = await tool.call(params.arguments ?? {}, signal)
    const value = { ok: true, data, error: null, ...meta }
    return envelope(value, false, version === protocolVersions[0] ? data?.artifacts : undefined)
  } catch (error) {
    return envelope({ ok: false, data: null, error: {
      code: errorCode(error, 'TOOL_FAILED'),
      message: String(error.message).slice(0, 1500), retryable: error.retryable === true, details: error.details ?? {}
    } }, true)
  }
}

async function dispatch(message) {
  const { id, method, params = {} } = message
  if (id === undefined) {
    if (method === 'notifications/initialized' && stage === 'initialized') stage = 'ready'
    if (method === 'notifications/cancelled' && isObject(params)) {
      const task = current.get(params.requestId)
      if (task && task.method !== 'initialize') {
        task.cancelled = true
        task.controller.abort(failure('CANCELLED', 'MCP 请求已取消'))
      }
    }
    return
  }
  if (!isObject(params)) return rpcError(id, -32602, 'Invalid params')
  if (method === 'initialize') {
    if (stage !== 'starting') return rpcError(id, -32600, 'MCP session already initialized')
    if (typeof params.protocolVersion !== 'string' || !isObject(params.capabilities) || !isObject(params.clientInfo)) {
      return rpcError(id, -32602, 'Invalid initialize params')
    }
    stage = 'initializing'
    try { result(id, await initialize(params)) }
    catch (error) {
      stage = 'failed'
      rpcError(id, -32001, String(error.message).slice(0, 1500), { code: errorCode(error, 'STARTUP_FAILED') })
    }
    return
  }
  if (method === 'ping' && ['initialized', 'ready'].includes(stage)) return result(id, {})
  if (stage !== 'ready') return rpcError(id, -32001, 'MCP session is not ready')
  if (method === 'tools/list') return result(id, { tools: [...tools.index.values()].map(entry => entry.tool) })
  if (!settings.sessionPath && ['resources/list', 'resources/templates/list'].includes(method)) {
    return result(id, method === 'resources/list' ? { resources: [] } : { resourceTemplates: [] })
  }
  if (method !== 'tools/call' && (method !== 'resources/read' || settings.sessionPath)) {
    return rpcError(id, -32601, 'Method not found')
  }
  if (current.has(id)) return
  if (current.size >= maxPending) return rpcError(id, -32002, 'MCP request queue is full', { code: 'QUEUE_FULL' })
  const controller = new AbortController()
  const task = { controller, method, cancelled: false }
  const signal = AbortSignal.any([controller.signal, AbortSignal.timeout(
    ['render.model', 'render.candidate'].includes(params.name) ? 180000 : 90000
  )])
  current.set(id, task)
  try {
    const value = method === 'tools/call' ? await callTool(params, signal) : { contents: [await readArtifact(workspace, params.uri)] }
    if (!task.cancelled) result(id, value)
  } catch (error) {
    if (!task.cancelled) rpcError(id, -32002, String(error.message).slice(0, 1500), { code: errorCode(error, 'ARTIFACT_READ_FAILED') })
  } finally { current.delete(id) }
}

try {
  for await (const raw of lines(input, maxRequest)) {
    let message
    try { message = JSON.parse(raw) } catch { rpcError(null, -32700, 'Parse error'); continue }
    if (!isObject(message) || message.jsonrpc !== '2.0' || typeof message.method !== 'string' ||
        message.id !== undefined && !isId(message.id)) {
      rpcError(null, -32600, 'Invalid request')
      continue
    }
    const pending = dispatch(message).catch(error => rpcError(message.id ?? null, -32603, String(error.message).slice(0, 1500)))
    active.add(pending)
    void pending.finally(() => active.delete(pending))
  }
} catch (error) {
  if (!shutdown.signal.aborted) process.stderr.write('NBTCreator MCP: ' + error.message + '\n')
} finally {
  close()
  await Promise.allSettled(active)
  await tools?.close()
}
