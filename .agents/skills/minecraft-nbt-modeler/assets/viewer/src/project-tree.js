import {latestSources} from './project-catalog.js'
import {createLibraryTreeRow} from './library-browser.js'

const idFor=(...parts)=>JSON.stringify(parts)
const collator=new Intl.Collator('zh-CN',{numeric:true})

export function createProjectTree({container,api,onSelect,onOpen,onStatus,onOrderChange}){
 const heading=document.createElement('div');heading.className='project-tree-heading'
 const title=document.createElement('strong');title.textContent='项目文件'
 const reset=document.createElement('button');reset.type='button';reset.className='project-tree-reset';reset.textContent='↺';reset.title='恢复默认排序（bugged 放最后）';reset.setAttribute('aria-label','恢复默认排序')
 heading.append(title,reset)
 const hint=document.createElement('p');hint.className='project-tree-hint';hint.textContent='拖动排序 · Alt + ↑ / ↓ 移动'
 const tree=document.createElement('div');tree.className='project-tree-list';tree.setAttribute('role','tree');tree.setAttribute('aria-label','项目文件')
 container.replaceChildren(heading,hint,tree)
 let models=[],orders={},roots=[],nodes=new Map(),expanded=new Set(),focused='',selected={},saving=Promise.resolve(),dragged='',initialized=false,sortCache=new Map(),objectOrder=null
 function sorted(children,parent){
  if(sortCache.has(parent))return sortCache.get(parent)
  const saved=orders[parent]||[]
  const positions=new Map(saved.map((id,index)=>[id,index]))
  const result=[...children].sort((a,b)=>{
   const x=positions.get(a.id)??-1,y=positions.get(b.id)??-1
   if(x>=0||y>=0)return (x<0?Infinity:x)-(y<0?Infinity:y)
   return Number(a.shape==='bugged')-Number(b.shape==='bugged')||collator.compare(a.label,b.label)
  })
  sortCache.set(parent,result);return result
 }
 function invalidate(){sortCache.clear();objectOrder=null}
 function save(){
  onStatus('正在保存项目排序…')
  const snapshot=structuredClone({orders})
  saving=saving.catch(()=>{}).then(()=>api('project-layout',snapshot))
  saving.then(()=>onStatus('项目排序已保存到当前工作区')).catch(error=>onStatus('排序未保存：'+error.message))
 }
 function siblings(node){return node.parent==='root'?roots:nodes.get(node.parent)?.children||[]}
 function move(node,target,after=false){
  if(!target||target.id===node.id||target.parent!==node.parent)return
  const list=sorted(siblings(node),node.parent).map(item=>item.id).filter(id=>id!==node.id),index=list.indexOf(target.id)
  if(index<0)return
  list.splice(index+(after?1:0),0,node.id);orders[node.parent]=list;invalidate();focused=node.id;render();onOrderChange();save()
 }
 function select(node){
  const opening=node.children.length&&!expanded.has(node.id)
  selected={project:node.project,shape:node.kind==='project'?'*':node.shape,object:node.kind==='object'?node.object:''}
  if(node.children.length)expanded.add(node.id)
  focused=node.id;onSelect(selected)
  if(opening)render();else for(const row of tree.querySelectorAll('[role=treeitem]'))row.setAttribute('aria-selected',String(isSelected(nodes.get(row.dataset.nodeId))))
 }
 function isSelected(node){return node.kind==='object'?selected.object===node.object:node.kind==='shape'?selected.project===node.project&&selected.shape===node.shape&&!selected.object:selected.project===node.project&&selected.shape==='*'&&!selected.object}
 function render(){
  const wasFocused=tree.contains(document.activeElement),scrollTop=tree.scrollTop;tree.replaceChildren()
  const all=document.createElement('button');all.type='button';all.className='project-tree-all';all.textContent='全部项目';all.onclick=()=>{selected={project:'*',shape:'*',object:''};onSelect(selected);render()};tree.append(all)
  const visible=[]
  function append(node,level){
   const {row,toggle,button:label}=createLibraryTreeRow({label:node.label,level,folder:node.kind!=='object',count:node.count,expanded:node.children.length?expanded.has(node.id):undefined});row.dataset.nodeId=node.id;row.dataset.nodeKind=node.kind;row.dataset.shape=node.shape||'';row.setAttribute('aria-selected',String(isSelected(node)));row.setAttribute('aria-keyshortcuts','Alt+ArrowUp Alt+ArrowDown');row.draggable=true;row.title=node.kind==='object'?node.label+'\n'+(node.item.relative_path||'')+'\n双击进入模型编辑；拖动或 Alt + 方向键排序':node.label+'；拖动排序'
   toggle.onclick=()=>{focused=node.id;if(expanded.has(node.id))expanded.delete(node.id);else expanded.add(node.id);render()}
   label.onclick=()=>select(node)
   if(node.kind==='object')label.ondblclick=()=>onOpen(node.item)
   const peers=sorted(siblings(node),node.parent),index=peers.findIndex(item=>item.id===node.id)
   for(const [direction,symbol,title]of [[-1,'↑','上移'],[1,'↓','下移']]){const button=document.createElement('button');button.type='button';button.className='project-tree-move';button.tabIndex=-1;button.textContent=symbol;button.setAttribute('aria-label',title+node.label);button.disabled=index+direction<0||index+direction>=peers.length;button.onclick=()=>move(node,peers[index+direction],direction>0);row.append(button)}
   row.onfocus=()=>{focused=node.id;visible.forEach(element=>element.tabIndex=element===row?0:-1)}
   row.onkeydown=event=>{
    const target=visible.indexOf(row);let next
    if(event.altKey&&(event.key==='ArrowUp'||event.key==='ArrowDown')){const delta=event.key==='ArrowUp'?-1:1;move(node,peers[index+delta],delta>0)}
    else if(event.key==='ArrowDown')next=visible[target+1]
    else if(event.key==='ArrowUp')next=visible[target-1]
    else if(event.key==='Home')next=visible[0]
    else if(event.key==='End')next=visible.at(-1)
    else if(event.key==='ArrowRight'&&node.children.length){if(!expanded.has(node.id)){expanded.add(node.id);render()}else next=visible[target+1]}
    else if(event.key==='ArrowLeft'){if(expanded.has(node.id)){expanded.delete(node.id);render()}else next=visible.find(element=>element.dataset.nodeId===node.parent)}
    else if(event.key==='Enter')select(node)
    else if(event.key===' '&&node.children.length){if(expanded.has(node.id))expanded.delete(node.id);else expanded.add(node.id);render()}
    else return
    event.preventDefault();next?.focus()
   }
   row.ondragstart=event=>{dragged=node.id;event.dataTransfer.setData('application/x-nbtcreator-node',node.id);event.dataTransfer.effectAllowed='move';row.classList.add('dragging')}
   row.ondragover=event=>{const source=nodes.get(dragged);if(source&&source.parent===node.parent){event.preventDefault();event.dataTransfer.dropEffect='move';row.classList.add('drop-target')}}
   row.ondragleave=()=>row.classList.remove('drop-target')
   row.ondragend=()=>{dragged='';tree.querySelectorAll('.dragging,.drop-target').forEach(item=>item.classList.remove('dragging','drop-target'))}
   row.ondrop=event=>{event.preventDefault();const source=nodes.get(dragged);row.classList.remove('drop-target');if(source)move(source,node,event.clientY>row.getBoundingClientRect().top+row.offsetHeight/2);dragged=''}
   visible.push(row);tree.append(row)
   if(expanded.has(node.id))for(const child of sorted(node.children,node.id))append(child,level+1)
  }
  for(const node of sorted(roots,'root'))append(node,0)
  tree.scrollTop=scrollTop
  const active=visible.find(row=>row.dataset.nodeId===focused)||visible[0];if(active){active.tabIndex=0;if(wasFocused)active.focus({preventScroll:true})}
 }
 function update(items){
  models=items;nodes=new Map();roots=[];invalidate();const latest=latestSources(models)
  for(const item of models){
   const projectId=idFor('project',item.project_key),shapeId=idFor('shape',item.project_key,item.shape_group),objectKey=item.object_key||item.group||item.source,objectId=idFor('object',objectKey)
   if(!nodes.has(projectId)){const node={id:projectId,kind:'project',project:item.project_key,label:item.project_name,parent:'root',children:[],count:0};nodes.set(projectId,node);roots.push(node)}
   if(!nodes.has(shapeId)){const node={id:shapeId,kind:'shape',project:item.project_key,shape:item.shape_group,label:item.shape_group_zh,parent:projectId,children:[],count:0};nodes.set(shapeId,node);nodes.get(projectId).children.push(node)}
   if(!nodes.has(objectId)){const node={id:objectId,kind:'object',project:item.project_key,shape:item.shape_group,object:objectKey,label:item.object_name||item.name_zh||item.name||item.label,parent:shapeId,children:[],count:0,item};nodes.set(objectId,node);nodes.get(shapeId).children.push(node);nodes.get(projectId).count++;nodes.get(shapeId).count++}
   const node=nodes.get(objectId);node.count++;if(latest.has(item.source))node.item=item
  }
  if(!initialized&&roots.length){if(roots.length===1)expanded.add(roots[0].id);initialized=true}
  render()
 }
 reset.onclick=()=>{orders={};invalidate();render();onOrderChange();save()}
 api('project-layout').then(value=>{orders=value.orders||{};invalidate();render();onOrderChange()}).catch(error=>onStatus('无法读取项目排序：'+error.message))
 return {update,orderedObjects(){if(objectOrder)return objectOrder;const result=[];function visit(children,parent){for(const node of sorted(children,parent)){if(node.kind==='object')result.push(node.object);else visit(node.children,node.id)}}visit(roots,'root');objectOrder=result;return result},select(value){selected=value;for(const row of tree.querySelectorAll('[role=treeitem]'))row.setAttribute('aria-selected',String(isSelected(nodes.get(row.dataset.nodeId))))}}
}
