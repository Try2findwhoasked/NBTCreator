import {createLibraryTreeRow} from './library-browser.js'

// The three material editions share a folder interaction: the whole row
// selects and toggles, while file rows open the corresponding inspector.
export function createUseTree({container,title,onFolder,onItem,groupsFor,customGroups=()=>[],assignment=()=>''}){
 const expanded=new Set()
 function render(items,selected='all'){
  const scroll=container.querySelector('.project-tree-list')?.scrollTop??0
  container.replaceChildren()
  const heading=document.createElement('div');heading.className='project-tree-heading';const name=document.createElement('strong');name.textContent=title;heading.append(name)
  const list=document.createElement('div');list.className='project-tree-list';list.setAttribute('role','tree');list.setAttribute('aria-label',title+'文件');container.append(heading,list)
  const groups=new Map()
  for(const item of items)for(const tag of groupsFor(item)){const key='tag:'+tag;if(!groups.has(key))groups.set(key,{label:tag,items:[]});groups.get(key).items.push(item)}
  for(const group of customGroups())groups.set('group:'+group.id,{label:group.name,items:items.filter(item=>assignment(item.id)===group.id)})
  const folders=[['all',{label:'全部'+title,items}],...groups.entries()]
  for(const [key,group]of folders){
   const entry=createLibraryTreeRow({label:group.label,folder:true,count:group.items.length,expanded:expanded.has(key)})
   entry.row.dataset.folderId=key;entry.row.setAttribute('aria-selected',String(selected===key));entry.toggle.remove()
   const activate=()=>{if(expanded.has(key))expanded.delete(key);else expanded.add(key);onFolder(key);render(items,key)}
   entry.row.onclick=activate;entry.row.onkeydown=event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();activate()}}
   entry.row.tabIndex=0;entry.row.title='点击'+(expanded.has(key)?'收起':'展开')+'并筛选'+group.label;list.append(entry.row)
   if(expanded.has(key))for(const item of group.items){const child=createLibraryTreeRow({label:item.name,level:1});child.toggle.remove();child.row.tabIndex=0;child.row.dataset.fileId=item.id;child.row.onclick=()=>onItem(item);child.row.onkeydown=event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();onItem(item)}};list.append(child.row)}
  }
  list.scrollTop=scroll
 }
 return {render}
}
