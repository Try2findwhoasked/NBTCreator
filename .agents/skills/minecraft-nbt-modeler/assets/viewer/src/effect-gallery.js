import './effect-gallery.css'

// Effects have their own visible library view; component workflows keep their IDs.
export function initEffectGallery({api,openEffect,manage,capture}){
 const host=document.getElementById('asset-workspace'),componentBody=host.querySelector('.library-layout'),toolbar=host.querySelector('.library-toolbar'),search=document.getElementById('asset-search'),trash=document.getElementById('asset-trash')
 const tabs=document.createElement('nav');tabs.className='asset-kind-tabs';tabs.setAttribute('aria-label','资产类型');tabs.innerHTML='<button id="asset-kind-components" type="button" aria-pressed="true">建筑构件</button><button id="asset-kind-effects" type="button" aria-pressed="false">效果预设</button>';toolbar.before(tabs);const help=document.createElement('p');help.className='asset-type-help';help.textContent='建筑构件是可放置的几何；效果预设是材质、旧化等工具设置。配方和材质主题在左侧单独管理。';tabs.after(help)
 const gallery=document.createElement('section');gallery.id='effect-assets-gallery';gallery.hidden=true;gallery.innerHTML='<div class="effect-gallery-heading"><p id="effect-assets-count" role="status"></p><div><button id="effect-assets-capture" type="button">保存当前工具配置</button><button id="effect-assets-import" type="button">导入或管理效果</button></div></div><div id="effect-assets-grid" class="project-grid"></div>';componentBody.after(gallery)
 const componentButton=tabs.querySelector('#asset-kind-components'),effectButton=tabs.querySelector('#asset-kind-effects'),count=gallery.querySelector('#effect-assets-count'),grid=gallery.querySelector('#effect-assets-grid')
 let mode='components',items=[],first=true,autoSelected=false,epoch=0
 function select(value,automatic=false){mode=value;autoSelected=automatic;componentBody.hidden=value!=='components';componentBody.style.display=value==='components'?'':'none';gallery.hidden=value!=='effects';componentButton.setAttribute('aria-pressed',String(value==='components'));effectButton.setAttribute('aria-pressed',String(value==='effects'));document.getElementById('tool-effects-open').hidden=value!=='effects';search.placeholder=value==='effects'?'搜索效果名称或说明':'名称、标签或尺寸';for(const id of ['asset-import','asset-save-selection','asset-create-agent'])document.getElementById(id).hidden=value==='effects';if(value==='effects')render()}
 function render(){
  const query=search.value.trim().toLocaleLowerCase(),visible=items.filter(item=>!!item.archived===trash.checked&&(!query||[item.name,item.settings.style_note??''].join(' ').toLocaleLowerCase().includes(query)))
  effectButton.textContent='效果预设 · '+items.filter(item=>!item.archived).length;count.textContent=visible.length+' 项'+(trash.checked?'已回收':'可用')+'工具效果 · 点击查看前后3D样例';grid.replaceChildren()
  for(const item of visible){
   const article=document.createElement('article');article.className='project-card';const card=document.createElement('button');card.type='button';card.className='effect-asset-card';card.dataset.effectAssetId=item.id
   const cover=document.createElement('span');cover.className='project-cover';if(item.thumbnail){const image=document.createElement('img');image.src=item.thumbnail;image.alt=item.name;image.loading='lazy';image.decoding='async';cover.append(image)}else cover.textContent='点击生成效果预览'
   const name=document.createElement('strong'),note=document.createElement('span');name.textContent=item.name;note.className='project-card-meta';note.textContent=item.settings.style_note||'工具配置 · 点击查看和载入';card.append(cover,name,note);card.onclick=()=>openEffect(item.id);article.append(card);grid.append(article)
  }
  if(!visible.length){const empty=document.createElement('p');empty.textContent=trash.checked?'效果回收站为空':query?'没有匹配的工具效果':'暂无工具效果，可保存当前配置或手动导入';grid.append(empty)}
 }
 async function refresh(){const token=++epoch;try{const [effects,components]=await Promise.all([api('effect-assets/list',{}),api('components')]);if(token!==epoch)return;items=effects.items;render();if(first){first=false;if(!components.items.length)select('effects',true)}if(effects.errors?.length)count.textContent+='；'+effects.errors.length+' 项效果无法读取'}catch(error){count.textContent=error.message;if(mode==='effects')grid.replaceChildren()}}
 componentButton.onclick=()=>select('components');effectButton.onclick=()=>{select('effects');refresh()};gallery.querySelector('#effect-assets-capture').onclick=capture;const legacy=gallery.querySelector('#effect-assets-import');legacy.hidden=true;legacy.onclick=manage;const manager=document.getElementById('tool-effects-open');manager.textContent='导入与管理预设';gallery.querySelector('.effect-gallery-heading>div').append(manager)
 search.addEventListener('input',()=>{if(mode==='effects')render()});trash.addEventListener('change',()=>{if(mode==='effects')render()});document.getElementById('asset-refresh').addEventListener('click',refresh)
 window.addEventListener('creator-workspace-change',event=>{if(event.detail==='assets')refresh()});for(const event of ['creator-tool-effects-change','creator-assets-organized'])window.addEventListener(event,refresh)
 // A new component should become visible after a capture/import into an empty library.
 new MutationObserver(()=>{if(autoSelected&&document.querySelector('#asset-grid .asset-card'))select('components')}).observe(document.getElementById('asset-grid'),{childList:true})
 if(document.body.dataset.workspace==='assets')refresh()
 return {refresh}
}
