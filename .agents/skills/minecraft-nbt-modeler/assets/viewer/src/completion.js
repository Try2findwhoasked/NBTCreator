let completionId=0
export function complete(input,provider,onChoose=()=>{},options={}){
  const popup=document.createElement('div');popup.className='completion-popup';popup.hidden=true;popup.setAttribute('role','listbox');popup.id='complete-'+(input.id||++completionId)
  document.body.append(popup);input.setAttribute('aria-controls',popup.id);input.setAttribute('aria-autocomplete','list')
  let items=[],active=0,range=null
  function close(){popup.hidden=true;input.setAttribute('aria-expanded','false')}
  function paint(){
    popup.replaceChildren();const rect=input.getBoundingClientRect()
    popup.style.left=Math.max(8,Math.min(rect.left,innerWidth-320))+'px';popup.style.width=Math.min(Math.max(rect.width,300),innerWidth-24)+'px'
    popup.style.top=Math.min(rect.bottom+4,innerHeight-220)+'px'
    items.forEach((item,i)=>{const button=document.createElement('button');button.type='button';button.setAttribute('role','option');button.setAttribute('aria-selected',String(i===active));button.textContent=item.label;button.title=item.detail ?? item.value
      button.addEventListener('mousedown',event=>event.preventDefault());button.addEventListener('click',()=>choose(i));popup.append(button)})
    popup.hidden=!items.length;input.setAttribute('aria-expanded',String(Boolean(items.length)))
  }
  function refresh(){if(input.disabled||document.activeElement!==input||!input.getClientRects().length)return close();const result=provider(input.value,input.selectionStart ?? input.value.length);range=result?.range;items=(result?.items ?? []).slice(0,options.maxItems ?? 12);active=Math.max(0,items.findIndex(item=>item.selected));paint();if(options.highlightSelection&&!popup.hidden)popup.children[active]?.scrollIntoView({block:'nearest'})}
  function choose(index){const item=items[index];if(!item||!range)return;input.setRangeText(item.value,range[0],range[1],'end');close();input.dispatchEvent(new Event('input',{bubbles:true}));input.dispatchEvent(new Event('change',{bubbles:true}));close();input.focus();onChoose(item)}
  input.addEventListener('input',event=>{if(!event.isComposing)refresh()});input.addEventListener('focus',refresh)
  input.addEventListener('keydown',event=>{
    if(event.isComposing||popup.hidden||event.ctrlKey||event.altKey||event.metaKey)return
    if(event.key==='Escape'){event.preventDefault();close()}
    else if(event.key==='ArrowDown'||event.key==='ArrowUp'){event.preventDefault();active=(active+(event.key==='ArrowDown'?1:items.length-1))%items.length;paint();popup.children[active]?.scrollIntoView({block:'nearest'})}
    else if(event.key==='Tab'&&!event.shiftKey||event.key==='Enter'){event.preventDefault();choose(active)}
  });input.addEventListener('blur',close);window.addEventListener('resize',close);window.addEventListener('scroll',event=>{if(!popup.contains(event.target))close()},true)
  return {refresh,close}
}
