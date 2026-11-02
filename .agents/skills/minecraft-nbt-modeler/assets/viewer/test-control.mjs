import fs from 'node:fs/promises'
import {gzipSync,gunzipSync} from 'node:zlib'
import path from 'node:path'
import assert from 'node:assert/strict'
import { parseArgs } from 'node:util'
import { createHash } from 'node:crypto'
import { startDetailServer } from './detail-server.mjs'
import { launchRenderBrowser } from './browser-launch.mjs'

const { values }=parseArgs({options:{fixture:{type:'string'},output:{type:'string'},python:{type:'string'},port:{type:'string'}}})
if(!values.fixture || !values.output)throw new Error('Provide --fixture backend-fixture-directory --output new-directory')
const output=path.resolve(values.output);await fs.mkdir(output)
const workspace=path.join(output,'workspace'), modelRoot=path.join(workspace,'nbt_models/sample')
await fs.mkdir(path.join(modelRoot,'master'),{recursive:true})
const source=path.join(modelRoot,'master/test.master.json.gz')
await fs.copyFile(path.join(values.fixture,'基线 空格.master.json.gz'),source)
await fs.copyFile(path.join(values.fixture,'context.json'),path.join(modelRoot,'coordinates.json'))
await fs.mkdir(path.join(modelRoot,'previews'))
const review=JSON.parse(await fs.readFile(path.join(values.fixture,'review/review.json'),'utf8'))
for(let i=0;i<2;i++){
  const image=path.join(modelRoot,'previews',`picture_${i+1}.png`)
  await fs.copyFile(path.join(values.fixture,'review',`thumbnail_${i<10?'0':''}${i}.png`),image)
  await fs.writeFile(image.replace('.png','.json'),JSON.stringify({geometry_sha256:review.source_geometry_sha256,camera:review.thumbnails[i].camera}))
}
await fs.writeFile(path.join(modelRoot,'room_description.json'),JSON.stringify({schema_version:1,name_zh:'测试石砖厅',shape:'single',shape_zh:'单格',display_name:'测试石砖厅-单格',master:source,audit:{compliant:true}}))
const hash=bytes=>createHash('sha256').update(bytes).digest('hex')
const second=path.join(workspace,'nbt_models/r002_second/master/test.master.json.gz')
await fs.mkdir(path.dirname(second),{recursive:true});const secondData=JSON.parse(gunzipSync(await fs.readFile(source)));secondData.synthetic_building_id='r002_second';await fs.writeFile(second,gzipSync(JSON.stringify(secondData)));await fs.utimes(second,1,1)
await fs.copyFile(path.join(modelRoot,'coordinates.json'),path.join(path.dirname(path.dirname(second)),'coordinates.json'))
await fs.cp(path.join(modelRoot,'previews'),path.join(path.dirname(path.dirname(second)),'previews'),{recursive:true})
await fs.writeFile(path.join(path.dirname(path.dirname(second)),'room_description.json'),JSON.stringify({schema_version:1,name_zh:'第二测试厅',shape:'single',shape_zh:'单格',display_name:'第二测试厅-单格',master:second,audit:{compliant:true}}))
const original=hash(await fs.readFile(source)), checks={}
let app,browser
try{
  app=await startDetailServer({port:Number(values.port ?? 5191),workspace,output:path.join(output,'jobs'),python:values.python ?? 'python'})
  browser=await launchRenderBrowser()
  for(const scale of [1,2]){
    const context=await browser.newContext({viewport:{width:1440,height:1000},deviceScaleFactor:scale,acceptDownloads:true})
    const page=await context.newPage(), errors=[]
    page.on('pageerror',error=>errors.push(error.message))
    await page.goto(app.url)
    await page.waitForFunction(()=>window.detailControl?.state.selectedImage && document.querySelector('#review-image').naturalWidth>0 && !window.detailControl.state.busy,undefined,{timeout:60000})
    await page.locator('#workspace-tools').evaluate(e=>e.open=true);await page.locator('#auto-preview').uncheck()
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true)
    checks['dpi_'+scale+'_no_horizontal_overflow']=true
    assert.equal(await page.locator('.app-header').count(),0)
    assert.equal(await page.locator('#catalog-summary').isVisible(),false)
    await page.locator('#model-info summary').first().click()
    assert.equal(await page.locator('#catalog-summary').isVisible(),true)
    await page.locator('#model-info summary').first().click()
    checks.metadata_in_info_popover_and_no_page_header=true
    assert.equal(await page.locator('#viewer').isVisible(),false)
    assert.equal(await page.evaluate(()=>performance.getEntriesByType('resource').some(item=>item.name.includes('default-pack'))),false)
    checks.no_automatic_webgl_or_resource_pack=true
    await page.locator('#tool-tabs button').nth(4).click();await page.locator('#open-orthographic').click()
    assert.equal(await page.locator('#orthographic-dialog').evaluate(el=>el.tagName),'SECTION')
    assert.equal(await page.evaluate(()=>document.querySelectorAll(':modal').length),0)
    await page.locator('canvas[data-projection=top]').scrollIntoViewIfNeeded()
    const top=await page.locator('canvas[data-projection=top]').boundingBox()
    await page.mouse.move(top.x+top.width*.3,top.y+top.height*.3);await page.mouse.down();await page.mouse.move(top.x+top.width*.7,top.y+top.height*.7);await page.mouse.up()
    const topRange=await page.evaluate(()=>window.detailControl.gather())
    assert.equal(topRange.whole_region,false);assert.ok(topRange.lo[0]>0&&topRange.hi[2]<47);assert.equal(topRange.lo[1],0)
    await page.locator('canvas[data-projection=front]').scrollIntoViewIfNeeded()
    const front=await page.locator('canvas[data-projection=front]').boundingBox()
    await page.mouse.move(front.x+front.width*.4,front.y+front.height*.45);await page.mouse.down();await page.mouse.move(front.x+front.width*.6,front.y+front.height*.55);await page.mouse.up()
    const frontRange=await page.evaluate(()=>window.detailControl.gather())
    assert.deepEqual([frontRange.lo[2],frontRange.hi[2]],[topRange.lo[2],topRange.hi[2]]);assert.ok(frontRange.lo[1]>0)
    await page.locator('#close-orthographic').click();await page.locator('#whole-region').check()
    checks.orthographic_box_selection_updates_xyz_and_preserves_other_axis=true
    assert.equal(await page.locator('#models option').first().textContent(),'测试石砖厅-单格')
    assert.ok(await page.locator('.sidebar').evaluate(el=>el.getBoundingClientRect().width<innerWidth*.4))
    assert.ok(await page.locator('.viewport-card').evaluate(el=>el.getBoundingClientRect().height>=300))
    await page.locator('#tool-tabs button').nth(2).click()
    await page.locator('#weather-enabled').evaluate(el=>el.closest('details').open=true)
    await page.locator('#moss-state').fill('苔石砖')
    assert.equal(await page.evaluate(()=>window.detailControl.gather().weathering.moss_state),'minecraft:mossy_stone_bricks')
    checks.compact_layout_paths_and_chinese_blocks=true
    assert.ok((await page.evaluate(()=>window.detailControl.state.images)).every(image=>image.thumbnail&&image.thumbnail_bytes>0))
    assert.ok(await page.locator('#gallery').evaluate(el=>el.getBoundingClientRect().top<document.querySelector('.viewport-card').getBoundingClientRect().top))
    checks.thumbnails_above_preview=true
    checks.real_thumbnail_resources=true
    await page.locator('#tool-tabs button').nth(1).click()
    await page.locator('#pattern-from').locator('..').getByRole('button',{name:'展开方块选择'}).click()
    await page.getByRole('option',{name:'石砖 · stone_bricks',exact:true}).click()
    assert.equal(await page.locator('#pattern-from').inputValue(),'石砖')
    await page.locator('#pattern-from').fill('安山')
    await page.locator('#pattern-from').locator('..').getByRole('button',{name:'展开方块选择'}).click()
    assert.ok((await page.locator('.completion-popup:not([hidden]) [role=option]').allTextContents()).every(text=>text.includes('安山')))
    await page.locator('#pattern-from').fill('石砖')
    await page.locator('#pattern-from').locator('..').getByRole('button',{name:'展开方块选择'}).click()
    assert.equal(await page.getByRole('option',{name:'石砖 · stone_bricks',exact:true}).getAttribute('aria-selected'),'true')
    await page.locator('#pattern-from').press('Escape')
    checks.dropdown_filters_current_input_and_highlights_selected_block=true
    await page.locator('#pattern-from').fill('石砖;安山')
    await page.locator('#pattern-from').press('Tab')
    assert.deepEqual(await page.evaluate(()=>window.detailControl.gather().pattern.from_states),['minecraft:stone_bricks','minecraft:andesite'])
    await page.locator('#pattern-from').fill('石砖')
    await page.locator('#palette .block-select-toggle').first().click()
    await page.getByRole('option',{name:'石砖 · stone_bricks',exact:true}).click()
    assert.equal(await page.evaluate(()=>window.detailControl.gather().pattern.palette[0].state),'minecraft:stone_bricks')
    checks.clickable_chinese_block_dropdown_and_multi_source_completion=true
    await page.locator('#pattern-enabled').check()
    await page.locator('#pattern-fraction').fill('25')
    assert.equal(await page.evaluate(()=>window.detailControl.gather().pattern.fraction),.25)
    assert.equal(await page.locator('#pattern-fraction-range').inputValue(),'25')
    checks.slider_number_binding=true
    await page.locator('#pattern-fraction').fill('30')
    await page.locator('#undo-settings').click()
    assert.equal(await page.evaluate(()=>window.detailControl.gather().pattern.fraction),.25)
    await page.locator('#redo-settings').click()
    assert.equal(await page.evaluate(()=>window.detailControl.gather().pattern.fraction),.3)
    await page.locator('#undo-settings').click()
    checks.settings_undo_redo=true
    await page.locator('#tool-tabs button').nth(5).click()
    await page.locator('#replace-enabled').check()
    assert.equal(await page.evaluate(()=>window.detailControl.gather().replace.enabled),true)
    await page.locator('#replace-enabled').uncheck()
    await page.locator('#tool-tabs button').nth(6).click()
    assert.ok(await page.locator('.material-sample').count()>0)
    await page.locator('#tool-tabs button').nth(7).click()
    assert.equal(await page.locator('#structure-mode').isVisible(),true)
    checks.new_tool_panels_and_current_building_materials=true
    await page.locator('#tool-tabs button').nth(1).click()
    await page.getByRole('button',{name:'生成修改方案',exact:true}).click()
    await page.waitForFunction(()=>Boolean(window.detailControl.state.bundle)&&!window.detailControl.state.busy,undefined,{timeout:60000})
    const bundle=await page.evaluate(()=>window.detailControl.state.bundle)
    const plan=JSON.parse(await fs.readFile(path.join(path.dirname(bundle),'plan.json')))
    assert.equal(plan.operations[0].fraction,.25)
    assert.equal(hash(await fs.readFile(source)),original)
    assert.equal(await page.locator('#apply').isDisabled(),true)
    checks.plan_export_and_no_baseline_write=true
    checks.application_requires_review=true
    await page.locator('.output-card').evaluate(el=>el.open=true)
    await page.locator('#save-root').fill(path.join(output,'effects'))
    await page.locator('#set-output').click()
    await page.waitForFunction(()=>window.detailControl.state.output.endsWith('effects'))
    await page.locator('#effect-name').fill('苔痕效果')
    await page.getByRole('button',{name:'保存调整设置',exact:true}).click()
    await page.getByRole('link',{name:'另下载一份设置'}).waitFor()
    await page.locator('.output-card').evaluate(el=>el.open=false)
    assert.ok((await fs.readdir(path.join(output,'effects'))).some(name=>name.startsWith('苔痕效果')))
    checks.settings_saved_in_selected_folder=true
    const downloadPromise=page.waitForEvent('download')
    await page.getByRole('link',{name:'另下载一份设置'}).click()
    const download=await downloadPromise
    const preset=path.join(output,`settings-dpi-${scale}.json`);await download.saveAs(preset)
    assert.equal(JSON.parse(await fs.readFile(preset)).settings.pattern.fraction,.25)
    checks.preset_download_preserves_settings=true
    await page.locator('#tool-tabs button').nth(0).click()
    await page.locator('#strength').fill('50')
    await page.locator('#preset-file').setInputFiles(preset)
    await page.waitForFunction(()=>!window.detailControl.state.busy&&document.querySelector('#strength').value==='100',undefined,{timeout:60000})
    assert.equal(await page.evaluate(()=>window.detailControl.gather().pattern.fraction),.25)
    checks.preset_import_round_trip=true
    await page.waitForFunction(()=>document.querySelector('#review-image').naturalWidth>0&&!window.detailControl.state.busy)
    if(scale===1){
      await page.locator('#review-image').click()
      assert.ok((await page.locator('#feedback-text').inputValue()).includes('#1 '))
      const imagePoint=await page.locator('#review-image').evaluate(el=>{const r=el.getBoundingClientRect(),s=Math.min(r.width/el.naturalWidth,r.height/el.naturalHeight);return{x:r.x+r.width/2+el.naturalWidth*s*.15,y:r.y+r.height/2}})
      await page.mouse.click(imagePoint.x,imagePoint.y)
      assert.ok((await page.locator('#feedback-text').inputValue()).includes('#2 '))
      assert.equal(await page.locator('.image-pin.draft').count(),2)
      assert.ok((await page.locator('#feedback-context').textContent()).includes('picture_2.png'))
      await page.locator('#feedback-text').fill('@苔痕')
      await page.locator('#feedback-text').press('Tab')
      assert.ok((await page.locator('#feedback-text').inputValue()).includes('@[苔痕效果'))
      const referenceToken=await page.locator('#feedback-text').inputValue()
      await page.locator('#feedback-text').fill(referenceToken+' SYNTHETIC FIXTURE ONLY: make this pit smaller; <b>plain text</b>.')
      await page.getByRole('button',{name:'保存这条意见',exact:true}).click()
      await page.waitForFunction(()=>window.detailControl.state.notes.length===1)
      const note=await page.evaluate(()=>window.detailControl.state.notes[0])
      assert.equal(note.references.length,1);assert.ok(note.references[0].sha256);checks.effect_file_tab_completion_and_saved_reference=true
      assert.ok(Math.abs(note.point.x-.5)<.01&&Math.abs(note.point.y-.5)<.01)
      assert.equal(note.anchors.length,2);assert.deepEqual(note.anchors.map(p=>p.number),[1,2]);checks.multiple_image_points_auto_number_and_save=true
      assert.equal(await page.locator('#feedback-notes b').count(),0)
      checks.image_pin_and_safe_comment_text=true
      await page.reload()
      await page.waitForFunction(()=>window.detailControl?.state.notes.length===1&&!window.detailControl.state.busy,undefined,{timeout:60000})
      await page.locator('#workspace-tools').evaluate(e=>e.open=true);await page.locator('#auto-preview').uncheck()
      checks.feedback_survives_reload=true
      assert.equal(await page.locator('.image-pin').count(),2)
      const freshPoint=await page.locator('#review-image').evaluate(el=>{const r=el.getBoundingClientRect(),s=Math.min(r.width/el.naturalWidth,r.height/el.naturalHeight);return{x:r.x+r.width/2-el.naturalWidth*s*.2,y:r.y+r.height/2}})
      await page.mouse.click(freshPoint.x,freshPoint.y)
      assert.ok((await page.locator('#feedback-text').inputValue()).includes('#3 '))
      await page.locator('#draft-markers button').click();assert.equal(await page.locator('.image-pin.draft').count(),0)
      assert.equal(await page.locator('#feedback-text').inputValue(),'')
      checks.removing_draft_point_removes_its_default_comment_prefix=true
      await page.getByRole('button',{name:'标为已解决',exact:true}).click()
      await page.waitForFunction(()=>window.detailControl.state.notes[0].status==='resolved')
      await page.getByRole('button',{name:'下载这张图的修改意见',exact:true}).click()
      await page.getByRole('link',{name:'下载意见 JSON',exact:true}).waitFor()
      const link=await page.getByRole('link',{name:'下载意见 JSON',exact:true}).getAttribute('href')
      const exported=await (await fetch(new URL(link,app.url))).json()
      assert.equal(exported.notes.length,1);assert.equal(exported.binding.source_sha256,original)
      assert.ok((await page.locator('#feedback-file').textContent()).includes('修改意见'))
      checks.feedback_resolution_and_export=true
      await page.locator('#image-mode').click();await page.locator('#image-select').selectOption('1')
      await page.waitForFunction(()=>window.detailControl.state.notes.length===0)
      checks.notes_do_not_cross_images=true
      await page.locator('#image-mode').click();await page.locator('#image-select').selectOption('0')
      await page.waitForFunction(()=>window.detailControl.state.notes.length===1)
      await page.getByRole('button',{name:'打开 3D',exact:true}).click()
      await page.waitForFunction(()=>document.querySelector('#viewer').contentWindow?.nbtModeler?.status==='ready'&&!window.detailControl.state.busy,undefined,{timeout:60000})
      assert.equal(await page.evaluate(()=>document.querySelector('#viewer').contentWindow.nbtModeler.metadata().quality),'fast')
      const panBefore=await page.evaluate(()=>document.querySelector('#viewer').contentWindow.nbtModeler.metadata())
      const canvasBox=await page.frameLocator('#viewer').locator('#preview').boundingBox()
      await page.mouse.move(canvasBox.x+canvasBox.width*.5,canvasBox.y+canvasBox.height*.5);await page.mouse.down({button:'middle'});await page.mouse.move(canvasBox.x+canvasBox.width*.5+40,canvasBox.y+canvasBox.height*.5+15,{steps:5});await page.mouse.up({button:'middle'})
      await page.waitForFunction(target=>document.querySelector('#viewer').contentWindow.nbtModeler.metadata().camera.target.some((value,i)=>Math.abs(value-target[i])>.01),panBefore.camera.target)
      const panAfter=await page.evaluate(()=>document.querySelector('#viewer').contentWindow.nbtModeler.metadata())
      assert.equal(panAfter.mesh_builds,panBefore.mesh_builds)
      assert.ok(panAfter.camera.eye.every((value,i)=>Math.abs((value-panBefore.camera.eye[i])-(panAfter.camera.target[i]-panBefore.camera.target[i]))<.001))
      checks.middle_button_pans_without_rotating_or_rebuilding=true
      const frame=()=>page.frameLocator('#viewer')
      const boxStatus=await page.evaluate(()=>document.querySelector('#viewer').contentWindow.nbtModeler.selectionStatus())
      assert.equal(boxStatus.visible,true)
      await page.locator('#tool-tabs button').nth(4).click()
      await page.locator('#open-orthographic').click()
      assert.equal(await page.evaluate(()=>document.querySelectorAll(':modal').length),0)
      assert.ok(await page.locator('#orthographic-dialog').evaluate(el=>el.getBoundingClientRect().right<=document.querySelector('#viewer').getBoundingClientRect().left))
      await page.locator('#whole-region').uncheck();await page.locator('#lo-x').fill('5');await page.locator('#hi-x').fill('12')
      const changedBounds=await page.evaluate(()=>document.querySelector('#viewer').contentWindow.nbtModeler.selectionStatus())
      assert.deepEqual([changedBounds.range.lo[0],changedBounds.range.hi[0]],[5,12])
      await page.locator('#show-selection').uncheck();assert.equal(await page.evaluate(()=>document.querySelector('#viewer').contentWindow.nbtModeler.selectionStatus().visible),false)
      await page.locator('#show-selection').check()
      await page.screenshot({path:path.join(output,'docked-white-views-with-3d.png')})
      await page.locator('#whole-region').check()
      assert.deepEqual(await page.evaluate(()=>document.querySelector('#viewer').contentWindow.nbtModeler.selectionStatus().range.lo),[0,0,0])
      await page.locator('#close-orthographic').click()
      checks.three_dimensional_selection_box_tracks_xyz_and_visibility=true
      await page.locator('#pick-material').click()
      const pickCanvas=await frame().locator('#preview').boundingBox()
      await page.mouse.click(pickCanvas.x+pickCanvas.width/2,pickCanvas.y+pickCanvas.height/2)
      await page.waitForFunction(()=>Boolean(window.detailControl.state.pickedMaterial),undefined,{timeout:15000})
      const picked=await page.evaluate(()=>window.detailControl.state.pickedMaterial)
      assert.ok(picked.state.startsWith('minecraft:'));assert.equal(picked.position.length,3)
      await page.locator('#picked-target').selectOption('replace-to');await page.locator('#use-picked-material').click()
      assert.equal(await page.evaluate(()=>window.detailControl.gather().replace.state),picked.state)
      assert.equal(await page.locator('.completion-popup:not([hidden])').count(),0)
      await page.locator('#pick-material').click()
      checks.clicking_visible_3d_block_samples_and_populates_parameters=true

      await page.locator('#pick-coordinate').click()
      const positions=await page.evaluate(()=>{
        const v=document.querySelector('#viewer').contentWindow.nbtModeler,points=[]
        for(const y of [0,.2,-.2,.4,-.4])for(const x of [0,.2,-.2,.4,-.4]){const p=v.pickBlock(x,y);if(p&&!points.some(q=>q.position.join(',')===p.position.join(',')))points.push({x,y,...p});if(points.length===2)return points}
        return points
      })
      assert.equal(positions.length,2)
      const builds=await page.evaluate(()=>document.querySelector('#viewer').contentWindow.nbtModeler.metadata().mesh_builds)
      const voxelCanvas=await frame().locator('#preview').boundingBox()
      for(const p of positions)await page.mouse.click(voxelCanvas.x+(p.x+1)*voxelCanvas.width/2,voxelCanvas.y+(1-p.y)*voxelCanvas.height/2)
      await page.waitForFunction(()=>window.detailControl.state.draftPoints.length===2)
      assert.ok((await page.locator('#feedback-text').inputValue()).includes('#1 '));assert.ok((await page.locator('#feedback-text').inputValue()).includes('#2 '))
      assert.equal(await page.evaluate(()=>document.querySelector('#viewer').contentWindow.nbtModeler.commentMarkerStatus().length),2)
      assert.equal(await page.evaluate(()=>document.querySelector('#viewer').contentWindow.nbtModeler.metadata().mesh_builds),builds)
      await page.locator('#feedback-text').fill('#1 Repair the arch\n#2 Lower the beam')
      await page.locator('#save-feedback').click();await page.waitForFunction(()=>window.detailControl.state.notes.length===1)
      const voxelNote=await page.evaluate(()=>window.detailControl.state.notes[0])
      assert.equal(voxelNote.anchors.length,2);assert.deepEqual(voxelNote.anchors.map(p=>p.position),positions.map(p=>p.position));assert.ok(voxelNote.anchors.every(p=>p.view.camera.eye.length===3))
      await page.locator('#export-feedback').click();await page.getByRole('link',{name:'下载意见 JSON',exact:true}).waitFor()
      const voxelLink=await page.getByRole('link',{name:'下载意见 JSON',exact:true}).getAttribute('href')
      const voxelExport=await(await fetch(new URL(voxelLink,app.url))).json();assert.equal(voxelExport.binding.kind,'3d');assert.equal(voxelExport.notes[0].anchors.length,2)
      checks.multiple_3d_positions_comments_and_camera_export_without_mesh_rebuild=true
      await page.locator('#pick-coordinate').click()
      await page.screenshot({path:path.join(output,'multiple-3d-comments.png')})

      assert.equal(await page.locator('#feedback-card').isVisible(),true)
      assert.ok(await page.locator('#feedback-card').evaluate(el=>el.getBoundingClientRect().bottom<=innerHeight-48))
      assert.ok(await page.locator('#settings').evaluate(el=>el.getBoundingClientRect().bottom<=document.querySelector('.preset-card').getBoundingClientRect().top))
      checks.preview_and_comments_fit_without_covering_controls=true
      assert.equal(await page.locator('#three-toolbar').evaluate(el=>el.parentElement.classList.contains('review-toolbar')),true)
      assert.ok(await page.locator('#save-feedback').evaluate(el=>el.getBoundingClientRect().bottom<=document.querySelector('#feedback-card').getBoundingClientRect().bottom))
      checks.single_preview_toolbar_and_visible_comment_save=true
      assert.equal(await page.locator('#image-select').isVisible(),false)
      await page.locator('.stage').evaluate(el=>el.scrollTop=el.scrollHeight)
      const selectorStaysVisible=await page.locator('#image-select').evaluate(el=>{
        const r=el.getBoundingClientRect(),p=el.closest('.stage').getBoundingClientRect()
        return r.top>=p.top && r.bottom<=p.bottom
      })
      assert.equal(await page.locator('.thumbnail-card').isVisible(),false);checks.image_selector_hidden_in_3d=true
      await page.screenshot({path:path.join(output,'control-3d.png')})
      const cameraCheck=await page.evaluate(()=>{
        const v=document.querySelector('#viewer').contentWindow.nbtModeler
        const before=Array.from(v.camera.getCamera().position)
        v.camera.resumeOrbit()
        const after=Array.from(v.camera.getCamera().position)
        return before.every((value,i)=>Math.abs(value-after[i])<.001)
      })
      assert.equal(cameraCheck,true);checks.camera_does_not_jump_on_interaction=true
      await page.getByRole('button',{name:'关闭 3D',exact:true}).click()
      await page.waitForFunction(()=>document.querySelector('#viewer').src==='about:blank'&&window.detailControl.state.mode==='images')
      checks.opt_in_3d_and_release=true
      await page.getByRole('button',{name:'打开 3D',exact:true}).click()
      await page.waitForFunction(()=>!window.detailControl.state.busy&&window.detailControl.state.mode==='3d')
      assert.equal(await page.evaluate(()=>window.detailControl.state.notes[0].anchors.length),2)
      assert.equal(await page.evaluate(()=>document.querySelector('#viewer').contentWindow.nbtModeler.commentMarkerStatus().length),2)
      checks.three_dimensional_comments_reload_for_same_geometry=true
      await page.locator('#image-mode').click();await page.locator('#image-select').selectOption('1')
      await page.waitForFunction(()=>window.detailControl.state.mode==='images'&&document.querySelector('#viewer').src==='about:blank')
      assert.equal(await page.locator('#review-canvas').isVisible(),true)
      checks.selecting_image_exits_3d=true
    }
    await page.locator('.sidebar').evaluate(element=>{element.scrollTop=0})
    await page.screenshot({path:path.join(output,`control-dpi-${scale}.png`)})
    if(scale===2){
      const index=await page.evaluate(source=>window.detailControl.state.models.findIndex(model=>model.source===source),second)
      await page.locator('#models').selectOption(String(index))
      await page.waitForFunction(source=>window.detailControl.state.info?.source===source&&!window.detailControl.state.busy,second)
      await page.waitForFunction(()=>window.detailControl.state.selectedImage&&window.detailControl.state.notes.length===0)
      assert.ok((await page.locator('#feedback-context').textContent()).includes('第二测试厅'))
      checks.building_switch_loads_right_workspace_and_isolates_notes=true
      await page.locator('#auto-preview').check()
      await page.waitForFunction(()=>window.detailControl.state.preview&&!window.detailControl.state.previewBusy,undefined,{timeout:90000})
      const preview=await page.evaluate(()=>window.detailControl.state.preview)
      assert.ok(preview.preview_only&&preview.changed_blocks>0)
      const after=await page.evaluate(()=>document.querySelector('#viewer').contentWindow.nbtModeler.metadata())
      assert.equal(after.geometry_sha256,preview.geometry_sha256)
      await page.locator('#compare-before').click()
      await page.waitForFunction(()=>window.detailControl.state.comparisonSide==='before')
      const before=await page.evaluate(()=>document.querySelector('#viewer').contentWindow.nbtModeler.metadata())
      assert.notEqual(before.geometry_sha256,after.geometry_sha256)
      assert.deepEqual(before.camera,after.camera)
      await page.locator('#compare-after').click()
      await page.waitForFunction(()=>window.detailControl.state.comparisonSide==='after')
      assert.equal(await page.evaluate(()=>document.querySelector('#viewer').contentWindow.nbtModeler.metadata().geometry_sha256),after.geometry_sha256)
      assert.equal(hash(await fs.readFile(source)),original)
      await page.screenshot({path:path.join(output,'live-effect-preview.png')})
      checks.live_preview_changes_geometry_preserves_camera_and_source=true
      await page.locator('#export-revision').click()
      await page.waitForFunction(()=>!window.detailControl.state.busy&&document.querySelector('#status').textContent.includes('下一版建筑已保存'),undefined,{timeout:90000})
      const outputText=await page.locator('#result-links').textContent()
      assert.ok(outputText.includes('versions'))
      assert.ok((await page.locator('#result-links a').allTextContents()).some(name=>name.endsWith('.nbt')))
      checks.website_exports_a_real_next_version_with_nbt=true
    }
    assert.deepEqual(errors,[])
    await context.close()
  }
  const denied=await fetch(new URL('/__detail__/init',app.url),{headers:{Origin:'https://example.invalid'}})
  assert.equal(denied.status,403);checks.foreign_origin_refused=true
  const result={passed:true,checks}
  await fs.writeFile(path.join(output,'results.json'),JSON.stringify(result,null,2)+'\n')
  console.log(JSON.stringify({passed:true,checks:Object.keys(checks).length,report:path.join(output,'results.json')}))
}finally{if(browser)await browser.close();if(app)await app.close()}
