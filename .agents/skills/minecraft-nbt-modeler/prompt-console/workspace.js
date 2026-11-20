/* Architect-facing prompt queue. Generation, review and external handoff are
   separate actions; every item keeps its own archived document and session. */
(() => {
 globalThis.createPromptWorkspace=function(hooks){
  const $=id=>document.getElementById(id),C=NbtPrompt,items=[];let active=null,loading=true,working=false,silent=false,cancelled=false,batchRunning=false,pristine=true,queueScope='active'
  const scopes=['active','published','trash'],chosen=new Set()
  let multi=false,groupScope='',management=null,primaryAction=''
  const titleOf=item=>item.document?.project.name??item.name??'未命名建筑'
  const live=()=>items.filter(item=>!item.deleted_at)
  const awaitingAgent=item=>item.task?.status==='pending'
  const scopeItems=()=>items.filter(item=>queueScope==='trash'?item.deleted_at:
   !item.deleted_at&&(queueScope==='published'?awaitingAgent(item):!item.task))
  const matching=available=>available.filter(item=>!groupScope||item.group===groupScope)
  const signature=doc=>JSON.stringify([doc.project,doc.operations,doc.aiDraft,doc.proposal_draft,doc.workbench?.instruction,doc.user_requirements,doc.design_standard,doc.design_override,doc.constraints])
  const phase=item=>item.task?'published':item.document?.workbench?.status==='reviewed'||!item.document&&item.review_state==='reviewed'?'reviewed':item.document?.proposal_draft?'pending':item.document?.workbench?.generated===false||!item.document&&item.generation_state===false?'waiting':'pending'
  const labels={published:'已交接 · 等待外部助手读取',reviewed:'已审查 · 可以交接',pending:'待审查 · 修改后自动保存',waiting:'待编写'}
  function syncNavigation(){
   const step=document.body.classList.contains('output-open')?'handoff':!$('ai').hidden?'write':'review'
   for(const button of document.querySelectorAll('[data-planning-step]')){button.disabled=working||loading||hooks.isGenerating()||queueScope==='trash';if(button.dataset.planningStep===step)button.setAttribute('aria-current','step');else button.removeAttribute('aria-current')}
   const tab=document.querySelector('.tab:not([hidden])'),hint=$('planning-next');if(tab&&hint.parentElement!==tab)tab.prepend(hint)
   let command=['prompt-batch-open','批量编写']
   if(batchRunning)command=['prompt-batch-open','停止生成']
   else if(hooks.isGenerating())command=['prompt-ai-cancel','停止生成']
   else if(active&&awaitingAgent(active)&&step==='handoff')command=['prompt-task-copy','复制读取命令']
   else if(!active&&step==='write')command=['prompt-batch-open','批量编写']
   else if(step==='review')command=active?.task?['prompt-output-toggle','查看交接结果']:['left-save','确认并交接']
   else if(step==='handoff')command=['copy','复制完整提示词']
   else if(!$('prompt-ai-apply').disabled)command=['prompt-ai-apply','采用并审查']
   else command=['prompt-ai-generate','生成提示词']
   primaryAction=command[0]
   const primary=$('prompt-primary')
   primary.textContent=command[1];primary.hidden=queueScope==='trash'||Boolean(active?.task&&!awaitingAgent(active))
   primary.disabled=$(primaryAction).disabled||loading||working&&!batchRunning&&!hooks.isGenerating()||batchRunning&&cancelled
   $('prompt-batch-open').hidden=primaryAction==='prompt-batch-open'
   $('prompt-output-toggle').hidden=primaryAction==='prompt-output-toggle'||queueScope==='trash'
   $('copy').hidden=step!=='handoff'||primaryAction==='copy'
   for(const id of ['markdown','plan','config'])$(id).hidden=step!=='handoff'
   $('prompt-ai-references').hidden=step!=='write'
   $('prompt-next').hidden=!active||step==='handoff'
   $('prompt-delete').hidden=!active||multi
   $('prompt-review').hidden=step!=='review'||!active||!!active.task
   if($('prompt-batch-retry'))$('prompt-batch-retry').hidden=!live().some(item=>phase(item)==='waiting')
  }
  $('prompt-primary').onclick=()=>$(primaryAction)?.click()
  function showOutput(open){document.body.classList.toggle('output-open',open);$('prompt-output-toggle').setAttribute('aria-expanded',String(open));$('prompt-output-toggle').textContent=open?'返回编辑提示词':'查看完整提示词';syncNavigation()}
  for(const button of document.querySelectorAll('[data-tab]'))button.addEventListener('click',()=>queueMicrotask(syncNavigation))
  $('prompt-output-toggle').onclick=()=>showOutput(!document.body.classList.contains('output-open'));$('prompt-output-close').onclick=()=>showOutput(false)
  function showQueue(open){document.body.classList.toggle('queue-open',open);$('prompt-queue-toggle').setAttribute('aria-expanded',String(open))}
  $('prompt-queue-toggle').onclick=()=>showQueue(!document.body.classList.contains('queue-open'))
  $('prompt-queue-list').addEventListener('click',event=>{if(!multi&&queueScope!=='trash'&&event.target.closest('[data-prompt-id]'))showQueue(false)})
  for(const scope of scopes)$('prompt-scope-'+scope).onclick=()=>guard(async()=>{
   if(scope===queueScope)return
   if(active)await hooks.flush()
   queueScope=scope;groupScope='';multi=false;chosen.clear()
   const first=scope==='trash'?null:scopeItems()[0]
   if(first)await select(first,{skipFlush:true});else clearDocument()
  })
  document.addEventListener('keydown',event=>{
   if(event.key!=='Escape')return
   if($('prompt-more').open){$('prompt-more').open=false;$('prompt-more').querySelector('summary').focus()}
   else if(document.body.classList.contains('queue-open')){showQueue(false);$('prompt-queue-toggle').focus()}
  })
  document.addEventListener('pointerdown',event=>{if(!event.target.closest('#prompt-more'))$('prompt-more').open=false})
  $('prompt-more').addEventListener('click',event=>{if(event.target.closest('button'))$('prompt-more').open=false})
  $('prompt-write-manually').onclick=()=>{document.querySelector('[data-tab=project]').click();$('project-fields').querySelector('input,textarea,select')?.focus()}
  for(const button of document.querySelectorAll('[data-planning-step]'))button.onclick=()=>{
   const step=button.dataset.planningStep
   if(step==='handoff')showOutput(true)
   else{showOutput(false);document.querySelector('[data-tab='+ (step==='write'?'ai':'project') +']').click()}
  }
  function render(){
   document.querySelector('.editor').inert=working||loading;document.querySelector('.output').inert=working||loading
   for(const id of ['prompt-ai-mode','prompt-ai-instruction','prompt-user-requirements','prompt-ai-generate'])$(id).disabled=loading||working||hooks.isGenerating()
   const available=scopeItems(),groups=[...new Set(available.map(item=>item.group).filter(Boolean))].sort((a,b)=>a.localeCompare(b,'zh-CN'))
   if(groupScope&&!groups.includes(groupScope))groupScope=''
   const groupFilter=$('prompt-group-filter')
   groupFilter.replaceChildren(new Option('全部分组',''),...groups.map(name=>new Option(name,name)));groupFilter.value=groupScope;groupFilter.hidden=!groups.length||queueScope==='trash'
   const visible=matching(available)
   $('prompt-queue-count').textContent=visible.length+' 条';const reviewed=live().filter(i=>phase(i)==='reviewed').length,published=live().filter(awaitingAgent).length
   for(const scope of scopes){$('prompt-scope-'+scope).setAttribute('aria-pressed',String(queueScope===scope));$('prompt-scope-'+scope).disabled=loading||working||hooks.isGenerating()}
   $('prompt-scope-published').textContent=`待领取 ${published}`
   $('prompt-queue-progress').textContent=''
   $('prompt-publish-reviewed').disabled=loading||working||!reviewed||!hooks.bridge?.publish
   $('prompt-publish-reviewed').hidden=multi||queueScope!=='active'
   for(const id of ['prompt-add','prompt-batch-open','prompt-next','prompt-review'])$(id).disabled=loading||working||hooks.isGenerating()
   if(batchRunning)$('prompt-batch-open').disabled=false
   $('prompt-delete').disabled=loading||working||hooks.isGenerating()||!active
   $('prompt-review').disabled||=!active||phase(active)==='published'||!hooks.valid()
   $('left-save').disabled=loading||working||hooks.isGenerating()||!active||!!active.document?.proposal_draft||!hooks.valid()
   $('left-save').textContent=active&&phase(active)==='published'?'已交接 · 查看任务':'确认并交接'
   if($('prompt-batch-retry'))$('prompt-batch-retry').disabled=loading||working||hooks.isGenerating()||!live().some(item=>phase(item)==='waiting')
   $('prompt-list-select').setAttribute('aria-pressed',String(multi))
   $('prompt-list-select').disabled=loading||working||hooks.isGenerating()||!available.length
   $('prompt-selection-bar').hidden=!multi
   $('prompt-selection-count').textContent=`已选 ${chosen.size} 项`
   $('prompt-selection-all').disabled=loading||working||hooks.isGenerating()||!visible.some(item=>!chosen.has(item.id))
   $('prompt-selection-group').hidden=queueScope==='trash'
   $('prompt-selection-recycle').textContent=queueScope==='trash'?'恢复':'移入回收站'
   for(const id of ['prompt-selection-group','prompt-selection-recycle'])$(id).disabled=working||hooks.isGenerating()||!chosen.size
   $('prompt-selection-done').disabled=working
   document.body.classList.toggle('prompt-trash-open',queueScope==='trash')
   const currentPhase=active?phase(active):'waiting';syncNavigation()
   $('planning-next').textContent=loading?'正在读取已保存的方案…':working?'正在保存或交接，请稍候…':currentPhase==='published'?'方案已交接。请在外部建造助手中读取任务；建筑完成后，回到建筑库刷新查看。':currentPhase==='reviewed'?'已标记审查完成。点击“确认并交接”发送当前要求；建筑仍需由外部助手制作。':currentPhase==='waiting'?'可以让 AI 起草，也可以直接手动填写要求。这里只编写方案。':'逐项核对用途、尺寸和空间要求。确认后再交接给建造助手。'
   const list=$('prompt-queue-list');list.replaceChildren()
   visible.forEach(item=>{
    const row=document.createElement('div');row.className='prompt-queue-row';row.setAttribute('role','listitem')
    const b=document.createElement('button');b.type='button';b.dataset.promptId=item.id;b.disabled=loading||working||hooks.isGenerating();b.setAttribute('aria-current',String(item===active))
    const h=document.createElement('strong'),s=document.createElement('small');h.textContent=titleOf(item)
    s.textContent=[item.failure?'未完成 · '+item.failure:labels[phase(item)].split(' · ')[0],item.group].filter(Boolean).join(' · ')
    b.append(h,s);b.onclick=()=>{if(multi||queueScope==='trash'){multi=true;toggle(item)}else guard(()=>select(item))}
    row.append(b)
    if(multi){const checkbox=document.createElement('input');checkbox.type='checkbox';checkbox.checked=chosen.has(item.id);checkbox.disabled=b.disabled;checkbox.setAttribute('aria-label','选择 '+titleOf(item));checkbox.onchange=()=>toggle(item,true);row.append(checkbox)}
    list.append(row)
   })
   if(!visible.length){const empty=document.createElement('p');empty.className='queue-empty';empty.textContent=queueScope==='trash'?'回收站为空':queueScope==='published'?'没有待领取任务':'没有待处理方案。可以批量编写新方案。';list.append(empty)}
   if(active){$('prompt-document-number').textContent=`第 ${Math.max(1,available.indexOf(active)+1)} / ${Math.max(1,available.length)} 条提示词`;$('prompt-document-title').textContent=titleOf(active);$('prompt-review-state').textContent=labels[phase(active)].split(' · ')[0];$('prompt-review-state').dataset.state=phase(active)}
   else{$('prompt-document-number').textContent='当前提示词';$('prompt-document-title').textContent='编写建筑要求';$('prompt-review-state').textContent='待编写';$('prompt-review-state').dataset.state='waiting'}
  }
  function edited(doc){
   if(silent||loading||queueScope==='trash')return
   const initial=C.defaults();initial.project.output=C.outputPath(initial.project);initial.design_standard=doc.design_standard;initial.design_override=doc.design_override
   if(!active&&signature(doc)===signature(initial)&&JSON.stringify(doc.workbench)===JSON.stringify(initial.workbench))return
   pristine=false
   if(!doc.export_id)doc.export_id=crypto.randomUUID().replaceAll('-','')
   if(!active||active.id!==doc.export_id){active=items.find(i=>i.id===doc.export_id);if(!active){hooks.prepareDraft?.(doc);active={id:doc.export_id};items.push(active)}}
   if(!active.document||signature(doc)!==signature(active.document)){
    $('prompt-editor-save-state').textContent='等待自动保存'
    if(active.document){doc.workbench={...doc.workbench,status:'pending'};active.task=null;active.review_state='pending';delete active.failure;if(queueScope==='published')queueScope='active'}
   }
   active.name=doc.project.name;active.document=C.clone(doc);render()
  }
  function saved(result){if(!result)return;const item=items.find(i=>i.id===result.id);if(item){if((item.saved?.revision??item.revision)!==result.revision)item.task=null;item.saved=result;Object.assign(item,{index:result.index,revision:result.revision,updated_at:result.updated_at})} $('prompt-editor-save-state').textContent='已自动保存';render()}
  function published(task){
   if(!active)return
   active.task=task;queueScope='published'
   hooks.restoreTask(task)
   if(awaitingAgent(active))showOutput(true)
   else clearDocument()
   render()
  }
  let checkingHandoffs=false
  async function refreshHandoffs(){
   if(checkingHandoffs||loading||working||hooks.isGenerating()||!hooks.bridge?.library||
     !live().some(item=>item.task&&item.task.status!=='completed')||
     window.frameElement&&!window.frameElement.getClientRects().length)return
   checkingHandoffs=true
   // A save or publish started during this request can replace the task object.
   const tracked=live().filter(item=>item.task).map(item=>[item,item.task])
   try{
    const {statuses}=await hooks.bridge.library({action:'task-statuses'})
    if(working||hooks.isGenerating())return
    let changed=false
    for(const [item,task] of tracked){
     const status=statuses[task.id]
     if(item.task!==task||!status||task.status===status)continue
     task.status=status
     if(!awaitingAgent(item))chosen.delete(item.id)
     changed=true
    }
    if(!changed)return
    if(active?.task&&!awaitingAgent(active))clearDocument()
    render()
   }catch{
    // Keep the last confirmed state during temporary backend unavailability.
   }finally{checkingHandoffs=false}
  }
  window.addEventListener('focus',refreshHandoffs)
  if(hooks.bridge?.library)setInterval(refreshHandoffs,4000)
  async function materialize(item){if(item.document)return item.document;if(!hooks.bridge?.library)throw Error('无法读取已保存的提示词');const loaded=await hooks.bridge.library({action:'read',index:item.index,id:item.id});item.document=C.normalize(loaded.document);item.document.export_id=item.id;hooks.remember(item.id,loaded,item.document);return item.document}
  async function select(item,{skipFlush=false,tab}={}){
   if(!skipFlush)await hooks.flush()
   const doc=await materialize(item);silent=true
   try{active=item;pristine=false;hooks.replace(C.clone(doc));hooks.instruction(doc.workbench?.instruction??'');hooks.restoreTask(item.task);showOutput(!!item.task);const target=tab??(doc.proposal_draft?'ai':doc.workbench?.generated||doc.workbench?.status==='reviewed'?'project':'ai');document.querySelector(`[data-tab=${target}]`).click();document.querySelector('.tab:not([hidden])').scrollTop=0}finally{silent=false;render()}
  }
  async function guard(fn){if(loading||working||hooks.isGenerating())return;working=true;render();try{return await fn()}catch(error){hooks.message(error.message,true)}finally{working=false;document.body.classList.remove('prompt-processing');render()}}
  async function appendDocument(doc,instruction='',standard){
   queueScope='active';groupScope=''
   hooks.prepareDraft?.(doc)
   standard??=await hooks.bridge?.standards?.();if(standard?.revision)doc.design_standard=C.clone(standard)
   doc.export_id=crypto.randomUUID().replaceAll('-','');doc.workbench={...doc.workbench,status:'pending',generated:false,instruction,created_at:Date.now()};const item={id:doc.export_id,name:doc.project.name,document:doc};items.push(item);await select(item,{skipFlush:true,tab:'ai'});hooks.update();await hooks.flush();return item
  }
  async function addBlank(){const item=await guard(async()=>{await hooks.flush();return appendDocument(C.defaults())});if(item)hooks.newDocument?.();return item}
  async function confirmCurrent(){
   if(!hooks.valid())throw Error('请先填写完整的建筑要求，再确认这条提示词')
   const doc=hooks.document();if(doc.proposal_draft)throw Error('请先采用、重新生成或放弃 AI 候选，再确认提示词')
   // Update the cached document first so marking review does not look like an edit.
   doc.workbench={...doc.workbench,status:'reviewed'};if(active){delete active.failure;active.document=C.clone(doc);}hooks.update();await hooks.flush();render()
  }
  function clearDocument(){
   active=null;pristine=true;hooks.restoreTask(null);showOutput(false);silent=true
   try{hooks.replace(C.defaults());hooks.instruction('');document.querySelector('[data-tab=ai]').click()}finally{silent=false}
  }
  function toggle(item,checkbox=false){
   if(chosen.has(item.id))chosen.delete(item.id);else chosen.add(item.id)
   render()
   const button=[...$('prompt-queue-list').querySelectorAll('[data-prompt-id]')].find(row=>row.dataset.promptId===item.id)
   if(button)(checkbox?button.nextElementSibling:button)?.focus()
  }
  function setMulti(value){multi=value;if(!multi)chosen.clear();render()}
  $('prompt-list-select').onclick=()=>setMulti(!multi)
  $('prompt-selection-all').onclick=()=>{for(const item of matching(scopeItems()))chosen.add(item.id);render()}
  $('prompt-selection-done').onclick=()=>{setMulti(false);$('prompt-list-select').focus()}
  $('prompt-group-filter').onchange=event=>{groupScope=event.target.value;render()}
  function manage(action,list){
   if(loading||working||hooks.isGenerating()||!list.length)return
   management={action,list}
   $('prompt-delete-title').textContent=`${{trash:'移入回收站',restore:'恢复',group:'移到分组'}[action]} ${list.length} 条方案？`
   $('prompt-delete-name').replaceChildren(...list.map(item=>{const name=document.createElement('li');name.textContent=titleOf(item);return name}))
   $('prompt-manage-group-label').hidden=action!=='group';$('prompt-manage-group').value=''
   $('prompt-group-names').replaceChildren(...[...new Set(items.map(item=>item.group).filter(Boolean))].map(group=>new Option(group,group)))
   $('prompt-delete-confirm').textContent=action==='trash'?'移入回收站':action==='restore'?'恢复':'移动'
   $('prompt-delete-dialog').showModal()
  }
  const selections=()=>items.filter(item=>chosen.has(item.id))
  $('prompt-selection-group').onclick=()=>manage('group',selections())
  $('prompt-selection-recycle').onclick=()=>manage(queueScope==='trash'?'restore':'trash',selections())
  $('prompt-review').onclick=()=>guard(async()=>{await confirmCurrent();hooks.message('已标记审查完成。')})
  $('prompt-delete').onclick=()=>{if(active)manage('trash',[active])}
  $('prompt-delete-cancel').onclick=()=>$('prompt-delete-dialog').close()
  $('prompt-delete-confirm').onclick=()=>guard(async()=>{
   $('prompt-delete-dialog').close()
   const {action,list}=management;management=null
   if(active&&hooks.valid())await hooks.flush()
   else if(action==='trash'&&list.includes(active))await hooks.discard()
   if(!hooks.bridge?.library)throw Error('方案整理需要工作区桌面版')
   const group=$('prompt-manage-group').value.trim()
   const failed=[],byId=new Map(list.map(item=>[item.id,item]))
   for(let start=0;start<list.length;start+=100){
    const batch=list.slice(start,start+100)
    try{
     const result=await hooks.bridge.library({action,group,items:batch.map(({id,index,revision,updated_at})=>({id,index,revision,updated_at}))})
     for(const entry of result.items){
      const item=byId.get(entry.id);if(!item)continue
      if(entry.status!=='complete'){failed.push(titleOf(item)+'：'+entry.error);continue}
      chosen.delete(item.id)
      if(action==='trash')item.deleted_at=new Date().toISOString()
      else if(action==='restore')delete item.deleted_at
      else item.group=group
     }
    }catch(error){failed.push(...list.slice(start).map(item=>titleOf(item)+'：'+error.message));break}
   }
   if(active?.deleted_at){await hooks.discard();const next=scopeItems()[0];if(next)await select(next,{skipFlush:true});else clearDocument()}
   $('prompt-selection-status').textContent=`已处理 ${list.length-failed.length} 条方案`+(failed.length?'。'+failed.join('。'):'')
  })
  $('prompt-add').onclick=addBlank
  $('prompt-next').onclick=()=>guard(async()=>{
   await hooks.flush();const next=active&&phase(active)==='waiting'?active:live().find(i=>i!==active&&phase(i)==='waiting')
   if(!next){await appendDocument(C.defaults());hooks.message('已新增下一条提示词。描述这座建筑，再点击“生成这条提示词”。');return}
   await select(next,{skipFlush:true,tab:'ai'});await hooks.generate();hooks.update();await hooks.flush();hooks.message('下一条建议已生成，请逐项审查并采用。')
  })
  const retry=document.createElement('button');retry.id='prompt-batch-retry';retry.type='button';retry.textContent='重试未完成项';$('prompt-batch-open').after(retry);retry.onclick=()=>guard(async()=>{await hooks.flush();await runBatch(live().filter(item=>phase(item)==='waiting'))});
  $('prompt-batch-open').onclick=()=>{if(loading||working||hooks.isGenerating())return;$('prompt-batch-status').textContent='';$('prompt-batch-dialog').showModal()}
  function batchItems(){const lines=$('prompt-batch-items').value.split(/\r?\n/).filter(line=>line.trim());if(!lines.length||lines.length>20)throw Error('请填写 1～20 座建筑，每行一座');const common=$('prompt-batch-common').value;return lines.map(line=>{const separator=line.search(/[|｜]/),name=(separator<0?line:line.slice(0,separator)).trim(),specific=separator<0?'':line.slice(separator+1);if(!name||name.length>70)throw Error('每座建筑的名称请控制在 1～70 字');const requirements=[common,specific].filter(value=>value.trim()).join('\n');if(requirements.length>4000)throw Error('共同要求与单座建筑要求合计请控制在 4000 字以内');return {name,requirements}})}
  async function addBatch(generate){
   let requested;try{requested=batchItems()}catch(error){$('prompt-batch-status').textContent=error.message;return}
   return guard(async()=>{
    await hooks.flush();$('prompt-batch-dialog').close();const added=[],standard=await hooks.bridge?.standards?.();cancelled=false
    const template=C.clone(hooks.document()),inherit=$('prompt-batch-inherit').checked;
    for(const request of requested){
     const doc=C.defaults();
     if(inherit){doc.constraints=C.clone(template.constraints??[]);if(C.buildingShapes[template.project.buildingShape])C.applyShape(doc.project,template.project.buildingShape);for(const key of [...Object.keys(C.designContract.fields),'size_policy'])if(key!=='name'&&template.project[key]!==undefined)doc.project[key]=C.clone(template.project[key]);doc.workbench.brief_fields=C.clone(template.workbench?.brief_fields??C.designContract.default_editable_fields);}
     doc.project.name=request.name;doc.project.output=C.outputPath(doc.project);if(request.requirements)doc.user_requirements=request.requirements;added.push(await appendDocument(doc,'',standard));
    }
    if(!generate){await select(added[0],{skipFlush:true,tab:'ai'});hooks.message(`已添加 ${added.length} 座建筑。点击“生成下一条”依次编写。`);return}
    await runBatch(added)
   })
  }
  async function runBatch(added){
   if(!added.length)return
   const limit=Math.max(1,Math.min(4,await hooks.concurrency()));cancelled=false;batchRunning=true;const running=new Set();let completed=0,cursor=0,failed=0
   document.body.classList.add('prompt-processing');$('prompt-batch-open').textContent='停止批量生成';$('prompt-batch-open').disabled=false
   $('prompt-batch-open').onclick=()=>{cancelled=true;for(const id of running)hooks.cancelDocument(id);$('prompt-primary').textContent='正在停止…';$('prompt-primary').disabled=true}
   syncNavigation()
   async function worker(){while(!cancelled&&cursor<added.length){const item=added[cursor++];await materialize(item);const snapshot=C.clone(item.document),before=JSON.stringify(snapshot);running.add(item.id);delete item.failure
     try{const generated=await hooks.generateDocument(snapshot,()=>cancelled);if(cancelled)break;if(JSON.stringify(item.document)!==before)throw Error('此条要求已改变，请重新生成');const result=await hooks.saveDocument(generated);item.document=generated;saved(result);completed++}
     catch(error){item.failure=cancelled?'已停止，可重试':error.message;failed++}
     finally{running.delete(item.id);render();$('prompt-queue-progress').textContent=`已生成 ${completed} / ${added.length} · 正在编写 ${running.size} 条${failed?' · 未完成 '+failed+' 条':''}`}
   }}
   try{await Promise.all(Array.from({length:Math.min(limit,added.length)},worker))}
   finally{batchRunning=false;$('prompt-batch-open').textContent='批量编写';$('prompt-batch-open').onclick=()=>{$('prompt-batch-status').textContent='';$('prompt-batch-dialog').showModal()};document.body.classList.remove('prompt-processing')}
   const first=added.find(item=>item.document.workbench?.generated)??added[0];await select(first,{skipFlush:true,tab:'ai'})
   hooks.message(`已生成 ${completed} / ${added.length} 条，候选分别保存，请逐条审查并采用。${cancelled?'已停止，可重试未完成项。':failed?'部分未完成，请查看列表说明并重试。':''}`,failed>0&&!cancelled)
  }
  $('prompt-batch-add').onclick=()=>addBatch(false);$('prompt-batch-generate').onclick=()=>addBatch(true)
  $('prompt-publish-reviewed').onclick=()=>guard(async()=>{
   await hooks.flush();let count=0;for(const item of live().filter(i=>phase(i)==='reviewed')){await materialize(item);await hooks.registerDraftRoom?.(item.document);const saved=await hooks.saveDocument(item.document);item.saved=saved;item.index=saved.index;item.revision=saved.revision;item.updated_at=saved.updated_at;item.task=await hooks.bridge.publish({index:saved.index,id:saved.id,revision:saved.revision});count++;render()}
   if(active?.task)published(active.task)
   else queueScope='published'
   hooks.message(`已交接 ${count} 条提示词。请手动让外部建造助手调用 Skill 读取新增任务。`)
  })
  async function load(){
   try{
    if(hooks.bridge?.library){const result=await hooks.bridge.library({action:'list'});result.items.sort((a,b)=>(a.queue_created_at??Date.parse(a.updated_at))-(b.queue_created_at??Date.parse(b.updated_at)));for(const item of result.items)items.push({...item,task:item.published_task});const first=live().find(item=>phase(item)!=='published');if(first)await select(first,{skipFlush:true});else{silent=true;try{const doc=C.defaults(),standard=await hooks.bridge?.standards?.();if(standard?.revision)doc.design_standard=C.clone(standard);hooks.replace(doc);hooks.instruction('')}finally{silent=false}}}
   }catch(error){hooks.message('提示词列表读取失败：'+error.message,true);throw error}
   finally{loading=false;document.body.dataset.promptReady='true';hooks.update();render()}
  }
  render()
  return {load,edited,saved,published,confirmCurrent,addBlank,showOutput,exclusive:guard,refresh:render,get busy(){return working||loading},get loading(){return loading},get pristine(){return pristine},get acceptsAutosave(){return !silent&&!loading&&!!active&&!active.deleted_at&&queueScope!=='trash'}}
 }
})();
