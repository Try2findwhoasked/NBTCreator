import assert from 'node:assert/strict'
import test from 'node:test'
import '../../.agents/skills/minecraft-nbt-modeler/prompt-console/catalog.js'
import '../../.agents/skills/minecraft-nbt-modeler/prompt-console/core.js'
const C=globalThis.NbtPrompt

test('archive classification preserves design dimensions and occupancy',()=>{
 assert.equal(Object.keys(C.buildingShapes).length,8)
 for(const key of Object.keys(C.buildingShapes)){
  const state=C.defaults(),size=[...state.project.size],cells=[...state.project.context.cells];state.project.name='试作大厅';C.applyShape(state.project,key)
  assert.deepEqual(state.project.size,size)
  assert.deepEqual(state.project.context.cells,cells)
  assert.deepEqual(C.validate(state),[])
  assert.equal(C.outputPath(state.project),`nbt_models/${key}/试作大厅`)
  assert.ok(C.prompt(state).includes('WorkingModel.save_draft'))
 }
})

test('draft archive is derived while existing-model output remains explicit',()=>{
 const state=C.defaults();state.project.name='新/建筑:名称';state.project.output='D:/private/previous-version'
 assert.equal(C.outputPath(state.project),'nbt_models/standalone/新_建筑_名称')
 const prompt=C.prompt(state)
 assert.ok(!prompt.includes('D:/private'))
 assert.ok(prompt.includes('不限制初稿总方块量'))
 state.project.stage='plan';assert.equal(C.outputPath(state.project),'D:/private/previous-version')
 const legacy=C.defaults();delete legacy.project.buildingShape;legacy.project.size=[48,24,96]
 assert.equal(C.normalize(legacy).project.buildingShape,'long')
})

test('draft prompts export the selected integration context without editing the input',()=>{
 const state=C.defaults()
 Object.assign(state.project.context,{mode:'saodg',ports:[],door_y:2})
 const context=()=>JSON.parse(C.prompt(state).split('# 验证上下文草案')[1].split('```')[1].slice(4))
 assert.equal(context().mode,'standalone')
 assert.deepEqual(context().openings,[])
 assert.ok(!Object.hasOwn(context(),'door_y'))
 assert.ok(!Object.hasOwn(context(),'ports'))
 assert.equal(state.project.context.door_y,2)
 state.project.context.openings=[{id:'old-opening'}]
 state.project.integration='saodg'
 assert.equal(context().mode,'saodg')
 assert.ok(!Object.hasOwn(context(),'openings'))
 assert.deepEqual(context(),C.exportContext(state))
 assert.equal(context().door_y,2)
 assert.deepEqual(context().ports,[])
 state.project.stage='refine'
 state.project.source='existing/master/model.snbt'
 state.project.integration='saodg'
 delete state.project.context.mode
 assert.equal(C.effectiveProject(state).integration,'standalone')
 assert.deepEqual(context(),{...state.project.context,max_changed_blocks:state.project.budget})
 delete state.project.context.openings
 assert.equal(C.effectiveProject(state).integration,'saodg')
 assert.deepEqual(context(),{...state.project.context,max_changed_blocks:state.project.budget})
})

test('read-only prompt diagnoses candidates without asking for production work',()=>{
 const state=C.defaults()
 state.project.source='existing/master/model.snbt'
 state.project.stage='plan'
 state.operations=[C.operation('box')]
 const text=C.prompt(state)
 for(const required of ['只读检查源','列出缺失坐标','待补的坐标','后续阶段参考','真实缩略图','明确要求定稿'])assert.ok(text.includes(required),required)
 for(const forbidden of ['分配下一版本','核对每步选区和真实模型后再执行','制作阶段交付完整','自动存放规则','出整体、无剖切入口'])assert.ok(!text.includes(forbidden),forbidden)
 state.project.stage='refine'
 for(const required of ['分配下一版本','真实用户精修确认','制作阶段交付完整'])assert.ok(C.prompt(state).includes(required),required)
})
