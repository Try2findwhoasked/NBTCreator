// Real IPC/workspace transition against a deliberately hanging local mock API.
import fs from 'node:fs/promises'
import path from 'node:path'
import http from 'node:http'
import assert from 'node:assert/strict'
import {createRequire} from 'node:module'
import {spawnSync} from 'node:child_process'
import {root,skill,python} from '../scripts/paths.mjs'
const require=createRequire(path.join(skill,'assets/viewer/package.json')),{_electron}=require('playwright')
const output=path.join(root,'build','workspace-api-desktop-'+Date.now());await fs.mkdir(output,{recursive:true})
const workspace=path.join(output,'old-workspace'),next=path.join(output,'new-workspace')
const made=spawnSync(python,[path.join(root,'tests/make_fixture.py'),path.join(workspace,'nbt_models/sample')],{encoding:'utf8'})
assert.equal(made.status,0,made.stderr);await fs.mkdir(next)
let enteredResolve,abortedResolve,first=true,calls=0,oldResponse,app,abortTimer
const entered=new Promise(resolve=>enteredResolve=resolve),aborted=new Promise(resolve=>abortedResolve=resolve)
const server=http.createServer(async(req,res)=>{
 let body='';for await(const chunk of req)body+=chunk
 calls++;res.setHeader('Content-Type','application/json')
 if(first&&req.url==='/v1/chat/completions'){
  first=false;oldResponse=res;enteredResolve()
  res.once('close',()=>{if(!res.writableEnded)abortedResolve()})
  return
 }
 res.end(JSON.stringify({choices:[{message:{content:'new workspace candidate'},finish_reason:'stop'}]}))
})
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve))
try{
 const env={...process.env,NBTCREATOR_AUTOMATION:'1'};delete env.ELECTRON_RUN_AS_NODE
 app=await _electron.launch({executablePath:process.env.NBTCREATOR_TEST_EXE||path.join(root,'node_modules/electron/dist/electron.exe'),args:[...(process.env.NBTCREATOR_TEST_EXE?[]:[root]),'--workspace',workspace,'--user-data-dir',path.join(output,'profile')],env,timeout:60000})
 const page=await app.firstWindow();page.setDefaultTimeout(30000)
 await page.waitForFunction(()=>window.detailControl?.state.info&&!window.detailControl.state.busy,undefined,{timeout:60000})
 await page.evaluate(baseUrl=>window.nbtDesktop.apiSave({enabled:true,provider:'compatible',baseUrl,model:'mock-model',jsonMode:true}),`http://127.0.0.1:${server.address().port}/v1`)
 await page.locator('#tool-tabs button').nth(9).click()
 await page.locator('#ai-mode').selectOption('prompt');await page.locator('#ai-instruction').fill('old workspace pending candidate')
 await page.locator('#ai-generate').click();await entered
 await app.evaluate(({dialog},folder)=>{dialog.showOpenDialog=async()=>({canceled:false,filePaths:[folder]});dialog.showMessageBox=async()=>({response:0})},next)
 await page.evaluate(()=>{window.nbtDesktop.chooseWorkspace().catch(()=>{})})
 await Promise.race([aborted,new Promise((_,reject)=>{abortTimer=setTimeout(()=>reject(Error('old API request was not aborted')),10000)})]);clearTimeout(abortTimer)
 await page.waitForFunction(folder=>window.detailControl?.state.workspace===folder&&!window.detailControl.state.busy,next,{timeout:60000})
 const fresh=await page.evaluate(()=>window.nbtDesktop.apiGenerate({mode:'prompt',instruction:'new workspace request'}))
 assert.equal(fresh.text,'new workspace candidate');assert.equal(calls,2)
 const newJobs=await page.evaluate(async()=>await(await fetch('/__detail__/jobs')).json())
 assert.equal(newJobs.some(job=>String(job.instruction||'').includes('old workspace')),false)
 assert.equal(await page.locator('#ai-result').inputValue(),'')
 const pointer=JSON.parse(await fs.readFile(path.join(output,'profile/settings.json'),'utf8'))
 assert.equal(path.resolve(path.join(output,'profile'),pointer.workspace),next)
 const oldJobs=await fs.readdir(path.join(workspace,'nbt_models/_workspaces/desktop/jobs'),{withFileTypes:true})
 const oldAi=[]
 for(const item of oldJobs){try{const record=JSON.parse(await fs.readFile(path.join(workspace,'nbt_models/_workspaces/desktop/jobs',item.name,'job.json'),'utf8'));if(record.kind==='ai')oldAi.push(record)}catch{}}
 await fs.writeFile(path.join(output,'results.json'),JSON.stringify({passed:true,checks:{old_api_connection_aborted:true,new_workspace_api_slot_reusable:true,old_result_not_applied_to_new_page:true,old_activity_not_written_to_new_jobs:true,remembered_workspace_updated:true},old_activity_statuses:oldAi.map(record=>record.status)},null,2))
 console.log(JSON.stringify({passed:true,checks:5,old_activity_statuses:oldAi.map(record=>record.status),output}))
}finally{
 clearTimeout(abortTimer);oldResponse?.destroy();await app?.close();await new Promise(resolve=>server.close(resolve))
}
