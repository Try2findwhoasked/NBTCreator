const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs/promises'),os=require('node:os'),path=require('node:path')
const {createApiService,validatePatch,configOf}=require('../desktop/api-service.cjs')
const storage={isAsyncEncryptionAvailable:async()=>true,encryptStringAsync:async s=>Buffer.from(s).map(v=>v^123),decryptStringAsync:async b=>({result:Buffer.from(b).map(v=>v^123).toString(),shouldReEncrypt:false})}
const context={size:[48,16,48],lo:[8,4,8],hi:[15,10,15],materials:[{state:'stone_bricks',count:1}]}
const result={summary:'添加一根柱子',settings_patch:{lo:[10,4,10],hi:[10,7,10],structure:{enabled:true,mode:'fill',state:'stone_bricks',classification:'body',thickness:1,offset:[0,0,0]}}}
test('internal skill replaces repeated built-in workflow prose while retaining user rules and selected knowledge',async()=>{
 let payload;const directory=await fs.mkdtemp(path.join(os.tmpdir(),'nbt-internal-short-'))
 const api=createApiService({directory,safeStorage:storage,workflowContext:async()=>({workflow:'structure',base_rules:'REDUNDANT_BUILTIN_RULES',workflow_steps:'REDUNDANT_STEPS',rules:'USER_CUSTOM_RULE',instruction:'USER_INSTRUCTION',knowledge:[{label:'选择的资料',content:'USER_SELECTED_KNOWLEDGE'}]}),fetchImpl:async(_u,o)=>{payload=JSON.parse(o.body);return new Response(JSON.stringify({choices:[{message:{content:JSON.stringify(result)},finish_reason:'stop'}]}))}})
 try{await api.save({enabled:true});await api.generate({mode:'structure',instruction:'添加柱子',context});const sent=JSON.stringify(payload);assert.ok(!sent.includes('REDUNDANT_'));for(const text of ['USER_CUSTOM_RULE','USER_INSTRUCTION','USER_SELECTED_KNOWLEDGE'])assert.ok(sent.includes(text));assert.ok(payload.messages[0].content.includes('settings_patch'));assert.equal(payload.response_format.type,'json_object')}finally{await fs.rm(directory,{recursive:true,force:true})}
})
async function service(fetchImpl){const directory=await fs.mkdtemp(path.join(os.tmpdir(),'nbt-api-'));return {directory,api:createApiService({directory,safeStorage:storage,fetchImpl}),close:()=>fs.rm(directory,{recursive:true,force:true})}}
test('disabled configuration never performs network calls',async()=>{let calls=0;const s=await service(async()=>{calls++});try{await s.api.load();await assert.rejects(s.api.models(),/关闭/);assert.equal(calls,0)}finally{await s.close()}})
test('encrypted key retained but never returned; explicit deletion',async()=>{const s=await service();try{await s.api.save({key:'mock-secret',enabled:true});assert.equal((await s.api.load()).hasKey,true);assert.ok(!(await fs.readFile(path.join(s.directory,'api-settings.json'),'utf8')).includes('mock-secret'));await s.api.save({enabled:false});assert.equal(s.api.publicConfig().hasKey,true);await s.api.save({clearKey:true});assert.equal(s.api.publicConfig().hasKey,false)}finally{await s.close()}})
test('prompt request only transmits reduced context and model headers',async()=>{let body;const s=await service(async(_url,opts)=>{body=JSON.parse(opts.body);assert.equal(opts.headers.Authorization,'Bearer mock-secret');return new Response(JSON.stringify({choices:[{message:{content:'建模提示词正文'},finish_reason:'stop'}]}))});try{await s.api.save({enabled:true,key:'mock-secret'});const r=await s.api.generate({mode:'prompt',instruction:'设计石柱',context:{...context,source:'private-path',blocks:['do not send']}});assert.equal(r.text,'建模提示词正文');assert.ok(!JSON.stringify(body).includes('private-path'));assert.ok(!JSON.stringify(body).includes('do not send'))}finally{await s.close()}})
test('restricted structure accepted and JSON output requested',async()=>{const s=await service(async(_url,opts)=>{assert.equal(JSON.parse(opts.body).response_format.type,'json_object');assert.equal(JSON.parse(opts.body).max_tokens,12288);return new Response(JSON.stringify({choices:[{message:{content:JSON.stringify(result)},finish_reason:'stop'}]}))});try{await s.api.save({enabled:true});assert.deepEqual((await s.api.generate({mode:'structure',instruction:'添加柱子',context})).settings_patch,result.settings_patch)}finally{await s.close()}})
test('arbitrary fields, code, out of selection and invalid states rejected',()=>{assert.throws(()=>validatePatch({...result,code:'exec'},context));assert.throws(()=>validatePatch({...result,settings_patch:{...result.settings_patch,lo:[0,0,0]}},context));assert.throws(()=>validatePatch({...result,settings_patch:{...result.settings_patch,structure:{...result.settings_patch.structure,state:'$evil'}}},context));assert.throws(()=>configOf({baseUrl:'http://example.com'}));assert.throws(()=>configOf({baseUrl:'https://user:password@example.com'}))})
test('empty and truncated outputs are reported; response error body never exposed',async()=>{for(const data of [{choices:[{message:{content:' '}}]},{choices:[{message:{content:'x'},finish_reason:'length'}]}]){const s=await service(async()=>new Response(JSON.stringify(data)));try{await s.api.save({enabled:true});await assert.rejects(s.api.generate({mode:'prompt',instruction:'task',context}))}finally{await s.close()}}const s=await service(async()=>new Response('mock-secret',{status:401}));try{await s.api.save({enabled:true});await assert.rejects(s.api.models(),e=>e.message.includes('401')&&!e.message.includes('mock-secret'))}finally{await s.close()}})
test('cancel in-flight request and reject concurrency',async()=>{const s=await service((_url,opts)=>new Promise((_resolve,reject)=>opts.signal.addEventListener('abort',()=>reject(new DOMException('cancel','AbortError')))));try{await s.api.save({enabled:true});const pending=s.api.models();await new Promise(r=>setImmediate(r));await assert.rejects(s.api.models(),/已有/);await assert.rejects(s.api.save({enabled:false}),/进行中/);s.api.cancel();await assert.rejects(pending,/取消/)}finally{await s.close()}})
test('changed server does not inherit previous key; broken optional config keeps offline mode',async()=>{const s=await service();try{await s.api.save({enabled:true,key:'mock-secret'});await s.api.save({baseUrl:'https://other.example/v1',provider:'compatible',enabled:true});assert.equal(s.api.publicConfig().hasKey,false);await fs.writeFile(path.join(s.directory,'api-settings.json'),'{broken');const loaded=await s.api.load();assert.equal(loaded.enabled,false);assert.equal(loaded.hasKey,false)}finally{await s.close()}})

test('small structures reject out-of-region geometry, air, excess work and unsafe beam widths',()=>{
 const {validateSmallStructure}=require('../desktop/api-service.cjs')
 const ctx={size:[48,24,48],lo:[4,4,4],hi:[15,15,15]}
 const op={kind:'box',label:'柱',classification:'body',lo:[6,4,6],hi:[6,8,6],state:'stone_bricks'}
 const proposal=operation=>({summary:'局部小构件',settings_patch:{lo:ctx.lo,hi:ctx.hi,operations:[operation]}})
 assert.deepEqual(validateSmallStructure(proposal(op),ctx).settings_patch.operations,[op])
 assert.throws(()=>validateSmallStructure(proposal({...op,hi:[16,8,6]}),ctx),/超出/)
 assert.equal(validateSmallStructure(proposal({...op,state:'air'}),ctx).settings_patch.operations[0].state,'air')
 assert.throws(()=>validateSmallStructure(proposal({...op,script:'exec'}),ctx))
 assert.throws(()=>validateSmallStructure(proposal({...op,kind:'beam',start:[6,4,6],end:[6,8,6],width:5}),ctx),/厚度/)
 assert.throws(()=>validateSmallStructure({...proposal(op),settings_patch:{lo:ctx.lo,hi:ctx.hi,operations:Array(129).fill(op)}},ctx),/128步/)
})

 test('internal workflow reference reaches only its associated API invocation',async()=>{
  let payload;const directory=await fs.mkdtemp(path.join(os.tmpdir(),'nbt-flow-api-'))
  const api=createApiService({directory,safeStorage:storage,workflowContext:async key=>({workflow:key,rules:'custom-rule',knowledge:[{label:'reference',content:'selected-reference'}]}),fetchImpl:async(_u,o)=>{payload=JSON.parse(o.body);return new Response(JSON.stringify({choices:[{message:{content:'text'},finish_reason:'stop'}]}))}})
  try{await api.save({enabled:true});await api.generate({mode:'prompt',instruction:'task',context:null});const sent=JSON.parse(payload.messages[1].content);assert.equal(sent.internal_workflow.workflow,'prompt');assert.equal(sent.internal_workflow.knowledge[0].content,'selected-reference')}finally{await fs.rm(directory,{recursive:true,force:true})}
 })

test('local small structure coordinates translate exactly once and reject out-of-bounds',()=>{
 const {localSmallStructure}=require('../desktop/api-service.cjs')
 const c={size:[48,24,48],lo:[10,4,20],hi:[16,11,26]}
 const r={coordinate_space:'local',summary:'柱',settings_patch:{lo:[0,0,0],hi:[6,7,6],operations:[{kind:'box',label:'柱',classification:'body',lo:[2,0,2],hi:[2,4,2],state:'stone_bricks'}]}}
 const translated=localSmallStructure(r,c);assert.deepEqual(translated.settings_patch.operations[0].lo,[12,4,22]);assert.deepEqual(r.settings_patch.operations[0].lo,[2,0,2])
 assert.throws(()=>localSmallStructure({...r,coordinate_space:'global'},c),/相对坐标/)
 assert.throws(()=>localSmallStructure({...r,settings_patch:{...r.settings_patch,hi:[7,7,6]}},c),/选区/)
})

test('small structure presentation accepts one bounded angle and a name, retaining legacy output support',()=>{
 const {localSmallStructure}=require('../desktop/api-service.cjs')
 const proposal={structure_name:'带帽石柱',camera:{azimuth:90,elevation:25},operations:[{pos:[1,0,1],state:'stone'}]}
 const normalized=localSmallStructure(proposal,context);assert.equal(normalized.structure_name,'带帽石柱');assert.deepEqual(normalized.camera,proposal.camera);assert.deepEqual(normalized.settings_patch.operations[0].lo,[9,4,9])
 const old=localSmallStructure({blocks:[{pos:[0,0,0],state:'stone'}]},context);assert.ok(old.structure_name);assert.deepEqual(old.camera,{azimuth:45,elevation:25})
 for(const camera of [[],null,{azimuth:181,elevation:0},{azimuth:0,elevation:Infinity},{azimuth:0,elevation:0,eye:[1,2,3]}])assert.throws(()=>localSmallStructure({...proposal,camera},context))
 for(const structure_name of ['',{},'x'.repeat(121)])assert.throws(()=>localSmallStructure({...proposal,structure_name},context))
})

test('small components normalize missing fields, relative blocks and beam bounds',()=>{
 const {localSmallStructure}=require('../desktop/api-service.cjs');const c={size:[48,24,48],lo:[10,4,20],hi:[20,15,30],materials:[]}
 const blocks=localSmallStructure({blocks:[{pos:['1','2','3'],block:{Name:'minecraft:oak_stairs',Properties:{facing:'east',half:'bottom'}}}]},c)
 assert.deepEqual(blocks.settings_patch.operations[0].lo,[11,6,23]);assert.ok(blocks.settings_patch.operations[0].state.includes('facing=east'))
 const steps=localSmallStructure({operations:[{kind:'beam',start:[1,1,1],end:[5,5,5],state:'oak_log'},{kind:'carve',pos:[2,2,2]}]},c)
 assert.equal(steps.settings_patch.operations[0].width,1);assert.equal(steps.settings_patch.operations[1].state,'air')
 assert.equal(localSmallStructure({operations:Array.from({length:64},(_,i)=>({pos:[i%8,0,Math.floor(i/8)],state:'stone'}))},c).settings_patch.operations.length,64)
 assert.throws(()=>localSmallStructure({blocks:[{pos:[11,1,1],state:'stone'}]},c),/超出/)
})

test('viewport attachments use image messages only for explicitly enabled workflows',async()=>{
 const directory=await fs.mkdtemp(path.join(os.tmpdir(),'nbt-image-api-'));let payload,enabled=true
 const api=createApiService({directory,safeStorage:storage,workflowContext:async()=>({attachViewport:enabled}),fetchImpl:async(_u,o)=>{payload=JSON.parse(o.body);return new Response(JSON.stringify({choices:[{message:{content:'text'},finish_reason:'stop'}]}))}})
 const input={mode:'prompt',instruction:'查看当前画面',context:null,viewport:{dataUrl:'data:image/jpeg;base64,/9j/2Q==',width:64,height:64}}
 try{await api.save({enabled:true});await api.generate(input);assert.equal(payload.messages[1].content[1].type,'image_url');await assert.rejects(api.generate({...input,viewport:{...input.viewport,dataUrl:'https://external/image'}}),/截图格式/);enabled=false;await assert.rejects(api.generate(input),/未启用/)}finally{await fs.rm(directory,{recursive:true,force:true})}
})

test('truncated small structure retries once with compact geometry and records bounded usage',async()=>{
 let calls=0;const s=await service(async(_url,opts)=>{const body=JSON.parse(opts.body);calls++;if(calls===1)return new Response(JSON.stringify({choices:[{message:{content:'{"blocks":['},finish_reason:'length'}]}));assert.ok(body.messages[0].content.includes('最多24个'));return new Response(JSON.stringify({choices:[{message:{content:JSON.stringify({operations:[{kind:'box',lo:[1,0,1],hi:[1,3,1],state:'stone'}]})},finish_reason:'stop'}],usage:{prompt_tokens:100,completion_tokens:80,total_tokens:180,private_field:'do not persist'}}))});try{await s.api.save({enabled:true});const result=await s.api.generate({mode:'small_structure',instruction:'石柱',context});assert.equal(calls,2);assert.deepEqual(result.settings_patch.operations[0].lo,[9,4,9]);assert.equal(result.api_metrics.attempts,2);assert.equal(result.api_metrics.retried_compact,true);assert.equal(result.api_metrics.total_tokens,180);assert.equal(result.api_metrics.calls[0].finish_reason,'length');assert.equal(result.api_metrics.calls[1].total_tokens,180);assert.equal(result.api_metrics.calls[0].total_tokens,undefined);assert.equal(JSON.stringify(result.api_metrics).includes('do not persist'),false)}finally{await s.close()}
})
test('repeated truncation never applies partial geometry or loops; cancellation covers workflow preparation',async()=>{
 let calls=0;const s=await service(async()=>{calls++;return new Response(JSON.stringify({choices:[{message:{content:'{"blocks":['},finish_reason:'length'}],usage:{completion_tokens:12288}}))});try{await s.api.save({enabled:true});await assert.rejects(s.api.generate({mode:'small_structure',instruction:'石柱',context}),/重试1次.*24576/);assert.equal(calls,2)}finally{await s.close()}
 const directory=await fs.mkdtemp(path.join(os.tmpdir(),'nbt-api-prepare-'));let release,network=0;const api=createApiService({directory,safeStorage:storage,workflowContext:()=>new Promise(resolve=>release=resolve),fetchImpl:async()=>{network++;return new Response('{}')}});try{await api.save({enabled:true});const pending=api.generate({mode:'prompt',instruction:'task',context:null});await assert.rejects(api.generate({mode:'prompt',instruction:'duplicate',context:null}),/已有/);api.cancel();release(null);await assert.rejects(pending,/取消/);assert.equal(network,0)}finally{await fs.rm(directory,{recursive:true,force:true})}
})

test('measurements cover response wait, parse and local rejection without persisting API content',async()=>{
 const s=await service(async()=>{await new Promise(resolve=>setTimeout(resolve,15));return new Response(JSON.stringify({choices:[{message:{content:JSON.stringify({...result,settings_patch:{...result.settings_patch,lo:[0,0,0]}})},finish_reason:'stop'}],usage:{prompt_tokens:12,completion_tokens:8,total_tokens:20}}))})
 try{
  await s.api.save({enabled:true,key:'private-key'})
  await assert.rejects(s.api.generate({mode:'structure',instruction:'在选区添加柱子',context}),error=>{
   const m=error.api_metrics;assert.match(error.message,/超出/);assert.equal(m.attempts,1);assert.ok(m.calls[0].headers_ms>=1);assert.ok(m.calls[0].elapsed_ms>=m.calls[0].headers_ms);assert.ok(m.service_total_ms>=m.calls[0].elapsed_ms);assert.ok(m.validation_ms>=0);assert.equal(m.calls[0].status,'complete');assert.equal(m.total_tokens,20);assert.ok(m.calls[0].response_bytes>0);assert.ok(!JSON.stringify(m).includes('private-key'));assert.ok(!JSON.stringify(m).includes('添加柱子'));return true
  })
 }finally{await s.close()}
})

test('HTTP failures, cancellation and repeated truncation retain individual attempt measurements',async()=>{
 const s=await service(async()=>new Response('private provider body',{status:429}))
 try{await s.api.save({enabled:true});await assert.rejects(s.api.generate({mode:'prompt',instruction:'task',context:null}),error=>{assert.equal(error.api_metrics.calls[0].http_status,429);assert.equal(error.api_metrics.calls[0].status,'failed');assert.ok(!JSON.stringify(error.api_metrics).includes('private'));return true})}finally{await s.close()}
 const cancelled=await service((_url,opts)=>new Promise((_resolve,reject)=>opts.signal.addEventListener('abort',()=>reject(new DOMException('abort','AbortError')))))
 try{await cancelled.api.save({enabled:true});const pending=cancelled.api.generate({mode:'prompt',instruction:'task',context:null});await new Promise(resolve=>setImmediate(resolve));cancelled.api.cancel();await assert.rejects(pending,error=>{assert.equal(error.api_metrics.calls[0].status,'cancelled');assert.ok(error.api_metrics.service_total_ms>=0);return true})}finally{await cancelled.close()}
 let attempt=0;const retry=await service(async()=>{attempt++;return new Response(JSON.stringify({choices:[{message:{content:attempt===1?'partial':JSON.stringify({blocks:[{pos:[0,0,0],state:'stone'}]})},finish_reason:attempt===1?'length':'stop'}],usage:{prompt_tokens:10,completion_tokens:attempt*5,total_tokens:10+attempt*5}}))})
 try{await retry.api.save({enabled:true});const r=await retry.api.generate({mode:'small_structure',instruction:'柱',context});assert.equal(r.api_metrics.prompt_tokens,20);assert.equal(r.api_metrics.completion_tokens,15);assert.equal(r.api_metrics.total_tokens,35);assert.equal(r.api_metrics.calls.length,2);assert.ok(r.api_metrics.calls[1].input_text_chars>r.api_metrics.calls[0].input_text_chars)}finally{await retry.close()}
})

test('workbench script binds a compact delta without sending or asking AI to copy hashes',async()=>{
 const input={mode:'workbench',instruction:'第12步改安山岩',context:{project:{size:[48,24,48]},baseline_binding:'a'.repeat(64),operations:Array.from({length:60},()=>({kind:'box',label:'墙段',classification:'wall',lo:[2,1,2],hi:[20,8,2],state:'stone_bricks'}))}}
 let responseChars=0
 const s=await service(async(_url,opts)=>{
  const sent=JSON.parse(JSON.parse(opts.body).messages[1].content)
  assert.equal(sent.context.operations.length,60);assert.equal(sent.context.operation_base,undefined);assert.equal(sent.context.baseline_binding,undefined);assert.equal(JSON.parse(opts.body).max_tokens,12288)
  const content=JSON.stringify({summary:'改墙面',operation_patch:{changes:[{step:12,set:{state:'andesite'}}]}});responseChars=content.length
  return new Response(JSON.stringify({choices:[{message:{content},finish_reason:'stop'}]}))
 })
 try{await s.api.save({enabled:true});const r=await s.api.generate(input);assert.equal(r.operations.length,60);assert.match(r.operation_patch.baseline,/^[a-f0-9]{64}$/);assert.match(r.operation_patch.changes[0].expected,/^[a-f0-9]{64}$/);assert.equal(r.operations[11].state,'andesite');assert.equal(input.context.operations[11].state,'stone_bricks');assert.equal(r.api_metrics.operation_changes,1);assert.equal(r.api_metrics.output_chars,responseChars);assert.ok(responseChars<JSON.stringify(r.operations).length/10)}finally{await s.close()}
})

test('independent asset creation sends a reduced library reference and returns the shared spec without needing a source model',async()=>{
 let sent,bad=false
 const s=await service(async(_url,options)=>{sent=JSON.parse(options.body);return new Response(JSON.stringify({choices:[{finish_reason:'stop',message:{content:JSON.stringify({name:'AI别名',size:bad?[8,8,8]:[7,8,7],operations:[{kind:'box',label:'柱',classification:'body',lo:[2,0,2],hi:[4,5,4],state:'stone_bricks'}],camera:{azimuth:45,elevation:25}})}}]}))})
 const input={mode:'component',instruction:'独立石柱',context:{name:'指定名称',size:[7,8,7],source:'private-path',references:[{id:'a'.repeat(32),content_sha256:'b'.repeat(64),name:'参考柱',size:[3,6,3],palette:['stone_bricks'],blocks:['do-not-send'],file:'private-file'}]}}
 try{await s.api.save({enabled:true});const r=await s.api.generate(input);assert.equal(r.mode,'component');assert.equal(r.spec.name,'指定名称');assert.deepEqual(r.spec.size,[7,8,7]);assert.ok(sent.messages[0].content.includes('"placements"'));assert.ok(!JSON.stringify(sent).includes('private-path'));assert.ok(!JSON.stringify(sent).includes('private-file'));assert.ok(!JSON.stringify(sent).includes('do-not-send'));bad=true;await assert.rejects(s.api.generate(input),/不能更改/)}finally{await s.close()}
})

test('advanced API options reach actual request while protocol and secrets remain application-owned',async()=>{let payload;const s=await service(async(_url,options)=>{payload=JSON.parse(options.body);return new Response(JSON.stringify({choices:[{message:{content:'ok'},finish_reason:'stop'}]}))});try{await s.api.save({enabled:true,timeoutMs:120000,tokenParameter:'max_completion_tokens',requestOptions:{temperature:.4,top_p:.85,max_tokens:2048,presence_penalty:.2,frequency_penalty:-.1,seed:123,stop:['END'],reasoning_effort:'low',thinking:{type:'disabled'}}});await s.api.generate({mode:'prompt',instruction:'test'});assert.equal(payload.max_completion_tokens,2048);assert.equal(payload.max_tokens,undefined);assert.equal(payload.temperature,.4);assert.deepEqual(payload.stop,['END']);assert.equal(payload.stream,false);assert.equal(payload.messages.length,2);assert.equal(payload.thinking.type,'disabled');await s.api.save({enabled:false});assert.equal((await s.api.load()).requestOptions.max_tokens,2048);assert.equal(s.api.publicConfig().timeoutMs,120000);for(const requestOptions of [{messages:[]},{Authorization:'secret'},{response_format:{type:'text'}},{max_tokens:1.5},{temperature:3},{stop:['']},{seed:NaN},{thinking:{type:'enabled',code:'bad'}}])await assert.rejects(s.api.save({requestOptions}));await assert.rejects(s.api.save({timeoutMs:1}));assert.equal((await s.api.load()).requestOptions.temperature,.4)}finally{await s.close()}})
