import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import path from 'node:path'
import http from 'node:http'
import {createRequire} from 'node:module'
import {root,skill} from '../scripts/paths.mjs'
import {minimizedScreenshots} from './minimized-screenshots.mjs'
const require=createRequire(path.join(skill,'assets/viewer/package.json')),{_electron}=require('playwright')
const output=path.join(root,'build','ai-character-limit-'+Date.now()),workspace=path.join(output,'workspace'),calls=[];await fs.mkdir(workspace,{recursive:true})
const server=http.createServer(async(req,res)=>{let raw='';for await(const chunk of req)raw+=chunk;const body=JSON.parse(raw);calls.push(body);res.setHeader('Content-Type','application/json');res.end(JSON.stringify({choices:[{finish_reason:'stop',message:{content:calls.length===1?'字'.repeat(101):'限额内的中文说明。'}}]}))});await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));let app,page;const errors=[]
try{
 const env={...process.env,NBTCREATOR_AUTOMATION:'1'};delete env.ELECTRON_RUN_AS_NODE
 app=await _electron.launch({executablePath:process.env.NBTCREATOR_TEST_EXE||path.join(root,'node_modules/electron/dist/electron.exe'),args:[...(process.env.NBTCREATOR_TEST_EXE?[]:[root]),'--workspace',workspace,'--user-data-dir',path.join(output,'profile')],env,timeout:60000});page=await app.firstWindow();await minimizedScreenshots(app,page);page.setDefaultTimeout(60000);page.on('pageerror',e=>errors.push(e.message))
 await page.waitForFunction(()=>window.detailControl?.state.catalogReady);await page.locator('button[data-workspace=ai]').click();await page.locator('#api-enabled').check();await page.locator('#api-provider').selectOption('compatible');await page.locator('#api-base').fill(`http://127.0.0.1:${server.address().port}`);await page.locator('#api-model').fill('local-mock');await page.locator('#api-character-limit').fill('100');await page.locator('#api-save').click();await page.waitForFunction(()=>document.querySelector('#ai-status').textContent.includes('已保存'))
 assert.equal((await page.evaluate(()=>window.nbtDesktop.apiConfig())).outputCharLimit,100);await page.reload();await page.waitForFunction(()=>window.detailControl?.state.catalogReady);await page.locator('button[data-workspace=ai]').click();assert.equal(await page.locator('#api-character-limit').inputValue(),'100')
 await page.locator('button[data-workspace=model]').click();await page.locator('#tool-tabs [data-tool-index="9"]').evaluate(e=>e.click());await page.locator('#ai-mode').selectOption('prompt');await page.locator('#ai-instruction').fill('简短介绍房间');await page.locator('#ai-generate').click();await page.waitForFunction(()=>document.querySelector('#ai-result').value==='限额内的中文说明。'&&!document.querySelector('#ai-generate').disabled)
 assert.equal(calls.length,2);assert.ok(calls[0].messages[0].content.includes('最终结果限制为 100 字'));assert.ok(calls[1].messages.at(-1).content.includes('超过 100 字'));assert.deepEqual(errors,[])
 await page.locator('button[data-workspace=ai]').click();await page.locator('#api-character-limit').fill('0');await page.locator('#api-save').click();await page.waitForFunction(()=>document.querySelector('#ai-status').textContent.includes('已保存'));assert.equal((await page.evaluate(()=>window.nbtDesktop.apiConfig())).outputCharLimit,0)
 await page.locator('button[data-workspace=model]').click();await page.locator('#tool-tabs [data-tool-index="9"]').evaluate(e=>e.click());await page.locator('#ai-generate').click();await page.waitForFunction(()=>!document.querySelector('#ai-generate').disabled);assert.ok(calls.at(-1).messages[0].content.includes('不设应用字数限制'));assert.deepEqual(errors,[])
 await fs.writeFile(path.join(output,'results.json'),JSON.stringify({passed:true,checks:{character_setting_saves_and_restores:true,first_request_contains_limit:true,over_limit_reply_is_corrected_before_display:true,zero_disables_character_limit_in_actual_requests:true},external_api_used:false},null,2));console.log(JSON.stringify({passed:true,checks:4,output}))
}finally{await app?.close();server.closeAllConnections();await new Promise(resolve=>server.close(resolve))}
