import {createHash, randomUUID} from 'node:crypto'
import fs from 'node:fs/promises'
import path from 'node:path'

const methods = new Set(['inspect', 'claim', 'release', 'plan_merge', 'save_draft'])
const imageLimit = 64 * 1024 * 1024
const png = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10])

export function createAuthoringRoutes({workspace, outputRoot, body, json, invoke}) {
  const images = new Map()
  const prefix = '/__detail__/authoring/'
  const register = row => {
    const token = createHash('sha256').update(JSON.stringify([row.path, row.sha256])).digest('hex')
    if (images.size >= 2048 && !images.has(token)) images.delete(images.keys().next().value)
    images.set(token, {path: row.path, sha256: row.sha256})
    return {...row, url: prefix + 'image/' + token}
  }

  async function readImage(row) {
    const root = await fs.realpath(workspace)
    const file = await fs.realpath(path.resolve(root, row.path))
    const relative = path.relative(root, file)
    if (!relative || relative === '..' || relative.startsWith('..' + path.sep) || path.isAbsolute(relative)) throw Error('图像超出工作区')
    const stat = await fs.stat(file)
    if (!stat.isFile() || stat.size > imageLimit) throw Error('图像无效或过大')
    const bytes = await fs.readFile(file)
    if (bytes.length > imageLimit || createHash('sha256').update(bytes).digest('hex') !== row.sha256) throw Error('图像已变化')
    if (bytes.subarray(0, 8).equals(png)) return [bytes, 'image/png']
    if (bytes[0] === 255 && bytes[1] === 216 && bytes[2] === 255) return [bytes, 'image/jpeg']
    throw Error('图像格式无效')
  }

  return async (req, res, url) => {
    if (!url.pathname.startsWith(prefix)) return false
    const action = url.pathname.slice(prefix.length)
    if (req.method === 'GET' && action.startsWith('image/')) {
      const row = images.get(action.slice(6))
      if (!row) throw Error('图像尚未登记或已失效')
      const [bytes, type] = await readImage(row)
      res.setHeader('Content-Type', type)
      res.setHeader('X-Content-Type-Options', 'nosniff')
      res.setHeader('Cache-Control', 'no-store')
      res.end(bytes)
      return true
    }
    if (req.method !== 'POST' || !methods.has(action)) {
      json(res, {error: '未知制作运行操作'}, 404)
      return true
    }
    const input = await body(req, 256 * 1024)
    if (action !== 'inspect' && input.params?.package_id !== 'root') throw Error('桌面只执行一级的合模和发布操作')
    if (action === 'save_draft' && input.params?.technical_trial !== undefined) throw Error('桌面保存需要完整的候选审阅证据')
    const request = {protocol_version: 1, method: 'authoring.' + action, request_id: input.request_id, params: input.params}
    const directory = path.join(outputRoot, 'system')
    await fs.mkdir(directory, {recursive: true})
    const file = path.join(directory, 'authoring-' + randomUUID() + '.json')
    await fs.writeFile(file, JSON.stringify(request), {flag: 'wx'})
    try {
      const reply = await invoke(['authoring', '--workspace', workspace, '--request', file])
      if (action === 'inspect' && reply.ok) {
        const run = reply.data
        if (run.draft) run.draft.absolute_source = path.resolve(workspace, run.draft.source)
        const stale = new Set(run.reference_issues.map(row => row.id))
        if (run.references) run.references.images = run.references.images.map(row => stale.has(row.id) ? row : register(row))
        for (const review of run.reviews ?? []) {
          for (const side of Object.values(review.renders)) {
            side.images = Object.fromEntries(Object.entries(side.images).map(([key, row]) => [key, register(row)]))
          }
        }
      }
      json(res, reply)
    } finally {
      await fs.unlink(file).catch(() => {})
    }
    return true
  }
}
