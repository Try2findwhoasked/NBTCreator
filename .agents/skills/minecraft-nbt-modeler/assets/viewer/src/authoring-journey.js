import {authoringFlow} from './authoring-flow.mjs'
import './authoring-journey.css'

export function initAuthoringJourney({state,gather,showPanel,openModel}) {
 const $=id=>document.getElementById(id)
 const panel=document.createElement('section');panel.id='authoring-journey';panel.setAttribute('aria-label','当前编辑进度')
 panel.innerHTML='<div class="journey-heading"><strong id="journey-title"></strong></div><p id="journey-hint"></p>'
 $('studio-inspector-nav').before(panel)
 const action=document.createElement('button');action.id='journey-action';action.type='button';document.querySelector('.studio-primary-actions').append(action)
 const title=$('journey-title'),hint=$('journey-hint')
 title.setAttribute('role','status');title.setAttribute('aria-live','polite')
 const result=document.createElement('button');result.type='button';result.id='journey-result';result.textContent='查看保存结果';result.onclick=()=>window.creatorWorkspace.select('tasks');panel.append(result)
 const homes=new Map();for(const id of ['update-preview','validate-preview','save-authoring-version','export-revision']){const control=$(id),home=document.createComment(id+'-home');control.before(home);homes.set(id,home)}
 const receipts=new Map();let receipt=null,flow=null
 function sync(){
  const s=state();let current=false,settings='',parameterError=''
  try{settings=JSON.stringify(gather());current=!!s.preview&&s.previewSettings===settings}catch(error){parameterError=error.message}
  const invalid=$('settings').querySelector('input:invalid,select:invalid,textarea:invalid')
  if(invalid&&!parameterError){const name=invalid.getAttribute('aria-label')??[...invalid.closest('label')?.childNodes??[]].find(n=>n.nodeType===Node.TEXT_NODE&&n.textContent.trim())?.textContent.trim()??'参数';parameterError=invalid.validity.rangeUnderflow?name+'不能小于 '+invalid.min+'。':invalid.validity.rangeOverflow?name+'不能大于 '+invalid.max+'。':name+'需要填写有效数值，请核对允许范围与步长。'}
  // Saving advances the history head. Editing the old parent must not invite
  // another save, even after changing settings or returning from another page.
  receipt=receipts.get(s.info?.source)
  if(receipt?.sourceHash!==s.info?.source_sha256)receipt=null
  flow=authoringFlow(s,current,receipt)
  if(flow.action==='checks'&&$('studio-workspace').dataset.view==='inspect')flow={...flow,action:'tools',label:'返回调整参数'}
  if(s.info&&parameterError&&!s.busy&&!s.previewBusy&&!s.versionComparing&&!s.transforming)flow={...flow,canSave:false,action:null,tone:'warning',title:'参数需要调整',hint:parameterError}
  result.hidden=!receipt;result.disabled=!!(s.busy||s.previewBusy||s.commitBusy||s.sessionRestoring)
  panel.dataset.tone=flow.tone;panel.dataset.step=String(flow.step)
  if(title.textContent!==flow.title)title.textContent=flow.title
  hint.textContent=flow.hint
  action.hidden=!s.info||!flow.action||homes.has(flow.action);action.disabled=!flow.action;action.textContent=flow.label??'';action.classList.add('primary')
  for(const id of ['update-preview','validate-preview','save-authoring-version','export-revision']){
   const control=$(id),home=homes.get(id),primary=document.querySelector('.studio-primary-actions');control.classList.toggle('primary',flow.action===id)
   if(flow.action===id){if(control.parentNode!==primary)primary.prepend(control)}else if(control.previousSibling!==home)home.after(control)
   if(id==='save-authoring-version'||id==='export-revision'){
    control.disabled=!flow.canSave
    control.title=flow.canSave?(id==='save-authoring-version'?'另存 SNBT 制作版，继续编辑':'另存新版本，并生成可用于游戏的 NBT 文件'):flow.hint
    control.setAttribute('aria-describedby','journey-hint')
   }
  }
  $('studio-delivery-receipt').textContent=receipt?(receipt.draftOnly?'SNBT 制作版已保存：':'定稿 NBT 已导出：')+receipt.output:''
  if(flow.action&&$(flow.action))action.disabled=$(flow.action).disabled
 }
 action.onclick=async()=>{
  sync()
  if(flow.action==='open-saved'){
   try{await openModel({source:receipt.master})}catch(error){hint.textContent='新版本未能打开：'+error.message+'。可在运行记录中查看保存位置后重试。'}
  }
  else if(flow.action==='project'||flow.action==='tasks')window.creatorWorkspace.select(flow.action)
  else if(flow.action==='checks')showPanel('checks')
  else if(flow.action==='tools')showPanel('tools')
  else if(flow.action)$(flow.action)?.click()
 }
 window.addEventListener('creator-version-saved',event=>{receipts.set(event.detail.source,event.detail);sync()})
 window.addEventListener('creator-working-version-selected',event=>{receipts.delete(event.detail);sync()})
 window.addEventListener('creator-editor-state',sync)
 window.addEventListener('creator-workspace-change',sync)
 window.addEventListener('creator-studio-panel',sync)
 for(const event of ['input','change'])$('settings').addEventListener(event,()=>queueMicrotask(sync))
 sync()
}
