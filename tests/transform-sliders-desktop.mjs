import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import path from 'node:path'
import {spawnSync} from 'node:child_process'
import {createHash} from 'node:crypto'
import {createRequire} from 'node:module'
import {root,skill,python} from '../scripts/paths.mjs'
import {minimizedScreenshots} from './minimized-screenshots.mjs'
const require=createRequire(path.join(skill,'assets/viewer/package.json')),{_electron}=require('playwright')
const output=path.join(root,'build','transform-sliders-'+Date.now()),workspace=path.join(output,'workspace'),folder=path.join(workspace,'nbt_models/single/sliders/v1')
const fixture=spawnSync(python,[path.join(root,'tests/make_fixture.py'),folder],{encoding:'utf8',windowsHide:true});assert.equal(fixture.status,0,fixture.stderr)
const source=path.join(folder,'synthetic.master.json.gz'),digest=b=>createHash('sha256').update(b).digest('hex'),before=digest(await fs.readFile(source))
await fs.mkdir(path.join(workspace,'.nbtcreator'),{recursive:true});await fs.writeFile(path.join(workspace,'.nbtcreator/preferences.json'),JSON.stringify({startPage:'model',autoPreview:false}))
let app,page;const errors=[],checks={}
const click=id=>page.locator('#'+id).evaluate(e=>e.click()),slide=(id,value)=>page.locator('#'+id).evaluate((e,value)=>{e.value=value;e.dispatchEvent(new Event('input',{bubbles:true}))},String(value))
const voxel=p=>page.evaluate(p=>document.querySelector('#viewer').contentWindow.nbtModeler.snapshot.master_blocks.find(([q])=>q.every((v,i)=>v===p[i]))?.[1]??'minecraft:air',p)
async function launch(){const env={...process.env,NBTCREATOR_AUTOMATION:'1',OPENBLAS_NUM_THREADS:'1',OMP_NUM_THREADS:'1'};delete env.ELECTRON_RUN_AS_NODE;app=await _electron.launch({executablePath:process.env.NBTCREATOR_TEST_EXE||path.join(root,'node_modules/electron/dist/electron.exe'),args:[...(process.env.NBTCREATOR_TEST_EXE?[]:[root]),'--workspace',workspace,'--user-data-dir',path.join(output,'profile')],env,timeout:60000});page=await app.firstWindow();page.setDefaultTimeout(60000);await minimizedScreenshots(app,page);page.on('pageerror',e=>errors.push(e.message));await page.waitForFunction(()=>window.nbtEditSession?.ready&&!window.detailControl.state.busy&&!window.detailControl.state.sessionRestoring);await page.getByRole('button',{name:'AI建模',exact:true}).evaluate(e=>e.click());await page.locator('.ai-component-movement').evaluate(e=>e.open=true)}
async function preview(){await click('ai-move-preview');await page.waitForFunction(()=>!document.querySelector('#ai-move-x').disabled&&!window.detailControl.state.commitBusy&&!window.detailControl.state.previewBusy);assert.ok(!(await page.locator('#ai-status').getAttribute('class')??'').includes('error'),await page.locator('#ai-status').textContent())}
try{
 await launch()
 await page.evaluate(()=>{const s=window.detailControl.gather();s.whole_region=false;s.lo=[10,4,10];s.hi=[14,5,11];s.operations=[{kind:'box',label:'横梁',classification:'body',lo:[10,4,10],hi:[14,5,11],state:'oak_log[axis=x]'}];window.detailControl.restore(s)})
 await page.locator('.ai-component-movement details').filter({has:page.locator('#ai-group-adopt')}).evaluate(e=>e.open=true);await click('ai-group-adopt')
 await slide('ai-move-x-slider',3);assert.equal(await page.locator('#ai-move-x').inputValue(),'3');await slide('ai-rotate-slider',1);assert.equal(await page.locator('#ai-rotate-turns').inputValue(),'1')
 assert.deepEqual(await page.evaluate(()=>window.detailControl.gather().operations[0].lo),[10,4,10]);await preview()
 assert.equal(await voxel([14,4,14]),'minecraft:oak_log[axis=z]');assert.equal(await voxel([10,4,10]),'minecraft:air');checks.asymmetric_rotation_and_move_sliders_preview_real_voxels=true
 await page.evaluate(()=>window.nbtEditSession.flush());await app.close();app=null;await launch()
 assert.equal(await page.locator('#ai-move-x').inputValue(),'3');assert.equal(await page.locator('#ai-move-x-slider').inputValue(),'3');assert.equal(await page.locator('#ai-rotate-turns').inputValue(),'1');assert.equal(await page.locator('#ai-rotate-slider').inputValue(),'1');assert.equal(await page.evaluate(()=>window.detailControl.state.lastAIGroup.quarter_turns),1);checks.restart_preserves_offset_rotation_and_sliders=true
 await slide('ai-move-x-slider',0);await slide('ai-rotate-slider',0);await preview();assert.equal(await voxel([10,4,10]),'minecraft:oak_log[axis=x]');assert.equal(await voxel([14,4,14]),'minecraft:air');checks.zero_restores_original_geometry_and_state=true
 await click('viewport-assets');await click('copy-selection-3d');await page.waitForFunction(()=>document.querySelector('#viewer').contentWindow.nbtModeler.transformStatus())
 await slide('component-transform-x-slider',22);await page.waitForFunction(()=>document.querySelector('#viewer').contentWindow.nbtModeler.transformStatus()?.position[0]===22);assert.equal(await page.locator('#component-transform-x').inputValue(),'22')
 await slide('component-transform-turns-slider',1);await page.waitForFunction(()=>document.querySelector('#viewer').contentWindow.nbtModeler.transformStatus()?.quarter_turns===1);assert.equal(await page.locator('#component-transform-turns').inputValue(),'1')
 await page.locator('#component-transform-turns').selectOption('2');await page.waitForFunction(()=>document.querySelector('#component-transform-turns-slider').value==='2');await click('component-transform-cancel');checks.component_sliders_sync_with_numeric_fields_and_3d_gizmo=true
 assert.equal(digest(await fs.readFile(source)),before);assert.deepEqual(errors,[]);checks.source_unchanged_and_no_renderer_errors=true
 await page.screenshot({path:path.join(output,'transform-sliders.png')});await fs.writeFile(path.join(output,'results.json'),JSON.stringify({passed:true,checks},null,2));console.log(JSON.stringify({passed:true,checks,output}))
}catch(e){console.error(JSON.stringify({output,checks,errors}));throw e}finally{await app?.close()}
