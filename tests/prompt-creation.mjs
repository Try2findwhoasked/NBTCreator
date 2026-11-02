import assert from 'node:assert/strict'
import test from 'node:test'
import '../.agents/skills/minecraft-nbt-modeler/prompt-console/catalog.js'
import '../.agents/skills/minecraft-nbt-modeler/prompt-console/core.js'
const C=globalThis.NbtPrompt

test('all canonical building shapes fill dimensions, occupancy and portable archive paths',()=>{
 assert.equal(Object.keys(C.buildingShapes).length,8)
 for(const key of Object.keys(C.buildingShapes)){
  const state=C.defaults();state.project.name='试作大厅';C.applyShape(state.project,key)
  assert.deepEqual(state.project.size,C.buildingShapes[key].size)
  assert.deepEqual(state.project.context.cells,C.buildingShapes[key].cells)
  assert.deepEqual(C.validate(state),[])
  assert.equal(C.outputPath(state.project),`nbt_models/${key}/试作大厅`)
  assert.ok(C.prompt(state).includes('nbt_library.py new'))
 }
})

test('draft archive is derived while existing-model output remains explicit',()=>{
 const state=C.defaults();state.project.name='新/建筑:名称';state.project.output='D:/private/previous-version'
 assert.equal(C.outputPath(state.project),'nbt_models/single/新_建筑_名称')
 const prompt=C.prompt(state)
 assert.ok(!prompt.includes('D:/private'))
 assert.ok(prompt.includes('不限制初稿总方块量'))
 state.project.stage='plan';assert.equal(C.outputPath(state.project),'D:/private/previous-version')
 const legacy=C.defaults();delete legacy.project.buildingShape;legacy.project.size=[48,24,96]
 assert.equal(C.normalize(legacy).project.buildingShape,'long')
})
