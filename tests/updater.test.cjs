const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs/promises'),os=require('node:os'),path=require('node:path'),crypto=require('node:crypto')
const {createUpdater,newer}=require('../desktop/updater.cjs')
const storage={isAsyncEncryptionAvailable:async()=>true,encryptStringAsync:async s=>Buffer.from(s).map(v=>v^73),decryptStringAsync:async b=>({result:Buffer.from(b).map(v=>v^73).toString()})}
test('versions compare numerically without downgrading or prerelease confusion',()=>{assert.equal(newer('v1.10.0','1.9.0'),true);assert.equal(newer('v1.8.0','1.9.0'),false);assert.equal(newer('v1.10.0-beta','1.9.0'),false)})
test('updates verify checksums and never forward the private token to the CDN',async t=>{
 const directory=await fs.mkdtemp(path.join(os.tmpdir(),'nbt-updater-'));t.after(()=>fs.rm(directory,{recursive:true,force:true}))
 const bytes=Buffer.from('zip-data'),hash=crypto.createHash('sha256').update(bytes).digest('hex'),name='NBTCreator-9.0.0-windows-x64-app-update.zip';let bad=false,tokenOnCDN=false
 const fetchImpl=async(url,options)=>{
  if(url.endsWith('/latest'))return Response.json({tag_name:'v9.0.0',assets:[{id:1,name,size:bytes.length},{id:2,name:name+'.sha256',size:100}],body:'notes'})
  if(url.endsWith('/2'))return new Response(`${bad?'0'.repeat(64):hash}  ${name}\n`)
  if(url.endsWith('/1'))return new Response(null,{status:302,headers:{location:'https://release-assets.githubusercontent.com/data'}})
  tokenOnCDN=!!options.headers?.Authorization;return new Response(bytes)
 }
 const service=createUpdater({directory,version:'1.8.0',safeStorage:storage,fetchImpl})
 await service.saveAccess({token:'private-token'});assert.ok(!(await fs.readFile(path.join(directory,'update-access.json'),'utf8')).includes('private-token'));assert.equal((await service.check()).available,true)
 const downloaded=await service.download('app-update');assert.deepEqual(await fs.readFile(downloaded.path),bytes);assert.equal(tokenOnCDN,false)
 bad=true;await assert.rejects(service.download('app-update'),/SHA256/);assert.deepEqual(await fs.readFile(downloaded.path),bytes);assert.equal((await fs.readdir(path.dirname(downloaded.path))).some(f=>f.endsWith('.partial')),false)
 await service.saveAccess({clear:true});assert.equal((await service.access()).hasToken,false)
})
test('unexpected download redirects are rejected',async t=>{
 const directory=await fs.mkdtemp(path.join(os.tmpdir(),'nbt-updater-'));t.after(()=>fs.rm(directory,{recursive:true,force:true}))
 const service=createUpdater({directory,version:'1.8.0',safeStorage:storage,fetchImpl:async()=>new Response(null,{status:302,headers:{location:'https://example.com/stolen'}})})
 await assert.rejects(service.check(),/不支持的下载地址/)
})

const deferred=()=>{let resolve;const promise=new Promise(r=>resolve=r);return {promise,resolve}}
async function fixture(t,fetchImpl){const directory=await fs.mkdtemp(path.join(os.tmpdir(),'nbt-updater-'));t.after(()=>fs.rm(directory,{recursive:true,force:true}));return {directory,service:createUpdater({directory,version:'1.8.0',safeStorage:storage,fetchImpl})}}
const name='NBTCreator-9.0.0-windows-x64-app-update.zip',bytes=Buffer.from('verified-zip'),checksum=crypto.createHash('sha256').update(bytes).digest('hex')+'  '+name+'\n'
const release=()=>({tag_name:'v9.0.0',assets:[{id:1,name,size:bytes.length},{id:2,name:name+'.sha256',size:Buffer.byteLength(checksum)}]})

test('a pending release check excludes downloads, other checks and credential changes',async t=>{
 const started=deferred(),gate=deferred();let requests=0
 const {service}=await fixture(t,async()=>{requests++;started.resolve();await gate.promise;return Response.json(release())})
 const checking=service.check();await started.promise
 const rejected=[assert.rejects(service.download('app-update'),/正在|等待/),assert.rejects(service.check(),/正在|等待/),assert.rejects(service.saveAccess({clear:true}),/正在|等待/)]
 gate.resolve();await Promise.all([checking,...rejected])
 assert.equal(requests,1)
})

test('failed release checks cannot cache a prerelease or keep offering an older result',async t=>{
 let latest=release(),assetCalls=0
 const {service}=await fixture(t,async url=>{if(url.endsWith('/latest'))return Response.json(latest);assetCalls++;throw Error('unexpected asset request')})
 assert.equal((await service.check()).available,true)
 latest={...release(),prerelease:true};await assert.rejects(service.check(),/稳定发行版/)
 await assert.rejects(service.download('app-update'),/稳定发行版/)
 assert.equal(assetCalls,0)
 for(const invalid of [null,{...release(),tag_name:['v9.0.0']},{...release(),assets:null}]){latest=invalid;await assert.rejects(service.check(),/稳定发行版/)}
 latest=release();assert.equal((await service.check()).available,true)
})

test('only unambiguous packages with valid checksum metadata are offered',async t=>{
 let latest=release()
 const {service}=await fixture(t,async()=>Response.json(latest))
 for(const assets of [[],[release().assets[0]],[...release().assets,release().assets[0]],[release().assets[0],{...release().assets[1],size:0}],[release().assets[0],{...release().assets[1],size:4097}],[{...release().assets[0],id:0},release().assets[1]]]){
  latest={...release(),assets};const result=await service.check();assert.deepEqual(result.assets,[]);assert.equal(result.available,true)
 }
 latest=release();assert.deepEqual((await service.check()).assets,['app-update'])
})

test('checksum bodies are bounded while reading, regardless of declared size',async t=>{
 let cancelled=false,pulls=0
 const {service,directory}=await fixture(t,async url=>{
  if(url.endsWith('/latest'))return Response.json(release())
  assert.ok(url.endsWith('/2'),'package must not be requested before checksum validation')
  return new Response(new ReadableStream({pull(controller){pulls++;if(pulls>8)controller.close();else controller.enqueue(new Uint8Array(1024))},cancel(){cancelled=true}}))
 })
 await assert.rejects(service.download('app-update'),/校验文件.*过大/)
 assert.equal(cancelled,true);assert.ok(pulls<8);assert.equal(service.status().status,'failed')
 assert.deepEqual(await fs.readdir(directory),[])
})

test('release metadata is bounded and invalid JSON reports a release error',async t=>{
 let invalid=false,cancelled=false,pulls=0
 const {service}=await fixture(t,async()=>invalid?new Response('{broken'):new Response(new ReadableStream({pull(controller){pulls++;if(pulls>80)controller.close();else controller.enqueue(new Uint8Array(65536))},cancel(){cancelled=true}})))
 await assert.rejects(service.check(),/发行版.*过大/);assert.equal(cancelled,true);assert.ok(pulls<80)
 invalid=true;await assert.rejects(service.check(),/稳定发行版/)
})

test('failed streams preserve a verified ZIP, clear stale status and allow retry',async t=>{
 let mode='ok',cancelled=false
 const {service}=await fixture(t,async url=>{
  if(url.endsWith('/latest'))return Response.json(release())
  if(url.endsWith('/2'))return new Response(mode==='checksum'?'invalid':checksum)
  if(mode==='short')return new Response(bytes.subarray(1))
  if(mode==='large')return new Response(new ReadableStream({pull(controller){controller.enqueue(new Uint8Array(bytes.length+1))},cancel(){cancelled=true}}))
  return new Response(bytes)
 })
 const ready=await service.download('app-update')
 for(const value of ['checksum','short','large']){
  mode=value;await assert.rejects(service.download('app-update'),/大小|SHA256|校验文件/)
  assert.equal(service.status().status,'failed');assert.equal(service.status().path,undefined);assert.equal(service.status().kind,undefined)
  assert.deepEqual(await fs.readFile(ready.path),bytes);assert.deepEqual(await fs.readdir(path.dirname(ready.path)),[name])
 }
 assert.equal(cancelled,true);mode='ok';assert.equal((await service.download('app-update')).status,'ready')
})

test('credential changes are exclusive and invalidate the previously checked release',async t=>{
 const started=deferred(),gate=deferred();let latestCalls=0
 const directory=await fs.mkdtemp(path.join(os.tmpdir(),'nbt-updater-'));t.after(()=>fs.rm(directory,{recursive:true,force:true}))
 const service=createUpdater({directory,version:'1.8.0',safeStorage:{...storage,encryptStringAsync:async value=>{started.resolve();await gate.promise;return storage.encryptStringAsync(value)}},fetchImpl:async url=>{
  if(url.endsWith('/latest')){latestCalls++;return Response.json(release())}
  return new Response(url.endsWith('/2')?checksum:bytes)
 }})
 await service.check();const saving=service.saveAccess({token:'fixture-token'});await started.promise
 const rejected=[assert.rejects(service.check(),/正在保存/),assert.rejects(service.download('app-update'),/正在保存/),assert.rejects(service.saveAccess({clear:true}),/正在保存/)]
 gate.resolve();await Promise.all([saving,...rejected]);await service.download('app-update');assert.equal(latestCalls,2)
 await service.saveAccess({clear:true});await service.download('app-update');assert.equal(latestCalls,3)
})
