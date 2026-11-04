import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import path from 'node:path'
import {spawnSync} from 'node:child_process'
import {createHash} from 'node:crypto'
import {createRequire} from 'node:module'
import {root,skill,python} from '../scripts/paths.mjs'
import {minimizedScreenshots} from './minimized-screenshots.mjs'
const require=createRequire(path.join(skill,'assets/viewer/package.json')),{_electron}=require('playwright')
const output=path.join(root,'build','operation-history-'+Date.now()),workspace=path.join(output,'workspace'),sample=path.join(workspace,'nbt_models/sample')
const fixture=spawnSync(python,[path.join(root,'tests/make_fixture.py'),sample],{encoding:'utf8',windowsHide:true});assert.equal(fixture.status,0,fixture.stderr)
const source=path.join(sample,'synthetic.master.json.gz'),hash=bytes=>createHash('sha256').update(bytes).digest('hex'),before=hash(await fs.readFile(source))
await fs.mkdir(path.join(workspace,'.nbtcreator'),{recursive:true});await fs.writeFile(path.join(workspace,'.nbtcreator/preferences.json'),JSON.stringify({startPage:'model',autoPreview:false}))
let app;const checks={}
try{
 const env={...process.env,NBTCREATOR_AUTOMATION:'1'};delete env.ELECTRON_RUN_AS_NODE
 app=await _electron.launch({executablePath:process.env.NBTCREATOR_TEST_EXE||path.join(root,'node_modules/electron/dist/electron.exe'),args:[...(process.env.NBTCREATOR_TEST_EXE?[]:[root]),'--workspace',workspace,'--user-data-dir',path.join(output,'profile')],env,timeout:60000})
 const page=await app.firstWindow();await minimizedScreenshots(app,page);const errors=[];page.on('pageerror',error=>errors.push(error.message));page.setDefaultTimeout(60000)
 await page.waitForFunction(()=>window.detailControl?.state.info&&!window.detailControl.state.busy)
 await page.getByRole('button',{name:'建模工具',exact:true}).evaluate(el=>el.click());await page.locator('#auto-preview').uncheck()
 assert.equal(await page.locator('#operation-sequence').isVisible(),false);assert.equal(await page.locator('.operation-row').count(),0);checks.compact_list_and_advanced_json=true
 const activate=selector=>page.locator(selector).evaluate(el=>el.click())
 async function add(name,state){await page.locator('#operation-kind').selectOption('box');await activate('#operation-add');const row=page.locator('.operation-row').last();await row.locator('details').evaluate(el=>el.open=true);await row.locator('textarea').fill(JSON.stringify({kind:'box',label:name,classification:'body',lo:[10,4,10],hi:[10,6,10],state}));await row.getByRole('button',{name:'应用本步骤参数'}).evaluate(el=>el.click())}
 const operations=()=>page.evaluate(()=>window.detailControl.gather().operations)
 async function preview(){const previous=await page.evaluate(()=>window.detailControl.state.preview?.snapshot);await activate('#update-preview');await page.waitForFunction(previous=>!window.detailControl.state.previewBusy&&window.detailControl.state.preview?.snapshot!==previous&&window.detailControl.state.previewSettings===JSON.stringify(window.detailControl.gather()),previous);const result=await page.evaluate(()=>window.detailControl.state.preview);const snapshot=JSON.parse(await fs.readFile(result.snapshot,'utf8'));return {result,blocks:new Map(snapshot.master_blocks.map(([p,state])=>[p.join(','),state]))}}
 await add('石柱','stone_bricks');await add('柱头材质','gold_block');assert.equal((await operations()).length,2);let candidate=await preview();assert.equal(candidate.blocks.get('10,4,10'),'minecraft:gold_block');checks.ordered_steps_actual_candidate=true
 await activate('.operation-row:last-child input[type=checkbox]');assert.equal((await operations())[1].enabled,false);candidate=await preview();assert.equal(candidate.blocks.get('10,4,10'),'minecraft:stone_bricks');checks.disabled_step_not_written=true
 await activate('.operation-row:first-child input[type=checkbox]');candidate=await preview();assert.equal(candidate.result.changed_blocks,0);assert.equal(candidate.blocks.has('10,4,10'),false);assert.ok((await page.locator('#operation-summary').textContent()).includes('0 项启用'));checks.all_disabled_restores_baseline=true
 await activate('.operation-row:first-child input[type=checkbox]');await activate('.operation-row:last-child input[type=checkbox]');await activate('.operation-row:last-child [data-action=up]');candidate=await preview();assert.equal(candidate.blocks.get('10,4,10'),'minecraft:stone_bricks');checks.reorder_recomputes_from_same_source=true
 await page.locator('.operation-name').first().fill('金色柱头');await page.locator('.operation-name').first().evaluate(el=>el.dispatchEvent(new Event('change',{bubbles:true})));assert.equal((await operations())[0].label,'金色柱头')
 await activate('.operation-row:first-child [data-action=copy]');assert.equal((await operations()).length,3);await activate('.operation-row:nth-child(2) [data-action=remove]');assert.equal((await operations()).length,2);checks.rename_copy_remove=true
 const latest=await operations();await activate('#undo-settings');assert.equal((await operations()).length,3);await activate('#redo-settings');assert.deepEqual(await operations(),latest);checks.undo_redo_restore_operations=true
 await activate('#open-settings-history');await page.locator('.history-rename').last().evaluate(el=>el.click());await page.locator('#history-name').fill('柱头候选 A');await activate('#history-name-save');await page.waitForFunction(()=>!document.querySelector('#history-rename-dialog').open);assert.ok((await page.locator('#history-current').textContent()).includes('柱头候选 A'));await page.waitForTimeout(300);await page.screenshot({path:path.join(output,'named-history.png')});checks.named_history=true
 await activate('[data-history-index="0"]');assert.equal((await operations()).length,0);await activate('#close-settings-history');await page.locator('#operation-kind').selectOption('box');await activate('#operation-add');assert.equal(await page.locator('#redo-settings').isDisabled(),true);checks.jump_and_new_branch_discards_redo=true
 await page.evaluate(()=>document.activeElement?.blur());await page.keyboard.press('Control+z');assert.equal((await operations()).length,0);await page.keyboard.press('Control+Shift+z');assert.equal((await operations()).length,1);checks.keyboard_history_outside_text=true
 await page.locator('#operation-sequence').evaluate(el=>el.closest('details').open=true);await page.locator('#operation-sequence').fill('{invalid');assert.ok((await page.locator('#operation-summary').textContent()).includes('修正完整 JSON'));await activate('#undo-settings');assert.deepEqual(await operations(),[]);checks.invalid_json_recoverable=true
 await page.locator('#settings').evaluate(el=>el.scrollTop=0);await page.waitForTimeout(300);await page.screenshot({path:path.join(output,'operation-history.png')});assert.equal(hash(await fs.readFile(source)),before);assert.deepEqual(errors,[]);assert.equal(await app.evaluate(({BrowserWindow})=>BrowserWindow.getAllWindows()[0].isMinimized()),true);checks.minimized_original_unchanged_no_errors=true
 await fs.writeFile(path.join(output,'results.json'),JSON.stringify({passed:true,checks},null,2));console.log(JSON.stringify({passed:true,checks:Object.keys(checks).length,output}))
}catch(error){console.error(JSON.stringify({output,checks}));throw error}finally{await app?.close()}
