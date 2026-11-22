import './project-manager.css'
import {createComparison} from '../library/library-comparison.js'
import {initProjectOrganization} from './project-organization.js'
import {initBatchWorkspaces} from './batch-workspaces.js'
import {filterProjects,latestSources,matchesProjectConstraint,projectStage,DEFAULT_PROJECT_STAGES,includesDiscarded} from './project-catalog.js'
import {createProjectTree} from './project-tree.js'
import {checkboxFilter} from './project-filters.js'
import {initLibraryBrowser} from '../library/library-browser.js'
import {floatingDetails,chevron} from '../floating-panel.js'
import {initProjectBatch} from './project-batch.js'
import {initBuildingHistory} from './building-history.js'
import {initProjectConstraints} from './project-constraints.js'

// Browsing and read-only previews never change the editor's selected source.
export function initProjectManager({api,openModel,isBusy,setBusy,refresh,historyContext=()=>null,historyCompare=()=>{}}){
 const host=document.createElement('section');host.id='project-workspace';host.hidden=true
 host.innerHTML=`<header class="project-heading"><div><h1>项目管理</h1><p>浏览当前工作区的建筑，预览后进入模型编辑。</p></div><div id="project-native-actions"></div></header>
 <div class="project-toolbar"><label class="project-search">查找建筑<input id="project-search" type="search" placeholder="建筑名、项目、版本或路径"></label><button id="project-refresh" type="button">刷新建筑库</button></div>
 <div class="project-layout"><aside id="project-tree" aria-label="项目、形状与对象"></aside><main class="project-library"><div class="project-filters" id="project-filter-controls"><button id="project-clear" type="button">重置筛选</button></div><p id="project-count" class="muted" role="status"></p><p id="project-loading" role="status">正在读取建筑库…</p><p id="project-breadcrumb"></p><div id="project-grid" class="project-grid"></div><button id="project-more" type="button" hidden>加载更多</button><p id="project-status" role="status"></p></main></div>`
 document.querySelector('.creator-header').after(host)
 const dialog=document.createElement('dialog');dialog.id='project-preview-dialog';dialog.setAttribute('aria-labelledby','project-preview-title')
 dialog.innerHTML='<header><div><h2 id="project-preview-title">建筑预览</h2><p id="project-preview-meta"></p></div><button id="project-preview-close" type="button" aria-label="关闭建筑详情">关闭</button></header><div class="project-detail-body"><div class="project-preview-stage"><img id="project-preview-image" alt="建筑预览" hidden><iframe id="project-preview-3d" title="项目建筑只读3D预览" src="about:blank" hidden></iframe><p id="project-preview-status" role="status"></p></div><aside class="project-detail-management" aria-label="建筑管理"><h3>建筑管理</h3><p>选择后自动保存，归组不移动文件。</p><div id="project-preview-management"></div><details><summary>文件位置与版本</summary><p id="project-preview-location" class="path"></p></details><p id="project-manage-status" role="status"></p></aside></div><footer><span>预览不修改建筑；需要调整模型时进入编辑。</span><button id="project-preview-render" type="button">打开 3D 预览</button><button id="project-preview-edit" class="primary" type="button">进入模型编辑</button></footer>'
 document.body.append(dialog)
 const $=id=>document.getElementById(id),covers=new Map()
 const history=initBuildingHistory({api,openModel,refresh,isBusy,context:historyContext,compare:historyCompare})
 let thumbnailRun=null
 let treeModels=null,treeShowDiscarded=false,batch=null,workspaces=null,visibleModels=[]
 let models=[],workspace='',limit=24,generation=0,selected=null,previewGeneration=0,previewBusy=false,object='',catalogLoading=true,latest=new Set(),coverQueue=[],activeCovers=0,searchTimer
 let constraintFolders=[],constraintFolder='',treeSelection=null
 let layoutProjects=[],constraintGroups=[],layoutRooms=[]
 const shapeNames=Object.fromEntries(Object.entries(globalThis.NbtToolCatalog.building_shapes).map(([key,shape])=>[key,shape.library_label??shape.label]))
 function foldersFor(items,paths,scopes=[]){
  const folders=new Map()
  const projectFolder=(project,label)=>{
   const folder=['nbt_models',project].filter(Boolean).join('/')
   folders.set(folder,{folder,project,projectLabel:label,label})
   return folder
  }
  for(const item of items){
   const {project_key:project,project_name:label,shape_group:shape}=item
   if(typeof project!=='string')continue
   const parent=projectFolder(project,label)
   if(item.room_id)continue
   if(Object.hasOwn(shapeNames,shape)){
    const folder=parent+'/'+shape
   const relative=item.relative_path?.replaceAll('\\','/')??'',prefix=folder.slice('nbt_models/'.length)+'/'
   if(relative.startsWith(prefix)){
    folders.set(folder,{folder,project,shape,projectLabel:label,shapeLabel:shapeNames[shape],label:`${label} / ${shapeNames[shape]}`})
    const objectName=relative.slice(prefix.length).split('/')[0]
    if(objectName){const child=folder+'/'+objectName;folders.set(child,{folder:child,project,shape,object:item.object_key||item.group||item.source,projectLabel:label,shapeLabel:shapeNames[shape],label:`${label} / ${shapeNames[shape]} / ${objectName}`})}
   }
   }
  }
  for(const folder of paths){
   const parts=folder.split('/').slice(1),shapeIndex=parts.findIndex(part=>Object.hasOwn(shapeNames,part)),project=(shapeIndex<0?parts:parts.slice(0,shapeIndex)).join('/'),shape=shapeIndex<0?null:parts[shapeIndex]
   const label=project||folders.get('nbt_models')?.label||workspace.split(/[\\/]/).at(-1)||'工作区根目录'
   projectFolder(project,label)
   if(shape){const base=['nbt_models',project,shape].filter(Boolean).join('/');folders.set(base,{folder:base,project,shape,projectLabel:label,shapeLabel:shapeNames[shape],label:`${label} / ${shapeNames[shape]}`});const objectName=parts.slice(shapeIndex+1).join('/');if(objectName){const prior=folders.get(folder);folders.set(folder,{folder,project,shape,object:prior?.object??objectName,projectLabel:label,shapeLabel:shapeNames[shape],label:`${label} / ${shapeNames[shape]} / ${objectName}`})}}
  }
  for(const item of scopes){
   const projectLabel=folders.get(['nbt_models',item.project].filter(Boolean).join('/'))?.label??(item.project||'我的项目')
   const shapeLabel=shapeNames[item.shape]
   folders.set(item.folder,{...item,projectLabel,shapeLabel,label:[projectLabel,shapeLabel,item.name].filter(Boolean).join(' / ')})
  }
  return [...folders.values()].sort((a,b)=>a.folder.localeCompare(b.folder,'zh-CN'))
 }
 function constraintFolderFor(source){
  if(!source)return ''
  const normalize=value=>value.replaceAll('\\','/').replace(/^\.\//,'').toLowerCase()
  const relativeModel=item=>item.relative_path?'nbt_models/'+item.relative_path:''
  const key=normalize(source),item=models.find(model=>normalize(model.source)===key||normalize(relativeModel(model))===key)
  if(item?.room_folder)return item.room_folder
  if(!item?.relative_path)return ''
  const relative=normalize(relativeModel(item))
  let folder=''
  for(const entry of constraintFolders){
   if(entry.project===item.project_key&&entry.folder.length>folder.length&&relative.startsWith(normalize(entry.folder)+'/'))folder=entry.folder
  }
  return folder
 }
 function defaultConstraintFolder(){
  const projects=constraintFolders.filter(entry=>!entry.shape)
  return projects.length===1?projects[0].folder:''
 }
 function layoutProject(folder){
  return layoutProjects.filter(project=>folder===project||folder.startsWith(project+'/')).sort((a,b)=>b.length-a.length)[0]??
    (!models.length&&constraintFolders.length===1&&constraintFolders[0].folder===folder?folder:'')
 }
 function draftConstraintScopes(folder){
  const project=constraintFolders.find(entry=>entry.folder===folder)?.project
  if(project===undefined)return []
  const folders=new Set(constraintGroups.filter(rule=>rule.project_key===project&&!rule.archived).map(rule=>rule.folder))
  return constraintFolders.filter(entry=>entry.project===project&&entry.shape&&!entry.object&&folders.has(entry.folder)).map(entry=>entry.folder)
 }
 const message=text=>{$('project-status').textContent=text;const note=document.getElementById('project-manage-status');if(note)note.textContent=text}
 const coverTargets=new WeakMap()
 const coverObserver=new IntersectionObserver(entries=>{for(const entry of entries)if(entry.isIntersecting){const task=coverTargets.get(entry.target);coverObserver.unobserve(entry.target);if(task)coverQueue.push(task)}pumpCovers()},{root:host,rootMargin:'160px'})
 const stageLabels={unrefined:'未精修',refined:'已精修',finalized:'已定稿',discarded:'废稿'}
 const change=()=>{object='';limit=24;render()}
 const addFilter=(id,label,options,defaults)=>checkboxFilter({host:$('project-filter-controls'),id,label,options,defaults,onChange:()=>{if(['project-filter','project-shape','project-constraint-filter'].includes(id))treeSelection=null;change()}})
 const filters={project:addFilter('project-filter','项目',[],['all']),shape:addFilter('project-shape','形状',[],['all']),constraint:addFilter('project-constraint-filter','约束',[],['all']),stage:addFilter('project-stage','创作阶段',Object.entries(stageLabels),DEFAULT_PROJECT_STAGES),version:addFilter('project-version','版本范围',[['latest','最新版本'],['older','历史版本'],['intermediate','中间稿']],['latest']),readability:addFilter('project-readability','文件状态',[['readable','已检查可打开'],['unverified','待检查'],['unreadable','无法读取']],['all'])}
 $('project-filter-controls').append($('project-clear'))
 const native=$('project-native-actions'),workspaceMenu=document.createElement('details');workspaceMenu.id='project-workspace-menu';workspaceMenu.className='library-filter-menu';workspaceMenu.innerHTML='<summary>工作区'+chevron+'</summary><div id="project-workspace-menu-content" class="library-workspace-panel"><p>切换整个项目目录。当前目录中的建筑、构件、Skill 与应用配置一起使用。</p></div>';native.append(workspaceMenu)
 const library=initLibraryBrowser({host,prefix:'project',title:'建筑库',description:'点击建筑卡片，在同一窗口预览、管理，或进入编辑。左侧切换项目，顶部可搜索名称和筛选版本；已弃用的草稿默认隐藏。“工作区”用于选择另一整个项目文件夹。',search:$('project-search'),refresh:$('project-refresh'),actions:native,filters:$('project-filter-controls'),tree:$('project-tree'),main:host.querySelector('.project-library'),count:$('project-count'),breadcrumb:$('project-breadcrumb'),loading:$('project-loading')})
 library.body.append(dialog)
 const displayName=item=>item.object_name||item.name_zh||item.name||item.label
 const compare=createComparison({
  host,grid:$('project-grid'),kind:'建筑版本',key:item=>item.source,name:item=>[displayName(item),item.version].filter(Boolean).join(' / '),
  fields:[['版本',item=>item.version],['项目',item=>item.project_name],['形状',item=>item.shape_group_zh],['尺寸（格）',item=>item.size?.join(' × ')],['创作阶段',item=>stageLabels[projectStage(item)]],['文件位置',item=>item.relative_path]],
  preview:async item=>item.unreadable?null:(await cover(item,true)).thumbnail,
  canComparePair:()=>!targetIntent,available:item=>!item.unreadable,openLabel:'打开建筑',open:edit,
  pairAction:async(reference,item)=>{
   try{if(await edit(item,{resumeTarget:false}))await historyCompare({reference_source:reference.source,source:item.source,source_sha256:historyContext()?.source_sha256})}
   catch(error){message(error.message)}
  }
 })
 library.scope.innerHTML='<label><select id="project-quick-version" aria-label="显示版本"><option value="latest">版本：最新</option><option value="older">版本：历史</option><option value="all">版本：全部</option><option value="custom" disabled>版本：自定义</option></select></label><span class="scope-summary"></span><button type="button" id="project-reset-view">恢复默认视图</button>'
 $('project-quick-version').onchange=event=>{filters.version.set([event.target.value]);change()}
 $('project-reset-view').onclick=()=>{$('project-clear').click();$('project-search').focus()}
 const targetRequest=document.createElement('section');targetRequest.className='library-target-request';targetRequest.hidden=true
 const targetHint=document.createElement('strong'),cancelTarget=document.createElement('button')
 cancelTarget.type='button';cancelTarget.textContent='取消选择';targetRequest.append(targetHint,cancelTarget);library.header.after(targetRequest)
 let targetIntent=null,openingTarget=false
 function clearTarget(){targetIntent=null;targetRequest.hidden=true}
 function chooseTarget(name,onOpen,onCancel){
  compare.reset()
  batch?.exit()
  targetIntent={onOpen,onCancel};targetHint.textContent='为“'+name+'”选择目标建筑';targetRequest.hidden=false
  window.creatorWorkspace.select('project')
 }
 cancelTarget.onclick=()=>{const cancel=targetIntent?.onCancel;clearTarget();cancel?.()}
 const thumbnails=document.createElement('button');thumbnails.id='project-generate-thumbnails';thumbnails.type='button';thumbnails.textContent='生成缩略图';library.toolbar.append(thumbnails)
 thumbnails.onclick=async()=>{
  if(thumbnailRun){thumbnailRun.cancelled=true;thumbnails.textContent='正在停止…';return}
  if(isBusy()){message('请等待当前任务完成');return}
  const run={cancelled:false,workspace,items:visibleModels.filter(item=>!item.unreadable&&!item.effect_file)},total=run.items.length;thumbnailRun=run;let cursor=0,complete=0,failed=0
  thumbnails.textContent='停止生成缩略图'
  const worker=async()=>{while(!run.cancelled&&cursor<total&&workspace===run.workspace){const item=run.items[cursor++];try{const result=await cover(item,true);if(workspace!==run.workspace)break;for(const card of $('project-grid').children)if(card.dataset.source===item.source)displayCover(card.querySelector('.project-cover'),result,item);if(!result.thumbnail)throw Error('没有可用缩略图');complete++}catch{failed++}if(workspace===run.workspace)message(`缩略图：${complete+failed}/${total}，${complete} 项完成，${failed} 项失败`)}}
  try{await Promise.all([worker(),worker()]);if(workspace===run.workspace)message(`缩略图${run.cancelled?'已停止':'已完成'}：${complete} 项成功，${failed} 项失败；缓存会随滚动自动加载`)}finally{if(thumbnailRun===run){thumbnailRun=null;thumbnails.textContent='生成缩略图'}}
 }
 const autoMore=document.createElement('label');autoMore.className='inline';autoMore.innerHTML='<input id="project-auto-more" type="checkbox" checked>自动加载更多';library.toolbar.append(autoMore)
 const moreObserver=new IntersectionObserver(entries=>{if(entries.some(entry=>entry.isIntersecting)&&document.body.dataset.workspace==='project'&&$('project-auto-more').checked&&!$('project-more').hidden){limit+=24;render(true)}},{root:library.main,rootMargin:'240px'});moreObserver.observe($('project-more'))
 $('project-refresh').textContent='刷新';floatingDetails(workspaceMenu,$('project-workspace-menu-content'),{minimum:360})
 function selectTreeFolder(value){
  treeSelection=value
  filters.project.set(value.project==='*'?['all']:[value.project]);filters.shape.set(value.shape==='*'?['all']:[value.shape])
  filters.constraint.reset()
  object=value.object;$('project-search').value='';limit=24;render()
 }
 const treeView=createProjectTree({container:$('project-tree'),api,onStatus:message,onOrderChange:render,onOpen:edit,onSelect:selectTreeFolder,onManageRoom:manageRoom})
 const constraints=initProjectConstraints({api,container:$('project-tree').querySelector('.project-tree-heading'),getFolders:()=>constraintFolders,getFolder:()=>constraintFolder,onFolderChange(folder){
  if(document.body.dataset.workspace==='prompt')return
  const entry=constraintFolders.find(item=>item.folder===folder)
  selectTreeFolder({project:entry?.project??'*',shape:entry?.shape??'*',object:''})
  if(entry)treeView.revealProject(entry.project)
 }})
 const organization=initProjectOrganization({api,container:$('project-tree'),message,changed:()=>{treeSelection=null;object='';filters.project.reset();filters.shape.reset();limit=24;treeModels=null;populateFilters();render()}})
 batch=initProjectBatch({host,api,library,getVisible:()=>visibleModels,getModels:()=>models,getConstraintGroups:()=>constraintGroups,render,isBusy,setBusy,refresh,message,organization})
 workspaces=initBatchWorkspaces({host,api,getModels:()=>models,openModel:edit,previewModel:showPreview,render})
 async function edit(item,{resumeTarget=true}={}){
  if(item.effect_file)return showEffect(item)
  let opening=false
  try{if(isBusy()||previewBusy)throw Error('请等待当前任务完成');if(item.unreadable)throw Error(item.error||'此模型文件无法读取');opening=true;if(dialog.open)dialog.close();openingTarget=!!targetIntent&&resumeTarget;const info=await openModel(item);if(info){item.unverified=false;item.geometry_sha256=info.geometry_sha256;item.size=info.size}if(dialog.open)dialog.close();await workspaces?.seen(item.source).catch(error=>message('模型已打开；批次标记未更新：'+error.message))
   if(resumeTarget&&targetIntent&&info){const resume=targetIntent.onOpen;clearTarget();opening=false;await resume(info)}
   return true}
  catch(e){if(opening&&item.unverified&&!(e instanceof TypeError)){item.unverified=false;item.unreadable=true;item.error=e.message;latest=latestSources(models);render()}if(dialog.open)$('project-preview-status').textContent=e.message;else message(e.message);return false}
  finally{openingTarget=false}
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
  const scopedModels=organization.filter(models.filter(item=>!item.trashed))
  const browsingModels=showDiscarded?scopedModels:scopedModels.filter(item=>projectStage(item)!=='discarded')
  latest=latestSources(browsingModels)
  if(treeModels!==models||treeShowDiscarded!==showDiscarded){treeModels=models;treeShowDiscarded=showDiscarded;treeView.update(browsingModels,constraintFolders,{layoutProjects,constraintGroups,rooms:layoutRooms})}
  const scrollTop=library.main.scrollTop,token=append?generation:++generation
  if(!append){coverObserver.disconnect();coverQueue=[]}
  const trash=!!batch?.trash,query=$('project-search').value
  const constraint=treeSelection?.constraint,rule=constraintGroups.find(group=>group.id===constraint)
  const inGroup=item=>constraint===undefined||(constraint==='unassigned'?!item.owner_constraint_id:rule&&matchesProjectConstraint(item,rule))
  const chosen=new Set(filters.constraint.get()),allConstraints=filters.constraint.isAll()
  const inConstraint=item=>allConstraints||(item.constraint_ids?.length?item.constraint_ids.some(id=>chosen.has(id)):chosen.has('unassigned'))
  const visible=trash?filterProjects(models.filter(item=>item.trashed),{version:'all',stage:'all',query}):filterProjects(scopedModels.filter(item=>inGroup(item)&&inConstraint(item)),{project:filters.project.get(),shape:filters.shape.get(),object,version:filters.version.get(),readability:filters.readability.get(),stage:filters.stage.get(),query},latest)
  const order=new Map(treeView.orderedObjects().map((key,index)=>[key,index]))
  visible.sort((a,b)=>(order.get(a.object_key||a.group||a.source)??Infinity)-(order.get(b.object_key||b.group||b.source)??Infinity)||Number(a.is_delivery)-Number(b.is_delivery)||Number(latest.has(b.source))-Number(latest.has(a.source)))
  visibleModels=visible
  batch?.sync()
  treeView.select({...treeSelection,project:treeSelection?.project??'*',shape:treeSelection?.shape??'*',object})
  const projectFolders=treeSelection&&constraintFolders.filter(entry=>entry.project===treeSelection.project)
  const scope=projectFolders&&(projectFolders.find(entry=>entry.object&&entry.object===treeSelection.object)??projectFolders.find(entry=>entry.folder===rule?.folder)??projectFolders.find(entry=>entry.shape===treeSelection.shape&&!entry.object)??projectFolders.find(entry=>!entry.shape))
  const nextFolder=scope?.folder??''
  if(nextFolder!==constraintFolder){constraintFolder=nextFolder;window.dispatchEvent(new CustomEvent('project-constraint-folder',{detail:nextFolder}))}
  constraints.scope(scope)
  const versions=filters.version.get()
  $('project-quick-version').value=versions.length===3?'all':versions.length===1&&['latest','older'].includes(versions[0])?versions[0]:'custom'
  const summary=Object.values(filters).map(filter=>filter.description()).filter(Boolean)
  if($('project-search').value.trim())summary.unshift('搜索“'+$('project-search').value.trim()+'”')
  library.scope.querySelector('.scope-summary').textContent=summary.join(' / ')
  library.scope.hidden=!summary.length&&!treeSelection&&!object&&!$('project-tree').querySelector('[data-custom-menu][aria-pressed=true]')
  $('project-count').textContent=trash?`回收站 · ${visible.length} 个版本`:`${visible.length} 个版本 / 库内共 ${models.filter(item=>!item.trashed).length} 个版本`
  const selectedObject=models.find(item=>(item.object_key||item.group||item.source)===object)
  const projectName=constraintFolders.filter(entry=>!entry.shape).length===1?'我的项目':scope?.projectLabel
  const objectName=selectedObject?.object_name||selectedObject?.name_zh||selectedObject?.name
  const groupName=rule?.name??(constraint==='unassigned'?'未归组':'')
  $('project-breadcrumb').textContent=groupName?[projectName,groupName,objectName].filter(Boolean).join(' / '):selectedObject?[projectName??selectedObject.project_name,selectedObject.shape_group_zh,objectName].filter(Boolean).join(' / '):scope?.label??''
  const start=append?$('project-grid').querySelectorAll('.project-card').length:0
  if(!append)$('project-grid').replaceChildren();$('project-more').hidden=visible.length<=limit
  const entries=[]
  for(const item of visible.slice(start,limit)){
   const card=document.createElement('article');card.className='project-card';card.dataset.source=item.source
   const main=document.createElement('button');main.type='button';main.className='project-card-open project-card-preview project-card-manage';main.title=(batch?.active||trash?'选择版本：':'查看与管理：')+item.source;main.onclick=()=>{if(batch?.active||trash){if(!batch.active)$('project-select').click();batch.toggle(item)}else showPreview(item)};main.ondblclick=()=>{if(!batch?.active&&!trash)edit(item)}
   const thumb=document.createElement('span');thumb.className='project-cover';thumb.textContent='NBT · 点击查看与管理'
   const title=document.createElement('strong');title.textContent=item.object_name||item.name_zh||item.name||item.label
   const meta=document.createElement('span');meta.className='project-card-meta';meta.textContent=[item.size?.join(' × '),item.bugged||item.unreadable?'待修复':stageLabels[projectStage(item)],item.version,latest.has(item.source)?'最新版本':'历史版本',item.is_delivery?'交付副本':''].filter(Boolean).join(' · ');meta.title=[item.shape_group_zh,item.version,item.relative_path].filter(Boolean).join(' · ')
   const location=document.createElement('span');location.className='project-card-path';location.textContent=item.relative_path||item.label;location.title=item.source
   main.append(thumb,title,meta,location)
   const preview=document.createElement('button');preview.type='button';preview.className='project-card-edit';preview.textContent=targetIntent?'选为目标建筑':'打开建筑';preview.disabled=!!item.unreadable||!!batch?.active;preview.onclick=()=>edit(item)
   if(item.unreadable){thumb.textContent='文件无法读取';location.textContent=item.error;location.title=item.error;card.classList.add('project-unreadable')}
   const footer=document.createElement('div');footer.className='project-card-footer';const controls=document.createElement('div');controls.className='project-card-actions';controls.append(preview);card.append(main,footer);footer.append(controls);footer.hidden=trash||!!batch?.active
   if(!trash&&!batch?.active){compare.decorate(card,item);workspaces?.decorate(card,item)}
   batch?.decorate(card,item);$('project-grid').append(card);entries.push({item,node:thumb,card,token})
  }
  if(!visible.length){
   const empty=document.createElement('section');empty.className='project-empty'
   const title=document.createElement('strong'),hint=document.createElement('p'),actions=document.createElement('div');actions.className='project-empty-actions'
   title.textContent=catalogLoading&&!models.length?'正在读取建筑':'还没有'+(models.length?'匹配的建筑':'第一座建筑')
   hint.textContent=catalogLoading&&!models.length?'可以先编写创作方案，建筑列表会在读取完成后更新。':models.length?'尝试换一个名称，或清除搜索和筛选条件。':'已有建筑可以用“打开 NBT”载入。想从头创作，先写下建筑要求，再交给建造助手。'
   const next=document.createElement('button');next.type='button';next.className='primary';next.textContent=models.length?'清除搜索与筛选':'编写创作方案';next.onclick=()=>{if(models.length){$('project-search').value='';$('project-clear').click()}else window.creatorWorkspace?.select('prompt')}
   if(!catalogLoading||models.length)actions.append(next)
   if(trash){title.textContent=query?'没有匹配的回收版本':'回收站为空';hint.textContent='';actions.replaceChildren()}
   empty.append(title,hint,actions);$('project-grid').append(empty)
  }
  for(const task of entries){if(task.item.effect_file)continue;if(task.item.unreadable){task.node.textContent='文件无法读取';continue}coverTargets.set(task.card,task);if(document.body.dataset.workspace==='project')coverObserver.observe(task.card)}
  library.main.scrollTop=scrollTop
 }
 function manageRoom(room){
  const dialog=document.createElement('dialog');dialog.className='review-help-dialog'
  const form=document.createElement('form'),title=document.createElement('h3'),nameLabel=document.createElement('label'),name=document.createElement('input')
  title.textContent='房间管理';nameLabel.textContent='房间名称';name.value=room.name;name.required=true;name.maxLength=120;nameLabel.append(name)
  const rules=constraintGroups.filter(group=>(group.builtin||group.project_key===room.project_key)&&!group.archived)
  const refs=document.createElement('fieldset'),legend=document.createElement('legend');legend.textContent='引用约束';refs.append(legend)
  const selection=new Map(),owner=document.createElement('select'),ownerLabel=document.createElement('label');ownerLabel.textContent='归属目录';ownerLabel.append(owner)
  owner.add(new Option('未归组',''))
  for(const rule of rules){
   const option=new Option(rule.name,rule.id),label=document.createElement('label'),check=document.createElement('input')
   if(!rule.builtin)owner.add(option)
   check.type='checkbox';check.checked=room.constraint_ids.includes(rule.id);selection.set(rule.id,check);label.append(check,rule.name);refs.append(label)
  }
  if(room.owner_constraint_id&&!selection.has(room.owner_constraint_id))owner.add(new Option('当前归属（已归档）',room.owner_constraint_id))
  owner.value=room.owner_constraint_id??''
  const status=document.createElement('p');status.setAttribute('role','status')
  const actions=document.createElement('footer'),close=document.createElement('button'),save=document.createElement('button')
  close.type='button';close.textContent='取消';close.onclick=()=>dialog.close();save.type='submit'
  function updateAction(){save.textContent=(owner.value||null)===room.owner_constraint_id?'保存房间资料':'移动房间并保存';selection.get(owner.value)&&(selection.get(owner.value).checked=true)}
  owner.onchange=updateAction;updateAction();actions.append(close,save)
  form.append(title,nameLabel,ownerLabel,refs,status,actions);dialog.append(form);document.body.append(dialog);dialog.addEventListener('close',()=>dialog.remove());dialog.showModal()
  form.onsubmit=async event=>{
   event.preventDefault();const nextOwner=owner.value||null,move=nextOwner!==room.owner_constraint_id
   const chosen=room.constraint_ids.filter(id=>!selection.has(id));for(const [id,check] of selection)if(check.checked||id===nextOwner)chosen.push(id)
   save.disabled=true;close.disabled=true;status.textContent='正在保存…'
   try{
    await api('prompt-library',{action:move?'move-room':'update-room',folder:room.folder,revision:room.revision??0,name:name.value,owner_constraint_id:nextOwner,constraint_ids:chosen})
   }catch(error){status.textContent=error.message;save.disabled=false;close.disabled=false;return}
   dialog.close();const preview=$('project-preview-dialog');if(preview.open)preview.close()
   try{await refresh();message(move?'房间已移到所选归属目录':'房间资料已保存')}
   catch(error){message('房间已保存。刷新建筑库失败：'+error.message)}
  }
 }
 function constraintEvidence(item){
  const ids=item.constraint_ids??[],evidence=item.constraint_evidence??{}
  const details=document.createElement('details');details.className='project-constraint-evidence'
  const summary=document.createElement('summary');summary.textContent=`引用约束 · ${ids.length} 项`;details.append(summary)
  if(!ids.length){const empty=document.createElement('p');empty.textContent='尚未引用约束';details.append(empty);return details}
  const sources={registered:'房间登记',handoff:'交接方案',receipt:'初稿回传','room-rule':'房间专属规则',manual:'手动关联'}
  for(const id of ids){
   const rule=constraintGroups.find(group=>group.id===id),row=document.createElement('div'),name=document.createElement('strong')
   name.textContent=rule?.name??id;row.append(name)
   for(const proof of evidence[id]??[]){
    const origin=document.createElement('button');origin.type='button';origin.className='project-evidence-path'
    origin.textContent=[sources[proof.kind],proof.name].filter(Boolean).join(' · ');origin.title='复制来源路径 · '+proof.path
    const path=document.createElement('small');path.textContent=proof.path
    origin.onclick=async()=>{try{await navigator.clipboard.writeText(workspace+'/'+proof.path);message('已复制来源路径')}catch(error){message(error.message)}}
    row.append(origin,path)
   }
   details.append(row)
  }
  return details
 }
 function managementFor(item){
  const management=document.createElement('div');management.className='project-item-management';organization.decorate(management,item)
  const stage=document.createElement('select');stage.className='project-card-stage';stage.setAttribute('aria-label','创作状态：'+(item.object_name||item.name_zh||item.name));stage.add(new Option('按版本资料判断：'+stageLabels[projectStage({...item,stage:item.stage_manual?item.stage_auto:item.stage})],'auto'));for(const [key,label]of Object.entries(stageLabels))stage.add(new Option(label,key));stage.value=item.stage_manual?item.stage:'auto';stage.title='仅标记此文件的创作进度，不代表精修授权或验收通过';stage.onchange=async()=>{const value=stage.value;stage.disabled=true;try{await api('project-stage',{source:item.source,stage:value});if(value==='auto'){item.stage=item.stage_auto;delete item.stage_manual}else{if(!item.stage_manual)item.stage_auto=item.stage;item.stage=value;item.stage_manual=true}treeModels=null;render();stage.disabled=false;message('创作状态已保存；文件变化后需重新确认')}catch(error){message(error.message);stage.disabled=false}}
  const stageLabel=document.createElement('label');stageLabel.textContent='创作阶段';stageLabel.append(stage);management.append(stageLabel)
  if(item.bugged||item.unreadable){
   const actions=document.createElement('div');actions.className='project-repair-actions';const category=document.createElement('select');category.className='project-repair-category';category.setAttribute('aria-label','修复后归类');for(const [value,label]of [['auto','参考原分类（无资料则独立结构）'],...Object.entries(shapeNames)])category.add(new Option(label,value));const repair=document.createElement('button');repair.type='button';repair.className='project-repair';repair.textContent='尝试修复并归类';repair.title='保留原文件，恢复可确定的数据为新主模型候选；不自动导出NBT'
   repair.onclick=async()=>{if(isBusy()||thumbnailRun){message('请等待当前任务结束');return}repair.disabled=true;category.disabled=true;setBusy(true);let result;try{message('正在检查格式并尝试恢复；原文件保留…');result=await api('project-repair',{source:item.source,category:category.value,file_size:item.file_size,modified_ns:item.modified_ns});if(result.status==='recovered_candidate'){setBusy(false);await refresh();filters.shape.set([result.category]);filters.project.set(['all']);filters.stage.reset();filters.readability.reset();filters.version.set(['latest']);object='';$('project-search').value='';limit=24;render();message('已生成归类候选：'+result.candidate+'。请看图检查，尚未导出NBT。报告：'+result.report)}else message('未能自动恢复：'+result.error+'。原文件保留；报告：'+result.report)}catch(error){message('修复未完成：'+error.message)}finally{setBusy(false);repair.disabled=false;category.disabled=false}}
   const label=document.createElement('label');label.textContent='修复后放入哪个分类';label.append(category);actions.append(label,repair);management.append(actions)
  }
  const open=document.createElement('button');open.type='button';open.className='project-history-open';open.textContent='查看版本历史';open.onclick=()=>{dialog.close();history.open(item.source)};management.append(open)
  const room=layoutRooms.find(entry=>entry.id===item.room_id)
  if(room){const button=document.createElement('button');button.type='button';button.textContent='房间管理';button.onclick=()=>manageRoom(room);management.append(button)}
  management.append(constraintEvidence(item))
  return management
 }
 async function showEffect(item){
  try{const result=await api('effects/read',{id:item.effect_file.id});const d=document.createElement('dialog');d.className='review-help-dialog';const title=document.createElement('h3'),text=document.createElement('textarea'),close=document.createElement('button');title.textContent=result.name;text.readOnly=true;text.rows=18;text.style.width='100%';text.value=JSON.stringify(result.content,null,2);close.textContent='关闭';close.onclick=()=>d.close();d.append(title,text,close);d.addEventListener('close',()=>d.remove());document.body.append(d);d.showModal();return true}catch(e){message(e.message);return false}
 }
 async function showPreview(item){
  if(item.effect_file)return showEffect(item)

  if(isBusy()||previewBusy){message('请等待当前任务完成');return false}
  selected=item;const token=++previewGeneration
  $('project-preview-edit').textContent=targetIntent?'使用这座建筑并返回构件':'打开建筑编辑'
  $('project-preview-management').replaceChildren(managementFor(item));$('project-preview-location').textContent=[item.source,item.version].filter(Boolean).join(' · ');$('project-manage-status').textContent='';$('project-preview-edit').disabled=!!item.unreadable;$('project-preview-render').disabled=!!item.unreadable;$('project-preview-render').hidden=false
  let taskLink=dialog.querySelector('#project-preview-task-link');if(!taskLink){taskLink=document.createElement('div');taskLink.id='project-preview-task-link';dialog.querySelector('footer').prepend(taskLink)}taskLink.replaceChildren();const batchLink=workspaces?.previewLink(item.source);if(batchLink)taskLink.append(batchLink)
  $('project-preview-title').textContent=item.object_name||item.name_zh||item.name||item.label;$('project-preview-meta').textContent=[item.size?.join(' × '),stageLabels[projectStage(item)],item.version].filter(Boolean).join(' · ')
  $('project-preview-image').hidden=true;$('project-preview-3d').hidden=true;$('project-preview-3d').src='about:blank';$('project-preview-status').textContent='正在读取截面预览；首次缺图时会生成并缓存…';if(!dialog.open)dialog.show();library.body.classList.add('selection-open')
  const cardCover=[...$('project-grid').querySelectorAll('.project-card')].find(card=>card.dataset.source===item.source)?.querySelector('.project-cover img')
  if(cardCover?.src){$('project-preview-image').src=cardCover.src;$('project-preview-image').hidden=false;$('project-preview-status').textContent='正在准备可旋转的 3D 预览…'}
  if(item.unreadable){$('project-preview-status').textContent=item.error||'文件无法读取，可在右侧尝试修复。';return false}
  if(item.bugged&&window.nbtPreviewPreferences?.mode!=='images'){$('project-preview-status').textContent='此文件需要检查。可尝试 3D 预览，或在右侧修复并归类。';return true}
  if(item.source_kind==='assembly'){const shown=await render3D();if(shown&&token===previewGeneration)await workspaces?.seen(item.source).catch(error=>message(error.message));return shown}
  // Detail selection stays immediate; the larger WebGL snapshot starts only
  // when the user requests 3D from the inspector.
  try{const result=await cover(item,true);if(token!==previewGeneration||!dialog.open)return false
   if(result.image){$('project-preview-image').src=result.image;$('project-preview-image').hidden=false;$('project-preview-status').textContent=result.generated?'当前版本截面示意图 · 已缓存（简化材质）':result.section?'整体截面预览 · 已缓存':'当前版本尚无截面渲染图，显示已有渲染图'}
   else if(await render3D()===false)return false
   for(const card of $('project-grid').querySelectorAll('.project-card'))if(card.dataset.source===item.source)displayCover(card.querySelector('.project-cover'),result,item)
   covers.clear();await workspaces?.seen(item.source).catch(error=>message(error.message));return true
  }catch(e){if(token===previewGeneration&&dialog.open)$('project-preview-status').textContent=e.message+'；可尝试打开 3D 预览。';return false}
 }
 async function render3D(){
  if(!selected||selected.unreadable||previewBusy||isBusy())return false
  const token=previewGeneration,item=selected;previewBusy=true;setBusy(true);$('project-preview-close').disabled=false
  $('project-preview-status').textContent='正在读取 NBT 并准备 3D 预览…'
  try{
   const {id}=await api('jobs',{kind:'snapshot',request:{source:item.source,context:'',cameras:'',settings:{}}})
   let job
   do{await new Promise(resolve=>setTimeout(resolve,400));job=await api('jobs/'+id)}while(job.status==='running')
   if(job.status!=='complete')throw Error(job.error||'3D 预览未完成')
   if(token!==previewGeneration||!dialog.open)return
   const frame=$('project-preview-3d');frame.src=`/?model_key=${encodeURIComponent(job.result.model_key)}&embedded=1&quality=${encodeURIComponent(window.nbtPreviewPreferences?.quality??'balanced')}&pixelRatio=0.75&maxFps=24`;frame.hidden=false;$('project-preview-image').hidden=true;$('project-preview-render').hidden=true;$('project-preview-status').textContent='左键原地转向，中键平移，滚轮沿视线前进／后退。此处仅预览，不修改建筑。';return true
  }catch(e){if(token===previewGeneration&&dialog.open)$('project-preview-status').textContent=e.message;return false}
  finally{previewBusy=false;setBusy(false)}
 }
 function populateFilters(){
  const scoped=organization.filter(models),projects=new Map(scoped.map(item=>[item.project_key,item.project_name])),shapes=new Map(scoped.map(item=>[item.shape_group,item.shape_group_zh]));shapes.set('bugged','bugged（待修复）')
  for(const folder of constraintFolders){projects.set(folder.project,folder.projectLabel);if(folder.shape)shapes.set(folder.shape,folder.shapeLabel)}
  const shapeOrder=[...Object.keys(shapeNames),'unclassified','bugged']
  filters.project.options([...projects].sort((a,b)=>a[1].localeCompare(b[1],'zh-CN')))
  filters.shape.options([...shapes].sort((a,b)=>shapeOrder.indexOf(a[0])-shapeOrder.indexOf(b[0])))
  filters.constraint.options([...constraintGroups.filter(group=>!group.archived).map(group=>[group.id,group.name]),['unassigned','未引用约束']])
 }
 $('project-search').oninput=()=>{clearTimeout(searchTimer);searchTimer=setTimeout(()=>{limit=24;render()},120)}
 $('project-clear').onclick=()=>{organization.reset();for(const filter of Object.values(filters))filter.reset();$('project-search').value='';treeSelection=null;object='';limit=24;render()}
 $('project-more').onclick=()=>{limit+=24;render(true)}
 $('project-refresh').onclick=async()=>{try{message('正在刷新建筑库…');covers.clear();await refresh();await workspaces?.refresh();message('建筑库已刷新')}catch(e){message(e.message)}}
 $('project-preview-close').onclick=()=>dialog.close();$('project-preview-render').onclick=render3D;$('project-preview-edit').onclick=()=>edit(selected)
 dialog.addEventListener('close',()=>{
  // The close event can arrive after the detail panel has been reopened.
  if(dialog.open)return
  previewGeneration++;library.body.classList.remove('selection-open');$('project-preview-3d').src='about:blank';$('project-preview-3d').hidden=true;$('project-preview-image').removeAttribute('src')
 })
 window.addEventListener('creator-workspace-change',event=>{if(event.detail==='project'){render()}else{if(!openingTarget)clearTarget();if(thumbnailRun)thumbnailRun.cancelled=true;generation++;coverObserver.disconnect();coverQueue=[];if(dialog.open)dialog.close()}})
 return {chooseTarget,openFile:source=>targetIntent?edit({source}):openModel({source}),getVisible:()=>visibleModels,constraintFolders:()=>constraintFolders,constraintFolder:()=>constraintFolder,constraintFolderFor,defaultConstraintFolder,layoutProject,draftConstraintScopes,startConstraint:()=>constraintGroups.find(group=>group.id===treeSelection?.constraint&&!group.archived),checked(info){for(const item of models)if(item.source===info.source){item.unverified=false;item.unreadable=false;item.geometry_sha256=info.geometry_sha256;item.size=info.size}latest=latestSources(models);if(document.body.dataset.workspace==='project')render()},setLoading(text){catalogLoading=!!text;$('project-loading').textContent=text;$('project-refresh').disabled=catalogLoading;host.setAttribute('aria-busy',String(catalogLoading&&!models.length))},update(items,root,folders=[],catalog={}){if(root!==workspace){compare.reset();clearTarget()}models=items;compare.reconcile(items);batch?.update();latest=latestSources(models);workspace=root;layoutProjects=catalog.layout_projects??[];constraintGroups=catalog.constraint_groups??[];layoutRooms=catalog.rooms??[];constraintFolders=foldersFor(items,folders,catalog.constraint_scopes);workspaces?.update(workspace);host.dataset.workspaceRoot=workspace;populateFilters();render();window.dispatchEvent(new Event('project-constraint-folders-loaded'))}}
}
