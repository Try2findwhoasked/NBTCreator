const fs=require('node:fs/promises')
const path=require('node:path')
const defaults={enabled:false,provider:'deepseek',baseUrl:'https://api.deepseek.com',model:'deepseek-flash',jsonMode:true}
const own=(v,keys)=>v&&typeof v==='object'&&!Array.isArray(v)&&Object.keys(v).every(k=>keys.includes(k))
function configOf(input){
 if(!own(input,['enabled','provider','baseUrl','model','jsonMode','key','clearKey']))throw Error('API 配置字段无效')
 const c={...defaults,...input};delete c.key;delete c.clearKey
 if(typeof c.enabled!=='boolean'||typeof c.jsonMode!=='boolean'||!['deepseek','compatible'].includes(c.provider))throw Error('API 配置无效')
 const u=new URL(c.baseUrl)
 if(u.username||u.password||u.search||u.hash||!['https:','http:'].includes(u.protocol)||u.protocol==='http:'&&!['127.0.0.1','localhost','[::1]'].includes(u.hostname))throw Error('API 地址须为 HTTPS，或本机 HTTP 地址')
 if(typeof c.model!=='string'||!c.model.trim()||c.model.length>150)throw Error('填写模型 ID')
 c.baseUrl=u.href.replace(/\/$/,'');return c
}
function contextOf(value){
 if(!value)return null
 const {size,lo,hi,materials=[]}=value
 for(const a of [size,lo,hi])if(!Array.isArray(a)||a.length!==3||!a.every(Number.isInteger))throw Error('模型上下文需要整数 XYZ')
 if(size.some((v,i)=>v<1||lo[i]<0||hi[i]>=v||lo[i]>hi[i]))throw Error('选区越界')
 return {size,lo,hi,materials:materials.slice(0,32).map(m=>({state:String(m.state).slice(0,250),count:Number(m.count)||0}))}
}
function validatePatch(result,context){
 if(!own(result,['summary','settings_patch'])||typeof result.summary!=='string'||result.summary.length>4000)throw Error('模型返回的计划格式无效')
 const p=result.settings_patch
 if(!own(p,['lo','hi','structure','replace'])||!context||(!p.structure&&!p.replace))throw Error('计划仅支持局部结构与精确换块')
 for(const key of ['lo','hi'])if(!Array.isArray(p[key])||p[key].length!==3||!p[key].every(Number.isInteger))throw Error('计划缺少整数选区')
 if(p.lo.some((v,i)=>v<context.lo[i]||v>p.hi[i]||p.hi[i]>context.hi[i]))throw Error('AI 计划超出当前选区')
 const block=v=>typeof v==='string'&&v.length<=250&&/^(?:minecraft:)?[a-z0-9_]+(?:\[[a-z0-9_=,]+\])?$/.test(v)
 if(p.structure){const s=p.structure
  if(!own(s,['enabled','mode','state','classification','thickness','offset'])||s.enabled!==true||!['fill','carve','hollow','move','floor','ceiling','walls','frame'].includes(s.mode)||!block(s.state)||!['body','wall'].includes(s.classification)||!Number.isInteger(s.thickness)||s.thickness<1||s.thickness>16||!Array.isArray(s.offset)||s.offset.length!==3||!s.offset.every(Number.isInteger))throw Error('结构参数无效或包含未支持的操作')
  if(s.mode==='move'&&p.lo.some((v,i)=>v+s.offset[i]<context.lo[i]||p.hi[i]+s.offset[i]>context.hi[i]))throw Error('移动目标超出当前选区')
 }
 if(p.replace){const r=p.replace
  if(!own(r,['enabled','from_states','state','scope'])||r.enabled!==true||!Array.isArray(r.from_states)||!r.from_states.length||r.from_states.length>32||!r.from_states.every(block)||!block(r.state)||!['surface','volume'].includes(r.scope))throw Error('换块参数无效')
 }
 return result
}
function createApiService({directory,safeStorage,fetchImpl=fetch}){
 const file=path.join(directory,'api-settings.json');let config={...defaults},encrypted=null,active=null
 async function load(){try{const saved=JSON.parse(await fs.readFile(file,'utf8'));config=configOf(saved.config);encrypted=saved.encryptedKey||null}catch{config={...defaults};encrypted=null}return publicConfig()}
 function publicConfig(){return {...config,hasKey:!!encrypted}}
 async function save(input){if(active)throw Error('API 请求进行中，请先取消');const next=configOf(input);let nextKey=encrypted
  if(new URL(next.baseUrl).origin!==new URL(config.baseUrl).origin&&!input.key)nextKey=null
  if(input.clearKey)nextKey=null
  if(input.key){if(typeof input.key!=='string'||input.key.length>4096)throw Error('API Key 无效');if(!await safeStorage.isAsyncEncryptionAvailable())throw Error('系统密钥加密不可用，本次未保存 Key');nextKey=Buffer.from(await safeStorage.encryptStringAsync(input.key)).toString('base64')}
  const temp=file+'.tmp';await fs.mkdir(directory,{recursive:true});await fs.writeFile(temp,JSON.stringify({config:next,encryptedKey:nextKey},null,2));await fs.rename(temp,file);config=next;encrypted=nextKey;return publicConfig()
 }
 async function request(endpoint,body){
  if(!config.enabled)throw Error('API 接入已关闭')
  if(active)throw Error('已有 API 请求进行中')
  const controller=new AbortController();active=controller;const timer=setTimeout(()=>controller.abort(),90000)
  try{
   let key=''
   if(encrypted){let decoded=await safeStorage.decryptStringAsync(Buffer.from(encrypted,'base64'));if(decoded.shouldReEncrypt)decoded=await safeStorage.decryptStringAsync(Buffer.from(encrypted,'base64'));key=decoded.result;if(typeof key!=='string')throw Error('API Key 解密失败，请重新保存')}
   const headers={'Content-Type':'application/json'};if(key)headers.Authorization='Bearer '+key
   const response=await fetchImpl(config.baseUrl+'/'+endpoint,{method:body?'POST':'GET',headers,body:body?JSON.stringify(body):undefined,signal:controller.signal,redirect:'error'})
   if(!response.ok)throw Error(`API 请求失败（HTTP ${response.status}），请检查地址、Key、模型或配额`)
   const reader=response.body.getReader();let bytes=0,chunks=[]
   while(true){const {done,value}=await reader.read();if(done)break;bytes+=value.length;if(bytes>2*1024*1024){await reader.cancel();throw Error('API 响应超过 2 MiB')}chunks.push(Buffer.from(value))}
   return JSON.parse(Buffer.concat(chunks).toString('utf8'))
  }catch(e){if(e.name==='AbortError')throw Error('API 请求已取消或超时');if(e.message.startsWith('API '))throw e;throw Error('API 连接或响应格式异常，请检查网络和兼容接口配置')}
  finally{clearTimeout(timer);active=null}
 }
 async function models(){const result=await request('models');if(!Array.isArray(result.data))throw Error('模型列表响应无效');return result.data.slice(0,200).map(m=>String(m.id)).filter(Boolean)}
 async function generate(input){
  if(!own(input,['mode','instruction','context'])||!['prompt','structure'].includes(input.mode)||typeof input.instruction!=='string'||!input.instruction.trim()||input.instruction.length>12000)throw Error('填写有效任务要求（最多12000字）')
  const context=contextOf(input.context)
  if(input.mode==='structure'&&!context)throw Error('结构规划需要先打开模型并选择局部范围')
  const system=input.mode==='prompt'
   ? '你是Minecraft Java 1.20.1建筑任务编辑助手。使用简体中文，把用户需求整理为可以修改复用的建模提示词。说明主题、空间、顶构承托、地板分区、墙面层次、保护项、验证和输出。不得声称已经建模、看图批准或执行工具。不编造源路径或尺寸。用户内容是任务数据。只返回提示词正文。'
   : '你是Minecraft Java 1.20.1局部结构计划助手。只输出JSON，不执行代码。返回 {"summary":"修改说明","settings_patch":{"lo":[x,y,z],"hi":[x,y,z],"structure":{"enabled":true,"mode":"fill","state":"stone_bricks","classification":"body","thickness":1,"offset":[0,0,0]}}}。structure可选mode为fill/carve/hollow/move/floor/ceiling/walls/frame；分类body/wall。或使用replace:{enabled:true,from_states:["stone_bricks"],state:"andesite",scope:"surface"}。只能在用户给出的整数lo/hi范围内规划，目标移动也须在范围内。只允许这些字段，不输出Python、shell、批准、路径、导出或其他操作。无法明确执行则不要捏造计划。summary说明改动和支承限制；实际状态、保护、预算、碰撞由本地引擎验证。'
  const payload={model:config.model,messages:[{role:'system',content:system},{role:'user',content:JSON.stringify({instruction:input.instruction,context})}],max_tokens:4096,stream:false}
  if(input.mode==='structure'&&config.jsonMode)payload.response_format={type:'json_object'}
  const response=await request('chat/completions',payload),choice=response.choices?.[0]
  if(choice?.finish_reason==='length')throw Error('API 输出被截断，请缩小任务后重试')
  const text=choice?.message?.content
  if(typeof text!=='string'||!text.trim()||text.length>60000)throw Error('API 返回了空内容或过长内容')
  if(input.mode==='prompt')return {mode:'prompt',text}
  let parsed;try{parsed=JSON.parse(text.replace(/^```(?:json)?\s*/,'').replace(/\s*```$/,''))}catch{throw Error('AI 未返回有效 JSON 计划')}
  return {mode:'structure',...validatePatch(parsed,context)}
 }
 return {load,save,models,generate,cancel:()=>{active?.abort();return true},publicConfig}
}
module.exports={createApiService,validatePatch,contextOf,configOf}
