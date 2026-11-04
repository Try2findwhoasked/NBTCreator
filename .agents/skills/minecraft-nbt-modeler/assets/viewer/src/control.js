import {initAgentTaskReturns} from './agent-task-return.js'
import {renderDiagnostics} from './diagnostic-guidance.js'
import {linkRange} from './range-control.js'

import {initRoadPanel} from './road-panel.js'
import {initProtectionView} from './protection-view.js'
import {initWalkView} from './walk-view.js'
import {initCommentTasks} from './comment-tasks.js'
import {initDisclosureIcons} from './ui-icons.js'
import {floatingDetails,chevron} from './floating-panel.js'
import {initAssetWorkspace} from './asset-workspace.js'
import {initReusableLibrary} from './reusable-library.js'
import {initOperationHistory} from './operation-history.js'
import {initPreviewToolbar} from './preview-toolbar.js'
import {initVersionCompare} from './version-compare.js'
import {initComponentEditor} from './component-editor.js'
import {initModelPicker} from './model-picker.js'
import {initCommandCenter} from './command-center.js'
import {toolPanels as commandPanels} from './command-contract.mjs'
import {createSettingsHistory} from './settings-history.mjs'
import {createEditSessionController} from './edit-session.js'
import {initToolEffects} from './tool-effects.js'
import {initRoomScore} from './room-score.js'
import {initAppSettings} from './app-settings.js'
import {translateComponent} from './component-move.js'
import {aiBounds,aiGroupMatches,moveAIGroup,aiSurfaceOffset,aiComponentCamera} from './ai-component.mjs'
import {requestAI,cancelAI} from './ai-request.js'
import {initReferencePicker} from './reference-picker.js'
import '../../../prompt-console/catalog.js'
import './control.css'
import './prompt-panel.css'
import {initDesktop} from './desktop-adapter.js'
import {initApiAssistant} from './api-assistant.js'
import {initWorkspaceShell} from './workspace-shell.js'
import {initProjectManager} from './project-manager.js'
import {filterProjects} from './project-catalog.js'
import {initTaskRecords} from './task-records.js'
import {initHelpDialogs} from './help-dialogs.js'
import './modern.css'
import './usability.css'
import { createOrthographic } from './orthographic.js'
import { complete } from './completion.js'
import blockNames from './block-names.json'

const blockId = value => value.replace(/[^;\n]+/g, part => {
  const text=part.trim(), split=text.indexOf('['), base=split<0?text:text.slice(0,split)
  const entry=Object.entries(blockNames).find(([id,name])=>name===base)
  return (entry ? 'minecraft:'+entry[0] : base)+(split<0?'':text.slice(split))
})
function blockPicker(input) {
  input.placeholder='输入中文或 ID，也可展开列表选择'
  input.value=input.value.split(';').map(value=>{
    const text=value.trim(),split=text.indexOf('['),base=(split<0?text:text.slice(0,split)).replace(/^minecraft:/,'')
    return (blockNames[base] ?? (split<0?text:text.slice(0,split)))+(split<0?'':text.slice(split))
  }).join('; ')
  if(input.dataset.blockPicker)return
  input.dataset.blockPicker='1';input.removeAttribute('list')
  const wrapper=document.createElement('span');wrapper.className='block-select'
  input.replaceWith(wrapper);wrapper.append(input)
  const button=document.createElement('button');button.type='button';button.className='block-select-toggle';button.innerHTML=chevron
  button.setAttribute('aria-label','展开方块选择');button.title='展开中文方块列表；可输入名称或 ID 搜索'
  wrapper.append(button)
  let browse=false
  input.addEventListener('input',()=>browse=false)
  const picker=complete(input,(value,caret)=>{
    const start=value.lastIndexOf(';',Math.max(0,caret-1))+1,end=value.indexOf(';',caret),stop=end<0?value.length:end
    const current=value.slice(start,stop).trim(),base=current.split('[')[0].replace(/^minecraft:/,'')
    const exact=Object.entries(blockNames).find(([id,name])=>id===base||name===base)
    const token=browse&&exact?'':base
    if(token.includes('[')&&!browse)return null
    const frequent=['stone_bricks','cracked_stone_bricks','mossy_stone_bricks','stone','cobblestone','mossy_cobblestone','deepslate_bricks','oak_planks','spruce_planks','andesite','tuff','air']
    const entries=Object.entries(blockNames).filter(([id,name])=>!token||name.includes(token)||id.includes(token))
    if(browse)entries.sort((a,b)=>{const x=frequent.indexOf(a[0]),y=frequent.indexOf(b[0]);return (x<0?999:x)-(y<0?999:y)})
    return {range:[start,stop],items:entries.map(([id,name])=>({label:name+' · '+id,value:name,detail:'minecraft:'+id,selected:exact?.[0]===id}))}
  },()=>browse=false,{maxItems:1003,highlightSelection:true})
  button.addEventListener('mousedown',event=>event.preventDefault())
  button.addEventListener('click',()=>{if(input.disabled)return;browse=true;input.focus({preventScroll:true});requestAnimationFrame(()=>picker.refresh())})
  input.addEventListener('click',()=>{if(input.getAttribute('aria-expanded')==='true')picker.refresh()})
  input.addEventListener('keydown',event=>{if(event.altKey&&event.key==='ArrowDown'){event.preventDefault();browse=true;picker.refresh()}})
}
for(const id of ['pattern-from','weather-from','moss-state','crack-state','replace-from','replace-to','structure-state'])blockPicker(document.getElementById(id))

const $ = id => document.getElementById(id)
const state = { models: [], settings: null, info: null, bundle: '', busy: false, currentViews: [], images: [], selectedImage: null, notes: [], noteDrafts: new Map(), draftPoint: null, imageGeneration: 0, viewerGeneration: 0, mode: 'images', savingNote: false, imageLimit: 8, effectFiles: [], output: '', references: [], workspace: '', configChanged: false, previewRevision: 0, previewBusy: false, preview: null }
let operationEditor,previewToolbar,editSession,lastValidSessionSettings,versionComparison,componentEditor,apiAssistant,protectionView,walkView
async function api(route, data) {
  const response = await fetch('/__detail__/'+route, data === undefined ? {} : {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data),
  })
  const result = await response.json()
  if (!response.ok) throw new Error(result.error ?? response.statusText)
  return result
}
function status(message, kind = '') {
  if(kind==='error')document.querySelector('.result-panel').open=true
  $('status').textContent = message.length > 550 ? message.slice(0,550)+'…（完整信息见下方记录）' : message
  $('status-badge').className = 'badge '+kind
  $('status-badge').textContent = kind === 'error' ? '需处理' : kind === 'warn' ? '待复核' : kind==='cancelled'?'已取消':state.busy ? '进行中' : '就绪'
}
function number(id) {
  const value = Number($(id).value)
  if (!$(id).value.trim() || !Number.isFinite(value)) throw new Error('请填写有效数字：'+id)
  return value
}
function percent(parent, id, label, value, max = 100) {
  const row = document.createElement('label'); row.textContent = label
  const controls = document.createElement('div'); controls.className = 'percent-row'
  const slider = document.createElement('input'); slider.type = 'range'; slider.min = 0; slider.max = max; slider.step = .1; slider.value = value; slider.id = id+'-range'; slider.setAttribute('aria-label', label+'滑块')
  const input = document.createElement('input'); input.type = 'number'; input.min = 0; input.max = max; input.step = .1; input.value = value; input.id = id; input.setAttribute('aria-label', label)
  slider.addEventListener('input', () => { input.value = slider.value; updateCount() })
  input.addEventListener('input', () => { slider.value = input.value; updateCount() })
  const unit = document.createElement('span'); unit.textContent = '%'
  controls.append(slider, input, unit); row.append(controls); $(parent).append(row)
}
percent('global-fields', 'strength', '整体效果强度', 100, 200)
percent('pattern-fields', 'pattern-fraction', '原方块中有多少参与混搭', 15)
percent('weather-fields', 'moss', '表面长苔比例', 12)
percent('weather-fields', 'cracks', '表面开裂比例', 6)
percent('floor-fields', 'floor-fraction', '地面破损比例', 4)
percent('floor-fields', 'slab-share', '破损位置中使用半砖的比例', 85)
const structureMoveSync=['x','y','z'].map((axis,i)=>{const input=$('move-'+axis),slider=document.createElement('input');slider.type='range';slider.id='move-'+axis+'-range';slider.setAttribute('aria-label','局部结构移动'+axis.toUpperCase()+'滑块');input.after(slider);return linkRange(input,slider,()=>{const size=state.info?.size[i]??65,lo=Number($('lo-'+axis).value),hi=Number($('hi-'+axis).value);return [-lo,size-1-hi]})})


// Show one parameter group at a time; values remain mounted when switching.
const toolPanels=[...document.querySelectorAll('#settings > .card')]
const toolLabels=Object.fromEntries(commandPanels.map(([label,index])=>[index,label]))
const toolOrder=commandPanels.map(([,index])=>index)
function selectTool(index){
  toolPanels.forEach((panel,i)=>{panel.hidden=i!==index;if(i===index&&panel.tagName==='DETAILS')panel.open=true})
  ;[...$('tool-tabs').children].forEach(button=>button.setAttribute('aria-pressed',String(Number(button.dataset.toolIndex)===index)))
}
toolOrder.forEach(index=>{
  const button=document.createElement('button');button.type='button';button.textContent=toolLabels[index];button.dataset.toolIndex=index
  button.addEventListener('click',()=>selectTool(index));$('tool-tabs').append(button)
})
selectTool(0)
for(const [kind,[label]]of Object.entries(globalThis.NbtToolCatalog.tools)){const option=document.createElement('option');option.value=kind;option.textContent=label;$('operation-kind').append(option)}
function syncToolAvailability(){$('operation-add').disabled=state.busy||!$('operation-kind').value||!!window.nbtDisabledTools?.has($('operation-kind').value)}
window.addEventListener('creator-tool-preferences',()=>queueMicrotask(syncToolAvailability))
$('operation-kind').addEventListener('change',syncToolAvailability)
$('operation-add').onclick=()=>{try{const kind=$('operation-kind').value;if(window.nbtDisabledTools?.has(kind))throw Error('该工具已在设置中停用');if(!kind)throw Error('请先在设置中启用工具');const [label,defaults]=globalThis.NbtToolCatalog.tools[kind];const op={kind,...structuredClone(globalThis.NbtToolCatalog.common),...structuredClone(defaults),label};if(kind==='auto_floor'){delete op.lo;delete op.hi;op.include_boxes=[]}const list=JSON.parse($('operation-sequence').value);if(!Array.isArray(list))throw Error('序列须为数组');list.push(op);operationEditor.replace(list,'添加：'+label)}catch(e){status(e.message,'error')}}
$('operation-clear').onclick=()=>operationEditor.replace([],'清空工具序列')

function addMaterial(material = '', weight = 1) {
  const row = document.createElement('div'); row.className = 'palette-row'
  const name = document.createElement('input'); name.value = material; name.placeholder = 'minecraft:stone_bricks'; name.setAttribute('aria-label', '替换后的方块')
  const amount = document.createElement('input'); amount.type = 'number'; amount.min = 0; amount.step = .1; amount.value = weight; amount.setAttribute('aria-label', '方块份数')
  const remove = document.createElement('button'); remove.type = 'button'; remove.textContent = '×'; remove.setAttribute('aria-label', '删除材质')
  remove.addEventListener('click', () => { row.remove(); updateRatios();$('settings').dispatchEvent(new Event('input',{bubbles:true})) }); amount.addEventListener('input', updateRatios)
  row.append(name, amount, remove); blockPicker(name); $('palette').append(row); updateRatios()
}
function updateRatios() {
  const values = [...$('palette').querySelectorAll('.palette-row')].map(row => Number(row.children[1].value) || 0)
  const sum = values.reduce((a, b) => a+b, 0)
  $('palette-ratios').textContent = sum > 0 ? '实际使用比例：'+values.map(v => (v/sum*100).toFixed(1)+'%').join(' / ') : '至少给一种方块填写大于 0 的份数'
}
const sourceList = id => blockId($(id).value).split(/[;\n]+/).map(v => v.trim()).filter(Boolean)
function gather() {
  const palette = [...$('palette').querySelectorAll('.palette-row')].map(row => ({ state: blockId(row.querySelector('[data-block-picker]').value.trim()), weight: Number(row.children[1].value) }))
  return {
    operations:JSON.parse($('operation-sequence').value),
    structure:{enabled:$('structure-enabled').checked,mode:$('structure-mode').value,state:blockId($('structure-state').value.trim()),classification:$('structure-classification').value,thickness:number('structure-thickness'),offset:['move-x','move-y','move-z'].map(number)},
    replace:{enabled:$('replace-enabled').checked,from_states:sourceList('replace-from'),state:blockId($('replace-to').value.trim()),scope:$('replace-scope').value},
    strength: number('strength'), seed: number('seed'), style_note: $('style-note').value, max_changed_blocks: number('budget'),
    whole_region: $('whole-region').checked, lo: ['lo-x','lo-y','lo-z'].map(number), hi: ['hi-x','hi-y','hi-z'].map(number),
    pattern: { enabled: $('pattern-enabled').checked, fraction: number('pattern-fraction')/100, mode: $('pattern-mode').value, scale: number('noise-scale'), scope: $('pattern-scope').value, from_states: sourceList('pattern-from'), palette },
    weathering: { enabled: $('weather-enabled').checked, from_states: sourceList('weather-from'), moss_fraction: number('moss')/100, cracks_fraction: number('cracks')/100,
      moss_state: blockId($('moss-state').value.trim()), crack_state: blockId($('crack-state').value.trim()), patch_size: [number('moss-min'),number('moss-max')], crack_length: [number('crack-min'),number('crack-max')] },
    floor: { enabled: $('floor-enabled').checked, profile: $('floor-profile').value, fraction: number('floor-fraction')/100, slab_share: number('slab-share')/100,
      patch_size: [number('floor-min'),number('floor-max')], pit_depth: number('pit-depth'), route_margin: number('route-margin'), exclude_boxes: JSON.parse($('floor-excludes').value), slab_overrides: JSON.parse($('slab-overrides').value) },
  }
}
function request() {
  if(state.info&&$('source').value.trim()!==state.info.source)throw new Error('建筑路径已改变，请先打开该建筑再保存效果或生成方案')
  return { schema_version: 1, source: $('source').value.trim(), source_sha256: state.info?.source_sha256, context: $('context').value.trim(), cameras: $('cameras').value.trim(), review: $('review').value.trim(), settings: gather() }
}
async function captureViewport(isCancelled=()=>false){
 const source=state.info?.source,sha=state.info?.source_sha256,started=Date.now()
 while(state.busy||state.previewBusy||state.commitBusy||state.sessionRestoring){
  if(isCancelled())throw Error('API请求已取消')
  if(Date.now()-started>15000)throw Error('预览仍在运行，尚未向API发送内容；请完成当前任务后重试，或关闭该工作流的截图开关')
  await new Promise(resolve=>setTimeout(resolve,100))
 }
 if(source!==state.info?.source||sha!==state.info?.source_sha256)throw Error('等待截图时建筑已切换，请重新生成')
 const viewer=$('viewer').contentWindow?.nbtModeler
 if(state.mode==='3d'&&viewer?.status==='ready')return viewer.captureCurrent()
 const img=$('review-image')
 if(state.info&&img.complete&&img.naturalWidth){const canvas=document.createElement('canvas'),ratio=Math.min(1,1280/Math.max(img.naturalWidth,img.naturalHeight));canvas.width=Math.max(1,Math.round(img.naturalWidth*ratio));canvas.height=Math.max(1,Math.round(img.naturalHeight*ratio));canvas.getContext('2d').drawImage(img,0,0,canvas.width,canvas.height);return {dataUrl:canvas.toDataURL('image/jpeg',.82),width:canvas.width,height:canvas.height}}
 throw Error('没有可用的建模视口，请先打开3D或建筑图片，或关闭该工作流的截图开关')
}
let promptLoaded=false
initReferencePicker({api})
window.nbtPromptStorage=Object.freeze({save:payload=>api('prompt-save',payload)})
// The iframe gets only prompt generation, never the native API/key management bridge.
window.nbtPromptAI=Object.freeze({
 config:()=>window.nbtDesktop?.apiConfig?.()??Promise.resolve({enabled:false,available:false}),
 generate:instruction=>{if(!window.nbtDesktop?.apiGenerate)throw Error('AI 需要 Electron 桌面版');return requestAI({mode:'prompt',instruction,context:null},captureViewport)},
 generateWorkbench:(instruction,context)=>{if(!window.nbtDesktop?.apiGenerate)throw Error('AI需要Electron桌面版');return requestAI({mode:'workbench',instruction,context},captureViewport)},
 cancel:()=>cancelAI(),
 settings:()=>$('open-api').click()
})
async function syncPrompt(){
  const label=$('prompt-sync-status');$('sync-prompt').disabled=true
  try{
    if(!state.info)throw new Error('请先在细节控制台打开建筑；新建任务可直接编辑提示词')
    label.textContent='正在读取当前建筑、参数和保护配置…'
    const req=request(),result=await api('prompt-export',req)
    const selected=state.models.find(m=>m.source===result.source)
    $('prompt-frame').contentWindow.NbtPromptUI.receive({...result,name:selected?.name,buildingShape:selected?.shape,
      contextPath:req.context,reviewPath:req.review,output:state.info?.workdir??state.output,budget:req.settings.max_changed_blocks})
    label.textContent='已载入当前建筑与参数；面板修改只用于生成提示词'
  }catch(error){label.textContent=error.message}
  finally{$('sync-prompt').disabled=false}
}
$('open-prompt').addEventListener('click',()=>{
  if(!$('prompt-dialog').open)$('prompt-dialog').show()
  window.creatorWorkspace?.opened('prompt')
  if(!promptLoaded){
    const frame=$('prompt-frame');frame.addEventListener('load',()=>{promptLoaded=true;$('prompt-sync-status').textContent='新建初稿方案；修改已有作品时请主动载入当前建筑'},{once:true})
    frame.src='/__detail__/prompt/index.html'
  }else $('prompt-sync-status').textContent='保留上次编辑。需要更新时点击“载入当前建筑与参数”（替换工具序列）'
})
$('sync-prompt').addEventListener('click',syncPrompt)
$('prompt-new').addEventListener('click',()=>{if(!promptLoaded)return;$('prompt-frame').contentWindow.NbtPromptUI.newDraft();$('prompt-sync-status').textContent='新建初稿方案：形状、尺寸与保存位置按 skill 规范自动填写'})
$('close-prompt').addEventListener('click',()=>$('prompt-dialog').close())
for(const [button,target]of [['prompt-import','import'],['prompt-save','save'],['prompt-reset','reset']])$(button).addEventListener('click',()=>$('prompt-frame').contentDocument?.getElementById(target)?.click())
function setValue(id, value) {
  $(id).value = value
  if ($(id+'-range')) $(id+'-range').value = value
}
function restore(s) {
  $('operation-sequence').value=JSON.stringify(s.operations??[],null,2)
  operationEditor?.sync()
  state.settings = structuredClone(s)
  const structure=s.structure ?? {enabled:false,mode:'fill',state:'stone_bricks',classification:'body',thickness:1,offset:[0,0,0]}
  $('structure-enabled').checked=structure.enabled;setValue('structure-mode',structure.mode);setValue('structure-state',structure.state);setValue('structure-classification',structure.classification);setValue('structure-thickness',structure.thickness);['move-x','move-y','move-z'].forEach((id,i)=>setValue(id,structure.offset[i]))
  const replacement=s.replace ?? {enabled:false,from_states:['stone_bricks'],state:'andesite',scope:'surface'}
  $('replace-enabled').checked=replacement.enabled;setValue('replace-from',replacement.from_states.join('; '));setValue('replace-to',replacement.state);setValue('replace-scope',replacement.scope)
  setValue('strength', s.strength); setValue('seed', s.seed); setValue('style-note', s.style_note); setValue('budget', s.max_changed_blocks)
  $('whole-region').checked = s.whole_region
  ;['x','y','z'].forEach((axis, i) => { setValue('lo-'+axis,s.lo[i]); setValue('hi-'+axis,s.hi[i]) })
  $('pattern-enabled').checked=s.pattern.enabled; setValue('pattern-fraction',s.pattern.fraction*100); setValue('pattern-mode',s.pattern.mode); setValue('noise-scale',s.pattern.scale); setValue('pattern-scope',s.pattern.scope); setValue('pattern-from',s.pattern.from_states.join('; '))
  $('palette').replaceChildren(); s.pattern.palette.forEach(p => addMaterial(p.state,p.weight))
  $('weather-enabled').checked=s.weathering.enabled; setValue('moss',s.weathering.moss_fraction*100); setValue('cracks',s.weathering.cracks_fraction*100); setValue('weather-from',s.weathering.from_states.join('; ')); setValue('moss-state',s.weathering.moss_state); setValue('crack-state',s.weathering.crack_state)
  setValue('moss-min',s.weathering.patch_size[0]);setValue('moss-max',s.weathering.patch_size[1]);setValue('crack-min',s.weathering.crack_length[0]);setValue('crack-max',s.weathering.crack_length[1])
  $('floor-enabled').checked=s.floor.enabled;setValue('floor-profile',s.floor.profile);setValue('floor-fraction',s.floor.fraction*100);setValue('slab-share',s.floor.slab_share*100);setValue('floor-min',s.floor.patch_size[0]);setValue('floor-max',s.floor.patch_size[1]);setValue('pit-depth',s.floor.pit_depth);setValue('route-margin',s.floor.route_margin)
  for(const id of ['pattern-from','weather-from','moss-state','crack-state','replace-from','replace-to','structure-state'])blockPicker($(id))
  setValue('floor-excludes',JSON.stringify(s.floor.exclude_boxes,null,2));setValue('slab-overrides',JSON.stringify(s.floor.slab_overrides,null,2)); updateCount()
}
function updateCount() {
  structureMoveSync.forEach(sync=>sync())
  operationEditor?.sync()
  let extra=0;try{const operations=JSON.parse($('operation-sequence').value);if(Array.isArray(operations))extra=operations.filter(op=>op?.enabled!==false).length}catch{}
  const count = ['structure-enabled','replace-enabled','pattern-enabled','weather-enabled','floor-enabled'].filter(id => $(id).checked).length+extra
  $('operation-count').textContent = count ? `${count} 项工具已启用 · 总体强度 ${$('strength').value}%` : '所有工具当前关闭'
  syncWorkspace();syncSelectionRange()
  $('copy-agent-plan').disabled = state.busy || !state.bundle || !state.agentText
  $('apply').disabled = state.busy || !state.bundle || !$('review').value.trim()
  let currentPreview=false;try{currentPreview=!!state.preview&&state.previewSettings===JSON.stringify(gather())}catch{}
  $('validate-preview').disabled=state.busy||state.previewBusy||!currentPreview
  syncVersionReadonly()
  versionComparison?.sync()
  componentEditor?.sync()
}
const taskControlStates=new Map(),readonlyControlStates=new Map()
function syncVersionReadonly(){
 const locked=!!(state.versionComparing||state.transforming)
 document.querySelector('.sidebar').inert=locked
 const disable=control=>{if(!control)return;if(!readonlyControlStates.has(control))readonlyControlStates.set(control,taskControlStates.has(control)?taskControlStates.get(control):control.disabled);control.disabled=true}
 if(locked){document.querySelector('.action-bar').inert=!!state.versionComparing||!state.previewBusy;$('feedback-card').hidden=true
  for(const button of document.querySelectorAll('.action-bar button'))if(button.id!=='cancel')disable(button)
  for(const id of ['pick-material','pick-coordinate','viewport-assets','update-preview','validate-preview','compare-before','compare-after','three-quality','view-select','auto-preview','show-selection'])disable($(id))
  if(state.transforming)disable($('open-version-compare'))
 }else if(readonlyControlStates.size){
  // Comparison and handle editing own a temporary lock above the task lock.
  // Remove that lock without granting actions which were unavailable before it.
  const restore=(control,disabled)=>{if(state.busy||taskControlStates.has(control))taskControlStates.set(control,disabled);control.disabled=state.busy||disabled}
  for(const [control,disabled]of readonlyControlStates)if(control.isConnected)restore(control,disabled)
  readonlyControlStates.clear()
  restore($('update-preview'),state.previewBusy||!state.info)
  for(const id of ['compare-before','compare-after'])restore($(id),state.previewBusy||!state.preview)
  let current=false;try{current=!!state.preview&&state.previewSettings===JSON.stringify(gather())}catch{}
  restore($('validate-preview'),state.previewBusy||!current)
 }
}
function busy(value) {
  state.busy = value
  // A task temporarily locks controls; it does not grant unavailable actions.
  if(value){
   const controls=[...document.querySelectorAll('button')].filter(button=>button.id!=='cancel'&&button.id!=='open-command-center'&&!button.closest('#command-dialog,#project-batch-dialog,#component-author'))
   controls.push(...document.querySelectorAll('.sidebar input, .sidebar select, .sidebar textarea'))
   for(const control of controls){if(!taskControlStates.has(control))taskControlStates.set(control,control.disabled);control.disabled=true}
  }else{for(const [control,disabled]of taskControlStates)if(control.isConnected)control.disabled=disabled;taskControlStates.clear()}
  $('compare-before').disabled=value||!state.preview;$('compare-after').disabled=value||!state.preview
  $('pick-material').disabled=value||state.mode!=='3d';$('pick-coordinate').disabled=value||state.mode!=='3d';
  $('export-revision').disabled=value||!state.info;
  $('cancel').disabled = !(value||state.previewBusy); $('pause-3d').disabled=state.mode!=='3d'; $('enable-3d').disabled=value||!state.info; $('save-feedback').disabled=value||!state.feedbackTarget||state.feedbackLoading||state.savingNote; updateCount()
  historyButtons();syncToolAvailability()
  operationEditor?.setBusy(value)
  previewToolbar?.sync(state.mode,value,!!state.info)
  syncVersionReadonly()
  for(const id of ['session-save-now','session-reload','session-valid-inputs'])if($(id))$(id).disabled=value||state.restoreSession===false
  window.dispatchEvent(new Event('creator-editor-state'))
  if (!$('status-badge').classList.contains('warn') && !$('status-badge').classList.contains('error')) $('status-badge').textContent=value?'进行中':'就绪'
}
function stashDraft() {
  if (state.noteKey) state.noteDrafts.set(state.noteKey,{text:$('feedback-text').value,points:structuredClone(state.draftPoints ?? []),references:referencedFiles().map(file=>file.id)})
}
const anchorsOf=note=>note.anchors ?? (note.point?[{kind:'image',number:note.number,...note.point}]:[])
function allMarkers(){return [...state.notes.flatMap(note=>anchorsOf(note).map(p=>({...p,status:note.status,text:note.text,noteNumber:note.number}))),...(state.draftPoints ?? []).map(p=>({...p,status:'draft'}))]}
function nextMarkerNumber(){return Math.max(0,...state.notes.map(n=>n.number),...allMarkers().map(p=>p.number))+1}
function syncMarkers(){renderPins();const viewer=$('viewer').contentWindow?.nbtModeler;if(viewer?.status==='ready')viewer.setCommentMarkers(allMarkers().filter(p=>p.kind==='voxel'))}
function focusMarker(number){
  const point=allMarkers().find(p=>p.number===number);if(!point)return
  if(point.status==='draft'){removeDraftMarker(number);return}
  if(!document.getElementById('note-'+point.noteNumber)&&state.noteRecord){$('comment-search').value='';$('comment-filter').value='all';renderNotes(state.noteRecord)}
  state.activeNote=point.noteNumber;document.getElementById('note-'+point.noteNumber)?.scrollIntoView({block:'nearest'})
  document.querySelectorAll('.feedback-note').forEach(row=>row.classList.toggle('active',row.id==='note-'+point.noteNumber));renderPins()
}
function removeDraftMarker(number){
  state.draftPoints=(state.draftPoints ?? []).filter(p=>p.number!==number)
  $('feedback-text').value=$('feedback-text').value.replace(new RegExp('(^|\\n)#'+number+'(?=\\s|$)[ \\t]*','g'),'$1')
  state.draftPoint=state.draftPoints.find(p=>p.kind==='image') ?? null;syncMessageContext();stashDraft();syncMarkers()
}
function addDraftMarker(point){
  if(state.feedbackLoading||!state.feedbackTarget)return
  if((state.draftPoints ?? []).length>=100){status('每条意见最多选100个位置，请先保存。','warn');return}
  if((state.draftPoints ?? []).some(p=>point.kind==='voxel'?p.position?.join(',')===point.position.join(','):p.kind==='image'&&Math.hypot(p.x-point.x,p.y-point.y)<.005))return
  const number=nextMarkerNumber();state.draftPoints ??=[];state.draftPoints.push({...point,number})
  const input=$('feedback-text');input.value+=(input.value&&!input.value.endsWith('\n')?'\n':'')+'#'+number+' '
  state.draftPoint=state.draftPoints.find(p=>p.kind==='image') ?? null;state.activeNote=null;syncMessageContext();stashDraft();syncMarkers()
  // Keep focus in the preview for consecutive selections; the comment field stays editable below.
}
async function activateFeedback(target){
  state.noteRecord=null
  stashDraft();const generation=state.feedbackGeneration=(state.feedbackGeneration ?? 0)+1
  state.feedbackTarget=target;state.notes=[];state.noteKey=target?.key ?? null;state.draftPoints=[];state.draftPoint=null
  $('feedback-notes').replaceChildren();$('feedback-links').replaceChildren();$('feedback-text').value='';$('feedback-file').textContent=''
  $('feedback-card').hidden=!target
  if(!target){state.feedbackLoading=false;syncMessageContext();syncMarkers();return}
  const draft=state.noteDrafts.get(target.key);state.draftPoints=structuredClone(draft?.points ?? []);state.draftPoint=state.draftPoints.find(p=>p.kind==='image') ?? null;$('feedback-text').value=draft?.text ?? ''
  state.feedbackLoading=true;$('save-feedback').disabled=true;syncMessageContext();syncMarkers()
  try{const record=await api('feedback/list',{target_id:target.id});if(generation===state.feedbackGeneration)renderNotes(record)}
  finally{if(generation===state.feedbackGeneration){state.feedbackLoading=false;$('save-feedback').disabled=state.busy||state.savingNote}}
}
function activateImageFeedback(){const image=state.selectedImage;return activateFeedback(image?{kind:'image',id:image.id,key:(image.source_sha256 ?? state.info.source_sha256)+':'+image.image_sha256,name:image.name,source:image.source}:null)}
function activateViewerFeedback(id){const meta=$('viewer').contentWindow.nbtModeler.metadata();return activateFeedback({kind:'3d',id,key:meta.source_sha256+':3d:'+meta.geometry_sha256,name:'3D 方块坐标 · '+(state.comparisonSide==='after'?'调整效果':'当前建筑'),source:state.viewerSource,geometry:meta.geometry_sha256})}
function imageMode() {
  if(state.transforming){componentEditor?.cancel().then(imageMode).catch(error=>status(error.message,'error'));return}
  if(state.versionComparing){versionComparison?.close().then(imageMode).catch(error=>status(error.message,'error'));return}
  state.mode='images';state.viewerGeneration++;$('pick-material').disabled=true
  $('pick-coordinate').disabled=true
  $('viewer').src='about:blank';$('viewer').hidden=true;$('three-toolbar').hidden=true
  $('image-toolbar').hidden=false;$('review-canvas').hidden=!state.selectedImage;$('empty-view').hidden=Boolean(state.selectedImage)
  $('pause-3d').disabled=true;$('view-hint').textContent='点击图片定位修改位置；需要旋转查看时可打开 3D。'
  activateImageFeedback().catch(error=>status(error.message,'error'))
  syncWorkspace()
  previewToolbar?.sync(state.mode,state.busy,!!state.info)
}
function imageBox() {
  const image=$('review-image'),rect=image.getBoundingClientRect()
  if (!image.naturalWidth || !rect.width) return null
  const scale=Math.min(rect.width/image.naturalWidth,rect.height/image.naturalHeight)
  const width=image.naturalWidth*scale,height=image.naturalHeight*scale
  return {left:(rect.width-width)/2,top:(rect.height-height)/2,width,height,rect}
}
function renderPins() {
  const box=imageBox();if(!box)return
  const layer=$('pin-layer');layer.style.left=box.left+'px';layer.style.top=box.top+'px';layer.style.width=box.width+'px';layer.style.height=box.height+'px';layer.replaceChildren()
  for(const note of allMarkers().filter(p=>p.kind==='image')){
    const pin=document.createElement('button');pin.className='image-pin '+note.status;pin.textContent='#'+note.number;pin.style.left=note.x*100+'%';pin.style.top=note.y*100+'%';pin.title=note.text ?? '未保存；点击移除此点';pin.classList.toggle('active',state.activeNote===note.noteNumber)
    pin.addEventListener('click',event=>{event.stopPropagation();focusMarker(note.number)})
    layer.append(pin)
  }
}
function renderNotes(record) {
  state.noteRecord=record
  state.notes=record.notes;$('feedback-file').textContent='意见文件：'+record.file
  $('feedback-notes').replaceChildren()
  const query=$('comment-search').value.toLowerCase(),filter=$('comment-filter').value
  const shown=record.notes.filter(note=>(filter==='all'||note.status===filter)&&(!query||JSON.stringify([note.text,note.number,anchorsOf(note)]).toLowerCase().includes(query)))
  $('comment-count').textContent=`${record.notes.filter(n=>n.status==='open').length} 待修改 / ${record.notes.length} 条`
  if(!shown.length){const empty=document.createElement('p');empty.className='comment-empty';empty.textContent=record.notes.length?'没有匹配的意见':'暂无已保存意见。点击画面添加位置，写下修改内容。';$('feedback-notes').append(empty)}
  for(const note of shown){
    const row=document.createElement('div');row.id='note-'+note.number;row.className='feedback-note '+note.status
    const content=document.createElement('div'),title=document.createElement('strong'),text=document.createElement('p')
    const anchors=anchorsOf(note)
    title.textContent=`意见 #${note.number} · ${note.status==='open'?'待修改':'已解决'}`
    title.title=anchors.map(p=>p.kind==='voxel'?`#${p.number}：${p.state}`:`#${p.number}：图片 ${(p.x*100).toFixed(1)}%, ${(p.y*100).toFixed(1)}%`).join('\n')
    text.textContent=note.text;content.append(title,text)
    const positions=document.createElement('div');positions.className='comment-anchor-links';for(const anchor of anchors){const b=document.createElement('button');b.type='button';b.textContent='#'+anchor.number+(anchor.kind==='voxel'?' · '+anchor.position.join(', '):' · 图片位置');b.onclick=()=>focusMarker(anchor.number);positions.append(b)}content.append(positions)
    for(const ref of note.references ?? []){const file=document.createElement('small');file.textContent='引用效果：'+ref.name;file.title=ref.path+' · SHA256 '+ref.sha256;content.append(file)}
    const toggle=document.createElement('button');toggle.textContent=note.status==='open'?'标为已解决':'重新打开'
    toggle.addEventListener('click',handle(async()=>{
      const target=state.feedbackTarget,updated=await api('feedback/status',{target_id:target.id,note_id:note.id,status:note.status==='open'?'resolved':'open'})
      if(state.feedbackTarget?.id===target.id)renderNotes(updated)
    }));row.append(content,toggle);$('feedback-notes').append(row)
  }
  syncMessageContext();syncMarkers()
}
async function selectImage(index) {
  stashDraft();const image=state.images[index];state.selectedImage=image ?? null
  const generation=++state.imageGeneration
  $('feedback-links').replaceChildren();$('feedback-notes').replaceChildren();state.notes=[]
  if(!image){$('review-canvas').hidden=true;await activateFeedback(null);syncWorkspace();return}
  $('model-hash').textContent='图片对应的建筑版本 '+(image.geometry_sha256 ?? state.info.geometry_sha256).slice(0,16)
  syncMessageContext()
  ;[...$('gallery').children].forEach((button,i)=>{button.classList.toggle('selected',i===index);button.setAttribute('aria-pressed',String(i===index))})
  $('image-select').value=index;$('review-image').src=image.url;$('original-image').href=image.url;$('original-image').hidden=false
  state.activeNote=null;syncMessageContext();syncWorkspace();
  $('feedback-image-name').textContent=image.name;$('review-image').alt='评审图片：'+image.name
  $('feedback-card').hidden=!state.selectedImage;$('review-canvas').hidden=state.mode!=='images';$('empty-view').hidden=true
  if(generation===state.imageGeneration)await activateImageFeedback()
}
function gallery(images = []) {
  stashDraft();const oldHash=state.selectedImage?.image_sha256
  state.images=images;$('gallery').replaceChildren();$('image-select').replaceChildren()
  images.forEach((image,index)=>{
    const button=document.createElement('button'),img=document.createElement('img'),label=document.createElement('span')
    img.src=image.thumbnail ?? image.url;img.loading='lazy';img.decoding='async';img.alt=image.name;label.textContent=image.name
    button.title=image.name;button.append(img,label);button.addEventListener('click',handle(()=>{imageMode();return selectImage(index)}));$('gallery').append(button)
    const option=document.createElement('option');option.value=index;option.textContent=image.name+(image.restored?' · 草稿画面':'');$('image-select').append(option)
  })
  $('image-count').textContent=images.length ? `共 ${images.length} 张，点击切换` : '这座建筑暂时没有对应的预览图'
  if(!images.length){
    const option=document.createElement('option');option.textContent='暂无预览图，可点击底部“为原建筑生成预览图”';$('image-select').append(option)
    $('original-image').hidden=true
  }
  $('image-select').disabled=!images.length
  const index=Math.max(0,images.findIndex(image=>image.image_sha256===oldHash))
  selectImage(index).catch(error=>status(error.message,'error'))
}

async function runJob(kind, overrides = {}) {
  if(state.versionComparing)throw Error('请先结束版本对比，再执行编辑、验证或导出')
  const cancelEpoch=state.cancelEpoch??0
  const payload = { kind, request: request(), bundle: state.bundle, review: $('review').value.trim() }
  Object.assign(payload.request, overrides)
  if(kind==='validate')payload.snapshot_key=state.preview?.model_key
  busy(true); status('正在执行：'+({plan:'生成计划',snapshot:'载入三维模型',prepare:'准备建筑审阅图',render:'批量保存源视图',apply:'应用已批准计划',revision:'导出建筑下一版',validate:'检查当前候选效果'}[kind] ?? kind))
  try {
    while(state.previewBusy)await new Promise(resolve=>setTimeout(resolve,100))
    if(cancelEpoch!==(state.cancelEpoch??0))throw new DOMException('任务已取消','AbortError')
    const submitted = await api('jobs', payload)
    if(cancelEpoch!==(state.cancelEpoch??0)){await api('cancel',{});throw new DOMException('任务已取消','AbortError')}
    let job
    do { await new Promise(resolve => setTimeout(resolve, 350)); job = await api('jobs/'+submitted.id) } while(job.status === 'running')
    $('jobs').textContent = `${job.kind} · ${job.status} · ${job.directory}`
    if(job.status==='cancelled')throw new DOMException(job.error||'任务已取消，诊断文件保留','AbortError')
    if (job.status !== 'complete') throw new Error(job.error ?? '任务失败')
    const result = job.result
    if(kind==='plan')state.configChanged=false
    await refreshEffects()
    $('result-log').textContent = kind==='validate'
      ? Object.entries(result.checks).map(([key,value])=>`${value.passed?'通过':'未通过'} · ${key}${value.error?'：'+value.error:''}`).join('\n')+'\n只检查当前候选，未写出正式建筑。'
      : kind === 'snapshot'
      ? `已载入 ${result.size.join(' × ')} 建筑，共 ${result.cameras.length} 个观察角度。\n`+(result.read_only_view?(result.context_warning||'当前仅作几何查看，尚无完整坐标/保护配置；没有执行通路或导出验收。'):'当前显示为所选模型；调整左侧设置不会直接改动建筑。')
      : kind === 'plan' ? `${result.operations} 项操作已编译。\n`+(result.estimates ?? []).map(e=>`${e.kind}：${e.writes} 个候选写入`).join('\n')+(result.warning?'\n估算未完成，完整原因见高级记录。':'\n这些是候选统计，不是已执行结果。')
      : result.changed_blocks !== undefined ? `新版本修改了 ${result.changed_blocks} 个方块${result.wall_membership_changes?'，另有 '+result.wall_membership_changes+' 个墙层归属变化':''}，原建筑保留。` : '结果已保存至本次独立任务目录。'
    $('advanced-log').textContent=JSON.stringify(result,null,2)
    $('result-links').replaceChildren()
    if(result.validation_download){const link=document.createElement('a');link.href=result.validation_download;link.download='validation.json';link.textContent='下载候选检查报告';$('result-links').append(link)}
    if(result.runtime_files){const label=document.createElement('span');label.textContent='已保存下一版：'+result.output;$('result-links').append(label);for(const file of result.nbt_downloads ?? []){const link=document.createElement('a');link.href=file.url;link.download=file.name;link.textContent=file.name;$('result-links').append(link)}}
    if (result.plan_download) {
      const link=document.createElement('a');link.href=result.plan_download;link.download='plan.json';link.textContent='下载修改方案（工具用）';$('result-links').append(link)
    }
    if(result.preview_source){const button=document.createElement('button');button.textContent='在 3D 中查看新版本';button.addEventListener('click',handle(()=>runJob('snapshot',{source:result.preview_source})));$('result-links').append(button)}
    if (result.bundle) state.bundle=result.bundle
    if (result.handoff_text) {
      state.agentText=result.handoff_text
      const link=document.createElement('a');link.href=result.handoff_download;link.download='交给Agent.md';link.textContent='下载给 Agent 的完整交接方案';$('result-links').append(link)
    }
    if (result.review) $('review').value=result.review
    if (result.images?.length) { imageMode(); gallery(result.images) }
    if (result.model_key) await loadViewer(result, Boolean(overrides.source))
    if(kind==='validate'){
      let host=document.querySelector('#candidate-diagnostics');if(!host){host=document.createElement('section');host.id='candidate-diagnostics';host.className='diagnostic-guidance';$('candidate-check-state').closest('.preview-controls').after(host)}renderDiagnostics(host,result.diagnostics,{isCurrent:()=>state.candidateValidation===result&&state.previewSettings===JSON.stringify(gather()),status:(text,error)=>status(text,error?'error':'')})
      state.candidateValidation=result
      $('candidate-check-state').textContent=result.passed?'当前候选检查通过 · 仍需看图确认':'候选检查未通过 · 查看下方报告'
      status(result.passed?'当前候选的参数绑定、保护和整体检查通过；未生成正式建筑，仍需看图。':'候选检查未通过，请查看检查报告并调整。',result.passed?'':'error')
    }else status(result.warning ? '方案已保存，建筑检查未通过：'+result.warning : ({plan:`Agent 交接方案已生成：${result.operations} 项操作。点击“复制给 Agent”继续，原建筑未改变。`,prepare:'建筑审阅图已保存到本建筑的 Agent交接 文件夹，目录已自动关联。请看图后，在 Agent 对话中明确是否同意继续精修。',render:'原建筑的多角度预览图已保存。',apply:'新建筑已另存，原建筑保留。',revision:'下一版建筑已保存到原工作文件夹；包含主模型、NBT切片和分层交付。',snapshot:state.mode==='3d'?'三维已按需载入；可关闭 3D 返回看图模式。':'已返回看图模式。'}[kind] ?? '完成'), result.warning ? 'warn' : '')
    return result
  } catch(error) { if(error.name!=='AbortError'&&['prepare','apply'].includes(kind))$('advanced-review').open=true;throw error } finally { busy(false) }
}
async function loadViewer(result, isNewVersion = false) {
  state.viewerModelKey=result.model_key
  result={...result,cameras:(result.cameras??[]).map(camera=>({...camera,cuts:(camera.cuts??[]).map(c=>Array.isArray(c)?{axis:c[0],position:c[1],removed_side:c[2]}:c)}))}
  stashDraft()
  state.comparisonSide=result.preview_only?(result.model_key===result.baseline_key?'before':'after'):null
  const generation=++state.viewerGeneration
  state.mode='3d';state.viewerSource=result.source ?? state.info?.source;syncWorkspace();$('image-toolbar').hidden=false;$('three-toolbar').hidden=false;$('review-canvas').hidden=true;$('feedback-card').hidden=!state.selectedImage;$('pause-3d').disabled=false
  previewToolbar?.sync(state.mode,state.busy,!!state.info)
  $('view-hint').textContent=$('three-quality').value==='fast'?'颜色用于区分朝向；看实际方块请切换材质 3D 或看图片':'材质 3D（看方块） · 左键原地转向，中键平移，滚轮前进／后退'
  state.currentViews = result.cameras
  $('view-select').replaceChildren()
  result.cameras.forEach((view, i) => { const option=document.createElement('option');option.value=i;option.textContent=({whole:'整体',entry:'入口'})[view.role ?? view.id] ?? view.role ?? view.id;$('view-select').append(option) })
  $('view-select').disabled=false
  $('view-cut').max=result.size[1]-1;$('view-cut').value=result.size[1]-1;$('cut-value').textContent='完整'
  const frame=$('viewer');frame.hidden=false;$('empty-view').hidden=true
  await new Promise((resolve,reject) => {
    let timer=setTimeout(()=>reject(new Error('三维预览初始化超时')),60000)
    frame.onload=async()=>{try{if(generation!==state.viewerGeneration){clearTimeout(timer);resolve();return};await frame.contentWindow.nbtModeler.ready;if(generation!==state.viewerGeneration){clearTimeout(timer);resolve();return};if(result.cameras.length)await frame.contentWindow.nbtModeler.renderView(result.cameras[0]);clearTimeout(timer);resolve()}catch(error){clearTimeout(timer);reject(error)}}
    frame.src=`/?model_key=${encodeURIComponent(result.model_key)}&embedded=1&quality=${$('three-quality').value}&pixelRatio=0.75&maxFps=24`
  })
  protectionView?.refresh();walkView?.sync();syncSelectionRange();$('pick-material').disabled=false;$('pick-coordinate').disabled=false;syncPicking()
  state.viewerFeedbackId=result.feedback_id;await activateViewerFeedback(result.feedback_id)
  $('model-hash').textContent=(isNewVersion?'新版本预览 ':'原建筑版本 ')+result.geometry_sha256.slice(0,16)
  syncVersionReadonly()
}
async function loadModel(preserve=false){
  await componentEditor?.cancel()
  await versionComparison?.close()
  const previous=state.info?.source_sha256
  const previousGroup=state.lastAIGroup,previousSource=state.info?.source
  lockEditorRecovery()
  try{
  await editSession?.beforeOpen()
  if(state.info&&state.info.source!==$('source').value.trim()){state.noteDrafts=new Map();state.noteKey=null;state.preview=null;state.previewSettings=null;state.comparisonSide=null;if(!preserve&&state.defaultSettings)restore(state.defaultSettings)}
  try{await loadModelCore(preserve);if(previousSource===state.info.source&&previous===state.info.source_sha256)state.lastAIGroup=previousGroup;try{lastValidSessionSettings=gather()}catch{}await editSession?.opened(state.info,(!preserve||previous!==state.info.source_sha256)&&!state.skipSessionRestore);state.skipSessionRestore=false;setResumeSource(state.info.source);notifyAIComponent(true)}
  catch(error){editSession?.resume();throw error}
  }finally{unlockEditorRecovery();protectionView?.refresh()}
}
async function loadModelCore(preserve = false) {
  state.selectionEditPicking=null;state.walkPicking=false;state.aiPlacing=null;state.assetPicking=null;state.lastAIGroup=null
  stashDraft();imageMode();busy(true)
  try {
    status('正在打开建筑及门口、通路等保护设置…')
    const previousHash=state.info?.source_sha256
    const info=await api('inspect',{source:$('source').value.trim(),image_limit:state.imageLimit});state.info=info
    projectManager.checked(info)
    if(info.agent_handoff){
      const shared=info.agent_handoff
      $('agent-handoff-path').textContent=shared.directory;$('agent-handoff-path').title=shared.directory
      if(!preserve)$('review').value=shared.review||''
    }
    const sourceIndex=state.models.findIndex(model=>model.source===info.source)
    if(sourceIndex>=0)$('models').value=sourceIndex
    if (!$('context').value.trim()) $('context').value=info.context
    if (!$('cameras').value.trim()) $('cameras').value=info.cameras
    if(!preserve){['hi-x','hi-y','hi-z'].forEach((id,i)=>setValue(id,info.size[i]-1));setValue('budget',info.suggested_budget);setValue('floor-excludes',JSON.stringify(info.suggested_floor.exclude_boxes ?? [],null,2))}
    $('model-summary').textContent=`${info.size.join(' × ')} · ${info.solid_blocks.toLocaleString()} 个实体方块 · ${info.wall_blocks.toLocaleString()} 个单独记录的墙体方块`+(info.unknown_shapes.length?`。${info.unknown_shapes.length} 类方块暂时无法自动检查能否通行。可以先生成方案，生成新建筑前仍需通过检查。`:'')+(info.conservative_obstacles?.length?`。${info.conservative_obstacles.length} 类细件仅按保守障碍检查通路，不作为可站立地面，不代表精确碰撞或游戏验收。`:'')
    if(info.editing_ready===false)$('model-summary').textContent+='。当前可查看和标注；修改前需补齐坐标配置：'+[...(info.context_readiness?.missing??[]),...(info.context_readiness?.errors??[])].join('、')
    renderMaterials();if(!preserve||previousHash!==info.source_sha256)resetSettingsHistory();gallery(info.images);if(!preserve||previousHash!==info.source_sha256)state.bundle=''
  } finally { busy(false) }
  status(state.images.length?'图片已打开。点击上方缩略图切换视角，点击大图标位置、写修改意见。':'这座建筑还没有对应的图片。可点击“为原建筑生成预览图”，或打开 3D 查看。')
  if(!preserve&&(state.defaultPreviewMode!=='images'||!state.images.length))await runJob('snapshot')
}

let catalogEpoch=0
function updateCatalog(data){
 const previous=$('source').value
 state.models=data.catalog.models;state.catalogReady=true
 renderModels(previous);projectManager.update(data.project_catalog?.models??state.models,state.workspace)
 if(state.models.length&&!state.info&&!state.busy&&(!previous||!state.models.some(item=>item.source===previous))&&$('models').value!=='')selectModel(Number($('models').value))
 if(data.catalog.migration_in_progress)status('建筑库正在按形状迁移和校验，完成后刷新列表即可。','warn')
 else if(!state.models.length)status(`未发现可载入的完整建筑。扫描目录：${data.catalog.scan_root??state.workspace+'/nbt_models'}。已检查 ${data.catalog.scanned} 个文件，${data.catalog.skipped} 个格式不支持或损坏。请确认项目根目录，或直接打开完整 NBT / 主模型。`,'warn')
}
async function initialize() {
 await settingsReady
 const epoch=++catalogEpoch
 projectManager.setLoading('正在读取建筑库…')
 try {
  const data=await api('init');if(epoch!==catalogEpoch)return
  state.defaultSettings=data.defaults
  state.workspace=data.workspace;state.output=data.output;$('save-root').value=data.output;$('output-path').textContent=data.output
  if(!state.settings){if(data.initial_request){state.skipSessionRestore=true;restore(data.initial_request.settings);for(const key of ['source','context','cameras','review'])$(key).value=data.initial_request[key] ?? ''}else restore(data.defaults)}
  updateCatalog(data)
  if(!state.sessionStartupRead){state.sessionStartupRead=true;try{const result=state.restoreSession!==false?await api('edit-sessions/recent'):{recent:null};const recent=result.recent;if(recent?.exists&&!data.initial_request){const index=state.models.findIndex(item=>item.source===recent.source);if(index>=0)selectModel(index);else{$('source').value=recent.source;$('context').value='';$('cameras').value=''}$('resume-edit').hidden=false;$('resume-edit').title=recent.source;$('resume-edit').onclick=()=>openProjectModel({source:recent.source}).catch(error=>status(error.message,'error'))}}catch(error){sessionStatus.textContent='草稿索引暂时不可用：'+error.message;sessionStatus.classList.add('session-error')}}
  await refreshEffects()
  if(data.catalog_cached){
   projectManager.setLoading('已载入建筑索引，正在后台检查新增和变更…')
   const fresh=await api('catalog');if(epoch!==catalogEpoch)return
   updateCatalog(fresh)
  }
 } finally {
  if(epoch===catalogEpoch){projectManager.setLoading('');if(!state.busy&&!state.previewBusy)busy(false)}
 }
}
function selectModel(index) {
  const item=state.models[index];if(!item)return
  editSession?.checkpoint();editSession?.flush().catch(()=>{})
  if(state.info&&state.info.source!==item.source&&state.defaultSettings)restore(state.defaultSettings)
  state.noteDrafts=new Map();state.noteKey=null
  lastValidSessionSettings=null;state.previewSettings=null;state.comparisonSide=null;state.selectedImage=null
  $('source').value=item.source;$('context').value=item.context;$('cameras').value=item.cameras;state.bundle='';state.info=null;state.pickedMaterial=null;$('picked-material').hidden=true;$('orthographic-dialog').hidden=true
  $('viewer').hidden=true;$('viewer').src='about:blank';$('empty-view').hidden=false;$('view-select').disabled=true
  state.imageLimit=state.defaultImageLimit??8;state.configChanged=false;state.activeNote=null;state.preview=null;document.querySelector('#candidate-diagnostics')?.replaceChildren();state.candidateValidation=null;$('candidate-check-state').textContent='候选尚未检查';state.previewRevision++;clearTimeout(previewTimer);$('compare-before').disabled=true;$('compare-after').disabled=true;$('preview-state').textContent='效果预览不会保存为正式建筑'
  $('model-summary').textContent='正在切换建筑…';$('result-links').replaceChildren();$('result-log').textContent='';$('status').textContent='请选择效果设置，右侧将载入对应图片。'
  imageMode();gallery([]);updateCount()
}
function handle(fn) { return async event => { try { await fn(event) } catch(error) { status(error.message,error.name==='AbortError'?'cancelled':'error') } } }
$('refresh').addEventListener('click',handle(initialize))
$('models').addEventListener('change',handle(async()=>{selectModel(Number($('models').value));await loadModel()}))
$('load').addEventListener('click',handle(()=>loadModel()))
  $('enable-3d').addEventListener('click',handle(()=>state.mode==='3d'?imageMode():runJob('snapshot')))
$('pause-3d').addEventListener('click',imageMode)
$('image-mode').addEventListener('click',imageMode)
$('image-select').addEventListener('change',handle(()=>{imageMode();return selectImage(Number($('image-select').value))}))
$('more-images').addEventListener('click',handle(async()=>{state.imageLimit=32;await loadModel(true)}))
$('review-image').addEventListener('load',renderPins)
new ResizeObserver(renderPins).observe($('review-canvas'))
$('export-revision').addEventListener('click',handle(async()=>{if(!state.preview||state.previewSettings!==JSON.stringify(gather()))throw new Error('请先更新效果预览，确认当前设置后再导出下一版');return runJob('revision')}))
$('plan').addEventListener('click',handle(()=>runJob('plan')))
$('copy-agent-plan').addEventListener('click',handle(async()=>{
  if(!state.bundle||!state.agentText)throw Error('请先生成当前参数的 Agent 修改方案')
  if(window.nbtDesktop?.copyAgentPlan)await window.nbtDesktop.copyAgentPlan(state.agentText)
  else await navigator.clipboard.writeText(state.agentText)
  status('已复制。粘贴给 Agent，由 Agent 在原建筑工作文件夹生成下一版；完成后刷新建筑列表。')
}))
$('prepare').addEventListener('click',handle(()=>runJob('prepare')))
$('render').addEventListener('click',handle(()=>runJob('render')))
$('apply').addEventListener('click',handle(()=>runJob('apply')))
$('cancel').addEventListener('click',handle(async()=>{state.cancelEpoch=(state.cancelEpoch??0)+1;state.previewRevision++;clearTimeout(previewTimer);await api('cancel',{});status('任务取消已处理；已产生的诊断文件保留。','cancelled')}))
$('add-material').addEventListener('click',()=>{addMaterial();$('settings').dispatchEvent(new Event('input',{bubbles:true}))})
$('settings').addEventListener('input',event=>{if(event.target.id==='materials-search'||event.target.closest('#operation-list,#ai-model-panel'))return;if(/^(lo|hi)-[xyz]$/.test(event.target.id))$('whole-region').checked=false;state.configChanged=true;state.bundle='';updateCount();const title=event.target.closest('label')?.firstChild?.textContent?.trim()||event.target.getAttribute('aria-label')||'工具参数';recordSettings('调整：'+title.slice(0,36),{group:event.target.id||''});if(event.target.id!=='style-note')schedulePreview()});$('review').addEventListener('input',updateCount)
$('settings').addEventListener('submit',event=>event.preventDefault())
$('floor-profile').addEventListener('change',()=>{
  const defaults={maintained:[0,100,3],worn:[4,85,4],ruined:[8,70,6],cavern:[6,85,5]}[$('floor-profile').value]
  setValue('floor-fraction',defaults[0]);setValue('slab-share',defaults[1]);setValue('floor-max',defaults[2])
})
$('view-select').addEventListener('change',handle(async()=>{$('view-cut').value=$('view-cut').max;$('cut-value').textContent='预设';await $('viewer').contentWindow.nbtModeler.renderView(state.currentViews[Number($('view-select').value)])}))
async function manualFilter() {
  const api=$('viewer').contentWindow?.nbtModeler;if(!api || api.status!=='ready')return
  const m=api.metadata(), y=number('view-cut');$('cut-value').textContent=y
  await api.renderView({...m.camera,layer:$('view-layer').value,lighting:m.lighting,cuts:y===Number($('view-cut').max)?[]:[{axis:'y',position:y+1,removed_side:'above'}]})
}
$('view-layer').addEventListener('change',handle(manualFilter));$('view-cut').addEventListener('change',handle(manualFilter))
$('save-preset').addEventListener('click',handle(async()=>{
  await toolEffects.captureCurrent()
}))
$('load-preset').addEventListener('click',()=>$('preset-file').click())
$('preset-file').addEventListener('change',handle(async()=>{
  const file=$('preset-file').files[0];if(!file)return
  const data=await api('resolve-request',{request:JSON.parse(await file.text())});await editSession?.beforeOpen();state.skipSessionRestore=true;restore(data.settings)
  for(const key of ['source','context','cameras','review'])$(key).value=data[key] ?? ''
  state.bundle='';await loadModel(true)
}))
let previewTimer
function schedulePreview(){
  state.previewRevision++;clearTimeout(previewTimer)
  document.querySelector('#candidate-diagnostics')?.replaceChildren();state.candidateValidation=null;$('candidate-check-state').textContent='参数已改变，需重新检查';$('validate-preview').disabled=true
  $('preview-state').textContent='设置已改变，等待更新预览…'
  if($('auto-preview').checked&&state.info&&window.creatorWorkspace?.current()==='model')previewTimer=setTimeout(()=>{if(window.creatorWorkspace.current()==='model')updatePreview().catch(error=>{$('preview-state').textContent='预览失败：'+error.message})},(state.previewDelay??1400))
}
async function updatePreview(required=false){
  await versionComparison?.close()
  if(!state.info)return
  if(state.commitBusy&&required!==true)return
  if(state.previewBusy||state.busy){if(required===true)throw Error('已有建模任务正在运行，本次未更新预览');if($('auto-preview').checked)previewTimer=setTimeout(()=>updatePreview().catch(error=>$('preview-state').textContent='预览失败：'+error.message),700);return}
  const revision=state.previewRevision,source=state.info.source,payload=request(),cancelEpoch=state.cancelEpoch??0
  state.previewBusy=true;window.dispatchEvent(new Event('creator-editor-state'));$('update-preview').disabled=true;$('preview-state').textContent='正在计算效果，仍可继续调参…'
  syncVersionReadonly()
  $('cancel').disabled=false
  document.querySelector('#candidate-diagnostics')?.replaceChildren();state.candidateValidation=null;$('candidate-check-state').textContent='候选尚未检查';$('validate-preview').disabled=true
  try{
    const submitted=await api('jobs',{kind:'preview',request:payload})
    if(cancelEpoch!==(state.cancelEpoch??0)){await api('cancel',{});throw new DOMException('预览已取消','AbortError')}
    let job;do{await new Promise(resolve=>setTimeout(resolve,300));job=await api('jobs/'+submitted.id)}while(job.status==='running')
    if(job.status==='cancelled'||cancelEpoch!==(state.cancelEpoch??0))throw new DOMException('预览已取消，原稿保留','AbortError')
    if(job.status!=='complete'){await protectionView?.conflict(job.error_details,job.error);throw new Error(job.error ?? '计算失败')}
    if(revision!==state.previewRevision||source!==state.info?.source){if(required===true)throw Error('建筑或参数在计算期间改变，本次预览未采用');return}
    state.preview=job.result;state.previewSettings=JSON.stringify(payload.settings)
    await showComparison('after')
    if(required===true&&(state.previewSettings!==JSON.stringify(gather())||$('viewer').contentWindow?.nbtModeler?.metadata().geometry_sha256!==job.result.geometry_sha256))throw Error('当前3D画面未与本次参数一致，请重新更新预览')
    $('compare-before').disabled=false;$('compare-after').disabled=false
    $('preview-state').textContent=`调整效果 · ${job.result.changed_blocks} 个方块变化${job.result.wall_membership_changes?' · '+job.result.wall_membership_changes+' 个墙层归属变化':''} · 仅预览，未生成正式建筑`
    status('参数效果预览已更新。用“看原建筑 / 看调整效果”在同一视角对比；保存调整设置可留存当前配方。')
  }finally{state.previewBusy=false;$('update-preview').disabled=false;$('cancel').disabled=!state.busy;updateCount();window.dispatchEvent(new Event('creator-editor-state'))}
}
async function showComparison(side){
  const result=state.preview;if(!result)return
  const previousViewer=$('viewer').contentWindow?.nbtModeler,previousView=state.mode==='3d'&&previousViewer?.status==='ready'?previousViewer.metadata():null
  state.comparisonSide=null
  const generation=state.comparisonGeneration=(state.comparisonGeneration ?? 0)+1
  const key=side==='before'?result.baseline_key:result.model_key
  $('compare-before').setAttribute('aria-pressed',String(side==='before'));$('compare-after').setAttribute('aria-pressed',String(side==='after'))
  // Material changes need textures: normal-color geometry mode cannot show mixing.
  if(state.mode!=='3d'||$('viewer').contentWindow?.nbtModeler?.status!=='ready'||$('three-quality').value!=='balanced'){
    $('three-quality').value='balanced';await loadViewer({...result,model_key:key,feedback_id:side==='before'?result.baseline_feedback_id:result.feedback_id},false)
    if(previousView)await $('viewer').contentWindow.nbtModeler.renderView({...previousView.camera,cuts:previousView.cuts,layer:previousView.layer,lighting:previousView.lighting})
  }else{
    const response=await fetch('/__nbt_modeler__/model.json?model_key='+encodeURIComponent(key));if(!response.ok)throw new Error('预览读取失败')
    const snapshot=await response.json();if(generation!==state.comparisonGeneration)return
    await $('viewer').contentWindow.nbtModeler.replaceSnapshot(snapshot)
  }
  if(generation!==state.comparisonGeneration)return
  state.viewerModelKey=key;protectionView?.sync();walkView?.sync();state.comparisonSide=side
  state.viewerFeedbackId=side==='before'?result.baseline_feedback_id:result.feedback_id;await activateViewerFeedback(state.viewerFeedbackId)
  $('workspace-context').textContent=`${modelName()} · ${side==='before'?'原建筑':'参数调整效果'} · 同一视角对比，仅预览`
  $('model-hash').textContent=side==='before'?'原建筑':'效果预览（未保存为正式建筑）'
}
$('auto-preview').addEventListener('change',()=>{if($('auto-preview').checked)schedulePreview();else clearTimeout(previewTimer)})
$('update-preview').addEventListener('click',handle(updatePreview))
$('validate-preview').addEventListener('click',handle(()=>{
  if(!state.preview||state.previewSettings!==JSON.stringify(gather()))throw Error('请先更新当前参数的效果预览')
  return runJob('validate')
}))
$('compare-before').addEventListener('click',handle(()=>showComparison('before')))
$('compare-after').addEventListener('click',handle(()=>showComparison('after')))
function modelName(source=state.info?.source){return state.models.find(model=>model.source===source)?.name ?? source?.split(/[\\/]/).slice(-3).join(' / ') ?? '尚未选择建筑'}
function syncWorkspace(){
  const view=state.mode==='3d'?'3D 观察':state.selectedImage?.name ?? '暂无图片'
  const source=state.mode==='3d'?state.viewerSource:state.selectedImage?.source ?? state.info?.source
  $('workspace-context').textContent=`${modelName(source)} · ${view} · ${state.configChanged?'设置已修改，等待效果预览':'显示已保存的建筑'}`
}
function syncMessageContext(){
  $('comment-length').textContent=$('feedback-text').value.length+' / 4000'
  const target=state.feedbackTarget,points=state.draftPoints ?? []
  $('feedback-context').textContent=target?`${modelName(target.source)} · ${target.name}`:'请先打开图片或3D'
  $('feedback-context').title=[target?.source,target?.name,target?.geometry].filter(Boolean).join('\n')
  $('draft-point').textContent=points.length?`${points.length} 个点 · 未保存`:`${target?.kind==='3d'?'整座建筑':'整图'} · 未保存`
  $('feedback-text').placeholder=`${target?.kind==='3d'?'点“3D选点评论”，连续点击建筑表面。':'连续点击大图选择多个位置。'}每个点自动插入 #1、#2…，在编号后写对应意见；点击未保存的编号可移除该点。输入 @ 引用效果文件；Tab 补全。点“保存这条意见”才会保存文字和全部位置。`
  $('export-feedback').textContent=target?.kind==='3d'?'下载3D修改意见':'下载这张图的修改意见'
  $('draft-markers').replaceChildren()
  for(const point of points){const chip=document.createElement('button');chip.type='button';chip.textContent='#'+point.number+(point.kind==='voxel'?' ('+point.position.join(', ')+')':'')+' ×';chip.title='移除此标记';chip.addEventListener('click',()=>removeDraftMarker(point.number));$('draft-markers').append(chip)}
  syncReferences()
}
function referencedFiles(){return state.effectFiles.filter(file=>$('feedback-text').value.includes('@['+file.name+']'))}
function syncReferences(){
  $('reference-chips').replaceChildren()
  for(const file of referencedFiles()){const chip=document.createElement('span');chip.className='file-chip';chip.textContent='效果文件：'+file.name;chip.title=file.path;$('reference-chips').append(chip)}
}
async function refreshEffects(){
  const result=await api('effects');state.effectFiles=result.files;state.output=result.root
  $('refresh-effects').title=`已找到 ${result.files.length} 个效果文件${result.truncated?'（文件较多，请选更具体的文件夹）':''}`;syncReferences()
}
function renderModels(previous=$('source').value){
  const query=$('model-search').value.toLocaleLowerCase(),history=$('model-history').checked
  const options=filterProjects(state.models,{version:history?'all':'latest',query}).map(model=>({model,index:state.models.indexOf(model)}))
  $('models').replaceChildren();const batches=new Map()
  for(const {model,index} of options){
    let group=batches.get(model.batch)
    if(!group){group=document.createElement('optgroup');group.label=model.batch||'未分组';batches.set(model.batch,group);$('models').append(group)}
    const option=document.createElement('option');option.value=index;option.textContent=model.label+(history?' · '+model.version:'');option.title=model.source;group.append(option)
  }
  const existing=options.find(item=>item.model.source===previous)
  if(existing)$('models').value=existing.index
  else if(previous){
    const index=state.models.findIndex(model=>model.source===previous)
    if(index>=0){const option=document.createElement('option');option.value=index;option.textContent='当前打开（不在筛选结果中）：'+state.models[index].label;$('models').prepend(option);$('models').value=index}
  }
  if(!options.length&&!$('models').options.length){const option=document.createElement('option');option.value='';option.textContent=state.models.length?'没有匹配的建筑，请调整搜索条件':'未发现可载入建筑，请检查工作区或直接打开 NBT';$('models').append(option)}
  $('catalog-summary').textContent=`${options.length} 个${history?'建筑版本':'建筑（每座仅列最新保存版本）'} · 已排除测试文件及同建筑的相同几何副本`
}
$('model-search').addEventListener('input',()=>renderModels())
$('model-history').addEventListener('change',()=>renderModels())
$('choose-output').addEventListener('click',handle(async()=>{const result=await api('choose-output',{});if(!result.path)return;$('save-root').value=result.path;$('set-output').click()}))
$('set-output').addEventListener('click',handle(async()=>{const result=await api('output',{output:$('save-root').value.trim()});state.effectFiles=result.files;state.output=result.root;$('save-root').value=result.root;$('output-path').textContent=result.root;syncReferences();status('默认保存位置已记住：'+result.root)}))
for(const id of ['refresh-effects','refresh-reference'])$(id).addEventListener('click',handle(refreshEffects))
complete($('feedback-text'),(value,caret)=>{
  const prefix=value.slice(0,caret),match=prefix.match(/@([^@\n]*)$/)
  if(!match||match[1].includes(']'))return null
  const query=match[1].replace(/^\[/,'').toLocaleLowerCase()
  return {range:[caret-match[0].length,caret],items:state.effectFiles.filter(file=>file.name.toLocaleLowerCase().includes(query)).map(file=>({label:file.name,value:'@['+file.name+']',detail:file.path}))}
},syncReferences)
for(const id of ['source','context','cameras'])complete($(id),(value)=>({range:[0,value.length],items:[...new Set(state.models.map(model=>model[id==='source'?'source':id]).filter(Boolean))].filter(file=>file.toLocaleLowerCase().includes(value.toLocaleLowerCase())).map(file=>({label:file,value:file}))}))
complete($('save-root'),value=>({range:[0,value.length],items:[...new Set([state.output,...state.effectFiles.map(file=>file.path.replace(/[\\/][^\\/]+$/,''))])].filter(Boolean).filter(folder=>folder!==value&&folder.toLocaleLowerCase().includes(value.toLocaleLowerCase())).map(folder=>({label:folder,value:folder}))}))
complete($('model-search'),value=>({range:[0,value.length],items:!value?[]:[...new Set(state.models.map(model=>model.name))].filter(name=>name.includes(value)&&name!==value).map(name=>({label:name,value:name}))}),()=>renderModels())
const settingsHistory=createSettingsHistory()
document.body.append($('settings-history-dialog'))
$('open-settings-history').onclick=()=>$('settings-history-dialog').showModal()
$('close-settings-history').onclick=()=>$('settings-history-dialog').close()
const historyRename=document.createElement('dialog');historyRename.id='history-rename-dialog';historyRename.innerHTML='<form method="dialog"><h3>历史记录名称</h3><label>名称<input id="history-name" maxlength="160" required></label><div class="note-actions"><button value="cancel" formnovalidate>取消</button><button id="history-name-save" value="save" class="primary">保存名称</button></div></form>';document.body.append(historyRename)
let renamingHistory=-1
historyRename.querySelector('form').addEventListener('submit',event=>{if(event.submitter?.value!=='save')return;event.preventDefault();try{settingsHistory.rename(renamingHistory,$('history-name').value);historyButtons();historyRename.close('save')}catch(error){$('history-name').setCustomValidity(error.message);$('history-name').reportValidity()}})
$('history-name').addEventListener('input',()=>$('history-name').setCustomValidity(''))
function historyButtons(){
  const entries=settingsHistory.entries,cursor=settingsHistory.cursor
  $('undo-settings').disabled=state.busy||cursor<=0
  $('redo-settings').disabled=state.busy||cursor>=entries.length-1
  $('history-current').textContent=entries.length?`当前：${entries[cursor].label} · ${cursor+1} / ${entries.length}。仅恢复本次打开建筑的候选参数。`:'打开建筑后开始记录；保存调整设置可留存方案。'
  const host=$('settings-history-list');host.replaceChildren()
  for(const entry of entries){const row=document.createElement('li'),button=document.createElement('button'),time=document.createElement('time'),rename=document.createElement('button');button.type=rename.type='button';button.textContent=entry.label;button.title=entry.label;button.dataset.historyIndex=entry.index;button.setAttribute('aria-current',String(entry.current));button.disabled=state.busy;button.onclick=()=>restoreHistory(entry.index);time.textContent=new Date(entry.at).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'});rename.className='history-rename';rename.textContent='✎';rename.setAttribute('aria-label','重命名历史：'+entry.label);rename.disabled=state.busy;rename.onclick=()=>{renamingHistory=entry.index;$('history-name').value=entry.label;historyRename.returnValue='';historyRename.showModal()};row.append(button,time,rename);host.append(row)}
}
function resetSettingsHistory(){settingsHistory.reset(gather());historyButtons()}
function recordSettings(label='调整参数',options={}){
  try{if(settingsHistory.record(gather(),label,options))historyButtons()
  }catch{} // Keep incomplete numeric edits out of the history.
}
function restoreHistory(index){
  if(state.busy)return;const next=settingsHistory.jump(index);if(!next)return
  restore(next);state.lastAIGroup=null;state.configChanged=true;state.bundle='';historyButtons();schedulePreview()
}
function travelSettings(direction){restoreHistory(settingsHistory.cursor+direction)}
$('undo-settings').addEventListener('click',()=>travelSettings(-1));$('redo-settings').addEventListener('click',()=>travelSettings(1))
operationEditor=initOperationHistory({onChange:label=>{state.lastAIGroup=null;state.configChanged=true;state.bundle='';updateCount();recordSettings(label);schedulePreview()},onError:message=>status(message,'error')})
function renderMaterials(){
  const query=$('materials-search').value.toLocaleLowerCase();$('model-materials').replaceChildren()
  const materials=(state.info?.materials ?? []).filter(item=>{
    const id=item.state.replace(/^minecraft:/,'').split('[')[0],name=blockNames[id] ?? id
    return (name+' '+item.state).toLocaleLowerCase().includes(query)
  })
  for(const item of materials.slice(0,100)){
    const row=document.createElement('div');row.className='material-sample'
    const id=item.state.replace(/^minecraft:/,'').split('[')[0],label=document.createElement('span');label.textContent=(blockNames[id] ?? id)+' × '+item.count;label.title=item.state
    const add=document.createElement('button');add.type='button';add.textContent='加入混搭';add.title='将此方块及其状态加入混搭材质列表'
    add.addEventListener('click',()=>{addMaterial(item.state,1);recordSettings();state.configChanged=true;state.bundle='';updateCount();schedulePreview();add.textContent='已加入混搭'})
    row.append(label,add);$('model-materials').append(row)
  }
  if(!materials.length)$('model-materials').textContent=state.info?'没有匹配的方块':'先打开建筑，再查看它使用的方块'
}
$('materials-search').addEventListener('input',renderMaterials)
$('edit-structure-region').addEventListener('click',()=>{selectTool(4);$('whole-region').checked=false;$('lo-x').focus()})
function syncSelectionRange(){
  const viewer=$('viewer').contentWindow?.nbtModeler
  if(viewer?.status!=='ready'||!state.info)return
  if(state.versionComparing||state.transforming){viewer.setSelectionRange(null);return}
  const lo=$('whole-region').checked?[0,0,0]:['lo-x','lo-y','lo-z'].map(id=>Number($(id).value))
  const hi=$('whole-region').checked?state.info.size.map(v=>v-1):['hi-x','hi-y','hi-z'].map(id=>Number($(id).value))
  viewer.setSelectionRange($('show-selection').checked?{lo,hi}:null);protectionView?.sync()
}
$('show-selection').addEventListener('change',syncSelectionRange)
function syncPicking(){
  if(state.assetPicking||state.aiPlacing||state.picking||state.coordinatePicking||state.transforming)state.selectionEditPicking=null
  if(state.assetPicking||state.aiPlacing||state.picking||state.coordinatePicking||state.transforming)state.walkPicking=false
  $('pick-material').setAttribute('aria-pressed',String(Boolean(state.picking)))
  const materialCaption=$('pick-material').querySelector('.toolbar-caption');if(materialCaption)materialCaption.textContent=state.picking?'结束取材':'取材'
  $('pick-coordinate').setAttribute('aria-pressed',String(Boolean(state.coordinatePicking)))
  const commentCaption=$('pick-coordinate').querySelector('.toolbar-caption');if(commentCaption)commentCaption.textContent=state.coordinatePicking?'结束标注':'标注'
  $('viewer').contentWindow?.nbtModeler?.setPicking(Boolean(state.selectionEditPicking||state.walkPicking||state.assetPicking||state.aiPlacing||state.picking||state.coordinatePicking),state.selectionEditPicking?'selection-edit':state.coordinatePicking?'comment':'material')
}
window.addEventListener('keydown',event=>{if(event.key==='Escape'&&state.selectionEditPicking){state.selectionEditPicking=null;syncPicking();$('view-hint').textContent='已取消编辑选区选择。'}})
$('pick-coordinate').addEventListener('click',()=>{
  state.walkPicking=false;state.assetPicking=null;state.aiPlacing=null;state.coordinatePicking=!state.coordinatePicking;state.picking=false;syncPicking()
  $('view-hint').textContent=state.coordinatePicking?'连续点击表面添加 #编号，下面按编号写意见；中键平移，滚轮前进／后退。':'左键原地转向，中键平移，滚轮前进／后退'
})
$('pick-material').addEventListener('click',()=>{
  state.walkPicking=false;state.assetPicking=null;state.aiPlacing=null;state.picking=!state.picking;state.coordinatePicking=false;syncPicking()
  if(state.picking)$('view-hint').textContent='点击可见方块取材；中键可平移。取材后在左侧选择用途。'
})
window.addEventListener('message',event=>{
  if(event.origin!==location.origin||event.source!==$('viewer').contentWindow)return
  if(event.data?.type==='nbt-pick-cancelled'){state.selectionEditPicking=null;syncPicking();return}
  if(event.data?.type==='nbt-annotation-focused'){focusMarker(event.data.number);return}
  if(!['nbt-material-picked','nbt-coordinate-picked'].includes(event.data?.type))return
  const picked=event.data.result
  if(!picked){$('view-hint').textContent='此处没有选到可见方块，请点击建筑表面。';return}
  if(typeof picked.state!=='string'||!Array.isArray(picked.position)||picked.position.length!==3)return
  if(picked.geometry_sha256!==$('viewer').contentWindow.nbtModeler.metadata().geometry_sha256)return
  if(state.selectionEditPicking){
    const pick=state.selectionEditPicking
    if(pick.geometry!==picked.geometry_sha256||pick.source!==state.info?.source){state.selectionEditPicking=null;syncPicking();status('选点期间画面已变化，请重新选择。','warn');return}
    pick.points.push(picked.position)
    if(pick.points.length===1){$('view-hint').textContent='已选第一个角点 '+picked.position.join(', ')+'；再选一个已有方块作为另一个角点。';return}
    const lo=[0,1,2].map(i=>Math.min(pick.points[0][i],pick.points[1][i])),hi=[0,1,2].map(i=>Math.max(pick.points[0][i],pick.points[1][i]));state.selectionEditPicking=null;syncPicking()
    if(lo.reduce((v,n,i)=>v*(hi[i]-n+1),1)>65536){status('选区超过65536格，请重新选择更小范围。','warn');return}
    $('whole-region').checked=false;['x','y','z'].forEach((axis,i)=>{setValue('lo-'+axis,lo[i]);setValue('hi-'+axis,hi[i])});state.bundle='';updateCount();recordSettings('AI编辑选区');schedulePreview();syncSelectionRange();$('view-hint').textContent='编辑范围 '+lo.join(', ')+' → '+hi.join(', ')+'；可调整XYZ后描述修改要求。';return
  }
  if(state.walkPicking&&walkView?.consumePick(picked))return
  if(componentEditor?.consumePick(picked))return
  if(state.assetPicking){const callback=state.assetPicking;state.assetPicking=null;syncPicking();Promise.resolve(callback(picked.position.map((v,i)=>v+(picked.normal?.[i]||0)))).catch(error=>status(error.message,'error'));return}
  if(state.aiPlacing){
    const placing=state.aiPlacing;state.aiPlacing=null;syncPicking()
    if(placing.move){window.dispatchEvent(new CustomEvent('nbt-ai-placement-start'));Promise.resolve().then(()=>{const group=currentAIGroup();if(!group)throw Error('最近构件已改变，请重新载入');return moveRecentAI(aiSurfaceOffset(group,picked,state.info.size))}).then(()=>{const text='最近AI构件已放置到所选表面，3D预览已更新';$('ai-placement-status').textContent=text;window.dispatchEvent(new CustomEvent('nbt-ai-placement-result',{detail:{text}}))}).catch(error=>{status(error.message,'error');window.dispatchEvent(new CustomEvent('nbt-ai-placement-result',{detail:{text:error.message,error:true}}))});return}
    try{const size=placing.size,lo=aiSurfaceOffset({base:[{lo:[0,0,0],hi:size.map(n=>n-1)}]},picked,state.info.size),hi=lo.map((v,i)=>v+size[i]-1)
     $('whole-region').checked=false;['x','y','z'].forEach((axis,i)=>{setValue('lo-'+axis,lo[i]);setValue('hi-'+axis,hi[i])});state.bundle='';updateCount();recordSettings();schedulePreview();selectTool(9)
     $('ai-placement-status').textContent='放置表面 '+picked.position.join(', ')+'；选区 '+lo.join(', ')+' → '+hi.join(', ')
    }catch(error){$('ai-placement-status').textContent=error.message;status(error.message,'error')}return
  }
  if(event.data.type==='nbt-coordinate-picked'){
    if(state.coordinatePicking&&state.feedbackTarget?.kind==='3d'&&state.feedbackTarget.geometry===picked.geometry_sha256)addDraftMarker({kind:'voxel',...picked})
    return
  }
  state.pickedMaterial=picked;const id=picked.state.split('[')[0].replace(/^minecraft:/,'')
  $('picked-material').hidden=false;$('picked-material-label').textContent=`${blockNames[id] ?? id} · 坐标 ${picked.position.join(', ')}`
  $('picked-material-state').textContent=picked.state
  selectTool(6);$('settings').scrollTop=0;$('view-hint').textContent='已取材：'+(blockNames[id] ?? id)+'。在左侧选择填入位置或加入混搭。'
})
function pickedValue(){if(!state.pickedMaterial)return null;return $('pick-exact-state').checked?state.pickedMaterial.state:state.pickedMaterial.state.split('[')[0]}
$('use-picked-material').addEventListener('click',()=>{
  const value=pickedValue();if(!value)return
  const id=$('picked-target').value;$(id).value=value;blockPicker($(id));$(id).dispatchEvent(new Event('input',{bubbles:true}))
  selectTool(id==='pattern-from'?1:id.startsWith('replace-')?5:id==='structure-state'?7:2)
})
$('add-picked-material').addEventListener('click',()=>{
  const value=pickedValue();if(!value)return;addMaterial(value,1);$('settings').dispatchEvent(new Event('input',{bubbles:true}));selectTool(1)
})
createOrthographic({getInfo:()=>state.info,getRange:()=>($('whole-region').checked&&state.info?{lo:[0,0,0],hi:state.info.size.map(v=>v-1)}:{lo:['lo-x','lo-y','lo-z'].map(id=>Number($(id).value)),hi:['hi-x','hi-y','hi-z'].map(id=>Number($(id).value))}),setRange:range=>{$('whole-region').checked=false;['x','y','z'].forEach((axis,i)=>{setValue('lo-'+axis,range.lo[i]);setValue('hi-'+axis,range.hi[i])});syncSelectionRange()}})
window.detailControl={gather,request,restore,loadModel,runJob,state,selectImage,imageMode}
async function openProjectModel(item){
 if(state.busy||state.previewBusy||state.sessionRestoring)throw Error('请等待当前任务完成')
 if(state.info?.source!==item.source){
  stashDraft()
  const index=state.models.findIndex(model=>model.source===item.source)
  if(index>=0)selectModel(index)
  else{$('source').value=item.source;$('context').value='';$('cameras').value=''}
  state.openingProjectModel=true
  try{window.creatorWorkspace.select('model');await loadModel()}finally{state.openingProjectModel=false}
 }
 window.creatorWorkspace.select('model')
 return state.info
}
const projectManager=initProjectManager({api,openModel:openProjectModel,isBusy:()=>state.busy||state.previewBusy||state.sessionRestoring,setBusy:busy,refresh:initialize})
initDesktop(source=>openProjectModel({source}))
initModelPicker()
function notifyAIComponent(restored=false){window.dispatchEvent(new CustomEvent('nbt-ai-component-state',{detail:{restored}}))}
function currentAIGroup(){try{const group=state.lastAIGroup;return group&&group.source===state.info?.source&&group.source_sha256===state.info?.source_sha256&&aiGroupMatches(group,gather())?group:null}catch{return null}}
function componentView(group){const frame=$('viewer');return aiComponentCamera(group.applied,group.camera,Math.max(1,frame.clientWidth)/Math.max(1,frame.clientHeight))}
async function commitPreviewSettings(next,label){
 const before=gather(),source=state.info?.source,sha=state.info?.source_sha256
 const oldViewer=$('viewer').contentWindow?.nbtModeler,old={preview:state.preview,settings:state.previewSettings,side:state.comparisonSide,id:state.viewerFeedbackId,source:state.viewerSource,snapshot:state.mode==='3d'&&oldViewer?.status==='ready'?oldViewer.snapshot:null,meta:state.mode==='3d'&&oldViewer?.status==='ready'?oldViewer.metadata():null}
 await api('prompt-export',{...request(),settings:next})
 if(source!==state.info?.source||sha!==state.info?.source_sha256||JSON.stringify(gather())!==JSON.stringify(before))throw Error('建筑或参数已改变，本次未应用')
 let staged=false
 try{restore(next);next=gather();staged=true;state.configChanged=true;state.bundle='';state.previewRevision++;clearTimeout(previewTimer);updateCount();await updatePreview(true);if(JSON.stringify(gather())!==JSON.stringify(next))throw Error('参数已改变，需重新更新预览');recordSettings(label)}
 catch(error){
  let unchanged=!staged;try{if(staged)unchanged=JSON.stringify(gather())===JSON.stringify(next)}catch{}
  if(source===state.info?.source&&sha===state.info?.source_sha256&&unchanged){
   restore(before);state.preview=old.preview;state.previewSettings=old.settings;state.comparisonSide=old.side;state.candidateValidation=null
   const viewer=$('viewer').contentWindow?.nbtModeler
   if(old.snapshot&&viewer?.status==='ready'){await viewer.replaceSnapshot(old.snapshot);await viewer.renderView({...old.meta.camera,cuts:old.meta.cuts,layer:old.meta.layer,lighting:old.meta.lighting});state.viewerSource=old.source;state.viewerFeedbackId=old.id;await activateViewerFeedback(old.id)}
   updateCount();$('preview-state').textContent='本次预览未应用，已保留原参数：'+error.message
  }
  throw error
 }
}
async function withPreviewCommit(action){
 if(!state.info||state.busy||state.previewBusy||state.commitBusy||state.sessionRestoring)throw Error('请等待当前建模任务完成')
 state.commitBusy=true;clearTimeout(previewTimer);window.dispatchEvent(new Event('creator-editor-state'))
 try{return await action()}finally{state.commitBusy=false;window.dispatchEvent(new Event('creator-editor-state'))}
}
function updateComponentRange(settings,bounds){
 if(!['structure','replace','pattern','weathering','floor'].some(key=>settings[key]?.enabled)){settings.whole_region=false;settings.lo=bounds.lo;settings.hi=bounds.hi}
}
async function moveRecentAI(offset,overwrite=$('ai-allow-overwrite')?.checked??false,turns=currentAIGroup()?.quarter_turns??0){return withPreviewCommit(async()=>{
 const group=currentAIGroup();if(!group)throw Error('请先载入一组AI构件；若已手动更改几何步骤，请撤销该更改或重新载入')
 const before=gather(),moved=moveAIGroup(group,before,offset,state.info.size,overwrite,turns),next=structuredClone(before);for(const op of moved.operations)op.skip_protected=$('ai-skip-protected')?.checked??false;next.operations.splice(group.start,group.base.length,...moved.operations);updateComponentRange(next,moved)
 await commitPreviewSettings(next,'调整 AI 构件：'+offset.join(', ')+' · '+(turns*90)+'°');group.applied=structuredClone(moved.operations);group.offset=[...offset];group.quarter_turns=turns;group.overwrite=!!overwrite;notifyAIComponent()
})}
const aiPromptArchiveId=crypto.randomUUID().replaceAll('-','')
apiAssistant=initApiAssistant({
 selectionContext:async allow_overwrite=>{
  if(state.selectionEditPicking)throw Error('请先完成两点选区或按Esc取消，再生成');if(!state.info||gather().whole_region)throw Error('请先选择局部编辑范围');const source=state.info.source,settings=JSON.stringify(gather())
  if(!state.preview||state.previewSettings!==settings)await updatePreview(true)
  if(source!==state.info?.source||JSON.stringify(gather())!==settings||state.previewSettings!==settings)throw Error('参数或选区已变化，请重新生成')
  await showComparison('after');const s=gather(),geometry_sha256=state.preview.geometry_sha256
  const selection=await api('selection-edit/context',{snapshot_key:state.preview.model_key,request:{source,source_sha256:state.info.source_sha256,geometry_sha256,lo:s.lo,hi:s.hi}})
  if(source!==state.info?.source||JSON.stringify(gather())!==settings)throw Error('读取期间选区已变化，请重新生成')
  return {size:state.info.size,lo:s.lo,hi:s.hi,allow_overwrite,selection}
 },
 pickEditRegion:async()=>{if(!state.info||state.busy||state.previewBusy||state.commitBusy)throw Error('请先打开建筑并等待当前任务完成');if(state.mode!=='3d')await runJob('snapshot');state.walkPicking=false;state.assetPicking=null;state.aiPlacing=null;state.picking=false;state.coordinatePicking=false;state.selectionEditPicking={source:state.info.source,geometry:$('viewer').contentWindow.nbtModeler.metadata().geometry_sha256,points:[]};syncPicking();$('view-hint').textContent='依次点击两个已有方块，取包围盒作为编辑范围；Esc取消，左键拖动仍可转向。'},
 cancelEditPick:()=>{state.selectionEditPicking=null;syncPicking()},
 archivePrompt:async(text,token)=>{const bound=JSON.parse(token);if(!bound.source)return null;if(bound.source!==state.info?.source||bound.source_sha256!==state.info?.source_sha256)throw Error('源建筑已切换，未把建议写入其他建筑');return api('prompt-save',{session_id:aiPromptArchiveId,text,document:{origin:'model_ai',source_sha256:bound.source_sha256,project:{name:modelName(),stage:'plan',source:bound.source,contextPath:$('context').value.trim(),size:state.info.size},operations:bound.settings.operations??[]},plan:{operations:bound.settings.operations??[]},context:{contextPath:$('context').value.trim()}})},
 captureViewport,isBusy:()=>state.busy||state.previewBusy||state.commitBusy||state.sessionRestoring||state.transforming||state.versionComparing,
 context:()=>{const s=gather(),info=state.info;if(!info)return null;return {size:info.size,lo:s.whole_region?[0,0,0]:s.lo,hi:s.whole_region?info.size.map(v=>v-1):s.hi,materials:info.materials,allow_overwrite:$('ai-allow-overwrite')?.checked??false}},
 binding:()=>JSON.stringify({source:state.info?.source,source_sha256:state.info?.source_sha256,settings:gather()}),
 componentState:()=>{const group=currentAIGroup();return group?{offset:group.offset??[0,0,0],quarter_turns:group.quarter_turns??0,size:state.info.size,base_bounds:aiBounds(group.base),bounds:aiBounds(group.applied),overwrite:group.overwrite,structure_name:group.structure_name??group.base[0].label,camera_details:componentView(group)}:null},
 focusComponent:async()=>{const group=currentAIGroup(),viewer=$('viewer').contentWindow?.nbtModeler;if(!group||state.busy||state.previewBusy||state.commitBusy||state.sessionRestoring||state.mode!=='3d'||viewer?.status!=='ready')throw Error('请先完成构件预览并打开3D');await viewer.setCamera(componentView(group));$('view-hint').textContent=(group.structure_name??group.base[0].label)+' · 构件观察视角';editSession?.schedule()},
 operationChoices:()=>{try{return gather().operations.map((op,index)=>({index,label:op.label,kind:op.kind}))}catch{return[]}},
 adoptComponent:(start,end)=>{if(state.busy||state.previewBusy||state.commitBusy)throw Error('请等待当前建模任务完成');const settings=gather(),operations=settings.operations.slice(start,end+1),write_group=crypto.randomUUID();if(!Number.isInteger(start)||!Number.isInteger(end)||start<0||end<start||end>=settings.operations.length||operations.some(op=>!['box','beam','frame'].includes(op.kind)))throw Error('请选择一组连续的AI方块、梁或边框步骤');state.lastAIGroup={source:state.info.source,source_sha256:state.info.source_sha256,start,base:operations.map(op=>({...structuredClone(op),write_group})),applied:structuredClone(operations),offset:[0,0,0],overwrite:$('ai-allow-overwrite').checked};notifyAIComponent();editSession?.schedule()},
 localSelection:()=>!!state.info&&!gather().whole_region,
 pickPlacement:async(size,existing=true)=>{
  if(!state.info||state.busy||state.previewBusy||state.commitBusy)throw Error('请先打开建筑并等待当前任务完成')
  if(size.some((v,i)=>v>state.info.size[i]))throw Error('放置范围大于当前建筑尺寸')
  if(state.mode!=='3d')await runJob('snapshot')
  state.walkPicking=false;state.aiPlacing={size,move:existing&&!!currentAIGroup()};state.picking=false;state.coordinatePicking=false;syncPicking();$('view-hint').textContent=state.aiPlacing.move?'点击表面放置最近一组AI构件，随后立即更新3D预览。':'点击表面选择新构件的生成范围，随后生成并预览。'
 },
 apply:async(patch,options={})=>withPreviewCommit(async()=>{
  const before=gather(),next=structuredClone(before)
  if(options.mode==='selection_edit'){
   if(state.previewSettings!==JSON.stringify(before)||state.preview?.geometry_sha256!==patch.baseline_geometry_sha256)throw Error('本次编辑参考的候选已变化，请重新生成')
   const compiled=await api('selection-edit/compile',{snapshot_key:state.preview.model_key,request:{source:state.info.source,source_sha256:state.info.source_sha256,geometry_sha256:patch.baseline_geometry_sha256,lo:patch.lo,hi:patch.hi,operations:patch.operations.filter(op=>op.enabled!==false),allow_overwrite:!!options.overwrite}})
   next.operations.push(...compiled.operations);await commitPreviewSettings(next,'AI选区编辑：'+(options.summary??'自然语言工具步骤'));state.lastAIGroup=null;notifyAIComponent();return
  }
  if(patch.operations){const write_group=crypto.randomUUID(),operations=patch.operations.map(op=>({...structuredClone(op),overwrite:!!options.overwrite,skip_protected:options.mode==='small_structure'&&!!options.skipProtected,write_group}));next.operations.push(...operations);updateComponentRange(next,patch)
   const presentation=options.presentation??{}
   await commitPreviewSettings(next,'AI：'+(presentation.structure_name||operations[0]?.label||'局部结构调整'))
   state.lastAIGroup={source:state.info.source,source_sha256:state.info.source_sha256,start:next.operations.length-operations.length,base:structuredClone(operations),applied:structuredClone(operations),offset:[0,0,0],overwrite:!!options.overwrite,...(presentation.structure_name?{structure_name:presentation.structure_name}:{}),...(presentation.camera?{camera:structuredClone(presentation.camera)}:{})};notifyAIComponent();editSession?.schedule()
  }else{next.whole_region=false;next.lo=patch.lo;next.hi=patch.hi;next.structure={...next.structure,enabled:false,...patch.structure};next.replace={...next.replace,enabled:false,...patch.replace};await commitPreviewSettings(next,'AI：局部结构调整')}
 }),
 moveComponent:moveRecentAI
})
async function applyComponentPatch(patch,expected){return withPreviewCommit(async()=>{
 const before=gather();if(expected&&expected!==JSON.stringify(before))throw Error('模型参数已改变，请重新开始放置')
 const next=structuredClone(before);next.operations.push(...patch.operations);updateComponentRange(next,patch)
 await commitPreviewSettings(next,(patch.mode==='move'?'移动选区：':'放置构件：')+(patch.name||patch.operations[0]?.label||'构件'))
})}
function reusableContext(){if(!state.info)return null;const s=gather();return {name:state.info.source.split(/[\\/]/).slice(-3).join('/'),source:state.info.source,source_sha256:state.info.source_sha256,size:state.info.size,busy:!!(state.busy||state.previewBusy||state.commitBusy||state.sessionRestoring||state.versionComparing||state.transforming),whole:s.whole_region,lo:s.whole_region?[0,0,0]:s.lo,hi:s.whole_region?state.info.size.map(v=>v-1):s.hi,operations:s.operations,settings:JSON.stringify(s),target_id:state.mode==='3d'&&state.feedbackTarget?.kind==='3d'?state.feedbackTarget.id:null}}
async function applyReusable(patch,expected){
 if(state.versionComparing||state.transforming)throw Error('请先结束版本对比或手柄调整')
 const previous=window.creatorWorkspace.current(),dialogs=['asset-inspector-dialog','reusable-dialog'].map(id=>$(id)).filter(d=>d?.open)
 window.creatorWorkspace.select('model')
 try{await applyComponentPatch(patch,expected)}catch(error){window.creatorWorkspace.select(previous);for(const dialog of dialogs)if(!dialog.open)dialog.showModal();throw error}
}
function captureToolEffect(){
 const settings=structuredClone(gather());for(const key of ['lo','hi','whole_region','max_changed_blocks'])delete settings[key]
 const active=Number(document.querySelector('#tool-tabs button[aria-pressed=true]')?.dataset.toolIndex??0),panel={1:'pattern',2:'weathering',3:'floor',5:'replace',7:'structure'}[active];if(panel)settings[panel].enabled=true
 if(active===10){const s=gather();settings.operations=[{kind:'auto_road',label:'自动道路',classification:'body',lo:s.whole_region?[0,0,0]:s.lo,hi:s.whole_region?(state.info?.size??[48,16,48]).map(n=>n-1):s.hi,start:['x','y','z'].map(a=>Number($('road-start-'+a).value)),end:['x','y','z'].map(a=>Number($('road-end-'+a).value)),width:Number($('road-width').value),depth:Number($('road-depth').value),route:$('road-route').value,state:$('road-state').value.trim()}]}
 settings.operations=settings.operations.map(op=>Object.fromEntries(Object.entries(op).filter(([key])=>!['write_group','write_bounds','max_writes','overwrite','skip_protected'].includes(key))))
 return {name:toolLabels[active]??'我的工具效果',settings,tags:[]}
}
const toolEffects=initToolEffects({api,capture:captureToolEffect,context:reusableContext,apply:(patch,expected)=>withPreviewCommit(async()=>{if(expected!==JSON.stringify(gather()))throw Error('模型参数已变化');const next=structuredClone(gather()),settings=structuredClone(patch.settings),operations=settings.operations??[];delete settings.operations;for(const [key,value]of Object.entries(settings))next[key]=value&&typeof value==='object'&&!Array.isArray(value)?{...next[key],...value}:value;next.operations.push(...operations);window.creatorWorkspace.select('model');await commitPreviewSettings(next,'载入工具效果：'+patch.name)})})
const reusableLibrary=initReusableLibrary({api,context:reusableContext,apply:applyReusable})
initAssetWorkspace({
 api,context:reusableContext,decorateTree:reusableLibrary.decorateTree,
 pickPosition:async callback=>{if(!state.info||state.busy||state.previewBusy)throw Error('请先打开建筑并等待任务完成');window.creatorWorkspace.select('model');if(state.mode!=='3d')await runJob('snapshot');state.aiPlacing=null;state.picking=false;state.coordinatePicking=false;state.assetPicking=callback;syncPicking();$('view-hint').textContent='点击建筑表面设置构件锚点并生成预览；左键拖动仍可转向'},
 interactive:(component,options)=>options.selection?componentEditor.startSelection(options.move):componentEditor.startAsset(component,options),
 apply:applyReusable
})
toolEffects.attach()
previewToolbar=initPreviewToolbar()
protectionView=initProtectionView({api,context:()=>state.info?{source:state.info.source,source_sha256:state.info.source_sha256,context:$('context').value.trim()}:null,viewer:()=>$('viewer').contentWindow?.nbtModeler,ensure3D:async()=>{if(state.mode!=='3d')await runJob('snapshot')},viewChanged:()=>{const v=$('viewer').contentWindow?.nbtModeler;if(v?.status==='ready')syncComparisonViewControls(v.snapshot,v.metadata())}})
initCommentTasks({api,context:()=>state.info&&!state.busy&&!state.previewBusy?{source:state.info.source,source_sha256:state.info.source_sha256}:null})
initRoomScore({api,context:()=>state.info&&!state.versionComparing?{source:state.info.source,source_sha256:state.info.source_sha256,context:$('context').value.trim(),snapshot_key:state.viewerModelKey,busy:state.busy||state.previewBusy||state.transforming}:null,viewer:()=>$('viewer').contentWindow?.nbtModeler,ensure3D:async()=>{if(state.mode!=='3d')await runJob('snapshot')},busy})
walkView=initWalkView({api,context:()=>state.info&&!state.versionComparing?{source:state.info.source,source_sha256:state.info.source_sha256,context:$('context').value.trim(),snapshot_key:state.viewerModelKey,busy:state.busy||state.previewBusy||state.transforming}:null,viewer:()=>$('viewer').contentWindow?.nbtModeler,ensure3D:async()=>{if(state.versionComparing)throw Error('请先结束版本对比，再检查当前建筑');if(state.mode!=='3d')await runJob('snapshot')},busy,picking:value=>{state.walkPicking=value;if(value){state.aiPlacing=null;state.assetPicking=null;state.picking=false;state.coordinatePicking=false}syncPicking()},viewChanged:()=>{const v=$('viewer').contentWindow?.nbtModeler;syncComparisonViewControls(v.snapshot,v.metadata())}})
function syncComparisonViewControls(snapshot,view){
 const maximum=snapshot.size[1]-1,cut=view.cuts.find(c=>c.axis==='y'&&c.removed_side==='above')
 $('view-cut').max=maximum;$('view-cut').value=cut?Math.max(0,Math.min(maximum,cut.position-1)):maximum;$('view-layer').value=view.layer;$('cut-value').textContent=cut?$('view-cut').value:'完整'
}
versionComparison=initVersionCompare({
 context:()=>({info:state.info,models:state.models,preview:state.preview,busy:state.busy||state.previewBusy||state.sessionRestoring||state.transforming||state.commitBusy}),api,busy,message:status,
 prepare:()=>editSession?.flush(),viewer:()=>$('viewer').contentWindow?.nbtModeler,
 enter:async()=>{
  stashDraft();const viewer=$('viewer').contentWindow?.nbtModeler
  const previous={mode:state.mode,snapshot:viewer?.status==='ready'?viewer.snapshot:null,view:viewer?.status==='ready'?viewer.metadata():null,viewerSource:state.viewerSource,feedbackId:state.viewerFeedbackId,comparisonSide:state.comparisonSide,currentViews:state.currentViews,picking:state.picking,coordinatePicking:state.coordinatePicking,hashLabel:$('model-hash').textContent}
  state.versionComparing=true;state.picking=false;state.coordinatePicking=false;clearTimeout(previewTimer);await activateFeedback(null);syncVersionReadonly();return previous
 },
 show:async(result,side,snapshot)=>{
  const viewer=$('viewer').contentWindow?.nbtModeler
  if(state.mode==='3d'&&viewer?.status==='ready')await viewer.replaceSnapshot(snapshot)
  else await loadViewer({...result,source:side==='before'?(result.reference_source??result.source):result.source,model_key:side==='before'?result.baseline_key:result.model_key,feedback_id:side==='before'?result.baseline_feedback_id:result.feedback_id},false)
  state.viewerSource=snapshot.source;state.viewerFeedbackId=side==='before'?result.baseline_feedback_id:result.feedback_id;state.comparisonSide=null
  await activateFeedback(null);const active=$('viewer').contentWindow.nbtModeler
  syncComparisonViewControls(snapshot,active.metadata())
  $('model-hash').textContent=(side==='before'?'对比基准 · ':'对比当前 · ')+snapshot.geometry_sha256.slice(0,16)
  $('view-hint').textContent='只读版本对比 · 左键转向、中键平移、滚轮前后移动；结束对比后继续编辑'
  previewToolbar?.sync(state.mode,state.busy,!!state.info);syncVersionReadonly()
 },
 leave:async previous=>{
  if(previous.mode==='3d'&&previous.snapshot){const viewer=$('viewer').contentWindow.nbtModeler;await viewer.replaceSnapshot(previous.snapshot);await viewer.renderView({...previous.view.camera,cuts:previous.view.cuts,layer:previous.view.layer,lighting:previous.view.lighting});state.viewerSource=previous.viewerSource;state.viewerFeedbackId=previous.feedbackId;state.comparisonSide=previous.comparisonSide;state.currentViews=previous.currentViews;state.picking=previous.picking;state.coordinatePicking=previous.coordinatePicking;syncComparisonViewControls(previous.snapshot,previous.view);state.versionComparing=false;await activateViewerFeedback(previous.feedbackId);syncPicking()}
  else{state.versionComparing=false;imageMode()}
  $('model-hash').textContent=previous.hashLabel;busy(false);document.querySelector('.action-bar').inert=window.creatorWorkspace?.current()!=='model';$('three-quality').disabled=false;$('auto-preview').disabled=false;$('view-select').disabled=false;$('view-hint').textContent=state.mode==='3d'?'材质 3D · 左键原地转向，中键平移，滚轮前进／后退':$('view-hint').textContent
 },viewChanged:()=>syncComparisonViewControls($('viewer').contentWindow.nbtModeler.snapshot,$('viewer').contentWindow.nbtModeler.metadata())
})
initAgentTaskReturns({api,context:()=>({info:state.info,busy:state.busy||state.previewBusy||state.commitBusy||state.versionComparing,camera:$('viewer').contentWindow?.nbtModeler?.metadata?.().camera}),compare:(pair,camera)=>versionComparison.compare(pair,camera),message:text=>status(text)})
componentEditor=initComponentEditor({
 api,message:status,viewer:()=>$('viewer').contentWindow?.nbtModeler,
 context:()=>{if(!state.info)return{};const settings=gather();return {source:state.info.source,source_sha256:state.info.source_sha256,size:state.info.size,whole:settings.whole_region,lo:settings.whole_region?[0,0,0]:settings.lo,hi:settings.whole_region?state.info.size.map(n=>n-1):settings.hi,settings:JSON.stringify(settings),target_id:state.viewerFeedbackId}},
 prepare:async()=>{
  if(!state.info||state.busy||state.previewBusy||state.commitBusy||state.sessionRestoring)throw Error('请先打开建筑并等待当前任务完成')
  await versionComparison.close();window.creatorWorkspace.select('model');clearTimeout(previewTimer)
  const settings=gather(),hasTools=settings.operations.some(op=>op.enabled!==false)||['structure','replace','pattern','weathering','floor'].some(key=>settings[key]?.enabled)
  if(hasTools){if(state.preview&&state.previewSettings===JSON.stringify(settings))await showComparison('after');else await updatePreview(true)}
  else if(state.mode!=='3d'||$('viewer').contentWindow?.nbtModeler?.metadata().geometry_sha256!==state.info.geometry_sha256)await runJob('snapshot')
  await editSession.flush();const s=gather();return {source:state.info.source,source_sha256:state.info.source_sha256,size:state.info.size,whole:s.whole_region,lo:s.whole_region?[0,0,0]:s.lo,hi:s.whole_region?state.info.size.map(n=>n-1):s.hi,settings:JSON.stringify(s),target_id:state.viewerFeedbackId}
 },
 lock:value=>{state.transforming=value;clearTimeout(previewTimer);state.picking=false;state.coordinatePicking=false;state.assetPicking=null;state.aiPlacing=null;syncPicking();busy(false);for(const id of ['three-quality','view-select','auto-preview','show-selection'])$(id).disabled=value;if(!value){document.querySelector('.action-bar').inert=window.creatorWorkspace?.current()!=='model';$('feedback-card').hidden=!state.feedbackTarget;syncMessageContext();editSession.schedule()}syncSelectionRange();$('view-hint').textContent=value?'临时构件：拖动箭头移动、绿色圆环旋转；应用后生成真实候选。':'左键转向，中键平移，滚轮前进／后退'},
 apply:applyComponentPatch,
 committed:async()=>{state.transformCommittedSafe=true;try{await editSession.flush()}finally{state.transformCommittedSafe=false}}
})
initWorkspaceShell()
initTaskRecords()
const settingsReady=initAppSettings()
initHelpDialogs()
const commentComposer=document.createElement('div');commentComposer.className='comment-composer'
for(const element of [$('feedback-text'),document.querySelector('.comment-compose-meta'),$('draft-markers'),$('reference-chips'),document.querySelector('#feedback-card>.note-actions')])commentComposer.append(element)
const commentThread=document.createElement('div');commentThread.className='comment-thread';commentThread.append(document.querySelector('.comment-tools'),$('feedback-notes'))
$('feedback-card').insertBefore(commentComposer,$('feedback-links'));$('feedback-card').insertBefore(commentThread,$('feedback-links'))
const commentHeading=document.createElement('div');commentHeading.className='comment-heading';commentHeading.append(document.querySelector('#feedback-card>.section-title'),document.querySelector('#feedback-card>.feedback-meta'));$('feedback-card').prepend(commentHeading)
const commentThreadMeta=document.createElement('div');commentThreadMeta.className='comment-thread-meta';commentThreadMeta.append($('comment-compose-hint'),$('draft-markers'));commentThread.prepend(commentThreadMeta)
$('review-help-open').onclick=()=>$('review-help-dialog').showModal();$('review-help-close').onclick=()=>$('review-help-dialog').close()
for(const id of ['comment-search','comment-filter'])$(id).addEventListener(id==='comment-search'?'input':'change',()=>{if(state.noteRecord)renderNotes(state.noteRecord)})
$('feedback-text').addEventListener('input',()=>$('comment-length').textContent=$('feedback-text').value.length+' / 4000')
$('feedback-text').addEventListener('keydown',event=>{if(!event.isComposing&&(event.ctrlKey||event.metaKey)&&event.key==='Enter'){event.preventDefault();$('save-feedback').click()}})
window.addEventListener('creator-workspace-change',event=>{if(event.detail!=='model')clearTimeout(previewTimer);if(event.detail==='model'&&state.catalogReady&&!state.info&&!state.busy&&!state.openingProjectModel&&$('source').value)loadModel().catch(error=>status(error.message,'error'))})
const resumeEdit=document.createElement('button');resumeEdit.id='resume-edit';resumeEdit.type='button';resumeEdit.textContent='继续上次编辑';resumeEdit.hidden=true;document.getElementById('project-native-actions').append(resumeEdit)
function setResumeSource(source){resumeEdit.hidden=false;resumeEdit.title=source;resumeEdit.onclick=()=>openProjectModel({source}).catch(error=>status(error.message,'error'))}
const sessionStatus=document.createElement('p');sessionStatus.id='session-status';sessionStatus.setAttribute('role','status');sessionStatus.textContent='编辑草稿将自动保存到当前工作区';$('history-current').after(sessionStatus)
const sessionActions=document.createElement('details');sessionActions.id='session-actions';sessionActions.innerHTML='<summary>编辑草稿</summary><p class="muted">自动保存参数、视口与未保存评论；刷新或重启后按源文件哈希恢复。草稿不进入正式评论索引，不构成批准。关闭自动保存可在设置 → 常规中调整。</p><button id="session-save-now" type="button">立即保存草稿</button><button id="session-reload" type="button">重新读取草稿</button><button id="session-valid-inputs" type="button">放弃未完成的参数输入</button>';$('save-preset').closest('.preset-card').append(sessionActions)
const preset=$('save-preset').closest('.preset-card'),presetToolbar=document.createElement('div'),presetSecondary=document.createElement('div');presetToolbar.className='preset-toolbar';presetSecondary.className='preset-secondary'
const oldPresetRow=$('save-preset').parentElement;presetToolbar.append(preset.querySelector('.history-actions'),$('open-settings-history'),$('save-preset'),$('load-preset'));oldPresetRow.remove();preset.prepend(presetToolbar);presetSecondary.append(sessionStatus,preset.querySelector('.review-advanced-shell'),sessionActions);preset.append(presetSecondary)
for(const [id,label]of [['undo-settings','撤销'],['redo-settings','重做'],['open-settings-history','历史'],['save-preset','保存配置'],['load-preset','读取配置']]){const b=$(id);b.setAttribute('aria-label',b.textContent);b.title=b.title||b.textContent;b.textContent=label}
for(const [id,label]of [['advanced-review','Agent 精修'],['session-actions','草稿']]){const details=$(id),summary=details.querySelector(':scope>summary'),panel=document.createElement('div');panel.className='preset-flyout';summary.title=summary.textContent;summary.textContent=label;for(const child of [...details.childNodes])if(child!==summary)panel.append(child);details.append(panel);floatingDetails(details,panel,{minimum:360})}
const reviewShell=presetSecondary.querySelector('.review-advanced-shell'),reviewPanel=$('advanced-review').querySelector('.preset-flyout'),reviewHelp=$('review-help-open'),reviewHeading=document.createElement('div');reviewHeading.className='preset-review-heading';const reviewCaption=document.createElement('strong');reviewCaption.textContent='Agent 精修审阅与执行';reviewHeading.append(reviewCaption,reviewHelp);reviewPanel.prepend(reviewHeading);reviewShell.append($('advanced-review'));for(const details of [$('advanced-review'),sessionActions]){const summary=details.querySelector(':scope>summary');summary.insertAdjacentHTML('beforeend',chevron);summary.classList.add('preset-menu-trigger')}
initDisclosureIcons()
function captureEditSession(){
 if(state.transforming&&!state.transformCommittedSafe)return null
 if(state.versionComparing)return null
 if(!state.info||state.busy||state.savingNote)return null
 try{lastValidSessionSettings=gather()}catch{}
 if(!lastValidSessionSettings)return null
 stashDraft()
 const viewer=$('viewer').contentWindow?.nbtModeler,meta=state.mode==='3d'&&viewer?.status==='ready'?viewer.metadata():null
 const controls=Object.fromEntries([...$('settings').querySelectorAll('input[id],select[id],textarea[id]')].filter(e=>!e.readOnly&&!e.closest('#operation-list')&&!e.id.endsWith('-range')&&e.id!=='operation-sequence'&&e.id!=='materials-search'&&e.id!=='operation-kind').map(e=>[e.id,e.type==='checkbox'?e.checked:e.value]))
 const drafts=[...state.noteDrafts].filter(([key,draft])=>key.startsWith(state.info.source_sha256+':')&&(draft.text?.trim()||draft.points?.length)).slice(-50).map(([key,d])=>[key,{text:d.text,points:d.points}])
 const comparison=state.mode==='3d'?(state.comparisonSide==='after'&&meta?.geometry_sha256===state.preview?.geometry_sha256?'after':'before'):null
 const preview=comparison==='after'&&state.previewSettings&&state.previewSettings!==JSON.stringify(lastValidSessionSettings)?JSON.parse(state.previewSettings):undefined
 let raw=$('operation-sequence').value;try{if(JSON.stringify(JSON.parse(raw))===JSON.stringify(lastValidSessionSettings.operations))raw=null}catch{}
 const group=currentAIGroup(),ai_component=group?Object.fromEntries(['start','base','applied','offset','overwrite','quarter_turns','structure_name','camera'].filter(key=>group[key]!==undefined).map(key=>[key,structuredClone(group[key])])):null
 return {source:state.info.source,source_sha256:state.info.source_sha256,state:{settings:lastValidSessionSettings,operations_text:raw,controls,view:{mode:state.mode,quality:$('three-quality').value,camera:meta?.camera,cuts:meta?.cuts??[],layer:meta?.layer??$('view-layer').value,cut:Number($('view-cut').value),show_selection:$('show-selection').checked,image_hash:state.selectedImage?.image_sha256??null,image_name:state.selectedImage?.name??null,comparison,preview_settings:preview},drafts,ai_component,ai_candidate:apiAssistant?.capture()??null}}
}
async function restoreEditSession(saved,recovered={}){
 lockEditorRecovery();sessionStatus.textContent='正在恢复编辑草稿与上次画面…'
 try{return await restoreEditSessionCore(saved,recovered)}finally{unlockEditorRecovery()}
}
function lockEditorRecovery(){state.recoveryLocks=(state.recoveryLocks??0)+1;state.sessionRestoring=true;document.querySelector('.workspace').inert=true;document.querySelector('.action-bar').inert=true}
function unlockEditorRecovery(){state.recoveryLocks=Math.max(0,(state.recoveryLocks??0)-1);if(state.recoveryLocks)return;state.sessionRestoring=false;const workspace=window.creatorWorkspace?.current();document.querySelector('.workspace').inert=workspace!=='model';document.querySelector('.action-bar').inert=state.versionComparing||['project','assets','prompt','ai'].includes(workspace);versionComparison?.sync();window.dispatchEvent(new Event('creator-editor-state'))}
async function restoreEditSessionCore(saved,recovered){
 const source=state.info?.source_sha256,pending=saved.settings
 restore(pending);lastValidSessionSettings=structuredClone(pending);resetSettingsHistory();settingsHistory.rename(0,'恢复的编辑草稿');historyButtons()
 state.lastAIGroup=saved.ai_component?{...structuredClone(saved.ai_component),source:state.info.source,source_sha256:state.info.source_sha256}:null
 for(const [key,draft]of saved.drafts)state.noteDrafts.set(key,structuredClone(draft))
 const view=saved.view
 try{
 if(view.mode==='3d'){
  $('three-quality').value=view.quality
  if(view.comparison==='after'){const candidate=view.preview_settings??pending;restore(candidate);state.previewRevision++;await updatePreview();if(state.previewSettings!==JSON.stringify(candidate))throw Error('候选效果未能重新计算；已保留参数草稿')}
  else if(state.mode!=='3d')await runJob('snapshot')
  if(source!==state.info?.source_sha256)throw Error('恢复期间建筑已切换')
  const viewer=$('viewer').contentWindow?.nbtModeler
  if(viewer?.status==='ready'&&view.camera)await viewer.renderView({...view.camera,layer:view.layer,cuts:view.cuts,lighting:viewer.metadata().lighting})
  $('view-layer').value=view.layer;$('view-cut').value=view.cut;$('cut-value').textContent=view.cut===Number($('view-cut').max)?'完整':view.cut
  if(state.viewerFeedbackId)await activateViewerFeedback(state.viewerFeedbackId)
 }else{imageMode();let index=state.images.findIndex(image=>image.image_sha256===view.image_hash&&(!view.image_name||image.name===view.image_name));if(index<0&&recovered.image){gallery([...state.images,recovered.image]);index=state.images.length-1}if(index>=0)await selectImage(index)}
 }finally{
 restore(pending)
 for(const [id,value]of Object.entries(saved.controls)){const element=$(id);if(!element?.closest('#settings')||element.closest('#operation-list')||!['INPUT','SELECT','TEXTAREA'].includes(element.tagName)||element.readOnly)continue;if(element.type==='checkbox')element.checked=value===true;else element.value=String(value)}
 $('operation-sequence').value=saved.operations_text??JSON.stringify(pending.operations,null,2);operationEditor.sync();$('show-selection').checked=view.show_selection;state.configChanged=true;state.bundle='';syncSelectionRange();updateCount()
 if(state.previewSettings&&state.previewSettings!==JSON.stringify(pending))$('preview-state').textContent='已恢复上次画面；参数还有未预览的修改，请更新效果'
 apiAssistant?.restore(saved.ai_candidate,saved.controls?.['ai-result']??'');syncMessageContext();syncMarkers()
 }
}
editSession=createEditSessionController({api,capture:captureEditSession,restore:restoreEditSession,enabled:()=>state.restoreSession!==false,message:(text,error=false)=>{sessionStatus.textContent=text;sessionStatus.title=text;sessionStatus.classList.toggle('session-error',error)}})
window.addEventListener('creator-ai-candidate-change',()=>editSession?.schedule())
window.nbtEditSession=Object.freeze({flush:()=>Promise.all([editSession.flush(),$('prompt-frame').contentWindow?.NbtPromptUI?.flushExport?.()]),get ready(){return !state.sessionRestoring&&!editSession.loading&&editSession.source===state.info?.source},get loading(){return editSession.loading||state.sessionRestoring}})
$('session-save-now').onclick=handle(async()=>{editSession.checkpoint(true);await editSession.flush()})
$('session-reload').onclick=handle(async()=>{if(!state.info)return;lockEditorRecovery();try{await editSession.beforeOpen();await editSession.opened(state.info,true)}finally{unlockEditorRecovery()}})
$('session-valid-inputs').onclick=()=>{if(lastValidSessionSettings){restore(lastValidSessionSettings);recordSettings('放弃未完成输入');schedulePreview();editSession.schedule()}}
document.addEventListener('input',event=>{if(event.target.closest('#settings,#feedback-text'))editSession.schedule()})
document.addEventListener('change',event=>{if(event.target.closest('#settings,.review-toolbar'))editSession.schedule()})
window.addEventListener('creator-session-preference',event=>{for(const id of ['session-save-now','session-reload','session-valid-inputs'])$(id).disabled=state.busy||!event.detail;if(!event.detail){sessionStatus.textContent='编辑草稿自动保存与恢复已关闭';sessionStatus.classList.remove('session-error')}else editSession.schedule()})
initCommandCenter({api,state:()=>state,selectTool,message:status})
initialize().then(()=>{
  const source=new URLSearchParams(location.search).get('source')
  if(source){const index=state.models.findIndex(model=>model.source===source);if(index<0)throw new Error('所选结构不在当前建筑目录中，请刷新现有结构选择器。');selectModel(index);renderModels()}
  if($('source').value&&!state.info&&!state.busy&&window.creatorWorkspace.current()==='model')return loadModel()
}).catch(error=>status(error.message,'error'))

$('review-image').addEventListener('click',event=>{
  const box=imageBox();if(!box)return
  const x=(event.clientX-box.rect.left-box.left)/box.width,y=(event.clientY-box.rect.top-box.top)/box.height
  if(x<0||x>1||y<0||y>1)return
  addDraftMarker({kind:'image',x,y})
})
$('feedback-text').addEventListener('input',()=>{stashDraft();syncReferences()})
$('whole-image-note').addEventListener('click',()=>{for(const point of [...(state.draftPoints ?? [])])removeDraftMarker(point.number)})
$('save-feedback').addEventListener('click',handle(async()=>{
  if(state.savingNote||state.feedbackLoading||!state.feedbackTarget)return
  const missing=[...$('feedback-text').value.matchAll(/@\[([^\]]+)\]/g)].map(match=>match[1]).filter(name=>!state.effectFiles.some(file=>file.name===name))
  if(missing.length)throw new Error('这些引用文件不在当前保存文件夹中，请刷新文件列表或重新选择：'+missing.join('、'))
  const target=state.feedbackTarget,key=state.noteKey
  state.savingNote=true;$('save-feedback').disabled=true
  try{
    const record=await api('feedback/add',{target_id:target.id,text:$('feedback-text').value,anchors:state.draftPoints ?? [],references:referencedFiles().map(file=>file.id)})
    state.noteDrafts.delete(key)
    if(state.feedbackTarget?.id===target.id){$('feedback-text').value='';state.draftPoint=null;state.draftPoints=[];syncMessageContext();renderNotes(record)}
    status((target.kind==='3d'?'3D坐标':'图片位置')+'与评论已一起保存到本地，编号与当前版本绑定。')
  }finally{state.savingNote=false;$('save-feedback').disabled=state.busy||state.feedbackLoading||!state.feedbackTarget}
}))
$('export-feedback').addEventListener('click',handle(async()=>{
  if(!state.feedbackTarget)return
  const result=await api('feedback/export',{target_id:state.feedbackTarget.id});$('feedback-links').replaceChildren()
  for(const [key,label,filename] of [['json','下载意见 JSON','feedback.json'],['markdown','下载意见 Markdown','feedback.md']]){
    const a=document.createElement('a');a.href=result[key];a.download=filename;a.textContent=label;$('feedback-links').append(a)
  }
  $('feedback-file').textContent='意见文件：'+result.file
}))

initRoadPanel({context:()=>{if(!state.info)return null;const s=gather();return {lo:s.whole_region?[0,0,0]:s.lo,hi:s.whole_region?state.info.size.map(n=>n-1):s.hi,budget:s.max_changed_blocks,settings:JSON.stringify(s)}},apply:async(op,expected)=>withPreviewCommit(async()=>{const next=gather();if(JSON.stringify(next)!==expected)throw Error("建筑参数已变化，请重新铺设");next.operations.push(op);await commitPreviewSettings(next,"自动道路铺设")}),report:text=>status(text,"error")})
