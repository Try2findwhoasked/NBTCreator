import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import path from 'node:path'
import {createRequire} from 'node:module'
import {root,skill} from '../scripts/paths.mjs'
import {minimizedScreenshots} from './minimized-screenshots.mjs'

const require=createRequire(path.join(skill,'assets/viewer/package.json')),{_electron}=require('playwright')
const output=path.join(root,'build','pattern-assets-'+Date.now()),workspace=path.join(output,'workspace'),checks={}
const builtinCount=Object.keys(JSON.parse(await fs.readFile(path.join(skill,'assets/ornament-patterns/manifest.json'),'utf8'))).length
await fs.mkdir(path.join(workspace,'.nbtcreator'),{recursive:true})
await fs.writeFile(path.join(workspace,'.nbtcreator/preferences.json'),JSON.stringify({startPage:'assets'}))
let app
try{
 const env={...process.env,NBTCREATOR_AUTOMATION:'1'};delete env.ELECTRON_RUN_AS_NODE
 app=await _electron.launch({executablePath:process.env.NBTCREATOR_TEST_EXE||path.join(root,'node_modules/electron/dist/electron.exe'),args:[...(process.env.NBTCREATOR_TEST_EXE?[]:[root]),'--workspace',workspace,'--user-data-dir',path.join(output,'profile')],env,timeout:60000})
 const page=await app.firstWindow();page.setDefaultTimeout(60000);await minimizedScreenshots(app,page)
 const errors=[];page.on('pageerror',error=>errors.push(error.message))
 const post=async(tool,args)=>page.evaluate(async({tool,args})=>{const response=await fetch('/__detail__/components/agent',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({tool,arguments:args})});const value=await response.json();if(!response.ok)throw Error(JSON.stringify(value));return value},{tool,args})
 await page.locator('#asset-kind-patterns').click()
 await page.waitForFunction(count=>document.querySelectorAll('.pattern-asset-card').length===count,builtinCount)
 assert.equal(await page.locator('#pattern-assets-gallery').isVisible(),true)
 assert.equal(await page.locator('#effect-assets-gallery').isVisible(),false)
 const builtinMicroCount=Object.keys(JSON.parse(await fs.readFile(path.join(skill,'assets/ornament-patterns/manifest.json'),'utf8'))).filter(key=>key.startsWith('micro-')).length
 assert.equal(await page.locator('[data-pattern-asset-id^="builtin:micro-"]').count(),builtinMicroCount)
 await page.locator('[data-pattern-asset-id="builtin:gothic-pointed-tracery"]').click()
 await page.waitForFunction(()=>document.querySelector('#pattern-assets-name').value==='哥特尖拱窗棂')
 assert.equal(await page.locator('#pattern-fit-micro').isChecked(),false)
 assert.equal(await page.locator('#pattern-fit-width').inputValue(),'32')
 await page.locator('#pattern-assets-fit').click()
 await page.waitForFunction(()=>document.querySelector('#pattern-assets-status').textContent.includes('拟合预览已生成'))
 await page.waitForFunction(()=>document.querySelector('#pattern-assets-viewer').contentWindow.nbtModeler?.status==='ready')
 await page.locator('#pattern-assets-close').click()
 checks.architectural_preset_uses_full_size_preview=true
 await page.locator('[data-pattern-asset-id="builtin:micro-link"]').click()
 await page.locator('#pattern-fit-width').fill('2');await page.locator('#pattern-fit-height').fill('2')
 await page.locator('#pattern-fit-repeat-u').fill('1');await page.locator('#pattern-fit-repeat-v').fill('1')
 await page.locator('#pattern-assets-fit').click()
 await page.waitForFunction(()=>document.querySelector('#pattern-assets-status').textContent.includes('微型单元 2 × 2'))
 assert.ok((await page.locator('#pattern-assets-status').textContent()).includes('主孔洞 1 → 1'))
 await page.waitForFunction(()=>document.querySelector('#pattern-assets-viewer').contentWindow.nbtModeler?.status==='ready')
 await page.screenshot({path:path.join(output,'micro-link-two-block.png')})
 await page.locator('#pattern-assets-close').click()
 checks.small_builtin_ring_is_visible_and_fits_at_two_blocks=true
 await page.locator('[data-pattern-asset-id="builtin:checkerboard"]').click()
 await page.waitForFunction(()=>document.querySelector('#pattern-assets-image').naturalWidth>0)
 assert.equal(await page.locator('#pattern-assets-save').isDisabled(),true)
 checks.builtins_are_visible_as_readonly_pattern_assets=true
 const before=await post('pattern_assets',{action:'get',id:'builtin:checkerboard'})
 await page.locator('#pattern-assets-dialog details').first().locator('summary').click()
 await page.locator('#pattern-crop-x1').fill('50')
 await page.locator('#pattern-assets-crop').click()
 await page.waitForFunction(()=>document.querySelector('#pattern-assets-status').textContent.includes('另存'))
 let listing=await post('pattern_assets',{action:'list'}),native=listing.items.find(item=>!item.builtin)
 assert.equal(native.resolution[0],Math.ceil(before.resolution[0]/2));assert.equal(native.resolution[1],before.resolution[1])
 await page.locator('#pattern-assets-name').fill('我的裁取纹样')
 await page.locator('#pattern-assets-tags').fill('室内, 花纹')
 await page.locator('#pattern-assets-save').click()
 await page.waitForFunction(()=>document.querySelector('#pattern-assets-status').textContent.includes('标签已保存'))
 const renamed=await post('pattern_assets',{action:'get',id:native.id});assert.equal(renamed.name,'我的裁取纹样');assert.deepEqual(renamed.tags,['室内','花纹'])
 await page.locator('#pattern-assets-archive').click()
 await page.waitForFunction(()=>document.querySelector('#pattern-assets-status').textContent.includes('回收站'))
 assert.equal((await post('pattern_assets',{action:'get',id:native.id})).archived,true)
 await page.locator('#pattern-assets-archive').click()
 await page.waitForFunction(()=>document.querySelector('#pattern-assets-status').textContent.includes('已恢复'))
 await page.locator('#pattern-assets-close').click()
 checks.region_copy_rename_archive_and_restore_preserve_original=true
 await page.locator('#pattern-assets-new').click()
 await page.locator('#pattern-assets-name').fill('组合花纹测试')
 await page.locator('#pattern-assets-create').click()
 await page.waitForFunction(()=>document.querySelector('#pattern-assets-status').textContent.includes('组合纹样已生成'))
 await page.waitForFunction(()=>document.querySelector('#pattern-assets-image').complete&&document.querySelector('#pattern-assets-image').naturalWidth===16)
 listing=await post('pattern_assets',{action:'list'});assert.equal(listing.items.filter(item=>!item.builtin).length,2)
 checks.composed_pattern_is_saved_with_native_thumbnail_and_recipe=true
 assert.equal(await page.locator('#pattern-fit-micro').isChecked(),true)
 assert.equal(await page.locator('#pattern-fit-width').inputValue(),'4')
 assert.equal(await page.locator('#pattern-fit-height').inputValue(),'4')
 await page.locator('#pattern-assets-fit').click()
 await page.waitForFunction(()=>document.querySelector('#pattern-assets-viewer').contentWindow.nbtModeler?.status==='ready')
 await page.waitForFunction(()=>!document.querySelector('#pattern-assets-save-component').disabled)
 const fitted=await page.locator('#pattern-assets-viewer').evaluate(frame=>frame.contentWindow.nbtModeler.metadata())
 assert.ok(fitted.camera)
 assert.ok((await page.locator('#pattern-assets-status').textContent()).includes('微型单元 4 × 4'))
 assert.equal(await page.locator('#pattern-assets-image').isVisible(),false)
 const frameBox=await page.locator('#pattern-assets-viewer').boundingBox(),paneBox=await page.locator('.pattern-asset-body>section').first().boundingBox()
 assert.ok(frameBox.x>=paneBox.x&&frameBox.x+frameBox.width<=paneBox.x+paneBox.width+1)
 await page.screenshot();await page.waitForTimeout(150)
 await page.screenshot({path:path.join(output,'pattern-asset-fit.png')})
 await page.locator('#pattern-assets-save-component').click()
 await page.waitForFunction(()=>document.querySelector('#asset-kind-components').getAttribute('aria-pressed')==='true'&&document.querySelectorAll('.asset-card').length===1)
 assert.equal((await post('structure_list',{})).items.length,1)
 checks.pattern_can_be_fitted_and_saved_as_a_separate_component=true
 await page.locator('#asset-kind-patterns').click();await page.waitForFunction(count=>document.querySelectorAll('.pattern-asset-card').length===count,builtinCount+2)
 await page.locator('#asset-search').fill('组合花纹测试');assert.equal(await page.locator('.pattern-asset-card').count(),1)
 await page.locator('#asset-search').fill('')
 await page.locator('#pattern-assets-file').setInputFiles(path.join(skill,'assets/ornament-patterns/checkerboard.png'))
 await page.waitForFunction(()=>document.querySelector('#pattern-assets-status').textContent.includes('图片已保存'))
 assert.equal((await post('pattern_assets',{action:'list'})).items.filter(item=>!item.builtin).length,3)
 await page.locator('#pattern-assets-close').click()
 checks.image_upload_is_imported_as_an_independent_native_asset=true
 assert.equal(await page.locator('#asset-workspace .library-layout').isVisible(),false)
 assert.equal(await page.locator('#pattern-assets-gallery').isVisible(),true)
 await page.screenshot();await page.waitForTimeout(150);await page.screenshot({path:path.join(output,'pattern-asset-library.png')})
 await page.reload();await page.locator('#asset-kind-patterns').click();await page.waitForFunction(count=>document.querySelectorAll('.pattern-asset-card').length===count,builtinCount+3)
 assert.deepEqual(errors,[]);checks.search_and_reload_keep_patterns_distinct_from_components=true
 assert.equal(await fs.readdir(path.join(workspace,'nbt_models/_exports')).then(()=>true,()=>false),false)
 await fs.writeFile(path.join(output,'results.json'),JSON.stringify({passed:true,checks},null,2));console.log(JSON.stringify({passed:true,checks:Object.keys(checks).length,output}))
}finally{await app?.close()}
