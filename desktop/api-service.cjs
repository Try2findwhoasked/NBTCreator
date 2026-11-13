const fs=require('node:fs/promises')
const path=require('node:path')
const {performance}=require('node:perf_hooks')
const {normalizeSmallStructure}=require('./small-structure-normalize.cjs')
const {normalizeReply}=require('./ai-output-normalize.cjs')
const {extractResult}=require('./ai-result-extract.cjs')
const {cleanContext,validateWorkbench}=require('./workbench-contract.cjs')
const {validateRequestOptions}=require('./api-options.cjs')
const {cleanSelectionContext,validateSelectionResult}=require('./selection-edit.cjs')
const {createAiScheduler}=require('./ai-scheduler.cjs')
const defaults={maxConcurrent:2,enabled:false,provider:'deepseek',baseUrl:'https://api.deepseek.com',model:'deepseek-flash',jsonMode:true,outputCharLimit:0,timeoutMs:90000,tokenParameter:'max_tokens',requestOptions:{}}
const own=(v,keys)=>v&&typeof v==='object'&&!Array.isArray(v)&&Object.keys(v).every(k=>keys.includes(k))
function configOf(input){
 if(!own(input,['maxConcurrent','enabled','provider','baseUrl','model','jsonMode','key','clearKey','outputCharLimit','timeoutMs','tokenParameter','requestOptions']))throw Error('API 配置字段无效')
 const c={...defaults,...input};if(!Number.isInteger(c.maxConcurrent)||c.maxConcurrent<1||c.maxConcurrent>4)throw Error('AI 并发数须为1～4');delete c.key;delete c.clearKey
 if(typeof c.enabled!=='boolean'||typeof c.jsonMode!=='boolean'||!['deepseek','compatible'].includes(c.provider))throw Error('API 配置无效')
 const u=new URL(c.baseUrl)
 if(u.username||u.password||u.search||u.hash||!['https:','http:'].includes(u.protocol)||u.protocol==='http:'&&!['127.0.0.1','localhost','[::1]'].includes(u.hostname))throw Error('API 地址须为 HTTPS，或本机 HTTP 地址')
 if(typeof c.model!=='string'||!c.model.trim()||c.model.length>150)throw Error('填写模型 ID')
 if(!Number.isInteger(c.timeoutMs)||c.timeoutMs<5000||c.timeoutMs>300000||!['max_tokens','max_completion_tokens'].includes(c.tokenParameter))throw Error('API超时须为5～300秒，令牌参数使用支持的名称')
 if(!Number.isSafeInteger(c.outputCharLimit)||c.outputCharLimit!==0&&c.outputCharLimit<100||c.outputCharLimit>60000)throw Error('输出字数上限须为0（不限制）或100～60000的整数')
 c.requestOptions=validateRequestOptions(c.requestOptions)
 c.baseUrl=u.href.replace(/\/$/,'');return c
}
function contextOf(value){
 if(!value)return null
 const {size,lo,hi,materials=[],allow_overwrite=false}=value
 if(typeof allow_overwrite!=='boolean')throw Error('是否允许覆盖须为勾选状态')
 for(const a of [size,lo,hi])if(!Array.isArray(a)||a.length!==3||!a.every(Number.isInteger))throw Error('模型上下文需要整数 XYZ')
 if(size.some((v,i)=>v<1||lo[i]<0||hi[i]>=v||lo[i]>hi[i]))throw Error('选区越界')
 return {size,lo,hi,allow_overwrite,materials:materials.slice(0,32).map(m=>({state:String(m.state).slice(0,250),count:Number(m.count)||0}))}
}
function componentContext(value){
 if(!value||!Array.isArray(value.size)||value.size.length!==3||!value.size.every(n=>Number.isInteger(n)&&n>=1&&n<=64))throw Error('独立结构尺寸须为1到64格整数XYZ')
 if(typeof value.name!=='string'||!value.name.trim()||value.name.length>80)throw Error('独立结构名称须为1到80字')
 if(!Array.isArray(value.references??[])||(value.references??[]).length>32)throw Error('独立结构最多引用32个资产')
 const references=(value.references??[]).map(item=>{
  if(!/^[a-f0-9]{32}$/.test(item.id)||!/^[a-f0-9]{64}$/.test(item.content_sha256))throw Error('引用资产编号或哈希无效')
  if(!Array.isArray(item.size)||item.size.length!==3||!item.size.every(n=>Number.isInteger(n)&&n>=1&&n<=64))throw Error('引用资产尺寸无效')
  return {id:item.id,content_sha256:item.content_sha256,name:String(item.name).slice(0,80),size:[...item.size],anchor:Array.isArray(item.anchor)?item.anchor.slice(0,3):undefined,palette:Array.isArray(item.palette)?item.palette.slice(0,32).map(value=>String(value).slice(0,250)):undefined}
 })
 return {name:value.name.trim(),size:[...value.size],references}
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
function validateSmallStructure(result,context){
 if(!own(result,['summary','settings_patch'])||typeof result.summary!=='string'||!result.summary.trim()||result.summary.length>4000)throw Error('小型结构方案格式无效')
 const p=result.settings_patch
 if(!context||!own(p,['lo','hi','operations'])||!Array.isArray(p.operations)||!p.operations.length||p.operations.length>128)throw Error('小型结构须包含1到128步工具操作')
 for(const key of ['lo','hi'])if(!Array.isArray(p[key])||p[key].length!==3||!p[key].every(Number.isInteger))throw Error('需要整数选区')
 if(p.lo.some((v,i)=>v<context.lo[i]||v>p.hi[i]||p.hi[i]>context.hi[i]))throw Error('小型结构超出当前选区')
 let writes=0
 for(const op of p.operations){
  if(!own(op,['kind','label','classification','lo','hi','state','start','end','width','thickness'])||!['box','beam','frame'].includes(op.kind)||typeof op.label!=='string'||!op.label.trim()||op.label.length>250||!['body','wall'].includes(op.classification))throw Error('小型结构只支持方块区域、梁和边框')
  if(typeof op.state!=='string'||op.state.length>250||!/^(?:minecraft:)?[a-z0-9_]+(?:\[[a-z0-9_=,]+\])?$/.test(op.state))throw Error('小型结构需要有效的方块材质')
  for(const key of ['lo','hi'])if(!Array.isArray(op[key])||op[key].length!==3||!op[key].every(Number.isInteger))throw Error('构件需要整数XYZ选区')
  if(op.lo.some((v,i)=>v<p.lo[i]||v>op.hi[i]||op.hi[i]>p.hi[i]))throw Error('构件超出当前选区')
  if(op.kind==='beam'){
   if(![1,3,5].includes(op.width))throw Error('梁宽须为1、3或5')
   const margin=Math.floor(op.width/2)
   for(const key of ['start','end'])if(!Array.isArray(op[key])||op[key].length!==3||!op[key].every((v,i)=>Number.isInteger(v)&&v-margin>=op.lo[i]&&v+margin<=op.hi[i]))throw Error('梁的端点或厚度超出选区')
  }
  if(op.kind==='frame'&&(!Number.isInteger(op.thickness)||op.thickness<1||op.thickness>8||op.lo.filter((v,i)=>v===op.hi[i]).length!==1))throw Error('边框需要平面选区和有效厚度')
  writes+=op.lo.reduce((n,v,i)=>n*(op.hi[i]-v+1),1)
 }

 return result
}
function localSmallStructure(result,context){
 result=normalizeSmallStructure(result,context)
 if(!own(result,['summary','settings_patch','coordinate_space','structure_name','camera'])||result.coordinate_space!=='local')throw Error('小型结构必须声明coordinate_space=local，使用选区相对坐标')
 const localSize=context.hi.map((v,i)=>v-context.lo[i]+1),local={...context,size:localSize,lo:[0,0,0],hi:localSize.map(v=>v-1)}
 const normalized=validateSmallStructure({summary:result.summary,settings_patch:result.settings_patch},local)
 const translated=structuredClone(normalized),p=translated.settings_patch
 for(const key of ['lo','hi'])p[key]=p[key].map((v,i)=>v+context.lo[i])
 for(const op of p.operations)for(const key of ['lo','hi','start','end'])if(op[key])op[key]=op[key].map((v,i)=>v+context.lo[i])
 return {...validateSmallStructure(translated,context),structure_name:result.structure_name,camera:result.camera}
}
function createApiService({directory,safeStorage,fetchImpl=fetch,workflowContext=async()=>null,validateCandidate=async()=>{}}){
 const file=path.join(directory,'api-settings.json');let config={...defaults},encrypted=null,modelBusy=false,saving=false;const transports=new Set(),scheduler=createAiScheduler({limit:()=>config.maxConcurrent})
 async function load(){if(scheduler.size||modelBusy||saving)return publicConfig();try{const saved=JSON.parse(await fs.readFile(file,'utf8'));config=configOf(saved.config);encrypted=saved.encryptedKey||null}catch{config={...defaults};encrypted=null}return publicConfig()}
 function publicConfig(){return {...structuredClone(config),hasKey:!!encrypted}}
 async function save(input){if(transports.size||scheduler.size||modelBusy||saving)throw Error('API 请求或配置保存进行中，请稍后重试');saving=true;try{const next=configOf({...config,...input});let nextKey=encrypted
  if(new URL(next.baseUrl).origin!==new URL(config.baseUrl).origin&&!input.key)nextKey=null
  if(input.clearKey)nextKey=null
  if(input.key){if(typeof input.key!=='string'||input.key.length>4096)throw Error('API Key 无效');if(!await safeStorage.isAsyncEncryptionAvailable())throw Error('系统密钥加密不可用，本次未保存 Key');nextKey=Buffer.from(await safeStorage.encryptStringAsync(input.key)).toString('base64')}
  const temp=file+'.tmp';await fs.mkdir(directory,{recursive:true});await fs.writeFile(temp,JSON.stringify({config:next,encryptedKey:nextKey},null,2));await fs.rename(temp,file);config=next;encrypted=nextKey;return publicConfig()}finally{saving=false}
 }
 async function request(endpoint,body,measurement,token){
  if(!config.enabled)throw Error('API 接入已关闭')
  const controller=new AbortController();transports.add(controller);const cancel=()=>controller.abort();token?.controller.signal.addEventListener('abort',cancel,{once:true});if(token?.cancelled)controller.abort();let timedOut=false;const timer=setTimeout(()=>{timedOut=true;controller.abort()},config.timeoutMs)
  const started=performance.now()
  if(measurement){measurement.status='failed';measurement.response_bytes=0}
  try{
   const serialized=body?JSON.stringify(body):undefined
   if(measurement)measurement.request_bytes=Buffer.byteLength(serialized||'','utf8')
   let key=''
   if(encrypted){let decoded=await safeStorage.decryptStringAsync(Buffer.from(encrypted,'base64'));if(decoded.shouldReEncrypt)decoded=await safeStorage.decryptStringAsync(Buffer.from(encrypted,'base64'));key=decoded.result;if(typeof key!=='string')throw Error('API Key 解密失败，请重新保存')}
   const headers={'Content-Type':'application/json'};if(key)headers.Authorization='Bearer '+key
   const sent=performance.now()
   let response
   try{response=await fetchImpl(config.baseUrl+'/'+endpoint,{method:body?'POST':'GET',headers,body:serialized,signal:controller.signal,redirect:'error'})}
   finally{if(measurement)measurement.headers_ms=Math.round(performance.now()-sent)}
   if(measurement)measurement.http_status=response.status
   if(!response.ok)throw Error(`API 请求失败（HTTP ${response.status}），请检查地址、Key、模型或配额`)
   const reader=response.body.getReader();let bytes=0,chunks=[]
   const reading=performance.now()
   try{while(true){const {done,value}=await reader.read();if(done)break;bytes+=value.length;if(measurement)measurement.response_bytes=bytes;if(bytes>2*1024*1024){await reader.cancel();throw Error('API 响应超过 2 MiB')}chunks.push(Buffer.from(value))}}
   finally{if(measurement)measurement.read_ms=Math.round(performance.now()-reading)}
   const parsing=performance.now()
   try{const result=JSON.parse(Buffer.concat(chunks).toString('utf8'));if(measurement)measurement.status='complete';return result}
   finally{if(measurement)measurement.response_parse_ms=Math.round(performance.now()-parsing)}
  }catch(e){if(e.name==='AbortError'){const cancelled=token?.cancelled||!timedOut;if(measurement)measurement.status=cancelled?'cancelled':'timeout';throw Object.assign(Error(cancelled?'API 请求已取消':'API 请求超时，请稍后重试'),{code:cancelled?'AI_CANCELLED':'AI_TIMEOUT',retryable:!cancelled})}if(e.message.startsWith('API '))throw e;throw Error('API 连接或响应格式异常，请检查网络和兼容接口配置')}
  finally{if(measurement)measurement.elapsed_ms=Math.round(performance.now()-started);clearTimeout(timer);transports.delete(controller);token?.controller.signal.removeEventListener('abort',cancel)}
 }
 async function models(){if(modelBusy||scheduler.size||saving)throw Error('已有 API 请求进行中');modelBusy=true;try{const result=await request('models');if(!Array.isArray(result.data))throw Error('模型列表响应无效');return result.data.slice(0,200).map(m=>String(m.id)).filter(Boolean)}finally{modelBusy=false}}
 async function generateCore(input,token){
  const api_metrics=token.metrics
  if(!own(input,['mode','instruction','context','viewport','retrieval'])||!['prompt','structure','small_structure','workbench','component','selection_edit'].includes(input.mode)||typeof input.instruction!=='string'||!input.instruction.trim()||input.instruction.length>12000)throw Error('填写有效任务要求（最多12000字）')
  if(input.retrieval&&(!own(input.retrieval,['id','sha256'])||!/^[a-f0-9]{32}$/.test(input.retrieval.id)||!/^[a-f0-9]{64}$/.test(input.retrieval.sha256)))throw Error('参考集合编号或哈希无效')
  let context=input.mode==='workbench'?cleanContext(input.context):input.mode==='component'?componentContext(input.context):input.mode==='selection_edit'?cleanSelectionContext(input.context):contextOf(input.context)
  if(['structure','small_structure'].includes(input.mode)&&!context)throw Error('结构规划需要先打开模型并选择局部范围')
  let system=(config.outputCharLimit?`最终结果限制为 ${config.outputCharLimit} 字（Unicode字符，含空白和JSON标点）；不计可分离的思考与说明。`:'最终结果不设应用字数限制。')+'只输出完整最终结果，不输出思考。JSON任务只给一个完整对象；文字任务可用单独的<final>与</final>包围正文。不要为了凑长度省略必要设计。\n'+require('./internal-skill.cjs').buildInternalPrompt(input.mode,context)
  const internal=await token.workflowPromise;if(token.cancelled)throw Error('API 请求已取消')
  if(internal?.retrieved_assets?.length&&input.mode==='component'){const references=[...context.references];for(const item of internal.retrieved_assets){const old=references.find(ref=>ref.id===item.id);if(old&&old.content_sha256!==item.content_sha256)throw Error('引用资产已变化，请重新选择');if(!old)references.push(item)}context=componentContext({...context,references})}
  const {retrieved_assets,base_rules,workflow_steps,...providerWorkflow}=internal??{}
  if(internal?.reference_sources)system+=' 本次提供了编号参考来源；需要引用时使用其citation编号，不编造来源或声称已验证。引用资产仅可使用context.references里实际提供的id与内容哈希，可按结构协议旋转、镜像和material_map换材质。'
  const apiContext=input.mode==='selection_edit'?{size:context.selection.size,lo:[0,0,0],hi:context.selection.size.map(n=>n-1),allow_overwrite:context.allow_overwrite,selection:{palette:context.selection.palette,runs:context.selection.runs,air_omitted:true}}:input.mode==='small_structure'?{...context,size:context.hi.map((v,i)=>v-context.lo[i]+1),lo:[0,0,0],hi:context.hi.map((v,i)=>v-context.lo[i])}:input.mode==='workbench'?Object.fromEntries(Object.entries(context).filter(([key])=>key!=='baseline_binding')):context
  let image
  if(input.viewport){
    if(!internal?.attachViewport)throw Error('该工作流未启用发送视口截图')
    const v=input.viewport
    if(!own(v,['dataUrl','width','height'])||typeof v.dataUrl!=='string'||!/^data:image\/(jpeg|png);base64,[A-Za-z0-9+/]+={0,2}$/.test(v.dataUrl)||v.dataUrl.length>3*1024*1024||![v.width,v.height].every(n=>Number.isInteger(n)&&n>0&&n<=1280))throw Error('视口截图格式或尺寸无效')
    image=v.dataUrl
  }else if(internal?.attachViewport)throw Error('该工作流需要视口截图，请先打开建筑画面或关闭截图开关')
  const payload={model:config.model,messages:[{role:'system',content:system},{role:'user',content:JSON.stringify({instruction:input.instruction,context:apiContext,...(internal?{internal_workflow:providerWorkflow}:{})})}],max_tokens:input.mode==='prompt'?6144:12288,stream:false}
  if(new URL(config.baseUrl).hostname==='api.deepseek.com'&&['deepseek-flash','deepseek-v4-pro'].includes(config.model)&&config.requestOptions.thinking===undefined&&config.requestOptions.reasoning_effort===undefined)payload.thinking={type:'disabled'}
  Object.assign(payload,config.requestOptions)
  if(config.tokenParameter==='max_completion_tokens'){payload.max_completion_tokens=payload.max_tokens;delete payload.max_tokens}
  if(image)payload.messages[1].content=[{type:'text',text:payload.messages[1].content+'\n附图是当前建模视口，仅用于理解外观；坐标以本地上下文为准，不能从图片推定已验证或已批准。'},{type:'image_url',image_url:{url:image,detail:'auto'}}]
  if(input.mode!=='prompt'&&config.jsonMode)payload.response_format={type:'json_object'}
  api_metrics.prepare_ms=Math.round(performance.now()-token.started)
  const textChars=()=>payload.messages.reduce((n,message)=>n+(typeof message.content==='string'?message.content.length:message.content.filter(item=>item.type==='text').reduce((sum,item)=>sum+item.text.length,0)),0)
  api_metrics.input_text_chars=textChars()
  let response
  const invoke=async()=>{
   if(token.cancelled)throw Error('API 请求已取消')
   const measurement={attempt:++api_metrics.attempts,max_tokens:payload.max_tokens??payload.max_completion_tokens,input_text_chars:textChars()};api_metrics.calls.push(measurement)
   try{
    const value=await request('chat/completions',payload,measurement,token)
    const reason=value.choices?.[0]?.finish_reason
    measurement.finish_reason=['stop','length','content_filter','tool_calls','function_call'].includes(reason)?reason:'unknown'
    for(const key of ['prompt_tokens','completion_tokens','total_tokens'])if(Number.isSafeInteger(value.usage?.[key])&&value.usage[key]>=0){measurement[key]=value.usage[key];api_metrics[key]=(api_metrics[key]??0)+value.usage[key]}
    const reasoning=value.usage?.completion_tokens_details?.reasoning_tokens
    if(Number.isSafeInteger(reasoning)&&reasoning>=0){measurement.reasoning_tokens=reasoning;api_metrics.reasoning_tokens=(api_metrics.reasoning_tokens??0)+reasoning}
    api_metrics.finish_reason=measurement.finish_reason
    return value
   }catch(e){if(image&&/HTTP (400|415|422)/.test(e.message))throw Error(e.message+'；本次附带视口截图，请确认模型支持图像输入，或关闭工作流截图开关');throw e}
  }
  let compactRetries=0
  const originalMessages=structuredClone(payload.messages)
  const validateResponse=async()=>{
   if(token.cancelled)throw Error('API 请求已取消')
   const choice=response.choices?.[0],raw=choice?.message?.content
   if(typeof raw==='string')api_metrics.output_chars=Array.from(raw).length
   const lengthError=()=>Error('API 输出达到长度上限'+(compactRetries?'；已自动精简重试1次，仍未返回完整方案':'')+'。本次没有应用任何不完整内容。'+(api_metrics.completion_tokens?' 累计返回令牌数：'+api_metrics.completion_tokens:''))
   let extracted;try{extracted=extractResult(raw,input.mode)}catch(error){if(choice?.finish_reason==='length')throw lengthError();throw error}
   if(choice?.finish_reason==='length'&&input.mode==='prompt'&&!extracted.framed)throw lengthError()
   const text=extracted.text
   api_metrics.output_chars=Array.from(text).length
   if(text.length>120000)throw Error('最终结果超过本地处理体积上限')
   if(config.outputCharLimit&&Array.from(text).length>config.outputCharLimit)throw Error('输出超过 '+config.outputCharLimit+' 字上限，请压缩为完整答案')
  const validating=performance.now()
  try{
   if(input.mode==='prompt')return {mode:'prompt',text,api_metrics,...(internal?.reference_sources?{reference_sources:internal.reference_sources}:{})}
   const referenceFields=internal?.reference_sources?{reference_sources:internal.reference_sources}:{}
   let parsed=extracted.parsed
   if(['structure','small_structure','component','selection_edit','workbench'].includes(input.mode))parsed=normalizeReply(parsed,input.mode,context)
   if(input.mode==='selection_edit'){const result={mode:'selection_edit',...validateSelectionResult(parsed,context),api_metrics,...referenceFields};await validateCandidate({mode:input.mode,result,context,signal:token.controller.signal});return result}
   if(input.mode==='component'){
    const schema=require('../.agents/skills/minecraft-nbt-modeler/tool-catalog.json').agent_tools.structure_preview.parameters.properties.spec
    if(!own(parsed,Object.keys(schema.properties)))throw Error('独立结构方案含未开放字段')
    const spec={...parsed,name:context.name,size:context.size}
    if(parsed.size&&JSON.stringify(parsed.size)!==JSON.stringify(context.size))throw Error('AI不能更改用户指定的独立结构尺寸')
    if(!['operations','placements'].some(key=>Array.isArray(spec[key])&&spec[key].length))throw Error('独立结构需要工具步骤或引用资产')
    if(spec.placements!==undefined&&(!Array.isArray(spec.placements)||spec.placements.length>32))throw Error('引用放置须为至多32项的数组')
    const used=[];for(const item of spec.placements??[]){const reference=context.references.find(ref=>ref.id===item.id&&ref.content_sha256===item.content_sha256);if(!reference)throw Error('AI引用了未提供或哈希不匹配的资产');used.push(item.id)}const result={mode:'component',spec,api_metrics,reference_sources:internal?.reference_sources??[],used_assets:[...new Set(used)]};await validateCandidate({mode:input.mode,result,context,signal:token.controller.signal});return result
   }
   if(input.mode==='workbench'){const validated=validateWorkbench(parsed,context);await validateCandidate({mode:input.mode,result:validated,context,signal:token.controller.signal});if(parsed.operation_patch)api_metrics.operation_changes=parsed.operation_patch.changes.length;return {mode:'workbench',...validated,...(parsed.operation_patch?{operation_patch:parsed.operation_patch}:{}),api_metrics,...referenceFields}}
   const result=input.mode==='small_structure'?{mode:'small_structure',...localSmallStructure(parsed,context),api_metrics,...referenceFields}:{mode:'structure',...validatePatch(parsed,context),api_metrics,...referenceFields}
   await validateCandidate({mode:input.mode,result,context,signal:token.controller.signal});return result
  }finally{api_metrics.validation_ms=(api_metrics.validation_ms??0)+Math.round(performance.now()-validating)}
  }
  while(true){
   response=await invoke()
   try{const result=await validateResponse();api_metrics.calls.at(-1).validation_status='passed';return result}catch(error){
    api_metrics.calls.at(-1).validation_status='failed';api_metrics.calls.at(-1).validation_issue=require('./ai-validation-issue.cjs').validationIssue(error)
    if(token.cancelled)throw Error('API 请求已取消')
    const reason=response.choices?.[0]?.finish_reason,text=response.choices?.[0]?.message?.content
    if(error.retryable===false||reason==='content_filter'||api_metrics.attempts>=3||reason==='length'&&compactRetries>=1)throw error
    if(reason==='length'){compactRetries++;api_metrics.retried_compact=true}
    const feedback=reason==='length'?'上次输出达到长度上限。重新给出完整精简答案，不续写；小构件只保留最多24个box/beam/frame操作。':('本地校验未通过：'+error.message.replace(/[\r\n]/g,' ').slice(0,300)+'。仅修正格式、长度或错误参数，保持原任务和原上下文，不扩大权限。')
    payload.messages=structuredClone(originalMessages)
    if(reason!=='length'&&typeof text==='string'&&text.length<=48000&&Array.from(text).length<=Math.min(config.outputCharLimit?config.outputCharLimit*2:24000,24000))payload.messages.push({role:'assistant',content:text})
    else payload.messages.push({role:'assistant',content:'（本地已省略上一次不完整或过长的输出，不能视为已完成的候选。）'})
    payload.messages.push({role:'user',content:feedback+(input.mode==='component'||input.mode==='workbench'&&context.task==='draft'?' 复杂工具难以满足几何条件时，可用box/beam/frame等基础操作组合表达同一构造，保留必要的结构和功能，不以删掉设计需求代替修复。':'')+(config.outputCharLimit?` 最终结果限制仍为 ${config.outputCharLimit} 字。`:' 最终结果不设应用字数限制。')+'只返回完整最终结果，不带无关解释。'})
   }
  }
 }
 async function generate(input,options={}){
  if(modelBusy||saving)throw Error('API 连接测试或配置保存进行中，请稍后重试')
  const frozen=structuredClone(input)
  return scheduler.run(options.requestId,async token=>{
   token.workflowPromise=token.prepared
   try{return await generateCore(frozen,token)}catch(error){error.api_metrics=token.metrics;throw error}
   finally{token.metrics.service_total_ms=Math.round(performance.now()-token.started)}
  },()=>workflowContext(frozen.mode==='workbench'&&['draft','brief'].includes(frozen.context?.task)?'draft':frozen.mode,{retrieval:frozen.retrieval}))
 }
 return {load,save,models,generate,cancel:id=>{const found=scheduler.cancel(id);if(id===undefined)for(const controller of transports)controller.abort();return found||id===undefined},publicConfig,state:scheduler.state}

}
module.exports={localSmallStructure,validateSmallStructure,createApiService,validatePatch,contextOf,configOf}
