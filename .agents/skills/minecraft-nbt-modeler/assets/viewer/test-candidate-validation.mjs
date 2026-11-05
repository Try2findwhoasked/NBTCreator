// Real browser/API coverage: exact candidate verdict, stale settings and failure diagnostics.
import fs from 'node:fs/promises'
import path from 'node:path'
import {fileURLToPath} from 'node:url'
import {parseArgs} from 'node:util'
import {execFileSync} from 'node:child_process'
import {createHash} from 'node:crypto'
import assert from 'node:assert/strict'
import {startDetailServer} from './detail-server.mjs'
import {launchRenderBrowser} from './browser-launch.mjs'

const {values}=parseArgs({options:{output:{type:'string'},python:{type:'string'}}})
if(!values.output)throw Error('Provide --output new-directory')
const out=path.resolve(values.output);await fs.mkdir(out)
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../../../../..')
const workspace=path.join(out,'workspace'),version=path.join(workspace,'nbt_models/single/候选检查/v01')
await fs.mkdir(workspace,{recursive:true})
execFileSync(values.python??'python',['-c','import runpy,sys;runpy.run_path(sys.argv[1])["make_fixture"](sys.argv[2])',path.join(root,'tests/candidate-validation.py'),version],{windowsHide:true,cwd:root})
const source=path.join(version,'master/master_geometry.json.gz'),hash=bytes=>createHash('sha256').update(bytes).digest('hex'),original=hash(await fs.readFile(source))
let server,browser;const checks={},errors=[]
try{
  server=await startDetailServer({workspace,output:path.join(out,'jobs'),python:values.python??'python'})
  browser=await launchRenderBrowser();const page=await browser.newPage({viewport:{width:1500,height:1000}})
  page.on('pageerror',e=>errors.push(e.message))
  await page.goto(server.url)
  await page.waitForFunction(()=>window.detailControl?.state.info&&!window.detailControl.state.busy,undefined,{timeout:60000})
  await page.locator('button[data-workspace=model]').click()
  await page.locator('#auto-preview').uncheck()
  await page.locator('#tool-tabs [data-tool-index="8"]').evaluate(e=>e.click())
  assert.equal(await page.locator('#validate-preview').isDisabled(),true)
  checks.no_candidate_cannot_be_checked=true
  async function operations(ops){
    await page.locator('#operation-sequence').evaluate(input=>input.closest('details').open=true)
    await page.locator('#tool-tabs [data-tool-index="8"]').evaluate(e=>e.click());await page.locator('#operation-sequence').fill(JSON.stringify(ops))
    await page.locator('#update-preview').click()
    await page.waitForFunction(()=>window.detailControl.state.preview&&!window.detailControl.state.previewBusy,undefined,{timeout:60000})
  }
  await operations([{kind:'box',label:'safe candidate',lo:[8,2,8],hi:[8,4,8],state:'stone_bricks',classification:'body'}])
  await page.locator('#validate-preview').click()
  await page.waitForFunction(()=>window.detailControl.state.candidateValidation?.passed===true&&!window.detailControl.state.busy,undefined,{timeout:60000})
  assert.ok((await page.locator('#candidate-check-state').textContent()).includes('通过'))
  const success=await page.evaluate(()=>window.detailControl.state.candidateValidation)
  assert.equal(success.changed_blocks,3);assert.equal(success.asset_written,false);assert.equal(success.approval_created,false)
  const response=await fetch(new URL(success.validation_download,server.url));assert.equal(response.status,200)
  const report=await response.json();assert.equal(report.checks.candidate_geometry.details.routes.passed,true)
  checks.actual_candidate_check_and_downloadable_report=true
  await page.locator('#tool-tabs [data-tool-index="8"]').evaluate(e=>e.click());await page.locator('#operation-sequence').fill(JSON.stringify([{kind:'box',label:'changed',lo:[8,2,8],hi:[8,4,8],state:'gold_block',classification:'body'}]))
  assert.equal(await page.locator('#validate-preview').isDisabled(),true)
  assert.equal(await page.evaluate(()=>window.detailControl.state.candidateValidation),null)
  checks.parameter_change_invalidates_old_pass=true
  await operations([{kind:'box',label:'leaking candidate',lo:[0,8,30],hi:[0,8,30],state:'air',classification:'wall'}])
  await page.locator('#validate-preview').click()
  await page.waitForFunction(()=>window.detailControl.state.candidateValidation?.passed===false&&!window.detailControl.state.busy,undefined,{timeout:60000})
  assert.equal(await page.locator('.result-panel').evaluate(e=>e.open),true)
  assert.ok((await page.locator('#result-log').textContent()).includes('未通过'))
  assert.ok((await page.locator('#candidate-check-state').textContent()).includes('未通过'))
  checks.failed_check_is_not_hidden_or_presented_as_success=true
  await page.locator('button[data-workspace=tasks]').click()
  await page.waitForFunction(()=>document.querySelectorAll('.task-entry').length>0)
  await page.locator('#task-filter').selectOption('failed')
  assert.ok((await page.locator('#task-list').textContent()).includes('检查候选效果'))
  assert.ok((await page.locator('.task-state.failed').first().textContent()).includes('未通过'))
  checks.task_filter_and_verdict_are_consistent=true
  await page.locator('button[data-workspace=model]').click()
  await page.locator('.result-panel').evaluate(e=>e.open=false)
  await page.locator('#tool-tabs [data-tool-index="8"]').evaluate(e=>e.click());await page.locator('#operation-sequence').fill(JSON.stringify([{kind:'box',label:'cancel preview',lo:[8,2,8],hi:[8,4,8],state:'stone_bricks',classification:'body'}]))
  await page.locator('#update-preview').click()
  await page.waitForFunction(()=>window.detailControl.state.previewBusy)
  assert.equal(await page.locator('#cancel').isDisabled(),false)
  await page.locator('#cancel').click()
  await page.waitForFunction(()=>!window.detailControl.state.previewBusy&&!window.detailControl.state.busy,undefined,{timeout:60000})
  assert.equal(await page.locator('.result-panel').evaluate(e=>e.open),false)
  assert.ok((await page.locator('#status').textContent()).includes('取消'))
  checks.preview_cancel_is_available_and_does_not_open_error_details=true
  await page.locator('button[data-workspace=tasks]').click()
  await page.locator('#task-filter').selectOption('cancelled')
  await page.waitForFunction(()=>document.querySelectorAll('.task-state.cancelled').length>0)
  checks.cancelled_task_has_its_own_filter_and_state=true
  assert.equal(hash(await fs.readFile(source)),original);checks.original_source_preserved=true
  assert.deepEqual(errors,[]);checks.no_renderer_errors=true
  await page.screenshot({path:path.join(out,'candidate-validation-tasks.png')})
  await fs.writeFile(path.join(out,'results.json'),JSON.stringify({passed:true,checks},null,2))
  console.log(JSON.stringify({passed:true,checks:Object.keys(checks).length,output:out}))
}finally{await browser?.close();await server?.close()}
