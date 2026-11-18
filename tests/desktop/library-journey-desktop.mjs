import assert from 'node:assert/strict'
import {positionComponent,confirmComponent} from '../support/component-placement.mjs'
import fs from 'node:fs/promises'
import path from 'node:path'
import {createRequire} from 'node:module'
import {execFileSync} from 'node:child_process'
import {root,skill,python} from '../../scripts/paths.mjs'
import {minimizedScreenshots} from '../support/minimized-screenshots.mjs'

const output=path.join(root,'build','library-journey-'+Date.now())
const workspace=path.join(output,'workspace')
const require=createRequire(path.join(skill,'assets/viewer/package.json'))
const {_electron}=require('playwright')
for(const version of ['v1','v2']){
 const dir=path.join(workspace,'nbt_models/single/hall',version)
 execFileSync(python,[path.join(root,'tests/support/make_fixture.py'),dir],{windowsHide:true})
}
execFileSync(python,['-c',`import sys
sys.path.insert(0,sys.argv[1])
from nbt_components import store
for i,name in enumerate(['白石柱','青石柱']):
 store(sys.argv[2],dict(schema_version=1,name=name,tags=['石柱'],size=[1,i+2,1],anchor=[0,0,0],palette=['stone'],blocks=[[0,y,0,0,False] for y in range(i+2)]))
`,path.join(skill,'scripts'),workspace],{windowsHide:true})
await fs.mkdir(path.join(workspace,'.nbtcreator'),{recursive:true})
await fs.writeFile(path.join(workspace,'.nbtcreator/preferences.json'),JSON.stringify({startPage:'project',autoPreview:false,previewMode:'images'}))
let app,page
const errors=[],checks={}
try{
 const env={...process.env,NBTCREATOR_AUTOMATION:'1'};delete env.ELECTRON_RUN_AS_NODE
 app=await _electron.launch({executablePath:process.env.NBTCREATOR_TEST_EXE||path.join(root,'node_modules/electron/dist/electron.exe'),args:[...(process.env.NBTCREATOR_TEST_EXE?[]:[root]),'--workspace',workspace,'--user-data-dir',path.join(output,'profile')],env,timeout:60000})
 page=await app.firstWindow();await minimizedScreenshots(app,page);page.setDefaultTimeout(45000)
 page.on('pageerror',error=>errors.push(error.message))
 const click=selector=>page.locator(selector).click()
 async function capture(name){
  await page.screenshot();await page.waitForTimeout(230);await page.screenshot({path:path.join(output,name+'.png')})
 }
 const dialog=page.locator('.library-comparison[open]')
 async function compare(kind){
  const tray=page.locator('.library-tray[data-library-kind="'+kind+'"]')
  await tray.getByRole('button',{name:'并排比较'}).click()
  await dialog.waitFor()
  assert.equal(await dialog.locator('thead th').count(),3)
 }
 await page.waitForSelector('#project-grid .project-card')
 await page.setViewportSize({width:1280,height:800})
 assert.equal(await page.locator('#project-generate-thumbnails').isVisible(),false)
 assert.equal(await page.locator('#project-grid .library-choice-mark:visible').count(),0)
 await page.setViewportSize({width:600,height:760});await click('#project-workspace .library-tree-toggle')
 assert.equal(await page.locator('#project-tree').isVisible(),true);await page.keyboard.press('Escape')
 assert.equal(await page.locator('#project-tree').isVisible(),false)
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false)
 await page.setViewportSize({width:1280,height:800});await capture('buildings')
 await click('#project-workspace .library-compare-mode')
 await click('#project-grid [data-compare-id]')
 await page.selectOption('#project-quick-version','older')
 await click('#project-grid [data-compare-id]')
 await compare('建筑版本')
 assert.ok(await dialog.locator('tr[data-different=true]').count()>0)
 await page.waitForFunction(()=>document.querySelectorAll('.library-comparison[open] img').length===2)
 await capture('building-comparison')
 await dialog.getByRole('button',{name:'查看三维差异'}).click()
 await page.waitForFunction(()=>window.detailControl.state.versionComparing&&!window.detailControl.state.busy)
 await click('#end-version-compare')
 await page.waitForFunction(()=>!window.detailControl.state.versionComparing&&!window.detailControl.state.busy)
 checks.compare_versions_across_filters_in_3d=true

 await click('button[data-workspace=assets]')
 await click('#asset-kind-components');await page.waitForSelector('#asset-grid .asset-card')
 await click('#asset-filters-menu>summary');await page.selectOption('#asset-source-filter','local');await page.keyboard.press('Escape')
 await capture('components')
 assert.equal(await page.locator('#asset-create-agent').isVisible(),false)
 await click('#asset-library-menu > summary');assert.equal(await page.locator('#asset-create-agent').isVisible(),true);await page.keyboard.press('Escape')
 await click('#asset-filters-menu > summary');await page.selectOption('#asset-sort','blocks');await click('#asset-filters-menu > summary')
 await click('#asset-workspace .library-compare-mode[data-library-kind=构件]')
 await page.waitForFunction(()=>document.querySelectorAll('#asset-grid [data-compare-id]').length===2)
 await page.locator('#asset-grid [data-compare-id]').first().click()
 await page.locator('#asset-search').fill('青石')
 await click('#asset-grid [data-compare-id]')
 await compare('构件')
 assert.ok(await dialog.getByRole('row',{name:/方块数/}).textContent().then(text=>text.includes('2')&&text.includes('3')))
 await capture('component-comparison')
 await dialog.getByRole('button',{name:'查看与放置'}).last().click()
 assert.equal(await page.locator('#asset-name').textContent(),'青石柱')
 const needsTarget=await page.locator('#asset-place').textContent()==='选择目标建筑'
 await click('#asset-place')
 if(needsTarget){
  await page.waitForSelector('.library-target-request:not([hidden])')
  await page.selectOption('#project-quick-version','latest')
  await click('#project-grid .project-card-edit')
 }
 await positionComponent(page,[16,4,16]);await capture('placement');await confirmComponent(page)
 await page.waitForFunction(()=>document.body.dataset.workspace==='model'&&window.detailControl.state.preview&&!window.detailControl.state.commitBusy)
 checks.select_target_returns_to_chosen_component_and_previews=true
 await click('button[data-workspace=assets]')
 await click('#asset-kind-effects')
 await page.locator('#asset-search').fill('')
 const effects=page.locator('#effect-assets-grid [data-compare-id]')
 await click('#asset-workspace .library-compare-mode[data-library-kind=效果预设]')
 await effects.nth(0).click();await effects.nth(1).click()
 await compare('效果预设')
 await dialog.getByRole('button',{name:'返回列表'}).click()
 await click('#asset-kind-patterns')
 const patterns=page.locator('#pattern-assets-grid [data-compare-id]')
 await click('#asset-workspace .library-compare-mode[data-library-kind=纹样]')
 await patterns.nth(0).click();await patterns.nth(1).click()
 await compare('纹样')
 await dialog.getByRole('button',{name:'查看与拟合'}).first().click()
 await page.waitForSelector('#pattern-assets-dialog[open]')
 checks.effect_and_pattern_comparisons_are_independent=true
 assert.deepEqual(errors,[])
 console.log(JSON.stringify({passed:true,output,checks}))
}catch(error){
 console.error(JSON.stringify({output,checks,errors,state:await page?.evaluate(()=>({page:document.body.dataset.workspace,dialogs:[...document.querySelectorAll('dialog[open]')].map(e=>e.id),project:document.querySelector('#project-status')?.textContent,status:document.querySelector('#status')?.textContent})).catch(()=>null)}))
 await page?.screenshot({path:path.join(output,'failure.png')}).catch(()=>{})
 throw error
}finally{await app?.close()}
