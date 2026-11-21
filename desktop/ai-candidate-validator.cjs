const fs=require('node:fs/promises'),path=require('node:path'),{pathToFileURL}=require('node:url')

function createCandidateValidator({root,python,directory,getWorkspace}){
 let session,workspace,loading
 async function validate({mode,result,context,signal}){
  if(mode==='prompt'||mode==='workbench'&&['brief','constraint'].includes(context.task))return
  const fatal=message=>Object.assign(Error(message),{retryable:false})
  if(signal?.aborted)throw fatal('AI几何预检已取消')
  const target=path.resolve(getWorkspace())
  loading??=import(pathToFileURL(path.join(root,'.agents/skills/minecraft-nbt-modeler/assets/viewer/engine-session.mjs')).href)
  const {createEngineSession}=await loading
  // Workspace transitions are serialized by workspace-api. The worker also
  // changes, so compiled data cannot follow the user into another project.
  if(session&&workspace!==target)await validate.close()
  if(!session){workspace=target;session=createEngineSession({workspace,python})}
  await fs.mkdir(path.join(directory,'ai-validation'),{recursive:true})
  const value=await session.request('validate',{mode,result,context},{signal})
  if(value.ok!==true){
   if(value.code!=='VALIDATION_ERROR')throw fatal(value.error||'AI几何预检失败')
   throw Object.assign(Error('共享引擎预检未通过：'+String(value.error??'候选无效').slice(0,1000)),{issue:value.issue})
  }
  return value.result
 }
 validate.close=async()=>{const old=session;session=null;workspace=null;await old?.close()}
 validate.state=()=>session?.state()??{running:false,queued:0,starts:0,closed:false}
 return validate
}
module.exports={createCandidateValidator}
