export function initInternalAISettings(dialog,knowledge){
 const bridge=window.nbtDesktop
 const tabs=document.createElement('nav');tabs.className='ai-settings-tabs';tabs.innerHTML='<button type="button" id="internal-ai-tab" aria-pressed="true">内部 AI · API / 工作流 / 资料</button><button type="button" id="external-skill-tab" aria-pressed="false">对外 Skill · Agent 知识暴露</button>'
 dialog.querySelector('.ai-heading').after(tabs)
 const panel=document.createElement('section');panel.className='internal-ai-settings'
 panel.innerHTML='<h3>内部 AI 工作流</h3><p class="muted">这些配置提供给应用调用的 API 模型，和右侧“对外 Skill”独立。每个位置可使用不同规则和资料；保存配置不联网，点击生成时才发送该工作流选中的内容。</p><label>使用位置 / 工作流<select id="internal-flow"></select></label><p id="internal-flow-steps" class="workflow-steps"></p><label>工作流补充要求<textarea id="internal-flow-instruction" maxlength="6000" rows="3" placeholder="例如：先说明布局，再列构件步骤；优先使用工作区指定的建筑风格。"></textarea></label><label>Rule 规范<textarea id="internal-flow-rules" maxlength="12000" rows="5"></textarea></label><p class="muted">可补充设计和表达要求；工具协议、选区、源保护和真实确认仍由应用校验。</p><h4>本流程使用的内部资料库</h4><div id="internal-knowledge"></div><div class="ai-buttons"><button id="internal-import" type="button">添加内部资料…</button><button id="internal-save" class="primary" type="button">保存全部工作流</button><button id="internal-refresh" type="button">重新读取</button></div><p id="internal-status" role="status"></p>'
 dialog.querySelector('.ai-layout').append(panel)
 const $=id=>document.getElementById(id);let config,current
 function message(text){$('internal-status').textContent=text}
 function capture(){if(!config||!current)return;config.workflows[current]={rules:$('internal-flow-rules').value,instruction:$('internal-flow-instruction').value,knowledge:[...panel.querySelectorAll('[data-internal-knowledge]:checked')].map(e=>e.dataset.internalKnowledge)}}
 function render(){current=$('internal-flow').value;const f=config.workflows[current];$('internal-flow-steps').textContent=config.flows[current].steps;$('internal-flow-instruction').value=f.instruction;$('internal-flow-rules').value=f.rules;const list=$('internal-knowledge');list.replaceChildren()
  for(const [id,doc]of [...Object.entries(config.builtins),...config.documents.map(d=>[d.id,d])]){const label=document.createElement('label');label.className='knowledge-choice inline';const input=document.createElement('input');input.type='checkbox';input.dataset.internalKnowledge=id;input.checked=f.knowledge.includes(id);label.append(input,document.createTextNode(doc.label+(id.startsWith('builtin:')?'（内置）':'（导入）')));list.append(label)}
 }
 async function load(value){config=value??await bridge.internalAIConfig();const previous=current;$('internal-flow').replaceChildren();for(const [key,f]of Object.entries(config.flows)){const o=document.createElement('option');o.value=key;o.textContent=f.label;$('internal-flow').append(o)}if(config.flows[previous])$('internal-flow').value=previous;render()}
 function select(external){dialog.dataset.settingsScope=external?'external':'internal';knowledge.hidden=!external;panel.hidden=external;dialog.querySelector('.ai-config').hidden=external;$('internal-ai-tab').setAttribute('aria-pressed',String(!external));$('external-skill-tab').setAttribute('aria-pressed',String(external))}
 $('internal-ai-tab').onclick=()=>select(false);$('external-skill-tab').onclick=()=>select(true)
 $('internal-flow').onchange=()=>{capture();render()}
 $('internal-refresh').onclick=()=>load().then(()=>message('已读取当前工作区的内部 AI 配置')).catch(e=>message(e.message))
 $('internal-save').onclick=async()=>{try{capture();await load(await bridge.internalAISave({workflows:config.workflows}));message('全部工作流已保存；仅生成时发送选中的资料。')}catch(e){message(e.message)}}
 $('internal-import').onclick=async()=>{try{capture();await bridge.internalAISave({workflows:config.workflows});const data=await bridge.internalAIImport();if(data)await load(data);message('资料已加入内部库；勾选所需工作流并保存后才会发送。')}catch(e){message(e.message)}}
 select(false);load().catch(e=>message(e.message))
}
