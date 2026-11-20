import './effect-gallery.css'
import {createComparison} from './library-comparison.js'
import {initPatternAssets} from './pattern-assets.js'
import {createUseTree} from './library-use-tree.js'
import {createLibrarySelection} from './library-selection.js'
import {semanticTags} from './asset-categories.js'

// Effects have their own visible library view; component workflows keep their IDs.
export function initEffectGallery({api,openEffect,manage,capture}){
 const host=document.getElementById('asset-workspace'),componentBody=host.querySelector('.library-layout'),toolbar=host.querySelector('.library-toolbar'),search=document.getElementById('asset-search'),trash=document.getElementById('asset-trash')
 const tabs=document.createElement('nav');tabs.className='asset-kind-tabs';tabs.setAttribute('aria-label','资产类型');tabs.innerHTML='<button id="asset-kind-components" type="button" aria-pressed="true">建筑构件</button><button id="asset-kind-effects" type="button" aria-pressed="false">效果预设</button>';toolbar.insertBefore(tabs,toolbar.querySelector('.library-actions'));const help=document.createElement('p');help.className='asset-type-help';help.textContent='建筑构件是可放置的几何；效果预设是材质、旧化等工具设置。配方和材质主题在左侧单独管理。';help.hidden=true
 const gallery=document.createElement('section');gallery.id='effect-assets-gallery';gallery.hidden=true;gallery.innerHTML='<div class="effect-gallery-heading"><p id="effect-assets-count" role="status"></p><div><button id="effect-assets-capture" type="button">保存当前工具配置</button><button id="effect-assets-import" type="button">导入或管理效果</button></div></div><div class="library-layout effect-library-layout"><aside id="effect-assets-tree" class="library-tree" aria-label="效果预设文件"></aside><main class="library-main"><div id="effect-assets-grid" class="project-grid"></div></main></div>';componentBody.after(gallery)
 const componentButton=tabs.querySelector('#asset-kind-components'),effectButton=tabs.querySelector('#asset-kind-effects'),count=gallery.querySelector('#effect-assets-count'),grid=gallery.querySelector('#effect-assets-grid')
 const groupManager=window.creatorAssetGroups
 let mode='components',items=[],epoch=0,folder='all'
 const layout=gallery.querySelector('.effect-library-layout')
 const selection=createLibrarySelection({layout,title:'效果预设',onOpen:item=>openEffect(item.id)})
 const tree=createUseTree({container:gallery.querySelector('#effect-assets-tree'),title:'效果预设',groupsFor:semanticTags,customGroups:()=>groupManager.groups('effects'),assignment:id=>groupManager.assignment('effects',id),onFolder:key=>{folder=key;render()},onItem:item=>selection.show(item,item.settings.style_note||'工具配置')})
 const compare=createComparison({host,grid,kind:'效果预设',key:item=>item.id,name:item=>item.name,
  fields:[['效果说明',item=>item.settings.style_note],['启用的工具',item=>Object.entries({pattern:'混材',weathering:'旧化',floor:'地面',replace:'方块替换',structure:'结构编辑'}).filter(([key])=>item.settings[key]?.enabled).map(([,label])=>label).join('、')||'无'],['标签',item=>item.tags?.join('、')],['附加步骤',item=>String(item.settings.operations?.length??0)]],
  preview:item=>item.thumbnail,openLabel:'查看前后效果',open:item=>openEffect(item.id)})
 host.dataset.kind=mode
 function select(value){host.dataset.kind=value;groupManager.clearSelection();const treeToggle=host.querySelector('.library-tree-toggle');treeToggle.hidden=false;treeToggle.textContent='文件夹';treeToggle.setAttribute('aria-controls',{components:'asset-tree',effects:'effect-assets-tree',patterns:'pattern-assets-tree'}[value]);mode=value;componentBody.hidden=value!=='components';componentBody.style.display=value==='components'?'':'none';gallery.hidden=value!=='effects';patterns.host.hidden=value!=='patterns';patterns.button.setAttribute('aria-pressed',String(value==='patterns'));componentButton.setAttribute('aria-pressed',String(value==='components'));effectButton.setAttribute('aria-pressed',String(value==='effects'));document.getElementById('tool-effects-open').hidden=value!=='effects';search.placeholder=value==='effects'?'搜索效果名称或说明':value==='patterns'?'搜索纹样名称或标签':'名称、分类、来源或尺寸';for(const id of ['asset-import','asset-create-agent'])document.getElementById(id).hidden=value!=='components';if(value==='effects')render()}
 function render(){
  if(folder.startsWith('group:')&&!groupManager.groups('effects').some(group=>group.id===folder.slice(6)))folder='all'
  const query=search.value.trim().toLocaleLowerCase(),available=items.filter(item=>!!item.archived===trash.checked),visible=available.filter(item=>(folder==='all'||folder.startsWith('tag:')&&semanticTags(item).includes(folder.slice(4))||folder.startsWith('group:')&&groupManager.assignment('effects',item.id)===folder.slice(6))&&(!query||[item.name,item.settings.style_note??''].join(' ').toLocaleLowerCase().includes(query)))
  groupManager.setVisible('effects',visible)
  tree.render(available,folder)
  effectButton.textContent='效果预设 · '+items.filter(item=>!item.archived).length;count.textContent=visible.length+' 项'+(trash.checked?'已回收':'可用')+'工具效果 · 点击查看前后3D样例';grid.replaceChildren()
  for(const item of visible){
   const article=document.createElement('article');article.className='project-card';const card=document.createElement('button');card.type='button';card.className='effect-asset-card';card.dataset.effectAssetId=item.id
   const cover=document.createElement('span');cover.className='project-cover';if(item.thumbnail){const image=document.createElement('img');image.src=item.thumbnail;image.alt=item.name;image.loading='lazy';image.decoding='async';cover.append(image)}else cover.textContent='点击生成效果预览'
   const name=document.createElement('strong'),note=document.createElement('span');name.textContent=item.name;note.className='project-card-meta';note.textContent=item.settings.style_note||'工具配置 · 双击打开';card.append(cover,name,note);card.onclick=()=>selection.show(item,item.settings.style_note||'工具配置');card.ondblclick=()=>openEffect(item.id);article.append(card);groupManager.decorate(article,'effects',item.id);compare.decorate(article,item);grid.append(article)
  }
  if(!visible.length){const empty=document.createElement('p');empty.textContent=trash.checked?'效果回收站为空':query?'没有匹配的工具效果':'暂无工具效果，可保存当前配置或手动导入';grid.append(empty)}
 }
 async function refresh(){const token=++epoch;try{const effects=await api('effect-assets/list',{});if(token!==epoch)return;items=effects.items;compare.reconcile(items);render();if(effects.errors?.length)count.textContent+='；'+effects.errors.length+' 项效果无法读取'}catch(error){count.textContent=error.message;if(mode==='effects')grid.replaceChildren()}}
 const patterns=initPatternAssets({api,tabs,search,trash,selectMode:select});help.hidden=true
 componentButton.onclick=()=>select('components');effectButton.onclick=()=>{select('effects');refresh()};gallery.querySelector('#effect-assets-capture').onclick=capture;const legacy=gallery.querySelector('#effect-assets-import');legacy.hidden=true;legacy.onclick=manage;const manager=document.getElementById('tool-effects-open');manager.textContent='导入与管理预设';gallery.querySelector('.effect-gallery-heading>div').append(manager)
 search.addEventListener('input',()=>{if(mode==='effects')render()});trash.addEventListener('change',()=>{if(mode==='effects')render()});document.getElementById('asset-refresh').addEventListener('click',refresh)
 window.addEventListener('creator-asset-groups-change',()=>{if(mode==='effects')render()})
 window.addEventListener('creator-workspace-change',event=>{if(event.detail==='assets')refresh()});for(const event of ['creator-tool-effects-change','creator-assets-organized'])window.addEventListener(event,refresh)
 select('components')
 if(document.body.dataset.workspace==='assets')refresh()
 return {refresh}
}
