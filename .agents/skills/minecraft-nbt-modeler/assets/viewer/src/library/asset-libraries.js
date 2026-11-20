import './asset-libraries.css'

export function initAssetLibraries({actions,api,refresh}){
 const open=document.createElement('button')
 open.type='button';open.id='asset-libraries-open';open.textContent='来源管理';actions.append(open)
 const dialog=document.createElement('dialog')
 dialog.id='asset-libraries';dialog.className='asset-libraries-dialog'
 dialog.innerHTML=`<header><h2>素材来源</h2><button type="button" id="asset-libraries-close">关闭</button></header>
 <div class="asset-sources-body"><p>连接的配方与构件会直接显示在素材库，可按来源筛选。</p>
 <form id="asset-libraries-form"><label>本地库目录或 HTTPS 清单<input id="asset-libraries-source" required maxlength="2048" placeholder="库目录、library.json 或 registry.json 地址"></label><button type="submit">查看清单</button></form>
 <div id="asset-libraries-discovery"></div><p id="asset-libraries-status" role="status" aria-live="polite"></p>
 <div id="asset-libraries-connections"></div></div>`
 document.body.append(dialog)
 const $=id=>dialog.querySelector('#'+id)
 const call=(action,args={})=>api('asset-libraries/'+action,args)
 let pending=false
 const status=(message,error=false)=>{$('asset-libraries-status').textContent=message;$('asset-libraries-status').classList.toggle('error',error)}
 function node(tag,value){const element=document.createElement(tag);element.textContent=value;return element}
 function button(label,action,sourceId='',operation=''){
  const element=node('button',label);element.type='button'
  element.dataset.sourceAction=operation;element.dataset.sourceId=sourceId
  element.onclick=()=>perform(action);return element
 }
 async function perform(action){
  if(pending)return
  const focused=document.activeElement
  const focusKey=focused?.dataset.sourceAction,sourceId=focused?.dataset.sourceId
  pending=true;dialog.setAttribute('aria-busy','true')
  for(const element of dialog.querySelectorAll('button,input'))element.disabled=true
  try{await action()}catch(error){status(error.message,true)}
  finally{
   pending=false;dialog.setAttribute('aria-busy','false')
   for(const element of dialog.querySelectorAll('button,input'))element.disabled=false
   if(dialog.open&&focused&&!focused.isConnected){
    const next=[...dialog.querySelectorAll('button')].find(item=>item.dataset.sourceAction===focusKey&&item.dataset.sourceId===sourceId)
    ;(next??$('asset-libraries-close')).focus()
   }
  }
 }
 async function change(action,source,extra={}){
  try{
   const result=await call(action,{id:source.id,...extra})
   await refresh({action,source:result.source})
   status(action==='remove'?'已移除来源连接。':action==='rollback'?'已切换至缓存的上一版本。':action==='enable'?(extra.enabled?'已启用来源。':'已停用来源。'):'来源已刷新。')
  }finally{await load()}
 }
 async function load(){
  const result=await call('browse')
  $('asset-libraries-connections').replaceChildren()
  const local=document.createElement('article')
  local.append(node('strong','本地工作区'),node('p','本地副本可直接编辑。'))
  $('asset-libraries-connections').append(local)
  for(const source of result.sources){
   const card=document.createElement('article');card.dataset.sourceId=source.id
   card.append(node('strong',source.bundled?'应用自带':source.name),node('p',`${source.version??'版本不可用'} · ${source.count??0} 项 · ${source.enabled?'已启用':'已停用'}`))
   if(source.source)card.append(node('small',source.source))
   if(source.error)card.append(node('p','上次刷新未完成，当前保留缓存版本。'+source.error.message))
   for(const error of result.errors.filter(error=>error.source_id===source.id))card.append(node('p',error.error))
   if(!source.bundled){
    card.append(button('联网刷新',()=>change('refresh',source),source.id,'refresh'),button(source.enabled?'停用':'启用',()=>change('enable',source,{enabled:!source.enabled}),source.id,'enable'))
    if(source.history?.length)card.append(button('回退上一版',()=>change('rollback',source),source.id,'rollback'))
    card.append(button('移除连接',()=>change('remove',source),source.id,'remove'))
   }
   $('asset-libraries-connections').append(card)
  }
  if(result.errors.some(error=>error.source_id==='configuration'))status('来源配置暂时无法读取，请检查工作区连接记录。',true)
 }
 $('asset-libraries-form').onsubmit=event=>{
  event.preventDefault()
  perform(async()=>{
   status('正在读取清单…')
   const result=await call('discover',{source:$('asset-libraries-source').value.trim()})
   $('asset-libraries-discovery').replaceChildren()
   for(const entry of result.items){
    const card=document.createElement('article')
    card.append(node('strong',entry.name),node('small',`${entry.id} · ${entry.version}`),button('连接此来源',async()=>{
     status('正在校验并缓存素材…')
     const added=await call('add',{source:entry.source,manifest_sha256:entry.manifest_sha256})
     await load();await refresh({action:'add',source:added.source})
     status('已连接，在素材库中按此来源显示。')
    }))
    $('asset-libraries-discovery').append(card)
   }
   status(`找到 ${result.items.length} 个来源，可选择连接。`)
  })
 }
 $('asset-libraries-close').onclick=()=>dialog.close()
 dialog.addEventListener('cancel',event=>{if(pending)event.preventDefault()})
 dialog.addEventListener('close',()=>{
  const entry=document.getElementById('asset-library-menu')?.querySelector('summary')??document.getElementById('asset-search')
  if(entry?.getClientRects().length)entry.focus()
 })
 open.onclick=()=>{if(!dialog.open)dialog.showModal();status('');perform(load)}
 return {open:()=>open.click()}
}
