import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import path from 'node:path'
import {createRequire} from 'node:module'
import {root,skill} from '../scripts/paths.mjs'
import {minimizedScreenshots} from './minimized-screenshots.mjs'
const require=createRequire(path.join(skill,'assets/viewer/package.json')),{_electron}=require('playwright')
const output=path.join(root,'build','updater-'+Date.now()),workspace=path.join(output,'workspace'),checks={},errors=[]
await fs.mkdir(workspace,{recursive:true})
const env={...process.env,NBTCREATOR_AUTOMATION:'1'};delete env.ELECTRON_RUN_AS_NODE
let app,page
const click=id=>page.locator('#'+id).evaluate(e=>e.click())
const status=text=>page.waitForFunction(text=>document.querySelector('#settings-status').textContent.includes(text),text)
async function checkResult(result){await app.evaluate(({ipcMain},result)=>{ipcMain.removeHandler('nbt:update-check');ipcMain.handle('nbt:update-check',()=>{if(result.error)throw Error(result.error);return result})},result);await click('update-check')}
const ready={current:'3.0.0',latest:'v9.0.0',available:true,notes:'Local updater fixture',assets:['app-update']}
try{
 app=await _electron.launch({executablePath:process.env.NBTCREATOR_TEST_EXE||path.join(root,'node_modules/electron/dist/electron.exe'),args:[...(process.env.NBTCREATOR_TEST_EXE?[]:[root]),'--workspace',workspace,'--user-data-dir',path.join(output,'profile')],env,timeout:60000})
 page=await app.firstWindow();page.setDefaultTimeout(30000);await minimizedScreenshots(app,page);page.on('pageerror',e=>errors.push(e.message))
 await page.waitForFunction(()=>window.detailControl?.state.catalogReady)
 await click('open-settings');await page.waitForFunction(()=>!document.querySelector('#settings-save').disabled);await page.locator('[data-settings-tab=updates]').evaluate(e=>e.click())
 await checkResult(ready);await status('发现 v9.0.0');assert.equal(await page.locator('#update-download').isDisabled(),false)
 await checkResult({...ready,assets:[]});await status('尚不完整');assert.equal(await page.locator('#update-download').isDisabled(),true);checks.incomplete_release_cannot_download=true
 await checkResult(ready);await status('可一键下载');await checkResult({error:'Local check failed'});await status('Local check failed');assert.equal(await page.locator('#update-download').isDisabled(),true);assert.equal(await page.locator('#update-notes').textContent(),'');checks.failed_check_clears_previous_offer=true
 await app.evaluate(({ipcMain})=>{ipcMain.removeHandler('nbt:update-check');ipcMain.handle('nbt:update-check',()=>new Promise(resolve=>globalThis.finishUpdateCheck=resolve))})
 await click('update-check');await status('正在检查')
 for(const id of ['update-check','update-download','update-kind','update-token-save','update-token-clear'])assert.equal(await page.locator('#'+id).isDisabled(),true,id)
 await click('close-settings');await click('open-settings');await page.waitForFunction(()=>!document.querySelector('#settings-save').disabled);assert.equal(await page.locator('#update-check').isDisabled(),true)
 await app.evaluate((_,result)=>globalThis.finishUpdateCheck(result),{...ready,assets:['portable']});await status('可一键下载');assert.equal(await page.locator('#update-kind').inputValue(),'portable');checks.check_lock_survives_dialog_reopen=true
 await app.evaluate(({ipcMain})=>{
  ipcMain.removeHandler('nbt:update-download');ipcMain.handle('nbt:update-download',(_,kind)=>{globalThis.downloadKind=kind;return new Promise((resolve,reject)=>{globalThis.finishUpdateDownload=resolve;globalThis.failUpdateDownload=reject})})
  ipcMain.removeHandler('nbt:update-status');ipcMain.handle('nbt:update-status',()=>{globalThis.updatePolled=true;throw Error('Local polling failure')})
 })
 await click('update-download');await status('正在下载')
 for(const id of ['update-check','update-download','update-kind','update-token-save'])assert.equal(await page.locator('#'+id).isDisabled(),true,id)
 // Wait for an actual failed IPC poll, then let the download itself fail.
 await app.evaluate(()=>new Promise((resolve,reject)=>{const timer=setInterval(()=>{if(globalThis.updatePolled){clearInterval(timer);clearTimeout(timeout);resolve()}},20);const timeout=setTimeout(()=>{clearInterval(timer);reject(Error('No update progress poll'))},5000)}))
 await app.evaluate(()=>globalThis.failUpdateDownload(Error('Local download interrupted')));await status('Local download interrupted');assert.equal(await page.locator('#update-progress').textContent(),'下载失败，可重试');assert.equal(await page.locator('#update-download').isDisabled(),false);checks.poll_failure_is_handled_and_download_can_retry=true
 await click('update-download');await status('正在下载');assert.equal(await app.evaluate(()=>globalThis.downloadKind),'portable')
 await app.evaluate(()=>globalThis.finishUpdateDownload({status:'ready',received:1048576,total:1048576,path:'verified-update.zip',kind:'portable'}));await status('SHA256校验完成');assert.equal(await page.locator('#update-progress').textContent(),'1.0 / 1.0 MiB');checks.retry_finishes_with_final_progress=true
 assert.equal(await app.evaluate(({BrowserWindow})=>BrowserWindow.getAllWindows()[0].isMinimized()),true);assert.deepEqual(errors,[])
 await page.screenshot();await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))))
 await page.screenshot({path:path.join(output,'updates.png')});await fs.writeFile(path.join(output,'results.json'),JSON.stringify({passed:true,checks},null,2));console.log(JSON.stringify({passed:true,checks,output}))
}catch(error){console.error(JSON.stringify({output,checks,errors}));throw error}finally{await app?.close()}
