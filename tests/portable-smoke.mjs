import fs from 'node:fs/promises'
import {createReadStream} from 'node:fs'
import {createHash} from 'node:crypto'
import path from 'node:path'
import assert from 'node:assert/strict'
import {execFileSync} from 'node:child_process'
import {root,python} from '../scripts/paths.mjs'
const i=process.argv.indexOf('--archive-dir'),folder=path.resolve(root,i<0?'dist/portable':process.argv[i+1])
const zip=(await fs.readdir(folder)).find(f=>f.endsWith('-portable.zip'));if(!zip)throw Error('Missing portable ZIP')
const manifest=JSON.parse(await fs.readFile(path.join(folder,zip.replace(/\.zip$/,'.manifest.json')),'utf8'))
const splitFiles=(await fs.readdir(folder)).filter(f=>f.endsWith('-app-update.manifest.json')||f.endsWith('-runtime.manifest.json'))
if(splitFiles.length===2){const entries=[];for(const file of splitFiles)entries.push(...JSON.parse(await fs.readFile(path.join(folder,file),'utf8')).files);assert.equal(new Set(entries.map(f=>f.path)).size,entries.length);assert.deepEqual(entries.sort((a,b)=>a.path.localeCompare(b.path)),manifest.files.sort((a,b)=>a.path.localeCompare(b.path)))}
const output=path.join(root,'build','portable-'+Date.now())
const reused=process.argv.indexOf('--unpacked-dir'),unpacked=reused<0?output:path.resolve(root,process.argv[reused+1])
if(reused<0)execFileSync(python,[path.join(root,'scripts/portable-archive.py'),'unpack','--source',path.join(folder,zip),'--output',output],{stdio:'inherit'})
else{
 await fs.mkdir(output)
 const digest=async file=>{const h=createHash('sha256');for await(const chunk of createReadStream(file))h.update(chunk);return h.digest('hex')}
 assert.equal(await digest(path.join(folder,zip)),manifest.sha256)
 for(const item of manifest.files){const file=path.resolve(unpacked,item.path);assert.ok(file.startsWith(unpacked+path.sep));assert.equal((await fs.stat(file)).size,item.bytes,item.path);assert.equal(await digest(file),item.sha256,item.path)}
 console.log(JSON.stringify({verified_existing_extraction:true,files:manifest.files.length}))
}
const exe=path.join(unpacked,'NBTCreator-win32-x64/NBTCreator.exe'),app=path.join(path.dirname(exe),'resources/app')
const env={...process.env,PATH:path.join(process.env.WINDIR||'C:/Windows','System32'),ELECTRON_RUN_AS_NODE:'1',PYTHONNOUSERSITE:'1'}
delete env.NBTCREATOR_PYTHON;delete env.PYTHONPATH;delete env.PYTHONHOME
function run(args){return execFileSync(exe,args,{env,encoding:'utf8',windowsHide:true,timeout:180000,maxBuffer:4*1024*1024})}
const probe=run(['-e',`const {resolvePython,configureRenderRuntime}=require(${JSON.stringify(path.join(app,'desktop/python-runtime.cjs'))});configureRenderRuntime(${JSON.stringify(app)},process.execPath);const {execFileSync}=require('node:child_process');const p=resolvePython(${JSON.stringify(app)});console.log(execFileSync(p,['-c','import numpy,PIL;print(numpy.__version__,PIL.__version__)'],{encoding:'utf8'}));`])
assert.ok(probe.includes('2.4.2 12.1.0'))
const caps=JSON.parse(run([path.join(app,'scripts/cli.mjs'),'capabilities']));assert.equal(Object.keys(caps.tools).length,19)
const workspace=path.join(output,'workspace');await fs.mkdir(workspace)
run([path.join(app,'scripts/cli.mjs'),'--workspace',workspace,'exposure','apply'])
assert.ok((await fs.readFile(path.join(workspace,'.agents/skills/nbtcreator-workspace/SKILL.md'),'utf8')).includes('.nbtcreator/runtimes'))
const exportedRuntime=(await fs.readdir(path.join(workspace,'.nbtcreator/runtimes')))[0]
assert.ok(JSON.parse(await fs.readFile(path.join(workspace,'.nbtcreator/runtimes',exportedRuntime,'assets/viewer/package-lock.json'),'utf8')).lockfileVersion)
run([path.join(app,'scripts/cli.mjs'),'--workspace',workspace,'ai-style','set','--workflow','small_structure','--creativity','85'])
assert.equal(JSON.parse(run([path.join(app,'scripts/cli.mjs'),'--workspace',workspace,'ai-style','prompt','--workflow','small_structure'])).result.values.creativity,85)
assert.deepEqual(JSON.parse(run([path.join(app,'scripts/cli.mjs'),'--workspace',workspace,'components','list'])).result.items,[])
const browserScript=path.join(output,'browser-probe.mjs')
await fs.writeFile(browserScript,`import {createRequire} from 'node:module';const r=createRequire(${JSON.stringify(path.join(app,'.agents/skills/minecraft-nbt-modeler/assets/viewer/package.json'))});const b=await r('playwright').chromium.launch({executablePath:${JSON.stringify(path.join(app,'runtime/browser/chrome.exe'))},headless:true});const p=await b.newPage();await p.setContent('<title>portable</title>');if(await p.title()!=='portable')throw Error('browser');await b.close();console.log('browser-ok')`)
assert.ok(run([browserScript]).includes('browser-ok'))
const fixture=path.join(output,'tiny.master.json.gz'),cameras=path.join(output,'cameras.json'),rendered=path.join(output,'rendered')
execFileSync(path.join(app,'runtime/python/python.exe'),['-c',`import sys;sys.path.insert(0,${JSON.stringify(path.join(app,'.agents/skills/minecraft-nbt-modeler/scripts'))});from nbt_assembly import Volume;from nbt_refine import save_master;m=Volume((8,8,8));m.box((0,0,0),(7,1,7),'stone_bricks');save_master(${JSON.stringify(fixture)},m,set())`],{env,windowsHide:true})
await fs.writeFile(cameras,JSON.stringify([{id:'whole',eye:[15,13,15],target:[4,1,4]}]))
run([path.join(app,'scripts/cli.mjs'),'render','--source',fixture,'--cameras',cameras,'--output',rendered,'--width','320','--height','240','--quality','balanced'])
assert.ok((await fs.readdir(rendered)).some(f=>f.endsWith('.png')))
const facadeRendered=path.join(output,'workspace-rendered')
execFileSync(path.join(app,'runtime/python/python.exe'),[path.join(workspace,'.agents/skills/nbtcreator-workspace/nbt.py'),'render','--source',fixture,'--cameras',cameras,'--output',facadeRendered,'--width','320','--height','240'],{env,cwd:workspace,windowsHide:true,timeout:180000})
assert.equal(JSON.parse(await fs.readFile(path.join(facadeRendered,'render_manifest.json'),'utf8')).status,'complete')
const candidate=path.join(workspace,'candidate-fixture'),scripts=path.join(workspace,'.nbtcreator/runtimes',exportedRuntime,'scripts')
await fs.mkdir(candidate)
const code=`import sys,json
from pathlib import Path
sys.path.insert(0,${JSON.stringify(scripts)})
from nbt_assembly import Volume
from nbt_refine import save_master
from nbt_detail_control import default_settings,preview_effect,digest
folder=Path(${JSON.stringify(candidate)})
m=Volume((24,12,28));m.box((0,0,0),(23,11,27),'stone_bricks');m.box((1,1,1),(22,10,26),'air')
walls={p for p in m.blocks if p[0] in (0,23) or p[2] in (0,27)}
source=folder/'source.master.json.gz';save_master(source,m,walls)
context=dict(mode='standalone',openings=[],start=[2.5,1,2.5],targets={'end':[20.5,1,24.5]},interior_probes=[[10,2,10]],cameras=[dict(role='whole',id='overview',eye=[40,25,40],target=[12,3,14]),dict(role='entry',id='entry',eye=[2.5,2.62,2.5],target=[10,3,10])])
(folder/'context.json').write_text(json.dumps(context),encoding='utf8')
settings=default_settings();settings['operations']=[dict(kind='box',label='portable candidate',lo=[5,1,5],hi=[5,3,5],state='stone_bricks',classification='body')]
request=dict(source=str(source),source_sha256=digest(source),context=str(folder/'context.json'),settings=settings)
(folder/'request.json').write_text(json.dumps(request),encoding='utf8')
preview_effect(request,folder/'preview')
`
execFileSync(path.join(app,'runtime/python/python.exe'),['-B','-c',code],{env,windowsHide:true,timeout:180000})
execFileSync(path.join(app,'runtime/python/python.exe'),[path.join(workspace,'.agents/skills/nbtcreator-workspace/nbt.py'),'validate','--request',path.join(candidate,'request.json'),'--snapshot',path.join(candidate,'preview/after.json'),'--output',path.join(candidate,'checked')],{env,cwd:workspace,windowsHide:true,timeout:180000})
const verified=JSON.parse(await fs.readFile(path.join(candidate,'checked/validation.json'),'utf8'))
assert.equal(verified.passed,true);assert.equal(verified.asset_written,false)
await fs.writeFile(path.join(output,'results.json'),JSON.stringify({passed:true,checks:{zip_manifest_and_hidden_skill:true,private_python_dependencies:true,electron_node_cli:true,workspace_skill_generation:true,shared_regional_ai_preferences:true,component_library_cli:true,bundled_chromium:true,python_node_batch_render:true,workspace_facade_private_render_runtime:true,standalone_candidate_checked_in_private_runtime:true}},null,2))
console.log(JSON.stringify({passed:true,checks:10,output}))
