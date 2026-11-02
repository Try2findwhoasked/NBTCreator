// Actual console DOM and styles; synthetic empty catalogue, no model writes.
import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import path from 'node:path'
import {startDetailServer} from './detail-server.mjs'
import {launchRenderBrowser} from './browser-launch.mjs'
const output=path.resolve(process.argv[2] ?? '');if(!process.argv[2])throw Error('Pass NEW output directory')
await fs.mkdir(output);const workspace=path.join(output,'workspace');await fs.mkdir(workspace)
let app,browser;const checks=[]
try{
 app=await startDetailServer({workspace,output:path.join(output,'jobs')})
 browser=await launchRenderBrowser()
 for(const [width,height,dpi,zoom]of [[1440,1000,1,1],[1440,1000,2,1],[1920,1080,1,1.25],[1920,1080,2,2],[1024,768,1,1],[900,700,1,1],[390,844,2,1]]){
   const context=await browser.newContext({viewport:{width,height},deviceScaleFactor:dpi}),page=await context.newPage(),errors=[]
   page.on('pageerror',e=>errors.push(e.message));await page.goto(app.url)
   await page.waitForFunction(()=>window.detailControl?.state.settings&&!window.detailControl.state.busy,undefined,{timeout:30000})
   await page.evaluate(z=>document.body.style.zoom=z,zoom)
   async function layout(){return page.evaluate(()=>{
     const rect=e=>{const r=e.getBoundingClientRect();return {top:r.top,bottom:r.bottom,left:r.left,right:r.right,height:r.height}}
     const nav=document.querySelector('#tool-tabs'),form=document.querySelector('#settings'),buttons=[...nav.children],sidebar=document.querySelector('.sidebar')
     return {nav:rect(nav),form:rect(form),buttons:buttons.map(rect),overflow:document.documentElement.scrollWidth>innerWidth+1,
       area:getComputedStyle(nav).gridArea,sidebar:getComputedStyle(sidebar).display}
   })}
   for(const expanded of [false,true]){
     await page.locator('.output-card').evaluate((e,v)=>e.open=v,expanded)
     for(let i=0;i<10;i++){
       await page.locator('#tool-tabs button').nth(i).click()
       const bounds=await layout()
       assert.ok(bounds.nav.bottom<=bounds.form.top+1,JSON.stringify({width,height,dpi,zoom,expanded,i,bounds}))
       for(const b of bounds.buttons){assert.ok(b.top>=bounds.nav.top-1&&b.bottom<=bounds.nav.bottom+1,'tab buttons must fit within nav height')}
       assert.equal(bounds.overflow,false,'no page horizontal overflow')
       const visible=await page.locator('#settings > .card').evaluateAll(items=>items.filter(e=>!e.hidden).length)
       assert.equal(visible,1)
     }
   }
   await page.locator('.output-card').evaluate(e=>e.open=false)
   await page.locator('#tool-tabs button').first().click()
   await page.locator('#settings').evaluate(e=>e.scrollTop=80)
   const bounds=await layout();assert.ok(bounds.nav.bottom<=bounds.form.top+1)
   await page.screenshot({path:path.join(output,`sidebar_${width}_${dpi}_${zoom}.png`)})
   assert.deepEqual(errors,[]);checks.push({width,height,dpi,zoom,passed:true});await context.close()
 }
 await fs.writeFile(path.join(output,'results.json'),JSON.stringify({passed:true,scenarios:checks,tab_checks:7*2*10},null,2))
 console.log(JSON.stringify({passed:true,scenarios:checks.length,tab_checks:140,output}))
}finally{await browser?.close();await app?.close()}
