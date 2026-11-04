import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import path from 'node:path'
import {spawnSync} from 'node:child_process'
import {createHash} from 'node:crypto'
import {createRequire} from 'node:module'
import {root,skill,python} from '../scripts/paths.mjs'
import {minimizedScreenshots} from './minimized-screenshots.mjs'
const require=createRequire(path.join(skill,'assets/viewer/package.json')),{_electron}=require('playwright')
const output=path.join(root,'build','preview-toolbar-'+Date.now()),workspace=path.join(output,'workspace'),sample=path.join(workspace,'nbt_models/sample')
const made=spawnSync(python,[path.join(root,'tests/make_fixture.py'),sample],{encoding:'utf8',windowsHide:true});assert.equal(made.status,0,made.stderr)
const source=path.join(sample,'synthetic.master.json.gz'),hash=bytes=>createHash('sha256').update(bytes).digest('hex'),before=hash(await fs.readFile(source))
await fs.mkdir(path.join(workspace,'.nbtcreator'),{recursive:true});await fs.writeFile(path.join(workspace,'.nbtcreator/preferences.json'),JSON.stringify({startPage:'model',autoPreview:false}))
let app;const checks={}
try{
 const env={...process.env,NBTCREATOR_AUTOMATION:'1'};delete env.ELECTRON_RUN_AS_NODE
 app=await _electron.launch({executablePath:process.env.NBTCREATOR_TEST_EXE||path.join(root,'node_modules/electron/dist/electron.exe'),args:[...(process.env.NBTCREATOR_TEST_EXE?[]:[root]),'--workspace',workspace,'--user-data-dir',path.join(output,'profile')],env,timeout:60000})
 const page=await app.firstWindow();await minimizedScreenshots(app,page);const errors=[];page.on('pageerror',error=>errors.push(error.message))
 await page.waitForFunction(()=>window.detailControl?.state.info&&window.detailControl.state.mode==='3d'&&!window.detailControl.state.busy)
 const click=selector=>page.locator(selector).evaluate(el=>el.click())
 assert.equal(await page.locator('#enable-3d').getAttribute('aria-pressed'),'true');assert.equal(await page.locator('#pause-3d').isVisible(),false);checks.single_3d_toggle=true
 const measurements=[]
 for(const width of [1500,980,900]){
  await page.setViewportSize({width:width-16,height:780});await page.waitForFunction(width=>innerWidth===width,width-16)
  await page.waitForTimeout(150)
  const measure=await page.locator('.review-toolbar').evaluate(bar=>{const r=bar.getBoundingClientRect(),items=[...bar.querySelectorAll('button:not([hidden]),select,input[type=checkbox],input[type=range]')].filter(el=>el.getClientRects().length).map(el=>{const r=el.getBoundingClientRect();return {id:el.id,cy:r.y+r.height/2}});return {height:r.height,width:r.width,scroll:bar.scrollWidth,client:bar.clientWidth,items}})
  assert.ok(measure.height<=42,JSON.stringify(measure));assert.ok(Math.max(...measure.items.map(e=>e.cy))-Math.min(...measure.items.map(e=>e.cy))<3,JSON.stringify(measure));assert.ok(measure.scroll<=measure.client+1,JSON.stringify(measure));measurements.push({window:width,...measure})
 }
 checks.one_row_at_1500_980_900_without_scroll=true
 await click('#pick-material');assert.equal(await page.locator('#pick-material').getAttribute('aria-pressed'),'true');assert.equal(await page.locator('#pick-material svg').count(),1);await click('#pick-material')
 await click('#pick-coordinate');assert.equal(await page.locator('#pick-coordinate').getAttribute('aria-pressed'),'true');assert.equal(await page.locator('#pick-coordinate svg').count(),1);await click('#pick-coordinate');checks.compact_pick_controls_keep_icons=true
 await click('#viewport-assets');assert.equal(await page.locator('#viewport-asset-menu').isVisible(),true);assert.equal(await page.locator('#viewport-assets').getAttribute('aria-expanded'),'true');assert.equal(await page.locator('#save-selection-asset').isVisible(),true)
 await page.locator('#viewport-assets').focus();await page.keyboard.press('ArrowDown');await page.keyboard.press('Escape');await page.waitForFunction(()=>!document.querySelector('#viewport-asset-menu').matches(':popover-open'));assert.equal(await page.evaluate(()=>document.activeElement.id),'viewport-assets');await click('#viewport-assets');await click('#open-assets');await page.waitForFunction(()=>window.creatorWorkspace.current()==='assets');assert.equal(await page.locator('#viewport-asset-menu').isVisible(),false);await page.locator('button[data-workspace=model]').evaluate(el=>el.click());checks.asset_actions_in_popover=true
 await click('#enable-3d');await page.waitForFunction(()=>window.detailControl.state.mode==='images');assert.equal(await page.locator('#enable-3d').getAttribute('aria-pressed'),'false');await click('#enable-3d');await page.waitForFunction(()=>window.detailControl.state.mode==='3d'&&!window.detailControl.state.busy);checks.toggle_returns_to_images_and_reopens=true
 await page.setViewportSize({width:1484,height:910});await page.waitForTimeout(200);let clip=await page.locator('.review-toolbar').boundingBox();await page.screenshot({clip});await page.waitForTimeout(150);await page.screenshot({clip,path:path.join(output,'toolbar.png')})
 await page.setViewportSize({width:964,height:900});await page.locator('.review-toolbar').evaluate(el=>el.scrollIntoView({block:'center'}));await page.waitForTimeout(200);clip=await page.locator('.review-toolbar').boundingBox();await page.screenshot({clip});await page.waitForTimeout(150);await page.screenshot({clip,path:path.join(output,'toolbar-narrow.png')})
 assert.equal(hash(await fs.readFile(source)),before);assert.deepEqual(errors,[]);assert.equal(await app.evaluate(({BrowserWindow})=>BrowserWindow.getAllWindows()[0].isMinimized()),true);checks.original_unchanged_minimized_no_errors=true
 await fs.writeFile(path.join(output,'results.json'),JSON.stringify({passed:true,checks,measurements},null,2));console.log(JSON.stringify({passed:true,checks:Object.keys(checks).length,output}))
}catch(error){console.error(JSON.stringify({output,checks}));throw error}finally{await app?.close()}
