import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import path from 'node:path'
import http from 'node:http'
import {spawnSync} from 'node:child_process'
import {createRequire} from 'node:module'
import {root, skill, python} from '../../scripts/paths.mjs'
import {minimizedScreenshots} from '../support/minimized-screenshots.mjs'

const require=createRequire(path.join(skill,'assets/viewer/package.json'))
const {_electron}=require('playwright')
const output=path.join(root,'build','creation-workflows-'+Date.now())
const workspace=path.join(output,'workspace')
const preferences=path.join(workspace,'.nbtcreator/preferences.json')
await fs.mkdir(path.dirname(preferences),{recursive:true})
await fs.writeFile(preferences,JSON.stringify({startPage:'prompt',autoPreview:false}))
const calls=[]
const server=http.createServer(async(req,res)=>{
 let body=''
 for await(const chunk of req)body+=chunk
 calls.push(JSON.parse(body))
 res.setHeader('Content-Type','application/json')
 res.end(JSON.stringify({choices:[{finish_reason:'stop',message:{content:JSON.stringify({
  summary:'补风格',project_patch:{style:'保留原钟，木梁承担顶构。'}
 })}}]}))
})
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve))

const env={...process.env,NBTCREATOR_AUTOMATION:'1'}
delete env.ELECTRON_RUN_AS_NODE
let app
async function launch(){
 app=await _electron.launch({executablePath:process.env.NBTCREATOR_TEST_EXE||path.join(root,'node_modules/electron/dist/electron.exe'),
  args:[...(process.env.NBTCREATOR_TEST_EXE?[]:[root]),'--workspace',workspace,'--user-data-dir',path.join(output,'profile')],env,timeout:60000})
 const page=await app.firstWindow()
 page.setDefaultTimeout(60000)
 await minimizedScreenshots(app,page)
 await page.waitForFunction(()=>document.querySelector('#prompt-frame')?.contentDocument?.body?.dataset.promptReady==='true')
 return page
}

async function openCreationSettings(page){
 await page.locator('#open-settings').click()
 await page.locator('[data-settings-tab=ai]').click()
}

try{
 let page=await launch()
 const errors=[]
 page.on('pageerror',error=>errors.push(error.message))
 await openCreationSettings(page)
 assert.equal(await page.locator('#setting-creation-mode').inputValue(),'economy')
 await page.locator('#setting-creation-mode').selectOption('maximum')
 await page.locator('#setting-economy-model').fill('test-economy')
 await page.locator('#setting-quality-model').fill('test-strong')
 await page.locator('#settings-save').click()
 await page.waitForFunction(()=>document.querySelector('#settings-status').textContent.includes('已保存'))
 await page.locator('#close-settings').click()

 const frame=page.frameLocator('#prompt-frame')
 await frame.locator('[data-planning-step=review]').click()
 await frame.locator('[data-field=name]').fill('外部起草测试楼')
 await frame.locator('[data-field=size_policy]').selectOption('fixed')
 await frame.locator('[data-planning-step=write]').click()
 const mandatory='保留西塔原钟。\n入口净宽至少三格。'
 await frame.locator('#prompt-user-requirements').fill(mandatory)
 await frame.locator('#prompt-ai-instruction').fill('补充入口布局，保留主体。')
 await frame.locator('#prompt-external-draft > summary').click()
 await frame.locator('body').evaluate(()=>{
  Object.defineProperty(navigator,'clipboard',{value:{writeText:async text=>{window.testDraftPacket=text}}})
 })
 async function copy(){
  await frame.locator('#prompt-external-copy').click()
  await frame.locator('#prompt-ai-status').filter({hasText:'已复制'}).waitFor()
  return JSON.parse(await frame.locator('body').evaluate(()=>window.testDraftPacket))
 }
 async function importReply(reply){
  await frame.locator('#prompt-external-reply').fill(JSON.stringify(reply))
  await frame.locator('#prompt-external-import').click()
 }
 const old=await copy()
 assert.equal(old.user_requirements,mandatory)
 assert.equal(old.instruction,'补充入口布局，保留主体。')
 assert.ok(!old.editable_fields.includes('size'))
 assert.ok(!Object.hasOwn(old.project,'source'))
 await frame.locator('#prompt-ai-instruction').fill('补充入口到主厅的连接。')
 await importReply({...old.response,project_patch:{layout:'过渡门廊'}})
 await frame.locator('#prompt-ai-status').filter({hasText:'旧稿'}).waitFor()
 const packet=await copy()
 await importReply({...packet.response,project_patch:{layout:'过渡门廊',source:'unauthorised.snbt'}})
 await frame.locator('#prompt-ai-status').filter({hasText:'不能修改'}).waitFor()
 await importReply({...packet.response,project_patch:{layout:'由过渡门廊进入主厅。',style:'建议石构。'}})
 await frame.locator('[data-proposal-field=layout]').waitFor()
 assert.equal(calls.length,0)
 assert.equal(await frame.locator('[data-field=layout]').inputValue(),'')
 await frame.locator('[data-adopt-field=style]').uncheck()
 await frame.locator('#prompt-primary').click()
 assert.equal(await frame.locator('[data-field=layout]').inputValue(),'由过渡门廊进入主厅。')
 assert.notEqual(await frame.locator('[data-field=style]').inputValue(),'建议石构。')

 await page.evaluate(baseUrl=>window.nbtDesktop.apiSave({enabled:true,provider:'compatible',baseUrl,model:'test-regular'}),
  `http://127.0.0.1:${server.address().port}`)
 await frame.locator('[data-planning-step=write]').click()
 await frame.locator('#prompt-primary').click()
 await frame.locator('[data-proposal-field=style]').waitFor()
 assert.equal(calls.at(-1).model,'test-strong')
 await frame.locator('#prompt-primary').click()
 assert.equal(await frame.locator('[data-field=style]').inputValue(),'保留原钟，木梁承担顶构。')
 await frame.locator('#prompt-primary').click()
 await page.waitForFunction(()=>document.querySelector('#prompt-frame').contentDocument.querySelector('#prompt-task-state').dataset.id)
 const id=await frame.locator('#prompt-task-state').getAttribute('data-id')
 const entry=path.join(workspace,'.agents/skills/nbtcreator-workspace/nbt.py')
 const result=spawnSync(python,['-B',entry,'prompts','task','--id',id],
  {cwd:workspace,env:{...env,PYTHONIOENCODING:'utf-8'},encoding:'utf8',windowsHide:true})
 assert.equal(result.status,0,result.stderr+result.stdout)
 const task=JSON.parse(result.stdout)
 assert.equal(task.task.creation.mode,'maximum')
 assert.equal(task.task.creation.quality_model,'test-strong')
 assert.ok(task.text.includes(mandatory))
 assert.ok(task.text.includes('由过渡门廊进入主厅。'))
 assert.equal(task.document.user_requirements,mandatory)
 assert.deepEqual(errors,[])
 await app.close()
 page=await launch()
 await openCreationSettings(page)
 assert.equal(await page.locator('#setting-creation-mode').inputValue(),'maximum')
 assert.equal(await page.locator('#setting-economy-model').inputValue(),'test-economy')
 assert.equal(await page.locator('#setting-quality-model').inputValue(),'test-strong')
 await page.locator('#setting-creation-mode').selectOption('economy')
 await page.locator('#settings-save').click()
 await page.waitForFunction(()=>document.querySelector('#settings-status').textContent.includes('已保存'))
 const stored=JSON.parse(await fs.readFile(preferences,'utf8'))
 assert.equal(stored.creationMode,'economy')
 const again=spawnSync(python,['-B',entry,'prompts','task','--id',id],
  {cwd:workspace,env:{...env,PYTHONIOENCODING:'utf-8'},encoding:'utf8',windowsHide:true})
 assert.equal(JSON.parse(again.stdout).task.creation.mode,'maximum')
 console.log(JSON.stringify({passed:true,output}))
}finally{
 await app?.close().catch(()=>{})
 server.closeAllConnections()
 await new Promise(resolve=>server.close(resolve))
}
