const {randomUUID}=require('node:crypto')
function createAiScheduler({limit=()=>2,maxPending=64,maxPreparing=2}={}){
 const tasks=new Map(),queue=[],preparations=[];let running=0,preparing=0
 const cancelled=()=>Object.assign(Error('API 请求已取消'),{code:'AI_CANCELLED',retryable:false})
 function pump(){while(running<limit()&&queue.length){const item=queue[0];if(!tasks.has(item.id)){queue.shift();continue}queue.shift();running++;item.state='running';item.token.metrics.queue_ms=Math.round(performance.now()-item.token.started);Promise.resolve().then(()=>{if(item.token.cancelled)throw cancelled();return item.run(item.token)}).then(value=>{running--;tasks.delete(item.id);pump();item.resolve(value)},error=>{running--;tasks.delete(item.id);pump();item.reject(error)})}}
 function prepareNext(){while(preparing<maxPreparing&&preparations.length){const item=preparations.shift();if(!tasks.has(item.id))continue;preparing++;let started;Promise.resolve().then(async()=>{const snapshot=await item.token.captured;if(item.token.cancelled)throw cancelled();started=performance.now();return item.prepare(snapshot)}).then(item.preparedResolve,item.preparedReject).finally(()=>{preparing--;item.token.metrics.context_prepare_ms=started===undefined?0:Math.round(performance.now()-started);prepareNext();pump()})}}
 function run(id,operation,prepare=()=>null,capture=()=>null){
  id??=randomUUID();if(typeof id!=='string'||!/^[A-Za-z0-9_-]{16,128}$/.test(id))return Promise.reject(Error('AI 请求编号无效'))
  if(tasks.has(id))return Promise.reject(Object.assign(Error('AI 请求编号已在执行'),{code:'REQUEST_IN_PROGRESS'}))
  if(tasks.size>=maxPending)return Promise.reject(Object.assign(Error('AI 等待队列已满'),{code:'AI_QUEUE_FULL',retryable:true}))
  const token={id,cancelled:false,controller:new AbortController(),started:performance.now(),metrics:{attempts:0,finish_reason:'unknown',retried_compact:false,calls:[]}}
  token.captured=Promise.resolve().then(async()=>{const started=performance.now();try{if(token.cancelled)throw cancelled();return await capture()}finally{token.metrics.capture_ms=Math.round(performance.now()-started)}});token.captured.catch(()=>{})
  let preparedResolve,preparedReject;token.prepared=new Promise((resolve,reject)=>{preparedResolve=resolve;preparedReject=reject});token.prepared.catch(()=>{})
  const promise=new Promise((resolve,reject)=>{const item={id,run:operation,prepare,resolve,reject,token,preparedResolve,preparedReject,state:'queued'};tasks.set(id,item);queue.push(item);preparations.push(item)})
  prepareNext();pump();return promise
 }
 function cancel(id){const selected=id===undefined?[...tasks.values()]:[tasks.get(id)].filter(Boolean);for(const item of selected){item.token.cancelled=true;item.token.controller.abort();if(item.state==='queued'){tasks.delete(item.id);const at=queue.indexOf(item);if(at>=0)queue.splice(at,1);const pending=preparations.indexOf(item);if(pending>=0)preparations.splice(pending,1);item.preparedReject(cancelled());item.reject(cancelled())}}prepareNext();pump();return selected.length>0}
 return {run,cancel,get size(){return tasks.size},state:()=>({running,queued:tasks.size-running,limit:limit()})}
}
module.exports={createAiScheduler}
