const {test}=require('node:test'),assert=require('node:assert/strict')
const {buildInternalPrompt,toolContract}=require('../desktop/internal-skill.cjs')
const catalog=require('../.agents/skills/minecraft-nbt-modeler/tool-catalog.json')
test('compact internal contracts retain every tool, parameter limit and geometry mode without duplicate templates',()=>{
 const contract=toolContract();assert.deepEqual(Object.keys(contract.tools),Object.keys(catalog.tools))
 function constraints(value){if(Array.isArray(value))return value.map(constraints);if(!value||typeof value!=='object')return value;return Object.fromEntries(Object.entries(value).filter(([k])=>!['description','title','default','examples'].includes(k)).map(([k,v])=>[k,constraints(v)]))}
 for(const [kind,schema]of Object.entries(catalog.operation_parameters)){
  const {name,...actual}=contract.tools[kind];actual.properties={...contract.common,...actual.properties}
  assert.deepEqual(actual,{...constraints(schema),properties:{...contract.common,...constraints(schema.properties)}},kind)
 }
 assert.deepEqual(contract.geometry_parameters,constraints(catalog.geometry_parameters))
 assert.ok(buildInternalPrompt('component').length<17000)
 assert.ok(buildInternalPrompt('workbench',{task:'draft'}).length<18000)
 assert.ok(buildInternalPrompt('small_structure').length<1000)
 assert.ok(buildInternalPrompt('prompt').length<234)
 assert.ok(!buildInternalPrompt('component').includes('参数模板'))
 assert.ok(buildInternalPrompt('workbench',{task:'controls'}).includes('operation_patch'))
 assert.ok(buildInternalPrompt('selection_edit').includes('write_bounds'))
})
