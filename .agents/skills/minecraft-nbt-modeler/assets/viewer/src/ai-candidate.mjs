import {aiComponentCamera} from './ai-component.mjs'
const object=value=>value&&typeof value==='object'&&!Array.isArray(value)
export function validateAICandidate(value,hash){
 if(value==null)return null
 if(!object(value)||Object.keys(value).some(k=>!['schema_version','source_sha256','settings','can_apply','result'].includes(k))||value.schema_version!==1||value.source_sha256!==hash||typeof value.can_apply!=='boolean'||!object(value.settings)||!object(value.result))throw Error('AI候选草稿的来源或格式无效')
 const r=value.result
 if(Object.keys(r).some(k=>!['mode','summary','text','settings_patch','structure_name','camera'].includes(k))||!['prompt','structure','small_structure'].includes(r.mode)||typeof(r.summary??'')!=='string'||(r.summary??'').length>4000||typeof(r.text??'')!=='string'||(r.text??'').length>60000||JSON.stringify(r).length>256*1024)throw Error('AI候选内容无效或过大')
 if(r.mode!=='prompt'&&(!object(r.settings_patch)||Object.keys(r.settings_patch).some(k=>!['lo','hi','structure','replace','operations'].includes(k))))throw Error('AI候选参数字段无效')
 if(r.structure_name!==undefined&&(typeof r.structure_name!=='string'||!r.structure_name.trim()||r.structure_name.length>120))throw Error('AI候选名称无效')
 if(r.camera!==undefined)aiComponentCamera(r.settings_patch?.operations??[],r.camera)
 return value
}
