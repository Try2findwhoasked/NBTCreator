import fs from 'node:fs/promises'
import path from 'node:path'
import assert from 'node:assert/strict'
import {parseArgs} from 'node:util'
import {startWorkbenchServer} from '../server.mjs'
import {launchRenderBrowser} from './runtime.mjs'
const {values}=parseArgs({options:{fixture:{type:'string'},model:{type:'string'},output:{type:'string'}}})
if(!values.fixture||!values.model||!values.output)throw new Error('Provide --fixture synthetic mod workspace --model complete master --output new-directory')
const output=path.resolve(values.output);await fs.mkdir(output);const workspace=path.join(output,'workspace');await fs.cp(values.fixture,workspace,{recursive:true})
const source=path.join(workspace,'nbt_models/single/合并测试/v01/master/master_geometry.json.gz');await fs.mkdir(path.dirname(source),{recursive:true});await fs.copyFile(values.model,source)
const legacy=path.join(workspace,'build/nbt_control');await fs.mkdir(path.join(legacy,'mod_structure_changes/old/backup'),{recursive:true})
const state=JSON.stringify({schema_version:1,favorites:[source],selected:[source]}),receipt='{"status":"historical","source":"do not rewrite"}\r\n'
await fs.writeFile(path.join(legacy,'structure_library.json'),state);await fs.writeFile(path.join(legacy,'mod_structure_changes/old/backup/result.json'),receipt)
let app,browser;const checks={}
try{
  app=await startWorkbenchServer({workspace});const base=new URL(app.url).origin
  assert.equal(await fs.readFile(path.join(app.dataRoot,'structure_library.json'),'utf8'),state)
  assert.equal(await fs.readFile(path.join(app.dataRoot,'mod_structure_changes/old/backup/result.json'),'utf8'),receipt)
  assert.equal(await fs.readFile(path.join(legacy,'structure_library.json'),'utf8'),state);checks.legacy_state_and_receipts_copied_without_loss=true
  const info=await(await fetch(base+'/api/workbench')).json();assert.equal(info.editor_url,null);assert.ok(info.data_root.endsWith(path.join('build','structure_workbench')));checks.own_service_and_data_root=true
  for(const route of ['/control.html','/__detail__/init','/__detail__/jobs','/api/asset/unknown'])assert.equal((await fetch(base+route)).status,404);checks.detail_service_routes_not_mounted=true
  browser=await launchRenderBrowser();const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];page.on('pageerror',error=>errors.push(error.message));await page.goto(app.url);await page.waitForFunction(()=>window.modStructures?.state.catalog?.rooms.length===7)
  await page.getByRole('link',{name:'作者结构库',exact:true}).click();await page.waitForFunction(()=>window.structureLibrary?.state.models.length===1);assert.equal(new URL(page.url()).origin,base);assert.equal(await page.locator('#selected-count').textContent(),'已选 1 项');checks.unified_tabs_share_one_origin_and_saved_selection=true
  await page.getByRole('link',{name:'模组结构管理',exact:true}).click();await page.waitForFunction(()=>window.modStructures?.state.catalog?.rooms.length===7);assert.equal(new URL(page.url()).origin,base);checks.module_management_and_author_library_consolidated=true
  const beforeLeave=await(await fetch(base+'/api/workbench')).json();assert.equal(beforeLeave.editor_url,null);checks.browsing_does_not_start_detail_console=true
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);assert.deepEqual(errors,[]);checks.no_browser_errors_or_horizontal_overflow=true
  await app.close();app=await startWorkbenchServer({workspace});assert.equal(await fs.readFile(path.join(app.dataRoot,'structure_library.json'),'utf8'),state);checks.migration_idempotent_on_restart=true
  await app.close();app=await startWorkbenchServer({workspace,dataRoot:path.join(output,'custom_data')});await(await fetch(new URL('/api/library',app.url))).json();await fs.access(path.join(app.dataRoot,'catalog_metadata.json'));assert.equal(await fs.readFile(path.join(app.dataRoot,'structure_library.json'),'utf8'),state);checks.custom_data_root_contains_catalog_and_migrated_state=true
  await fs.writeFile(path.join(output,'results.json'),JSON.stringify({passed:true,checks},null,2));console.log(JSON.stringify({passed:true,checks:Object.keys(checks).length,output}))
}finally{await browser?.close();await app?.close()}
