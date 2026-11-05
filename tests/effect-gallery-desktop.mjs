import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import path from 'node:path'
import {createRequire} from 'node:module'
import {root,skill} from '../scripts/paths.mjs'
import {minimizedScreenshots} from './minimized-screenshots.mjs'
const require=createRequire(path.join(skill,'assets/viewer/package.json')),{_electron}=require('playwright')
const output=path.join(root,'build','effect-gallery-'+Date.now()),workspace=path.join(output,'workspace'),checks={};await fs.mkdir(path.join(workspace,'.nbtcreator'),{recursive:true});await fs.writeFile(path.join(workspace,'.nbtcreator/preferences.json'),JSON.stringify({startPage:'assets'}))
let app,page
try{
 const env={...process.env,NBTCREATOR_AUTOMATION:'1'};delete env.ELECTRON_RUN_AS_NODE
 app=await _electron.launch({executablePath:process.env.NBTCREATOR_TEST_EXE||path.join(root,'node_modules/electron/dist/electron.exe'),args:[...(process.env.NBTCREATOR_TEST_EXE?[]:[root]),'--workspace',workspace,'--user-data-dir',path.join(output,'profile')],env,timeout:60000});page=await app.firstWindow();page.setDefaultTimeout(60000);await minimizedScreenshots(app,page);const errors=[];page.on('pageerror',error=>errors.push(error.message))
 await page.waitForFunction(()=>document.querySelectorAll('.effect-asset-card').length===32);assert.equal(await page.locator('#effect-assets-gallery').isVisible(),true);assert.equal(await page.locator('#tool-effects-dialog').evaluate(e=>e.open),false);assert.equal(await page.locator('#asset-kind-effects').getAttribute('aria-pressed'),'true');assert.equal(await page.locator('.asset-card').count(),0);await page.waitForFunction(()=>[...document.querySelectorAll('.effect-asset-card img')].every(img=>img.complete&&img.naturalWidth>0));checks.blank_assets_show_initial_effect_cards_and_thumbnails_without_opening_a_dialog=true
 await page.locator('#asset-search').fill('三格宽石砖');assert.equal(await page.locator('.effect-asset-card').count(),1);await page.locator('.effect-asset-card').click();await page.waitForFunction(()=>document.querySelector('#tool-effects-viewer').contentWindow.nbtModeler?.status==='ready');assert.equal(await page.locator('#tool-effects-name').inputValue(),'三格宽石砖步道');await page.locator('#tool-effects-close').click();await page.locator('#asset-search').fill('');await page.screenshot();await page.waitForTimeout(150);await page.screenshot({path:path.join(output,'initial-effects-in-asset-manager.png')});checks.search_and_card_open_real_3d_preview=true
 await page.locator('#asset-kind-components').click();assert.equal(await page.locator('#effect-assets-gallery').isVisible(),false);assert.equal(await page.locator('#asset-create-agent').isVisible(),true);assert.equal(await page.locator('.asset-card').count(),0);await page.locator('#asset-kind-effects').click();await page.waitForFunction(()=>document.querySelectorAll('.effect-asset-card').length===32);checks.effects_and_components_have_distinct_visible_tabs=true
 await page.reload();await page.waitForFunction(()=>document.querySelectorAll('.effect-asset-card').length===32);assert.equal(await page.locator('#effect-assets-gallery').isVisible(),true);assert.deepEqual(errors,[]);checks.reload_does_not_duplicate_initial_effects=true
 await fs.writeFile(path.join(output,'results.json'),JSON.stringify({passed:true,checks},null,2));console.log(JSON.stringify({passed:true,checks:Object.keys(checks).length,output}))
}finally{await app?.close()}
