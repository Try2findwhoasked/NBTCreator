// Synthetic structure-selector regression; no edits to authored structures.
import fs from 'node:fs/promises'
import path from 'node:path'
import assert from 'node:assert/strict'
import { gunzipSync } from 'node:zlib'
import { createHash } from 'node:crypto'
import { parseArgs } from 'node:util'
import { startWorkbenchServer } from '../server.mjs'
import { launchRenderBrowser } from './runtime.mjs'

const {values}=parseArgs({options:{fixture:{type:'string'},output:{type:'string'},python:{type:'string'}}})
if(!values.fixture||!values.output)throw new Error('Provide --fixture check_detail_control_fixtures output --output new-directory')
const output=path.resolve(values.output);await fs.mkdir(output)
const workspace=path.join(output,'workspace'),root=path.join(workspace,'nbt_models'),checks={}
const fixture=await fs.readFile(path.join(values.fixture,'基线 空格.master.json.gz'))
const revised=await fs.readFile(path.join(values.fixture,'revision/refined.master.json.gz'))
const sources=[]
async function model(name,shape,version,bytes=fixture,withImage=false){
  const directory=path.join(root,shape,name,version),source=path.join(directory,'master/master_geometry.json.gz'),data=JSON.parse(gunzipSync(bytes))
  await fs.mkdir(path.dirname(source),{recursive:true});await fs.writeFile(source,bytes)
  await fs.copyFile(path.join(values.fixture,'context.json'),path.join(directory,'coordinates.json'))
  await fs.writeFile(path.join(directory,'room_description.json'),JSON.stringify({name_zh:name,shape,shape_zh:{single:'单格',l_shape:'L形'}[shape],display_name:name+'-'+shape,version_name:version,master:source,size:data.size,cells:[[0,0]],description_zh:'合成工具测试，不是建筑验收'}))
  if(withImage){
    const preview=path.join(directory,'previews');await fs.mkdir(preview)
    await fs.copyFile(path.join(values.fixture,'review/thumbnail_00.png'),path.join(preview,'overview.png'))
    await fs.writeFile(path.join(preview,'overview.json'),JSON.stringify({geometry_sha256:data.geometry_sha256}))
    await fs.copyFile(path.join(preview,'overview.png'),path.join(preview,'wrong_version.png'))
    await fs.writeFile(path.join(preview,'wrong_version.json'),JSON.stringify({geometry_sha256:'wrong'}))
  }
  sources.push({source,hash:createHash('sha256').update(bytes).digest('hex')});return source
}
const oldSource=await model('测试石砖厅','single','2026-11-01_draft01',fixture,true)
const source=await model('测试石砖厅','single','2026-11-02_draft02',revised,true)
const second=await model('第二测试厅','l_shape','v01',fixture)
for(let i=0;i<37;i++)await model('分页结构'+String(i).padStart(2,'0'),'single','v01')
const hidden=path.join(root,'bugged/hidden/master_geometry.json.gz');await fs.mkdir(path.dirname(hidden),{recursive:true});await fs.writeFile(hidden,fixture)
let app,browser
try{
  app=await startWorkbenchServer({workspace,python:values.python||'python',library:true})
  const base=new URL(app.url).origin
  const call=async(route,data)=>{const response=await fetch(base+'/api/library'+route,data?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)}:{});const value=await response.json();if(!response.ok)throw new Error(value.error);return value}
  let catalog=await call('');assert.equal(catalog.models.length,40);assert.ok(catalog.models.every(model=>model.size&&model.id&&model.relative_path&&!model.source.includes('bugged')));checks.catalog_metadata_and_hidden_directories=true
  const current=catalog.models.find(model=>model.source===source),other=catalog.models.find(model=>model.source===second)
  await Promise.all([call('/state',{collection:'favorites',id:current.id,enabled:true}),call('/state',{collection:'selected',id:other.id,enabled:true})])
  catalog=await call('');assert.deepEqual(catalog.state.favorites,[source]);assert.deepEqual(catalog.state.selected,[second]);checks.concurrent_updates_are_serialized=true
  assert.equal((await fetch(base+'/api/library/cover/not-a-model')).status,400)
  assert.equal((await fetch(base+'/api/library/state',{method:'POST',headers:{'Content-Type':'application/json',Origin:'https://example.com'},body:'{}'})).status,403);checks.unknown_ids_and_cross_origin_refused=true
  browser=await launchRenderBrowser()
  const context=await browser.newContext({viewport:{width:1600,height:1050},acceptDownloads:true}),page=await context.newPage(),errors=[]
  page.on('pageerror',error=>errors.push(error.message))
  await page.goto(app.url);await page.waitForFunction(()=>window.structureLibrary?.state.models.length===40)
  assert.equal(await page.locator('.structure-card').count(),36)
  await page.locator('#next-page').click();assert.equal(await page.locator('.structure-card').count(),3);checks.pagination_and_latest_version_grouping=true
  await page.locator('#library-search').fill('测试石砖厅');assert.equal(await page.locator('.structure-card').count(),1)
  await page.locator('#library-history').check();assert.equal(await page.locator('.structure-card').count(),2);checks.search_and_history=true
  await page.locator('#library-history').uncheck();await page.locator('.card-content').click()
  await page.waitForFunction(()=>document.querySelector('.detail-cover img')?.naturalWidth>0)
  assert.ok((await page.locator('#structure-detail').innerText()).includes('2026-11-02_draft02'))
  assert.ok((await page.locator('#structure-detail .detail-path').textContent()).includes(source))
  assert.equal(await page.locator('iframe').count(),0)
  assert.equal(await page.evaluate(()=>performance.getEntriesByType('resource').some(item=>item.name.includes('default-pack'))),false);checks.bound_covers_detail_and_no_webgl=true
  await page.screenshot({path:path.join(output,'selector-desktop.png')})
  await page.getByRole('checkbox',{name:'加入清单：测试石砖厅-single',exact:true}).check()
  await page.waitForFunction(()=>window.structureLibrary.state.selected.length===2&&!window.structureLibrary.state.busy)
  const downloaded=page.waitForEvent('download');await page.locator('#export-selection').click();const download=await downloaded;await download.saveAs(path.join(output,'selection.json'))
  const manifest=JSON.parse(await fs.readFile(path.join(output,'selection.json'),'utf8'));assert.equal(manifest.models.length,2);assert.ok(manifest.models.every(model=>model.geometry_sha256&&model.source&&model.context));checks.selection_export_contains_source_binding=true
  await page.reload();await page.waitForFunction(()=>window.structureLibrary?.state.selected.length===2)
  await page.locator('[data-collection=favorites]').click();assert.equal(await page.locator('.structure-card').count(),1);checks.favorites_and_selection_survive_reload=true
  await page.locator('[data-collection=all]').click();await page.locator('#shapes button').filter({hasText:'L形'}).click();assert.equal(await page.locator('.structure-card').count(),1)
  await page.locator('.card-content').click();assert.ok(await page.locator('.detail-cover .placeholder-label').textContent());checks.shape_filter_and_missing_image_fallback=true
  for(const size of [{width:390,height:844},{width:1000,height:800},{width:1920,height:1080}]){
    await page.setViewportSize(size);assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true)
  }
  await page.setViewportSize({width:390,height:844});await page.screenshot({path:path.join(output,'selector-mobile.png'),fullPage:true});checks.responsive_layout=true
  const dpi=await browser.newContext({viewport:{width:1440,height:1000},deviceScaleFactor:2}),dpiPage=await dpi.newPage();await dpiPage.goto(app.url);await dpiPage.waitForFunction(()=>window.structureLibrary?.state.models.length===40);assert.equal(await dpiPage.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);await dpi.close();checks.high_dpi_layout=true
  await page.setViewportSize({width:1600,height:1050});const popup=page.waitForEvent('popup');await page.locator('#choose-structure').click();const editor=await popup
  await editor.waitForFunction(expected=>window.detailControl?.state.info?.source===expected,second,{timeout:60000});assert.notEqual(new URL(editor.url()).origin,base);checks.independent_detail_console_opens_matching_model=true
  assert.equal(await editor.locator('#structure-library-dialog').count(),0);assert.equal(await editor.locator('#open-structure-library').count(),0);checks.original_editor_keeps_separate_interface=true
  assert.equal((await fetch(base+'/__detail__/init')).status,404);checks.workbench_does_not_expose_editor_api=true
  assert.deepEqual(errors,[]);checks.no_browser_errors=true
  await page.goto(app.url)
  const originalTime=await fs.stat(source);await fs.utimes(source,new Date(),new Date(Date.now()+5000))
  assert.equal((await fetch(base+'/api/library/cover/'+current.id)).status,400);await fs.utimes(source,originalTime.atime,originalTime.mtime);checks.changed_source_requires_refresh=true
  await fs.rm(second);const refreshed=await call('?refresh=1');assert.ok(!refreshed.models.some(model=>model.source===second));checks.refresh_discovers_removed_files=true
  for(const item of sources.filter(item=>item.source!==second))assert.equal(createHash('sha256').update(await fs.readFile(item.source)).digest('hex'),item.hash)
  checks.structure_bytes_unchanged=true
  await app.close();app=await startWorkbenchServer({workspace,python:values.python||'python',library:true})
  const restarted=await (await fetch(new URL('/api/library',app.url))).json();assert.ok(restarted.state.selected.includes(source)&&restarted.state.favorites.includes(source));checks.persistence_survives_service_restart=true
  await fs.writeFile(path.join(output,'results.json'),JSON.stringify({passed:true,checks},null,2))
  console.log(JSON.stringify({passed:true,checks:Object.keys(checks).length,output}))
}finally{await browser?.close();await app?.close()}
