export function initWorkspaceShell(){
 const $=id=>document.getElementById(id),model=document.querySelector('.workspace'),actions=document.querySelector('.action-bar'),result=document.querySelector('.result-panel')
 const marker=document.createComment('runtime-panel-home');result.before(marker)
 let active='model',moving=false,returnFromAI='model'
 function select(name){
  if(moving||!['model','prompt','ai','tasks'].includes(name))return
  if(name==='ai'&&active!=='ai')returnFromAI=active==='prompt'?'prompt':'model'
  moving=true
  try{
   if(name!=='prompt'&&$('prompt-dialog').open)$('prompt-dialog').close()
   if(name!=='ai'&&$('api-dialog').open)$('api-dialog').close()
   if(name==='prompt'&&!$('prompt-dialog').open)$('open-prompt').click()
   if(name==='ai'&&!$('api-dialog').open)$('open-api').click()
   active=name;document.body.dataset.workspace=name
   model.inert=name==='prompt'||name==='ai'||name==='tasks';actions.inert=name==='prompt'||name==='ai'
   $('task-workspace').hidden=name!=='tasks'
   if(name==='tasks'){$('task-workspace-content').append(result)}else if(result.parentElement===$('task-workspace-content'))marker.after(result)
   document.querySelectorAll('button[data-workspace]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.workspace===name)))
   window.dispatchEvent(new CustomEvent('creator-workspace-change',{detail:name}))
  }finally{moving=false}
 }
 for(const button of document.querySelectorAll('button[data-workspace]'))button.onclick=()=>select(button.dataset.workspace)
 $('prompt-dialog').addEventListener('close',()=>{if(!moving&&active==='prompt')select('model')})
 $('api-dialog').addEventListener('close',()=>{if(!moving&&active==='ai')select(returnFromAI)})
 window.creatorWorkspace=Object.freeze({select,opened:select,current:()=>active})
 select('model')
}
