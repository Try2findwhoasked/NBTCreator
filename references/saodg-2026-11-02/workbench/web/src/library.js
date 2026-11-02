
const $ = id => document.getElementById(id)
const embedded = new URLSearchParams(location.search).has('embedded') && parent !== window
const state = { models: [], favorites: [], selected: [], collection: 'all', shape: '', current: null, page: 0, busy: false }
const pageSize = 36, coverCache = new Map(), coverQueue = []
let coverWorkers = 0, observer, stateWrites = Promise.resolve(), saveCount = 0
const shapeNames = {single:'单格',long:'长条',square:'方形',l_shape:'L形',t_shape:'T形',cross:'十字形',standalone:'独立建筑',irregular:'不规则'}
const shapeOf = model => model.shape || 'unknown'
const shapeName = model => model.shape_zh || shapeNames[shapeOf(model)] || '未标注'
function el(tag, text, className) {
  const node = document.createElement(tag)
  if (text !== undefined) node.textContent = text
  if (className) node.className = className
  return node
}
async function api(route, data) {
  const response = await fetch('/api/library' + route, data ? {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)} : {})
  const result = await response.json()
  if (!response.ok) throw new Error(result.error || '读取失败')
  return result
}
function notice(text, error = false) { $('library-notice').textContent = text; if (error) $('save-status').textContent = '操作未完成' }
function handle(fn) { return async event => { try { await fn(event) } catch (error) { notice(error.message, true) } } }
function latest() {
  if ($('library-history').checked) return state.models
  const formal = new Set(state.models.filter(model => !model.intermediate).map(model => model.group)), groups = new Set()
  return state.models.filter(model => {
    if (model.intermediate && formal.has(model.group) || groups.has(model.group)) return false
    groups.add(model.group); return true
  })
}
function filtered() {
  const query = $('library-search').value.trim().toLocaleLowerCase()
  let models = latest().filter(model => (!state.shape || shapeOf(model) === state.shape) &&
    (state.collection === 'all' || state[state.collection].includes(model.source)) &&
    (!query || [model.label, model.name, model.description_zh, model.version, model.source, shapeName(model)].join(' ').toLocaleLowerCase().includes(query)))
  const sort = $('library-sort').value
  if (sort !== 'recent') models = [...models].sort((a,b) => (sort === 'shape' ? shapeName(a).localeCompare(shapeName(b),'zh-CN') : 0) || a.name.localeCompare(b.name,'zh-CN') || b.modified_ns-a.modified_ns)
  return models
}
function footprint(model) {
  const svg = document.createElementNS('http://www.w3.org/2000/svg','svg')
  svg.classList.add('footprint'); svg.setAttribute('viewBox','0 0 100 100'); svg.setAttribute('aria-hidden','true')
  const fallbacks = {single:[[0,0]],long:[[0,0],[1,0],[2,0]],square:[[0,0],[1,0],[0,1],[1,1]],l_shape:[[0,0],[0,1],[1,1]],t_shape:[[0,0],[1,0],[2,0],[1,1]],cross:[[1,0],[0,1],[1,1],[2,1],[1,2]]}
  const cells = Array.isArray(model.cells) && model.cells.length ? model.cells : fallbacks[shapeOf(model)] || [[0,0]]
  const valid = cells.filter(p => Array.isArray(p) && p.length===2 && p.every(Number.isFinite))
  if (!valid.length) return svg
  const minX=Math.min(...valid.map(p=>p[0])),minZ=Math.min(...valid.map(p=>p[1]))
  const width=Math.max(...valid.map(p=>p[0]))-minX+1,height=Math.max(...valid.map(p=>p[1]))-minZ+1,unit=78/Math.max(width,height)
  for (const [x,z] of valid) {
    const rect=document.createElementNS(svg.namespaceURI,'rect')
    for (const [key,value] of Object.entries({x:(100-width*unit)/2+(x-minX)*unit+2,y:(100-height*unit)/2+(z-minZ)*unit+2,width:unit-4,height:unit-4,rx:3,fill:'#7eaa82',stroke:'#c0dbb5','stroke-width':1.2})) rect.setAttribute(key,value)
    svg.append(rect)
  }
  return svg
}
function placeholder(model) {
  const node=el('div',undefined,'cover-placeholder');node.append(footprint(model),el('span','占地示意 · 暂无预览','placeholder-label'));return node
}
function cover(model) {
  if (!coverCache.has(model.id)) coverCache.set(model.id, new Promise((resolve,reject) => {coverQueue.push({model,resolve,reject});pumpCovers()}).catch(error=>{coverCache.delete(model.id);throw error}))
  return coverCache.get(model.id)
}
function pumpCovers() {
  while (coverWorkers<3 && coverQueue.length) {
    const {model,resolve,reject}=coverQueue.shift();coverWorkers++
    api('/cover/'+model.id).then(resolve,reject).finally(()=>{coverWorkers--;pumpCovers()})
  }
}
async function showCover(target, model, detail = false) {
  try {
    const data=await cover(model)
    if (!target.isConnected) return
    if (data.thumbnail) {const img=el('img');img.alt=model.label+' · 已保存预览';img.loading='lazy';img.decoding='async';img.src=data.thumbnail;target.replaceChildren(img)}
    if(detail && data.image && state.current?.id===model.id){const link=el('a','打开预览原图');link.href=data.image;link.target='_blank';link.rel='noopener';$('detail-actions')?.append(link)}
  } catch (error) {
    if(target.isConnected){target.title=error.message;const label=target.querySelector('.placeholder-label');if(label)label.textContent='封面未载入 · 可刷新重试'}
  }
}
function changeCollection(model, collection, enabled) {
  saveCount++;state.busy=true;$('save-status').textContent='正在保存清单…'
  const operation=stateWrites.then(async()=>{
    const saved=await api('/state',{id:model?.id,collection,enabled,clear:!model});state.favorites=saved.favorites;state.selected=saved.selected;render()
  }).finally(()=>{saveCount--;state.busy=saveCount>0;if(!state.busy)$('save-status').textContent='清单已保存'})
  stateWrites=operation.catch(()=>{})
  return operation
}
function card(model) {
  const card=el('article',undefined,'structure-card'+(state.current?.id===model.id?' current':'')+(state.selected.includes(model.source)?' chosen':''));card.dataset.id=model.id
  const pick=el('label',undefined,'card-pick'),checkbox=el('input');checkbox.type='checkbox';checkbox.checked=state.selected.includes(model.source);checkbox.setAttribute('aria-label','加入清单：'+model.label);checkbox.addEventListener('change',handle(()=>changeCollection(model,'selected',checkbox.checked)));pick.append(checkbox)
  const star=el('button',state.favorites.includes(model.source)?'★':'☆','card-star');star.setAttribute('aria-label','收藏：'+model.label);star.setAttribute('aria-pressed',String(state.favorites.includes(model.source)));star.addEventListener('click',handle(()=>changeCollection(model,'favorites',!state.favorites.includes(model.source))))
  const image=el('button',undefined,'card-cover');image.setAttribute('aria-label','查看：'+model.label);image.append(placeholder(model));image.addEventListener('click',()=>select(model));observer.observe(image);image.dataset.id=model.id
  const text=el('button',undefined,'card-content');text.title=model.source;text.append(el('h3',model.name_zh||model.name))
  const meta=el('div',undefined,'card-meta');meta.append(el('span',shapeName(model),'shape-tag'),el('span',model.size?.join(' × ')||'尺寸未索引'));text.append(meta,el('div',model.version||'原稿','card-version'));text.addEventListener('click',()=>select(model))
  card.append(pick,star,image,text);return card
}
function render() {
  observer?.disconnect()
  observer=new IntersectionObserver(entries=>{for(const entry of entries)if(entry.isIntersecting){const model=state.models.find(model=>model.id===entry.target.dataset.id);if(model)showCover(entry.target,model);observer.unobserve(entry.target)}},{rootMargin:'100px'})
  const models=filtered(),pages=Math.max(1,Math.ceil(models.length/pageSize));state.page=Math.min(state.page,pages-1)
  $('structure-grid').replaceChildren(...models.slice(state.page*pageSize,(state.page+1)*pageSize).map(card))
  if(!models.length)$('structure-grid').append(el('div','没有匹配的结构。试试清除搜索、切换形状，或显示历史版本。','empty-results'))
  const available=state.models.filter(model=>state.selected.includes(model.source))
  $('selected-count').textContent=`已选 ${available.length} 项`;$('export-selection').disabled=!available.length;$('clear-selection').disabled=!state.selected.length
  const titles={all:'全部建筑',favorites:'我的收藏',selected:'已选清单'}
  $('collection-title').textContent=titles[state.collection]+(state.shape?' / '+(shapeNames[state.shape]||'未标注'):'')
  $('library-summary').textContent=`${models.length} 个${$('library-history').checked?'建筑版本':'建筑'} · ${state.models.length} 个有效版本已索引`
  $('page-count').textContent=`${state.page+1} / ${pages} 页`;$('previous-page').disabled=!state.page;$('next-page').disabled=state.page>=pages-1
  for(const button of $('collections').children){const key=button.dataset.collection;button.classList.toggle('active',key===state.collection);button.querySelector('span').textContent=key==='all'?latest().length:state.models.filter(model=>state[key].includes(model.source)).length}
  $('shapes').replaceChildren()
  for(const shape of ['',...new Set(state.models.map(shapeOf))]){
    const button=el('button',shape?(shapeNames[shape]||'未标注'):'全部形状');button.classList.toggle('active',state.shape===shape);button.append(el('span',latest().filter(model=>!shape||shapeOf(model)===shape).length));button.addEventListener('click',()=>{state.shape=shape;state.page=0;render()});$('shapes').append(button)
  }
  $('choose-structure').disabled=!state.current
  if(state.current)renderDetail()
}
function select(model){state.current=model;render();if(innerWidth<=800)$('structure-detail').scrollIntoView({behavior:'smooth',block:'start'})}
function renderDetail(){
  const model=state.current,detail=$('structure-detail'),image=el('div',undefined,'detail-cover');image.append(placeholder(model));detail.replaceChildren(image,el('span',shapeName(model),'shape-tag'),el('h2',model.name_zh||model.name,'detail-title'),el('p',model.description_zh||'该结构尚未填写中文说明。','detail-description'))
  const list=el('dl',undefined,'detail-list')
  for(const [label,value] of [['版本',model.version],['尺寸',model.size?.join(' × ')||'未索引'],['修改于',new Date(model.modified_ns/1e6).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false})],['几何哈希',model.geometry_sha256.slice(0,16)+'…']])list.append(el('dt',label),el('dd',value))
  detail.append(list,el('p',model.source,'detail-path'))
  const actions=el('div',undefined,'detail-actions');actions.id='detail-actions'
  const copy=el('button','复制文件路径');copy.addEventListener('click',handle(async()=>{await navigator.clipboard.writeText(model.source);notice('已复制完整模型路径。')}))
  const star=el('button',state.favorites.includes(model.source)?'★ 已收藏':'☆ 收藏');star.addEventListener('click',handle(()=>changeCollection(model,'favorites',!state.favorites.includes(model.source))))
  actions.append(copy,star);detail.append(actions,el('p','预览只使用与当前几何哈希一致的已保存图片。占地示意用于辨识形状；索引和收藏不代表密闭、通路、设计或游戏验收通过。','detail-scope'));showCover(image,model,true)
}
async function choose(){
  const model=state.current;if(!model)return
  const tab=window.open('about:blank','_blank')
  try{
    const response=await fetch('/api/editor/open',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({source:model.source})}),result=await response.json()
    if(!response.ok)throw new Error(result.error)
    if(tab)tab.location.href=result.url;else notice('细节控制台已启动，请允许浏览器打开新窗口后重试。')
  }catch(error){tab?.close();throw error}
}
async function load(refresh=false){
  $('refresh-library').disabled=true;notice('正在读取本地目录…')
  try{
    const data=await api(refresh?'?refresh=1':'');state.models=data.models;state.favorites=data.state.favorites;state.selected=data.state.selected
    if(refresh)coverCache.clear()
    if(state.current)state.current=state.models.find(model=>model.id===state.current.id)||null
    $('library-root').textContent=data.root;$('state-file').textContent='收藏 / 清单：'+data.state_file
    if(!state.current)$('structure-detail').replaceChildren(el('div','点击卡片查看结构详情。','detail-placeholder'))
    render()
    const missing=state.selected.filter(source=>!state.models.some(model=>model.source===source)).length
    notice(data.migration_in_progress?'建筑库正在迁移，完成后请刷新。':missing?`${missing} 项已选路径当前不可用；导出仅包含目录中现存的结构。`:data.models.length?'默认每座建筑只展示最新保存版本；可勾选历史版本查找旧稿。':'nbt_models 中没有可用的完整主模型。测试、缓存及 bugged 目录默认隐藏。')
  }finally{$('refresh-library').disabled=false}
}
for(const button of $('collections').children)button.addEventListener('click',()=>{state.collection=button.dataset.collection;state.page=0;render()})
for(const id of ['library-search','library-history','library-sort'])$(id).addEventListener(id==='library-search'?'input':'change',()=>{state.page=0;render()})
$('refresh-library').addEventListener('click',handle(()=>load(true)))
$('previous-page').addEventListener('click',()=>{state.page--;render();document.querySelector('.library-main').scrollTo(0,0)})
$('next-page').addEventListener('click',()=>{state.page++;render();document.querySelector('.library-main').scrollTo(0,0)})
$('clear-selection').addEventListener('click',handle(()=>changeCollection(null,'selected',false)))
$('choose-structure').addEventListener('click',handle(choose))
$('close-picker').hidden=!embedded;$('close-picker').addEventListener('click',()=>parent.postMessage({type:'nbt-library-close'},location.origin))
$('export-selection').addEventListener('click',()=>{
  if(state.busy){notice('清单正在保存，请稍后导出。');return}
  const models=state.models.filter(model=>state.selected.includes(model.source)).map(({id,label,name_zh,shape,version,source,geometry_sha256,context,cameras})=>({id,label,name_zh,shape,version,source,geometry_sha256,context,cameras}))
  const value={schema_version:1,kind:'nbt_structure_selection',created_at:new Date().toISOString(),note:'本地结构选择清单，不是精修批准或运行验收。',models}
  const url=URL.createObjectURL(new Blob([JSON.stringify(value,null,2)+'\n'],{type:'application/json'})),a=el('a');a.href=url;a.download='结构选择清单_'+new Date().toISOString().replace(/[:.]/g,'-')+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);notice(`已导出 ${models.length} 项结构路径与几何哈希。`)
})
window.structureLibrary={state,filtered,load}
load().catch(error=>notice(error.message,true))
