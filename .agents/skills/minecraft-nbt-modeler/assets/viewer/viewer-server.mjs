// Static production host. Vite is imported only for explicit/unbuilt development.
import fs from 'node:fs/promises'
import {createReadStream} from 'node:fs'
import {createServer} from 'node:http'
import path from 'node:path'
import {fileURLToPath} from 'node:url'
const root=path.dirname(fileURLToPath(import.meta.url))
const contentTypes={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.mjs':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.json':'application/json; charset=utf-8','.png':'image/png','.jpg':'image/jpeg','.webp':'image/webp','.svg':'image/svg+xml','.woff2':'font/woff2','.wasm':'application/wasm'}
async function exists(file){try{await fs.access(file);return true}catch{return false}}
export async function createViewerServer({model,port=0,quiet=true,apiHandler,modelResolver,frontendMode='auto'}={}){
 if(!['auto','production','development'].includes(frontendMode))throw Error('Invalid frontend mode')
 const web=path.join(root,'web-dist'),ready=await exists(path.join(web,'frontend-manifest.json'))
 if(frontendMode==='development'||frontendMode==='auto'&&!ready){
  const {createDevViewerServer}=await import('./viewer-server-dev.mjs')
  return {...await createDevViewerServer({model,port,quiet,apiHandler,modelResolver}),frontend:'development'}
 }
 if(!ready)throw Error('Production frontend missing. Run npm run build:web before packaging.')
 for(const file of ['index.html','control.html','default-pack'])if(!await exists(path.join(web,file)))throw Error('Incomplete production frontend: '+file)
 if(!Number.isInteger(port)||port<0||port>65535)throw Error('Invalid port')
 if(model){model=path.resolve(model);await fs.access(model)}
 const server=createServer(async(req,res)=>{
  try{
   const host=req.headers.host??'',origin=req.headers.origin
   if(!/^127\.0\.0\.1:\d+$/.test(host)||origin&&origin!==`http://${host}`||req.headers['sec-fetch-site']==='cross-site'){res.writeHead(403);res.end('Local viewer requests only');return}
   const url=new URL(req.url,`http://${host}`)
   if(apiHandler&&await apiHandler(req,res,url))return
   if(req.method!=='GET'&&req.method!=='HEAD'){res.writeHead(405);res.end('Method not allowed');return}
   let target,dynamic=false
   if(url.pathname==='/__nbt_modeler__/model.json'){
    target=modelResolver?modelResolver(url.searchParams.get('model_key')):model;dynamic=true
    if(!target){res.writeHead(404);res.end('No selected model');return}
   }else{
    let relative=decodeURIComponent(url.pathname)
    if(relative.startsWith('/__minecraft_builder__/default-pack/'))relative='/default-pack/'+relative.slice('/__minecraft_builder__/default-pack/'.length)
    if(relative==='/')relative='/index.html'
    target=path.resolve(web,'.'+relative)
    if(!target.startsWith(web+path.sep)||relative.includes('\\')||relative.includes('\0')){res.writeHead(403);res.end('Invalid asset path');return}
   }
   let stat;try{stat=await fs.stat(target)}catch{res.writeHead(404);res.end('Not found');return}
   if(!stat.isFile()){res.writeHead(404);res.end('Not found');return}
   res.setHeader('Content-Type',contentTypes[path.extname(target)]??'application/octet-stream')
   res.setHeader('X-Content-Type-Options','nosniff')
   res.setHeader('Cache-Control',dynamic||target.endsWith('.html')?'no-store':'private, max-age=3600')
   res.setHeader('Content-Length',stat.size)
   if(req.method==='HEAD'){res.end();return}
   createReadStream(target).on('error',()=>res.destroy()).pipe(res)
  }catch{if(!res.headersSent){res.writeHead(400);res.end('Invalid request')}else res.destroy()}
 })
 await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(port,'127.0.0.1',resolve)})
 return {url:`http://127.0.0.1:${server.address().port}/`,frontend:'production',close:()=>new Promise((resolve,reject)=>{server.close(error=>error?reject(error):resolve());server.closeAllConnections?.()})}
}
