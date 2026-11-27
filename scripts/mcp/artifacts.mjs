import { createHash, randomUUID } from 'node:crypto'
import { createReadStream } from 'node:fs'
import fs from 'node:fs/promises'
import path from 'node:path'
import { engineScript, runPython } from './python.mjs'
import { failure } from './stdio.mjs'

const digestPattern = '[0-9a-f]{64}'
const digestRegex = new RegExp('^' + digestPattern + '$')
const filePattern = '[A-Za-z0-9_-]{1,128}\\.(?:json|png)'
const artifactUri = new RegExp('^nbtcreator-artifact://render/([a-f0-9-]{36})/(' + filePattern + ')\\?sha256=(' + digestPattern + ')$')
const fileName = new RegExp('^' + filePattern + '$')
const manifestName = 'render_manifest.json'
const mimeType = name => name.endsWith('.png') ? 'image/png' : 'application/json'
const renderRoot = 'nbt_models/_workspaces/mcp/renders'
const maxArtifact = 16 * 1024 * 1024
const hash = bytes => createHash('sha256').update(bytes).digest('hex')

function inside(parent, target) {
  const relative = path.relative(parent, target)
  return relative && relative !== '..' && !relative.startsWith('..' + path.sep) && !path.isAbsolute(relative)
}

async function checkedFile(workspace, input, { parent = path.join(workspace, 'nbt_models'), alias = workspace } = {}) {
  if (typeof input !== 'string' || input.length > 1000) throw failure('INVALID_PATH', '文件路径无效')
  let candidate = path.resolve(workspace, input)
  if (inside(alias, candidate)) candidate = path.join(workspace, path.relative(alias, candidate))
  if (!inside(parent, candidate)) throw failure('WORKSPACE_ACCESS_DENIED', '文件须位于当前工作区的 nbt_models 内')
  const file = await fs.realpath(candidate).catch(() => null)
  if (file && !inside(parent, file)) throw failure('WORKSPACE_ACCESS_DENIED', '文件须位于当前工作区的 nbt_models 内')
  if (!file || !(await fs.stat(file)).isFile()) {
    throw failure('FILE_UNAVAILABLE', '文件不存在或无法在当前工作区访问')
  }
  return file
}

async function readBytes(file) {
  const handle = await fs.open(file, 'r')
  try {
    const { size } = await handle.stat()
    if (size > maxArtifact) throw failure('ARTIFACT_TOO_LARGE', '单个 MCP 产物不得超过 16 MiB')
    const buffer = Buffer.allocUnsafe(size + 1)
    let offset = 0
    while (offset < buffer.length) {
      const { bytesRead } = await handle.read(buffer, offset, buffer.length - offset, offset)
      if (!bytesRead) break
      offset += bytesRead
    }
    if (offset !== size) throw failure('ARTIFACT_CHANGED', '读取期间产物大小变化')
    return buffer.subarray(0, size)
  } finally { await handle.close() }
}

async function fileHash(file, signal) {
  const digest = createHash('sha256')
  for await (const chunk of createReadStream(file, { signal })) digest.update(chunk)
  return digest.digest('hex')
}

function artifact(workspace, directory, name, digest) {
  if (!fileName.test(name) || !digestRegex.test(digest)) throw failure('INVALID_ARTIFACT', '渲染产物名称或 SHA256 无效')
  return {
    uri: 'nbtcreator-artifact://render/' + path.basename(directory) + '/' + name + '?sha256=' + digest,
    path: path.relative(workspace, path.join(directory, name)).split(path.sep).join('/'),
    name, sha256: digest, mimeType: mimeType(name)
  }
}

function entries(manifest) {
  if (manifest.status !== 'complete' || !Array.isArray(manifest.images) || !manifest.images.length) {
    throw failure('RENDER_INCOMPLETE', '渲染批次没有完整产物')
  }
  return new Map(manifest.images.flatMap(row => [[row.image, row.sha256], [row.metadata, row.metadata_sha256]]))
}

async function renderDirectory(workspace, id, create) {
  // Check each existing ancestor before making a directory. Do not follow
  // junctions in the workspace's MCP output tree.
  let directory = workspace
  for (const part of renderRoot.split('/')) {
    directory = path.join(directory, part)
    if (create) await fs.mkdir(directory).catch(error => { if (error.code !== 'EEXIST') throw error })
    if (path.relative(directory, await fs.realpath(directory))) {
      throw failure('WORKSPACE_ACCESS_DENIED', 'MCP 产物目录不能使用目录重定向')
    }
  }
  return path.join(directory, id)
}

export async function renderModel(workspace, alias, args, signal) {
  const source = await checkedFile(workspace, args.source, { alias })
  const cameras = await checkedFile(workspace, args.cameras, { alias })
  if (!/\.(?:snbt|nbt|gz|json)$/i.test(source) || !/\.json$/i.test(cameras)) {
    throw failure('INVALID_PATH', '渲染仅接收已有模型和 JSON 机位文件')
  }
  if ((await fs.stat(cameras)).size > 512 * 1024) throw failure('REQUEST_TOO_LARGE', '相机文件超过 512 KiB')
  const cameraBytes = await readBytes(cameras)
  if (cameraBytes.length > 512 * 1024) throw failure('REQUEST_TOO_LARGE', '相机文件超过 512 KiB')
  if (await fileHash(source, signal) !== args.source_sha256 || hash(cameraBytes) !== args.cameras_sha256) {
    throw failure('INPUT_CHANGED', '建筑源或机位文件已变化')
  }
  const views = JSON.parse(cameraBytes)
  if (!Array.isArray(views) || !views.length || views.length > 64) throw failure('INVALID_ARGUMENTS', '相机文件须含 1～64 个机位')
  const directory = await renderDirectory(workspace, randomUUID(), true)
  const result = await runPython(workspace, [engineScript('nbt_task.py'), 'render', '--source', source, '--cameras', cameras,
    '--output', directory, '--width', String(args.width ?? 960), '--height', String(args.height ?? 640),
    '--quality', args.quality ?? 'balanced'], { signal, tree: true })
  if (result.code !== 0 || result.data.status !== 'complete') throw failure('RENDER_FAILED', '实纹理出图失败')
  const manifestFile = await checkedFile(workspace, path.join(directory, manifestName), { parent: directory })
  const raw = await readBytes(manifestFile)
  const manifest = JSON.parse(raw)
  if (manifest.source_sha256 !== args.source_sha256 || manifest.cameras_sha256 !== args.cameras_sha256) {
    throw failure('INPUT_CHANGED', '出图回执与请求中的建筑源或相机 SHA256 不符')
  }
  const files = [artifact(workspace, directory, manifestName, hash(raw))]
  for (const [name, digest] of entries(manifest)) files.push(artifact(workspace, directory, name, digest))
  return { source_sha256: manifest.source_sha256, geometry_sha256: manifest.geometry_sha256,
    cameras_sha256: manifest.cameras_sha256, width: manifest.width, height: manifest.height, artifacts: files }
}

export async function readArtifact(workspace, uri) {
  const match = typeof uri === 'string' && artifactUri.exec(uri)
  if (!match) throw failure('ARTIFACT_NOT_FOUND', 'MCP 产物引用无效')
  const [, id, name, expected] = match
  try {
    const directory = await renderDirectory(workspace, id, false)
    if (path.relative(directory, await fs.realpath(directory))) throw failure('ARTIFACT_NOT_FOUND', 'MCP 产物目录无效')
    const raw = await readBytes(await checkedFile(workspace, path.join(directory, manifestName), { parent: directory }))
    const registered = entries(JSON.parse(raw))
    if (name !== manifestName && !registered.has(name)) throw failure('ARTIFACT_NOT_FOUND', '渲染清单没有该产物')
    const data = name === manifestName ? raw : await readBytes(await checkedFile(workspace, path.join(directory, name), { parent: directory }))
    if (hash(data) !== expected || (name !== manifestName && registered.get(name) !== expected)) {
      throw failure('ARTIFACT_CHANGED', '产物 SHA256 已变化，请重新生成')
    }
    return { uri, mimeType: mimeType(name), ...(name.endsWith('.png') ? { blob: data.toString('base64') } : { text: data.toString('utf8') }) }
  } catch (error) {
    if (error.code?.startsWith('ARTIFACT_')) throw error
    throw failure('ARTIFACT_NOT_FOUND', '当前工作区没有可读取的完整产物')
  }
}
