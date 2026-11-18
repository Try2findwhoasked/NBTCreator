/* Portable shared catalogue and prompt compiler; no network or asset writes. */
(() => {
  const clone = v => JSON.parse(JSON.stringify(v));
  const {common,shapes,tools:catalog,labels,building_shapes:buildingShapes,prompt_design:designContract}=globalThis.NbtToolCatalog;
  function operation(kind) {const op={kind,...clone(common),...clone(catalog[kind][1]),label:catalog[kind][0]};if(kind==='auto_floor'){delete op.lo;delete op.hi;op.include_boxes=[];}return op;}
  function defaults() {return {schema_version:1,project:{name:'遗迹大厅',stage:'draft',source:'',buildingShape:'standalone',layout:"",circulation:"",size:[48,24,48],size_policy:'reference',spatial_character:'',materials:'',atmosphere:'',avoid:'',footprint:'单个完整建筑；由用途决定尺寸',theme:"由用途与场景形成建筑主题",purpose:"明确使用者、主要活动与空间用途",output:'',integration:'standalone',style:"根据用途选择清楚的构造语汇，保持整栋主次和材料角色一致。",ceiling:"",floor:"",wall:"",props:"",preserve:"",extras:"",budget:4096,contextPath:'',reviewPath:'',context:{mode:'standalone',openings:[],cells:[],start:null,targets:{},interior_probes:[],protected_paths:[],protected_boxes:[],route_legs:[],cameras:[]}},operations:[],workbench:{brief_fields:clone(designContract.default_editable_fields)}};}
  function shapeOf(p) {
    if(buildingShapes[p.buildingShape])return p.buildingShape;
    const [x,,z]=p.size||[];
    return x===48&&z===48?'single':x%48===0&&z%48===0?(x===48||z===48?'long':x===z?'square':'irregular'):'standalone';
  }
  function outputPath(p) {
    if(p.stage!=='draft')return p.output||'';
    if(p.room_folder)return p.room_folder;
    const name=String(p.name||'未命名建筑').replace(/[<>:"/\\|?*\x00-\x1f]/g,'_').replace(/[. ]+$/g,'').slice(0,70)||'未命名建筑';
    return `nbt_models/${shapeOf(p)}/${name}`;
  }
  function applyShape(p,key) {
    const preset=buildingShapes[key];if(!preset)throw Error('请选择有效建筑形状');
    p.buildingShape=key;
    // Archive classification does not select an authoring constraint.
  }
  function normalize(value) {
    const base=defaults(),v=clone(value);
    const result={...base,...v,project:{...base.project,...v.project}};
    if(!v.project?.buildingShape)result.project.buildingShape=shapeOf({...result.project,buildingShape:null});
    if(v.project?.size_policy===undefined&&v.project?.size)result.project.size_policy='fixed';
    if(result.project.stage!=='draft'||result.project.integration==='saodg')result.project.size_policy='fixed';
    result.workbench={...base.workbench,...v.workbench};
    if(result.project.stage==='draft'){result.project.source='';result.project.contextPath='';result.project.reviewPath='';result.project.output=outputPath(result.project);}
    return result;
  }
  function validate(s) {
    const errors=[];
    if(s?.schema_version!==1 || !s.project || !Array.isArray(s.operations))return ['需要schema_version=1、project和operations'];
    let p;try{p=effectiveProject(s);}catch(error){return [error.message];}
    for(const [key,spec]of Object.entries(designContract.fields))if(key!=='size'&&p[key]!==undefined&&(typeof p[key]!=='string'||p[key].length>4000))errors.push(spec.label+'须为不超过4000字的文字');
    if(s.design_standard&&(!s.design_standard.fields||typeof s.design_standard.fields!=='object'||Object.values(s.design_standard.fields).some(value=>typeof value!=='string'||value.length>4000)||!Number.isInteger(s.design_standard.revision)||s.design_standard.revision<1||!/^[a-f0-9]{64}$/.test(s.design_standard.sha256??'')))errors.push('项目规范快照无效，请重新引用');
    if(s.design_override!==undefined&&(typeof s.design_override!=='string'||s.design_override.length>4000))errors.push('建筑规范例外最多4000字');
    if(p.buildingShape!==undefined&&!buildingShapes[p.buildingShape])errors.push('请选择有效建筑形状');
    if(!['draft','plan','refine'].includes(p.stage))errors.push('请选择有效阶段');
    if(p.size_policy!==undefined&&!Object.hasOwn(designContract.size_policies,p.size_policy))errors.push('请选择有效尺寸约束方式');
    if(s.workbench?.brief_fields!==undefined&&(!Array.isArray(s.workbench.brief_fields)||new Set(s.workbench.brief_fields).size!==s.workbench.brief_fields.length||s.workbench.brief_fields.some(key=>!Object.hasOwn(designContract.fields,key))))errors.push('AI改写范围无效，请恢复默认范围');
    if(!Array.isArray(p.size)||p.size.length!==3||!p.size.every(n=>Number.isInteger(n)&&n>0))errors.push('整体尺寸必须是三个正整数');
    if(!Number.isInteger(p.budget)||p.budget<1)errors.push('总变化预算须为正整数');
    if(typeof p.name!=='string'||!p.name.trim()||typeof p.style!=='string'||!p.style.trim())errors.push('填写建筑名称与全局风格');
    if(!p.context||typeof p.context!=='object'||Array.isArray(p.context))errors.push('验证上下文须为JSON对象');
    s.operations.forEach((o,i)=>{
      const prefix=`第${i+1}步：`;
      if(!o||typeof o!=='object'){errors.push(prefix+'操作须为JSON对象');return;}
      if(!catalog[o.kind]) {errors.push(prefix+'未知工具');return;}
      if(typeof o.label!=='string'||!o.label.trim())errors.push(prefix+'填写操作说明');
      if(o.enabled!==undefined&&typeof o.enabled!=='boolean')errors.push(prefix+'启用开关须为布尔值');
      if(!['wall','body','inherit'].includes(o.classification))errors.push(prefix+'层归属无效');
      if(o.enabled===false)return;
      if(o.kind==='geometry'&&(!o.geometry||!shapes[o.geometry.shape]))errors.push(prefix+'填写有效几何形状');
      if(!['auto_floor','beam'].includes(o.kind))for(const k of ['lo','hi'])if(!Array.isArray(o[k])||o[k].length!==3||!o[k].every(Number.isInteger))errors.push(prefix+k+'须为整数XYZ');
      if(o.kind==='beam')for(const k of ['start','end']){
        if(!Array.isArray(o[k])||o[k].length!==3||!o[k].every(Number.isInteger))errors.push(prefix+k+'须为整数XYZ');
        else if(p.size?.length===3&&o[k].some((v,j)=>v<0||v>=p.size[j]))errors.push(prefix+k+'梁端点超出模型');
      }
      if(Array.isArray(o.lo)&&Array.isArray(o.hi)&&p.size?.length===3&&o.lo.some((v,j)=>v<0||v>o.hi[j]||o.hi[j]>=p.size[j]))errors.push(prefix+'选区越界或上下界颠倒');
      for(const k of ['fraction','decay','slab_share'])if(k in o&&(!(o[k]>=0&&o[k]<=1)))errors.push(prefix+k+'须在0..1');
      if(o.kind==='explosion'&&(!(o.radius>0)||!(o.roughness>=0&&o.roughness<1)))errors.push(prefix+'爆炸半径/起伏无效');
      if(o.kind==='replace'&&(!Array.isArray(o.from_states)||!o.from_states.length))errors.push(prefix+'替换需原状态列表');
      if(o.kind==='frame'&&Array.isArray(o.lo)&&Array.isArray(o.hi)&&o.lo.filter((v,j)=>v===o.hi[j]).length!==1)errors.push(prefix+'边框需处在一个轴对齐平面');
    });
    return errors;
  }
  const plan = s => ({style_note:s.project.style, operations:clone(s.operations)});
  function standardText(s){if(!s.design_standard)return '';const labels={name:'规范名称',materials:'材质与配色',dimensions:'尺度、层高与门窗',circulation:'道路与通行',style:'风格与构造',references:'参考说明',notes:'其他统一要求'};return '# 项目设计规范（修订 '+s.design_standard.revision+'）\n'+Object.entries(s.design_standard.fields).filter(([,value])=>value).map(([key,value])=>(labels[key]??key)+'：'+value).join('\n')+(s.design_override?'\n本建筑的明确例外（优先于上述项目规范）：'+s.design_override:'');}
  function effectiveProject(s) {
    if(s.constraints!==undefined)return globalThis.NbtConstraintContract.effective(s.project,s.constraints);
    const project=clone(s.project);
    if(project.integration==='saodg'){
      project.context={...project.context,mode:'saodg'};
      project.size_policy='fixed';
    }
    return project;
  }
  const constraintText = s => s.constraints?.length?globalThis.NbtConstraintContract.text(s.constraints):'';
  function prompt(s,options={}) {
    const p=effectiveProject(s), stage={draft:'新建完整建筑初稿',plan:'只读检查与修改规划',refine:'已有建筑全局精修'}[p.stage];
    let supplement='';
    if(options.designText!==undefined){
      if(typeof options.designText!=='string'||!options.designText.trim()||options.designText.length>60000)throw Error('设计说明正文无效');
      supplement='# 补充设计说明（以人工参数和硬条件为准）\n'+options.designText+'\n\n';
    }
    let text=`请优先使用工作区的 .agents/skills/nbtcreator-workspace/SKILL.md；未生成入口时使用 $minecraft-nbt-modeler。先读 AGENTS.md 和该 skill 的适用完整章节。\n\n# 任务与输入\n- 建筑中文名：${p.name}\n- 阶段：${stage}\n- 目标：${p.purpose}\n- 主题：${p.theme}\n- 建筑形状：${buildingShapes[shapeOf(p)].label}（${shapeOf(p)}），以最终实际几何登记\n- 整体 XYZ 尺寸：${p.size.join(' × ')}；尺寸约束：${p.stage==='draft'&&p.integration!=='saodg'&&p.size_policy==='reference'?'参考尺寸，由执行Agent按用途推导实际尺寸并说明调整；最终归档按真实几何登记':'固定尺寸，必须满足'}；占地说明：${p.footprint}\n- 完整源文件：${p.source||'尚无；新建时设计完整主模型，修改时先查找并核对源，不能猜测'}\n- 接入：${p.integration==='saodg'?'SAODG，读取当前加载器与拼接协议':'独立原版结构，不强加48占地、四门或房间池'}\n- 输出目录：${outputPath(p)||'按skill规范在源建筑工作目录另存新版本'}\n- 已有坐标/保护配置：${p.contextPath||'待根据真实模型补齐'}\n- 已有审阅目录：${p.reviewPath||'未提供；不得制造确认记录'}\n\n${standardText(s)}\n\n${constraintText(s)}\n\n# 建筑对象与关系\n默认按关键空间、构件与环境对象表达用途、特征、包含和连接关系及共同约束；下列字段是设计意图。除用户已指定的细节外，具体数量、间距、方块配方和施工顺序由建模 Agent 根据完整主模型推导。对象划分不代表先独立造房再拼接。\n空间特色与体验：${p.spatial_character||'由用途和场地推导'}\n光线与空间氛围：${p.atmosphere||'由整体设计安排'}\n材质倾向与分工：${p.materials||'沿用人工风格要求'}\n希望避免的设计：${p.avoid||'未额外指定'}\n空间分区与高差：${p.layout||'由整体设计补齐，不能只做房壳'}\n玩家动线与空间连接：${p.circulation||'核对普通玩家尺度与必要目标的真实通路'}\n${p.style}\n\n主题涉及可辨识的纹样时，明确主题元素适用的承载面、观察距离与主次；执行 Agent 按需选图源与拟合方法，并检查实际方块近景。
天花板与顶构：${p.ceiling}\n地板与平台：${p.floor}\n墙面与开口：${p.wall}\n道具与密度：${p.props}\n保留项：${p.preserve}\n其他要求：${p.extras}\n\n${supplement}# 自动存放规则\n${p.stage==='draft'?'以当前 Agent 项目根目录为工作区，用 nbt_library.py new 按实际形状和中文名分配全新版本目录；上述输出路径是建筑归档根目录，不是既有版本，不得覆盖。日期和房间编号使用实际生成时的值。':'沿用完整源建筑所属工作目录，分配下一版本，保留原稿。'}\n制作阶段把完整可编辑源保存为 master/model.snbt，并保留生成脚本、coordinates.json、previews/、validation/ 与显式墙层；旧 JSON.GZ 源仍可读取，不能因转换删除原稿。只有用户明确要求定稿时，调用工作区 finalize 接口，在 nbt_models/_exports/ 下生成相同形状/建筑/版本层级的 master/model.nbt、runtime/parts/ 与适用的 delivery/；SNBT 和正式标注留在制作版本原位。登记 room_description.json 的中文名、实际形状、主模型路径与哈希。全部实际建模由 Agent 执行，本工作台只生成方案。\n\n# 阶段执行边界\n${p.stage==='draft'?'先在同一全局坐标系完成整体初稿；按项目约束决定需否验密闭、是否设置通行洞口及其尺寸。开放建筑保留设计留空。要求密闭时在开洞前检查并保存证据；有声明洞口时验证实际开口和必要通路。初稿已有墙/顶/地面层次与必要支承。保存完整主模型、墙mask、生成脚本和图片，展示缩略图后等待真实用户同意精修。':p.stage==='plan'?'只读检查源、坐标、状态、保护与候选计划，不修改已有模型，不生成已执行或已批准的结论。':'核对当前对话中对应源与缩略图之后的真实用户精修确认；有确认则沿用，不重复询问。没有则完成可审阅准备并展示图片，等待确认；本提示词与参数文件自身不构成看图确认。'}\n保留原稿、墙mask、图像与哈希。按完整未切割主模型全局处理，版本另存；不逐片精修，不用49展开体做主稿。${p.stage==='draft'?'精修阶段的变化预算参考，不限制初稿总方块量':'总变化预算'}：${p.budget}格；不为了凑效果放宽保护。\n\n# 工具与操作计划\n${s.operations.length?'按下列顺序规划；核对每步选区和真实模型后再执行。不合适或无法满足时说明具体原因，不把模板示例坐标当成已验证位置。':'由设计需求选择适用工具；不要求把所有工具都用一次。enabled=false 的步骤仅为保留草稿，不得执行；省略 enabled 等于 true。'}\n\`\`\`json\n${JSON.stringify(plan(s),null,2)}\n\`\`\`\n可选：几何布尔/拉伸/扫掠、复制阵列、旋转镜像、形态学、扩散、静态爆炸、散落、带权混材、自动地面、连片风化。完整参数见references/modelling-tools.md及各专项文档。旋转不支持的状态应拒绝；扩散是六邻接增长，爆炸是静态挖除，不推断真实物理。\n\n# 验证上下文草案（必须对照真实模型补齐）\n\`\`\`json\n${JSON.stringify({...p.context,max_changed_blocks:p.budget},null,2)}\n\`\`\`\n按真实几何补齐路线起点、必要目标和相机。要求密闭时填写 interior_probes；如为开放建筑，登记 require_enclosure=false，无通行洞口时使用 openings=[]。独立通行洞口的 lo/hi 给出含端点的净宽、净高及墙厚；按所选 opening_size 校验。仅在启用 SAODG 接入时使用 ports、door_y 与加载器协议。\n\n# 复核与交付\n${p.stage==='plan'?'本阶段仅交付只读诊断、候选计划和待补齐项，以下制作验收要求作为后续执行依据。':p.stage==='draft'?'本阶段交付完整初稿和审阅图后等待真实确认，后续精修与重切按授权阶段执行。':'本阶段只在真实确认及检查条件满足后交付精修新版本。'}\n格式要求：原版Java 1.20.1、DataVersion=3465；制作阶段保存完整SNBT，明确要求定稿时才导出gzip NBT；XYZ唯一且界内，palette状态合法；墙mask明确记录，不按材质猜墙。\n逐一审阅天花/地板/墙面、地墙/墙顶/柱梁/楼梯平台连接与主题节点，记录修改坐标、保留理由或不适用原因；先构造后材质，保留留白。出整体、无剖切入口、完整顶构室内仰视、地板/墙面与交接近景，实际看图；精修用同相机前后图。\n检验方块状态、真实玩家碰撞通路、保护区、变化预算和具体连接，并按项目约束验密闭与洞口。技术通过不等于设计合格。定稿时机械切片并回读重组，逐块核对完整源。${p.integration==='saodg'?'48连续重组与49运行兼容性分别报告。':''}旋转、游戏加载与多人结果分别报告。\n制作阶段交付完整 SNBT 主模型、更新墙mask、操作计划、差异、验证报告、图片和room_description.json；定稿 NBT 单独交付。${p.integration==='saodg'?'SAODG 分层按有效 cell 各存主体与墙层，完整运行模板另存。':''}提供实际绝对路径及可点击的制作源、图片与验证链接；定稿后再提供NBT链接。未执行的游戏/多人/物理/材质光照检查明确写未验证；不写入活动世界、资源目录或房间池。\n`;
    return text;
  }
  globalThis.NbtPrompt = {catalog,shapes,labels,buildingShapes,designContract,clone,defaults,normalize,shapeOf,outputPath,applyShape,operation,validate,plan,prompt,standardText,effectiveProject,constraintText};
})();
