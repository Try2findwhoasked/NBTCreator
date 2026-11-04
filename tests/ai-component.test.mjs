import {test} from 'node:test'
import assert from 'node:assert/strict'
import {aiGroupMatches,moveAIGroup,aiSurfaceOffset,aiComponentCamera} from '../.agents/skills/minecraft-nbt-modeler/assets/viewer/src/ai-component.mjs'
import {cameraView} from '../.agents/skills/minecraft-nbt-modeler/assets/viewer/src/view-contract.mjs'
import {rotateState,rotateAIComponent} from '../.agents/skills/minecraft-nbt-modeler/assets/viewer/src/ai-rotation.mjs'
const op={kind:'box',label:'柱',classification:'body',lo:[10,4,10],hi:[11,6,11],state:'gold_block',overwrite:false,write_group:'12345678-1234-1234-1234-123456789abc'}
test('rotation transforms an asymmetric group, beam endpoints and state axes from the original basis',()=>{
 const base=[{...op,lo:[10,4,10],hi:[14,4,11],state:'oak_log'}, {...op,kind:'beam',lo:[10,5,10],hi:[14,5,10],start:[10,5,10],end:[14,5,10],width:1,state:'oak_log[axis=x]'}],original=structuredClone(base)
 const group={start:0,base,applied:base},settings={operations:base},patch=moveAIGroup(group,settings,[2,0,3],[48,16,48],false,1)
 assert.deepEqual(patch.lo,[12,4,13]);assert.deepEqual(patch.hi,[13,5,17]);assert.deepEqual(patch.operations[1].start,[13,5,13]);assert.deepEqual(patch.operations[1].end,[13,5,17]);assert.equal(patch.operations[1].state,'minecraft:oak_log[axis=z]');assert.equal(patch.operations[0].state,'minecraft:oak_log[axis=y]');assert.deepEqual(base,original)
 group.applied=patch.operations;group.quarter_turns=1;settings.operations=patch.operations
 assert.deepEqual(moveAIGroup(group,settings,[0,0,0],[48,16,48],false,0).operations,base)
 assert.deepEqual(aiSurfaceOffset(group,{position:[20,3,20],normal:[0,1,0]},[48,16,48]),[9,0,8])
 assert.throws(()=>moveAIGroup(group,settings,[37,0,0],[48,16,48],false,1),/边界/)
 for(const turns of [-1,4,.5,NaN])assert.throws(()=>rotateAIComponent(base,turns))
})
test('state rotation uses implicit defaults and refuses unsupported state families',()=>{
 assert.equal(rotateState('carved_pumpkin',1),'minecraft:carved_pumpkin[facing=east]')
 for(const value of ['oak_stairs','oak_stairs[facing=east]','furnace','oak_door','rail','oak_sign'])assert.throws(()=>rotateState(value,1),/不支持/)
 assert.equal(rotateState('oak_stairs',0),'oak_stairs')
})
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

test('one suggested angle becomes a valid camera fitted to actual component bounds, including narrow viewports',()=>{
 const before=structuredClone(op),wide=aiComponentCamera([op],{azimuth:90,elevation:25},2),narrow=aiComponentCamera([op],{azimuth:90,elevation:25},.5)
 assert.deepEqual(wide.target,[11,5.5,11]);assert.deepEqual(cameraView(wide),wide);assert.equal(wide.fov,55);assert.ok(wide.eye[0]>wide.target[0]);assert.ok(Math.abs(wide.eye[2]-wide.target[2])<1e-8)
 const distance=c=>Math.hypot(...c.eye.map((n,i)=>n-c.target[i]));assert.ok(distance(narrow)>distance(wide));assert.deepEqual(op,before)
 const moved=moveAIGroup({start:0,base:[op],applied:[op]},{operations:[op]},[4,0,-2],[48,16,48]);const camera=aiComponentCamera(moved.operations,{azimuth:90,elevation:25},2)
 assert.deepEqual(camera.target,[15,5.5,9]);assert.ok(Math.abs(distance(camera)-distance(wide))<1e-8)
 for(const elevation of [-90,90])assert.doesNotThrow(()=>cameraView(aiComponentCamera([op],{azimuth:45,elevation})))
 for(const hint of [null,[],{azimuth:0,elevation:91},{azimuth:NaN,elevation:0},{azimuth:0,elevation:0,eye:[1,2,3]}])assert.throws(()=>aiComponentCamera([op],hint))
})
