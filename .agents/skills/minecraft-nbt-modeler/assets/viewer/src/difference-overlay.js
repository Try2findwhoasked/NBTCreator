import {Scene,BoxGeometry,MeshBasicMaterial,InstancedMesh,Matrix4} from 'three'
import {DIFFERENCE_COLORS,clipDifferenceRun} from './difference-index.mjs'
export function differenceOverlay(){
 const scene=new Scene();let meshes=[],visible=0
 function clear(){for(const mesh of meshes){scene.remove(mesh);mesh.geometry.dispose();mesh.material.dispose()}meshes=[];visible=0}
 function update(data,{cuts,layer,side,enabled}){
  clear();if(!data||!enabled)return
  const grouped=new Map(Object.keys(DIFFERENCE_COLORS).map(kind=>[kind,[]]))
  for(const run of data.runs){const clipped=clipDifferenceRun(run,cuts,layer,side);if(clipped)grouped.get(clipped.kind).push(clipped)}
  const matrix=new Matrix4()
  for(const [kind,runs] of grouped){if(!runs.length)continue
   const mesh=new InstancedMesh(new BoxGeometry(1,1,1),new MeshBasicMaterial({color:DIFFERENCE_COLORS[kind],transparent:true,opacity:.5,depthWrite:false,toneMapped:false}),runs.length)
   // One prism per contiguous X run, avoiding one draw object per changed voxel.
   runs.forEach(({lo,hi},i)=>{matrix.makeScale(...hi.map((v,i)=>v-lo[i]+.012));matrix.setPosition(...lo.map((v,i)=>(v+hi[i])/2));mesh.setMatrixAt(i,matrix)})
   mesh.instanceMatrix.needsUpdate=true;mesh.frustumCulled=false;scene.add(mesh);meshes.push(mesh);visible+=runs.length
  }
 }
 return {scene,update,clear,status:()=>({prisms:visible,draw_calls:meshes.length})}
}
