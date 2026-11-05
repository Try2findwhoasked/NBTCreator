const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path')
const {normalizeReply}=require('../desktop/ai-output-normalize.cjs'),{cleanContext,validateWorkbench}=require('../desktop/workbench-contract.cjs')
const scope=vm.createContext({});for(const name of ['catalog.js','core.js'])vm.runInContext(fs.readFileSync(path.join(__dirname,'../.agents/skills/minecraft-nbt-modeler/prompt-console',name),'utf8'),scope)
const C=scope.NbtPrompt
test('AI accepted beams in steps 21-23 remain valid in the prompt editor without redundant bounds',()=>{
 const design=C.defaults();design.operations=Array.from({length:20},()=>C.operation('box'))
 const beam={kind:'beam',start:[5,5,5],end:[15,8,5],state:'stone_bricks',width:1}
 const operations=[...JSON.parse(JSON.stringify(design.operations)),beam,{...beam,start:[5,5,8],end:[15,8,8]},{...beam,start:[5,5,11],end:[15,8,11]}]
 const ctx=cleanContext({project:{size:[48,24,48]},operations:[]}),result=validateWorkbench(normalizeReply({operations},'workbench',ctx),ctx)
 design.operations=result.operations;assert.deepEqual(Array.from(C.validate(design)),[])
 assert.equal(C.plan(design).operations[20].lo,undefined);assert.deepEqual(Array.from(C.plan(design).operations[20].start),[5,5,5])
})
test('beam endpoints still require bounded integers and ordinary region tools retain bounds checks',()=>{
 for(const patch of [{start:[1,2]},{end:[1,'2',3]},{end:[48,2,3]}]){const d=C.defaults();d.operations=[{kind:'beam',label:'梁',classification:'body',start:[1,2,3],end:[4,2,3],state:'stone',...patch}];assert.ok(C.validate(d).length>0)}
 for(const kind of ['box','frame','pattern']){const d=C.defaults();d.operations=[{kind,label:'无选区',classification:'body',state:'stone'}];assert.doesNotThrow(()=>C.validate(d));assert.ok(C.validate(d).some(error=>error.includes('lo须为整数XYZ')))}
})
