import {requestAI,previewAI,cancelAI} from './ai-request.js'

export function initComponentAuthor({actions,api,created}){
 const open=document.createElement('button');open.id='asset-create-agent';open.type='button';open.textContent='让 Agent 生成资产';actions.append(open)
 const dialog=document.createElement('dialog');dialog.id='component-author';dialog.className='component-author'
 dialog.innerHTML=`<header><div><h2 id="component-title">生成资产</h2><p>内置 AI 与外部 Agent 共用构件规范</p></div><button id="component-close" class="quiet" type="button">关闭</button></header>
 <div class="component-author-body"><section class="component-author-form" aria-label="结构创作参数">
 <label>结构名称<input id="component-name" maxlength="80" value="独立石构件"></label>
 <div class="component-size-field"><span>尺寸 · 每轴 1～64 格</span><div class="component-size-vector">${['x','y','z'].map((axis,i)=>`<label>${axis.toUpperCase()}<input id="component-size-${axis}" type="number" min="1" max="64" step="1" value="${[7,8,7][i]}" aria-label="独立结构尺寸${axis.toUpperCase()}"></label>`).join('')}</div></div>
 <label>参考资产<select id="component-reference"><option value="">不引用已有资产</option></select></label>
 <label>创作要求<textarea id="component-instruction" rows="5" maxlength="12000" placeholder="描述构件的用途、形状、材质和细节，例如带基座与柱帽的石砖柱。"></textarea></label>
 <div class="component-author-actions"><button id="component-generate" type="button">生成预览</button><button id="component-generate-save" class="primary" type="button">生成并入库</button><button id="component-copy-agent" type="button">复制给外部 Agent</button></div>
 <details id="component-advanced"><summary>高级 · 结构参数</summary><label>可粘贴外部 Agent 的 JSON 方案<textarea id="component-spec" rows="8" spellcheck="false"></textarea></label><button id="component-preview" type="button">校验参数并预览</button></details>
 </section><section class="component-author-preview" aria-label="结构预览">
 <div class="component-preview-heading"><strong id="component-preview-name">结构预览</strong><span>材质 3D</span></div>
 <div id="component-preview-empty"><strong>预览独立构件</strong><span>生成方案或载入参数后，在这里查看效果</span></div>
 <div id="component-preview-area" hidden><iframe id="component-viewer" title="独立结构材质3D预览"></iframe><details><summary>缩略图与检查记录</summary><img id="component-thumbnail" alt="独立结构几何缩略图"><pre id="component-view-info"></pre></details></div>
 <p id="component-status" role="status"></p></section></div>
 <footer><span id="component-footer-hint">查看预览后保存到构件库，可在建筑中放置复用。</span><button id="component-write" class="primary" type="button" disabled>保存新资产</button></footer>`
 document.body.append(dialog)
 const $=id=>dialog.querySelector('#'+id),call=(tool,arguments_)=>api('components/agent',{tool,arguments:arguments_})
 const references=document.createElement('button');references.id='component-references';references.type='button';references.textContent='检索并选择参考';$('component-generate').after(references);const referenceSources=document.createElement('div');referenceSources.id='component-reference-sources';referenceSources.className='ai-reference-sources';$('component-status').before(referenceSources);references.onclick=()=>{try{window.nbtReferencePicker.open({workflow:'component',query:$('component-instruction').value,size:context().size}).catch(error=>status(error.message,true))}catch(error){status(error.message,true)}};window.addEventListener('nbt-reference-change',event=>{if(event.detail==='component'){invalidate();const selected=window.nbtReferencePicker?.summary('component')??[];references.textContent='检索并选择参考'+(selected.length?'（'+selected.length+'）':'');references.title=selected.map(item=>item.label).join('、')}})
 let candidate=null,binding=null,epoch=0,phase=null
 const status=(message,error=false)=>{$('component-status').textContent=message;$('component-status').classList.toggle('error',error)}
 const fingerprint=()=>JSON.stringify(['component-name','component-size-x','component-size-y','component-size-z','component-reference','component-instruction','component-spec'].map(id=>$(id).value).concat(window.nbtReferencePicker?.receipt('component')??null))
 function invalidate(){candidate=null;binding=null;$('component-write').disabled=true}
 function lock(value,kind=null){phase=value?kind:null;for(const id of ['component-generate','component-generate-save','component-copy-agent','component-preview','component-name','component-size-x','component-size-y','component-size-z','component-reference','component-instruction','component-spec','component-references'])$(id).disabled=value;$('component-close').disabled=value&&kind==='write';$('component-write').disabled=value||!candidate||binding!==fingerprint()||dialog.dataset.mode==='view'}
 function context(){const name=$('component-name').value.trim(),size=['x','y','z'].map(axis=>Number($('component-size-'+axis).value));if(!name||name.length>80||!size.every(n=>Number.isInteger(n)&&n>=1&&n<=64))throw Error('请填写名称和1～64格的整数尺寸');return {name,size,references:[]}}
 async function show(result,token){
  if(token!==epoch||!dialog.open)return
  candidate=null;binding=null
  $('component-preview-area').hidden=false;$('component-preview-empty').hidden=true;$('component-thumbnail').src=result.thumbnail;$('component-preview-name').textContent=result.name+' · '+result.size.join(' × ')+' · '+result.block_count+' 格'
  window.nbtReferencePicker?.sources(referenceSources,result)
  $('component-view-info').textContent=JSON.stringify({name:result.name,size:result.size,content_sha256:result.content_sha256,camera:result.cameras[0],verification:result.verification},null,2)
  const frame=$('component-viewer')
  await new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(Error('独立结构3D预览加载超时')),60000);frame.onload=()=>Promise.resolve(frame.contentWindow?.nbtModeler?.ready).then(()=>{clearTimeout(timer);resolve()},error=>{clearTimeout(timer);reject(error)});frame.src='/index.html?embedded=1&quality=balanced&model_key='+encodeURIComponent(result.model_key)})
  if(token!==epoch||!dialog.open)return
  const viewer=frame.contentWindow?.nbtModeler;if(viewer?.status!=='ready')throw Error('独立结构3D未能加载')
  await viewer.setCamera(result.cameras[0])
 }
 async function preview(spec,token){
  invalidate();status('正在通过共用引擎检查并生成独立结构…')
  const result=await call('structure_preview',{spec,...(window.nbtReferencePicker?.receipt('component')?{reference_bundle:window.nbtReferencePicker.receipt('component')}:{})});await show(result,token)
  if(token!==epoch||!dialog.open)return
  $('component-name').value=result.name;for(const [i,axis]of ['x','y','z'].entries())$('component-size-'+axis).value=result.size[i]
  candidate=result;binding=fingerprint();status(`“${result.name}”已生成真实候选预览，共 ${result.block_count} 格；查看后可保存新资产`)
 }
 const safe=action=>async()=>{if(phase)return;const token=++epoch;try{lock(true,'preview');await action(token)}catch(error){if(token===epoch)status(error.message,true)}finally{if(token===epoch)lock(false);else if(!dialog.open)phase=null}}
 open.onclick=async()=>{
  if(dialog.open)return;const token=++epoch;invalidate();status('');dialog.dataset.mode='create';$('component-title').textContent='生成资产';$('component-footer-hint').textContent='查看预览后保存到构件库，可在建筑中放置复用。';dialog.showModal();lock(true,'load')
  try{const result=await call('structure_list',{});if(token!==epoch||!dialog.open)return;$('component-reference').replaceChildren(new Option('不引用已有资产',''),...result.items.filter(item=>!item.archived).map(item=>new Option(item.name+' · '+item.size.join('×'),item.id)))}catch(error){if(token===epoch)status(error.message,true)}finally{if(token===epoch)lock(false);else if(!dialog.open)phase=null}
 }
 for(const element of dialog.querySelectorAll('input,textarea,select'))element.addEventListener('input',invalidate)
 $('component-reference').addEventListener('change',invalidate)
 $('component-close').onclick=()=>dialog.close();dialog.addEventListener('cancel',event=>{if(phase==='write')event.preventDefault()})
 dialog.addEventListener('close',()=>{epoch++;if(phase==='ai')cancelAI('component');invalidate();$('component-viewer').src='about:blank';$('component-preview-area').hidden=true;$('component-preview-empty').hidden=false;$('component-preview-name').textContent='结构预览'})
 $('component-preview').onclick=safe(async token=>{const spec=JSON.parse($('component-spec').value);await preview(spec,token)})
 $('component-generate-save').onclick=()=>generate(true)
 $('component-generate').onclick=()=>generate(false)
 async function generate(saveAfter=false){
  if(phase)return;const token=++epoch
  try{
   if(!window.nbtDesktop?.apiGenerate)throw Error('内置 AI 生成需要Electron桌面版；仍可粘贴外部Agent参数并预览')
   const c=context(),instruction=$('component-instruction').value.trim();if(!instruction)throw Error('请填写结构创作要求')
   invalidate();lock(true,'ai');status('正在生成独立结构方案…')
   if($('component-reference').value)c.references=[await call('structure_read',{id:$('component-reference').value})]
   if(token!==epoch||!dialog.open)return
   const result=await requestAI({mode:'component',instruction,context:c},()=>{const viewer=$('component-viewer').contentWindow?.nbtModeler;if(viewer?.status!=='ready')throw Error('尚无独立结构视口；请先关闭本工作流截图开关或生成一次参数预览');return viewer.captureCurrent()})
   if(token!==epoch||!dialog.open)return
   window.nbtReferencePicker?.sources(referenceSources,result);$('component-spec').value=JSON.stringify(result.spec,null,2);phase='preview'
   await previewAI(result,()=>preview(result.spec,token))
   if(saveAfter&&token===epoch&&dialog.open){lock(true,'write');const item=await call('structure_save',{preview_id:candidate.preview_id,preview_sha256:candidate.preview_sha256});dialog.close();await created(item)}
  }catch(error){if(token===epoch)status(error.message,true)}finally{if(token===epoch)lock(false);else if(!dialog.open)phase=null}
 }
 $('component-write').onclick=async()=>{
  if(phase)return
  try{if(!candidate||binding!==fingerprint())throw Error('参数已变化，请重新预览');lock(true,'write');const item=await call('structure_save',{preview_id:candidate.preview_id,preview_sha256:candidate.preview_sha256});dialog.close();await created(item)}catch(error){status(error.message,true)}finally{lock(false)}
 }
 $('component-copy-agent').onclick=()=>{
  try{const c=context(),text=`请在当前Agent项目中读取 .agents/skills/nbtcreator-workspace/SKILL.md 和构件资产规范，使用共用 structure_* 工具生成资产。\n名称：${c.name}\n尺寸：${c.size.join(',')}\n要求：${$('component-instruction').value}\n参考资产编号：${$('component-reference').value||'未指定'}\n先调用 capabilities 查看 agent_tools。入口：python .agents/skills/nbtcreator-workspace/nbt.py components agent --tool <工具名> --request <参数JSON>。如已选本地参考集合，先 retrieve read 核对集合及出处，结构预览时传入 reference_bundle；集合：${JSON.stringify(window.nbtReferencePicker?.receipt('component')??null)}。可直接用 structure_save({spec}) 保存生成资产并生成批次清单，或用 asset-batches save 批量保存，资产标记为待审阅。也可先 structure_list/read；用 structure_preview 生成真实候选和图片，实际查看后再按授权 structure_write 保存新资产。structure_place 只返回参数化候选，按保护/预算、preview/validate 和显式新版本导出流程应用。不要生成代码、伪造看图批准或覆盖源。创作偏好使用 ai-style prompt --workflow component。`;if(window.nbtDesktop?.copyAgentPlan)window.nbtDesktop.copyAgentPlan(text).then(()=>status('外部 Agent 任务已复制')).catch(error=>status(error.message,true));else navigator.clipboard.writeText(text).then(()=>status('外部 Agent 任务已复制'))}catch(error){status(error.message,true)}
 }
 return {open:()=>open.click(),view:async id=>{
  if(phase)throw Error('请等待当前结构任务完成')
  const token=++epoch;invalidate();dialog.dataset.mode='view';$('component-title').textContent='结构预览';$('component-footer-hint').textContent='只读查看构件，不改变当前建筑。';if(!dialog.open)dialog.showModal();lock(true,'preview');status('正在读取独立结构…')
  try{const result=await call('structure_view',{id});await show(result,token);if(token!==epoch||!dialog.open)return;$('component-name').value=result.name;for(const [i,axis]of ['x','y','z'].entries())$('component-size-'+axis).value=result.size[i];$('component-spec').value='';$('component-reference').replaceChildren(new Option('不引用已有资产',''),new Option(result.name,id));$('component-reference').value=id;status('已打开独立结构的只读3D视图；不会修改当前建筑')}catch(error){if(token===epoch)status(error.message,true);throw error}finally{if(token===epoch)lock(false);else if(!dialog.open)phase=null}
 }}
}
