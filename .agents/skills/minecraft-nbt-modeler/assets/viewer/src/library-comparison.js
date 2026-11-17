import './library-workbench.css'

const el=(tag,text,className)=>{
 const node=document.createElement(tag)
 if(text!==undefined)node.textContent=text
 if(className)node.className=className
 return node
}
function button(label,click){
 const node=el('button',label)
 node.type='button'
 node.onclick=click
 return node
}

// A comparison belongs to one catalogue, independent of the current search.
// Re-resolve selected IDs on refresh so removed entries can't be acted upon.
export function createComparison({host,grid,kind,key,name,fields,preview,open,openLabel,pairAction,canComparePair=()=>true,available=()=>true}){
 const selected=new Map()
 let comparing=false
 const mode=button('比较',()=>setMode(!comparing))
 mode.className='library-compare-mode'
 mode.dataset.libraryKind=kind
 host.querySelector('.library-toolbar').append(mode)
 const tray=el('section',undefined,'library-tray')
 tray.dataset.libraryKind=kind
 tray.setAttribute('aria-label',kind+'比较栏')
 const selection=el('div',undefined,'library-tray-items')
 const review=button('并排比较',show)
 const status=el('span')
 status.setAttribute('role','status')
 tray.append(status,selection,review)
 host.append(tray)
 const dialog=el('dialog',undefined,'library-comparison')
 dialog.setAttribute('aria-label','比较'+kind)
 const header=el('header'),title=el('h2','比较'+kind)
 header.append(title,button('返回列表',()=>dialog.close()))
 const content=el('div',undefined,'comparison-content')
 const footer=el('footer')
 dialog.append(header,content,footer);document.body.append(dialog)
 let revision=0
 function setMode(active){
  comparing=active
  if(!active)selected.clear()
  grid.classList.toggle('choosing-comparison',active)
  mode.textContent=active?'退出比较':'比较'
  mode.setAttribute('aria-pressed',String(active))
  sync()
 }

 function sync(){
  tray.hidden=!comparing
  review.disabled=selected.size!==2
  status.textContent=['点选两项进行比较','再选一项即可比较','已选两项'][selected.size]
  selection.replaceChildren()
  for(const [id,item] of selected){
   const remove=button(name(item)+' ×',()=>{selected.delete(id);sync();mode.focus()})
   remove.setAttribute('aria-label','移出比较：'+name(item));selection.append(remove)
  }
  for(const pick of grid.querySelectorAll('[data-compare-id]'))paint(pick)
 }
 function paint(pick){
  const chosen=selected.has(pick.dataset.compareId)
  const mark=pick.querySelector('.library-choice-mark')
  mark.hidden=!comparing
  mark.textContent=chosen?'已选':'选择'
  pick.classList.toggle('comparison-selected',chosen)
  if(comparing){
   pick.setAttribute('aria-label',(chosen?'移出比较：':'加入比较：')+pick.dataset.compareName)
   pick.setAttribute('aria-pressed',String(chosen))
  }else{
   pick.removeAttribute('aria-label')
   if(pick.dataset.originalPressed!==undefined)pick.setAttribute('aria-pressed',pick.dataset.originalPressed)
   else pick.removeAttribute('aria-pressed')
  }
 }
 function decorate(card,item){
  const id=key(item)
  const pick=card.querySelector('button')
  pick.dataset.compareName=name(item)
  if(pick.hasAttribute('aria-pressed'))pick.dataset.originalPressed=pick.getAttribute('aria-pressed')
  pick.addEventListener('click',event=>{
   if(!comparing)return
   event.preventDefault();event.stopImmediatePropagation()
   if(selected.has(id))selected.delete(id)
   else if(selected.size<2)selected.set(id,item)
   else {status.textContent='已选两项，先移出一项再更换。';return}
   sync()
  },true)
  pick.dataset.compareId=id
  pick.append(el('span',undefined,'library-choice-mark'))
  paint(pick)
 }
 function reconcile(items){
  mode.disabled=items.length<2&&!comparing
  mode.title=mode.disabled?'库中至少需要两项才能比较':'在筛选结果中选择两项'
  if(!selected.size)return
  const latest=new Map(items.map(item=>[key(item),item]))
  for(const id of selected.keys()){
   if(latest.has(id))selected.set(id,latest.get(id))
   else selected.delete(id)
  }
  sync()
  if(dialog.open){if(selected.size===2)show();else dialog.close()}
 }
 async function show(){
  if(selected.size!==2)return
  const token=++revision,pair=[...selected.values()]
  const table=el('table'),head=el('thead'),headRow=el('tr'),body=el('tbody')
  headRow.append(el('th','比较项目'))
  for(const item of pair){const th=el('th',name(item));th.scope='col';headRow.append(th)}
  head.append(headRow);table.append(head,body)
  function row(label){
   const tr=el('tr'),th=el('th',label)
   th.scope='row';tr.append(th);body.append(tr);return tr
  }
  const images=row('预览')
  for(const item of pair){
   const cell=el('td','正在读取…','comparison-image');images.append(cell)
   Promise.resolve().then(()=>preview(item)).then(url=>{
    if(token!==revision||!dialog.open)return
    if(!url){cell.textContent='暂无预览图';return}
    const image=el('img');image.alt=name(item)+'的预览';image.onerror=()=>{cell.textContent='预览图无法读取'}
    image.src=url;cell.replaceChildren(image)
   }).catch(()=>{if(token===revision)cell.textContent='预览图无法读取'})
  }
  for(const [label,value] of fields){
   const tr=row(label),values=pair.map(item=>value(item) || '未记录')
   tr.dataset.different=String(values[0]!==values[1])
   for(const text of values)tr.append(el('td',text))
  }
  const choose=row('下一步')
  for(const item of pair){
   const td=el('td'),go=button(openLabel,()=>{dialog.close();setMode(false);open(item)})
   go.disabled=!available(item);td.append(go);choose.append(td)
  }
  content.replaceChildren(table);footer.replaceChildren()
  if(pairAction){
   const compare=button('查看三维差异',()=>{dialog.close();setMode(false);pairAction(...pair)})
   compare.disabled=!pair.every(available)||!canComparePair()
   footer.append(el('span','以左侧为基准，查看右侧版本的方块变化。'),compare)
  }
  footer.hidden=!pairAction
  if(!dialog.open)dialog.showModal()
 }
 dialog.addEventListener('close',()=>{revision++;if(!tray.hidden&&tray.offsetWidth)review.focus({preventScroll:true})})
 setMode(false)
 return {decorate,reconcile,reset(){setMode(false);if(dialog.open)dialog.close()}}
}
