import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import path from 'node:path'
import {spawnSync} from 'node:child_process'
import {createHash} from 'node:crypto'
import {createRequire} from 'node:module'
import {root,skill,python} from '../scripts/paths.mjs'
import {minimizedScreenshots} from './minimized-screenshots.mjs'

const require=createRequire(path.join(skill,'assets/viewer/package.json'))
const {_electron}=require('playwright')
const output=path.join(root,'build','asset-interaction-'+Date.now())
const workspace=path.join(output,'workspace'),folder=path.join(workspace,'nbt_models/single/room/v1')
const fixture=spawnSync(python,[path.join(root,'tests/make_fixture.py'),folder],{encoding:'utf8',windowsHide:true})
assert.equal(fixture.status,0,fixture.stderr)
const source=path.join(folder,'synthetic.master.json.gz')
const hash=bytes=>createHash('sha256').update(bytes).digest('hex'),baseline=hash(await fs.readFile(source))
const asset=spawnSync(python,['-c',`import sys;sys.path.insert(0,sys.argv[1]);from nbt_components import store;store(sys.argv[2],dict(schema_version=1,name='交互测试石柱',tags=['建筑骨架'],size=[1,3,1],anchor=[0,0,0],palette=['stone'],blocks=[[0,y,0,0,False] for y in range(3)]))`,path.join(skill,'scripts'),workspace],{encoding:'utf8',windowsHide:true})
assert.equal(asset.status,0,asset.stderr)
await fs.mkdir(path.join(workspace,'.nbtcreator'),{recursive:true})
await fs.writeFile(path.join(workspace,'.nbtcreator/preferences.json'),JSON.stringify({startPage:'project',autoPreview:false}))
let app,page;const checks={},errors=[]
async function click(id){await page.waitForFunction(id=>{const e=document.getElementById(id);return e&&!e.disabled},id);await page.locator('#'+id).evaluate(e=>e.click())}
try{
 const env={...process.env,NBTCREATOR_AUTOMATION:'1'};delete env.ELECTRON_RUN_AS_NODE
 app=await _electron.launch({executablePath:process.env.NBTCREATOR_TEST_EXE||path.join(root,'node_modules/electron/dist/electron.exe'),args:[...(process.env.NBTCREATOR_TEST_EXE?[]:[root]),'--workspace',workspace,'--user-data-dir',path.join(output,'profile')],env,timeout:60000})
 page=await app.firstWindow();page.setDefaultTimeout(60000);await minimizedScreenshots(app,page);page.on('pageerror',e=>errors.push(e.message))
 await page.waitForFunction(()=>window.detailControl?.state.catalogReady)
 assert.equal(await page.evaluate(()=>window.detailControl.state.info),null)
 await page.locator('button[data-workspace=assets]').evaluate(e=>e.click())
 await page.locator('.asset-card').waitFor();await page.locator('.asset-card').evaluate(e=>e.click())
 for(const id of ['asset-place','asset-pick','asset-use-range','asset-adjust-3d'])assert.equal(await page.locator('#'+id).isDisabled(),true)
 assert.equal(await page.locator('#asset-update').isEnabled(),true)
 assert.ok((await page.locator('#asset-target').textContent()).includes('请先'))
 checks.no_target_disables_placement_and_keeps_library_management=true

 await page.locator('#asset-edit-name').fill('');await click('asset-update')
 await page.waitForFunction(()=>!document.querySelector('#asset-update').disabled&&document.querySelector('#asset-detail-status').classList.contains('error'))
 assert.equal(await page.locator('#asset-detail-status').isVisible(),true)
 assert.ok((await page.locator('#asset-detail-status').textContent()).length>0)
 assert.equal(await page.locator('.asset-card strong').textContent(),'交互测试石柱')
 await page.screenshot();await page.waitForTimeout(150);await page.screenshot({path:path.join(output,'error-in-inspector.png')})
 checks.rename_error_visible_in_active_dialog_and_original_kept=true

 let release,seen;const waiting=new Promise(resolve=>seen=resolve)
 await page.route('**/__detail__/components/update',async route=>{seen();await new Promise(resolve=>release=resolve);await route.continue()})
 await page.locator('#asset-edit-name').fill('交互验收石柱');await click('asset-update');await waiting
 for(const id of ['asset-update','asset-edit-name','asset-edit-tags','asset-archive','asset-place'])assert.equal(await page.locator('#'+id).isDisabled(),true)
 assert.equal(await page.locator('#asset-inspector-close').isEnabled(),true)
 await click('asset-inspector-close');release()
 await page.waitForFunction(()=>document.querySelector('.asset-card strong').textContent==='交互验收石柱'&&document.querySelector('#asset-inspector-dialog').getAttribute('aria-busy')==='false')
 await page.unroute('**/__detail__/components/update')
 assert.equal(await page.locator('#asset-inspector-dialog').evaluate(e=>e.open),false)
 await click('asset-refresh');assert.equal(await page.locator('#asset-inspector-dialog').evaluate(e=>e.open),false)
 checks.inflight_management_is_locked_and_closed_dialog_stays_closed=true

 await page.locator('button[data-workspace=project]').evaluate(e=>e.click());await page.locator('.project-card-open').first().evaluate(e=>e.click());await page.waitForFunction(()=>!window.detailControl.state.busy);await click('project-preview-edit')
 await page.waitForFunction(()=>window.detailControl.state.info&&!window.detailControl.state.busy&&window.detailControl.state.mode==='3d')
 let releasePreview,previewSeen;const previewWaiting=new Promise(resolve=>previewSeen=resolve)
 await page.route('**/__detail__/jobs',async route=>{if(route.request().method()==='POST'&&route.request().postDataJSON()?.kind==='preview'){previewSeen();await new Promise(resolve=>releasePreview=resolve)}await route.continue()})
 await click('update-preview');await previewWaiting
 await page.locator('button[data-workspace=assets]').evaluate(e=>e.click());await page.locator('.asset-card').evaluate(e=>e.click())
 assert.equal(await page.locator('#asset-place').isDisabled(),true);assert.equal(await page.locator('#asset-inspector-close').isEnabled(),true)
 releasePreview();await page.waitForFunction(()=>!window.detailControl.state.previewBusy&&!document.querySelector('#asset-place').disabled);await page.unroute('**/__detail__/jobs')
 await click('asset-inspector-close')
 checks.model_preview_busy_state_blocks_placement_and_recovers=true
 await page.locator('button[data-workspace=assets]').evaluate(e=>e.click());await page.locator('.asset-card').evaluate(e=>e.click())
 for(const [axis,value]of [['x',60],['y',4],['z',16]])await page.locator('#asset-position-'+axis).fill(String(value))
 await click('asset-place');await page.waitForFunction(()=>!document.querySelector('#asset-place').disabled&&document.querySelector('#asset-detail-status').classList.contains('error'))
 assert.equal(await page.locator('#asset-inspector-dialog').evaluate(e=>e.open),true)
 assert.equal(await page.locator('#asset-detail-status').isVisible(),true)
 await page.locator('#asset-inspector-dialog').evaluate(e=>e.scrollTop=e.scrollHeight);await page.waitForTimeout(50)
 assert.equal(await page.locator('#asset-detail-status').evaluate(e=>{const r=e.getBoundingClientRect(),d=e.closest('dialog').getBoundingClientRect();return r.top>=d.top&&r.bottom<=d.bottom}),true)
 assert.deepEqual(await page.evaluate(()=>window.detailControl.gather().operations),[])
 checks.out_of_bounds_placement_reports_in_dialog_without_mutation=true

 await page.locator('#asset-position-x').fill('16');await click('asset-place')
 await page.waitForFunction(()=>document.body.dataset.workspace==='model'&&!window.detailControl.state.previewBusy&&!window.detailControl.state.commitBusy&&window.detailControl.state.preview)
 assert.ok((await page.evaluate(()=>window.detailControl.gather().operations)).length)
 checks.failed_placement_can_be_corrected_and_retried=true
 const valid=await page.locator('#operation-sequence').inputValue()
 await page.locator('#operation-sequence').evaluate(e=>{e.value='{';e.dispatchEvent(new Event('input',{bubbles:true}))})
 await page.locator('button[data-workspace=assets]').evaluate(e=>e.click());await page.locator('.asset-card').evaluate(e=>e.click())
 assert.equal(await page.locator('#asset-place').isDisabled(),true)
 assert.ok((await page.locator('#asset-target').textContent()).includes('参数尚未'))
 assert.equal(await page.locator('#asset-update').isEnabled(),true)
 await click('asset-inspector-close');await page.locator('#operation-sequence').evaluate((e,text)=>{e.value=text;e.dispatchEvent(new Event('input',{bubbles:true}))},valid)
 checks.unfinished_model_parameters_do_not_break_library_management=true
 assert.equal(hash(await fs.readFile(source)),baseline);assert.deepEqual(errors,[])
 await fs.writeFile(path.join(output,'results.json'),JSON.stringify({passed:true,checks},null,2));console.log(JSON.stringify({passed:true,checks,output}))
}catch(error){console.error(JSON.stringify({output,checks,errors,status:await page?.locator('#asset-detail-status').textContent().catch(()=>null)}));throw error}finally{await app?.close()}
