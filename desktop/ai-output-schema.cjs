// Provider schema and local validation share one contract; execution still uses the engine validators.
const catalog=require('../.agents/skills/minecraft-nbt-modeler/tool-catalog.json')
const {isDeepStrictEqual}=require('node:util')
const constraints=require('../.agents/skills/minecraft-nbt-modeler/prompt-console/constraint-contract.cjs').create(catalog)
const forbidden=new Set(['overwrite','write_bounds','write_group','max_writes'])
const object=properties=>({type:'object',properties,required:Object.keys(properties),additionalProperties:false})
const array=(items,maxItems,minItems=0)=>({type:'array',items,minItems,maxItems})
const string=(maxLength=250)=>({type:'string',maxLength})
const integer={type:'integer'},number={type:'number'},boolean={type:'boolean'}
const vector=array(integer,3,3),summary={type:'string',minLength:1,maxLength:160}
const fixedVector=(size,schema=vector)=>({...schema,enum:[size]})
const projectSize=(context,bound,schema=vector)=>
 context.existing_model||context.project?.size_policy==='fixed'||bound.size!==undefined?
  fixedVector(context.project.size,schema):schema
const enumeration=values=>({type:typeof values[0],enum:values})
const optional=schema=>({anyOf:[schema,{type:'null'}],_optional:true})
const camera=object({azimuth:{...number,minimum:-180,maximum:180},elevation:{...number,minimum:-90,maximum:90}})
const mapSchema=()=>({...array(object({key:string(),value:string()}),32),_map:true})
const mirrorValues=catalog.operation_parameters.transform_region.properties.mirror.enum
const mirrorSchema=enumeration(mirrorValues.filter(value=>value!==null))
const clearMirror={...object({value:{type:'null'}}),_clearMirror:true}
// Some catalogue arrays specify only the container. Keep their concrete wire shapes here.
const untypedArrays={
 from_states:array(string(),128),offset:vector,centre:array(number,3,3),
 seeds:array(vector,128),patch_size:array(integer,2,2),
 exclude_boxes:array(object({lo:vector,hi:vector}),128),
 palette:array(string(),128),voxels:array(array(integer,4,4),65536)
}
function strictParameter(schema,key,patch=false){
 if(key==='geometry')return {$ref:'#/$defs/geometry'}
 if(key==='slab_overrides')return mapSchema()
 if(key==='mirror')return patch&&mirrorValues.includes(null)?{anyOf:[mirrorSchema,clearMirror]}:mirrorSchema
 if(key==='label')return {...schema,minLength:1,maxLength:80}
 if(schema.anyOf)return {...schema,anyOf:schema.anyOf.map(branch=>strictParameter(branch,key))}
 if(schema.type==='object')return object(Object.fromEntries(Object.entries(schema.properties).map(([name,child])=>{
  const field=strictParameter(child,name)
  return [name,schema.required?.includes(name)?field:optional(field)]
 })))
 if(schema.type==='array')return schema.items?{...schema,items:strictParameter(schema.items)}:{...untypedArrays[key],...schema}
 return schema
}
function sample(value,key=''){
 if(Array.isArray(value))return array(value.length?sample(value[0]):object({lo:vector,hi:vector}),key==='voxels'?65536:128)
 if(value&&typeof value==='object')return object(Object.fromEntries(Object.entries(value).map(([k,v])=>[k,sample(v,k)])))
 if(typeof value==='number')return ['count','iterations','steps','seed','rays','samples','width','thickness','pit_depth','depth','quarter_turns'].includes(key)?integer:number
 if(typeof value==='boolean')return boolean
 return string()
}
function operation(kind,patch=false){
 const contract=catalog.operation_parameters[kind],properties=patch?{}:{kind:enumeration([kind])}
 for(const [key,value]of Object.entries(contract.properties)){
  if(forbidden.has(key))continue
  const schema=strictParameter(value,key,patch)
  const required=!patch&&(['label','classification'].includes(key)||contract.required.includes(key))
  properties[key]=required?schema:optional(schema)
 }
 return object(properties)
}
function geometryDefinition(){return {anyOf:Object.entries(catalog.shapes).map(([shape,defaults])=>catalog.geometry_parameters[shape]?strictParameter(catalog.geometry_parameters[shape]):object({shape:enumeration([shape]),...Object.fromEntries(Object.entries(defaults).map(([key,value])=>[key,key==='children'?array({$ref:'#/$defs/geometry'},32,1):sample(value,key)]))}))}}
function buildOutputSchema(mode,context){
 if(mode==='prompt')return null
 let schema
 const operations={anyOf:Object.keys(catalog.tools).map(kind=>operation(kind))}
 if(mode==='small_structure'){
  const common={label:{type:'string',minLength:1,maxLength:80},classification:enumeration(['body','wall']),lo:vector,hi:vector,state:string()}
  const tools={anyOf:['box','beam','frame'].map(kind=>object({kind:enumeration([kind]),...common,...(kind==='beam'?{start:vector,end:vector,width:enumeration([1,3,5])}:kind==='frame'?{thickness:{...integer,minimum:1,maximum:8}}:{})}))}
  schema=object({coordinate_space:enumeration(['local']),summary,structure_name:{type:'string',minLength:1,maxLength:120},camera:optional(camera),settings_patch:object({lo:vector,hi:vector,operations:array(tools,48,1)})})
 }else if(mode==='structure'){
  schema=object({summary,settings_patch:object({lo:vector,hi:vector,structure:optional(object({enabled:enumeration([true]),mode:enumeration(['fill','carve','hollow','move','floor','ceiling','walls','frame']),state:string(),classification:enumeration(['body','wall']),thickness:{...integer,minimum:1,maximum:16},offset:vector})),replace:optional(object({enabled:enumeration([true]),from_states:array(string(),32,1),state:string(),scope:enumeration(['surface','volume'])}))})})
 }else if(mode==='selection_edit')schema=object({coordinate_space:enumeration(['local']),summary,operations:array(operations,32)})
 else if(mode==='component'){
  const placement=object({id:{type:'string',pattern:'^[a-f0-9]{32}$'},content_sha256:{type:'string',pattern:'^[a-f0-9]{64}$'},position:vector,quarter_turns:optional({...integer,minimum:0,maximum:3}),mirror:optional({type:['string','null'],enum:['x','z',null]}),material_map:optional(mapSchema())})
  schema=object({name:enumeration([context.name]),size:context.size?fixedVector(context.size):vector,camera:optional(camera),operations:array(operations,48),placements:array(placement,32)})
 }else if(mode==='workbench'&&context.task==='constraint'){
  const properties=catalog.project_constraints.rules.properties
  return object({name:{type:'string',minLength:1,maxLength:80},rules:object(Object.fromEntries(Object.entries(properties).map(([key,schema])=>[key,optional(schema)])))})
 }else if(mode==='workbench'&&context.task==='brief'){
  const fields=context.brief_scope?.editable_fields??Object.keys(catalog.prompt_design.fields)
  const bound=constraints.resolve(context.constraints??[])
  const properties=Object.fromEntries(fields.map(key=>{
   if(!Object.hasOwn(catalog.prompt_design.fields,key))throw Error('AI修改范围无效')
   const field=key==='size'?projectSize(context,bound,array({...integer,minimum:1,maximum:4096},3,3)):key==='buildingShape'?enumeration(Object.keys(catalog.building_shapes)):{type:'string',minLength:1,maxLength:4000}
   return [key,optional(field)]
  }))
  return object({summary,project_patch:object(properties)})
 }else if(mode==='workbench'){
  const fields=Object.keys(catalog.prompt_design.fields).filter(key=>key!=='size'),draft=context.task==='draft',required=new Set(['name','theme','purpose','layout','circulation','style','ceiling','floor','wall','props'])
  const properties=Object.fromEntries(fields.map(key=>{const schema=key==='buildingShape'?enumeration(Object.keys(catalog.building_shapes)):{type:'string',maxLength:4000,...(draft&&required.has(key)?{minLength:1}:{})};return [key,draft&&required.has(key)?schema:optional(schema)]}))
  const bound=constraints.resolve(context.constraints??[])
  const project=context.project??{}
  for(const key of ['buildingShape','footprint'])if(bound[key]!==undefined||(key==='buildingShape'&&context.existing_model)){
   properties[key]=optional(typeof project[key]==='string'?enumeration([project[key]]):{type:'null'})
  }
  properties.size=optional(projectSize(context,bound))
  schema=object({summary,project_patch:object(properties),operations:draft?array(operations,64,1):optional(array(operations,64))})
  if(!draft){
   const change=(step,set)=>object({step,expected:optional(string(64)),set})
   const stepsByKind=new Map()
   for(const [index,op] of (context.operations??[]).entries()){
    if(!Object.hasOwn(catalog.tools,op?.kind))continue
    if(!stepsByKind.has(op.kind))stepsByKind.set(op.kind,[])
    stepsByKind.get(op.kind).push(index+1)
   }
   const steps=context.operations&&Array.from(stepsByKind,([kind,indexes])=>
    change(enumeration(indexes),operation(kind,true)))
   const changes=steps?{anyOf:steps}:change({...integer,minimum:1,maximum:128},{anyOf:Object.keys(catalog.tools).map(kind=>operation(kind,true))})
   if(steps?.length){
    const slot={...integer,minimum:1,maximum:context.operations.length},expected=optional(string(64))
    const position=enumeration(['before','after'])
    changes.anyOf.push(object({action:enumeration(['remove']),step:slot,expected}),
      object({action:enumeration(['move']),step:slot,expected,position,anchor:slot,anchor_expected:expected}),
      object({action:enumeration(['insert']),step:slot,expected,position,operation:{$ref:'#/properties/operations/anyOf/0/items'}}))
   }
   schema.properties.operation_patch=optional(steps?.length===0?{type:'null'}:
    object({baseline:optional(string(64)),changes:array(changes,16,1)}))
   schema.required.push('operation_patch')
  }
 }else throw Error('未知结构化输出工作流')
 if(['workbench','component','selection_edit'].includes(mode))schema.$defs={geometry:geometryDefinition()}
 return schema
}
function providerSchema(schema){if(Array.isArray(schema))return schema.map(providerSchema);if(!schema||typeof schema!=='object')return schema;return Object.fromEntries(Object.entries(schema).filter(([key])=>!key.startsWith('_')).map(([key,value])=>[key,providerSchema(value)]))}
function decodeOutput(value,schema,root=schema,depth=0){
 if(depth>32)throw Error('AI结构化输出嵌套过深')
 const fail=()=>{throw Error('AI返回内容不符合严格输出约束')}
 if(schema.$ref)return decodeOutput(value,schema.$ref.slice(2).split('/').reduce((part,key)=>part[key],root),root,depth+1)
 if(schema.anyOf){if(value===null&&schema._optional)return undefined;for(const branch of schema.anyOf){try{return decodeOutput(value,branch,root,depth+1)}catch{}}return fail()}
 const types=Array.isArray(schema.type)?schema.type:[schema.type],type=value===null?'null':Array.isArray(value)?'array':typeof value
 if(!types.includes(type)&&!(type==='number'&&types.includes('integer')&&Number.isSafeInteger(value)))return fail()
 if(schema.enum&&!schema.enum.some(item=>isDeepStrictEqual(item,value)))return fail()
 if(type==='string'&&(value.length<(schema.minLength??0)||value.length>(schema.maxLength??Infinity)||schema.pattern&&!new RegExp(schema.pattern).test(value)))return fail()
 if(type==='number'&&(!Number.isFinite(value)||value<(schema.minimum??-Infinity)||value>(schema.maximum??Infinity)||(schema.exclusiveMinimum!==undefined&&value<=schema.exclusiveMinimum)))return fail()
 if(type==='array'){
  if(value.length<(schema.minItems??0)||value.length>(schema.maxItems??Infinity))return fail()
  const decoded=value.map(item=>decodeOutput(item,schema.items,root,depth+1))
  if(schema._map){const keys=decoded.map(item=>item.key);if(new Set(keys).size!==keys.length||keys.some(key=>['__proto__','constructor','prototype'].includes(key)))return fail();return Object.fromEntries(decoded.map(item=>[item.key,item.value]))}
  return decoded
 }
 if(type==='object'){
  if(Object.keys(value).some(key=>!Object.hasOwn(schema.properties,key))||schema.required.some(key=>!Object.hasOwn(value,key)))return fail()
  const decoded=Object.fromEntries(Object.entries(value).map(([key,item])=>[key,decodeOutput(item,schema.properties[key],root,depth+1)]).filter(([,item])=>item!==undefined))
  return schema._clearMirror?decoded.value:decoded
 }
 return value
}
module.exports={buildOutputSchema,providerSchema,decodeOutput}
