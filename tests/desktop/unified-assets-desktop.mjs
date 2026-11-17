import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import path from 'node:path'
import http from 'node:http'
import {createHash} from 'node:crypto'
import {execFileSync} from 'node:child_process'
import {createRequire} from 'node:module'
import {root,skill,python} from '../../scripts/paths.mjs'
import {minimizedScreenshots} from '../support/minimized-screenshots.mjs'

const output=path.join(root,'build','unified-assets-'+Date.now())
const workspace=path.join(output,'workspace')
const modelDir=path.join(workspace,'nbt_models/single/test-hall/v1')
execFileSync(python,[path.join(root,'tests/support/make_fixture.py'),modelDir],{windowsHide:true})
const source=path.join(modelDir,'synthetic.master.json.gz')
const sha=raw=>createHash('sha256').update(raw).digest('hex')
const original=sha(await fs.readFile(source))
await fs.mkdir(path.join(workspace,'.nbtcreator'),{recursive:true})
await fs.writeFile(path.join(workspace,'.nbtcreator/preferences.json'),JSON.stringify({startPage:'project',autoPreview:false}))
execFileSync(python,['-B','-c',`import sys;sys.path.insert(0,sys.argv[1]);from nbt_components import store;store(sys.argv[2],dict(schema_version=1,name='本地白石方柱',size=[2,3,2],anchor=[1,0,1],palette=['quartz_block'],blocks=[[x,y,z,0,False] for x in range(2) for y in range(3) for z in range(2)]))`,path.join(skill,'scripts'),workspace],{windowsHide:true})

const encode=value=>Buffer.from(JSON.stringify(value))
let version='1.0.0',unavailable=false
const requested=[]
const recipe={schema_version:1,kind:'nbtcreator.parametric-recipe',arguments:{kind:'pillar',name:'外部可调方柱',size:[3,8,3],material:'stone_bricks',form:{section:'square',shaft_inset:0,base_height:1,capital_height:1}}}
function files(){
 const component={schema_version:1,name:'外部固定方柱',size:[3,4,3],anchor:[1,0,1],palette:[version==='1.0.0'?'gold_block':'diamond_block'],blocks:Array.from({length:36},(_,index)=>[index%3,Math.floor(index/9),Math.floor(index/3)%3,0,false])}
 const payloads={'/recipe.json':encode(recipe),'/component.json':encode(component)}
 const assets=Object.entries(payloads).map(([file,raw],index)=>({id:index?'fixed':'recipe',name:index?component.name:recipe.arguments.name,type:index?'component':'parametric_recipe',category:'验收构件',path:file.slice(1),bytes:raw.length,sha256:sha(raw)}))
 const manifest=encode({schema_version:1,kind:'nbtcreator.asset-library',id:'test.unified',name:'统一来源验收库',version,license:'CC0-1.0',assets})
 return {...payloads,'/library.json':manifest,'/registry.json':encode({schema_version:1,kind:'nbtcreator.asset-registry',libraries:[{id:'test.unified',name:'统一来源验收库',version,path:'library.json',manifest_sha256:sha(manifest)}]})}
}
const server=http.createServer((request,response)=>{
 requested.push(request.url)
 const body=files()[request.url]
 if(unavailable||!body){response.writeHead(404);response.end();return}
 response.writeHead(200,{'Content-Type':'application/json','Content-Length':body.length});response.end(body)
})
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve))
const require=createRequire(path.join(skill,'assets/viewer/package.json'))
const {_electron}=require('playwright')
let app,page
const checks={},errors=[],layouts=[]
const env={...process.env,NBTCREATOR_AUTOMATION:'1',OPENBLAS_NUM_THREADS:'1',OMP_NUM_THREADS:'1'};delete env.ELECTRON_RUN_AS_NODE
async function launch(folder,profile){
 app=await _electron.launch({executablePath:path.join(root,'node_modules/electron/dist/electron.exe'),args:[root,'--workspace',folder,'--user-data-dir',profile],env,timeout:60000})
 page=await app.firstWindow();page.setDefaultTimeout(75000);await minimizedScreenshots(app,page)
 page.on('pageerror',error=>errors.push(error.message))
 await page.waitForFunction(()=>window.detailControl?.state.catalogReady)
}
const click=selector=>page.locator(selector).click()
const idleSources=()=>page.waitForFunction(()=>document.querySelector('#asset-libraries').getAttribute('aria-busy')==='false')
const count=async()=>Number((await page.locator('#asset-count').textContent()).match(/\d+/)[0])
async function filter(sourceId,type='all'){
 await click('#asset-filters-menu>summary')
 await page.locator('#asset-source-filter').selectOption(sourceId)
 await page.locator('#asset-content-filter').selectOption(type)
 await page.keyboard.press('Escape')
}
async function sources(){
 await click('#asset-library-menu>summary');await click('#asset-libraries-open');await idleSources()
}
async function previewReady(){await page.waitForFunction(()=>document.querySelector('#asset-inspector-dialog').open&&!document.querySelector('#asset-copy-local').disabled)}
async function capture(name){
 await page.screenshot();await page.waitForTimeout(250)
 await page.screenshot({path:path.join(output,name+'.png')})
}
async function layout(name){
 const result=await page.evaluate(()=>{
  const issues=[],dialog=document.querySelector('#asset-inspector-dialog[open]')??document.querySelector('#asset-libraries[open]')
  if(document.documentElement.scrollWidth>innerWidth+1)issues.push('page horizontal overflow')
  if(dialog){
   const rect=dialog.getBoundingClientRect()
   if(rect.left<0||rect.top<0||rect.right>innerWidth+1||rect.bottom>innerHeight+1)issues.push('dialog outside viewport')
   if(dialog.scrollWidth>dialog.clientWidth+1)issues.push('dialog horizontal overflow')
   for(const selector of ['#asset-inspector-close','#asset-libraries-close']){
    const close=dialog.querySelector(selector)
    if(close?.getClientRects().length){const rect=close.getBoundingClientRect();if(rect.top<0||rect.left<0||rect.bottom>innerHeight||rect.right>innerWidth)issues.push('close button outside viewport')}
   }
  }
  return {issues,viewport:[innerWidth,innerHeight]}
 })
 layouts.push({name,...result});assert.deepEqual(result.issues,[],JSON.stringify({name,...result}))
}
try{
 await launch(workspace,path.join(output,'profile'))
 await page.setViewportSize({width:1440,height:900})
 await click('[data-workspace=assets]')
 await page.waitForFunction(()=>Number(document.getElementById('asset-workspace').dataset.catalogueCount)>120)
 assert.equal(await count(),122)
 assert.equal(await page.locator('.asset-kind-tabs button').count(),3)
 await page.waitForFunction(()=>[...document.querySelectorAll('#asset-grid img')].filter(image=>image.complete&&image.naturalWidth>0).length>=3)
 await capture('catalogue-all-sources')
 await filter('bundled')
 await page.locator('#asset-search').fill('ornate-window-gothic-gilded')
 await page.waitForFunction(()=>[...document.querySelectorAll('#asset-grid img')].some(image=>image.complete&&image.naturalWidth>0))
 await click('[data-source-id=bundled][data-asset-type=parametric_recipe][data-asset-ref="nbtcreator.modular/ornate-window-gothic-gilded"]')
 await previewReady()
 assert.equal(await page.locator('#asset-recipe-parameters').isVisible(),true)
 await page.locator('#asset-recipe-y').fill('30')
 assert.equal(await page.locator('#asset-copy-local').isDisabled(),true)
 await click('#asset-preview-refresh');await previewReady()
 assert.match(await page.locator('#asset-preview-status').textContent(),/23 × 30 × 5/)
 checks.bundled_browsing_real_thumbnails_and_parameter_preview_without_copy=true
 for(const [width,height,zoom]of [[1440,900,1],[900,650,1],[1440,900,1.25],[1440,900,1.5],[900,650,1.25],[900,650,1.5]]){
  await page.setViewportSize({width,height})
  await app.evaluate(({BrowserWindow},zoom)=>BrowserWindow.getAllWindows()[0].webContents.setZoomFactor(zoom),zoom)
  const name='recipe-'+width+'x'+height+'-'+zoom
  assert.ok(Math.abs((await app.evaluate(({BrowserWindow})=>BrowserWindow.getAllWindows()[0].webContents.getZoomFactor()))-zoom)<1e-6)
  await layout(name);await capture(name)
 }
 await page.setViewportSize({width:1440,height:900});await app.evaluate(({BrowserWindow})=>BrowserWindow.getAllWindows()[0].webContents.setZoomFactor(1))
 await click('#asset-inspector-close')
 await page.waitForFunction(()=>[...document.querySelectorAll('#asset-grid [data-asset-ref="nbtcreator.modular/ornate-window-gothic-gilded"]')].some(element=>element===document.activeElement))
 await sources()
 assert.equal(await page.locator('#asset-libraries-items').count(),0)
 await page.locator('#asset-libraries-source').fill(`http://127.0.0.1:${server.address().port}/registry.json`)
 await page.locator('#asset-libraries-form button[type=submit]').click();await idleSources()
 await click('#asset-libraries-discovery button');await idleSources()
 const sourceId=await page.locator('#asset-libraries-connections article[data-source-id]:not([data-source-id=bundled])').getAttribute('data-source-id')
 await capture('source-management')
 await click('#asset-libraries-close')
 assert.equal(await count(),2)
 assert.equal(await page.locator('#asset-source-filter').inputValue(),sourceId)
 await page.waitForFunction(()=>document.querySelectorAll('#asset-grid img').length===2&&[...document.querySelectorAll('#asset-grid img')].every(image=>image.complete&&image.naturalWidth>0))
 await capture('catalogue-connected-source')
 await filter('all');await page.locator('#asset-search').fill('方柱')
 const visibleSources=await page.locator('#asset-grid .asset-card').evaluateAll(cards=>[...new Set(cards.map(card=>card.dataset.sourceId))])
 assert.deepEqual(visibleSources.sort(),['local','bundled',sourceId].sort())
 await page.waitForFunction(()=>[...document.querySelectorAll('#asset-grid img')].filter(image=>image.complete&&image.naturalWidth>0).length===document.querySelectorAll('#asset-grid .asset-card').length)
 await capture('catalogue-all-three-origins')
 await filter(sourceId);await page.locator('#asset-search').fill('')
 assert.equal((await fs.readdir(path.join(workspace,'.nbtcreator/components'))).filter(name=>/^[a-f0-9]{32}\.json$/.test(name)).length,1)
 checks.source_management_connects_into_main_catalogue_without_import=true
 await click(`[data-source-id="${sourceId}"][data-asset-type=parametric_recipe]`);await previewReady()
 await page.locator('#asset-recipe-y').fill('10');await click('#asset-preview-refresh');await previewReady()
 await click('#asset-copy-local')
 await page.waitForFunction(()=>document.getElementById('asset-edit-name')===document.activeElement)
 await page.locator('#asset-edit-name').fill('我的可编辑细柱');await click('#asset-update')
 await page.waitForFunction(()=>document.getElementById('asset-detail-status').textContent.includes('名称与标签已保存'))
 await click('#asset-inspector-close')
 assert.equal(await count(),2)
 checks.explicit_copy_creates_an_editable_local_pending_asset=true
 await filter(sourceId,'component')
 await click(`[data-source-id="${sourceId}"][data-asset-type=component]`);await previewReady()
 await click('#asset-choose-building')
 await page.waitForSelector('.library-target-request:not([hidden])')
 await click('#project-grid .project-card-edit')
 await page.waitForSelector('#asset-inspector-dialog[open]');await previewReady()
 for(const [axis,value]of [['x',16],['y',4],['z',16]])await page.locator('#asset-position-'+axis).fill(String(value))
 await capture('direct-placement')
 await click('#asset-place')
 await page.waitForFunction(()=>document.body.dataset.workspace==='model'&&window.detailControl.state.preview&&!window.detailControl.state.commitBusy)
 assert.equal(sha(await fs.readFile(source)),original)
 assert.equal((await fs.readdir(path.join(workspace,'.nbtcreator/components'))).filter(name=>/^[a-f0-9]{32}\.json$/.test(name)).length,2)
 checks.connected_component_places_directly_as_candidate_without_import=true
 await click('[data-workspace=assets]');await filter(sourceId,'component')
 await click(`[data-source-id="${sourceId}"][data-asset-type=component]`);await previewReady()
 for(const [axis,value]of [['x',20],['y',4],['z',20]])await page.locator('#asset-position-'+axis).fill(String(value))
 await click('#asset-detail .placement-methods>summary');await click('#asset-adjust-3d')
 await page.waitForSelector('#component-editor:not([hidden])')
 const previousPreview=await page.evaluate(()=>JSON.stringify(window.detailControl.state.preview))
 await click('#component-transform-apply')
 await page.waitForFunction(previous=>document.getElementById('component-editor').hidden&&!window.detailControl.state.commitBusy&&JSON.stringify(window.detailControl.state.preview)!==previous,previousPreview)
 assert.equal(sha(await fs.readFile(source)),original)
 checks.connected_component_uses_the_existing_3d_handle_path=true
 await click('[data-workspace=assets]');await filter(sourceId)
 version='1.1.0';await sources()
 await page.locator(`[data-source-id="${sourceId}"] button[data-source-action=refresh]`).click();await idleSources()
 assert.match(await page.locator(`#asset-libraries-connections article[data-source-id="${sourceId}"]`).textContent(),/1\.1\.0/)
 const requestsBeforeRollback=requested.length
 await page.locator(`[data-source-id="${sourceId}"] button[data-source-action=rollback]`).click();await idleSources()
 assert.match(await page.locator(`#asset-libraries-connections article[data-source-id="${sourceId}"]`).textContent(),/1\.0\.0/)
 assert.equal(requested.length,requestsBeforeRollback)
 unavailable=true
 await page.locator(`[data-source-id="${sourceId}"] button[data-source-action=refresh]`).click();await idleSources()
 assert.match(await page.locator('#asset-libraries-status').textContent(),/不可用/)
 await click('#asset-libraries-close')
 assert.equal(await count(),2)
 const requestsOffline=requested.length
 await click(`[data-source-id="${sourceId}"][data-asset-type=component]`);await previewReady();await click('#asset-inspector-close')
 assert.equal(requested.length,requestsOffline)
 checks.refresh_rollback_and_failed_refresh_preserve_offline_use=true
 await sources();await page.locator(`[data-source-id="${sourceId}"] button[data-source-action=enable]`).click();await idleSources();await click('#asset-libraries-close')
 assert.equal(await count(),0)
 await filter('local');assert.equal(await count(),2)
 await sources();await page.locator(`[data-source-id="${sourceId}"] button[data-source-action=enable]`).click();await idleSources();await click('#asset-libraries-close')
 await filter(sourceId);assert.equal(await count(),2)
 await sources();await page.locator(`[data-source-id="${sourceId}"] button[data-source-action=remove]`).click();await idleSources();await click('#asset-libraries-close')
 await filter('local');assert.equal(await count(),2)
 checks.disable_remove_restore_keep_local_copies=true
 assert.equal(sha(await fs.readFile(source)),original)
 assert.deepEqual(errors,[])
 await app.close();app=null
 const second=path.join(output,'second-workspace');await fs.mkdir(second)
 await launch(second,path.join(output,'second-profile'));await click('[data-workspace=assets]')
 await page.waitForFunction(()=>Number(document.getElementById('asset-workspace').dataset.catalogueCount)===121)
 assert.equal(await page.locator('#asset-source-filter option').count(),3)
 checks.workspace_connections_and_local_copies_are_isolated=true
 await fs.writeFile(path.join(output,'results.json'),JSON.stringify({passed:true,checks,layouts,errors,output},null,2))
 console.log(JSON.stringify({passed:true,checks,layouts:layouts.length,output}))
}catch(error){
 console.error(JSON.stringify({output,checks,errors}))
 await capture('failure').catch(()=>{})
 if(page)console.error(await page.locator('#asset-detail-status').textContent().catch(()=>''),await page.locator('#asset-preview-status').textContent().catch(()=>''))
 throw error
}finally{await app?.close();await new Promise(resolve=>server.close(resolve))}
