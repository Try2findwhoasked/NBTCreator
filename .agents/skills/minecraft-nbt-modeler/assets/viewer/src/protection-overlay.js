import {Scene,BoxGeometry,MeshBasicMaterial,InstancedMesh,Matrix4} from 'three'

export function protectionOverlay(){
 const scene=new Scene();let meshes=[],visible=0
 function clear(){for(const mesh of meshes){scene.remove(mesh);mesh.geometry.dispose();mesh.material.dispose()}meshes=[];visible=0}
 function update(data,conflicts,cuts,enabled){
  clear();if(!data||!enabled)return;const matrix=new Matrix4()
  const clip=run=>{const [x,y,z,length]=run,lo=[x,y,z],hi=[x+length,y+1,z+1];for(const cut of cuts){const i='xyz'.indexOf(cut.axis);if(cut.removed_side==='above')hi[i]=Math.min(hi[i],cut.position);else lo[i]=Math.max(lo[i],cut.position)}return lo.some((v,i)=>v>=hi[i])?null:{lo,hi}}
  for(const [runs,color,opacity]of [[data.runs,0xf2b544,.2],[conflicts.map(p=>[...p,1]),0xff425b,.62]]){
   const boxes=runs.map(clip).filter(Boolean);if(!boxes.length)continue
   const mesh=new InstancedMesh(new BoxGeometry(1,1,1),new MeshBasicMaterial({color,transparent:true,opacity,depthWrite:false,depthTest:false,toneMapped:false}),boxes.length)
   boxes.forEach(({lo,hi},i)=>{matrix.makeScale(...hi.map((v,i)=>v-lo[i]+.018));matrix.setPosition(...lo.map((v,i)=>(v+hi[i])/2));mesh.setMatrixAt(i,matrix)});mesh.instanceMatrix.needsUpdate=true;mesh.frustumCulled=false;scene.add(mesh);meshes.push(mesh);visible+=boxes.length
  }
 }
 return {scene,update,clear,status:()=>({prisms:visible,draw_calls:meshes.length})}
}
