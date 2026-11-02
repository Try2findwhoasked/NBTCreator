const fs=require('node:fs/promises'),path=require('node:path'),crypto=require('node:crypto')
const flows={
 draft:{label:'提示词方案 · 完整初稿',steps:'读取设计要求 → 补齐空间与构造 → 返回表单和工具候选 → 用户采用 → 复制给Agent制作',rules:'先整体空间后材质细节；补齐入口、主空间、辅助区、高差、支承及玩家动线。不得把方案说成已生成的NBT。'},
 workbench:{label:'提示词方案 · 配置控件',steps:'读取当前表单 → 提议设计字段和工具序列 → 校验 → 用户采用',rules:'保留不需修改的字段与步骤；已有模型尺寸、路径、阶段和保护保持本地值。'},
 prompt:{label:'提示词方案 / 模型编辑 · 文字编写',steps:'读取本次文字要求 → 补充设计说明 → 返回候选正文 → 用户采用或复制',rules:'使用简体中文和具体构造说明，不声称已执行、已看图或已获批准。'},
 structure:{label:'模型编辑 · 局部编辑',steps:'读取局部选区与材质 → 生成填充/换块候选 → 本地校验 → 预览 → 用户导出',rules:'严格留在选区内；保护必要路线和承重，不能降低验证要求。'},
 small_structure:{label:'模型编辑 · 小型结构 / 3D放置',steps:'3D点选/XYZ限定体积 → 发送局部尺寸和材质 → AI返回相对坐标步骤 → 脚本平移及检查 → 候选合并和3D渲染 → 用户确认导出NBT',rules:'1. 使用选区局部坐标，原点为选区最小角，X宽/Y高/Z深；只返回整数坐标与minecraft方块状态。\n2. 先确定占地、支承、净空和用途，再拆分box/beam/frame；也可逐块返回pos/state，单个方块用lo=hi的box表达。最多128步，需要开口可用air；缺失的常规字段由应用补齐。\n3. 不输出NBT二进制、palette索引、Python或任意代码，不猜全局坐标。\n4. 保留玩家通路和承重，避免悬空；朝向与半砖等属性必须合法。\n5. 应用负责平移坐标、注册表校验、保护/预算检查、墙归属、合并和导出；结果只是候选，不能声称已经保存或验证通过。'}
}
flows.draft.rules+='\n声明整体尺寸与有效占地；闭合外壳后检查全部腔体，再按声明开洞；初稿已有顶构承托、墙面/地板层次和主题节点。安排实际主模型/图片/验证交付，等待对应看图确认后才精修。'
flows.workbench.rules+='\n坐标和工具步骤只是候选，按真实模型核对；只改用户需要的设计字段，保持未调整步骤。发现缺参数时明确列出，不捏造验证。'
flows.prompt.rules+='\n明确用途、玩家活动、空间关系、构造连接和交付阶段。区分已有事实、设计建议与待验证项，输出可修改的中文说明。'
flows.structure.rules+='\n局部编辑只允许已开放的结构/换块参数，移动目标也必须界内。候选必须通过源哈希、合法状态、保护和预算检查后预览；保存建筑由用户另行导出。'
const builtins={
 'builtin:design':{label:'整体创作原则',file:'design-principles.md'},
 'builtin:space':{label:'空间与构造细节',file:'spatial-detail-design.md'},
 'builtin:scale':{label:'玩家尺度',file:'player-scale.md'},
 'builtin:tools':{label:'建模工具说明',file:'modelling-tools.md'},
 'builtin:delivery':{label:'输出与归档规范',file:'output-storage.md'}
}
function createInternalAI({workspace,skill}){
 const base=()=>path.join(workspace(),'.nbtcreator','internal-ai'),file=()=>path.join(base(),'config.json')
 const defaults=()=>({schema_version:1,workflows:Object.fromEntries(Object.entries(flows).map(([key,value])=>[key,{rules:value.rules,instruction:'',knowledge:[],attachViewport:false}])),documents:[]})
 async function load(){try{return JSON.parse(await fs.readFile(file(),'utf8'))}catch(e){if(e.code==='ENOENT')return defaults();throw e}}
 function validate(c){
  if(!c||c.schema_version!==1||!c.workflows||!Array.isArray(c.documents)||c.documents.length>100)throw Error('内部AI配置无效')
  const ids=new Set(Object.keys(builtins))
  for(const d of c.documents){if(!/^[a-f0-9]{64}$/.test(d.id)||d.path!==`knowledge/${d.id}.md`||typeof d.label!=='string'||d.label.length>150)throw Error('内部资料记录无效');ids.add(d.id)}
  if(Object.keys(c.workflows).some(k=>!flows[k]))throw Error('未知AI工作流')
  for(const key of Object.keys(flows)){const f=c.workflows[key];if(f?.attachViewport!==undefined&&typeof f.attachViewport!=='boolean')throw Error('截图开关无效');if(!f||typeof f.rules!=='string'||f.rules.length>12000||typeof f.instruction!=='string'||f.instruction.length>6000||!Array.isArray(f.knowledge)||f.knowledge.some(id=>!ids.has(id)))throw Error('工作流规则或资料选择无效')}
  return c
 }
 async function persist(c){validate(c);await fs.mkdir(base(),{recursive:true});const tmp=file()+'.'+crypto.randomUUID()+'.tmp';await fs.writeFile(tmp,JSON.stringify(c,null,2));await fs.rename(tmp,file())}
 async function show(){const c=validate(await load());return {...c,flows,builtins,location:'.nbtcreator/internal-ai/'}}
 async function save(input){const current=await load();const c=validate({...current,workflows:input.workflows});await persist(c);return show()}
 async function importDocuments(files){const c=validate(await load());await fs.mkdir(path.join(base(),'knowledge'),{recursive:true})
  for(const source of files){if(!['.md','.txt'].includes(path.extname(source).toLowerCase()))throw Error('仅支持Markdown和TXT');const bytes=await fs.readFile(source);if(bytes.length>256*1024||bytes.includes(0))throw Error('单个资料须为不超过256KiB的文本');const id=crypto.createHash('sha256').update(bytes).digest('hex');if(c.documents.some(d=>d.id===id))continue;const relative=`knowledge/${id}.md`;await fs.writeFile(path.join(base(),relative),bytes,{flag:'wx'}).catch(e=>{if(e.code!=='EEXIST')throw e});c.documents.push({id,path:relative,label:path.basename(source).slice(0,150)})}
  await persist(c);return show()
 }
 async function context(key){if(!flows[key])throw Error('未知AI工作流');const c=validate(await load()),flow=c.workflows[key],knowledge=[];let total=0
  for(const id of flow.knowledge){const b=builtins[id],d=c.documents.find(d=>d.id===id);const content=await fs.readFile(b?path.join(skill,'references',b.file):path.join(base(),d.path),'utf8');total+=content.length;if(total>48000)throw Error('本工作流资料总量超过48000字，请减少选中的文档');knowledge.push({label:b?.label??d.label,content})}
  return {attachViewport:flow.attachViewport===true,workflow:key,workflow_steps:flows[key].steps,base_rules:flows[key].rules,rules:flow.rules,instruction:flow.instruction,knowledge}
 }
 async function preview(id){const c=validate(await load()),b=builtins[id],d=c.documents.find(d=>d.id===id);if(!b&&!d)throw Error('未知内部资料');return {title:b?.label??d.label,recipient:'仅在勾选并保存后，随对应工作流发送全文给已配置的 API。',text:await fs.readFile(b?path.join(skill,'references',b.file):path.join(base(),d.path),'utf8')}}
 return {show,save,importDocuments,context,preview}
}
Object.assign(builtins['builtin:design'],{summary:'设计独立空间构想、结构层次、主题节点与留白；避免只换材质或复制同一种房型。',use:'首次初稿、整体重设计、纠正重复布局'})
Object.assign(builtins['builtin:space'],{summary:'天花承托、地板分区、墙面厚度、门窗收口及三者交接，指导细节主次和尺度。',use:'完整初稿、小型构件、细节方案'})
Object.assign(builtins['builtin:scale'],{summary:'按普通玩家身体与碰撞尺度考虑净高、通路、平台、楼梯和可达性。',use:'所有涉及玩家通行的空间和构件'})
Object.assign(builtins['builtin:tools'],{summary:'几何、复制、旋转、扩散与破坏等完整工具参数；内部小型结构只开放其中的受限子集。',use:'表单工具规划；不代表AI获得全部工具执行权限'})
Object.assign(builtins['builtin:delivery'],{summary:'nbt_models形状归档、中文描述、日期版本命名及master/runtime/delivery等分区。',use:'完整任务交付规划；小型结构的NBT封装由脚本负责'})
module.exports={createInternalAI,flows}
