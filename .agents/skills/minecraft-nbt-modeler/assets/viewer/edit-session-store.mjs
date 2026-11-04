import fs from 'node:fs/promises'
import {createReadStream,constants} from 'node:fs'
import path from 'node:path'
import {createHash,randomUUID} from 'node:crypto'
import net from 'node:net'
import {aiGroupMatches,aiComponentCamera} from './src/ai-component.mjs'
import {validateAICandidate} from './src/ai-candidate.mjs'
const SHA=/^[a-f0-9]{64}$/
const plain=value=>value&&typeof value==='object'&&!Array.isArray(value)
const keys=(value,allowed)=>plain(value)&&Object.keys(value).every(key=>allowed.includes(key))
const settingsKeys=['operations','structure','replace','strength','seed','style_note','max_changed_blocks','whole_region','lo','hi','pattern','weathering','floor']
function settings(value){if(!keys(value,settingsKeys)||!Array.isArray(value.operations)||value.operations.length>128||!['structure','replace','pattern','weathering','floor'].every(key=>plain(value[key])))throw Error('编辑草稿的参数结构无效')}
export function validateSessionState(value,hash){
 if(!keys(value,['settings','operations_text','controls','view','drafts','ai_component','ai_candidate']))throw Error('编辑草稿字段无效')
 if(value.ai_candidate){validateAICandidate(value.ai_candidate,hash);settings(value.ai_candidate.settings)}
 settings(value.settings)
 const group=value.ai_component
 if(group!==undefined&&group!==null){
  const validOp=op=>keys(op,['kind','label','classification','lo','hi','state','start','end','width','thickness','enabled','overwrite','write_group','skip_protected'])&&(op.skip_protected===undefined||typeof op.skip_protected==='boolean')&&['box','beam','frame'].includes(op.kind)&&typeof op.label==='string'&&op.label.length<=250&&typeof op.state==='string'&&op.state.length<=250&&['body','wall'].includes(op.classification)&&(op.write_group===undefined||typeof op.write_group==='string'&&/^[a-f0-9-]{36}$/.test(op.write_group))&&['lo','hi'].every(key=>Array.isArray(op[key])&&op[key].length===3&&op[key].every(Number.isSafeInteger))
  if(!keys(group,['start','base','applied','offset','overwrite','quarter_turns','structure_name','camera'])||!Number.isInteger(group.start)||group.start<0||!Array.isArray(group.base)||!Array.isArray(group.applied)||!group.base.length||group.base.length>128||group.base.length!==group.applied.length||![...group.base,...group.applied].every(validOp)||!Array.isArray(group.offset)||group.offset.length!==3||!group.offset.every(Number.isSafeInteger)||typeof group.overwrite!=='boolean'||!aiGroupMatches(group,value.settings))throw Error('AI构件草稿与工具序列不匹配')
  if(group.quarter_turns!==undefined&&(!Number.isInteger(group.quarter_turns)||group.quarter_turns<0||group.quarter_turns>3))throw Error('AI构件旋转无效')
  if(group.structure_name!==undefined&&(typeof group.structure_name!=='string'||!group.structure_name.trim()||group.structure_name.length>120))throw Error('AI构件名称无效')
  if(group.camera!==undefined)aiComponentCamera(group.applied,group.camera)
 }
 if(value.operations_text!==null&&(typeof value.operations_text!=='string'||value.operations_text.length>6*1024*1024))throw Error('工具序列草稿过大')
 if(!plain(value.controls)||Object.keys(value.controls).length>150||Object.entries(value.controls).some(([id,v])=>!/^[a-z][a-z0-9-]{0,60}$/.test(id)||!['string','boolean'].includes(typeof v)||(typeof v==='string'&&v.length>6*1024*1024)))throw Error('编辑控件草稿无效')
 const view=value.view
 if(!keys(view,['mode','quality','camera','cuts','layer','cut','show_selection','image_hash','image_name','comparison','preview_settings'])||!['images','3d'].includes(view.mode)||!['fast','balanced'].includes(view.quality)||!['all','body','walls'].includes(view.layer)||!Number.isInteger(view.cut)||typeof view.show_selection!=='boolean')throw Error('视口草稿无效')
 if(view.camera){if(!keys(view.camera,['eye','target','up','fov'])||!['eye','target','up'].every(key=>Array.isArray(view.camera[key])&&view.camera[key].length===3&&view.camera[key].every(Number.isFinite))||!Number.isFinite(view.camera.fov)||view.camera.fov<=0||view.camera.fov>=180||Math.hypot(...view.camera.eye.map((v,i)=>v-view.camera.target[i]))<1e-6||Math.hypot(...view.camera.up)<1e-6)throw Error('草稿相机无效')}
 if(!Array.isArray(view.cuts)||view.cuts.length>8||view.cuts.some(c=>!keys(c,['axis','position','removed_side'])||!['x','y','z'].includes(c.axis)||!Number.isFinite(c.position)||!['above','below'].includes(c.removed_side)))throw Error('草稿剖切无效')
 if(view.image_hash!==null&&!SHA.test(view.image_hash))throw Error('草稿图片绑定无效')
 if(view.image_name!==undefined&&view.image_name!==null&&(typeof view.image_name!=='string'||view.image_name.length>255||path.basename(view.image_name)!==view.image_name||/[\\/]/.test(view.image_name)||!view.image_name.toLowerCase().endsWith('.png')))throw Error('草稿图片名称无效')
 if(!['before','after',null].includes(view.comparison))throw Error('草稿候选状态无效')
 if(view.preview_settings)settings(view.preview_settings)
 if(!Array.isArray(value.drafts)||value.drafts.length>50)throw Error('评论草稿最多保存50个画面')
 for(const item of value.drafts){if(!Array.isArray(item)||item.length!==2||typeof item[0]!=='string'||!item[0].startsWith(hash+':')||!/^[a-f0-9]{64}:(?:3d:)?[a-f0-9]{64}$/.test(item[0]))throw Error('评论草稿不属于当前建筑版本');const d=item[1];if(!keys(d,['text','points'])||typeof d.text!=='string'||d.text.length>4000||!Array.isArray(d.points)||d.points.length>100)throw Error('评论草稿无效');for(const p of d.points){if(!plain(p)||!['image','voxel'].includes(p.kind)||!Number.isInteger(p.number)||p.number<1)throw Error('评论标记无效');if(p.kind==='image'&&![p.x,p.y].every(n=>Number.isFinite(n)&&n>=0&&n<=1))throw Error('图片标记无效');if(p.kind==='voxel'&&(!Array.isArray(p.position)||p.position.length!==3||!p.position.every(Number.isInteger)||typeof p.state!=='string'||p.source_sha256!==hash||!SHA.test(p.geometry_sha256)))throw Error('方块标记绑定无效')}}
 if(Buffer.byteLength(JSON.stringify(value))>24*1024*1024)throw Error('编辑草稿超过24 MiB，请减少工具序列或另存调整设置')
 return value
}
export function createEditSessionStore(workspace){
 workspace=path.resolve(workspace);const directory=path.join(workspace,'.nbtcreator/edit-sessions'),indexFile=path.join(directory,'index.json'),hashes=new Map();let writing=Promise.resolve()
 const digest=value=>createHash('sha256').update(value).digest('hex')
 const canonical=fs.realpath(workspace).catch(()=>workspace)
 async function lock(action){
  // Windows named-pipe ownership disappears with the process, avoiding stale
  // lock files after a crash. It serializes revision and index commits in two apps.
  if(process.platform!=='win32')return action()
  const address='\\\\.\\pipe\\nbtcreator-drafts-'+digest((await canonical).toLowerCase()),deadline=Date.now()+2500
  let server
  for(;;){server=net.createServer(socket=>socket.destroy());try{await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(address,resolve)});break}catch(error){if(error.code!=='EADDRINUSE')throw error;if(Date.now()>deadline)throw Error('另一窗口正在保存草稿，请稍后再试');await new Promise(resolve=>setTimeout(resolve,20))}}
  try{return await action()}finally{await new Promise(resolve=>server.close(resolve))}
 }
 function portable(source){const relative=path.relative(workspace,source);return !path.isAbsolute(relative)&&relative!=='..'&&!relative.startsWith('..'+path.sep)?relative.split(path.sep).join('/'):source}
 function identity(source){if(typeof source!=='string'||!path.isAbsolute(source)||source.startsWith('\\\\')||source.startsWith('//'))throw Error('请选择本地建筑文件');return digest(portable(path.resolve(source)).toLowerCase())}
 async function read(file){if((await fs.stat(file)).size>32*1024*1024)throw Error('编辑草稿文件过大');return JSON.parse((await fs.readFile(file,'utf8')).replace(/^\uFEFF/,''))}
 async function index(){try{const value=await read(indexFile);if(value.schema_version!==1||!plain(value.sources))throw Error('编辑草稿索引无效');return value}catch(error){if(error.code==='ENOENT')return {schema_version:1,last:null,sources:{}};throw error}}
 async function atomic(file,data){await fs.mkdir(directory,{recursive:true});const temporary=file+'.'+randomUUID()+'.tmp';await fs.writeFile(temporary,JSON.stringify(data)+'\n');await fs.rename(temporary,file)}
 async function sourceHash(source){const stat=await fs.stat(source,{bigint:true}),stamp=[stat.size,stat.mtimeNs,stat.ctimeNs].join(':');if(!stat.isFile())throw Error('建筑源不是文件');const old=hashes.get(source);if(old?.stamp===stamp)return old.hash;const hash=createHash('sha256');for await(const bytes of createReadStream(source))hash.update(bytes);const final=await fs.stat(source,{bigint:true});if([final.size,final.mtimeNs,final.ctimeNs].join(':')!==stamp)throw Error('建筑源正在变化，请稍后重试');const value=hash.digest('hex');hashes.set(source,{stamp,hash:value});return value}
 function fileFor(key,hash){return path.join(directory,digest(key+':'+hash)+'.json')}
 function metadata(record){return {source:path.resolve(workspace,record.source),source_sha256:record.source_sha256,updated_at:record.updated_at,revision:record.revision}}
 async function recent(){const data=await index(),record=data.sources[data.last];if(!record)return null;const value=metadata(record);try{await fs.access(value.source);return {...value,exists:true}}catch(error){if(error.code!=='ENOENT')throw error;return {...value,exists:false}}}
 async function load(source){await writing.catch(()=>{});const key=identity(source),hash=await sourceHash(source),file=fileFor(key,hash);try{const data=await read(file);if(data.schema_version!==1||data.source_sha256!==hash||identity(path.resolve(workspace,data.source))!==key)throw Error('编辑草稿来源不匹配');validateSessionState(data.state,hash);return {status:'found',...metadata(data),state:data.state}}catch(error){if(error.code!=='ENOENT')throw error;const data=await index(),old=data.sources[key];return {status:old&&old.source_sha256!==hash?'source_changed':'empty',source,source_sha256:hash,revision:0,previous:old?metadata(old):null}}}
 function save(input){const result=writing.then(()=>lock(async()=>{
  if(!keys(input,['source','source_sha256','expected_revision','client_id','sequence','state'])||!SHA.test(input.source_sha256)||!Number.isInteger(input.expected_revision)||input.expected_revision<0||typeof input.client_id!=='string'||!/^[a-f0-9-]{36}$/.test(input.client_id)||!Number.isInteger(input.sequence)||input.sequence<1)throw Error('编辑草稿保存请求无效')
  const key=identity(input.source),hash=await sourceHash(input.source);if(hash!==input.source_sha256)throw Error('源建筑已变化；旧草稿保留，请重新打开建筑')
  validateSessionState(input.state,hash);const file=fileFor(key,hash);let revision=0,old;try{old=await read(file);revision=old.revision;if(!Number.isInteger(revision)||revision<1)throw Error('编辑草稿版本无效')}catch(error){if(error.code!=='ENOENT')throw error}
  if(old?.client_id===input.client_id&&input.sequence<=old.sequence)return {status:'saved',...metadata(old)}
  if(revision!==input.expected_revision&&old?.client_id!==input.client_id)throw Error('编辑草稿已被另一个窗口更新，请重新读取后再编辑')
  const record={schema_version:1,source:portable(input.source),source_sha256:hash,revision:revision+1,client_id:input.client_id,sequence:input.sequence,updated_at:new Date().toISOString(),state:input.state};await atomic(file,record)
  const data=await index();data.last=key;const {state,...summary}=record;data.sources[key]=summary;await atomic(indexFile,data);return {status:'saved',...metadata(record)}
 }));writing=result.catch(()=>{});return result}
 function imagePaths(sourceHash,imageHash,name){if(!SHA.test(sourceHash)||!SHA.test(imageHash)||typeof name!=='string'||name.length>255||path.basename(name)!==name||/[\\/]/.test(name)||!name.toLowerCase().endsWith('.png'))throw Error('草稿图片证据参数无效');const folder=path.join(directory,'images',sourceHash,imageHash);return {folder,image:path.join(folder,name),meta:path.join(folder,name.replace(/\.png$/i,'.json'))}}
 async function rememberImage(binding){const files=imagePaths(binding.source_sha256,binding.image_sha256,path.basename(binding.image));if(await sourceHash(binding.image)!==binding.image_sha256)throw Error('图片已变化，请重新打开画面再保存草稿');await fs.mkdir(files.folder,{recursive:true});try{await fs.copyFile(binding.image,files.image,constants.COPYFILE_EXCL)}catch(error){if(error.code!=='EEXIST')throw error}if(await sourceHash(files.image)!==binding.image_sha256)throw Error('草稿图片证据已变化，未覆盖');const data={source_sha256:binding.source_sha256,geometry_sha256:binding.geometry_sha256,image_sha256:binding.image_sha256,camera:binding.camera??null,cuts:binding.cuts??[]};try{await fs.writeFile(files.meta,JSON.stringify(data)+'\n',{flag:'wx'})}catch(error){if(error.code!=='EEXIST')throw error}return files.image}
 async function imageEvidence(sourceDigest,imageHash,name,geometry){if(!name)return null;const files=imagePaths(sourceDigest,imageHash,name);try{const meta=await read(files.meta);if(meta.source_sha256!==sourceDigest||meta.geometry_sha256!==geometry||meta.image_sha256!==imageHash||await sourceHash(files.image)!==imageHash)throw Error('草稿图片证据不匹配');return files.image}catch(error){if(error.code==='ENOENT')return null;throw error}}
 return {recent,load,save,rememberImage,imageEvidence}
}
