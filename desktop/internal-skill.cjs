const fs=require('node:fs'),path=require('node:path')
const catalog=require('../.agents/skills/minecraft-nbt-modeler/tool-catalog.json')
const directory=path.join(__dirname,'skills/nbtcreator-internal'),cache=new Map()
function read(name){if(!cache.has(name)){const text=fs.readFileSync(path.join(directory,name),'utf8');cache.set(name,text.replace(/^---\r?\n[\s\S]*?\r?\n---\r?\n/,'').trim())}return cache.get(name)}
const common=['label','classification','lo','hi','enabled']
const strictGuide='严格 JSON 中每个对象都须包含所选 Schema 分支的全部键，不加额外键。没有值的可空字段填 null；必填数组仅在允许零项时用 []，有最小项数的数组须满足下限。使用嵌套对象时按其定义填全键，不能用 {} 占位。必填文本、坐标和工具实际需要的参数须给有效值。映射字段按 Schema 使用 [{"key":"原状态","value":"目标状态"}] 数组。summary 为1～160字。'
function concise(schema){if(Array.isArray(schema))return schema.map(concise);if(!schema||typeof schema!=='object')return schema;return Object.fromEntries(Object.entries(schema).filter(([key])=>!['description','title','default','examples'].includes(key)).map(([key,value])=>[key,concise(value)]))}
function toolContract(kinds=Object.keys(catalog.tools)){
 const selected=new Set(kinds)
 return {common:concise(Object.fromEntries(common.map(key=>[key,catalog.operation_parameters.box.properties[key]]))),tools:Object.fromEntries(Object.entries(catalog.operation_parameters).filter(([kind])=>selected.has(kind)).map(([kind,schema])=>[kind,{name:catalog.tools[kind][0],rules:catalog.tools[kind][2],...concise({...schema,properties:Object.fromEntries(Object.entries(schema.properties).filter(([key])=>!common.includes(key)))})}])),...(selected.has('geometry')?{geometry_parameters:concise(catalog.geometry_parameters),shapes:catalog.shapes}:{})}
}
function selectTools(instruction='',context={}){
 const selected=new Set(['box','hollow_box','beam','frame','replace'])
 function scan(value,depth=0){if(depth>8||!value||typeof value!=='object')return;if(Array.isArray(value)){value.slice(0,128).forEach(v=>scan(v,depth+1));return}if(Object.hasOwn(catalog.tools,value.kind))selected.add(value.kind);Object.values(value).forEach(v=>scan(v,depth+1))}
 scan(context)
 const text=instruction.toLowerCase()
 for(const kind of Object.keys(catalog.tools))if(new RegExp('(^|[^a-z_])'+kind+'($|[^a-z_])').test(text))selected.add(kind)
 const routes=[[/曲面|圆|弧|球|穹|布尔|挤出|拉伸|csg|loft|sweep|curv|sphere|dome|circular|extrud|lathe/i,['geometry']],[/楼梯|台阶|stairs/i,['auto_stairs']],
  [/屋顶|屋面|roof/i,['auto_roof']], [/道路|公路|road/i,['auto_road','terrain_road']],
  [/复制|阵列|重复|旋转|镜像|copy|array|repeat|rotate|mirror/i,['copy_region','repeat_region','transform_region','array_region']],
  [/混材|纹理|配色|噪声|pattern/i,['pattern','surface_palette']], [/风化|破损|weather/i,['weathering']],
  [/散布|散落|scatter/i,['scatter']], [/膨胀|侵蚀|morph/i,['morphology']], [/扩散|diffus/i,['diffusion']],
  [/爆炸|爆破|explos/i,['explosion']], [/地板|地面|floor/i,['auto_floor']], [/对齐|吸附|align/i,['align_region']]]
 for(const [match,kinds]of routes)if(match.test(text))kinds.forEach(kind=>selected.add(kind))
 return Object.keys(catalog.tools).filter(kind=>selected.has(kind))
}
const registry=require('../.agents/skills/minecraft-nbt-modeler/references/block-registry-1.20.1.json')
const materialChoices=['air','stone','stone_bricks','cracked_stone_bricks','mossy_stone_bricks','cobblestone','mossy_cobblestone','andesite','polished_andesite','deepslate_bricks','deepslate_tiles','sandstone','chiseled_sandstone','smooth_sandstone','oak_planks','spruce_planks','oak_log','spruce_log','stone_brick_slab','stone_brick_stairs','sandstone_slab'].filter(name=>registry.blocks['minecraft:'+name])
function buildInternalPrompt(mode,context={},options={}){
 if(!['prompt','structure','small_structure','component','selection_edit','workbench'].includes(mode))throw Error('未知内部Skill工作流')
 if(mode==='workbench'&&context.task==='constraint')return '根据用户要求编写一项可复用的建筑约束候选，返回一个JSON对象{name,rules}。名称1～80字。至少给一项明确规则。'+(options.strictSchema?'rules 的全部规则键都须出现，未指定的规则填 null。':'rules 只列明确的规则，未指定的键省略。')+'不输出工具步骤、代码、路径或执行权限，不声称已保存或已批准。size_policy需要size；cells需要cell_size，必须不重复且不能超出size。尺寸单位为方块，cells为XZ网格坐标。'+(options.strictSchema?'规则值以随附 Schema 为准。':'规则字段契约：'+JSON.stringify(catalog.project_constraints.rules))
 if(mode==='workbench'&&context.task==='brief'){
  const names=context.brief_scope?.editable_fields??Object.keys(catalog.prompt_design.fields)
  const labels=Object.fromEntries(names.map(key=>[key,catalog.prompt_design.fields[key].label]))
  return read('references/brief.md')+(options.strictSchema?'\n'+strictGuide:'')+'\n本次允许修改的设计项：'+JSON.stringify(labels)+(names.includes('buildingShape')?'\nbuilding_shapes：'+JSON.stringify(Object.keys(catalog.building_shapes)):'')
 }
 let guide=read('references/'+mode+'.md')
 if(mode==='small_structure'&&options.strictSchema){
  guide=guide.split('## 普通 JSON')[0].trim()+'\n使用 settings_patch.operations，须有1～48步。填写 coordinate_space: "local"、structure_name、选区局部 lo/hi 及每步的 lo/hi。camera 未指定时填 null。'
 }
 const parts=mode==='prompt'?[guide]:[read('SKILL.md').split('## 维护路由')[0].trim(),guide]
 if(mode!=='prompt'&&options.strictSchema)parts.push(strictGuide)
 if(mode==='workbench'&&context.task==='controls'&&options.strictSchema)parts.push('修改 transform_region 步骤时，set.mirror 填 null 表示保留原值，填 "x" 或 "z" 设置镜像，填 {"value":null} 显式清除镜像。')
 if(!options.strictSchema&&['component','selection_edit','workbench'].includes(mode)){
  const contract=toolContract(options.fullTools?undefined:selectTools(options.instruction??'',context))
  parts.push('操作采用扁平对象，kind指定工具。公共字段common只作定义，不嵌套到步骤中；各工具的专属字段不得混用。示例：{"kind":"box","lo":[0,0,0],"hi":[0,2,0],"state":"stone_bricks"}。坐标按本次任务调整。随附当前任务所需工具；required和参数范围仍逐项适用：'+JSON.stringify(contract))
 }
 if(['component','selection_edit','workbench'].includes(mode))parts.push('方块优先从已验证的1.20.1材质选择：'+materialChoices.join(',')+'。其他方块也须确实存在于1.20.1，不能使用tuff_bricks等不存在于该版本的名称。属性必须合法，底半砖用type=bottom。')
 if(mode==='component'&&!options.strictSchema)parts.push('spec定义：'+JSON.stringify(concise(catalog.agent_tools.structure_preview.parameters.properties.spec)))
 if(mode==='workbench'){
  if(!options.strictSchema){
   const fields=Object.entries(catalog.prompt_design.fields).filter(([key])=>!context.existing_model||!['size','buildingShape'].includes(key))
   parts.push('project_patch 可改设计字段：'+JSON.stringify(Object.fromEntries(fields.map(([key,field])=>[key,field.label]))))
  }
  if(context.task==='draft')parts.push(read('references/draft.md'),'building_shapes：'+JSON.stringify(catalog.building_shapes))
  if(context.task==='controls')parts.push(read('references/controls.md'))
 }
 if(!options.strictSchema&&['component','selection_edit','workbench'].includes(mode))parts.push('紧凑格式：boxes:[[x0,y0,z0,x1,y1,z1,材质,可选归属]]；可选palette:[状态]后写材质索引，与operations互斥。脚本补步骤名和归属、合并连续完整长方体；summary可省略，独立资产不返回summary。复杂工具仍用对象，不能省略几何参数。')
 return parts.join('\n')
}
module.exports={buildInternalPrompt,toolContract,selectTools}
