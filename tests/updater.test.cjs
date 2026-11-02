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
