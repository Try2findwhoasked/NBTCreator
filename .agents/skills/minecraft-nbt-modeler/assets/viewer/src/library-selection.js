export function createLibrarySelection({layout,title,onOpen}){
 const aside=document.createElement('aside');aside.className='library-selection';aside.hidden=true;aside.setAttribute('aria-label',title+'详情')
 const header=document.createElement('header'),heading=document.createElement('h2'),close=document.createElement('button');heading.textContent=title+'详情';close.type='button';close.textContent='关闭';close.setAttribute('aria-label','关闭'+title+'详情');header.append(heading,close)
 const image=document.createElement('img');image.alt='';const name=document.createElement('strong'),meta=document.createElement('p'),open=document.createElement('button');open.type='button';open.className='primary';open.textContent='打开详情';aside.append(header,image,name,meta,open);layout.append(aside)
 let selected=null
 function hide(){selected=null;aside.hidden=true;layout.classList.remove('selection-open')}
 close.onclick=hide;open.onclick=()=>selected&&onOpen(selected)
 aside.addEventListener('keydown',event=>{if(event.key==='Escape'){event.preventDefault();hide()}})
 return {aside,show(item,description=''){selected=item;name.textContent=item.name;meta.textContent=description;image.src=item.thumbnail??'';image.hidden=!item.thumbnail;image.alt=item.name;aside.hidden=false;layout.classList.add('selection-open')},hide,get selected(){return selected}}
}
