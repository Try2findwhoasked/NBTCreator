// Convert only the reviewed candidate to the original model-facing coordinate
// space. Settings, private paths and geometry outside the selection stay local.
export function previewRepair(result, failure, context, sourceHash, options){
 const patch=structuredClone(result.settings_patch)
 if(failure.source_sha256!==sourceHash||!context)throw Error('预览源版本已变化，请重新生成')
 if(result.mode==='selection_edit'&&patch.baseline_geometry_sha256!==context.selection?.geometry_sha256)
  throw Error('选区数据已变化，请重新预览')
 const local=p=>p.map((v,i)=>v-context.lo[i])
 let candidate
 if(result.mode==='selection_edit'){
  candidate={summary:result.summary,coordinate_space:'local',operations:patch.operations}
 }else if(result.mode==='small_structure'){
  for(const field of ['lo','hi'])patch[field]=local(patch[field])
  for(const op of patch.operations)for(const key of ['lo','hi','start','end'])if(op[key])op[key]=local(op[key])
  candidate={summary:result.summary,coordinate_space:'local',structure_name:result.structure_name,camera:result.camera,settings_patch:patch}
 }else candidate={summary:result.summary,settings_patch:patch}
 const inside=p=>p.every((v,i)=>v>=context.lo[i]&&v<=context.hi[i])
 const crossed_faces=[]
 for(const [i,axis] of ['x','y','z'].entries()){
  if(failure.positions.some(p=>p[i]<context.lo[i]))crossed_faces.push('-'+axis)
  if(failure.positions.some(p=>p[i]>context.hi[i]))crossed_faces.push('+'+axis)
 }
 return {candidate,issue:{kind:failure.kind,step:failure.step,panel:failure.panel,
  source_sha256:sourceHash,policy_sha256:failure.policy_sha256,settings_sha256:failure.settings_sha256,
  lo:context.lo,hi:context.hi,max_changed_blocks:failure.max_changed_blocks,
  allow_overwrite:options.overwrite,skip_protected:options.skipProtected,
  positions:failure.positions.filter(inside).slice(0,8).map(local),crossed_faces,
  ...(context.selection?{geometry_sha256:context.selection.geometry_sha256}:{})}}
}
