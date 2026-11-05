const catalog=require('../.agents/skills/minecraft-nbt-modeler/tool-catalog.json')
function validateParameter(value,s,field='parameter'){
  if(s.anyOf){for(const branch of s.anyOf){try{validateParameter(value,branch,field);return}catch{}}throw Error('Invalid operation parameter alternatives: '+field)}
  if(Array.isArray(s.type)){for(const type of s.type){try{validateParameter(value,{...s,type},field);return}catch{}}throw Error('Invalid operation parameter type: '+field)}
  const type=s.type,valid={null:value===null,integer:Number.isSafeInteger(value),number:typeof value==='number'&&Number.isFinite(value),boolean:typeof value==='boolean',string:typeof value==='string',array:Array.isArray(value),object:!!value&&typeof value==='object'&&!Array.isArray(value)}
  if(type&&valid[type]===false)throw Error('Invalid operation parameter type: '+field+' requires '+type)
  if(s.enum&&!s.enum.includes(value))throw Error('Invalid operation parameter choice: '+field+' must be '+s.enum.join('/'))
  if(['integer','number'].includes(type)&&(value<(s.minimum??-Infinity)||value>(s.maximum??Infinity)||s.exclusiveMinimum!==undefined&&value<=s.exclusiveMinimum))throw Error('Operation parameter outside limits')
  if(type==='object'){const props=s.properties??{};if((s.required??[]).some(k=>!Object.hasOwn(value,k)))throw Error('Missing nested operation parameter: '+field);if(s.additionalProperties===false&&Object.keys(value).some(k=>!Object.hasOwn(props,k)))throw Error('Unknown nested operation parameter: '+field+' only accepts '+Object.keys(props).join('/'));for(const [k,v]of Object.entries(value))if(props[k])validateParameter(v,props[k],field+'.'+k)}
  if(type==='array'){if(value.length<(s.minItems??0)||value.length>(s.maxItems??1000000))throw Error('Invalid operation parameter length: '+field);for(const item of value)validateParameter(item,s.items??{},field+'[]')}
}
function validateOperation(op){
 const schema=Object.hasOwn(catalog.operation_parameters,op.kind)?catalog.operation_parameters[op.kind]:null
 if(!schema)throw Error('Unknown operation')
 for(const [key,value]of Object.entries(op))if(schema.properties[key])validateParameter(value,schema.properties[key],key)
 function geometry(spec,depth=0){if(depth>16||!spec||typeof spec!=='object'||Array.isArray(spec))throw Error('Invalid geometry nesting');if(!Object.hasOwn(catalog.shapes,spec.shape))throw Error('Unknown geometry shape');if(catalog.geometry_parameters[spec.shape])validateParameter(spec,catalog.geometry_parameters[spec.shape]);for(const child of spec.children??[])geometry(child,depth+1)}
 if(op.kind==='geometry')geometry(op.geometry)
 const required=[...(schema.required??[])],rule=schema.mode_requirements
 if(rule){const mode=op[rule.field]??rule.default;if(!Object.hasOwn(rule.choices,mode))throw Error('Unknown operation mode');required.push(...rule.choices[mode])}
 if(op.kind==='selection_replace'&&(op.selection??'connected')!=='surface')required.push('seed_position')
 if(required.some(key=>!Object.hasOwn(op,key)))throw Error('Missing operation parameter (XYZ bounds or mode fields)')
}
module.exports={validateOperation,validateParameter}
