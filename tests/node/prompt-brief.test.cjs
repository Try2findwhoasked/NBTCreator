const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs/promises'),os=require('node:os'),path=require('node:path')
const {createApiService}=require('../../desktop/api-service.cjs'),{createCandidateValidator}=require('../../desktop/ai-candidate-validator.cjs'),{buildInternalPrompt}=require('../../desktop/internal-skill.cjs')
const project=Object.fromEntries(['name','theme','purpose','layout','circulation','style','ceiling','floor','wall','props'].map(key=>[key,'可交接的设计要求']))
test('ordinary prompt drafts return requirements without tool generation or a Python geometry process',async t=>{
 const directory=await fs.mkdtemp(path.join(os.tmpdir(),'nbt-brief-'));t.after(()=>fs.rm(directory,{recursive:true,force:true}));const calls=[]
 const api=createApiService({directory,safeStorage:{},validateCandidate:createCandidateValidator({root:path.resolve(__dirname,'../..'),python:'missing-python-for-text-only.exe',directory,getWorkspace:()=>directory}),fetchImpl:async(_u,o)=>{calls.push(JSON.parse(o.body));return new Response(JSON.stringify({choices:[{finish_reason:'stop',message:{content:JSON.stringify({project_patch:project})}}]}))}})
 await api.save({enabled:true});const result=await api.generate({mode:'workbench',instruction:'写提示词并交接',context:{task:'brief',project:{size:[48,24,48]},operations:[{kind:'box',state:'stone'}]}})
 assert.equal(result.operations,undefined);assert.equal(result.project_patch.name,project.name);assert.equal(result.api_metrics.attempts,1);assert.equal(calls.length,1);assert.equal(JSON.parse(calls[0].messages[1].content).context.operations.length,0);assert.ok(!calls[0].messages[0].content.includes('geometry_parameters'));assert.ok(buildInternalPrompt('workbench',{task:'brief'}).length<1000);assert.equal((await fs.readdir(directory)).includes('ai-validation'),false)
})
test('model tool output is corrected into a requirements-only handoff instead of executed',async t=>{
 const directory=await fs.mkdtemp(path.join(os.tmpdir(),'nbt-brief-repair-'));t.after(()=>fs.rm(directory,{recursive:true,force:true}));let n=0
 const api=createApiService({directory,safeStorage:{},fetchImpl:async()=>{const reply={project_patch:project,...(++n===1?{operations:[{kind:'box',lo:[0,0,0],hi:[0,1,0],state:'stone'}]}:{})};return new Response(JSON.stringify({choices:[{finish_reason:'stop',message:{content:JSON.stringify(reply)}}]}))}})
 await api.save({enabled:true});const result=await api.generate({mode:'workbench',instruction:'编写设计',context:{task:'brief',project:{size:[48,24,48]},operations:[]}});assert.equal(n,2);assert.equal(result.operations,undefined)
})


test('design briefs describe objects and relations while deferring construction choices',()=>{
 const brief=buildInternalPrompt('workbench',{task:'brief'}),prose=buildInternalPrompt('prompt')
 for(const text of [brief,prose]){assert.ok(text.includes('连接关系'));assert.ok(text.includes('实现自由'));assert.ok(text.includes('施工'));assert.ok(!text.includes('geometry_parameters'))}
 assert.ok(brief.includes('用户明确给出的坐标、尺寸与约束可以保留'))
 assert.ok(brief.includes('不返回operations'))
})


test('partial prose suggestions respect human scope and need no geometry worker',async t=>{
 const directory=await fs.mkdtemp(path.join(os.tmpdir(),'nbt-partial-brief-'));t.after(()=>fs.rm(directory,{recursive:true,force:true}));const calls=[]
 const api=createApiService({directory,safeStorage:{},validateCandidate:createCandidateValidator({root:path.resolve(__dirname,'../..'),python:'missing-python.exe',directory,getWorkspace:()=>directory}),fetchImpl:async(_u,o)=>{
  calls.push(JSON.parse(o.body));const patch=calls.length===1?{layout:'沿坡展开',materials:'擅自替换'}:{layout:'沿坡展开'}
  return new Response(JSON.stringify({choices:[{finish_reason:'stop',message:{content:JSON.stringify({project_patch:patch})}}]}))
 }})
 await api.save({enabled:true})
 const result=await api.generate({mode:'workbench',instruction:'只补布局',context:{task:'brief',project:{size:[32,18,40],name:'人工名',style:'石木结构',materials:'铜只用于接头',size_policy:'fixed'},brief_scope:{editable_fields:['layout']},operations:[]}})
 assert.equal(calls.length,2);assert.deepEqual(result.project_patch,{layout:'沿坡展开'})
 assert.ok(calls[1].messages.at(-1).content.includes('未勾选'))
 for(const call of calls)assert.ok(!call.messages[0].content.includes('geometry_parameters'))
 assert.equal((await fs.readdir(directory)).includes('ai-validation'),false)
})

test('length recovery for a brief stays prose-only and retains its edit scope',async t=>{
 const directory=await fs.mkdtemp(path.join(os.tmpdir(),'nbt-brief-length-'));t.after(()=>fs.rm(directory,{recursive:true,force:true}));const calls=[]
 const api=createApiService({directory,safeStorage:{},fetchImpl:async(_u,o)=>{
  calls.push(JSON.parse(o.body));return new Response(JSON.stringify({choices:[{finish_reason:calls.length===1?'length':'stop',message:{content:calls.length===1?'{"project_patch":':JSON.stringify({project_patch:{style:'厚石基座与轻木构'}})}}]}))
 }})
 await api.save({enabled:true});const result=await api.generate({mode:'workbench',instruction:'写设计意图',context:{task:'brief',project:{size:[48,24,48]},brief_scope:{editable_fields:['style']}}})
 assert.equal(result.project_patch.style,'厚石基座与轻木构');assert.equal(calls.length,2)
 const feedback=calls[1].messages.at(-1).content;assert.ok(!feedback.includes('box/beam/frame'));assert.ok(feedback.includes('设计文字'))
 assert.deepEqual(JSON.parse(calls[0].messages[1].content).context.brief_scope,JSON.parse(calls[1].messages[1].content).context.brief_scope)
})

test('prose uses the original at the provider but searches references only with the real topic',async t=>{
 const {excerpts}=require('../../desktop/ai-knowledge.cjs')
 const directory=await fs.mkdtemp(path.join(os.tmpdir(),'nbt-prose-'));t.after(()=>fs.rm(directory,{recursive:true,force:true}));const calls=[]
 const topic='悬索栈桥',original='与检索无关的原稿\n'+('保留原文。'.repeat(3400)),requirements='西塔保留原钟。'
 const api=createApiService({directory,safeStorage:{},workflowContext:(_key,{instruction})=>{
  assert.ok(instruction.includes(topic));assert.ok(!instruction.includes('与检索无关的原稿'));return {knowledge:excerpts([{label:'长资料',content:'甲'.repeat(7350)+topic+'乙'.repeat(750)}],instruction)}
 },fetchImpl:async(_url,options)=>{calls.push(JSON.parse(options.body));return new Response(JSON.stringify({choices:[{finish_reason:'stop',message:{content:'修改后的说明'}}]}))}})
 await api.save({enabled:true})
 const context={task:'design_prose',project:{name:'观测工坊',size:[48,24,48],integration:'saodg',source:'local-private-path'},user_requirements:requirements,original_text:original,operation_intents:[{kind:'box',steps:2}]}
 await api.generate({mode:'prompt',instruction:'只改'+topic+'的最后一句',context});assert.equal(calls.length,1)
 const request=JSON.parse(calls[0].messages[1].content),system=calls[0].messages[0].content;assert.equal(request.context.original_text,original);assert.equal(request.context.project.integration,'saodg');assert.equal(request.context.project.size_policy,'fixed');assert.equal(request.context.user_requirements,requirements);assert.ok(request.internal_workflow.knowledge[0].content.includes(topic));assert.ok(!JSON.stringify(request).includes('local-private-path'));assert.match(system,/其余段落保留原措辞/);assert.match(system,/6 × 净高 5/);assert.doesNotMatch(system,/先合并重复内容|说明用途、空间连接关系/)
 await assert.rejects(api.generate({mode:'prompt',instruction:topic,context:{...context,operation_intents:[{kind:'box',steps:1,lo:[0,0,0]}]}}),/工具意图摘要无效/)
 assert.equal(calls.length,1)
})

test('length recovery for a local revision does not ask the provider to condense untouched prose',async t=>{
 const directory=await fs.mkdtemp(path.join(os.tmpdir(),'nbt-prose-retry-'));t.after(()=>fs.rm(directory,{recursive:true,force:true}));const calls=[]
 const preserved='低廊很窄。\n\n侧窗的光线到达前厅。',original=preserved+'\n\n原来的结尾。',revised=preserved+'\n\n结尾改作等候区。'
 const api=createApiService({directory,safeStorage:{},fetchImpl:async(_url,options)=>{
  calls.push(JSON.parse(options.body));const first=calls.length===1
  return new Response(JSON.stringify({choices:[{finish_reason:first?'length':'stop',message:{content:first?preserved:revised}}]}))
 }})
 await api.save({enabled:true})
 const result=await api.generate({mode:'prompt',instruction:'只改最后一句',context:{task:'design_prose',project:{size:[48,24,48]},original_text:original}})
 assert.equal(result.text,revised);assert.equal(calls.length,2)
 assert.equal(JSON.parse(calls[1].messages[1].content).context.original_text,original)
 assert.match(calls[1].messages.at(-1).content,/不压缩或删除原稿其余内容/)
})
