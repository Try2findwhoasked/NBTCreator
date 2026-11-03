import {initAppSettings} from './app-settings.js'
import {translateComponent} from './component-move.js'
import {requestAI,cancelAI} from './ai-request.js'
import '../../../prompt-console/catalog.js'
import './control.css'
import './prompt-panel.css'
import {initDesktop} from './desktop-adapter.js'
import {initApiAssistant} from './api-assistant.js'
import {initWorkspaceShell} from './workspace-shell.js'
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
  input.placeholder='输入中文或 ID，也可点击 ▾ 选择'
  input.value=input.value.split(';').map(value=>{
    const text=value.trim(),split=text.indexOf('['),base=(split<0?text:text.slice(0,split)).replace(/^minecraft:/,'')
    return (blockNames[base] ?? (split<0?text:text.slice(0,split)))+(split<0?'':text.slice(split))
  }).join('; ')
  if(input.dataset.blockPicker)return
  input.dataset.blockPicker='1';input.removeAttribute('list')
  const wrapper=document.createElement('span');wrapper.className='block-select'
  input.replaceWith(wrapper);wrapper.append(input)
  const button=document.createElement('button');button.type='button';button.className='block-select-toggle';button.textContent='▾'
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
  $('status-badge').textContent = kind === 'error' ? '需处理' : kind === 'warn' ? '待复核' : state.busy ? '进行中' : '就绪'
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

// Show one parameter group at a time; values remain mounted when switching.
const toolPanels=[...document.querySelectorAll('#settings > .card')]
const toolLabels=['整体效果','方块混搭','长苔与裂纹','自动地面','修改范围','精确换块','建筑取材','结构编辑','建模工具','AI建模']
function selectTool(index){
  toolPanels.forEach((panel,i)=>{panel.hidden=i!==index;if(i===index&&panel.tagName==='DETAILS')panel.open=true})
  ;[...$('tool-tabs').children].forEach((button,i)=>button.setAttribute('aria-pressed',String(i===index)))
}
toolLabels.forEach((label,index)=>{
  const button=document.createElement('button');button.type='button';button.textContent=label
  button.addEventListener('click',()=>selectTool(index));$('tool-tabs').append(button)
})
selectTool(0)
for(const [kind,[label]]of Object.entries(globalThis.NbtToolCatalog.tools)){const option=document.createElement('option');option.value=kind;option.textContent=label;$('operation-kind').append(option)}
$('operation-add').onclick=()=>{try{const kind=$('operation-kind').value,[label,defaults]=globalThis.NbtToolCatalog.tools[kind];const op={kind,...structuredClone(globalThis.NbtToolCatalog.common),...structuredClone(defaults),label};if(kind==='auto_floor'){delete op.lo;delete op.hi;op.include_boxes=[]}const list=JSON.parse($('operation-sequence').value);if(!Array.isArray(list))throw Error('序列须为数组');list.push(op);$('operation-sequence').value=JSON.stringify(list,null,2);$('operation-sequence').dispatchEvent(new Event('input',{bubbles:true}))}catch(e){status(e.message,'error')}}
$('operation-clear').onclick=()=>{$('operation-sequence').value='[]';$('operation-sequence').dispatchEvent(new Event('input',{bubbles:true}))}

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
async function captureViewport(){
 if(state.busy||state.previewBusy)throw Error('请等当前模型任务完成后再截图')
 const viewer=$('viewer').contentWindow?.nbtModeler
 if(state.mode==='3d'&&viewer?.status==='ready')return viewer.captureCurrent()
 const img=$('review-image')
 if(state.info&&img.complete&&img.naturalWidth){const canvas=document.createElement('canvas'),ratio=Math.min(1,1280/Math.max(img.naturalWidth,img.naturalHeight));canvas.width=Math.max(1,Math.round(img.naturalWidth*ratio));canvas.height=Math.max(1,Math.round(img.naturalHeight*ratio));canvas.getContext('2d').drawImage(img,0,0,canvas.width,canvas.height);return {dataUrl:canvas.toDataURL('image/jpeg',.82),width:canvas.width,height:canvas.height}}
 throw Error('没有可用的建模视口，请先打开3D或建筑图片，或关闭该工作流的截图开关')
}
let promptLoaded=false
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
  let extra=0;try{const operations=JSON.parse($('operation-sequence').value);if(Array.isArray(operations))extra=operations.length}catch{}
  const count = ['structure-enabled','replace-enabled','pattern-enabled','weather-enabled','floor-enabled'].filter(id => $(id).checked).length+extra
  $('operation-count').textContent = count ? `${count} 项工具已启用 · 总体强度 ${$('strength').value}%` : '所有工具当前关闭'
  syncWorkspace();syncSelectionRange()
  $('copy-agent-plan').disabled = state.busy || !state.bundle || !state.agentText
  $('apply').disabled = state.busy || !state.bundle || !$('review').value.trim()
}
function busy(value) {
  state.busy = value
  for (const button of document.querySelectorAll('button')) if (button.id !== 'cancel') button.disabled = value
  for (const input of document.querySelectorAll('.sidebar input, .sidebar select, .sidebar textarea')) input.disabled = value
  $('compare-before').disabled=value||!state.preview;$('compare-after').disabled=value||!state.preview
  $('pick-material').disabled=value||state.mode!=='3d';$('pick-coordinate').disabled=value||state.mode!=='3d';
  $('export-revision').disabled=value||!state.info;
  $('cancel').disabled = !value; $('pause-3d').disabled=state.mode!=='3d'; $('enable-3d').disabled=value||!state.info; $('save-feedback').disabled=value||!state.feedbackTarget||state.feedbackLoading||state.savingNote; updateCount()
  historyButtons()
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
  state.mode='images';state.viewerGeneration++;$('pick-material').disabled=true
  $('pick-coordinate').disabled=true
  $('viewer').src='about:blank';$('viewer').hidden=true;$('three-toolbar').hidden=true
  $('image-toolbar').hidden=false;$('review-canvas').hidden=!state.selectedImage;$('empty-view').hidden=Boolean(state.selectedImage)
  $('pause-3d').disabled=true;$('view-hint').textContent='点击图片定位修改位置；需要旋转查看时可打开 3D。'
  activateImageFeedback().catch(error=>status(error.message,'error'))
  syncWorkspace()
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
    const option=document.createElement('option');option.value=index;option.textContent=image.name;$('image-select').append(option)
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
  const payload = { kind, request: request(), bundle: state.bundle, review: $('review').value.trim() }
  Object.assign(payload.request, overrides)
  busy(true); status('正在执行：'+({plan:'生成计划',snapshot:'载入三维模型',prepare:'准备建筑审阅图',render:'批量保存源视图',apply:'应用已批准计划',revision:'导出建筑下一版'}[kind] ?? kind))
  try {
    while(state.previewBusy)await new Promise(resolve=>setTimeout(resolve,100))
    const submitted = await api('jobs', payload)
    let job
    do { await new Promise(resolve => setTimeout(resolve, 350)); job = await api('jobs/'+submitted.id) } while(job.status === 'running')
    $('jobs').textContent = `${job.kind} · ${job.status} · ${job.directory}`
    if (job.status !== 'complete') throw new Error(job.error ?? '任务失败')
    const result = job.result
    if(kind==='plan')state.configChanged=false
    await refreshEffects()
    $('result-log').textContent = kind === 'snapshot'
      ? `已载入 ${result.size.join(' × ')} 建筑，共 ${result.cameras.length} 个观察角度。\n`+(result.read_only_view?'当前仅作几何查看，尚无任务坐标/保护配置；没有执行通路或导出验收。':'当前显示为所选模型；调整左侧设置不会直接改动建筑。')
      : kind === 'plan' ? `${result.operations} 项操作已编译。\n`+(result.estimates ?? []).map(e=>`${e.kind}：${e.writes} 个候选写入`).join('\n')+(result.warning?'\n估算未完成，完整原因见高级记录。':'\n这些是候选统计，不是已执行结果。')
      : result.changed_blocks !== undefined ? `新版本修改了 ${result.changed_blocks} 个方块，原建筑保留。` : '结果已保存至本次独立任务目录。'
    $('advanced-log').textContent=JSON.stringify(result,null,2)
    $('result-links').replaceChildren()
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
    status(result.warning ? '方案已保存，建筑检查未通过：'+result.warning : ({plan:`Agent 交接方案已生成：${result.operations} 项操作。点击“复制给 Agent”继续，原建筑未改变。`,prepare:'建筑审阅图已保存到本建筑的 Agent交接 文件夹，目录已自动关联。请看图后，在 Agent 对话中明确是否同意继续精修。',render:'原建筑的多角度预览图已保存。',apply:'新建筑已另存，原建筑保留。',revision:'下一版建筑已保存到原工作文件夹；包含主模型、NBT切片和分层交付。',snapshot:state.mode==='3d'?'三维已按需载入；可关闭 3D 返回看图模式。':'已返回看图模式。'}[kind] ?? '完成'), result.warning ? 'warn' : '')
    return result
  } catch(error) { if(['prepare','apply'].includes(kind))$('advanced-review').open=true;throw error } finally { busy(false) }
}
async function loadViewer(result, isNewVersion = false) {
  result={...result,cameras:(result.cameras??[]).map(camera=>({...camera,cuts:(camera.cuts??[]).map(c=>Array.isArray(c)?{axis:c[0],position:c[1],removed_side:c[2]}:c)}))}
  stashDraft()
  state.comparisonSide=result.preview_only?(result.model_key===result.baseline_key?'before':'after'):null
  const generation=++state.viewerGeneration
  state.mode='3d';state.viewerSource=result.source ?? state.info?.source;syncWorkspace();$('image-toolbar').hidden=false;$('three-toolbar').hidden=false;$('review-canvas').hidden=true;$('feedback-card').hidden=!state.selectedImage;$('pause-3d').disabled=false
  $('view-hint').textContent=$('three-quality').value==='fast'?'颜色用于区分朝向；看实际方块请切换材质 3D 或看图片':'材质 3D（看方块） · 左键旋转，中键平移，滚轮缩放'
  state.currentViews = result.cameras
  $('view-select').replaceChildren()
  result.cameras.forEach((view, i) => { const option=document.createElement('option');option.value=i;option.textContent=view.role ?? view.id;$('view-select').append(option) })
  $('view-select').disabled=false
  $('view-cut').max=result.size[1]-1;$('view-cut').value=result.size[1]-1;$('cut-value').textContent='完整'
  const frame=$('viewer');frame.hidden=false;$('empty-view').hidden=true
  await new Promise((resolve,reject) => {
    let timer=setTimeout(()=>reject(new Error('三维预览初始化超时')),60000)
    frame.onload=async()=>{try{if(generation!==state.viewerGeneration){clearTimeout(timer);resolve();return};await frame.contentWindow.nbtModeler.ready;if(generation!==state.viewerGeneration){clearTimeout(timer);resolve();return};if(result.cameras.length)await frame.contentWindow.nbtModeler.renderView(result.cameras[0]);clearTimeout(timer);resolve()}catch(error){clearTimeout(timer);reject(error)}}
    frame.src=`/?model_key=${encodeURIComponent(result.model_key)}&embedded=1&quality=${$('three-quality').value}&pixelRatio=0.75&maxFps=24`
  })
  syncSelectionRange();$('pick-material').disabled=false;$('pick-coordinate').disabled=false;syncPicking()
  state.viewerFeedbackId=result.feedback_id;await activateViewerFeedback(result.feedback_id)
  $('model-hash').textContent=(isNewVersion?'新版本预览 ':'原建筑版本 ')+result.geometry_sha256.slice(0,16)
}
async function loadModel(preserve = false) {
  state.aiPlacing=null;state.lastAIGroup=null
  stashDraft();imageMode();busy(true)
  try {
    status('正在打开建筑及门口、通路等保护设置…')
    const previousHash=state.info?.source_sha256
    const info=await api('inspect',{source:$('source').value.trim(),image_limit:state.imageLimit});state.info=info
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
    $('model-summary').textContent=`${info.size.join(' × ')} · ${info.solid_blocks.toLocaleString()} 个实体方块 · ${info.wall_blocks.toLocaleString()} 个单独记录的墙体方块`+(info.unknown_shapes.length?`。${info.unknown_shapes.length} 类方块暂时无法自动检查能否通行。可以先生成方案，生成新建筑前仍需通过检查。`:'')
    renderMaterials();if(!preserve||previousHash!==info.source_sha256)resetSettingsHistory();gallery(info.images);if(!preserve||previousHash!==info.source_sha256)state.bundle=''
  } finally { busy(false) }
  status(state.images.length?'图片已打开。点击上方缩略图切换视角，点击大图标位置、写修改意见。':'这座建筑还没有对应的图片。可点击“为原建筑生成预览图”，或打开 3D 查看。')
  if(!preserve&&!state.images.length)await runJob('snapshot')
}

async function initialize() {
  busy(true)
  try {
    const data=await api('init'); state.models=data.catalog.models;state.workspace=data.workspace;state.output=data.output;$('save-root').value=data.output
    await refreshEffects()
    if(!state.settings){if(data.initial_request){restore(data.initial_request.settings);for(const key of ['source','context','cameras','review'])$(key).value=data.initial_request[key] ?? ''}else restore(data.defaults)}
    $('output-path').textContent=data.output
    const previous=$('source').value
    renderModels(previous)
    if(state.models.length && !previous&&$('models').value!==''){selectModel(Number($('models').value))}
    else if(data.catalog.migration_in_progress)status('建筑库正在按形状迁移和校验，完成后刷新列表即可。','warn')
    else if(!state.models.length)status(`未发现可载入的完整建筑。扫描目录：${data.catalog.scan_root??state.workspace+'/nbt_models'}。已检查 ${data.catalog.scanned} 个文件，${data.catalog.skipped} 个格式不支持或损坏。请确认项目根目录，或直接打开完整 NBT / 主模型。`,'warn')
  } finally { busy(false) }
}
function selectModel(index) {
  const item=state.models[index];if(!item)return
  $('source').value=item.source;$('context').value=item.context;$('cameras').value=item.cameras;state.bundle='';state.info=null;state.pickedMaterial=null;$('picked-material').hidden=true;$('orthographic-dialog').hidden=true
  $('viewer').hidden=true;$('viewer').src='about:blank';$('empty-view').hidden=false;$('view-select').disabled=true
  state.imageLimit=state.defaultImageLimit??8;state.configChanged=false;state.activeNote=null;state.preview=null;state.previewRevision++;clearTimeout(previewTimer);$('compare-before').disabled=true;$('compare-after').disabled=true;$('preview-state').textContent='效果预览不会保存为正式建筑'
  $('model-summary').textContent='正在切换建筑…';$('result-links').replaceChildren();$('result-log').textContent='';$('status').textContent='请选择效果设置，右侧将载入对应图片。'
  imageMode();gallery([]);updateCount()
}
function handle(fn) { return async event => { try { await fn(event) } catch(error) { status(error.message,'error') } } }
$('refresh').addEventListener('click',handle(initialize))
$('models').addEventListener('change',handle(async()=>{selectModel(Number($('models').value));await loadModel()}))
$('load').addEventListener('click',handle(()=>loadModel()))
$('enable-3d').addEventListener('click',handle(()=>runJob('snapshot')))
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
$('cancel').addEventListener('click',handle(()=>api('cancel',{})))
$('add-material').addEventListener('click',()=>{addMaterial();$('settings').dispatchEvent(new Event('input',{bubbles:true}))})
$('settings').addEventListener('input',event=>{if(event.target.id==='materials-search')return;if(/^(lo|hi)-[xyz]$/.test(event.target.id))$('whole-region').checked=false;state.configChanged=true;state.bundle='';updateCount();recordSettings();if(event.target.id!=='style-note')schedulePreview()});$('review').addEventListener('input',updateCount)
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
  const result=await api('effects/save',{request:request(),name:$('effect-name').value})
  await refreshEffects();status('效果设置已保存：'+result.path+'；可在右侧用 @ 引用。')
  const link=document.createElement('a');link.textContent='另下载一份设置';const url=URL.createObjectURL(new Blob([JSON.stringify(request(),null,2)],{type:'application/json'}));link.href=url;link.download='detail_settings.json';$('result-links').replaceChildren(link);setTimeout(()=>URL.revokeObjectURL(url),60000)
}))
$('load-preset').addEventListener('click',()=>$('preset-file').click())
$('preset-file').addEventListener('change',handle(async()=>{
  const file=$('preset-file').files[0];if(!file)return
  const data=await api('resolve-request',{request:JSON.parse(await file.text())});restore(data.settings)
  for(const key of ['source','context','cameras','review'])$(key).value=data[key] ?? ''
  state.bundle='';await loadModel(true)
}))
let previewTimer
function schedulePreview(){
  state.previewRevision++;clearTimeout(previewTimer)
  $('preview-state').textContent='设置已改变，等待更新预览…'
  if($('auto-preview').checked&&state.info)previewTimer=setTimeout(()=>updatePreview().catch(error=>{$('preview-state').textContent='预览失败：'+error.message}),(state.previewDelay??1400))
}
async function updatePreview(){
  if(!state.info)return
  if(state.previewBusy||state.busy){if($('auto-preview').checked)previewTimer=setTimeout(()=>updatePreview().catch(error=>$('preview-state').textContent='预览失败：'+error.message),700);return}
  const revision=state.previewRevision,source=state.info.source,payload=request()
  state.previewBusy=true;$('update-preview').disabled=true;$('preview-state').textContent='正在计算效果，仍可继续调参…'
  try{
    const submitted=await api('jobs',{kind:'preview',request:payload})
    let job;do{await new Promise(resolve=>setTimeout(resolve,300));job=await api('jobs/'+submitted.id)}while(job.status==='running')
    if(job.status!=='complete')throw new Error(job.error ?? '计算失败')
    if(revision!==state.previewRevision||source!==state.info?.source)return
    state.preview=job.result;state.previewSettings=JSON.stringify(payload.settings)
    await showComparison('after')
    $('compare-before').disabled=false;$('compare-after').disabled=false
    $('preview-state').textContent=`调整效果 · ${job.result.changed_blocks} 个方块变化 · 仅预览，未生成正式建筑`
    status('参数效果预览已更新。用“看原建筑 / 看调整效果”在同一视角对比；保存调整设置可留存当前配方。')
  }finally{state.previewBusy=false;$('update-preview').disabled=false}
}
async function showComparison(side){
  const result=state.preview;if(!result)return
  state.comparisonSide=null
  const generation=state.comparisonGeneration=(state.comparisonGeneration ?? 0)+1
  const key=side==='before'?result.baseline_key:result.model_key
  $('compare-before').setAttribute('aria-pressed',String(side==='before'));$('compare-after').setAttribute('aria-pressed',String(side==='after'))
  // Material changes need textures: normal-color geometry mode cannot show mixing.
  if(state.mode!=='3d'||$('viewer').contentWindow?.nbtModeler?.status!=='ready'||$('three-quality').value!=='balanced'){
    $('three-quality').value='balanced';await loadViewer({...result,model_key:key,feedback_id:side==='before'?result.baseline_feedback_id:result.feedback_id},false)
  }else{
    const response=await fetch('/__nbt_modeler__/model.json?model_key='+encodeURIComponent(key));if(!response.ok)throw new Error('预览读取失败')
    const snapshot=await response.json();if(generation!==state.comparisonGeneration)return
    await $('viewer').contentWindow.nbtModeler.replaceSnapshot(snapshot)
  }
  if(generation!==state.comparisonGeneration)return
  state.comparisonSide=side
  state.viewerFeedbackId=side==='before'?result.baseline_feedback_id:result.feedback_id;await activateViewerFeedback(state.viewerFeedbackId)
  $('workspace-context').textContent=`${modelName()} · ${side==='before'?'原建筑':'参数调整效果'} · 同一视角对比，仅预览`
  $('model-hash').textContent=side==='before'?'原建筑':'效果预览（未保存为正式建筑）'
}
$('auto-preview').addEventListener('change',()=>{if($('auto-preview').checked)schedulePreview();else clearTimeout(previewTimer)})
$('update-preview').addEventListener('click',handle(updatePreview))
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
  const query=$('model-search').value.toLocaleLowerCase(),history=$('model-history').checked,groups=new Set(),options=[]
  state.models.forEach((model,index)=>{
    if(!history&&model.intermediate&&state.models.some(other=>other.group===model.group&&!other.intermediate))return
    if(!history&&groups.has(model.group))return
    groups.add(model.group)
    if(query&&!(model.label+' '+model.source).toLocaleLowerCase().includes(query))return
    options.push({model,index})
  })
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
let settingsHistory=[],settingsCursor=-1
function historyButtons(){
  $('undo-settings').disabled=state.busy||settingsCursor<=0
  $('redo-settings').disabled=state.busy||settingsCursor>=settingsHistory.length-1
}
function resetSettingsHistory(){settingsHistory=[JSON.stringify(gather())];settingsCursor=0;historyButtons()}
function recordSettings(){
  try{const next=JSON.stringify(gather());if(settingsHistory[settingsCursor]===next)return
    settingsHistory=settingsHistory.slice(0,settingsCursor+1);settingsHistory.push(next)
    if(settingsHistory.length>60)settingsHistory.shift();settingsCursor=settingsHistory.length-1;historyButtons()
  }catch{} // Keep incomplete numeric edits out of the history.
}
function travelSettings(direction){
  const next=settingsCursor+direction;if(next<0||next>=settingsHistory.length)return
  settingsCursor=next;restore(JSON.parse(settingsHistory[next]));state.configChanged=true;state.bundle='';historyButtons();schedulePreview()
}
$('undo-settings').addEventListener('click',()=>travelSettings(-1));$('redo-settings').addEventListener('click',()=>travelSettings(1))
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
  const lo=$('whole-region').checked?[0,0,0]:['lo-x','lo-y','lo-z'].map(id=>Number($(id).value))
  const hi=$('whole-region').checked?state.info.size.map(v=>v-1):['hi-x','hi-y','hi-z'].map(id=>Number($(id).value))
  viewer.setSelectionRange($('show-selection').checked?{lo,hi}:null)
}
$('show-selection').addEventListener('change',syncSelectionRange)
function syncPicking(){
  $('pick-material').setAttribute('aria-pressed',String(Boolean(state.picking)))
  $('pick-material').textContent=state.picking?'结束取材':'3D 取材'
  $('pick-coordinate').setAttribute('aria-pressed',String(Boolean(state.coordinatePicking)))
  $('pick-coordinate').textContent=state.coordinatePicking?'结束选点':'3D 选点评论'
  $('viewer').contentWindow?.nbtModeler?.setPicking(Boolean(state.aiPlacing||state.picking||state.coordinatePicking),state.coordinatePicking?'comment':'material')
}
$('pick-coordinate').addEventListener('click',()=>{
  state.aiPlacing=null;state.coordinatePicking=!state.coordinatePicking;state.picking=false;syncPicking()
  $('view-hint').textContent=state.coordinatePicking?'连续点击表面添加 #编号，下面按编号写意见；中键平移，滚轮缩放。':'左键旋转，中键平移，滚轮缩放'
})
$('pick-material').addEventListener('click',()=>{
  state.aiPlacing=null;state.picking=!state.picking;state.coordinatePicking=false;syncPicking()
  if(state.picking)$('view-hint').textContent='点击可见方块取材；中键可平移。取材后在左侧选择用途。'
})
window.addEventListener('message',event=>{
  if(event.origin!==location.origin||event.source!==$('viewer').contentWindow)return
  if(event.data?.type==='nbt-annotation-focused'){focusMarker(event.data.number);return}
  if(!['nbt-material-picked','nbt-coordinate-picked'].includes(event.data?.type))return
  const picked=event.data.result
  if(!picked){$('view-hint').textContent='此处没有选到可见方块，请点击建筑表面。';return}
  if(typeof picked.state!=='string'||!Array.isArray(picked.position)||picked.position.length!==3)return
  if(picked.geometry_sha256!==$('viewer').contentWindow.nbtModeler.metadata().geometry_sha256)return
  if(state.aiPlacing){
    const size=state.aiPlacing,normal=picked.normal||[0,1,0],anchor=picked.position.map((v,i)=>v+normal[i]);
    const lo=anchor.map((v,i)=>Math.max(0,Math.min(state.info.size[i]-size[i],v-(i===1?0:Math.floor(size[i]/2))))),hi=lo.map((v,i)=>v+size[i]-1)
    $('whole-region').checked=false;['x','y','z'].forEach((axis,i)=>{setValue('lo-'+axis,lo[i]);setValue('hi-'+axis,hi[i])});state.aiPlacing=null;state.bundle='';syncPicking();updateCount();recordSettings();selectTool(9)
    $('ai-placement-status').textContent='放置表面 '+picked.position.join(', ')+'；选区 '+lo.join(', ')+' → '+hi.join(', ');return
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
initDesktop(async source=>{$('source').value=source;$('context').value='';$('cameras').value='';await loadModel()})
initApiAssistant({
 captureViewport,
 context:()=>{const s=gather(),info=state.info;if(!info)return null;return {size:info.size,lo:s.whole_region?[0,0,0]:s.lo,hi:s.whole_region?info.size.map(v=>v-1):s.hi,materials:info.materials}},
 binding:()=>JSON.stringify({source:state.info?.source_sha256,settings:gather()}),
 localSelection:()=>!!state.info&&!gather().whole_region,
 pickPlacement:async size=>{
   if(!state.info||state.busy||state.previewBusy)throw Error('请先打开建筑并等待当前任务完成')
   if(size.some((v,i)=>v>state.info.size[i]))throw Error('放置范围大于当前建筑尺寸')
   if(state.mode!=='3d')await runJob('snapshot')
   state.aiPlacing=size;state.picking=false;state.coordinatePicking=false;syncPicking();$('view-hint').textContent='点击表面确定 AI 构件放置位置；随后点击“生成并立即预览”。'
 },
 apply:async patch=>{
  if(state.busy||state.previewBusy)throw Error('请等待当前任务完成')
  const next=gather();next.whole_region=false;next.lo=patch.lo;next.hi=patch.hi
  if(patch.operations)next.operations=[...(next.operations||[]),...patch.operations]
  else {next.structure={...next.structure,enabled:false,...patch.structure};next.replace={...next.replace,enabled:false,...patch.replace}}
  await api('prompt-export',{...request(),settings:next})
  restore(next);state.configChanged=true;state.bundle='';updateCount();recordSettings();state.previewRevision++;clearTimeout(previewTimer)
  await updatePreview()
  if(patch.operations)state.lastAIGroup={source:state.info.source_sha256,start:next.operations.length-patch.operations.length,base:structuredClone(patch.operations),applied:JSON.stringify(patch.operations)}
 },
 moveComponent:async offset=>{
  if(state.busy||state.previewBusy)throw Error('请等待当前任务完成')
  const group=state.lastAIGroup;if(!group||group.source!==state.info?.source_sha256)throw Error('请先载入或生成一组AI构件')
  const before=gather(),current=before.operations.slice(group.start,group.start+group.base.length)
  if(JSON.stringify(current)!==group.applied)throw Error('这组工具步骤已经手动改变，请重新生成构件后再整体移动')
  const moved=translateComponent(group.base,offset,state.info.size),next=structuredClone(before);next.operations.splice(group.start,group.base.length,...moved)
  await api('prompt-export',{...request(),settings:next})
  restore(next);state.configChanged=true;state.bundle='';updateCount();state.previewRevision++;clearTimeout(previewTimer)
  try{await updatePreview();group.applied=JSON.stringify(moved);recordSettings()}catch(e){restore(before);throw e}
 }
})
initWorkspaceShell()
initTaskRecords()
initAppSettings()
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
initialize().then(()=>{
  const source=new URLSearchParams(location.search).get('source')
  if(source){const index=state.models.findIndex(model=>model.source===source);if(index<0)throw new Error('所选结构不在当前建筑目录中，请刷新现有结构选择器。');selectModel(index);renderModels()}
  if($('source').value)return loadModel()
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
