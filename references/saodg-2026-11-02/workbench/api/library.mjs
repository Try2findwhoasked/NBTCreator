// Local catalog/selection metadata only. Structure geometry is never written here.
import fs from 'node:fs/promises'
import path from 'node:path'
import { createHash, randomUUID } from 'node:crypto'

export function structureLibrary({ workspace, invoke, asset, json, dataRoot }) {
  const stateFile = path.join(dataRoot, 'structure_library.json')
  let listing, pending, writer = Promise.resolve()
  const covers = new Map()
  const idFor = source => createHash('sha256').update(source).digest('hex')
  async function catalog(refresh = false) {
    if (pending) return pending
    if (listing && !refresh) return listing
    pending = invoke(['catalog','--cache',path.join(dataRoot,'catalog_metadata.json')]).then(data => {
      listing = { ...data, models: data.models.map(model => ({ ...model, id: idFor(model.source) })) }
      covers.clear()
      return listing
    }).finally(() => { pending = null })
    return pending
  }
  async function readState() {
    try {
      const value = JSON.parse(await fs.readFile(stateFile, 'utf8'))
      return { favorites: Array.isArray(value.favorites) ? value.favorites.filter(x=>typeof x==='string') : [],
        selected: Array.isArray(value.selected) ? value.selected.filter(x=>typeof x==='string') : [] }
    } catch (error) {
      if (error.code === 'ENOENT') return { favorites: [], selected: [] }
      throw new Error('结构清单读取失败，原文件已保留：' + error.message)
    }
  }
  async function update(input) {
    const action = async () => {
      const data = await catalog(), state = await readState()
      if (!['favorites', 'selected'].includes(input.collection)) throw new Error('未知结构清单')
      if (input.clear === true && input.collection === 'selected') state.selected = []
      else {
        const model = data.models.find(model => model.id === input.id)
        if (!model || typeof input.enabled !== 'boolean') throw new Error('结构已不在目录中，请刷新列表')
        const set = new Set(state[input.collection])
        if (input.enabled) set.add(model.source); else set.delete(model.source)
        state[input.collection] = [...set]
      }
      await fs.mkdir(path.dirname(stateFile), { recursive: true })
      const temp = stateFile + '.' + randomUUID() + '.tmp'
      try { await fs.writeFile(temp, JSON.stringify({ schema_version: 1, ...state }, null, 2)); await fs.rename(temp, stateFile) }
      finally { await fs.rm(temp, { force: true }) }
      return state
    }
    const result = writer.then(action)
    writer = result.catch(() => {})
    return result
  }
  return { catalog, async handle(req, res, url, readBody) {
    if (req.method === 'GET' && url.pathname === '/api/library') {
      const data = await catalog(url.searchParams.get('refresh') === '1')
      await writer
      json(res, { ...data, state: await readState(), state_file: stateFile, root: path.join(workspace, 'nbt_models') })
    } else if (req.method === 'POST' && url.pathname === '/api/library/state') json(res, await update(await readBody(req)))
    else if (req.method === 'GET' && url.pathname.startsWith('/api/library/cover/')) {
      const id = url.pathname.split('/').at(-1), data = await catalog()
      const model = data.models.find(model => model.id === id)
      if (!model) throw new Error('未知结构，请刷新目录')
      const stat = await fs.stat(model.source)
      if (stat.size !== model.file_size || Math.abs(stat.mtimeMs - model.modified_ns / 1e6) > 2) throw new Error('结构已变化，请刷新目录')
      if (!covers.has(id)) covers.set(id, invoke(['cover', '--source', model.source, '--geometry', model.geometry_sha256,
        '--cache', path.join(dataRoot, 'library_thumbs')]).then(cover => ({
        thumbnail: cover.thumbnail ? asset(cover.thumbnail) : null, image: cover.image ? asset(cover.image) : null
      })).catch(error => { covers.delete(id); throw error }))
      json(res, await covers.get(id))
    } else return false
    return true
  } }
}
