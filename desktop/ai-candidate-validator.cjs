const fs=require('node:fs/promises'),path=require('node:path'),{spawn}=require('node:child_process'),{randomUUID}=require('node:crypto')

function createCandidateValidator({root,python,directory,getWorkspace}){
 return async({mode,result,context,signal})=>{
  if(mode==='prompt')return
  const folder=path.join(directory,'ai-validation'),file=path.join(folder,randomUUID()+'.json')
  const fatal=message=>Object.assign(Error(message),{retryable:false})
  await fs.mkdir(folder,{recursive:true})
  try{
   if(signal?.aborted)throw fatal('AI几何预检已取消')
   await fs.writeFile(file,JSON.stringify({mode,result,context,workspace:getWorkspace()}),{flag:'wx'})
   const value=await new Promise((resolve,reject)=>{
    const child=spawn(python,['-B',path.join(root,'.agents/skills/minecraft-nbt-modeler/scripts/nbt_ai_validate.py'),'--request',file],{cwd:root,windowsHide:true,shell:false});let output='',settled=false
    const finish=(error,value)=>{if(settled)return;settled=true;clearTimeout(timer);signal?.removeEventListener('abort',cancel);error?reject(error):resolve(value)}
    const cancel=()=>{child.kill();finish(fatal('AI几何预检已取消'))},timer=setTimeout(()=>{child.kill();finish(fatal('AI几何预检超时，请缩小生成范围'))},30000)
    signal?.addEventListener('abort',cancel,{once:true});if(signal?.aborted)cancel()
    child.stdout.on('data',chunk=>{output+=chunk.toString();if(output.length>65536){child.kill();finish(fatal('AI几何预检返回过大'))}});child.stderr.on('data',()=>{})
    child.on('error',()=>finish(fatal('AI几何预检进程无法启动，请检查随包Python运行环境')))
    child.on('close',code=>{if(settled)return;if(code!==0)return finish(fatal('AI几何预检进程异常结束'));try{finish(null,JSON.parse(output))}catch{finish(fatal('AI几何预检未返回有效检查记录'))}})
   })
   if(value.ok!==true)throw Error('共享引擎预检未通过：'+String(value.error??'候选无效').slice(0,1000))
   return value.result
  }finally{await fs.unlink(file).catch(()=>{})}
 }
}
module.exports={createCandidateValidator}
