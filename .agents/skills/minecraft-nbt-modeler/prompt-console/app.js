(() => {
 const C=NbtPrompt, $=id=>document.getElementById(id), storage='nbt-prompt-console-v2';
 let state=C.defaults(), pending=new Map(),autosave,studio;const archivedPrompts=new Map();
 const constraintStorage=parent===window?null:parent.nbtPromptStorage;
 let constraintFolder=constraintStorage?.constraintFolder?.()??'',constraintLibrary=[],constraintLoading=false,constraintError='',constraintRequest=0;
 try{const saved=localStorage.getItem(storage);if(parent===window&&saved){const candidate=C.normalize(JSON.parse(saved));if(!C.validate(candidate).length)state=candidate;}}catch{}
 const projectFields={...Object.fromEntries(Object.entries(C.designContract.fields).map(([key,value])=>[key,value.label])),buildingShape:'归档形状（按实际模型登记）',stage:'这次要做什么',size_policy:'尺寸约束方式',source:'正在修改的建筑文件',integration:'使用场景',output:'建筑保存位置',budget:'最多允许修改的方块数',contextPath:'通路与保护区域配置',reviewPath:'看图确认资料（可留空）'};
 const options={size_policy:Object.entries(C.designContract.size_policies),buildingShape:Object.entries(C.buildingShapes).map(([k,v])=>[k,v.label]),stage:[['draft','首次创建完整初稿'],['plan','只读修改规划'],['refine','已有建筑精修']],integration:[['standalone','独立建筑'],['saodg','SAODG 接入']],classification:['body','wall','inherit'],mirror:[['','无'],['x','X 镜像'],['z','Z 镜像']],profile:['maintained','worn','ruined','cavern'],action:['replace','fill'],scope:['surface','volume'],shape_policy:['preserve','any']};
 function element(tag,text,cls){const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;}
 function download(name,value,type='application/json'){const blob=new Blob([typeof value==='string'?value:JSON.stringify(value,null,2)],{type});const a=element('a');a.href=URL.createObjectURL(blob);a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);}
 function notify(message,error=false){$('status').textContent=message;$('status').classList.toggle('error',error);$('prompt-editor-save-state').textContent=error?message:'修改后自动保存';$('prompt-editor-save-state').title=message;$('prompt-editor-save-state').classList.toggle('error',error);}
 function binding(){return JSON.stringify({project:state.project,operations:state.operations,...(state.constraints?.length?{constraints:state.constraints}:{}),...(state.design_standard?{project_standard:C.standardText(state)}:{})});}
 function requestBinding(){return JSON.stringify({design:binding(),brief_fields:briefFields(state)});}
 function aiDraft(){return state.aiDraft&&typeof state.aiDraft.text==='string'&&state.aiDraft.text.length<=60000&&state.aiDraft.binding===binding()?state.aiDraft:null;}
 function composeAI(text){return C.prompt(state,{designText:text});}
 function outputText(){const cached=archivedPrompts.get(state.export_id);if(cached?.binding===JSON.stringify(state))return cached.original.text;return aiDraft()?composeAI(aiDraft().text):C.prompt(state);}
 function update(){const errors=[...pending.values(),...C.validate(state)];const invalid=errors.length>0;if(!invalid&&state.project.stage==='draft'){state.project.output=C.outputPath(C.effectiveProject(state));const output=document.querySelector('[data-field=output]');if(output)output.value=state.project.output;}if(state.proposal_draft&&state.proposal_draft.binding!==requestBinding())delete state.proposal_draft;for(const id of ['copy','markdown','plan','config','save','left-save'])$(id).disabled=invalid;
   $('result').value=invalid?'请先补齐以下内容：\n'+errors.join('\n'):outputText();notify(invalid?errors.join('\n'):state.operations.length?`${state.operations.filter(op=>op.enabled!==false).length} 个启用 / ${state.operations.length} 个高级步骤 · 供建造助手核对`:'请核对建筑要求，审查后交给建造助手制作',invalid);$('count').textContent=state.operations.length;
   $('output-mode').textContent=aiDraft()?'当前任务包含：已采用的 AI 建议、建筑要求及校验配置':state.aiDraft?'建筑要求已修改，任务已更新为当前表单内容；请重新核对 AI 建议':'当前任务使用表单中的建筑要求';
   if(!state.export_id)state.export_id=crypto.randomUUID().replaceAll('-','');
   studio?.edited(state);if(!studio?.loading&&!studio?.pristine)autosave?.schedule(!invalid);
   if(!invalid)try{localStorage.setItem(storage,JSON.stringify(state));}catch{notify('当前浏览器无法自动暂存，请使用“保存方案”');}
 }
 function selectOptions(key,kind){if(key==='mode')return {geometry:['set','add','subtract','intersect'],morphology:['dilate','erode','shell','opening','closing'],pattern:['independent','clustered']}[kind];if(key==='width')return ['1','3','5'];return options[key];}
 function field(parent,key,value,setter,{kind='',label='',token=key,wide=false}={}){
   if(value&&typeof value==='object'&&!Array.isArray(value)){
     const group=element('div',undefined,'wide nested');group.append(element('strong',label||C.labels[key]||key));const content=element('div',undefined,'fields');
     for(const [child,v]of Object.entries(value)){if(key==='geometry'&&child==='shape')continue;field(content,child,v,n=>{value[child]=n;setter(value);},{kind,label:C.labels[child]||child,token:token+'.'+child});}
     group.append(content);parent.append(group);return group;
   }
   if(Array.isArray(value)&&value.length===3&&value.every(v=>typeof v==='number')){
     const group=element('div',undefined,'wide vector');group.append(element('span',label||C.labels[key]||key));const row=element('div',undefined,'xyz');
     value.forEach((v,i)=>{const child=element('label','XYZ'[i]),input=element('input');input.type='number';input.step='any';input.value=v;input.dataset.field=key+'.'+'xyz'[i];input.oninput=()=>{if(input.value.trim()&&Number.isFinite(Number(input.value))){value[i]=Number(input.value);setter([...value]);pending.delete(token+'.'+i);}else pending.set(token+'.'+i,`${key}需要有效XYZ数字`);update();};child.append(input);row.append(child);});group.append(row);parent.append(group);return group;
   }
   const wrapper=element('label',undefined,wide?'wide':'');wrapper.append(element('span',label||C.labels[key]||key));let input;const opts=selectOptions(key,kind);
   if(opts){input=element('select');for(const opt of opts){const [v,t]=Array.isArray(opt)?opt:[opt,opt];const e=element('option',t);e.value=v;input.append(e);}input.value=value===null?'':String(value);}
   else if(typeof value==='boolean'){input=element('input');input.type='checkbox';input.checked=value;}
   else if(typeof value==='number'){input=element('input');input.type='number';input.step='any';input.value=value;}
   else if(typeof value==='object'){input=element('textarea');input.className='json';input.value=JSON.stringify(value,null,2);wrapper.classList.add('wide');}
   else if(wide){input=element('textarea');input.value=value;}
   else {input=element('input');input.type='text';input.value=value;}
   input.dataset.field=key;
   input.addEventListener(opts?'change':'input',()=>{try{
     let v=typeof value==='boolean'?input.checked:typeof value==='number'?Number(input.value):typeof value==='object'&&!opts?JSON.parse(input.value):input.value;
     if(typeof value==='number'&&(!input.value.trim()||!Number.isFinite(v)))throw Error('需要有效数字');
     if(key==='mirror'&&v==='')v=null;if(key==='width')v=Number(v);
     setter(v);pending.delete(token);
   }catch(e){pending.set(token,`${label||C.labels[key]||key}：${e.message}`);}update();});wrapper.append(input);parent.append(wrapper);return input;
 }
 function briefFields(doc=state){const value=doc.workbench?.brief_fields??C.designContract.default_editable_fields;return Array.isArray(value)?[...value]:[];}
 function renderBriefScope(){
   const host=$('prompt-ai-fields');if(!host)return;host.replaceChildren();
   const selected=new Set(briefFields());
   for(const [key,spec]of Object.entries(C.designContract.fields)){
     const label=element('label',undefined,'inline'),input=element('input');input.type='checkbox';input.dataset.briefField=key;input.checked=selected.has(key);input.disabled=aiRunning;
     input.onchange=()=>{const next=new Set(briefFields());if(input.checked)next.add(key);else next.delete(key);state.workbench={...state.workbench,brief_fields:[...next]};$('prompt-ai-fields-title').textContent='AI可修改的参数（'+next.size+'/'+Object.keys(C.designContract.fields).length+'）';update();};
     label.append(input,document.createTextNode(spec.label));host.append(label);
   }
   $('prompt-ai-fields-title').textContent='AI可修改的参数（'+selected.size+'/'+Object.keys(C.designContract.fields).length+'）';
   $('prompt-ai-scope').hidden=$('prompt-ai-mode').value!=='draft';
 }
 function renderProject(){
   const host=$('project-fields'),draft=state.project.stage==='draft';host.replaceChildren();
   const shown=C.effectiveProject(state),bound=NbtConstraintContract.resolve(state.constraints??[]);
   const constraints=element('fieldset',undefined,'field-group');constraints.id='prompt-constraints';host.append(constraints);renderConstraints();
   const sections=[['建筑概况',['name','stage','buildingShape','integration','theme','purpose']],['空间与体验',['size','size_policy','footprint','spatial_character','layout','circulation','atmosphere']],['风格与部位意图',['style','materials','ceiling','floor','wall','props']],['硬条件与补充',['avoid','preserve','extras']],['文件与修改范围（高级）',['source','output','budget','contextPath','reviewPath']]];const groups=new Map();
   for(const [title,keys]of sections){const group=element('fieldset',undefined,'field-group'),legend=element('legend',title),fields=element('div',undefined,'fields');group.append(legend,fields);host.append(group);for(const key of keys)groups.set(key,fields)}
   for(const [key,label]of Object.entries(projectFields)){
     if(draft&&['source','contextPath','reviewPath','budget'].includes(key))continue;
     const input=field(groups.get(key),key,key==='output'?C.outputPath(shown):shown[key],v=>{
       if(key==='buildingShape')C.applyShape(state.project,v);else state.project[key]=v;
       if(key==='integration'&&v==='saodg')state.project.size_policy='fixed';
       if(key==='stage'&&v!=='draft')state.project.size_policy='fixed';
       if(key==='stage'&&v==='draft'){state.project.source='';state.project.contextPath='';state.project.reviewPath='';state.project.context=C.defaults().project.context;}
       if(['buildingShape','stage','integration'].includes(key))renderProject();
     },{label:key==='output'&&draft?'自动保存到当前项目':label,token:'project.'+key,wide:['theme','purpose','style','ceiling','floor','wall','props','preserve','extras','source','output','contextPath','reviewPath','footprint','layout','circulation','spatial_character','materials','atmosphere','avoid'].includes(key)});
     if(key==='output'&&draft){input.readOnly=true;input.classList.add('auto-path');const hint=element('small','建造助手会在这里为建筑另存新版本。制作稿使用 SNBT；你定稿后，再导出到专用 NBT 交付目录。','field-help');input.parentElement.append(hint);}
     if(key==='buildingShape'&&!draft)input.disabled=true;
     if(Object.hasOwn(C.designContract.fields,key)&&['INPUT','TEXTAREA'].includes(input.tagName)&&typeof state.project[key]==='string')input.maxLength=4000;
     if(key==='size_policy'&&(!draft||state.project.integration==='saodg'))input.disabled=true;
     if(Object.hasOwn(bound,key)){if(input.matches('input,select,textarea'))input.disabled=true;else input.querySelectorAll('input,select,textarea').forEach(node=>node.disabled=true);input.title='来自已选项目约束；可移除引用或在项目管理中另存约束';}
   }
   $('context-json').value=JSON.stringify(state.project.context,null,2);
   const draftOption=$('prompt-ai-mode').querySelector('[value=draft]');draftOption.disabled=!draft;
   if(!draft&&$('prompt-ai-mode').value==='draft')$('prompt-ai-mode').value='text';
   $('project-intro').textContent=draft?'人工参数可逐项修改；未限定的部位可以留空。AI只辅助编写设计意图，具体构造由执行Agent推导。':'正在编写已有建筑的修改要求。原建筑和保护范围沿用当前版本；改动会自动保存为提示词。';
   renderBriefScope();
 }

 function renderConstraints(){
   const host=$('prompt-constraints');if(!host)return;host.replaceChildren(element('legend','项目约束'));
   const folders=constraintStorage?.constraintFolders?.()??[];
   const folderName=folder=>folders.find(entry=>entry.folder===folder)?.label??(folder||'工作区共用');
   if(constraintStorage){
     const label=element('label','从文件夹选约束'),picker=element('select');picker.id='prompt-constraint-folder';
     picker.add(new Option('工作区共用',''));
     for(const entry of folders)picker.add(new Option(entry.label,entry.folder));
     if(constraintFolder&&!folders.some(entry=>entry.folder===constraintFolder))picker.add(new Option(constraintFolder,constraintFolder));
     picker.value=constraintFolder;picker.disabled=aiRunning;picker.onchange=()=>refreshConstraints(picker.value);label.append(picker);host.append(label);
   }
   host.append(element('p','勾选后，提示词会列出这一版的尺寸、可建网格和文字要求。换文件夹可以继续选，之前的勾选会保留。','field-help'));
   const actions=element('div',undefined,'constraint-actions');
   const openConstraints=(create=false)=>parent.dispatchEvent(new CustomEvent('project-constraints-open',{detail:{folder:constraintFolder,create,agent:create}}));
   for(const [label,run]of [['编辑文件夹约束',()=>openConstraints()],['Agent 创建约束',()=>openConstraints(true)],['刷新约束',()=>refreshConstraints(constraintFolder)]]){const button=element('button',label);button.type='button';button.disabled=constraintLoading||aiRunning||!constraintStorage;button.onclick=run;actions.append(button)}host.append(actions);
   const selected=state.constraints??[],items=new Map(constraintLibrary.map(item=>[item.id,item]));for(const item of selected)if(!items.has(item.id))items.set(item.id,item);
   if(!constraintLibrary.length)host.append(element('p',constraintError||(constraintLoading?'正在读取「'+folderName(constraintFolder)+'」的约束…':'「'+folderName(constraintFolder)+'」还没有可选的约束。'),'field-help'));
   for(const item of items.values()){
     const saved=selected.find(value=>value.id===item.id),row=element('div',undefined,'constraint-choice'),label=element('label',undefined,'inline'),check=element('input');check.type='checkbox';check.dataset.constraintId=item.id;check.checked=!!saved;check.disabled=constraintLoading||aiRunning;
     check.onchange=async()=>{check.disabled=true;try{await window.NbtPromptUI.applyConstraints(check.checked?[...selected,item]:selected.filter(value=>value.id!==item.id))}catch(error){notify(error.message,true);renderConstraints()}};
     const shown=saved??item;
     label.append(check,document.createTextNode(shown.name+' · 第 '+shown.revision+' 版'));row.append(label);
     if((shown.folder??'')!==constraintFolder)row.append(element('small','来自「'+folderName(shown.folder)+'」'));
     if(saved&&saved.sha256!==item.sha256){const latest=element('button','改用第 '+item.revision+' 版');latest.type='button';latest.disabled=aiRunning;latest.onclick=()=>window.NbtPromptUI.applyConstraints(selected.map(value=>value.id===item.id?item:value)).catch(error=>notify(error.message,true));row.append(latest)}
     const details=element('details'),summary=element('summary','查看要求'),description=element('ul');
     for(const line of NbtConstraintContract.describe(shown.rules))description.append(element('li',line));
     details.append(summary,description);row.append(details);host.append(row);
   }
 }
 async function refreshConstraints(folder=constraintFolder){
   const request=++constraintRequest;
   constraintFolder=folder;constraintLibrary=[];constraintError='';constraintLoading=true;renderConstraints();
   try{const result=await constraintStorage?.constraints?.(folder);if(request===constraintRequest)constraintLibrary=result?.items??[]}
   catch(error){if(request===constraintRequest)constraintError='读取约束失败。'+error.message}
   finally{if(request===constraintRequest){constraintLoading=false;renderConstraints()}}
 }

 function renderOperations(){const host=$('operations');host.replaceChildren();if(!state.operations.length)host.append(element('p','尚未添加工具。可以先只填写建筑要求，由 Agent 按需选择。','empty'));
   state.operations.forEach((op,i)=>{const card=element('article',undefined,'step');card.dataset.step=i;const header=element('div',undefined,'step-head');header.append(element('strong',`${String(i+1).padStart(2,'0')}  ${C.catalog[op.kind][0]}`));
     for(const [text,action,disabled]of [['↑',()=>{[state.operations[i-1],state.operations[i]]=[op,state.operations[i-1]];},i===0],['↓',()=>{[state.operations[i+1],state.operations[i]]=[op,state.operations[i+1]];},i===state.operations.length-1],['复制',()=>state.operations.splice(i+1,0,C.clone(op)),false],['删除',()=>state.operations.splice(i,1),false]]){const b=element('button',text);b.disabled=disabled;b.onclick=()=>{if(pending.size){notify('请先修复未完成的参数，再调整步骤',true);return;}action();renderOperations();update();};header.append(b);}const toggleLabel=element("label","启用 "),toggle=element("input");toggle.type="checkbox";toggle.checked=op.enabled!==false;toggle.setAttribute("aria-label",`启用第${i+1}步`);toggle.onchange=()=>{op.enabled=toggle.checked;renderOperations();update();};toggleLabel.append(toggle);header.append(toggleLabel);card.dataset.enabled=String(op.enabled!==false);card.append(header,element('p',C.catalog[op.kind][2],'hint'));
     const fields=element('div',undefined,'fields');
     if(op.kind==='geometry'){const label=element('label','几何类型'),sel=element('select');sel.dataset.field='shape';for(const shape of Object.keys(C.shapes)){const o=element('option',shape);o.value=shape;sel.append(o);}sel.value=op.geometry.shape;sel.onchange=()=>{op.geometry={shape:sel.value,...C.clone(C.shapes[sel.value])};pending.delete(`op.${i}.geometry`);renderOperations();update();};label.append(sel);fields.append(label);}
     for(const [key,value]of Object.entries(op)){if(key==='kind'||key==='enabled')continue;field(fields,key,value,v=>{op[key]=v;},{kind:op.kind,token:`op.${i}.${key}`,wide:key==='label'});}card.append(fields);
     const details=element('details');details.append(element('summary','高级：编辑本步骤完整 JSON（可补充可选参数）'));const raw=element('textarea');raw.className='json';raw.value=JSON.stringify(op,null,2);raw.setAttribute('aria-label','本步骤完整 JSON');details.ontoggle=()=>{if(details.open)raw.value=JSON.stringify(op,null,2);};const apply=element('button','应用步骤 JSON');apply.onclick=()=>{try{const value=JSON.parse(raw.value);const candidate=C.clone(state);candidate.operations[i]=value;const errors=C.validate(candidate);if(errors.length)throw Error(errors.join('；'));state=candidate;for(const k of pending.keys())if(k.startsWith(`op.${i}.`))pending.delete(k);renderOperations();update();}catch(e){notify('步骤 JSON：'+e.message,true);}};details.append(raw,apply);card.append(details);host.append(card);
   });
 }
 for(const [kind,[label]]of Object.entries(C.catalog)){const o=element('option',label);o.value=kind;$('kind').append(o);}
 $('add').onclick=()=>{if(pending.size){notify('请先修复未完成的参数',true);return;}state.operations.push(C.operation($('kind').value));renderOperations();update();};
 $('prompt-advanced-toggle').onclick=()=>{const open=$('prompt-advanced-tabs').hidden;$('prompt-advanced-tabs').hidden=!open;$('prompt-advanced-toggle').setAttribute('aria-expanded',String(open));$('prompt-ai-mode').querySelector('[value=controls]').hidden=!open;if(!open){if($('prompt-ai-mode').value==='controls')$('prompt-ai-mode').value=state.project.stage==='draft'?'draft':'text';if(['tools','context'].some(id=>!$(id).hidden))document.querySelector('[data-tab=project]').click()}};
 document.querySelectorAll('[data-tab]').forEach(b=>b.onclick=()=>{document.querySelectorAll('[data-tab]').forEach(x=>{x.classList.toggle('active',x===b);x.setAttribute('aria-pressed',String(x===b))});document.querySelectorAll('.tab').forEach(x=>x.hidden=x.id!==b.dataset.tab);});
 $('context-json').oninput=()=>{try{const v=JSON.parse($('context-json').value);if(!v||typeof v!=='object'||Array.isArray(v))throw Error('上下文须为对象');state.project.context=v;pending.delete('context');$('context-error').textContent='';}catch(e){pending.set('context','上下文JSON无效：'+e.message);$('context-error').textContent=e.message;}update();};
 $('save').onclick=()=>download('nbt_prompt_settings.json',state);
 $('left-read').onclick=()=>$('import').click();
 $('left-save').onclick=()=>studio.exclusive(async()=>{
  const button=$('left-save');button.disabled=true
  try{
   if(pending.size||C.validate(state).length)throw Error('请先修正当前参数，再保存任务')
   const saved=await autosave.flush()
   if(!saved||!parent.nbtPromptStorage?.publish)throw Error('保存任务需要在工作区桌面版中使用')
   if(pending.size||C.validate(state).length)throw Error('参数已变化，请修正后重新保存任务')
   await studio.confirmCurrent();const current=await autosave.flush();const task=await parent.nbtPromptStorage.publish({index:current.index,id:current.id,revision:current.revision});studio.published(task)
   const status=$('prompt-task-state');status.dataset.id=task.id;status.dataset.path=task.directory;status.textContent='已交接“'+state.project.name+'”，请手动让外部助手读取任务。';status.title=task.directory
   $('prompt-task-command').textContent='python .agents/skills/nbtcreator-workspace/nbt.py prompts task --id '+task.id
   $('prompt-task-handoff').hidden=false;studio.showOutput(true);notify(task.unchanged?'该任务已保存，未重复创建文件夹':'任务目录已创建，提示词和方案已保存，可交给外部 Agent')
  }catch(error){notify(error.message,true)}finally{button.disabled=pending.size>0||C.validate(state).length>0}
 });
 $('prompt-task-copy').onclick=async()=>{try{await navigator.clipboard.writeText($('prompt-task-command').textContent);notify('Agent读取命令已复制')}catch{notify($('prompt-task-command').textContent)}}
 $('markdown').onclick=()=>download('NBT建模完整提示词.md',outputText(),'text/markdown;charset=utf-8');
 $('plan').onclick=()=>download('plan.json',C.plan(state));
 $('config').onclick=()=>download('context_draft.json',{...C.effectiveProject(state).context,max_changed_blocks:state.project.budget});
 $('copy').onclick=async()=>{try{await autosave?.flush();if(navigator.clipboard?.writeText)await navigator.clipboard.writeText($('result').value);else throw Error('fallback');notify('完整提示词已复制');}catch{$('result').focus();$('result').select();notify(document.execCommand('copy')?'完整提示词已复制':'已选中提示词，请按 Ctrl+C');}};
 $('import').onclick=()=>$('file').click();$('file').onchange=async()=>{const f=$('file').files[0];if(!f)return;try{const v=JSON.parse(await f.text());const candidate=C.normalize(v);const errors=C.validate(candidate);if(errors.length)throw Error(errors.join('；'));state=candidate;pending.clear();renderProject();renderOperations();update();}catch(e){notify('导入失败：'+e.message,true);}finally{$('file').value='';}};
 $('reset').onclick=()=>studio.addBlank();
 let aiBridge=null,candidateBinding=null,aiRunning=false,aiEpoch=0,candidateMode='text';
 try{if(window.parent!==window&&window.parent.location.origin===location.origin)aiBridge=window.parent.nbtPromptAI;}catch{}
 function aiMessage(text,error=false){$('prompt-ai-status').textContent=text;$('prompt-ai-status').classList.toggle('error',error);}
 function aiLock(value){aiRunning=value;renderConstraints();$('prompt-ai-mode').disabled=value;$('prompt-ai-generate').disabled=value;$('prompt-ai-cancel').disabled=!value;$('prompt-ai-cancel').hidden=!value;$('prompt-ai-settings').disabled=value;document.querySelectorAll('[data-brief-field]').forEach(input=>input.disabled=value);$('prompt-ai-fields-default').disabled=value;studio?.refresh();}
 function renderCandidate(){
  const host=$('prompt-ai-review');host.replaceChildren();$('prompt-ai-proposal').hidden=!candidateBinding;$('prompt-ai-raw').open=candidateMode==='text';if(!candidateBinding||candidateMode==='text')return;
  try{const proposal=JSON.parse($('prompt-ai-candidate').value);for(const [key,value]of Object.entries(proposal.project_patch??{})){const label=element('label',undefined,['name','buildingShape'].includes(key)?'':'wide');label.append(element('span',projectFields[key]??key));const input=element(key==='name'?'input':'textarea');input.dataset.proposalField=key;input.value=Array.isArray(value)?value.join(' × '):value;input.oninput=()=>{const parsed=JSON.parse($('prompt-ai-candidate').value);parsed.project_patch[key]=key==='size'?input.value.split(/[×xX,， ]+/).filter(Boolean).map(Number):input.value;$('prompt-ai-candidate').value=JSON.stringify(parsed,null,2);state.proposal_draft={binding:candidateBinding,mode:candidateMode,raw:$('prompt-ai-candidate').value};update()};label.append(input);host.append(label)}}catch{aiMessage('AI 返回内容无法展开，请在高级数据中检查格式。',true)}
 }
 function restoreCandidate(){const draft=state.proposal_draft;candidateBinding=draft?.binding===requestBinding()?draft.binding:null;candidateMode=draft?.mode??'draft';$('prompt-ai-candidate').value=candidateBinding?draft.raw:'';$('prompt-ai-apply').disabled=!candidateBinding;renderCandidate()}
 $('prompt-ai-candidate').oninput=()=>{if(candidateBinding){state.proposal_draft={binding:candidateBinding,mode:candidateMode,raw:$('prompt-ai-candidate').value};update()}};
 $('prompt-ai-raw').addEventListener('toggle',()=>{if(!$('prompt-ai-raw').open)renderCandidate()});
 $('prompt-ai-fields-default').onclick=()=>{state.workbench={...state.workbench,brief_fields:C.clone(C.designContract.default_editable_fields)};renderBriefScope();update();};
 $('prompt-ai-instruction').addEventListener('input',()=>{state.workbench={...state.workbench,instruction:$('prompt-ai-instruction').value};update()});
 $('prompt-ai-mode').onchange=()=>{candidateBinding=null;$('prompt-ai-apply').disabled=true;renderBriefScope();aiMessage('已切换AI模式，请重新生成候选方案。');}
 async function refreshAI(){
   if(!aiBridge){$('prompt-ai-indicator').textContent='离线编辑模式';aiMessage('当前可离线填写和导出方案。要使用 AI 辅助，请在 NBTCreator 应用中打开此页。');return;}
   try{const c=await aiBridge.config();$('prompt-ai-indicator').textContent=c.enabled?'AI 已连接':'尚未连接 AI';if(!c.enabled)aiMessage('可在“API 设置”中连接 AI；也可以直接填写建筑要求完成方案。');}catch(e){aiMessage(e.message,true);}
 }
 document.querySelector('[data-tab=ai]').addEventListener('click',refreshAI);refreshAI();
 $('prompt-ai-references').onclick=()=>{const flow=$('prompt-ai-mode').value==='draft'?'draft':$('prompt-ai-mode').value==='text'?'prompt':'workbench';const picker=window.parent?.nbtReferencePicker;if(picker)picker.open({workflow:flow,query:$('prompt-ai-instruction').value}).catch(error=>aiMessage(error.message,true));else aiMessage('本地检索在桌面版工作区提供',true)};
 $('prompt-ai-settings').onclick=()=>{if(aiBridge)aiBridge.settings();else aiMessage('API 设置在 Electron 桌面版主界面右上角提供。',true);};
 function sanitizedDesign(doc=state,mode=$('prompt-ai-mode').value){
   const p=C.effectiveProject(doc),keys=[...Object.keys(C.designContract.fields),'size_policy','integration'];
   const project=Object.fromEntries(keys.map(k=>[k,p[k]]));
   project.extras=String(p.extras??'').split('\n').filter(line=>!line.startsWith('源文件 SHA256：')).join('\n');
   const allowed=new Set(['kind','label','enabled','classification','lo','hi','geometry','mode','state','from_states','seed','max_writes','offset','count','destination','quarter_turns','mirror','move','include_air','overwrite','iterations','seeds','steps','decay','surface_only','centre','radius','roughness','rays','ray_length','ray_width','fraction','spacing','supported','action','scope','scale','palette','preserve_properties','shape_policy','profile','style_note','slab_share','patch_size','pit_depth','route_margin','exclude_boxes','include_boxes','slab_overrides','moss','cracks','floor','thickness','width','start','end']);
   return {project,...(doc.constraints?.length?{constraints:C.clone(doc.constraints)}:{}),task:mode==='draft'?'draft':'controls',...(mode==='draft'?{brief_scope:{editable_fields:briefFields(doc)}}:{}),existing_model:!!p.source,...(doc.design_standard?{project_standard:C.standardText(doc)}:{}),operations:doc.operations.map(op=>Object.fromEntries(Object.entries(op).filter(([key])=>allowed.has(key))))};
 }
 $('prompt-ai-generate').onclick=async()=>{
   if(aiRunning)return;const epoch=++aiEpoch;
   try{
     if(!aiBridge)throw Error('AI 需要在 Electron 桌面版内使用');
     if(pending.size||C.validate(state).length)throw Error('请先修正当前方案参数');
     const before=requestBinding();candidateBinding=null;$('prompt-ai-apply').disabled=true;
     const mode=$('prompt-ai-mode').value;
     const input=NbtPromptAIInput.request(mode,$('prompt-ai-instruction').value,sanitizedDesign());
     aiLock(true);aiMessage('正在根据当前设计要求生成建议…');
     candidateMode=mode;
     if(candidateMode==='draft'&&(state.project.stage!=='draft'||state.project.source))throw Error('请先点击“新建初稿”，再生成完整初稿方案');
     if(input.mode==='workbench'){input.context.baseline_binding=await NbtPromptAIInput.bindingToken(before);if(requestBinding()!==before)throw Error('方案已改变，请重新生成候选')}
     if(epoch!==aiEpoch)throw Object.assign(Error('本次生成已终止'),{code:'AI_CANCELLED'});
     let result=input.mode==='workbench'?await aiBridge.generateWorkbench(input.instruction,input.context):await aiBridge.generate(input.instruction);
     if(epoch!==aiEpoch)throw Object.assign(Error('本次生成已终止'),{code:'AI_CANCELLED'});
     window.parent?.nbtReferencePicker?.sources($('prompt-ai-sources'),result);
     if(requestBinding()!==before)throw Error('生成期间方案已改变，请基于当前方案重新生成');
     if(result.operation_patch)result={...result,operations:NbtPromptAIInput.mergeOperations(state.operations,result.operation_patch)};
     if(candidateMode==='text'&&(result.mode!=='prompt'||typeof result.text!=='string'||!result.text.trim()))throw Error('AI 返回内容无效');
     $('prompt-ai-candidate').value=candidateMode!=='text'?JSON.stringify({summary:result.summary,project_patch:result.project_patch,operations:result.operations},null,2):result.text;candidateBinding=before;state.proposal_draft={binding:before,mode:candidateMode,raw:$('prompt-ai-candidate').value};$('prompt-ai-apply').disabled=false;renderCandidate();update();aiMessage(candidateMode!=='text'?'设计要求已生成。可以直接修改各项文字，再点击“采用并继续审查”。':'说明已写好，可以修改后采用。');
   }catch(e){if(epoch===aiEpoch)aiMessage(e.message,e.code!=='AI_CANCELLED');}finally{if(epoch===aiEpoch)aiLock(false);}
 };
 $('prompt-ai-cancel').onclick=()=>{aiEpoch++;aiBridge?.cancel();aiLock(false);aiMessage('本次生成已终止，可重新编写。')};
 function adoptProposal(base,proposal,mode){
     const patch=proposal.project_patch??{},allowed=Object.keys(C.designContract.fields);
     if(Object.keys(patch).some(key=>!allowed.includes(key)))throw Error('方案不能改写路径、阶段、预算或保护字段');
     const bound=NbtConstraintContract.resolve(base.constraints??[]),effective=C.effectiveProject(base);for(const key of ['buildingShape','size','footprint'])if(bound[key]!==undefined&&patch[key]!==undefined&&JSON.stringify(patch[key])!==JSON.stringify(effective[key]))throw Error('AI不能修改已选项目约束：'+key);
     if(base.project.source&&patch.size&&JSON.stringify(patch.size)!==JSON.stringify(base.project.size))throw Error('已有模型的尺寸保持不变');
     if(mode==='draft')NbtPromptAIInput.assertPatch(base.project,patch,briefFields(base));
     const next=C.clone(base);if(patch.buildingShape&&mode!=='draft'){if(!C.buildingShapes[patch.buildingShape]||base.project.source&&patch.buildingShape!==base.project.buildingShape)throw Error('建筑形状无效，或已有模型形状不能由 AI 改写');C.applyShape(next.project,patch.buildingShape);}for(const [key,value]of Object.entries(patch)){if(key!=='size'&&(typeof value!=='string'||value.length>4000))throw Error('设计字段需为有效文字');next.project[key]=value;}
     if(proposal.operations!==undefined)next.operations=proposal.operations;
     if(mode==='draft'){
       if(!Object.keys(patch).length)throw Error('需要至少一项设计建议');
       if(proposal.operations!==undefined&&(!Array.isArray(proposal.operations)||proposal.operations.length))throw Error('提示词编写只采用设计要求；具体工具步骤请使用高级工具模式');
     }
     const errors=C.validate(next);if(errors.length)throw Error(errors.join('；'));delete next.aiDraft;delete next.proposal_draft;next.workbench={...next.workbench,generated:true,status:'pending'};return next;
 }
 async function generateDocument(doc,isCancelled=()=>false){
   if(!aiBridge)throw Error('AI 需要在 Electron 桌面版内使用');
   const base=C.clone(doc),mode='draft',errors=C.validate(base);if(errors.length)throw Error(errors.join('；'));
   const before=JSON.stringify({project:base.project,operations:base.operations,...(base.constraints?.length?{constraints:base.constraints}:{}),brief_fields:briefFields(base),...(base.design_standard?{project_standard:C.standardText(base)}:{})});
   const input=NbtPromptAIInput.request(mode,base.workbench?.instruction??'',sanitizedDesign(base,mode));
   input.context.baseline_binding=await NbtPromptAIInput.bindingToken(before);
   if(isCancelled())throw Error('已停止批量生成');
   const result=await aiBridge.generateWorkbench(input.instruction,input.context,{scope:'prompt:'+base.export_id});
   if(result.operation_patch)result.operations=NbtPromptAIInput.mergeOperations(base.operations,result.operation_patch);
   return adoptProposal(base,result,mode);
 }
 $('prompt-ai-apply').onclick=()=>{try{
   if(aiRunning||candidateBinding!==requestBinding()||pending.size||C.validate(state).length)throw Error('方案已改变或参数无效，请重新生成建议');
   const text=$('prompt-ai-candidate').value.trim();if(!text||text.length>60000)throw Error('填写有效的候选建议');
   if(candidateMode!=='text'){
     const next=adoptProposal(state,JSON.parse(text),candidateMode);state=next;pending.clear();renderProject();renderOperations();candidateBinding=null;$('prompt-ai-apply').disabled=true;renderCandidate();update();document.querySelector('[data-tab=project]').click();aiMessage('设计要求已采用，请逐项审查；修改会自动保存。');return;
   }
   state.aiDraft={text,binding:binding()};delete state.proposal_draft;state.workbench={...state.workbench,generated:true,status:'pending'};candidateBinding=null;$('prompt-ai-apply').disabled=true;renderCandidate();update();aiMessage('已采用设计说明，请审查完整提示词。');
 }catch(e){aiMessage(e.message,true);}};
 $('prompt-ai-reset').onclick=()=>{delete state.aiDraft;delete state.proposal_draft;candidateBinding=null;$('prompt-ai-apply').disabled=true;renderCandidate();update();document.querySelector('[data-tab=project]').click();aiMessage('现在使用手工填写的建筑要求。');};
 window.NbtPromptUI={newDraft(){return studio.addBlank()},async receive(payload){
   if(studio.busy||aiRunning)throw Error('请等待当前提示词处理完成');await autosave.flush();
   if(pending.size)throw Error('提示词中有未完成的参数，请先修复或保存');
   const same=state.project.source===payload.source;
   const next=same?C.clone(state):C.defaults();
   next.project={...next.project,name:same?next.project.name:payload.name||next.project.name,source:payload.source,size:payload.size,buildingShape:C.buildingShapes[payload.buildingShape]?payload.buildingShape:C.shapeOf({size:payload.size}),
     stage:'plan',size_policy:'fixed',contextPath:payload.contextPath||'',reviewPath:payload.reviewPath||'',output:payload.output||'',
     context:payload.context,style:payload.plan.style_note,budget:payload.budget};
   next.project.extras=(same?next.project.extras+'\n':'')+'源文件 SHA256：'+payload.source_sha256+'。本次从细节控制台载入参数，仅作规划，不代表已执行或已批准。';
   next.source_sha256=payload.source_sha256;
   next.operations=C.clone(payload.plan.operations);
   const errors=C.validate(next);if(errors.length)throw Error(errors.join('；'));
   state=next;pending.clear();renderProject();renderOperations();update();
   if(payload.constraintFolder!==undefined)refreshConstraints(payload.constraintFolder);
 }};
 if(window.parent!==window){document.body.classList.add('embedded');}
 const payload=doc=>{const cached=archivedPrompts.get(doc.export_id);if(cached?.binding===JSON.stringify(doc))return {session_id:doc.export_id,document:C.clone(cached.original.document),text:cached.original.text,plan:cached.original.plan,context:cached.original.context};const designText=doc.aiDraft?.binding===JSON.stringify({project:doc.project,operations:doc.operations,...(doc.constraints?.length?{constraints:doc.constraints}:{}),...(doc.design_standard?{project_standard:C.standardText(doc)}:{})})?doc.aiDraft.text:undefined;return {session_id:doc.export_id,document:C.clone(doc),text:C.prompt(doc,designText===undefined?{}:{designText}),plan:C.plan(doc),context:{...C.effectiveProject(doc).context,max_changed_blocks:doc.project.budget}}};
 autosave=createPromptAutosave({host:$('output-mode'),read:()=>payload(state),onSaved:result=>studio?.saved(result)});
 studio=createPromptWorkspace({remember:(id,original,doc)=>archivedPrompts.set(id,{original,binding:JSON.stringify(doc)}),document:()=>state,valid:()=>!pending.size&&!C.validate(state).length,isGenerating:()=>aiRunning,flush:()=>autosave.flush(),discard:()=>autosave.discard(),bridge:parent!==window?parent.nbtPromptStorage:null,message:notify,update,saveDocument:doc=>parent.nbtPromptStorage.save(payload(doc)),generateDocument,concurrency:async()=>(await aiBridge?.config())?.maxConcurrent??2,cancelDocument:id=>aiBridge?.cancel('prompt:'+id),instruction:text=>{$('prompt-ai-instruction').value=text},cancel:()=>aiBridge?.cancel(),restoreTask(task){$('prompt-task-handoff').hidden=!task;if(task){$('prompt-task-state').dataset.id=task.id;$('prompt-task-state').dataset.path=task.directory;$('prompt-task-state').textContent='已交接，请手动让外部助手读取。';$('prompt-task-command').textContent='python .agents/skills/nbtcreator-workspace/nbt.py prompts task --id '+task.id}},replace(doc){state=doc;pending.clear();$('prompt-ai-mode').value=state.project.stage==='draft'?'draft':'text';renderProject();renderOperations();restoreCandidate();update()},async generate(){await $('prompt-ai-generate').onclick();if(!candidateBinding)throw Error($('prompt-ai-status').textContent);$('prompt-ai-apply').onclick();if(candidateBinding)throw Error($('prompt-ai-status').textContent)}});
 window.NbtPromptUI.defaultStandards=snapshot=>{if(!studio.pristine||studio.busy||aiRunning)return;state.design_standard=C.clone(snapshot);update()};
 window.NbtPromptUI.applyStandards=async(snapshot,override='')=>{if(studio.busy||aiRunning)throw Error('请先结束当前提示词操作');await autosave.flush();if(snapshot)state.design_standard=C.clone(snapshot);else delete state.design_standard;state.design_override=override;state.workbench={...state.workbench,status:'pending'};delete state.aiDraft;delete state.proposal_draft;candidateBinding=null;restoreCandidate();update();await autosave.flush()};
 window.NbtPromptUI.standards=()=>({snapshot:state.design_standard?C.clone(state.design_standard):null,override:state.design_override??''});
 window.NbtPromptUI.constraints=()=>C.clone(state.constraints??[]);
 window.NbtPromptUI.applyConstraints=async snapshots=>{await studio.exclusive(async()=>{
   if(aiRunning)throw Error('请先结束当前提示词操作');
   if(pending.size)throw Error('请先修复未完成的参数');
   const next=C.clone(state);next.constraints=C.clone(snapshots);const errors=C.validate(next);if(errors.length)throw Error(errors.join('；'));
   if(!C.validate(state).length)await autosave.flush();state=next;state.workbench={...state.workbench,status:'pending'};delete state.aiDraft;delete state.proposal_draft;candidateBinding=null;renderProject();restoreCandidate();update();await autosave.flush();
 });renderConstraints()};
 const norms=document.createElement('button');norms.id='prompt-project-standards';norms.type='button';norms.textContent='项目设计规范';$('prompt-batch-open').after(norms);norms.onclick=()=>parent.dispatchEvent(new Event('architect-standards'));
 window.NbtPromptUI.flushExport=()=>autosave.flush();
 if(constraintStorage){
  parent.addEventListener('project-constraints-changed',event=>{if(event.detail===constraintFolder)refreshConstraints(constraintFolder)});
  parent.addEventListener('project-constraint-folder',event=>refreshConstraints(event.detail));
  parent.addEventListener('project-constraint-folders-loaded',renderConstraints);
 }
 // Keep one document navigation. Batch commands belong to the list rather
 // than competing with the current document's next action.
 const listTools=document.createElement('details');listTools.id='prompt-list-tools';listTools.innerHTML='<summary>列表工具</summary><div></div>';$('prompt-queue-list').before(listTools);listTools.querySelector('div').append($('prompt-batch-open'),$('prompt-batch-retry'),norms,$('prompt-publish-reviewed'));
 $('prompt-add').textContent='新建方案';document.querySelector('.queue-heading h2').textContent='我的方案';document.querySelector('.queue-intro').textContent='每份方案独立保存。选择一份继续编辑。';
 document.querySelector('[data-planning-step=write]').textContent='起草要求';document.querySelector('[data-planning-step=review]').textContent='编辑与审查';document.querySelector('[data-planning-step=handoff]').textContent='交接结果';
 $('prompt-advanced-toggle').textContent='建造与约束';$('prompt-more').querySelector('summary').textContent='方案操作';
 renderProject();renderOperations();update();refreshConstraints();window.NbtPromptUI.ready=studio.load();window.NbtPromptUI.ready.catch(()=>{});
})();
