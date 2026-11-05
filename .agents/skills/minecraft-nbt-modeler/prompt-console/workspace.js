/* Architect-facing prompt queue. Generation, review and external handoff are
   separate actions; every item keeps its own archived document and session. */
(() => {
 globalThis.createPromptWorkspace=function(hooks){
  const $=id=>document.getElementById(id),C=NbtPrompt,items=[];let active=null,loading=true,working=false,silent=false,cancelled=false,batchRunning=false,pristine=true
  const signature=doc=>JSON.stringify([doc.project,doc.operations,doc.aiDraft,doc.proposal_draft,doc.workbench?.instruction])
  const phase=item=>item.task?'published':item.document?.workbench?.status==='reviewed'||!item.document&&item.review_state==='reviewed'?'reviewed':item.document?.proposal_draft?'pending':item.document?.workbench?.generated===false||!item.document&&item.generation_state===false?'waiting':'pending'
  const labels={published:'已交接 · 等待外部助手读取',reviewed:'已审查 · 可以交接',pending:'待审查 · 修改后自动保存',waiting:'待编写'}
  function showOutput(open){document.body.classList.toggle('output-open',open);$('prompt-output-toggle').setAttribute('aria-expanded',String(open));$('prompt-output-toggle').textContent=open?'返回编辑提示词':'查看完整提示词'}
  $('prompt-output-toggle').onclick=()=>showOutput(!document.body.classList.contains('output-open'));$('prompt-output-close').onclick=()=>showOutput(false)
  function render(){
   document.querySelector('.editor').inert=working;document.querySelector('.output').inert=working
   $('prompt-queue-count').textContent=items.length+' 条';const reviewed=items.filter(i=>phase(i)==='reviewed').length,published=items.filter(i=>phase(i)==='published').length
   $('prompt-queue-progress').textContent=`${items.length} 条提示词 · ${reviewed} 条已审查 · ${published} 条已交接`
   $('prompt-publish-reviewed').disabled=loading||working||!reviewed||!hooks.bridge?.publish
   for(const id of ['prompt-add','prompt-batch-open','prompt-next','prompt-review'])$(id).disabled=loading||working||hooks.isGenerating()
   if(batchRunning)$('prompt-batch-open').disabled=false
   const list=$('prompt-queue-list');list.replaceChildren()
   items.forEach((item,index)=>{const b=document.createElement('button');b.type='button';b.dataset.promptId=item.id;b.disabled=loading||working||hooks.isGenerating();b.setAttribute('role','listitem');b.setAttribute('aria-current',String(item===active));const h=document.createElement('strong'),s=document.createElement('small');h.textContent=String(index+1).padStart(2,'0')+'  '+(item.document?.project.name??item.name??'未命名建筑');s.textContent=labels[phase(item)];b.append(h,s);b.onclick=()=>guard(()=>select(item));list.append(b)})
   if(active){$('prompt-document-number').textContent=`第 ${items.indexOf(active)+1} / ${items.length} 条提示词`;$('prompt-document-title').textContent=active.document?.project.name??active.name??'编写建筑要求';$('prompt-review-state').textContent=labels[phase(active)].split(' · ')[0];$('prompt-review-state').dataset.state=phase(active)}
  }
  function edited(doc){
   if(silent||loading)return
   const initial=C.defaults();initial.project.output=C.outputPath(initial.project)
   if(!active&&!items.length&&!doc.workbench&&signature(doc)===signature(initial))return
   pristine=false
   if(!doc.export_id)doc.export_id=crypto.randomUUID().replaceAll('-','')
   if(!active||active.id!==doc.export_id){active=items.find(i=>i.id===doc.export_id);if(!active){active={id:doc.export_id};items.push(active)}}
   if(active.document&&signature(doc)!==signature(active.document)){doc.workbench={...doc.workbench,status:'pending'};active.task=null;active.review_state='pending'}
   active.name=doc.project.name;active.document=C.clone(doc);render()
  }
  function saved(result){if(!result)return;const item=items.find(i=>i.id===result.id);if(item){if((item.saved?.revision??item.revision)!==result.revision)item.task=null;item.saved=result;item.index=result.index;item.revision=result.revision} $('prompt-editor-save-state').textContent='已自动保存';render()}
  function published(task){if(active){active.task=task;render()}}
  async function materialize(item){if(item.document)return item.document;if(!hooks.bridge?.library)throw Error('无法读取已保存的提示词');const loaded=await hooks.bridge.library({action:'read',index:item.index,id:item.id});item.document=C.normalize(loaded.document);item.document.export_id=item.id;hooks.remember(item.id,loaded,item.document);return item.document}
  async function select(item,{skipFlush=false,tab}={}){
   if(!skipFlush)await hooks.flush()
   const doc=await materialize(item);silent=true
   try{active=item;hooks.replace(C.clone(doc));hooks.instruction(doc.workbench?.instruction??'');hooks.restoreTask(item.task);showOutput(false);const target=tab??(doc.workbench?.generated||doc.workbench?.status==='reviewed'?'project':'ai');document.querySelector(`[data-tab=${target}]`).click();document.querySelector('.tab:not([hidden])').scrollTop=0}finally{silent=false;render()}
  }
  async function guard(fn){if(loading||working||hooks.isGenerating())return;working=true;render();try{return await fn()}catch(error){hooks.message(error.message,true)}finally{working=false;document.body.classList.remove('prompt-processing');render()}}
  async function appendDocument(doc,instruction=''){
   doc.export_id=crypto.randomUUID().replaceAll('-','');doc.workbench={status:'pending',generated:false,instruction,created_at:Date.now()};const item={id:doc.export_id,name:doc.project.name,document:doc};items.push(item);await select(item,{skipFlush:true,tab:'ai'});hooks.update();await hooks.flush();return item
  }
  async function addBlank(){return guard(async()=>{await hooks.flush();return appendDocument(C.defaults())})}
  async function confirmCurrent(){
   if(!hooks.valid())throw Error('请先填写完整的建筑要求，再确认这条提示词')
   const doc=hooks.document();if(doc.proposal_draft)throw Error('请先采用或修改 AI 写好的设计要求，再确认提示词')
   // Update the cached document first so marking review does not look like an edit.
   doc.workbench={...doc.workbench,status:'reviewed'};if(active)active.document=C.clone(doc);hooks.update();await hooks.flush();render()
  }
  $('prompt-review').onclick=()=>guard(async()=>{await confirmCurrent();hooks.message('这条提示词已审查。可以继续下一条，或交给建造助手。')})
  $('prompt-add').onclick=addBlank
  $('prompt-next').onclick=()=>guard(async()=>{
   await hooks.flush();const next=active&&phase(active)==='waiting'?active:items.slice(items.indexOf(active)+1).find(i=>phase(i)==='waiting')??items.find(i=>i!==active&&phase(i)==='waiting')
   if(!next){await appendDocument(C.defaults());hooks.message('已新增下一条提示词。描述这座建筑，再点击“生成这条提示词”。');return}
   await select(next,{skipFlush:true,tab:'ai'});await hooks.generate();hooks.update();await hooks.flush();hooks.message('下一条提示词已生成，请逐项审查修改。')
  })
  $('prompt-batch-open').onclick=()=>{if(loading||working||hooks.isGenerating())return;$('prompt-batch-status').textContent='';$('prompt-batch-dialog').showModal()}
  function batchItems(){const lines=$('prompt-batch-items').value.split(/\r?\n/).map(s=>s.trim()).filter(Boolean);if(!lines.length||lines.length>20)throw Error('请填写 1～20 座建筑，每行一座');const common=$('prompt-batch-common').value.trim();return lines.map(line=>{const [name,...rest]=line.split(/[|｜]/);if(!name.trim()||name.trim().length>70)throw Error('每座建筑的名称请控制在 1～70 字');const instruction=[common,'建筑名称：'+name.trim(),rest.join('；')||line].filter(Boolean).join('\n');if(instruction.length>4000)throw Error('共同要求与单座建筑要求合计请控制在 4000 字以内');return {name:name.trim(),instruction}})}
  async function addBatch(generate){
   let requested;try{requested=batchItems()}catch(error){$('prompt-batch-status').textContent=error.message;return}
   return guard(async()=>{
    await hooks.flush();$('prompt-batch-dialog').close();const added=[];cancelled=false
    for(const request of requested){const doc=C.defaults();doc.project.name=request.name;added.push(await appendDocument(doc,request.instruction))}
    if(!generate){await select(added[0],{skipFlush:true,tab:'ai'});hooks.message(`已添加 ${added.length} 座建筑。点击“生成下一条”依次编写。`);return}
    batchRunning=true;document.body.classList.add('prompt-processing');$('prompt-batch-open').textContent='停止批量生成';$('prompt-batch-open').disabled=false;$('prompt-batch-open').onclick=()=>{cancelled=true;hooks.cancel();$('prompt-batch-open').textContent='正在停止…'}
    let completed=0,failure=''
    try{for(const item of added){if(cancelled)break;await select(item,{skipFlush:true,tab:'ai'});$('prompt-queue-progress').textContent=`正在生成 ${completed+1} / ${added.length}：${item.name}`;try{await hooks.generate();hooks.update();await hooks.flush();completed++}catch(error){failure=error.message;break}}}
    finally{batchRunning=false;$('prompt-batch-open').textContent='批量编写';$('prompt-batch-open').onclick=()=>{$('prompt-batch-status').textContent='';$('prompt-batch-dialog').showModal()};document.body.classList.remove('prompt-processing')}
    const first=added.find(i=>i.document.workbench?.generated)??added[0];await select(first,{tab:first.document.workbench?.generated?'project':'ai'});hooks.message(`已生成 ${completed} / ${added.length} 条，草稿分别保存，请逐条审查。${failure?'生成已停止：'+failure:cancelled?'已停止，其余建筑仍在列表中。':''}`,!!failure)
   })
  }
  $('prompt-batch-add').onclick=()=>addBatch(false);$('prompt-batch-generate').onclick=()=>addBatch(true)
  $('prompt-publish-reviewed').onclick=()=>guard(async()=>{
   await hooks.flush();let count=0;for(const item of items.filter(i=>phase(i)==='reviewed')){await materialize(item);const saved=await hooks.saveDocument(item.document);item.saved=saved;item.index=saved.index;item.revision=saved.revision;item.task=await hooks.bridge.publish({index:saved.index,id:saved.id,revision:saved.revision});count++;render()}
   hooks.restoreTask(active?.task);hooks.message(`已交接 ${count} 条提示词。请手动让外部建造助手调用 Skill 读取新增任务。`);showOutput(true)
  })
  async function load(){
   try{
    if(hooks.bridge?.library){const result=await hooks.bridge.library({action:'list'});result.items.sort((a,b)=>(a.queue_created_at??Date.parse(a.updated_at))-(b.queue_created_at??Date.parse(b.updated_at)));for(const item of result.items)items.push({...item,task:item.published_task});if(items.length)await select(items[0],{skipFlush:true});else{silent=true;try{hooks.replace(C.defaults());hooks.instruction('')}finally{silent=false}}}
   }catch(error){hooks.message('提示词列表读取失败：'+error.message,true);throw error}
   finally{loading=false;document.body.dataset.promptReady='true';hooks.update();render()}
  }
  return {load,edited,saved,published,confirmCurrent,addBlank,showOutput,exclusive:guard,refresh:render,get busy(){return working||loading},get loading(){return loading},get pristine(){return pristine}}
 }
})();
