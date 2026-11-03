import {createLibraryTreeRow} from './library-browser.js'

export function createAssetTree({container,onCategory,onOpen,onRender=()=>{}}){
 const expanded=new Set();let focused=''
 return {render(items,category,selected){
  const scroll=container.querySelector('.project-tree-list')?.scrollTop??0,hadFocus=container.contains(document.activeElement)
  container.replaceChildren();const heading=document.createElement('div');heading.className='project-tree-heading';const title=document.createElement('strong');title.textContent='构件分类';const reset=document.createElement('button');reset.className='project-tree-reset';reset.textContent='↺';reset.type='button';reset.title='显示全部构件';reset.setAttribute('aria-label','显示全部构件');reset.onclick=()=>onCategory('all');heading.append(title,reset)
  const hint=document.createElement('p');hint.className='project-tree-hint';hint.textContent='按标签分类 · 点击构件查看';const list=document.createElement('div');list.className='project-tree-list';list.setAttribute('role','tree');list.setAttribute('aria-label','构件标签与对象');const all=document.createElement('button');all.type='button';all.className='project-tree-all';all.textContent='全部构件';all.onclick=()=>onCategory('all');list.append(all);container.append(heading,hint,list)
  const groups=new Map();for(const item of items){for(const tag of item.tags??[]){const key='tag:'+tag;if(!groups.has(key))groups.set(key,{name:tag,items:[]});groups.get(key).items.push(item)}}
  const untagged=items.filter(item=>!item.tags?.length);if(untagged.length)groups.set('untagged',{name:'未分类',items:untagged})
  const rows=[];const add=(entry,id,action)=>{entry.row.dataset.assetNode=id;entry.row.onfocus=()=>{focused=id;rows.forEach(row=>row.tabIndex=row===entry.row?0:-1)};entry.button.onclick=action;entry.row.onkeydown=event=>{let next;if(event.key==='ArrowDown')next=rows[rows.indexOf(entry.row)+1];else if(event.key==='ArrowUp')next=rows[rows.indexOf(entry.row)-1];else if(event.key==='Home')next=rows[0];else if(event.key==='End')next=rows.at(-1);else if(event.key==='Enter')action();else if(['ArrowRight','ArrowLeft',' '].includes(event.key)&&!entry.toggle.disabled){const open=entry.row.getAttribute('aria-expanded')==='true';if(event.key===' '||event.key==='ArrowRight'&&!open||event.key==='ArrowLeft'&&open)entry.toggle.click()}else return;event.preventDefault();next?.focus()};rows.push(entry.row);list.append(entry.row)}
  for(const [key,group]of [...groups].sort((a,b)=>Number(a[0]==='untagged')-Number(b[0]==='untagged')||a[1].name.localeCompare(b[1].name,'zh-CN'))){const entry=createLibraryTreeRow({label:group.name,folder:true,count:group.items.length,expanded:expanded.has(key)});entry.row.setAttribute('aria-selected',String(category===key));entry.toggle.onclick=()=>{if(expanded.has(key))expanded.delete(key);else expanded.add(key);this.render(items,category,selected)};add(entry,key,()=>{expanded.add(key);onCategory(key)})
   if(expanded.has(key))for(const item of group.items){const child=createLibraryTreeRow({label:item.name,level:1,count:''});child.row.setAttribute('aria-selected',String(selected?.id===item.id));add(child,key+':'+item.id,()=>onOpen(item))}
  }
  onRender(container);list.scrollTop=scroll;const active=rows.find(row=>row.dataset.assetNode===focused)||rows[0];if(active){active.tabIndex=0;if(hadFocus)active.focus({preventScroll:true})}
 }}
}
