const {test}=require('node:test'),assert=require('node:assert/strict')
const {validateWorkbench,cleanContext}=require('../desktop/workbench-contract.cjs')
const context=cleanContext({project:{name:'大厅',size:[48,24,48],source:'private-path',budget:100},existing_model:true,operations:[]})
test('workbench can adjust editable fields and sequence while paths are removed',()=>{assert.equal(context.project.source,undefined);assert.equal(context.project.budget,undefined);assert.equal(validateWorkbench({summary:'加强层次',project_patch:{theme:'石构大厅',ceiling:'梁端落柱'},operations:[{kind:'box',label:'柱',classification:'body',lo:[4,4,4],hi:[4,8,4],state:'stone_bricks'}]},context).project_patch.ceiling,'梁端落柱')})
test('workbench preserves disabled draft steps but rejects ambiguous switches',()=>{const step={kind:'box',label:'保留草稿',classification:'body',enabled:false};assert.equal(validateWorkbench({summary:'保留',operations:[step]},context).operations[0].enabled,false);for(const enabled of [0,'false',null])assert.throws(()=>validateWorkbench({summary:'错误开关',operations:[{...step,enabled}]},context),/布尔/);assert.throws(()=>validateWorkbench({summary:'重新启用需要选区',operations:[{...step,enabled:true}]},context),/XYZ/)})
test('workbench refuses source, stage, budget, unknown tools and resizing existing source',()=>{for(const key of ['source','stage','budget','context'])assert.throws(()=>validateWorkbench({summary:'bad',project_patch:{[key]:'bad'}},context));assert.throws(()=>validateWorkbench({summary:'bad',project_patch:{size:[96,24,48]}},context));assert.throws(()=>validateWorkbench({summary:'bad',operations:[{kind:'python',label:'bad',classification:'body'}]},context));assert.throws(()=>validateWorkbench({summary:'bad',operations:[{kind:'box',label:'bad',classification:'body',lo:[0,0,0],hi:[50,2,2]}]},context))})

test('complete first-draft proposal requires design, circulation and initial construction',()=>{
 const draft=cleanContext({task:'draft',project:{size:[48,24,48],buildingShape:'single'},existing_model:false,operations:[]})
 const patch=Object.fromEntries(['name','theme','purpose','layout','circulation','style','ceiling','floor','wall','props'].map(k=>[k,'完整设计说明']))
 const result={summary:'初稿',project_patch:{...patch,buildingShape:'single'},operations:[{kind:'box',label:'主题平台',classification:'body',lo:[5,2,5],hi:[10,3,10],state:'stone_bricks'}]}
 assert.equal(validateWorkbench(result,draft),result)
 assert.throws(()=>validateWorkbench({...result,operations:[]},draft),/初始构造/)
 assert.throws(()=>validateWorkbench({...result,project_patch:{...patch,circulation:''}},draft),/circulation/)
 assert.throws(()=>validateWorkbench({...result,project_patch:{...patch,buildingShape:'unknown'}},draft),/形状/)
 assert.throws(()=>cleanContext({task:'draft',project:{size:[48,24,48]},existing_model:true}),/新建任务/)
})
