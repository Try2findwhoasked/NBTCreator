import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import path from 'node:path'
import http from 'node:http'
import {pathToFileURL} from 'node:url'
import {root,skill} from '../scripts/paths.mjs'
const {createViewerServer}=await import(pathToFileURL(path.join(skill,'assets/viewer/viewer-server.mjs')).href)
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
 await fs.writeFile(path.join(output,'results.json'),JSON.stringify({passed:true,checks},null,2));console.log(JSON.stringify({passed:true,checks:Object.keys(checks).length,output}))
}finally{await server?.close()}
