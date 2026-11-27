// One sequential, workspace-bound Python worker. Never retries a request.
import {spawn} from 'node:child_process'
import {randomUUID} from 'node:crypto'
import path from 'node:path'
import {fileURLToPath} from 'node:url'

export function createEngineSession({workspace,python='python',script=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../../scripts/nbt_engine_session.py'),timeoutMs=30000,idleMs=30000,maxPending=32}={}){
 workspace=path.resolve(workspace)
 let worker=null,current=null,closed=false,idleTimer,buffer=Buffer.alloc(0),starts=0
 const queue=[]
 const failure=(message,code)=>Object.assign(Error(message),{code,retryable:false})
 const ref=value=>{worker?.[value]?.();for(const stream of [worker?.stdin,worker?.stdout,worker?.stderr])stream?.[value]?.()}
 function finish(error,value){if(!current)return;const task=current;current=null;clearTimeout(task.timer);task.signal?.removeEventListener('abort',task.abort);error?task.reject(error):task.resolve(value);pump()}
 function stop(){clearTimeout(idleTimer);const old=worker;worker=null;buffer=Buffer.alloc(0);if(old){old.stdin.destroy();old.kill()}return old}
 function start(){
  starts++;const child=spawn(python,['-u','-B',script,'--workspace',workspace],{cwd:path.dirname(script),shell:false,windowsHide:true,env:{...process.env,PYTHONUTF8:'1',PYTHONIOENCODING:'utf-8'}});worker=child;buffer=Buffer.alloc(0)
  child.stdin.on('error',()=>{})
  child.stderr.on('data',()=>{})
  child.stdout.on('data',chunk=>{
   if(worker!==child)return
   buffer=Buffer.concat([buffer,chunk]);if(buffer.length>32*1024*1024+1){stop();finish(failure('建模会话返回过大','RESPONSE_TOO_LARGE'));return}
   const end=buffer.indexOf(10);if(end<0)return
   try{
    const data=JSON.parse(buffer.subarray(0,end).toString('utf8'));buffer=buffer.subarray(end+1)
    if(!current||data.id!==current.id||buffer.length)throw Error('会话响应编号或边界无效')
    if(data.code==='STALE_ENGINE')stop()
    finish(null,data)
   }catch{stop();finish(failure('建模会话响应无效','INVALID_RESPONSE'))}
  })
  child.on('error',()=>{if(worker===child){stop();finish(failure('建模进程无法启动，请检查Python运行环境','ENGINE_UNAVAILABLE'))}})
  child.on('close',()=>{if(worker===child){stop();finish(failure('建模进程异常结束；本次请求未重试','ENGINE_EXITED'))}})
 }
 function pump(){
  if(current||closed)return
  const task=queue.shift()
  if(!task){if(worker){ref('unref');idleTimer=setTimeout(()=>stop(),idleMs);idleTimer.unref()}return}
  clearTimeout(idleTimer);current=task
  if(!worker)start();ref('ref')
  task.timer=setTimeout(()=>{stop();finish(failure('建模会话超时，请缩小生成范围','ENGINE_TIMEOUT'))},timeoutMs)
  worker.stdin.write(task.payload)
 }
 function request(method,params,{signal}={}){
  if(closed)return Promise.reject(failure('建模会话已关闭','ENGINE_CLOSED'))
  if(signal?.aborted)return Promise.reject(failure('建模会话已取消','AI_CANCELLED'))
  if(queue.length+Number(!!current)>=maxPending)return Promise.reject(failure('建模会话等待队列已满','ENGINE_QUEUE_FULL'))
  const id=randomUUID(),payload=Buffer.from(JSON.stringify({id,method,params})+'\n')
  if(payload.length>8*1024*1024)return Promise.reject(failure('建模请求超过8MiB','REQUEST_TOO_LARGE'))
  return new Promise((resolve,reject)=>{
   const task={id,payload,resolve,reject,signal}
   task.abort=()=>{if(current===task){stop();finish(failure('建模会话已取消','AI_CANCELLED'))}else{const index=queue.indexOf(task);if(index>=0){queue.splice(index,1);signal.removeEventListener('abort',task.abort);reject(failure('建模会话已取消','AI_CANCELLED'))}}}
   signal?.addEventListener('abort',task.abort,{once:true});queue.push(task);pump()
  })
 }
 async function close(){closed=true;clearTimeout(idleTimer);for(const task of queue.splice(0)){task.signal?.removeEventListener('abort',task.abort);task.reject(failure('建模会话已关闭','ENGINE_CLOSED'))}ref('ref');const child=stop();finish(failure('建模会话已关闭','ENGINE_CLOSED'));if(child&&child.exitCode===null&&child.signalCode===null)await new Promise(resolve=>child.once('close',resolve))}
 return {request,close,state:()=>({running:!!current,queued:queue.length,starts,closed})}
}
