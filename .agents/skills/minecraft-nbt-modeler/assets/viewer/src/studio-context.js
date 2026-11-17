import {aiGroupMatches,aiBounds} from './ai-component.mjs'
// Context is read from the existing editor, selection and operation group. It
// does not invent a scene graph or introduce a second set of model parameters.
export function initStudioContext({state,gather,showPanel,setInspector}) {
 const $=id=>document.getElementById(id),workspace=$('studio-workspace'),actions=$('studio-actions')
 const tasks=document.querySelector('.creator-workspaces [data-workspace=tasks]');document.querySelector('.creator-header-actions').prepend(tasks)
 const location=document.createElement('button');location.type='button';location.id='studio-workspace-location';document.querySelector('.creator-brand').append(location)
 const locationLabel=$('desktop-workspace-label');function locationText(){const full=locationLabel?.title??'';location.textContent=full?'工作区：'+full.split(/[\\/]/).filter(Boolean).at(-1):'当前工作区';location.title=full||'查看工作区与文件位置'}
 if(locationLabel)new MutationObserver(locationText).observe(locationLabel,{childList:true,attributes:true,attributeFilter:['title']});locationText();location.onclick=async()=>{await $('open-settings').onclick();document.querySelector('[data-settings-tab=storage]')?.click()}
 const title=document.createElement('div');title.id='studio-object-context';$('studio-model-menu').before(title);title.append($('studio-model-menu'))
 const meta=document.createElement('span');meta.id='studio-object-meta';title.append(meta)
 const views=document.createElement('nav');views.id='studio-views';views.setAttribute('aria-label','当前建筑工作视图')
 for(const [name,label]of [['prepare','准备编辑'],['inspect','检查与交付']]){const b=document.createElement('button');b.type='button';b.id='studio-view-'+name;b.dataset.studioView=name;b.textContent=label;b.title=label+'；同一建筑，保留镜头、剖切和参数';b.onclick=()=>showPanel(name==='inspect'?'checks':lastEditPanel);views.append(b)}
 let lastEditPanel='tools';actions.insertBefore(views,$('studio-step'));$('studio-step').hidden=true
 const scope=document.createElement('section');scope.id='studio-object-inspector';scope.innerHTML='<div class="studio-object-heading"><strong id="studio-object-name">尚未打开建筑</strong><button type="button" id="studio-edit-scope">修改范围</button></div><dl><dt>作用范围</dt><dd id="studio-object-scope"></dd><dt>尺寸</dt><dd id="studio-object-size"></dd><dt>坐标</dt><dd id="studio-object-position"></dd></dl><p id="studio-object-help"></p>'
 $('studio-tool-menu').before(scope)
 $('studio-edit-scope').onclick=()=>{showPanel('tools');if(scope.dataset.instance==='placed'){document.querySelector('#tool-tabs [data-tool-index="8"]').click();document.querySelector(`#operation-list [data-operation="${state().recentComponent.start}"] .operation-name`)?.focus()}else if(scope.dataset.instance==='ai'){document.querySelector('#tool-tabs [data-tool-index="9"]').click();$('ai-move-x').closest('details').open=true;$('ai-move-x').focus()}else{document.querySelector('#tool-tabs [data-tool-index="4"]').click();$('whole-region').closest('details').open=true;$('whole-region').focus()}}
 for(const edge of ['lo','hi'])for(const axis of ['x','y','z']){$(`${edge}-${axis}`).setAttribute('aria-label',`${edge==='lo'?'起点':'终点'} ${axis.toUpperCase()}（格）`);$(`${edge}-${axis}`).title='建筑局部坐标，单位：方块格；含起点和终点'}
 const modes=document.createElement('div');modes.id='studio-canvas-mode';modes.hidden=true;modes.innerHTML='<strong></strong><span></span><button type="button">退出 Esc</button>';$('studio-viewport').querySelector('.canvas-wrap').append(modes)
 modes.querySelector('button').onclick=()=>{if(state().transforming)$('component-transform-cancel').click();else window.detailControl.exitCanvasMode?.()}
 const component=$('component-editor');if(component){$('studio-inspector').append(component);component.classList.add('studio-component-inspector')}
 let displayedSource='',lastMode=''
 function sync(){
  const s=state(),model=s.models?.find(m=>m.source===s.info?.source),source=s.info?.source??''
  const normalize=p=>p.replaceAll('\\','/').toLowerCase(),versioned=!!s.info&&normalize(s.info.workdir)!==normalize(s.info.version_dir),family=versioned?s.models?.find(m=>normalize(m.source).startsWith(normalize(s.info.workdir)+'/')):null,name=model?.name??family?.name??(versioned?s.info.workdir.split(/[\\/]/).at(-1):source.split(/[\\/]/).at(-1))??'当前建筑'
  if(displayedSource!==source){displayedSource=source;lastEditPanel='tools'}
  const version=model?.version??(versioned?s.info.version_dir.split(/[\\/]/).at(-1):'导入文件')
  let fresh=false;try{fresh=s.previewSettings===JSON.stringify(gather())}catch{}
  const side=s.versionComparing?'版本对比（只读）':s.preview&&s.comparisonSide==='after'?(fresh?'候选预览':'旧候选 · 需更新'):'原稿'
  meta.textContent=s.info?[version,side].filter(Boolean).join(' · '):'从建筑库打开，或编写首份方案'
  meta.title=source
  $('studio-model-menu').querySelector('summary span').textContent=s.info?name:'选择建筑'
  for(const b of views.children){const selected=b.dataset.studioView===(workspace.dataset.view??'prepare');b.setAttribute('aria-pressed',String(selected));b.disabled=!!(s.versionComparing||s.transforming)}
  let settings;try{settings=gather()}catch{}
  const tool=Number(document.querySelector('#tool-tabs [aria-pressed=true]')?.dataset.toolIndex),placed=tool===8,group=placed?s.recentComponent:s.lastAIGroup;let validGroup=false
  try{validGroup=(placed||tool===9)&&group&&group.source===source&&group.source_sha256===s.info?.source_sha256&&settings&&aiGroupMatches(group,settings)}catch{}
  scope.dataset.instance=validGroup?(placed?'placed':'ai'):'';$('studio-edit-scope').textContent=validGroup?'查看实例参数':'修改范围'
  const lo=settings?.whole_region?[0,0,0]:settings?.lo,hi=settings?.whole_region?s.info?.size?.map(n=>n-1):settings?.hi
  $('studio-object-name').textContent=validGroup?(group.name??group.structure_name??group.base[0]?.label??'当前构件实例'):(s.info?name:'尚未打开建筑')
  $('studio-object-scope').textContent=!s.info?'未选择':validGroup?'构件实例 · 操作序列内的同一组步骤':settings?.whole_region?'整栋建筑':'当前选区'
  const bounds=validGroup?aiBounds(group.applied):null,componentLo=bounds?.lo??lo,componentHi=bounds?.hi??hi
  $('studio-object-size').textContent=componentLo&&componentHi?componentHi.map((n,i)=>n-componentLo[i]+1).join(' × ')+' 格':'—'
  $('studio-object-position').textContent=componentLo&&componentHi?componentLo.join(', ')+' → '+componentHi.join(', ')+'（XYZ）':'—'
  $('studio-object-help').textContent=validGroup?(placed?'实例由建造步骤组成，可修改步骤名称、坐标和参数。手柄在放置前调整。':'实例位移、旋转和覆盖参数在“AI 构件”工具中调整。其他工具仍使用整栋或当前选区。'):'范围适用于支持选区的工具；操作序列内的步骤使用各自坐标。'
  for(const row of document.querySelectorAll('#operation-list [data-operation]'))row.classList.toggle('inspected-instance',!!(validGroup&&placed&&Number(row.dataset.operation)>=group.start&&Number(row.dataset.operation)<group.start+group.base.length))
  $('studio-edit-scope').disabled=!s.info||!!(s.busy||s.previewBusy||s.transforming||s.versionComparing)
  $('studio-delivery-target').textContent=s.info?name+' / '+version+' → 新版本（保留原稿）':'请先打开建筑'
  $('studio-delivery-location').textContent=s.info?(s.info.workdir??source.split(/[\\/]/).slice(0,-1).join(' / '))+' / 新版本（保存时分配版本号）':'—'
  let mode='',help=''
  if(s.versionComparing){mode='版本对比 · 只读';help='结束对比后继续编辑'}
  else if(s.transforming){mode='构件手柄';help='W 移动 / E 旋转；应用后生成候选'}
  else if(s.selectionEditPicking){mode='两点选区';help='依次选择两个角点'}
  else if(s.assetPicking||s.aiPlacing){mode='构件放置';help='点击建筑表面选择放置位置'}
  else if(s.walkPicking){mode='通路选点';help='点击建筑选择检查位置'}
  else if(s.picking){mode='方块取材';help='点击可见方块，再选择材质用途'}
  else if(s.coordinatePicking){mode='位置标注';help='点击建筑，再填写修改意见'}
  modes.hidden=!mode;modes.querySelector('strong').textContent=mode;modes.querySelector('span').textContent=help;modes.querySelector('button').textContent=s.versionComparing?'结束对比 Esc':'退出 Esc';modes.querySelector('button').disabled=!!(s.busy||s.previewBusy||s.commitBusy)
  workspace.classList.toggle('transform-active',!!s.transforming)
  if(s.transforming&&lastMode!==mode)setInspector(true)
  lastMode=mode
 }
 window.addEventListener('creator-studio-panel',event=>{if(event.detail!=='checks')lastEditPanel=event.detail;sync()})
 for(const event of ['creator-editor-state','creator-workspace-change','nbt-ai-component-state','creator-tool-select'])window.addEventListener(event,sync)
 for(const event of ['input','change'])$('settings').addEventListener(event,()=>queueMicrotask(sync))
 sync()
}
