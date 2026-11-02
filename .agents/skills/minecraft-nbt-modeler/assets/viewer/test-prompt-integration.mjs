// Synthetic integration only: no user assets or approval records changed.
import fs from 'node:fs/promises'
import path from 'node:path'
import assert from 'node:assert/strict'
import {createHash} from 'node:crypto'
import {startDetailServer} from './detail-server.mjs'
import {launchRenderBrowser} from './browser-launch.mjs'
const [fixture,outputArg]=process.argv.slice(2)
if(!fixture||!outputArg)throw Error('Pass fixture directory and NEW output directory')
const output=path.resolve(outputArg);await fs.mkdir(output)
const workspace=path.join(output,'workspace'),modelRoot=path.join(workspace,'nbt_models/sample/master')
await fs.mkdir(modelRoot,{recursive:true})
const source=path.join(modelRoot,'synthetic.master.json.gz'),contextFile=path.join(modelRoot,'coordinates.json')
await fs.copyFile(path.join(fixture,'基线 空格.master.json.gz'),source)
await fs.copyFile(path.join(fixture,'context.json'),contextFile)
const original=await fs.readFile(source),hash=bytes=>createHash('sha256').update(bytes).digest('hex')
let app,browser;const checks={}
try{
 app=await startDetailServer({workspace,output:path.join(output,'jobs')})
 browser=await launchRenderBrowser();const page=await browser.newPage({viewport:{width:1440,height:1000},acceptDownloads:true}),errors=[]
 page.on('pageerror',e=>errors.push(e.message));await page.goto(app.url)
 await page.waitForFunction(()=>window.detailControl?.state.info&&!window.detailControl.state.busy,undefined,{timeout:60000})
 await page.locator('#auto-preview').uncheck()
 await page.evaluate(()=>{const c=window.detailControl,s=c.gather();s.pattern.enabled=true;s.pattern.fraction=.23;s.style_note='集成回归统一石构';s.whole_region=false;s.lo=[2,4,2];s.hi=[20,12,20];c.restore(s)})
 await page.locator('button[data-workspace=prompt]').click()
 await page.waitForFunction(()=>document.querySelector('#prompt-sync-status').textContent.startsWith('已载入'),undefined,{timeout:30000})
 const frame=page.frameLocator('#prompt-frame')
 const text=await frame.locator('#result').inputValue()
 assert.ok(text.includes(source));assert.ok(text.includes(hash(original)));assert.ok(text.includes('集成回归统一石构'))
 assert.ok(text.includes('"fraction": 0.23'));assert.ok(text.includes('只读检查与修改规划'))
 const context=JSON.parse(await frame.locator('#context-json').inputValue());assert.ok(context.start);assert.ok(context.interior_probes.length)
 checks.current_model_settings_region_context_bound=true
 const downloadPromise=page.waitForEvent('download');await frame.locator('#plan').click();await (await downloadPromise).saveAs(path.join(output,'plan.json'))
 const plan=JSON.parse(await fs.readFile(path.join(output,'plan.json'),'utf8'));assert.equal(plan.operations[0].fraction,.23);assert.deepEqual(plan.operations[0].lo,[2,4,2]);checks.backend_compiler_matches_download=true
 await frame.locator('[data-field=name]').fill('保留的设计要求')
 await page.locator('#close-prompt').click();assert.equal(await page.locator('#prompt-dialog').isVisible(),false)
 await page.locator('button[data-workspace=prompt]').click();assert.equal(await frame.locator('[data-field=name]').inputValue(),'保留的设计要求');checks.close_reopen_keeps_edits=true
 await frame.getByRole('button',{name:/02 工具序列/}).click();await frame.locator('#kind').selectOption('explosion');await frame.locator('#add').click()
 assert.equal(await frame.locator('.step').count(),2)
 assert.equal(await page.evaluate(()=>window.detailControl.gather().pattern.fraction),.23);checks.prompt_edits_do_not_apply_to_model=true
 await page.locator('#sync-prompt').click();await page.waitForFunction(()=>document.querySelector('#prompt-sync-status').textContent.startsWith('已载入'))
 assert.equal(await frame.locator('.step').count(),1)
 assert.equal(await frame.locator('[data-field=name]').inputValue(),'保留的设计要求');checks.explicit_sync_preserves_design_and_refreshes_operations=true
 await page.screenshot({path:path.join(output,'integrated.png')})
 await page.setViewportSize({width:390,height:844})
 assert.ok(await page.evaluate(()=>document.querySelector('#prompt-dialog').getBoundingClientRect().width<=innerWidth))
 assert.ok(await frame.locator('body').evaluate(()=>document.documentElement.scrollWidth<=innerWidth));checks.narrow_panel_layout=true
 await page.setViewportSize({width:1440,height:1000})
 await page.locator('#close-prompt').click()
 const responses=await page.evaluate(async()=>{const request=window.detailControl.request();const send=(data,headers={})=>fetch('/__detail__/prompt-export',{method:'POST',headers:{'Content-Type':'application/json',...headers},body:JSON.stringify(data)}).then(r=>r.status);return {stale:await send({...request,source_sha256:'stale'}),invalid:await send({...request,settings:{...request.settings,strength:999}})}})
 assert.equal(responses.stale,400);assert.equal(responses.invalid,400);checks.stale_source_and_invalid_settings_rejected=true
 const denied=await fetch(new URL('/__detail__/prompt-export',app.url),{method:'POST',headers:{Origin:'http://example.com'},body:'{}'});assert.equal(denied.status,403)
 const traversal=await fetch(new URL('/__detail__/prompt/no-file.js',app.url));assert.equal(traversal.status,400);checks.origin_and_static_allowlist=true
 await fs.writeFile(source,Buffer.concat([original,Buffer.from('changed')]))
 await page.locator('button[data-workspace=prompt]').click();await page.locator('#sync-prompt').click()
 await page.waitForFunction(()=>document.querySelector('#prompt-sync-status').textContent.includes('版本已改变'))
 await fs.writeFile(source,original);checks.changed_disk_source_rejected=true
 assert.equal(hash(await fs.readFile(source)),hash(original));assert.deepEqual(errors,[])
 assert.equal((await fs.readdir(path.join(output,'jobs'))).includes('approval.json'),false)
 checks.original_unchanged_and_no_browser_errors=true
 await fs.writeFile(path.join(output,'results.json'),JSON.stringify({passed:true,checks},null,2))
 console.log(JSON.stringify({passed:true,checks:Object.keys(checks).length,output}))
}finally{await browser?.close();await app?.close()}
