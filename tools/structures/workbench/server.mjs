// Independent structure workbench. Only the on-demand renderer uses toolkit UI code.
import fs from 'node:fs/promises'
import {createReadStream} from 'node:fs'
import {createServer} from 'node:http'
import path from 'node:path'
import {fileURLToPath,pathToFileURL} from 'node:url'
import {spawn} from 'node:child_process'
import {randomUUID,createHash} from 'node:crypto'
import {parseArgs} from 'node:util'
import {structureLibrary} from './api/library.mjs'
import {modStructures} from './api/mod-structures.mjs'

const here=path.dirname(fileURLToPath(import.meta.url)),web=path.join(here,'web')
const mime={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.png':'image/png','.jpg':'image/jpeg','.json':'application/json; charset=utf-8'}
const json=(res,value,status=200)=>{res.statusCode=status;res.setHeader('Content-Type',mime['.json']);res.setHeader('Cache-Control','no-store');res.end(JSON.stringify(value))}
async function body(req){let value='';req.setEncoding('utf8');for await(const chunk of req){value+=chunk;if(Buffer.byteLength(value)>1024*1024)throw new Error('请求超过1MiB')}return JSON.parse(value)}
function invoke(python,backend,workspace,args,env){return new Promise((resolve,reject)=>{const child=spawn(python,['-B',backend,...args,'--workspace',workspace],{cwd:workspace,windowsHide:true,shell:false,env});let stdout='',stderr='';child.stdout.setEncoding('utf8');child.stderr.setEncoding('utf8');child.stdout.on('data',chunk=>stdout+=chunk);child.stderr.on('data',chunk=>stderr+=chunk);child.on('error',reject);child.on('close',code=>{try{const result=JSON.parse(stdout);if(code||!result.ok)throw new Error(result.error||stderr);resolve(result.result)}catch(error){reject(error)}})})}

async function migrateLegacy(workspace,dataRoot){
  const marker=path.join(dataRoot,'legacy_migration.json')
  try{await fs.access(marker);return}catch{}
  const legacy=path.join(workspace,'build/nbt_control'),files=[]
  // Retain the originals and their receipts; future writes go only to the new root.
  for(const name of ['structure_library.json','mod_structure_changes']){
    async function copy(relative){const source=path.join(legacy,relative),target=path.join(dataRoot,relative);let info;try{info=await fs.lstat(source)}catch(error){if(error.code==='ENOENT')return;throw error}if(info.isSymbolicLink())throw new Error('旧工作台数据包含符号链接：'+source)
      if(info.isDirectory()){for(const entry of await fs.readdir(source))await copy(path.join(relative,entry));return}
      if(!info.isFile())return;const bytes=await fs.readFile(source),sha256=createHash('sha256').update(bytes).digest('hex');await fs.mkdir(path.dirname(target),{recursive:true});let copied=true
      try{await fs.writeFile(target,bytes,{flag:'wx'})}catch(error){if(error.code!=='EEXIST')throw error;copied=false}
      files.push({source,target,sha256,copied,retained_original:true})
      if(copied&&createHash('sha256').update(await fs.readFile(target)).digest('hex')!==sha256)throw new Error('工作台迁移校验失败')
    }await copy(name)
  }
  const temporary=marker+'.'+randomUUID()+'.tmp';await fs.writeFile(temporary,JSON.stringify({status:'complete',files},null,2));await fs.rename(temporary,marker)
}

export async function startWorkbenchServer({workspace,python='python',port=0,dataRoot,toolkit,library=false}={}){
  workspace=path.resolve(workspace??path.resolve(here,'../../..'))
  dataRoot=path.resolve(dataRoot??path.join(workspace,'build/structure_workbench'))
  toolkit=path.resolve(toolkit??process.env.SAODG_NBT_TOOLKIT??path.join(path.resolve(here,'../../..'),'.agents/skills/minecraft-nbt-modeler'))
  if(!Number.isInteger(port)||port<0||port>65535)throw new Error('无效端口')
  if(dataRoot===toolkit||dataRoot.startsWith(toolkit+path.sep))throw new Error('工作台数据必须存放在细节控制台目录之外')
  await fs.mkdir(dataRoot,{recursive:true});await migrateLegacy(workspace,dataRoot)
  const assets=new Map(),env={...process.env,SAODG_NBT_TOOLKIT:toolkit};let preview,editorChild,editorUrl=null,editorPending
  const asset=file=>{const id=randomUUID();assets.set(id,path.resolve(file));return '/api/asset/'+id}
  const releasePreview=async()=>{await preview?.close();preview=null}
  async function openPreview(model){await releasePreview();const {createViewerServer}=await import(pathToFileURL(path.join(toolkit,'assets/viewer/viewer-server.mjs')));preview=await createViewerServer({model,port:0});return preview.url+'?quality=fast&pixelRatio=0.75&maxFps=24'}
  const libraryApi=structureLibrary({workspace,dataRoot,json,asset,invoke:args=>invoke(python,path.join(here,'library_backend.py'),workspace,args,env)})
  const modApi=modStructures({workspace,python,dataRoot,env,backend:path.join(here,'backend.py'),asset,openPreview,json,body})
  async function openEditor(source){
    const catalog=await libraryApi.catalog();if(!catalog.models.some(model=>model.source===source))throw new Error('请选择作者库中完整登记的结构')
    if(!editorUrl){
      editorPending??=new Promise((resolve,reject)=>{
        const child=spawn(process.execPath,[path.join(toolkit,'assets/viewer/detail-server.mjs'),'--workspace',workspace,'--python',python,'--port','0','--no-open'],{cwd:workspace,windowsHide:true,shell:false});editorChild=child
        let value='',stderr='';const timer=setTimeout(()=>{child.kill();reject(new Error('细节控制台启动超时'))},30000)
        child.stdout.setEncoding('utf8');child.stderr.setEncoding('utf8');child.stderr.on('data',chunk=>stderr+=chunk)
        child.stdout.on('data',chunk=>{value+=chunk;const line=value.split('\n').find(line=>line.trim().startsWith('{'));if(!line)return;try{const result=JSON.parse(line);if(result.url){clearTimeout(timer);editorUrl=result.url;resolve(editorUrl)}}catch{}})
        child.on('error',error=>{clearTimeout(timer);reject(error)});child.on('exit',()=>{clearTimeout(timer);editorChild=null;editorUrl=null;editorPending=null;reject(new Error('细节控制台已退出 '+stderr))})
      }).catch(error=>{editorPending=null;throw error})
      await editorPending
    }
    const target=new URL(editorUrl);target.searchParams.set('source',source);return target.href
  }
  const server=createServer(async(req,res)=>{try{
    const host=req.headers.host??'',origin=req.headers.origin
    if(!/^127\.0\.0\.1:\d+$/.test(host)||(origin&&origin!==`http://${host}`)||req.headers['sec-fetch-site']==='cross-site'){res.statusCode=403;res.end('Local workbench requests only');return}
    const url=new URL(req.url,'http://'+host)
    if(await libraryApi.handle(req,res,url,body))return
    if(await modApi(req,res,url))return
    if(req.method==='GET'&&url.pathname==='/api/workbench'){json(res,{workspace,data_root:dataRoot,toolkit,editor_url:editorUrl,features:['mod_structures','author_library']});return}
    if(req.method==='POST'&&url.pathname==='/api/editor/open'){json(res,{url:await openEditor((await body(req)).source)});return}
    if(req.method==='POST'&&url.pathname==='/api/preview/release'){await releasePreview();json(res,{released:true});return}
    let file
    if(url.pathname.startsWith('/api/asset/'))file=assets.get(url.pathname.split('/').at(-1))
    else if(!url.pathname.startsWith('/api/')&&req.method==='GET'){
      const pathname=url.pathname==='/'?'/mod-structures.html':decodeURIComponent(url.pathname);const candidate=path.resolve(web,'.'+pathname)
      if(candidate.startsWith(web+path.sep)&&['.html','.css','.js'].includes(path.extname(candidate))){let real;try{real=await fs.realpath(candidate)}catch(error){if(error.code!=='ENOENT')throw error}if(real?.startsWith(web+path.sep))file=real}
    }
    if(!file){json(res,{error:'未找到工作台资源'},404);return}
    res.setHeader('Content-Type',mime[path.extname(file)]??'application/octet-stream');res.setHeader('Cache-Control','no-store');createReadStream(file).on('error',()=>{res.statusCode=404;res.end()}).pipe(res)
  }catch(error){json(res,{error:error.message},400)}})
  await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(port,'127.0.0.1',resolve)})
  return {url:`http://127.0.0.1:${server.address().port}/${library?'library.html':'mod-structures.html'}`,dataRoot,close:async()=>{await releasePreview();editorChild?.kill();await new Promise(resolve=>server.close(resolve))}}
}

async function main(){const {values}=parseArgs({options:{workspace:{type:'string'},python:{type:'string'},port:{type:'string',default:'0'},'data-root':{type:'string'},toolkit:{type:'string'},library:{type:'boolean'},'no-open':{type:'boolean'}}});const app=await startWorkbenchServer({...values,dataRoot:values['data-root'],port:Number(values.port)});console.log(JSON.stringify({url:app.url,data_root:app.dataRoot}));if(!values['no-open']){const child=spawn(process.platform==='win32'?'cmd':process.platform==='darwin'?'open':'xdg-open',process.platform==='win32'?['/c','start','',app.url]:[app.url],{windowsHide:true,detached:true,stdio:'ignore'});child.on('error',()=>{});child.unref()}const stop=async()=>{await app.close();process.exit(0)};process.on('SIGINT',stop);process.on('SIGTERM',stop)}
if(process.argv[1]&&import.meta.url===pathToFileURL(path.resolve(process.argv[1])).href)main().catch(error=>{console.error(error.stack);process.exitCode=1})
