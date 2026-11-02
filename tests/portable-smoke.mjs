import fs from 'node:fs/promises'
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
execFileSync(python,[path.join(root,'scripts/portable-archive.py'),'unpack','--source',path.join(folder,zip),'--output',output],{stdio:'inherit'})
const exe=path.join(output,'NBTCreator-win32-x64/NBTCreator.exe'),app=path.join(path.dirname(exe),'resources/app')
const env={...process.env,PATH:path.join(process.env.WINDIR||'C:/Windows','System32'),ELECTRON_RUN_AS_NODE:'1',PYTHONNOUSERSITE:'1'}
delete env.NBTCREATOR_PYTHON;delete env.PYTHONPATH;delete env.PYTHONHOME
function run(args){return execFileSync(exe,args,{env,encoding:'utf8',windowsHide:true,timeout:180000,maxBuffer:4*1024*1024})}
const probe=run(['-e',`const {resolvePython,configureRenderRuntime}=require(${JSON.stringify(path.join(app,'desktop/python-runtime.cjs'))});configureRenderRuntime(${JSON.stringify(app)},process.execPath);const {execFileSync}=require('node:child_process');const p=resolvePython(${JSON.stringify(app)});console.log(execFileSync(p,['-c','import numpy,PIL;print(numpy.__version__,PIL.__version__)'],{encoding:'utf8'}));`])
assert.ok(probe.includes('2.4.2 12.1.0'))
const caps=JSON.parse(run([path.join(app,'scripts/cli.mjs'),'capabilities']));assert.equal(Object.keys(caps.tools).length,18)
const workspace=path.join(output,'workspace');await fs.mkdir(workspace)
run([path.join(app,'scripts/cli.mjs'),'--workspace',workspace,'exposure','apply'])
assert.ok((await fs.readFile(path.join(workspace,'.agents/skills/nbtcreator-workspace/SKILL.md'),'utf8')).includes('.nbtcreator/runtimes'))
const browserScript=path.join(output,'browser-probe.mjs')
await fs.writeFile(browserScript,`import {createRequire} from 'node:module';const r=createRequire(${JSON.stringify(path.join(app,'.agents/skills/minecraft-nbt-modeler/assets/viewer/package.json'))});const b=await r('playwright').chromium.launch({executablePath:${JSON.stringify(path.join(app,'runtime/browser/chrome.exe'))},headless:true});const p=await b.newPage();await p.setContent('<title>portable</title>');if(await p.title()!=='portable')throw Error('browser');await b.close();console.log('browser-ok')`)
assert.ok(run([browserScript]).includes('browser-ok'))
const fixture=path.join(output,'tiny.master.json.gz'),cameras=path.join(output,'cameras.json'),rendered=path.join(output,'rendered')
execFileSync(path.join(app,'runtime/python/python.exe'),['-c',`import sys;sys.path.insert(0,${JSON.stringify(path.join(app,'.agents/skills/minecraft-nbt-modeler/scripts'))});from nbt_assembly import Volume;from nbt_refine import save_master;m=Volume((8,8,8));m.box((0,0,0),(7,1,7),'stone_bricks');save_master(${JSON.stringify(fixture)},m,set())`],{env,windowsHide:true})
await fs.writeFile(cameras,JSON.stringify([{id:'whole',eye:[15,13,15],target:[4,1,4]}]))
run([path.join(app,'scripts/cli.mjs'),'render','--source',fixture,'--cameras',cameras,'--output',rendered,'--width','320','--height','240','--quality','balanced'])
assert.ok((await fs.readdir(rendered)).some(f=>f.endsWith('.png')))
await fs.writeFile(path.join(output,'results.json'),JSON.stringify({passed:true,checks:{zip_manifest_and_hidden_skill:true,private_python_dependencies:true,electron_node_cli:true,workspace_skill_generation:true,bundled_chromium:true,python_node_batch_render:true}},null,2))
console.log(JSON.stringify({passed:true,checks:6,output}))
