import './asset-workspace.css'
import {createComparison} from './library-comparison.js'
import {semanticTags} from './asset-categories.js'
import {initAssetBatches} from './asset-batches.js'
import {initLibraryBrowser} from './library-browser.js'
import {createAssetTree} from './asset-tree.js'
import {initComponentAuthor} from '../components/component-author.js'
import {initAssetLibraries} from './asset-libraries.js'
import {createAssetPreview} from './library-asset-preview.js'
import {initAssetGroups} from './asset-groups.js'

export function initAssetWorkspace({api,context,interactive,chooseTarget,decorateTree=()=>{}}){
 const host=document.createElement('section');host.id='asset-workspace';host.hidden=true
 host.innerHTML=`<div class="asset-toolbar"><label>搜索构件<input id="asset-search" type="search" placeholder="名称、标签或尺寸"></label><label class="inline"><input id="asset-trash" type="checkbox">查看回收站</label><button id="asset-refresh">刷新</button><button id="asset-import">导入构件</button><input id="asset-import-file" type="file" accept="application/json,.json" hidden></div>
 <p id="asset-status" role="status"></p><div class="asset-layout"><main><p id="asset-count"></p><div id="asset-grid"></div><button id="asset-more" hidden>加载更多</button></main><aside id="asset-detail" hidden>
 <img id="asset-image" alt="构件几何示意图"><h2 id="asset-name"></h2><p id="asset-meta"></p><p class="muted">几何与简化材质示意；放置后在当前建筑中查看实际效果。</p>
 <label>名称<input id="asset-edit-name" maxlength="80"></label><label>标签（逗号分隔）<input id="asset-edit-tags" maxlength="500"></label><button id="asset-update">保存名称与标签</button><a id="asset-export" download>导出构件 JSON</a><button id="asset-archive">移入回收站</button>
 <p id="asset-target"></p><button id="asset-place" type="button" class="primary">放到当前建筑</button></aside></div>`
 document.querySelector('.creator-header').after(host)
 const main=host.querySelector('.asset-layout>main'),actions=document.createElement('div'),filters=document.createElement('div'),tree=document.createElement('aside'),breadcrumb=document.createElement('p');tree.id='asset-tree';tree.setAttribute('aria-label','构件分类');breadcrumb.id='asset-breadcrumb';filters.className='project-filters';filters.append(document.getElementById('asset-trash').closest('label'));actions.append(document.getElementById('asset-import'));const importFile=document.getElementById('asset-import-file'),status=document.getElementById('asset-status'),inspector=document.getElementById('asset-detail');main.append(status)
 const browser=initLibraryBrowser({host,prefix:'asset',title:'资产管理',description:'浏览本地、自带和已连接来源的配方与构件，按名称、分类或来源筛选。点击素材可查看三维、调整配方参数和放置候选；来源连接与版本操作在素材库工具中管理。',search:document.getElementById('asset-search'),refresh:document.getElementById('asset-refresh'),actions,filters,tree,main,count:document.getElementById('asset-count'),breadcrumb});host.append(importFile)
 const groupManager=initAssetGroups({host,api});window.creatorAssetGroups=groupManager
 const inspectorDialog=document.createElement('dialog');inspectorDialog.id='asset-inspector-dialog';const inspectorHeader=document.createElement('header'),closeInspector=document.createElement('button');closeInspector.type='button';closeInspector.textContent='关闭';closeInspector.id='asset-inspector-close';closeInspector.onclick=()=>inspectorDialog.close();inspectorHeader.append(inspector.querySelector('#asset-name'),closeInspector);inspectorDialog.append(inspectorHeader,inspector);const inspectorStatus=document.createElement('p');inspectorStatus.id='asset-detail-status';inspectorStatus.setAttribute('role','status');inspectorStatus.setAttribute('aria-live','polite');inspectorStatus.hidden=true;inspectorHeader.after(inspectorStatus);browser.body.append(inspectorDialog);inspectorDialog.addEventListener('close',()=>browser.body.classList.remove('selection-open'))
 const save=document.createElement('dialog');save.id='asset-save-dialog';save.className='review-help-dialog'
 save.innerHTML='<h2>保存当前选区为构件</h2><p>保存当前显示的 3D 原模型或候选选区。每轴最多64格，共最多65536格；不修改建筑。</p><label>构件名称<input id="asset-save-name" maxlength="80"></label><label>标签（逗号分隔）<input id="asset-save-tags"></label><label class="inline"><input id="asset-save-air" type="checkbox">包含选区内的空气（用于保留开口；放置时可能需要允许覆盖）</label><p id="asset-save-range"></p><p id="asset-save-error" role="status"></p><button id="asset-save-cancel">取消</button><button id="asset-save-confirm" class="primary">保存到构件库</button>'
 document.body.append(save)
 const $=id=>document.getElementById(id),message=(text,error=false)=>{$('asset-status').textContent=text;$('asset-status').classList.toggle('error',error);inspectorStatus.textContent=text;inspectorStatus.classList.toggle('error',error);inspectorStatus.hidden=!text}
 let items=[],selected=null,limit=24,pending=false,saveContext=null,loaded=false,category='all',assetPreview=null,refreshEpoch=0,renderEpoch=0
 const thumbnailJobs=new WeakMap()
 let thumbnailQueue=[],thumbnailBusy=0
 const thumbnailObserver=new IntersectionObserver(entries=>{
  for(const entry of entries){
   if(!entry.isIntersecting)continue
   thumbnailObserver.unobserve(entry.target)
   const job=thumbnailJobs.get(entry.target)
   if(job)thumbnailQueue.push(job)
  }
  pumpThumbnails()
 },{root:browser.main,rootMargin:'80px'})
 function pumpThumbnails(){
  while(thumbnailBusy<2&&thumbnailQueue.length&&document.body.dataset.workspace==='assets'&&host.dataset.kind==='components'){
   const job=thumbnailQueue.shift()
   if(job.epoch!==renderEpoch||!job.cover.isConnected)continue
   thumbnailBusy++
   api('asset-libraries/thumbnail',job.item.library_ref).then(result=>{
    if(job.epoch!==renderEpoch||!job.cover.isConnected)return
    job.item.thumbnail=result.thumbnail
    const image=document.createElement('img');image.src=result.thumbnail;image.alt=job.item.name;image.decoding='async'
    job.cover.classList.remove('asset-thumbnail-pending');job.cover.replaceChildren(image)
   }).catch(()=>{if(job.cover.isConnected)job.cover.textContent='点击查看预览'}).finally(()=>{thumbnailBusy--;pumpThumbnails()})
  }
 }
 const sourceLabel=item=>item.source_label??'本地工作区'
 host.addEventListener('click',event=>{if(event.target.id==='asset-kind-components')pumpThumbnails()})
 const typeLabel=item=>item.type==='parametric_recipe'?'可调配方':'构件'
 const sourceFields=document.createElement('label')
 sourceFields.innerHTML='来源<select id="asset-source-filter"><option value="all">全部来源</option><option value="local">本地工作区</option><option value="bundled">应用自带</option></select>'
 sourceFields.dataset.toolKind='components'
 const typeFields=document.createElement('label')
 typeFields.innerHTML='素材类型<select id="asset-content-filter"><option value="all">配方与构件</option><option value="parametric_recipe">可调配方</option><option value="component">构件</option></select>'
 typeFields.dataset.toolKind='components'
 filters.append(sourceFields,typeFields)
 const sourceFilter=$('asset-source-filter'),contentFilter=$('asset-content-filter')
 browser.scope.innerHTML='<label>审阅状态<select id="asset-review-filter"><option value="all">全部素材</option><option value="pending">待看图审阅</option></select></label><label>排列方式<select id="asset-sort"><option value="library">库内顺序</option><option value="name">按名称</option><option value="blocks">方块数从少到多</option></select></label><button type="button" id="asset-reset-view">恢复默认视图</button>'
 const reviewFilter=$('asset-review-filter'),sort=$('asset-sort')
 function resetView(){reviewFilter.value='all';sort.value='library';sourceFilter.value='all';contentFilter.value='all';category='all';$('asset-search').value='';$('asset-trash').checked=false;selected=null;limit=24;details();$('asset-search').dispatchEvent(new Event('input'));$('asset-search').focus()}
 $('asset-reset-view').onclick=resetView
 for(const field of [reviewFilter,sort])field.onchange=()=>{limit=24;render()}
 for(const field of [sourceFilter,contentFilter])field.onchange=()=>{category='all';limit=24;render()}
 function inspectItem(item){if(pending)return;selected=item;message('');details(true);render();assetPreview.select(item)}
 const compare=createComparison({host,grid:$('asset-grid'),kind:'构件',key:item=>item.id,name:item=>item.name,
  fields:[['类型',typeLabel],['来源',sourceLabel],['版本',item=>item.version??'工作区副本'],['尺寸（格）',item=>item.size.join(' × ')],['方块数',item=>item.block_count===undefined?'预览后显示':String(item.block_count)],['锚点 XYZ',item=>item.anchor?.join(', ')??'随配方生成'],['分类',item=>semanticTags(item).join('、')]],
  preview:async item=>item.thumbnail??(item.library_ref?(await api('asset-libraries/thumbnail',item.library_ref)).thumbnail:null),openLabel:'查看与放置',open:inspectItem})
 const treeView=createAssetTree({container:tree,onCategory:value=>{category=value;limit=24;render()},onOpen:inspectItem,onRender:decorateTree,groups:()=>groupManager.groups('components'),assignment:id=>groupManager.assignment('components',id)})
 window.addEventListener('creator-assets-organized',()=>refresh().catch(error=>message(error.message)))
 const tags=text=>text.split(/[,，]/).map(v=>v.trim()).filter(Boolean)
 const assetFigure=document.createElement('figure');assetFigure.className='asset-detail-figure'
 $('asset-image').before(assetFigure);assetFigure.append($('asset-image'))
 const caption=document.createElement('figcaption');assetFigure.append(caption);caption.append($('asset-meta'))
 const captionNote=inspector.querySelector(':scope > p.muted')
 if(captionNote)captionNote.remove()
 function target(){try{const c=context();$('asset-target').textContent=c?.name?`当前建筑 · ${c.name}`:'';$('asset-place').textContent=c?'放到当前建筑':'选择目标建筑';return c}catch{$('asset-target').textContent='请先补齐当前建筑的编辑参数。';return null}}
 function controls(){
  let current=null,invalid=false
  try{current=context()}catch{invalid=true}
  const locked=pending||!!current?.busy
  for(const card of $('asset-grid').querySelectorAll('.asset-card'))card.disabled=pending
  inspectorDialog.setAttribute('aria-busy',String(pending))
  for(const field of inspector.querySelectorAll('input,select,button')){
   if(field.closest('#asset-recipe-parameters')||field.id==='asset-preview-refresh')continue
   field.disabled=locked||!selected
  }
  assetPreview?.lock(locked)
  const needsPreview=!!selected?.library_ref&&!assetPreview?.canUse()
  $('asset-place').disabled=locked||invalid||!selected||!!selected.archived||needsPreview
  $('asset-place').hidden=!!selected?.archived
  if($('asset-copy-local'))$('asset-copy-local').disabled=locked||!selected?.library_ref||needsPreview
  $('asset-inspector-close').disabled=false
 }
 function details(reveal=false){
  $('asset-detail').hidden=!selected;if(!selected){if(inspectorDialog.open)inspectorDialog.close();return}
  if(selected.thumbnail)$('asset-image').src=selected.thumbnail
  $('asset-name').textContent=selected.name;$('asset-meta').textContent=`${typeLabel(selected)} · ${selected.size.join(' × ')}${selected.block_count===undefined?'':` · ${selected.block_count} 格`}`
  $('asset-edit-name').value=selected.name;$('asset-edit-tags').value=selected.tags.join(', ');$('asset-export').href=selected.download;$('asset-export').download=selected.name+'.component.json';$('asset-archive').textContent=selected.archived?'恢复构件':'移入回收站'
  inspector.querySelector('.asset-management').hidden=!!selected.library_ref
  $('asset-origin').hidden=!selected.library_ref
  $('asset-copy-local').textContent=selected.type==='parametric_recipe'?'保存参数结果为本地构件':'复制到本地编辑'
  $('asset-source-note').textContent=`${sourceLabel(selected)}${selected.version?' · '+selected.version:''} · ${selected.library_ref?(selected.type==='parametric_recipe'?'可调参预览和放置':'可直接预览和放置'):'可编辑的工作区构件'}`
  if(reveal)inspector.querySelector('.asset-management').open=!!selected.archived
  controls()
  target()
  if(reveal&&document.body.dataset.workspace==='assets'&&!inspectorDialog.open){inspectorDialog.show();browser.body.classList.add('selection-open')}
 }
 function render(){
  const epoch=++renderEpoch
  thumbnailObserver.disconnect();thumbnailQueue=[]
  if(category.startsWith('group:')&&!groupManager.groups('components').some(group=>group.id===category.slice(6)))category='all'
  const query=$('asset-search').value.toLocaleLowerCase(),trash=$('asset-trash').checked,scroll=browser.main.scrollTop
  const browsing=items.filter(item=>!!item.archived===trash&&(sourceFilter.value==='all'||item.source_id===sourceFilter.value)&&(contentFilter.value==='all'||item.type===contentFilter.value))
  treeView.render(browsing,category,selected);$('asset-breadcrumb').textContent=category==='all'?'配方与构件':category==='untagged'?'未分类':category.startsWith('group:')?groupManager.groups('components').find(group=>group.id===category.slice(6))?.name??'自定义文件夹':category.slice(4)
  const visible=browsing.filter(item=>(reviewFilter.value==='all'||item.review_status==='pending_visual_review')&&(category==='all'||category==='untagged'&&!item.tags.length||category.startsWith('tag:')&&semanticTags(item).includes(category.slice(4))||category.startsWith('group:')&&groupManager.assignment('components',item.id)===category.slice(6))&&(!query||[item.name,item.asset_id??'',sourceLabel(item),...semanticTags(item),...item.tags,item.size.join('x')].join(' ').toLocaleLowerCase().includes(query)))
  groupManager.setVisible('components',visible)
  if(sort.value==='name')visible.sort((a,b)=>a.name.localeCompare(b.name,'zh-CN'))
  if(sort.value==='blocks')visible.sort((a,b)=>(a.block_count??Infinity)-(b.block_count??Infinity)||a.name.localeCompare(b.name,'zh-CN'))
  const criteria=[sourceFilter.value!=='all'?sourceFilter.selectedOptions[0]?.textContent:'',contentFilter.value!=='all'?contentFilter.selectedOptions[0]?.textContent:'',reviewFilter.value==='pending'?'待看图审阅':'',sort.value==='blocks'?'方块数从少到多':sort.value==='name'?'按名称排列':'',trash?'回收站':''].filter(Boolean)
  const activeScope=browser.scope.querySelector('.scope-summary')??document.createElement('span')
  activeScope.className='scope-summary';activeScope.textContent=criteria.join(' / ');browser.scope.append(activeScope);browser.scope.hidden=!criteria.length
  $('asset-count').textContent=`${visible.length} 项${trash?'已回收':'素材'}`;$('asset-grid').replaceChildren();$('asset-more').hidden=visible.length<=limit
  host.dataset.catalogueCount=String(items.filter(item=>!item.archived).length)
  for(const item of visible.slice(0,limit)){
   const card=document.createElement('button');card.type='button';card.className='asset-card';card.dataset.assetId=item.id;card.dataset.assetRef=item.library_ref?.id??item.id;card.dataset.sourceId=item.source_id;card.dataset.assetType=item.type;card.disabled=pending;card.setAttribute('aria-pressed',String(selected?.id===item.id))
   const cover=document.createElement('span');cover.className='project-cover';if(item.thumbnail){const image=document.createElement('img');image.src=item.thumbnail;image.loading='lazy';image.decoding='async';image.alt=item.name;cover.append(image)}else{cover.classList.add('asset-thumbnail-pending');cover.textContent='正在准备几何预览'}
   const name=document.createElement('strong'),meta=document.createElement('span'),labels=document.createElement('small');name.textContent=item.name;meta.className='project-card-meta';meta.textContent=`${typeLabel(item)} · ${item.size.join(' × ')}`;labels.textContent=sourceLabel(item)+' · '+semanticTags(item).join(' · ');card.append(cover,name,meta,labels);const duplicates=browsing.filter(other=>other.id!==item.id&&item.source_id==='local'&&other.source_id==='local'&&item.content_sha256&&other.content_sha256===item.content_sha256);if(duplicates.length){const note=document.createElement('small');note.className='asset-duplicate-note';note.textContent='与 '+duplicates.length+' 项构件内容相同';note.title=duplicates.map(v=>v.name).join('、');card.append(note)}
   const wrapper=document.createElement('article');wrapper.className='project-card';wrapper.append(card);card.onclick=()=>inspectItem(item);card.ondblclick=()=>{inspectItem(item);inspector.querySelector('.asset-management').open=!item.library_ref};groupManager.decorate(wrapper,'components',item.id);compare.decorate(wrapper,item);$('asset-grid').append(wrapper)
   if(item.library_ref&&!item.thumbnail){thumbnailJobs.set(card,{item,cover,epoch});thumbnailObserver.observe(card)}
  }
  if(!visible.length){
   const empty=document.createElement('section'),hint=document.createElement('p'),next=document.createElement('button')
   empty.className='asset-empty';next.type='button'
   if(query||category!=='all'||reviewFilter.value!=='all'||sourceFilter.value!=='all'||contentFilter.value!=='all'){
    hint.textContent='当前条件下没有匹配的构件。';next.textContent='恢复默认视图';next.onclick=resetView
   }else if(trash){
    hint.textContent='回收站为空。';next.textContent='返回可用构件';next.onclick=()=>{$('asset-trash').click()}
   }else{
    hint.textContent='构件库还没有内容。可以导入构件 JSON，也可以打开建筑，将局部选区保存为构件。';next.textContent='导入构件 JSON';next.onclick=()=>$('asset-import').click()
   }
   empty.append(hint,next);$('asset-grid').append(empty)
  }
  browser.main.scrollTop=scroll
 }
 async function refresh(reveal=false){
  const token=++refreshEpoch
  const [local,catalogue]=await Promise.all([api('components'),api('asset-libraries/browse',{})])
  if(token!==refreshEpoch)return
  const previous=selected
  items=[...local.items.map(item=>({...item,type:'component',source_id:'local',source_label:'本地工作区'})),...catalogue.items.map(item=>({
   ...item,id:item.source_id+':'+item.id,archived:false,source_label:item.source_id==='bundled'?'应用自带':item.source_name,
   library_ref:Object.fromEntries(['id','sha256','source_id','version','manifest_sha256'].map(key=>[key,item[key]]))
  }))]
  const filter=sourceFilter.value
  sourceFilter.replaceChildren(new Option('全部来源','all'),new Option('本地工作区','local'),...catalogue.sources.map(source=>new Option((source.bundled?'应用自带':source.name)+(source.enabled?'':'（已停用）'),source.id)))
  if([...sourceFilter.options].some(option=>option.value===filter))sourceFilter.value=filter
  compare.reconcile(items);loaded=true;selected=items.find(item=>item.id===previous?.id)||null
  render();details(reveal)
  if(selected&&inspectorDialog.open&&(reveal||JSON.stringify(previous?.library_ref)!==JSON.stringify(selected.library_ref)||previous?.content_sha256!==selected.content_sha256))assetPreview.select(selected)
  if(previous&&!selected){assetPreview.close();message('所选素材已移除或来源已停用，请重新选择。')}
  const errors=[...(local.errors??[]),...(catalogue.errors??[])]
  if(errors.length)message(`${errors.length} 项素材或来源无法读取，其余内容已加载`,true)
 }
 async function perform(action){if(pending)throw Error('请等待当前构件任务完成');pending=true;if(inspectorDialog.open&&inspectorStatus.classList.contains('error'))message('正在处理…');controls();try{return await action()}finally{pending=false;controls()}}
 initComponentAuthor({actions,api,created:async item=>{selected=item;await refresh(true);message('独立结构已保存为新资产，可查看、整理和按参数放置')}})
 initAssetLibraries({actions,api,refresh:async change=>{
  await refresh()
  if(change?.action==='add'){sourceFilter.value=change.source.id;contentFilter.value='all';$('asset-search').value='';category='all';limit=24;render()}
 }})
 const management=document.createElement('details');management.className='asset-management'
 const manageTitle=document.createElement('summary');manageTitle.textContent='管理构件资料'
 management.append(manageTitle,$('asset-edit-name').closest('label'),$('asset-edit-tags').closest('label'),$('asset-update'),$('asset-export'),$('asset-archive'))
 inspector.append(management)
 const overview=document.createElement('section');overview.className='asset-overview'
 inspector.prepend(overview);overview.append(assetFigure,management)
 const sourceNote=document.createElement('p');sourceNote.id='asset-source-note';sourceNote.className='asset-source-note';overview.prepend(sourceNote)
 const origin=document.createElement('section');origin.id='asset-origin';origin.className='asset-origin';origin.hidden=true
 const copyLocal=document.createElement('button');copyLocal.id='asset-copy-local';copyLocal.type='button';copyLocal.textContent='复制到本地编辑'
 const reloadSource=document.createElement('button');reloadSource.id='asset-reload-source';reloadSource.type='button';reloadSource.textContent='载入当前版本'
 origin.append(copyLocal,reloadSource);overview.append(origin)
 const placementAction=$('asset-place'),placementTarget=$('asset-target')
 const placementPrimary=document.createElement('div');placementPrimary.className='asset-placement-primary'
 placementPrimary.append(placementTarget,placementAction)
 overview.insertBefore(placementPrimary,management)
 const parameters=document.createElement('div');overview.insertBefore(parameters,management)
 assetPreview=createAssetPreview({figure:assetFigure,overview,parameterHost:parameters,api,active:()=>inspectorDialog.open,onState:controls})
 async function placementOptions(){
  const item=selected
  if(!item||item.archived)throw Error('请选择可用构件')
  const reference=item.library_ref?assetPreview.request():null
  const component=reference?(await api('asset-libraries/resolve',reference)).component:await api('components/get',{id:item.id})
  const {items:recipes}=await api('recipes')
  const themes=recipes.filter(recipe=>recipe.asset_type==='theme'&&!recipe.archived).map(({name,id})=>({label:name,value:id}))
  return {item,component,options:{placement:true,...(reference?{library:reference}:{id:item.id}),themes}}
 }
 copyLocal.onclick=async()=>{
  try{await perform(async()=>{
   const result=await api('asset-libraries/copy',assetPreview.request())
   selected=result.item;sourceFilter.value='local';contentFilter.value='component';category='all';$('asset-search').value=''
   await refresh(true);management.open=true;message('已生成待审阅的本地副本，可编辑名称、标签并继续放置。')
  });$('asset-edit-name').focus()}catch(error){message(error.message,true)}
 }
 reloadSource.onclick=async()=>{
  try{await perform(async()=>{await refresh(true);if(selected)message('当前版本资料已载入，请核对参数和预览。')})}
  catch(error){message(error.message,true)}
 }
 inspectorDialog.addEventListener('close',()=>{
  assetPreview.close()
  queueMicrotask(()=>{
   if(document.body.dataset.workspace!=='assets'||document.querySelector('dialog[open]'))return
   const card=[...$('asset-grid').querySelectorAll('.asset-card')].find(card=>card.dataset.assetId===selected?.id)
   ;(card??$('asset-search')).focus({preventScroll:true})
  })
 })
 function openSave(){
  const c=context();if(!c?.target_id)throw Error('请先打开3D，并在修改范围中选择要保存的局部选区')
  if(c.whole)throw Error('请先在“修改范围”关闭整座建筑并指定构件选区')
  saveContext=structuredClone(c);$('asset-save-name').value='';$('asset-save-error').textContent='';$('asset-save-range').textContent=`选区 ${c.lo.join(', ')} → ${c.hi.join(', ')}；锚点默认为底部中心`;save.showModal();$('asset-save-name').focus()
 }
 const safe=action=>async()=>{try{await perform(action)}catch(error){message(error.message,true)}}
 window.addEventListener('creator-editor-state',controls)
 $('asset-save-cancel').onclick=()=>save.close()
 $('asset-save-confirm').onclick=async()=>{try{await perform(async()=>{const current=context();if(!current||current.target_id!==saveContext?.target_id)throw Error('显示的模型已改变，请重新选择选区');const result=await api('components/save',{target_id:saveContext.target_id,name:$('asset-save-name').value,tags:tags($('asset-save-tags').value),lo:saveContext.lo,hi:saveContext.hi,include_air:$('asset-save-air').checked});save.close();window.creatorWorkspace.select('assets');selected=result;await refresh(true);message('构件已保存到当前工作区，可复用于其他建筑')})}catch(error){$('asset-save-error').textContent=error.message}}
 $('asset-refresh').onclick=safe(()=>refresh());$('asset-search').oninput=()=>{limit=24;render()};$('asset-trash').onchange=()=>{selected=null;limit=24;render();details()};$('asset-more').onclick=()=>{limit+=24;render()}
 $('asset-update').onclick=safe(async()=>{if(!selected)throw Error('请选择构件');await api('components/update',{id:selected.id,name:$('asset-edit-name').value,tags:tags($('asset-edit-tags').value)});await refresh();message('名称与标签已保存')})
 $('asset-archive').onclick=safe(async()=>{if(!selected)return;const archived=!selected.archived;await api('components/update',{id:selected.id,archived});selected=null;await refresh();message(archived?'构件已移入回收站，可勾选回收站恢复':'构件已恢复')})
 $('asset-import').onclick=()=>$('asset-import-file').click();$('asset-import-file').onchange=safe(async()=>{const file=$('asset-import-file').files[0];if(!file)return;if(file.size>8*1024*1024)throw Error('构件文件超过8 MiB');const component=JSON.parse(await file.text()),result=await api('components/import',{component});selected=result;await refresh(true);message('构件已导入')})
 $('asset-place').onclick=safe(async()=>{
  const {item,component,options}=await placementOptions()
  if(context()){await interactive(component,options);return}
  inspectorDialog.close()
  chooseTarget(item.name,()=>interactive(component,options).catch(error=>message(error.message,true)),()=>{window.creatorWorkspace.select('assets');inspectItem(item)})
 })
 window.addEventListener('creator-workspace-change',event=>{if(event.detail==='assets'){target();if(!pending)refresh().catch(e=>message(e.message))}else if(inspectorDialog.open)inspectorDialog.close()})
 window.addEventListener('creator-asset-groups-change',()=>{if(host.dataset.kind==='components')render()})
 const open=document.createElement('button'),capture=document.createElement('button');open.id='open-assets';open.textContent='放置构件';capture.id='save-selection-asset';capture.textContent='选区存为构件';for(const button of [open,capture])button.type='button'
 open.onclick=()=>window.creatorWorkspace.select('assets');capture.onclick=()=>{try{openSave()}catch(e){message(e.message);window.creatorWorkspace.select('assets')}}
 document.querySelector('.review-toolbar').append(open,capture)
 for(const [id,label,move]of [['copy-selection-3d','复制选区并调整',false],['move-selection-3d','移动选区并调整',true]]){const button=document.createElement('button');button.id=id;button.type='button';button.textContent=label;button.onclick=()=>interactive(null,{selection:true,move}).catch(error=>{message(error.message);window.creatorWorkspace.select('assets')});document.querySelector('.review-toolbar').append(button)}
 initAssetBatches({api,host,refresh})
 return {refresh,openSave}
}
