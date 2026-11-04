import {minimizedScreenshots} from './minimized-screenshots.mjs'
import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import path from 'node:path'
import {spawnSync} from 'node:child_process'
import {createRequire} from 'node:module'
import {root,skill,python} from '../scripts/paths.mjs'
const require=createRequire(path.join(skill,'assets/viewer/package.json')),{_electron}=require('playwright')
const output=path.join(root,'build','ai-style-ui-'+Date.now()),workspace=path.join(output,'workspace')
await fs.mkdir(path.join(workspace,'.nbtcreator'),{recursive:true});await fs.writeFile(path.join(workspace,'.nbtcreator/preferences.json'),JSON.stringify({startPage:'assets'}))
let app;const checks={}
try{
 const env={...process.env,NBTCREATOR_AUTOMATION:'1'};delete env.ELECTRON_RUN_AS_NODE
 app=await _electron.launch({executablePath:process.env.NBTCREATOR_TEST_EXE||path.join(root,'node_modules/electron/dist/electron.exe'),args:[...(process.env.NBTCREATOR_TEST_EXE?[]:[root]),'--workspace',workspace,'--user-data-dir',path.join(output,'profile')],env,timeout:60000})
 const page=await app.firstWindow();await minimizedScreenshots(app,page);const errors=[];page.on('pageerror',error=>errors.push(error.message))
 await page.waitForFunction(()=>window.creatorWorkspace?.current()==='assets');await page.locator('[data-workspace=ai]').click();await page.waitForFunction(()=>document.querySelectorAll('#internal-style-controls input[type=range]').length===4)
 await page.locator('#internal-flow').selectOption('draft');await page.locator('#ai-style-creativity').press('End');await page.locator('#ai-style-detail').press('Home');await page.locator('#internal-flow').selectOption('small_structure');await page.locator('#ai-style-creativity').press('Home');await page.locator('#ai-style-detail').press('End');await page.locator('#internal-flow').selectOption('draft')
 assert.equal(await page.locator('#ai-style-creativity').inputValue(),'100');assert.equal(await page.locator('#ai-style-detail').inputValue(),'0');checks.independent_regions_preserve_edits=true
 await page.locator('#internal-save').click();await page.waitForFunction(()=>document.querySelector('#internal-status').textContent.includes('已同步到 Skill'));await page.locator('.ai-style-settings').evaluate(el=>el.scrollIntoView({block:'start'}));await page.waitForTimeout(400);await page.screenshot({path:path.join(output,'creative-preferences.png')})
 const shared=JSON.parse(await fs.readFile(path.join(workspace,'.nbtcreator/ai-style.json'),'utf8'));assert.equal(shared.workflows.draft.creativity,100);assert.equal(shared.workflows.draft.detail,0);assert.equal(shared.workflows.small_structure.creativity,0);assert.equal(shared.workflows.small_structure.detail,100);checks.shared_file_matches_controls=true
 const entry=await fs.readFile(path.join(workspace,'.agents/skills/nbtcreator-workspace/SKILL.md'),'utf8');assert.ok(entry.includes('ai-style.json'));assert.ok(entry.includes('ai-style prompt'))
 const cli=spawnSync(python,[path.join(workspace,'.agents/skills/nbtcreator-workspace/nbt.py'),'ai-style','prompt','--workflow','draft'],{cwd:workspace,encoding:'utf8',windowsHide:true});assert.equal(cli.status,0,cli.stderr);assert.equal(JSON.parse(cli.stdout).result.values.creativity,100);checks.external_skill_reads_same_preferences=true
 await page.reload();await page.waitForFunction(()=>window.creatorWorkspace?.current()==='assets');await page.locator('[data-workspace=ai]').click();await page.waitForFunction(()=>document.querySelector('#ai-style-creativity')?.value==='100');assert.equal(await page.locator('#ai-style-detail').inputValue(),'0');assert.equal(await app.evaluate(({BrowserWindow})=>BrowserWindow.getAllWindows()[0].isMinimized()),true);assert.deepEqual(errors,[]);checks.reload_persistent_minimized_no_errors=true
 await fs.writeFile(path.join(output,'results.json'),JSON.stringify({passed:true,checks},null,2));console.log(JSON.stringify({passed:true,checks:Object.keys(checks).length,output}))
}finally{await app?.close()}
