const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs/promises'),os=require('node:os'),path=require('node:path')
const {excerpts,BUDGET}=require('../../desktop/ai-knowledge.cjs')
const {buildOutputSchema,providerSchema,decodeOutput}=require('../../desktop/ai-output-schema.cjs')
const {createApiService,configOf}=require('../../desktop/api-service.cjs')
const context={size:[16,16,16],lo:[4,4,4],hi:[7,7,7],allow_overwrite:false,materials:[]}
const box={kind:'box',label:'柱',classification:'body',lo:[0,0,0],hi:[0,2,0],state:'stone_bricks'}
const small={coordinate_space:'local',summary:'添加有支承的柱子',structure_name:'柱',camera:{azimuth:45,elevation:25},settings_patch:{lo:[0,0,0],hi:[3,3,3],operations:[box]}}

test('long knowledge is bounded, relevant, deterministic and explicitly excerpted; duplicate content is sent once',()=>{
 const docs=Array.from({length:8},(_,i)=>({label:'规范'+i,content:'# 总则\n保留通路和支承。\n'+('无关风格描述\n'.repeat(180))+'# 承重拱门\n承重拱门落在扶壁上。\n'+('其他背景\n'.repeat(180))}))
 // Different documents, plus one exact duplicate.
 docs.forEach((doc,i)=>doc.content+='编号'+i)
 const result=excerpts([...docs,docs[0]],'设计承重拱门')
 assert.equal(result.length,8);assert.ok(result.reduce((n,d)=>n+d.content.length,0)<=BUDGET)
 assert.ok(result.every(d=>d.excerpted&&d.omitted&&d.content.includes('承重拱门落在扶壁上')&&d.content.includes('保留通路和支承')))
 assert.deepEqual(result,excerpts([...docs,docs[0]],'设计承重拱门'))
 assert.deepEqual(excerpts([{label:'短文',content:'完整短文'}]),[{label:'短文',content:'完整短文'}])
 const many=excerpts(Array.from({length:105},(_,i)=>({label:''+i,content:'文'.repeat(1000)+i})))
 assert.ok(many.every(doc=>doc.content.length>0));assert.ok(many.reduce((n,d)=>n+d.content.length,0)<=BUDGET)
})

test('actual workflow preparation forwards the task query and preserves complete custom rules',async t=>{
 const {createInternalAI}=require('../../desktop/internal-ai.cjs'),directory=await fs.mkdtemp(path.join(os.tmpdir(),'nbt-speed-context-'))
 t.after(()=>fs.rm(directory,{recursive:true,force:true}))
 const internal=createInternalAI({workspace:()=>directory,skill:path.resolve(__dirname,'../../.agents/skills/minecraft-nbt-modeler')})
 const source=path.join(directory,'reference.md');await fs.writeFile(source,'首段规范\n'+('背景说明\n'.repeat(1500))+'必须保留的拱门支承细节\n'+('其他说明\n'.repeat(1500)))
 const config=await internal.importDocuments([source]);config.workflows.prompt.knowledge=[config.documents[0].id];config.workflows.prompt.rules='完整规则'.repeat(1500);await internal.save({workflows:config.workflows})
 let sent
 const api=createApiService({directory:path.join(directory,'user'),safeStorage:{},workflowContext:(key,request)=>internal.context(key,request),fetchImpl:async(_url,options)=>{sent=JSON.parse(JSON.parse(options.body).messages[1].content);return new Response(JSON.stringify({choices:[{finish_reason:'stop',message:{content:'设计正文'}}]}))}})
 await api.save({enabled:true});await api.generate({mode:'prompt',instruction:'拱门支承细节',context:null})
 assert.equal(sent.internal_workflow.rules,config.workflows.prompt.rules)
 const doc=sent.internal_workflow.knowledge[0];assert.ok(doc.content.length<=4000);assert.ok(doc.content.includes('必须保留的拱门支承细节'));assert.equal(doc.omitted,true)
 assert.equal(sent.internal_workflow.workflow_steps,undefined);assert.equal(sent.internal_workflow.attachViewport,undefined)
})

test('strict small structure schema rejects extra fields, fractional coordinates, excess steps and long summaries',()=>{
 const schema=buildOutputSchema('small_structure',context)
 assert.deepEqual(decodeOutput(small,schema),small)
 const {camera,...withoutCamera}=small
 assert.deepEqual(decodeOutput({...small,camera:null},schema),withoutCamera)
 for(const value of [{...small,code:'x'},{...small,summary:'字'.repeat(161)},{...small,settings_patch:{...small.settings_patch,operations:Array(49).fill(box)}},{...small,settings_patch:{...small.settings_patch,lo:[0.1,0,0]}}])assert.throws(()=>decodeOutput(value,schema),/约束/)
})

// Fill only explicitly nullable wire fields. Concrete operations/patches below remain authored fixtures.
function nullable(value,schema,root=schema){
 if(value===null||typeof value!=='object')return value
 if(schema.$ref)return nullable(value,root.$defs[schema.$ref.split('/').at(-1)],root)
 if(schema.anyOf){if(value===null)return null;const branch=schema.anyOf.find(s=>s.type==='object'&&['kind','step'].every(key=>!s.properties[key]?.enum||s.properties[key].enum.includes(value[key])))??schema.anyOf[0];return nullable(value,branch,root)}
 if(schema.type==='object')return Object.fromEntries(Object.entries(schema.properties).map(([key,s])=>[key,value[key]===undefined?null:nullable(value[key],s,root)]))
 if(schema.type==='array')return value.map(item=>nullable(item,schema.items,root))
 return value
}
test('strict schemas cover each structured workflow and decode nullable patches and material maps',()=>{
 const samples={
  structure:{summary:'填充',settings_patch:{lo:[4,4,4],hi:[4,6,4],structure:{enabled:true,mode:'fill',state:'stone',classification:'body',thickness:1,offset:[0,0,0]}}},
  selection_edit:{coordinate_space:'local',summary:'添加柱',operations:[box]},
  component:{name:'构件',size:[4,4,4],camera:{azimuth:45,elevation:25},operations:[box],placements:[{id:'a'.repeat(32),content_sha256:'b'.repeat(64),position:[0,0,0],material_map:[{key:'stone',value:'andesite'}]}]},
  workbench:{summary:'改主题',project_patch:{theme:'石屋'}}
 }
 for(const [mode,value]of Object.entries(samples)){
  const schema=buildOutputSchema(mode,{...context,name:'构件',task:'controls',...(mode==='component'?{size:value.size}:{})}),wire=nullable(value,schema),decoded=decodeOutput(wire,schema)
  if(mode==='component')assert.deepEqual(decoded.placements[0].material_map,{stone:'andesite'})
  else assert.deepEqual(decoded,value)
  const provider=providerSchema(schema)
  function check(node){if(!node||typeof node!=='object')return;assert.ok(!Object.keys(node).some(k=>k.startsWith('_')));if(node.type==='object'){assert.equal(node.additionalProperties,false);assert.deepEqual(node.required,Object.keys(node.properties))}Object.values(node).forEach(v=>Array.isArray(v)?v.forEach(check):check(v))}
  check(provider)
 }
 assert.equal(buildOutputSchema('prompt',context),null)
 const schema=buildOutputSchema('component',{name:'构件'}),wire=nullable(samples.component,schema)
 wire.placements[0].material_map.push({key:'stone',value:'gold_block'});assert.throws(()=>decodeOutput(wire,schema))
})

test('component camera is optional in ordinary JSON and nullable in strict JSON',async t=>{
 const directory=await fs.mkdtemp(path.join(os.tmpdir(),'nbt-component-format-'))
 t.after(()=>fs.rm(directory,{recursive:true,force:true}))
 const context={name:'测试柱',size:[4,4,4]},candidate={...context,operations:[box],placements:[]}
 const schema=buildOutputSchema('component',context),strictReply=nullable(candidate,schema)
 let payload
 const api=createApiService({directory,safeStorage:{},fetchImpl:async(_url,options)=>{
  payload=JSON.parse(options.body)
  const content=JSON.stringify(payload.response_format?.type==='json_schema'?strictReply:candidate)
  return new Response(JSON.stringify({choices:[{finish_reason:'stop',message:{content}}]}))
 }})
 await api.save({enabled:true,provider:'compatible'})
 const request={mode:'component',instruction:'制作一根石柱',context}
 const ordinary=await api.generate(request)
 assert.match(payload.messages[0].content,/普通 JSON 可省略 camera/)
 assert.equal(ordinary.spec.camera,undefined)
 assert.deepEqual(ordinary.spec.size,[4,4,4])
 await api.save({strictSchema:true})
 const strict=await api.generate(request)
 assert.match(payload.messages[0].content,/严格 JSON 无自定义视角时填 camera: null/)
 assert.equal(strict.spec.camera,undefined)
 assert.deepEqual(strict.spec.size,[4,4,4])
 assert.throws(()=>decodeOutput({...strictReply,size:[5,4,4]},schema),/严格输出约束/)
 const missingCamera={...strictReply};delete missingCamera.camera
 assert.throws(()=>decodeOutput(missingCamera,schema),/约束/)
})

test('strict draft fields remain required and control deltas preserve untouched steps',()=>{
 const {validateWorkbench,operationBase}=require('../../desktop/workbench-contract.cjs')
 const context={task:'controls',existing_model:false,project:{size:[4,4,4]},operations:[box,{...box,label:'另一根柱',lo:[2,0,0],hi:[2,2,0]}]},base=operationBase(context)
 const candidate={summary:'只改第一步材质',project_patch:{},operation_patch:{baseline:base.baseline,changes:[{step:1,expected:base.steps[0].expected,set:{state:'andesite'}}]}}
 const schema=buildOutputSchema('workbench',context),decoded=decodeOutput(nullable(candidate,schema),schema),merged=validateWorkbench(decoded,context)
 assert.equal(merged.operations[0].state,'andesite');assert.deepEqual(merged.operations[1],context.operations[1])
 const {normalizeReply}=require('../../desktop/ai-output-normalize.cjs')
 const withoutWireFingerprints=nullable({summary:candidate.summary,project_patch:{},
  operation_patch:{changes:[{step:1,set:{state:'andesite'}}]}},schema)
 const locallyBound=normalizeReply(decodeOutput(withoutWireFingerprints,schema),'workbench',context)
 assert.deepEqual(locallyBound.operation_patch,candidate.operation_patch)
 const draft={...context,task:'draft'},draftSchema=buildOutputSchema('workbench',draft),project_patch=Object.fromEntries(['name','theme','purpose','layout','circulation','style','ceiling','floor','wall','props'].map(key=>[key,'完整设计']))
 const wire=nullable({summary:'整体初稿',project_patch,operations:[box]},draftSchema)
 assert.equal(validateWorkbench(decodeOutput(wire,draftSchema),draft).operations.length,1)
 wire.project_patch.circulation=null;assert.throws(()=>decodeOutput(wire,draftSchema))
})

test('strict complete operations and increments cover the catalogue without authority fields',()=>{
 const catalog=require('../../.agents/skills/minecraft-nbt-modeler/tool-catalog.json')
 const schema=buildOutputSchema('workbench',{task:'controls'})
 const full=schema.properties.operations.anyOf[0].items.anyOf
 const sets=schema.properties.operation_patch.anyOf[0].properties.changes.items.properties.set.anyOf
 const examples={
  pattern:{scale:[2,3,4],palette:['stone',{state:'andesite',weight:null}]},
  auto_roof:{footprint:[[0,0],[3,3]],corner_lift:2,rise:1.5},
  selection_replace:{from_states:['stone']},
  align_region:{source_anchor:[0,0,0],target_anchor:[1,1,1]},
  array_region:{centre:[1,0,1],radius:2,count:3,start_angle:0,sweep_angle:180},
  auto_stairs:{centre:[1,0,1],radius:2,turns:1}
 }
 for(const [i,[kind,contract]] of Object.entries(catalog.operation_parameters).entries()){
  const keys=Object.keys(contract.properties).filter(key=>!['overwrite','write_bounds','write_group','max_writes'].includes(key))
  assert.deepEqual(full[i].required,['kind',...keys],kind)
  assert.deepEqual(sets[i].required,keys,kind)
  assert.deepEqual(Object.keys(full[i].properties),full[i].required)
  assert.deepEqual(Object.keys(sets[i].properties),keys)
  if(!examples[kind])continue
  const values=examples[kind],op={...box,kind,...values}
  const decoded=decodeOutput(nullable(op,full[i],schema),full[i],schema)
  const update=decodeOutput(nullable(values,sets[i],schema),sets[i],schema)
  assert.deepEqual(decoded,{...Object.fromEntries(Object.entries(box).filter(([key])=>full[i].required.includes(key))),kind,...update})
  assert.throws(()=>decodeOutput({...nullable(values,sets[i],schema),overwrite:true},sets[i],schema))
 }
 const roof=full.find(branch=>branch.properties.kind.enum[0]==='auto_roof')
 for(const invalid of [{rise:0},{corner_lift:9},{footprint:[[0,0],[3,3,3]]}]){
  assert.throws(()=>decodeOutput(nullable({...box,kind:'auto_roof',...invalid},roof,schema),roof,schema))
 }
})

test('workbench API merges strict vector scales and explicit mirror clears like ordinary JSON',async t=>{
 const directory=await fs.mkdtemp(path.join(os.tmpdir(),'nbt-strict-controls-'))
 t.after(()=>fs.rm(directory,{recursive:true,force:true}))
 const pattern={...box,kind:'pattern',palette:['stone'],scale:6}
 delete pattern.state
 const transform={...box,kind:'transform_region',destination:[2,0,0],mirror:'x'}
 delete transform.state
 const context={task:'controls',project:{size:[8,8,8]},operations:[pattern,transform]}
 const schema=buildOutputSchema('workbench',context)
 const ordinary={summary:'调整纹理并取消镜像',operation_patch:{changes:[{step:1,set:{scale:[2,3,4]}},{step:2,set:{mirror:null,quarter_turns:1}}]}}
 const strict=nullable({...ordinary,project_patch:{},operation_patch:{changes:ordinary.operation_patch.changes.map(({step,set})=>({
  step,set:{...set,...(step===2?{mirror:{value:null}}:{})}
 }))}},schema)
 let reply=ordinary,payload,validationCount=0
 const api=createApiService({directory,safeStorage:{},validateCandidate:async()=>{validationCount++},fetchImpl:async(_url,options)=>{
  payload=JSON.parse(options.body)
  return new Response(JSON.stringify({choices:[{finish_reason:'stop',message:{content:JSON.stringify(reply)}}]}))
 }})
 await api.save({enabled:true,provider:'compatible'})
 const input={mode:'workbench',instruction:'修改原有步骤',context}
 const plain=await api.generate(input)
 await api.save({strictSchema:true})
 reply=strict
 const structured=await api.generate(input)
 assert.match(payload.messages[0].content,/"value":null.*显式清除镜像/)
 assert.deepEqual(structured.operations,plain.operations)
 assert.deepEqual(structured.operation_patch,plain.operation_patch)
 assert.deepEqual(structured.operations[0].scale,[2,3,4])
 assert.equal(structured.operations[1].mirror,null)
 const transformSet=strict.operation_patch.changes[1].set
 transformSet.mirror=null
 assert.equal((await api.generate(input)).operations[1].mirror,'x')
 transformSet.mirror={value:'z'}
 await assert.rejects(api.generate(input),/严格输出约束/)
 transformSet.mirror=null
 strict.operation_patch.changes[1].expected='f'.repeat(64)
 await assert.rejects(api.generate(input),/指纹不匹配/)
 assert.equal(validationCount,3)
})

test('strict workbench replies still require real engine geometry preflight',async t=>{
 const directory=await fs.mkdtemp(path.join(os.tmpdir(),'nbt-strict-preflight-'))
 t.after(()=>fs.rm(directory,{recursive:true,force:true}))
 const {createCandidateValidator}=require('../../desktop/ai-candidate-validator.cjs')
 const validateCandidate=createCandidateValidator({root:path.resolve(__dirname,'../..'),python:process.env.NBTCREATOR_PYTHON||'python',directory,getWorkspace:()=>directory})
 const context={task:'draft',project:{size:[16,10,16]}}
 const schema=buildOutputSchema('workbench',context)
 const operation={...box,kind:'auto_stairs',hi:[15,9,15],start:[2,1,2],end:[12,1,2]}
 const project_patch=Object.fromEntries(['name','theme','purpose','layout','circulation','style','ceiling','floor','wall','props'].map(key=>[key,'完整设计']))
 const reply=nullable({summary:'生成楼梯',project_patch,operations:[operation]},schema)
 assert.equal(decodeOutput(reply,schema).operations[0].kind,'auto_stairs')
 const api=createApiService({directory,safeStorage:{},validateCandidate,fetchImpl:async()=>new Response(JSON.stringify({
  choices:[{finish_reason:'stop',message:{content:JSON.stringify(reply)}}]
 }))})
 await api.save({enabled:true,provider:'compatible',strictSchema:true})
 await assert.rejects(api.generate({mode:'workbench',instruction:'生成楼梯',context}),/above start/)
})

test('bound material increment rejects resized sources and wrong step fields at schema decoding',async t=>{
 const directory=await fs.mkdtemp(path.join(os.tmpdir(),'nbt-strict-material-'))
 t.after(()=>fs.rm(directory,{recursive:true,force:true}))
 const context={task:'controls',existing_model:true,project:{size:[16,9,16]},operations:[
  {...box,lo:[2,0,2],hi:[2,6,2]}
 ]}
 const schema=buildOutputSchema('workbench',context)
 const candidate={summary:'只换柱材',project_patch:{},operation_patch:{changes:[{step:1,set:{state:'andesite'}}]}}
 let reply=nullable(candidate,schema),payload,validated=0
 const api=createApiService({directory,safeStorage:{},validateCandidate:async()=>{validated++},fetchImpl:async(_url,options)=>{
  payload=JSON.parse(options.body)
  return new Response(JSON.stringify({choices:[{finish_reason:'stop',message:{content:JSON.stringify(reply)}}]}))
 }})
 await api.save({enabled:true,provider:'compatible',strictSchema:true})
 const input={mode:'workbench',instruction:'把柱子改为安山岩',context}
 const result=await api.generate(input)
 assert.equal(result.operations[0].state,'andesite')
 assert.equal(result.api_metrics.output_schema_bytes,Buffer.byteLength(JSON.stringify(payload.response_format.json_schema.schema)))
 assert.ok(result.api_metrics.output_schema_bytes<50000)
 reply.project_patch.size=[17,9,16]
 await assert.rejects(api.generate(input),/严格输出约束/)
 reply.project_patch.size=[16,9,16]
 reply.operation_patch.changes[0].set.width=3
 await assert.rejects(api.generate(input),/严格输出约束/)
 assert.equal(validated,1)
})

test('workbench UI context keeps catalogue-required anchors and merges into the original operation',()=>{
 const folder='../../.agents/skills/minecraft-nbt-modeler/prompt-console/'
 require(folder+'catalog.js')
 require(folder+'core.js')
 require(folder+'ai-input.js')
 const {cleanContext,validateWorkbench}=require('../../desktop/workbench-contract.cjs')
 const {normalizeReply}=require('../../desktop/ai-output-normalize.cjs')
 const original={...box,kind:'align_region',lo:[0,0,0],hi:[1,1,1],mode:'anchor',
  source_anchor:[0,0,0],target_anchor:[4,0,0],overwrite:true,source:'private/model.snbt'}
 delete original.state
 const operation=globalThis.NbtPrompt.aiOperation(original)
 assert.deepEqual(operation.source_anchor,original.source_anchor)
 assert.deepEqual(operation.target_anchor,original.target_anchor)
 assert.equal(operation.overwrite,undefined)
 assert.equal(operation.source,undefined)
 const context=cleanContext({task:'controls',existing_model:true,project:{size:[16,9,16]},operations:[operation]})
 const proposal=normalizeReply({summary:'改名称',operation_patch:{changes:[{step:1,set:{label:'对齐'}}]}},'workbench',context)
 assert.equal(validateWorkbench(proposal,context).operations[0].label,'对齐')
 assert.deepEqual(globalThis.NbtPromptAIInput.mergeOperations([original],proposal.operation_patch),[{...original,label:'对齐'}])
})

test('strict schema requests keep engine boundary checks and never silently downgrade unsupported APIs',async t=>{
 const directory=await fs.mkdtemp(path.join(os.tmpdir(),'nbt-speed-'));t.after(()=>fs.rm(directory,{recursive:true,force:true}));let calls=0,payload,reply=small,unsupported=false
 const api=createApiService({directory,safeStorage:{},fetchImpl:async(_url,options)=>{calls++;payload=JSON.parse(options.body);return unsupported?new Response('private-provider-error',{status:400}):new Response(JSON.stringify({choices:[{finish_reason:'stop',message:{content:JSON.stringify(reply)}}]}))}})
 assert.equal(configOf({}).strictSchema,false);assert.throws(()=>configOf({strictSchema:true}),/DeepSeek/)
 await api.save({enabled:true,provider:'compatible',strictSchema:true})
 const input={mode:'small_structure',instruction:'添加柱子',context},result=await api.generate(input)
 assert.equal(payload.response_format.type,'json_schema');assert.equal(payload.response_format.json_schema.strict,true)
 assert.match(payload.messages[0].content,/settings_patch\.operations/)
 assert.doesNotMatch(payload.messages[0].content,/"boxes"|最多128步/)
 assert.deepEqual(result.settings_patch.operations[0].lo,[4,4,4]);assert.equal(result.api_metrics.attempts,1)
 reply={...small,settings_patch:{...small.settings_patch,operations:[{...box,hi:[9,9,9]}]}}
 await assert.rejects(api.generate(input),/超出/)
 reply={...small,summary:'字'.repeat(161)};await assert.rejects(api.generate(input),/约束/)
 unsupported=true;const before=calls;await assert.rejects(api.generate(input),e=>/严格Schema/.test(e.message)&&!e.message.includes('private-provider-error'));assert.equal(calls,before+1)
 await api.save({strictSchema:false});unsupported=false;reply=small;await api.generate(input);assert.equal(payload.response_format.type,'json_object')
})

test('renderer configuration reads start independently before either completes',async t=>{
 const code=await fs.readFile(path.resolve(__dirname,'../../.agents/skills/minecraft-nbt-modeler/assets/viewer/src/ai-request.js'),'utf8'),priorWindow=global.window,priorFetch=global.fetch
 t.after(()=>{global.window=priorWindow;global.fetch=priorFetch})
 let resolveConfig,resolveConnection,connectionStarted=false
 global.window={nbtDesktop:{internalAIConfig:()=>new Promise(resolve=>resolveConfig=resolve),apiConfig:()=>{connectionStarted=true;return new Promise(resolve=>resolveConnection=resolve)},apiGenerate:async()=>({text:'正文'})}}
 global.fetch=async()=>new Response(JSON.stringify({id:'task'}))
 const {requestAI}=await import('data:text/javascript;base64,'+Buffer.from(code).toString('base64')),pending=requestAI({mode:'prompt',instruction:'主题'})
 assert.equal(connectionStarted,true)
 resolveConfig({workflows:{prompt:{}},flows:{prompt:{label:'文字'}}});resolveConnection({model:'mock',provider:'compatible'})
 assert.equal((await pending).text,'正文')
})
