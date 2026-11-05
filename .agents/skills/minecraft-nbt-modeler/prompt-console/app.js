(() => {
 const C=NbtPrompt, $=id=>document.getElementById(id), storage='nbt-prompt-console-v2';
 let state=C.defaults(), pending=new Map(),autosave;
 try{const saved=localStorage.getItem(storage);if(saved){const candidate=C.normalize(JSON.parse(saved));if(!C.validate(candidate).length)state=candidate;}}catch{}
 const projectFields={name:'建筑中文名',stage:'任务方式',buildingShape:'建筑形状（选择后自动填尺寸与占地）',source:'完整主模型路径（已有作品）',size:'整体尺寸 XYZ',footprint:'占地与空间关系',layout:'空间分区、楼层与高差',circulation:'玩家动线与空间连接',theme:'主题与氛围',purpose:'用途与玩家活动',integration:'接入方式',output:'新版本输出目录',style:'全局材质角色、构造尺度与留白',ceiling:'天花板 / 顶构要求',floor:'地板 / 平台要求',wall:'墙面 / 开口要求',props:'道具 / 细节密度',preserve:'保留项与保护要求',extras:'其他要求',budget:'精修总变化预算',contextPath:'已有坐标保护配置路径',reviewPath:'已有审阅目录（可留空）'};
 const options={buildingShape:Object.entries(C.buildingShapes).map(([k,v])=>[k,v.label]),stage:[['draft','首次创建完整初稿'],['plan','只读修改规划'],['refine','已有建筑精修']],integration:[['standalone','独立建筑'],['saodg','SAODG 接入']],classification:['body','wall','inherit'],mirror:[['','无'],['x','X 镜像'],['z','Z 镜像']],profile:['maintained','worn','ruined','cavern'],action:['replace','fill'],scope:['surface','volume'],shape_policy:['preserve','any']};
 function element(tag,text,cls){const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;}
 function download(name,value,type='application/json'){const blob=new Blob([typeof value==='string'?value:JSON.stringify(value,null,2)],{type});const a=element('a');a.href=URL.createObjectURL(blob);a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);}
 function notify(message,error=false){$('status').textContent=message;$('status').classList.toggle('error',error);}
 function binding(){return JSON.stringify({project:state.project,operations:state.operations});}
 function aiDraft(){return state.aiDraft&&typeof state.aiDraft.text==='string'&&state.aiDraft.text.length<=60000&&state.aiDraft.binding===binding()?state.aiDraft:null;}
 function composeAI(text){const base=C.prompt(state);return base.slice(0,base.indexOf('# 全局设计与细节要求'))+'# 全局设计与细节要求（AI 建议，待审阅）\n'+text+'\n\n'+base.slice(base.indexOf('# 自动存放规则'));}
 function outputText(){return aiDraft()?composeAI(aiDraft().text):C.prompt(state);}
 function update(){if(state.project.stage==='draft'){state.project.output=C.outputPath(state.project);const output=document.querySelector('[data-field=output]');if(output)output.value=state.project.output;}const errors=[...pending.values(),...C.validate(state)];const invalid=errors.length>0;for(const id of ['copy','markdown','plan','config','save','left-save'])$(id).disabled=invalid;
   $('result').value=invalid?'参数尚未有效，请先修正：\n'+errors.join('\n'):outputText();notify(invalid?errors.join('\n'):state.operations.length?`${state.operations.filter(op=>op.enabled!==false).length} 个启用 / ${state.operations.length} 个高级步骤 · 供接收 Agent 核对`:'提示词草稿有效，可保存任务并交接给 Agent',invalid);$('count').textContent=state.operations.length;
   $('output-mode').textContent=aiDraft()?'当前导出：AI 设计建议 + 本地任务元数据、工具计划与验证要求':state.aiDraft?'方案已变化，当前导出参数生成稿；AI 建议需重新生成或重新审阅':'当前导出：参数生成稿';
   if(!state.export_id)state.export_id=crypto.randomUUID().replaceAll('-','');
   autosave?.schedule(!invalid);
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
 function renderProject(){
   const host=$('project-fields'),draft=state.project.stage==='draft';host.replaceChildren();
   for(const [key,label]of Object.entries(projectFields)){
     if(draft&&['source','contextPath','reviewPath','budget'].includes(key))continue;
     const input=field(host,key,key==='output'?C.outputPath(state.project):state.project[key],v=>{
       if(key==='buildingShape')C.applyShape(state.project,v);else state.project[key]=v;
       if(key==='stage'&&v==='draft'){state.project.source='';state.project.contextPath='';state.project.reviewPath='';state.project.context=C.defaults().project.context;}
       if(['buildingShape','stage'].includes(key))renderProject();
     },{label:key==='output'&&draft?'自动归档目录（相对当前工作区）':label,token:'project.'+key,wide:['theme','purpose','style','ceiling','floor','wall','props','preserve','extras','source','output','contextPath','reviewPath','footprint','layout','circulation'].includes(key)});
     if(key==='output'&&draft){input.readOnly=true;input.classList.add('auto-path');const hint=element('small','由 Agent 按 skill 规范新建日期版本，自动保存主模型、NBT、图像和验证资料；无需填写绝对路径。','field-help');input.parentElement.append(hint);}
     if(key==='buildingShape'&&!draft)input.disabled=true;
   }
   $('context-json').value=JSON.stringify(state.project.context,null,2);
   const draftOption=$('prompt-ai-mode').querySelector('[value=draft]');draftOption.disabled=!draft;
   if(!draft&&$('prompt-ai-mode').value==='draft')$('prompt-ai-mode').value='text';
   $('project-intro').textContent=draft?'用于首次创建模型。选择形状带出尺寸和占地，再完善主题、空间与细节；示例可改，不会强制套用固定房型。':'这是已有建筑的方案。源、保护和确认沿用所选版本；想新做建筑，请点击上方“新建初稿”。';
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
 document.querySelectorAll('[data-tab]').forEach(b=>b.onclick=()=>{document.querySelectorAll('[data-tab]').forEach(x=>x.classList.toggle('active',x===b));document.querySelectorAll('.tab').forEach(x=>x.hidden=x.id!==b.dataset.tab);});
 $('context-json').oninput=()=>{try{const v=JSON.parse($('context-json').value);if(!v||typeof v!=='object'||Array.isArray(v))throw Error('上下文须为对象');state.project.context=v;pending.delete('context');$('context-error').textContent='';}catch(e){pending.set('context','上下文JSON无效：'+e.message);$('context-error').textContent=e.message;}update();};
 $('save').onclick=()=>download('nbt_prompt_settings.json',state);
 $('left-read').onclick=()=>$('import').click();
 $('left-save').onclick=async()=>{
  const button=$('left-save');button.disabled=true
  try{
   if(pending.size||C.validate(state).length)throw Error('请先修正当前参数，再保存任务')
   const saved=await autosave.flush()
   if(!saved||!parent.nbtPromptStorage?.publish)throw Error('保存任务需要在工作区桌面版中使用')
   if(pending.size||C.validate(state).length)throw Error('参数已变化，请修正后重新保存任务')
   const task=await parent.nbtPromptStorage.publish({index:saved.index,id:saved.id,revision:saved.revision})
   const status=$('prompt-task-state');status.dataset.id=task.id;status.dataset.path=task.directory;status.textContent='任务已保存：'+task.directory;status.title=task.directory
   $('prompt-task-command').textContent='python .agents/skills/nbtcreator-workspace/nbt.py prompts task --id '+task.id
   $('prompt-task-handoff').hidden=false;notify(task.unchanged?'该任务已保存，未重复创建文件夹':'任务目录已创建，提示词和方案已保存，可交给外部 Agent')
  }catch(error){notify(error.message,true)}finally{button.disabled=pending.size>0||C.validate(state).length>0}
 };
 $('prompt-task-copy').onclick=async()=>{try{await navigator.clipboard.writeText($('prompt-task-command').textContent);notify('Agent读取命令已复制')}catch{notify($('prompt-task-command').textContent)}}
 $('markdown').onclick=()=>download('NBT建模完整提示词.md',outputText(),'text/markdown;charset=utf-8');
 $('plan').onclick=()=>download('plan.json',C.plan(state));
 $('config').onclick=()=>download('context_draft.json',{...state.project.context,max_changed_blocks:state.project.budget});
 $('copy').onclick=async()=>{try{await autosave?.flush();if(navigator.clipboard?.writeText)await navigator.clipboard.writeText($('result').value);else throw Error('fallback');notify('完整提示词已复制');}catch{$('result').focus();$('result').select();notify(document.execCommand('copy')?'完整提示词已复制':'已选中提示词，请按 Ctrl+C');}};
 $('import').onclick=()=>$('file').click();$('file').onchange=async()=>{const f=$('file').files[0];if(!f)return;try{const v=JSON.parse(await f.text());const candidate=C.normalize(v);const errors=C.validate(candidate);if(errors.length)throw Error(errors.join('；'));state=candidate;pending.clear();renderProject();renderOperations();update();}catch(e){notify('导入失败：'+e.message,true);}finally{$('file').value='';}};
 $('reset').onclick=()=>{if(!confirm('重置当前方案？未导出的修改将清除。'))return;state=C.defaults();pending.clear();renderProject();renderOperations();update();};
 let aiBridge=null,candidateBinding=null,aiRunning=false,candidateMode='text';
 try{if(window.parent!==window&&window.parent.location.origin===location.origin)aiBridge=window.parent.nbtPromptAI;}catch{}
 function aiMessage(text,error=false){$('prompt-ai-status').textContent=text;$('prompt-ai-status').classList.toggle('error',error);}
 function aiLock(value){aiRunning=value;$('prompt-ai-mode').disabled=value;$('prompt-ai-generate').disabled=value;$('prompt-ai-cancel').disabled=!value;$('prompt-ai-settings').disabled=value;}
 $('prompt-ai-mode').onchange=()=>{candidateBinding=null;$('prompt-ai-apply').disabled=true;aiMessage('已切换AI模式，请重新生成候选方案。');}
 async function refreshAI(){
   if(!aiBridge){$('prompt-ai-indicator').textContent='离线编辑模式';aiMessage('在 NBTCreator 桌面细节控制台内打开本页，可使用共用 API；当前仍可离线编辑和导出。');return;}
   try{const c=await aiBridge.config();$('prompt-ai-indicator').textContent=c.enabled?'API 已启用':'API 未启用';if(!c.enabled)aiMessage('请先通过“API 设置”启用并保存连接。');}catch(e){aiMessage(e.message,true);}
 }
 document.querySelector('[data-tab=ai]').addEventListener('click',refreshAI);refreshAI();
 $('prompt-ai-references').onclick=()=>{const flow=$('prompt-ai-mode').value==='draft'?'draft':$('prompt-ai-mode').value==='text'?'prompt':'workbench';const picker=window.parent?.nbtReferencePicker;if(picker)picker.open({workflow:flow,query:$('prompt-ai-instruction').value}).catch(error=>aiMessage(error.message,true));else aiMessage('本地检索在桌面版工作区提供',true)};
 $('prompt-ai-settings').onclick=()=>{if(aiBridge)aiBridge.settings();else aiMessage('API 设置在 Electron 桌面版主界面右上角提供。',true);};
 function sanitizedDesign(){
   const p=state.project,keys=['name','buildingShape','layout','circulation','stage','size','footprint','theme','purpose','integration','style','ceiling','floor','wall','props','preserve','budget'];
   const project=Object.fromEntries(keys.map(k=>[k,p[k]]));
   project.extras=String(p.extras??'').split('\n').filter(line=>!line.startsWith('源文件 SHA256：')).join('\n');
   const allowed=new Set(['kind','label','enabled','classification','lo','hi','geometry','mode','state','from_states','seed','max_writes','offset','count','destination','quarter_turns','mirror','move','include_air','overwrite','iterations','seeds','steps','decay','surface_only','centre','radius','roughness','rays','ray_length','ray_width','fraction','spacing','supported','action','scope','scale','palette','preserve_properties','shape_policy','profile','style_note','slab_share','patch_size','pit_depth','route_margin','exclude_boxes','include_boxes','slab_overrides','moss','cracks','floor','thickness','width','start','end']);
   return {project,task:$('prompt-ai-mode').value==='draft'?'draft':'controls',existing_model:!!p.source,operations:state.operations.map(op=>Object.fromEntries(Object.entries(op).filter(([key])=>allowed.has(key))))};
 }
 $('prompt-ai-generate').onclick=async()=>{
   if(aiRunning)return;
   try{
     if(!aiBridge)throw Error('AI 需要在 Electron 桌面版内使用');
     if(pending.size||C.validate(state).length)throw Error('请先修正当前方案参数');
     const before=binding();candidateBinding=null;$('prompt-ai-apply').disabled=true;
     const mode=$('prompt-ai-mode').value;
     const input=NbtPromptAIInput.request(mode,$('prompt-ai-instruction').value,sanitizedDesign());
     aiLock(true);aiMessage('正在根据当前设计要求生成建议…');
     candidateMode=mode;
     if(candidateMode==='draft'&&(state.project.stage!=='draft'||state.project.source))throw Error('请先点击“新建初稿”，再生成完整初稿方案');
     if(input.mode==='workbench'){input.context.baseline_binding=await NbtPromptAIInput.bindingToken(before);if(binding()!==before)throw Error('方案已改变，请重新生成候选')}
     let result=input.mode==='workbench'?await aiBridge.generateWorkbench(input.instruction,input.context):await aiBridge.generate(input.instruction);
     window.parent?.nbtReferencePicker?.sources($('prompt-ai-sources'),result);
     if(binding()!==before)throw Error('生成期间方案已改变，请基于当前方案重新生成');
     if(result.operation_patch)result={...result,operations:NbtPromptAIInput.mergeOperations(state.operations,result.operation_patch)};
     if(candidateMode==='text'&&(result.mode!=='prompt'||typeof result.text!=='string'||!result.text.trim()))throw Error('AI 返回内容无效');
     $('prompt-ai-candidate').value=candidateMode!=='text'?JSON.stringify({summary:result.summary,project_patch:result.project_patch,operations:result.operations},null,2):result.text;candidateBinding=before;$('prompt-ai-apply').disabled=false;aiMessage(candidateMode!=='text'?'完整候选方案已生成，审阅JSON后点击采用，即可回填左侧。':'建议已生成，可编辑后采用；当前导出内容尚未改变。');
   }catch(e){aiMessage(e.message,true);}finally{aiLock(false);}
 };
 $('prompt-ai-cancel').onclick=()=>aiBridge?.cancel();
 $('prompt-ai-apply').onclick=()=>{try{
   if(aiRunning||candidateBinding!==binding()||pending.size||C.validate(state).length)throw Error('方案已改变或参数无效，请重新生成建议');
   const text=$('prompt-ai-candidate').value.trim();if(!text||text.length>60000)throw Error('填写有效的候选建议');
   if(candidateMode!=='text'){
     const proposal=JSON.parse(text),patch=proposal.project_patch??{},allowed=['buildingShape','layout','circulation','name','theme','purpose','footprint','style','ceiling','floor','wall','props','preserve','extras','size'];
     if(Object.keys(patch).some(key=>!allowed.includes(key)))throw Error('方案不能改写路径、阶段、预算或保护字段');
     if(state.project.source&&patch.size&&JSON.stringify(patch.size)!==JSON.stringify(state.project.size))throw Error('已有模型的尺寸保持不变');
     const next=C.clone(state);if(patch.buildingShape){if(!C.buildingShapes[patch.buildingShape]||state.project.source&&patch.buildingShape!==state.project.buildingShape)throw Error('建筑形状无效，或已有模型形状不能由 AI 改写');C.applyShape(next.project,patch.buildingShape);}for(const [key,value]of Object.entries(patch)){if(key!=='size'&&(typeof value!=='string'||value.length>4000))throw Error('设计字段需为有效文字');next.project[key]=value;}
     if(proposal.operations!==undefined)next.operations=proposal.operations;
     if(candidateMode==='draft'){
       for(const key of ['name','theme','purpose','layout','circulation','style','ceiling','floor','wall','props'])if(typeof patch[key]!=='string'||!patch[key].trim())throw Error('完整初稿需补齐：'+(projectFields[key]||key));
       if(proposal.operations!==undefined&&(!Array.isArray(proposal.operations)||proposal.operations.length))throw Error('提示词编写只采用设计要求；具体工具步骤请使用高级工具模式');
     }
     const errors=C.validate(next);if(errors.length)throw Error(errors.join('；'));delete next.aiDraft;state=next;pending.clear();renderProject();renderOperations();update();candidateBinding=null;$('prompt-ai-apply').disabled=true;document.querySelector('[data-tab=project]').click();aiMessage(candidateMode==='draft'?'完整初稿方案已回填；复制提示词交给 Agent 制作，尚未生成 NBT。':'已回填左侧设计控件和工具序列；未改动源路径、保护配置或批准状态。');return;
   }
   state.aiDraft={text,binding:binding()};update();aiMessage('已采用 AI 设计建议；工具计划、任务元数据、阶段与保护要求沿用本地方案。');
 }catch(e){aiMessage(e.message,true);}};
 $('prompt-ai-reset').onclick=()=>{delete state.aiDraft;update();aiMessage('已切回参数生成稿；表单和工具序列保持。');};
 window.NbtPromptUI={newDraft(){
   try{localStorage.setItem(storage+'-previous',JSON.stringify(state));}catch{}
   state=C.defaults();pending.clear();candidateBinding=null;$('prompt-ai-mode').value='draft';$('prompt-ai-apply').disabled=true;
   renderProject();renderOperations();update();document.querySelector('[data-tab=ai]').click();notify('已新建初稿方案；上一份表单已在本浏览器暂存备份。');
 },receive(payload){
   if(pending.size)throw Error('提示词中有未完成的参数，请先修复或保存');
   const same=state.project.source===payload.source;
   const next=same?C.clone(state):C.defaults();
   next.project={...next.project,name:same?next.project.name:payload.name||next.project.name,source:payload.source,size:payload.size,buildingShape:C.buildingShapes[payload.buildingShape]?payload.buildingShape:C.shapeOf({size:payload.size}),
     stage:'plan',contextPath:payload.contextPath||'',reviewPath:payload.reviewPath||'',output:payload.output||'',
     context:payload.context,style:payload.plan.style_note,budget:payload.budget};
   next.project.extras=(same?next.project.extras+'\n':'')+'源文件 SHA256：'+payload.source_sha256+'。本次从细节控制台载入参数，仅作规划，不代表已执行或已批准。';
   next.source_sha256=payload.source_sha256;
   next.operations=C.clone(payload.plan.operations);
   const errors=C.validate(next);if(errors.length)throw Error(errors.join('；'));
   state=next;pending.clear();renderProject();renderOperations();update();
 }};
 if(window.parent!==window){document.body.classList.add('embedded');}
 autosave=createPromptAutosave({host:$('output-mode'),read:()=>({session_id:state.export_id,document:C.clone(state),text:outputText(),plan:C.plan(state),context:{...state.project.context,max_changed_blocks:state.project.budget}})});
 window.NbtPromptUI.flushExport=()=>autosave.flush();
 renderProject();renderOperations();update();
})();
