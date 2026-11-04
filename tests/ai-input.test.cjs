const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path')
const scope=vm.createContext({crypto:require('node:crypto').webcrypto,TextEncoder});vm.runInContext(fs.readFileSync(path.join(__dirname,'../.agents/skills/minecraft-nbt-modeler/prompt-console/ai-input.js'),'utf8'),scope)
const {request}=scope.NbtPromptAIInput
const box={kind:'box',label:'墙面',classification:'wall',state:'stone_bricks',lo:[2,1,2],hi:[20,8,2]}
const design={project:{name:'大厅',size:[48,24,48],wall:'墙面分层',source:'private-path',budget:4096},operations:Array.from({length:60},()=>({...box}))}
test('prose editing summarizes repeated tool intent and never transmits executable arrays or local metadata',()=>{
 const before=JSON.stringify(design),input=request('text','强化墙面层次',design)
 assert.equal(input.mode,'prompt');assert.equal(input.context,null)
 const text=input.instruction
 for(const value of ['private-path','"source"','"budget"','"lo"','"hi"','"operations"'])assert.ok(!text.includes(value),value)
 const summary=JSON.parse(text.split('设计草案摘要 JSON：\n')[1]);assert.equal(summary.operation_count,60);assert.equal(summary.operation_intents.length,1);assert.equal(summary.operation_intents[0].steps,60);assert.equal(summary.operation_intents[0].state,'stone_bricks')
 assert.equal(JSON.stringify(design),before);assert.ok(text.length<JSON.stringify(design).length/3)
})
test('controls and draft retain full context and bypass the unrelated prose size guard',()=>{
 const large={...design,project:{...design.project,wall:'层次'.repeat(10000)}}
 for(const mode of ['controls','draft']){const input=request(mode,'调整墙面',large);assert.equal(input.mode,'workbench');assert.equal(input.context,large);assert.equal(input.instruction,'调整墙面')}
 assert.throws(()=>request('text','润色',large),/摘要较大/)
 assert.throws(()=>request('controls','x'.repeat(12001),design),/12000/)
})
test('disabled and distinct construction intent stay separate in the prose summary',()=>{
 const input=request('text','保留未启用的草稿',{...design,operations:[box,{...box,enabled:false},{...box,state:'andesite'}]})
 const summary=JSON.parse(input.instruction.split('设计草案摘要 JSON：\n')[1]);assert.equal(summary.operation_intents.length,3);assert.equal(summary.operation_intents[1].enabled,false)
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
