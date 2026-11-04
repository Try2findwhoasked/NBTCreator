const add=(a,b)=>a.map((v,i)=>v+b[i])
const sub=(a,b)=>a.map((v,i)=>v-b[i])
const scale=(a,n)=>a.map(v=>v*n)
const dot=(a,b)=>a.reduce((n,v,i)=>n+v*b[i],0)
const cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]
const unit=a=>scale(a,1/Math.hypot(...a))
function rotate(v,axis,angle){return add(add(scale(v,Math.cos(angle)),scale(cross(axis,v),Math.sin(angle))),scale(axis,dot(axis,v)*(1-Math.cos(angle))))}
const LOOK_SPEED=1/320
const WHEEL_SPEED=.0125
const PAN_SPEED=.5
export const CAMERA_CONTROL_DEFAULTS=Object.freeze({cameraLookSpeed:100,cameraPanSpeed:100,cameraWheelSpeed:100,cameraInvertX:false,cameraInvertY:false})
export function normalizeCameraControls(value={}){
  const result={...CAMERA_CONTROL_DEFAULTS}
  for(const key of Object.keys(result))if(value[key]!==undefined)result[key]=value[key]
  if(!['cameraLookSpeed','cameraPanSpeed','cameraWheelSpeed'].every(key=>Number.isInteger(result[key])&&result[key]>=10&&result[key]<=300)||!['cameraInvertX','cameraInvertY'].every(key=>typeof result[key]==='boolean'))throw Error('3D操作配置无效：速度须为10～300%，反转须为勾选状态')
  return result
}

// Interactive movement changes the eye and target together. Looking around
// changes only the target, including after loading a saved camera preset.
export class ViewCamera {
  constructor(canvas,center,distance,onChange=()=>{}){
    this.canvas=canvas;this.distance=distance;this.onChange=onChange;this.fov=60;this.controls=normalizeCameraControls();this.interactionEnabled=true
    this.fixed={position:add(Array.from(center),[-distance*Math.sin(.82)*Math.cos(.62),distance*Math.sin(.62),distance*Math.cos(.82)*Math.cos(.62)]),target:Array.from(center),up:[0,1,0]}
    canvas.addEventListener('pointerdown',event=>{
      if(!this.interactionEnabled)return
      if(event.button!==0&&event.button!==1)return
      event.preventDefault();this.dragMode=event.button===1?'pan':'rotate'
      this.pickDragOrigin=this.dragMode==='rotate'&&canvas.dataset.pickMode==='true'?[event.clientX,event.clientY]:null
      this.lastPos=[event.clientX,event.clientY];canvas.setPointerCapture?.(event.pointerId)
    })
    const stop=event=>{this.lastPos=null;this.pickDragOrigin=null;if(canvas.hasPointerCapture?.(event.pointerId))canvas.releasePointerCapture(event.pointerId)}
    for(const name of ['pointerup','pointercancel','lostpointercapture'])canvas.addEventListener(name,stop)
    canvas.addEventListener('pointermove',event=>{
      if(!this.interactionEnabled||!this.lastPos)return
      if(this.pickDragOrigin){if(Math.hypot(event.clientX-this.pickDragOrigin[0],event.clientY-this.pickDragOrigin[1])<=5)return;this.pickDragOrigin=null}
      const dx=event.clientX-this.lastPos[0],dy=event.clientY-this.lastPos[1]
      this.lastPos=[event.clientX,event.clientY]
      if(this.dragMode==='pan')this.pan(dx,dy)
      else this.look(dx,dy)
      this.onChange()
    })
    canvas.addEventListener('wheel',event=>{
      event.preventDefault()
      if(!this.interactionEnabled)return
      const pixels=event.deltaY*(event.deltaMode===1?16:event.deltaMode===2?Math.max(1,canvas.clientHeight):1)
      if(!Number.isFinite(pixels)||!pixels)return
      this.move(-pixels*WHEEL_SPEED*this.controls.cameraWheelSpeed/100);this.onChange()
    },{passive:false})
  }
  getCamera(){return this.fixed}
  setInteractionEnabled(value){this.interactionEnabled=Boolean(value);if(!this.interactionEnabled){this.lastPos=null;this.pickDragOrigin=null}}
  setControls(value){this.controls=normalizeCameraControls({...this.controls,...value});return {...this.controls}}
  move(amount){
    const state=this.fixed,shift=scale(unit(sub(state.target,state.position)),amount)
    state.position=add(state.position,shift);state.target=add(state.target,shift)
  }
  look(dx,dy){
    const state=this.fixed,up=unit(state.up??[0,1,0]),offset=sub(state.target,state.position),distance=Math.hypot(...offset)
    // First-person drag: right looks right, down looks down.
    const speed=LOOK_SPEED*this.controls.cameraLookSpeed/100
    let forward=rotate(unit(offset),up,-dx*speed*(this.controls.cameraInvertX?-1:1))
    const pitch=Math.asin(Math.max(-1,Math.min(1,dot(forward,up)))),next=Math.max(-Math.PI/2+.01,Math.min(Math.PI/2-.01,pitch-dy*speed*(this.controls.cameraInvertY?-1:1)))
    forward=rotate(forward,unit(cross(forward,up)),next-pitch)
    state.target=add(state.position,scale(forward,distance))
  }
  pan(dx,dy){
    const state=this.fixed,forward=unit(sub(state.target,state.position)),right=unit(cross(forward,state.up??[0,1,0])),up=cross(right,forward)
    const amount=PAN_SPEED*this.controls.cameraPanSpeed/100*2*Math.min(80,Math.max(4,Math.hypot(...sub(state.target,state.position))))*Math.tan(this.fov*Math.PI/360)/Math.max(1,this.canvas.clientHeight)
    const shift=add(scale(right,-dx*amount),scale(up,dy*amount))
    state.position=add(state.position,shift);state.target=add(state.target,shift)
  }
}
