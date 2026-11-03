import {test} from 'node:test'
import assert from 'node:assert/strict'
import {differenceIndex,clipDifferenceRun,focusDifference} from '../.agents/skills/minecraft-nbt-modeler/assets/viewer/src/difference-index.mjs'
test('lossless intervals support changed-only filtering without filling gaps',()=>{
 const index=differenceIndex({schema_version:1,runs:[['added',1,2,3,4,false,false],['replaced',8,2,3,1,true,true]]})
 for(const x of [1,2,3,4,8])assert.equal(index.has([x,2,3]),true)
 for(const x of [0,5,6,7,9])assert.equal(index.has([x,2,3]),false)
 assert.equal(index.has([2,3,3]),false)
 assert.throws(()=>differenceIndex({schema_version:1,runs:[['added',0,0,0,0,false,false]]}))
})
test('removed wall ghosts respect the old wall layer and XYZ clipping',()=>{
 const run=['removed',2,4,6,7,true,false]
 assert.equal(clipDifferenceRun(run,[],'body','after'),null)
 assert.deepEqual(clipDifferenceRun(run,[{axis:'x',position:5,removed_side:'above'}],'walls','after'),{kind:'removed',lo:[2,4,6],hi:[5,5,7]})
 assert.equal(clipDifferenceRun(run,[{axis:'y',position:4,removed_side:'above'}],'all','before'),null)
})
test('focusing preserves viewing direction and fits narrow viewports',()=>{
 const view={eye:[20,10,-10],target:[0,0,0],up:[0,1,0],fov:60},bounds={lo:[10,2,5],hi:[15,4,10]},wide=focusDifference(bounds,view,2),narrow=focusDifference(bounds,view,.5)
 assert.deepEqual(wide.target,[13,3.5,8]);assert.deepEqual(wide.up,view.up)
 const distance=v=>Math.hypot(...v.eye.map((n,i)=>n-v.target[i]))
 assert.ok(distance(narrow)>distance(wide));assert.ok(wide.eye.every(Number.isFinite))
 const direction=wide.eye.map((n,i)=>(n-wide.target[i])/distance(wide)),n=Math.hypot(...view.eye)
 assert.ok(direction.every((v,i)=>Math.abs(v-view.eye[i]/n)<1e-10))
})
