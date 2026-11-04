async function activity(body){const r=await fetch('/__detail__/ai-activities',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const v=await r.json();if(!r.ok)throw Error(v.error||'AI任务日志写入失败');return v}
let inFlight=false,cancelled=false
export function cancelAI(){cancelled=true;return window.nbtDesktop.apiCancel()}
export async function requestAI(input,capture){
 if(inFlight)throw Error('已有AI请求进行中，请等待或取消')
 inFlight=true;cancelled=false;let log,apiMetrics
 const started=performance.now(),timings={setup_ms:0,capture_ms:0,api_roundtrip_ms:0}
 const measure=async(key,operation)=>{const at=performance.now();try{return await operation()}finally{timings[key]=Math.round(performance.now()-at)}}
 try{
 const flow=input.mode==='workbench'&&input.context?.task==='draft'?'draft':input.mode
 const retrieval=window.nbtReferencePicker?.receipt(flow)
 const [config,connection]=await Promise.all([window.nbtDesktop.internalAIConfig(),window.nbtDesktop.apiConfig()]),settings=config.workflows[flow]
 log=await activity({action:'start',workflow:flow,label:config.flows[flow].label,instruction:input.instruction.slice(0,12000),screenshot:!!settings.attachViewport,model:connection.model,provider:connection.provider})
 timings.setup_ms=Math.round(performance.now()-started)
  if(cancelled)throw Error('API请求已取消')
  let viewport
  if(settings.attachViewport){await activity({action:'stage',id:log.id,phase:'capture',message:'等待当前预览完成，截取建模视口'});if(!capture)throw Error('当前流程无法读取建模视口');viewport=await measure('capture_ms',()=>capture(()=>cancelled))}
  if(cancelled)throw Error('API请求已取消')
  await activity({action:'stage',id:log.id,phase:'api',message:viewport?'发送要求与视口截图，等待API返回':'发送文字要求，等待API返回'})
  if(cancelled)throw Error('API请求已取消')
  const result=await measure('api_roundtrip_ms',()=>window.nbtDesktop.apiGenerate({...input,...(retrieval?{retrieval}:{}),...(viewport?{viewport}:{})}))
  apiMetrics=result?.api_metrics??result?.api_error?.api_metrics
  if(result?.api_error){const error=new Error(result.api_error.message);error.api_metrics=result.api_error.api_metrics;throw error}
  if(cancelled)throw Error('API请求已取消')
  timings.request_total_ms=Math.round(performance.now()-started)
  await activity({action:'finish',id:log.id,status:'complete',api_metrics:result.api_metrics,timings,message:(result.api_metrics?.retried_compact?'输出达到上限后已精简重试成功；':'')+'API候选已返回并通过格式校验，尚未执行建筑导出',summary:result.summary||result.text?.slice(0,1200)||'',operations:result.settings_patch?.operations?.length??result.operations?.length??0,reference_sources:result.reference_sources})
  return {...result,activity_id:log.id}
 }catch(e){timings.request_total_ms=Math.round(performance.now()-started);if(log)try{await activity({action:'finish',id:log.id,status:/取消/.test(e.message)?'cancelled':'failed',api_metrics:e.api_metrics??apiMetrics,timings,message:e.message})}catch{}throw e}finally{inFlight=false}
}
export async function previewAI(result,apply){
 if(!result?.activity_id)return apply()
 await activity({action:'stage',id:result.activity_id,phase:'preview',message:'本地校验、合并候选并生成3D预览'})
 const started=performance.now(),timings=()=>({preview_ms:Math.round(performance.now()-started)})
 try{const value=await apply();await activity({action:'finish',id:result.activity_id,status:'complete',timings:timings(),message:'本地预览完成；原稿保留，尚未导出正式建筑'});return value}
 catch(e){const cancelled=e.name==='AbortError'||/取消/.test(e.message);await activity({action:'finish',id:result.activity_id,status:cancelled?'cancelled':'failed',timings:timings(),message:(cancelled?'预览取消：':'预览失败：')+e.message});throw e}
}
