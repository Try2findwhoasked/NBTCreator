import './studio-workspace.css'
import {floatingDetails,chevron} from './floating-panel.js'
import {applyStudioCopy} from './studio-copy.js'

// One inspector and one canvas. All authoring inputs retain their original
// nodes, event handlers, selection, validation and export contracts.
export function initStudioWorkspace({state,gather}){
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
 function menu(id,label,panel,minimum=270){const d=document.createElement('details');d.id=id;d.className='studio-menu';const summary=document.createElement('summary');summary.innerHTML='<span></span>'+chevron;summary.querySelector('span').textContent=label;panel.classList.add('studio-menu-panel');d.append(summary,panel);floatingDetails(d,panel,{minimum});return d}

 // Model selection lives in the title row, never above every tool's parameters.
 const sourcePanel=document.createElement('div');sourcePanel.append($('model-library'))
 const sourceMenu=menu('studio-model-menu','选择建筑',sourcePanel,330)
 const toggle=button('studio-inspector-toggle','收起面板',()=>setInspector(!inspectorOpen));toggle.setAttribute('aria-controls','studio-inspector')
 const primary=document.createElement('div');primary.className='studio-primary-actions';actions.append(primary);primary.append($('cancel'),$('update-preview'),$('validate-preview'),$('export-revision'))
 for(const [id,label]of [['update-preview','预览效果'],['validate-preview','检查效果'],['export-revision','导出下一版'],['cancel','取消任务']])$(id).textContent=label
 const currentStep=document.createElement('span');currentStep.id='studio-step';currentStep.setAttribute('role','status')
 actions.replaceChildren(toggle,sourceMenu,currentStep,primary);workspace.prepend(actions)
 if($('open-building-history'))actions.insertBefore($('open-building-history'),currentStep)
 const saveDraft=button('save-authoring-version','保存制作版',async()=>{try{await window.detailControl.saveAuthoringVersion()}catch(error){$('studio-show-status')?.click();document.getElementById('status').textContent=error.message}});saveDraft.title='将当前候选保存为新的 SNBT 制作版本，不生成定稿 NBT';primary.insertBefore(saveDraft,$('export-revision'))

 const inspectorNav=document.createElement('nav');inspectorNav.id='studio-inspector-nav';inspectorNav.setAttribute('aria-label','编辑面板')
 const pages={}
 for(const [name,label]of [['tools','工具'],['notes','标注'],['checks','检查'],['more','更多']]){const page=document.createElement('section');page.id='studio-'+name;page.className='studio-inspector-page';page.hidden=name!=='tools';pages[name]=page;sidebar.append(page);const b=button('studio-panel-'+name,label,()=>showPanel(name));b.dataset.studioPanel=name;b.setAttribute('aria-controls',page.id);inspectorNav.append(b)}
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
 const notePick=button('studio-note-pick','在画面上选点',()=>{if(state().mode==='3d'&&$('pick-coordinate').getAttribute('aria-pressed')!=='true')$('pick-coordinate').click()});feedback.querySelector('.comment-composer').prepend(notePick)
 feedback.querySelector('h2').textContent='修改意见';$('refresh-reference').textContent='刷新引用';$('whole-image-note').textContent='清空选点';$('save-feedback').textContent='保存意见'
 $('feedback-text').placeholder='描述要修改的内容。可点击画面选点；Ctrl+Enter 保存。'
 const noteUtilities=document.createElement('div');noteUtilities.append($('refresh-reference'),$('export-feedback'),$('comment-tasks-open'));const noteMenu=menu('studio-note-menu','标注工具',noteUtilities,280);feedback.querySelector('.comment-heading').append(noteMenu)

 // Existing validation creates its diagnostics after this node.
 const checks=document.querySelector('.preview-controls')
 const diagnosticTools=document.createElement('div');diagnosticTools.className='studio-secondary-actions'
 for(const id of ['protection-open','walk-open','room-score-open','open-version-compare'])if($(id))diagnosticTools.append($(id))
 pages.checks.append(heading('本次修改的检查结果'),checks,heading('进一步检查'),diagnosticTools)
 const result=document.querySelector('.result-panel');result.open=true
 const fileMenu=document.querySelector('.output-card');fileMenu.querySelector('summary').textContent='参数文件的保存位置'
 const agent=document.createElement('section');agent.className='studio-more-section';pages.more.append(agent);agent.append(heading('与 Agent 协作'),$('plan'),$('copy-agent-plan'),$('agent-return-open'),document.querySelector('.review-advanced-shell'))
 $('plan').textContent='生成修改方案';$('copy-agent-plan').textContent='复制给 Agent'
 const presets=document.querySelector('.preset-card');presets.prepend(heading('参数文件与编辑进度'))
 const images=document.createElement('section');images.className='studio-more-section';pages.more.append(images);images.append(heading('原始建筑的预览图片'),$('render'));$('render').textContent='生成原建筑预览图'
 pages.more.append(result,agent,presets,fileMenu,images)
 sidebar.replaceChildren(inspectorNav,...Object.values(pages))

 const splitter=document.createElement('div');splitter.id='studio-panel-resize';splitter.tabIndex=0;splitter.setAttribute('role','separator');splitter.setAttribute('aria-orientation','vertical');splitter.setAttribute('aria-label','调整操作面板宽度');splitter.title='左右拖动调整面板宽度，双击恢复默认；方向键也可调整';sidebar.after(splitter)
 let preferredWidth=400
 try{const saved=Number(localStorage.getItem('nbt-studio-panel-width'));if(saved>=320&&saved<=720)preferredWidth=saved}catch{}
 function panelWidth(value,persist=false){const max=Math.min(720,Math.max(320,innerWidth-360)),width=Math.round(Math.min(max,Math.max(320,value)));workspace.style.setProperty('--studio-panel',width+'px');splitter.setAttribute('aria-valuemin','320');splitter.setAttribute('aria-valuemax',String(max));splitter.setAttribute('aria-valuenow',String(width));if(persist){preferredWidth=width;try{localStorage.setItem('nbt-studio-panel-width',String(width))}catch{}}return width}
 panelWidth(preferredWidth);window.addEventListener('resize',()=>panelWidth(preferredWidth))
 let drag=null
 splitter.onpointerdown=event=>{if(event.button!==0)return;drag={x:event.clientX,width:sidebar.getBoundingClientRect().width};splitter.setPointerCapture(event.pointerId);document.body.classList.add('studio-resizing');event.preventDefault()}
 splitter.onpointermove=event=>{if(drag)panelWidth(drag.width+event.clientX-drag.x)}
 const endResize=()=>{if(!drag)return;panelWidth(sidebar.getBoundingClientRect().width,true);drag=null;document.body.classList.remove('studio-resizing')}
 splitter.onpointerup=endResize;splitter.onpointercancel=endResize;splitter.onlostpointercapture=endResize
 splitter.ondblclick=()=>panelWidth(400,true)
 splitter.onkeydown=event=>{const current=Number(splitter.getAttribute('aria-valuenow'));if(['ArrowLeft','ArrowRight','Home','End'].includes(event.key)){event.preventDefault();panelWidth(event.key==='Home'?400:event.key==='End'?720:current+(event.key==='ArrowLeft'?-20:20),true)}}

 // The viewport toolbar contains only viewing/pointing controls. Secondary
 // display settings are in a popover and never wrap into extra canvas rows.
 const bar=document.querySelector('.review-toolbar'),displayPanel=document.createElement('div')
 displayPanel.append(heading('显示设置'),$('three-quality'),$('show-selection').closest('label'))
 const viewLabels=[...$('three-toolbar').querySelectorAll('label')]
 for(const label of viewLabels.slice(1))displayPanel.append(label)
 const viewMenu=menu('studio-view-menu','显示',displayPanel,270)
 const comparison=document.createElement('div');comparison.className='studio-comparison';bar.append(comparison);comparison.append($('compare-before'),$('compare-after'));$('compare-before').textContent='原建筑';$('compare-after').textContent='调整后'
 const three=$('three-toolbar');three.replaceChildren(viewLabels[0]);bar.append(comparison,viewMenu)
 const photoStrip=document.querySelector('.thumbnail-card');photoStrip.id='studio-photos';photoStrip.querySelector('.inline-info').removeAttribute('open')
 const photoButton=button('studio-photo-toggle','选择图片',()=>{photoStrip.classList.toggle('photos-open');photoButton.setAttribute('aria-expanded',String(photoStrip.classList.contains('photos-open')))});photoButton.setAttribute('aria-expanded','false');photoButton.setAttribute('aria-controls','studio-photos');bar.append(photoButton)
 let compactView=false
 function fitViewport(){const compact=viewport.clientWidth<720;if(compact===compactView)return;compactView=compact;if(compact){displayPanel.append(viewLabels[0],comparison,photoButton)}else{three.append(viewLabels[0]);bar.insertBefore(comparison,viewMenu);bar.append(photoButton)}viewLabels[0].hidden=compact&&state().mode!=='3d'}
 new ResizeObserver(fitViewport).observe(viewport)
 stage.replaceChildren(viewport,photoStrip)
 checks.replaceChildren($('candidate-check-state'),$('preview-state'))
 const empty=$('empty-view');empty.innerHTML='<strong>打开建筑，开始编辑</strong><span>从项目选择已有建筑，或在设计页编写新方案。</span>'
 const emptyActions=document.createElement('div');emptyActions.className='studio-empty-actions';emptyActions.append(button('studio-browse-projects','打开项目',()=>window.creatorWorkspace.select('project')),button('studio-new-design','新建设计方案',()=>window.creatorWorkspace.select('prompt')));emptyActions.firstChild.className='primary';empty.append(emptyActions)

 const statusbar=document.createElement('footer');statusbar.id='studio-statusbar'
 const statusLink=button('studio-show-status','就绪',()=>showPanel('more'));statusLink.title='查看完整运行记录'
 statusbar.append($('status-badge'),statusLink,$('operation-count'),$('session-status'));workspace.append(statusbar)
 pages.more.append(...retained.childNodes);retained.remove()

 let inspectorOpen=true,active='tools'
 function setInspector(open){inspectorOpen=open;workspace.classList.toggle('inspector-closed',!open);toggle.textContent=open?'收起面板':'展开面板';toggle.setAttribute('aria-expanded',String(open))}
 function showPanel(name){if(!pages[name])return;active=name;for(const [key,page]of Object.entries(pages))page.hidden=key!==name;for(const b of inspectorNav.children)b.setAttribute('aria-pressed',String(b.dataset.studioPanel===name));setInspector(true)}
 showPanel('tools')
 window.addEventListener('creator-tool-select',()=>{toolChooser.open=false;if(tools.matches(':popover-open'))tools.hidePopover();const chosen=tools.querySelector('[aria-pressed=true]');toolChooser.querySelector('summary span').textContent=chosen?.textContent??'选择工具';showPanel('tools')})
 $('pick-material').addEventListener('click',()=>{if($('pick-material').getAttribute('aria-pressed')==='true'){const b=tools.querySelector('[data-tool-index="6"]');b.click()}})
 $('pick-coordinate').addEventListener('click',()=>{if($('pick-coordinate').getAttribute('aria-pressed')==='true')showPanel('notes')})
 $('validate-preview').addEventListener('click',()=>showPanel('checks'))
 window.addEventListener('creator-status',event=>{statusLink.textContent=event.detail.message;statusLink.title=event.detail.message;if(event.detail.kind==='error')showPanel(state().candidateValidation?'checks':'more')})
 const captionObserver=new MutationObserver(()=>{statusLink.textContent=$('status').textContent;statusLink.title=$('status').textContent});captionObserver.observe($('status'),{childList:true,characterData:true,subtree:true})
 function sync(){
  const s=state(),model=s.models?.find(m=>m.source===s.info?.source)
  let current=false;try{current=!!s.preview&&s.previewSettings===JSON.stringify(gather())}catch{}
  sourceMenu.querySelector('summary span').textContent=model?.name??(s.info?'当前建筑':'选择建筑')
  sourceMenu.querySelector('summary').title=s.info?.source??'选择要编辑的建筑'
  currentStep.textContent=!s.info?'尚未打开建筑':s.busy||s.previewBusy?'正在处理…':current?(s.candidateValidation?.passed?'修改预览已通过检查':'正在查看修改预览'):s.preview?'设置已改变，请更新预览':'正在查看原建筑'
  $('export-revision').title=current?'将当前候选另存为 SNBT 制作源，并在 _exports 镜像目录生成定稿 NBT':'请先预览当前参数，再定稿导出';$('validate-preview').title=current?'检查当前候选的参数、保护与改动上限':'请先预览当前参数，再检查效果'
  photoButton.hidden=s.mode==='3d';if(s.mode==='3d')photoStrip.classList.remove('photos-open')
  if(compactView)viewLabels[0].hidden=s.mode!=='3d'
  noteHint.hidden=!feedback.hidden;notePick.disabled=$('pick-coordinate').disabled
  $('studio-panel-notes').textContent='标注'+(s.notes?.length?' '+s.notes.length:'')
  if(s.versionComparing||s.transforming)currentStep.textContent=s.versionComparing?'版本对比 · 只读查看':'正在调整构件'
 }
 new MutationObserver(sync).observe(feedback,{attributes:true,attributeFilter:['hidden']})
 new MutationObserver(sync).observe($('models'),{childList:true,subtree:true})
 window.addEventListener('creator-editor-state',sync);window.addEventListener('creator-workspace-change',sync);sync()
 for(const event of ['input','change'])$('settings').addEventListener(event,()=>queueMicrotask(sync))
 const newDesign=button('studio-project-new','新建设计方案',()=>window.creatorWorkspace.select('prompt'));newDesign.className='primary';$('project-native-actions').append(newDesign)
 applyStudioCopy()
 window.creatorStudio=Object.freeze({showPanel,setInspector,current:()=>active})
}
