// Local read-only model viewer. The renderer frontend is attributed in LICENSE.upstream.
import fs from 'node:fs/promises'
import { createReadStream } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { createServer } from 'vite'

const root = path.dirname(fileURLToPath(import.meta.url))
export async function createDevViewerServer({ model, port = 0, quiet = true, apiHandler, modelResolver }) {
  if (model) model = path.resolve(model)
  if (!Number.isInteger(port) || port < 0 || port > 65535) throw new Error('Invalid port')
  if (model) await fs.access(model)
const lodestone = path.resolve(path.dirname(fileURLToPath(import.meta.resolve('@mattzh72/lodestone'))), '..')
const pack = path.join(lodestone, 'assets/default-pack')
const server = await createServer({
  root, appType: 'spa', logLevel: quiet ? 'error' : 'info', cacheDir: path.join(root, 'node_modules/.vite'),
  // Vite interprets port 0 as its default; let automatic batch viewers find a
  // free port while keeping explicit interactive ports strict.
  server: { host: '127.0.0.1', port, strictPort: port !== 0, hmr: !quiet },
  plugins: [{
    name: 'nbt-modeler-local-input',
    configureServer(vite) {
      vite.middlewares.use(async (req, res, next) => {
        try {
        const host = req.headers.host ?? ''
        const origin = req.headers.origin
        if (!/^127\.0\.0\.1:\d+$/.test(host) || (origin && origin !== `http://${host}`) || req.headers['sec-fetch-site'] === 'cross-site') {
          res.statusCode = 403; res.end('Local viewer requests only'); return
        }
        const requestUrl = new URL(req.url, `http://${host}`)
        const pathname = requestUrl.pathname
        if (apiHandler && await apiHandler(req, res, requestUrl)) return
        let target
        if (pathname === '/__nbt_modeler__/model.json') {
          target = modelResolver ? modelResolver(requestUrl.searchParams.get('model_key')) : model
          if (!target) { res.statusCode = 404; res.end('No selected model'); return }
        }
        else if (pathname.startsWith('/__minecraft_builder__/default-pack/')) {
          const relative = decodeURIComponent(pathname.slice('/__minecraft_builder__/default-pack/'.length))
          target = path.resolve(pack, relative)
          if (!target.startsWith(pack + path.sep)) { res.statusCode = 403; res.end(); return }
        } else { next(); return }
        res.setHeader('Cache-Control', 'no-store')
        if (target.endsWith('.json')) res.setHeader('Content-Type', 'application/json')
        if (target.endsWith('.png')) res.setHeader('Content-Type', 'image/png')
        const stream = createReadStream(target)
        stream.on('error', () => { res.statusCode = 404; res.end('Not found') })
        stream.pipe(res)
        } catch (error) { res.statusCode = 400; res.end(error.message) }
      })
    },
  }],
})
  try {
    await server.listen()
    return { url: server.resolvedUrls.local[0], close: () => server.close() }
  } catch (error) {
    await server.close()
    throw error
  }
}
