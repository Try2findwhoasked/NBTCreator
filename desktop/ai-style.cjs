const fs=require('node:fs/promises'),path=require('node:path'),crypto=require('node:crypto')
function createAIStyle({workspace,skill}){
 const schema=require(path.join(skill,'config/ai-style-schema.json'))
 const defaults=()=>({schema_version:1,workflows:Object.fromEntries(Object.keys(schema.workflows).map(flow=>[flow,Object.fromEntries(Object.entries(schema.dimensions).map(([key,value])=>[key,value.default]))]))})
 function validate(data){
  if(!data||data.schema_version!==1||!data.workflows||Object.keys(data.workflows).length!==Object.keys(schema.workflows).length||Object.keys(data.workflows).some(key=>!schema.workflows[key]))throw Error('AI创作偏好配置无效')
  for(const values of Object.values(data.workflows))if(!values||Object.keys(values).length!==Object.keys(schema.dimensions).length||Object.entries(values).some(([key,value])=>!schema.dimensions[key]||!Number.isInteger(value)||value<0||value>100))throw Error('AI创作偏好参数须为0～100的整数')
  return data
 }
 const file=()=>path.join(workspace(),'.nbtcreator/ai-style.json')
 async function load(){try{return validate(JSON.parse((await fs.readFile(file(),'utf8')).replace(/^\uFEFF/,'')))}catch(error){if(error.code==='ENOENT')return defaults();throw error}}
 async function save(data){validate(data);await fs.mkdir(path.dirname(file()),{recursive:true});const temporary=file()+'.'+crypto.randomUUID()+'.tmp';await fs.writeFile(temporary,JSON.stringify(data,null,2)+'\n');await fs.rename(temporary,file());return data}
 async function context(workflow){if(!schema.workflows[workflow])throw Error('未知AI使用区域');const values=(await load()).workflows[workflow],lines=[`使用区域：${schema.workflows[workflow]}。以下为创作偏好；用户本次明确要求优先。`]
  for(const [key,dimension]of Object.entries(schema.dimensions)){const value=values[key],band=value<34?'low':value>66?'high':'middle';lines.push(`${dimension.label} ${value}/100（${dimension.left} ↔ ${dimension.right}）：${dimension[band]}`)}
  lines.push('创作偏好不改变选区、源文件、保护、预算、返回格式及真实看图确认要求；不得据此声称已执行或已通过验收。')
  return {values,prompt:lines.join('\n')}
 }
 return {schema,load,save,context,validate}
}
module.exports={createAIStyle}
