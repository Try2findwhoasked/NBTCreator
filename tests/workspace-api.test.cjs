const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs/promises'),os=require('node:os'),path=require('node:path')
const {createWorkspaceApi}=require('../desktop/workspace-api.cjs')
const {createApiService}=require('../desktop/api-service.cjs')
const deferred=()=>{let resolve;return {promise:new Promise(r=>resolve=r),resolve:v=>resolve(v)}}

test('workspace switch aborts active API, frees concurrency and prevents old result application',async()=>{
 const directory=await fs.mkdtemp(path.join(os.tmpdir(),'nbt-workspace-api-'));let api,workspace='old',first=true,signal
 const lifecycle=createWorkspaceApi({cancel:()=>api.cancel()}),applied=[]
 api=createApiService({directory,safeStorage:{},fetchImpl:async(_url,options)=>{
  if(first){first=false;signal=options.signal;return new Promise((_resolve,reject)=>signal.addEventListener('abort',()=>reject(new DOMException('cancel','AbortError'))))}
  return new Response(JSON.stringify({data:[{id:'new-workspace-model'}]}))
 }})
 try{
  await api.save({enabled:true})
  const old=lifecycle.run(()=>api.models()).then(value=>applied.push({workspace,value}))
  const rejection=assert.rejects(old,/取消|工作区/)
  await new Promise(r=>setImmediate(r));await lifecycle.suspend();await rejection
  assert.equal(signal.aborted,true);assert.deepEqual(applied,[]);assert.equal(lifecycle.state().pending,0)
  await assert.rejects(lifecycle.run(()=>api.models()),/正在切换/)
  workspace='new';lifecycle.resume()
  const models=await lifecycle.run(()=>api.models());assert.deepEqual(models,['new-workspace-model'])
 }finally{api.cancel();await fs.rm(directory,{recursive:true,force:true})}
})

test('cancel during knowledge loading refuses before API request starts',async()=>{
 const directory=await fs.mkdtemp(path.join(os.tmpdir(),'nbt-workspace-context-')),loading=deferred(),entered=deferred();let api,calls=0
 const lifecycle=createWorkspaceApi({cancel:()=>api.cancel()})
 api=createApiService({directory,safeStorage:{},workflowContext:key=>lifecycle.guardContext(async()=>{entered.resolve();return loading.promise}),fetchImpl:async()=>{calls++;return new Response(JSON.stringify({choices:[{finish_reason:'stop',message:{content:'new result'}}]}))}})
 try{
  await api.save({enabled:true})
  const old=lifecycle.run(()=>api.generate({mode:'prompt',instruction:'old workspace instructions'})),rejected=assert.rejects(old,/工作区已切换/)
  await entered.promise;const transition=lifecycle.suspend();loading.resolve({workflow:'prompt',rules:'old knowledge'})
  await transition;await rejected;assert.equal(calls,0);assert.equal(lifecycle.state().pending,0)
  lifecycle.resume();const fresh=await lifecycle.run(()=>api.generate({mode:'prompt',instruction:'new workspace instructions'}))
  assert.equal(fresh.text,'new result');assert.equal(calls,1)
 }finally{api.cancel();await fs.rm(directory,{recursive:true,force:true})}
})

test('late non-abortable results cannot cross workspace epochs',async()=>{
 const result=deferred(),lifecycle=createWorkspaceApi({cancel:()=>{}}),applied=[]
 const old=lifecycle.run(()=>result.promise).then(value=>applied.push(value)),rejected=assert.rejects(old,/工作区已切换/)
 const transition=lifecycle.suspend();result.resolve('stale candidate');await transition;await rejected
 lifecycle.resume();assert.deepEqual(applied,[]);assert.equal(await lifecycle.run(async()=>'fresh'),'fresh')
})

test('unsettled request times out without silently permitting a workspace change',async()=>{
 const result=deferred(),lifecycle=createWorkspaceApi({cancel:()=>{},timeoutMs:20})
 const old=lifecycle.run(()=>result.promise),rejected=assert.rejects(old,/工作区已切换/)
 await assert.rejects(lifecycle.suspend(),/已取消切换/);assert.equal(lifecycle.state().paused,true)
 result.resolve('late');await rejected;lifecycle.resume();assert.equal(lifecycle.state().pending,0)
})

test('workspace switch cancels running and queued generations and waits for their context readers',async()=>{
 const directory=await fs.mkdtemp(path.join(os.tmpdir(),'nbt-workspace-parallel-')),context=deferred();let api,calls=0,prepared=0
 const lifecycle=createWorkspaceApi({cancel:()=>api.cancel()})
 api=createApiService({directory,safeStorage:{},workflowContext:()=>lifecycle.guardContext(async()=>{prepared++;await context.promise;return {}}),fetchImpl:async()=>{calls++;throw Error('old workspace reached provider')}})
 try{await api.save({enabled:true,maxConcurrent:2});const pending=Array.from({length:4},(_,i)=>lifecycle.run(()=>api.generate({mode:'prompt',instruction:'old '+i},{requestId:'workspace-parallel-'+i})));const settled=Promise.allSettled(pending)
  await new Promise(resolve=>setImmediate(resolve));assert.equal(prepared,4);assert.equal(api.state().queued,2);const transition=lifecycle.suspend();await new Promise(resolve=>setImmediate(resolve));assert.ok(lifecycle.state().pending>0);context.resolve();await transition
  assert.ok((await settled).every(result=>result.status==='rejected'));assert.equal(calls,0);assert.equal(api.state().running,0);assert.equal(lifecycle.state().pending,0)
 }finally{api.cancel();context.resolve();await fs.rm(directory,{recursive:true,force:true})}
})
