import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import path from 'node:path'
import http from 'node:http'
import {pathToFileURL} from 'node:url'
import {root,skill} from '../../scripts/paths.mjs'
const {createViewerServer}=await import(pathToFileURL(path.join(skill,'assets/viewer/viewer-server.mjs')).href)
const {startDetailServer}=await import(pathToFileURL(path.join(skill,'assets/viewer/detail-server.mjs')).href)
const output=path.join(root,'build','production-server-'+Date.now());await fs.mkdir(output,{recursive:true})
const snapshot=path.join(output,'model.json');await fs.writeFile(snapshot,JSON.stringify({fixture:true}))
let server;const checks={}
try{
 server=await createViewerServer({model:snapshot,frontendMode:'production'})
 assert.equal(server.frontend,'production');const control=await fetch(server.url+'control.html');const html=await control.text();assert.equal(control.status,200);assert.ok(!html.includes('/@vite/client'));assert.ok(!html.includes('/src/control.js'));checks.built_html_only=true
 const asset=html.match(/src="([^"]+\.js)"/)[1];assert.equal((await fetch(new URL(asset,server.url))).status,200)
 for(const route of ['src/control.js','node_modules/vite/package.json','@vite/client','.env','../../package.json','%2e%2e%2f%2e%2e%2fpackage.json']){const r=await fetch(server.url+route);assert.ok([403,404].includes(r.status),route)}checks.no_source_or_dev_endpoints=true
 assert.equal((await fetch(server.url,{headers:{Origin:'https://example.com'}})).status,403);checks.origin_rejection=true
 const spoof=await new Promise(resolve=>{http.get(server.url,{headers:{Host:'example.com'}},res=>{res.resume();resolve(res.statusCode)})});assert.equal(spoof,403);checks.host_rejection=true
 assert.deepEqual(await(await fetch(server.url+'__nbt_modeler__/model.json')).json(),{fixture:true});checks.registered_snapshot=true
 const manifest=JSON.parse(await fs.readFile(path.join(skill,'assets/viewer/web-dist/frontend-manifest.json'),'utf8'));const pack=manifest.files.find(f=>f.path.startsWith('default-pack/'));assert.ok(pack)
 assert.equal((await fetch(server.url+'__minecraft_builder__/'+pack.path)).status,200);checks.bundled_texture_pack=true
 const head=await fetch(server.url+'control.html',{method:'HEAD'});assert.equal(head.status,200);assert.ok(Number(head.headers.get('content-length'))>0);checks.head_support=true
 await server.close();server=null;checks.clean_shutdown=true
 const portable=path.join(output,'portable');await fs.mkdir(portable);await fs.copyFile(path.join(skill,'assets/viewer/viewer-server.mjs'),path.join(portable,'viewer-server.mjs'));await fs.cp(path.join(skill,'assets/viewer/web-dist'),path.join(portable,'web-dist'),{recursive:true})
 const {createViewerServer:createPortable}=await import(pathToFileURL(path.join(portable,'viewer-server.mjs')).href)
 server=await createPortable({model:snapshot,frontendMode:'production'});assert.equal((await fetch(server.url+'control.html')).status,200);await server.close();server=null;checks.production_runs_without_node_modules=true
 server=await createViewerServer({model:snapshot,frontendMode:'development'});assert.equal(server.frontend,'development');assert.ok((await(await fetch(server.url+'control.html')).text()).includes('/@vite/client'));await server.close();server=null;checks.explicit_development_fallback=true
 const workspace=path.join(output,'workspace');await fs.mkdir(workspace)
 server=await startDetailServer({workspace,frontendMode:'production'})
 const recent=new URL('/__detail__/edit-sessions/recent',server.url)
 const response=await fetch(recent);assert.equal(response.status,200);assert.deepEqual(await response.json(),{recent:null})
 assert.equal((await fetch(recent,{headers:{Origin:'https://example.com'}})).status,403)
 const editSpoof=await new Promise((resolve,reject)=>http.get(recent,{headers:{Host:'example.com'}},res=>{res.resume();resolve(res.statusCode)}).on('error',reject))
 assert.equal(editSpoof,403)
 const load=await fetch(new URL('load',recent),{method:'POST',body:JSON.stringify({source:path.join(workspace,'nbt_models','unopened.snbt')})})
 assert.equal(load.status,400);assert.match((await load.json()).error,/请先打开完整建筑/)
 const activity = new URL('/__detail__/ai-activities', server.url)
 const post = async data => {
  const response = await fetch(activity, { method: 'POST', body: JSON.stringify(data) })
  assert.ok(response.ok)
  return response.json()
 }
 const first = await post({action:'start', workflow:'prompt', instruction:'first job'})
 const second = await post({action:'start', workflow:'prompt', label:'Latest job', instruction:'full detail only'})
 await post({action:'finish', id:second.id, status:'complete', message:'summary event'})
 const summaries = new URL('/__detail__/jobs?view=summary&limit=1', server.url)
 const latest = await fetch(summaries)
 const tag = latest.headers.get('ETag')
 const page = await latest.json()
 assert.equal(page.total, 2)
 assert.equal(page.items.length, 1)
 assert.equal(page.items[0].id, second.id)
 assert.equal(page.items[0].last_message, 'summary event')
 assert.equal(page.items[0].instruction, undefined)
 assert.equal(page.items[0].events, undefined)
 assert.equal((await fetch(summaries, {headers:{'If-None-Match':tag}})).status, 304)
 const pending = new URL(summaries)
 pending.searchParams.set('offset', '1')
 assert.equal((await (await fetch(pending)).json()).items[0].id, first.id)
 const filtered = new URL(summaries)
 filtered.searchParams.set('status', 'complete')
 filtered.searchParams.set('q', 'full detail')
 assert.equal((await (await fetch(filtered)).json()).matched, 1)
 const detail = await (await fetch(new URL('/__detail__/jobs/' + second.id, server.url))).json()
 assert.equal(detail.instruction, 'full detail only')
 assert.equal(detail.events.length, 2)
 await post({action:'stage', id:second.id, phase:'preview', message:'updated'})
 const refreshed = await fetch(summaries, {headers:{'If-None-Match':tag}})
 assert.equal(refreshed.status, 200)
 assert.equal((await refreshed.json()).items[0].last_message, 'updated')
 checks.task_summary_pagination_filters_and_conditional_polling=true
 await server.close();server=null;checks.edit_session_routes_use_shared_http_guards=true
 await fs.writeFile(path.join(output,'results.json'),JSON.stringify({passed:true,checks},null,2));console.log(JSON.stringify({passed:true,checks:Object.keys(checks).length,output}))
}finally{await server?.close()}
