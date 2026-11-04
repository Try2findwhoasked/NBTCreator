// Persist only bounded provenance, never passage content, local paths or credentials.
export function referenceSources(value){
 if(value===undefined)return []
 if(!Array.isArray(value)||value.length>16)throw Error('参考来源数量无效')
 return value.map(item=>{
  if(!item||!['asset','knowledge'].includes(item.kind)||typeof item.label!=='string'||!item.label.trim()||item.label.length>150||typeof item.id!=='string'||item.id.length>256||!/^R(?:[1-9]|1[0-6])$/.test(item.citation)||!/^[a-f0-9]{64}$/.test(item.sha256))throw Error('参考来源记录无效')
  const clean={kind:item.kind,label:item.label,id:item.id,citation:item.citation,sha256:item.sha256}
  if(item.kind==='knowledge'){if(![item.line_start,item.line_end].every(n=>Number.isSafeInteger(n)&&n>0)||item.line_start>item.line_end||typeof item.heading!=='string'||item.heading.length>250||typeof item.clipped!=='boolean')throw Error('引用资料行号无效');Object.assign(clean,{heading:item.heading,line_start:item.line_start,line_end:item.line_end,clipped:item.clipped})}
  else{if(!/^[a-f0-9]{32}$/.test(item.asset_id)||!Array.isArray(item.size)||item.size.length!==3||!item.size.every(n=>Number.isInteger(n)&&n>0&&n<=64))throw Error('引用资产记录无效');Object.assign(clean,{asset_id:item.asset_id,size:[...item.size]})}
  return clean
 })
}
