const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs/promises'),path=require('node:path'),os=require('node:os'),{spawnSync}=require('node:child_process')
const {createAIStyle}=require('../desktop/ai-style.cjs')
const skill=path.resolve(__dirname,'../.agents/skills/minecraft-nbt-modeler')
test('native and external CLI read exactly the same regional AI preferences',async t=>{
 const workspace=await fs.mkdtemp(path.join(os.tmpdir(),'nbt-ai-style-'));t.after(()=>fs.rm(workspace,{recursive:true,force:true}))
 const styles=createAIStyle({workspace:()=>workspace,skill}),config=await styles.load()
 config.workflows.small_structure.creativity=98;config.workflows.small_structure.detail=12;config.workflows.draft.creativity=10;await styles.save(config)
 const run=spawnSync('python',[path.join(skill,'scripts/nbt_ai_style.py'),'--workspace',workspace,'prompt','--workflow','small_structure'],{encoding:'utf8',windowsHide:true});assert.equal(run.status,0,run.stderr)
 const cli=JSON.parse(run.stdout).result,native=await styles.context('small_structure');assert.deepEqual(cli.values,native.values);assert.equal(cli.prompt,native.prompt);assert.ok(native.prompt.includes('98/100'));assert.ok(native.prompt.includes('返回格式'))
 assert.equal((await styles.context('draft')).values.creativity,10)
 const set=spawnSync('python',[path.join(skill,'scripts/nbt_ai_style.py'),'--workspace',workspace,'set','--workflow','small_structure','--detail','90'],{encoding:'utf8',windowsHide:true});assert.equal(set.status,0,set.stderr);assert.equal((await styles.context('small_structure')).values.detail,90)
 const invalid=await styles.load();invalid.workflows.draft.creativity=101;await assert.rejects(styles.save(invalid));assert.equal((await styles.context('draft')).values.creativity,10)
 const file=path.join(workspace,'.nbtcreator/ai-style.json');await fs.writeFile(file,'\uFEFF'+await fs.readFile(file,'utf8'));assert.equal((await styles.context('small_structure')).values.detail,90)
})

test('legacy five-region preferences gain independent assets identically in native and CLI readers',async t=>{
 const workspace=await fs.mkdtemp(path.join(os.tmpdir(),'nbt-ai-style-migration-'));t.after(()=>fs.rm(workspace,{recursive:true,force:true}))
 const styles=createAIStyle({workspace:()=>workspace,skill}),old=await styles.load();delete old.workflows.component;old.workflows.small_structure.creativity=88
 await fs.mkdir(path.join(workspace,'.nbtcreator'),{recursive:true});await fs.writeFile(path.join(workspace,'.nbtcreator/ai-style.json'),JSON.stringify(old))
 const native=await styles.context('component'),run=spawnSync('python',[path.join(skill,'scripts/nbt_ai_style.py'),'--workspace',workspace,'prompt','--workflow','component'],{encoding:'utf8',windowsHide:true});assert.equal(run.status,0,run.stderr);const cli=JSON.parse(run.stdout).result;assert.equal(native.values.creativity,88);assert.deepEqual(cli.values,native.values);assert.equal(cli.prompt,native.prompt)
})


test('internal prose detail is role-specific while external construction preferences stay intact',async t=>{
 const workspace=await fs.mkdtemp(path.join(os.tmpdir(),'nbt-prose-style-'));t.after(()=>fs.rm(workspace,{recursive:true,force:true}))
 const styles=createAIStyle({workspace:()=>workspace,skill}),config=await styles.load();config.workflows.draft.detail=95;await styles.save(config)
 const native=await styles.context('draft'),run=spawnSync('python',[path.join(skill,'scripts/nbt_ai_style.py'),'--workspace',workspace,'prompt','--workflow','draft'],{encoding:'utf8',windowsHide:true})
 assert.equal(run.status,0,run.stderr);assert.equal(JSON.parse(run.stdout).result.prompt,native.prompt)
 const {createInternalAI}=require('../desktop/internal-ai.cjs');const internal=await createInternalAI({workspace:()=>workspace,skill}).context('draft');assert.deepEqual(internal.style,native.values);assert.ok(internal.style_prompt.includes('执行Agent推导'));assert.ok(native.prompt.includes('操作步骤'))
 assert.equal((await styles.context('component')).values.detail,config.workflows.component.detail)
})
