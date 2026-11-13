const {createAIStyle}=require('./ai-style.cjs')
const fs=require('node:fs/promises'),path=require('node:path'),crypto=require('node:crypto')
const flows={
 draft:{label:'提示词方案 · 交接要求',steps:'整理设计要求 → 用户审阅 → 保存任务与提示词 → 下一个Agent读取后制作',rules:'只编写设计要求和交接文字；以关键空间、构件与环境为对象，描述用途、特征、包含和连接关系及共同约束；默认不预定数量、间距、方块配方或施工顺序，用户明确给定的细节保留。具体建模步骤由接收任务的Agent编写，不在提示词编写阶段实施模型。'},
 workbench:{label:'提示词方案 · 配置控件',steps:'读取当前表单 → 提议设计字段和工具序列 → 校验 → 用户采用',rules:'保留不需修改的字段与步骤；已有模型尺寸、路径、阶段和保护保持本地值。'},
 prompt:{label:'提示词方案 / 模型编辑 · 文字编写',steps:'读取本次文字要求 → 补充设计说明 → 返回候选正文 → 用户采用或复制',rules:'使用简体中文描述建筑对象、职责和关系，保留实现自由，不声称已执行、已看图或已获批准。'},
 structure:{label:'模型编辑 · 局部编辑',steps:'读取局部选区与材质 → 生成填充/换块候选 → 本地校验 → 预览 → 用户导出',rules:'严格留在选区内；保护必要路线和承重，不能降低验证要求。'},
 small_structure:{label:'模型编辑 · 小型结构 / 3D放置',steps:'3D点选/XYZ限定体积 → 发送局部尺寸和材质 → AI返回相对坐标步骤 → 脚本平移及检查 → 候选合并和3D渲染 → 用户确认导出NBT',rules:'1. 使用选区局部坐标，原点为选区最小角，X宽/Y高/Z深；只返回整数坐标与minecraft方块状态。\n2. 先确定占地、支承、净空和用途，再拆分box/beam/frame；也可逐块返回pos/state，单个方块用lo=hi的box表达。最多128步，需要开口可用air；缺失的常规字段由应用补齐。\n3. 不输出NBT二进制、palette索引、Python或任意代码，不猜全局坐标。\n4. 保留玩家通路和承重，避免悬空；朝向与半砖等属性必须合法。\n5. 应用负责平移坐标、注册表校验、保护/预算检查、墙归属、合并和导出；结果只是候选，不能声称已经保存或验证通过。'}
}
flows.component={label:'资产管理 · 独立结构',steps:'读取资产与创作要求 → 返回共用结构参数 → 本地引擎生成独立预览 → 用户保存新资产 → 按参数放置候选',rules:'使用共用结构Agent协议、建模工具目录和局部整数XYZ坐标。独立结构不依赖已打开建筑；已有资产用编号与内容哈希引用。返回一个结构名称和一个相机角度，由脚本补齐镜头。保存资产不等于设计批准，放置仍需保护、预算、真实预览与显式导出。'}
flows.selection_edit={label:'模型编辑 · 选区自然语言工具编辑',steps:'读取现有候选的完整选区方块摘要 → 返回相对坐标工具步骤 → 用户审阅 → 同一引擎限制实际写入范围并预览 → 操作历史可撤销 → 用户显式导出',rules:'按完整选区的实际方块与墙层规划，保留不需改变的内容。使用局部原点与共用工具目录，选择适用步骤，最多32步；不得猜选区外环境或返回执行代码。覆盖由用户控制，保护、预算及墙层规则仍由引擎检查。不能把计划或预览称为已导出或已批准。'}
flows.small_structure.rules+='\n优先合并相邻同材质体积，通常不超过48个操作；只对零散装饰逐块描述。返回紧凑完整JSON，summary简短，不重复列出每个方块。允许覆盖只作用于实际写入位置，不能放宽保护和预算。'
flows.draft.rules+='\n声明整体尺寸与有效占地；闭合外壳后检查全部腔体，再按声明开洞；初稿已有顶构承托、墙面/地板层次和主题节点。安排实际主模型/图片/验证交付，等待对应看图确认后才精修。'
flows.workbench.rules+='\n坐标和工具步骤只是候选，按真实模型核对；只改用户需要的设计字段，保持未调整步骤。发现缺参数时明确列出，不捏造验证。'
flows.prompt.rules+='\n明确用途、玩家活动、空间关系、构造连接和交付阶段。区分已有事实、设计建议与待验证项，输出可修改的中文说明。'
flows.structure.rules+='\n局部编辑只允许已开放的结构/换块参数，移动目标也必须界内。候选必须通过源哈希、合法状态、保护和预算检查后预览；保存建筑由用户另行导出。'
const builtins=require('../.agents/skills/minecraft-nbt-modeler/tool-catalog.json').knowledge_sources
function createInternalAI({workspace,skill,retrieve}){
 const styles=createAIStyle({workspace,skill})
 const base=()=>path.join(workspace(),'.nbtcreator','internal-ai'),file=()=>path.join(base(),'config.json')
 const defaults=()=>({schema_version:1,workflows:Object.fromEntries(Object.entries(flows).map(([key,value])=>[key,{rules:value.rules,instruction:'',knowledge:[],attachViewport:false}])),documents:[]})
 async function load(){try{const data=JSON.parse(await fs.readFile(file(),'utf8'));if(data.schema_version===1&&data.workflows&&!data.workflows.component&&Object.keys(data.workflows).length===5&&Object.keys(data.workflows).every(key=>flows[key]))data.workflows.component=defaults().workflows.component;if(data.schema_version===1&&data.workflows&&[5,6].includes(Object.keys(data.workflows).length)&&Object.keys(data.workflows).every(key=>flows[key])&&['draft','workbench','prompt','structure','small_structure'].every(key=>data.workflows[key])){if(!data.workflows.component)data.workflows.component=defaults().workflows.component;if(!data.workflows.selection_edit)data.workflows.selection_edit=defaults().workflows.selection_edit}return data}catch(e){if(e.code==='ENOENT')return defaults();throw e}}
 function validate(c){
  if(!c||c.schema_version!==1||!c.workflows||!Array.isArray(c.documents)||c.documents.length>100)throw Error('内部AI配置无效')
  const ids=new Set(Object.keys(builtins))
  for(const d of c.documents){if(!/^[a-f0-9]{64}$/.test(d.id)||d.path!==`knowledge/${d.id}.md`||typeof d.label!=='string'||d.label.length>150)throw Error('内部资料记录无效');ids.add(d.id)}
  if(Object.keys(c.workflows).some(k=>!flows[k]))throw Error('未知AI工作流')
  for(const key of Object.keys(flows)){const f=c.workflows[key];if(f?.attachViewport!==undefined&&typeof f.attachViewport!=='boolean')throw Error('截图开关无效');if(!f||typeof f.rules!=='string'||f.rules.length>12000||typeof f.instruction!=='string'||f.instruction.length>6000||!Array.isArray(f.knowledge)||f.knowledge.some(id=>!ids.has(id)))throw Error('工作流规则或资料选择无效')}
  return c
 }
 async function persist(c){validate(c);await fs.mkdir(base(),{recursive:true});const tmp=file()+'.'+crypto.randomUUID()+'.tmp';await fs.writeFile(tmp,JSON.stringify(c,null,2));await fs.rename(tmp,file())}
 async function show(){const c=validate(await load()),preferences=await styles.load();return {...c,workflows:Object.fromEntries(Object.entries(c.workflows).map(([key,value])=>[key,{...value,style:preferences.workflows[key]}])),styleSchema:styles.schema.dimensions,flows,builtins,location:'.nbtcreator/internal-ai/',styleLocation:'.nbtcreator/ai-style.json'}}
 async function save(input){const current=await load(),preferences=await styles.load();const c=validate({...current,workflows:input.workflows});for(const [key,value]of Object.entries(c.workflows))if(value.style!==undefined)preferences.workflows[key]=value.style;styles.validate(preferences);const clean={...c,workflows:Object.fromEntries(Object.entries(c.workflows).map(([key,value])=>{const {style,...rest}=value;return [key,rest]}))};await styles.save(preferences);await persist(clean);return show()}
 async function importDocuments(files){const c=validate(await load());await fs.mkdir(path.join(base(),'knowledge'),{recursive:true})
  for(const source of files){if(!['.md','.txt'].includes(path.extname(source).toLowerCase()))throw Error('仅支持Markdown和TXT');const bytes=await fs.readFile(source);if(bytes.length>256*1024||bytes.includes(0))throw Error('单个资料须为不超过256KiB的文本');const id=crypto.createHash('sha256').update(bytes).digest('hex');if(c.documents.some(d=>d.id===id))continue;const relative=`knowledge/${id}.md`;await fs.writeFile(path.join(base(),relative),bytes,{flag:'wx'}).catch(e=>{if(e.code!=='EEXIST')throw e});c.documents.push({id,path:relative,label:path.basename(source).slice(0,150)})}
  await persist(c);return show()
 }
 async function context(key,request={}){if(!flows[key])throw Error('未知AI工作流');const c=validate(await load()),flow=c.workflows[key],knowledge=[];let total=0
  let bundle;if(request.retrieval){if(!retrieve)throw Error('当前环境无法校验参考集合');bundle=await retrieve({...request.retrieval,workflow:key});if(bundle.workflow!==key||!Array.isArray(bundle.sources)||!Array.isArray(bundle.knowledge)||!Array.isArray(bundle.references))throw Error('参考集合工作流或内容无效');knowledge.push(...bundle.knowledge)}
  for(const id of request.retrieval?[]:flow.knowledge){const b=builtins[id],d=c.documents.find(d=>d.id===id);const content=await fs.readFile(b?path.join(skill,'references',b.file):path.join(base(),d.path),'utf8');total+=content.length;if(total>48000)throw Error('本工作流资料总量超过48000字，请减少选中的文档');knowledge.push({label:b?.label??d.label,content})}
  const preference=await styles.context(key)
  return {style:preference.values,style_prompt:preference.prompt,attachViewport:flow.attachViewport===true,workflow:key,workflow_steps:flows[key].steps,base_rules:flows[key].rules,...(flow.rules===flows[key].rules?{}:{rules:flow.rules}),instruction:flow.instruction,knowledge,...(bundle?{reference_sources:bundle.sources,retrieved_assets:bundle.references}:{})}
 }
 async function preview(id){const c=validate(await load()),b=builtins[id],d=c.documents.find(d=>d.id===id);if(!b&&!d)throw Error('未知内部资料');return {title:b?.label??d.label,recipient:'仅在勾选并保存后，默认随对应工作流发送全文；使用本地检索集合后只发送所选片段给已配置的 API。',text:await fs.readFile(b?path.join(skill,'references',b.file):path.join(base(),d.path),'utf8')}}
 return {show,save,importDocuments,context,preview}
}
module.exports={createInternalAI,flows}
