const {test}=require('node:test'),assert=require('node:assert/strict')
const {buildInternalPrompt,toolContract,selectTools}=require('../../desktop/internal-skill.cjs')
const catalog=require('../../.agents/skills/minecraft-nbt-modeler/tool-catalog.json')
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

test('the small-structure prompt uses inline states for boxes',()=>{
 const prompt=buildInternalPrompt('small_structure')
 assert.match(prompt,/不得用全局坐标或palette索引/)
 assert.doesNotMatch(prompt,/可选palette/)
})

test('natural roof and stair requests discover only their relevant tools and preserve strong intent',async t=>{
 const {requiredRoutes,checkDesignRoutes}=require('../../desktop/internal-skill.cjs')
 assert.ok(selectTools('做个歇山顶').includes('auto_roof'))
 assert.ok(!selectTools('做个歇山顶').includes('geometry'))
 assert.ok(selectTools('螺旋梯').includes('auto_stairs'))
 assert.ok(selectTools('盘旋楼梯').includes('auto_stairs'))
 assert.ok(selectTools('做一座九脊殿').includes('auto_roof'))
 assert.ok(selectTools('回旋式阶梯').includes('auto_stairs'))
 assert.ok(selectTools('把这段平移构件').includes('move_region'))
 assert.ok(!selectTools('旋转楼梯').includes('transform_region'))
 assert.ok(!selectTools('旋转楼梯').includes('array_region'))
 assert.match(buildInternalPrompt('component',{}, {instruction:'做个歇山顶'}),/组合/)
 assert.deepEqual(requiredRoutes('拆除螺旋楼梯。不要做歇山顶。'),[])
 assert.deepEqual(requiredRoutes('做个像螺旋梯的雕塑'),[])
 const specified=requiredRoutes('制作旋梯，半径4格、宽2格，绕2圈')
 assert.deepEqual(specified[0].parameters,{radius:4,width:2,turns:2})
 assert.throws(()=>checkDesignRoutes(specified,'component',{},[{kind:'auto_stairs',mode:'spiral',radius:4,width:2}]),/尚未表达/)
 assert.throws(()=>checkDesignRoutes(requiredRoutes('螺旋梯'),'small_structure',{}),{code:'AI_DESIGN_ROUTE_REQUIRED'})
 assert.throws(()=>checkDesignRoutes(requiredRoutes('做个歇山顶'),'component',{},[{kind:'auto_roof',roof:'hip'}]),/尚未表达/)
 checkDesignRoutes(requiredRoutes('做个歇山顶'),'component',{},[{kind:'auto_roof',roof:'hip'},{kind:'auto_roof',roof:'gable'}])
 const fs=require('node:fs/promises'),os=require('node:os'),path=require('node:path')
 const {createApiService}=require('../../desktop/api-service.cjs')
 const directory=await fs.mkdtemp(path.join(os.tmpdir(),'nbt-route-'));t.after(()=>fs.rm(directory,{recursive:true,force:true}))
 let calls=0,checked=[]
 const spiral={kind:'auto_stairs',mode:'spiral',lo:[0,0,0],hi:[15,15,15],centre:[8,1,8],start:[5,1,5],end:[5,6,5],radius:3,turns:1}
 const box={kind:'box',lo:[0,0,0],hi:[0,1,0],state:'stone'}
 const api=createApiService({directory,safeStorage:{},validateCandidate:async input=>{checked=input.context.required_designs},fetchImpl:async()=>new Response(JSON.stringify({choices:[{finish_reason:'stop',
  message:{content:JSON.stringify({operations:[++calls===1?box:spiral]})}}]}))})
 await api.save({enabled:true})
 const result=await api.generate({mode:'component',instruction:'螺旋梯',context:{name:'螺旋梯',size:[16,16,16]}})
 assert.equal(result.spec.operations[0].mode,'spiral')
 assert.deepEqual(checked,['spiral_stair'])
 assert.equal(result.api_metrics.calls[0].validation_issue.code,'required_design_missing')
})

test('structure prompt example uses model coordinates and decodes in strict mode',()=>{
 const {buildOutputSchema,decodeOutput}=require('../../desktop/ai-output-schema.cjs')
 const {validatePatch}=require('../../desktop/api-service.cjs')
 const context={lo:[12,3,20],hi:[15,6,25]}
 const prompt=buildInternalPrompt('structure',context,{strictSchema:true})
 const example=JSON.parse(prompt.match(/可返回 (\{.*\})。/)[1])
 const decoded=decodeOutput(example,buildOutputSchema('structure',context))
 assert.deepEqual(validatePatch(decoded,context).settings_patch.lo,context.lo)
 assert.throws(()=>validatePatch({...decoded,settings_patch:{...decoded.settings_patch,lo:[0,0,0]}},context),/超出当前选区/)
})

test('strict controls example and constraint placeholders pass local validation',()=>{
 const {buildOutputSchema,decodeOutput}=require('../../desktop/ai-output-schema.cjs')
 const {normalizeReply}=require('../../desktop/ai-output-normalize.cjs')
 const {validateWorkbench}=require('../../desktop/workbench-contract.cjs')
 const context={task:'controls',project:{size:[4,4,4]},operations:[
  {kind:'box',label:'石柱',classification:'body',lo:[0,0,0],hi:[0,2,0],state:'minecraft:stone'}
 ]}
 const schema=buildOutputSchema('workbench',context)
 const prompt=buildInternalPrompt('workbench',context,{strictSchema:true})
 const operation_patch=JSON.parse(prompt.match(/对应的 operation_patch 为 (\{.*\})。其他工具/)[1])
 const project_patch=Object.fromEntries(schema.properties.project_patch.required.map(key=>[key,null]))
 const reply={summary:'换材',project_patch,operations:null,operation_patch}
 const normalized=normalizeReply(decodeOutput(reply,schema),'workbench',context)
 assert.equal(validateWorkbench(normalized,context).operations[0].state,'minecraft:andesite')
 const full={...reply,operations:[{...context.operations[0],enabled:null}],operation_patch:null}
 assert.deepEqual(validateWorkbench(decodeOutput(full,schema),context).operations,context.operations)
 delete reply.operation_patch.changes[0].set.label
 assert.throws(()=>decodeOutput(reply,schema),/严格输出约束/)

 const constraint={task:'constraint'},constraintSchema=buildOutputSchema('workbench',constraint)
 assert.match(buildInternalPrompt('workbench',constraint,{strictSchema:true}),/全部规则键都须出现/)
 assert.match(buildInternalPrompt('workbench',constraint),/未指定的键省略/)
 const rules=Object.fromEntries(constraintSchema.properties.rules.required.map(key=>[key,null]))
 const decoded=decodeOutput({name:'开放建筑',rules:{...rules,require_enclosure:false}},constraintSchema)
 assert.deepEqual(validateWorkbench(decoded,constraint).rules,{require_enclosure:false})

 const {validateSelectionResult}=require('../../desktop/selection-edit.cjs')
 const selection={lo:[12,3,20],hi:[15,6,25],selection:{geometry_sha256:'a'.repeat(64)}}
 const noAction={coordinate_space:'local',summary:'选区缺少安全施工空间',operations:[]}
 const decodedSelection=decodeOutput(noAction,buildOutputSchema('selection_edit',selection))
 assert.deepEqual(validateSelectionResult(decodedSelection,selection).settings_patch.operations,[])
})

test('a parameter repair can expand the tool contract without changing the request context',async t=>{
 const fs=require('node:fs/promises'),os=require('node:os'),path=require('node:path')
 const {createApiService}=require('../../desktop/api-service.cjs')
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
