import './reference-picker.css'
const node=(tag,text)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;return e}

export function initReferencePicker({api}){
 const chosen=new Map(),dialog=node('dialog');dialog.id='reference-picker'
 dialog.innerHTML='<header><div><h2>检索本地参考</h2><p>勾选后才用于本工作流下一次 AI 请求；本地检索不联网。</p></div><button id="reference-close" type="button">关闭</button></header><form id="reference-search-form"><input id="reference-query" aria-label="检索要求" maxlength="12000" placeholder="例如：水渠桥、承托、墙面收口"><button id="reference-search" type="submit">检索</button></form><p id="reference-status" role="status"></p><div id="reference-results"></div><details id="reference-document" hidden><summary>资料原文与位置</summary><pre id="reference-document-text"></pre></details><footer><span id="reference-count">尚未选择</span><button id="reference-clear" type="button">恢复工作流原配置</button><button id="reference-use" type="button" class="primary" disabled>使用勾选参考</button></footer>'
 document.body.append(dialog);const $=id=>dialog.querySelector('#'+id)
 let context=null,found=null,epoch=0,busy=false
 const report=text=>$('reference-status').textContent=text
 function lock(value){busy=value;for(const id of ['reference-search','reference-query','reference-use','reference-clear'])$(id).disabled=value;if(!value)sync()}
 function sync(){const count=dialog.querySelectorAll('[data-reference-id]:checked').length;$('reference-count').textContent=count+' 项 · 最多16项';$('reference-use').disabled=busy||count<1||count>16}
 const safe=action=>async event=>{event?.preventDefault();if(busy)return;const token=epoch;lock(true);try{await action(token)}catch(error){if(token===epoch)report(error.message)}finally{if(token===epoch)lock(false)}}
 function draw(){
  const results=$('reference-results');results.replaceChildren()
  const groups=[['资产 · 可旋转、镜像和换材质；不缩放',found.assets],['资料 · 仅检索本工作流已启用的文档',found.knowledge]]
  for(const [title,items]of groups){const section=node('section');section.append(node('h3',title));if(!items.length)section.append(node('p','没有匹配项。资料需要先在 AI 助手中为此工作流勾选。'))
   for(const item of items){const card=node('article'),label=node('label'),check=node('input');card.className='reference-card';check.type='checkbox';check.dataset.referenceId=item.id;check.onchange=sync;label.append(check,node('strong',item.label));card.append(label)
    if(item.thumbnail){const image=node('img');image.src=item.thumbnail;image.loading='lazy';image.alt=item.label+'几何示意';card.append(image)}
    card.append(node('small',item.kind==='asset'?item.size.join(' × ')+' · '+item.reason:item.heading+' · 第'+item.line_start+'～'+item.line_end+'行'+(item.clipped?'（长行已截取）':'')),node('p',item.kind==='asset'?'标签：'+item.tags.join('、'):item.text));const path=node('small',item.locator+' · SHA256 '+(item.sha256??item.content_sha256));path.className='reference-path';card.append(path)
    if(item.kind==='knowledge'){const view=node('button','查看完整原文');view.type='button';view.onclick=safe(async token=>{const document=await api('retrieve/source',{workflow:context.workflow,document_id:item.document_id,sha256:item.sha256});if(token!==epoch)return;$('reference-document').hidden=false;$('reference-document').open=true;$('reference-document-text').textContent=document.locator+'\nSHA256 '+document.sha256+'\n\n'+document.text});card.append(view)}
    section.append(card)
   }results.append(section)
  }sync()
 }
 async function search(token){const request={...context,query:$('reference-query').value.trim()};report('正在本地检索名称、标签、尺寸与资料片段…');const result=await api('retrieve/search',request);if(token!==epoch)return;context=request;found=result;draw();report(result.assets.length+' 个资产、'+result.knowledge.length+' 段资料；仅为匹配建议，不表示已验证适用。')}
 $('reference-query').oninput=()=>{found=null;$('reference-results').replaceChildren();sync();report('要求已修改，请重新检索。')}
 $('reference-search-form').onsubmit=safe(search)
 $('reference-use').onclick=safe(async token=>{if(!found)throw Error('先检索本地参考');const selected=[...dialog.querySelectorAll('[data-reference-id]:checked')].map(e=>e.dataset.referenceId),result=await api('retrieve/bundle',{...context,selected});if(token!==epoch)return;chosen.set(context.workflow,{id:result.id,sha256:result.sha256,sources:result.sources});window.dispatchEvent(new CustomEvent('nbt-reference-change',{detail:context.workflow}));dialog.close()})
 $('reference-clear').onclick=()=>{if(!context)return;chosen.delete(context.workflow);window.dispatchEvent(new CustomEvent('nbt-reference-change',{detail:context.workflow}));dialog.close()}
 $('reference-close').onclick=()=>dialog.close();dialog.addEventListener('close',()=>{epoch++;busy=false})
 async function open(input){if(dialog.open||busy)return;context={workflow:input.workflow,size:input.size??null,query:input.query?.trim()||''};found=null;$('reference-query').value=context.query;$('reference-results').replaceChildren();$('reference-document').hidden=true;$('reference-document-text').textContent='';report(context.workflow==='component'?'参考资产会绑定实际内容哈希，预览时再核验。':'此工作流检索已选资料片段；直接复用资产请使用资产管理的独立结构创作。');dialog.showModal();epoch++;lock(false);if(context.query)await safe(search)()}
 function receipt(workflow){const value=chosen.get(workflow);return value?{id:value.id,sha256:value.sha256}:undefined}
 function sources(host,result){host.replaceChildren();for(const item of result?.reference_sources??[]){const line=node('p',`${item.citation} · ${item.label}${item.line_start?' · 第'+item.line_start+'～'+item.line_end+'行':''}`);line.title='SHA256 '+item.sha256;host.append(line)}if(host.childNodes.length)host.prepend(node('small',result?.reference_history?'此资产保存时记录的参考；不代表来源当前仍启用或内容未变化。':'本次提供的参考；资料是否被模型采纳需结合结果审阅。'))}
 const picker={open,receipt,sources,summary:workflow=>chosen.get(workflow)?.sources??[]};window.nbtReferencePicker=Object.freeze(picker);return picker
}
