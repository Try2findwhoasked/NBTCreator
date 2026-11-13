const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs/promises'),os=require('node:os'),path=require('node:path')
const {createApiService}=require('../desktop/api-service.cjs')
const {createAiScheduler}=require('../desktop/ai-scheduler.cjs')
const tick=()=>new Promise(r=>setImmediate(r)),response=text=>new Response(JSON.stringify({choices:[{finish_reason:'stop',message:{content:text}}]}))
test('two suggestions overlap, third waits, targeted cancellation does not abort its neighbour',async()=>{
 const directory=await fs.mkdtemp(path.join(os.tmpdir(),'nbt-ai-parallel-'));const calls=[]
 const api=createApiService({directory,safeStorage:{},fetchImpl:(_u,o)=>new Promise((resolve,reject)=>{const instruction=JSON.parse(o.body).messages[1].content;calls.push({instruction,signal:o.signal,resolve});o.signal.addEventListener('abort',()=>reject(new DOMException('cancel','AbortError')))})})
 try{await api.save({enabled:true,maxConcurrent:2});const run=id=>api.generate({mode:'prompt',instruction:id},{requestId:id})
  const a=run('parallel-request-0001'),b=run('parallel-request-0002'),c=run('parallel-request-0003');const failed=assert.rejects(a,/取消/)
  await tick();assert.equal(calls.length,2);assert.deepEqual(api.state(),{running:2,queued:1,limit:2})
  api.cancel('parallel-request-0001');await failed;await tick();assert.equal(calls.length,3);assert.equal(calls[1].signal.aborted,false)
  calls[1].resolve(response('second'));calls[2].resolve(response('third'));assert.equal((await b).text,'second');assert.equal((await c).text,'third');assert.equal(api.state().running,0)
 }finally{api.cancel();await fs.rm(directory,{recursive:true,force:true})}
})

test('queue freezes input and prepares workspace context at admission; provider failures free the next slot',async()=>{
 const directory=await fs.mkdtemp(path.join(os.tmpdir(),'nbt-ai-snapshot-'));const calls=[];let revision=1,prepared=[]
 const api=createApiService({directory,safeStorage:{},workflowContext:async()=>{prepared.push(revision);return {user_rules:'revision '+revision}},fetchImpl:(_u,o)=>new Promise((resolve,reject)=>calls.push({body:JSON.parse(o.body),resolve,reject}))})
 try{await api.save({enabled:true,maxConcurrent:1});const input={mode:'prompt',instruction:'before'}
  const a=api.generate({mode:'prompt',instruction:'first'},{requestId:'snapshot-request-0001'}),b=api.generate(input,{requestId:'snapshot-request-0002'});input.instruction='after';await tick();revision=2
  const rejected=assert.rejects(a,/连接/);calls[0].reject(Error('network failed'));await rejected;await tick();assert.equal(calls.length,2);assert.deepEqual(prepared,[1,1]);assert.match(calls[1].body.messages[1].content,/before/);assert.doesNotMatch(calls[1].body.messages[1].content,/after/);calls[1].resolve(response('saved'));await b
 }finally{api.cancel();await fs.rm(directory,{recursive:true,force:true})}
})

test('scheduler rejects overload, duplicate live IDs, and drains cancellation without leaking queued entries',async()=>{
 const scheduler=createAiScheduler({limit:()=>1,maxPending:2});let finish
 const a=scheduler.run('bounded-request-0001',()=>new Promise(resolve=>finish=resolve));await tick()
 const b=scheduler.run('bounded-request-0002',()=>assert.fail('cancelled queued operation ran'));const cancelled=assert.rejects(b,{code:'AI_CANCELLED'})
 await assert.rejects(scheduler.run('bounded-request-0002',()=>{}),{code:'REQUEST_IN_PROGRESS'})
 await assert.rejects(scheduler.run('bounded-request-0003',()=>{}),{code:'AI_QUEUE_FULL'})
 scheduler.cancel('bounded-request-0002');await cancelled;assert.equal(scheduler.size,1);finish('done');await a;assert.equal(scheduler.size,0)
})

test('configuration writes are exclusive so a provider or key cannot change beneath a generation',async()=>{
 const directory=await fs.mkdtemp(path.join(os.tmpdir(),'nbt-ai-config-'));let finishEncryption
 const api=createApiService({directory,safeStorage:{isAsyncEncryptionAvailable:async()=>true,encryptStringAsync:()=>new Promise(resolve=>finishEncryption=resolve)},fetchImpl:async()=>response('result')})
 try{const saving=api.save({enabled:true,key:'synthetic'});await tick();await assert.rejects(api.generate({mode:'prompt',instruction:'during save'}),/配置保存/);await assert.rejects(api.save({model:'different'}),/保存/);finishEncryption(Buffer.from('encrypted'));await saving;assert.equal(api.publicConfig().model,'deepseek-flash')}
 finally{api.cancel();await fs.rm(directory,{recursive:true,force:true})}
})
test('queued cancellation never calls provider and leaves the running request alive',async()=>{
 const directory=await fs.mkdtemp(path.join(os.tmpdir(),'nbt-ai-queue-'));let release,calls=0
 const api=createApiService({directory,safeStorage:{},fetchImpl:()=>{calls++;return new Promise(r=>release=r)}})
 try{await api.save({enabled:true,maxConcurrent:1});const a=api.generate({mode:'prompt',instruction:'first'},{requestId:'queue-request-0001'}),b=api.generate({mode:'prompt',instruction:'second'},{requestId:'queue-request-0002'});const rejected=assert.rejects(b,/取消/);await tick();api.cancel('queue-request-0002');await rejected;release(response('first'));await a;assert.equal(calls,1)}finally{api.cancel();await fs.rm(directory,{recursive:true,force:true})}
})
