async function activity(body){const r=await fetch('/__detail__/ai-activities',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const v=await r.json();if(!r.ok)throw Error(v.error||'AI任务日志写入失败');return v}
const inFlight=new Map()
const cancelledError=()=>Object.assign(Error('本次生成已终止'),{code:'AI_CANCELLED'})
export function cancelAI(scope){const selected=[...inFlight.entries()].filter(([key])=>scope===undefined||key===scope);for(const [,token]of selected){token.cancelled=true;token.stop();Promise.resolve().then(()=>window.nbtDesktop.apiCancel(token.id)).catch(()=>{})}return Promise.resolve(selected.length>0)}
export async function requestAI(input,capture,options={}){
 input=structuredClone(input)
 const scope=options.scope??input.mode;if(inFlight.has(scope))throw Error('当前编辑区域已有AI请求，请等待或取消')
 const token={id:crypto.randomUUID(),cancelled:false};const stopped=new Promise((_,reject)=>{token.stop=()=>reject(cancelledError())});stopped.catch(()=>{});const wait=operation=>Promise.race([operation,stopped]);inFlight.set(scope,token);let log,apiMetrics,finishSent=false
 const finishCancelled=()=>{if(!log||finishSent)return;finishSent=true;activity({action:'finish',id:log.id,status:'cancelled',api_metrics:apiMetrics,timings,message:'本次生成已终止，未采用结果'}).catch(()=>{})}
 const started=performance.now(),timings={setup_ms:0,capture_ms:0,api_roundtrip_ms:0}
 const measure=async(key,operation)=>{const at=performance.now();try{return await operation()}finally{timings[key]=Math.round(performance.now()-at)}}
 try{
 const flow=input.mode==='workbench'&&input.context?.task==='draft'?'draft':input.mode
 const retrieval=structuredClone(window.nbtReferencePicker?.receipt(flow))
 const [config,connection]=await wait(Promise.all([window.nbtDesktop.internalAIConfig(),window.nbtDesktop.apiConfig()])),settings=config.workflows[flow]
 await wait(activity({action:'start',workflow:flow,label:config.flows[flow].label,instruction:input.instruction.slice(0,12000),screenshot:!!settings.attachViewport,model:connection.model,provider:connection.provider}).then(value=>{log=value;if(token.cancelled)finishCancelled();return value}))
 timings.setup_ms=Math.round(performance.now()-started)
  if(token.cancelled)throw cancelledError()
  let viewport
  if(settings.attachViewport){await wait(activity({action:'stage',id:log.id,phase:'capture',message:'等待当前预览完成，截取建模视口'}));if(!capture)throw Error('当前流程无法读取建模视口');viewport=await wait(measure('capture_ms',()=>capture(()=>token.cancelled)))}
  if(token.cancelled)throw cancelledError()
  await wait(activity({action:'stage',id:log.id,phase:'api',message:viewport?'发送要求与视口截图，等待API返回':'发送文字要求，等待API返回'}))
  if(token.cancelled)throw cancelledError()
  const result=await wait(measure('api_roundtrip_ms',()=>window.nbtDesktop.apiGenerate({...input,...(retrieval?{retrieval}:{}),...(viewport?{viewport}:{})},{requestId:token.id})))
  apiMetrics=result?.api_metrics??result?.api_error?.api_metrics
  if(result?.api_error){const error=new Error(result.api_error.message);error.api_metrics=result.api_error.api_metrics;error.code=result.api_error.code;error.retryable=result.api_error.retryable;throw error}
  if(token.cancelled)throw cancelledError()
  timings.request_total_ms=Math.round(performance.now()-started)
  await wait(activity({action:'finish',id:log.id,status:'complete',api_metrics:result.api_metrics,timings,message:(result.api_metrics?.retried_compact?'输出达到上限后已精简重试成功；':'')+'API候选已返回并通过格式校验，尚未执行建筑导出',summary:result.summary||result.text?.slice(0,1200)||'',operations:result.settings_patch?.operations?.length??result.operations?.length??0,reference_sources:result.reference_sources}))
  if(token.cancelled)throw cancelledError()
  return {...result,activity_id:log.id}
 }catch(e){timings.request_total_ms=Math.round(performance.now()-started);if(token.cancelled||e.code==='AI_CANCELLED'){finishCancelled();throw cancelledError()}if(log)try{await activity({action:'finish',id:log.id,status:'failed',api_metrics:e.api_metrics??apiMetrics,timings,message:e.message})}catch{}throw e}finally{if(inFlight.get(scope)===token)inFlight.delete(scope)}
}
export async function previewAI(result,apply){
 if(!result?.activity_id)return apply()
 await activity({action:'stage',id:result.activity_id,phase:'preview',message:'本地校验、合并候选并生成3D预览'})
 const started=performance.now(),timings=()=>({preview_ms:Math.round(performance.now()-started)})
 try{const value=await apply();await activity({action:'finish',id:result.activity_id,status:'complete',timings:timings(),message:'本地预览完成；原稿保留，尚未导出正式建筑'});return value}
 catch(e){const cancelled=e.name==='AbortError'||/取消/.test(e.message);await activity({action:'finish',id:result.activity_id,status:cancelled?'cancelled':'failed',timings:timings(),message:(cancelled?'预览取消：':'预览失败：')+e.message});throw e}
}
