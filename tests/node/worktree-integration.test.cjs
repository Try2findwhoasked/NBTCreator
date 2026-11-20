const {test}=require('node:test')
const assert=require('node:assert/strict')
const fs=require('node:fs/promises'),os=require('node:os'),path=require('node:path')
const {createApiService}=require('../../desktop/api-service.cjs')
const {createInternalAI}=require('../../desktop/internal-ai.cjs')
const {createCandidateValidator}=require('../../desktop/ai-candidate-validator.cjs')

function wire(value,schema){
 if(schema.anyOf){if(value===undefined)return null;return wire(value,schema.anyOf.find(branch=>branch.type!=='null'))}
 if(schema.type==='object')return Object.fromEntries(Object.entries(schema.properties).map(([key,child])=>[key,wire(value?.[key],child)]))
 if(schema.type==='array')return value.map(item=>wire(item,schema.items))
 return value
}

test('strict briefs follow the selected new design fields without geometry output or execution',async t=>{
 const directory=await fs.mkdtemp(path.join(os.tmpdir(),'nbt-merged-brief-'));t.after(()=>fs.rm(directory,{recursive:true,force:true}))
 let sent
 const reply={summary:'补充空间和材质分工',project_patch:{spatial_character:'进入低廊后面向高厅',materials:'石基座、木梁与铜接头'}}
 const api=createApiService({directory,safeStorage:{},validateCandidate:createCandidateValidator({root:path.resolve(__dirname,'../..'),python:'missing-python-for-brief.exe',directory,getWorkspace:()=>directory}),fetchImpl:async(_url,options)=>{
  sent=JSON.parse(options.body)
  return new Response(JSON.stringify({choices:[{finish_reason:'stop',message:{content:JSON.stringify(wire(reply,sent.response_format.json_schema.schema))}}]}))
 }})
 await api.save({enabled:true,provider:'compatible',strictSchema:true})
 const result=await api.generate({mode:'workbench',instruction:'只补空间体验和材质分工',context:{task:'brief',project:{size:[32,18,40],name:'人工命名',size_policy:'fixed'},brief_scope:{editable_fields:['spatial_character','materials']}}})
 assert.deepEqual(result.project_patch,reply.project_patch)
 assert.equal(result.operations,undefined)
 const schema=sent.response_format.json_schema.schema
 assert.deepEqual(Object.keys(schema.properties.project_patch.properties),['spatial_character','materials'])
 assert.equal(schema.properties.operations,undefined);assert.equal(schema.properties.operation_patch,undefined)
 assert.equal(schema.$defs,undefined)
 assert.ok(!sent.messages[0].content.includes('工具语义'))
 assert.equal(result.api_metrics.attempts,1)
 assert.equal((await fs.readdir(directory)).includes('ai-validation'),false)
})

test('strict brief schemas cannot override fixed dimensions or add unselected fields',async t=>{
 const directory=await fs.mkdtemp(path.join(os.tmpdir(),'nbt-merged-scope-'));t.after(()=>fs.rm(directory,{recursive:true,force:true}))
 let size=[17,9,16]
 const api=createApiService({directory,safeStorage:{},fetchImpl:async(_url,options)=>{
  const sent=JSON.parse(options.body),schema=sent.response_format?.json_schema?.schema
  const reply={summary:'调整风格',project_patch:{size,style:'素木'}}
  return new Response(JSON.stringify({choices:[{finish_reason:'stop',message:{content:JSON.stringify(schema?wire(reply,schema):reply)}}]}))
 }})
 await api.save({enabled:true,provider:'compatible',strictSchema:true})
 const context={task:'brief',project:{size:[16,9,16],size_policy:'fixed'},brief_scope:{editable_fields:['size','style']}}
 const request={mode:'workbench',instruction:'整理风格和尺寸',context}
 await assert.rejects(api.generate(request),/严格输出约束/)
 const unlocked={...request,context:{...context,project:{...context.project,size_policy:'reference'}}}
 assert.deepEqual((await api.generate(unlocked)).project_patch.size,[17,9,16])
 size=[16,9,16]
 assert.deepEqual((await api.generate(request)).project_patch.size,[16,9,16])
 await api.save({strictSchema:false})
 assert.deepEqual((await api.generate(request)).project_patch.size,[16,9,16])
 const {buildOutputSchema,decodeOutput}=require('../../desktop/ai-output-schema.cjs')
 const schema=buildOutputSchema('workbench',{task:'brief',brief_scope:{editable_fields:['layout']}})
 assert.throws(()=>decodeOutput({summary:'越权修改',project_patch:{layout:'布局',materials:'擅自换材质'}},schema),/约束/)
})

test('parallel excerpt reads preserve queued source snapshots and user rules',async t=>{
 const directory=await fs.mkdtemp(path.join(os.tmpdir(),'nbt-merged-snapshot-'));t.after(()=>fs.rm(directory,{recursive:true,force:true}))
 const internal=createInternalAI({workspace:()=>directory,skill:path.resolve(__dirname,'../../.agents/skills/minecraft-nbt-modeler')})
 const input=path.join(directory,'reference.md');await fs.writeFile(input,'总则\n'+('背景说明\n'.repeat(1200))+'拱门落在扶壁上\n'+('其他背景\n'.repeat(1200)))
 const config=await internal.importDocuments([input]);const doc=config.documents[0]
 config.workflows.prompt.knowledge=[doc.id];config.workflows.prompt.rules='人工规则完整保留'.repeat(500)
 await internal.save({workflows:config.workflows})
 const snapshot=await internal.capture('prompt')
 const result=await internal.context('prompt',{instruction:'拱门扶壁'},snapshot)
 assert.equal(result.rules,config.workflows.prompt.rules)
 assert.ok(result.knowledge[0].excerpted);assert.ok(result.knowledge[0].content.includes('拱门落在扶壁上'))
 await fs.writeFile(path.join(directory,'.nbtcreator/internal-ai',doc.path),'排队后修改资料')
 await assert.rejects(internal.context('prompt',{instruction:'拱门'},snapshot),/已变化/)
})

test('explicit retrieval passages and provenance bypass automatic excerpt reduction',async t=>{
 const directory=await fs.mkdtemp(path.join(os.tmpdir(),'nbt-merged-retrieval-'));t.after(()=>fs.rm(directory,{recursive:true,force:true}))
 const knowledge=[{label:'已选片段',content:'保留选定证据'.repeat(1200)}],sources=[{citation:'R1',sha256:'a'.repeat(64)}]
 const internal=createInternalAI({workspace:()=>directory,skill:path.resolve(__dirname,'../../.agents/skills/minecraft-nbt-modeler'),retrieve:async()=>({workflow:'prompt',knowledge,sources,references:[]})})
 const snapshot=await internal.capture('prompt',{retrieval:{id:'fixture'}})
 const result=await internal.context('prompt',{retrieval:{id:'fixture'},instruction:'简短请求'},snapshot)
 assert.deepEqual(result.knowledge,knowledge);assert.deepEqual(result.reference_sources,sources)
})
