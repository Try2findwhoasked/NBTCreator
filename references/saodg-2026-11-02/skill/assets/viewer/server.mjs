// Interactive viewer launcher; batch rendering imports the same server implementation.
import { parseArgs } from 'node:util'
import { spawn } from 'node:child_process'
import { createViewerServer } from './viewer-server.mjs'
const { values } = parseArgs({ options: {
  model: { type: 'string' }, port: { type: 'string', default: '5173' }, 'no-open': { type: 'boolean' },
} })
if (!values.model) throw new Error('Usage: node server.mjs --model snapshot.json [--port 5173] [--no-open]')
const viewer = await createViewerServer({ model: values.model, port: Number(values.port), quiet: false })
console.log(JSON.stringify({ url: viewer.url, model: values.model, read_only: true }))
if (!values['no-open']) {
  const command = process.platform === 'win32' ? 'cmd' : process.platform === 'darwin' ? 'open' : 'xdg-open'
  const args = process.platform === 'win32' ? ['/c', 'start', '', viewer.url] : [viewer.url]
  const child = spawn(command, args, { stdio: 'ignore', detached: true, windowsHide: true })
  child.on('error', () => {}); child.unref()
}
async function stop() { await viewer.close(); process.exit(0) }
process.on('SIGINT', stop); process.on('SIGTERM', stop)
