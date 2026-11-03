import {floatingDetails,chevron} from './floating-panel.js'
export function checkboxFilter({host,id,label,options,defaults,onChange}){
 const root=document.createElement('details');root.className='project-checkbox-filter';root.id=id
 const summary=document.createElement('summary'),name=document.createElement('span'),selectedText=document.createElement('strong'),value=document.createElement('span'),arrow=document.createElement('i');arrow.className='filter-chevron';arrow.innerHTML=chevron;name.textContent=label;selectedText.append(value,arrow);summary.append(name,selectedText)
 const panel=document.createElement('div');panel.className='project-filter-options';panel.setAttribute('role','group');panel.setAttribute('aria-label',label)
 root.append(summary,panel);host.append(root)
 let choices=[],selected=new Set(defaults),initial=true
 function render(){
  const focused=root.contains(document.activeElement)&&document.activeElement.tagName==='INPUT'?{value:document.activeElement.value,all:!!document.activeElement.dataset.filterAll}:null
  panel.replaceChildren()
  const all=document.createElement('label'),toggle=document.createElement('input');toggle.type='checkbox';toggle.value='all';toggle.dataset.filterAll='1';toggle.checked=selected.size===choices.length&&choices.length>0;toggle.indeterminate=selected.size>0&&selected.size<choices.length;toggle.setAttribute('aria-label',label+'：全部');all.append(toggle,document.createTextNode('全部'));panel.append(all)
  toggle.onchange=()=>{selected=new Set(toggle.checked?choices.map(([key])=>key):[]);render();onChange()}
  for(const [key,text]of choices){const row=document.createElement('label'),input=document.createElement('input');input.type='checkbox';input.value=key;input.checked=selected.has(key);input.setAttribute('aria-label',label+'：'+text);input.onchange=()=>{if(input.checked)selected.add(key);else selected.delete(key);render();onChange()};row.append(input,document.createTextNode(text));panel.append(row)}
  const names=choices.filter(([key])=>selected.has(key)).map(([,text])=>text);value.textContent=names.length===choices.length?'全部':names.length===0?'未选择':names.length===1?names[0]:names.length+' 项';summary.title=names.join('、')||'没有选中条件'
  if(focused)[...panel.querySelectorAll('input')].find(input=>input.value===focused.value&&!!input.dataset.filterAll===focused.all)?.focus({preventScroll:true})
 }
 function setOptions(next){const wasAll=choices.length>0&&selected.size===choices.length;choices=next;selected=new Set((initial&&defaults.includes('all')||wasAll)?choices.map(([key])=>key):[...selected].filter(key=>choices.some(([value])=>value===key)));if(choices.length)initial=false;render()}
 setOptions(options)
 floatingDetails(root,panel)
 return {get:()=>[...selected],set(keys){selected=new Set(keys.includes('all')?choices.map(([key])=>key):keys);render()},options:setOptions,reset(){selected=new Set(defaults.includes('all')?choices.map(([key])=>key):defaults);render()}}
}
