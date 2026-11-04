// Focused integration: image-free 3D feedback and temporary-effect version isolation.
import fs from 'node:fs/promises'
import path from 'node:path'
import assert from 'node:assert/strict'
import {parseArgs} from 'node:util'
import {startDetailServer} from './detail-server.mjs'
import {launchRenderBrowser} from './browser-launch.mjs'
const {values}=parseArgs({options:{fixture:{type:'string'},output:{type:'string'},python:{type:'string'}}})
if(!values.fixture||!values.output)throw new Error('Provide --fixture and new --output')
const out=path.resolve(values.output);await fs.mkdir(out)
const workspace=path.join(out,'workspace'),root=path.join(workspace,'nbt_models/sample'),source=path.join(root,'master/test.master.json.gz')
await fs.mkdir(path.dirname(source),{recursive:true});await fs.copyFile(path.join(values.fixture,'基线 空格.master.json.gz'),source)
await fs.copyFile(path.join(values.fixture,'context.json'),path.join(root,'coordinates.json'))
await fs.writeFile(path.join(root,'room_description.json'),JSON.stringify({name_zh:'无图片测试厅',shape:'single',display_name:'无图片测试厅-单格',master:source,audit:{compliant:true}}))
let app,browser;const checks={}
try{
  app=await startDetailServer({workspace,output:path.join(out,'jobs'),port:5193,python:values.python ?? 'python'})
  browser=await launchRenderBrowser();const page=await browser.newPage({viewport:{width:1366,height:900}}),errors=[];page.on('pageerror',e=>errors.push(e.message))
  await page.goto(app.url);await page.waitForFunction(()=>window.detailControl?.state.info&&!window.detailControl.state.busy,undefined,{timeout:60000})
  await page.locator('#auto-preview').uncheck();assert.equal(await page.evaluate(()=>window.detailControl.state.images.length),0)
  await page.locator('#enable-3d').click();await page.waitForFunction(()=>window.detailControl.state.feedbackTarget?.kind==='3d'&&!window.detailControl.state.busy,undefined,{timeout:60000})
  assert.equal(await page.locator('#feedback-card').isVisible(),true)
  async function pick(){
    await page.locator('#pick-coordinate').click()
    const p=await page.evaluate(()=>{const v=document.querySelector('#viewer').contentWindow.nbtModeler;for(const y of [0,.2,-.2])for(const x of [0,.2,-.2])if(v.pickBlock(x,y))return{x,y}})
    assert.ok(p);const r=await page.frameLocator('#viewer').locator('#preview').boundingBox();await page.mouse.click(r.x+(p.x+1)*r.width/2,r.y+(1-p.y)*r.height/2)
    await page.waitForFunction(()=>window.detailControl.state.draftPoints.length===1);await page.locator('#pick-coordinate').click()
  }
  await pick();await page.locator('#feedback-text').fill('#1 Original building note');await page.locator('#save-feedback').click();await page.waitForFunction(()=>window.detailControl.state.notes.length===1)
  const baseline=await page.evaluate(()=>window.detailControl.state.notes[0].anchors[0]);checks.no_image_required_for_coordinate_comments=true
  await page.locator('#image-mode').click();assert.equal(await page.locator('#feedback-card').isVisible(),false)
  await page.locator('#enable-3d').click();await page.waitForFunction(()=>!window.detailControl.state.busy&&window.detailControl.state.notes.length===1,undefined,{timeout:60000})
  checks.no_image_comments_restore_on_reopen=true
  await page.locator('#tool-tabs button').nth(1).click();await page.locator('#pattern-enabled').check();await page.locator('#pattern-fraction').fill('25')
  await page.locator('#update-preview').click();await page.waitForFunction(()=>window.detailControl.state.comparisonSide==='after'&&!window.detailControl.state.previewBusy,undefined,{timeout:90000})
  assert.notEqual(await page.evaluate(()=>window.detailControl.state.feedbackTarget.geometry),baseline.geometry_sha256)
  assert.equal(await page.evaluate(()=>window.detailControl.state.notes.length),0)
  await pick();const temporary=await page.evaluate(()=>window.detailControl.state.draftPoints[0]);assert.equal(temporary.number,1)
  await page.locator('#feedback-text').fill('#1 Adjusted building note')
  await page.locator('#compare-before').click();await page.waitForFunction(()=>window.detailControl.state.comparisonSide==='before'&&!window.detailControl.state.feedbackLoading)
  assert.equal(await page.evaluate(()=>window.detailControl.state.notes[0].text),'#1 Original building note')
  assert.equal(await page.evaluate(()=>window.detailControl.state.draftPoints.length),0)
  await page.locator('#compare-after').click();await page.waitForFunction(()=>window.detailControl.state.comparisonSide==='after'&&!window.detailControl.state.feedbackLoading)
  assert.equal(await page.locator('#feedback-text').inputValue(),'#1 Adjusted building note');assert.equal(await page.evaluate(()=>window.detailControl.state.draftPoints.length),1)
  checks.comparison_isolates_original_effect_comments_and_drafts=true
  await page.locator('#save-feedback').click();await page.waitForFunction(()=>window.detailControl.state.notes.length===1)
  const target=await page.evaluate(()=>window.detailControl.state.feedbackTarget)
  const invalid=await fetch(new URL('/__detail__/feedback/add',app.url),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({target_id:target.id,text:'invalid coordinate',anchors:[{...temporary,number:2,position:[999,0,0]}]})})
  assert.equal(invalid.status,400);assert.ok((await invalid.json()).error);checks.server_rejects_coordinates_outside_actual_snapshot=true
  await page.screenshot({path:path.join(out,'no-image-effect-comments.png')});assert.deepEqual(errors,[])
  await fs.writeFile(path.join(out,'results.json'),JSON.stringify({passed:true,checks},null,2));console.log(JSON.stringify({passed:true,checks:Object.keys(checks).length}))
}finally{await browser?.close();await app?.close()}
