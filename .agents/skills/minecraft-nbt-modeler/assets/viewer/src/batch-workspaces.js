import './batch-workspaces.css'

const statusNames={authoring:'制作中',review:'待审阅',delivered:'已交付',failed:'未完成',cancelled:'已取消'}
const roleNames={gallery:'图册',archive:'压缩包',report:'报告／清单',script:'脚本',design:'设计资料',preview:'预览图',other:'其他文件'}
const fileNames={missing:'文件缺失',changed:'内容已变化',needs_verification:'打开时核对',unchanged:'已登记',verified:'哈希一致'}
const key=source=>source.replaceAll('\\','/').toLowerCase()
const element=(tag,text,className)=>{const node=document.createElement(tag);if(text!==undefined)node.textContent=text;if(className)node.className=className;return node}

// A registered task links to authoring models; its delivery copies never enter latest-version selection.
export function initBatchWorkspaces({host,api,getModels,openModel,previewModel,render}){
 const launch=element('button','制作批次');launch.id='batch-workspaces-open';launch.type='button';host.querySelector('.library-actions').prepend(launch)
 const dialog=element('dialog');dialog.id='batch-workspaces-dialog'
 dialog.innerHTML=`<header><div><h2>制作批次</h2><small>过程工作区、正式模型与交付图册</small></div><button id="batch-workspaces-close" type="button">关闭</button></header>
 <div class="batch-workspaces-toolbar"><form id="batch-workspaces-create"><input id="batch-workspaces-name" aria-label="新批次名称" placeholder="新批次名称，例如：残败地牢 30 间" maxlength="160" required><button type="submit">新建批次</button></form><button id="batch-workspaces-refresh" type="button">刷新</button></div>
 <p id="batch-workspaces-message" role="status"></p><div class="batch-workspaces-body"><nav id="batch-workspaces-list" aria-label="批次列表"></nav><main id="batch-workspaces-detail"></main></div>`
 document.body.append(dialog)
 const $=id=>dialog.querySelector('#'+id)
 let tasks=[],candidates=[],links=new Map(),selected='',selectedCandidate='',pending=false,root='',generation=0,loaded=false
 const report=text=>$('batch-workspaces-message').textContent=text
 const safe=action=>async()=>{if(pending)return;pending=true;dialog.setAttribute('aria-busy','true');try{await action()}catch(error){report(error.message)}finally{pending=false;dialog.removeAttribute('aria-busy')}}
 const button=(text,action,props={})=>{const node=element('button',text);node.type='button';Object.assign(node,props);node.onclick=safe(action);return node}
 const pathRow=path=>{const row=element('p',path,'batch-actual-path');row.title=path;return row}
 function reindex(){links=new Map();for(const task of tasks)for(const item of task.models){const path=key(item.absolute_source);if(!links.has(path))links.set(path,[]);links.get(path).push({task,item})}}
 async function refresh(){
  const token=++generation,result=await api('batches/list',{});if(token!==generation)return
  tasks=result.tasks.sort((a,b)=>b.updated_at.localeCompare(a.updated_at));candidates=result.candidates;loaded=true;reindex();launch.classList.toggle('batch-has-new',tasks.some(task=>task.is_new));launch.title=result.batch_root
  if(!selected&&!selectedCandidate)selected=tasks[0]?.id||''
  draw();render();report(result.errors.length?result.errors.map(item=>item.error).join('；'):`${tasks.length} 个已登记批次${candidates.length?' · '+candidates.length+' 个旧批次可登记':''}`)
 }
 function draw(){
  const list=$('batch-workspaces-list');list.replaceChildren()
  for(const task of tasks){const node=button('',async()=>{selected=task.id;selectedCandidate='';draw()});node.dataset.batchId=task.id;node.setAttribute('aria-current',String(selected===task.id));node.append(element('strong',task.name),element('small',`${statusNames[task.status]} · ${task.models.filter(item=>item.kind==='formal').length} 个正式版本${task.is_new?' · 新增':''}`));list.append(node)}
  if(candidates.length){list.append(element('h3','未登记的旧批次'));for(const candidate of candidates){const node=button(candidate.name,async()=>{selected='';selectedCandidate=candidate.workspace_dir;draw()});node.dataset.candidate=candidate.workspace_dir;node.setAttribute('aria-current',String(selectedCandidate===candidate.workspace_dir));list.append(node)}}
  if(!tasks.length&&!candidates.length)list.append(element('p','还没有制作批次。'))
  drawDetail()
 }
 function drawDetail(){
  const detail=$('batch-workspaces-detail');detail.replaceChildren();const task=tasks.find(item=>item.id===selected),candidate=candidates.find(item=>item.workspace_dir===selectedCandidate)
  if(candidate){detail.append(element('h3',candidate.name),pathRow(candidate.workspace_dir),element('p','登记会在原批次内新增 task.json 并建立索引，不搬动已有模型或文件。旧模型默认不标为新增。'));const label=element('label'),check=element('input');check.type='checkbox';check.id='batch-import-highlight';label.append(check,document.createTextNode('将本批次登记的模型标为新增（7 天内，查看后消除）'));detail.append(label,button('登记此批次',async()=>{report('正在核对主模型与图册，首次登记可能需要一些时间…');const result=await api('batches/import',{...candidate,highlight_existing:check.checked});selected=result.id;selectedCandidate='';await refresh()}));return}
  if(!task){detail.append(element('p','选择左侧批次，或填写名称创建。新批次保存在 nbt_models/_workspaces/batches/ 中。'));return}
  detail.append(element('h3',task.name),element('p',`${statusNames[task.status]} · ${new Date(task.updated_at).toLocaleString('zh-CN')}`),pathRow(task.absolute_workspace))
  const actions=element('div',undefined,'batch-link-actions');actions.append(button('打开批次文件夹',()=>native(task,'workspace')),button('复制批次路径',()=>copy(task.absolute_workspace)),button('全部标为已查看',async()=>{await api('batches/ack',{id:task.id,all:true});await refresh()}));detail.append(actions)
  detail.append(element('p','脚本、设计、验证、预览和中间稿放在本批次；正式模型仍在形状／名称／版本目录。这里的交付状态不代表用户已批准精修或完成验收。','batch-workspace-note'))
  const models=element('section');models.append(element('h4','关联模型'))
  appendPages(models,task.models,item=>{
   const row=element('article',undefined,'batch-linked-item');row.dataset.modelId=item.id;row.classList.toggle('batch-item-new',item.is_new);row.append(element('strong',item.name),element('small',`${item.kind==='formal'?'正式模型':'中间稿（仅预览）'} · ${item.size.join(' × ')} · ${fileNames[item.file_status]}${item.is_new?' · 新增':''}`),pathRow(item.absolute_source))
   const controls=element('div',undefined,'batch-link-actions'),disabled=['missing','changed'].includes(item.file_status);controls.append(button('预览',()=>view(task,item,false),{disabled}));if(item.kind==='formal')controls.append(button('进入模型编辑',()=>view(task,item,true),{disabled}));controls.append(button('所在文件夹',()=>native(task,'model',item.id,'reveal'),{disabled}));row.append(controls);return row
  });detail.append(models)
  const files=element('section');files.append(element('h4','图册与其他产物'))
  appendPages(files,task.artifacts,item=>{const row=element('article',undefined,'batch-linked-item');row.dataset.artifactId=item.id;row.append(element('strong',item.name),element('small',`${roleNames[item.role]} · ${fileNames[item.file_status]}`),pathRow(item.absolute_path));const actions=element('div',undefined,'batch-link-actions'),disabled=['missing','changed'].includes(item.file_status);actions.append(button(item.role==='gallery'?'打开图册':'打开／定位',()=>native(task,'artifact',item.id),{disabled}),button('所在文件夹',()=>native(task,'artifact',item.id,'reveal'),{disabled}),button('复制路径',()=>copy(item.absolute_path)));row.append(actions);return row});detail.append(files)
 }
 function appendPages(host,items,make){let limit=0;const more=button('显示更多',async()=>append());function append(){for(const item of items.slice(limit,limit+60))host.insertBefore(make(item),more);limit+=60;more.hidden=limit>=items.length}host.append(more);append();if(!items.length)host.prepend(element('p','尚未登记。'))}
 async function copy(text){if(window.nbtDesktop?.copyAgentPlan)await window.nbtDesktop.copyAgentPlan(text);else await navigator.clipboard.writeText(text);report('路径已复制')}
 async function native(task,kind,item_id,mode='open'){if(!window.nbtDesktop?.batchOpen)throw Error('请使用桌面版打开本地文件；也可复制显示的实际路径');const result=await window.nbtDesktop.batchOpen({id:task.id,kind,item_id,mode});report((result.action==='reveal'?'已定位：':'已打开：')+result.path)}
 async function view(task,item,editing){
  await api('batches/locate',{id:task.id,kind:'model',item_id:item.id})
  const model=getModels().find(model=>key(model.source)===key(item.absolute_source))||{source:item.absolute_source,name_zh:item.name,object_name:item.name,size:item.size,geometry_sha256:item.geometry_sha256,relative_path:item.source,unverified:true}
  if(editing)dialog.close();const result=await (editing?openModel(model):previewModel(model));if(result!==false)await seen(model.source)
 }
 async function seen(source){const matches=links.get(key(source))||[];for(const {task,item} of matches)if(item.is_new)await api('batches/ack',{id:task.id,model_ids:[item.id]});if(matches.length)await refresh()}
 async function open(source){if(!dialog.open)dialog.showModal();await refresh();if(source){const match=links.get(key(source))?.[0];if(match){selected=match.task.id;selectedCandidate='';draw()}}}
 launch.onclick=safe(()=>open());$('batch-workspaces-close').onclick=()=>dialog.close();$('batch-workspaces-refresh').onclick=safe(refresh)
 $('batch-workspaces-create').onsubmit=event=>{event.preventDefault();safe(async()=>{const result=await api('batches/create',{name:$('batch-workspaces-name').value});selected=result.id;selectedCandidate='';$('batch-workspaces-name').value='';await refresh();report('已创建批次。Agent 使用 batches record 将正式模型与图册登记到此批次。')})()}
 window.addEventListener('creator-workspace-change',event=>{if(event.detail==='project')refresh().catch(error=>{launch.title=error.message});else if(dialog.open)dialog.close()})
 return {update(workspace){if(root===workspace&&loaded)return;root=workspace;tasks=[];links.clear();selected='';selectedCandidate='';loaded=false;refresh().catch(error=>{launch.title=error.message})},refresh,seen,decorate(card,item){const matches=links.get(key(item.source));if(!matches?.length)return;const fresh=matches.some(({item})=>item.is_new);card.classList.toggle('batch-item-new',fresh);const link=button(fresh?'批次 · 新增':'批次',()=>open(item.source));link.className='project-card-batch';link.title=matches.map(({task})=>task.name).join('、');card.append(link)},previewLink(source){const matches=links.get(key(source));return matches?.length?button('查看制作批次',()=>open(source)):null}}
}
