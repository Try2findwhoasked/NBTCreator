(() => {
  const designFields = ['name','buildingShape','size','footprint','theme','purpose','layout','circulation','style','ceiling','floor','wall','props','preserve','extras'];
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
    return {project,...(design.project_standard?{project_standard:design.project_standard}:{}),operation_count:design.operations.length,operation_intents:[...groups.values()]};
  }
  function request(mode,instruction,design) {
    if (!['text','controls','draft'].includes(mode)) throw Error('未知 AI 方案模式');
    if (typeof instruction !== 'string' || instruction.length > 12000) throw Error('填写有效任务要求（最多12000字）');
    if (mode === 'draft') return {mode:'workbench',instruction:instruction.trim() || '请完善建筑要求，编写交接给下一个Agent的提示词，不实施建模',context:{...design,task:'brief',operations:[]}};
    if (mode === 'controls') return {mode:'workbench',instruction:instruction.trim() || '请完善当前建筑方案，配置合适的设计字段，保留不需要修改的工具',context:design};
    const text = '请基于下面的建筑设计草案，生成可供审阅的中文设计要求段落。采用面向对象的建筑设计：围绕关键空间、构件与环境对象，表达用途、特征、包含和连接关系、共同约束；顶构、地板、墙面和道具只说明职责与设计意图，保留实现自由，不擅自补具体数量、间距、方块配方或施工顺序。用户明确指定的细节和约束原样保留；明确要求详细时再展开。保留主题、布局和已给定工具意图，不输出新坐标、不声称已执行或已批准；不必重复技术命令，因为应用将保留本地阶段规则、工具计划、保护配置和交付要求。正文建议600字以内，用户明确要求更详细时以用户要求为准，不复述工具摘要。\n用户补充：'+instruction+'\n设计草案摘要 JSON：\n'+JSON.stringify(textContext(design));
    if (text.length > 12000) throw Error('文字设计摘要较大，请缩短设计文字或工具说明后再润色；控件和初稿模式不受此摘要长度限制');
    return {mode:'prompt',instruction:text,context:null};
  }
  async function bindingToken(binding) {
    const bytes = await globalThis.crypto.subtle.digest('SHA-256',new TextEncoder().encode(binding));
    return Array.from(new Uint8Array(bytes),value=>value.toString(16).padStart(2,'0')).join('');
  }
  // Called only after the main process validates the delta and the caller
  // checks the complete local binding. Keep opaque local fields off the wire.
  function mergeOperations(operations,patch) {
    if (!patch || !Array.isArray(patch.changes) || !patch.changes.length || patch.changes.length > 16) throw Error('工具增量格式无效');
    const merged=JSON.parse(JSON.stringify(operations)),seen=new Set();
    for (const change of patch.changes) {
      if (!Number.isInteger(change.step) || change.step < 1 || change.step > merged.length || seen.has(change.step)) throw Error('增量目标步骤无效');
      seen.add(change.step);
      if (!change.set || typeof change.set !== 'object' || Array.isArray(change.set) || Object.keys(change.set).some(key=>['__proto__','constructor','prototype','kind','overwrite','write_group','max_writes'].includes(key))) throw Error('增量不能修改工具权限或执行字段');
      Object.assign(merged[change.step-1],JSON.parse(JSON.stringify(change.set)));
    }
    return merged;
  }
  globalThis.NbtPromptAIInput = {textContext,request,bindingToken,mergeOperations};
})();
