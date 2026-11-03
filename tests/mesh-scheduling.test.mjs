import {test} from 'node:test'
import assert from 'node:assert/strict'
import {yieldForMeshBuild,installMeshScheduling} from '../.agents/skills/minecraft-nbt-modeler/assets/viewer/src/mesh-scheduling.mjs'

test('a starved idle callback cannot stall mesh construction',async()=>{
 let timer,idle,cancelled,cleared
 const pending=yieldForMeshBuild({setTimeout(callback,ms){timer=callback;assert.equal(ms,32);return 1},clearTimeout(id){cleared=id},requestIdleCallback(callback,options){idle=callback;assert.equal(options.timeout,32);return 2},cancelIdleCallback(id){cancelled=id}})
 timer();await pending;assert.equal(cancelled,2);assert.equal(cleared,1);idle();assert.equal(cancelled,2)
})
test('idle completion cancels its fallback and unavailable idle still yields',async()=>{
 let idle,cancelled=0
 const pending=yieldForMeshBuild({setTimeout(){return 7},clearTimeout(id){assert.equal(id,7);cancelled++},requestIdleCallback(callback){idle=callback;return 8},cancelIdleCallback(){}});idle();await pending;assert.equal(cancelled,1)
 await yieldForMeshBuild({setTimeout,clearTimeout})
 await yieldForMeshBuild({setTimeout,clearTimeout,requestIdleCallback(){throw Error('unavailable')}})
})
test('both renderer build stages are patched without changing browser globals',async()=>{
 const original=globalThis.requestIdleCallback
 class Renderer{yieldControl(){return new Promise(()=>{})}}class Builder extends Renderer{}
 installMeshScheduling(Renderer,Builder);await Renderer.prototype.yieldControl();await Builder.prototype.yieldControl();assert.equal(globalThis.requestIdleCallback,original);assert.throws(()=>installMeshScheduling(class {},Builder),/版本/)
})
