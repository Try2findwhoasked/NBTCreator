export function initTaskRecords(){
 const $=id=>document.getElementById(id),labels={ai:'AI 构建 / 方案',plan:'生成修改方案',preview:'效果预览',snapshot:'载入3D模型',render:'纹理出图',revision:'导出建筑新版本',prepare:'生成审阅图',apply:'已确认精修',preset:'保存参数'},statuses={running:'运行中',complete:'已完成',failed:'失败',cancelled:'已取消'}
 let records=[],timer=null,loading=false
 const text=(tag,value,cls)=>{const e=document.createElement(tag);if(value!==undefined)e.textContent=value;if(cls)e.className=cls;return e}
 function render(){
  const query=$('task-search').value.toLowerCase(),filter=$('task-filter').value
  const shown=records.filter(job=>(filter==='all'||job.status===filter)&&(!query||JSON.stringify([job.kind,job.label,job.instruction,labels[job.kind],job.status,job.directory,job.result?.output,job.error]).toLowerCase().includes(query))).slice(0,100)
  $('task-list-summary').textContent=`当前会话 ${records.length} 项 · 显示 ${shown.length} 项`;$('task-list').replaceChildren()
  if(!shown.length){$('task-list').append(text('p','暂无匹配任务。生成预览、方案或导出后，记录会显示在这里。','muted'));return}
  for(const job of shown){
   const card=text('article',undefined,'task-entry'),header=text('div',undefined,'task-entry-header')
   header.append(text('strong',job.label??labels[job.kind]??job.kind),text('span',statuses[job.status]??job.status,'task-state '+job.status));card.append(header)
   const start=new Date(job.created_at),end=job.completed_at?new Date(job.completed_at):null
   card.append(text('p',`${start.toLocaleString('zh-CN')} · ${end?((end-start)/1000).toFixed(1)+' 秒':'正在处理'}`,'task-time'))
   const r=job.result??{},summary=[];if(r.changed_blocks!==undefined)summary.push(`${r.changed_blocks} 个方块变化`);if(r.operations!==undefined)summary.push(`${Array.isArray(r.operations)?r.operations.length:r.operations} 项操作`);if(r.preview_only)summary.push('仅预览');if(r.runtime_files?.length)summary.push(`${r.runtime_files.length} 份 NBT`)
   if(job.kind==='ai'){summary.push(job.screenshot?'已附视口截图':'仅文字');const trail=text('ol',undefined,'ai-task-events');for(const event of job.events??[])trail.append(text('li',new Date(event.time).toLocaleTimeString('zh-CN')+' · '+event.message));card.append(trail);if(job.result?.summary)card.append(text('p',job.result.summary,'task-entry-summary'))}
   if(summary.length)card.append(text('p',summary.join(' · '),'task-entry-summary'))
   if(job.error)card.append(text('p',job.error,'task-entry-error'))
   const path=r.output??job.directory;const location=text('p',path,'task-location');location.title=path;card.append(location)
   const links=text('div',undefined,'task-file-links')
   for(const file of r.nbt_downloads??[]){const a=text('a',file.name);a.href=file.url;a.download=file.name;links.append(a)}
   if(r.plan_download){const a=text('a','下载操作计划');a.href=r.plan_download;a.download='plan.json';links.append(a)}
   card.append(links)
   const more=text('details');more.append(text('summary','技术记录（JSON）'),text('pre',JSON.stringify(job,null,2)));card.append(more);$('task-list').append(card)
  }
 }
 async function refresh(){if(loading)return;loading=true;try{const response=await fetch('/__detail__/jobs');if(!response.ok)throw Error('任务记录加载失败');records=(await response.json()).reverse();render()}catch(e){$('task-list-summary').textContent=e.message}finally{loading=false}}
 $('task-search').oninput=render;$('task-filter').onchange=render;$('refresh-task-list').onclick=refresh
 window.addEventListener('creator-workspace-change',event=>{clearInterval(timer);if(event.detail==='tasks'){refresh();timer=setInterval(refresh,1500)}})
}
