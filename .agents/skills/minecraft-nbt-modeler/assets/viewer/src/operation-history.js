import './operation-history.css'
// This is an editor for the shared operations JSON, not a second plan format.
export function initOperationHistory({onChange,onError}){
 const raw=document.getElementById('operation-sequence'),host=document.getElementById('operation-list'),summary=document.getElementById('operation-summary')
 let locked=false,last=''
 function read(){const list=JSON.parse(raw.value);if(!Array.isArray(list)||list.length>128||list.some(op=>!op||typeof op!=='object'||Array.isArray(op)||!globalThis.NbtToolCatalog.tools[op.kind]||typeof op.label!=='string'||!op.label.trim()||(op.enabled!==undefined&&typeof op.enabled!=='boolean')))throw Error('工具序列须为最多128项的已知工具对象数组，每步需要名称与布尔开关');return list}
 function commit(list,label){if(locked)return;raw.value=JSON.stringify(list,null,2);sync(true);onChange(label)}
 function mutate(index,action,label){try{const list=read();if(!list[index])throw Error('步骤已改变，请重试');action(list);commit(list,label)}catch(error){onError(error.message)}}
 function sync(force=false){
  if(!force&&last===raw.value)return;last=raw.value;host.replaceChildren()
  let list
  try{list=read()}catch(error){summary.textContent=error.message+'；修正完整 JSON 或撤销后继续';summary.className='operation-warning';return}
  const active=list.filter(op=>op.enabled!==false).length;summary.className='muted';summary.textContent=list.length?`${active} 项启用 / ${list.length} 项步骤 · 从上到下执行`:'尚无工具步骤。可添加工具、采用 AI 构件或放置资产。'
  list.forEach((op,index)=>{
   const row=document.createElement('article');row.className='operation-row';row.dataset.operation=index;row.dataset.enabled=String(op.enabled!==false)
   const heading=document.createElement('div');heading.className='operation-row-heading'
   const toggle=document.createElement('input');toggle.type='checkbox';toggle.checked=op.enabled!==false;toggle.disabled=locked;toggle.setAttribute('aria-label',`启用第${index+1}步`);toggle.onchange=()=>mutate(index,l=>l[index].enabled=toggle.checked,(toggle.checked?'启用':'停用')+'：'+op.label)
   const name=document.createElement('input');name.className='operation-name';name.value=op.label||'';name.maxLength=160;name.disabled=locked;name.setAttribute('aria-label',`第${index+1}步名称`);name.onchange=()=>{if(!name.value.trim()){name.value=op.label;onError('步骤名称不能为空');return}mutate(index,l=>l[index].label=name.value.trim(),'重命名：'+name.value.trim())};name.onkeydown=event=>{if(event.key==='Enter'){event.preventDefault();name.blur()}}
   const kind=document.createElement('small');kind.textContent=`${index+1}. ${globalThis.NbtToolCatalog.tools[op.kind][0]}`
   heading.append(toggle,name);row.append(heading,kind)
   const actions=document.createElement('div');actions.className='operation-row-actions'
   for(const [action,text,disabled,run]of [
    ['up','上移',index===0,l=>[l[index-1],l[index]]=[l[index],l[index-1]]],
    ['down','下移',index===list.length-1,l=>[l[index+1],l[index]]=[l[index],l[index+1]]],
    ['copy','复制',list.length===128,l=>l.splice(index+1,0,{...structuredClone(l[index]),label:l[index].label+' 副本'})],
    ['remove','删除',false,l=>l.splice(index,1)]]){
    const button=document.createElement('button');button.type='button';button.dataset.action=action;button.textContent=text;button.disabled=locked||disabled;button.setAttribute('aria-label',`${text}第${index+1}步`);button.onclick=()=>mutate(index,run,text+'：'+op.label);actions.append(button)
   }
   const range=document.createElement('span');range.textContent=Array.isArray(op.lo)&&Array.isArray(op.hi)?`${op.lo.join(',')} → ${op.hi.join(',')}`:'自动识别范围';range.className='operation-range';row.append(range,actions)
   const detail=document.createElement('details'),caption=document.createElement('summary'),editor=document.createElement('textarea'),apply=document.createElement('button')
   caption.textContent='本步骤参数';editor.rows=8;editor.spellcheck=false;editor.value=JSON.stringify(op,null,2);editor.disabled=locked;editor.setAttribute('aria-label',`第${index+1}步参数 JSON`);apply.type='button';apply.textContent='应用本步骤参数';apply.disabled=locked
   apply.onclick=()=>{try{const value=JSON.parse(editor.value);if(!value||typeof value!=='object'||Array.isArray(value)||!globalThis.NbtToolCatalog.tools[value.kind]||typeof value.label!=='string'||!value.label.trim()||(value.enabled!==undefined&&typeof value.enabled!=='boolean'))throw Error('请填写有效工具、名称与布尔开关');mutate(index,l=>l[index]=value,'编辑：'+value.label)}catch(error){onError(error.message)}}
   detail.append(caption,editor,apply);row.append(detail);host.append(row)
  })
 }
 return {sync,replace:commit,setBusy(value){locked=value;sync(true)}}
}
