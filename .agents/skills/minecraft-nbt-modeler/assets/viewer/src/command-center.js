import './command-center.css'
import {commandDefinitions,defaultPreferences,validateCommandPreferences,eventShortcut,shortcutLabel,searchCommands} from './command-contract.mjs'

export function initCommandCenter({api,state,selectTool,message}){
 const $=id=>document.getElementById(id),commands=commandDefinitions(globalThis.NbtToolCatalog),byId=new Map(commands.map(c=>[c.id,c]))
 let preferences=defaultPreferences(),revision=0,queue=Promise.resolve(),loaded=false,shown=[],active=0,previousFocus=null,restoreFocus=true,draft=null,recording=null,availabilityTimer
 const dialog=document.createElement('dialog');dialog.id='command-dialog';dialog.className='command-dialog';dialog.setAttribute('aria-label','搜索命令与工具')
 dialog.innerHTML='<header><svg viewBox="0 0 20 20" aria-hidden="true"><circle cx="8.5" cy="8.5" r="5.5"/><path d="m13 13 4 4"/></svg><input id="command-query" type="search" autocomplete="off" placeholder="搜索工具、工作区或操作…" aria-label="搜索工具、工作区或操作"><button id="command-close" type="button" aria-label="关闭命令搜索">Esc</button></header><p id="command-results-hint"></p><ul id="command-results" aria-label="匹配命令"></ul><footer><span>↑ ↓ 选择 · Enter 执行 · ☆ 收藏</span><button id="command-shortcut-settings" type="button">快捷键设置</button></footer><p id="command-status" role="status"></p>';document.body.append(dialog)
 const opener=document.createElement('button');opener.id='open-command-center';opener.type='button';opener.innerHTML='<svg viewBox="0 0 20 20" aria-hidden="true"><circle cx="8.5" cy="8.5" r="5.5"/><path d="m13 13 4 4"/></svg><span>搜索工具</span><kbd></kbd>';opener.setAttribute('aria-label','搜索命令与工具');document.querySelector('.creator-header-actions').prepend(opener)
 const effectiveKey=id=>preferences.shortcuts[id]??byId.get(id)?.shortcut??''
 const modalOpen=()=>[...document.querySelectorAll('dialog[open]')].some(d=>d!==dialog&&!['prompt-dialog','api-dialog'].includes(d.id))
 function reason(command){
  const s=state();if(command.id==='commands.open')return ''
  if(s.sessionRestoring)return '正在恢复建筑草稿，请稍候'
  if(command.workspace){const tab=document.querySelector(`button[data-workspace="${command.workspace}"]`);if(tab?.disabled||s.busy)return '当前任务仍在运行'}
  if(command.id==='settings.open'&&(!$('open-settings')||$('open-settings').disabled))return '设置暂不可用'
  if(command.model&&!s.info)return '请先从项目管理打开建筑'
  if((command.model||command.panel!==undefined)&&(s.transforming||s.versionComparing))return s.transforming?'请先应用或取消3D构件调整':'请先退出版本对比'
  if(command.model&&(s.previewBusy||s.commitBusy))return '正在更新候选模型，请稍候'
  if(command.target&&$(command.target)?.disabled)return '此操作当前不可用，请先完成对应步骤'
  if(command.target&&!$(command.target))return '当前环境不提供此操作'
  if(command.id.startsWith('asset.')&&$('whole-region')?.checked)return '请先在修改范围中选择局部区域'
  if(command.id==='asset.capture'&&s.mode!=='3d')return '请先打开3D，再保存所看选区'
  return ''
 }
 function updateOpener(){const key=effectiveKey('commands.open');opener.querySelector('kbd').textContent=shortcutLabel(key);opener.querySelector('kbd').hidden=!key;opener.title='搜索命令与工具'+(key?' · '+shortcutLabel(key):'')}
 async function load(){const result=await api('command-preferences');preferences=validateCommandPreferences(result.preferences,commands);revision=result.revision;loaded=true;updateOpener();return result}
 async function mutate(change){const operation=queue.catch(()=>{}).then(async()=>{if(!loaded)await load();const next=validateCommandPreferences(change(structuredClone(preferences)),commands);if(JSON.stringify(next)===JSON.stringify(preferences))return;const result=await api('command-preferences',{expected_revision:revision,preferences:next});preferences=result.preferences;revision=result.revision;updateOpener()});queue=operation;return operation}
 function announce(value,error=false){$('command-status').textContent=value;$('command-status').classList.toggle('error',error)}
 function highlight(index,scroll=false){active=Math.max(0,Math.min(index,shown.length-1));[...$('command-results').children].forEach((row,i)=>{row.classList.toggle('selected',i===active);row.querySelector('.command-run').setAttribute('aria-current',String(i===active))});if(scroll)$('command-results').children[active]?.scrollIntoView({block:'nearest'})}
 function render(){
  const prior=shown[active]?.id;shown=searchCommands(commands.filter(c=>c.id!=='commands.open'),preferences,$('command-query').value);const host=$('command-results');host.replaceChildren()
  $('command-results-hint').textContent=shown.length?`${shown.length} 项 · 收藏和最近使用的命令优先`:'没有匹配命令，可尝试工具中文名或 box、beam 等工具 ID'
  for(const command of shown){const row=document.createElement('li');row.dataset.command=command.id;const run=document.createElement('button');run.type='button';run.className='command-run';const heading=document.createElement('strong');heading.textContent=command.label;const hint=document.createElement('span');hint.className='command-description';const unavailable=reason(command);hint.textContent=unavailable||command.group+(preferences.favorites.includes(command.id)?' · 常用':preferences.recent.includes(command.id)?' · 最近使用':'');run.disabled=!!unavailable;run.append(heading,hint);run.onclick=()=>execute(command.id).catch(error=>announce(error.message,true));const key=document.createElement('kbd');key.textContent=shortcutLabel(effectiveKey(command.id));run.append(key)
   const favorite=document.createElement('button');favorite.type='button';favorite.className='command-favorite';const pinned=preferences.favorites.includes(command.id);favorite.textContent=pinned?'★':'☆';favorite.setAttribute('aria-label',(pinned?'取消收藏：':'收藏：')+command.label);favorite.setAttribute('aria-pressed',String(pinned));favorite.onclick=async()=>{try{await mutate(p=>{p.favorites=p.favorites.includes(command.id)?p.favorites.filter(id=>id!==command.id):[...p.favorites,command.id];return p});render();announce(pinned?'已取消收藏':'已收藏，搜索为空时优先显示')}catch(error){announce(error.message,true)}}
   row.append(run,favorite);host.append(row)
  }
  highlight(Math.max(0,shown.findIndex(c=>c.id===prior)))
 }
 function open(){if(dialog.open){dialog.close();return}if(modalOpen())return;previousFocus=document.activeElement;announce('');$('command-query').value='';render();dialog.showModal();$('command-query').focus();availabilityTimer=setInterval(()=>{for(const row of $('command-results').children){const c=byId.get(row.dataset.command),unavailable=reason(c);row.querySelector('.command-run').disabled=!!unavailable;row.querySelector('.command-description').textContent=unavailable||c.group+(preferences.favorites.includes(c.id)?' · 常用':preferences.recent.includes(c.id)?' · 最近使用':'')}},200)}
 async function execute(id){const command=byId.get(id);if(!command)throw Error('未知命令');const unavailable=reason(command);if(unavailable)throw Error(unavailable);if(id==='commands.open'){open();return}
  restoreFocus=false;dialog.close();if(command.workspace)window.creatorWorkspace.select(command.workspace)
  if(command.panel!==undefined){selectTool(command.panel);$('settings').scrollTop=0;document.querySelector(`#tool-tabs button[data-tool-index="${command.panel}"]`)?.focus({preventScroll:true})}
  else if(command.kind){selectTool(8);$('operation-kind').value=command.kind;$('operation-add').click()}
  else if(command.target){const target=$(command.target);if(target.disabled||target.closest('[inert]'))throw Error('此操作暂不可用');target.click()}
  mutate(p=>({...p,recent:[id,...p.recent.filter(v=>v!==id)].slice(0,20)})).catch(error=>message('命令已执行，使用记录未保存：'+error.message,'error'))
 }
 opener.onclick=open;$('command-close').onclick=()=>dialog.close();$('command-query').oninput=()=>{active=0;render()}
 dialog.addEventListener('close',()=>{clearInterval(availabilityTimer);if(restoreFocus&&previousFocus?.isConnected)previousFocus.focus({preventScroll:true});restoreFocus=true})
 dialog.addEventListener('keydown',event=>{if(event.isComposing)return;if(event.key==='Escape'){event.preventDefault();event.stopPropagation();dialog.close()}else if(event.key==='ArrowDown'||event.key==='ArrowUp'){event.preventDefault();highlight((active+(event.key==='ArrowDown'?1:-1)+shown.length)%Math.max(1,shown.length),true)}else if(event.key==='Enter'&&event.target===$('command-query')){event.preventDefault();if(shown[active])execute(shown[active].id).catch(error=>announce(error.message,true))}})
 function onKey(event){
  if(event.defaultPrevented||modalOpen())return;const key=eventShortcut(event);if(!key)return
  let command=commands.find(c=>effectiveKey(c.id)===key)
  if(!command&&key==='Ctrl+Shift+KeyZ'&&!Object.hasOwn(preferences.shortcuts,'edit.redo'))command=byId.get('edit.redo')
  if(!command||dialog.open&&command.id!=='commands.open')return
  if(command.id!=='commands.open'&&(command.model&&event.target.closest?.('input,textarea,select,[contenteditable="true"]')||window.creatorWorkspace.current()!=='model'&&command.id.startsWith('edit.')))return
  // A recognized command owns the key even while unavailable; it must never fall through to an unsafe alternate action.
  event.preventDefault();event.stopPropagation();execute(command.id).catch(error=>message(error.message,'error'))
 }
 document.addEventListener('keydown',onKey,true)
 const documents=new WeakSet();function hookFrame(frame){const attach=()=>{try{const doc=frame.contentDocument;if(doc&&!documents.has(doc)){documents.add(doc);doc.addEventListener('keydown',onKey,true)}}catch{}};frame.addEventListener('load',attach);attach()}
 for(const id of ['viewer','prompt-frame'])hookFrame($(id))

 // Settings use the same validated draft and workspace file as the palette.
 const settings=$('app-settings-dialog'),section=document.createElement('section');section.dataset.settingsPage='commands';section.hidden=true
 section.innerHTML='<h3>常用工具与快捷键</h3><p>点击快捷键框后按组合键；Backspace 清除，Esc 取消录入。输入框内保留文字编辑快捷键，Ctrl+K 可从输入框或3D视口打开搜索。3D 手柄的 W、E、Esc 和评论的 Ctrl+Enter 保持专用。</p><input id="command-settings-search" type="search" placeholder="查找要设置的命令" aria-label="筛选快捷键命令"><div class="command-settings-actions"><button type="button" id="command-shortcuts-reset">恢复默认快捷键</button><button type="button" id="command-favorites-clear">清空收藏</button></div><p id="command-settings-status" role="status"></p><div id="command-shortcut-list"></div><p>配置保存到当前工作区的 .nbtcreator/commands.json；更换电脑后仍可复用。Ctrl+Z / Ctrl+Y 默认撤销、重做参数，Ctrl+Shift+Z 也可重做。系统关闭、重载、全屏和文字编辑组合键不能分配给其他操作。最后点击底部“保存配置”生效。</p>'
 function settingsMessage(value,error=false){$('command-settings-status').textContent=value;$('command-settings-status').classList.toggle('error',error)}
 function renderSettings(){
  const host=$('command-shortcut-list'),query=$('command-settings-search').value.trim().toLowerCase();host.replaceChildren();recording=null
  for(const command of commands.filter(c=>[c.label,c.id,c.group].join(' ').toLowerCase().includes(query))){const row=document.createElement('div');row.className='command-shortcut-row';row.dataset.command=command.id;const label=document.createElement('label'),name=document.createElement('strong'),group=document.createElement('small'),input=document.createElement('input'),clear=document.createElement('button');name.textContent=command.label;group.textContent=command.group;label.append(name,group);input.id='shortcut-'+command.id.replaceAll('.','-');input.readOnly=true;input.placeholder='未设置';input.value=shortcutLabel(draft?.[command.id]??command.shortcut??'');input.setAttribute('aria-label','快捷键：'+command.label);label.htmlFor=input.id;clear.type='button';clear.textContent='×';clear.setAttribute('aria-label','清除快捷键：'+command.label)
   function stop(){recording=null;input.classList.remove('recording');input.value=shortcutLabel(draft?.[command.id]??command.shortcut??'')}
   input.onfocus=()=>{recording=command.id;input.classList.add('recording');input.value='请按组合键…'};input.onblur=stop
   input.onkeydown=event=>{if(event.isComposing||event.key==='Tab')return;event.preventDefault();event.stopPropagation();if(event.key==='Escape'){stop();return}if(['Control','Alt','Shift'].includes(event.key))return;try{const key=['Backspace','Delete'].includes(event.key)?'':eventShortcut(event);if(key===null)throw Error('请使用 Ctrl / Alt 组合键，或可用的功能键');const next={...draft,[command.id]:key};validateCommandPreferences({...preferences,shortcuts:next},commands);draft=next;stop();settingsMessage('快捷键已调整，点击“保存配置”后生效')}catch(error){settingsMessage(error.message,true)}}
   clear.onclick=()=>{draft={...draft,[command.id]:''};stop();settingsMessage('快捷键已清除，点击“保存配置”后生效')};row.append(label,input,clear);host.append(row)
  }
 }
 if(settings){settings.querySelector('.settings-content').append(section);const tab=document.createElement('button');tab.type='button';tab.dataset.settingsTab='commands';tab.textContent='操作与快捷键';const nav=settings.querySelector('.settings-tabs');nav.insertBefore(tab,nav.querySelector('[data-settings-tab=updates]'));tab.onclick=()=>{settings.querySelectorAll('[data-settings-page]').forEach(p=>p.hidden=p!==section);settings.querySelectorAll('[data-settings-tab]').forEach(b=>b.setAttribute('aria-pressed',String(b===tab)))}
  $('command-settings-search').oninput=renderSettings;$('command-shortcuts-reset').onclick=()=>{draft={};renderSettings();settingsMessage('已恢复默认快捷键，点击“保存配置”后生效')};$('command-favorites-clear').onclick=async()=>{try{await mutate(p=>({...p,favorites:[]}));settingsMessage('当前工作区收藏已清空')}catch(error){settingsMessage(error.message,true)}}
 }
 $('command-shortcut-settings').disabled=!settings;$('command-shortcut-settings').onclick=async()=>{if(!settings)return;try{dialog.close();await $('open-settings').onclick();if(settings.open)settings.querySelector('[data-settings-tab=commands]').click()}catch(error){message(error.message,'error')}}
 const controller={async settingsOpened(){await queue.catch(()=>{});try{await load();settingsMessage('')}catch(error){settingsMessage('命令配置未读取：'+error.message,true)}draft={...preferences.shortcuts};renderSettings()},async saveSettings(){if(draft===null||JSON.stringify(draft)===JSON.stringify(preferences.shortcuts))return;await mutate(p=>({...p,shortcuts:draft}));renderSettings();settingsMessage('快捷键已保存')},open,execute,ready:null}
 controller.ready=load().catch(error=>message('命令收藏与快捷键未读取：'+error.message,'error'));window.nbtCommands=Object.freeze(controller);updateOpener();return controller
}
