const {test}=require('node:test'),assert=require('node:assert/strict'),path=require('node:path')
const fs=require('node:fs'),os=require('node:os'),{spawnSync}=require('node:child_process')
const {selectWorkspace,normalizeWorkspace}=require('../../desktop/workspace.cjs')
const root=path.resolve('app'),agent=path.resolve('agent'),options={cwd:agent,root,packaged:false,settingsDirectory:path.resolve('settings'),config:{workspace:path.join(root,'workspace')}}
test('agent cwd and explicit project choices are retained, software-directory defaults are ignored',()=>{assert.equal(selectWorkspace(options),agent);assert.equal(selectWorkspace({...options,explicit:'other'}),path.join(agent,'other'));assert.equal(selectWorkspace({...options,environment:'custom'}),path.join(agent,'custom'));assert.equal(selectWorkspace({...options,config:{workspace:root,workspace_source:'manual'}}),agent);assert.equal(selectWorkspace({...options,cwd:root,config:{}}),null)})
test('packaged app refuses to default to its installation or system directory',()=>{const exe=path.join(root,'bin','NBTCreator.exe');assert.equal(selectWorkspace({...options,packaged:true,root,cwd:root,executable:exe}),null)})
test('explicit Agent invocation does not inherit another manually selected project',()=>{assert.equal(selectWorkspace({...options,agentCwd:agent,config:{workspace:root,workspace_source:'manual'}}),agent)})
test('asset folder, cache, room and accidentally nested asset folders normalize to project root',()=>{for(const relative of ['nbt_models','nbt_models/_workspaces','nbt_models/single/room/v01','nbt_models/_workspaces/nbt_models'])assert.equal(normalizeWorkspace(path.join(agent,relative)),agent);assert.equal(selectWorkspace({...options,config:{workspace:path.join(agent,'nbt_models/_workspaces'),workspace_source:'manual'}}),agent)})

test('CLI distinguishes a missing workspace or file path from a missing Python executable',()=>{
 const directory=fs.mkdtempSync(path.join(os.tmpdir(),'nbtcreator-cli-'))
 const missing=path.join(directory,'missing project'),file=path.join(directory,'project.txt')
 const cli=path.resolve(__dirname,'../../scripts/cli.mjs')
 const run=(workspace,python)=>spawnSync(process.execPath,[cli,'--workspace',workspace,'exposure','apply'],{
  encoding:'utf8',windowsHide:true,env:{...process.env,NBTCREATOR_PYTHON:python}
 })
 try{
  fs.writeFileSync(file,'')
  const missingDirectory=run(missing,process.execPath)
  assert.equal(missingDirectory.status,1)
  assert.ok(missingDirectory.stderr.includes(missing))
  assert.match(missingDirectory.stderr,/不存在/)
  assert.equal(fs.existsSync(missing),false)
  const notDirectory=run(file,process.execPath)
  assert.equal(notDirectory.status,1)
  assert.ok(notDirectory.stderr.includes(file))
  assert.match(notDirectory.stderr,/不是目录/)
  const missingPython=run(directory,path.join(directory,'missing-python.exe'))
  assert.equal(missingPython.status,1)
  assert.match(missingPython.stderr,/Python 不可用/)
 }finally{
  if(fs.existsSync(file))fs.unlinkSync(file)
  fs.rmdirSync(directory)
 }
})

test('top-level CLI help succeeds and unknown commands point to the route guide',()=>{
 const cli=path.resolve(__dirname,'../../scripts/cli.mjs')
 const run=argument=>spawnSync(process.execPath,[cli,argument],{encoding:'utf8',windowsHide:true})
 for(const flag of ['-h','--help']){
  const help=run(flag)
  assert.equal(help.status,0,help.stderr)
  assert.match(help.stdout,/capabilities --routes/)
 }
 for(const name of ['part-search','constructor']){
  const unknown=run(name)
  assert.equal(unknown.status,1)
  assert.ok(unknown.stderr.includes(name))
  assert.match(unknown.stderr,/capabilities --routes/)
 }
})
