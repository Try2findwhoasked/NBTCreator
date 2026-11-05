const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs/promises'),os=require('node:os'),path=require('node:path')
const {extractResult}=require('../desktop/ai-result-extract.cjs'),{createApiService}=require('../desktop/api-service.cjs')
test('extracts only a complete unambiguous final result without deleting literal data',()=>{
 assert.deepEqual(extractResult('<think>考虑 {"example":1}</think>\n说明\n```json\n{"boxes":[[0,0,0,0,0,0,"stone"]]}\n```\n结束','component').parsed.boxes[0],[0,0,0,0,0,0,'stone'])
 assert.equal(extractResult('说明\n<final>正文</final>\n其他说明','prompt').text,'正文')
 assert.equal(extractResult('{"text":"<think>literal</think> and } and \\\""}','component').parsed.text,'<think>literal</think> and } and "')
 assert.deepEqual(extractResult('结果如下： {"a":{"b":"}"}} 附注','component').parsed,{a:{b:'}'}})
 assert.deepEqual(extractResult('<final>{"text":"```json literal```"}</final>','component').parsed,{text:'```json literal```'})
 for(const text of ['<think>{"a":1}','<final>{"a":1}','<final>{"a":1}</final>\n<final>{','{"a":1} {"b":2}','{"a":1} {','[{"a":1}]','<final>[{"a":1}]</final>'])assert.throws(()=>extractResult(text,'component'))
})
test('unlimited mode takes final text only, while explicit limits apply only to the extracted answer',async t=>{
 const directory=await fs.mkdtemp(path.join(os.tmpdir(),'nbt-extract-'));t.after(()=>fs.rm(directory,{recursive:true,force:true}));let payload
 let answer='最终正文'
 const api=createApiService({directory,safeStorage:{},fetchImpl:async(_u,o)=>{payload=JSON.parse(o.body);return new Response(JSON.stringify({choices:[{finish_reason:'stop',message:{reasoning_content:'private separate reasoning',content:'<think>'+('思考'.repeat(5000))+'</think>\n<final>'+answer+'</final>'}}]}))}})
 await api.save({enabled:true,outputCharLimit:100});assert.equal((await api.generate({mode:'prompt',instruction:'正文'})).text,'最终正文')
 answer='字'.repeat(15000);await api.save({outputCharLimit:0,requestOptions:{max_tokens:32768}});assert.equal((await api.generate({mode:'prompt',instruction:'正文'})).text,answer);assert.ok(payload.messages[0].content.includes('不设应用字数限制'));assert.equal(JSON.stringify(payload).includes('private separate reasoning'),false)
})
test('a complete validated JSON can survive a length finish; incomplete JSON and unmarked prose cannot',async t=>{
 const directory=await fs.mkdtemp(path.join(os.tmpdir(),'nbt-extract-length-'));t.after(()=>fs.rm(directory,{recursive:true,force:true}));let text='```json\n{"boxes":[[0,0,0,0,1,0,"stone"]]}\n```\n未完的附注',calls=0
 const api=createApiService({directory,safeStorage:{},fetchImpl:async()=>{calls++;return new Response(JSON.stringify({choices:[{finish_reason:'length',message:{content:text}}]}))}});await api.save({enabled:true})
 const input={mode:'small_structure',instruction:'柱子',context:{size:[4,4,4],lo:[0,0,0],hi:[3,3,3]}}
 assert.equal((await api.generate(input)).settings_patch.operations.length,1);assert.equal(calls,1)
 text='{"boxes":[';await assert.rejects(api.generate(input));assert.equal(calls,3)
 text='未完成的文字';await assert.rejects(api.generate({mode:'prompt',instruction:'正文'}));assert.equal(calls,5)
 text='<final>完成的正文</final>\n未完的附注';assert.equal((await api.generate({mode:'prompt',instruction:'正文'})).text,'完成的正文');assert.equal(calls,6)
})
test('official DeepSeek defaults disable thinking, explicit choices remain authoritative and usage is separated',async t=>{
 const directory=await fs.mkdtemp(path.join(os.tmpdir(),'nbt-thinking-'));t.after(()=>fs.rm(directory,{recursive:true,force:true}));let payload
 const api=createApiService({directory,safeStorage:{},fetchImpl:async(_u,o)=>{payload=JSON.parse(o.body);return new Response(JSON.stringify({choices:[{finish_reason:'stop',message:{content:'正文',reasoning_content:'private'}}],usage:{completion_tokens:12,completion_tokens_details:{reasoning_tokens:10}}}))}})
 await api.save({enabled:true});const r=await api.generate({mode:'prompt',instruction:'正文'});assert.equal(payload.thinking.type,'disabled');assert.equal(r.api_metrics.reasoning_tokens,10);assert.equal(r.api_metrics.calls[0].reasoning_tokens,10)
 await api.save({requestOptions:{thinking:{type:'enabled'}}});await api.generate({mode:'prompt',instruction:'正文'});assert.equal(payload.thinking.type,'enabled')
 await api.save({provider:'compatible',baseUrl:'http://localhost:9999',requestOptions:{}});await api.generate({mode:'prompt',instruction:'正文'});assert.equal(payload.thinking,undefined)
})
