import {translateComponent} from './component-move.js'
import {cameraView} from './view-contract.mjs'
const ignored=new Set(['label','enabled','overwrite','write_group'])
export function aiSignature(operations){return JSON.stringify(operations.map(op=>Object.fromEntries(Object.keys(op).filter(k=>!ignored.has(k)).sort().map(k=>[k,op[k]]))))}
export function aiBounds(operations){if(!operations?.length)throw Error('AI构件没有工具步骤');return {lo:[0,1,2].map(i=>Math.min(...operations.map(op=>op.lo[i]))),hi:[0,1,2].map(i=>Math.max(...operations.map(op=>op.hi[i])))}}
export function aiComponentCamera(operations,hint={azimuth:45,elevation:25},aspect=1){
 if(!hint||typeof hint!=='object'||Array.isArray(hint)||Object.keys(hint).some(key=>!['azimuth','elevation'].includes(key))||!Number.isFinite(hint.azimuth)||Math.abs(hint.azimuth)>180||!Number.isFinite(hint.elevation)||Math.abs(hint.elevation)>90)throw Error('构件建议视角无效')
 if(!Number.isFinite(aspect)||aspect<=0)throw Error('视口比例无效')
 const {lo,hi}=aiBounds(operations),span=hi.map((v,i)=>v-lo[i]+1)
 if(!span.every(v=>Number.isFinite(v)&&v>0))throw Error('构件范围无效')
 const target=lo.map((v,i)=>(v+hi[i]+1)/2),fov=55,angle=Math.min(fov*Math.PI/360,Math.atan(Math.tan(fov*Math.PI/360)*aspect))
 const distance=Math.max(2,Math.hypot(...span)/2/Math.sin(angle)*1.15),a=hint.azimuth*Math.PI/180,e=hint.elevation*Math.PI/180
 const direction=[Math.sin(a)*Math.cos(e),Math.sin(e),Math.cos(a)*Math.cos(e)]
 return cameraView({eye:target.map((v,i)=>v+direction[i]*distance),target,up:Math.abs(hint.elevation)>89?[0,0,-1]:[0,1,0],fov})
}
export function aiGroupMatches(group,settings){return !!group&&Array.isArray(group.base)&&group.base.length>0&&aiSignature(settings.operations.slice(group.start,group.start+group.base.length))===aiSignature(group.applied)}
export function moveAIGroup(group,settings,offset,size,overwrite=false){
 if(!aiGroupMatches(group,settings))throw Error('这组构件的几何步骤已手动改变；请撤销修改或重新载入构件')
 const current=settings.operations.slice(group.start,group.start+group.base.length),operations=translateComponent(group.base,offset,size)
 for(const [i,op]of operations.entries()){op.label=current[i].label;op.overwrite=!!overwrite;if(current[i].enabled!==undefined)op.enabled=current[i].enabled;else delete op.enabled}
 return {operations,...aiBounds(operations)}
}
export function aiSurfaceOffset(group,picked,size){
 const bounds=aiBounds(group.base),shape=bounds.hi.map((n,i)=>n-bounds.lo[i]+1),normal=picked.normal??[0,1,0],axis=normal.findIndex(n=>n!==0)
 if(axis<0||normal.filter(n=>n!==0).length!==1)throw Error('请选择方块的平整表面')
 const lo=picked.position.map((n,i)=>i===axis?(normal[i]>0?n+1:n-shape[i]):n-Math.floor(shape[i]/2))
 if(lo.some((n,i)=>n<0||n+shape[i]>size[i]))throw Error('这个表面放不下整组构件，请换一个位置或使用 XYZ 偏移')
 return lo.map((n,i)=>n-bounds.lo[i])
}
