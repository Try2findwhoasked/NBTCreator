import { spawn } from 'node:child_process'
import { setTimeout as delay } from 'node:timers/promises'
import { failure, isId, isObject, lines, maxPending, maxRequest, maxResponse, protocolVersions, send } from './stdio.mjs'

export function createMcpClient({ executable, args, cwd, env, version, expectedServiceVersion, onStatus = () => {}, onDiagnostic = () => {} }) {
  let active, closed = false, serial = 0, generation = 0
  let status = { state: 'idle', generation }
  const retiring = new Set()

  function publish(state, fields) {
    status = { state, generation, ...fields }
    onStatus(status)
  }

  function end(session, error) {
    if (session.ended) return
    session.ended = true
    for (const task of session.pending.values()) task.finish(error)
    if (active === session) {
      active = null
      if (!closed) publish('unavailable', { error: { code: error.code, message: error.message } })
    }
  }

  function retire(session) {
    if (session.exited) return session.exit
    if (!session.closing) {
      session.child.stdin.end()
      session.closing = (async () => {
        await Promise.race([session.exit, delay(5000, undefined, { ref: false })])
        if (!session.exited) session.child.kill()
        await Promise.race([session.exit, delay(2000, undefined, { ref: false })])
      })()
      retiring.add(session.closing)
      void session.closing.finally(() => retiring.delete(session.closing))
    }
    return session.closing
  }

  function rpc(session, method, params, { signal, timeout = 90000 } = {}) {
    if (session.ended || active !== session) return Promise.reject(failure('SERVICE_EXITED', 'MCP 服务已退出'))
    if (signal?.aborted) return Promise.reject(signal.reason)
    if (session.pending.size >= maxPending) return Promise.reject(failure('QUEUE_FULL', 'MCP 请求队列已满'))
    const id = ++serial
    return new Promise((resolve, reject) => {
      const finish = (error, data) => {
        clearTimeout(timer)
        signal?.removeEventListener('abort', abort)
        session.pending.delete(id)
        if (error) reject(error); else resolve(data)
      }
      const cancel = problem => {
        if (method !== 'initialize') {
          try { send(session.child.stdin, { method: 'notifications/cancelled', params: { requestId: id } }, maxRequest) } catch {}
        }
        finish(problem)
      }
      const abort = () => cancel(signal.reason)
      const timer = setTimeout(() => cancel(failure('TIMEOUT', 'MCP 请求超时')), timeout)
      session.pending.set(id, { finish })
      signal?.addEventListener('abort', abort, { once: true })
      try { send(session.child.stdin, { id, method, params }, maxRequest) } catch (error) { finish(error) }
    })
  }

  function start() {
    if (closed) return Promise.reject(failure('SERVICE_CLOSED', 'MCP 工作区会话已关闭'))
    if (active) return active.ready
    const child = spawn(executable, args, { cwd, env, shell: false, windowsHide: true })
    const session = { child, pending: new Map(), ended: false }
    active = session
    generation++
    publish('starting')
    session.exit = new Promise(resolve => child.once('close', () => { session.exited = true; resolve() }))
    child.stdin.on('error', () => {})
    child.stderr.setEncoding('utf8')
    child.stderr.on('data', onDiagnostic)
    child.on('error', error => end(session, failure('SERVICE_START_FAILED', '启动 MCP 服务失败：' + error.code)))
    child.on('close', () => end(session, failure('SERVICE_EXITED', 'MCP 服务已退出。本次调用没有自动重试。')))
    void (async () => {
      for await (const raw of lines(child.stdout, maxResponse)) {
        const message = JSON.parse(raw)
        if (!isObject(message) || message.jsonrpc !== '2.0') throw Error('Invalid MCP response')
        if (!isId(message.id)) continue
        const task = session.pending.get(message.id)
        if (!task) continue
        if (message.error) task.finish(failure(message.error.data?.code ?? 'MCP_ERROR', message.error.message, message.error.data))
        else if (Object.hasOwn(message, 'result')) task.finish(null, message.result)
        else throw Error('MCP response has no result')
      }
    })().catch(() => {
      end(session, failure('INVALID_RESPONSE', 'MCP 响应格式无效'))
      void retire(session)
    })
    session.ready = (async () => {
      try {
        const hello = await rpc(session, 'initialize', {
          protocolVersion: protocolVersions[0], capabilities: {}, clientInfo: { name: 'nbtcreator-desktop', version }
        }, { timeout: 18000 })
        if (!protocolVersions.includes(hello.protocolVersion) || !hello.capabilities?.tools || hello.serverInfo?.name !== 'nbtcreator' ||
          expectedServiceVersion && hello.serverInfo.version !== expectedServiceVersion) {
          throw failure('PROTOCOL_VERSION_UNSUPPORTED', 'MCP 服务握手或版本不匹配')
        }
        send(child.stdin, { method: 'notifications/initialized' }, maxRequest)
        publish('ready', { protocolVersion: hello.protocolVersion, serviceVersion: hello.serverInfo.version })
        return hello
      } catch (error) {
        end(session, error)
        void retire(session)
        throw error
      }
    })()
    return session.ready
  }

  return {
    start,
    status: () => status,
    async request(method, params = {}, options) {
      // Only a later request starts a replacement instance. In-flight writes
      // can have a durable receipt even if their transport result was lost.
      options?.signal?.throwIfAborted()
      const readiness = start(), session = active
      await readiness
      return rpc(session, method, params, options)
    },
    async close() {
      closed = true
      const session = active
      if (session) {
        end(session, failure('SERVICE_CLOSED', 'MCP 工作区会话已关闭'))
        void retire(session)
      }
      await Promise.allSettled(retiring)
    }
  }
}
