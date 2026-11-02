import fs from 'node:fs/promises'
import path from 'node:path'
import assert from 'node:assert/strict'
import {spawnSync} from 'node:child_process'
import {createRequire} from 'node:module'
import {root,skill,python} from '../scripts/paths.mjs'
const require=createRequire(path.join(skill,'assets/viewer/package.json')),{_electron}=require('playwright')
const output=path.join(root,'build','catalog-desktop-'+Date.now());await fs.mkdir(output,{recursive:true})
const workspace=path.join(output,'workspace'),sample=path.join(workspace,'nbt_models/sample')
const fixture=spawnSync(python,[path.join(root,'tests/make_fixture.py'),sample],{encoding:'utf8'});assert.equal(fixture.status,0,fixture.stderr)
const script="import sys;from pathlib import Path;sys.path.insert(0,sys.argv[1]);from nbt_model import Model;p=Path(sys.argv[2]);p.mkdir(parents=True);m=Model((12,12,12));m.box((0,0,0),(11,11,11),'stone_bricks');m.box((2,2,2),(9,9,9),'air');m.check_sealed([(5,5,5)]);m.save(p/'only.nbt')"
const standalone=path.join(workspace,'nbt_models/standalone');const made=spawnSync(python,['-c',script,path.join(skill,'scripts'),standalone],{encoding:'utf8'});assert.equal(made.status,0,made.stderr)
const wronglySelected=path.join(workspace,'nbt_models/_workspaces');await fs.mkdir(wronglySelected,{recursive:true})
let app;const checks={}
try{
 const env={...process.env,NBTCREATOR_AUTOMATION:'1'};delete env.ELECTRON_RUN_AS_NODE
 app=await _electron.launch({executablePath:process.env.NBTCREATOR_TEST_EXE||path.join(root,'node_modules/electron/dist/electron.exe'),args:[...(process.env.NBTCREATOR_TEST_EXE?[]:[root]),'--workspace',wronglySelected,'--user-data-dir',path.join(output,'profile')],env,timeout:60000})
 const page=await app.firstWindow(),errors=[];page.setDefaultTimeout(30000);page.on('pageerror',e=>errors.push(e.message))
 await page.waitForFunction(()=>window.detailControl?.state.info&&!window.detailControl.state.busy,undefined,{timeout:60000})
 assert.equal((await page.evaluate(()=>window.nbtDesktop.info())).workspace,workspace);assert.equal(await page.evaluate(()=>window.detailControl.state.models.length),2);checks.cached_subfolder_normalized_and_nbt_listed=true
 const index=await page.evaluate(source=>window.detailControl.state.models.findIndex(m=>m.source===source),path.join(standalone,'only.nbt'));assert.ok(index>=0)
 await page.locator('#models').selectOption(String(index));await page.waitForFunction(()=>window.detailControl.state.info?.size[0]===12&&!window.detailControl.state.busy)
 await page.locator('#auto-preview').uncheck();await page.locator('#enable-3d').click();await page.waitForFunction(()=>window.detailControl.state.mode==='3d'&&!window.detailControl.state.busy,undefined,{timeout:60000})
 assert.equal(await page.evaluate(()=>window.detailControl.state.info.context),'');assert.ok((await page.locator('#result-log').textContent()).includes('仅作几何查看'));checks.standalone_nbt_3d_without_authoring_context=true
 await page.evaluate(()=>window.nbtDesktop.exposureSave({schema_version:1,enabled_groups:['core','props']}))
 const next=path.join(output,'next-workspace');await fs.mkdir(path.join(next,'nbt_models/_workspaces'),{recursive:true})
 await app.evaluate(({dialog},folder)=>{dialog.showOpenDialog=async()=>({canceled:false,filePaths:[folder]});dialog.showMessageBox=async()=>({response:0})},path.join(next,'nbt_models/_workspaces'))
 await page.locator('#desktop-workspace').click();await page.waitForFunction(w=>window.detailControl?.state.workspace===w&&!window.detailControl.state.busy,next,{timeout:60000})
 const config=JSON.parse(await fs.readFile(path.join(next,'.nbtcreator/skill-exposure.json'),'utf8'));assert.deepEqual(config.enabled_groups,['core','props'])
 const entry=path.join(next,'.agents/skills/nbtcreator-workspace/nbt.py');const run=spawnSync(python,[entry,'capabilities'],{cwd:next,encoding:'utf8'});assert.equal(run.status,0,run.stderr);assert.equal(Object.keys(JSON.parse(run.stdout).tools).length,18)
 assert.ok((await fs.readdir(path.join(next,'.nbtcreator/runtimes'))).length);assert.ok((await fs.readFile(path.join(next,'.agents/skills/nbtcreator-workspace/SKILL.md'),'utf8')).includes('.nbtcreator/runtimes'));checks.switch_transfers_skill_runtime_and_selection=true
 assert.ok((await fs.stat(path.join(workspace,'.agents/skills/nbtcreator-workspace/nbt.py'))).isFile());checks.original_workspace_preserved=true
 await page.screenshot({path:path.join(output,'after-switch.png')});assert.deepEqual(errors,[])
 await fs.writeFile(path.join(output,'results.json'),JSON.stringify({passed:true,checks},null,2));console.log(JSON.stringify({passed:true,checks:Object.keys(checks).length,output}))
}finally{await app?.close()}
