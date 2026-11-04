import assert from 'node:assert/strict'
import {test} from 'node:test'
import {ViewCamera} from '../.agents/skills/minecraft-nbt-modeler/assets/viewer/src/camera-controls.mjs'
const distance=(a,b)=>Math.hypot(...a.map((v,i)=>v-b[i]))
function fixture(){
 const handlers={},canvas={dataset:{},clientHeight:600,addEventListener:(key,fn)=>handlers[key]=fn,setPointerCapture(){},hasPointerCapture(){return false}}
 let changes=0;const camera=new ViewCamera(canvas,[10,5,10],25,()=>changes++)
 return {camera,handlers,canvas,changes:()=>changes}
}
test('wheel advances beyond original target and backwards beyond old distance limit',()=>{
 const {camera,handlers}=fixture(),start=structuredClone(camera.getCamera())
 const wheel=(deltaY,deltaMode=0)=>handlers.wheel({deltaY,deltaMode,preventDefault(){}})
 for(let i=0;i<30;i++)wheel(-120)
 const forward=structuredClone(camera.getCamera());assert.ok(distance(forward.position,start.position)>distance(start.position,start.target))
 assert.ok(Math.abs(distance(forward.position,forward.target)-25)<1e-8)
 for(let i=0;i<800;i++)wheel(120)
 assert.ok(distance(camera.fixed.position,start.position)>500)
 for(let i=0;i<770;i++)wheel(-120)
 assert.ok(distance(camera.fixed.position,start.position)<1e-8)
 wheel(-3,1);assert.ok(distance(camera.fixed.position,start.position)<1)
})
test('first-person drag looks right and down with a gentle turn and short wheel step',()=>{
 const {camera,handlers}=fixture();camera.fixed={position:[0,0,0],target:[0,0,-10],up:[0,1,0]}
 camera.look(100,0);assert.ok(camera.fixed.target[0]>0);assert.deepEqual(camera.fixed.position,[0,0,0])
 const angle=Math.acos(-camera.fixed.target[2]/10);assert.ok(angle>.15&&angle<.4)
 camera.fixed={position:[0,0,0],target:[0,0,-10],up:[0,1,0]};camera.look(0,100);assert.ok(camera.fixed.target[1]<0)
 const before=structuredClone(camera.fixed);handlers.wheel({deltaY:-120,deltaMode:0,preventDefault(){}})
 const step=distance(camera.fixed.position,before.position);assert.ok(step>=.5&&step<=2)
})
test('looking rotates around the eye after movement and presets; pan preserves orientation',()=>{
 const {camera}=fixture();camera.move(100);let before=structuredClone(camera.fixed)
 camera.look(90,25);assert.deepEqual(camera.fixed.position,before.position);assert.ok(distance(camera.fixed.target,before.target)>1)
 camera.fixed={position:[2,3,4],target:[2,3,-4],up:[0,1,0]};before=structuredClone(camera.fixed)
 camera.look(-110,10000);assert.deepEqual(camera.fixed.position,before.position)
 assert.ok(camera.fixed.target.every(Number.isFinite));assert.ok(Math.abs(distance(camera.fixed.position,camera.fixed.target)-8)<1e-8)
 before=structuredClone(camera.fixed);camera.pan(40,20)
 const shift=camera.fixed.position.map((v,i)=>v-before.position[i]);assert.ok(shift.some(v=>Math.abs(v)>.1))
 assert.ok(camera.fixed.target.every((v,i)=>Math.abs(v-before.target[i]-shift[i])<1e-8))
})
test('pick clicks do not move camera while a drag still looks around',()=>{
 const {camera,handlers,canvas,changes}=fixture();canvas.dataset.pickMode='true';const start=structuredClone(camera.fixed)
 handlers.pointerdown({button:0,clientX:100,clientY:100,pointerId:1,preventDefault(){}})
 handlers.pointermove({clientX:102,clientY:101});assert.deepEqual(camera.fixed,start);assert.equal(changes(),0)
 handlers.pointermove({clientX:150,clientY:120});assert.deepEqual(camera.fixed.position,start.position);assert.notDeepEqual(camera.fixed.target,start.target)
 handlers.pointercancel({pointerId:1});const stopped=structuredClone(camera.fixed);handlers.pointermove({clientX:180,clientY:150});assert.deepEqual(camera.fixed,stopped)
})
test('horizontal and vertical inversion are independent in all four combinations',()=>{
 for(const cameraInvertX of [false,true])for(const cameraInvertY of [false,true]){
  const {camera}=fixture();camera.fixed={position:[0,0,0],target:[0,0,-10],up:[0,1,0]}
  camera.setControls({cameraInvertX,cameraInvertY});camera.look(40,30)
  assert.equal(camera.fixed.target[0]>0,!cameraInvertX);assert.equal(camera.fixed.target[1]>0,cameraInvertY)
  assert.deepEqual(camera.fixed.position,[0,0,0])
 }
})
test('speed changes apply independently without moving the current camera',()=>{
 const normal=fixture(),slow=fixture();const initial=structuredClone(slow.camera.fixed)
 slow.camera.setControls({cameraLookSpeed:50,cameraPanSpeed:25,cameraWheelSpeed:200})
 assert.deepEqual(slow.camera.fixed,initial)
 normal.camera.pan(20,0);slow.camera.pan(20,0)
 assert.ok(Math.abs(distance(slow.camera.fixed.position,initial.position)/distance(normal.camera.fixed.position,initial.position)-.25)<1e-8)
 for(const f of [normal,slow]){f.camera.fixed={position:[0,0,0],target:[0,0,-10],up:[0,1,0]};f.camera.look(40,0)}
 const angle=c=>Math.atan2(c.fixed.target[0],-c.fixed.target[2]);assert.ok(Math.abs(angle(slow.camera)/angle(normal.camera)-.5)<1e-8)
 const beforeNormal=structuredClone(normal.camera.fixed),beforeSlow=structuredClone(slow.camera.fixed)
 for(const f of [normal,slow])f.handlers.wheel({deltaY:-120,deltaMode:0,preventDefault(){}})
 assert.ok(Math.abs(distance(slow.camera.fixed.position,beforeSlow.position)/distance(normal.camera.fixed.position,beforeNormal.position)-2)<1e-8)
 for(const value of [0,301,NaN,50.5,'100'])assert.throws(()=>slow.camera.setControls({cameraLookSpeed:value}))
 assert.throws(()=>slow.camera.setControls({cameraInvertX:1}));assert.equal(slow.camera.controls.cameraLookSpeed,50)
})
