const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path')
const scope=vm.createContext({NbtToolCatalog:require('../../.agents/skills/minecraft-nbt-modeler/tool-catalog.json'),crypto:require('node:crypto').webcrypto,TextEncoder,structuredClone})
for(const file of ['operation-delta.cjs','ai-input.js'])vm.runInContext(fs.readFileSync(path.join(__dirname,'../../.agents/skills/minecraft-nbt-modeler/prompt-console',file),'utf8'),scope)
const {request}=scope.NbtPromptAIInput
const box={kind:'box',label:'墙面',classification:'wall',state:'stone_bricks',lo:[2,1,2],hi:[20,8,2]}
const design={project:{name:'大厅',size:[48,24,48],wall:'墙面分层',source:'private-path',budget:4096},operations:Array.from({length:60},()=>({...box}))}
test('prose editing summarizes repeated tool intent and never transmits executable arrays or local metadata',()=>{
 const before=JSON.stringify(design),input=request('text','强化墙面层次',design)
 assert.equal(input.mode,'prompt');assert.equal(input.instruction,'强化墙面层次')
 const text=JSON.stringify(input.context)
 for(const value of ['private-path','"source"','"budget"','"lo"','"hi"','"operations"'])assert.ok(!text.includes(value),value)
 const summary=input.context;assert.equal(summary.task,'design_prose');assert.equal(summary.operation_intents.length,1);assert.equal(summary.operation_intents[0].steps,60);assert.equal(summary.operation_intents[0].state,'stone_bricks')
 assert.equal(JSON.stringify(design),before);assert.ok(text.length<JSON.stringify(design).length/3)
})
test('advanced controls retain tool context while ordinary draft requests only ask for a handoff brief',()=>{
 const large={...design,project:{...design.project,wall:'层次'.repeat(10000)}}
 const control=request('controls','调整墙面',large);assert.equal(control.context,large)
 const brief=request('draft','调整墙面',large);assert.equal(brief.mode,'workbench');assert.equal(brief.context.task,'brief');assert.equal(brief.context.operations.length,0);assert.equal(brief.context.project,large.project);assert.equal(brief.instruction,'调整墙面')
 assert.equal(request('text','润色',large).instruction,'润色')
 assert.throws(()=>request('controls','x'.repeat(12001),design),/12000/)
})
test('disabled and distinct construction intent stay separate in the prose summary',()=>{
 const input=request('text','保留未启用的草稿',{...design,operations:[box,{...box,enabled:false},{...box,state:'andesite'}]})
 assert.equal(input.context.operation_intents.length,3);assert.equal(input.context.operation_intents[1].enabled,false)
})

test('polishing keeps the original prose and hard requirements separate from this turn',()=>{
 const original='第一段必须原样保留。\n\n原来的结尾。',requirements='保留西塔原钟。';
 const input=request('text','只改最后一句',{...design,project:{...design.project,integration:'saodg'},user_requirements:requirements},original)
 assert.equal(input.instruction,'只改最后一句');assert.equal(input.context.original_text,original);assert.equal(input.context.project.integration,'saodg');assert.equal(input.context.user_requirements,requirements)
 assert.equal(request('text','',design).context.original_text,undefined)
})

test('local plan binding distinguishes identical geometry from different sources without sending paths',async()=>{
 const a=await scope.NbtPromptAIInput.bindingToken(JSON.stringify({...design,source:'C:/one/private.nbt'})),b=await scope.NbtPromptAIInput.bindingToken(JSON.stringify({...design,source:'C:/two/private.nbt'}))
 assert.match(a,/^[a-f0-9]{64}$/);assert.notEqual(a,b);assert.equal(a.includes('private'),false)
})

test('local delta merge preserves opaque fields deliberately excluded from API context',()=>{
 const operations=[{...box,write_group:'local-only',voxels:[[1,2,3,0]],local_note:'keep'},{...box,state:'dirt'}],before=JSON.stringify(operations)
 const merged=scope.NbtPromptAIInput.mergeOperations(operations,{changes:[{step:1,set:{state:'andesite'}}]})
 assert.equal(merged[0].state,'andesite');assert.equal(merged[0].write_group,'local-only');assert.equal(merged[0].local_note,'keep');assert.equal(JSON.stringify(merged[0].voxels),'[[1,2,3,0]]');assert.equal(merged[1].state,'dirt');assert.equal(JSON.stringify(operations),before)
 for(const set of [{overwrite:true},{kind:'python'},{write_group:'foreign'}])assert.throws(()=>scope.NbtPromptAIInput.mergeOperations(operations,{changes:[{step:1,set}]}))
 assert.throws(()=>scope.NbtPromptAIInput.mergeOperations(operations,{changes:[{step:1,set:{state:'andesite'}},{step:3,set:{state:'stone'}}]}));assert.equal(JSON.stringify(operations),before)
})


test('brief edit scopes carry only declared design fields and preserve locked values',()=>{
 const project={name:'人工名称',size:[48,24,48],theme:'人工主题',style:'石木构',materials:'铜只用于接头'}
 const scoped={project,operations:[],brief_scope:{editable_fields:['layout','atmosphere']}}
 const input=request('draft','补充空间体验',scoped)
 assert.equal(JSON.stringify(input.context.brief_scope.editable_fields),'["layout","atmosphere"]')
 assert.doesNotThrow(()=>scope.NbtPromptAIInput.assertPatch(project,{layout:'沿坡分层'},['layout']))
 assert.throws(()=>scope.NbtPromptAIInput.assertPatch(project,{theme:'随机主题'},['layout']),/未勾选/)
 assert.throws(()=>request('draft','补充',{...scoped,brief_scope:{editable_fields:['source']}}),/允许AI/)
 assert.throws(()=>request('draft','补充',{...scoped,brief_scope:{editable_fields:[]}}),/至少/)
 assert.equal(project.theme,'人工主题')
})


test('human design controls survive prompt compilation and prose supplements exactly once',()=>{
 const ui=vm.createContext({NbtToolCatalog:require('../../.agents/skills/minecraft-nbt-modeler/tool-catalog.json')})
 vm.runInContext(fs.readFileSync(path.join(__dirname,'../../.agents/skills/minecraft-nbt-modeler/prompt-console/core.js'),'utf8'),ui)
 const C=ui.NbtPrompt,doc=C.defaults();Object.assign(doc.project,{materials:'人指定铜与木',spatial_character:'转角后展开视野',atmosphere:'柔和侧光',avoid:'不要中央圆环',preserve:'保留北侧通路',size_policy:'fixed'})
 doc.user_requirements='原样保留西塔原钟。\n入口净宽不少于 3 格。';doc.workbench.instruction='只改最后一句'
 const raw=C.prompt(doc,{designText:'可修改的概念说明'})
 for(const value of ['人指定铜与木','转角后展开视野','柔和侧光','不要中央圆环','保留北侧通路','固定尺寸','可修改的概念说明'])assert.ok(raw.includes(value),value)
 assert.equal(raw.split('# 自动存放规则').length-1,1)
 assert.equal(raw.split('# 补充设计说明').length-1,1)
 assert.equal(raw.split(doc.user_requirements).length-1,1);assert.ok(!raw.includes(doc.workbench.instruction));assert.ok(C.prompt(doc).includes(doc.user_requirements));assert.equal(C.normalize(doc).user_requirements,doc.user_requirements)
 assert.ok(raw.indexOf('# 补充设计说明')<raw.indexOf('# 自动存放规则'))
 assert.equal(C.defaults().project.size_policy,'reference')
 const legacy=C.defaults();delete legacy.project.size_policy
 assert.equal(C.normalize(legacy).project.size_policy,'fixed')
 assert.equal(C.normalize({...doc,workbench:{brief_fields:['style']}}).workbench.brief_fields[0],'style')
 doc.project.integration='saodg';doc.project.size_policy='reference';assert.ok(C.prompt(doc).includes('固定尺寸'));assert.equal(C.normalize(doc).project.size_policy,'fixed')
 assert.equal(C.normalize({...doc,project:{...doc.project,integration:'standalone',stage:'plan'}}).project.size_policy,'fixed')
 doc.project.avoid='x'.repeat(4001);assert.ok(C.validate(doc).some(error=>error.includes('4000')))
})
