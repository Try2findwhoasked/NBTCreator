export function initTaskRecords(){
 const $=id=>document.getElementById(id),labels={batch:'批量预览与检查',ai:'AI 构建 / 方案',plan:'生成修改方案',preview:'效果预览',snapshot:'载入3D模型',render:'纹理出图',revision:'导出建筑新版本',prepare:'生成审阅图',apply:'已确认精修',preset:'保存参数',validate:'检查候选效果',compare:'只读版本对比','walk-inspect':'玩家尺度与通路检查'},statuses={running:'运行中',complete:'已完成',failed:'失败',cancelled:'已取消'}
 const effectiveStatus=job=>(job.kind==='validate'&&job.result?.passed===false||job.kind==='walk-inspect'&&job.result?.report?.passed===false||job.kind==='batch'&&job.result?.progress?.failed>0)?'failed':job.status
 const phaseName=job=>({capture:'视口截图',api:'API 生成',preview:'本地预览'}[job.phase]??(job.kind==='ai'?'AI 请求':'本地任务'))
 const text=(tag,value,cls)=>{const e=document.createElement(tag);if(value!==undefined)e.textContent=value;if(cls)e.className=cls;return e}
  const seconds=value=>(value/1000).toFixed(2)+' 秒'
  function measurements(job,body){
   const t=job.timings??{},m=job.api_metrics??{}
   const phases=[['capture_ms','截图'],['api_roundtrip_ms','AI请求'],['preview_ms','本地预览']].filter(([key])=>Number.isFinite(t[key])).map(([key,label])=>label+' '+seconds(t[key]))
   if(phases.length)body.append(text('p',phases.join(' · ')))
   if(Number.isFinite(t.request_total_ms))body.append(text('p','生成候选合计 '+seconds(t.request_total_ms)+'（不含之后的审阅等待和本地预览）','muted'))
   if(Number.isFinite(m.input_text_chars))body.append(text('p','输入文字 '+m.input_text_chars+' 字符'+(Number.isFinite(m.output_chars)?' · 返回正文 '+m.output_chars+' 字符':'')))
   for(const call of m.calls??[]){
    const parts=['第 '+call.attempt+' 次 API：'+({complete:'已返回',failed:'失败',timeout:'超时',cancelled:'取消'}[call.status]??'结束')]
    if(Number.isFinite(call.elapsed_ms))parts.push(seconds(call.elapsed_ms))
    if(Number.isFinite(call.headers_ms))parts.push('等待响应 '+seconds(call.headers_ms))
    if(Number.isFinite(call.read_ms))parts.push('接收 '+seconds(call.read_ms))
    if(Number.isFinite(call.completion_tokens))parts.push('返回 '+call.completion_tokens+' tokens')
    if(call.finish_reason==='length')parts.push('达到长度上限')
    body.append(text('p',parts.join(' · ')))
   }
   if(m.calls?.length){const counted=m.calls.filter(call=>Number.isFinite(call.total_tokens)).length;body.append(text('p','接口提供了 '+counted+'/'+m.calls.length+' 次请求的合计 token 用量；缺失用量不按零消耗计算。','muted'))}
   if(Number.isFinite(m.validation_ms))body.append(text('p','返回格式与参数检查 '+seconds(m.validation_ms),'muted'))
   if(Number.isFinite(m.operation_changes))body.append(text('p','AI增量修改 '+m.operation_changes+' 个工具步骤，其余步骤由本地保留。'))
  }
 let records=[],timer=null,loading=false,selected=null,detailSignature='';const cards=new Map()
 const dialog=document.createElement('dialog');dialog.id='task-detail-dialog';dialog.className='task-detail-dialog';dialog.innerHTML='<header><h2>任务详情</h2><button type="button" id="task-detail-close">关闭</button></header><div id="task-detail-body"></div>';document.body.append(dialog);$('task-detail-close').onclick=()=>dialog.close();dialog.addEventListener('close',()=>{selected=null;detailSignature=''})
 function description(job){const r=job.result??{},parts=[];if(job.kind==='walk-inspect'&&r.report)return (r.report.passed?'静态步行通过':r.report.search_limit_reached?'达到搜索上限，未完成检查':'存在未通过或未确定项目')+' · '+r.report.targets.length+' 个终点 · 不写建筑';if(Number.isFinite(r.changed_blocks))parts.push(`${r.changed_blocks} 个方块变化`);if(r.operations!==undefined)parts.push(`${Array.isArray(r.operations)?r.operations.length:r.operations} 项操作`);if(r.wall_membership_changes)parts.push(`${r.wall_membership_changes} 个墙层归属变化`);if(r.runtime_files?.length)parts.push(`${r.runtime_files.length} 份 NBT`);if(job.kind==='ai')parts.push(job.screenshot?'已附视口截图':'仅文字');if(r.preview_only)parts.push('仅预览');return (job.kind==='ai'?[r.summary,job.events?.at(-1)?.message].filter(Boolean).join(' · '):r.summary)||parts.join(' · ')||'查看详情了解执行过程与输出。'}
 function timing(job){const start=new Date(job.created_at),end=job.completed_at?new Date(job.completed_at):null;return `${start.toLocaleString('zh-CN')} · ${end?((end-start)/1000).toFixed(1)+' 秒':'正在处理'}`}
 function downloads(job){const r=job.result??{},files=[...(r.nbt_downloads??[])];for(const [key,name,file]of [['plan_download','操作计划','plan.json'],['validation_download','候选检查报告','validation.json'],['difference_download','差异报告','difference.json'],['report_download','通路检查报告','walk-inspection.json']])if(r[key])files.push({name,url:r[key],file});return files}
 function fillDetail(){
  const job=records.find(job=>job.id===selected);if(!job)return;const signature=JSON.stringify(job);if(signature===detailSignature)return;detailSignature=signature
  const body=$('task-detail-body'),scroll=body.scrollTop,technicalOpen=body.querySelector('details')?.open??false;body.replaceChildren();dialog.querySelector('h2').textContent=job.label??labels[job.kind]??job.kind
  body.append(text('p',timing(job),'task-time'),text('p',description(job),'task-entry-summary'));if(job.kind==='ai'){const m=job.api_metrics;body.append(text('h3','请求信息'),text('p',`${phaseName(job)} · ${statuses[effectiveStatus(job)]??job.status}${job.model?' · '+job.model:''}`));if(m)body.append(text('p',`${m.attempts??1} 次 API 请求${m.retried_compact?'（包含一次精简重试）':''}${Number.isFinite(m.completion_tokens)?' · 返回 '+m.completion_tokens+' tokens':''}${Number.isFinite(m.total_tokens)?' · 合计 '+m.total_tokens+' tokens':''}`));body.append(text('p','API 返回候选后，还要经过本地校验和预览。此处完成不代表正式建筑已导出。','muted'))}if(job.instruction)body.append(text('h3','本次要求'),text('p',job.instruction,'task-instruction'));if(job.error)body.append(text('p',phaseName(job)+'未完成：'+job.error,'task-entry-error'))
   if(job.backend_exit){const e=job.backend_exit;body.append(text('h3','本地工具进程'),text('p',e.phase+' · 退出 '+(e.exit_hex??e.exit_code??e.signal)+' · 返回 '+e.stdout_bytes+' 字节'));if(!e.stdout_bytes&&e.exit_code!==0)body.append(text('p','进程结束前没有返回结果；不是已完成的模型，也不能据此判断AI响应有问题。','muted'))}
   if(job.kind==='ai')measurements(job,body)
   if(job.result?.reference_sources?.length){body.append(text('h3','本次提供的参考'));for(const item of job.result.reference_sources){const row=text('p',item.citation+' · '+item.label+(item.line_start?' · 第'+item.line_start+'～'+item.line_end+'行':''),'task-location');row.title='SHA256 '+item.sha256;body.append(row)}body.append(text('small','这些来源曾提供给模型；是否被采纳需结合结果审阅。'))}
   if(job.result?.diagnostics?.issues?.length){body.append(text('h3','检查问题与调整方向'));for(const issue of job.result.diagnostics.issues){body.append(text('strong',issue.title),text('p',issue.explanation));const steps=text('ul');for(const line of issue.suggestions)steps.append(text('li',line));body.append(steps)}body.append(text('small','这是当时报告的解释；当前版本变化后应重新检查。'))}
   if(job.events?.length){body.append(text('h3','执行过程'));const trail=text('ol',undefined,'ai-task-events');for(const event of job.events)trail.append(text('li',new Date(event.time).toLocaleTimeString('zh-CN')+' · '+event.message));body.append(trail)}
  const location=job.result?.output??job.directory;if(location)body.append(text('h3','输出位置'),text('p',location,'task-location'))
  const links=text('div',undefined,'task-file-links');for(const file of downloads(job)){const a=text('a',file.name);a.href=file.url;a.download=file.file??file.name;links.append(a)}if(links.children.length)body.append(text('h3','下载产物'),links)
  const technical=text('details');technical.open=technicalOpen;technical.append(text('summary','技术记录（JSON）'),text('pre',JSON.stringify(job,null,2)));body.append(technical);body.scrollTop=scroll
 }
 function render(){
  const query=$('task-search').value.toLowerCase(),filter=$('task-filter').value,shown=records.filter(job=>(filter==='all'||effectiveStatus(job)===filter)&&(!query||JSON.stringify([job.kind,job.label,job.instruction,labels[job.kind],effectiveStatus(job),job.directory,job.result?.output,job.error]).toLowerCase().includes(query))).slice(0,100),list=$('task-list'),wanted=new Set(shown.map(job=>job.id))
  $('task-list-summary').textContent=`当前会话 ${records.length} 项 · 显示 ${shown.length} 项`;list.querySelector('.task-empty')?.remove()
  for(const [id,entry]of cards)if(!wanted.has(id)){entry.card.remove();cards.delete(id)}
  let previous=null
  for(const job of shown){
   let entry=cards.get(job.id);if(!entry){const card=text('article',undefined,'task-entry');card.dataset.taskId=job.id;card.innerHTML='<div class="task-entry-header"><strong></strong><span></span></div><p class="task-time"></p><p class="task-entry-summary"></p><p class="task-entry-error" hidden></p><p class="task-location"></p><button type="button" class="task-details-button">查看详情与产物</button>';card.querySelector('button').onclick=()=>{selected=job.id;detailSignature='';fillDetail();dialog.showModal()};entry={card,signature:''};cards.set(job.id,entry)}
   const signature=JSON.stringify(job);if(signature!==entry.signature){entry.signature=signature;const card=entry.card,title=job.label??labels[job.kind]??job.kind;card.querySelector('strong').textContent=title;card.querySelector('strong').title=title;const state=card.querySelector('.task-entry-header span');state.className='task-state '+effectiveStatus(job);state.textContent=job.kind==='ai'&&job.status==='failed'?phaseName(job)+'未完成':job.kind==='validate'&&job.result?.passed===false?'检查未通过':job.kind==='walk-inspect'&&job.result?.report?.passed===false?(job.result.report.search_limit_reached?'检查未完成':'检查未通过 / 未确定'):statuses[effectiveStatus(job)]??job.status;card.querySelector('.task-time').textContent=timing(job);card.querySelector('.task-entry-summary').textContent=description(job);const error=card.querySelector('.task-entry-error');error.hidden=!job.error;error.textContent=job.error??'';error.title=job.error??'';const location=job.result?.output??job.directory??'';card.querySelector('.task-location').textContent=location;card.querySelector('.task-location').title=location;const count=downloads(job).length;card.querySelector('button').textContent=count?`查看详情 · ${count} 份产物`:'查看详情与日志'}
   const expected=previous?previous.nextElementSibling:list.firstElementChild;if(expected!==entry.card)list.insertBefore(entry.card,expected);previous=entry.card
  }
  if(!shown.length)list.append(text('p','暂无匹配任务。生成预览、方案或导出后，记录会显示在这里。','muted task-empty'));if(dialog.open)fillDetail()
 }
 async function refresh(){if(loading)return;loading=true;try{const response=await fetch('/__detail__/jobs');if(!response.ok)throw Error('任务记录加载失败');records=(await response.json()).reverse();render()}catch(e){$('task-list-summary').textContent=e.message}finally{loading=false}}
 $('task-search').oninput=render;$('task-filter').onchange=render;$('refresh-task-list').onclick=refresh
 window.addEventListener('creator-workspace-change',event=>{clearInterval(timer);dialog.close();if(event.detail==='tasks'){refresh();timer=setInterval(refresh,1500)}})
}
