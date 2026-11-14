// API calls live in the main process, beyond the lifetime of a workspace worker.
function createWorkspaceApi({cancel,timeoutMs=5000}){
 let epoch=0,paused=false
 const pending=new Set()
 const stale=()=>Error('工作区已切换，本次旧工作区 API 结果已作废')
 function check(token){if(paused||token!==epoch)throw stale()}
 function run(operation){
  if(paused)return Promise.reject(Error('正在切换工作区，请稍后再调用 API'))
  const token=epoch
  const task=(async()=>{const result=await operation();check(token);return result})()
  pending.add(task)
  return task.finally(()=>pending.delete(task))
 }
 function guardContext(operation){return run(operation)}
 async function suspend(){
  if(!paused){paused=true;epoch++;cancel()}
  let timer
  try{
   await Promise.race([
    Promise.allSettled([...pending]),
    new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error('旧工作区 API 尚未结束，已取消切换；请取消请求后重试')),timeoutMs)})
   ])
  }finally{clearTimeout(timer)}
 }
 return {run,guardContext,suspend,resume:()=>{paused=false},state:()=>({epoch,paused,pending:pending.size})}
}
module.exports={createWorkspaceApi}
