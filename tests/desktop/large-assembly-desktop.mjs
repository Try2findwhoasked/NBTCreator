import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import path from 'node:path'
import {spawnSync} from 'node:child_process'
import {createRequire} from 'node:module'
import {root,skill,python} from '../../scripts/paths.mjs'
import {minimizedScreenshots} from '../support/minimized-screenshots.mjs'

const require=createRequire(path.join(skill,'assets/viewer/package.json')),{_electron}=require('playwright')
const output=path.join(root,'build','large-assembly-desktop-'+Date.now()),workspace=path.join(output,'workspace')
await fs.mkdir(workspace,{recursive:true})
const script=`import sys;from pathlib import Path;sys.path.insert(0,sys.argv[2]);from nbt_large_assembly import AssemblyVolume,save_assembly;m=AssemblyVolume((300,384,300));m.put((2,2,2),'stone');m.put((299,295,299),'gold_block');save_assembly(Path(sys.argv[1])/'nbt_models/standalone/组装测试/v01/master',m,{(2,2,2)},[dict(offset=[0,0,0],size=[6,6,6]),dict(offset=[294,294,294],size=[6,90,6])])`
const fixture=spawnSync(python,['-B','-c',script,workspace,path.join(skill,'scripts')],{encoding:'utf8',windowsHide:true})
assert.equal(fixture.status,0,fixture.stderr)
const source=path.join(workspace,'nbt_models/standalone/组装测试/v01/master/assembly.json'),original=await fs.readFile(source)
let app,page;const errors=[],checks={}
try {
  const env={...process.env,NBTCREATOR_AUTOMATION:'1'};delete env.ELECTRON_RUN_AS_NODE
  app=await _electron.launch({executablePath:process.env.NBTCREATOR_TEST_EXE||path.join(root,'node_modules/electron/dist/electron.exe'),
    args:[...(process.env.NBTCREATOR_TEST_EXE?[]:[root]),'--workspace',workspace,'--user-data-dir',path.join(output,'profile')],env,timeout:60000})
  page=await app.firstWindow();page.setDefaultTimeout(60000);await minimizedScreenshots(app,page)
  page.on('pageerror',error=>errors.push(error.message))
  await page.waitForFunction(()=>window.detailControl?.state.catalogReady&&!window.detailControl.state.busy)
  await page.waitForFunction(()=>document.querySelectorAll('.project-card-preview').length===1)
  await page.locator('.project-card-preview').first().evaluate(element=>element.click())
  await page.waitForFunction(()=>!document.querySelector('#project-preview-3d').hidden&&document.querySelector('#project-preview-3d').contentWindow.nbtModeler?.status==='ready',null,{timeout:30000})
  assert.ok((await page.locator('#project-preview-location').textContent()).includes('assembly.json'))
  checks.aggregate_source_is_listed_once_and_previewed=true
  await page.locator('#project-preview-edit').evaluate(element=>element.click())
  await page.waitForFunction(()=>window.detailControl.state.info&&!window.detailControl.state.busy)
  const info=await page.evaluate(()=>window.detailControl.state.info)
  assert.equal(info.editing_ready,false)
  assert.match(info.context_readiness.errors.join(' '),/桌面编辑尚未接入/)
  checks.editor_reports_read_only_boundary=true
  assert.deepEqual(await fs.readFile(source),original);assert.deepEqual(errors,[])
  await fs.writeFile(path.join(output,'results.json'),JSON.stringify({passed:true,checks},null,2))
  console.log(JSON.stringify({passed:true,checks,output}))
} catch(error) {
  if(page) {
    try {console.error(JSON.stringify({output,checks,errors,diagnostic:await page.evaluate(()=>({
      status:document.querySelector('#status')?.textContent,project:document.querySelector('#project-preview-status')?.textContent,
      cards:document.querySelectorAll('.project-card-preview').length,busy:window.detailControl?.state.busy,
      catalogReady:window.detailControl?.state.catalogReady,info:window.detailControl?.state.info?.context_readiness}))}))} catch {}
  }
  throw error
} finally {await app?.close()}
