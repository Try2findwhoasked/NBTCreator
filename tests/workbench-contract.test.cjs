const {test}=require('node:test'),assert=require('node:assert/strict')
const {validateWorkbench,cleanContext,operationBase}=require('../desktop/workbench-contract.cjs')
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

const step={kind:'box',label:'墙段',classification:'wall',lo:[2,1,2],hi:[20,8,2],state:'stone_bricks'}
test('model-created steps reject unknown fields while trusted baseline metadata survives a delta',()=>{
 for(const field of ['script','shell','write_bounds','write_group','max_writes','overwrite'])assert.throws(()=>validateWorkbench({summary:'候选',operations:[{...step,[field]:true}]},context),/未开放字段/)
 const trusted={...step,local_note:'保留',write_group:'trusted-local'},ctx=cleanContext({project:{size:[48,24,48]},operations:[trusted]}),base=operationBase(ctx)
 const result=validateWorkbench({summary:'换材',operation_patch:{baseline:base.baseline,changes:[{step:1,expected:base.steps[0].expected,set:{state:'andesite'}}]}},ctx)
 assert.equal(result.operations[0].write_group,'trusted-local');assert.equal(result.operations[0].local_note,'保留')
})
test('deltas use the catalog schema for nullable mirrors and scalar-or-vector scales',()=>{
 for(const [op,set] of [[{...step,kind:'transform_region',mirror:null,destination:[24,1,24],quarter_turns:0},{mirror:'x'}],[{...step,kind:'transform_region',mirror:'x',destination:[24,1,24],quarter_turns:0},{mirror:null}],[{...step,kind:'pattern',scale:6,palette:['stone']},{scale:[2,3,4]}],[{...step,kind:'pattern',scale:[2,3,4],palette:['stone']},{scale:6}]]){
  const ctx=cleanContext({project:{size:[48,24,48]},operations:[op]}),base=operationBase(ctx)
  assert.deepEqual(validateWorkbench({summary:'调整',operation_patch:{baseline:base.baseline,changes:[{step:1,expected:base.steps[0].expected,set}]}},ctx).operations[0],{...op,...set})
 }
})
const controls=binding=>cleanContext({project:{name:'大厅',size:[48,24,48]},operations:Array.from({length:60},()=>structuredClone(step)),baseline_binding:binding,existing_model:true})
function proposal(ctx,index=12,set={state:'andesite'}){const base=operationBase(ctx);return {summary:'只改墙面材质',operation_patch:{baseline:base.baseline,changes:[{step:index,expected:base.steps[index-1].expected,set}]}}}
test('one-step deltas preserve the other 59 steps and input objects, and compare original fingerprints',()=>{
 const ctx=controls('a'.repeat(64)),patch=proposal(ctx),before=JSON.stringify(ctx),original=JSON.stringify(patch),merged=validateWorkbench(patch,ctx)
 assert.equal(merged.operations.length,60);assert.equal(merged.operations[11].state,'andesite');assert.equal(merged.operation_patch,undefined)
 assert.deepEqual(merged.operations.slice(0,11),ctx.operations.slice(0,11));assert.deepEqual(merged.operations.slice(12),ctx.operations.slice(12));assert.equal(JSON.stringify(ctx),before);assert.equal(JSON.stringify(patch),original)
 const reordered={...ctx,operations:[{...ctx.operations[0],label:'新步骤'},...ctx.operations.slice(1)]};assert.throws(()=>validateWorkbench(patch,reordered),/基线/)
 assert.throws(()=>validateWorkbench(patch,controls('b'.repeat(64))),/基线/)
 assert.throws(()=>validateWorkbench({...patch,operation_patch:{...patch.operation_patch,changes:[{...patch.operation_patch.changes[0],expected:'0'.repeat(64)}]}},ctx),/原步骤指纹/)
})
test('deltas reject ambiguous replacement, permissions, invalid targets and invalid merged geometry atomically',()=>{
 const ctx=controls('a'.repeat(64)),p=proposal(ctx),change=p.operation_patch.changes[0],before=JSON.stringify(ctx)
 assert.throws(()=>validateWorkbench({...p,operations:[]},ctx),/同时返回/)
 for(const set of [{kind:'python'},{overwrite:true},{write_group:'foreign'},{max_writes:1000000},{script:'exec'},JSON.parse('{"__proto__":{"polluted":true}}')])assert.throws(()=>validateWorkbench(proposal(ctx,12,set),ctx),/只能修改/)
 for(const changes of [[],[change,change],[{...change,step:0}],[{...change,step:61}],Array(17).fill(change)])assert.throws(()=>validateWorkbench({...p,operation_patch:{...p.operation_patch,changes}},ctx))
 assert.throws(()=>validateWorkbench(proposal(ctx,12,{hi:[100,8,2]}),ctx),/超出/)
 assert.throws(()=>validateWorkbench(proposal(ctx,12,{classification:'unknown'}),ctx),/归属/)
 for(const set of [{state:1},{state:null},{lo:'0,0,0'},{enabled:'false'},{state:'$exec'}])assert.throws(()=>validateWorkbench(proposal(ctx,12,set),ctx))
 assert.throws(()=>validateWorkbench({...p,project_patch:{source:'private'}},ctx),/源路径/)
 assert.throws(()=>validateWorkbench(p,{...ctx,task:'draft'}),/已有方案/)
 assert.equal(JSON.stringify(ctx),before)
})
test('full baselines are cloned rather than truncated, allowing a small patch on step 100',()=>{
 const input={project:{size:[48,24,48]},operations:Array.from({length:128},()=>structuredClone(step))},ctx=cleanContext(input)
 input.operations[0].state='dirt';input.project.size[0]=1
 assert.equal(ctx.operations[0].state,'stone_bricks');assert.equal(ctx.project.size[0],48)
 assert.equal(validateWorkbench(proposal(ctx,100),ctx).operations[99].state,'andesite')
 assert.throws(()=>cleanContext({...input,operations:Array(129).fill(step)}),/不能静默截断/)
 assert.throws(()=>validateWorkbench({summary:'完整替换',operations:ctx.operations},ctx),/64/)
})
