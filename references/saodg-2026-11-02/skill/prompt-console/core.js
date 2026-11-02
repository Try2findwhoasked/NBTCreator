/* Portable shared catalogue and prompt compiler; no network or asset writes. */
(() => {
  const clone = v => JSON.parse(JSON.stringify(v));
  const common = {label:'局部构件调整', classification:'body',lo:[4,4,4],hi:[19,15,19]};
  const shapes = {
    box:{min:[6,4,6],max:[12,10,12]}, sphere:{centre:[12,10,12],radius:4},
    ellipsoid:{centre:[12,10,12],radii:[4,5,3]}, cylinder:{centre:[12,10,12],radius:3,height:8,axis:'y'},
    cone:{centre:[12,10,12],radius:4,top_radius:0,height:8,axis:'y'},
    torus:{centre:[12,10,12],major_radius:4,minor_radius:1},
    polyline:{points:[[6,6,6],[12,10,12],[17,7,17]],radius:1},
    bezier:{points:[[6,6,6],[12,12,12],[17,7,17]],radius:1,samples:64},
    extrude:{vertices:[[6,6],[15,6],[15,15],[6,15]],bottom:5,top:10},
    union:{children:[{shape:'sphere',centre:[10,10,10],radius:3},{shape:'sphere',centre:[14,10,10],radius:3}]},
    intersection:{children:[{shape:'sphere',centre:[10,10,10],radius:4},{shape:'sphere',centre:[14,10,10],radius:4}]},
    difference:{children:[{shape:'sphere',centre:[12,10,12],radius:4},{shape:'sphere',centre:[12,10,12],radius:3}]}
  };
  const catalog = {
    geometry:['几何 / 布尔 / 拉伸', {geometry:{shape:'cylinder',...shapes.cylinder},mode:'set',state:'stone_bricks',max_writes:4096},'形体取样在方块中心；内部box的min/max是连续表面。几何超出lo/hi会被裁剪。'],
    box:['体素填充 / 挖空',{state:'stone_bricks'},'lo/hi含边界。挖空时将state改为air。'],
    hollow_box:['空心外壳',{state:'stone_bricks',thickness:1},'内部会挖空气；保留密闭外层与支承。'],
    frame:['平面边框',{lo:[4,4,4],hi:[4,12,16],state:'stone_bricks',thickness:1},'选区必须恰有一个轴的lo=hi。'],
    beam:['直线 / 斜梁',{start:[5,5,5],end:[15,12,15],state:'oak_log',width:1},'width仅1、3、5；自行检查端点支承与六邻接。'],
    replace:['精确状态替换',{from_states:['stone_bricks'],state:'andesite',max_writes:4096},'精确状态匹配；填写完整原状态，朝向不会自动迁移。'],
    move_region:['平移构件',{offset:[2,0,0],classification:'inherit'},'保留源状态与墙mask；目标冲突和保护区修改拒绝。'],
    copy_region:['快照复制',{offset:[8,0,0],include_air:false,overwrite:false,max_writes:4096},'复制不旋转朝向；主体与墙体请拆分操作。'],
    repeat_region:['线性阵列',{offset:[8,0,0],count:3,include_air:false,overwrite:false,max_writes:4096},'源快照复制到偏移的1..count倍处，目标需有足够空间。'],
    transform_region:['旋转 / 镜像',{destination:[24,4,4],quarter_turns:1,mirror:null,move:false,include_air:false,overwrite:false,max_writes:4096},'先镜像再绕Y转90°整数倍；不支持的状态家族拒绝，楼梯/门/轨道不能任意旋转。'],
    morphology:['膨胀 / 侵蚀 / 表皮',{mode:'dilate',iterations:1,state:'stone_bricks',from_states:['stone_bricks'],max_writes:4096},'六邻接；域外视为空。薄梁与外壳要保护，新格用state。'],
    diffusion:['多源 / 表面扩散',{seeds:[[12,8,12]],steps:8,decay:.2,surface_only:false,from_states:['stone_bricks'],state:'mossy_stone_bricks',seed:2718,max_writes:4096},'种子必须在合格未保护位置，steps为图距离；不会跨越断开的表面。'],
    explosion:['静态爆炸 / 放射裂缝',{centre:[12,10,12],radius:3,roughness:.15,rays:8,ray_length:5,ray_width:.55,from_states:['stone_bricks'],seed:2718,max_writes:4096},'静态挖除，不是TNT物理；球包围必须在选区内，保护位置跳过，保留坑底与外壳。'],
    scatter:['带间距散落',{fraction:.1,spacing:2,supported:true,state:'cobblestone',from_states:['air'],seed:2718,max_writes:4096},'supported只做下方非空气筛选，不认证真实碰撞或重力。'],
    pattern:['带权混材 / 连片噪声',{action:'replace',scope:'surface',mode:'clustered',scale:6,fraction:.15,from_states:['stone_bricks'],palette:[{state:'stone_bricks',weight:70},{state:'cracked_stone_bricks',weight:20},{state:'mossy_stone_bricks',weight:10}],preserve_properties:true,shape_policy:'preserve',seed:2718,classification:'inherit'},'palette是相对权重，fraction是覆盖率。源状态/形状策略另验。'],
    surface_palette:['低密度表面换材',{from_states:['stone_bricks'],palette:['cracked_stone_bricks','mossy_stone_bricks'],fraction:.1,seed:2718,classification:'inherit'},'不挖空气；带权需求请用pattern。'],
    weathering:['连片风化 / 苔痕 / 裂纹',{from_states:['stone_bricks'],seed:2718,moss:{fraction:.12,patch_size:[12,40],state:'mossy_stone_bricks'},cracks:{fraction:.06,length:[6,18],state:'cracked_stone_bricks'},floor:{fraction:0},classification:'inherit'},'完整块材质为主；地面自动识别优先auto_floor。'],
    auto_floor:['多层地面识别 / 半砖坑',{profile:'worn',style_note:'保留必要路线，局部轻度磨损',fraction:.04,slab_share:.85,patch_size:[2,4],pit_depth:1,route_margin:.5,exclude_boxes:[],slab_overrides:{},seed:2718,classification:'body'},'需要真实start/targets/ports/interior_probes；依赖实际模型，网页不能估算通过。']
  };
  const labels = {label:'操作说明',classification:'层归属',lo:'选区最小 XYZ',hi:'选区最大 XYZ',geometry:'几何定义',mode:'模式',state:'目标方块状态',from_states:'原状态列表',seed:'全局随机种子',max_writes:'本步最大变化',offset:'偏移 XYZ',count:'副本数量',destination:'目标最小 XYZ',quarter_turns:'90°旋转次数',mirror:'镜像轴',move:'移动源选区',include_air:'包含空气',overwrite:'允许覆盖',iterations:'迭代次数',seeds:'扩散种子 XYZ 列表',steps:'扩散步数',decay:'远处衰减',surface_only:'仅沿表面',centre:'中心 XYZ',radius:'半径',roughness:'边缘起伏',rays:'放射裂缝数',ray_length:'裂缝长度',ray_width:'裂缝半径',fraction:'覆盖比例 0～1',spacing:'最小间距',supported:'粗略支承筛选',action:'填充或替换',scope:'表面或体积',scale:'噪声尺度',palette:'材质与权重',preserve_properties:'保留兼容属性',shape_policy:'形状策略',profile:'地面风格',style_note:'设计说明',slab_share:'半砖份额',patch_size:'片区范围',pit_depth:'坑深',route_margin:'路线保护余量',exclude_boxes:'排除体积',slab_overrides:'半砖映射',moss:'苔痕参数',cracks:'裂纹参数',floor:'地面风化参数',thickness:'厚度',width:'梁宽',start:'起点 XYZ',end:'终点 XYZ'};
  function operation(kind) {const op={kind,...clone(common),...clone(catalog[kind][1]),label:catalog[kind][0]};if(kind==='auto_floor'){delete op.lo;delete op.hi;op.include_boxes=[];}return op;}
  function defaults() {return {schema_version:1,project:{name:'遗迹大厅',stage:'draft',source:'',size:[48,24,48],footprint:'单个完整建筑；由用途决定尺寸',theme:'古老石构遗迹，克制的磨损与清晰的结构层次',purpose:'探索、停留与普通玩家通行',output:'',integration:'standalone',style:'主材石砖；次材安山岩；木构仅用于有支承的局部构件。先做结构层次，再做材质。',ceiling:'梁架/拱券有真实落点；顶面节奏对应柱网与功能；墙顶、梁端、吊挂基座收口完整。',floor:'铺装回应动线与功能；台阶、桥头、平台有厚度与连续收边；适量成片磨损，必要通路平顺。',wall:'有墙脚、主体与顶部层次；门窗有厚度与过梁；壁龛保留外壳；避免所有墙等距复制同一组道具。',props:'道具有安装与使用空间；关键节点集中细节，其余区域保留留白。',preserve:'保留主轮廓、必要路线、端口、安全到达点、承重支撑和主题节点。',extras:'不要为满足工具清单强行添加不适用效果。',budget:4096,contextPath:'',reviewPath:'',context:{cells:[[0,0]],door_y:2,ports:[],start:null,targets:{},interior_probes:[],protected_paths:[],protected_boxes:[],route_legs:[],cameras:[]}},operations:[]};}
  function validate(s) {
    const errors=[];
    if(s?.schema_version!==1 || !s.project || !Array.isArray(s.operations))return ['需要schema_version=1、project和operations'];
    const p=s.project;
    if(!['draft','plan','refine'].includes(p.stage))errors.push('请选择有效阶段');
    if(!Array.isArray(p.size)||p.size.length!==3||!p.size.every(n=>Number.isInteger(n)&&n>0))errors.push('整体尺寸必须是三个正整数');
    if(!Number.isInteger(p.budget)||p.budget<1)errors.push('总变化预算须为正整数');
    if(!p.name?.trim()||!p.style?.trim())errors.push('填写建筑名称与全局风格');
    if(!p.context||typeof p.context!=='object'||Array.isArray(p.context))errors.push('验证上下文须为JSON对象');
    s.operations.forEach((o,i)=>{
      const prefix=`第${i+1}步：`;
      if(!o||typeof o!=='object'){errors.push(prefix+'操作须为JSON对象');return;}
      if(!catalog[o.kind]) {errors.push(prefix+'未知工具');return;}
      if(!o.label?.trim())errors.push(prefix+'填写操作说明');
      if(!['wall','body','inherit'].includes(o.classification))errors.push(prefix+'层归属无效');
      if(o.kind!=='auto_floor')for(const k of ['lo','hi'])if(!Array.isArray(o[k])||o[k].length!==3||!o[k].every(Number.isInteger))errors.push(prefix+k+'须为整数XYZ');
      if(Array.isArray(o.lo)&&Array.isArray(o.hi)&&p.size?.length===3&&o.lo.some((v,j)=>v<0||v>o.hi[j]||o.hi[j]>=p.size[j]))errors.push(prefix+'选区越界或上下界颠倒');
      for(const k of ['fraction','decay','slab_share'])if(k in o&&(!(o[k]>=0&&o[k]<=1)))errors.push(prefix+k+'须在0..1');
      if(o.kind==='explosion'&&(!(o.radius>0)||!(o.roughness>=0&&o.roughness<1)))errors.push(prefix+'爆炸半径/起伏无效');
      if(o.kind==='replace'&&(!Array.isArray(o.from_states)||!o.from_states.length))errors.push(prefix+'替换需原状态列表');
      if(o.kind==='frame'&&o.lo.filter((v,j)=>v===o.hi[j]).length!==1)errors.push(prefix+'边框需处在一个轴对齐平面');
    });
    return errors;
  }
  const plan = s => ({style_note:s.project.style, operations:clone(s.operations)});
  function prompt(s) {
    const p=s.project, stage={draft:'新建完整建筑初稿',plan:'只读检查与修改规划',refine:'已有建筑全局精修'}[p.stage];
    return `请使用工作区的 $minecraft-nbt-modeler 完成以下任务。先读 AGENTS.md 和该 skill 的适用完整章节。\n\n# 任务与输入\n- 建筑中文名：${p.name}\n- 阶段：${stage}\n- 目标：${p.purpose}\n- 主题：${p.theme}\n- 整体 XYZ 尺寸：${p.size.join(' × ')}；占地说明：${p.footprint}\n- 完整源文件：${p.source||'尚无；新建时设计完整主模型，修改时先查找并核对源，不能猜测'}\n- 接入：${p.integration==='saodg'?'SAODG，读取当前加载器与拼接协议':'独立原版结构，不强加48占地、四门或房间池'}\n- 输出目录：${p.output||'按skill默认日期/形状/中文房间名/版本新建目录'}\n- 已有坐标/保护配置：${p.contextPath||'待根据真实模型补齐'}\n- 已有审阅目录：${p.reviewPath||'未提供；不得制造确认记录'}\n\n# 全局设计与细节要求\n${p.style}\n\n天花板与顶构：${p.ceiling}\n地板与平台：${p.floor}\n墙面与开口：${p.wall}\n道具与密度：${p.props}\n保留项：${p.preserve}\n其他要求：${p.extras}\n\n# 阶段执行边界\n${p.stage==='draft'?'先在同一全局坐标系完成整体初稿；闭合外壳后检查全部腔体，按声明开洞并验证必要通路。初稿已有墙/顶/地面层次与必要支承。保存完整主模型、墙mask、生成脚本和图片，展示缩略图后等待真实用户同意精修。':p.stage==='plan'?'只读检查源、坐标、状态、保护与候选计划，不修改已有模型，不生成已执行或已批准的结论。':'核对当前对话中对应源与缩略图之后的真实用户精修确认；有确认则沿用，不重复询问。没有则完成可审阅准备并展示图片，等待确认；本提示词与参数文件自身不构成看图确认。'}\n保留原稿、墙mask、图像与哈希。按完整未切割主模型全局处理，版本另存；不逐片精修，不用49展开体做主稿。总变化预算：${p.budget}格；不为了凑效果放宽保护。\n\n# 工具与操作计划\n${s.operations.length?'按下列顺序规划；核对每步选区和真实模型后再执行。不合适或无法满足时说明具体原因，不把模板示例坐标当成已验证位置。':'由设计需求选择适用工具；不要求把所有工具都用一次。'}\n\`\`\`json\n${JSON.stringify(plan(s),null,2)}\n\`\`\`\n可选：几何布尔/拉伸/扫掠、复制阵列、旋转镜像、形态学、扩散、静态爆炸、散落、带权混材、自动地面、连片风化。完整参数见references/modelling-tools.md及各专项文档。旋转不支持的状态应拒绝；扩散是六邻接增长，爆炸是静态挖除，不推断真实物理。\n\n# 验证上下文草案（必须对照真实模型补齐）\n\`\`\`json\n${JSON.stringify({...p.context,max_changed_blocks:p.budget},null,2)}\n\`\`\`\n空start、腔体探针、必要目标与相机不代表验证完成；不要捏造玩家脚位、实际路径或批准记录。配置中的cells/door_y仅为待核对的SAODG网格草案；独立结构按实际尺寸选用支持的工具，不强行改成48。\n\n# 复核与交付\n${p.stage==='plan'?'本阶段仅交付只读诊断、候选计划和待补齐项，以下制作验收要求作为后续执行依据。':p.stage==='draft'?'本阶段交付完整初稿和审阅图后等待真实确认，后续精修与重切按授权阶段执行。':'本阶段只在真实确认及检查条件满足后交付精修新版本。'}\n格式要求：原版Java 1.20.1、gzip NBT、DataVersion=3465；XYZ唯一且界内，palette状态合法；墙mask明确记录，不按材质猜墙。\n逐一审阅天花/地板/墙面、地墙/墙顶/柱梁/楼梯平台连接与主题节点，记录修改坐标、保留理由或不适用原因；先构造后材质，保留留白。出整体、无剖切入口、完整顶构室内仰视、地板/墙面与交接近景，实际看图；精修用同相机前后图。\n重新验证状态、外壳密闭、声明开口、真实玩家碰撞通路、保护区、变化预算和具体连接。技术通过不等于设计合格。通过后再机械切片，48连续回读重组逐块等于完整源；48重组、49运行、旋转、游戏加载与多人结果分别报告。\n交付完整主模型、更新墙mask、NBT、操作计划、差异、验证报告、图片和room_description.json。SAODG分层按有效cell各body/walls两份，完整运行模板另存。提供实际绝对路径与可点击NBT链接。未执行的游戏/多人/物理/材质光照检查明确写未验证；不写入活动世界、资源目录或房间池。\n`;
  }
  globalThis.NbtPrompt = {catalog,shapes,labels,clone,defaults,operation,validate,plan,prompt};
})();
