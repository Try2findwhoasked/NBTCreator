import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import path from 'node:path'
import {spawnSync} from 'node:child_process'
import {createHash} from 'node:crypto'
import {createRequire} from 'node:module'
import {root,skill,python} from '../scripts/paths.mjs'
import {minimizedScreenshots} from './minimized-screenshots.mjs'
const require=createRequire(path.join(skill,'assets/viewer/package.json')),{_electron}=require('playwright')
const output=path.join(root,'build','auto-roads-'+Date.now()),workspace=path.join(output,'workspace'),folder=path.join(workspace,'nbt_models/single/roads/v1')
const fixture=spawnSync(python,[path.join(root,'tests/make_fixture.py'),folder],{encoding:'utf8',windowsHide:true});assert.equal(fixture.status,0,fixture.stderr)
const source=path.join(folder,'synthetic.master.json.gz'),digest=b=>createHash('sha256').update(b).digest('hex'),before=digest(await fs.readFile(source))
const coordinates=path.join(folder,'coordinates.json'),config=JSON.parse(await fs.readFile(coordinates));config.protected_boxes=[{lo:[20,3,10],hi:[20,3,10]}];await fs.writeFile(coordinates,JSON.stringify(config))
await fs.mkdir(path.join(workspace,'.nbtcreator'),{recursive:true});await fs.writeFile(path.join(workspace,'.nbtcreator/preferences.json'),JSON.stringify({startPage:'model',autoPreview:false}))
let app,page;const checks={},errors=[]
const click=id=>page.locator('#'+id).evaluate(e=>e.click()),geometry=()=>page.evaluate(()=>document.querySelector('#viewer').contentWindow.nbtModeler.metadata().geometry_sha256)
const voxel=p=>page.evaluate(p=>document.querySelector('#viewer').contentWindow.nbtModeler.snapshot.master_blocks.find(([q])=>q.every((v,i)=>v===p[i]))?.[1]??'minecraft:air',p)
async function preview(){await click('road-preview');await page.waitForFunction(()=>!document.querySelector('#road-preview').disabled&&!window.detailControl.state.commitBusy&&!window.detailControl.state.previewBusy);return page.locator('#road-status').textContent()}
try{
 const env={...process.env,NBTCREATOR_AUTOMATION:'1',OPENBLAS_NUM_THREADS:'1',OMP_NUM_THREADS:'1'};delete env.ELECTRON_RUN_AS_NODE
 app=await _electron.launch({executablePath:path.join(root,'node_modules/electron/dist/electron.exe'),args:[root,'--workspace',workspace,'--user-data-dir',path.join(output,'profile')],env,timeout:60000});page=await app.firstWindow();page.setDefaultTimeout(60000);await minimizedScreenshots(app,page);page.on('pageerror',e=>errors.push(e.message))
 await page.waitForFunction(()=>window.nbtEditSession?.ready&&!window.detailControl.state.busy&&!window.detailControl.state.sessionRestoring)
 await page.getByRole('button',{name:'自动道路',exact:true}).evaluate(e=>e.click());assert.equal(await page.locator('#road-panel').isVisible(),true);assert.equal(await page.locator('#tool-tabs button[aria-pressed=true]').textContent(),'自动道路');checks.road_panel_is_in_the_catalog_below_building_selector=true
 await page.evaluate(()=>{const s=window.detailControl.gather();s.whole_region=false;s.lo=[4,3,4];s.hi=[25,3,25];window.detailControl.restore(s)})
 await page.locator('#road-state').fill('gold_block');assert.ok((await preview()).includes('已有方块'));assert.equal(await page.evaluate(()=>window.detailControl.gather().operations.length),0);checks.occupied_surface_requires_explicit_overwrite=true
 await page.locator('#road-overwrite').check();assert.ok((await preview()).includes('道路已加入候选'));assert.equal(await voxel([6,3,6]),'minecraft:gold_block');assert.equal(await voxel([20,3,20]),'minecraft:gold_block');assert.equal(await voxel([2,3,2]),'minecraft:stone_bricks');checks.road_preview_changes_only_its_footprint=true
 const saved=await geometry(),operations=await page.evaluate(()=>window.detailControl.gather().operations)
 await page.locator('#road-route').selectOption('x_first');assert.ok((await preview()).includes('保护'));assert.equal(await geometry(),saved);assert.deepEqual(await page.evaluate(()=>window.detailControl.gather().operations),operations);checks.protection_failure_keeps_previous_candidate=true
 await page.locator('#road-end-x').fill('1000');assert.ok((await preview()).includes('超出'));assert.equal(await geometry(),saved);checks.out_of_bounds_keeps_previous_candidate=true
 assert.equal(digest(await fs.readFile(source)),before);assert.deepEqual(errors,[]);checks.source_unchanged_and_no_renderer_errors=true
 await page.screenshot({path:path.join(output,'auto-roads.png')});await fs.writeFile(path.join(output,'results.json'),JSON.stringify({passed:true,checks},null,2));console.log(JSON.stringify({passed:true,checks,output}))
}catch(e){console.error(JSON.stringify({output,checks,errors}));throw e}finally{await app?.close()}
