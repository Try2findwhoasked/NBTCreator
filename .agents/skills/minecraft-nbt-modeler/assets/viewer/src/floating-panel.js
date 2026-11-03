// Keep expandable controls out of document flow and preserve the page's scroll position.
export function floatingDetails(root,panel,{minimum=210}={}){
 const summary=root.querySelector(':scope > summary');panel.setAttribute('popover','manual')
 function close(){root.open=false;if(panel.matches(':popover-open'))panel.hidePopover()}
 function place(){const box=summary.getBoundingClientRect(),width=Math.min(Math.max(box.width,minimum),innerWidth-24);panel.style.width=width+'px';panel.style.left=Math.max(12,Math.min(box.left,innerWidth-width-12))+'px';const below=innerHeight-box.bottom-12,above=box.top-12,up=below<180&&above>below;panel.style.maxHeight=Math.max(80,Math.min(400,up?above:below))+'px';panel.style.top=(up?'auto':box.bottom+5+'px');panel.style.bottom=(up?innerHeight-box.top+5+'px':'auto')}
 function sync(){summary.setAttribute('aria-expanded',String(root.open));if(root.open){window.dispatchEvent(new CustomEvent('nbt-floating-open',{detail:root}));place();if(!panel.matches(':popover-open'))panel.showPopover()}else if(panel.matches(':popover-open'))panel.hidePopover()}
 summary.addEventListener('click',event=>{event.preventDefault();root.open=!root.open;sync()});root.addEventListener('toggle',()=>{if(root.open!==panel.matches(':popover-open'))sync()})
 document.addEventListener('pointerdown',event=>{if(root.open&&!root.contains(event.target))close()})
 document.addEventListener('keydown',event=>{if(root.open&&event.key==='Escape'){event.preventDefault();close();summary.focus({preventScroll:true})}})
 window.addEventListener('nbt-floating-open',event=>{if(event.detail!==root&&!root.contains(event.detail)&&!event.detail.contains(root))close()});window.addEventListener('resize',close)
 document.addEventListener('scroll',event=>{if(root.open&&!panel.contains(event.target))close()},true)
 window.addEventListener('creator-workspace-change',close)
 return {close}
}
export const chevron='<svg viewBox="0 0 16 16" aria-hidden="true"><path d="m4 6 4 4 4-4"/></svg>'
