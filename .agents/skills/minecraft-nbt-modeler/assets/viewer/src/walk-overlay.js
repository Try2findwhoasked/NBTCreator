import {Scene,BoxGeometry,MeshBasicMaterial,Mesh,BufferGeometry,Float32BufferAttribute,LineSegments,LineBasicMaterial} from 'three'

export function walkOverlay(){
 const scene=new Scene();let objects=[],poseCount=0,segments=0
 function clear(){for(const object of objects){scene.remove(object);object.geometry.dispose();object.material.dispose()}objects=[];poseCount=0;segments=0}
 function add(object){scene.add(object);objects.push(object)}
 function clippedBox(lo,hi,cuts){lo=[...lo];hi=[...hi];for(const cut of cuts){const axis='xyz'.indexOf(cut.axis);if(cut.removed_side==='above')hi[axis]=Math.min(hi[axis],cut.position);else lo[axis]=Math.max(lo[axis],cut.position)}return lo.some((v,i)=>v>=hi[i])?null:{lo,hi}}
 function box(lo,hi,color,opacity,cuts){const b=clippedBox(lo,hi,cuts);if(!b)return;const object=new Mesh(new BoxGeometry(...b.hi.map((n,i)=>n-b.lo[i])),new MeshBasicMaterial({color,transparent:true,opacity,depthWrite:false,depthTest:false,toneMapped:false}));object.position.set(...b.lo.map((n,i)=>(n+b.hi[i])/2));add(object)}
 function update(data,options,cuts){
  clear();if(!data||options.enabled===false)return
  for(const pose of data.poses){box(pose.lo,pose.hi,pose.standing?0x42b7f5:0xff425b,.28,cuts);poseCount++;for(const p of pose.collisions)box(p,p.map(n=>n+.5),0xff425b,.8,cuts)}
  const path=data.report.targets[options.target??0]?.path??[],vertices=[]
  for(let i=1;i<path.length;i++){
   let a=path[i-1].map((n,j)=>n+(j===1?.06:0)),b=path[i].map((n,j)=>n+(j===1?.06:0)),visible=true
   for(const cut of cuts){const axis='xyz'.indexOf(cut.axis),inside=p=>cut.removed_side==='above'?p[axis]<=cut.position:p[axis]>=cut.position,aa=inside(a),bb=inside(b);if(!aa&&!bb){visible=false;break}if(aa!==bb){const t=(cut.position-a[axis])/(b[axis]-a[axis]),hit=a.map((n,j)=>n+(b[j]-n)*t);if(aa)b=hit;else a=hit}}
   if(visible){vertices.push(...a,...b);segments++}
  }
  if(vertices.length){const geometry=new BufferGeometry();geometry.setAttribute('position',new Float32BufferAttribute(vertices,3));add(new LineSegments(geometry,new LineBasicMaterial({color:data.report.passed?0x25c98c:0xf2b544,depthTest:false,depthWrite:false,toneMapped:false})))}
 }
 return {scene,clear,update,status:()=>({poses:poseCount,segments,draw_calls:objects.length})}
}
