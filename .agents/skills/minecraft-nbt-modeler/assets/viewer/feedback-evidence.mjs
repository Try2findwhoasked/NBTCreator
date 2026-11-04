import fs from 'node:fs/promises'
import path from 'node:path'
import {createHash, randomUUID} from 'node:crypto'

const digest = bytes => createHash('sha256').update(bytes).digest('hex')
const relative = (file, directory) => path.relative(directory, file).split(path.sep).join('/')

export async function updateCommentIndex(binding, record, feedbackFile) {
  let version = binding.version_dir || path.dirname(binding.source)
  if (!binding.version_dir) while (['master','masters','runtime','parts','delivery'].includes(path.basename(version))) version=path.dirname(version)
  const directory=path.join(version,'修改意见'), target=path.join(directory,'评论索引.json')
  await fs.mkdir(directory,{recursive:true})
  let index={schema_version:1,paths_relative_to:'index_file',records:[]}
  try { index=JSON.parse(await fs.readFile(target,'utf8')) } catch(error){if(error.code!=='ENOENT')throw error}
  if(index.schema_version!==1||!Array.isArray(index.records))throw new Error('评论索引格式无效，未覆盖')
  const item={source:relative(binding.source,directory),source_sha256:binding.source_sha256,
    geometry_sha256:binding.geometry_sha256,kind:binding.kind==='3d'?'3d':'image',
    feedback_file:relative(feedbackFile,directory),feedback_sha256:digest(await fs.readFile(feedbackFile)),
    evidence_index:relative(feedbackFile+'.evidence.json',directory),
    notes:record.notes.map(note=>({id:note.id,status:note.status,text:note.text,anchors:note.anchors??(note.point?[{kind:'image',number:note.number,...note.point}]:[])})),
    updated_at:record.updated_at??null}
  index.records=index.records.filter(entry=>entry.feedback_file!==item.feedback_file)
  index.records.push(item)
  const temporary=target+'.'+randomUUID()+'.tmp'
  await fs.writeFile(temporary,JSON.stringify(index,null,2)+'\n',{flag:'wx'});await fs.rename(temporary,target)
  return target
}

// A sidecar preserves the original feedback and snapshot bytes. Paths in this
// index are relative to the feedback JSON, so moving a workspace needs no rewrite.
export async function archiveFeedbackEvidence(binding, record, feedbackFile) {
  let version = binding.version_dir || path.dirname(binding.source)
  if (!binding.version_dir) {
    while (['master','masters','runtime','parts','delivery'].includes(path.basename(version))) version = path.dirname(version)
  }
  const base = path.dirname(feedbackFile)
  const directory = path.join(version, '修改意见', '证据', binding.source_sha256)
  const files = []
  const originalBinding=record.binding??binding
  if(originalBinding.source_sha256!==binding.source_sha256||originalBinding.geometry_sha256!==binding.geometry_sha256)throw new Error('原意见绑定与当前模型版本不符')
  const sourceBytes = await fs.readFile(binding.source)
  if (digest(sourceBytes) !== binding.source_sha256) throw new Error('原建筑已变化，不能归档意见证据')
  files.push({role:'source', path:relative(binding.source,base), sha256:binding.source_sha256})
  let previous = {files:[]}
  try { previous = JSON.parse(await fs.readFile(feedbackFile+'.evidence.json','utf8')) } catch (error) { if(error.code!=='ENOENT')throw error }
  async function archive(role, original, sha256, current) {
    if (!/^[a-f0-9]{64}$/.test(sha256 || '')) throw new Error('意见证据缺少文件哈希')
    let bytes
    try {
      const stat = await fs.lstat(original)
      if (!stat.isFile() || stat.isSymbolicLink() || stat.size > 256*1024*1024) throw new Error('意见证据须为不超过256MiB的普通文件')
      bytes = await fs.readFile(original)
    } catch (error) {
      if (error.code !== 'ENOENT') throw error
      const saved = previous.files.find(item => item.role===role && item.sha256===sha256)
      if (saved) bytes = await fs.readFile(path.resolve(base,saved.path))
      else if(current)bytes=await fs.readFile(current)
      else throw new Error('意见引用文件缺失，请先恢复文件：'+original)
    }
    if (digest(bytes)!==sha256) throw new Error('意见引用文件已变化，未覆盖原证据：'+original)
    const extension = path.extname(original).replace(/[^.a-zA-Z0-9]/g,'').slice(0,12)
    const target = path.join(directory,sha256+extension)
    await fs.mkdir(directory,{recursive:true})
    try { await fs.writeFile(target,bytes,{flag:'wx'}) }
    catch(error) { if(error.code!=='EEXIST')throw error; if(digest(await fs.readFile(target))!==sha256)throw new Error('已归档证据被修改') }
    files.push({role, original_path:original, path:relative(target,base), sha256})
  }
  if (binding.kind==='3d') await archive('snapshot',originalBinding.snapshot,originalBinding.snapshot_sha256,
    binding.snapshot_sha256===originalBinding.snapshot_sha256?binding.snapshot:null)
  else await archive('image',originalBinding.image,originalBinding.image_sha256,
    binding.image_sha256===originalBinding.image_sha256?binding.image:null)
  for(const note of record.notes) for(const ref of note.references || []) await archive('reference:'+note.id+':'+ref.sha256,ref.path,ref.sha256)
  const sidecar = {schema_version:1, paths_relative_to:'feedback_file',source_sha256:binding.source_sha256,geometry_sha256:binding.geometry_sha256,files}
  const target=feedbackFile+'.evidence.json',temporary=target+'.'+randomUUID()+'.tmp'
  await fs.writeFile(temporary,JSON.stringify(sidecar,null,2)+'\n',{flag:'wx'})
  await fs.rename(temporary,target)
  return sidecar
}
