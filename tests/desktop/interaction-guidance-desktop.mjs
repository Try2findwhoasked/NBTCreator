import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import path from 'node:path'
import {createRequire} from 'node:module'
import {root,skill} from '../../scripts/paths.mjs'
import {minimizedScreenshots} from '../support/minimized-screenshots.mjs'
const require=createRequire(path.join(skill,'assets/viewer/package.json')),{_electron}=require('playwright')
const output=path.join(root,'build','interaction-guidance-'+Date.now()),workspace=path.join(output,'workspace')
await fs.mkdir(path.join(workspace,'.nbtcreator'),{recursive:true})
await fs.writeFile(path.join(workspace,'.nbtcreator/preferences.json'),JSON.stringify({startPage:'project',autoPreview:false}))
let app,page;const errors=[],checks={}
try {
 const env={...process.env,NBTCREATOR_AUTOMATION:'1'};delete env.ELECTRON_RUN_AS_NODE
 app=await _electron.launch({executablePath:path.join(root,'node_modules/electron/dist/electron.exe'),args:[root,'--workspace',workspace,'--user-data-dir',path.join(output,'profile')],env,timeout:60000})
 page=await app.firstWindow();page.setDefaultTimeout(60000);await minimizedScreenshots(app,page);page.on('pageerror',error=>errors.push(error.message))
 await page.waitForFunction(()=>window.detailControl?.state.catalogReady&&!window.detailControl.state.busy)
 await page.locator('.project-empty button').click()
 const frame=page.frameLocator('#prompt-frame')
 await page.waitForFunction(()=>document.querySelector('#prompt-frame').contentDocument?.body?.dataset.promptReady==='true')
 await frame.locator('#prompt-ai-settings').click();await page.waitForFunction(()=>document.body.dataset.workspace==='ai')
 await page.locator('#close-api').click();await page.waitForFunction(()=>document.body.dataset.workspace==='prompt')
 assert.equal(await page.locator('#close-prompt').textContent(),'返回建筑库')
 checks.ai_settings_preserves_planning_return_path=true
 await frame.locator('#prompt-write-manually').click()
 assert.equal(await frame.locator('#project-fields').isVisible(),true)
 await frame.locator('[data-field=name]').fill('手填的第一座建筑')
 await page.waitForFunction(()=>document.querySelector('#prompt-frame').contentDocument.querySelector('#prompt-editor-save-state').textContent==='已自动保存')
 assert.equal(await frame.locator('#prompt-review-state').textContent(),'待审查')
 assert.match(await frame.locator('#planning-next').textContent(),/核对/)
 checks.manual_first_design_saves_without_ai_or_handoff=true
 await frame.locator('[data-planning-step=handoff]').click();assert.equal(await frame.locator('#result').isVisible(),true)
 assert.equal(await frame.locator('#prompt-review-state').textContent(),'待审查')
 await frame.locator('[data-planning-step=review]').click();assert.equal(await frame.locator('#project-fields').isVisible(),true)
 checks.viewing_handoff_does_not_publish_or_approve=true
 for(const width of [768,390]) {
  await page.setViewportSize({width,height:800})
  const overflow=await page.evaluate(()=>({shell:document.documentElement.scrollWidth>innerWidth+1,prompt:document.querySelector('#prompt-frame').contentDocument.documentElement.scrollWidth>document.querySelector('#prompt-frame').contentWindow.innerWidth+1}))
  assert.deepEqual(overflow,{shell:false,prompt:false},JSON.stringify({width,overflow}))
  await page.screenshot({path:path.join(output,'planning-'+width+'.png')})
 }
 await page.locator('#close-prompt').click();await page.waitForFunction(()=>document.body.dataset.workspace==='project')
 await page.locator('[data-workspace=model]').click();assert.match(await page.locator('#journey-title').textContent(),/从一座建筑开始/)
 assert.equal(await page.locator('#export-revision').isDisabled(),true)
 await page.locator('#studio-inspector-toggle').click()
 assert.equal(await page.locator('#studio-browse-projects').isVisible(),true)
 await page.screenshot({path:path.join(output,'empty-editor-390.png')})
 checks.narrow_layout_and_return_navigation=true
 await page.setViewportSize({width:1000,height:760});await page.locator('[data-workspace=tasks]').click()
 await page.locator('#task-search').fill('不存在的任务')
 await page.locator('.task-empty button').click();assert.equal(await page.locator('#task-search').inputValue(),'')
 checks.empty_task_search_can_reset=true
 assert.deepEqual(errors,[])
 await fs.writeFile(path.join(output,'results.json'),JSON.stringify({passed:true,checks},null,2))
 console.log(JSON.stringify({passed:true,checks,output}))
} catch(error) {
 console.error(JSON.stringify({output,checks,errors}))
 if(page)await page.screenshot({path:path.join(output,'failure.png')}).catch(()=>{})
 throw error
} finally {await app?.close()}
