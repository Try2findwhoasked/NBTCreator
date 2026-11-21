const {isDeepStrictEqual}=require('node:util')
const {buildOutputSchema,decodeOutput}=require('./ai-output-schema.cjs')

const sha=value=>typeof value==='string'&&/^[0-9a-f]{64}$/.test(value)
const xyz=value=>Array.isArray(value)&&value.length===3&&value.every(Number.isSafeInteger)
const closed=properties=>({type:'object',properties,required:Object.keys(properties),additionalProperties:false})

// The complete baseline stays local. Only the failed operation and the small
// coordinate sample cross the provider boundary. The engine checks all writes.
function targetRepair(mode, context, repair, validate){
 const {candidate,issue}=repair??{}
 if(!['selection_edit','small_structure','structure'].includes(mode)||!candidate||!issue||
    !['occupied','outside_selection','protection_conflict','target_geometry'].includes(issue.kind)||
    ![issue.source_sha256,issue.policy_sha256,issue.settings_sha256].every(sha)||
    issue.allow_overwrite!==context.allow_overwrite||typeof issue.skip_protected!=='boolean'||
    !Number.isSafeInteger(issue.max_changed_blocks)||issue.max_changed_blocks<1||
    !Array.isArray(issue.positions)||issue.positions.length>8||
    !issue.positions.every(p=>xyz(p)&&p.every((n,i)=>n>=0&&n<=context.hi[i]-context.lo[i]))||
    !isDeepStrictEqual(issue.lo,context.lo)||!isDeepStrictEqual(issue.hi,context.hi)||
    mode==='selection_edit'&&issue.geometry_sha256!==context.selection.geometry_sha256)
  throw Error('真实预览修复绑定无效，请重新预览')
 if(Buffer.byteLength(JSON.stringify(candidate))>512*1024)throw Error('本地修复候选超过512 KiB，请拆分候选')
 validate(candidate)
 const panel=mode==='structure'?issue.panel:null
 const entries=mode==='selection_edit'?candidate.operations:candidate.settings_patch?.operations
 const failed=panel?candidate.settings_patch?.[panel]:entries?.[issue.step-1]
 if(panel?!['structure','replace'].includes(panel)||!failed:
    !Number.isSafeInteger(issue.step)||!failed||failed.enabled===false)throw Error('预览失败项不属于本次候选')
 const faces=issue.crossed_faces??[]
 if(!Array.isArray(faces)||faces.length>6||faces.some(face=>!['-x','+x','-y','+y','-z','+z'].includes(face)))throw Error('选区边界诊断无效')
 const evidence={kind:issue.kind,positions:issue.positions,crossed_faces:faces,max_changed_blocks:issue.max_changed_blocks,
  allow_overwrite:issue.allow_overwrite,skip_protected:issue.skip_protected,
  ...(panel?{panel,lo:candidate.settings_patch.lo,hi:candidate.settings_patch.hi}:{step:issue.step}),
  failed_operation:mode==='small_structure'?Object.fromEntries(['kind','label','classification','lo','hi','state','start','end','width','thickness'].filter(k=>Object.hasOwn(failed,k)).map(k=>[k,failed[k]])):failed}
 if(Buffer.byteLength(JSON.stringify(evidence))>12000)throw Error('失败步骤证据超过12000字节，请拆分候选')
 const full=buildOutputSchema(mode,context)
 let schema
 if(panel){
  const fields=full.properties.settings_patch.properties
  schema=closed({lo:fields.lo,hi:fields.hi,[panel]:fields[panel].anyOf[0]})
 }else{
  const items=(mode==='small_structure'?full.properties.settings_patch.properties:full.properties).operations.items
  schema=closed({step:{type:'integer',enum:[issue.step]},operation:items})
  if(full.$defs)schema.$defs=full.$defs
 }
 return {schema,evidence,merge(wire,strict){
  const value=strict?decodeOutput(wire,schema):wire
  if(!value||typeof value!=='object'||Array.isArray(value)||Object.keys(value).some(k=>!Object.hasOwn(schema.properties,k)))
   throw Error('修复只能替换已定位的一步')
  const result=structuredClone(candidate)
  if(panel){
   if(!value[panel]||!xyz(value.lo)||!xyz(value.hi))throw Error('修复需要失败面板与整数选区')
   if(value.lo.some((n,i)=>n<candidate.settings_patch.lo[i]||value.hi[i]>candidate.settings_patch.hi[i]))throw Error('修复不能扩大原候选选区')
   if(candidate.settings_patch[panel==='structure'?'replace':'structure']&&
     (!isDeepStrictEqual(value.lo,candidate.settings_patch.lo)||!isDeepStrictEqual(value.hi,candidate.settings_patch.hi)))
    throw Error('其他面板也使用同一选区，不能移动保留步骤')
   Object.assign(result.settings_patch,value)
  }else{
   if(value.step!==issue.step||!value.operation||typeof value.operation!=='object'||Array.isArray(value.operation)||
      value.operation.enabled===false||['overwrite','write_group','write_bounds','max_writes','skip_protected'].some(k=>Object.hasOwn(value.operation,k)))
    throw Error('修复须返回指定步骤且保持原权限')
   const operations=mode==='selection_edit'?result.operations:result.settings_patch.operations
   operations[issue.step-1]=value.operation
  }
  return result
 }}
}
module.exports={targetRepair}
