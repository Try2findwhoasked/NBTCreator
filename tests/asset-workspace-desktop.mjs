import {minimizedScreenshots} from './minimized-screenshots.mjs'
import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import path from 'node:path'
import {spawnSync} from 'node:child_process'
import {createHash} from 'node:crypto'
import {createRequire} from 'node:module'
import {root,skill,python} from '../scripts/paths.mjs'
const require=createRequire(path.join(skill,'assets/viewer/package.json')),{_electron}=require('playwright')
const output=path.join(root,'build','assets-'+Date.now()),workspace=path.join(output,'workspace'),folder=path.join(workspace,'nbt_models/single/asset-room/v1')
const made=spawnSync(python,[path.join(root,'tests/make_fixture.py'),folder],{encoding:'utf8',windowsHide:true});assert.equal(made.status,0,made.stderr)
const source=path.join(folder,'synthetic.master.json.gz')
const script=`import sys;sys.path.insert(0,sys.argv[1]);from nbt_refine import read_master,save_master;m,w=read_master(sys.argv[2]);m.blocks.update({(10,y,10):'minecraft:oak_log[axis=y]' for y in range(4,8)});w.add((10,4,10));save_master(sys.argv[2],m,w)`
const changed=spawnSync(python,['-c',script,path.join(skill,'scripts'),source],{encoding:'utf8',windowsHide:true});assert.equal(changed.status,0,changed.stderr)
const hash=bytes=>createHash('sha256').update(bytes).digest('hex'),before=hash(await fs.readFile(source))
await fs.mkdir(path.join(workspace,'.nbtcreator'),{recursive:true});await fs.writeFile(path.join(workspace,'.nbtcreator/preferences.json'),JSON.stringify({startPage:'model',autoPreview:false}))
let app;const checks={}
try{
 const env={...process.env,NBTCREATOR_AUTOMATION:'1'};delete env.ELECTRON_RUN_AS_NODE
 app=await _electron.launch({executablePath:process.env.NBTCREATOR_TEST_EXE||path.join(root,'node_modules/electron/dist/electron.exe'),args:[...(process.env.NBTCREATOR_TEST_EXE?[]:[root]),'--workspace',workspace,'--user-data-dir',path.join(output,'profile')],env,timeout:60000})
 const page=await app.firstWindow(),errors=[];await minimizedScreenshots(app,page);page.on('pageerror',e=>errors.push(e.message));page.setDefaultTimeout(60000)
 await page.waitForFunction(()=>window.detailControl?.state.info&&!window.detailControl.state.busy&&window.detailControl.state.mode==='3d')
 assert.equal(await app.evaluate(({BrowserWindow})=>BrowserWindow.getAllWindows()[0].isMinimized()),true);checks.minimized_window=true
 await page.getByRole('button',{name:'修改范围',exact:true}).click();await page.locator('#whole-region').uncheck()
 for(const axis of ['x','y','z']){await page.locator('#lo-'+axis).fill(axis==='y'?'4':'10');await page.locator('#hi-'+axis).fill(axis==='y'?'7':'10')}
 await page.locator('#viewport-assets').click();await page.locator('#save-selection-asset').click();await page.locator('#asset-save-name').fill('合成木柱');await page.locator('#asset-save-tags').fill('支承, 木构');await page.locator('#asset-save-confirm').click()
 await page.waitForFunction(()=>document.body.dataset.workspace==='assets'&&document.querySelectorAll('.asset-card').length===1)
 assert.equal(await page.locator('.workspace').isVisible(),false);assert.equal(await page.locator('.action-bar').isVisible(),false);assert.ok((await page.locator('#asset-meta').textContent()).includes('4 格'));checks.separate_workspace_and_capture=true
 await page.locator('#asset-edit-name').fill('可复用木柱');await page.locator('#asset-update').click();await page.waitForFunction(()=>document.querySelector('.asset-card strong').textContent==='可复用木柱')
 await page.locator('#asset-inspector-close').click();await page.locator('#asset-search').fill('不存在');assert.equal(await page.locator('.asset-card').count(),0);await page.locator('#asset-search').fill('木构');assert.equal(await page.locator('.asset-card').count(),1);await page.locator('.asset-card').click();checks.rename_tags_search=true
 const download=await page.locator('#asset-export').getAttribute('href'),data=await page.evaluate(async url=>(await fetch(url)).json(),download);assert.equal(data.size.join(','),'1,4,1');assert.equal(data.blocks.length,4);assert.equal(data.blocks.filter(b=>b[4]).length,1)
 await page.screenshot({path:path.join(output,'asset-workspace.png')});checks.portable_export_and_preview=true
 for(const [axis,value]of [['x','35'],['y','4'],['z','10']])await page.locator('#asset-position-'+axis).fill(value)
 await page.locator('#asset-place').click();await page.waitForFunction(()=>document.body.dataset.workspace==='model'&&window.detailControl.state.comparisonSide==='after'&&!window.detailControl.state.previewBusy)
 const operations=await page.evaluate(()=>window.detailControl.gather().operations);assert.equal(operations.length,2);assert.ok(operations.every(op=>op.kind==='paste_component'));assert.deepEqual(operations.map(op=>op.classification).sort(),['body','wall']);checks.reuse_preview_same_engine=true
 await page.locator('[data-workspace=assets]').click();await page.locator('.asset-card').click();await page.locator('#asset-archive').click();await page.waitForFunction(()=>document.querySelectorAll('.asset-card').length===0);await page.locator('#asset-filters-menu>summary').click();await page.locator('#asset-trash').check();await page.locator('.asset-card').click();await page.locator('#asset-archive').click();await page.locator('#asset-filters-menu>summary').click();await page.locator('#asset-trash').uncheck();await page.waitForFunction(()=>document.querySelectorAll('.asset-card').length===1);checks.recoverable_archive=true
 await page.locator('#asset-import-file').setInputFiles({name:'copy.component.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(data))});await page.waitForFunction(()=>document.querySelectorAll('.asset-card').length===2);checks.import_usable_asset=true
 await page.locator('#asset-inspector-close').click();await page.reload();await page.waitForFunction(()=>window.detailControl?.state.info&&!window.detailControl.state.busy);await page.locator('[data-workspace=assets]').click();await page.waitForFunction(()=>document.querySelectorAll('.asset-card').length===2);checks.persist_after_reload=true
 const cli=spawnSync(python,[path.join(workspace,'.agents/skills/nbtcreator-workspace/nbt.py'),'components','list'],{cwd:workspace,encoding:'utf8',windowsHide:true});assert.equal(cli.status,0,cli.stderr);assert.equal(JSON.parse(cli.stdout).result.items.length,2);checks.external_skill_same_assets=true
 const style=spawnSync(python,[path.join(workspace,'.agents/skills/nbtcreator-workspace/nbt.py'),'ai-style','prompt','--workflow','small_structure'],{cwd:workspace,encoding:'utf8',windowsHide:true});assert.equal(style.status,0,style.stderr);assert.equal(JSON.parse(style.stdout).result.workflow,'small_structure');checks.external_skill_style_callable=true
 assert.equal(hash(await fs.readFile(source)),before);assert.deepEqual(errors,[]);assert.equal(await app.evaluate(({BrowserWindow})=>BrowserWindow.getAllWindows()[0].isMinimized()),true);checks.original_unchanged_no_errors=true
 await fs.writeFile(path.join(output,'results.json'),JSON.stringify({passed:true,checks},null,2));console.log(JSON.stringify({passed:true,checks:Object.keys(checks).length,output}))
}finally{await app?.close()}
