import './asset-libraries.css'

export function initAssetLibraries({actions,api,author,refresh}){
 const open=document.createElement('button');open.type='button';open.id='asset-libraries-open';open.textContent='拓展资产库';actions.append(open)
 const dialog=document.createElement('dialog');dialog.id='asset-libraries';dialog.className='asset-libraries-dialog'
 dialog.innerHTML=`<header><h2>拓展资产库</h2><button type="button" id="asset-libraries-close">关闭</button></header>
 <p>连接本地目录或 HTTPS 库，已缓存的资产可离线使用。配方在参数化模块库预览后保存，构件导入后可在素材库查看和放置。</p>
 <form id="asset-libraries-form"><label>库目录或清单地址<input id="asset-libraries-source" required maxlength="2048" placeholder="本地绝对目录、library.json 或 registry.json 的 HTTPS 地址"></label><button type="submit">查看清单</button></form>
 <div id="asset-libraries-discovery"></div><p id="asset-libraries-status" role="status" aria-live="polite"></p>
 <h3>已连接的库</h3><div id="asset-libraries-connections"></div>
 <h3>可用资产</h3><label>搜索资产<input id="asset-libraries-search" type="search" placeholder="名称、分类、库编号"></label><div id="asset-libraries-items"></div>`
 document.body.append(dialog)
 const $=id=>dialog.querySelector('#'+id),call=(action,args={})=>api('asset-libraries/'+action,args)
 let pending=false,items=[],limit=60
 const status=(message,error=false)=>{$('asset-libraries-status').textContent=message;$('asset-libraries-status').classList.toggle('error',error)}
 const statuses={draft:'试作',stable:'常规',recommended:'推荐',deprecated:'旧款'}
 function node(tag,value){const element=document.createElement(tag);element.textContent=value;return element}
 function button(label,action){const element=node('button',label);element.type='button';element.onclick=()=>perform(action);return element}
 async function perform(action){if(pending)return;pending=true;dialog.setAttribute('aria-busy','true');for(const element of dialog.querySelectorAll('button,input'))element.disabled=true;try{await action()}catch(error){status(error.message,true)}finally{pending=false;dialog.setAttribute('aria-busy','false');for(const element of dialog.querySelectorAll('button,input'))element.disabled=false}}
 function renderItems(){
  const query=$('asset-libraries-search').value.trim().toLocaleLowerCase(),visible=items.filter(item=>[item.name,item.category,item.library_id].join(' ').toLocaleLowerCase().includes(query))
  $('asset-libraries-items').replaceChildren(node('p',`${visible.length} 项资产 · 含应用自带发行快照`))
  for(const item of visible.slice(0,limit)){
   const card=document.createElement('article');card.dataset.assetId=item.id;card.title='许可：'+item.license;card.append(node('strong',item.name),node('small',`${item.category} · ${item.library_id} · ${item.version} · ${statuses[item.status]??item.status}`))
   card.append(button(item.type==='parametric_recipe'?'使用配方':'导入构件',async()=>{
    const result=await call(item.type==='parametric_recipe'?'read':'import',{id:item.id,sha256:item.sha256})
    if(item.type==='parametric_recipe'){dialog.close();await author.useLibraryRecipe(result.asset)}
    else{await refresh();status('已导入为待审阅的新构件，可在素材库查看和放置')}
   }));$('asset-libraries-items').append(card)
  }
  if(visible.length>limit)$('asset-libraries-items').append(button('显示更多资产',()=>{limit+=60;renderItems()}))
 }
 async function load(){
  const result=await call('list');items=result.items.sort((a,b)=>Number(a.source_id==='bundled')-Number(b.source_id==='bundled'));$('asset-libraries-connections').replaceChildren()
  if(!result.sources.length)$('asset-libraries-connections').append(node('p','尚未连接外部库。应用自带配方可直接使用。'))
  for(const source of result.sources){
   const card=document.createElement('article');card.dataset.sourceId=source.id;card.append(node('strong',source.name),node('small',`${source.version} · ${source.count} 项 · ${source.enabled?'已启用':'已停用'}`),node('small',source.source))
   if(source.error)card.append(node('p','上次刷新失败：'+source.error.message))
   for(const error of result.errors.filter(error=>error.source_id===source.id))card.append(node('p','当前缓存不可用：'+error.error))
   card.append(button('刷新',async()=>{try{await call('refresh',{id:source.id});status('库已更新，本地版本已缓存')}finally{await load()}}),button(source.enabled?'停用':'启用',async()=>{await call('enable',{id:source.id,enabled:!source.enabled});await load();status(source.enabled?'已停用拓展库':'已启用拓展库')}),button('移除连接',async()=>{await call('remove',{id:source.id});await load();status('已移除连接，已导入的构件保留')}))
   if(source.history?.length)card.append(button('回退上一版',async()=>{await call('rollback',{id:source.id});await load();status('已回退到缓存版本')}))
   $('asset-libraries-connections').append(card)
  }
  renderItems()
  if(result.errors.length)status(result.errors.map(error=>error.error).join('；'),true)
 }
 $('asset-libraries-form').onsubmit=event=>{event.preventDefault();perform(async()=>{
  status('正在读取库清单…');const result=await call('discover',{source:$('asset-libraries-source').value.trim()});$('asset-libraries-discovery').replaceChildren()
  for(const entry of result.items){const card=document.createElement('article');card.append(node('strong',entry.name),node('small',`${entry.id} · ${entry.version}`),button('连接此库',async()=>{status('正在校验并缓存资产…');await call('add',{source:entry.source,manifest_sha256:entry.manifest_sha256});await load();status('已连接拓展库，资产已校验并缓存')}));$('asset-libraries-discovery').append(card)}
  status(`清单包含 ${result.items.length} 个库，选择需要连接的库`)
 })}
 $('asset-libraries-search').oninput=()=>{limit=60;renderItems()}
 $('asset-libraries-close').onclick=()=>dialog.close()
 dialog.addEventListener('cancel',event=>{if(pending)event.preventDefault()})
 open.onclick=()=>{if(!dialog.open)dialog.showModal();status('');perform(load)}
 return {open:()=>open.click()}
}
