const {test}=require('node:test'),assert=require('node:assert/strict')
const {normalizeReply}=require('../desktop/ai-output-normalize.cjs')
const {validateWorkbench,cleanContext,operationBase}=require('../desktop/workbench-contract.cjs')
test('palette boxes merge exact consecutive cuboids without filling gaps or reordering writes',()=>{
 const result=normalizeReply({palette:['stone','gold_block'],boxes:[[0,0,0,0,2,0,0],[1,0,0,1,2,0,0],[3,0,0,3,2,0,0],[0,0,0,0,0,0,1,'wall']]},'component',{})
 assert.equal(result.operations.length,3);assert.deepEqual(result.operations[0].hi,[1,2,0]);assert.deepEqual(result.operations[1].lo,[3,0,0]);assert.equal(result.operations[2].state,'gold_block');assert.equal(result.operations[2].classification,'wall');assert.equal(result.summary,undefined)
 for(const value of [{palette:['stone'],boxes:[[0,0,0,1,1,1,9]]},{boxes:[[0,0,0,1,1,1,'stone']],operations:[]},{boxes:[[1,0,0,0,1,1,'stone']]}])assert.throws(()=>normalizeReply(value,'component',{}))
})
test('script fills only structural metadata and binds omitted fingerprints to the original request',()=>{
 const context=cleanContext({project:{size:[8,8,8]},operations:[{kind:'box',label:'原步骤',classification:'wall',lo:[1,1,1],hi:[1,3,1],state:'stone'}]})
 const compact={operation_patch:{changes:[{step:1,set:{state:'andesite'}}]}},reply=normalizeReply(compact,'workbench',context),base=operationBase(context)
 assert.equal(reply.operation_patch.baseline,base.baseline);assert.equal(reply.operation_patch.changes[0].expected,base.steps[0].expected);assert.equal(validateWorkbench(reply,context).operations[0].classification,'wall');assert.equal(compact.operation_patch.baseline,undefined)
 const wrong=normalizeReply({operation_patch:{baseline:'0'.repeat(64),changes:[{step:1,set:{state:'stone'}}]}},'workbench',context);assert.throws(()=>validateWorkbench(wrong,context))
 const unsafe=normalizeReply({operations:[{kind:'box',lo:[1,1,1],hi:[1,2,1],state:'stone',shell:'exec'}]},'selection_edit',{});assert.equal(unsafe.operations[0].shell,'exec','normalization must not hide fields from validators')
 assert.equal(unsafe.operations[0].classification,'inherit','selection edits must retain the engine wall-ownership default')
 assert.equal(normalizeReply({boxes:[[0,0,0,0,0,0,'stone']]},'selection_edit',{}).operations[0].classification,'inherit')
})
test('standard block objects normalize in local edits, compact palettes and incremental patches',()=>{
 const state={Name:'minecraft:oak_log',Properties:{axis:'y'}}
 const reply=normalizeReply({settings_patch:{structure:{state}}},'structure',{});assert.equal(reply.settings_patch.structure.state,'minecraft:oak_log[axis=y]')
 assert.equal(normalizeReply({palette:[state],boxes:[[0,0,0,0,1,0,0]]},'component',{}).operations[0].state,'minecraft:oak_log[axis=y]')
 const ctx=cleanContext({project:{size:[8,8,8]},operations:[{kind:'box'}]})
 assert.equal(normalizeReply({operation_patch:{changes:[{step:1,set:{state}}]}},'workbench',ctx).operation_patch.changes[0].set.state,'minecraft:oak_log[axis=y]')
})
