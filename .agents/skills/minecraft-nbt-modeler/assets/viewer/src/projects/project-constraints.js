import './project-constraints.css'
import '../../../../prompt-console/catalog.js'
import '../../../../prompt-console/constraint-contract.cjs'

const element=(tag,text)=>{const node=document.createElement(tag);if(text!==undefined)node.textContent=text;return node}
export function initProjectConstraints({api,container,getFolders,getFolder,onFolderChange}){
 const openButton=element('button','共用约束');openButton.id='open-project-constraints';openButton.type='button';container.insertBefore(openButton,container.lastChild)
 const dialog=element('dialog');dialog.id='project-constraints-dialog';dialog.className='project-constraints-dialog'
 dialog.setAttribute('aria-labelledby','constraint-title')
 dialog.innerHTML=`<header><div><h2 id="constraint-title">文件夹约束</h2><label>约束所在文件夹<select id="constraint-folder"></select></label><p id="constraint-file"></p></div><button id="constraint-close" type="button">关闭</button></header>
 <section class="constraint-body"><aside><button id="constraint-new" type="button">新建约束</button><div id="constraint-library"></div></aside><div class="constraint-editor">
 <label>名称<input id="constraint-name" maxlength="80" placeholder="如 1×1 房间、L 形院落"></label>
 <label>从模板起步<select id="constraint-template"><option value="">自定义</option></select></label>
 <div class="constraint-fields"><label>整体尺寸（X × Y × Z，可留空）<input id="constraint-size" placeholder="96 × 28 × 96"></label><label>尺寸要求<select id="constraint-size-policy"><option value="fixed">固定尺寸</option><option value="reference">参考尺寸</option></select></label><label>归档形状<select id="constraint-shape"><option value="">由实际模型决定</option></select></label><label>网格边长（可留空）<input id="constraint-cell-size" type="number" min="1" max="512"></label></div>
 <label>可建的网格坐标（每行 X,Z，从 0 开始）<textarea id="constraint-cells" rows="3" placeholder="0,0&#10;0,1&#10;1,1"></textarea></label>
 <div class="constraint-fields">
 <label>接入扩展<select id="constraint-integration"><option value="">未限定</option><option value="standalone">独立建筑</option><option value="saodg">SAODG 房间接入</option></select></label>
 <label>密闭检查<select id="constraint-enclosure"><option value="">未限定</option><option value="true">要求密闭</option><option value="false">不要求密闭</option></select></label>
 <label>通行洞口<select id="constraint-openings-policy"><option value="">未限定</option><option value="optional">按设计决定</option><option value="required">至少一个</option><option value="none">不设置</option></select></label>
 <label>洞口净宽 × 净高（格）<input id="constraint-opening-size" placeholder="可留空，如 3 × 4"></label>
 </div>
 <label>占地要求<textarea id="constraint-footprint" rows="2" maxlength="4000" placeholder="如缺角留作庭院，不放方块"></textarea></label><label>通行、净高等要求<textarea id="constraint-requirements" rows="3" maxlength="4000" placeholder="如主入口净宽至少 3 格"></textarea></label>
 <details id="constraint-agent"><summary>让 Agent 填写约束</summary><label>要限制什么<textarea id="constraint-agent-instruction" rows="3" maxlength="4000" placeholder="如 L 形院落每格边长 32 方块，高 24 方块，缺角留空"></textarea></label><button id="constraint-agent-generate" type="button">生成草稿</button></details>
 </div></section><footer><div><button id="constraint-save" type="button" class="primary">保存约束</button><button id="constraint-delete" type="button">移除约束</button></div><p id="constraint-status" role="status"></p></footer>`
 document.body.append(dialog)
 const $=id=>dialog.querySelector('#constraint-'+id)
 let library={revision:0,items:[]},editing=null,pending=false,actor='human',folder='',loaded=false
 const say=text=>{$('status').textContent=text}
 const request=()=>folder?{folder}:{}
 const folderLabel=()=>getFolders().find(item=>item.folder===folder)?.label??(folder||'工作区共用')
 const catalog=()=>document.getElementById('prompt-frame')?.contentWindow?.NbtToolCatalog??window.NbtToolCatalog
 let presets=new Map()
 async function templates(){
  if(presets.size)return
  const {groups}=await api('architect/constraints-registry',{folders:[]})
  presets=new Map(groups.find(group=>group.source==='builtin').items.map(item=>[item.id,item]))
  for(const [key,shape]of Object.entries(catalog().building_shapes))$('shape').add(new Option(shape.label,key))
  for(const preset of presets.values())$('template').add(new Option(preset.name,preset.id))
 }
 function fill(item=null){
  editing=item?.id?item:null;actor='human';const rules=item?.rules??{}
  $('name').value=item?.name??'';$('template').value='';$('size').value=rules.size?.join(' × ')??'';$('size-policy').value=rules.size_policy??'fixed';$('shape').value=rules.buildingShape??(item?'':getFolders().find(entry=>entry.folder===folder)?.shape??'');$('cell-size').value=rules.cell_size??'';$('cells').value=rules.cells?.map(cell=>cell.join(',')).join('\n')??'';$('footprint').value=rules.footprint??'';$('requirements').value=rules.requirements??'';$('delete').disabled=!editing
  $('integration').value=rules.integration??''
  $('enclosure').value=String(rules.require_enclosure??'')
  $('openings-policy').value=rules.openings_policy??''
  $('opening-size').value=rules.opening_size?.join(' × ')??''
  for(const node of $('library').children)node.setAttribute('aria-pressed',String(node.dataset.constraintId===item?.id))
 }
 function render(){
  $('library').replaceChildren()
  for(const item of library.items){const button=element('button',item.name+' · 第 '+item.revision+' 版');button.type='button';button.dataset.constraintId=item.id;button.onclick=()=>{fill(item);say('保存后，已引用的方案仍使用第 '+item.revision+' 版。')};$('library').append(button)}
  if(!library.items.length)$('library').append(element('p','「'+folderLabel()+'」还没有约束。'))
 }
 function read(){
  const rules={}
  if($('shape').value)rules.buildingShape=$('shape').value
  if($('size').value.trim()){rules.size=$('size').value.trim().split(/[×xX,，\s]+/).map(Number);rules.size_policy=$('size-policy').value}
  if($('cell-size').value.trim())rules.cell_size=Number($('cell-size').value)
  if($('cells').value.trim())rules.cells=$('cells').value.trim().split(/\n/).map(line=>line.trim().split(/[,，\s]+/).map(Number))
  if($('integration').value)rules.integration=$('integration').value
  if($('enclosure').value)rules.require_enclosure=$('enclosure').value==='true'
  if($('openings-policy').value)rules.openings_policy=$('openings-policy').value
  if($('opening-size').value.trim())rules.opening_size=$('opening-size').value.trim().split(/[×xX,，\s]+/).map(Number)
  for(const key of ['footprint','requirements'])if($(key).value.trim())rules[key]=$(key).value.trim()
  return {name:$('name').value.trim(),rules}
 }
 async function perform(run){
  if(pending)return;pending=true;const controls=[...dialog.querySelectorAll('button,input,select,textarea')].map(node=>[node,node.disabled]);for(const [node]of controls)node.disabled=true
  try{await run()}catch(error){say(error.message)}finally{pending=false;for(const [node,disabled]of controls)if(node.isConnected)node.disabled=disabled;$('save').disabled=$('new').disabled=$('agent-generate').disabled=!loaded;$('delete').disabled=!loaded||!editing}
 }
 async function load(next,{create=false,agent=false}={}){
  folder=next;loaded=false;library={revision:0,items:[]};fill();$('library').replaceChildren()
  $('file').textContent=folder?folder+'/项目约束.json':'nbt_models/_workspaces/project_design/constraints.json'
  say('正在读取「'+folderLabel()+'」的约束…')
  library=await api('architect/constraints-list',request());loaded=true;render();fill(create?null:library.items[0]);$('agent').open=agent
  say('在创作方案里选「'+folderLabel()+'」，再勾选要写入提示词的约束。')
 }
 async function open({create=false,agent=false,folder:requested=getFolder()}={}){
  if(dialog.open)return
  const folders=getFolders(),choices=$('folder')
  choices.replaceChildren(new Option('工作区共用', ''),...folders.map(item=>new Option(item.label,item.folder)))
  if(requested&&!folders.some(item=>item.folder===requested))choices.add(new Option(requested,requested))
  choices.value=requested
  dialog.showModal();await perform(async()=>{await templates();await load(requested,{create,agent})})
  if(agent&&loaded){$('agent').scrollIntoView({block:'nearest'});$('agent-instruction').focus()}
 }
 $('folder').onchange=()=>perform(async()=>{const next=$('folder').value;await load(next);onFolderChange(next)})
 $('close').onclick=()=>{if(!pending)dialog.close()};dialog.addEventListener('cancel',event=>{if(pending)event.preventDefault()})
 $('new').onclick=()=>{fill();say('新约束将保存到「'+folderLabel()+'」。')}
 $('template').onchange=()=>{const preset=presets.get($('template').value);if(!preset)return;fill({name:preset.name,rules:preset.rules});$('template').value=preset.id;say('模板已填入，可以修改尺寸、网格及要求后保存。')}
 $('save').onclick=()=>perform(async()=>{library=await api('architect/constraints-save',{...request(),revision:library.revision,...(editing?.id?{id:editing.id}:{}),...read(),actor});render();fill(library.saved);say('已保存“'+library.saved.name+'”到「'+folderLabel()+'」，当前为第 '+library.saved.revision+' 版。');window.dispatchEvent(new CustomEvent('project-constraints-changed',{detail:folder}))})
 $('delete').onclick=()=>perform(async()=>{const name=editing.name;library=await api('architect/constraints-delete',{...request(),revision:library.revision,id:editing.id});render();fill();say('已从「'+folderLabel()+'」移除“'+name+'”。已引用的方案仍保留原版本。');window.dispatchEvent(new CustomEvent('project-constraints-changed',{detail:folder}))})
 $('agent-generate').onclick=()=>perform(async()=>{
  const instruction=$('agent-instruction').value.trim();if(!instruction)throw Error('请描述要创建的约束')
  if(!window.nbtPromptAI)throw Error('Agent 编写需要在应用中连接 AI')
  say('Agent 正在编写约束候选…')
  const result=await window.nbtPromptAI.generateWorkbench(instruction,{task:'constraint'},{scope:'project-constraint'})
  const candidate={name:result.name,rules:result.rules}
  globalThis.NbtConstraintContract.rules(candidate.rules)
  fill(candidate);actor='agent';say('Agent 已填好草稿。核对尺寸、网格和文字后，点击「保存约束」。')
 })
 openButton.onclick=()=>open()
 window.addEventListener('project-constraints-open',event=>open(event.detail??{}))
 window.addEventListener('creator-workspace-change',()=>{if(dialog.open&&!pending)dialog.close()})
 return {scope(entry){openButton.textContent=entry?'管理约束':'共用约束';openButton.title=entry?'管理「'+entry.label+'」的约束':'管理工作区共用约束';openButton.setAttribute('aria-label',openButton.title)}}
}
