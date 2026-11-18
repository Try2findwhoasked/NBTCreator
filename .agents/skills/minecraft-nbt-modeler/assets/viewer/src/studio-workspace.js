import './studio-workspace.css'
import {floatingDetails,chevron} from './floating-panel.js'
import {applyStudioCopy} from './studio-copy.js'
import {initAuthoringJourney} from './authoring-journey.js'
import {initStudioContext} from './studio-context.js'
import './studio-design.css'
import './library-unified.css'

// One inspector and one canvas. All authoring inputs retain their original
// nodes, event handlers, selection, validation and export contracts.
export function initStudioWorkspace({state,gather,openModel}){
 const $=id=>document.getElementById(id),workspace=document.querySelector('.workspace'),sidebar=document.querySelector('.sidebar'),stage=document.querySelector('.stage'),actions=document.querySelector('.action-bar'),viewport=document.querySelector('.viewport-card')
 document.body.dataset.shell='studio';workspace.id='studio-workspace';sidebar.id='studio-inspector';stage.id='studio-stage';actions.id='studio-actions';viewport.id='studio-viewport'
 const appHeader=document.querySelector('.creator-header');new ResizeObserver(()=>document.documentElement.style.setProperty('--studio-header',appHeader.getBoundingClientRect().height+'px')).observe(appHeader)
 const retained=document.createElement('div');retained.hidden=true;document.body.append(retained);retained.append(...actions.childNodes,$('open-prompt'))

 const names={project:'项目',assets:'素材',prompt:'设计',model:'编辑',ai:'AI 设置',tasks:'任务'}
 for(const button of document.querySelectorAll('.creator-workspaces button')){button.textContent=names[button.dataset.workspace];if(button.dataset.workspace==='ai')button.hidden=true}
 document.querySelector('.brand-mark').textContent='';document.querySelector('.brand-caption').remove()
 const aiSettings=document.createElement('button');aiSettings.type='button';aiSettings.id='studio-ai-settings';aiSettings.textContent='AI 设置';aiSettings.onclick=()=>window.creatorWorkspace.select('ai');document.querySelector('.creator-header-actions').append(aiSettings)

 function button(id,label,click){const b=document.createElement('button');b.id=id;b.type='button';b.textContent=label;b.onclick=click;return b}
 function heading(text){const h=document.createElement('h3');h.textContent=text;return h}
 function card(title,...content){const section=document.createElement('section');section.className='studio-side-card';section.append(heading(title),...content);return section}
 function cardActions(...controls){const row=document.createElement('div');row.className='studio-card-actions';row.append(...controls);return row}
 function menu(id,label,panel,minimum=270){const d=document.createElement('details');d.id=id;d.className='studio-menu';const summary=document.createElement('summary');summary.innerHTML='<span></span>'+chevron;summary.querySelector('span').textContent=label;panel.classList.add('studio-menu-panel');d.append(summary,panel);floatingDetails(d,panel,{minimum});return d}

 // Model selection lives in the title row, never above every tool's parameters.
 const sourcePanel=document.createElement('div');sourcePanel.append($('model-library'))
 const sourceMenu=menu('studio-model-menu','选择建筑',sourcePanel,330)
 const versionPanel=document.createElement('div');versionPanel.id='studio-version-panel';const versionList=document.createElement('div');versionList.id='studio-version-list';versionPanel.append(versionList)
 const versionMenu=menu('studio-version-menu','版本',versionPanel,290)
 const toggle=button('studio-inspector-toggle','收起面板',()=>setInspector(!inspectorOpen));toggle.setAttribute('aria-controls','studio-inspector')
 const primary=document.createElement('div');primary.className='studio-primary-actions';actions.append(primary);primary.append($('cancel'),$('update-preview'),$('validate-preview'),$('export-revision'))
 for(const [id,label]of [['update-preview','预览效果'],['validate-preview','检查效果'],['export-revision','导出下一版'],['cancel','取消任务']])$(id).textContent=label
 const currentStep=document.createElement('span');currentStep.id='studio-step';currentStep.setAttribute('role','status')
 actions.replaceChildren(toggle,sourceMenu,versionMenu,currentStep,primary);workspace.prepend(actions)
 if($('open-building-history')){const history=$('open-building-history');history.textContent='查看完整版本历史';versionPanel.append(history)}
 const saveDraft=button('save-authoring-version','保存制作版',async()=>{try{await window.detailControl.saveAuthoringVersion()}catch(error){showPanel('checks');$('status').textContent='制作版未保存：'+error.message;$('status-badge').textContent='保存失败';$('status-badge').className='badge error';saveDraft.focus()}});saveDraft.title='将当前候选保存为新的 SNBT 制作版本，不生成定稿 NBT';primary.insertBefore(saveDraft,$('export-revision'))

 const inspectorNav=document.createElement('nav');inspectorNav.id='studio-inspector-nav';inspectorNav.setAttribute('aria-label','编辑面板')
 const pages={}
 for(const [name,label]of [['notes','标注'],['tools','建筑'],['review','审查'],['checks','检查与交付'],['more','文件']]){const page=document.createElement('section');page.id='studio-'+name;page.className='studio-inspector-page';page.hidden=name!=='notes';pages[name]=page;sidebar.append(page);const b=button('studio-panel-'+name,label,()=>showPanel(name));b.dataset.studioPanel=name;b.setAttribute('aria-controls',page.id);inspectorNav.append(b)}
 const tools=$('tool-tabs'),toolChooser=menu('studio-tool-menu','整体效果',tools,320)
 tools.setAttribute('aria-label','选择建模工具')
 const toolFooter=document.createElement('div');toolFooter.id='studio-tool-footer';pages.tools.append(toolFooter);toolFooter.append($('undo-settings'),$('redo-settings'),$('auto-preview').closest('label'))
 $('auto-preview').closest('label').lastChild.textContent='自动预览'
 pages.tools.append(toolChooser,$('settings'),toolFooter)
 const reproducibility=document.createElement('details');reproducibility.className='studio-form-help';reproducibility.innerHTML='<summary>随机种子与备注</summary>'
 const seedLabel=$('seed').closest('label'),noteLabel=$('style-note').closest('label');seedLabel.firstChild.textContent='随机种子';noteLabel.firstChild.textContent='备注（可选）';$('style-note').placeholder='仅作记录，不影响参数计算。';seedLabel.before(reproducibility);reproducibility.append(seedLabel,noteLabel)
 for(const card of $('settings').children){const notes=[...card.querySelectorAll(':scope>p.muted:not([id])')];if(!notes.length)continue;const help=document.createElement('details');help.className='studio-form-help';help.innerHTML='<summary>工具说明</summary>';help.append(...notes);card.append(help)}

 const noteHint=document.createElement('p');noteHint.id='studio-notes-hint';noteHint.textContent='先打开一座建筑，再在画面上标记需要修改的位置。'
 const feedback=$('feedback-card');pages.notes.append(noteHint,feedback)
 const noteScope=document.createElement('div');noteScope.id='studio-note-scope';noteScope.append($('whole-image-note'),$('draft-point'));feedback.querySelector('.comment-composer').prepend(noteScope)
 feedback.querySelector('h2').textContent='修改意见';$('refresh-reference').textContent='刷新引用';$('whole-image-note').textContent='清空选点';$('save-feedback').textContent='保存意见'
 $('feedback-text').placeholder='描述要修改的位置和结果；在画布栏点击“选点标注”可添加 #1、#2 等位置。'
 const noteUtilities=document.createElement('div');noteUtilities.append($('refresh-reference'),$('export-feedback'));const noteMenu=menu('studio-note-menu','更多',noteUtilities,280);feedback.querySelector('.comment-heading').append(noteMenu)
 feedback.querySelector('.comment-thread').after($('comment-tasks-open'))

 // Existing validation creates its diagnostics after this node.
 const checks=document.querySelector('.preview-controls')
 const diagnosticTools=document.createElement('div');diagnosticTools.className='studio-secondary-actions'
 for(const id of ['room-score-open','open-version-compare'])if($(id))diagnosticTools.append($(id))
 pages.checks.append(card('本次修改的检查结果',checks),card('进一步检查',diagnosticTools))
 const coordinates=document.createElement('details');coordinates.id='studio-check-coordinates';coordinates.className='studio-form-help';coordinates.hidden=true
 coordinates.innerHTML='<summary>补齐检查资料</summary><label>坐标配置 JSON<input id="studio-check-context-path" type="text" spellcheck="false"></label><button id="studio-check-context-apply" type="button">使用配置并重新预览</button><p role="status"></p>'
 checks.before(coordinates)
 coordinates.addEventListener('toggle',()=>{if(coordinates.open)$('studio-check-context-path').value=$('context').value})
 $('studio-check-context-apply').onclick=async()=>{
  const control=$('studio-check-context-apply'),note=coordinates.querySelector('p')
  control.disabled=true;note.textContent=''
  try{await window.detailControl.updatePlacementContext($('studio-check-context-path').value)}
  catch(error){note.textContent=error.message}
  finally{control.disabled=false}
 }
 const previewCommands=document.createElement('div');previewCommands.id='studio-preview-commands';previewCommands.append($('update-preview'));pages.tools.append(previewCommands)
 const checkCommands=document.createElement('div');checkCommands.id='studio-check-commands';checkCommands.append($('validate-preview'));checks.before(checkCommands)
 const delivery=document.createElement('section');delivery.id='studio-delivery';delivery.innerHTML='<h3>保存与交付</h3><p>预览和检查不会保存建筑。制作版用于继续编辑，定稿 NBT 用于游戏。</p><dl><dt>目标</dt><dd id="studio-delivery-target"></dd><dt>保存位置</dt><dd id="studio-delivery-location"></dd><dt>制作版</dt><dd>新版本 / model.snbt</dd><dt>定稿文件</dt><dd>_exports / 对应建筑版本 / NBT</dd></dl><div id="studio-delivery-actions"></div><p id="studio-delivery-receipt" role="status"></p>'
 delivery.querySelector('#studio-delivery-actions').append(saveDraft,$('export-revision'));pages.checks.append(delivery)
 const result=document.querySelector('.result-panel');result.open=true
 const fileMenu=document.querySelector('.output-card');fileMenu.querySelector('summary').textContent='参数文件的保存位置'
 $('plan').textContent='生成修改方案';$('copy-agent-plan').textContent='复制给 Agent'
 const agent=card('与 Agent 协作',cardActions($('plan'),$('copy-agent-plan'),$('agent-return-open')),document.querySelector('.review-advanced-shell'))
 const presets=document.querySelector('.preset-card')
 const renderImages=$('render'),renderHelp=renderImages.nextElementSibling
 renderImages.textContent='生成原建筑预览图'
 const images=card('原始建筑的预览图片',cardActions(renderImages,...(renderHelp?.matches('.inline-info')?[renderHelp]:[])))
 pages.more.append(card('运行结果',result),agent,card('参数文件与编辑进度',presets,fileMenu),images)
 sidebar.replaceChildren(inspectorNav,...Object.values(pages))

 const splitter=document.createElement('div');splitter.id='studio-panel-resize';splitter.tabIndex=0;splitter.setAttribute('role','separator');splitter.setAttribute('aria-orientation','vertical');splitter.setAttribute('aria-label','调整操作面板宽度');splitter.title='左右拖动调整面板宽度，双击恢复默认；方向键也可调整';sidebar.after(splitter)
 let preferredWidth=384
 try{const saved=Number(localStorage.getItem('nbt-studio-panel-width'));if(saved>=320&&saved<=720)preferredWidth=saved}catch{}
 function panelWidth(value,persist=false){const max=Math.min(720,Math.max(320,innerWidth-360)),width=Math.round(Math.min(max,Math.max(320,value)));workspace.style.setProperty('--studio-panel',width+'px');splitter.setAttribute('aria-valuemin','320');splitter.setAttribute('aria-valuemax',String(max));splitter.setAttribute('aria-valuenow',String(width));if(persist){preferredWidth=width;try{localStorage.setItem('nbt-studio-panel-width',String(width))}catch{}}return width}
 panelWidth(preferredWidth);window.addEventListener('resize',()=>panelWidth(preferredWidth))
 let drag=null
 splitter.onpointerdown=event=>{if(event.button!==0)return;drag={x:event.clientX,width:sidebar.getBoundingClientRect().width};splitter.setPointerCapture(event.pointerId);document.body.classList.add('studio-resizing');event.preventDefault()}
 splitter.onpointermove=event=>{if(drag)panelWidth(drag.width+event.clientX-drag.x)}
 const endResize=()=>{if(!drag)return;panelWidth(sidebar.getBoundingClientRect().width,true);drag=null;document.body.classList.remove('studio-resizing')}
 splitter.onpointerup=endResize;splitter.onpointercancel=endResize;splitter.onlostpointercapture=endResize
 splitter.ondblclick=()=>panelWidth(384,true)
 splitter.onkeydown=event=>{const current=Number(splitter.getAttribute('aria-valuenow'));if(['ArrowLeft','ArrowRight','Home','End'].includes(event.key)){event.preventDefault();panelWidth(event.key==='Home'?384:event.key==='End'?720:current+(event.key==='ArrowLeft'?-20:20),true)}}

 // The viewport toolbar contains only viewing/pointing controls. Secondary
 // display settings are in a popover and never wrap into extra canvas rows.
 const bar=document.querySelector('.review-toolbar'),displayPanel=document.createElement('div')
 displayPanel.id='studio-display-settings';displayPanel.dataset.mode='3d';displayPanel.append(heading('显示设置'))
 const pictureGroup=document.createElement('section');pictureGroup.className='studio-display-group display-image';const imageHelp=document.createElement('p');imageHelp.textContent='在画布栏的“视角”选择图片。';pictureGroup.append(heading('图片'),imageHelp)
 const pictureSettings=document.createElement('section');pictureSettings.className='studio-display-group display-3d';pictureSettings.append(heading('画面'))
 const qualityRow=document.createElement('label');qualityRow.className='studio-display-row';qualityRow.append(document.createTextNode('画质'),$('three-quality'));pictureSettings.append(qualityRow)
 const viewLabels=[...$('three-toolbar').querySelectorAll('label')]
 const imageLabel=$('image-select').closest('label');imageLabel.classList.add('studio-image-view');imageLabel.firstChild.textContent='视角';imageLabel.hidden=true
 viewLabels[1].classList.add('studio-display-row');viewLabels[2].classList.add('studio-display-cut');pictureSettings.append(viewLabels[1],viewLabels[2])
 const overlayGroup=document.createElement('section');overlayGroup.className='studio-display-group display-3d';overlayGroup.append(heading('辅助显示'))
 const selectionLabel=$('show-selection').closest('label');selectionLabel.lastChild.textContent='选区框';overlayGroup.append(selectionLabel)
 const protectionLabel=document.createElement('label'),quickProtection=document.createElement('input');quickProtection.id='studio-protection-visible';quickProtection.type='checkbox';quickProtection.disabled=true;protectionLabel.append(quickProtection,document.createTextNode('保护区'));overlayGroup.append(protectionLabel)
 const pathLabel=document.createElement('label'),quickPath=document.createElement('input');quickPath.id='studio-walk-visible';quickPath.type='checkbox';quickPath.disabled=true;pathLabel.append(quickPath,document.createTextNode('玩家路径'));overlayGroup.append(pathLabel)
 const pathHint=document.createElement('p');pathHint.id='studio-walk-hint';pathHint.textContent='先检查路径，才能显示检查结果。';overlayGroup.append(pathHint)
 const detailActions=document.createElement('section');detailActions.className='studio-display-actions display-3d'
 displayPanel.append(pictureSettings,overlayGroup,detailActions,pictureGroup)
 const viewMenu=menu('studio-view-menu','显示',displayPanel,290)
 for(const id of ['walk-open','protection-open']){const control=$(id);if(!control)continue;control.textContent=id==='walk-open'?'检查路径':'保护区详情';detailActions.append(control);control.addEventListener('click',()=>{viewMenu.open=false;if(displayPanel.matches(':popover-open'))displayPanel.hidePopover()})}
 quickProtection.onchange=()=>{const original=$('protection-visible');original.checked=quickProtection.checked;original.dispatchEvent(new Event('change',{bubbles:true}))}
 quickPath.onchange=()=>{const original=$('walk-visible');original.checked=quickPath.checked;original.dispatchEvent(new Event('change',{bubbles:true}))}
 window.addEventListener('creator-protection-visibility',event=>{quickProtection.checked=event.detail.enabled;quickProtection.disabled=!event.detail.available})
 window.addEventListener('creator-walk-visibility',event=>{quickPath.checked=event.detail.hasResult&&event.detail.enabled;quickPath.disabled=!event.detail.hasResult;pathHint.textContent=event.detail.hasResult?'只显示当前路径检查结果。':'先点击“检查路径”生成结果。'})
 const comparison=document.createElement('div');comparison.className='studio-comparison';bar.append(comparison);comparison.append($('compare-before'),$('compare-after'));$('compare-before').textContent='原建筑';$('compare-after').textContent='调整后'
 const three=$('three-toolbar');three.replaceChildren(viewLabels[0]);bar.append(comparison,viewMenu);bar.insertBefore(imageLabel,comparison)
 bar.insertBefore($('pick-material'),$('pick-coordinate'))
 bar.insertBefore(comparison,$('viewport-assets'))
 const photoStrip=document.querySelector('.thumbnail-card');photoStrip.id='studio-photos';photoStrip.querySelector('.inline-info').removeAttribute('open')
 const photoHeader=document.createElement('header');photoHeader.className='studio-photo-header';photoHeader.append(heading('图片选择器'),button('studio-photo-close','关闭',()=>{photoStrip.classList.remove('photos-open');photoButton.setAttribute('aria-expanded','false')}));photoStrip.prepend(photoHeader)

 let photoDrag=null
 photoHeader.onpointerdown=event=>{if(event.button!==0||event.target.closest('button'))return;const r=photoStrip.getBoundingClientRect(),s=stage.getBoundingClientRect();photoDrag={x:event.clientX,y:event.clientY,left:r.left-s.left,top:r.top-s.top};photoHeader.setPointerCapture(event.pointerId);event.preventDefault()}
 photoHeader.onpointermove=event=>{if(!photoDrag)return;photoStrip.style.right='auto';photoStrip.style.left=Math.max(0,Math.min(stage.clientWidth-photoStrip.offsetWidth,photoDrag.left+event.clientX-photoDrag.x))+'px';photoStrip.style.top=Math.max(0,Math.min(stage.clientHeight-40,photoDrag.top+event.clientY-photoDrag.y))+'px'}
 for(const name of ['pointerup','pointercancel','lostpointercapture'])photoHeader.addEventListener(name,()=>{photoDrag=null})
 const photoButton=button('studio-photo-toggle','查看图片缩略图',()=>{photoStrip.classList.toggle('photos-open');photoButton.setAttribute('aria-expanded',String(photoStrip.classList.contains('photos-open')))});photoButton.setAttribute('aria-expanded','false');photoButton.setAttribute('aria-controls','studio-photos');pictureGroup.append(photoButton)
 let compactView=false
 function fitViewport(){const compact=viewport.clientWidth<720;if(compact===compactView)return;compactView=compact;if(compact)displayPanel.append(comparison);else bar.insertBefore(comparison,$('viewport-assets'))}
 new ResizeObserver(fitViewport).observe(viewport)
 stage.replaceChildren(viewport,photoStrip)
 checks.replaceChildren($('candidate-check-state'),$('preview-state'))
 const empty=$('empty-view');empty.innerHTML='<strong>打开建筑，开始编辑</strong><span>从项目选择已有建筑，或在设计页编写新方案。</span>'
 const emptyActions=document.createElement('div');emptyActions.className='studio-empty-actions';emptyActions.append(button('studio-browse-projects','打开项目',()=>window.creatorWorkspace.select('project')),button('studio-new-design','新建设计方案',()=>window.creatorWorkspace.select('prompt')));emptyActions.firstChild.className='primary';empty.append(emptyActions)

 const statusbar=document.createElement('footer');statusbar.id='studio-statusbar'
 const statusLink=button('studio-show-status','就绪',()=>window.creatorWorkspace.select('tasks'));statusLink.title='查看完整运行记录'
 statusbar.append($('status-badge'),statusLink,$('operation-count'),$('session-status'));workspace.append(statusbar)
 pages.more.append(...retained.childNodes);retained.remove()

 let inspectorOpen=true,active='tools'
 function setInspector(open){inspectorOpen=open;workspace.classList.toggle('inspector-closed',!open);toggle.textContent=open?'收起面板':'展开面板';toggle.setAttribute('aria-expanded',String(open))}
 function showPanel(name){if(!pages[name])return;active=name;workspace.dataset.view=name==='checks'?'inspect':'prepare';for(const [key,page]of Object.entries(pages))page.hidden=key!==name;for(const b of inspectorNav.children)b.setAttribute('aria-pressed',String(b.dataset.studioPanel===name));setInspector(true);window.dispatchEvent(new CustomEvent('creator-studio-panel',{detail:name}))}
 showPanel('notes')
 window.addEventListener('creator-tool-select',()=>{toolChooser.open=false;if(tools.matches(':popover-open'))tools.hidePopover();const chosen=tools.querySelector('[aria-pressed=true]');toolChooser.querySelector('summary span').textContent=chosen?.textContent??'选择工具';showPanel('tools')})
 $('pick-material').addEventListener('click',()=>{if($('pick-material').getAttribute('aria-pressed')==='true'){const b=tools.querySelector('[data-tool-index="6"]');b.click()}})
 $('pick-coordinate').addEventListener('click',()=>{if($('pick-coordinate').getAttribute('aria-pressed')==='true')showPanel('notes')})
 $('validate-preview').addEventListener('click',()=>showPanel('checks'))
 window.addEventListener('creator-status',event=>{statusLink.textContent=event.detail.message;statusLink.title=event.detail.message})
 const captionObserver=new MutationObserver(()=>{statusLink.textContent=$('status').textContent;statusLink.title=$('status').textContent});captionObserver.observe($('status'),{childList:true,characterData:true,subtree:true})
 let versionBinding=''
 function updateVersionMenu(model,models){
  const object=model?.object_key??model?.group??model?.source,versions=object?models.filter(item=>(item.object_key??item.group??item.source)===object&&!item.unreadable):[]
  const binding=JSON.stringify([model?.source,versions.map(item=>[item.source,item.version])]);if(binding===versionBinding)return;versionBinding=binding
  const summary=versionMenu.querySelector('summary span'),short=value=>String(value??'当前版本').split(/[\\/]/).at(-1)
  summary.textContent=model?'原稿 · '+short(model.version):'版本';versionMenu.querySelector('summary').title=model?.version??'请先打开建筑'
  versionList.replaceChildren()
  if(!versions.length){const empty=document.createElement('p');empty.textContent='请先打开建筑';versionList.append(empty);return}
  for(const item of versions.slice(0,30)){const choose=button('',short(item.version),async()=>{versionMenu.open=false;if(versionPanel.matches(':popover-open'))versionPanel.hidePopover();try{await openModel(item)}catch(error){$('status').textContent='版本未打开：'+error.message}});choose.title=item.version??item.source;choose.setAttribute('aria-current',String(item.source===model.source));versionList.append(choose)}
 }
 function sync(){
  const s=state(),model=s.models?.find(m=>m.source===s.info?.source)
  let current=false;try{current=!!s.preview&&s.previewSettings===JSON.stringify(gather())}catch{}
  coordinates.hidden=!s.preview?.missing_checks?.length
  sourceMenu.querySelector('summary span').textContent=model?.name??(s.info?'当前建筑':'选择建筑')
  sourceMenu.querySelector('summary').title=s.info?.source??'选择要编辑的建筑'
  updateVersionMenu(model,s.models??[])
  currentStep.textContent=!s.info?'尚未打开建筑':s.busy||s.previewBusy?'正在处理…':current?(s.candidateValidation?.passed?'修改预览已通过检查':'正在查看修改预览'):s.preview?'设置已改变，请更新预览':'正在查看原建筑'
  $('export-revision').title=current?'将当前候选另存为 SNBT 制作源，并在 _exports 镜像目录生成定稿 NBT':'请先预览当前参数，再定稿导出';$('validate-preview').title=current?'检查当前候选的参数、保护与改动上限':'请先预览当前参数，再检查效果'
  photoButton.hidden=s.mode!=='images';photoStrip.classList.toggle('has-image',!!s.selectedImage);if(s.mode!=='images'&&photoStrip.classList.contains('photos-open')){photoStrip.classList.remove('photos-open');photoButton.setAttribute('aria-expanded','false')}
  imageLabel.hidden=s.mode!=='images';viewLabels[0].hidden=s.mode!=='3d'
  displayPanel.dataset.mode=s.mode==='images'?'images':'3d'
  noteHint.hidden=!feedback.hidden
  $('studio-panel-notes').textContent='标注'+(s.notes?.length?' '+s.notes.length:'')
  if(s.versionComparing||s.transforming)currentStep.textContent=s.versionComparing?'版本对比 · 只读查看':'正在调整构件'
 }
 new MutationObserver(sync).observe(feedback,{attributes:true,attributeFilter:['hidden']})
 new MutationObserver(sync).observe($('models'),{childList:true,subtree:true})
 window.addEventListener('creator-editor-state',sync);window.addEventListener('creator-workspace-change',sync);sync()
 for(const event of ['input','change'])$('settings').addEventListener(event,()=>queueMicrotask(sync))
 const newDesign=button('studio-project-new','新建设计方案',()=>window.creatorWorkspace.select('prompt'));newDesign.className='primary';$('project-native-actions').append(newDesign)
 applyStudioCopy()
 initStudioContext({state,gather,showPanel,setInspector})
 initAuthoringJourney({state,gather,showPanel,openModel})
 window.creatorStudio=Object.freeze({showPanel,setInspector,current:()=>active})
}
