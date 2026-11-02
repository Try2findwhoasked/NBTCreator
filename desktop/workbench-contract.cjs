const catalog=require('../.agents/skills/minecraft-nbt-modeler/tool-catalog.json')
const fields=['name','theme','purpose','footprint','style','ceiling','floor','wall','props','preserve','extras']
function cleanContext(input){
 if(!input||!input.project||!Array.isArray(input.project.size))throw Error('需要当前提示词方案')
 const project={size:input.project.size}
 for(const key of fields)if(typeof input.project[key]==='string')project[key]=input.project[key].slice(0,4000)
 return {project,existing_model:input.existing_model===true,operations:Array.isArray(input.operations)?input.operations.slice(0,64):[]}
}
function validateWorkbench(result,context){
 if(!result||typeof result!=='object'||Array.isArray(result)||Object.keys(result).some(k=>!['summary','project_patch','operations'].includes(k))||typeof result.summary!=='string'||result.summary.length>4000)throw Error('AI控件方案格式无效')
 const patch=result.project_patch??{}
 if(!patch||Array.isArray(patch)||typeof patch!=='object'||Object.keys(patch).some(k=>!fields.includes(k)&&k!=='size'))throw Error('AI只能调整设计字段，不能修改源路径、阶段、保护或批准')
 for(const [key,value]of Object.entries(patch))if(key!=='size'&&(typeof value!=='string'||value.length>4000))throw Error('AI设计文字字段无效')
 if(patch.size){if(!Array.isArray(patch.size)||patch.size.length!==3||!patch.size.every(v=>Number.isInteger(v)&&v>0&&v<=4096))throw Error('设计尺寸无效');if(context.existing_model&&JSON.stringify(patch.size)!==JSON.stringify(context.project.size))throw Error('已有模型尺寸不可由AI改写')}
 if(result.operations!==undefined){
  if(!Array.isArray(result.operations)||result.operations.length>64)throw Error('工具序列最多64项')
  const size=patch.size??context.project.size
  for(const op of result.operations){if(!op||!catalog.tools[op.kind]||typeof op.label!=='string'||!op.label.trim()||!['body','wall','inherit'].includes(op.classification))throw Error('AI返回未支持的工具或归属')
   if(op.kind==='geometry'&&(!op.geometry||!catalog.shapes[op.geometry.shape]))throw Error('几何工具需要支持的形状定义')
   if(op.kind!=='auto_floor'&&op.kind!=='beam'){for(const key of ['lo','hi'])if(!Array.isArray(op[key])||op[key].length!==3||!op[key].every(Number.isInteger))throw Error('工具需要整数XYZ选区');if(op.lo.some((v,i)=>v<0||v>op.hi[i]||op.hi[i]>=size[i]))throw Error('AI工具超出方案尺寸')}
  }
 }
 return result
}
module.exports={cleanContext,validateWorkbench}
