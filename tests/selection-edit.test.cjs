const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs/promises'),os=require('node:os'),path=require('node:path')
const {cleanSelectionContext,validateSelectionResult}=require('../desktop/selection-edit.cjs'),{createApiService}=require('../desktop/api-service.cjs')
const {createAIStyle}=require('../desktop/ai-style.cjs'),{createInternalAI}=require('../desktop/internal-ai.cjs'),{spawnSync}=require('node:child_process')
const context={size:[48,16,48],lo:[10,3,10],hi:[12,6,12],allow_overwrite:true,selection:{schema_version:1,size:[3,4,3],geometry_sha256:'a'.repeat(64),palette:['minecraft:stone_bricks'],runs:[[0,0,0,3,0,0]],solid_blocks:3,air_omitted:true}}
test('exact selection validation keeps complete wall-aware RLE and rejects overlaps or partial data',()=>{
 assert.deepEqual(cleanSelectionContext(context),context);assert.throws(()=>cleanSelectionContext({...context,selection:{...context.selection,runs:[...context.selection.runs,[1,0,0,1,0,0]],solid_blocks:4}}),/重复/);assert.throws(()=>cleanSelectionContext({...context,selection:{...context.selection,solid_blocks:4}}),/计数/);assert.throws(()=>cleanSelectionContext({...context,selection:{...context.selection,air_omitted:false}}),/摘要/)
})
test('tool proposals preserve all kinds but cannot set execution or permission fields',()=>{
 const proposal={coordinate_space:'local',summary:'替换后在选区内复制',operations:[{kind:'replace',label:'局部换材',lo:[0,0,0],hi:[2,0,2],from_states:['stone_bricks'],state:'andesite'},{kind:'copy_region',label:'复制',lo:[0,0,0],hi:[0,0,0],offset:[1,0,0]}]},data=validateSelectionResult(proposal,context);assert.equal(data.settings_patch.baseline_geometry_sha256,context.selection.geometry_sha256);assert.deepEqual(data.settings_patch.operations,proposal.operations)
 for(const field of ['overwrite','write_group','write_bounds','max_writes','script'])assert.throws(()=>validateSelectionResult({...proposal,operations:[{...proposal.operations[0],[field]:true}]},context))
 assert.throws(()=>validateSelectionResult({...proposal,coordinate_space:'global'},context));assert.throws(()=>validateSelectionResult({...proposal,operations:[{kind:'geometry',geometry:{shape:'sphere',centre:[0,0,0],radius:Infinity}}]},context))
})
test('API sends local exact geometry without source metadata and uses its independent workflow',async t=>{
 const directory=await fs.mkdtemp(path.join(os.tmpdir(),'nbt-selection-api-'));t.after(()=>fs.rm(directory,{recursive:true,force:true}));let payload,flow
 const service=createApiService({directory,safeStorage:{isEncryptionAvailable:()=>true},workflowContext:async key=>(flow=key,{attachViewport:false}),fetchImpl:async(_url,options)=>{payload=JSON.parse(options.body);return new Response(JSON.stringify({choices:[{finish_reason:'stop',message:{content:JSON.stringify({coordinate_space:'local',summary:'换材',operations:[{kind:'replace',label:'换材',lo:[0,0,0],hi:[2,0,2],state:'andesite',from_states:['stone_bricks']}]})}}]}))}})
 await service.save({enabled:true});const result=await service.generate({mode:'selection_edit',instruction:'把选区地面改成安山岩',context:{...context,source:'private-path'}});assert.equal(result.mode,'selection_edit');assert.equal(flow,'selection_edit');const sent=JSON.parse(payload.messages[1].content);assert.deepEqual(sent.context.lo,[0,0,0]);assert.deepEqual(sent.context.size,[3,4,3]);assert.deepEqual(sent.context.selection.runs,context.selection.runs);assert.ok(!JSON.stringify(payload).includes('private-path'));assert.ok(!JSON.stringify(payload).includes(context.selection.geometry_sha256));assert.equal(payload.max_tokens,8192)
})

test('no-action proposals explain limitations without creating a fake tool step',()=>{
 const result=validateSelectionResult({coordinate_space:'local',summary:'选区太小，无法容纳楼梯；请扩大范围',operations:[]},context)
 assert.deepEqual(result.settings_patch.operations,[]);assert.match(result.summary,/扩大/)
})

test('five and six region migrations preserve saved customizations and independent selection preferences',async t=>{
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'nbt-selection-migrate-'));t.after(()=>fs.rm(root,{recursive:true,force:true}));const skill=path.resolve(__dirname,'../.agents/skills/minecraft-nbt-modeler')
 for(const count of [5,6]){
  const workspace=path.join(root,String(count)),style=createAIStyle({workspace:()=>workspace,skill}),internal=createInternalAI({workspace:()=>workspace,skill}),settings=await internal.show(),preferences=await style.load()
  delete settings.workflows.selection_edit;delete preferences.workflows.selection_edit
  if(count===5){delete settings.workflows.component;delete preferences.workflows.component}
  settings.workflows.structure.rules='已有局部编辑规则';settings.workflows.structure.attachViewport=true;settings.workflows.structure.knowledge=['builtin:tools'];preferences.workflows.structure.creativity=17
  await fs.mkdir(path.join(workspace,'.nbtcreator/internal-ai'),{recursive:true});await fs.writeFile(path.join(workspace,'.nbtcreator/internal-ai/config.json'),JSON.stringify(settings));await fs.writeFile(path.join(workspace,'.nbtcreator/ai-style.json'),JSON.stringify(preferences))
  const loaded=await internal.show();assert.equal(Object.keys(loaded.workflows).length,7);assert.equal(loaded.workflows.structure.rules,'已有局部编辑规则');assert.equal(loaded.workflows.structure.attachViewport,true);assert.deepEqual(loaded.workflows.structure.knowledge,['builtin:tools']);assert.equal(loaded.workflows.selection_edit.attachViewport,false);assert.equal(loaded.workflows.selection_edit.style.creativity,17)
  loaded.workflows.selection_edit.style.creativity=92;loaded.workflows.selection_edit.rules='独立选区规则';await internal.save({workflows:loaded.workflows});assert.equal((await style.context('structure')).values.creativity,17)
  const run=spawnSync('python',[path.join(skill,'scripts/nbt_ai_style.py'),'--workspace',workspace,'prompt','--workflow','selection_edit'],{encoding:'utf8',windowsHide:true});assert.equal(run.status,0,run.stderr);assert.equal(JSON.parse(run.stdout).result.values.creativity,92);assert.equal((await internal.show()).workflows.selection_edit.rules,'独立选区规则')
 }
})
