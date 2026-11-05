import './building-history.css'

export function initBuildingHistory({api,openModel,refresh,isBusy,context,compare}){
 const dialog=document.createElement('dialog');dialog.id='building-history-dialog';dialog.setAttribute('aria-label','建筑版本历史')
 dialog.innerHTML=`<header><div><h2>建筑版本</h2><p>找到要继续设计的版本，查看修改说明，或从旧版另存一份。</p></div><button id="version-history-close" type="button">关闭</button></header>
 <div class="building-history-body"><aside><button id="version-history-refresh" type="button">刷新版本</button><div id="version-history-versions"></div></aside><section>
 <h3 id="version-history-title"></h3><p id="version-history-metadata"></p><p id="version-history-warning"></p><label>修改说明<textarea id="version-history-message" maxlength="4000" rows="3"></textarea></label><label>从哪个版本修改而来<select id="version-history-parent"><option value="">来源未登记</option></select></label>
 <div class="history-actions"><button id="version-history-record" type="button">加入版本历史</button><button id="version-history-current" type="button">设为当前工作版</button><button id="version-history-open" type="button">打开这一版</button><button id="version-history-compare" type="button">对比来源版本</button><button id="version-history-derive" type="button">从这一版另存</button><button id="version-history-finalize" type="button" class="primary">定稿并导出 NBT</button></div>
 <details><summary>文件与历史位置</summary><p id="version-history-location" class="path"></p><p id="version-history-repository" class="path"></p></details><p id="version-history-status" role="status"></p></section></div>`
 document.body.append(dialog)
 const $=id=>dialog.querySelector('#'+id),opener=document.createElement('button');opener.id='open-building-history';opener.type='button';opener.textContent='版本';opener.title='查看当前建筑的版本历史';document.querySelector('.preview-controls').append(opener)
 let source='',data={versions:[],current:{}},selected=null,pending=false
 const actor={human:'人工保存',internal_ai:'内置 AI',external_agent:'外部 Agent',import:'已有文件'}
 const title=node=>node.version.split('/').at(-1)
 function message(text,error=false){$('version-history-status').textContent=text;$('version-history-status').classList.toggle('error',error)}
 function controls(){for(const e of dialog.querySelectorAll('button,input,select,textarea'))e.disabled=pending;const node=selected;for(const id of ['version-history-current','version-history-open','version-history-compare','version-history-derive','version-history-finalize'])$(id).disabled=pending||!node;if(node){$('version-history-open').disabled=pending||!node.source_matches;$('version-history-current').disabled=pending||!node.source_matches;$('version-history-finalize').disabled=pending||!node.source_matches;$('version-history-compare').disabled=pending||!node.source_matches||!node.parent||!data.versions.find(n=>n.id===node.parent)?.source_matches}$('version-history-parent').disabled=pending||!!selected;opener.disabled=!!isBusy()||!context()?.source}
 async function perform(fn){if(pending||isBusy())return;pending=true;controls();try{await fn()}catch(error){message(error.message,true)}finally{pending=false;controls()}}
 function details(){
  const node=selected
  $('version-history-title').textContent=node?title(node):'这一版还没有加入历史'
  $('version-history-metadata').textContent=node?`${actor[node.actor]??node.actor} · ${(node.size??[]).join(' × ')} · ${node.format.toUpperCase()} · ${node.tasks?.length??0} 个关联任务 · ${node.comments?.length??0} 条标注`:'加入历史后，可以追溯修改来源并从旧版继续设计。'
  $('version-history-warning').textContent=node?.acceptance==='pending_user_review'?'Agent 已回传，仍待你查看结构并核对。':node&&!node.source_matches?'原文件缺失或已变化；可以从已归档内容另存恢复。':''
  $('version-history-message').value=node?.message??'登记已有建筑版本'
  $('version-history-parent').replaceChildren(new Option('来源未登记',''));for(const item of data.versions)if(item.id!==node?.id)$('version-history-parent').add(new Option(title(item)+' · '+item.message,item.id));$('version-history-parent').value=node?.parent??''
  $('version-history-record').textContent=node?'保存说明与标注记录':'将这一版加入历史'
  $('version-history-finalize').textContent=node?.release?'核对已定稿文件':'定稿并导出 NBT'
  $('version-history-location').textContent=node?.absolute_source??source;$('version-history-repository').textContent=data.repository??'';controls()
 }
 function render(){
  const list=$('version-history-versions');list.replaceChildren()
  if(!data.versions.some(n=>n.absolute_source===source)){const draft=document.createElement('button');draft.type='button';draft.textContent='当前文件 · 未登记';draft.onclick=()=>{selected=null;render();details()};draft.setAttribute('aria-pressed',String(!selected));list.append(draft)}
  for(const node of data.versions){const b=document.createElement('button');b.type='button';b.dataset.historyId=node.id;b.setAttribute('aria-pressed',String(node.id===selected?.id));const h=document.createElement('strong'),p=document.createElement('span'),meta=document.createElement('small');h.textContent=title(node)+(data.current[node.building]===node.id?' · 当前工作版':'');p.textContent=node.message;meta.textContent=(actor[node.actor]??node.actor)+(node.release?' · 已导出 NBT':' · 建筑原稿');b.append(h,p,meta);b.onclick=()=>{selected=node;render();details()};list.append(b)}
  if(!data.versions.length){const p=document.createElement('p');p.textContent='还没有登记的版本。原文件不会被移动或覆盖。';list.append(p)}
 }
 async function load(prefer){data=await api('history/list',{source});selected=data.versions.find(n=>n.id===(prefer??selected?.id))??data.versions.find(n=>n.absolute_source===source)??null;render();details()}
 async function open(file){if(pending||isBusy())return;source=file??context()?.source;if(!source)return;selected=null;message('正在读取该建筑的版本历史…');dialog.showModal();await perform(async()=>{await load();message('选择左侧版本查看。编辑进度会自动保存；保存新版本时才记录建筑历史。')})}
 opener.onclick=()=>open();$('version-history-close').onclick=()=>dialog.close();$('version-history-refresh').onclick=()=>perform(()=>load())
 $('version-history-record').onclick=()=>perform(async()=>{const result=await api('history/record',{source:selected?.absolute_source??source,...(!selected&&$('version-history-parent').value?{parent:$('version-history-parent').value}:{}),message:$('version-history-message').value,actor:'import'});await load(result.version.id);message(result.unchanged?'内容未变，未创建重复历史记录。':'已记录建筑原稿、说明与当前批注快照。')})
 $('version-history-current').onclick=()=>perform(async()=>{await api('history/current',{id:selected.id});await load(selected.id);message('已设为当前工作版；文件和其他版本保持原样。')})
 $('version-history-open').onclick=()=>perform(async()=>{const node=selected;dialog.close();await openModel({source:node.absolute_source})})
 $('version-history-derive').onclick=()=>perform(async()=>{const result=await api('history/derive',{id:selected.id,message:$('version-history-message').value||'从历史版本继续编辑'});await refresh();dialog.close();await openModel({source:result.source})})
 $('version-history-compare').onclick=()=>perform(async()=>{const node=selected,parent=data.versions.find(n=>n.id===node.parent);dialog.close();await openModel({source:node.absolute_source});await compare({source:node.absolute_source,source_sha256:node.source_sha256,reference_source:parent.absolute_source,reference_sha256:parent.source_sha256})})
 $('version-history-finalize').onclick=()=>perform(async()=>{const result=await api('history/finalize',{id:selected.id});await load(selected.id);message('NBT 交付已保存：'+result.output+'。SNBT 与标注仍在原版本目录。')})
 dialog.addEventListener('cancel',event=>{if(pending)event.preventDefault()})
 window.addEventListener('creator-editor-state',controls);window.addEventListener('creator-workspace-change',()=>{if(dialog.open&&!pending)dialog.close();controls()});controls()
 window.creatorBuildingHistory=Object.freeze({open,opener})
 return {open,opener}
}
