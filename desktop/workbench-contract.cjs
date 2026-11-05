const {validateOperation}=require('./operation-parameters.cjs')
const catalog=require('../.agents/skills/minecraft-nbt-modeler/tool-catalog.json')
const {createHash}=require('node:crypto')
const fields=['buildingShape','layout','circulation','name','theme','purpose','footprint','style','ceiling','floor','wall','props','preserve','extras']
const SHA=/^[a-f0-9]{64}$/
const own=(value,allowed)=>value&&typeof value==='object'&&!Array.isArray(value)&&Object.keys(value).every(key=>allowed.includes(key))
function fingerprint(value){
 const stable=v=>Array.isArray(v)?v.map(stable):v&&typeof v==='object'?Object.fromEntries(Object.keys(v).sort().map(key=>[key,stable(v[key])])):v
 return createHash('sha256').update(JSON.stringify(stable(value))).digest('hex')
}
function cleanContext(input){
 if(!input||!input.project||!Array.isArray(input.project.size))throw Error('需要当前提示词方案')
 const project={size:[...input.project.size]}
 for(const key of fields)if(typeof input.project[key]==='string')project[key]=input.project[key].slice(0,4000)
 if(!project.size||project.size.length!==3||!project.size.every(v=>Number.isInteger(v)&&v>0&&v<=4096))throw Error('设计尺寸无效');
 if(input.task==='draft'&&input.existing_model)throw Error('完整初稿必须是新建任务');
 if(input.baseline_binding!==undefined&&!SHA.test(input.baseline_binding))throw Error('方案绑定指纹无效')
 if(input.operations!==undefined&&(!Array.isArray(input.operations)||input.operations.length>128))throw Error('当前工具序列最多128项，不能静默截断')
 return {project,task:input.task==='draft'?'draft':'controls',existing_model:input.existing_model===true,operations:structuredClone(input.operations??[]),...(input.baseline_binding?{baseline_binding:input.baseline_binding}:{})}
}
function operationBase(context){return {baseline:fingerprint(context),steps:context.operations.map((op,i)=>({step:i+1,expected:fingerprint(op)}))}}
function mergeOperationPatch(result,context){
 if(!own(result,['summary','project_patch','operation_patch'])||context.task==='draft')throw Error('步骤增量仅支持已有方案的控件修改，不能与完整序列同时返回')
 const patch=result.operation_patch,base=operationBase(context)
 if(!own(patch,['baseline','changes'])||patch.baseline!==base.baseline)throw Error('工具增量不属于当前方案基线，请重新生成')
 if(!Array.isArray(patch.changes)||!patch.changes.length||patch.changes.length>16)throw Error('工具增量须包含1到16项修改')
 const operations=structuredClone(context.operations),seen=new Set()
 for(const change of patch.changes){
  if(!own(change,['step','expected','set'])||!Number.isInteger(change.step)||change.step<1||change.step>operations.length||seen.has(change.step))throw Error('增量目标步骤无效或重复')
  seen.add(change.step)
  if(change.expected!==base.steps[change.step-1].expected)throw Error('增量原步骤指纹不匹配，请重新生成')
  const op=operations[change.step-1]
  const allowed=[...Object.keys(catalog.common),...Object.keys(catalog.operation_parameters[op.kind]?.properties??{})].filter(key=>!['overwrite','write_group','max_writes'].includes(key))
  if(!own(change.set,allowed)||!Object.keys(change.set).length)throw Error('增量只能修改工具参数，不能改变工具类型、覆盖权限、预算或执行字段')
  for(const [key,value]of Object.entries(change.set)){
   const sample=op[key]??catalog.common[key]??catalog.tools[op.kind]?.[1]?.[key]
   const valid=Array.isArray(sample)?Array.isArray(value):sample&&typeof sample==='object'?value&&typeof value==='object'&&!Array.isArray(value):(sample===undefined?({array:Array.isArray(value),integer:Number.isSafeInteger(value),number:typeof value==='number'&&Number.isFinite(value),object:!!value&&typeof value==='object'&&!Array.isArray(value),string:typeof value==='string',boolean:typeof value==='boolean'}[catalog.operation_parameters[op.kind]?.properties[key]?.type]===true):typeof value===typeof sample)&&(typeof value!=='number'||Number.isFinite(value))
   if(!valid)throw Error('增量工具参数类型无效：'+key)
   if(key==='state'&&!/^(?:minecraft:)?[a-z0-9_]+(?:\[[a-z0-9_=,]+\])?$/.test(value))throw Error('增量需要有效的方块状态')
   if(key==='label'&&(!value.trim()||value.length>250))throw Error('增量步骤名称须为1到250字')
  }
  Object.assign(op,structuredClone(change.set))
 }
 return {summary:result.summary,...(result.project_patch!==undefined?{project_patch:result.project_patch}:{}),operations}
}
function validateWorkbench(result,context){
 const incremental=result?.operation_patch!==undefined
 if(incremental)result=mergeOperationPatch(result,context)
 if(!result||typeof result!=='object'||Array.isArray(result)||Object.keys(result).some(k=>!['summary','project_patch','operations'].includes(k))||typeof result.summary!=='string'||result.summary.length>4000)throw Error('AI控件方案格式无效')
 const patch=result.project_patch??{}
 if(!patch||Array.isArray(patch)||typeof patch!=='object'||Object.keys(patch).some(k=>!fields.includes(k)&&k!=='size'))throw Error('AI只能调整设计字段，不能修改源路径、阶段、保护或批准')
 for(const [key,value]of Object.entries(patch))if(key!=='size'&&(typeof value!=='string'||value.length>4000))throw Error('AI设计文字字段无效')
 if(patch.buildingShape){if(!catalog.building_shapes[patch.buildingShape])throw Error('建筑形状无效');if(context.existing_model&&patch.buildingShape!==context.project.buildingShape)throw Error('已有模型形状不可由AI改写')}
 if(context.task==='draft'){for(const key of ['name','theme','purpose','layout','circulation','style','ceiling','floor','wall','props'])if(typeof patch[key]!=='string'||!patch[key].trim())throw Error('完整初稿缺少设计字段：'+key);if(!Array.isArray(result.operations)||!result.operations.length)throw Error('完整初稿需要初始构造工具步骤')}
 if(patch.size){if(!Array.isArray(patch.size)||patch.size.length!==3||!patch.size.every(v=>Number.isInteger(v)&&v>0&&v<=4096))throw Error('设计尺寸无效');if(context.existing_model&&JSON.stringify(patch.size)!==JSON.stringify(context.project.size))throw Error('已有模型尺寸不可由AI改写')}
 if(result.operations!==undefined){
  const limit=incremental?128:64
  if(!Array.isArray(result.operations)||result.operations.length>limit)throw Error('工具序列最多'+limit+'项')
  const size=patch.size??context.project.size
  for(const [index,op] of result.operations.entries()){
   const step='第'+(index+1)+'步',token=value=>typeof value==='string'&&/^[a-z_]{1,40}$/i.test(value)?JSON.stringify(value):'（缺失或类型无效）'
   if(!op||typeof op!=='object'||Array.isArray(op))throw Error(step+'需要工具对象')
   if(!Object.hasOwn(catalog.tools,op.kind))throw Error(step+' kind='+token(op.kind)+' 不支持；只能使用工具清单的规范键，例如box、hollow_box、geometry、pattern；不得自造工具名')
   if(!['body','wall','inherit'].includes(op.classification))throw Error(step+' classification='+token(op.classification)+' 无效；只支持body（主体）、wall（墙层）、inherit（保留归属），可省略由脚本补齐；不要填写structure/decor/opening等用途')
   if(typeof op.label!=='string'||!op.label.trim())throw Error(step+'缺少有效步骤名称label')
   if(op.enabled!==undefined&&typeof op.enabled!=='boolean')throw Error('工具 enabled 开关须为布尔值')
   if(op.enabled===false)continue
   try{validateOperation(op)}catch(error){throw Error(step+'（'+op.kind+'）参数无效：'+error.message)}
   if(op.kind==='geometry'&&(!op.geometry||!catalog.shapes[op.geometry.shape]))throw Error('几何工具需要支持的形状定义')
   if(op.kind!=='auto_floor'&&op.kind!=='beam'){for(const key of ['lo','hi'])if(!Array.isArray(op[key])||op[key].length!==3||!op[key].every(Number.isInteger))throw Error('工具需要整数XYZ选区');if(op.lo.some((v,i)=>v<0||v>op.hi[i]||op.hi[i]>=size[i]))throw Error('AI工具超出方案尺寸')}
  }
 }
 return result
}
module.exports={cleanContext,validateWorkbench,operationBase}
