const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),{createHash}=require('node:crypto')
const {cleanContext,validateWorkbench}=require('../desktop/workbench-contract.cjs')
const {createApiService}=require('../desktop/api-service.cjs')
const {createCandidateValidator}=require('../desktop/ai-candidate-validator.cjs')
const base=path.join(__dirname,'../.agents/skills/minecraft-nbt-modeler/prompt-console'),scope=vm.createContext({crypto:globalThis.crypto,TextEncoder})
for(const file of ['catalog.js','constraint-contract.cjs','core.js','ai-input.js'])vm.runInContext(fs.readFileSync(path.join(base,file),'utf8'),scope)
const plain=value=>JSON.parse(JSON.stringify(value))
function constraint(rules,name='L形约束',id='constraint-'+'a'.repeat(32)){
 const item={schema_version:1,id,revision:1,name,rules}
 const stable=value=>Array.isArray(value)?value.map(stable):value&&typeof value==='object'?Object.fromEntries(Object.keys(value).sort().map(key=>[key,stable(value[key])])):value
 return {...item,sha256:createHash('sha256').update(JSON.stringify(stable(item))).digest('hex')}
}
test('archive classification no longer injects shape templates or a default single-cell constraint',()=>{
 const C=scope.NbtPrompt,doc=C.defaults(),before=JSON.stringify(doc.project);assert.equal(doc.project.buildingShape,'standalone');assert.equal(doc.constraints,undefined)
 C.applyShape(doc.project,'l_shape');assert.deepEqual(plain(doc.project.size),[48,24,48]);assert.deepEqual(plain(doc.project.context.cells),[]);assert.equal(doc.project.footprint,JSON.parse(before).footprint)
})
test('selected custom-grid constraints reach prompt, AI and exports without mutating free design fields',()=>{
 const C=scope.NbtPrompt,doc=C.defaults(),before=JSON.stringify(doc.project)
 doc.constraints=[constraint({buildingShape:'l_shape',size:[64,24,64],cell_size:32,cells:[[0,0],[0,1],[1,1]],requirements:'缺角留作庭院'})]
 const effective=C.effectiveProject(doc),text=C.prompt(doc);assert.match(text,/# 已选项目约束/);assert.match(text,/缺角留作庭院/);assert.match(text,/64 × 24 × 64/);assert.match(text,/固定尺寸/);assert.equal(JSON.stringify(doc.project),before)
 assert.equal(effective.context.cell_size,32);assert.equal(C.outputPath(effective),'nbt_models/l_shape/遗迹大厅');assert.deepEqual(plain(C.validate(doc)),[])
 const input=scope.NbtPromptAIInput.request('draft','编写设计',{project:effective,operations:[],constraints:doc.constraints}),clean=cleanContext(plain(input.context));assert.equal(clean.project.size_policy,'fixed');assert.equal(clean.constraints[0].name,'L形约束')
 const prose=scope.NbtPromptAIInput.request('text','润色',{project:effective,operations:[],constraints:doc.constraints});assert.match(prose.instruction,/缺角留作庭院/)
 delete doc.constraints;assert.equal(JSON.stringify(C.effectiveProject(doc)),before)
})
test('conflicting, malformed and forged references fail and AI cannot override selected constraints',()=>{
 const C=scope.NbtPrompt,doc=C.defaults(),first=constraint({size:[64,24,64],buildingShape:'l_shape',footprint:'保留庭院'})
 doc.constraints=[first,constraint({size:[32,24,32]},'单格','constraint-'+'b'.repeat(32))];assert.match(C.validate(doc)[0],/冲突/)
 doc.constraints=[first,constraint({size:[64,24,64],size_policy:'reference'},'参考尺寸','constraint-'+'b'.repeat(32))];assert.match(C.validate(doc)[0],/冲突/)
 doc.constraints={};assert.match(C.validate(doc)[0],/约束/)
 const clean=cleanContext({task:'brief',project:plain(C.defaults().project),constraints:[first],brief_scope:{editable_fields:['size','buildingShape','footprint','style']},operations:[]})
 for(const patch of [{size:[48,24,48]},{buildingShape:'single'},{footprint:'占满缺角'}])assert.throws(()=>validateWorkbench({summary:'修改',project_patch:patch},clean),/已选项目约束/)
 assert.equal(validateWorkbench({summary:'修改风格',project_patch:{style:'石木构造'}},clean).project_patch.style,'石木构造')
 assert.throws(()=>cleanContext({project:{size:[48,24,48]},constraints:[{...first,name:'伪造'}]}),/哈希/)
 assert.throws(()=>cleanContext({project:{size:[48,24,48],buildingShape:'single'},existing_model:true,constraints:[first]}),/已有建筑/)
 assert.throws(()=>cleanContext({project:{size:[48,24,48]},constraints:[{...first,source:'private/path'}]}),/快照/)
})
test('Agent constraint generation has a JSON contract, repairs invalid rules and never starts geometry',async t=>{
 const directory=await fs.promises.mkdtemp(path.join(require('node:os').tmpdir(),'nbt-constraint-api-'));t.after(()=>fs.promises.rm(directory,{recursive:true,force:true}));const calls=[]
 const api=createApiService({directory,safeStorage:{},validateCandidate:createCandidateValidator({root:path.resolve(__dirname,'..'),python:'missing-python.exe',directory,getWorkspace:()=>directory}),fetchImpl:async(_url,options)=>{
  calls.push(JSON.parse(options.body));const rules=calls.length===1?{requirements:'入口净宽3格',source:'private/path'}:{requirements:'入口净宽3格'}
  return new Response(JSON.stringify({choices:[{finish_reason:'stop',message:{content:JSON.stringify({name:'通路约束',rules})}}]}))
 }})
 await api.save({enabled:true});const result=await api.generate({mode:'workbench',instruction:'创建通路约束',context:{task:'constraint'}})
 assert.deepEqual(result.rules,{requirements:'入口净宽3格'});assert.equal(calls.length,2);assert.ok(calls[0].messages[0].content.includes('JSON对象{name,rules}'));assert.ok(!calls[0].messages[0].content.includes('geometry_parameters'));assert.equal(calls[0].response_format.type,'json_object');assert.deepEqual(JSON.parse(calls[0].messages[1].content).context,{task:'constraint'});assert.ok(!(await fs.promises.readdir(directory)).includes('ai-validation'))
 assert.throws(()=>cleanContext({task:'constraint',project:{source:'private'}}),/不接受/)
})
test('strict-schema constraint generation uses the catalogue and removes unused nullable rules',async t=>{
 const directory=await fs.promises.mkdtemp(path.join(require('node:os').tmpdir(),'nbt-constraint-schema-'));t.after(()=>fs.promises.rm(directory,{recursive:true,force:true}));let request
 const rules=Object.fromEntries(Object.keys(require('../.agents/skills/minecraft-nbt-modeler/tool-catalog.json').project_constraints.rules.properties).map(key=>[key,null]));rules.requirements='主入口净宽3格'
 const api=createApiService({directory,safeStorage:{},fetchImpl:async(_url,options)=>{request=JSON.parse(options.body);return new Response(JSON.stringify({choices:[{finish_reason:'stop',message:{content:JSON.stringify({name:'入口约束',rules})}}]}))}})
 await api.save({enabled:true,provider:'compatible',strictSchema:true});const result=await api.generate({mode:'workbench',instruction:'创建入口约束',context:{task:'constraint'}})
 assert.deepEqual(result.rules,{requirements:'主入口净宽3格'});assert.equal(request.response_format.type,'json_schema');assert.ok(!request.messages[0].content.includes('工具语义'));assert.deepEqual(Object.keys(request.response_format.json_schema.schema.properties),['name','rules'])
})
