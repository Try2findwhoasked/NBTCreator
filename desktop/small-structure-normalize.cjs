// Tolerate model formatting differences; geometry still passes the strict local
// and Python validators after normalization and coordinate translation.
function normalizeSmallStructure(result,context){
 if(!result||typeof result!=='object'||['code','script','python','shell'].some(k=>k in result))throw Error('需要部件数据，不能返回执行代码')
 if(result.coordinate_space&&!['local','relative'].includes(result.coordinate_space))throw Error('部件必须使用当前选区的相对坐标')
 const patch=result.settings_patch??result
 const size=context.hi.map((v,i)=>v-context.lo[i]+1)
 const vector=v=>Array.isArray(v)&&v.length===3?v.map(n=>typeof n==='string'&&/^-?\d+$/.test(n)?Number(n):n):v
 let operations=patch.operations??patch.steps
 if(!operations&&Array.isArray(patch.blocks))operations=patch.blocks.map(b=>({kind:'box',lo:b.pos??b.position,hi:b.pos??b.position,state:b.state??b.block??b.material}))
 if(!Array.isArray(operations)||!operations.length||operations.length>128)throw Error('部件需要1到128步；较多相邻方块可合并为box')
 const fallback=context.materials?.find(m=>!/(?:^|:)air$/.test(m.state))?.state||'stone_bricks'
 operations=operations.map((source,i)=>{
  if(!source||typeof source!=='object'||['code','script','python','shell'].some(k=>k in source))throw Error('构件步骤须为数据')
  const kind={fill:'box',block:'box',carve:'box'}[source.kind]??source.kind??'box'
  let state=source.kind==='carve'?'air':source.state??source.block??source.material??fallback
  if(state&&typeof state==='object'&&typeof state.Name==='string')state=state.Name+(state.Properties?'['+Object.entries(state.Properties).map(([k,v])=>k+'='+v).join(',')+']':'')
  const op={kind,label:source.label||'AI 部件步骤 '+(i+1),classification:source.classification||'body',state}
  if(kind==='beam'){
   op.start=vector(source.start);op.end=vector(source.end);op.width=Number(source.width??1)
   if(!op.start||!op.end)throw Error('梁需要start和end端点')
   const r=Math.floor(op.width/2)
   op.lo=vector(source.lo)??op.start.map((v,j)=>Math.min(v,op.end[j])-r)
   op.hi=vector(source.hi)??op.start.map((v,j)=>Math.max(v,op.end[j])+r)
  }else{op.lo=vector(source.lo??source.pos??source.position);op.hi=vector(source.hi??source.pos??source.position);if(kind==='frame')op.thickness=Number(source.thickness??1)}
  return op
 })
 return {coordinate_space:'local',summary:result.summary||'已整理AI部件，待本地检查与预览',settings_patch:{lo:vector(patch.lo)??[0,0,0],hi:vector(patch.hi)??size.map(v=>v-1),operations}}
}
module.exports={normalizeSmallStructure}
