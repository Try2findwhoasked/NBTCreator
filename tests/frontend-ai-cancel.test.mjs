import {test} from 'node:test'
import assert from 'node:assert/strict'
const deferred=()=>{let resolve;return {promise:new Promise(done=>resolve=done),resolve:value=>resolve(value)}}
const tick=()=>new Promise(resolve=>setImmediate(resolve))
async function setup(t,overrides={}){
 const events=[],calls=[],previous={window:globalThis.window,fetch:globalThis.fetch}
 globalThis.window={nbtDesktop:{internalAIConfig:async()=>({workflows:{prompt:{}},flows:{prompt:{label:'提示词'}}}),apiConfig:async()=>({model:'synthetic',provider:'test'}),apiCancel:()=>new Promise(()=>{}),apiGenerate:async(_input,options)=>{calls.push(options.requestId);return {text:'fresh',api_metrics:{}}},...overrides}}
 globalThis.fetch=async(_url,options)=>{const body=JSON.parse(options.body);events.push(body);return {ok:true,json:async()=>body.action==='start'?{id:'activity-'+events.length}:{}}}
 t.after(()=>{globalThis.window=previous.window;globalThis.fetch=previous.fetch})
 return {...await import('../.agents/skills/minecraft-nbt-modeler/assets/viewer/src/ai-request.js?test='+crypto.randomUUID()),events,calls}
}

test('cancel terminates UI immediately during setup, without waiting for IPC acknowledgement or starting a late request',async t=>{
 const loading=deferred(),{requestAI,cancelAI,calls}=await setup(t,{internalAIConfig:()=>loading.promise})
 const result=requestAI({mode:'prompt',instruction:'old'},null,{scope:'old'}),rejected=assert.rejects(result,{code:'AI_CANCELLED'})
 await cancelAI('old');await rejected
 loading.resolve({workflows:{prompt:{}},flows:{prompt:{label:'提示词'}}});await tick();assert.equal(calls.length,0)
})

test('cancel terminates waiting UI, leaves neighbour alive, and discards a non-abortable late provider reply',async t=>{
 const old=deferred(),{requestAI,cancelAI,events}=await setup(t,{apiGenerate:input=>input.instruction==='old'?old.promise:Promise.resolve({text:'new',api_metrics:{}})})
 const first=requestAI({mode:'prompt',instruction:'old'},null,{scope:'first'}),rejected=assert.rejects(first,{code:'AI_CANCELLED'})
 await tick();await cancelAI('first');await rejected
 const fresh=await requestAI({mode:'prompt',instruction:'new'},null,{scope:'first'});assert.equal(fresh.text,'new')
 old.resolve({text:'late',api_metrics:{}});await tick();assert.equal(events.filter(event=>event.action==='finish'&&event.status==='complete').length,1);assert.equal(events.filter(event=>event.action==='finish'&&event.status==='cancelled').length,1)
})

test('activity start completing after cancellation is cleaned up without resuming generation',async t=>{
 const started=deferred(),env=await setup(t);let providerCalls=0
 window.nbtDesktop.apiGenerate=async()=>{providerCalls++;return {}}
 const regular=globalThis.fetch;globalThis.fetch=async(url,options)=>JSON.parse(options.body).action==='start'?{ok:true,json:()=>started.promise}:regular(url,options)
 const result=env.requestAI({mode:'prompt',instruction:'cancel start'}),rejected=assert.rejects(result,{code:'AI_CANCELLED'});await tick();await env.cancelAI('prompt');await rejected
 started.resolve({id:'late-log'});await tick();assert.equal(providerCalls,0);assert.equal(env.events.filter(event=>event.id==='late-log'&&event.status==='cancelled').length,1)
})
