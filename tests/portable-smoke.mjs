import fs from 'node:fs/promises'
import path from 'node:path'
import assert from 'node:assert/strict'
import {execFileSync} from 'node:child_process'
import {root,python} from '../scripts/paths.mjs'
const i=process.argv.indexOf('--archive-dir'),folder=path.resolve(root,i<0?'dist/portable':process.argv[i+1])
const zip=(await fs.readdir(folder)).find(f=>f.endsWith('-portable.zip'));if(!zip)throw Error('Missing portable ZIP')
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
await fs.writeFile(path.join(output,'results.json'),JSON.stringify({passed:true,checks:{zip_manifest_and_hidden_skill:true,private_python_dependencies:true,electron_node_cli:true,workspace_skill_generation:true,bundled_chromium:true}},null,2))
console.log(JSON.stringify({passed:true,checks:5,output}))
