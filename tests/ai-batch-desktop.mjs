import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import path from 'node:path'
import http from 'node:http'
import {spawnSync} from 'node:child_process'
import {createRequire} from 'node:module'
import {root,skill,python} from '../scripts/paths.mjs'
import {minimizedScreenshots} from './minimized-screenshots.mjs'
const require=createRequire(path.join(skill,'assets/viewer/package.json')),{_electron}=require('playwright'),output=path.join(root,'build','ai-batch-'+Date.now()),workspace=path.join(output,'workspace'),fixture=path.join(workspace,'nbt_models/single/面板测试/v01'),checks={},errors=[]
const made=spawnSync(python,[path.join(root,'tests/make_fixture.py'),fixture],{encoding:'utf8',windowsHide:true});assert.equal(made.status,0,made.stderr)
await fs.mkdir(path.join(workspace,'.nbtcreator'),{recursive:true});await fs.writeFile(path.join(workspace,'.nbtcreator/preferences.json'),JSON.stringify({startPage:'prompt',autoPreview:false}))

const counts=new Map();let live=0,peak=0
const server=http.createServer(async(req,res)=>{let raw='';for await(const chunk of req)raw+=chunk;const request=JSON.parse(raw),input=JSON.parse(request.messages[1].content),name=input.context.project.name;counts.set(name,(counts.get(name)??0)+1);live++;peak=Math.max(peak,live);res.once('close',()=>live--)
 if(name.startsWith('取消')&&counts.get(name)===1){await new Promise(resolve=>res.once('close',resolve));return}
 await new Promise(resolve=>setTimeout(resolve,150));if(res.destroyed)return
 if(name==='失败后重试'&&counts.get(name)===1){res.writeHead(503);res.end('{}');return}
 const project_patch={name,theme:'石构建筑',purpose:name+'的用途',layout:name+'的空间',circulation:'入口连接大厅和楼梯',style:'石砖与木构',ceiling:'梁柱支承屋顶',floor:'石材铺装',wall:'墙体留出门窗',props:'保留通路，节点放置陈设'}
 res.setHeader('Content-Type','application/json');res.end(JSON.stringify({choices:[{finish_reason:'stop',message:{content:JSON.stringify({project_patch})}}]}))
});await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve))
let app,page
const idle=()=>page.waitForFunction(()=>!document.querySelector('#prompt-frame').contentDocument.querySelector('#prompt-add').disabled)
async function batch(names){const f=page.frameLocator('#prompt-frame');await f.locator('#prompt-batch-open').click();await f.locator('#prompt-batch-items').fill(names.join('\n'));await f.locator('#prompt-batch-generate').click()}
try{
 const env={...process.env,NBTCREATOR_AUTOMATION:'1',OPENBLAS_NUM_THREADS:'1',OMP_NUM_THREADS:'1'};delete env.ELECTRON_RUN_AS_NODE
 app=await _electron.launch({executablePath:path.join(root,'node_modules/electron/dist/electron.exe'),args:[root,'--workspace',workspace,'--user-data-dir',path.join(output,'profile')],env,timeout:60000});page=await app.firstWindow();await minimizedScreenshots(app,page);page.setDefaultTimeout(60000);page.on('pageerror',e=>errors.push(e.message));await page.waitForFunction(()=>document.querySelector('#prompt-frame').contentDocument?.body?.dataset.promptReady==='true')
 await page.evaluate(baseUrl=>window.nbtDesktop.apiSave({enabled:true,provider:'compatible',baseUrl,model:'batch-mock',maxConcurrent:2}),`http://127.0.0.1:${server.address().port}`)
 const frame=page.frameLocator('#prompt-frame')
 await batch(['并发工坊','失败后重试','并发茶馆']);await idle();assert.equal(peak,2);assert.match(await frame.locator('#prompt-queue-list').textContent(),/未完成/)
 await frame.locator('#prompt-batch-retry').click();await idle();assert.deepEqual(Object.fromEntries(counts),{'并发工坊':1,'失败后重试':2,'并发茶馆':1});assert.doesNotMatch(await frame.locator('#prompt-queue-list').textContent(),/未完成/);checks.retry_only_regenerates_failed_document=true
 for(const name of ['并发工坊','失败后重试','并发茶馆']){await frame.locator('#prompt-queue-list button').filter({hasText:name}).click();await idle();assert.equal(await frame.locator('[data-field=purpose]').inputValue(),name+'的用途');assert.equal(await frame.locator('#prompt-review-state').textContent(),'待审查')};checks.parallel_outputs_are_bound_to_their_own_buildings=true
 await batch(['取消一号','取消二号']);await page.waitForFunction(()=>document.querySelector('#prompt-frame').contentDocument.querySelector('#prompt-batch-open').textContent==='停止批量生成');const deadline=Date.now()+30000;while(!counts.has('取消二号')&&Date.now()<deadline)await new Promise(resolve=>setTimeout(resolve,20));assert.ok(counts.has('取消二号'));await frame.locator('#prompt-batch-open').click();await idle();assert.equal(await frame.locator('#prompt-queue-list button').count(),5)
 await frame.locator('#prompt-batch-retry').click();await idle();assert.equal(counts.get('取消一号'),2);assert.equal(counts.get('取消二号'),2);assert.equal(counts.get('并发工坊'),1);assert.equal(await frame.locator('#prompt-batch-retry').isDisabled(),true);checks.batch_cancellation_keeps_drafts_and_retry_finishes_only_waiting_items=true
 await frame.locator('#prompt-batch-open').click();await frame.locator('#prompt-batch-items').fill('取消下一条');await frame.locator('#prompt-batch-add').click();await idle();await frame.locator('#prompt-next').click();
 const singleDeadline=Date.now()+30000;while(!counts.has('取消下一条')&&Date.now()<singleDeadline)await new Promise(resolve=>setTimeout(resolve,20));assert.equal(counts.get('取消下一条'),1);await frame.locator('#prompt-ai-cancel').click();await idle();assert.match(await frame.locator('#prompt-ai-status').textContent(),/已终止/);assert.equal(await frame.locator('#prompt-ai-cancel').isVisible(),false);checks.next_prompt_can_be_terminated_through_visible_control_without_waiting_for_provider=true
 await page.locator('#studio-ai-settings').click();await page.waitForFunction(()=>document.querySelector('#api-concurrency').value==='2');await page.locator('#api-concurrency').selectOption('3');await page.locator('#api-save').click();await page.waitForFunction(()=>document.querySelector('#api-config-status').textContent.includes('连接已保存'));assert.equal((await page.evaluate(()=>window.nbtDesktop.apiConfig())).maxConcurrent,3);checks.concurrency_setting_is_available_and_saved_through_UI=true
 assert.deepEqual(errors,[]);await page.screenshot();await page.screenshot({path:path.join(output,'completed.png')});await fs.writeFile(path.join(output,'results.json'),JSON.stringify({passed:true,peak,counts:Object.fromEntries(counts),checks},null,2));console.log(JSON.stringify({passed:true,peak,checks,output}))
}catch(error){await page?.screenshot({path:path.join(output,'failure.png')}).catch(()=>{});console.error(JSON.stringify({output,counts:Object.fromEntries(counts),errors}));throw error}finally{await app?.close();server.closeAllConnections();await new Promise(resolve=>server.close(resolve))}
