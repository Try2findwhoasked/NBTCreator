// Only a copied synthetic workspace is edited by this browser regression.
import fs from 'node:fs/promises'
import path from 'node:path'
import assert from 'node:assert/strict'
import {parseArgs} from 'node:util'
import {createHash} from 'node:crypto'
import {startWorkbenchServer} from '../server.mjs'
import {launchRenderBrowser} from './runtime.mjs'
const {values}=parseArgs({options:{fixture:{type:'string'},output:{type:'string'},python:{type:'string'}}})
if(!values.fixture||!values.output)throw new Error('Provide --fixture synthetic workspace --output new-directory')
const output=path.resolve(values.output);await fs.mkdir(output);const workspace=path.join(output,'workspace');await fs.cp(values.fixture,workspace,{recursive:true})
const data=path.join(workspace,'src/main/resources/data/saodg'),hash=bytes=>createHash('sha256').update(bytes).digest('hex'),checks={}
const templates=await fs.readdir(path.join(data,'structures'),{recursive:true}),originals=new Map()
for(const file of templates.filter(file=>file.endsWith('.nbt')))originals.set(file,hash(await fs.readFile(path.join(data,'structures',file))))
let app,browser
try{
  app=await startWorkbenchServer({workspace,python:values.python||'python'})
  browser=await launchRenderBrowser();const page=await browser.newPage({viewport:{width:1600,height:1050},acceptDownloads:true}),errors=[]
  page.on('pageerror',error=>errors.push(error.message));await page.goto(app.url)
  await page.waitForFunction(()=>window.modStructures?.state.catalog?.rooms.length===7)
  assert.equal(await page.locator('.structure-card').count(),7);assert.ok((await page.locator('#pool-count').textContent()).includes('6 /'))
  checks.mod_catalog_not_author_library=true
  await page.locator('[data-filter=disabled]').click();assert.equal(await page.locator('.structure-card').count(),1);assert.ok((await page.locator('.card-content').innerText()).includes('未选安全房'));checks.inactive_functional_definition_preserved=true
  await page.locator('[data-filter=all]').click();await page.locator('#room-search').fill('备用');await page.locator('.card-content').click()
  await page.waitForFunction(()=>document.querySelector('.detail-cover img')?.naturalWidth>0,undefined,{timeout:60000})
  assert.equal(await page.locator('.template-entry').count(),2);assert.ok((await page.locator('.template-entry').first().textContent()).includes('主体'));assert.ok((await page.locator('#room-detail').innerText()).includes('saodg:room_6'));checks.actual_templates_cover_and_layer_references=true
  assert.equal(await page.locator('#mod-preview-frame').getAttribute('src'),null);checks.three_dimensional_preview_is_on_demand=true
  const dungeonFile=path.join(data,'dungeons/ruins.json'),dungeonBytes=await fs.readFile(dungeonFile)
  await page.locator('#detail-enabled').uncheck();assert.equal(hash(await fs.readFile(dungeonFile)),hash(dungeonBytes));assert.equal(await page.locator('#review-changes').isEnabled(),true)
  await page.locator('#refresh-mod').click();assert.ok((await page.locator('#mod-notice').innerText()).includes('未保存'));checks.selection_is_draft_until_explicit_save=true
  await page.locator('#room-search').fill('战斗厅');await page.locator('.card-content').filter({hasText:'战斗厅'}).first().click();await page.locator('#room-priority').fill('25');await page.locator('#room-priority').press('Tab')
  assert.equal(await page.evaluate(()=>window.modStructures.state.priorities.size),1)
  await page.locator('#review-changes').click();assert.ok((await page.locator('#changes-list').textContent()).includes('优先级 70 → 25'));assert.equal(await page.locator('#changes-dialog').evaluate(node=>node.open),true)
  await page.locator('#apply-changes').click();await page.waitForFunction(()=>!window.modStructures.state.busy&&document.querySelector('#mod-notice').textContent.includes('已写入'),undefined,{timeout:30000})
  const pool=JSON.parse(await fs.readFile(dungeonFile,'utf8')).layout.room_pool;assert.equal(pool.includes('saodg:room_6'),false);assert.equal(JSON.parse(await fs.readFile(path.join(data,'rooms/room_1.json'),'utf8')).selection_priority,25)
  assert.equal(await page.locator('#review-changes').isDisabled(),true);checks.review_then_save_updates_real_resource_json=true
  const changesRoot=path.join(workspace,'build/structure_workbench/mod_structure_changes'),entries=await fs.readdir(changesRoot);assert.equal(entries.length,1);const before=await fs.readFile(path.join(changesRoot,entries[0],'backup/000_before.json'));assert.equal(hash(before),hash(dungeonBytes));checks.exact_original_file_backup=true
  await page.locator('#room-search').fill('入口');await page.locator('.card-content').click();await page.locator('#detail-enabled').uncheck();await page.locator('#review-changes').click();await page.locator('#apply-changes').click();await page.waitForFunction(()=>document.querySelector('#mod-notice').textContent.includes('必要用途'))
  assert.equal(JSON.parse(await fs.readFile(dungeonFile,'utf8')).layout.room_pool.includes('saodg:room_0'),true);assert.equal(await page.locator('#save-error').isVisible(),true);await page.locator('#cancel-changes').click();await page.locator('#reset-draft').click();checks.cannot_remove_last_required_room_type=true
  await page.locator('#preview-room').click();await page.waitForFunction(()=>document.querySelector('#mod-preview-dialog').open,undefined,{timeout:30000})
  await page.frameLocator('#mod-preview-frame').locator('#preview').waitFor({timeout:60000})
  const viewer=await (await page.locator('#mod-preview-frame').elementHandle()).contentFrame();await viewer.waitForFunction(()=>window.nbtModeler?.ready,undefined,{timeout:60000});await viewer.evaluate(()=>window.nbtModeler.ready)
  await page.locator('#close-mod-preview').click();await page.waitForFunction(()=>document.querySelector('#mod-preview-frame').getAttribute('src')==='about:blank');checks.actual_room_3d_loads_and_releases=true
  await page.locator('#room-search').fill('');await page.screenshot({path:path.join(output,'mod-manager-desktop.png')})
  for(const viewport of [{width:390,height:844},{width:1000,height:800},{width:1920,height:1080}]){await page.setViewportSize(viewport);assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true)}checks.responsive_layout=true
  await page.setViewportSize({width:390,height:844});await page.screenshot({path:path.join(output,'mod-manager-mobile.png'),fullPage:true})
  const base=new URL(app.url).origin;assert.equal((await fetch(base+'/api/mod/apply',{method:'POST',headers:{Origin:'https://example.com','Content-Type':'application/json'},body:'{}'})).status,403);checks.cross_origin_write_rejected=true
  for(const [file,original]of originals)assert.equal(hash(await fs.readFile(path.join(data,'structures',file))),original);checks.all_nbt_bytes_preserved=true
  assert.deepEqual(errors,[]);checks.no_browser_errors=true
  await fs.writeFile(path.join(output,'results.json'),JSON.stringify({passed:true,checks},null,2));console.log(JSON.stringify({passed:true,checks:Object.keys(checks).length,output}))
}finally{await browser?.close();await app?.close()}
