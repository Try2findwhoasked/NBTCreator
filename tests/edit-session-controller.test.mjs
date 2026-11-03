import {test} from 'node:test'
import assert from 'node:assert/strict'
import {createEditSessionController} from '../.agents/skills/minecraft-nbt-modeler/assets/viewer/src/edit-session.js'
test('a late recovery cannot replace the editor selected after it',async t=>{
 const old=globalThis.window;globalThis.window=new EventTarget();t.after(()=>{if(old===undefined)delete globalThis.window;else globalThis.window=old})
 const a={source:'A',source_sha256:'a'.repeat(64)},b={source:'B',source_sha256:'b'.repeat(64)},restored=[];let release,captured={...a,state:{value:'initial'}}
 const slow=new Promise(resolve=>release=resolve),api=async(route,input)=>route.endsWith('save')?{revision:1,updated_at:new Date().toISOString()}:input.source==='A'?slow:{status:'found',...b,revision:1,state:{value:'B'}}
 const controller=createEditSessionController({api,capture:()=>captured,restore:state=>restored.push(state.value)});t.after(()=>controller.dispose())
 await controller.beforeOpen();const first=controller.opened(a);captured={...b,state:{value:'initial'}};await controller.beforeOpen();await controller.opened(b);release({status:'found',...a,revision:1,state:{value:'A'}});await first
 assert.deepEqual(restored,['B']);assert.equal(controller.source,'B');assert.equal(controller.loading,false)
})
test('recovery uses the freshly inspected source hash and disabled settings perform no I/O',async t=>{
 const old=globalThis.window;globalThis.window=new EventTarget();t.after(()=>{if(old===undefined)delete globalThis.window;else globalThis.window=old})
 let calls=0,restores=0,enabled=false;const messages=[],info={source:'A',source_sha256:'a'.repeat(64)},controller=createEditSessionController({api:async()=>{calls++;return {...info,source_sha256:'b'.repeat(64),status:'found',state:{}}},capture:()=>({...info,state:{}}),restore:()=>restores++,enabled:()=>enabled,message:m=>messages.push(m)});t.after(()=>controller.dispose())
 await controller.beforeOpen();await controller.opened(info);await controller.flush();assert.equal(calls,0);assert.equal(restores,0)
 enabled=true;await controller.opened(info);assert.equal(restores,0);assert.ok(messages.at(-1).includes('源已变化'))
})
test('a failed model open cannot autosave fallback parameters over the previous draft',async t=>{
 const old=globalThis.window;globalThis.window=new EventTarget();t.after(()=>{if(old===undefined)delete globalThis.window;else globalThis.window=old})
 const info={source:'A',source_sha256:'a'.repeat(64)},saved=[];let value={...info,state:{value:'pending work'}}
 const controller=createEditSessionController({api:async(route,input)=>{if(route.endsWith('save')){saved.push(input.state.value);return {revision:saved.length,updated_at:new Date().toISOString()}}return {...info,status:'empty',revision:0}},capture:()=>value,restore:()=>{}});t.after(()=>controller.dispose())
 await controller.opened(info,false);await controller.beforeOpen();value={...info,state:{value:'fallback defaults after failure'}};controller.resume();await controller.flush();assert.deepEqual(saved,['pending work'])
})
