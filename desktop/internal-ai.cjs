const fs=require('node:fs/promises'),path=require('node:path'),crypto=require('node:crypto')
const flows={
 draft:{label:'提示词方案 · 完整初稿',steps:'读取设计要求 → 补齐空间与构造 → 返回表单和工具候选 → 用户采用 → 复制给Agent制作',rules:'先整体空间后材质细节；补齐入口、主空间、辅助区、高差、支承及玩家动线。不得把方案说成已生成的NBT。'},
 workbench:{label:'提示词方案 · 配置控件',steps:'读取当前表单 → 提议设计字段和工具序列 → 校验 → 用户采用',rules:'保留不需修改的字段与步骤；已有模型尺寸、路径、阶段和保护保持本地值。'},
 prompt:{label:'提示词方案 / 模型编辑 · 文字编写',steps:'读取本次文字要求 → 补充设计说明 → 返回候选正文 → 用户采用或复制',rules:'使用简体中文和具体构造说明，不声称已执行、已看图或已获批准。'},
 structure:{label:'模型编辑 · 局部编辑',steps:'读取局部选区与材质 → 生成填充/换块候选 → 本地校验 → 预览 → 用户导出',rules:'严格留在选区内；保护必要路线和承重，不能降低验证要求。'},
 small_structure:{label:'模型编辑 · 小型结构 / 3D放置',steps:'3D选点或XYZ选区 → 生成受限构件步骤 → 校验 → 候选插入 → 刷新3D → 用户导出',rules:'构件应有支承和使用空间。仅用允许的box/beam/frame步骤，不改变选区、源文件或批准。'}
}
const builtins={
 'builtin:design':{label:'整体创作原则',file:'design-principles.md'},
 'builtin:space':{label:'空间与构造细节',file:'spatial-detail-design.md'},
 'builtin:scale':{label:'玩家尺度',file:'player-scale.md'},
 'builtin:tools':{label:'建模工具说明',file:'modelling-tools.md'},
 'builtin:delivery':{label:'输出与归档规范',file:'output-storage.md'}
}
function createInternalAI({workspace,skill}){
 const base=()=>path.join(workspace(),'.nbtcreator','internal-ai'),file=()=>path.join(base(),'config.json')
 const defaults=()=>({schema_version:1,workflows:Object.fromEntries(Object.entries(flows).map(([key,value])=>[key,{rules:value.rules,instruction:'',knowledge:[]}])),documents:[]})
 async function load(){try{return JSON.parse(await fs.readFile(file(),'utf8'))}catch(e){if(e.code==='ENOENT')return defaults();throw e}}
 function validate(c){
  if(!c||c.schema_version!==1||!c.workflows||!Array.isArray(c.documents)||c.documents.length>100)throw Error('内部AI配置无效')
  const ids=new Set(Object.keys(builtins))
  for(const d of c.documents){if(!/^[a-f0-9]{64}$/.test(d.id)||d.path!==`knowledge/${d.id}.md`||typeof d.label!=='string'||d.label.length>150)throw Error('内部资料记录无效');ids.add(d.id)}
  if(Object.keys(c.workflows).some(k=>!flows[k]))throw Error('未知AI工作流')
  for(const key of Object.keys(flows)){const f=c.workflows[key];if(!f||typeof f.rules!=='string'||f.rules.length>12000||typeof f.instruction!=='string'||f.instruction.length>6000||!Array.isArray(f.knowledge)||f.knowledge.some(id=>!ids.has(id)))throw Error('工作流规则或资料选择无效')}
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
  return {workflow:key,workflow_steps:flows[key].steps,rules:flow.rules,instruction:flow.instruction,knowledge}
 }
 return {show,save,importDocuments,context}
}
module.exports={createInternalAI,flows}
