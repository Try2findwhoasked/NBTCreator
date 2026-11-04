const fs=require('node:fs/promises'),path=require('node:path'),crypto=require('node:crypto')
const REPO='Try2findwhoasked/NBTCreator',BASE=`https://api.github.com/repos/${REPO}`
function newer(a,b){const parse=v=>/^v?(\d+)\.(\d+)\.(\d+)$/.exec(v)?.slice(1).map(Number);const x=parse(a),y=parse(b);if(!x||!y)return false;for(let i=0;i<3;i++)if(x[i]!==y[i])return x[i]>y[i];return false}
function createUpdater({directory,version,safeStorage,fetchImpl=fetch}){
 let release=null,state={status:'idle',received:0,total:0},active=false
 const file=path.join(directory,'update-access.json')
 async function credential(){try{return JSON.parse(await fs.readFile(file,'utf8')).encrypted}catch(e){if(e.code==='ENOENT')return null;throw e}}
 async function access(){return {hasToken:!!await credential(),repository:REPO}}
 async function saveAccess(input){if(active)throw Error('请等待当前下载完成');if(input.clear){await fs.rm(file,{force:true});return access()}if(typeof input.token!=='string'||!input.token.trim()||input.token.length>4096)throw Error('填写GitHub只读访问令牌');if(!await safeStorage.isAsyncEncryptionAvailable())throw Error('系统加密不可用，未保存令牌');await fs.mkdir(directory,{recursive:true});await fs.writeFile(file,JSON.stringify({encrypted:Buffer.from(await safeStorage.encryptStringAsync(input.token.trim())).toString('base64')}));return access()}
 async function headers(accept){const encrypted=await credential(),headers={'Accept':accept,'User-Agent':'NBTCreator-Updater','X-GitHub-Api-Version':'2022-11-28'};if(encrypted){const decoded=await safeStorage.decryptStringAsync(Buffer.from(encrypted,'base64'));headers.Authorization='Bearer '+decoded.result}return headers}
 async function request(url,accept='application/vnd.github+json'){
  let response=await fetchImpl(url,{headers:await headers(accept),redirect:'manual',signal:AbortSignal.timeout(180000)})
  if(response.status===302){const next=new URL(response.headers.get('location'));if(next.protocol!=='https:'||!['release-assets.githubusercontent.com','objects.githubusercontent.com'].includes(next.hostname))throw Error('更新服务器返回了不支持的下载地址');response=await fetchImpl(next.href,{redirect:'error',signal:AbortSignal.timeout(180000)})}
  if(!response.ok)throw Error(response.status===404?'未找到可访问的发行版；私有仓库请配置有Contents只读权限的GitHub令牌。':`更新请求失败（HTTP ${response.status}）`)
  return response
 }
 async function check(){if(active)throw Error('正在下载更新');const response=await request(BASE+'/releases/latest');release=await response.json();if(release.draft||release.prerelease||!/^v\d+\.\d+\.\d+$/.test(release.tag_name))throw Error('没有有效的稳定发行版');state={status:'checked',received:0,total:0};return {current:version,latest:release.tag_name,available:newer(release.tag_name,version),notes:String(release.body||'').slice(0,16000),assets:['app-update','portable'].filter(kind=>release.assets?.some(a=>a.name===`NBTCreator-${release.tag_name.slice(1)}-windows-x64-${kind}.zip`))}}
 async function asset(a){if(!a||!Number.isSafeInteger(a.id)||a.id<1)throw Error('更新资产无效');return request(BASE+'/releases/assets/'+a.id,'application/octet-stream')}
 async function download(kind){
  if(active)throw Error('已有更新正在下载');if(!['app-update','portable'].includes(kind))throw Error('未知更新包类型');if(!release)await check();if(active)throw Error('已有更新正在下载');if(!newer(release.tag_name,version))throw Error('当前已是最新或更高版本')
  active=true;let partial
  try{
   const name=`NBTCreator-${release.tag_name.slice(1)}-windows-x64-${kind}.zip`,a=release.assets.find(a=>a.name===name),sum=release.assets.find(a=>a.name===name+'.sha256');if(!a||!sum||sum.size>4096||!Number.isSafeInteger(a.size)||a.size<1||a.size>2*1024**3)throw Error('发行包或校验文件不完整')
   const checksum=(await(await asset(sum)).text()).trim().split(/\s+/);if(!/^[a-f0-9]{64}$/i.test(checksum[0])||checksum.at(-1)!==name)throw Error('更新校验文件无效')
   const folder=path.join(directory,'updates',release.tag_name);await fs.mkdir(folder,{recursive:true});const target=path.join(folder,name);partial=target+'.partial';state={status:'downloading',received:0,total:a.size}
   const response=await asset(a),handle=await fs.open(partial,'w'),hash=crypto.createHash('sha256');try{for await(const chunk of response.body){state.received+=chunk.length;if(state.received>a.size)throw Error('下载大小不符');hash.update(chunk);await handle.writeFile(Buffer.from(chunk))}}finally{await handle.close()}
   if(state.received!==a.size||hash.digest('hex').toLowerCase()!==checksum[0].toLowerCase())throw Error('更新包SHA256校验失败，未采用下载文件')
   await fs.rename(partial,target);partial=null;state={...state,status:'ready',path:target,kind};return {...state}
  }catch(e){state={...state,status:'failed',error:e.message};throw e}finally{active=false;if(partial)await fs.rm(partial,{force:true})}
 }
 return {access,saveAccess,check,download,status:()=>({...state}),folder:()=>path.join(directory,'updates')}
}
module.exports={createUpdater,newer}
