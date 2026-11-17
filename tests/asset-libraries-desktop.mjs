import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import path from 'node:path'
import http from 'node:http'
import {createHash} from 'node:crypto'
import {createRequire} from 'node:module'
import {root,skill} from '../scripts/paths.mjs'
import {minimizedScreenshots} from './minimized-screenshots.mjs'
const require=createRequire(path.join(skill,'assets/viewer/package.json')),{_electron}=require('playwright')
const output=path.join(root,'build','asset-libraries-'+Date.now()),workspace=path.join(output,'workspace');await fs.mkdir(workspace,{recursive:true})
const sha=raw=>createHash('sha256').update(raw).digest('hex'),raw=value=>Buffer.from(JSON.stringify(value))
const recipe=raw({schema_version:1,kind:'nbtcreator.parametric-recipe',arguments:{kind:'pillar',name:'远端测试石柱',size:[3,12,3],material:'stone_bricks'}})
const component=raw({schema_version:1,name:'远端测试构件',size:[1,1,1],anchor:[0,0,0],palette:['gold_block'],blocks:[[0,0,0,0,false]]})
const manifest=raw({schema_version:1,kind:'nbtcreator.asset-library',id:'test.remote',name:'远端测试库',version:'1.0.0',license:'CC0-1.0',assets:[
 {id:'pillar',name:'远端测试石柱',type:'parametric_recipe',path:'pillar.json',bytes:recipe.length,sha256:sha(recipe)},
 {id:'component',name:'远端测试构件',type:'component',path:'component.json',bytes:component.length,sha256:sha(component)}]})
const registry=raw({schema_version:1,kind:'nbtcreator.asset-registry',libraries:[{id:'test.remote',name:'远端测试库',version:'1.0.0',path:'library.json',manifest_sha256:sha(manifest)}]})
let unavailable=false
const files={'/registry.json':registry,'/library.json':manifest,'/pillar.json':recipe,'/component.json':component}
const server=http.createServer((req,res)=>{const value=files[req.url];if(unavailable||!value){res.writeHead(404);res.end();return}res.writeHead(200,{'Content-Type':'application/json','Content-Length':value.length});res.end(value)})
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve))
let app,page;const errors=[],checks={}
const click=id=>page.locator('#'+id).evaluate(element=>element.click())
const idle=()=>page.waitForFunction(()=>document.querySelector('#asset-libraries').getAttribute('aria-busy')==='false')
try{
 const env={...process.env,NBTCREATOR_AUTOMATION:'1'};delete env.ELECTRON_RUN_AS_NODE
 app=await _electron.launch({executablePath:process.env.NBTCREATOR_TEST_EXE||path.join(root,'node_modules/electron/dist/electron.exe'),args:[...(process.env.NBTCREATOR_TEST_EXE?[]:[root]),'--workspace',workspace,'--user-data-dir',path.join(output,'profile')],env,timeout:60000})
 page=await app.firstWindow();page.setDefaultTimeout(60000);await minimizedScreenshots(app,page);page.on('pageerror',error=>errors.push(error.message));await page.waitForFunction(()=>window.detailControl?.state.catalogReady)
 await page.locator('[data-workspace=assets]').evaluate(element=>element.click());await click('asset-libraries-open');await idle()
 const more=page.locator('#asset-libraries-items>button').filter({hasText:'显示更多资产'});if(await more.count()){const count=await page.locator('#asset-libraries-items article').count();await more.evaluate(element=>element.click());await idle();assert.ok(await page.locator('#asset-libraries-items article').count()>count);checks.large_pack_pagination=true}
 await page.locator('#asset-libraries-search').fill('方柱');assert.ok(await page.locator('[data-asset-id="nbtcreator.modular/pillar-square"]').count());await page.locator('#asset-libraries-search').fill('');checks.bundled_snapshot_browsable=true
 await page.locator('#asset-libraries-source').fill(`http://127.0.0.1:${server.address().port}/registry.json`)
 await page.locator('#asset-libraries-form').evaluate(form=>form.requestSubmit());await idle()
 await page.locator('#asset-libraries-discovery button').evaluate(element=>element.click());await idle()
 assert.equal(await page.locator('#asset-libraries-connections article').count(),1);assert.equal(await page.locator('[data-asset-id="test.remote/pillar"]').count(),1);checks.remote_registry_connects_complete_library=true
 await page.screenshot({path:path.join(output,'library-manager.png')})
 await page.locator('[data-asset-id="test.remote/pillar"] button').evaluate(element=>element.click())
 await page.waitForFunction(()=>document.querySelector('#component-author').open&&!document.querySelector('#component-preset-kind').disabled)
 assert.equal(await page.locator('#component-preset-recipe').inputValue(),'test.remote/pillar')
 await click('component-preset-preview');await page.waitForFunction(()=>!document.querySelector('#component-write').disabled,undefined,{timeout:90000})
 assert.ok((await page.locator('#component-preview-name').textContent()).includes('远端测试石柱'));checks.external_recipe_compiles_in_real_preview=true
 await click('component-close');await click('asset-libraries-open');await idle()
 await page.locator('[data-asset-id="test.remote/component"] button').evaluate(element=>element.click());await idle()
 assert.ok((await page.locator('#asset-libraries-status').textContent()).includes('待审阅'));checks.component_import_preserves_review_flow=true
 unavailable=true
 await page.locator('#asset-libraries-connections article button').filter({hasText:'刷新'}).evaluate(element=>element.click());await idle()
 assert.ok((await page.locator('#asset-libraries-status').textContent()).includes('不可用'));assert.equal(await page.locator('[data-asset-id="test.remote/pillar"]').count(),1);checks.failed_remote_refresh_keeps_offline_assets=true
 await page.locator('#asset-libraries-connections article button').filter({hasText:'停用'}).evaluate(element=>element.click());await idle();assert.equal(await page.locator('[data-asset-id="test.remote/pillar"]').count(),0)
 await page.locator('#asset-libraries-connections article button').filter({hasText:'启用'}).evaluate(element=>element.click());await idle();assert.equal(await page.locator('[data-asset-id="test.remote/pillar"]').count(),1);checks.disable_enable_works_offline=true
 await page.locator('#asset-libraries-connections article button').filter({hasText:'移除连接'}).evaluate(element=>element.click());await idle();assert.equal(await page.locator('[data-asset-id="test.remote/pillar"]').count(),0)
 await click('asset-libraries-close');assert.ok((await page.locator('#asset-count').textContent()).includes('1'));checks.remove_keeps_imported_component=true
 assert.deepEqual(errors,[]);await fs.writeFile(path.join(output,'results.json'),JSON.stringify({passed:true,checks},null,2));console.log(JSON.stringify({passed:true,checks,output}))
}catch(error){console.error(JSON.stringify({output,checks,errors}));if(page)console.error(await page.locator('#asset-libraries-status').textContent().catch(()=>''));throw error}
finally{await app?.close();await new Promise(resolve=>server.close(resolve))}
