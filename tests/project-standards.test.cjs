const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm')
const {cleanContext}=require('../desktop/workbench-contract.cjs')
const base=path.join(__dirname,'../.agents/skills/minecraft-nbt-modeler/prompt-console'),scope=vm.createContext({crypto:globalThis.crypto,TextEncoder})
for(const file of ['catalog.js','core.js','ai-input.js'])vm.runInContext(fs.readFileSync(path.join(base,file),'utf8'),scope)
test('project rules and building exceptions remain in handoff and AI context without modifying model parameters',()=>{
 const doc=scope.NbtPrompt.defaults();doc.design_standard={schema_version:1,revision:3,sha256:'a'.repeat(64),fields:{name:'山城',materials:'石砖',dimensions:'净高4格',circulation:'保持道路通畅',style:'石构',references:'参考图说明',notes:''}};doc.design_override='茶馆可以采用木廊'
 const before=JSON.stringify(doc.project),text=scope.NbtPrompt.prompt(doc);assert.match(text,/修订 3/);assert.match(text,/茶馆可以采用木廊/);assert.ok(text.indexOf('# 项目设计规范')<text.indexOf('# 建筑对象与关系'))
 const design={project:doc.project,operations:[],project_standard:scope.NbtPrompt.standardText(doc)},request=scope.NbtPromptAIInput.request('draft','编写茶馆要求',design),clean=cleanContext(request.context)
 assert.match(clean.project_standard,/净高4格/);assert.match(clean.project_standard,/茶馆可以采用木廊/);assert.equal(JSON.stringify(doc.project),before);assert.equal(clean.operations.length,0);assert.equal(scope.NbtPrompt.normalize(doc).design_standard.revision,3)
 const prose=scope.NbtPromptAIInput.request('text','润色',design);assert.match(prose.instruction,/参考图说明/)
})
test('invalid imported rule snapshots and oversized API context fail clearly',()=>{
 const doc=scope.NbtPrompt.defaults();doc.design_standard={fields:{materials:42},revision:1,sha256:'bad'};assert.ok(scope.NbtPrompt.validate(doc).some(error=>error.includes('规范')))
 assert.throws(()=>cleanContext({project:{size:[48,24,48]},project_standard:'x'.repeat(40001)}),/规范/)
})
