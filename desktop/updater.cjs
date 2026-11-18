const fs=require('node:fs/promises'),path=require('node:path'),crypto=require('node:crypto')
const REPO='Try2findwhoasked/NBTCreator',BASE=`https://api.github.com/repos/${REPO}`
function newer(a,b){const parse=v=>/^v?(\d+)\.(\d+)\.(\d+)$/.exec(v)?.slice(1).map(Number);const x=parse(a),y=parse(b);if(!x||!y)return false;for(let i=0;i<3;i++)if(x[i]!==y[i])return x[i]>y[i];return false}
function createUpdater({directory,version,safeStorage,fetchImpl=fetch}){
 let release=null,state={status:'idle',received:0,total:0},active=null
 const file=path.join(directory,'update-access.json')
 async function exclusive(operation,run){
  if(active)throw Error(active==='checking'?'正在检查更新，请等待完成':active==='saving'?'正在保存更新访问配置，请等待完成':'正在下载更新，请等待完成')
  active=operation;try{return await run()}finally{active=null}
 }
 async function credential(){try{return JSON.parse(await fs.readFile(file,'utf8')).encrypted}catch(e){if(e.code==='ENOENT')return null;throw e}}
 async function access(){return {hasToken:!!await credential(),repository:REPO}}
 async function saveAccess(input){return exclusive('saving',async()=>{
  if(input.clear){await fs.rm(file,{force:true});release=null;return access()}
  if(typeof input.token!=='string'||!input.token.trim()||input.token.length>4096)throw Error('填写GitHub只读访问令牌')
  if(!await safeStorage.isAsyncEncryptionAvailable())throw Error('系统加密不可用，未保存令牌')
  await fs.mkdir(directory,{recursive:true});await fs.writeFile(file,JSON.stringify({encrypted:Buffer.from(await safeStorage.encryptStringAsync(input.token.trim())).toString('base64')}));release=null;return access()
 })}
 async function headers(accept){const encrypted=await credential(),headers={'Accept':accept,'User-Agent':'NBTCreator-Updater','X-GitHub-Api-Version':'2022-11-28'};if(encrypted){const decoded=await safeStorage.decryptStringAsync(Buffer.from(encrypted,'base64'));headers.Authorization='Bearer '+decoded.result}return headers}
 async function request(url,accept='application/vnd.github+json'){
  let response=await fetchImpl(url,{headers:await headers(accept),redirect:'manual',signal:AbortSignal.timeout(180000)})
  if(response.status===302){await response.body?.cancel().catch(()=>{});const next=new URL(response.headers.get('location'));if(next.protocol!=='https:'||!['release-assets.githubusercontent.com','objects.githubusercontent.com'].includes(next.hostname))throw Error('更新服务器返回了不支持的下载地址');response=await fetchImpl(next.href,{redirect:'error',signal:AbortSignal.timeout(180000)})}
  if(!response.ok){await response.body?.cancel().catch(()=>{});throw Error(response.status===404?'未找到可访问的发行版；私有仓库请配置有Contents只读权限的GitHub令牌。':`更新请求失败（HTTP ${response.status}）`)}
  return response
 }
 async function boundedText(response,limit,label){
  if(!response.body)throw Error(label+'为空')
  const chunks=[];let size=0
  for await(const chunk of response.body){size+=chunk.length;if(size>limit)throw Error(label+'过大');chunks.push(Buffer.from(chunk))}
  return Buffer.concat(chunks,size).toString('utf8')
 }
 async function readRelease(){
  const text=await boundedText(await request(BASE+'/releases/latest'),4*1024*1024,'更新发行版信息');let candidate
  try{candidate=JSON.parse(text)}catch{throw Error('没有有效的稳定发行版')}
  if(!candidate||candidate.draft||candidate.prerelease||typeof candidate.tag_name!=='string'||!/^v\d+\.\d+\.\d+$/.test(candidate.tag_name)||!Array.isArray(candidate.assets))throw Error('没有有效的稳定发行版')
  return candidate
 }
 function packageAssets(release,kind){
  const name=`NBTCreator-${release.tag_name.slice(1)}-windows-x64-${kind}.zip`,packages=release.assets.filter(a=>a?.name===name),checksums=release.assets.filter(a=>a?.name===name+'.sha256')
  const valid=(a,max)=>Number.isSafeInteger(a?.id)&&a.id>0&&Number.isSafeInteger(a.size)&&a.size>0&&a.size<=max
  if(packages.length!==1||checksums.length!==1||!valid(packages[0],2*1024**3)||!valid(checksums[0],4096)||packages[0].id===checksums[0].id)return null
  return {name,archive:packages[0],checksum:checksums[0]}
 }
 async function check(){return exclusive('checking',async()=>{
  release=null;state={status:'checking',received:0,total:0}
  try{release=await readRelease();state={status:'checked',received:0,total:0};return {current:version,latest:release.tag_name,available:newer(release.tag_name,version),notes:String(release.body||'').slice(0,16000),assets:['app-update','portable'].filter(kind=>packageAssets(release,kind))}}
  catch(e){state={status:'failed',received:0,total:0,error:e.message};throw e}
 })}
 async function asset(a){if(!a||!Number.isSafeInteger(a.id)||a.id<1)throw Error('更新资产无效');return request(BASE+'/releases/assets/'+a.id,'application/octet-stream')}
 async function download(kind){
  if(!['app-update','portable'].includes(kind))throw Error('未知更新包类型')
  return exclusive('downloading',async()=>{
   let partial;state={status:'downloading',received:0,total:0}
   try{
    if(!release)release=await readRelease()
    if(!newer(release.tag_name,version))throw Error('当前已是最新或更高版本')
    const assets=packageAssets(release,kind);if(!assets)throw Error('发行包或校验文件不完整')
    const {name,archive:a,checksum:sum}=assets
    const checksum=(await boundedText(await asset(sum),4096,'更新校验文件')).trim().split(/\s+/);if(checksum.length!==2||!/^[a-f0-9]{64}$/i.test(checksum[0])||checksum[1]!==name)throw Error('更新校验文件无效')
    const folder=path.join(directory,'updates',release.tag_name);await fs.mkdir(folder,{recursive:true});const target=path.join(folder,name);partial=target+'.partial';state={status:'downloading',received:0,total:a.size}
    const response=await asset(a),hash=crypto.createHash('sha256');let handle
    try{handle=await fs.open(partial,'w');for await(const chunk of response.body){state.received+=chunk.length;if(state.received>a.size)throw Error('下载大小不符');hash.update(chunk);await handle.writeFile(Buffer.from(chunk))}}
    finally{try{await handle?.close()}finally{await response.body?.cancel().catch(()=>{})}}
    if(state.received!==a.size||hash.digest('hex').toLowerCase()!==checksum[0].toLowerCase())throw Error('更新包SHA256校验失败，未采用下载文件')
    await fs.rename(partial,target);partial=null;state={...state,status:'ready',path:target,kind};return {...state}
   }catch(e){
    let error=e
    if(partial)try{await fs.rm(partial,{force:true})}catch{error=Error(e.message+'；临时下载文件清理失败，可稍后重试')}
    state={status:'failed',received:state.received,total:state.total,error:error.message};throw error
   }
  })
 }
 async function migrationTool(expected){
  return exclusive('migration-tool',async()=>{
   if(!/^\d+\.\d+\.\d+$/.test(version))throw Error('当前版本请使用随附迁移工具')
   const name='NBTCreator-'+version+'-constraint-room-migration.py'
   const cache=path.join(directory,'tools','constraint-room-migration',version,name)
   try{if((await fs.readFile(cache)).equals(expected))return cache}catch(error){if(error.code!=='ENOENT')throw error}
   const tag=JSON.parse(await boundedText(await request(BASE+'/releases/tags/v'+version),4*1024*1024,'迁移工具发行信息'))
   const candidates=tag.assets?.filter(item=>item?.name===name)
   if(tag.tag_name!=='v'+version||tag.draft||candidates?.length!==1||candidates[0].size!==expected.length)
    throw Error('找不到与应用匹配的迁移工具；可使用随附版本')
   const downloaded=Buffer.from(await boundedText(await asset(candidates[0]),expected.length,'迁移工具'))
   if(!downloaded.equals(expected))throw Error('迁移工具 SHA-256 内容校验失败')
   await fs.mkdir(path.dirname(cache),{recursive:true});await fs.writeFile(cache,downloaded)
   return cache
  })
 }
 return {access,saveAccess,check,download,migrationTool,status:()=>({...state}),folder:()=>path.join(directory,'updates')}
}
module.exports={createUpdater,newer}
