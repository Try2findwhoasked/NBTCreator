const catalog=require('../.agents/skills/minecraft-nbt-modeler/tool-catalog.json')
const {operationBase}=require('./workbench-contract.cjs')
const object=v=>v&&typeof v==='object'&&!Array.isArray(v)
function material(value){
 if(!object(value)||Object.keys(value).some(key=>!['Name','Properties'].includes(key))||typeof value.Name!=='string')return value
 const properties=value.Properties??{}
 if(!object(properties)||Object.entries(properties).some(([key,value])=>!/^[a-z0-9_]+$/.test(key)||typeof value!=='string'||!/^[a-z0-9_]+$/.test(value)))return value
 const entries=Object.entries(properties).sort(([a],[b])=>a.localeCompare(b))
 return value.Name+(entries.length?'['+entries.map(([k,v])=>k+'='+v).join(',')+']':'')
}
function materials(value){
 if(Array.isArray(value))return value.map(materials)
 if(!object(value))return value
 return Object.fromEntries(Object.entries(value).map(([key,value])=>[key,['state','slab_state','stair_state'].includes(key)?material(value):key==='from_states'&&Array.isArray(value)?value.map(material):key==='palette'&&Array.isArray(value)?value.map(entry=>object(entry)&&Object.hasOwn(entry,'Name')?material(entry):materials(entry)):materials(value)]))
}
function operation(value){
 const op=structuredClone(value)
 if(op.common!==undefined){
  if(!object(op.common)||Object.keys(op.common).some(key=>!['label','classification','lo','hi','enabled'].includes(key)))throw Error('工具common只允许公共数据字段，不能携带权限或未知字段')
  for(const [key,value]of Object.entries(op.common)){if(op[key]!==undefined&&JSON.stringify(op[key])!==JSON.stringify(value))throw Error('工具common与顶层字段冲突：'+key);op[key]=value}
  delete op.common
 }
 if(op.type!==undefined&&Object.hasOwn(catalog.tools,op.type)){if(op.kind!==undefined&&op.kind!==op.type)throw Error('工具kind与type冲突');op.kind=op.type;delete op.type}
 if(op.kind===undefined&&op.state!==undefined&&Array.isArray(op.lo)&&Array.isArray(op.hi)&&Object.keys(op).every(key=>['lo','hi','state','label','classification','enabled'].includes(key)))op.kind='box'
 return op
}
function boxes(rows,palette,defaultClassification){
 if(!Array.isArray(rows)||rows.length>128)throw Error('紧凑区域最多128项')
 if(Array.isArray(palette))palette=palette.map(material)
 if(palette!==undefined&&(!Array.isArray(palette)||!palette.length||palette.length>64||palette.some(s=>typeof s!=='string'||!s.length||s.length>250)))throw Error('紧凑材质表无效')
 const result=[]
 for(const row of rows){
  if(!Array.isArray(row)||![7,8].includes(row.length)||!row.slice(0,6).every(Number.isSafeInteger))throw Error('紧凑区域须为6个整数坐标、材质和可选归属')
  const state=Number.isInteger(row[6])&&palette?palette[row[6]]:material(row[6]),classification=row[7]??defaultClassification
  if(typeof state!=='string'||!state.length||!['body','wall','inherit'].includes(classification))throw Error('紧凑区域材质或归属无效')
  const next={kind:'box',lo:row.slice(0,3),hi:row.slice(3,6),state,classification}
  if(next.lo.some((v,i)=>v>next.hi[i]))throw Error('紧凑区域最小坐标不能超过最大坐标')
  // Only consecutive boxes whose union is exactly a cuboid may be combined.
  const last=result.at(-1)
  const axis=last&&last.state===state&&last.classification===classification?[0,1,2].find(a=>[0,1,2].every(i=>i===a||last.lo[i]===next.lo[i]&&last.hi[i]===next.hi[i])&&(last.hi[a]+1===next.lo[a]||next.hi[a]+1===last.lo[a])):undefined
  if(axis!==undefined){last.lo[axis]=Math.min(last.lo[axis],next.lo[axis]);last.hi[axis]=Math.max(last.hi[axis],next.hi[axis])}else result.push(next)
 }
 return result
}
function normalizeReply(value,mode,context){
 if(!object(value))return value
 const result=structuredClone(value),target=mode==='small_structure'?(result.settings_patch??result):result
 if(mode==='structure'&&object(result.settings_patch))result.settings_patch=materials(result.settings_patch)
 if(object(target)&&target.boxes!==undefined){
  if(target.operations!==undefined||target.steps!==undefined||target.blocks!==undefined)throw Error('紧凑区域不能与其他工具序列同时返回')
  target.operations=boxes(target.boxes,target.palette,mode==='selection_edit'?'inherit':'body');delete target.boxes;delete target.palette
 }else if(object(target)&&target.palette!==undefined)throw Error('材质表须与紧凑区域一起返回')
 if(Array.isArray(target.operations))target.operations=target.operations.map((value,i)=>{
  if(!object(value))return value
  const op=operation(value)
  if(!Object.hasOwn(catalog.tools,op.kind))return op
  return {...materials(op),label:op.label??catalog.tools[op.kind][0]+' '+(i+1),classification:op.classification??(mode==='selection_edit'||['pattern','weathering','replace'].includes(op.kind)?'inherit':'body')}
 })
 if(mode!=='component'&&result.summary===undefined)result.summary='参数候选，待本地检查'
 if(mode==='selection_edit'&&result.coordinate_space===undefined)result.coordinate_space='local'
 if(mode==='workbench'&&object(result.operation_patch)){
  const base=operationBase(context),patch=result.operation_patch
  if(patch.baseline===undefined)patch.baseline=base.baseline
  if(Array.isArray(patch.changes))for(const change of patch.changes)if(object(change)){if(object(change.set))change.set=materials(change.set);if(change.expected===undefined&&Number.isSafeInteger(change.step))change.expected=base.steps[change.step-1]?.expected}
 }
 if(mode==='workbench'&&object(result.project_patch))for(const key of ['layout','circulation','name','theme','purpose','footprint','style','ceiling','floor','wall','props','preserve','extras'])if(Array.isArray(result.project_patch[key])||object(result.project_patch[key]))result.project_patch[key]=JSON.stringify(result.project_patch[key])
 return result
}
module.exports={normalizeReply}
