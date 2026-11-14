const {test}=require('node:test'),assert=require('node:assert/strict')
const {buildInternalPrompt,toolContract,selectTools}=require('../desktop/internal-skill.cjs')
const catalog=require('../.agents/skills/minecraft-nbt-modeler/tool-catalog.json')
test('compact internal contracts retain every tool, parameter limit and geometry mode without duplicate templates',()=>{
 const contract=toolContract();assert.deepEqual(Object.keys(contract.tools),Object.keys(catalog.tools))
 function constraints(value){if(Array.isArray(value))return value.map(constraints);if(!value||typeof value!=='object')return value;return Object.fromEntries(Object.entries(value).filter(([k])=>!['description','title','default','examples'].includes(k)).map(([k,v])=>[k,constraints(v)]))}
 for(const [kind,schema]of Object.entries(catalog.operation_parameters)){
  const {name,rules,...actual}=contract.tools[kind];assert.equal(rules,catalog.tools[kind][2]);actual.properties={...contract.common,...actual.properties}
  assert.deepEqual(actual,{...constraints(schema),properties:{...contract.common,...constraints(schema.properties)}},kind)
 }
 assert.deepEqual(contract.geometry_parameters,constraints(catalog.geometry_parameters))
 assert.ok(buildInternalPrompt('component').length<20000)
 assert.ok(buildInternalPrompt('workbench',{task:'draft'}).length<20000)
 assert.ok(buildInternalPrompt('small_structure').length<1000)
 assert.ok(buildInternalPrompt('prompt').length<234)
 assert.ok(!buildInternalPrompt('component').includes('参数模板'))
 assert.ok(buildInternalPrompt('workbench',{task:'controls'}).includes('operation_patch'))
 assert.ok(buildInternalPrompt('selection_edit').includes('write_bounds'))
})

test('task contracts stay small while retaining requested tools and existing operations',()=>{
 const simple=buildInternalPrompt('component',{}, {instruction:'制作石桌'})
 assert.ok(simple.length<6000);assert.ok(!simple.includes('geometry_parameters'))
 assert.ok(simple.includes('placement')||simple.includes('placements'))
 const selected=selectTools('旋转复制一段圆弧，再添加楼梯',{operations:[{kind:'weathering'}]})
 for(const kind of ['geometry','transform_region','copy_region','auto_stairs','weathering'])assert.ok(selected.includes(kind),kind)
 const compact=toolContract(selected),full=toolContract()
 for(const kind of selected)assert.deepEqual(compact.tools[kind],full.tools[kind])
 assert.deepEqual(compact.geometry_parameters,full.geometry_parameters)
 assert.ok(buildInternalPrompt('component',{}, {fullTools:true}).length>simple.length)
 assert.ok(buildInternalPrompt('workbench',{task:'brief'}).includes('待验证'))
})

test('a parameter repair can expand the tool contract without changing the request context',async t=>{
 const fs=require('node:fs/promises'),os=require('node:os'),path=require('node:path')
 const {createApiService}=require('../desktop/api-service.cjs')
 const directory=await fs.mkdtemp(path.join(os.tmpdir(),'nbt-prompt-scope-'));t.after(()=>fs.rm(directory,{recursive:true,force:true}))
 const calls=[];let validations=0
 const api=createApiService({directory,safeStorage:{},fetchImpl:async(_url,options)=>{
  calls.push(JSON.parse(options.body));return new Response(JSON.stringify({choices:[{finish_reason:'stop',message:{content:JSON.stringify({operations:[{kind:'box',lo:[0,0,0],hi:[0,1,0],state:'stone'}]})}}]}))
 },validateCandidate:async()=>{if(++validations===1)throw Error('参数需要重新核对')}})
 await api.save({enabled:true})
 const result=await api.generate({mode:'component',instruction:'制作石桌',context:{name:'石桌',size:[4,4,4]}})
 assert.equal(calls.length,2);assert.ok(!calls[0].messages[0].content.includes('geometry_parameters'))
 assert.ok(calls[1].messages[0].content.includes('geometry_parameters'))
 assert.deepEqual(calls[0].messages[1],calls[1].messages[1])
 assert.equal(result.api_metrics.expanded_tool_contract,true);assert.deepEqual(result.spec.size,[4,4,4])
})
