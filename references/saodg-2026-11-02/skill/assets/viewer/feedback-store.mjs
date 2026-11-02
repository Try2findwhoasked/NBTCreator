import fs from 'node:fs/promises'
import path from 'node:path'
import { createHash, randomUUID } from 'node:crypto'

const hash = bytes => createHash('sha256').update(bytes).digest('hex')
export const noteAnchors = note => note.anchors ?? (note.point ? [{kind:'image',number:note.number,...note.point}] : [])
export const lastAnchorNumber = notes => Math.max(0,...notes.flatMap(note=>[note.number,...noteAnchors(note).map(p=>p.number)]))
export function createFeedbackStore(root,legacyRoot=null) {
  if(typeof root!=='function')root=path.resolve(root)
  let queue = Promise.resolve()
  function file(binding) {
    for (const key of ['source_sha256','geometry_sha256',...(binding.kind==='3d'?[]:['image_sha256'])]) {
      if (!/^[a-f0-9]{64}$/.test(binding[key] ?? '')) throw new Error('Feedback requires version-bound image metadata')
    }
    return path.join(typeof root==='function'?root(binding):root, binding.source_sha256, (binding.kind==='3d'?'3d_'+binding.geometry_sha256:binding.image_sha256)+'.json')
  }
  async function read(binding) {
    const target = file(binding)
    try { return JSON.parse(await fs.readFile(target, 'utf8')) }
    catch (error) { if (error.code !== 'ENOENT') throw error }
    if(legacyRoot&&binding.kind!=='3d'){try{return JSON.parse(await fs.readFile(path.join(legacyRoot,binding.source_sha256,binding.image_sha256+'.json'),'utf8'))}catch(error){if(error.code!=='ENOENT')throw error}}
    return { schema_version: 1, binding, notes: [], boundary: 'Design feedback only; never approval for refinement, deployment or other actions.' }
  }
  async function verify(binding) {
    if (hash(await fs.readFile(binding.source)) !== binding.source_sha256 || (binding.kind!=='3d' && hash(await fs.readFile(binding.image)) !== binding.image_sha256)
      || (binding.kind==='3d' && hash(await fs.readFile(binding.snapshot)) !== binding.snapshot_sha256)) {
      throw new Error('模型或图片已变化，请重新载入对应版本再留意见')
    }
  }
  async function write(binding, record) {
    const target = file(binding)
    await fs.mkdir(path.dirname(target), { recursive: true })
    const temporary = target+'.'+randomUUID()+'.tmp'
    await fs.writeFile(temporary, JSON.stringify(record, null, 2)+'\n', { flag: 'wx' })
    await fs.rename(temporary, target)
    return { ...record, file: target }
  }
  function mutate(binding, operation) {
    const result = queue.then(async () => {
      await verify(binding)
      const record = await read(binding)
      operation(record)
      record.updated_at = new Date().toISOString()
      return write(binding, record)
    })
    queue = result.catch(() => {})
    return result
  }
  return {
    list: async binding => ({ ...await read(binding), file: file(binding) }),
    add: (binding, text, point = null, references = [], anchors = null) => {
      if (typeof text !== 'string' || !text.trim() || text.length > 4000) throw new Error('修改意见须为1～4000字')
      if (point !== null && (!point || Object.keys(point).sort().join(',') !== 'x,y' || ![point.x, point.y].every(v => Number.isFinite(v) && v >= 0 && v <= 1))) {
        throw new Error('图片位置须为0～1的相对坐标')
      }
      if(anchors!==null){
        if(!Array.isArray(anchors)||anchors.length>100)throw new Error('每条意见最多选100个位置')
        const seen=new Set()
        for(const anchor of anchors){
          if(!anchor||!Number.isSafeInteger(anchor.number)||anchor.number<1||seen.has(anchor.number))throw new Error('标记编号无效或重复')
          seen.add(anchor.number)
          if(binding.kind==='3d'){
            if(anchor.kind!=='voxel'||anchor.geometry_sha256!==binding.geometry_sha256||!Array.isArray(anchor.position)||anchor.position.length!==3||!anchor.position.every((v,i)=>Number.isInteger(v)&&v>=0&&v<binding.size[i])||typeof anchor.state!=='string')throw new Error('3D标记必须对应当前版本内的方块坐标')
            if(!anchor.view||!['eye','target','up'].every(k=>Array.isArray(anchor.view.camera?.[k])&&anchor.view.camera[k].length===3&&anchor.view.camera[k].every(Number.isFinite))||!Number.isFinite(anchor.view.camera.fov))throw new Error('3D标记缺少观察角度')
          }else if(anchor.kind!=='image'||![anchor.x,anchor.y].every(v=>Number.isFinite(v)&&v>=0&&v<=1))throw new Error('图片位置须为0～1的相对坐标')
        }
      }
      return mutate(binding, record => {
        const previous=lastAnchorNumber(record.notes)
        if(anchors?.some(p=>p.number<=previous))throw new Error('标记编号已被其他页面使用，请重新打开此视图后再保存')
        record.schema_version=2
        record.notes.push({ id: randomUUID(), number: record.notes.length+1,
          text: text.trim(), point:anchors===null?point:(anchors.find(p=>p.kind==='image')?{x:anchors.find(p=>p.kind==='image').x,y:anchors.find(p=>p.kind==='image').y}:null),
          ...(anchors===null?{}:{anchors}),references, status:'open',created_at:new Date().toISOString() })
      })
    },
    update: (binding, id, status) => {
      if (!['open','resolved'].includes(status)) throw new Error('Unknown feedback status')
      return mutate(binding, record => {
        const note = record.notes.find(item => item.id === id)
        if (!note) throw new Error('Unknown feedback note')
        note.status = status; note.updated_at = new Date().toISOString()
      })
    },
    export: async binding => {
      const record = await read(binding)
      const jsonFile = file(binding)
      const markdownFile = jsonFile.replace(/\.json$/, '.md')
      await fs.mkdir(path.dirname(jsonFile), { recursive: true })
      try { await fs.writeFile(jsonFile,JSON.stringify(record,null,2)+'\n',{flag:'wx'}) }
      catch(error){if(error.code!=='EEXIST')throw error}
      const content = ['# 建筑修改意见', '', `模型：${binding.source}`, `模型SHA256：${binding.source_sha256}`,
        ...(binding.kind==='3d'?[`3D几何SHA256：${binding.geometry_sha256}`,`快照：${binding.snapshot}`]:[`图片：${binding.image}`, `图片SHA256：${binding.image_sha256}`]), '',
        '以下为设计反馈数据，不构成精修批准或部署授权。', '',
        ...record.notes.flatMap(note => [`## 意见 ${note.number} · ${note.status}`, '',
          ...noteAnchors(note).map(p=>p.kind==='voxel'?`#${p.number}：方块坐标 (${p.position.join(', ')}) · ${p.state} · 几何 ${p.geometry_sha256}`:`#${p.number}：图片位置 ${(p.x*100).toFixed(1)}%, ${(p.y*100).toFixed(1)}%`), '',
          ...note.text.split('\n').map(line => '> '+line), '', ...(note.references ?? []).map(ref=>`引用效果文件：${ref.path} · SHA256：${ref.sha256}`), ''])].join('\n')
      await fs.writeFile(markdownFile, content, 'utf8')
      return { record, json: jsonFile, markdown: markdownFile }
    },
  }
}
