import './reference-picker.css'
const node=(tag,text)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;return e}

export function initReferencePicker({api}){
 const chosen=new Map(),dialog=node('dialog');dialog.id='reference-picker'
 dialog.innerHTML='<header><div><h2>检索本地参考</h2><p>勾选后才用于本工作流下一次 AI 请求；本地检索不联网。</p></div><button id="reference-close" type="button">关闭</button></header><form id="reference-search-form"><input id="reference-query" aria-label="检索要求" maxlength="12000" placeholder="例如：水渠桥、承托、墙面收口"><button id="reference-search" type="submit">检索</button></form><p id="reference-status" role="status"></p><div id="reference-results"></div><details id="reference-document" hidden><summary>资料原文与位置</summary><pre id="reference-document-text"></pre></details><footer><span id="reference-count">尚未选择</span><button id="reference-clear" type="button">恢复工作流原配置</button><button id="reference-use" type="button" class="primary" disabled>使用勾选参考</button></footer>'
 document.body.append(dialog);const $=id=>dialog.querySelector('#'+id)
 const savedButton=node('button','已收藏网页');savedButton.id='reference-saved';savedButton.type='button';$('reference-search-form').append(savedButton)
 const libraries=node('details'),libraryList=node('div'),libraryActions=node('div'),addLibrary=node('button','连接书库…')
 libraries.id='reference-libraries';libraryList.id='reference-library-list';addLibrary.id='reference-library-add';addLibrary.type='button'
 libraries.append(node('summary','本地书库'),libraryActions,libraryList);libraryActions.append(addLibrary);$('reference-search-form').after(libraries)
 const online=node('details');online.id='reference-online'
 online.innerHTML='<summary>联网补查</summary><form id="reference-online-form"><input id="reference-online-query" aria-label="公开搜索词或原页链接" maxlength="1600" placeholder="例如：圣礼拜堂 玫瑰窗，或公开 HTTPS 原页链接" required><button id="reference-online-submit" type="submit">查找原文</button><label><input id="reference-online-refresh" type="checkbox">重新读取</label></form>'
 libraries.after(online)
 addLibrary.hidden=!window.nbtDesktop?.chooseReferenceLibrary
 let context=null,found=null,webEvidence=[],savedView=false,savedOffset=null,epoch=0,busy=false
 const report=text=>$('reference-status').textContent=text
 function lock(value){busy=value;for(const id of ['reference-search','reference-query','reference-use','reference-clear','reference-library-add','reference-online-query','reference-online-submit','reference-online-refresh','reference-saved'])$(id).disabled=value;for(const button of libraryList.querySelectorAll('button'))button.disabled=value;if(!value)sync()}
 function sync(){
  const selected=new Set([...dialog.querySelectorAll('[data-reference-id]:checked')].map(entry=>entry.dataset.referenceId))
  const passages=(found?.knowledge??[]).filter(item=>selected.has(item.id))
  const long=passages.some(item=>item.reference_type==='architecture_library')&&passages.reduce((total,item)=>total+[...item.text].length,0)>6000
  $('reference-count').textContent=`${selected.size} 项 · 最多16项${long?' · 建议将资料缩减到 6,000 字以内':''}`
  $('reference-use').disabled=busy||selected.size<1||selected.size>16
 }
 const safe=action=>async event=>{event?.preventDefault();if(busy)return;const token=epoch;lock(true);try{await action(token)}catch(error){if(token===epoch)report(error.message)}finally{if(token===epoch)lock(false)}}
 async function loadLibraries(token){
  const {libraries:items}=await api('retrieve/library',{workflow:context.workflow,action:'list'});if(token!==epoch)return
  libraryList.replaceChildren()
  if(!items.length)libraryList.append(node('p','暂无书库。选择包含 books.json 或 knowledge.json 的目录。'))
  for(const item of items){
   const row=node('div');row.className='reference-library-row'
   row.append(node('strong',item.name),node('span',item.message??`${item.documents} 份资料 · ${item.enabled?'本流程已启用':'本流程已停用'}`))
   for(const [label,action,options] of [[item.enabled?'本流程停用':'本流程启用','enable',{enabled:!item.enabled}],['更新索引','build',{}]]){
    const control=node('button',label);control.type='button';control.onclick=safe(next=>changeLibrary(next,{action,id:item.id,...options}));row.append(control)
   }
   libraryList.append(row)
  }
 }
 async function changeLibrary(token,request){
  report(request.action==='enable'?'正在保存书库选择…':'正在离线建立书库索引…');await api('retrieve/library',{workflow:context.workflow,...request});if(token!==epoch)return
  await loadLibraries(token);if(token!==epoch)return
  if($('reference-query').value.trim())await search(token);else report('书库设置已更新，可以开始检索。')
 }
 libraries.ontoggle=()=>{if(libraries.open&&dialog.open&&!busy)safe(loadLibraries)()}
 addLibrary.onclick=safe(async token=>{const path=await window.nbtDesktop.chooseReferenceLibrary();if(path&&token===epoch)await changeLibrary(token,{action:'add',path})})
 const webKey=item=>JSON.stringify([item.locator,item.heading,item.passage_sha256])
 async function loadSaved(token,offset=0){
  const result=await api('retrieve/saved-web',{workflow:context.workflow,action:'list',offset});if(token!==epoch)return
  savedView=true;savedOffset=result.next_offset;webEvidence=offset?[...webEvidence,...result.knowledge]:result.knowledge;draw()
  const errors=[...new Set(result.errors.map(item=>item.message))].join('。')
  report((webEvidence.length?`已载入 ${webEvidence.length} 条网页收藏。`:'本工作流还没有网页收藏。')+errors)
 }
 savedButton.onclick=safe(token=>loadSaved(token))
 async function changeSaved(token,item,action){
  const result=await api('retrieve/saved-web',{workflow:context.workflow,action,id:item.id});if(token!==epoch)return
  const saved=result.saved
  webEvidence=webEvidence.map(other=>webKey(other)===webKey(item)?{...other,saved,saved_id:saved?item.id:undefined}:other)
  if(found)await search(token)
  if(token!==epoch)return
  if(savedView)await loadSaved(token)
  else draw()
  if(token===epoch)report(saved?'已收藏到本工作流，可离线检索。':'已从本地收藏移除。')
 }
 function draw(){
  const results=$('reference-results'),previous=new Set([...results.querySelectorAll('[data-reference-id]:checked')].map(element=>element.dataset.referenceId));results.replaceChildren()
  const groups=found?[['资产 · 可旋转、镜像和换材质；不缩放',found.assets],['资料 · 本工作流已启用的文档和书库',found.knowledge.filter(item=>item.reference_type!=='web')]]:[]
  const webMatches=found?.knowledge.filter(item=>item.reference_type==='web')??[]
  const webItems=[...new Map([...webMatches,...webEvidence].map(item=>[webKey(item),item])).values()]
  if(webItems.length)groups.push([savedView||!webEvidence.length?'已收藏网页':'网页证据',webItems])
  for(const [title,items]of groups){const section=node('section');section.append(node('h3',title));if(!items.length)section.append(node('p','没有匹配项。'))
   for(const item of items){const card=node('article'),label=node('label'),check=node('input');card.className='reference-card';check.type='checkbox';check.dataset.referenceId=item.id;check.checked=previous.has(item.id);check.onchange=sync;label.append(check,node('strong',item.label));card.append(label)
    if(item.thumbnail){const image=node('img');image.src=item.thumbnail;image.loading='lazy';image.alt=item.label+'几何示意';card.append(image)}
    const fromWeb=item.reference_type==='web',webInfo=item.bibliography
    const position=fromWeb?`${webInfo.publisher} · ${item.heading} · ${webInfo.accessed_at.slice(0,10)} · ${webInfo.verification==='app_opened'?'已读原页':'宿主记录'}${item.saved?' · 已收藏':''}`:item.heading+' · 第'+item.line_start+'～'+item.line_end+'行'+(item.clipped?'（长行已截取）':'')
    card.append(node('small',item.kind==='asset'?item.size.join(' × ')+' · '+item.reason:position),node('p',item.kind==='asset'?'标签：'+item.tags.join('、'):item.text));const path=node('small',item.locator+' · SHA256 '+(item.sha256??item.content_sha256));path.className='reference-path';card.append(path)
    if(item.kind==='knowledge'){
     const fromLibrary=item.reference_type==='architecture_library',view=node('button',fromWeb?'查看证据出处':fromLibrary?'查看原文位置':'查看完整原文');view.type='button'
     view.onclick=safe(async token=>{
      const request={workflow:context.workflow,document_id:item.document_id,sha256:item.sha256}
      if(fromLibrary)Object.assign(request,{manifest_sha256:item.manifest_sha256,line:item.line_start})
      const document=await api('retrieve/source',request);if(token!==epoch)return
      const details=[document.locator,document.bibliography?.author,document.bibliography?.edition,fromLibrary&&document.bibliography?.source_url,fromWeb&&document.heading,fromWeb&&document.bibliography?.publisher,
       document.line_start&&`原文第 ${document.line_start}～${document.line_end} 行${document.clipped?'（已截取）':''}`,'SHA256 '+document.sha256]
      $('reference-document').hidden=false;$('reference-document').open=true;$('reference-document-text').textContent=details.filter(Boolean).join('\n')+'\n\n'+document.text
     });card.append(view)
    }
    if(fromWeb){
     const updated=item.saved&&item.saved_id&&item.saved_id!==item.id
     const bookmark=node('button',updated?'更新收藏':item.saved?'取消收藏':'收藏到本地');bookmark.type='button';bookmark.dataset.webFavorite=''
     bookmark.onclick=safe(token=>changeSaved(token,item,item.saved&&!updated?'remove':'add'));card.append(bookmark)
    }
    section.append(card)
   }results.append(section)
  }
  if(savedView&&savedOffset!==null){const more=node('button','更多收藏');more.type='button';more.onclick=safe(token=>loadSaved(token,savedOffset));results.append(more)}
  sync()
 }
 async function search(token){
  const request={...context,query:$('reference-query').value.trim()};report('正在本地检索资产和资料…')
  const result=await api('retrieve/search',request);if(token!==epoch)return
  context=request;found=result;draw()
  const unavailable=[...(result.library_errors??[]).map(item=>`${item.name}：${item.message}`),...(result.saved_web_errors??[]).map(item=>item.message)].join('。')
  report(`${result.assets.length} 个资产、${result.knowledge.length} 段资料。${unavailable}`)
 }
 $('reference-query').oninput=()=>{found=null;if(savedView){savedView=false;savedOffset=null;webEvidence=[]}draw();report('本地检索词已修改。')}
 $('reference-search-form').onsubmit=safe(search)
 $('reference-online-form').onsubmit=safe(async token=>{
  const text=$('reference-online-query').value.trim();if(!text)return
  const request={workflow:context.workflow,refresh:$('reference-online-refresh').checked,...(/^https?:\/\//i.test(text)?{urls:[text]}:{query:text})}
  report('正在读取公开来源…');const result=await api('retrieve/research',request);if(token!==epoch)return
  savedView=false;savedOffset=null;webEvidence=result.evidence;draw()
  const failures=[...new Set(result.failures.map(item=>item.message))].join('。')
  const summary=webEvidence.length?`取得 ${webEvidence.length} 条原文证据${result.metrics.cache_hit?'（缓存）':''}。`:'未取得可引用证据。'
  report(summary+failures)
 })
 $('reference-use').onclick=safe(async token=>{const selected=[...dialog.querySelectorAll('[data-reference-id]:checked')].map(e=>e.dataset.referenceId),request=selected.every(id=>id.startsWith('web:'))?{workflow:context.workflow,selected}:{...context,selected},result=await api('retrieve/bundle',request);if(token!==epoch)return;chosen.set(context.workflow,{id:result.id,sha256:result.sha256,sources:result.sources});window.dispatchEvent(new CustomEvent('nbt-reference-change',{detail:context.workflow}));dialog.close()})
 $('reference-clear').onclick=()=>{if(!context)return;chosen.delete(context.workflow);window.dispatchEvent(new CustomEvent('nbt-reference-change',{detail:context.workflow}));dialog.close()}
 $('reference-close').onclick=()=>dialog.close();dialog.addEventListener('close',()=>{epoch++;busy=false})
 async function open(input){if(dialog.open||busy)return;context={workflow:input.workflow,size:input.size??null,query:input.query?.trim()||''};found=null;webEvidence=[];savedView=false;savedOffset=null;libraries.open=false;online.open=false;libraryList.replaceChildren();$('reference-online-query').value='';$('reference-online-refresh').checked=false;$('reference-query').value=context.query;$('reference-results').replaceChildren();$('reference-document').hidden=true;$('reference-document-text').textContent='';report('按名称、构造或用途检索本工作流启用的资料。');dialog.showModal();epoch++;lock(false);if(context.query)await safe(search)()}
 function receipt(workflow){const value=chosen.get(workflow);return value?{id:value.id,sha256:value.sha256}:undefined}
 function sources(host,result){
  host.replaceChildren()
  for(const item of result?.reference_sources??[]){const line=node('p',`${item.citation} · ${item.label}${item.line_start?' · 第'+item.line_start+'～'+item.line_end+'行':''}`);line.title='SHA256 '+item.sha256;host.append(line)}
  if(host.childNodes.length)host.prepend(node('small',result?.reference_history?'此资产保存时记录的参考；不代表来源当前仍启用或内容未变化。':'本次提供的参考；资料是否被模型采纳需结合结果审阅。'))
  const delivery=result?.knowledge_delivery
  if(delivery?.mode==='explicit_collection'){
   host.append(node('small',`已发送显式集合的 ${delivery.selected} 项参考，替代 ${delivery.default_documents_replaced} 份默认资料。`))
  }else if(delivery?.documents?.length){
   const statuses={complete:'全文',excerpt:'片段',omitted:'预算内无可用片段'}
   for(const item of delivery.documents)host.append(node('p',`${item.label} · ${statuses[item.status]}`))
   if(delivery.duplicate_documents)host.append(node('small',`已合并 ${delivery.duplicate_documents} 份重复正文。`))
  }
 }
 const picker={open,receipt,sources,summary:workflow=>chosen.get(workflow)?.sources??[]};window.nbtReferencePicker=Object.freeze(picker);return picker
}
