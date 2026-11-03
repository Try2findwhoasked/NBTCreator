async function activity(body){const r=await fetch('/__detail__/ai-activities',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const v=await r.json();if(!r.ok)throw Error(v.error||'AI任务日志写入失败');return v}
let inFlight=false,cancelled=false
export function cancelAI(){cancelled=true;return window.nbtDesktop.apiCancel()}
export async function requestAI(input,capture){
 if(inFlight)throw Error('已有AI请求进行中，请等待或取消')
 inFlight=true;cancelled=false;let log
 try{
 const flow=input.mode==='workbench'&&input.context?.task==='draft'?'draft':input.mode
 const config=await window.nbtDesktop.internalAIConfig(),settings=config.workflows[flow]
 const connection=await window.nbtDesktop.apiConfig()
 log=await activity({action:'start',workflow:flow,label:config.flows[flow].label,instruction:input.instruction.slice(0,12000),screenshot:!!settings.attachViewport,model:connection.model,provider:connection.provider})
  if(cancelled)throw Error('API请求已取消')
  let viewport
  if(settings.attachViewport){await activity({action:'stage',id:log.id,message:'截取当前建模视口'});if(!capture)throw Error('当前流程无法读取建模视口');viewport=await capture()}
  if(cancelled)throw Error('API请求已取消')
  await activity({action:'stage',id:log.id,message:viewport?'发送要求与视口截图，等待API返回':'发送文字要求，等待API返回'})
  if(cancelled)throw Error('API请求已取消')
  const result=await window.nbtDesktop.apiGenerate({...input,...(viewport?{viewport}:{})})
  if(cancelled)throw Error('API请求已取消')
  await activity({action:'finish',id:log.id,status:'complete',message:'API候选已返回并通过格式校验，尚未执行建筑导出',summary:result.summary||result.text?.slice(0,1200)||'',operations:result.settings_patch?.operations?.length??result.operations?.length??0})
  return {...result,activity_id:log.id}
 }catch(e){if(log)await activity({action:'finish',id:log.id,status:/取消/.test(e.message)?'cancelled':'failed',message:e.message});throw e}finally{inFlight=false}
}
export async function previewAI(result,apply){
 if(!result?.activity_id)return apply()
 await activity({action:'stage',id:result.activity_id,message:'本地校验、合并候选并生成3D预览'})
 try{const value=await apply();await activity({action:'finish',id:result.activity_id,status:'complete',message:'本地预览完成；原稿保留，尚未导出正式建筑'});return value}
 catch(e){const cancelled=e.name==='AbortError'||/取消/.test(e.message);await activity({action:'finish',id:result.activity_id,status:cancelled?'cancelled':'failed',message:(cancelled?'预览取消：':'预览失败：')+e.message});throw e}
}
