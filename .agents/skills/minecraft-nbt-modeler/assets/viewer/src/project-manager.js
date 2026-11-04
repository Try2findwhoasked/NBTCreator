import './project-manager.css'
import {initBatchWorkspaces} from './batch-workspaces.js'
import {filterProjects,latestSources,projectStage,DEFAULT_PROJECT_STAGES,includesDiscarded} from './project-catalog.js'
import {createProjectTree} from './project-tree.js'
import {checkboxFilter} from './project-filters.js'
import {initLibraryBrowser} from './library-browser.js'
import {floatingDetails,chevron} from './floating-panel.js'
import {initProjectBatch} from './project-batch.js'

// Browsing and read-only previews never change the editor's selected source.
export function initProjectManager({api,openModel,isBusy,setBusy,refresh}){
 const host=document.createElement('section');host.id='project-workspace';host.hidden=true
 host.innerHTML=`<header class="project-heading"><div><h1>项目管理</h1><p>浏览当前工作区的建筑，预览后进入模型编辑。</p></div><div id="project-native-actions"></div></header>
 <div class="project-toolbar"><label class="project-search">查找建筑<input id="project-search" type="search" placeholder="建筑名、项目、版本或路径"></label><button id="project-refresh" type="button">刷新建筑库</button></div>
 <div class="project-layout"><aside id="project-tree" aria-label="项目、形状与对象"></aside><main class="project-library"><div class="project-filters" id="project-filter-controls"><button id="project-clear" type="button">重置筛选</button></div><p id="project-count" class="muted" role="status"></p><p id="project-loading" role="status">正在读取建筑库…</p><p id="project-breadcrumb"></p><div id="project-grid" class="project-grid"></div><button id="project-more" type="button" hidden>加载更多</button><p id="project-status" role="status"></p></main></div>`
 document.querySelector('.creator-header').after(host)
 const dialog=document.createElement('dialog');dialog.id='project-preview-dialog'
 dialog.innerHTML='<header><div><h2 id="project-preview-title">建筑预览</h2><p id="project-preview-meta"></p></div><button id="project-preview-close" type="button" aria-label="关闭建筑预览">关闭</button></header><div class="project-preview-stage"><img id="project-preview-image" alt="建筑预览" hidden><iframe id="project-preview-3d" title="项目建筑只读3D预览" src="about:blank" hidden></iframe><p id="project-preview-status" role="status"></p></div><footer><span>只读预览，进入模型编辑后可标注和调整。</span><button id="project-preview-render" type="button">打开 3D 预览</button><button id="project-preview-edit" class="primary" type="button">进入模型编辑</button></footer>'
 document.body.append(dialog)
 const $=id=>document.getElementById(id),covers=new Map()
 let thumbnailRun=null
 let treeModels=null,treeShowDiscarded=false,batch=null,workspaces=null,visibleModels=[]
 let models=[],workspace='',limit=24,generation=0,selected=null,previewGeneration=0,previewBusy=false,object='',catalogLoading=true,latest=new Set(),coverQueue=[],activeCovers=0,searchTimer
 const message=text=>$('project-status').textContent=text
 const coverTargets=new WeakMap()
 const coverObserver=new IntersectionObserver(entries=>{for(const entry of entries)if(entry.isIntersecting){const task=coverTargets.get(entry.target);coverObserver.unobserve(entry.target);if(task)coverQueue.push(task)}pumpCovers()},{root:host,rootMargin:'160px'})
 const stageLabels={unrefined:'未精修',refined:'已精修',finalized:'已定稿',discarded:'废稿'}
 const change=()=>{object='';limit=24;render()}
 const addFilter=(id,label,options,defaults)=>checkboxFilter({host:$('project-filter-controls'),id,label,options,defaults,onChange:change})
 const filters={project:addFilter('project-filter','项目',[],['all']),shape:addFilter('project-shape','形状',[],['all']),stage:addFilter('project-stage','创作阶段',Object.entries(stageLabels),DEFAULT_PROJECT_STAGES),version:addFilter('project-version','版本范围',[['latest','最新版本'],['older','历史版本'],['intermediate','中间稿']],['latest']),readability:addFilter('project-readability','文件状态',[['readable','已检查可打开'],['unverified','待检查'],['unreadable','无法读取']],['all'])}
 $('project-filter-controls').append($('project-clear'))
 const native=$('project-native-actions'),workspaceMenu=document.createElement('details');workspaceMenu.id='project-workspace-menu';workspaceMenu.className='library-filter-menu';workspaceMenu.innerHTML='<summary>工作区'+chevron+'</summary><div id="project-workspace-menu-content" class="library-workspace-panel"><p>切换整个项目目录。当前目录中的建筑、构件、Skill 与应用配置一起使用。</p></div>';native.append(workspaceMenu)
 const library=initLibraryBrowser({host,prefix:'project',title:'项目管理',description:'按项目、形状与对象浏览建筑。点击卡片进入模型编辑；“预览”先打开只读视图。筛选支持组合选择，废稿默认隐藏。工作区路径和切换入口收在右上的“工作区”中。',search:$('project-search'),refresh:$('project-refresh'),actions:native,filters:$('project-filter-controls'),tree:$('project-tree'),main:host.querySelector('.project-library'),count:$('project-count'),breadcrumb:$('project-breadcrumb'),loading:$('project-loading')})
 const thumbnails=document.createElement('button');thumbnails.id='project-generate-thumbnails';thumbnails.type='button';thumbnails.textContent='生成并加载缩略图';library.toolbar.append(thumbnails)
 thumbnails.onclick=async()=>{
  if(thumbnailRun){thumbnailRun.cancelled=true;thumbnails.textContent='正在停止…';return}
  if(isBusy()){message('请等待当前任务完成');return}
  const run={cancelled:false,workspace,items:visibleModels.filter(item=>!item.unreadable)},total=run.items.length;thumbnailRun=run;let cursor=0,complete=0,failed=0
  thumbnails.textContent='停止生成缩略图'
  const worker=async()=>{while(!run.cancelled&&cursor<total&&workspace===run.workspace){const item=run.items[cursor++];try{const result=await cover(item,true);if(workspace!==run.workspace)break;for(const card of $('project-grid').children)if(card.dataset.source===item.source)displayCover(card.querySelector('.project-cover'),result,item);if(!result.thumbnail)throw Error('没有可用缩略图');complete++}catch{failed++}if(workspace===run.workspace)message(`缩略图：${complete+failed}/${total}，${complete} 项完成，${failed} 项失败`)}}
  try{await Promise.all([worker(),worker()]);if(workspace===run.workspace)message(`缩略图${run.cancelled?'已停止':'已完成'}：${complete} 项成功，${failed} 项失败；缓存会随滚动自动加载`)}finally{if(thumbnailRun===run){thumbnailRun=null;thumbnails.textContent='生成并加载缩略图'}}
 }
 const autoMore=document.createElement('label');autoMore.className='inline';autoMore.innerHTML='<input id="project-auto-more" type="checkbox" checked>滚动自动加载更多';library.toolbar.append(autoMore)
 const moreObserver=new IntersectionObserver(entries=>{if(entries.some(entry=>entry.isIntersecting)&&document.body.dataset.workspace==='project'&&$('project-auto-more').checked&&!$('project-more').hidden){limit+=24;render(true)}},{root:library.main,rootMargin:'240px'});moreObserver.observe($('project-more'))
 $('project-refresh').textContent='刷新';floatingDetails(workspaceMenu,$('project-workspace-menu-content'),{minimum:360})
 const treeView=createProjectTree({container:$('project-tree'),api,onStatus:message,onOrderChange:render,onOpen:edit,onSelect:value=>{filters.project.set(value.project==='*'?['all']:[value.project]);filters.shape.set(value.shape==='*'?['all']:[value.shape]);object=value.object;$('project-search').value='';limit=24;render()}})
 batch=initProjectBatch({host,api,library,getVisible:()=>visibleModels,getModels:()=>models,render,isBusy,setBusy,refresh,message})
 workspaces=initBatchWorkspaces({host,api,getModels:()=>models,openModel:edit,previewModel:showPreview,render})
 async function edit(item){
  let opening=false
  try{if(isBusy()||previewBusy)throw Error('请等待当前任务完成');if(item.unreadable)throw Error(item.error||'此模型文件无法读取');opening=true;if(dialog.open)dialog.close();const info=await openModel(item);if(info){item.unverified=false;item.geometry_sha256=info.geometry_sha256;item.size=info.size}if(dialog.open)dialog.close();await workspaces?.seen(item.source).catch(error=>message('模型已打开；批次标记未更新：'+error.message));return true}
  catch(e){if(opening&&item.unverified&&!(e instanceof TypeError)){item.unverified=false;item.unreadable=true;item.error=e.message;latest=latestSources(models);render()}if(dialog.open)$('project-preview-status').textContent=e.message;else message(e.message);return false}
 }
 function cover(item,generate=false){
  const key=JSON.stringify([item.source,item.geometry_sha256,item.modified_ns,item.file_size,generate])
  if(!covers.has(key))covers.set(key,api('project-cover',{source:item.source,geometry:item.geometry_sha256,generate}).catch(e=>{covers.delete(key);throw e}))
  return covers.get(key)
 }
 function displayCover(node,result,item){
  if(result.thumbnail){const img=document.createElement('img');img.src=result.thumbnail;img.alt=item.object_name||item.name_zh||item.name||item.label;img.decoding='async';img.onerror=()=>{node.textContent='图片无法读取 · 点击预览重试'};node.replaceChildren(img)}
  else node.textContent='暂无当前版本预览 · 点击预览生成'
 }

 function pumpCovers(){
  if(document.body.dataset.workspace!=='project')return
  while(activeCovers<2&&coverQueue.length){
   const task=coverQueue.shift(),{item,node,token}=task
   if(token!==generation||!node.isConnected)continue
   activeCovers++
   cover(item).then(result=>{if(token!==generation||!node.isConnected)return;displayCover(node,result,item)}).catch(()=>{if(token===generation&&node.isConnected)node.textContent='预览暂不可用；可打开 3D'}).finally(()=>{activeCovers--;pumpCovers()})
  }
 }
 function render(append=false){
  const showDiscarded=includesDiscarded(filters.stage.get())
  const browsingModels=showDiscarded?models:models.filter(item=>projectStage(item)!=='discarded')
  latest=latestSources(browsingModels)
  if(treeModels!==models||treeShowDiscarded!==showDiscarded){treeModels=models;treeShowDiscarded=showDiscarded;treeView.update(browsingModels)}
  const scrollTop=library.main.scrollTop,token=append?generation:++generation
  if(!append){coverObserver.disconnect();coverQueue=[]}
  const visible=filterProjects(models,{project:filters.project.get(),shape:filters.shape.get(),object,version:filters.version.get(),readability:filters.readability.get(),stage:filters.stage.get(),query:$('project-search').value},latest)
  const order=new Map(treeView.orderedObjects().map((key,index)=>[key,index]))
  visible.sort((a,b)=>(order.get(a.object_key||a.group||a.source)??Infinity)-(order.get(b.object_key||b.group||b.source)??Infinity)||Number(a.is_delivery)-Number(b.is_delivery)||Number(latest.has(b.source))-Number(latest.has(a.source)))
  visibleModels=visible
  treeView.select({project:filters.project.get().length===1?filters.project.get()[0]:'*',shape:filters.shape.get().length===1?filters.shape.get()[0]:'*',object})
  $('project-count').textContent=`${visible.length} 个版本 · 建筑库共 ${latest.size} 个对象 / ${models.length} 个版本 · ${models.filter(item=>item.bugged).length} 个 bugged 版本`
  const selectedObject=models.find(item=>(item.object_key||item.group||item.source)===object)
  $('project-breadcrumb').textContent=[selectedObject?.project_name,selectedObject?.shape_group_zh,selectedObject?.object_name||selectedObject?.name_zh||selectedObject?.name].filter(Boolean).join(' / ')
  const start=append?$('project-grid').querySelectorAll('.project-card').length:0
  if(!append)$('project-grid').replaceChildren();$('project-more').hidden=visible.length<=limit
  const entries=[]
  for(const item of visible.slice(start,limit)){
   const card=document.createElement('article');card.className='project-card';card.dataset.source=item.source
   const main=document.createElement('button');main.type='button';main.className='project-card-open';main.title=(batch?.active?'选择版本：':'进入模型编辑：')+item.source;main.onclick=()=>batch?.active?batch.toggle(item):edit(item)
   const thumb=document.createElement('span');thumb.className='project-cover';thumb.textContent='NBT · 点击进入模型编辑'
   const title=document.createElement('strong');title.textContent=item.object_name||item.name_zh||item.name||item.label
   const meta=document.createElement('span');meta.className='project-card-meta';meta.textContent=[item.shape_group_zh,item.size?.join(' × '),item.version,latest.has(item.source)?'最新保存':'历史版本',item.intermediate?'中间稿':'',item.is_delivery?'交付副本':'',item.bugged?'待修复':'',item.unverified?'待检查':'',stageLabels[projectStage(item)]].filter(Boolean).join(' · ')
   const location=document.createElement('span');location.className='project-card-path';location.textContent=item.relative_path||item.label;location.title=item.source
   main.append(thumb,title,meta,location)
   const preview=document.createElement('button');preview.type='button';preview.className='project-card-preview';preview.textContent=item.unreadable?'查看原因':'预览';preview.onclick=()=>item.unreadable?message(item.relative_path+'：'+item.error):showPreview(item)
   if(item.unreadable){main.setAttribute('aria-disabled','true');thumb.textContent='文件无法读取';location.textContent=item.error;location.title=item.error;card.classList.add('project-unreadable')}
   const stage=document.createElement('select');stage.className='project-card-stage';stage.setAttribute('aria-label','创作状态：'+(item.object_name||item.name_zh||item.name));stage.add(new Option('自动判断：'+stageLabels[projectStage({...item,stage:item.stage_manual?item.stage_auto:item.stage})],'auto'));for(const [key,label]of Object.entries(stageLabels))stage.add(new Option(label,key));stage.value=item.stage_manual?item.stage:'auto';stage.title='仅标记此文件的创作进度，不代表精修授权或验收通过';stage.onchange=async()=>{const value=stage.value;stage.disabled=true;try{await api('project-stage',{source:item.source,stage:value});if(value==='auto'){item.stage=item.stage_auto;delete item.stage_manual}else{if(!item.stage_manual)item.stage_auto=item.stage;item.stage=value;item.stage_manual=true}treeModels=null;render();message('创作状态已保存；文件变化后需重新确认')}catch(error){message(error.message);stage.disabled=false}}
   card.append(main,stage,preview);
   if(item.bugged||item.unreadable){
    const actions=document.createElement('div');actions.className='project-repair-actions';const category=document.createElement('select');category.className='project-repair-category';category.setAttribute('aria-label','修复后归类');for(const [value,label]of [['auto','参考原分类（无资料则独立结构）'],['single','单格'],['long','长条'],['square','方形'],['l_shape','L形'],['t_shape','T形'],['cross','十字'],['standalone','独立结构'],['irregular','不规则']])category.add(new Option(label,value));const repair=document.createElement('button');repair.type='button';repair.className='project-repair';repair.textContent='尝试修复并归类';repair.title='保留原文件，恢复可确定的数据为新主模型候选；不自动导出NBT'
    repair.onclick=async()=>{if(isBusy()||thumbnailRun){message('请等待当前任务结束');return}repair.disabled=true;category.disabled=true;setBusy(true);let result;try{message('正在检查格式并尝试恢复；原文件保留…');result=await api('project-repair',{source:item.source,category:category.value,file_size:item.file_size,modified_ns:item.modified_ns});if(result.status==='recovered_candidate'){setBusy(false);await refresh();filters.shape.set([result.category]);filters.project.set(['all']);filters.stage.reset();filters.readability.reset();filters.version.set(['latest']);object='';$('project-search').value='';limit=24;render();message('已生成归类候选：'+result.candidate+'。请看图检查，尚未导出NBT。报告：'+result.report)}else message('未能自动恢复：'+result.error+'。原文件保留；报告：'+result.report)}catch(error){message('修复未完成：'+error.message)}finally{setBusy(false);repair.disabled=false;category.disabled=false}}
    actions.append(category,repair);card.append(actions)
   }
batch?.decorate(card,item);workspaces?.decorate(card,item);$('project-grid').append(card);entries.push({item,node:thumb,card,token})
  }
  if(!visible.length){const empty=document.createElement('p');empty.className='project-empty';empty.textContent=catalogLoading&&!models.length?'正在扫描建筑库，可先切换到其他工作区。':models.length?'没有匹配的建筑，试试清空搜索或重置筛选。':`当前工作区还没有建筑。可打开 NBT，或前往“提示词方案”为首次建模编写方案。建筑库按 Skill 规范保存在工作区的 nbt_models 中。`;if(!models.length&&!catalogLoading){const create=document.createElement('button');create.type='button';create.textContent='编写首次建模方案';create.onclick=()=>window.creatorWorkspace?.select('prompt');empty.append(document.createElement('br'),create)}$('project-grid').append(empty)}
  for(const task of entries){if(task.item.unreadable){task.node.textContent='文件无法读取';continue}coverTargets.set(task.card,task);if(document.body.dataset.workspace==='project')coverObserver.observe(task.card)}
  library.main.scrollTop=scrollTop
 }
 async function showPreview(item){
  if(isBusy()||previewBusy){message('请等待当前任务完成');return false}
  selected=item;const token=++previewGeneration
  let taskLink=dialog.querySelector('#project-preview-task-link');if(!taskLink){taskLink=document.createElement('div');taskLink.id='project-preview-task-link';dialog.querySelector('footer').prepend(taskLink)}taskLink.replaceChildren();const batchLink=workspaces?.previewLink(item.source);if(batchLink)taskLink.append(batchLink)
  $('project-preview-title').textContent=item.object_name||item.name_zh||item.name||item.label;$('project-preview-meta').textContent=[item.size?.join(' × '),item.version,item.relative_path].filter(Boolean).join(' · ')
  $('project-preview-image').hidden=true;$('project-preview-3d').hidden=true;$('project-preview-3d').src='about:blank';$('project-preview-status').textContent='正在读取截面预览；首次缺图时会生成并缓存…';dialog.showModal()
  if(window.nbtPreviewPreferences?.mode!=='images'){const shown=await render3D();if(shown)await workspaces?.seen(item.source).catch(error=>message(error.message));return shown}
  try{const result=await cover(item,true);if(token!==previewGeneration||!dialog.open)return false
   if(result.image){$('project-preview-image').src=result.image;$('project-preview-image').hidden=false;$('project-preview-status').textContent=result.generated?'当前版本截面示意图 · 已缓存（简化材质）':result.section?'整体截面预览 · 已缓存':'当前版本尚无截面渲染图，显示已有渲染图'}
   else if(await render3D()===false)return false
   for(const card of $('project-grid').querySelectorAll('.project-card'))if(card.dataset.source===item.source)displayCover(card.querySelector('.project-cover'),result,item)
   covers.clear();await workspaces?.seen(item.source).catch(error=>message(error.message));return true
  }catch(e){if(token===previewGeneration&&dialog.open)$('project-preview-status').textContent=e.message+'；可尝试打开 3D 预览。';return false}
 }
 async function render3D(){
  if(!selected||previewBusy||isBusy())return false
  const token=previewGeneration,item=selected;previewBusy=true;setBusy(true);$('project-preview-close').disabled=false
  $('project-preview-status').textContent='正在读取 NBT 并准备 3D 预览…'
  try{
   const {id}=await api('jobs',{kind:'snapshot',request:{source:item.source,context:'',cameras:'',settings:{}}})
   let job
   do{await new Promise(resolve=>setTimeout(resolve,400));job=await api('jobs/'+id)}while(job.status==='running')
   if(job.status!=='complete')throw Error(job.error||'3D 预览未完成')
   if(token!==previewGeneration||!dialog.open)return
   const frame=$('project-preview-3d');frame.src=`/?model_key=${encodeURIComponent(job.result.model_key)}&embedded=1&quality=${encodeURIComponent(window.nbtPreviewPreferences?.quality??'balanced')}&pixelRatio=0.75&maxFps=24`;frame.hidden=false;$('project-preview-image').hidden=true;$('project-preview-status').textContent='左键原地转向，中键平移，滚轮沿视线前进／后退。此处仅预览，不修改建筑。';return true
  }catch(e){if(token===previewGeneration&&dialog.open)$('project-preview-status').textContent=e.message;return false}
  finally{previewBusy=false;setBusy(false)}
 }
 function populateFilters(){
  const projects=new Map(models.map(item=>[item.project_key,item.project_name])),shapes=new Map(models.map(item=>[item.shape_group,item.shape_group_zh]));shapes.set('bugged','bugged（待修复）')
  for(const [filter,entries]of [[filters.project,projects],[filters.shape,shapes]])filter.options([...entries].sort((a,b)=>Number(a[0]==='bugged')-Number(b[0]==='bugged')||a[1].localeCompare(b[1],'zh-CN')))
 }
 $('project-search').oninput=()=>{clearTimeout(searchTimer);searchTimer=setTimeout(()=>{limit=24;render()},120)}
 $('project-clear').onclick=()=>{for(const filter of Object.values(filters))filter.reset();$('project-search').value='';object='';limit=24;render()}
 $('project-more').onclick=()=>{limit+=24;render(true)}
 $('project-refresh').onclick=async()=>{try{message('正在刷新建筑库…');covers.clear();await refresh();await workspaces?.refresh();message('建筑库已刷新')}catch(e){message(e.message)}}
 $('project-preview-close').onclick=()=>dialog.close();$('project-preview-render').onclick=render3D;$('project-preview-edit').onclick=()=>edit(selected)
 dialog.addEventListener('close',()=>{previewGeneration++;$('project-preview-3d').src='about:blank';$('project-preview-3d').hidden=true;$('project-preview-image').removeAttribute('src')})
 window.addEventListener('creator-workspace-change',event=>{if(event.detail==='project')render();else{if(thumbnailRun)thumbnailRun.cancelled=true;generation++;coverObserver.disconnect();coverQueue=[];if(dialog.open)dialog.close()}})
 return {checked(info){for(const item of models)if(item.source===info.source){item.unverified=false;item.unreadable=false;item.geometry_sha256=info.geometry_sha256;item.size=info.size}latest=latestSources(models);if(document.body.dataset.workspace==='project')render()},setLoading(text){catalogLoading=!!text;$('project-loading').textContent=text;$('project-refresh').disabled=catalogLoading;host.setAttribute('aria-busy',String(catalogLoading&&!models.length))},update(items,root){models=items;batch?.update();latest=latestSources(models);workspace=root;workspaces?.update(workspace);host.dataset.workspaceRoot=workspace;populateFilters();render()}}
}
