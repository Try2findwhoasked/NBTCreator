const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs/promises'),os=require('node:os'),path=require('node:path')
const {createApiService}=require('../desktop/api-service.cjs')
async function service(t,fetchImpl){const directory=await fs.mkdtemp(path.join(os.tmpdir(),'nbt-character-limit-'));t.after(()=>fs.rm(directory,{recursive:true,force:true}));return createApiService({directory,safeStorage:{},fetchImpl})}
const response=text=>new Response(JSON.stringify({choices:[{finish_reason:'stop',message:{content:text}}]}))
test('first request carries the saved character ceiling and oversized text is regenerated, not cut',async t=>{
 const calls=[];const api=await service(t,async(_u,o)=>{const p=JSON.parse(o.body);calls.push(p);return response('😀'.repeat(calls.length===1?101:100))})
 await api.save({enabled:true,outputCharLimit:100});assert.equal((await api.load()).outputCharLimit,100)
 const r=await api.generate({mode:'prompt',instruction:'简短描述'});assert.equal(Array.from(r.text).length,100);assert.equal(r.api_metrics.attempts,2);assert.ok(calls[0].messages[0].content.includes('输出限制为 100 字'));assert.equal(calls[0].messages.length,2);assert.ok(calls[1].messages.at(-1).content.includes('超过 100 字'));assert.equal(calls[1].messages[2].content,'😀'.repeat(101))
 for(const outputCharLimit of [99,60001,1.5,'100',null])await assert.rejects(api.save({outputCharLimit}))
})
test('format and geometry feedback repair within three requests against the same original context',async t=>{
 const calls=[];const api=await service(t,async(_u,o)=>{calls.push(JSON.parse(o.body));return response(calls.length===1?'not json':JSON.stringify({boxes:[[calls.length===2?999:1,0,1,calls.length===2?999:1,2,1,'stone']]}))})
 await api.save({enabled:true});const r=await api.generate({mode:'small_structure',instruction:'一根柱子',context:{size:[48,16,48],lo:[8,4,8],hi:[15,10,15]}})
 assert.equal(r.api_metrics.attempts,3);assert.deepEqual(r.settings_patch.operations[0].lo,[9,4,9]);assert.ok(calls[1].messages.at(-1).content.includes('JSON'));assert.ok(calls[2].messages.at(-1).content.includes('超出'));assert.equal(calls[0].messages[1].content,calls[2].messages[1].content);assert.equal(calls[2].messages.length,4)
})
test('repair stops at three requests and transport failures do not trigger format retries',async t=>{
 let n=0;const api=await service(t,async()=>{n++;return response('bad json')});await api.save({enabled:true});await assert.rejects(api.generate({mode:'small_structure',instruction:'柱子',context:{size:[4,4,4],lo:[0,0,0],hi:[3,3,3]}}),e=>e.api_metrics.attempts===3);assert.equal(n,3)
 let httpCalls=0;const http=await service(t,async()=>{httpCalls++;return new Response('private',{status:401})});await http.save({enabled:true});await assert.rejects(http.generate({mode:'prompt',instruction:'文字'}),/401/);assert.equal(httpCalls,1)
})
test('cancellation during a correction aborts the active request and does not start another',async t=>{
 let calls=0,started;const waiting=new Promise(resolve=>started=resolve),api=await service(t,async(_u,o)=>{if(++calls===1)return response('bad json');started();return new Promise((_resolve,reject)=>o.signal.addEventListener('abort',()=>reject(new DOMException('aborted','AbortError'))))})
 await api.save({enabled:true});const pending=api.generate({mode:'small_structure',instruction:'柱子',context:{size:[4,4,4],lo:[0,0,0],hi:[3,3,3]}});await waiting;api.cancel();await assert.rejects(pending);assert.equal(calls,2)
})
