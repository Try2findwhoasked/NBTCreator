import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import path from 'node:path'
import {spawnSync} from 'node:child_process'
import {createHash} from 'node:crypto'
import {createRequire} from 'node:module'
import {root,skill,python} from '../scripts/paths.mjs'
const require=createRequire(path.join(skill,'assets/viewer/package.json'))
const {_electron}=require('playwright')
const output=path.join(root,'build','desktop-'+Date.now());await fs.mkdir(output,{recursive:true})
const workspace=path.join(output,'workspace'),modelDir=path.join(workspace,'nbt_models/sample')
const fixture=spawnSync(python,[path.join(root,'tests/make_fixture.py'),modelDir],{encoding:'utf8',windowsHide:true});assert.equal(fixture.status,0,fixture.stderr)
const source=path.join(modelDir,'synthetic.master.json.gz'),hash=bytes=>createHash('sha256').update(bytes).digest('hex'),original=hash(await fs.readFile(source))
const executable=process.env.NBTCREATOR_TEST_EXE||path.join(root,'node_modules/electron/dist/electron.exe')
const env={...process.env,NBTCREATOR_AUTOMATION:'1'};delete env.ELECTRON_RUN_AS_NODE
const args=[...(process.env.NBTCREATOR_TEST_EXE?[]:[root]),'--workspace',workspace,'--user-data-dir',path.join(output,'profile')]
let app;const checks={}
try{
 app=await _electron.launch({executablePath:executable,args,env,timeout:60000})
 app.process().stdout?.on('data',data=>fs.appendFile(path.join(output,'electron.log'),data))
 app.process().stderr?.on('data',data=>fs.appendFile(path.join(output,'electron.log'),data))
 const page=await app.firstWindow({timeout:30000}),errors=[];page.on('pageerror',e=>{errors.push(e.message);console.error('renderer:',e.message)})
 page.on('console',msg=>{if(msg.type()==='error')console.error('console:',msg.text())})
 const diagnostic=setTimeout(async()=>{
  try{const info=await page.evaluate(()=>({url:location.href,title:document.title,body:document.body?.innerText.slice(0,3000),control:typeof window.detailControl,scripts:[...document.scripts].map(s=>s.src)}));await fs.writeFile(path.join(output,'startup.json'),JSON.stringify(info,null,2));await page.screenshot({path:path.join(output,'startup.png')});console.log(JSON.stringify({startup:info}))}catch{}
 },10000)
 await page.waitForFunction(()=>window.detailControl?.state.info&&!window.detailControl.state.busy,undefined,{timeout:60000})
 clearTimeout(diagnostic)
 assert.equal(await page.locator('#desktop-source').count(),1);assert.ok((await page.locator('#desktop-workspace-label').textContent()).includes(workspace));checks.native_bridge_and_workspace=true
 assert.equal((await page.evaluate(()=>window.nbtDesktop.info())).frontend,'production');assert.equal(await page.evaluate(()=>performance.getEntriesByType('resource').some(r=>r.name.includes('/@vite/')||r.name.includes('/src/control.js'))),false);checks.production_frontend_without_dev_client=true
 const prefs=await app.evaluate(({BrowserWindow})=>{const p=BrowserWindow.getAllWindows()[0].webContents.getLastWebPreferences();return {sandbox:p.sandbox,contextIsolation:p.contextIsolation,nodeIntegration:p.nodeIntegration}})
 assert.deepEqual(prefs,{sandbox:true,contextIsolation:true,nodeIntegration:false});checks.renderer_isolation=true
 assert.deepEqual(await page.locator('.creator-workspaces button').evaluateAll(items=>items.map(e=>e.dataset.workspace)),['prompt','model','ai','tasks'])
 assert.equal(await app.evaluate(({BrowserWindow})=>BrowserWindow.getAllWindows()[0].isMenuBarVisible()),false)
 assert.equal(await page.locator('.native-menu-triggers button').count(),2);checks.native_menu_in_single_header=true
 const bridge=await page.evaluate(()=>Object.keys(window.nbtDesktop).sort());assert.deepEqual(bridge,['apiCancel','apiConfig','apiGenerate','apiModels','apiSave','appSettings','appSettingsSave','chooseSource','chooseWorkspace','copyAgentPlan','exposureConfig','exposureImport','exposureSave','info','internalAIConfig','internalAIImport','internalAISave','knowledgePreview','settingsOpenFolder','systemMenu','updateAccess','updateAccessSave','updateCheck','updateDownload','updateFolder','updateStatus']);assert.equal(await page.evaluate(()=>typeof window.require),'undefined')
 await page.locator('#open-settings').click();assert.equal(await page.locator('#app-settings-dialog').isVisible(),true);await page.locator('[data-settings-tab=about]').click();assert.ok((await page.locator('#settings-about').textContent()).includes('Electron'));await page.locator('[data-settings-tab=general]').click();await page.locator('[data-settings-tab=preview]').click();await page.locator('#setting-preview-delay').fill('900');await page.locator('#setting-auto-preview').uncheck();await page.locator('#settings-save').click();await page.waitForFunction(()=>document.querySelector('#settings-status').textContent.includes('配置已保存'));assert.equal(await page.locator('#auto-preview').isChecked(),false);await page.screenshot({path:path.join(output,'settings.png')});await app.evaluate(({ipcMain})=>{ipcMain.removeHandler('nbt:update-check');ipcMain.handle('nbt:update-check',()=>({current:'1.9.0',latest:'v9.0.0',available:true,notes:'测试发行说明',assets:['app-update','portable']}))});await page.locator('[data-settings-tab=updates]').click();await page.locator('#update-check').click();await page.waitForFunction(()=>document.querySelector('#settings-status').textContent.includes('发现 v9.0.0'));assert.equal(await page.locator('#update-download').isDisabled(),false);await page.screenshot({path:path.join(output,'settings-updates.png')});await page.locator('[data-settings-tab=storage]').click();assert.ok((await page.locator('#settings-storage-paths').textContent()).includes(workspace));assert.ok((await page.locator('#settings-skill-entry').textContent()).includes('.agents'));await page.locator('#settings-skill-copy').click();await page.waitForFunction(()=>document.querySelector('#settings-status').textContent.includes('已复制'));await page.screenshot({path:path.join(output,'settings-storage.png')});await page.locator('#close-settings').click();assert.equal(JSON.parse(await fs.readFile(path.join(workspace,'.nbtcreator/preferences.json'),'utf8')).previewDelay,900);checks.app_settings_about_and_live_preferences=true
 await page.locator('#auto-preview').uncheck()
 await page.locator('#enable-3d').click();await page.waitForFunction(()=>window.detailControl.state.feedbackTarget?.kind==='3d'&&!window.detailControl.state.busy,undefined,{timeout:60000});checks.electron_webgl_and_python_snapshot=true
 await page.locator('#pick-coordinate').click()
 const orbitBox=await page.frameLocator('#viewer').locator('#preview').boundingBox(),cameraBefore=await page.evaluate(()=>JSON.stringify(document.querySelector('#viewer').contentWindow.nbtModeler.metadata().camera))
 await page.mouse.move(orbitBox.x+orbitBox.width*.5,orbitBox.y+orbitBox.height*.5);await page.mouse.down();await page.mouse.move(orbitBox.x+orbitBox.width*.5+75,orbitBox.y+orbitBox.height*.5+25,{steps:8});await page.mouse.up()
 assert.notEqual(await page.evaluate(()=>JSON.stringify(document.querySelector('#viewer').contentWindow.nbtModeler.metadata().camera)),cameraBefore);assert.equal(await page.evaluate(()=>window.detailControl.state.draftPoints.length),0);checks.left_drag_orbits_while_picking_without_marking=true

 const point=await page.evaluate(()=>{const v=document.querySelector('#viewer').contentWindow.nbtModeler;for(const y of [0,.2,-.2,.4,-.4])for(const x of [0,.2,-.2,.4,-.4])if(v.pickBlock(x,y))return {x,y}});assert.ok(point)
 const box=await page.frameLocator('#viewer').locator('#preview').boundingBox();await page.mouse.click(box.x+(point.x+1)*box.width/2,box.y+(1-point.y)*box.height/2)
 await page.waitForFunction(()=>window.detailControl.state.draftPoints.length===1)
 await page.locator('#feedback-text').fill('#1 SYNTHETIC desktop migration note');await page.locator('#save-feedback').click();await page.waitForFunction(()=>window.detailControl.state.notes.length===1);checks.coordinate_feedback_saved=true
 await page.locator('#comment-search').fill('不存在的评论');assert.equal(await page.locator('.feedback-note').count(),0);await page.locator('#comment-search').fill('');assert.equal(await page.locator('.feedback-note').count(),1);await page.locator('#feedback-text').fill('SYNTHETIC keyboard comment');await page.locator('#feedback-text').press('Control+Enter');await page.waitForFunction(()=>window.detailControl.state.notes.length===2);assert.equal(await page.locator('#comment-length').textContent(),'0 / 4000');checks.comment_search_and_keyboard_save=true;await page.screenshot({path:path.join(output,'model-comments.png')})
 assert.ok(await page.locator('.comment-thread #draft-markers').count());assert.ok(await page.locator('.comment-thread #comment-compose-hint').count());const heading=await page.locator('.comment-heading').evaluate(e=>{const a=e.querySelector('h2').getBoundingClientRect(),b=e.querySelector('#feedback-context').getBoundingClientRect();return Math.abs((a.top+a.bottom)/2-(b.top+b.bottom)/2)<3});assert.equal(heading,true);checks.single_line_comment_heading_and_right_markers=true
 await page.locator('#review-help-open').click();assert.equal(await page.locator('#review-help-dialog').isVisible(),true);assert.ok((await page.locator('#review-help-dialog').textContent()).includes('普通手动调参'));assert.ok((await page.locator('#review-help-dialog').textContent()).includes('approval.json'));await page.locator('#review-help-close').click();checks.advanced_refinement_help=true
 await page.locator('#pick-coordinate').click()
 await page.locator('#tool-tabs button').nth(1).click();await page.locator('#pattern-enabled').check();await page.locator('#pattern-fraction').fill('12')
 await page.locator('#plan').click();await page.waitForFunction(()=>!window.detailControl.state.busy&&Boolean(window.detailControl.state.agentText),undefined,{timeout:60000})
 const handoff=await page.evaluate(()=>({text:window.detailControl.state.agentText,bundle:window.detailControl.state.bundle,source:window.detailControl.state.info.source}))
 assert.ok(handoff.bundle.includes('Agent交接'));assert.ok(handoff.text.includes('源建筑所属工作文件夹'));assert.equal(await fs.readFile(path.join(path.dirname(handoff.bundle),'交给Agent.md'),'utf8'),handoff.text)
 const sharedRequest=JSON.parse(await fs.readFile(path.join(path.dirname(handoff.bundle),'request.json'),'utf8'));assert.equal(sharedRequest.path_base,'workspace');assert.equal(hash(await fs.readFile(source)),original)
 await page.locator('#copy-agent-plan').click();await page.waitForFunction(()=>document.querySelector('#status').textContent.startsWith('已复制'),undefined,{timeout:10000});assert.equal(await app.evaluate(({clipboard})=>clipboard.readText()),handoff.text);checks.agent_handoff_saved_and_copied=true
 assert.equal(await page.locator('#advanced-review').evaluate(e=>e.open),false);await page.locator('#advanced-review').evaluate(e=>e.open=true);await page.locator('#prepare').click();await page.waitForFunction(()=>!window.detailControl.state.busy&&Boolean(document.querySelector('#review').value),undefined,{timeout:60000})
 const review=await page.locator('#review').inputValue();assert.equal(path.dirname(review),path.join(path.dirname(path.dirname(handoff.bundle))))
 await assert.rejects(fs.access(path.join(review,'approval.json')))
 const associated=await page.evaluate(async source=>(await(await fetch('/__detail__/inspect',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({source})})).json()),source)
 assert.equal(associated.agent_handoff.review,review);assert.equal(await page.locator('#advanced-review').evaluate(e=>e.open),true);await page.locator('#advanced-review').evaluate(e=>e.open=false);checks.shared_review_auto_association_without_fake_approval=true
 await page.locator('#update-preview').click();await page.waitForFunction(()=>window.detailControl.state.comparisonSide==='after'&&!window.detailControl.state.previewBusy,undefined,{timeout:90000});checks.parameter_effect_preview=true
 await page.locator('#export-revision').click();await page.waitForFunction(()=>!window.detailControl.state.busy&&document.querySelector('#status').textContent.includes('下一版建筑已保存'),undefined,{timeout:90000})
 const links=await page.locator('#result-links a').allTextContents();assert.ok(links.some(n=>n.endsWith('.nbt')));assert.equal(hash(await fs.readFile(source)),original);checks.explicit_export_new_version_preserves_original=true
 await page.locator('button[data-workspace=prompt]').click();await page.waitForFunction(()=>document.querySelector('#prompt-frame').contentWindow.NbtPromptUI);await page.locator('#sync-prompt').click();await page.waitForFunction(()=>document.querySelector('#prompt-sync-status').textContent.startsWith('已载入'),undefined,{timeout:30000})
 assert.ok((await page.frameLocator('#prompt-frame').locator('#result').inputValue()).includes(source));await page.locator('#close-prompt').click();checks.prompt_console_reused=true
 await page.screenshot({path:path.join(output,'desktop.png')})
 const cli=spawnSync(process.execPath,[path.join(root,'scripts/cli.mjs'),'inspect','--source',source],{encoding:'utf8',windowsHide:true});assert.equal(cli.status,0,cli.stderr);assert.equal(JSON.parse(cli.stdout).source_sha256,original);checks.cli_same_engine_without_ui_automation=true
 assert.equal(await page.locator('#operation-kind option').count(),18)
 await page.locator('#tool-tabs button').nth(8).click();await page.locator('#operation-kind').selectOption('box');await page.locator('#operation-add').click()
 const extra=[{kind:'box',label:'共享序列柱',classification:'body',lo:[10,4,10],hi:[10,7,10],state:'stone_bricks'}]
 await page.locator('#operation-sequence').fill(JSON.stringify(extra));await page.locator('#pattern-enabled').evaluate(e=>{e.checked=false;e.dispatchEvent(new Event('input',{bubbles:true}))})
 await page.locator('#update-preview').click();await page.waitForFunction(()=>window.detailControl.state.comparisonSide==='after'&&!window.detailControl.state.previewBusy,undefined,{timeout:90000});assert.equal(await page.evaluate(()=>window.detailControl.gather().operations[0].kind),'box');checks.shared_catalogue_actual_gui_execution=true
 const entries=await fs.readdir(path.join(workspace,'nbt_models/_workspaces/desktop/jobs'),{withFileTypes:true});let relativeRequest=false;for(const entry of entries){const file=path.join(workspace,'nbt_models/_workspaces/desktop/jobs',entry.name,'request.json');try{const request=JSON.parse(await fs.readFile(file,'utf8'));if(request.source==='nbt_models/sample/synthetic.master.json.gz'&&request.path_base==='workspace')relativeRequest=true}catch{}}
 assert.equal(relativeRequest,true);checks.persisted_requests_use_workspace_relative_paths=true
 assert.equal(await page.locator('#open-prompt').isVisible(),false);assert.equal(await page.locator('#load').isVisible(),false);assert.equal(await page.locator('#workspace-tools').evaluate(e=>e.open),false);assert.equal(await page.locator('#gallery').isVisible(),false);assert.equal(await page.locator('.thumbnail-card').isVisible(),false);assert.equal(await page.locator('#open-api').isVisible(),false);checks.compact_model_controls_and_hidden_3d_thumbnails=true
 await page.locator('button[data-workspace=tasks]').click();await page.waitForFunction(()=>document.querySelectorAll('.task-entry').length>0);assert.ok((await page.locator('#task-list').textContent()).includes('导出建筑新版本'));await page.locator('#task-filter').selectOption('complete');assert.ok(await page.locator('.task-state.complete').count()>0);await page.screenshot({path:path.join(output,'tasks.png')});await page.locator('button[data-workspace=model]').click();assert.equal(await page.locator('.result-panel').evaluate(e=>e.open),false);assert.equal(await page.locator('#advanced-review').evaluate(e=>e.open),false);checks.details_stay_collapsed_after_tasks=true;checks.readable_task_records=true
 assert.deepEqual(errors,[]);checks.no_renderer_errors=true
 await fs.writeFile(path.join(output,'results.json'),JSON.stringify({passed:true,checks,executable,workspace},null,2));console.log(JSON.stringify({passed:true,checks:Object.keys(checks).length,output}))
}finally{await app?.close()}
