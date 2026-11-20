import {linkRange} from '../range-control.js'
import './component-editor.css'
import {componentBounds,surfacePosition} from './component-transform.mjs'

export function initComponentEditor({api,context,prepare,lock,apply,committed,viewer,message,previewPlacement,restorePlacement,commitPlacement}){
 const panel=document.createElement('section');panel.className='component-editor';panel.id='component-editor';panel.hidden=true;panel.setAttribute('aria-label','3D 构件调整')
 panel.innerHTML=`<header><strong id="component-transform-title">3D 构件调整</strong><button id="component-transform-cancel" type="button">取消</button></header><p class="transform-help">拖动彩色箭头移动；拖动绿色圆环按 90° 绕 Y 轴旋转。空白处仍可转向，中键平移，滚轮前后移动。</p><div class="transform-row"><button id="component-transform-translate" type="button">移动手柄 W</button><button id="component-transform-rotate" type="button">旋转手柄 E</button></div><div class="transform-vector">${['x','y','z'].map(axis=>`<label>${axis.toUpperCase()}<input id="component-transform-${axis}" type="number" step="1" aria-label="3D锚点${axis.toUpperCase()}"><input id="component-transform-${axis}-slider" type="range" min="0" max="64" step="1" value="0" aria-label="3D锚点${axis.toUpperCase()}滑块"></label>`).join('')}</div><div class="transform-row"><label>网格<select id="component-transform-grid"><option value="1">1 格</option><option value="2">2 格</option><option value="4">4 格</option><option value="8">8 格</option></select></label><label>旋转<select id="component-transform-turns"><option value="0">0°</option><option value="1">90°</option><option value="2">180°</option><option value="3">270°</option></select></label></div><label>旋转滑块<input id="component-transform-turns-slider" type="range" min="0" max="3" step="1" value="0" aria-label="3D构件旋转滑块"></label><label>镜像<select id="component-transform-mirror"><option value="">无</option><option value="x">沿 X 翻转</option><option value="z">沿 Z 翻转</option></select></label><button type="button" id="component-transform-surface">选表面贴放</button><label><input id="component-transform-overwrite" type="checkbox">允许覆盖目标已有方块</label><p id="component-transform-bounds"></p><p id="component-transform-message" role="status">位置示意；应用后查看真实方块效果。</p><p class="transform-help">贴面按方块格边界对齐，切向位置按所选网格吸附。取消 / Esc 不添加操作；应用后生成候选，再手动导出下一版。</p><div class="transform-actions"><button type="button" id="component-transform-apply" class="primary">应用并预览</button><button type="button" id="component-transform-repeat">应用后继续复制</button></div>`
 document.body.append(panel);const $=id=>document.getElementById(id),frame=()=>$('viewer');let session=null,working=false,starting=false,generation=0,mode='translate',pickSurface=false,returnFocus=null
 const advance=document.createElement('details');advance.className='transform-advanced';advance.innerHTML='<summary>高级设置</summary>'
 panel.querySelector('.transform-vector').before(advance)
 for(const field of [panel.querySelector('.transform-vector'),panel.querySelectorAll('.transform-row')[1],...['turns-slider','mirror','overwrite'].map(id=>$('component-transform-'+id).closest('label'))])advance.append(field)
 const array=document.createElement('div');array.id='component-placement-array';array.innerHTML=`${[['count','阵列数量',1],['spacing','阵列间距',0]].map(([key,label,value])=>`<span>${label} XYZ</span><div class="transform-vector">${['x','y','z'].map(axis=>`<label>${axis.toUpperCase()}<input type="number" id="component-placement-${key}-${axis}" value="${value}" step="1"></label>`).join('')}</div>`).join('')}<label>材质主题<select id="component-placement-theme"></select></label>`
 advance.append(array)
 const rotateOnce=document.createElement('button');rotateOnce.type='button';rotateOnce.id='component-placement-turn';rotateOnce.textContent='旋转 90°'
 $('component-transform-rotate').after(rotateOnce)
 function restoreFocus(){const target=returnFocus?.isConnected&&returnFocus.getClientRects().length&&!returnFocus.disabled?returnFocus:$('studio-panel-tools');target?.focus()}
 const report=(text,error=false)=>{$('component-transform-message').textContent=text;$('component-transform-message').classList.toggle('error',error)}
 function values(){const position=['x','y','z'].map(axis=>{const input=$('component-transform-'+axis),n=Number(input.value);if(!input.value.trim()||!Number.isInteger(n))throw Error('锚点 XYZ 须为整数');return n});return {position,quarter_turns:Number($('component-transform-turns').value),mirror:$('component-transform-mirror').value||null,grid:Number($('component-transform-grid').value),overwrite:$('component-transform-overwrite').checked}}
 function fields(value){for(const [i,axis]of ['x','y','z'].entries())$('component-transform-'+axis).value=value.position[i];$('component-transform-turns').value=value.quarter_turns;$('component-transform-turns-slider').value=value.quarter_turns;positionSync.forEach(sync=>sync())}
 function buttons(){for(const element of panel.querySelectorAll('button,input,select'))element.disabled=working;$('component-transform-translate').setAttribute('aria-pressed',String(mode==='translate'));$('component-transform-rotate').setAttribute('aria-pressed',String(mode==='rotate'));$('component-transform-surface').setAttribute('aria-pressed',String(pickSurface));$('component-transform-surface').textContent=session?.placement?(pickSurface?'点击建筑表面':'重新选点'):(pickSurface?'正在选面（点击取消）':'选表面贴放');if(session?.placement)$('component-transform-cancel').disabled=!!session.committing}
 function bounds(value){const b=componentBounds(session.component,value.position,value.quarter_turns,value.mirror),valid=b.lo.every((n,i)=>n>=0&&b.hi[i]<session.size[i]);$('component-transform-bounds').textContent=`XYZ ${b.lo.join(', ')} → ${b.hi.join(', ')} · ${session.component.blocks.length} 格`;$('component-transform-bounds').hidden=session.placement&&!session.positioned;$('component-transform-apply').disabled=working||!valid||(session.placement&&!session.candidate);$('component-transform-repeat').disabled=working||!valid;if(!valid&&(!session.placement||session.positioned))report('构件超出建筑边界，请重新选点或调整坐标。',true);return valid}
 async function show(){const current=session;if(!current)return;const value=values();const response=await viewer().configureTransform({component:current.component,model_size:current.size,...value,mode,pick_surface:pickSurface,show_ghost:!current.candidate});if(current!==session)return;fields(response);buttons();bounds(value);return response}
 let previewTimer
 async function cancel(){
  const current=session;if(!current)return
  if(current.committing||(!current.placement&&(working||starting)))throw Error('正在处理构件，请稍候')
  clearTimeout(previewTimer);generation++;session=null;panel.hidden=true;pickSurface=false
  try{await viewer()?.configureTransform(null);viewer()?.setPicking(false);if(current.entry)await restorePlacement(current.entry)}
  finally{lock(false);message('已退出构件调整');restoreFocus()}
 }
 async function start(kind,component=null,options={}){
  if(working||starting)throw Error('正在处理构件，请稍候');await cancel();returnFocus=document.activeElement;starting=true
  try{const base=await prepare(options.placement?'placement':kind);if(!base)throw Error('请先打开建筑');let extracted
   if(kind==='selection'){if(base.whole)throw Error('请先在“修改范围”中关闭整座建筑，并选择局部范围');extracted=await api('components/extract',{target_id:base.target_id,lo:base.lo,hi:base.hi,name:options.move?'移动选区':'复制选区'});component=extracted.component}
   if(!component)throw Error('请先选择构件');if(context().source!==base.source||context().source_sha256!==base.source_sha256||context().settings!==base.settings)throw Error('建筑或参数已变化，请重新开始')
   session={...base,kind,component,id:options.id,library:options.library,placement:!!options.placement,move:options.move===true,selection:extracted?{lo:extracted.lo,hi:extracted.hi,target_id:base.target_id}:null};mode='translate';pickSurface=session.placement
   const position=options.position??(extracted?extracted.lo.map((n,i)=>n+component.anchor[i]):base.lo.map((n,i)=>i===1?n:Math.floor((n+base.hi[i])/2)))
   fields({position,quarter_turns:options.quarter_turns??0});$('component-transform-mirror').value=options.mirror??'';$('component-transform-grid').value='1';$('component-transform-overwrite').checked=!!options.overwrite;$('component-transform-title').textContent=(session.move?'移动：':kind==='selection'?'复制：':'放置：')+component.name
   advance.open=!session.placement;array.hidden=!session.placement;rotateOnce.hidden=!session.placement
   $('component-transform-repeat').hidden=session.placement
   $('component-transform-apply').textContent=session.placement?'加入本次修改':'应用并退出'
   $('component-transform-cancel').textContent=session.placement?'退出放置':'取消'
   if(session.placement){
    $('component-transform-title').textContent='放置构件 · '+component.name
    for(const [i,axis] of ['x','y','z'].entries()){$('component-placement-count-'+axis).value=1;$('component-placement-spacing-'+axis).value=component.size[i]}
    $('component-placement-theme').replaceChildren(new Option('保留原材质',''),...(options.themes??[]).map(theme=>new Option(theme.label,theme.value)))
   }
   panel.dataset.placement=String(session.placement)
   lock(true);panel.hidden=false;report(session.placement?'点击建筑表面确定位置。':session.move?'移动会清除源选区的实体方块。':'用手柄调整位置或朝向。')
   await show()
   if(session.placement)viewer().setPicking(true,'material')
   $('component-transform-'+(session.placement?'surface':'x')).focus()
  }catch(error){
   if(session){const entry=session.entry;await viewer()?.configureTransform(null);session=null;panel.hidden=true;lock(false);if(entry)await restorePlacement(entry)}
   if(options.placement)message('未能开始放置：'+error.message,'error')
   throw error
  }finally{starting=false}
 }
 function checkCurrent(current){
  if(context().source!==current.source||context().source_sha256!==current.source_sha256||context().settings!==current.settings)throw Error('建筑或参数已变化，请取消后重新开始')
 }
 async function compile(current,value){
  const request={source:current.source,source_sha256:current.source_sha256,...value}
  if(current.kind==='selection')return api('components/transform',{...request,...current.selection,name:current.component.name,move:current.move})
  if(current.placement){
   for(const [key,field] of [['counts','count'],['spacing','spacing']])request[key]=['x','y','z'].map(axis=>{const input=$('component-placement-'+field+'-'+axis),number=Number(input.value);if(!input.value.trim()||!Number.isInteger(number))throw Error('阵列数量与间距须为整数');return number})
   request.theme=$('component-placement-theme').value||null
  }
  const {grid,...placement}=request
  if(current.library)return api('asset-libraries/place',{...placement,...current.library,content_sha256:current.component.content_sha256})
  return api(current.placement&&(request.counts.some(n=>n!==1)||request.theme)?'components/batch':'components/place',{...placement,...(current.id?{id:current.id}:{component:current.component}),content_sha256:current.component.content_sha256})
 }
 function queuePlacement(){
  const current=session;if(!current?.placement||!current.positioned)return
  current.candidate=null;const token=++generation;clearTimeout(previewTimer);buttons();bounds(values())
  previewTimer=setTimeout(async()=>{
   if(current!==session||token!==generation)return
   if(working){queuePlacement();return}
   try{
    const value=values();if(!bounds(value))return
    working=true;buttons();bounds(value);report('正在预览…')
    checkCurrent(current)
    const patch=await compile(current,value)
    if(current!==session||token!==generation)return
    const candidate=await previewPlacement(current,patch)
    if(current!==session||token!==generation)return
    await viewer().replaceSnapshot(candidate.snapshot)
    if(current!==session||token!==generation)return
    current.candidate=candidate;await show()
    if(current===session&&token===generation)report(candidate.result.missing_checks?.length?'缺少室内检查点，已预览位置。保存前请补齐检查资料。':`已预览 · ${candidate.result.changed_blocks} 个方块变化`)
   }catch(error){if(current===session&&token===generation){await viewer().replaceSnapshot(current.baseline);await show();report(error.message,true)}}
   finally{working=false;if(current===session){buttons();bounds(values())}}
  },100)
 }
 async function confirm(again){if(!session||working)return;const current=session,value=values();if(!bounds(value)||current.placement&&!current.candidate)return
  checkCurrent(current)
  current.committing=true
  working=true;buttons();report('正在核对构件、保护和冲突，并生成真实候选…')
  try{const patch=await compile(current,value)
   if(current.placement&&JSON.stringify(patch.operations)!==JSON.stringify(current.candidate.patch.operations))throw Error('构件内容已变化，请重新选点')
   await viewer().configureTransform(null)
   if(current.placement)await commitPlacement(current,current.candidate);else await apply(patch,current.settings)
   await committed()
   if(again){const next=context();session={...current,kind:'raw',id:null,move:false,selection:null,settings:next.settings,target_id:next.target_id};$('component-transform-title').textContent='继续复制：'+current.component.name;report('上一份已加入候选；移动手柄放下一份。结束时取消仅关闭当前示意。');await show()}
   else{session=null;panel.hidden=true;lock(false);message('构件已加入候选并预览；满意后保存制作版或定稿导出 NBT。');restoreFocus()}
  }catch(error){if(context().source===current.source&&context().source_sha256===current.source_sha256&&viewer()?.status==='ready')await show();else{session=null;panel.hidden=true;lock(false)}throw error}
  finally{current.committing=false;working=false;buttons();if(session)bounds(values())}
 }
 const safe=action=>()=>Promise.resolve().then(action).catch(error=>report(error.message,true))
 async function changed(){if(session?.placement){session.positioned=true;pickSurface=false;viewer().setPicking(false);queuePlacement()}await show()}
 const positionSync=['x','y','z'].map((axis,i)=>linkRange($('component-transform-'+axis),$('component-transform-'+axis+'-slider'),()=>[0,(session?.size[i]??65)-1],safe(changed)))
 $('component-transform-turns-slider').oninput=safe(()=>{$('component-transform-turns').value=$('component-transform-turns-slider').value;return changed()})
 const setMode=next=>{mode=next;pickSurface=false;return show()}
 for(const id of ['component-transform-x','component-transform-y','component-transform-z','component-transform-grid','component-transform-turns','component-transform-mirror','component-transform-overwrite',...Array.from(array.querySelectorAll('input,select'),field=>field.id)])$(id).addEventListener('change',safe(changed))
 rotateOnce.onclick=safe(()=>{const turns=$('component-transform-turns');turns.value=(Number(turns.value)+1)%4;return changed()})
 $('component-transform-translate').onclick=safe(()=>setMode('translate'));$('component-transform-rotate').onclick=safe(()=>setMode('rotate'));$('component-transform-surface').onclick=safe(async()=>{if(session.placement){clearTimeout(previewTimer);generation++;session.candidate=null;session.positioned=false;pickSurface=true;await viewer().replaceSnapshot(session.baseline);report('点击建筑表面确定位置。')}else pickSurface=!pickSurface;viewer().setPicking(pickSurface,'material');return show()});$('component-transform-cancel').onclick=safe(cancel);$('component-transform-apply').onclick=safe(()=>confirm(false));$('component-transform-repeat').onclick=safe(()=>confirm(true))
 function key(code){if(!session)return;if(code==='Escape')return safe(cancel)();if(working)return;if(code==='KeyW')return safe(()=>setMode('translate'))();if(code==='KeyE')return safe(()=>setMode('rotate'))()}
 window.addEventListener('keydown',event=>{if(session&&!event.ctrlKey&&!event.metaKey&&!event.altKey&&(event.code==='Escape'||!event.target.closest('input,textarea,select'))&&['Escape','KeyW','KeyE'].includes(event.code)){event.preventDefault();key(event.code)}})
 window.addEventListener('message',event=>{if(event.origin!==location.origin||event.source!==frame().contentWindow||!session)return
  if(event.data?.type==='nbt-transform-key'){key(event.data.code);return}
  if(event.data?.type!=='nbt-transform-change'||event.data.geometry_sha256!==viewer()?.metadata().geometry_sha256)return
  if(working)return
  try{
   const value=event.data.value;componentBounds(session.component,value.position,value.quarter_turns,value.mirror);fields(value)
   if(session.placement){
    session.positioned=true
    if(value.dragging){session.candidate=null;generation++;clearTimeout(previewTimer)}
    else queuePlacement()
   }
   buttons();bounds(value)
  }catch(error){report(error.message,true)}
 })
 window.addEventListener('creator-workspace-change',event=>{if(event.detail!=='model'&&session&&(!working||session.placement)&&!starting)cancel().catch(error=>message(error.message,'error'))})
 return {startAsset:(component,options)=>start('asset',component,options),startSelection:move=>start('selection',null,{move}),cancel,get active(){return !!session},get working(){return working||starting},sync:()=>{if(session){buttons();try{bounds(values())}catch{}}},consumePick(picked){if(!session)return false;if(pickSurface&&!working){safe(async()=>{const value=values();fields({...value,position:surfacePosition(session.component,picked,value.quarter_turns,value.mirror,value.grid)});if(session.placement)await changed();else{pickSurface=false;viewer().setPicking(false);report('已贴面，可拖动手柄微调。');await show()}})()}return true}}
}
