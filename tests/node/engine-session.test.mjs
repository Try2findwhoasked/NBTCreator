import {test} from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import os from 'node:os'
import path from 'node:path'
import {createEngineSession} from '../../.agents/skills/minecraft-nbt-modeler/assets/viewer/engine-session.mjs'
import {createCandidateValidator} from '../../desktop/ai-candidate-validator.cjs'
const python=process.env.NBTCREATOR_PYTHON||'python',root=path.resolve(import.meta.dirname,'../..')
async function setup(t,options={}){const workspace=await fs.mkdtemp(path.join(os.tmpdir(),'nbt-engine-')),session=createEngineSession({workspace,python,...options});t.after(async()=>{await session.close();await fs.rm(workspace,{recursive:true,force:true})});return {workspace,session}}
const spec={name:'半格测试',size:[3,3,3],operations:[{kind:'box',label:'底座',classification:'body',lo:[0,0,0],hi:[2,0,2],state:'stone'}]}

test('real JSON-lines worker reuses one process, caches fit and keeps invalid calls isolated',async t=>{
 const {session,workspace}=await setup(t)
 const args={surface:'wall',preset:'horizontal-stripes',size_uv:[4,8],micro_alignment:'fixed'}
 const first=await session.request('agent',{tool:'pattern_microfit',arguments:args})
 assert.equal(first.ok,true,first.error)
 const second=await session.request('agent',{tool:'pattern_microfit',arguments:args})
 assert.deepEqual(second.result,first.result);assert.ok(second.metrics.cache.hits>first.metrics.cache.hits)
 for(const params of [{tool:'structure_save',arguments:{}},{tool:'pattern_microfit',arguments:{...args,preview:true}},{tool:'pattern_mount',arguments:{review:{render:true}}},{tool:'__import__',arguments:{}}])assert.equal((await session.request('agent',params)).ok,false)
 assert.equal((await session.request('eval',{code:'bad'})).ok,false)
 assert.equal((await session.request('validate',{mode:'component',result:{spec},context:{}})).ok,true)
 assert.equal(session.state().starts,1);assert.deepEqual(await fs.readdir(workspace),[])
})

test('cancelling an executing request recycles the worker and preserves the queued neighbour',async t=>{
 const {session}=await setup(t),controller=new AbortController()
 const first=session.request('validate',{mode:'component',result:{spec},context:{}},{signal:controller.signal})
 const rejected=assert.rejects(first,{code:'AI_CANCELLED'})
 const second=session.request('validate',{mode:'component',result:{spec},context:{}})
 controller.abort();await rejected
 assert.equal((await second).ok,true);assert.equal(session.state().starts,2)
})

test('queue cancellation does not restart its neighbour; idle expiry creates a fresh session',async t=>{
 const {session}=await setup(t,{idleMs:20}),controller=new AbortController()
 const first=session.request('validate',{mode:'component',result:{spec},context:{}})
 const queued=session.request('agent',{tool:'pattern_list',arguments:{}},{signal:controller.signal})
 const rejected=assert.rejects(queued,{code:'AI_CANCELLED'});controller.abort();await rejected;assert.equal((await first).ok,true)
 assert.equal(session.state().starts,1)
 await new Promise(resolve=>setTimeout(resolve,50))
 assert.equal((await session.request('validate',{mode:'component',result:{spec},context:{}})).ok,true);assert.equal(session.state().starts,2)
})

test('timeout and bounded queue reject without replay; closing refuses new requests',async t=>{
 const {workspace}=await setup(t),script=path.join(workspace,'blocked.py')
 await fs.writeFile(script,'import sys,time\nfor line in sys.stdin: time.sleep(10)\n')
 const session=createEngineSession({workspace,python,script,timeoutMs:80,maxPending:1});t.after(()=>session.close())
 const waiting=session.request('validate',{});const rejected=assert.rejects(waiting,{code:'ENGINE_TIMEOUT'})
 await assert.rejects(session.request('validate',{}),{code:'ENGINE_QUEUE_FULL'});await rejected;assert.equal(session.state().starts,1)
 await session.close();await assert.rejects(session.request('validate',{}),{code:'ENGINE_CLOSED'})
})

test('unexpected process exit rejects once; a fresh worker serves the next explicit request',async()=>{
 const workspace=await fs.mkdtemp(path.join(os.tmpdir(),'nbt-engine-exit-')),script=path.join(workspace,'worker.py')
 await fs.writeFile(script,'raise SystemExit(3)\n')
 const session=createEngineSession({workspace,python,script})
 try{
  await assert.rejects(session.request('validate',{}),{code:'ENGINE_EXITED'});assert.equal(session.state().starts,1)
  await fs.writeFile(script,'import sys,json\nfor line in sys.stdin:\n request=json.loads(line)\n print(json.dumps({"id":request["id"],"ok":True,"result":{"fresh":True}}),flush=True)\n')
  assert.deepEqual((await session.request('validate',{})).result,{fresh:true});assert.equal(session.state().starts,2)
 }finally{await session.close();await fs.rm(workspace,{recursive:true,force:true})}
})

test('candidate validator reuses a worker and destroys it when the workspace changes',async t=>{
 const {workspace}=await setup(t);let target=workspace
 const validator=createCandidateValidator({root,python,directory:workspace,getWorkspace:()=>target});t.after(()=>validator.close())
 const request={mode:'component',context:{},result:{spec}}
 await validator(request);await validator(request);assert.equal(validator.state().starts,1)
 target=path.join(workspace,'other');await fs.mkdir(target)
 await validator(request);assert.equal(validator.state().starts,1);assert.deepEqual(await fs.readdir(target),[])
})

test('real local HTTP endpoint reuses pure candidates while preview keeps its separate file-producing flow',async()=>{
 const {startDetailServer}=await import('../../.agents/skills/minecraft-nbt-modeler/assets/viewer/detail-server.mjs')
 const workspace=await fs.mkdtemp(path.join(os.tmpdir(),'nbt-session-http-'));let server
 try{
  server=await startDetailServer({workspace,python,frontendMode:'production'})
  const request=async(tool,args)=>{const reply=await fetch(new URL('/__detail__/components/agent',server.url),{method:'POST',headers:{'content-type':'application/json',origin:new URL(server.url).origin},body:JSON.stringify({tool,arguments:args})});const result=await reply.json();assert.equal(reply.status,200,result.error);return result}
  const args={kind:'table',size:[3,3,3]}
  assert.deepEqual(await request('parametric_compile',args),await request('parametric_compile',args))
  const preview=await request('parametric_preview',args);assert.ok(preview.preview_id);await fs.access(preview.source)
  assert.deepEqual((await request('structure_list',{})).items,[])
 }finally{await server?.close();await fs.rm(workspace,{recursive:true,force:true})}
})
