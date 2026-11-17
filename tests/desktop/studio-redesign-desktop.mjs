import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import path from 'node:path'
import {spawnSync} from 'node:child_process'
import {createHash} from 'node:crypto'
import {createRequire} from 'node:module'
import {root,skill,python} from '../../scripts/paths.mjs'
import {minimizedScreenshots} from '../support/minimized-screenshots.mjs'

const require=createRequire(path.join(skill,'assets/viewer/package.json')),{_electron}=require('playwright')
const output=path.join(root,'build','studio-redesign-'+Date.now()),workspace=path.join(output,'workspace'),checks={},errors=[],layouts=[],captures=[]
await fs.mkdir(path.join(workspace,'.nbtcreator'),{recursive:true})
await fs.writeFile(path.join(workspace,'.nbtcreator/preferences.json'),JSON.stringify({startPage:'project',autoPreview:false}))
let app,page
const run=(args)=>{const result=spawnSync(python,args,{encoding:'utf8',windowsHide:true});assert.equal(result.status,0,result.stdout+result.stderr);return result.stdout}
const click=selector=>page.locator(selector).first().click()
const idle=()=>page.waitForFunction(()=>!window.detailControl.state.busy&&!window.detailControl.state.previewBusy&&!window.detailControl.state.commitBusy&&!window.detailControl.state.sessionRestoring)
const go=async panel=>{await click('[data-studio-view='+ (panel==='checks'?'inspect':'prepare') +']');if(panel!=='checks')await click('#studio-panel-'+panel)}
async function capture(name){await page.screenshot({path:path.join(output,name+'.png')});captures.push({name,...await page.evaluate(()=>({workspace:document.body.dataset.workspace,view:document.getElementById('studio-workspace').dataset.view,viewport:[innerWidth,innerHeight],title:document.getElementById('studio-object-meta').textContent}))})}
async function layout(name){const result=await page.evaluate(()=>{
 const issues=[],visible=e=>!!e.getClientRects().length&&!e.closest('[hidden]')
 if(document.documentElement.scrollWidth>innerWidth+1)issues.push('horizontal overflow')
 const selectors=['.creator-header','[data-studio-view]','.studio-primary-actions>.primary','#settings-save','#setting-open-ai','#close-settings','#close-prompt']
 for(const selector of selectors)for(const e of document.querySelectorAll(selector))if(visible(e)){const r=e.getBoundingClientRect();if(r.left<0||r.right>innerWidth+1||r.top<0||r.bottom>innerHeight+1)issues.push('offscreen '+(e.id||selector))}
 const frame=document.getElementById('prompt-frame');if(document.body.dataset.workspace==='prompt'&&frame.contentDocument){const d=frame.contentDocument;if(d.documentElement.scrollWidth>frame.contentWindow.innerWidth+1)issues.push('prompt horizontal overflow');const e=d.getElementById('left-save'),r=e.getBoundingClientRect();if(visible(e)&&r.bottom>frame.clientHeight+1)issues.push('prompt main action offscreen')}
 return {issues,width:innerWidth,height:innerHeight,canvas:document.querySelector('.canvas-wrap').getBoundingClientRect().toJSON()}
 });layouts.push({name,...result});assert.deepEqual(result.issues,[],JSON.stringify({name,...result}))}
try{
 const env={...process.env,NBTCREATOR_AUTOMATION:'1',OPENBLAS_NUM_THREADS:'1',OMP_NUM_THREADS:'1'};delete env.ELECTRON_RUN_AS_NODE
 app=await _electron.launch({executablePath:path.join(root,'node_modules/electron/dist/electron.exe'),args:[root,'--workspace',workspace,'--user-data-dir',path.join(output,'profile')],env,timeout:60000})
 page=await app.firstWindow();page.setDefaultTimeout(45000);await minimizedScreenshots(app,page);page.on('pageerror',e=>errors.push(e.message))
 await page.waitForFunction(()=>window.detailControl?.state.catalogReady&&!window.detailControl.state.busy)
 await page.setViewportSize({width:1440,height:900});await capture('empty-library')
 await click('.project-empty button');const f=page.frameLocator('#prompt-frame')
 await page.waitForFunction(()=>document.querySelector('#prompt-frame').contentDocument?.body.dataset.promptReady==='true')
 await f.locator('#prompt-write-manually').click();await f.locator('[data-field=name]').fill('山城工坊 · 手写方案')
 await page.waitForFunction(()=>document.querySelector('#prompt-frame').contentDocument.getElementById('prompt-editor-save-state').textContent==='已自动保存')
 const promptBefore=await f.locator('[data-field=name]').inputValue();await click('#studio-ai-settings');await click('#close-api');assert.equal(await f.locator('[data-field=name]').inputValue(),promptBefore)
 await capture('planning');await f.locator('#left-save').click();await page.waitForFunction(()=>!document.querySelector('#prompt-frame').contentDocument.getElementById('prompt-task-handoff').hidden)
 assert.match(await f.locator('#prompt-task-state').textContent(),/已交接/);await capture('handoff');await click('#close-prompt');await page.waitForFunction(()=>document.body.dataset.workspace==='project')
 checks.empty_library_manual_document_handoff_and_return=true

 const folder=path.join(workspace,'nbt_models/single/山城工坊/v1');run([path.join(root,'tests/support/make_fixture.py'),folder])
 run(['-c',`import sys;sys.path.insert(0,sys.argv[1]);from nbt_components import store;store(sys.argv[2],dict(schema_version=1,name='工坊石柱',tags=['柱'],size=[1,4,1],anchor=[0,0,0],palette=['gold_block'],blocks=[[0,y,0,0,False] for y in range(4)]))`,path.join(skill,'scripts'),workspace])
 await click('#project-library-menu>summary');await click('#project-refresh');await page.waitForSelector('.project-card-open')
 await click('#project-library-menu>summary');await click('#project-generate-thumbnails');await page.waitForSelector('.project-cover img');await capture('library')
 await click('.project-card-open');await click('#project-preview-edit');await idle();await page.waitForFunction(()=>document.querySelector('#viewer').contentWindow?.nbtModeler?.status==='ready')
 const source=path.join(folder,'synthetic.master.json.gz'),hash=b=>createHash('sha256').update(b).digest('hex'),original=hash(await fs.readFile(source))
 await click('#pick-material');assert.match(await page.locator('#studio-canvas-mode').textContent(),/方块取材/)
 const samplePoint=await page.evaluate(()=>{const v=document.querySelector('#viewer').contentWindow.nbtModeler;for(const y of [0,.2,-.2,.4,-.4])for(const x of [0,.2,-.2,.4,-.4])if(v.pickBlock(x,y))return {x,y}});assert.ok(samplePoint);const sampleCanvas=await page.frameLocator('#viewer').locator('#preview').boundingBox();await page.mouse.click(sampleCanvas.x+(samplePoint.x+1)*sampleCanvas.width/2,sampleCanvas.y+(1-samplePoint.y)*sampleCanvas.height/2);await page.waitForFunction(()=>window.detailControl.state.pickedMaterial);assert.match(await page.locator('#picked-material-label').textContent(),/坐标/)
 await page.locator('#pick-material').press('Escape');assert.equal(await page.locator('#studio-canvas-mode').isVisible(),false);assert.equal(await page.evaluate(()=>document.activeElement.id),'pick-material')
 await click('#pick-coordinate');await page.locator('#feedback-text').fill('尚未保存的修改意见');await page.locator('#feedback-text').press('Escape');assert.equal(await page.evaluate(()=>document.activeElement.id),'pick-coordinate');await go('tools')
 checks.canvas_modes_escape_and_focus=true
 await click('[data-workspace=assets]');await page.waitForSelector('.asset-card');await click('.asset-card');for(const [axis,value]of [['x',16],['y',4],['z',16]])await page.locator('#asset-position-'+axis).fill(String(value))
 await click('#asset-detail .placement-methods>summary');await click('#asset-adjust-3d');await page.waitForFunction(()=>window.detailControl.state.transforming);assert.equal(await page.locator('#studio-inspector #component-editor').count(),1);await page.locator('#component-transform-x').press('Escape');await page.waitForFunction(()=>!window.detailControl.state.transforming);assert.equal(await page.evaluate(()=>window.detailControl.gather().operations.length),0)
 await click('[data-workspace=assets]');await click('.asset-card');for(const [axis,value]of [['x',16],['y',4],['z',16]])await page.locator('#asset-position-'+axis).fill(String(value));await click('#asset-place');await idle();await page.waitForFunction(()=>window.detailControl.state.preview)
 await capture('editor');assert.match(await page.locator('#studio-object-scope').textContent(),/构件实例/)
 await go('notes');await page.locator('#feedback-text').fill('候选画面的修改意见草稿');await go('tools')
 const pose=await page.evaluate(()=>document.querySelector('#viewer').contentWindow.nbtModeler.metadata())
 await go('checks');await go('tools');const returned=await page.evaluate(()=>document.querySelector('#viewer').contentWindow.nbtModeler.metadata());assert.deepEqual(returned.camera,pose.camera);assert.deepEqual(returned.cuts,pose.cuts);assert.equal(await page.locator('#feedback-text').inputValue(),'候选画面的修改意见草稿')
 checks.instance_inspector_cancel_and_shared_view_preserve_state=true
 await click('#studio-tool-menu>summary');await click('#tool-tabs [data-tool-index="4"]');await click('#studio-edit-scope');await page.locator('#budget').fill('0');assert.equal(await page.locator('#journey-title').textContent(),'参数需要调整');assert.equal(await page.locator('#export-revision').isDisabled(),true);await capture('invalid-parameter');await page.locator('#budget').fill('4096')
 // Change a real parameter, fail once, then recover through the same controls.
 await page.locator('#budget').fill('4095');assert.match(await page.locator('#studio-object-meta').textContent(),/旧候选/);assert.equal(await page.locator('#save-authoring-version').isDisabled(),true)
 await page.route('**/__detail__/jobs',route=>route.request().method()==='POST'&&route.request().postDataJSON()?.kind==='preview'?route.fulfill({status:400,contentType:'application/json',body:JSON.stringify({error:'专项回归：候选计算失败'})}):route.continue())
 await click('#update-preview');await page.waitForFunction(()=>document.getElementById('status').textContent.includes('专项回归'));await idle();await capture('preview-failure');await page.unroute('**/__detail__/jobs');await click('#update-preview');await idle();await page.waitForFunction(()=>window.detailControl.state.previewSettings===JSON.stringify(window.detailControl.gather()))
 await go('checks');await click('#open-version-compare');await page.locator('#version-compare-kind').selectOption('candidate');await click('#start-version-compare');await page.waitForFunction(()=>window.detailControl.state.versionComparing);await page.frameLocator('#viewer').locator('#preview').press('Escape');await page.waitForFunction(()=>!window.detailControl.state.versionComparing);assert.equal(await page.locator('#studio-canvas-mode').isVisible(),false);checks.readonly_compare_escape_restores_editor=true
 await click('#validate-preview');await idle();assert.equal(await page.evaluate(()=>window.detailControl.state.candidateValidation.passed),true);await capture('checks-delivery')
 await page.route('**/__detail__/jobs',route=>route.request().method()==='POST'&&route.request().postDataJSON()?.kind==='revision'?route.fulfill({status:400,contentType:'application/json',body:JSON.stringify({error:'专项回归：保存失败'})}):route.continue());await click('#save-authoring-version');await page.waitForFunction(()=>document.getElementById('status').textContent.includes('制作版未保存'));assert.equal(await page.evaluate(()=>document.body.dataset.workspace),'model');assert.equal(await page.evaluate(()=>document.activeElement.id),'save-authoring-version');await page.unroute('**/__detail__/jobs')
 await click('#save-authoring-version');await idle();assert.equal(await page.locator('#journey-title').textContent(),'制作版已保存');assert.equal(hash(await fs.readFile(source)),original);await click('#journey-action');await page.waitForFunction(source=>window.detailControl.state.info.source!==source,source);await idle();assert.notEqual(await page.evaluate(()=>window.detailControl.state.info.source),source);assert.match(await page.locator('#studio-object-meta').textContent(),/^v\d+ ·/)
 await click('#update-preview');await idle();await go('checks');await click('#export-revision');await idle();assert.equal(await page.locator('#journey-title').textContent(),'NBT 已导出')
 const receipt=await page.evaluate(async()=>(await(await fetch('/__detail__/jobs')).json()).findLast(j=>j.kind==='revision'&&!j.result?.draft_only).result)
 run(['-c',`import sys;sys.path.insert(0,sys.argv[1]);from nbt_refine import read_master;a,_=read_master(sys.argv[2]);b,_=read_master(sys.argv[3]);assert a.fingerprint()==b.fingerprint()`,path.join(skill,'scripts'),receipt.master,receipt.runtime_files[0]])
 assert.equal(hash(await fs.readFile(source)),original);checks.stale_invalid_failed_candidate_and_real_draft_export_roundtrip=true
 await click('[data-workspace=tasks]');await page.waitForSelector('.task-entry');await capture('records');await click('.task-details-button');await capture('record-detail');await click('#task-detail-close')
 await click('#open-settings');await click('[data-settings-tab=general]');await capture('settings');await click('[data-settings-tab=ai]');assert.match(await page.locator('[data-settings-page=ai]').textContent(),/加密/);await click('#close-settings')
 checks.object_action_result_and_scoped_settings=true

 for(const [width,height,zoom]of [[1440,900,1],[900,650,1],[1440,900,1.25],[1440,900,1.5],[900,650,1.25],[900,650,1.5]]){
  await page.setViewportSize({width,height});await app.evaluate(({BrowserWindow},zoom)=>BrowserWindow.getAllWindows()[0].webContents.setZoomFactor(zoom),zoom)
  for(const destination of ['project','assets','model','prompt','tasks']){await click('[data-workspace='+destination+']');if(destination==='prompt')await page.waitForFunction(()=>document.querySelector('#prompt-frame').contentDocument?.body.dataset.promptReady==='true');await layout(destination+'-'+width+'-'+zoom)}
  if(width===900&&zoom>1){await click('[data-workspace=model]');await go('tools');await click('#studio-tool-menu>summary');await click('#tool-tabs [data-tool-index="0"]');await page.locator('#strength').scrollIntoViewIfNeeded();const reachable=await page.locator('#strength').evaluate(e=>{const r=e.getBoundingClientRect(),p=document.getElementById('studio-inspector').getBoundingClientRect();return r.top>=p.top&&r.bottom<=p.bottom&&r.bottom<=innerHeight});assert.equal(reachable,true,'tool input must remain reachable in a short inspector');await go('checks')}
  await click('[data-workspace=model]');await click('#open-settings');await layout('settings-'+width+'-'+zoom);if(zoom===1.5)await capture('settings-'+width+'-150');await click('#close-settings');if(zoom===1.5)await capture('editor-'+width+'-150')
 }
 checks.window_and_zoom_matrix=true
 await page.setViewportSize({width:1440,height:900});await app.evaluate(({BrowserWindow})=>BrowserWindow.getAllWindows()[0].webContents.setZoomFactor(1))
 for(const theme of ['blue','green','violet','sand','graphite']){await click('#open-settings');await click('[data-settings-tab=general]');await page.locator('#setting-color-scheme').selectOption(theme);await click('#settings-save');await page.waitForFunction(theme=>document.documentElement.dataset.colorScheme===theme,theme);await click('#close-settings');await capture('theme-'+theme)}
 assert.deepEqual(errors,[]);await fs.writeFile(path.join(output,'results.json'),JSON.stringify({passed:true,checks,layouts,captures,errors,fixture_only:true,actual_user_usability_feedback:false},null,2));console.log(JSON.stringify({passed:true,checks,layouts:layouts.length,output}))
}catch(error){console.error(JSON.stringify({output,checks,errors}));await capture('failure').catch(()=>{});throw error}finally{await app?.close()}
