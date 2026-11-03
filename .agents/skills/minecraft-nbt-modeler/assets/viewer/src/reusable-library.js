import './reusable-library.css'

const axes=['X','Y','Z'],vectorInputs=(prefix,values)=>`<span class="asset-vector">${axes.map((axis,i)=>`<input id="${prefix}-${i}" type="number" step="1" value="${values[i]}" aria-label="${prefix==='reusable-position'?'配方放置':prefix} ${axis}">`).join('')}</span>`
const tags=text=>text.split(/[,，]/).map(v=>v.trim()).filter(Boolean)
const clean=data=>{const copy=structuredClone(data);delete copy.id;delete copy.file;return copy}
const integerInputs=(root,prefix)=>axes.map((_,i)=>{const input=root.querySelector('#'+prefix+'-'+i),n=Number(input.value);if(!input.value.trim()||!Number.isInteger(n))throw Error('XYZ 坐标须为整数');return n})

export function initReusableLibrary({api,context,apply}){
 const dialog=document.createElement('dialog');dialog.id='reusable-dialog'
 dialog.innerHTML='<header><h2 id="reusable-title">操作配方</h2><button id="reusable-close" type="button">关闭</button></header><div class="reusable-toolbar"><input id="reusable-search" type="search" placeholder="名称或标签" aria-label="搜索配方或主题"><label class="inline"><input id="reusable-trash" type="checkbox">回收站</label><button id="reusable-new" type="button">新建</button><button id="reusable-capture" type="button">保存当前工具序列</button><button id="reusable-import" type="button">导入 JSON</button><input id="reusable-file" type="file" accept=".json,application/json" hidden></div><div class="reusable-body"><nav id="reusable-list" aria-label="配方或主题列表"></nav><section id="reusable-editor"></section></div><p id="reusable-status" role="status"></p>'
 document.body.append(dialog)
 const $=id=>dialog.querySelector('#'+id),message=text=>$('reusable-status').textContent=text
 let type='recipe',items=[],selected=null,pending=false,selection=0,captured=null
 const notify=()=>window.dispatchEvent(new CustomEvent('creator-reusable-change'))
 async function perform(action){if(pending)return;pending=true;const buttons=[...dialog.querySelectorAll('button:not(#reusable-close)')].map(b=>[b,b.disabled]);for(const [b]of buttons)b.disabled=true;try{await action()}catch(e){message(e.message)}finally{pending=false;for(const [b,disabled]of buttons)if(b.isConnected)b.disabled=disabled}}
 function drawList(){
  const q=$('reusable-search').value.toLocaleLowerCase(),trash=$('reusable-trash').checked,list=$('reusable-list');list.replaceChildren()
  for(const item of items.filter(v=>v.asset_type===type&&v.archived===trash&&[v.name,...v.tags].join(' ').toLocaleLowerCase().includes(q))){const button=document.createElement('button');button.type='button';button.dataset.reusableId=item.id;button.setAttribute('aria-pressed',String(selected?.id===item.id));const name=document.createElement('strong'),meta=document.createElement('small');name.textContent=item.name;meta.textContent=type==='recipe'?`${item.operation_count} 步 · ${item.parameter_count} 个参数`:`${item.material_count} 条材质映射`;button.append(name,meta);button.onclick=()=>perform(()=>choose(item.id));list.append(button)}
  if(!list.children.length){const p=document.createElement('p');p.textContent=trash?'回收站为空':'暂无内容，可新建、导入或保存工具序列';list.append(p)}
 }
 async function refresh(){const result=await api('recipes');items=result.items;drawList();if(result.errors.length)message(`${result.errors.length} 份文件无法读取，其余已载入`)}
 function base(data){
  selected=data;captured=null;drawList();const editor=$('reusable-editor');editor.innerHTML='<label>名称<input id="reusable-name" maxlength="80"></label><label>标签（逗号分隔）<input id="reusable-tags" maxlength="500"></label><div id="reusable-form"></div><div class="reusable-buttons"><button id="reusable-save" class="primary" type="button">保存到工作区</button><button id="reusable-export" type="button">导出 JSON</button><button id="reusable-archive" type="button">移入回收站</button></div>'
  $('reusable-name').value=data.name;$('reusable-tags').value=data.tags.join(', ');$('reusable-archive').hidden=!data.id;$('reusable-archive').textContent=data.archived?'恢复':'移入回收站'
  $('reusable-archive').onclick=()=>perform(async()=>{await api('recipes/archive',{id:data.id,archived:!data.archived});notify();await refresh();await choose(data.id);message(data.archived?'已恢复':'已移入回收站')})
  $('reusable-export').onclick=()=>{try{const value=edited(),url=URL.createObjectURL(new Blob([JSON.stringify(value,null,2)],{type:'application/json'})),link=document.createElement('a');link.href=url;link.download=value.name+'.'+value.asset_type+'.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}catch(e){message(e.message)}}
  $('reusable-save').onclick=()=>perform(async()=>{const result=await api('recipes/save',{asset:edited(),...(data.id?{id:data.id}:{})});notify();await refresh();await choose(result.id);message('已保存到工作区 .nbtcreator/reusable，可由应用和 Agent 共用')})
 }
 function edited(){
  if(!selected)throw Error('请先新建或选择内容')
  let value=clean(selected)
  if(type==='recipe'){value=JSON.parse($('reusable-json').value)}else{value.mapping={};for(const row of dialog.querySelectorAll('.reusable-mapping')){const [a,b]=row.querySelectorAll('input');if(!a.value.trim()&&!b.value.trim())continue;if(!a.value.trim()||!b.value.trim()||Object.hasOwn(value.mapping,a.value.trim()))throw Error('请填写完整且不重复的材质映射');value.mapping[a.value.trim()]=b.value.trim()}value.preserve_shape=$('reusable-preserve').checked}
  value.name=$('reusable-name').value;value.tags=tags($('reusable-tags').value);return value
 }
 function mappingRow(before='',after=''){
  const row=document.createElement('div');row.className='reusable-mapping';const a=document.createElement('input'),arrow=document.createElement('span'),b=document.createElement('input'),remove=document.createElement('button');a.value=before;b.value=after;a.placeholder='原方块，如 stone_bricks';b.placeholder='目标方块，如 deepslate_bricks';a.setAttribute('aria-label','原方块状态');b.setAttribute('aria-label','目标方块状态');arrow.textContent='→';remove.type='button';remove.textContent='×';remove.setAttribute('aria-label','删除材质映射');remove.onclick=()=>row.remove();row.append(a,arrow,b,remove);$('reusable-mappings').append(row)
 }
 async function choose(id){const token=++selection,data=await api('recipes/get',{id});if(token!==selection)return;show(data)}
 function show(data){
  type=data.asset_type;$('reusable-title').textContent=type==='recipe'?'操作配方':'材质主题';$('reusable-capture').hidden=type!=='recipe';base(data)
  const form=$('reusable-form')
  if(type==='theme'){
   form.innerHTML='<p>把一组原材质替换为另一组。主题可用于构件或操作配方；不会直接给整座建筑换材。只映射一次，保留兼容的朝向、半砖等状态。</p><div id="reusable-mappings"></div><button id="reusable-add-material" type="button">添加映射</button><label class="inline"><input id="reusable-preserve" type="checkbox">保持碰撞形状（推荐）</label><p>例如石砖 → 深板岩砖；保持形状时，完整方块不能直接换成半砖。关闭后仍需预览并检查通路。</p>'
   for(const [a,b]of Object.entries(data.mapping))mappingRow(a,b);$('reusable-add-material').onclick=()=>mappingRow();$('reusable-preserve').checked=data.preserve_shape
  }else{
   const c=context();form.innerHTML='<p>调整参数后，配方会展开为当前引擎的工具步骤；载入后立即预览，可撤销，正式建筑仍需另存下一版。位置是配方本地原点，保存当前序列时以其包围盒最小点归零。</p><fieldset><legend>本次参数</legend><div id="reusable-values"></div></fieldset><label>放置原点 XYZ'+vectorInputs('reusable-position',c?.lo??[0,0,0])+'</label><label>材质主题<select id="reusable-theme"><option value="">保留原材质</option></select></label><label class="inline"><input id="reusable-overwrite" type="checkbox">允许创建步骤覆盖已有方块</label><button id="reusable-apply" class="primary" type="button">载入并预览</button><details><summary>编辑参数定义与工具 JSON（高级）</summary><p>参数引用使用 {"param":"参数名"}；数值可加固定常量 add。这里保存数据，不运行脚本。修改 JSON 后先保存，再使用更新后的参数控件。</p><textarea id="reusable-json" rows="14" spellcheck="false" aria-label="配方 JSON"></textarea></details>'
   $('reusable-json').value=JSON.stringify(clean(data),null,2)
   for(const item of items.filter(v=>v.asset_type==='theme'&&!v.archived)){const option=document.createElement('option');option.value=item.id;option.textContent=item.name;$('reusable-theme').append(option)}
   for(const [key,spec]of Object.entries(data.parameters)){const label=document.createElement('label'),input=document.createElement('input');label.textContent=spec.label||key;input.dataset.recipeParam=key;input.type=spec.type==='boolean'?'checkbox':spec.type==='block'?'text':'number';if(spec.type==='boolean')input.checked=spec.default;else{input.value=spec.default;if(spec.type!=='block'){input.step=spec.type==='integer'?'1':'any';if(spec.min!==undefined)input.min=spec.min;if(spec.max!==undefined)input.max=spec.max}}label.append(input);$('reusable-values').append(label)}
   if(!Object.keys(data.parameters).length)$('reusable-values').textContent='固定工具序列，可在高级 JSON 中定义参数。'
   $('reusable-apply').disabled=!data.id||data.archived
   $('reusable-apply').onclick=()=>perform(async()=>{
    if($('reusable-json').value!==JSON.stringify(clean(data),null,2))throw Error('JSON 已修改，请先保存配方')
    const start=context();if(!start)throw Error('请先从项目管理打开建筑')
    const values={};for(const input of dialog.querySelectorAll('[data-recipe-param]')){const key=input.dataset.recipeParam,spec=data.parameters[key];if(input.type!=='checkbox'&&!input.value.trim())throw Error('请填写全部参数');values[key]=spec.type==='boolean'?input.checked:spec.type==='block'?input.value:Number(input.value)}
    const result=await api('recipes/compile',{id:data.id,values,position:integerInputs(dialog,'reusable-position'),theme:$('reusable-theme').value||null,overwrite:$('reusable-overwrite').checked,source:start.source,source_sha256:start.source_sha256})
    const now=context();if(!now||now.source!==start.source||now.source_sha256!==start.source_sha256||now.settings!==start.settings)throw Error('当前建筑或参数已改变，请重新载入配方')
    await apply(result,start.settings);dialog.close()
   })
  }
 }
 async function captureCurrent(){
  const c=context();if(!c?.operations?.length)throw Error('当前没有工具序列，请先在建模工具或 AI 建模中添加步骤。整体混材等独立面板不会自动收入配方。')
  const operations=structuredClone(c.operations),result=await api('recipes/capture',{operations,name:'我的操作配方'})
  show(result.asset);captured={operations,fields:result.fields};$('reusable-form').innerHTML='<p>原工具序列已按包围盒归零。勾选想在复用时调整的字段，并填写便于理解的参数名；未勾选的值保持固定。最多32项。</p><div class="reusable-fields" id="reusable-fields"></div><button id="reusable-build" type="button">生成参数控件</button>'
  for(const [index,field]of result.fields.entries()){
   const row=document.createElement('div');row.className='reusable-binding';const check=document.createElement('input'),label=document.createElement('span'),name=document.createElement('input');check.type='checkbox';check.dataset.binding=index;check.checked=typeof field.value==='string';const route=field.path.slice(1).map((key,i,a)=>typeof key==='number'&&['lo','hi','start','end','offset','destination','centre'].includes(a[i-1])?axes[key]:globalThis.NbtToolCatalog?.labels[key]??key).join(' / ');label.textContent=`步骤 ${field.path[0]+1} · ${route} = ${field.value}`;name.type='text';name.value=route;name.setAttribute('aria-label','参数显示名称 '+index);row.append(check,label,name);$('reusable-fields').append(row)
  }
  $('reusable-save').disabled=true;$('reusable-export').disabled=true
  $('reusable-build').onclick=()=>perform(async()=>{const {operations,fields}=captured,bindings=[...dialog.querySelectorAll('[data-binding]:checked')].map((input,i)=>({path:fields[Number(input.dataset.binding)].path,name:'p'+(i+1),label:input.parentElement.querySelector('input[type=text]').value}));const result=await api('recipes/capture',{operations,name:$('reusable-name').value,tags:tags($('reusable-tags').value),bindings});show(result.asset);message('已生成参数控件；保存后即可复用')})
 }
 async function open(kind){type=kind;selected=null;selection++;$('reusable-title').textContent=type==='recipe'?'操作配方':'材质主题';$('reusable-capture').hidden=type!=='recipe';$('reusable-search').value='';$('reusable-trash').checked=false;$('reusable-editor').innerHTML='<p>选择已有内容，或新建可复用配方与材质主题。资料保存在当前工作区。</p>';message('');if(!dialog.open)dialog.showModal();await perform(refresh)}
 $('reusable-close').onclick=()=>dialog.close();$('reusable-search').oninput=drawList;$('reusable-trash').onchange=drawList
 $('reusable-capture').onclick=()=>perform(captureCurrent)
 $('reusable-new').onclick=()=>show(type==='theme'?{schema_version:1,asset_type:'theme',name:'新的材质主题',tags:[],archived:false,mapping:{'minecraft:stone_bricks':'minecraft:deepslate_bricks'},preserve_shape:true}:{schema_version:1,asset_type:'recipe',name:'参数石柱',tags:[],archived:false,parameters:{height:{type:'integer',label:'柱高',default:4,min:1,max:64},material:{type:'block',label:'柱身方块',default:'minecraft:stone_bricks'}},operations:[{kind:'box',label:'配方石柱',classification:'body',lo:[0,0,0],hi:[0,{param:'height',add:-1},0],state:{param:'material'}}]})
 $('reusable-import').onclick=()=>$('reusable-file').click();$('reusable-file').onchange=()=>perform(async()=>{const file=$('reusable-file').files[0];$('reusable-file').value='';if(!file)return;if(file.size>8*1024*1024)throw Error('文件超过8 MiB');const data=JSON.parse(await file.text()),result=await api('recipes/save',{asset:clean(data)});type=result.asset_type;notify();await refresh();show(result);message('已导入工作区，可继续调整')})
 window.addEventListener('creator-workspace-change',e=>{if(e.detail!=='assets'&&dialog.open)dialog.close()})
 return {open,decorateTree(tree){const list=tree.querySelector('.project-tree-list');if(!list||list.querySelector('[data-reusable-open]'))return;const anchor=list.querySelector('.project-tree-all');for(const [kind,label]of [['theme','材质主题'],['recipe','操作配方']]){const button=document.createElement('button');button.type='button';button.className='project-tree-all reusable-navigation';button.dataset.reusableOpen=kind;button.innerHTML='<svg viewBox="0 0 20 20" aria-hidden="true"><path d="M2.5 5.5h5l2 2h8v8h-15z"/></svg>';const text=document.createElement('span');text.textContent=label;button.append(text);button.onclick=()=>open(kind).catch(e=>message(e.message));anchor.after(button)}}}
}
