import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import path from 'node:path'
import {spawnSync} from 'node:child_process'
import {createRequire} from 'node:module'
import {root,skill,python} from '../../scripts/paths.mjs'
import {minimizedScreenshots} from '../support/minimized-screenshots.mjs'
const require=createRequire(path.join(skill,'assets/viewer/package.json')),{_electron}=require('playwright'),output=path.join(root,'build','prompt-task-'+Date.now()),workspace=path.join(output,'workspace'),checks={},errors=[]
await fs.mkdir(path.join(workspace,'.nbtcreator'),{recursive:true});await fs.writeFile(path.join(workspace,'.nbtcreator/preferences.json'),JSON.stringify({startPage:'prompt',autoPreview:false}))
const runtime=python
const cli=args=>{const run=spawnSync(runtime,[path.join(workspace,'.agents/skills/nbtcreator-workspace/nbt.py'),'prompts',...args],{cwd:workspace,encoding:'utf8',windowsHide:true,timeout:30000});assert.equal(run.status,0,run.stdout+run.stderr);return JSON.parse(run.stdout)}
let app,page
try{
 const env={...process.env,NBTCREATOR_AUTOMATION:'1'};delete env.ELECTRON_RUN_AS_NODE
 app=await _electron.launch({executablePath:process.env.NBTCREATOR_TEST_EXE||path.join(root,'node_modules/electron/dist/electron.exe'),args:[...(process.env.NBTCREATOR_TEST_EXE?[]:[root]),'--workspace',workspace,'--user-data-dir',path.join(output,'profile')],env,timeout:60000});page=await app.firstWindow();page.setDefaultTimeout(60000);await minimizedScreenshots(app,page);page.on('pageerror',e=>errors.push(e.message));await page.waitForFunction(()=>document.querySelector('#prompt-frame').contentWindow.NbtPromptUI)
 const frame=page.frameLocator('#prompt-frame')
 const setContext=context=>frame.locator('#context-json').evaluate((input,context)=>{
  input.value=JSON.stringify({...JSON.parse(input.value),...context})
  input.dispatchEvent(new Event('input',{bubbles:true}))
 },context)
 const downloadContext=()=>frame.locator('#config').evaluate(async button=>{
  let blob
  const create=URL.createObjectURL,click=HTMLAnchorElement.prototype.click
  try{
   URL.createObjectURL=value=>{blob=value;return 'blob:context-test'}
   HTMLAnchorElement.prototype.click=function(){}
   button.click()
   return JSON.parse(await blob.text())
  }finally{URL.createObjectURL=create;HTMLAnchorElement.prototype.click=click}
 })
 const readContext=async task=>{
  const attachment=JSON.parse(await fs.readFile(path.join(task.directory,'上下文草案.json'),'utf8'))
  assert.deepEqual(attachment,task.context)
  assert.deepEqual(JSON.parse(await fs.readFile(path.join(path.dirname(task.prompt),'上下文草案.json'),'utf8')),attachment)
  assert.deepEqual(attachment,JSON.parse(task.text.split('# 验证上下文草案')[1].split('```')[1].slice(4)))
  return attachment
 }
 await frame.locator('[data-planning-step=review]').click()
 await frame.locator('[data-field=name]').fill('待交接神庙')
 await setContext({mode:'saodg',ports:[],door_y:2})
 const standaloneDownload=await downloadContext()
 await frame.locator('[data-field=theme]').fill('最后一次编辑直接交接')
 await frame.locator('#prompt-primary').click();await page.waitForFunction(()=>document.querySelector('#prompt-frame').contentDocument.querySelector('#prompt-task-state').dataset.id)
 const id=await frame.locator('#prompt-task-state').getAttribute('data-id'),found=cli(['tasks','--status','pending']);assert.equal(found.items.length,1);assert.equal(found.items[0].id,id);const task=cli(['task','--id',id]);assert.ok(task.text.includes('最后一次编辑直接交接'));assert.equal(task.approval,'not_granted_by_prompt');assert.equal(task.source_matches,null);assert.equal((await fs.readdir(task.directory)).length,5);checks.UI_creates_task_folder_and_external_skill_discovers_and_reads_latest_text=true
 const standalone=await readContext(task)
 assert.deepEqual(standalone,standaloneDownload)
 assert.equal(standalone.mode,'standalone')
 assert.equal(standalone.max_changed_blocks,4096)
 assert.ok(!Object.hasOwn(standalone,'ports')&&!Object.hasOwn(standalone,'door_y'))
 assert.ok((await frame.locator('#prompt-task-command').textContent()).endsWith(id))
 assert.equal(await frame.locator('#prompt-primary').textContent(),'复制读取命令')
 const duplicate=await page.evaluate(async()=>{
  const storage=window.nbtPromptStorage,{items}=await storage.library({action:'list'}),item=items.find(entry=>entry.published_task)
  return storage.publish({index:item.index,id:item.id,revision:item.revision})
 })
 assert.equal(duplicate.unchanged,true);assert.equal(cli(['tasks']).items.length,1);checks.duplicate_save_is_idempotent=true
 await frame.locator('#prompt-scope-active').click();assert.equal(await frame.locator('#prompt-queue-list [data-prompt-id]').count(),0)
 await frame.locator('#prompt-scope-published').click();assert.equal(await frame.locator('#prompt-queue-list [data-prompt-id]').count(),1)
 const leaseRequest=path.join(workspace,'lease-request.json')
 await fs.writeFile(leaseRequest,JSON.stringify({id,owner:'desktop test',request_id:'1'.repeat(32)}))
 const lease=cli(['claim','--request',leaseRequest])
 await frame.locator('#prompt-task-handoff').waitFor({state:'hidden'})
 assert.equal(await frame.locator('#prompt-queue-list [data-prompt-id]').count(),0)
 assert.equal(await frame.locator('#prompt-scope-published').textContent(),'待领取 0')
 assert.equal(cli(['task','--id',id]).text,task.text)
 await fs.writeFile(leaseRequest,JSON.stringify({id,lease_token:lease.lease_token,fence:lease.lease.fence,request_id:'2'.repeat(32)}))
 cli(['release','--request',leaseRequest])
 const waiting=frame.locator('#prompt-queue-list [data-prompt-id]')
 await waiting.waitFor()
 await waiting.click()
 await frame.locator('#prompt-task-handoff').waitFor({state:'visible'})
 checks.claim_hides_handoff_and_release_restores_it_without_changing_task_files=true
 await frame.locator('#prompt-scope-active').click();checks.handed_off_prompts_leave_active_queue=true
 await frame.locator('[data-planning-step=review]').click()
 await frame.locator('[data-field=name]').fill('第二座神庙')
 await setContext({mode:'standalone',openings:[{id:'old-opening'}],ports:[],door_y:2})
 await frame.locator('body').evaluate(async()=>{
  const {groups}=await parent.nbtPromptStorage.constraintRegistry([''],{id:'constraint-4ec612b39d6940d89cbcbf68314440ad'})
  await window.NbtPromptUI.applyConstraints([groups[0].items[0]])
 })
 const saodgDownload=await downloadContext()
 await frame.locator('[data-field=theme]').fill('新增第二条任务')
 await frame.locator('#prompt-primary').click();await page.waitForFunction(id=>{const actual=document.querySelector('#prompt-frame').contentDocument.querySelector('#prompt-task-state').dataset.id;return actual&&actual!==id},id)
 const next=cli(['tasks','--after',String(found.cursor)]);assert.equal(next.items.length,1);
 const saodg=await readContext(cli(['task','--id',next.items[0].id]))
 assert.deepEqual(saodg,saodgDownload)
 assert.equal(saodg.mode,'saodg')
 assert.equal(saodg.door_y,2)
 assert.deepEqual(saodg.ports,[])
 assert.equal(saodg.require_enclosure,true)
 assert.equal(saodg.openings_policy,'required')
 assert.deepEqual(saodg.opening_size,[6,5])
 assert.equal(saodg.cell_size,48)
 assert.ok(!Object.hasOwn(saodg,'openings'))
 assert.deepEqual(await readContext(cli(['task','--id',id])),standalone)
 checks.download_body_and_published_context_match_in_both_modes=true
 assert.ok(cli(['task','--id',next.items[0].id]).text.includes('新增第二条任务'));assert.ok(cli(['task','--id',id]).text.includes('最后一次编辑直接交接'));assert.throws(()=>cli(['task-status','--id',next.items[0].id,'--status','completed']),/先领取任务/);assert.equal(cli(['tasks','--status','pending']).items.length,2);checks.incremental_new_task_discovery_and_immutable_handoff=true
 await frame.locator('#prompt-scope-active').click();await frame.locator('[data-planning-step=review]').click();await frame.locator('[data-field="size.x"]').fill('');assert.equal(await frame.locator('#prompt-primary').isDisabled(),true);assert.equal(cli(['tasks']).items.length,2);await frame.locator('[data-field="size.x"]').fill('48');checks.invalid_form_cannot_publish_previous_prompt=true
 for(const [width,height] of [[1500,1000],[1000,760],[900,650]]){
  await app.evaluate(({BrowserWindow},bounds)=>{const win=BrowserWindow.getAllWindows()[0];win.setBounds(bounds);win.minimize()},{width,height});await page.setViewportSize({width:width-20,height:height-60})
  const geometry=await frame.locator('body').evaluate(()=>{const e=document.querySelector('.editor'),nav=e.querySelector('nav'),tab=document.querySelector('.tab:not([hidden])'),bar=document.querySelector('.editor-storage'),out=document.querySelector('.output'),text=document.querySelector('#result'),status=document.querySelector('#prompt-export-state'),rect=n=>n.getBoundingClientRect();return {width:innerWidth,overflow:document.documentElement.scrollWidth>innerWidth+1,navBottom:rect(nav).bottom,tabTop:rect(tab).top,tabBottom:rect(tab).bottom,barTop:rect(bar).top,textTop:rect(text).top,statusBottom:rect(status).bottom,mainDisplay:getComputedStyle(document.querySelector('main')).display,outputDisplay:getComputedStyle(out).display,editorRight:rect(e).right,outputLeft:rect(out).left}})
  assert.equal(geometry.overflow,false,JSON.stringify(geometry));assert.ok(geometry.navBottom<=geometry.tabTop+1,JSON.stringify(geometry));assert.ok(geometry.tabBottom<=geometry.barTop+1,JSON.stringify(geometry));assert.ok(geometry.textTop>=geometry.statusBottom,JSON.stringify(geometry));if(geometry.width>1240&&geometry.outputDisplay!=='none'){assert.equal(geometry.mainDisplay,'grid');assert.ok(geometry.editorRight<=geometry.outputLeft+1)};await page.screenshot();await page.waitForTimeout(150);await page.screenshot({path:path.join(output,'layout-'+width+'.png')})
 }
 checks.layout_has_no_overlapping_controls_at_three_window_sizes=true
 const beams=await frame.locator('body').evaluate(()=>{const C=window.NbtPrompt,d=C.defaults();d.project.name='梁参数一致性';d.operations=Array.from({length:20},()=>C.operation('box'));for(let i=0;i<3;i++)d.operations.push({kind:'beam',label:'不重复提供选区的梁'+i,classification:'body',start:[5,5,5+i*3],end:[15,8,5+i*3],state:'stone_bricks',width:1});return d})
 await frame.locator('#file').setInputFiles({name:'beam-plan.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(beams))});await page.waitForFunction(()=>document.querySelector('#prompt-frame').contentDocument.querySelector('#status').textContent.includes('23 个启用'))
 await frame.locator('[data-planning-step=review]').click();await frame.locator('#prompt-primary').click()
 await page.waitForFunction(()=>document.querySelector('#prompt-frame').contentDocument.querySelector('#prompt-task-state').dataset.path?.includes('梁参数一致性'));const beamFolder=await frame.locator('#prompt-task-state').getAttribute('data-path'),stored=JSON.parse(await fs.readFile(path.join(workspace,beamFolder,'方案.json'),'utf8'));assert.equal(stored.operations.length,23);assert.equal(stored.operations[20].lo,undefined);assert.deepEqual(stored.operations[22].end,[15,8,11]);checks.beams_21_to_23_import_and_publish_without_redundant_bounds=true
 await page.screenshot();await page.waitForTimeout(150);await page.screenshot({path:path.join(output,'prompt-task.png')});assert.deepEqual(errors,[]);await fs.writeFile(path.join(output,'results.json'),JSON.stringify({passed:true,checks,task_id:id},null,2));console.log(JSON.stringify({passed:true,checks:Object.keys(checks).length,output}))
}catch(error){console.error(JSON.stringify({output,checks,errors}));throw error}finally{await app?.close()}
