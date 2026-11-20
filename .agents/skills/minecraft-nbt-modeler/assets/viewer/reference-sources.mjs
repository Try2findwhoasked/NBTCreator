const sha=value=>typeof value==='string'&&/^[a-f0-9]{64}$/.test(value)
const text=(value,limit)=>typeof value==='string'&&[...value].length<=limit
function webLocation(item){
 const {source_url,verification,content_kind,accessed_at}=item.bibliography??{}
 let url
 try{if(text(source_url,2048))url=new URL(source_url)}catch{}
 if(url?.protocol!=='https:'||url.username||url.password||[...url.searchParams.keys()].some(key=>/auth|token|pass|secret|key|session|signature|credential|code|jwt/i.test(key))||!sha(item.passage_sha256)||
   !['app_opened','host_reported'].includes(verification)||!['excerpt','summary'].includes(content_kind)||
   !text(accessed_at,40)||!Number.isFinite(Date.parse(accessed_at)))throw Error('网页引用的出处无效')
 return {source_url,verification,content_kind,accessed_at}
}

export function referenceSources(value){
 if(value===undefined)return []
 if(!Array.isArray(value)||value.length>16)throw Error('参考来源数量无效')
 return value.map(item=>{
  if(!item||!['asset','knowledge'].includes(item.kind)||!text(item.label,250)||!item.label.trim()||!text(item.id,288)||!item.id||!/^R(?:[1-9]|1[0-6])$/.test(item.citation)||!sha(item.sha256))throw Error('参考来源记录无效')
  const clean={kind:item.kind,label:item.label,id:item.id,citation:item.citation,sha256:item.sha256}
  if(item.kind==='knowledge'){
   if(!text(item.heading,250))throw Error('引用章节无效')
   clean.heading=item.heading
   if(item.reference_type==='web'){
    Object.assign(clean,{reference_type:'web',passage_sha256:item.passage_sha256,bibliography:webLocation(item)})
   }else{
    if(![item.line_start,item.line_end].every(n=>Number.isSafeInteger(n)&&n>0)||item.line_start>item.line_end||typeof item.clipped!=='boolean')throw Error('引用资料行号无效')
    Object.assign(clean,{line_start:item.line_start,line_end:item.line_end,clipped:item.clipped})
    if(item.reference_type==='architecture_library'){
     if(!sha(item.manifest_sha256)||!sha(item.passage_sha256)||!text(item.library_name,150))throw Error('书库引用的出处无效')
     Object.assign(clean,{reference_type:item.reference_type,manifest_sha256:item.manifest_sha256,passage_sha256:item.passage_sha256,library_name:item.library_name})
    }else if(item.reference_type!==undefined)throw Error('未知引用资料类型')
   }
  }
  else{if(!/^[a-f0-9]{32}$/.test(item.asset_id)||!Array.isArray(item.size)||item.size.length!==3||!item.size.every(n=>Number.isInteger(n)&&n>0&&n<=64))throw Error('引用资产记录无效');Object.assign(clean,{asset_id:item.asset_id,size:[...item.size]})}
  return clean
 })
}
