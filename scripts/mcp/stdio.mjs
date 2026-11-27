import { TextDecoder } from 'node:util'

export const protocolVersions = ['2025-11-25', '2025-06-18', '2025-03-26']
export const maxRequest = 8 * 1024 * 1024
export const maxResponse = 32 * 1024 * 1024
export const maxPending = 8
export const isObject = value => value !== null && typeof value === 'object' && !Array.isArray(value)
export const isId = value => typeof value === 'string' || Number.isSafeInteger(value)
export const failure = (code, message, details) => Object.assign(new Error(message), { code, details })
export function errorCode(error, fallback) {
  if (error.name === 'TimeoutError') return 'TIMEOUT'
  if (error.name === 'AbortError') return 'CANCELLED'
  return typeof error.code === 'string' ? error.code : fallback
}

export async function* lines(stream, limit) {
  const decoder = new TextDecoder('utf-8', { fatal: true })
  let parts = [], size = 0
  for await (const chunk of stream) {
    let from = 0
    while (from < chunk.length) {
      const newline = chunk.indexOf(10, from)
      const part = chunk.subarray(from, newline < 0 ? chunk.length : newline)
      size += part.length
      if (size > limit) throw failure('FRAME_TOO_LARGE', 'MCP JSON line exceeds the transport limit')
      parts.push(part)
      if (newline < 0) break
      yield decoder.decode(Buffer.concat(parts, size))
      parts = []
      size = 0
      from = newline + 1
    }
  }
}

export function send(stream, message, limit) {
  const frame = Buffer.from(JSON.stringify({ jsonrpc: '2.0', ...message }) + '\n')
  if (frame.length - 1 > limit) throw failure('FRAME_TOO_LARGE', 'MCP message exceeds the transport limit')
  if (stream.destroyed || stream.writableEnded || stream.writableLength > limit) {
    throw failure('TRANSPORT_CLOSED', 'MCP transport is closed or its output queue is full')
  }
  stream.write(frame)
}
