(() => {
  const schema=globalThis.NbtToolCatalog.prompt_design;
  const designFields=[...Object.keys(schema.fields),'size_policy','integration'];
  function editableFields(design) {
    const selected=design.brief_scope?.editable_fields??schema.default_editable_fields;
    if(!Array.isArray(selected)||!selected.length||new Set(selected).size!==selected.length||selected.some(key=>!Object.hasOwn(schema.fields,key)))throw Error('至少勾选一项允许AI修改的设计参数');
    return [...selected];
  }
  function assertPatch(project,patch,selected) {
    if(!patch||typeof patch!=='object'||Array.isArray(patch))throw Error('设计建议格式无效');
    const allowed=new Set(selected??Object.keys(schema.fields));
    for(const [key,value]of Object.entries(patch)) {
      if(!Object.hasOwn(schema.fields,key))throw Error('方案不能修改路径、阶段或权限');
      if(!allowed.has(key)&&JSON.stringify(value)!==JSON.stringify(project[key]))throw Error('AI不能修改未勾选的设计项：'+schema.fields[key].label);
      if(key!=='size'&&typeof value==='string'&&!value.trim())throw Error('建议文字不能为空；可取消采用该项：'+schema.fields[key].label);
    }
    return patch;
  }
  function textContext(design) {
    const project = Object.fromEntries(designFields.filter(key => design.project[key] !== undefined).map(key => [key,design.project[key]]));
    const groups = new Map();
    for (const op of design.operations) {
      // Prose editing needs the tool's intent, not executable coordinates or geometry arrays.
      const intent = Object.fromEntries(['kind','label','enabled','classification','state','mode','action','scope'].filter(key => op[key] !== undefined).map(key => [key,op[key]]));
      if (op.geometry?.shape) intent.shape = op.geometry.shape;
      const key = JSON.stringify(intent);
      if (groups.has(key)) groups.get(key).steps++;
      else groups.set(key,{...intent,steps:1});
    }
    return {task:'design_prose',project,...(design.constraints?.length?{constraints:design.constraints}:{}),...(design.project_standard?{project_standard:design.project_standard}:{}),...(design.user_requirements?{user_requirements:design.user_requirements}:{}),operation_intents:[...groups.values()]};
  }
  function request(mode,instruction,design,originalText) {
    if (!['text','controls','draft'].includes(mode)) throw Error('未知 AI 方案模式');
    if (typeof instruction !== 'string' || instruction.length > 12000) throw Error('填写有效任务要求（最多12000字）');
    if (mode === 'draft') return {mode:'workbench',instruction:instruction.trim() || '请提出简明的建筑设计意图，保留人工硬条件，具体实现由执行Agent推导',context:{...design,task:'brief',operations:[],brief_scope:{editable_fields:editableFields(design)}}};
    if (mode === 'controls') return {mode:'workbench',instruction:instruction.trim() || '请完善当前建筑方案，配置合适的设计字段，保留不需要修改的工具',context:design};
    const context=textContext(design);
    if(originalText?.trim())context.original_text=originalText;
    return {mode:'prompt',instruction:instruction.trim()||(context.original_text?'润色当前说明，保留原意':'根据当前表单起草设计说明'),context};
  }
  async function bindingToken(binding) {
    const bytes = await globalThis.crypto.subtle.digest('SHA-256',new TextEncoder().encode(binding));
    return Array.from(new Uint8Array(bytes),value=>value.toString(16).padStart(2,'0')).join('');
  }
  async function externalRequest(binding,design,instruction,lockedFields) {
    const editable=editableFields(design).filter(key=>!lockedFields.includes(key));
    if(!editable.length)throw Error('请勾选至少一项未被硬条件锁定的设计参数');
    const {operations,task,brief_scope,constraints,...context}=design;
    const draft_binding=await bindingToken(binding);
    return {
      schema_version:1,draft_binding,instruction,
      ...context,...(constraints?.length?{constraints:constraints.map(({name,revision,rules})=>({name,revision,rules}))}:{}),editable_fields:editable,
      response:{schema_version:1,draft_binding,summary:'简要说明',project_patch:{}},
      rules:'只起草设计要求。按 response 格式返回纯 JSON，并原样带回 draft_binding。project_patch 只包含 editable_fields 中拟修改的字段。尊重用户原文、固定尺寸和已选约束。具体方块和工具步骤留给建模助手。'
    };
  }
  function readExternalSuggestion(raw,request) {
    if(typeof raw!=='string'||raw.length>60000)throw Error('外部建议最多 60000 字');
    let reply;
    try{reply=JSON.parse(raw);}catch{throw Error('请粘贴完整的 JSON 建议');}
    const fields=['schema_version','draft_binding','summary','project_patch'];
    if(!reply||Array.isArray(reply)||typeof reply!=='object'||Object.keys(reply).length!==fields.length||fields.some(key=>!Object.hasOwn(reply,key))||reply.schema_version!==1)
      throw Error('外部建议须符合复制请求中的返回格式');
    if(reply.draft_binding!==request.draft_binding)throw Error('这条建议属于另一份方案或旧稿，请重新复制起草请求');
    if(typeof reply.summary!=='string'||!reply.summary.trim()||reply.summary.length>1000)throw Error('外部建议需要 1–1000 字的说明');
    const patch=assertPatch(request.project,reply.project_patch,request.editable_fields);
    const keys=Object.keys(patch);
    if(!keys.length||keys.some(key=>!request.editable_fields.includes(key)))throw Error('外部建议只能包含已勾选且未锁定的设计参数');
    return {summary:reply.summary,project_patch:patch};
  }
  // Called only after the main process validates the delta and the caller
  // checks the complete local binding. Keep opaque local fields off the wire.
  function mergeOperations(operations,patch) {
    if (!patch || !Array.isArray(patch.changes) || !patch.changes.length || patch.changes.length > 16) throw Error('工具增量格式无效');
    for (const change of patch.changes) {
      if (change.action !== undefined) continue;
      if (!change.set || typeof change.set !== 'object' || Array.isArray(change.set) || Object.keys(change.set).some(key=>['__proto__','constructor','prototype','kind','overwrite','write_bounds','write_group','max_writes'].includes(key))) throw Error('增量不能修改工具权限或执行字段');
    }
    return globalThis.mergeOperationRows(operations,patch.changes).map(row=>row.op);
  }
  globalThis.NbtPromptAIInput = {textContext,request,bindingToken,mergeOperations,editableFields,assertPatch,externalRequest,readExternalSuggestion};
})();
