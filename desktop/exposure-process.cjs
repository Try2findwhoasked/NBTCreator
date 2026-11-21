const {spawn}=require('node:child_process')

function createExposureProcess({python,script,start=spawn}){
 const jobs=new Set()
 function run(workspace,command,options=[],timeoutMs=45000){
  return new Promise((resolve,reject)=>{
   const child=start(python,['-B',script,command,'--workspace',workspace,...options],{cwd:workspace,shell:false,windowsHide:true})
   const chunks=[]
   let bytes=0,finished=false
   function finish(error,value){
    if(finished)return
    finished=true
    clearTimeout(timer)
    jobs.delete(stop)
    if(error)reject(error)
    else resolve(value)
   }
   function stop(message){
    if(finished)return
    finish(Error(message))
    child.kill('SIGKILL')
   }
   const timer=setTimeout(()=>stop('资料同步超时，已终止进程；可在外部助手设置重试'),timeoutMs)
   jobs.add(stop)
   child.stderr.resume()
   child.stdout.on('data',chunk=>{
    if(finished)return
    bytes+=chunk.length
    if(bytes>6*1024*1024)stop('资料响应超过 6 MiB，请检查配置或缩小正文')
    else chunks.push(chunk)
   })
   child.once('error',finish)
   child.once('close',code=>{
    if(finished)return
    try{
     const result=JSON.parse(Buffer.concat(chunks).toString('utf8'))
     if(code!==0)throw Error(result.error||'资料同步失败')
     finish(null,result)
    }catch(error){finish(error instanceof SyntaxError?Error('资料响应无效，请检查工作区配置与写入权限'):error)}
   })
  })
 }
 return {run,cancel:()=>{for(const stop of jobs)stop('工作区已切换或关闭，资料同步已取消')}}
}
module.exports={createExposureProcess}
