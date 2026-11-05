const fs=require('node:fs'),path=require('node:path')
const catalog=require('../.agents/skills/minecraft-nbt-modeler/tool-catalog.json')
const directory=path.join(__dirname,'skills/nbtcreator-internal'),cache=new Map()
function read(name){if(!cache.has(name)){const text=fs.readFileSync(path.join(directory,name),'utf8');cache.set(name,text.replace(/^---\r?\n[\s\S]*?\r?\n---\r?\n/,'').trim())}return cache.get(name)}
const common=['label','classification','lo','hi','enabled']
function concise(schema){if(Array.isArray(schema))return schema.map(concise);if(!schema||typeof schema!=='object')return schema;return Object.fromEntries(Object.entries(schema).filter(([key])=>!['description','title','default','examples'].includes(key)).map(([key,value])=>[key,concise(value)]))}
function toolContract(){return {common:concise(Object.fromEntries(common.map(key=>[key,catalog.operation_parameters.box.properties[key]]))),tools:Object.fromEntries(Object.entries(catalog.operation_parameters).map(([kind,schema])=>[kind,{name:catalog.tools[kind][0],rules:catalog.tools[kind][2],...concise({...schema,properties:Object.fromEntries(Object.entries(schema.properties).filter(([key])=>!common.includes(key)))})}])),geometry_parameters:concise(catalog.geometry_parameters),shapes:catalog.shapes}}
const contract=JSON.stringify(toolContract())
const registry=require('../.agents/skills/minecraft-nbt-modeler/references/block-registry-1.20.1.json')
const materialChoices=['air','stone','stone_bricks','cracked_stone_bricks','mossy_stone_bricks','cobblestone','mossy_cobblestone','andesite','polished_andesite','deepslate_bricks','deepslate_tiles','sandstone','chiseled_sandstone','smooth_sandstone','oak_planks','spruce_planks','oak_log','spruce_log','stone_brick_slab','stone_brick_stairs','sandstone_slab'].filter(name=>registry.blocks['minecraft:'+name])
function buildInternalPrompt(mode,context={}){
 if(!['prompt','structure','small_structure','component','selection_edit','workbench'].includes(mode))throw Error('未知内部Skill工作流')
 if(mode==='workbench'&&context.task==='brief')return read('references/brief.md')+'\nbuilding_shapes：'+JSON.stringify(Object.keys(catalog.building_shapes))
 const parts=mode==='prompt'?[read('references/prompt.md')]:[read('SKILL.md').split('## 维护路由')[0].trim(),read('references/'+mode+'.md')]
 if(['component','selection_edit','workbench'].includes(mode))parts.push('操作是扁平对象，用kind作为工具键，不嵌套common，不用type；最小示例：{"kind":"box","lo":[0,0,0],"hi":[0,2,0],"state":"stone_bricks"}。示例坐标须按本次任务调整。共用工具字段（common适用于所有工具；required仍按每种工具；非公共字段不得混用）：'+contract)
 if(['component','selection_edit','workbench'].includes(mode))parts.push('方块优先从已验证的1.20.1材质选择：'+materialChoices.join(',')+'。其他方块也须确实存在于1.20.1，不能使用tuff_bricks等不存在于该版本的名称。属性必须合法，底半砖用type=bottom。')
 if(mode==='component')parts.push('spec定义：'+JSON.stringify(concise(catalog.agent_tools.structure_preview.parameters.properties.spec)))
 if(mode==='workbench'){
  if(context.task==='draft')parts.push(read('references/draft.md'),'building_shapes：'+JSON.stringify(catalog.building_shapes))
  if(context.task==='controls')parts.push(read('references/controls.md'))
 }
 if(mode!=='prompt'&&mode!=='structure')parts.push('紧凑格式：boxes:[[x0,y0,z0,x1,y1,z1,材质,可选归属]]；可选palette:[状态]后写材质索引，与operations互斥。脚本补步骤名和归属、合并连续完整长方体；summary可省略，独立资产不返回summary。复杂工具仍用对象，不能省略几何参数。')
 return parts.join('\n')
}
module.exports={buildInternalPrompt,toolContract}
