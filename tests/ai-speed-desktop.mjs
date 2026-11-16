import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import path from 'node:path'
import {spawnSync} from 'node:child_process'
import {createRequire} from 'node:module'
import {root,skill,python} from '../scripts/paths.mjs'
import {createFetchServer} from './fetch-server.mjs'
import {minimizedScreenshots} from './minimized-screenshots.mjs'
const require=createRequire(path.join(skill,'assets/viewer/package.json')),{_electron}=require('playwright')
const output=path.join(root,'build','ai-speed-'+Date.now()),workspace=path.join(output,'workspace'),sample=path.join(workspace,'nbt_models/sample')
await fs.mkdir(path.join(workspace,'.nbtcreator'),{recursive:true})
await fs.writeFile(path.join(workspace,'.nbtcreator/preferences.json'),JSON.stringify({startPage:'model'}))
const fixture=spawnSync(python,[path.join(root,'tests/make_fixture.py'),sample],{encoding:'utf8',windowsHide:true});assert.equal(fixture.status,0,fixture.stderr)
const calls=[]
const server=await createFetchServer(async(req,res)=>{
 let raw='';for await(const chunk of req)raw+=chunk
 const body=JSON.parse(raw);calls.push(body)
 const {context}=JSON.parse(body.messages[1].content),lo=context.lo
 res.setHeader('content-type','application/json')
 res.end(JSON.stringify({choices:[{finish_reason:'stop',message:{content:JSON.stringify({summary:'严格方案',settings_patch:{lo,hi:lo,structure:{enabled:true,mode:'fill',state:'stone_bricks',classification:'body',thickness:1,offset:[0,0,0]},replace:null}})}}]}))
})
let app
try{
 const env={...process.env,NBTCREATOR_AUTOMATION:'1'};delete env.ELECTRON_RUN_AS_NODE
 app=await _electron.launch({executablePath:process.env.NBTCREATOR_TEST_EXE||path.join(root,'node_modules/electron/dist/electron.exe'),args:[...(process.env.NBTCREATOR_TEST_EXE?[]:[root]),'--workspace',workspace,'--user-data-dir',path.join(output,'profile')],env,timeout:60000})
 const page=await app.firstWindow();await minimizedScreenshots(app,page)
 await page.waitForFunction(()=>window.detailControl?.state.info&&!window.detailControl.state.busy,undefined,{timeout:60000})
 await page.locator('#auto-preview').uncheck();await page.locator('#studio-ai-settings').click()
 await page.locator('#api-provider').selectOption('compatible');await page.locator('#api-base').fill(`http://127.0.0.1:${server.address().port}/v1`);await page.locator('#api-model').fill('schema-mock');await page.locator('#api-enabled').check()
 await page.locator('#api-advanced').evaluate(e=>e.open=true);await page.locator('#api-strict-schema').check();await page.locator('#api-save').click()
 await page.waitForFunction(()=>document.querySelector('#ai-status').textContent.includes('已保存'))
 assert.equal(JSON.parse(await fs.readFile(path.join(output,'profile/api-settings.json'),'utf8')).config.strictSchema,true)
 await page.locator('#close-api').click();await page.locator('#studio-panel-tools').click();await page.locator('#studio-tool-menu>summary').click();await page.locator('#tool-tabs button[data-tool-index="4"]').click();await page.locator('#whole-region').uncheck()
 for(const [id,value]of Object.entries({'lo-x':8,'lo-y':4,'lo-z':8,'hi-x':15,'hi-y':10,'hi-z':15}))await page.locator('#'+id).fill(String(value))
 await page.locator('#studio-tool-menu>summary').click();await page.locator('#tool-tabs button[data-tool-index="9"]').click();await page.locator('#ai-mode').selectOption('structure');await page.locator('#ai-instruction').fill('严格Schema添加一个方块');await page.locator('#ai-generate').click()
 await page.waitForFunction(()=>!document.querySelector('#ai-generate').disabled,undefined,{timeout:30000})
 assert.ok((await page.locator('#ai-result').inputValue()).includes('严格方案'),await page.locator('#ai-status').textContent())
 assert.equal(calls.length,1);assert.equal(calls[0].response_format.type,'json_schema');assert.equal(calls[0].response_format.json_schema.strict,true)
 assert.equal(await page.locator('#ai-apply').isDisabled(),false)
 await page.locator('#studio-ai-settings').click();assert.equal(await page.locator('#api-strict-schema').isChecked(),true)
 await page.locator('#api-options-reset').click();assert.equal(await page.locator('#api-strict-schema').isChecked(),false)
 await page.screenshot({path:path.join(output,'strict-schema.png')})
 console.log(JSON.stringify({passed:true,checks:['strict_setting_saved','schema_reaches_request','candidate_validated_without_export','setting_reflected_and_reset'],output}))
}finally{await app?.close();await new Promise(resolve=>server.close(resolve))}
