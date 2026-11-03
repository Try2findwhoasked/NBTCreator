import {test} from 'node:test'
import assert from 'node:assert/strict'
import {aiGroupMatches,moveAIGroup,aiSurfaceOffset} from '../.agents/skills/minecraft-nbt-modeler/assets/viewer/src/ai-component.mjs'
const op={kind:'box',label:'柱',classification:'body',lo:[10,4,10],hi:[11,6,11],state:'gold_block',overwrite:false,write_group:'12345678-1234-1234-1234-123456789abc'}
test('AI moves use the original basis, preserve labels, and allow returning to zero',()=>{
 const group={start:0,base:[op],applied:[op]},settings={operations:[structuredClone(op)]};settings.operations[0].label='改过的名字'
 assert.equal(aiGroupMatches(group,settings),true)
 let patch=moveAIGroup(group,settings,[5,0,-2],[48,16,48],true);assert.deepEqual(patch.operations[0].lo,[15,4,8]);assert.equal(patch.operations[0].label,'改过的名字');assert.equal(patch.operations[0].overwrite,true)
 group.applied=structuredClone(patch.operations);settings.operations=structuredClone(patch.operations);patch=moveAIGroup(group,settings,[0,0,0],[48,16,48]);assert.deepEqual(patch.operations[0].lo,[10,4,10]);assert.equal(patch.operations[0].overwrite,false)
 settings.operations[0].state='stone';assert.equal(aiGroupMatches(group,settings),false)
})
test('surface placement uses the whole component footprint rather than clipping against a wall',()=>{
 const group={base:[op]},size=[48,16,48]
 assert.deepEqual(aiSurfaceOffset(group,{position:[20,3,10],normal:[0,1,0]},size),[9,0,-1])
 assert.deepEqual(aiSurfaceOffset(group,{position:[30,5,20],normal:[-1,0,0]},size),[18,0,9])
 assert.throws(()=>aiSurfaceOffset(group,{position:[0,0,0],normal:[-1,0,0]},size),/放不下/)
})
