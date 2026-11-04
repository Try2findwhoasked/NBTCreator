const catalog=require('../.agents/skills/minecraft-nbt-modeler/tool-catalog.json')
function validateOperation(op){
 const schema=catalog.operation_parameters[op.kind]
 if(!schema)throw Error('Unknown operation')
 function check(value,s){
  const type=s.type,valid={integer:Number.isSafeInteger(value),number:typeof value==='number'&&Number.isFinite(value),boolean:typeof value==='boolean',string:typeof value==='string',array:Array.isArray(value),object:!!value&&typeof value==='object'&&!Array.isArray(value)}
  if(type&&valid[type]===false)throw Error('Invalid operation parameter type')
  if(s.enum&&!s.enum.includes(value))throw Error('Invalid operation parameter choice')
  if(['integer','number'].includes(type)&&(value<(s.minimum??-Infinity)||value>(s.maximum??Infinity)||s.exclusiveMinimum!==undefined&&value<=s.exclusiveMinimum))throw Error('Operation parameter outside limits')
  if(type==='array'){if(value.length<(s.minItems??0)||value.length>(s.maxItems??1000000))throw Error('Invalid operation parameter length');for(const item of value)check(item,s.items??{})}
 }
 for(const [key,value]of Object.entries(op))if(schema.properties[key])check(value,schema.properties[key])
 const required=[...(schema.required??[])],rule=schema.mode_requirements
 if(rule){const mode=op[rule.field]??rule.default;if(!Object.hasOwn(rule.choices,mode))throw Error('Unknown operation mode');required.push(...rule.choices[mode])}
 if(op.kind==='selection_replace'&&(op.selection??'connected')!=='surface')required.push('seed_position')
 if(required.some(key=>!Object.hasOwn(op,key)))throw Error('Missing operation parameter (XYZ bounds or mode fields)')
}
module.exports={validateOperation}
