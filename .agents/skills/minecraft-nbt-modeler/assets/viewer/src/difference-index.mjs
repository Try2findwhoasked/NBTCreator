export const DIFFERENCE_COLORS={added:0x25c98c,removed:0xf26778,replaced:0xf0b442,wall:0x649eff}
export function differenceIndex(data){
 if(!data||data.schema_version!==1||!Array.isArray(data.runs))throw Error('差异数据格式无效')
 const rows=new Map()
 for(const [kind,x,y,z,length,aw,bw] of data.runs){
  if(!(kind in DIFFERENCE_COLORS)||![x,y,z,length].every(Number.isInteger)||Math.min(x,y,z)<0||length<1||typeof aw!=='boolean'||typeof bw!=='boolean')throw Error('差异坐标无效')
  const key=y+','+z;if(!rows.has(key))rows.set(key,[]);rows.get(key).push([x,x+length])
 }
 for(const row of rows.values())row.sort((a,b)=>a[0]-b[0])
 return {has(p){const row=rows.get(p[1]+','+p[2]);if(!row)return false;let lo=0,hi=row.length;while(lo<hi){const mid=(lo+hi)>>>1;if(row[mid][0]<=p[0])lo=mid+1;else hi=mid}return lo>0&&p[0]<row[lo-1][1]}}
}
export function clipDifferenceRun(run,cuts,layer,side){
 const [kind,x,y,z,length,aw,bw]=run
 const wall=kind==='removed'?aw:kind==='added'?bw:side==='before'?aw:bw
 if(layer!=='all'&&(layer==='walls')!==wall)return null
 const lo=[x,y,z],hi=[x+length,y+1,z+1]
 for(const cut of cuts){const i='xyz'.indexOf(cut.axis);if(cut.removed_side==='above')hi[i]=Math.min(hi[i],cut.position);else lo[i]=Math.max(lo[i],cut.position)}
 return lo.some((n,i)=>n>=hi[i])?null:{kind,lo,hi}
}
export function focusDifference(bounds,view,aspect=1){
 if(!bounds||!bounds.lo?.every((n,i)=>Number.isFinite(n)&&Number.isFinite(bounds.hi[i])&&n<=bounds.hi[i]))throw Error('没有可定位的变化区域')
 const target=bounds.lo.map((v,i)=>(v+bounds.hi[i]+1)/2),radius=Math.max(1,Math.hypot(...bounds.lo.map((v,i)=>bounds.hi[i]+1-v))/2)
 let direction=view.eye.map((v,i)=>v-view.target[i]),n=Math.hypot(...direction);if(n<1e-6){direction=[1,.8,-1];n=Math.hypot(...direction)}
 const fov=(view.fov??60)*Math.PI/180,horizontal=2*Math.atan(Math.tan(fov/2)*Math.max(.1,aspect)),distance=radius/Math.sin(Math.min(fov,horizontal)/2)*1.2
 return {eye:target.map((v,i)=>v+direction[i]/n*distance),target,up:view.up??[0,1,0],fov:view.fov??60}
}
