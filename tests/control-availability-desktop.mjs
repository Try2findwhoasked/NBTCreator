import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import path from 'node:path'
import {spawnSync} from 'node:child_process'
import {createHash} from 'node:crypto'
import {createRequire} from 'node:module'
import {root,skill,python} from '../scripts/paths.mjs'
import {minimizedScreenshots} from './minimized-screenshots.mjs'

const require=createRequire(path.join(skill,'assets/viewer/package.json')),{_electron}=require('playwright')
const output=path.join(root,'build','control-availability-'+Date.now()),workspace=path.join(output,'workspace')
const folder=path.join(workspace,'nbt_models/single/availability/v1')
const run=(args,cwd=root)=>{const result=spawnSync(python,args,{cwd,encoding:'utf8',windowsHide:true});assert.equal(result.status,0,result.stdout+result.stderr);return result.stdout}
run([path.join(root,'tests/make_fixture.py'),folder])
const recipe={schema_version:1,asset_type:'recipe',name:'跨端参数石柱',tags:[],parameters:{height:{type:'integer',default:3,min:1,max:8}},operations:[{kind:'box',label:'柱身',classification:'body',lo:[0,0,0],hi:[0,{param:'height',add:-1},0],state:'gold_block'}]}
const request=path.join(output,'recipe.json');await fs.writeFile(request,JSON.stringify(recipe))
const saved=JSON.parse(run([path.join(skill,'scripts/nbt_recipes.py'),'--workspace',workspace,'save','--file',request])).result
const toolNames=Object.keys(JSON.parse(await fs.readFile(path.join(skill,'tool-catalog.json'),'utf8')).tools)
await fs.mkdir(path.join(workspace,'.nbtcreator'),{recursive:true});await fs.writeFile(path.join(workspace,'.nbtcreator/preferences.json'),JSON.stringify({startPage:'model',autoPreview:false,disabledTools:toolNames}))
const source=path.join(folder,'synthetic.master.json.gz'),hash=bytes=>createHash('sha256').update(bytes).digest('hex'),baseline=hash(await fs.readFile(source))
let app,page;const errors=[],checks={}
async function click(selector){await page.waitForFunction(selector=>{const e=document.querySelector(selector);return e&&!e.disabled},selector);await page.locator(selector).evaluate(e=>e.click())}
async function ready(){await page.waitForFunction(()=>window.detailControl?.state.info&&!window.detailControl.state.busy&&!window.detailControl.state.sessionRestoring&&window.detailControl.state.mode==='3d')}
async function recipes(){await click('button[data-workspace=assets]');await page.locator('[data-reusable-open=recipe]').waitFor();await click('[data-reusable-open=recipe]');await page.waitForFunction(()=>!document.querySelector('#reusable-new').disabled)}
try{
 const env={...process.env,NBTCREATOR_AUTOMATION:'1'};delete env.ELECTRON_RUN_AS_NODE
 app=await _electron.launch({executablePath:process.env.NBTCREATOR_TEST_EXE||path.join(root,'node_modules/electron/dist/electron.exe'),args:[...(process.env.NBTCREATOR_TEST_EXE?[]:[root]),'--workspace',workspace,'--user-data-dir',path.join(output,'profile')],env,timeout:60000})
 page=await app.firstWindow();page.setDefaultTimeout(90000);await minimizedScreenshots(app,page);page.on('pageerror',e=>errors.push(e.message));await ready()
 assert.equal(await page.locator('#operation-add').isDisabled(),true)
 assert.equal(await page.locator('#update-download').isDisabled(),true)
 await page.evaluate(async()=>window.detailControl.runJob('snapshot'))
 assert.equal(await page.locator('#operation-add').isDisabled(),true)
 assert.equal(await page.locator('#ai-apply').isDisabled(),true)
 assert.equal(await page.locator('#update-download').isDisabled(),true)
 checks.disabled_tool_entry_and_empty_ai_result_survive_model_tasks=true
 checks.unrequested_update_download_is_not_enabled_by_unrelated_tasks=true

 await page.evaluate(()=>{const s=window.detailControl.gather();s.operations=[{kind:'box',label:'已有步骤',classification:'body',lo:[8,4,8],hi:[8,6,8],state:'stone'}];window.detailControl.restore(s)})
 assert.equal(await page.locator('.operation-name').isEnabled(),true)
 assert.equal(await page.locator('#operation-add').isDisabled(),true)
 checks.disabled_new_tools_leave_existing_steps_editable=true

 await click('#open-settings');await page.locator('[data-enabled-tool=box]').evaluate(e=>{for(let p=e.parentElement;p;p=p.parentElement)if(p.tagName==='DETAILS')p.open=true})
 await page.locator('[data-enabled-tool=box]').check();await click('#settings-save')
 await page.waitForFunction(()=>document.querySelector('#settings-status').textContent.includes('配置已保存')&&!document.querySelector('#operation-add').disabled)
 assert.equal(await page.locator('#operation-kind').inputValue(),'box');await click('#close-settings');await page.reload();await ready()
 assert.equal(await page.locator('#operation-kind').inputValue(),'box');assert.equal(await page.locator('#operation-add').isEnabled(),true)
 checks.reenabling_one_tool_restores_its_entry=true

 await recipes();await click('#reusable-new');assert.equal(await page.locator('#reusable-apply').isDisabled(),true)
 await page.evaluate(async()=>window.detailControl.runJob('snapshot'))
 assert.equal(await page.locator('#reusable-apply').isDisabled(),true)
 checks.unsaved_recipe_stays_unavailable_after_task_completion=true

 await click('[data-reusable-id="'+saved.id+'"]');await page.waitForFunction(()=>document.querySelector('#reusable-name')?.value==='跨端参数石柱'&&!document.querySelector('#reusable-apply').disabled)
 for(const [axis,value]of [[0,20],[1,4],[2,20]])await page.locator('#reusable-position-'+axis).fill(String(value))
 await page.locator('[data-recipe-param=height]').fill('4')
 const before=await page.evaluate(()=>window.detailControl.gather().operations)
 let release,seen;const waiting=new Promise(resolve=>seen=resolve)
 await page.route('**/__detail__/recipes/compile',async route=>{seen();await new Promise(resolve=>release=resolve);await route.continue()})
 await click('#reusable-apply');await waiting
 for(const selector of ['[data-recipe-param=height]','#reusable-name','#reusable-position-0','#reusable-json','#reusable-theme'])assert.equal(await page.locator(selector).isDisabled(),true)
 assert.equal(await page.locator('#reusable-close').isEnabled(),true)
 recipe.operations[0].state='andesite';await fs.writeFile(request,JSON.stringify(recipe))
 const updated=JSON.parse(run([path.join(workspace,'.agents/skills/nbtcreator-workspace/nbt.py'),'recipes','save','--id',saved.id,'--file',request],workspace)).result
 assert.notEqual(updated.revision_sha256,saved.revision_sha256)
 release();await page.waitForFunction(()=>document.querySelector('#reusable-status').textContent.includes('配方已被其他操作修改')&&!document.querySelector('#reusable-apply').disabled);await page.unroute('**/__detail__/recipes/compile')
 assert.deepEqual(await page.evaluate(()=>window.detailControl.gather().operations),before)
 checks.inflight_recipe_fields_are_locked_and_stale_external_revision_is_rejected=true

 await click('[data-reusable-id="'+saved.id+'"]');await page.waitForFunction(()=>!document.querySelector('#reusable-apply').disabled)
 for(const [axis,value]of [[0,20],[1,4],[2,20]])await page.locator('#reusable-position-'+axis).fill(String(value))
 await click('#reusable-apply');await page.waitForFunction(count=>document.body.dataset.workspace==='model'&&!window.detailControl.state.commitBusy&&!window.detailControl.state.previewBusy&&window.detailControl.gather().operations.length===count+1,before.length)
 const last=await page.evaluate(()=>window.detailControl.gather().operations.at(-1));assert.equal(last.state.replace(/^minecraft:/,''),'andesite')
 assert.equal(await page.evaluate(()=>document.querySelector('#viewer').contentWindow.nbtModeler.snapshot.master_blocks.find(([p])=>p.join(',')==='20,4,20')?.[1]),'minecraft:andesite')
 checks.rereading_recipe_allows_actual_candidate_preview_of_new_revision=true
 assert.equal(hash(await fs.readFile(source)),baseline);assert.deepEqual(errors,[])
 await fs.writeFile(path.join(output,'results.json'),JSON.stringify({passed:true,checks},null,2));console.log(JSON.stringify({passed:true,checks,output}))
}catch(error){console.error(JSON.stringify({output,checks,errors,status:await page?.locator('#reusable-status').textContent().catch(()=>null)}));throw error}finally{await app?.close()}
