const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs/promises'),os=require('node:os'),path=require('node:path')
const {createApiService}=require('../desktop/api-service.cjs'),{createCandidateValidator}=require('../desktop/ai-candidate-validator.cjs'),{normalizeReply}=require('../desktop/ai-output-normalize.cjs')
const root=path.resolve(__dirname,'..'),context={task:'draft',project:{size:[16,10,16]},operations:[],existing_model:false}
const patch=Object.fromEntries(['name','theme','purpose','layout','circulation','style','ceiling','floor','wall','props'].map(key=>[key,'完整方案']))
const box={kind:'box',lo:[2,0,2],hi:[4,4,4],state:'stone_bricks'}
async function setup(t){const directory=await fs.mkdtemp(path.join(os.tmpdir(),'nbt-ai-preflight-'));t.after(()=>fs.rm(directory,{recursive:true,force:true}));return directory}

test('actual shared Python engine repairs semantic geometry before accepting an API result',async t=>{
 const directory=await setup(t),requests=[]
 const validator=createCandidateValidator({root,python:process.env.NBTCREATOR_PYTHON||'python',directory,getWorkspace:()=>directory})
 const api=createApiService({directory,safeStorage:{},validateCandidate:validator,fetchImpl:async(_u,options)=>{requests.push(JSON.parse(options.body));const operations=requests.length===1?[{kind:'auto_stairs',lo:[0,0,0],hi:[15,9,15],start:[2,1,2],end:[12,1,2]}]:[box];return new Response(JSON.stringify({choices:[{finish_reason:'stop',message:{content:JSON.stringify({project_patch:patch,operations})}}]}))}})
 await api.save({enabled:true});const result=await api.generate({mode:'workbench',instruction:'生成候选',context});assert.equal(result.api_metrics.attempts,2);assert.match(requests[1].messages.at(-1).content,/第1步.*auto_stairs/);assert.match(requests[1].messages.at(-1).content,/above start/);assert.equal(result.operations[0].kind,'box');assert.deepEqual(result.api_metrics.calls.map(call=>call.validation_status),['failed','passed']);assert.equal(result.api_metrics.calls[0].validation_issue.code,'invalid_geometry');assert.deepEqual(await fs.readdir(path.join(directory,'ai-validation')),[]);assert.equal((await fs.readdir(directory)).includes('nbt_models'),false)
})
test('runtime failures are not sent to the model as geometry mistakes or retried',async t=>{
 const directory=await setup(t),validator=createCandidateValidator({root,python:path.join(directory,'missing-python.exe'),directory,getWorkspace:()=>directory});let calls=0
 const api=createApiService({directory,safeStorage:{},validateCandidate:validator,fetchImpl:async()=>{calls++;return new Response(JSON.stringify({choices:[{finish_reason:'stop',message:{content:JSON.stringify({project_patch:patch,operations:[box]})}}]}))}})
 await api.save({enabled:true});await assert.rejects(api.generate({mode:'workbench',instruction:'候选',context}),/进程无法启动/);assert.equal(calls,1)
 const controller=new AbortController();controller.abort();await assert.rejects(validator({mode:'workbench',result:{},context,signal:controller.signal}),/取消/)
})
test('standard Name/Properties states and structured notes normalize without guessing layer intent',()=>{
 const input={project_patch:{preserve:[],extras:{notes:'保留主路'}},operations:[{...box,state:{Name:'minecraft:oak_log',Properties:{axis:'y'}}}]},result=normalizeReply(input,'workbench',context)
 assert.equal(result.operations[0].state,'minecraft:oak_log[axis=y]');assert.equal(result.project_patch.preserve,'[]');assert.equal(JSON.parse(result.project_patch.extras).notes,'保留主路');assert.equal(typeof input.operations[0].state,'object')
 assert.equal(normalizeReply({operations:[{...box,classification:'structure'}]},'workbench',context).operations[0].classification,'structure')
 assert.deepEqual(normalizeReply({operations:[{...box,state:{Name:'stone',script:'private'}}]},'workbench',context).operations[0].state,{Name:'stone',script:'private'})
 const alternate=normalizeReply({operations:[{type:'box',lo:box.lo,hi:box.hi,state:'stone',common:{classification:'wall',label:'墙层'}},{lo:box.lo,hi:box.hi,state:'stone'}]},'component',{})
 assert.equal(alternate.operations[0].kind,'box');assert.equal(alternate.operations[0].classification,'wall');assert.equal(alternate.operations[0].common,undefined);assert.equal(alternate.operations[1].kind,'box')
 for(const op of [{...box,common:{overwrite:true}},{...box,classification:'wall',common:{classification:'body'}},{...box,type:'beam'}])assert.throws(()=>normalizeReply({operations:[op]},'component',{}))
})
test('cancelling during local geometry preflight aborts validation without another model request',async t=>{
 const directory=await setup(t);let started,calls=0;const waiting=new Promise(resolve=>started=resolve)
 const api=createApiService({directory,safeStorage:{},fetchImpl:async()=>{calls++;return new Response(JSON.stringify({choices:[{finish_reason:'stop',message:{content:JSON.stringify({project_patch:patch,operations:[box]})}}]}))},validateCandidate:({signal})=>new Promise((_resolve,reject)=>{started();signal.addEventListener('abort',()=>reject(Error('几何预检已取消')),{once:true})})})
 await api.save({enabled:true});const pending=api.generate({mode:'workbench',instruction:'候选',context});await waiting;api.cancel();await assert.rejects(pending,/取消/);assert.equal(calls,1)
})
test('version registry reports all invalid materials together before geometry calculation',async t=>{
 const directory=await setup(t),validator=createCandidateValidator({root,python:process.env.NBTCREATOR_PYTHON||'python',directory,getWorkspace:()=>directory})
 await assert.rejects(validator({mode:'small_structure',context:{},result:{settings_patch:{operations:[{...box,state:'tuff_bricks'},{...box,state:'stone[bogus=x]'}]}}}),error=>error.message.includes('tuff_bricks')&&error.message.includes('bogus')&&error.message.includes('一次修正所有步骤'))
 const result=await validator({mode:'small_structure',context:{},result:{settings_patch:{operations:[box]}}});assert.equal(result.block_states,true);assert.equal(result.nbt_exported,false)
})
