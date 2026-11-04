import './asset-workspace.css'
import {initAssetBatches} from './asset-batches.js'
import {initLibraryBrowser} from './library-browser.js'
import {createAssetTree} from './asset-tree.js'
import {initComponentAuthor} from './component-author.js'

export function initAssetWorkspace({api,context,apply,pickPosition,interactive,decorateTree=()=>{}}){
 const host=document.createElement('section');host.id='asset-workspace';host.hidden=true
 host.innerHTML=`<header class="asset-heading"><div><h1>资产管理</h1><p>把选区保存为可复用构件，在当前工作区中搜索、整理和放置。</p></div><button id="asset-save-selection">保存当前选区</button></header>
 <div class="asset-toolbar"><label>搜索构件<input id="asset-search" type="search" placeholder="名称、标签或尺寸"></label><label class="inline"><input id="asset-trash" type="checkbox">查看回收站</label><button id="asset-refresh">刷新</button><button id="asset-import">导入构件</button><input id="asset-import-file" type="file" accept="application/json,.json" hidden></div>
 <p id="asset-status" role="status"></p><div class="asset-layout"><main><p id="asset-count"></p><div id="asset-grid"></div><button id="asset-more" hidden>加载更多</button></main><aside id="asset-detail" hidden>
 <img id="asset-image" alt="构件几何示意图"><h2 id="asset-name"></h2><p id="asset-meta"></p><p class="muted">几何与简化材质示意；放置后在当前建筑中查看实际效果。</p>
 <label>名称<input id="asset-edit-name" maxlength="80"></label><label>标签（逗号分隔）<input id="asset-edit-tags" maxlength="500"></label><button id="asset-update">保存名称与标签</button><a id="asset-export" download>导出构件 JSON</a><button id="asset-archive">移入回收站</button>
 <fieldset><legend>放置到当前建筑</legend><p id="asset-target"></p><label>锚点坐标 XYZ<span class="asset-vector">${['x','y','z'].map(axis=>`<input id="asset-position-${axis}" type="number" step="1" aria-label="构件锚点${axis.toUpperCase()}">`).join('')}</span></label><button id="asset-use-range">使用当前选区底部中心</button><label>旋转<select id="asset-rotation"><option value="0">0°</option><option value="1">90°</option><option value="2">180°</option><option value="3">270°</option></select></label><label>镜像<select id="asset-mirror"><option value="">无</option><option value="x">X 轴</option><option value="z">Z 轴</option></select></label><label class="inline"><input id="asset-overwrite" type="checkbox">允许覆盖已有方块</label><p class="muted">默认保留选区的实体方块与墙层。旋转或镜像暂不支持的方块状态会明确提示，不会猜测朝向。位置超界、保护冲突仍由引擎检查。</p><button id="asset-pick">3D 选点放置并预览</button><button id="asset-place" class="primary">载入并预览</button><p>只追加候选操作；满意后在模型编辑中导出下一版。</p></fieldset></aside></div>`
 document.querySelector('.creator-header').after(host)
 const main=host.querySelector('.asset-layout>main'),actions=document.createElement('div'),filters=document.createElement('div'),tree=document.createElement('aside'),breadcrumb=document.createElement('p');tree.id='asset-tree';tree.setAttribute('aria-label','构件分类');breadcrumb.id='asset-breadcrumb';filters.className='project-filters';filters.append(document.getElementById('asset-trash').closest('label'));actions.append(document.getElementById('asset-import'),document.getElementById('asset-save-selection'));const importFile=document.getElementById('asset-import-file'),status=document.getElementById('asset-status'),inspector=document.getElementById('asset-detail');main.append(status)
 const browser=initLibraryBrowser({host,prefix:'asset',title:'资产管理',description:'把模型选区保存为可复用构件。左侧按标签或未分类浏览，点击卡片查看、整理和放置。筛选中可查看回收站。构件只加入当前建筑的候选，满意后再导出下一版。',search:document.getElementById('asset-search'),refresh:document.getElementById('asset-refresh'),actions,filters,tree,main,count:document.getElementById('asset-count'),breadcrumb});host.append(importFile)
 const inspectorDialog=document.createElement('dialog');inspectorDialog.id='asset-inspector-dialog';const inspectorHeader=document.createElement('header'),closeInspector=document.createElement('button');closeInspector.type='button';closeInspector.textContent='关闭';closeInspector.id='asset-inspector-close';closeInspector.onclick=()=>inspectorDialog.close();inspectorHeader.append(inspector.querySelector('#asset-name'),closeInspector);inspectorDialog.append(inspectorHeader,inspector);document.body.append(inspectorDialog)
 const adjust=document.createElement('button');adjust.id='asset-adjust-3d';adjust.type='button';adjust.textContent='3D 手柄调整后放置';document.getElementById('asset-place').before(adjust)
 const batch=document.createElement('details');batch.id='asset-batch';batch.innerHTML='<summary>批量阵列与材质主题</summary><label>XYZ 数量<span class="asset-vector">'+['x','y','z'].map(axis=>`<input id="asset-count-${axis}" type="number" min="1" max="64" step="1" value="1" aria-label="阵列数量 ${axis.toUpperCase()}">`).join('')+'</span></label><label>XYZ 锚点间距<span class="asset-vector">'+['x','y','z'].map(axis=>`<input id="asset-spacing-${axis}" type="number" step="1" value="${axis==='y'?0:8}" aria-label="阵列间距 ${axis.toUpperCase()}">`).join('')+'</span></label><label>材质主题<select id="asset-theme"><option value="">保留原材质</option></select></label><p>数量包含第一份，总共最多64份、65536格记录；间距为相邻锚点距离，可为负数。仅“载入并预览”及“3D选点放置”使用这些设置，手柄调整仍为单份。副本实际方块重叠会提示调整间距。</p>';document.getElementById('asset-overwrite').closest('label').before(batch)
 const save=document.createElement('dialog');save.id='asset-save-dialog';save.className='review-help-dialog'
 save.innerHTML='<h2>保存当前选区为构件</h2><p>保存当前显示的 3D 原模型或候选选区。每轴最多64格，共最多65536格；不修改建筑。</p><label>构件名称<input id="asset-save-name" maxlength="80"></label><label>标签（逗号分隔）<input id="asset-save-tags"></label><label class="inline"><input id="asset-save-air" type="checkbox">包含选区内的空气（用于保留开口；放置时可能需要允许覆盖）</label><p id="asset-save-range"></p><p id="asset-save-error" role="status"></p><button id="asset-save-cancel">取消</button><button id="asset-save-confirm" class="primary">保存到构件库</button>'
 document.body.append(save)
 const $=id=>document.getElementById(id),message=text=>$('asset-status').textContent=text
 let items=[],selected=null,limit=24,pending=false,saveContext=null,loaded=false,category='all'
 const treeView=createAssetTree({container:tree,onCategory:value=>{category=value;limit=24;render()},onOpen:item=>{selected=item;details();try{useRange()}catch{}render()},onRender:decorateTree})
 const tags=text=>text.split(/[,，]/).map(v=>v.trim()).filter(Boolean)
 function target(){const c=context();$('asset-target').textContent=c?.name?`当前建筑：${c.name} · ${c.size.join(' × ')}`:'请先从项目管理打开一座建筑';return c}
 function coordinates(position){for(const [i,axis]of ['x','y','z'].entries())$('asset-position-'+axis).value=position[i]}
 function useRange(){const c=target();if(!c)throw Error('请先打开建筑');coordinates(c.lo.map((n,i)=>i===1?n:Math.floor((n+c.hi[i])/2)))}
 function details(){
  $('asset-detail').hidden=!selected;if(!selected){if(inspectorDialog.open)inspectorDialog.close();return}
  $('asset-image').src=selected.thumbnail||'';$('asset-name').textContent=selected.name;$('asset-meta').textContent=`${selected.size.join(' × ')} · ${selected.block_count} 格 · 锚点 ${selected.anchor.join(', ')}`
  $('asset-edit-name').value=selected.name;$('asset-edit-tags').value=selected.tags.join(', ');$('asset-export').href=selected.download;$('asset-export').download=selected.name+'.component.json';$('asset-archive').textContent=selected.archived?'恢复构件':'移入回收站'
  for(const id of ['asset-place','asset-pick','asset-use-range','asset-adjust-3d'])$(id).disabled=!!selected.archived
  target();refreshThemes().catch(error=>message(error.message))
  if(document.body.dataset.workspace==='assets'&&!inspectorDialog.open)inspectorDialog.showModal()
 }
 function render(){
  const query=$('asset-search').value.toLocaleLowerCase(),trash=$('asset-trash').checked,scroll=browser.main.scrollTop,browsing=items.filter(item=>!!item.archived===trash)
  treeView.render(browsing,category,selected);$('asset-breadcrumb').textContent=category==='all'?'全部构件':category==='untagged'?'未分类':category.slice(4)
  const visible=browsing.filter(item=>(category==='all'||category==='untagged'&&!item.tags.length||category.startsWith('tag:')&&item.tags.includes(category.slice(4)))&&(!query||[item.name,...item.tags,item.size.join('x')].join(' ').toLocaleLowerCase().includes(query)))
  $('asset-count').textContent=`${visible.length} 个${trash?'已回收':'可用'}构件`;$('asset-grid').replaceChildren();$('asset-more').hidden=visible.length<=limit
  for(const item of visible.slice(0,limit)){
   const card=document.createElement('button');card.type='button';card.className='asset-card';card.dataset.assetId=item.id;card.setAttribute('aria-pressed',String(selected?.id===item.id))
   const cover=document.createElement('span');cover.className='project-cover';if(item.thumbnail){const image=document.createElement('img');image.src=item.thumbnail;image.loading='lazy';image.decoding='async';image.alt=item.name;cover.append(image)}else cover.textContent='构件预览'
   const name=document.createElement('strong'),meta=document.createElement('span'),labels=document.createElement('small');name.textContent=item.name;meta.className='project-card-meta';meta.textContent=`${item.size.join(' × ')} · ${item.block_count} 格`;labels.textContent=[item.tags.join(' · '),item.review_status==='pending_visual_review'?'待审阅':''].filter(Boolean).join(' · ');labels.hidden=!labels.textContent;card.append(cover,name,meta,labels)
   const wrapper=document.createElement('article');wrapper.className='project-card';wrapper.append(card);card.onclick=()=>{selected=item;details();try{useRange()}catch{}render()};$('asset-grid').append(wrapper)
  }
  if(!visible.length){const empty=document.createElement('p');empty.className='asset-empty';empty.textContent=trash?'回收站为空。':query?'没有匹配构件，试试其他名称或标签。':'构件库还没有内容。打开建筑、选择局部范围后，保存当前选区；也可导入构件 JSON。';$('asset-grid').append(empty)}
  browser.main.scrollTop=scroll
 }
 async function refresh(){const result=await api('components');items=result.items;loaded=true;selected=items.find(item=>item.id===selected?.id)||null;render();details();if(result.errors.length)message(`${result.errors.length} 个构件文件无法读取，其余内容已加载`)}
 async function refreshThemes(){const {items}=await api('recipes'),select=$('asset-theme'),value=select.value;select.replaceChildren(new Option('保留原材质',''));for(const item of items.filter(v=>v.asset_type==='theme'&&!v.archived))select.add(new Option(item.name,item.id));if([...select.options].some(o=>o.value===value))select.value=value}
 window.addEventListener('creator-reusable-change',()=>refreshThemes().catch(error=>message(error.message)))
 async function perform(action){if(pending)throw Error('请等待当前构件任务完成');pending=true;try{return await action()}finally{pending=false}}
 const author=initComponentAuthor({actions,api,created:async item=>{selected=item;await refresh();message('独立结构已保存为新资产，可查看、整理和按参数放置')}})
 const viewIndependent=document.createElement('button');viewIndependent.id='asset-view-independent';viewIndependent.type='button';viewIndependent.textContent='独立3D查看';$('asset-export').after(viewIndependent);viewIndependent.onclick=async()=>{try{if(!selected)throw Error('请选择构件');await author.view(selected.id)}catch(error){message(error.message)}}
 function openSave(){
  const c=context();if(!c?.target_id)throw Error('请先打开3D，并在修改范围中选择要保存的局部选区')
  if(c.whole)throw Error('请先在“修改范围”关闭整座建筑并指定构件选区')
  saveContext=structuredClone(c);$('asset-save-name').value='';$('asset-save-error').textContent='';$('asset-save-range').textContent=`选区 ${c.lo.join(', ')} → ${c.hi.join(', ')}；锚点默认为底部中心`;save.showModal();$('asset-save-name').focus()
 }
 async function place(){
  if(!selected||selected.archived)throw Error('请先选择可用构件')
  const c=target();if(!c)throw Error('请先打开要放置的建筑')
  const position=['x','y','z'].map(axis=>{const input=$('asset-position-'+axis),n=Number(input.value);if(!input.value.trim()||!Number.isInteger(n))throw Error('锚点坐标须为整数');return n})
  const numbers=prefix=>['x','y','z'].map(axis=>{const input=$(prefix+axis),n=Number(input.value);if(!input.value.trim()||!Number.isInteger(n))throw Error('阵列数量与间距须为整数');return n}),counts=numbers('asset-count-'),spacing=numbers('asset-spacing-'),theme=$('asset-theme').value||null
  const result=await api(counts.some(n=>n!==1)||theme?'components/batch':'components/place',{id:selected.id,source:c.source,source_sha256:c.source_sha256,position,counts,spacing,theme,quarter_turns:Number($('asset-rotation').value),mirror:$('asset-mirror').value||null,overwrite:$('asset-overwrite').checked})
  const current=context();if(!current||current.source!==c.source||current.source_sha256!==c.source_sha256||current.settings!==c.settings)throw Error('当前建筑或参数已改变，请重新放置')
  await apply(result,c.settings);message(`构件“${selected.name}”${result.copies>1?'的 '+result.copies+' 份阵列':''}已加入候选；原建筑保留，满意后导出下一版`)
 }
 const safe=action=>async()=>{try{await perform(action)}catch(error){message(error.message)}}
 $('asset-save-selection').onclick=safe(openSave);$('asset-save-cancel').onclick=()=>save.close()
 $('asset-save-confirm').onclick=async()=>{try{await perform(async()=>{const current=context();if(!current||current.target_id!==saveContext?.target_id)throw Error('显示的模型已改变，请重新选择选区');const result=await api('components/save',{target_id:saveContext.target_id,name:$('asset-save-name').value,tags:tags($('asset-save-tags').value),lo:saveContext.lo,hi:saveContext.hi,include_air:$('asset-save-air').checked});save.close();window.creatorWorkspace.select('assets');selected=result;await refresh();message('构件已保存到当前工作区，可复用于其他建筑')})}catch(error){$('asset-save-error').textContent=error.message}}
 $('asset-refresh').onclick=safe(refresh);$('asset-search').oninput=()=>{limit=24;render()};$('asset-trash').onchange=()=>{selected=null;limit=24;render();details()};$('asset-more').onclick=()=>{limit+=24;render()}
 $('asset-update').onclick=safe(async()=>{if(!selected)throw Error('请选择构件');await api('components/update',{id:selected.id,name:$('asset-edit-name').value,tags:tags($('asset-edit-tags').value)});await refresh();message('名称与标签已保存')})
 $('asset-archive').onclick=safe(async()=>{if(!selected)return;const archived=!selected.archived;await api('components/update',{id:selected.id,archived});selected=null;await refresh();message(archived?'构件已移入回收站，可勾选回收站恢复':'构件已恢复')})
 $('asset-import').onclick=()=>$('asset-import-file').click();$('asset-import-file').onchange=safe(async()=>{const file=$('asset-import-file').files[0];if(!file)return;if(file.size>8*1024*1024)throw Error('构件文件超过8 MiB');const component=JSON.parse(await file.text()),result=await api('components/import',{component});selected=result;await refresh();message('构件已导入')})
 $('asset-use-range').onclick=safe(useRange);$('asset-place').onclick=safe(place)
 $('asset-adjust-3d').onclick=safe(async()=>{if(!selected||selected.archived)throw Error('请选择可用构件');if(['x','y','z'].every(axis=>!$('asset-position-'+axis).value.trim()))useRange();const position=['x','y','z'].map(axis=>{const input=$('asset-position-'+axis),n=Number(input.value);if(!input.value.trim()||!Number.isInteger(n))throw Error('请先填写整数锚点坐标，或使用当前选区');return n});const component=await api('components/get',{id:selected.id});await interactive(component,{id:selected.id,position,quarter_turns:Number($('asset-rotation').value),mirror:$('asset-mirror').value||null,overwrite:$('asset-overwrite').checked})})
 $('asset-pick').onclick=safe(async()=>{if(!selected||selected.archived)throw Error('请选择可用构件');await pickPosition(async position=>{coordinates(position);await perform(place)})})
 window.addEventListener('creator-workspace-change',event=>{if(event.detail==='assets'){target();if(!pending)refresh().catch(e=>message(e.message))}else if(inspectorDialog.open)inspectorDialog.close()})
 const open=document.createElement('button'),capture=document.createElement('button');open.id='open-assets';open.textContent='放置构件';capture.id='save-selection-asset';capture.textContent='选区存为构件';for(const button of [open,capture])button.type='button'
 open.onclick=()=>window.creatorWorkspace.select('assets');capture.onclick=()=>{try{openSave()}catch(e){message(e.message);window.creatorWorkspace.select('assets')}}
 document.querySelector('.review-toolbar').append(open,capture)
 for(const [id,label,move]of [['copy-selection-3d','复制选区并调整',false],['move-selection-3d','移动选区并调整',true]]){const button=document.createElement('button');button.id=id;button.type='button';button.textContent=label;button.onclick=()=>interactive(null,{selection:true,move}).catch(error=>{message(error.message);window.creatorWorkspace.select('assets')});document.querySelector('.review-toolbar').append(button)}
 initAssetBatches({api,host,refresh})
 return {refresh,openSave}
}
