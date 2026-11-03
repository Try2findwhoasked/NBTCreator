import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import path from 'node:path'
import {createRequire} from 'node:module'
import {spawnSync} from 'node:child_process'
import {root,skill,python} from '../scripts/paths.mjs'
import {createViewerServer} from '../.agents/skills/minecraft-nbt-modeler/assets/viewer/viewer-server.mjs'
const output=path.join(root,'build','project-performance-'+Date.now());await fs.mkdir(output,{recursive:true})
process.env.PLAYWRIGHT_BROWSERS_PATH??=path.join(root,'build/portable-browser')
const require=createRequire(path.join(skill,'assets/viewer/package.json')),{chromium}=require('playwright')
const source=path.join(skill,'assets/viewer/src'),baselineIndex=process.argv.indexOf('--baseline')
const baseline=baselineIndex>=0?await fs.readFile(path.resolve(process.argv[baselineIndex+1]),'utf8'):null
const fixture=Array.from({length:1000},(_,index)=>{const n=Math.floor(index/2);return {source:path.join(output,`room-${n}-v${index%2+1}.nbt`),group:'room-'+n,object_key:'room-'+n,name:'测试建筑 '+n,object_name:'测试建筑 '+n,name_zh:'测试建筑 '+n,label:'测试建筑 '+n,project_key:'',project_name:'性能测试',shape_group:'single',shape_group_zh:'单格',version:'v'+(index%2+1),relative_path:`single/测试建筑${n}/v${index%2+1}/room.nbt`,geometry_sha256:index.toString(16).padStart(64,'0'),size:[16,12,16],context:'',cameras:'',modified_ns:index,is_delivery:false}})
const defaults=spawnSync(python,[path.join(skill,'scripts/nbt_detail_control.py'),'defaults'],{encoding:'utf8',windowsHide:true});assert.equal(defaults.status,0,defaults.stderr)
let releaseInit;const initGate=new Promise(resolve=>releaseInit=resolve),checks={},metrics={covers:0,active:0,maxActive:0,inspects:0}
let server,browser
try{
 server=await createViewerServer({frontendMode:'production',apiHandler:async(req,res,url)=>{
  if(url.pathname.startsWith('/__bench__/')){
   const name=url.pathname.split('/').at(-1);let text,type='text/javascript'
   if(name==='index.html'){type='text/html';text='<html><head><link rel="stylesheet" href="/ __bench__/style.css"></head><body><aside id="project-tree" style="width:270px;height:450px"></aside></body></html>'.replace('/ __bench__/','/__bench__/')}
   else if(name==='style.css'){type='text/css';text=await fs.readFile(path.join(source,'project-manager.css'),'utf8')}
   else if(name==='before.js'&&baseline)text=baseline
   else if(['project-tree.js','project-catalog.js','library-browser.js','floating-panel.js'].includes(name))text=(await fs.readFile(path.join(source,name),'utf8')).replace("import './library-browser.css'",'')
   else return false
   res.setHeader('Content-Type',type);res.end(text);return true
  }
  if(!url.pathname.startsWith('/__detail__/'))return false
  let value={}
  if(url.pathname.endsWith('/init')){await initGate;value={workspace:output,output,catalog:{models:fixture,scanned:1000,skipped:0},project_catalog:{models:fixture},defaults:JSON.parse(defaults.stdout).result}}
  else if(url.pathname.endsWith('/command-preferences'))value={revision:0,preferences:{favorites:[],shortcuts:{},recent:[]}}
  else if(url.pathname.endsWith('/project-layout'))value={orders:{}}
  else if(url.pathname.endsWith('/effects'))value={files:[],root:output}
  else if(url.pathname.endsWith('/jobs'))value=[]
  else if(url.pathname.endsWith('/inspect')){metrics.inspects++;res.statusCode=400;value={error:'浏览时不应读取模型'}}
  else if(url.pathname.endsWith('/project-cover')){metrics.covers++;metrics.active++;metrics.maxActive=Math.max(metrics.maxActive,metrics.active);await new Promise(resolve=>setTimeout(resolve,120));metrics.active--;value={image:null,thumbnail:null}}
  res.setHeader('Content-Type','application/json');res.end(JSON.stringify(value));return true
 }})
 browser=await chromium.launch({executablePath:chromium.executablePath(),headless:true});const page=await browser.newPage({viewport:{width:1280,height:760}})
 await page.goto(server.url+'__bench__/index.html')
 async function measure(file){return page.evaluate(async({file,items})=>{
  const {createProjectTree}=await import('/__bench__/'+file),container=document.getElementById('project-tree');container.replaceChildren()
  const view=createProjectTree({container,api:async()=>({orders:{}}),onSelect:()=>{},onOpen:()=>{},onStatus:()=>{},onOrderChange:()=>{}});view.update(items);await new Promise(requestAnimationFrame)
  const button=container.querySelector('[data-node-kind=shape] .project-tree-label'),start=performance.now();button.click();const expand_ms=performance.now()-start
  const list=container.querySelector('.project-tree-list');list.scrollTop=600;const scroll=list.scrollTop;view.update(items)
  return {expand_ms,objects:container.querySelectorAll('[data-node-kind=object]').length,scroll_preserved:Math.abs(list.scrollTop-scroll)<1}
 },{file,items:fixture})}
 const before=baseline?await measure('before.js'):null,after=await measure('project-tree.js');assert.equal(after.objects,500);assert.ok(after.expand_ms<1000);assert.ok(after.scroll_preserved);if(before?.expand_ms>200)assert.ok(after.expand_ms<before.expand_ms*.5)
 checks.tree_large_folder_responsive=true;checks.tree_scroll_preserved=true
 await page.goto(server.url+'control.html');await page.locator('[data-workspace=project]').click();releaseInit()
 await page.waitForFunction(()=>document.querySelectorAll('.project-card').length===24)
 await page.waitForTimeout(800);assert.ok(metrics.covers<16,JSON.stringify(metrics));assert.ok(metrics.maxActive<=2);assert.equal(metrics.inspects,0);checks.visible_only_thumbnails_two_workers=true;checks.project_browsing_does_not_inspect_model=true
 const firstCard=await page.locator('.project-card').first().elementHandle();await page.locator('#project-more').click();await page.waitForFunction(()=>document.querySelectorAll('.project-card').length===48);assert.ok(await firstCard.evaluate(node=>node.isConnected));checks.pagination_preserves_existing_cards=true
 for(const query of ['建筑 1','建筑 12','建筑 123','建筑 499'])await page.locator('#project-search').fill(query)
 await page.waitForFunction(()=>document.querySelectorAll('.project-card').length===1&&document.querySelector('.project-card strong').textContent.endsWith('499'))
 assert.ok(metrics.maxActive<=2);checks.rapid_search_keeps_bounded_queue=true
 await page.locator('#project-search').fill('');await page.waitForFunction(()=>document.querySelectorAll('.project-card').length===24)
 await page.locator('[data-workspace=tasks]').click();await page.waitForTimeout(500);const stopped=metrics.covers;await page.waitForTimeout(500);assert.equal(metrics.covers,stopped);checks.hidden_workspace_stops_thumbnail_queue=true
 const result={passed:true,checks,metrics,before,after};await fs.writeFile(path.join(output,'results.json'),JSON.stringify(result,null,2));console.log(JSON.stringify({passed:true,checks:Object.keys(checks).length,before_ms:before?.expand_ms,after_ms:after.expand_ms,metrics,output}))
}finally{await browser?.close();await server?.close()}
