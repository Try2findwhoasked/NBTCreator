import test from 'node:test'
import assert from 'node:assert/strict'
import {translateComponent} from '../.agents/skills/minecraft-nbt-modeler/assets/viewer/src/component-move.js'
import {previewAI} from '../.agents/skills/minecraft-nbt-modeler/assets/viewer/src/ai-request.js'
test('whole component offsets preserve geometry, source steps and reject invalid destinations',()=>{
 const operations=[{kind:'beam',lo:[2,2,2],hi:[5,5,5],start:[2,2,2],end:[5,5,5],width:1,state:'oak_log'}]
 const moved=translateComponent(operations,[3,1,-1],[20,20,20]);assert.deepEqual(moved[0].lo,[5,3,1]);assert.deepEqual(moved[0].end,[8,6,4]);assert.deepEqual(operations[0].lo,[2,2,2]);assert.equal(moved[0].state,'oak_log')
 assert.deepEqual(translateComponent(operations,[0,0,0],[20,20,20]),operations)
 assert.throws(()=>translateComponent(operations,[-3,0,0],[20,20,20]),/边界/)
 assert.throws(()=>translateComponent(operations,[0,.5,0],[20,20,20]),/整数/)
})
test('cancelled local AI preview is recorded as cancelled instead of successful or failed',async()=>{
 const previous=globalThis.fetch,events=[]
 globalThis.fetch=async(url,options)=>{events.push(JSON.parse(options.body));return{ok:true,json:async()=>({})}}
 try{
  await assert.rejects(()=>previewAI({activity_id:'synthetic-preview'},async()=>{throw new DOMException('预览已取消','AbortError')}),/取消/)
  assert.equal(events.at(-1).action,'finish');assert.equal(events.at(-1).status,'cancelled')
  assert.ok(events.at(-1).message.includes('取消'))
 }finally{globalThis.fetch=previous}
})
