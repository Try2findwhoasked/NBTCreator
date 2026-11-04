import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import path from 'node:path'
import {spawnSync} from 'node:child_process'
import {createRequire} from 'node:module'
import {createHash} from 'node:crypto'
import {root,skill,python} from '../scripts/paths.mjs'
import {minimizedScreenshots} from './minimized-screenshots.mjs'
const require=createRequire(path.join(skill,'assets/viewer/package.json')),{_electron}=require('playwright')
const output=path.join(root,'build','project-recovery-'+Date.now()),workspace=path.join(output,'workspace')
const setup=spawnSync(python,['-c',`import sys,gzip,json
from pathlib import Path
sys.path.insert(0,sys.argv[1]);from nbt_assembly import Volume;from nbt_refine import save_master
root=Path(sys.argv[2]);m=Volume((8,8,8));m.box([0,0,0],[7,0,7],'stone_bricks');m.box([2,1,2],[2,4,2],'stone_bricks')
for i in range(30):
 p=root/'nbt_models/single'/('regular_%02d'%i)/'v1';p.mkdir(parents=True);save_master(p/'source.master.json.gz',m,set())
p=root/'nbt_models/bugged/broken_hash';p.mkdir(parents=True);save_master(p/'source.master.json.gz',m,{(2,1,2)})
f=p/'source.master.json.gz';d=json.loads(gzip.decompress(f.read_bytes()));d['geometry_sha256']='0'*64;f.write_bytes(gzip.compress(json.dumps(d).encode()))
p=root/'nbt_models/bugged/cannot_repair';p.mkdir(parents=True);(p/'source.master.json.gz').write_bytes(b'invalid gzip')
`,path.join(skill,'scripts'),workspace],{encoding:'utf8',windowsHide:true});assert.equal(setup.status,0,setup.stderr)
const broken=path.join(workspace,'nbt_models/bugged/broken_hash/source.master.json.gz'),hash=async file=>createHash('sha256').update(await fs.readFile(file)).digest('hex'),before=await hash(broken)
let app,page;const errors=[],checks={};const click=id=>page.locator('#'+id).evaluate(e=>e.click())
async function search(value){await page.locator('#project-search').fill(value);await page.waitForTimeout(250);await page.waitForFunction(value=>[...document.querySelectorAll('.project-card')].every(e=>e.dataset.source.includes(value)),value)}
try{
 const env={...process.env,NBTCREATOR_AUTOMATION:'1'};delete env.ELECTRON_RUN_AS_NODE
 app=await _electron.launch({executablePath:process.env.NBTCREATOR_TEST_EXE||path.join(root,'node_modules/electron/dist/electron.exe'),args:[...(process.env.NBTCREATOR_TEST_EXE?[]:[root]),'--workspace',workspace,'--user-data-dir',path.join(output,'profile')],env,timeout:60000});page=await app.firstWindow();page.setDefaultTimeout(60000);minimizedScreenshots(app,page);page.on('pageerror',e=>errors.push(e.message));await page.waitForFunction(()=>window.detailControl?.state.catalogReady&&document.querySelectorAll('.project-card').length>=24)
 assert.equal(await page.locator('#project-auto-more').isChecked(),true);await page.locator('#project-workspace .library-main').evaluate(e=>e.scrollTop=e.scrollHeight);await page.waitForFunction(()=>document.querySelectorAll('.project-card').length>24);checks.scroll_appends_more_cards_by_default=true
 await search('regular_00');await click('project-generate-thumbnails');await page.waitForFunction(()=>document.querySelector('#project-status').textContent.includes('缩略图已完成'));await page.waitForFunction(()=>document.querySelector('.project-cover img')?.complete);checks.explicit_generation_loads_real_thumbnail=true
 await search('broken_hash');await page.locator('.project-card-manage').evaluate(e=>e.click());await page.locator('.project-repair-category').selectOption('square');await page.locator('#project-manage-dialog .project-repair').evaluate(e=>e.click());await page.waitForFunction(()=>document.querySelector('#project-status').textContent.includes('已生成归类候选'));const status=await page.locator('#project-status').textContent();assert.ok(status.includes('nbt_models/square/recovered_broken_hash/'));await page.waitForFunction(()=>[...document.querySelectorAll('.project-card')].some(e=>e.dataset.source.includes('recovered_broken_hash')));assert.equal(await hash(broken),before);checks.repair_reclassifies_new_candidate_and_refreshes_library=true;await click('project-manage-close')
 await click('project-clear');await search('cannot_repair');await page.locator('.project-card-manage').evaluate(e=>e.click());await page.locator('#project-manage-dialog .project-repair').evaluate(e=>e.click());await page.waitForFunction(()=>document.querySelector('#project-status').textContent.includes('未能自动恢复'));assert.ok((await page.locator('#project-status').textContent()).includes('.nbtcreator/repairs/'));assert.equal((await fs.readFile(path.join(workspace,'nbt_models/bugged/cannot_repair/source.master.json.gz'))).toString(),'invalid gzip');checks.failed_repair_keeps_original_and_exposes_report=true
 const response=await page.evaluate(async()=>{const r=await fetch('/__detail__/project-repair',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({source:'../outside.nbt',category:'standalone'})});return r.status});assert.ok(response>=400);checks.backend_refuses_outside_paths=true
 assert.deepEqual(errors,[]);await fs.writeFile(path.join(output,'results.json'),JSON.stringify({passed:true,checks},null,2));console.log(JSON.stringify({passed:true,checks,output}))
}catch(e){console.error(JSON.stringify({output,checks,errors}));if(page)console.error(await page.locator('#project-status').textContent().catch(()=>''));throw e}finally{await app?.close()}
