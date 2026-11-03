import {Scene,Object3D,InstancedMesh,BoxGeometry,MeshBasicMaterial,Matrix4,Vector3,Box3} from 'three'
import {TransformControls} from 'three/addons/controls/TransformControls.js'
import {RangeBox} from './range-box.mjs'
import {componentBounds} from './component-transform.mjs'

export function createComponentGizmo({canvas,camera,viewCamera,requestRender,notify}){
 const scene=new Scene(),handlesScene=new Scene(),root=new Object3D(),visual=new Object3D();root.add(visual);scene.add(root)
 const controls=new TransformControls(camera,canvas);controls.setSize(.8);controls.setSpace('world');controls.setRotationSnap(Math.PI/2);controls.enabled=false;handlesScene.add(controls)
 const box=new RangeBox(new Box3(new Vector3(),new Vector3(1,1,1)),0x6fbbff);box.visible=false;handlesScene.add(box)
 let current=null,mesh=null,last='',syncing=false
 function state(){return current?{...current,component:undefined,...componentBounds(current.component,current.position,current.quarter_turns,current.mirror),dragging:controls.dragging,axis:controls.axis,valid:box.userData.valid}:null}
 function update(){
  if(!current)return
  root.position.fromArray(current.position);root.rotation.set(0,-current.quarter_turns*Math.PI/2,0)
  visual.scale.set(current.mirror==='x'?-1:1,1,current.mirror==='z'?-1:1)
  // The logical pivot is an integer anchor voxel; every voxel center remains
  // half a block offset in world space after rotating/mirroring that pivot.
  visual.position.set(.5,.5,.5).applyQuaternion(root.quaternion.clone().invert())
  const bounds=componentBounds(current.component,current.position,current.quarter_turns,current.mirror)
  box.box.min.fromArray(bounds.lo);box.box.max.fromArray(bounds.hi.map(n=>n+1));box.updateMatrixWorld(true);box.visible=true
  box.userData.valid=bounds.lo.every((n,i)=>n>=0&&bounds.hi[i]<current.model_size[i]);box.material.color.setHex(box.userData.valid?0x6fbbff:0xf26778);mesh.material.color.setHex(box.userData.valid?0x64b5f6:0xf26778)
  controls.setMode(current.mode);controls.showX=current.mode!=='rotate';controls.showY=true;controls.showZ=current.mode!=='rotate';controls.setTranslationSnap(current.grid);controls.enabled=!current.pick_surface
  scene.updateMatrixWorld(true);handlesScene.updateMatrixWorld(true);requestRender()
 }
 function publish(){const value=state(),key=JSON.stringify([value.position,value.quarter_turns]);if(key!==last){last=key;notify(value)}}
 controls.addEventListener('change',requestRender)
 controls.addEventListener('dragging-changed',event=>{viewCamera.setInteractionEnabled(!event.value);canvas.dataset.transformDragging=String(event.value);if(!event.value&&current)publish()})
 controls.addEventListener('objectChange',()=>{if(syncing||!current)return
  current.position=root.position.toArray().map(Math.round)
  const direction=new Vector3(0,0,1).applyQuaternion(root.quaternion);current.quarter_turns=(Math.round(-Math.atan2(direction.x,direction.z)/(Math.PI/2))%4+4)%4
  syncing=true;try{update()}finally{syncing=false}publish()
 })
 const pointer=event=>{const rect=canvas.getBoundingClientRect();return {x:(event.clientX-rect.left)/rect.width*2-1,y:1-(event.clientY-rect.top)/rect.height*2,button:event.button}}
 function guard(event){if(!current||!controls.enabled||event.button!==0)return;handlesScene.updateMatrixWorld(true);camera.updateMatrixWorld(true);controls.pointerHover(pointer(event));if(controls.axis){viewCamera.setInteractionEnabled(false);canvas.dataset.transformDragging='true'}}
 canvas.addEventListener('pointerdown',guard,true)
 const cancelled=()=>{if(controls.dragging)controls.pointerUp({button:0});viewCamera.setInteractionEnabled(true);canvas.dataset.transformDragging='false'}
 canvas.addEventListener('pointercancel',cancelled)
  canvas.addEventListener('pointerup',cancelled)
 function clear(){controls.detach();controls.enabled=false;current=null;last='';box.visible=false;if(mesh){visual.remove(mesh);mesh.geometry.dispose();mesh.material.dispose();mesh=null}cancelled();requestRender()}
 function configure(value){
  if(!value){clear();return null}
  const next={mode:'translate',grid:1,mirror:null,quarter_turns:0,pick_surface:false,...value}
  if(!['translate','rotate'].includes(next.mode)||!Number.isInteger(next.grid)||next.grid<1||next.grid>16||typeof next.pick_surface!=='boolean'||!Array.isArray(next.model_size)||!next.model_size.every(n=>Number.isInteger(n)&&n>0))throw Error('3D手柄参数无效')
  componentBounds(next.component,next.position,next.quarter_turns,next.mirror)
  if(!Array.isArray(next.component.blocks)||!next.component.blocks.length||next.component.blocks.length>65536||next.component.blocks.some(b=>!Array.isArray(b)||b.length!==5||b.slice(0,3).some((v,i)=>!Number.isInteger(v)||v<0||v>=next.component.size[i])))throw Error('3D构件体素无效')
  if(current?.component!==next.component){if(mesh){visual.remove(mesh);mesh.geometry.dispose();mesh.material.dispose()}
   const solid=next.component.blocks.filter(b=>!['minecraft:air','minecraft:cave_air','minecraft:void_air'].includes(next.component.palette[b[3]].split('[')[0]))
   mesh=new InstancedMesh(new BoxGeometry(.98,.98,.98),new MeshBasicMaterial({color:0x64b5f6,opacity:.48,transparent:true,depthWrite:false,toneMapped:false}),solid.length)
   const matrix=new Matrix4();solid.forEach((b,i)=>{matrix.makeTranslation(...b.slice(0,3).map((v,i)=>v-next.component.anchor[i]));mesh.setMatrixAt(i,matrix)});mesh.instanceMatrix.needsUpdate=true;mesh.frustumCulled=false;visual.add(mesh)
  }
  current=next;syncing=true;try{update();controls.attach(root)}finally{syncing=false}last=JSON.stringify([next.position,next.quarter_turns]);return state()
 }
 function screenHandles(){if(!current||!controls.enabled)return[];handlesScene.updateMatrixWorld(true);camera.updateMatrixWorld(true);const rect=canvas.getBoundingClientRect(),result=[]
  for(const object of controls._gizmo.picker[current.mode].children){if(!object.visible||!['X','Y','Z','XY','XZ','YZ'].includes(object.name))continue
   const p=new Box3().setFromObject(object).getCenter(new Vector3()).project(camera);result.push({axis:object.name,x:(p.x+1)*rect.width/2,y:(1-p.y)*rect.height/2})
  }return result
 }
 return {scene,handlesScene,configure,state,screenHandles,dispose(){clear();canvas.removeEventListener('pointerdown',guard,true);canvas.removeEventListener('pointercancel',cancelled);canvas.removeEventListener('pointerup',cancelled);controls.dispose();box.geometry.dispose();box.material.dispose()}}
}
