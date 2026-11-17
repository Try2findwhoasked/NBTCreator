const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs/promises'),os=require('node:os'),path=require('node:path')
const {createInternalAI}=require('../../desktop/internal-ai.cjs')

test('queued knowledge uses admission rules and rejects changed reference bytes',async t=>{
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'nbt-ai-capture-'));t.after(()=>fs.rm(root,{recursive:true,force:true}))
 const skill=path.resolve(__dirname,'../../.agents/skills/minecraft-nbt-modeler'),service=createInternalAI({workspace:()=>root,skill})
 const file=path.join(root,'reference.md');await fs.writeFile(file,'original')
 const config=await service.importDocuments([file]),id=config.documents[0].id
 config.workflows.draft.knowledge=[id];config.workflows.draft.instruction='original rules';await service.save({workflows:config.workflows})
 const snapshot=await service.capture('draft')
 config.workflows.draft.instruction='later rules';await service.save({workflows:config.workflows})
 assert.equal((await service.context('draft',{},snapshot)).instruction,'original rules')
 await fs.writeFile(path.join(root,'.nbtcreator/internal-ai',config.documents[0].path),'changed reference')
 await assert.rejects(service.context('draft',{},snapshot),/参考资料已变化/)
})
test('internal workflows and knowledge are separate, portable and selected per call',async t=>{
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'nbt-internal-'));t.after(()=>fs.rm(root,{recursive:true,force:true}))
 let workspace=path.join(root,'one');const skill=path.join(root,'skill');await fs.mkdir(path.join(skill,'references'),{recursive:true});await fs.mkdir(path.join(skill,'config'),{recursive:true});await fs.copyFile(path.resolve(__dirname,'../../.agents/skills/minecraft-nbt-modeler/config/ai-style-schema.json'),path.join(skill,'config/ai-style-schema.json'));await fs.writeFile(path.join(skill,'references/design-principles.md'),'builtin-design')
 const service=createInternalAI({workspace:()=>workspace,skill});let c=await service.show();assert.equal(Object.keys(c.workflows).length,7);assert.deepEqual((await service.context('draft')).knowledge,[])
 const defaults=await service.context('draft');assert.equal(defaults.rules,undefined);assert.equal(defaults.base_rules,c.workflows.draft.rules)
 const doc=path.join(root,'custom.md');await fs.writeFile(doc,'private-reference');c=await service.importDocuments([doc]);const id=c.documents[0].id
 c.workflows.draft.style.creativity=95;c.workflows.draft.style.detail=15;c.workflows.small_structure.style.creativity=10;c.workflows.draft.rules='draft-only-rule';c.workflows.draft.knowledge=[id,'builtin:design'];await service.save({workflows:c.workflows})
 const preference=await service.context('draft');assert.equal(preference.rules,'draft-only-rule');assert.equal(preference.base_rules,defaults.base_rules);assert.equal(preference.style.creativity,95);assert.equal(preference.style.detail,15);assert.ok(preference.style_prompt.includes('积极探索'));assert.equal((await service.context('small_structure')).style.creativity,10);const shared=JSON.parse(await fs.readFile(path.join(workspace,'.nbtcreator/ai-style.json'),'utf8'));assert.equal(shared.workflows.draft.creativity,95)
 assert.equal((await service.context('draft')).knowledge.length,2);assert.equal((await service.context('structure')).knowledge.length,0)
 await assert.rejects(fs.access(path.join(workspace,'.nbtcreator','skill-exposure.json')))
 workspace=path.join(root,'two');assert.equal((await service.show()).documents.length,0)
 workspace=path.join(root,'one');const invalid=await service.show();invalid.workflows.draft.knowledge=['../../secret'];await assert.rejects(service.save({workflows:invalid.workflows}))
 const bad=await service.show();bad.documents[0].path='../../secret';await fs.writeFile(path.join(workspace,'.nbtcreator/internal-ai/config.json'),JSON.stringify(bad));await assert.rejects(service.context('draft'))
})

test('legacy workflow settings keep their rules and viewport choice while gaining independent asset creation',async t=>{
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'nbt-internal-migration-'));t.after(()=>fs.rm(root,{recursive:true,force:true}));const skill=path.resolve(__dirname,'../../.agents/skills/minecraft-nbt-modeler'),service=createInternalAI({workspace:()=>root,skill}),old=await service.show();delete old.workflows.component;delete old.workflows.selection_edit;old.workflows.small_structure.rules='custom-local-rules';old.workflows.small_structure.attachViewport=true
 await fs.mkdir(path.join(root,'.nbtcreator/internal-ai'),{recursive:true});await fs.writeFile(path.join(root,'.nbtcreator/internal-ai/config.json'),JSON.stringify(old));const loaded=await service.show();assert.equal(Object.keys(loaded.workflows).length,7);assert.equal(loaded.workflows.small_structure.rules,'custom-local-rules');assert.equal(loaded.workflows.small_structure.attachViewport,true);assert.equal(loaded.workflows.component.attachViewport,false);assert.equal(loaded.workflows.selection_edit.attachViewport,false)
})

test('only the old factory draft rules migrate to prompt assistance while human settings survive',async t=>{
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'nbt-brief-migration-'));t.after(()=>fs.rm(root,{recursive:true,force:true}))
 const service=createInternalAI({workspace:()=>root,skill:path.resolve(__dirname,'../../.agents/skills/minecraft-nbt-modeler')}),config=await service.show(),factory=config.workflows.draft.rules
 config.workflows.draft.rules='只编写设计要求和交接文字；以关键空间、构件与环境为对象，描述用途、特征、包含和连接关系及共同约束；默认不预定数量、间距、方块配方或施工顺序，用户明确给定的细节保留。具体建模步骤由接收任务的Agent编写，不在提示词编写阶段实施模型。\n声明整体尺寸与有效占地；闭合外壳后检查全部腔体，再按声明开洞；初稿已有顶构承托、墙面/地板层次和主题节点。安排实际主模型/图片/验证交付，等待对应看图确认后才精修。'
 config.workflows.draft.instruction='保留院落和主厅关系';config.workflows.draft.knowledge=['builtin:design'];config.workflows.draft.attachViewport=true
 const file=path.join(root,'.nbtcreator/internal-ai/config.json');await fs.mkdir(path.dirname(file),{recursive:true});await fs.writeFile(file,JSON.stringify(config))
 const migrated=await service.show();assert.equal(migrated.workflows.draft.rules,factory);assert.equal(migrated.workflows.draft.instruction,'保留院落和主厅关系');assert.deepEqual(migrated.workflows.draft.knowledge,['builtin:design']);assert.equal(migrated.workflows.draft.attachViewport,true)
 migrated.workflows.draft.rules='人工规则：用途和动线优先';await service.save({workflows:migrated.workflows});assert.equal((await service.context('draft')).rules,'人工规则：用途和动线优先')
})


test('focused built-in topics stay optional and only the selected stage is sent',async t=>{
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'nbt-knowledge-stages-'));t.after(()=>fs.rm(root,{recursive:true,force:true}))
 const skill=path.resolve(__dirname,'../../.agents/skills/minecraft-nbt-modeler'),service=createInternalAI({workspace:()=>root,skill})
 const config=await service.show()
 for(const id of ['builtin:parametric','builtin:pattern-source','builtin:pattern-fit','builtin:surface-mount','builtin:object-scenes'])assert.ok(config.builtins[id],id)
 for(const flow of Object.values(config.workflows))assert.deepEqual(flow.knowledge,[])
 config.workflows.component.knowledge=['builtin:pattern-fit'];await service.save({workflows:config.workflows})
 const selected=await service.context('component')
 assert.equal(selected.knowledge.length,1);assert.ok(selected.knowledge[0].content.includes('# 纹样拟合与质量检查'));if(selected.knowledge[0].excerpted){assert.match(selected.knowledge[0].content,/^\[L1-\d+\]/);assert.equal(selected.knowledge[0].omitted,true)}
 assert.ok(!selected.knowledge[0].content.includes('## 小纹样生成、区域采样与组合资产'))
 assert.deepEqual((await service.context('draft')).knowledge,[])
 await assert.rejects(fs.access(path.join(root,'.nbtcreator/skill-exposure.json')))
})
