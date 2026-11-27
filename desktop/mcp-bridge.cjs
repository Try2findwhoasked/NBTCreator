const path = require('node:path')
const { pathToFileURL } = require('node:url')

const rendererTools = new Set([
  'model.inspect', 'model.candidate', 'model.preview', 'model.commit',
  'prompts.list', 'prompts.get', 'tasks.list', 'tasks.get', 'tasks.discover', 'tasks.revalidate',
  'annotations.scan', 'annotations.collect', 'annotation-tasks.list', 'annotation-tasks.evidence',
  'authoring.inspect', 'authoring.brief', 'authoring.block_state', 'authoring.context',
  'retrieve.search', 'retrieve.source', 'retrieve.read', 'retrieve.bundle', 'candidate.validate', 'render.model', 'render.candidate'
])
const modelTimeout = 85000
const rendererMaxPending = 6
const rendererMaxInput = 7 * 1024 * 1024
const rendererId = /^[A-Za-z0-9_-]{1,128}$/
const failure = (code, message) => Object.assign(Error(message), { code })
const errorResponse = error => ({
  ok: false, data: null, error: {
    code: error.name === 'TimeoutError' ? 'TIMEOUT' : error.name === 'AbortError' ? 'CANCELLED' :
      typeof error.code === 'string' ? error.code : 'MCP_FAILED',
    message: String(error.message).slice(0, 1500), retryable: error.retryable === true, details: error.details ?? {}
  }
})

async function createDesktopMcp({ root, workspace, executable, version, onStatus, onDiagnostic }) {
  const server = path.join(root, 'scripts/mcp/server.mjs')
  const module = await import(pathToFileURL(path.join(root, 'scripts/mcp/client.mjs')).href)
  const client = module.createMcpClient({ executable, args: [server, '--workspace', workspace, '--desktop'],
    cwd: root, env: { ...process.env, ELECTRON_RUN_AS_NODE: '1' }, version, expectedServiceVersion: version, onStatus, onDiagnostic })
  const pending = new Map()
  let scope = new AbortController()
  const request = (method, params, options = {}) => client.request(method, params, {
    ...options, signal: options.signal ? AbortSignal.any([options.signal, scope.signal]) : scope.signal
  })

  async function call(name, args, options) {
    const response = await request('tools/call', { name, arguments: args }, {
      timeout: ['render.model', 'render.candidate'].includes(name) ? 175000 : modelTimeout, ...options
    })
    return response.structuredContent
  }
  const run = async action => {
    try { return await action() } catch (error) { return errorResponse(error) }
  }
  function cancel(id) {
    const controller = pending.get(id)
    if (!controller) return false
    controller.abort(failure('CANCELLED', 'MCP 请求已取消'))
    return true
  }

  return {
    start: client.start,
    status: client.status,
    call,
    names: () => run(async () => {
      const response = await request('tools/list')
      return { ok: true, data: response.tools.filter(tool => rendererTools.has(tool.name)), error: null }
    }),
    rendererCall: input => run(async () => {
      if (!input || Object.keys(input).some(key => !['requestId', 'name', 'arguments'].includes(key)) ||
          typeof input.requestId !== 'string' || !rendererId.test(input.requestId) || !rendererTools.has(input.name) ||
          !input.arguments || typeof input.arguments !== 'object' || Array.isArray(input.arguments)) {
        throw failure('INVALID_ARGUMENTS', 'MCP 请求格式或工具名无效')
      }
      if (Buffer.byteLength(JSON.stringify(input)) > rendererMaxInput) throw failure('REQUEST_TOO_LARGE', 'MCP 请求超过 7 MiB')
      if (pending.has(input.requestId)) throw failure('REQUEST_ID_ACTIVE', 'MCP 请求编号正在使用')
      if (pending.size >= rendererMaxPending) throw failure('QUEUE_FULL', 'MCP 请求队列已满')
      const controller = new AbortController()
      pending.set(input.requestId, controller)
      try { return await call(input.name, input.arguments, { signal: controller.signal }) }
      finally { pending.delete(input.requestId) }
    }),
    readArtifact: uri => run(async () => {
      if (typeof uri !== 'string' || uri.length > 300 || !uri.startsWith('nbtcreator-artifact://render/')) {
        throw failure('INVALID_ARGUMENTS', 'MCP 产物引用无效')
      }
      const response = await request('resources/read', { uri }, { timeout: 20000 })
      return { ok: true, data: response.contents[0], error: null }
    }),
    cancel: id => typeof id === 'string' && rendererId.test(id) && cancel(id),
    cancelAll: () => {
      scope.abort(failure('CANCELLED', 'MCP 工作区请求已取消'))
      scope = new AbortController()
    },
    close: client.close
  }
}

module.exports = { createDesktopMcp, errorResponse }
