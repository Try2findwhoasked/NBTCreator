import test from 'node:test'
import assert from 'node:assert/strict'
import {translateComponent} from '../.agents/skills/minecraft-nbt-modeler/assets/viewer/src/component-move.js'
test('whole component offsets preserve geometry, source steps and reject invalid destinations',()=>{
 const operations=[{kind:'beam',lo:[2,2,2],hi:[5,5,5],start:[2,2,2],end:[5,5,5],width:1,state:'oak_log'}]
 const moved=translateComponent(operations,[3,1,-1],[20,20,20]);assert.deepEqual(moved[0].lo,[5,3,1]);assert.deepEqual(moved[0].end,[8,6,4]);assert.deepEqual(operations[0].lo,[2,2,2]);assert.equal(moved[0].state,'oak_log')
 assert.deepEqual(translateComponent(operations,[0,0,0],[20,20,20]),operations)
 assert.throws(()=>translateComponent(operations,[-3,0,0],[20,20,20]),/边界/)
 assert.throws(()=>translateComponent(operations,[0,.5,0],[20,20,20]),/整数/)
})
