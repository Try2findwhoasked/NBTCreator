import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import path from 'node:path'
import {spawnSync} from 'node:child_process'
import {createRequire} from 'node:module'
import {root,skill,python} from '../scripts/paths.mjs'
import {minimizedScreenshots} from './minimized-screenshots.mjs'
const require=createRequire(path.join(skill,'assets/viewer/package.json')),{_electron}=require('playwright')
const output=path.join(root,'build','project-menus-'+Date.now()),workspace=path.join(output,'workspace'),folder=path.join(workspace,'nbt_models/single/hall/v1')
const made=spawnSync(python,[path.join(root,'tests/make_fixture.py'),folder],{encoding:'utf8',windowsHide:true});assert.equal(made.status,0,made.stderr)
const source=path.join(folder,'synthetic.master.json.gz'),original=await fs.readFile(source)
let app,page;const errors=[],checks={};const click=id=>page.locator('#'+id).evaluate(e=>e.click())
async function launch(){const env={...process.env,NBTCREATOR_AUTOMATION:'1'};delete env.ELECTRON_RUN_AS_NODE;app=await _electron.launch({executablePath:process.env.NBTCREATOR_TEST_EXE||path.join(root,'node_modules/electron/dist/electron.exe'),args:[...(process.env.NBTCREATOR_TEST_EXE?[]:[root]),'--workspace',workspace,'--user-data-dir',path.join(output,'profile')],env,timeout:60000});page=await app.firstWindow();page.setDefaultTimeout(60000);minimizedScreenshots(app,page);page.on('pageerror',e=>errors.push(e.message));await page.waitForFunction(()=>window.detailControl?.state.catalogReady&&!document.querySelector('#project-menu-create').disabled)}
try{
 await launch();await page.waitForFunction(()=>document.querySelector('.project-card-manage'));await click('project-menu-create');await page.locator('#project-menu-name').fill('建筑素材');await click('project-menu-save');await page.waitForFunction(()=>!document.querySelector('#project-menu-dialog').open);let id=await page.locator('[data-custom-menu]').getAttribute('data-custom-menu');await page.locator('.project-card-manage').evaluate(e=>e.click());assert.equal(await page.locator('.project-content-kind').count(),0);await page.locator('.project-custom-menu').selectOption(id);await page.waitForFunction(()=>!document.querySelector('.project-custom-menu').disabled);await click('project-manage-close');checks.native_building_cards_do_not_require_effect_classification=true
 await app.close();app=null;await launch();await page.locator('[data-custom-menu]').evaluate(e=>e.click());await page.waitForFunction(()=>document.querySelectorAll('.project-card').length===1);checks.menu_and_membership_survive_restart=true
 await page.getByRole('button',{name:'重命名菜单 建筑素材',exact:true}).evaluate(e=>e.click());await page.locator('#project-menu-name').fill('我的建筑');await click('project-menu-save');await page.waitForFunction(()=>document.querySelector('[data-custom-menu]').textContent==='我的建筑');await page.getByRole('button',{name:'删除菜单 我的建筑',exact:true}).evaluate(e=>e.click());await page.waitForFunction(()=>document.querySelectorAll('[data-custom-menu]').length===0);assert.deepEqual(await fs.readFile(source),original);checks.rename_delete_never_move_or_delete_assets=true
 await page.evaluate(async source=>{await fetch('/__detail__/effects/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:'参数效果',request:{source,settings:{operations:[]}}})})},source);await click('project-refresh');await page.waitForFunction(()=>document.querySelector('#project-status').textContent==='建筑库已刷新');assert.equal(await page.locator('.project-card').count(),1);assert.equal(await page.locator('[data-content-kind=effect]').count(),0);checks.saved_effect_parameters_are_not_building_cards=true
 assert.deepEqual(errors,[]);await fs.writeFile(path.join(output,'results.json'),JSON.stringify({passed:true,checks},null,2));console.log(JSON.stringify({passed:true,checks,output}))
}catch(e){console.error(JSON.stringify({output,checks,errors}));throw e}finally{await app?.close()}
