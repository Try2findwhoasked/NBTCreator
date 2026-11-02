(() => {
 const C=NbtPrompt, $=id=>document.getElementById(id), storage='nbt-prompt-console-v1';
 let state=C.defaults(), pending=new Map();
 try{const saved=localStorage.getItem(storage);if(saved){const candidate=JSON.parse(saved);if(!C.validate(candidate).length)state=candidate;}}catch{}
 const projectFields={name:'建筑中文名',stage:'当前阶段',source:'完整主模型路径（已有作品）',size:'整体尺寸 XYZ',footprint:'占地与空间关系',theme:'主题与氛围',purpose:'用途与玩家活动',integration:'接入方式',output:'新版本输出目录',style:'全局材质角色、构造尺度与留白',ceiling:'天花板 / 顶构要求',floor:'地板 / 平台要求',wall:'墙面 / 开口要求',props:'道具 / 细节密度',preserve:'保留项与保护要求',extras:'其他要求',budget:'精修总变化预算',contextPath:'已有坐标保护配置路径',reviewPath:'已有审阅目录（可留空）'};
 const options={stage:[['draft','新建初稿'],['plan','只读修改规划'],['refine','已有建筑精修']],integration:[['standalone','独立建筑'],['saodg','SAODG 接入']],classification:['body','wall','inherit'],mirror:[['','无'],['x','X 镜像'],['z','Z 镜像']],profile:['maintained','worn','ruined','cavern'],action:['replace','fill'],scope:['surface','volume'],shape_policy:['preserve','any']};
 function element(tag,text,cls){const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;}
 function download(name,value,type='application/json'){const blob=new Blob([typeof value==='string'?value:JSON.stringify(value,null,2)],{type});const a=element('a');a.href=URL.createObjectURL(blob);a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);}
 function notify(message,error=false){$('status').textContent=message;$('status').classList.toggle('error',error);}
 function binding(){return JSON.stringify({project:state.project,operations:state.operations});}
 function aiDraft(){return state.aiDraft&&typeof state.aiDraft.text==='string'&&state.aiDraft.text.length<=60000&&state.aiDraft.binding===binding()?state.aiDraft:null;}
 function composeAI(text){const base=C.prompt(state);return base.slice(0,base.indexOf('# 全局设计与细节要求'))+'# 全局设计与细节要求（AI 建议，待审阅）\n'+text+'\n\n'+base.slice(base.indexOf('# 阶段执行边界'));}
 function outputText(){return aiDraft()?composeAI(aiDraft().text):C.prompt(state);}
 function update(){const errors=[...pending.values(),...C.validate(state)];const invalid=errors.length>0;for(const id of ['copy','markdown','plan','config','save'])$(id).disabled=invalid;
   $('result').value=invalid?'参数尚未有效，请先修正：\n'+errors.join('\n'):outputText();notify(invalid?errors.join('\n'):`${state.operations.length} 个步骤 · 参数草案有效 · 尚未验证模型`,invalid);$('count').textContent=state.operations.length;
   $('output-mode').textContent=aiDraft()?'当前导出：AI 设计建议 + 本地任务元数据、工具计划与验证要求':state.aiDraft?'方案已变化，当前导出参数生成稿；AI 建议需重新生成或重新审阅':'当前导出：参数生成稿';
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
 function renderProject(){const host=$('project-fields');host.replaceChildren();for(const [key,label]of Object.entries(projectFields))field(host,key,state.project[key],v=>state.project[key]=v,{label,token:'project.'+key,wide:['theme','purpose','style','ceiling','floor','wall','props','preserve','extras','source','output','contextPath','reviewPath','footprint'].includes(key)});$('context-json').value=JSON.stringify(state.project.context,null,2);}
 function renderOperations(){const host=$('operations');host.replaceChildren();if(!state.operations.length)host.append(element('p','尚未添加工具。可以先只填写建筑要求，由 Agent 按需选择。','empty'));
   state.operations.forEach((op,i)=>{const card=element('article',undefined,'step');card.dataset.step=i;const header=element('div',undefined,'step-head');header.append(element('strong',`${String(i+1).padStart(2,'0')}  ${C.catalog[op.kind][0]}`));
     for(const [text,action,disabled]of [['↑',()=>{[state.operations[i-1],state.operations[i]]=[op,state.operations[i-1]];},i===0],['↓',()=>{[state.operations[i+1],state.operations[i]]=[op,state.operations[i+1]];},i===state.operations.length-1],['复制',()=>state.operations.splice(i+1,0,C.clone(op)),false],['删除',()=>state.operations.splice(i,1),false]]){const b=element('button',text);b.disabled=disabled;b.onclick=()=>{if(pending.size){notify('请先修复未完成的参数，再调整步骤',true);return;}action();renderOperations();update();};header.append(b);}card.append(header,element('p',C.catalog[op.kind][2],'hint'));
     const fields=element('div',undefined,'fields');
     if(op.kind==='geometry'){const label=element('label','几何类型'),sel=element('select');sel.dataset.field='shape';for(const shape of Object.keys(C.shapes)){const o=element('option',shape);o.value=shape;sel.append(o);}sel.value=op.geometry.shape;sel.onchange=()=>{op.geometry={shape:sel.value,...C.clone(C.shapes[sel.value])};pending.delete(`op.${i}.geometry`);renderOperations();update();};label.append(sel);fields.append(label);}
     for(const [key,value]of Object.entries(op)){if(key==='kind')continue;field(fields,key,value,v=>{op[key]=v;},{kind:op.kind,token:`op.${i}.${key}`,wide:key==='label'});}card.append(fields);
     const details=element('details');details.append(element('summary','高级：编辑本步骤完整 JSON（可补充可选参数）'));const raw=element('textarea');raw.className='json';raw.value=JSON.stringify(op,null,2);raw.setAttribute('aria-label','本步骤完整 JSON');details.ontoggle=()=>{if(details.open)raw.value=JSON.stringify(op,null,2);};const apply=element('button','应用步骤 JSON');apply.onclick=()=>{try{const value=JSON.parse(raw.value);const candidate=C.clone(state);candidate.operations[i]=value;const errors=C.validate(candidate);if(errors.length)throw Error(errors.join('；'));state=candidate;for(const k of pending.keys())if(k.startsWith(`op.${i}.`))pending.delete(k);renderOperations();update();}catch(e){notify('步骤 JSON：'+e.message,true);}};details.append(raw,apply);card.append(details);host.append(card);
   });
 }
 for(const [kind,[label]]of Object.entries(C.catalog)){const o=element('option',label);o.value=kind;$('kind').append(o);}
 $('add').onclick=()=>{if(pending.size){notify('请先修复未完成的参数',true);return;}state.operations.push(C.operation($('kind').value));renderOperations();update();};
 document.querySelectorAll('[data-tab]').forEach(b=>b.onclick=()=>{document.querySelectorAll('[data-tab]').forEach(x=>x.classList.toggle('active',x===b));document.querySelectorAll('.tab').forEach(x=>x.hidden=x.id!==b.dataset.tab);});
 $('context-json').oninput=()=>{try{const v=JSON.parse($('context-json').value);if(!v||typeof v!=='object'||Array.isArray(v))throw Error('上下文须为对象');state.project.context=v;pending.delete('context');$('context-error').textContent='';}catch(e){pending.set('context','上下文JSON无效：'+e.message);$('context-error').textContent=e.message;}update();};
 $('save').onclick=()=>download('nbt_prompt_settings.json',state);
 $('markdown').onclick=()=>download('NBT建模完整提示词.md',outputText(),'text/markdown;charset=utf-8');
 $('plan').onclick=()=>download('plan.json',C.plan(state));
 $('config').onclick=()=>download('context_draft.json',{...state.project.context,max_changed_blocks:state.project.budget});
 $('copy').onclick=async()=>{try{if(navigator.clipboard?.writeText)await navigator.clipboard.writeText($('result').value);else throw Error('fallback');notify('完整提示词已复制');}catch{$('result').focus();$('result').select();notify(document.execCommand('copy')?'完整提示词已复制':'已选中提示词，请按 Ctrl+C');}};
 $('import').onclick=()=>$('file').click();$('file').onchange=async()=>{const f=$('file').files[0];if(!f)return;try{const v=JSON.parse(await f.text());const candidate={...C.defaults(),...v,project:{...C.defaults().project,...v.project}};const errors=C.validate(candidate);if(errors.length)throw Error(errors.join('；'));state=candidate;pending.clear();renderProject();renderOperations();update();}catch(e){notify('导入失败：'+e.message,true);}finally{$('file').value='';}};
 $('reset').onclick=()=>{if(!confirm('重置当前方案？未导出的修改将清除。'))return;state=C.defaults();pending.clear();renderProject();renderOperations();update();};
 let aiBridge=null,candidateBinding=null,aiRunning=false;
 try{if(window.parent!==window&&window.parent.location.origin===location.origin)aiBridge=window.parent.nbtPromptAI;}catch{}
 function aiMessage(text,error=false){$('prompt-ai-status').textContent=text;$('prompt-ai-status').classList.toggle('error',error);}
 function aiLock(value){aiRunning=value;$('prompt-ai-generate').disabled=value;$('prompt-ai-cancel').disabled=!value;$('prompt-ai-settings').disabled=value;}
 async function refreshAI(){
   if(!aiBridge){$('prompt-ai-indicator').textContent='离线编辑模式';aiMessage('在 NBTCreator 桌面细节控制台内打开本页，可使用共用 API；当前仍可离线编辑和导出。');return;}
   try{const c=await aiBridge.config();$('prompt-ai-indicator').textContent=c.enabled?'API 已启用':'API 未启用';if(!c.enabled)aiMessage('请先通过“API 设置”启用并保存连接。');}catch(e){aiMessage(e.message,true);}
 }
 $('prompt-ai-open').onclick=()=>{$('prompt-ai-panel').open=true;refreshAI();};
 $('prompt-ai-settings').onclick=()=>{if(aiBridge)aiBridge.settings();else aiMessage('API 设置在 Electron 桌面版主界面右上角提供。',true);};
 function sanitizedDesign(){
   const p=state.project,keys=['name','stage','size','footprint','theme','purpose','integration','style','ceiling','floor','wall','props','preserve','budget'];
   const project=Object.fromEntries(keys.map(k=>[k,p[k]]));
   project.extras=String(p.extras??'').split('\n').filter(line=>!line.startsWith('源文件 SHA256：')).join('\n');
   const allowed=new Set(['kind','label','classification','lo','hi','geometry','mode','state','from_states','seed','max_writes','offset','count','destination','quarter_turns','mirror','move','include_air','overwrite','iterations','seeds','steps','decay','surface_only','centre','radius','roughness','rays','ray_length','ray_width','fraction','spacing','supported','action','scope','scale','palette','preserve_properties','shape_policy','profile','style_note','slab_share','patch_size','pit_depth','route_margin','exclude_boxes','include_boxes','slab_overrides','moss','cracks','floor','thickness','width','start','end']);
   return {project,operations:state.operations.map(op=>Object.fromEntries(Object.entries(op).filter(([key])=>allowed.has(key))))};
 }
 $('prompt-ai-generate').onclick=async()=>{
   if(aiRunning)return;
   try{
     if(!aiBridge)throw Error('AI 需要在 Electron 桌面版内使用');
     if(pending.size||C.validate(state).length)throw Error('请先修正当前方案参数');
     const before=binding();candidateBinding=null;$('prompt-ai-apply').disabled=true;
     const instruction='请基于下面的建筑设计草案，生成可供审阅的中文设计要求段落，补足天花承托、地板分区、墙面层次、交接收口与细节主次。保留主题、布局和已给定工具意图，不输出新坐标、不声称已执行或已批准；不必重复技术命令，因为应用将保留本地阶段规则、工具计划、保护配置和交付要求。\n用户补充：'+$('prompt-ai-instruction').value+'\n设计草案 JSON：\n'+JSON.stringify(sanitizedDesign());
     if(instruction.length>12000)throw Error('方案较大，请减少工具序列或缩短设计要求后再调用 AI');
     aiLock(true);aiMessage('正在根据当前设计要求生成建议…');
     const result=await aiBridge.generate(instruction);
     if(binding()!==before)throw Error('生成期间方案已改变，请基于当前方案重新生成');
     if(result.mode!=='prompt'||typeof result.text!=='string'||!result.text.trim())throw Error('AI 返回内容无效');
     $('prompt-ai-candidate').value=result.text;candidateBinding=before;$('prompt-ai-apply').disabled=false;aiMessage('建议已生成，可编辑后采用；当前导出内容尚未改变。');
   }catch(e){aiMessage(e.message,true);}finally{aiLock(false);}
 };
 $('prompt-ai-cancel').onclick=()=>aiBridge?.cancel();
 $('prompt-ai-apply').onclick=()=>{try{
   if(aiRunning||candidateBinding!==binding()||pending.size||C.validate(state).length)throw Error('方案已改变或参数无效，请重新生成建议');
   const text=$('prompt-ai-candidate').value.trim();if(!text||text.length>60000)throw Error('填写有效的候选建议');
   state.aiDraft={text,binding:binding()};update();aiMessage('已采用 AI 设计建议；工具计划、任务元数据、阶段与保护要求沿用本地方案。');
 }catch(e){aiMessage(e.message,true);}};
 $('prompt-ai-reset').onclick=()=>{delete state.aiDraft;update();aiMessage('已切回参数生成稿；表单和工具序列保持。');};
 window.NbtPromptUI={receive(payload){
   if(pending.size)throw Error('提示词中有未完成的参数，请先修复或保存');
   const same=state.project.source===payload.source;
   const next=same?C.clone(state):C.defaults();
   next.project={...next.project,name:same?next.project.name:payload.name||next.project.name,source:payload.source,size:payload.size,
     stage:'plan',contextPath:payload.contextPath||'',reviewPath:payload.reviewPath||'',output:payload.output||'',
     context:payload.context,style:payload.plan.style_note,budget:payload.budget};
   next.project.extras=(same?next.project.extras+'\n':'')+'源文件 SHA256：'+payload.source_sha256+'。本次从细节控制台载入参数，仅作规划，不代表已执行或已批准。';
   next.operations=C.clone(payload.plan.operations);
   const errors=C.validate(next);if(errors.length)throw Error(errors.join('；'));
   state=next;pending.clear();renderProject();renderOperations();update();
 }};
 if(window.parent!==window){document.body.classList.add('embedded');}
 renderProject();renderOperations();update();
})();
