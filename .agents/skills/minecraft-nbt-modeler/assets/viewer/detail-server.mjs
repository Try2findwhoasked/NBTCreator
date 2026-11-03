import {portableRequest,absoluteRequest} from './portable-paths.mjs'
import {handoffInfo,writeHandoff} from './agent-handoff.mjs'
// Local detail-control API. All work uses argument arrays and data-only requests.
import fs from 'node:fs/promises'
import { createReadStream } from 'node:fs'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { parseArgs } from 'node:util'
import { randomUUID, createHash } from 'node:crypto'
import { spawn } from 'node:child_process'
import { createViewerServer } from './viewer-server.mjs'
import { savedEffects } from './saved-effects.mjs'
import { createFeedbackStore } from './feedback-store.mjs'
import {createCatalogStore} from './catalog-store.mjs'
import {createProjectStages} from './project-stages.mjs'
import {createEditSessionStore} from './edit-session-store.mjs'
import {createCommandStore} from './command-store.mjs'
import {cleanApiMetrics,cleanTimings} from './ai-metrics.mjs'

const here = path.dirname(fileURLToPath(import.meta.url))
const backend = path.resolve(here, '../../scripts/nbt_detail_control.py')
const json = (res, value, status = 200) => {
  res.statusCode = status; res.setHeader('Content-Type', 'application/json; charset=utf-8')
  res.setHeader('Cache-Control', 'no-store'); res.end(JSON.stringify(value))
}
async function body(req,limit=8*1024*1024) {
  req.setEncoding('utf8')
  let text = ''
  for await (const chunk of req) {
    text += chunk
    if (Buffer.byteLength(text) > limit) throw new Error('Request exceeds '+(limit/1024/1024)+' MiB')
  }
  return JSON.parse(text)
}
function localPath(value) {
  if (typeof value !== 'string' || !path.isAbsolute(value) || value.startsWith('\\\\') || value.startsWith('//')) {
    throw new Error('Choose an absolute local file path')
  }
  return path.resolve(value)
}
function dateStamp() {
  const parts = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23' }).formatToParts(new Date())
  const p = Object.fromEntries(parts.map(item => [item.type, item.value]))
  return `${p.year}-${p.month}-${p.day}/${p.hour}${p.minute}${p.second}`
}

export async function startDetailServer({ workspace, output, python = 'python', port = 0, initialPreset, frontendMode='auto' }) {
  workspace = path.resolve(workspace)
  let outputRoot = path.resolve(output ?? path.join(workspace, 'nbt_models/_workspaces', dateStamp()+'_detail_control_web'))
  const skillRoot = path.resolve(here, '../..')
  if (outputRoot === skillRoot || outputRoot.startsWith(skillRoot+path.sep)) throw new Error('Keep jobs outside the skill installation')
  const effects=savedEffects({workspace,skillRoot,initial:outputRoot})
  outputRoot=await effects.init()
  const jobs = new Map(), snapshots = new Map(), assets = new Map()
  const bindings = new Map(), modelInfo = new Map()
  const sameSource=(a,b)=>typeof a==='string'&&typeof b==='string'&&(process.platform==='win32'?a.toLowerCase()===b.toLowerCase():a===b)
  const openedSource=source=>modelInfo.get(source)||[...modelInfo.values()].find(info=>sameSource(info.source,source))
  const catalogStore=createCatalogStore({workspace,scan:()=>invoke(['catalog','--workspace',workspace,'--include-bugged','--index-only'])})
  const covers=new Map(),batchAssets=new Map()
  const projectStages=createProjectStages(workspace)
  const editSessions=createEditSessionStore(workspace)
  const commandStore=createCommandStore(workspace,JSON.parse(await fs.readFile(path.join(skillRoot,'tool-catalog.json'),'utf8')))
  const ownedChildren=new Set(),stoppingChildren=new WeakMap(),childStopped=Symbol('childStopped')
  let closing=false,closePromise
  const feedback = createFeedbackStore(binding=>{if(!binding.workdir)throw new Error('请重新打开建筑以识别修改意见目录');return path.join(binding.workdir,'修改意见')},path.join(workspace,'build/nbt_feedback'))
  const jobFinished=Symbol('jobFinished')
  const cancelledError=()=>Object.assign(new Error('任务已取消；已生成的诊断文件保留'),{code:'NBTCREATOR_CANCELLED'})
  function checkpoint(job){if(job?.cancel_requested)throw cancelledError()}
  async function registerSnapshot(file,source,job){
    checkpoint(job)
    const bytes=await fs.readFile(file),snapshot=JSON.parse(bytes),id=randomUUID()
    checkpoint(job)
    const info=modelInfo.get(source) ?? await invoke(['inspect','--source',source],undefined,undefined,job)
    checkpoint(job)
    modelInfo.set(source,info)
    bindings.set(id,{kind:'3d',workdir:info.workdir,version_dir:info.version_dir,source,source_sha256:snapshot.source_sha256,geometry_sha256:snapshot.geometry_sha256,
      size:snapshot.size,snapshot:file,snapshot_sha256:createHash('sha256').update(bytes).digest('hex')})
    return id
  }
  let activeJob = null
  async function invoke(args, logPath, onSpawn, job) {
    if(closing)throw new Error('建模服务正在关闭')
    checkpoint(job)
    return new Promise((resolve, reject) => {
      const child = spawn(python, ['-B', backend, ...args], { cwd: workspace, windowsHide: true, shell: false })
      ownedChildren.add(child)
      child[childStopped]=new Promise(done=>child.once('close',()=>{ownedChildren.delete(child);done()}))
      if(job){job.child=child;job.phase=args[0];job.backend_pid=child.pid}
      onSpawn?.(child)
      let stdout = '', stderr = ''
      child.stdout.setEncoding('utf8'); child.stderr.setEncoding('utf8')
      child.stdout.on('data', chunk => { stdout += chunk.toString('utf8') })
      child.stderr.on('data', chunk => { stderr += chunk.toString('utf8') })
      child.on('error', reject)
      child.on('close', async code => {
        if(job?.child===child){delete job.child;delete job.backend_pid}
        try {
          if (logPath) await fs.writeFile(logPath, stdout+'\n'+stderr)
          checkpoint(job)
          const data = JSON.parse(stdout)
          if(args[0]==='validate' && code===1 && data.ok && data.result?.status==='candidate_failed')return resolve(data.result)
          if (code !== 0 || !data.ok) throw Object.assign(new Error(data.error ?? stderr ?? 'Backend failed'),{details:data.details})
          resolve(data.result)
        } catch (error) { reject(Object.assign(new Error(error.message + (stderr ? '\n'+stderr : '')),{details:error.details})) }
      })
    })
  }
  function asset(file) {
    const id = randomUUID(); assets.set(id, path.resolve(file)); return `/__detail__/asset/${id}`
  }
  async function registerImages(files, info, job) {
    checkpoint(job)
    if (!files.length) return []
    const system = path.join(outputRoot,'system'); await fs.mkdir(system,{recursive:true})
    const requestFile = path.join(system,'thumbs-'+randomUUID()+'.json')
    await fs.writeFile(requestFile,JSON.stringify(files))
    checkpoint(job)
    const result = await invoke(['thumbnails','--request',requestFile,'--cache',path.join(workspace,'nbt_models/_workspaces/cache/thumbs')],undefined,undefined,job)
    const images=[]
    for (const image of result.images) {
      checkpoint(job)
      const url=asset(image.image), id=url.split('/').at(-1)
      let camera=null, cuts=[]
      try { const meta=JSON.parse(await fs.readFile(image.image.replace(/\.png$/i,'.json'),'utf8')); camera=meta.camera ?? null; cuts=meta.cuts ?? [] } catch {}
      bindings.set(id,{workdir:info.workdir,version_dir:info.version_dir,source:info.source,source_sha256:info.source_sha256,geometry_sha256:info.geometry_sha256,
        image:image.image,image_sha256:image.image_sha256,camera,cuts})
      images.push({id,source:info.source,geometry_sha256:info.geometry_sha256,path:image.image,name:path.basename(image.image),url,thumbnail:asset(image.thumbnail),thumbnail_bytes:image.thumbnail_bytes,image_sha256:image.image_sha256,source_sha256:info.source_sha256})
    }
    return images
  }
  async function launchJob(input) {
    if(closing)throw new Error('建模服务正在关闭')
    if (activeJob) throw new Error('A job is already running; wait or cancel it first')
    const kind = input.kind
    if(kind==='batch')return launchProjectBatch(input)
    if (!['plan', 'prepare', 'render', 'snapshot', 'apply', 'preset', 'preview', 'revision', 'validate', 'compare'].includes(kind)) throw new Error('Unknown job kind')
    const request = input.request
    request.source = localPath(request.source)
    if(request.context)request.context=localPath(request.context)
    else if(!['snapshot','compare'].includes(kind))throw new Error('修改、验证或导出需要门口/路线等坐标保护配置；缺少配置时可先打开3D只读查看')
    if(kind==='compare'){if(typeof request.reference_source!=='string'||!request.reference_source)throw new Error('请选择要比较的已有版本');request.reference_source=localPath(request.reference_source)}
    if (request.cameras) request.cameras = localPath(request.cameras)
    const checkedSnapshot=kind==='validate'?snapshots.get(input.snapshot_key):null
    if(kind==='validate'&&!checkedSnapshot)throw new Error('请先计算当前效果预览，再检查该候选')
    const id = randomUUID()
    const directory = path.join(outputRoot, 'jobs', id)
    const requestPath = path.join(directory, 'request.json')
    const job = { id, kind, status: 'running', created_at: new Date().toISOString(), directory }
    jobs.set(id, job); activeJob = job
    job[jobFinished]=(async () => {
      try {
        await fs.mkdir(directory, { recursive: true })
        checkpoint(job)
        await fs.writeFile(requestPath, JSON.stringify(portableRequest(request,workspace), null, 2))
        checkpoint(job)
        let result
        if (kind === 'preset') result = { status: 'preset_saved', download: asset(requestPath) }
        else {
          let resultDirectory = path.join(directory, 'result')
          let info
          if (['plan','prepare','apply'].includes(kind)) {
            info = await invoke(['inspect','--source',request.source],path.join(directory,'inspect.log'),undefined,job)
            checkpoint(job)
            modelInfo.set(request.source,info)
            const handoff = await handoffInfo(info)
            checkpoint(job)
            if (kind === 'apply') resultDirectory = path.join(info.workdir, 'refined_'+Date.now()+parseInt(id.slice(0,8),16))
            else {
              await fs.mkdir(handoff.directory,{recursive:true})
              checkpoint(job)
              resultDirectory = path.join(handoff.directory, (kind === 'prepare' ? 'review-' : 'plan-')+id)
            }
          }
          const args = [kind, '--request', requestPath, '--output', resultDirectory]
          if(kind==='validate')args.push('--snapshot',checkedSnapshot)
          if (kind === 'apply') args.push('--bundle', localPath(input.bundle), '--review', localPath(input.review))
          result = await invoke(args, path.join(directory, 'backend.log'), undefined,job)
          checkpoint(job)
          if (kind === 'plan') Object.assign(result,await writeHandoff({workspace,info,request,result,requestFile:requestPath}))
        }
        checkpoint(job)
        result.source=request.source
        if(result.baseline_snapshot){const key=randomUUID();snapshots.set(key,result.baseline_snapshot);result.baseline_key=key;result.baseline_feedback_id=await registerSnapshot(result.baseline_snapshot,result.reference_source??request.source,job)}
        if (result.snapshot) {
          checkpoint(job)
          const key = randomUUID(); snapshots.set(key, result.snapshot); result.model_key = key
          result.feedback_id=await registerSnapshot(result.snapshot,request.source,job)
        }
        checkpoint(job)
        if (result.images?.length) {
          const source=result.preview_source ?? request.source
          const info=modelInfo.get(source) ?? await invoke(['inspect','--source',source],undefined,undefined,job)
          checkpoint(job)
          modelInfo.set(source,info)
          result.images=await registerImages(result.images,info,job)
        } else result.images=[]
        checkpoint(job)
        if (result.plan) result.plan_download = asset(result.plan)
        if (result.validation) result.validation_download = asset(result.validation)
        if (result.difference) result.difference_download = asset(result.difference)
        if (result.handoff_file) result.handoff_download = asset(result.handoff_file)
        if(result.runtime_files)result.nbt_downloads=result.runtime_files.map(file=>({name:path.basename(file),url:asset(file)}))
        job.result = result; job.status = 'complete'
      } catch (error) { job.error = job.cancel_requested?cancelledError().message:error.message;if(error.details)job.error_details=error.details;job.status = job.cancel_requested||error.code==='NBTCREATOR_CANCELLED'?'cancelled':'failed' }
      finally {
        job.completed_at = new Date().toISOString(); delete job.child;delete job.backend_pid
        try{await fs.writeFile(path.join(directory, 'job.json'), JSON.stringify(job, null, 2))}
        catch(error){job.persistence_error=error.message}
        if(activeJob===job)activeJob=null
      }
    })()
    return { id }
  }
  async function projectBatch(action,input={}){
    const system=path.join(outputRoot,'system');await fs.mkdir(system,{recursive:true});const request=path.join(system,'batch-'+randomUUID()+'.json');await fs.writeFile(request,JSON.stringify(input))
    try{return await invoke(['project-batch','--workspace',workspace,'--action',action,'--request',request])}finally{await fs.unlink(request).catch(()=>{})}
  }
  function exposeProjectQueue(queue){
    const safeAsset=(file,base=workspace)=>{const resolved=path.resolve(workspace,file),relative=path.relative(base,resolved);if(relative==='..'||relative.startsWith('..'+path.sep)||path.isAbsolute(relative))throw Error('批量任务产物路径越界');if(!batchAssets.has(resolved))batchAssets.set(resolved,asset(resolved));return batchAssets.get(resolved)}
    return {...queue,items:queue.items.map(item=>({...item,steps:Object.fromEntries(Object.entries(item.steps).map(([kind,step])=>[kind,{...step,...(step.report?{report_download:safeAsset(step.report,path.join(workspace,'.nbtcreator/project-queues',queue.id))}:{}),...(step.result?.image?{image_download:safeAsset(step.result.image),thumbnail_download:safeAsset(step.result.thumbnail)}:{})}]))}))}
  }
  async function launchProjectBatch(input){
    if(typeof input.queue_id!=='string'||!/^[a-f0-9]{32}$/.test(input.queue_id))throw Error('批量任务编号无效')
    const id=randomUUID(),directory=path.join(outputRoot,'jobs',id),job={id,kind:'batch',status:'running',created_at:new Date().toISOString(),directory,queue_id:input.queue_id};jobs.set(id,job);activeJob=job
    job[jobFinished]=(async()=>{const file=path.join(directory,'request.json');try{
      await fs.mkdir(directory,{recursive:true});await fs.writeFile(file,JSON.stringify({id:input.queue_id}));checkpoint(job)
      const queue=await invoke(['project-batch','--workspace',workspace,'--action','run','--request',file],path.join(directory,'backend.log'),undefined,job);checkpoint(job)
      for(const item of queue.items){const checked=item.steps.check?.result;if(!checked)continue;const source=path.resolve(workspace,item.source);if(checked.checks?.file?.passed)await catalogStore.record({source,geometry_sha256:checked.geometry_sha256,size:checked.size});else if(checked.checks?.file?.passed===false)await catalogStore.recordFailure(source,checked.checks.file.error)}
      job.result={queue_id:queue.id,progress:queue.progress,summary:`${queue.progress.complete} 项完成 · ${queue.progress.failed} 项未通过`,output:path.join(workspace,'.nbtcreator/project-queues',queue.id)};job.status='complete'
    }catch(error){job.status=job.cancel_requested?'cancelled':'failed';job.error=error.message}
    finally{
      if(job.cancel_requested&&!closing)await projectBatch('cancel',{id:input.queue_id}).catch(()=>{})
      job.completed_at=new Date().toISOString();await fs.writeFile(path.join(directory,'job.json'),JSON.stringify(job,null,2)).catch(error=>{job.persistence_error=error.message});if(activeJob===job)activeJob=null
    }})();return {id}
  }
  function serialJob(job) {
    const { child, ...rest } = job
    return rest
  }
  function terminate(child){
    if(stoppingChildren.has(child))return stoppingChildren.get(child)
    const stopped=(async()=>{
      if(ownedChildren.has(child)&&child.exitCode===null&&child.signalCode===null&&child.pid){
        if(process.platform==='win32')await new Promise(resolve=>{
          const kill=spawn('taskkill.exe',['/PID',String(child.pid),'/T','/F'],{windowsHide:true,shell:false})
          kill.on('close',code=>{if(code!==0&&child.exitCode===null)child.kill('SIGTERM');resolve()})
          kill.on('error',()=>{if(child.exitCode===null)child.kill('SIGTERM');resolve()})
        })
        else child.kill('SIGTERM')
      }
      await child[childStopped]
    })()
    stoppingChildren.set(child,stopped);return stopped
  }
  async function cancel() {
    const job=activeJob
    if(!job)return
    if(job.status!=='running'){await job[jobFinished];return}
    job.cancel_requested=true;job.cancel_requested_at??=new Date().toISOString()
    const child = job.child
    if(child)await terminate(child)
    await job[jobFinished]
  }
  const viewer = await createViewerServer({ port, frontendMode, modelResolver: key => snapshots.get(key), apiHandler: async (req, res, url) => {
    if (!url.pathname.startsWith('/__detail__/')) return false
    try {
      if(url.pathname==='/__detail__/edit-sessions/recent'&&req.method==='GET'){json(res,{recent:await editSessions.recent()})
      } else if(url.pathname==='/__detail__/edit-sessions/load'&&req.method==='POST'){
        const input=await body(req),source=localPath(input.source),info=openedSource(source);if(!info)throw Error('请先打开完整建筑再恢复编辑草稿')
        const result=await editSessions.load(source),view=result.state?.view
        if(view?.mode==='images'&&view.image_hash&&!info.images?.some(image=>image.image_sha256===view.image_hash&&(!view.image_name||image.name===view.image_name))){
          try{const file=await editSessions.imageEvidence(result.source_sha256,view.image_hash,view.image_name,info.geometry_sha256);if(file){result.image=(await registerImages([file],info))[0];result.image.restored=true}else result.warning='上次图片不在当前列表，且没有可用的图片证据；其文字和标记草稿仍保留'}catch(error){result.warning=error.message}
        }
        json(res,result)
      } else if(url.pathname==='/__detail__/edit-sessions/save'&&req.method==='POST'){
        const input=await body(req,32*1024*1024);input.source=localPath(input.source);if(!openedSource(input.source))throw Error('请先打开完整建筑再保存编辑草稿')
        let warning;const view=input.state?.view
        if(view?.mode==='images'&&view.image_hash){const binding=[...bindings.values()].find(b=>b.image&&sameSource(b.source,input.source)&&b.source_sha256===input.source_sha256&&b.image_sha256===view.image_hash&&(!view.image_name||path.basename(b.image)===view.image_name));try{if(!binding)throw Error('请重新打开该图片以保存画面证据');await editSessions.rememberImage(binding)}catch(error){warning='参数与文字草稿已存，但图片未归档：'+error.message}}
        json(res,{...await editSessions.save(input),...(warning?{warning}:{})})
      } else if (req.method === 'POST' && url.pathname === '/__detail__/resolve-request') { json(res,absoluteRequest((await body(req)).request,workspace))
      } else if (url.pathname === '/__detail__/project-stage' && req.method==='POST') {
        const input=await body(req);json(res,await projectStages.save(localPath(input.source),input.stage))
      } else if(url.pathname==='/__detail__/project-stage-batch'&&req.method==='POST'){
        const input=await body(req);if(!Array.isArray(input.items)||input.items.length<1||input.items.length>100||!['auto','unrefined','refined','finalized','discarded'].includes(input.stage))throw Error('批量标记需要1～100个版本及有效创作状态')
        const results=[];for(const item of input.items){try{const result=await projectStages.save(localPath(item.source),input.stage,{bytes:item.file_size,modified_ns:typeof item.modified_ns==='string'?item.modified_ns:undefined,modified_ms:Math.trunc(Number(item.modified_ns)/1e6)});results.push({...result,status:'complete'})}catch(error){results.push({source:item.source,status:'failed',error:error.message})}}
        json(res,{items:results,asset_written:false,approval_created:false})
      } else if(url.pathname==='/__detail__/project-batch'||url.pathname.startsWith('/__detail__/project-batch/')){
        const action=url.pathname.split('/')[3]||'list'
        if(!['list','create','get','retry','cancel'].includes(action)||req.method!==(action==='list'?'GET':'POST'))throw Error('无效批量任务请求')
        const input=action==='list'?{}:await body(req)
        const result=action==='get'&&activeJob?.kind==='batch'&&activeJob.queue_id===input.id?JSON.parse(await fs.readFile(path.join(workspace,'.nbtcreator/project-queues',input.id,'queue.json'),'utf8')):await projectBatch(action,input)
        if(action==='get'&&!result.progress){const steps=result.items.flatMap(item=>Object.values(item.steps));result.progress=Object.fromEntries(['pending','running','complete','failed','cancelled'].map(key=>[key,steps.filter(step=>step.status===key).length]));result.progress.total=steps.length}
        json(res,action==='list'?result:exposeProjectQueue(result))
      } else if (url.pathname === '/__detail__/project-layout' && ['GET','POST'].includes(req.method)) {
        const directory=path.join(workspace,'.nbtcreator'),file=path.join(directory,'project-manager.json')
        if(req.method==='GET'){
          try{json(res,JSON.parse(await fs.readFile(file,'utf8')))}catch(error){if(error.code!=='ENOENT')throw error;json(res,{orders:{}})}
        }else{
          const input=await body(req),orders=input.orders
          if(!orders||Array.isArray(orders)||typeof orders!=='object'||Object.keys(input).some(key=>key!=='orders')||Object.keys(orders).length>3000)throw Error('项目排序配置无效')
          let count=0
          for(const [key,items]of Object.entries(orders)){if(key.length>4096||!Array.isArray(items)||items.some(item=>typeof item!=='string'||item.length>4096)||new Set(items).size!==items.length)throw Error('项目排序配置无效');count+=items.length}
          if(count>6000)throw Error('排序项目过多')
          await fs.mkdir(directory,{recursive:true});const temporary=file+'.'+randomUUID()+'.tmp'
          await fs.writeFile(temporary,JSON.stringify({orders},null,2));await fs.rename(temporary,file);json(res,{orders})
        }
      } else if (req.method === 'GET' && url.pathname === '/__detail__/init') {
        const [loaded, defaults] = await Promise.all([catalogStore.initial(), invoke(['defaults'])]),projectCatalog=await projectStages.apply(loaded.catalog)
        const catalog={...projectCatalog,models:projectCatalog.models.filter(item=>!item.bugged&&!item.unreadable)}
        json(res, { catalog, defaults, workspace, output: outputRoot, features:{web_revision:true,project_feedback:true},
          project_catalog:projectCatalog,catalog_cached:loaded.cached,initial_request:initialPreset ? absoluteRequest(JSON.parse(await fs.readFile(initialPreset,'utf8')),workspace) : null })
      } else if(req.method==='GET'&&url.pathname==='/__detail__/command-preferences')json(res,await commandStore.read())
      else if(req.method==='POST'&&url.pathname==='/__detail__/command-preferences')json(res,await commandStore.save(await body(req,64*1024)))
      else if (req.method === 'GET' && url.pathname === '/__detail__/catalog') {
        const projectCatalog=await projectStages.apply(await catalogStore.refresh());covers.clear()
        json(res,{project_catalog:projectCatalog,catalog:{...projectCatalog,models:projectCatalog.models.filter(item=>!item.bugged&&!item.unreadable)}})
      } else if (req.method === 'GET' && url.pathname.startsWith('/__detail__/prompt/')) {
        const name=url.pathname.slice('/__detail__/prompt/'.length)
        if(!['index.html','core.js','ai-input.js','app.js','style.css','design-tokens.css','theme.css','catalog.js'].includes(name))throw new Error('Unknown prompt asset')
        res.setHeader('Content-Type',name.endsWith('.html')?'text/html; charset=utf-8':name.endsWith('.js')?'text/javascript; charset=utf-8':'text/css; charset=utf-8')
        res.setHeader('Cache-Control','no-store')
        res.end(await fs.readFile(path.join(skillRoot,'prompt-console',name)))
      } else if (req.method === 'POST' && url.pathname === '/__detail__/prompt-export') {
        const input=await body(req)
        input.source=localPath(input.source)
        if(!modelInfo.has(input.source))throw new Error('请先打开要生成提示词的建筑')
        if(input.context)input.context=localPath(input.context)
        if(input.cameras)input.cameras=localPath(input.cameras)
        const directory=path.join(outputRoot,'system');await fs.mkdir(directory,{recursive:true})
        const requestPath=path.join(directory,'prompt-'+randomUUID()+'.json')
        await fs.writeFile(requestPath,JSON.stringify(portableRequest(input,workspace)))
        json(res,await invoke(['prompt','--request',requestPath]))
      } else if(url.pathname==='/__detail__/recipes'||url.pathname.startsWith('/__detail__/recipes/')){
        const action=url.pathname.split('/')[3]||'list'
        if(!['list','get','save','capture','archive','compile'].includes(action)||req.method!==(action==='list'?'GET':'POST'))throw Error('无效配方请求')
        const input=action==='list'?{}:await body(req)
        if(action==='compile'){
          const info=openedSource(localPath(input.source));if(!info||input.source_sha256!==info.source_sha256)throw Error('当前建筑已改变，请重新载入')
          if(createHash('sha256').update(await fs.readFile(info.source)).digest('hex')!==info.source_sha256)throw Error('源文件已改变，请刷新建筑')
          input.size=info.size
        }
        const system=path.join(outputRoot,'system');await fs.mkdir(system,{recursive:true});const file=path.join(system,'recipe-'+randomUUID()+'.json');await fs.writeFile(file,JSON.stringify(input));let result
        try{result=await invoke(['recipes','--workspace',workspace,'--action',action,'--request',file])}finally{await fs.unlink(file).catch(()=>{})}
        if(action==='list')result={...result,items:result.items.map(item=>({...item,download:asset(item.file)}))}
        json(res,result)
      } else if ((url.pathname==='/__detail__/components'||url.pathname.startsWith('/__detail__/components/'))) {
        const action=url.pathname.split('/')[3]||'list'
        if(!['list','save','get','place','batch','import','update','extract','transform'].includes(action)||req.method!==(action==='list'?'GET':'POST'))throw Error('无效构件请求')
        const input=action==='list'?{}:await body(req)
        if(['save','extract','transform'].includes(action)){
          const binding=bindings.get(input.target_id)
          if(!binding||binding.kind!=='3d')throw Error('请先打开要保存的3D模型或候选')
          Object.assign(input,{source:binding.source,snapshot:binding.snapshot,snapshot_sha256:binding.snapshot_sha256})
        }
        if(['place','batch','transform'].includes(action)){
          const info=openedSource(localPath(input.source))
          if(!info||input.source_sha256!==info.source_sha256)throw Error('当前模型版本已改变，请重新打开')
          const actual=createHash('sha256').update(await fs.readFile(info.source)).digest('hex')
          if(actual!==info.source_sha256)throw Error('源文件已改变，请刷新模型')
          input.size=info.size
        }
        const system=path.join(outputRoot,'system');await fs.mkdir(system,{recursive:true})
        const file=path.join(system,'components-'+randomUUID()+'.json')
        await fs.writeFile(file,JSON.stringify(input))
        let result
        try{result=await invoke(['components','--workspace',workspace,'--action',action,'--request',file])}finally{await fs.unlink(file).catch(()=>{})}
        const expose=item=>({...item,thumbnail:item.thumbnail?asset(item.thumbnail):null,download:item.file?asset(item.file):null})
        if(action==='list')result={...result,items:result.items.map(expose)}
        if(['save','import'].includes(action))result=expose(result)
        json(res,result)
      } else if (req.method === 'POST' && url.pathname === '/__detail__/inspect') {
        const input = await body(req)
        const source=localPath(input.source)
        const result = await invoke(['inspect', '--source', source,'--image-limit',String(input.image_limit ?? 8)])
        await catalogStore.record(result)
        modelInfo.set(source,result)
        result.agent_handoff = await handoffInfo(result)
        result.images = await registerImages(result.images,result)
        json(res, result)
      } else if(req.method==='POST'&&url.pathname==='/__detail__/protection-mask'){
        const input=await body(req),info=openedSource(localPath(input.source));if(!info||info.source_sha256!==input.source_sha256)throw Error('请先打开当前版本再查看保护区')
        const system=path.join(outputRoot,'system');await fs.mkdir(system,{recursive:true});const file=path.join(system,'protection-'+randomUUID()+'.json');await fs.writeFile(file,JSON.stringify({source:info.source,source_sha256:info.source_sha256,context:input.context?localPath(input.context):''}))
        try{json(res,await invoke(['protection-mask','--request',file]))}finally{await fs.unlink(file).catch(()=>{})}
      } else if (req.method === 'POST' && url.pathname === '/__detail__/project-cover') {
        const input=await body(req),source=localPath(input.source)
        const geometry=input.geometry??''
        if(typeof geometry!=='string'||(geometry&&! /^[a-f0-9]{64}$/.test(geometry)))throw new Error('请选择建筑库中的有效模型')
        const modelRoot=path.join(workspace,'nbt_models'),relative=path.relative(modelRoot,await fs.realpath(source))
        if(relative==='..'||relative.startsWith('..'+path.sep)||path.isAbsolute(relative))throw new Error('请选择当前工作区建筑库中的模型')
        const stat=await fs.stat(source),key=JSON.stringify([source,geometry,stat.mtimeMs,stat.size,input.generate===true])
        let entry=covers.get(key)
        if(!entry||Date.now()-entry.created>60000){
          const promise=invoke(['cover','--source',source,'--geometry',geometry,'--cache',path.join(workspace,'.nbtcreator/cache/section-covers'),...(input.generate===true?['--generate-missing']:[])]).then(result=>({image:result.image?asset(result.image):null,thumbnail:result.thumbnail?asset(result.thumbnail):null,section:result.section,profile:result.profile,cached:result.cached,generated:result.generated})).catch(error=>{covers.delete(key);throw error})
          entry={created:Date.now(),promise};if(covers.size>=600)covers.delete(covers.keys().next().value);covers.set(key,entry)
        }
        const result=await entry.promise
        // A newly generated cover must replace a cached miss immediately,
        // including after the library is filtered or refreshed.
        if(input.generate===true)for(const saved of covers.keys())if(saved!==key&&JSON.parse(saved)[0]===source)covers.delete(saved)
        json(res,result)
      } else if (req.method === 'POST' && url.pathname.startsWith('/__detail__/feedback/')) {
        const input=await body(req), binding=bindings.get(input.target_id ?? input.image_id)
        if(!binding)throw new Error('请先打开对应图片或3D建筑')
        const operation=url.pathname.split('/').at(-1)
        if(operation==='list')json(res,await feedback.list(binding))
        else if(operation==='add'){
          if(binding.kind==='3d'){
            if(!Array.isArray(input.anchors))throw new Error('3D意见需要明确的位置列表')
            const snapshot=JSON.parse(await fs.readFile(binding.snapshot,'utf8')),blocks=new Map(snapshot.blocks.map(([p,s])=>[p.join(','),s]))
            for(const anchor of input.anchors){if(!Array.isArray(anchor?.position)||blocks.get(anchor.position.join(','))!==anchor.state||['minecraft:air','minecraft:cave_air','minecraft:void_air'].includes(anchor.state?.split('[')[0]))throw new Error('选取的坐标与当前3D快照不符，请重新选点')}
          }
          json(res,await feedback.add(binding,input.text,input.point ?? null,await effects.references(input.references ?? []),input.anchors ?? null))
        }
        else if(operation==='status')json(res,await feedback.update(binding,input.note_id,input.status))
        else if(operation==='export'){
          const exported=await feedback.export(binding)
          json(res,{json:asset(exported.json),markdown:asset(exported.markdown),file:exported.json})
        }else throw new Error('Unknown feedback operation')
      } else if(req.method==='POST'&&url.pathname==='/__detail__/choose-output'){
        const code='import tkinter as t, tkinter.filedialog as f, json, sys; r=t.Tk(); r.withdraw(); r.attributes("-topmost", True); print(json.dumps(f.askdirectory(parent=r,initialdir=sys.argv[1],title="选择效果文件保存文件夹"))); r.destroy()'
        const selected=await new Promise((resolve,reject)=>{
          const child=spawn(python,['-c',code,outputRoot],{windowsHide:true,shell:false});let value='',error=''
          child.stdout.on('data',data=>value+=data);child.stderr.on('data',data=>error+=data);child.on('error',reject)
          child.on('close',exit=>{try{if(exit!==0)throw new Error('文件夹选择器不可用，请直接填写完整路径。'+error);resolve(JSON.parse(value))}catch(e){reject(e)}})
        });json(res,{path:selected})
      } else if(req.method==='POST'&&url.pathname==='/__detail__/output'){
        if(activeJob)throw new Error('请等当前任务结束后再更换保存位置')
        outputRoot=await effects.set((await body(req)).output);json(res,await effects.scan())
      } else if(req.method==='GET'&&url.pathname==='/__detail__/effects')json(res,await effects.scan())
      else if(req.method==='POST'&&url.pathname==='/__detail__/effects/save'){
        const input=await body(req);json(res,await effects.save(input.request,input.name))
      } else if(req.method==='POST'&&url.pathname==='/__detail__/ai-activities'){
        const input=await body(req)
        if(input.action==='start'){
          if(!['draft','prompt','workbench','structure','small_structure'].includes(input.workflow))throw Error('Unknown AI workflow')
          const id=randomUUID(),directory=path.join(outputRoot,'jobs',id)
          await fs.mkdir(directory,{recursive:true})
          const job={id,kind:'ai',workflow:input.workflow,label:String(input.label||'AI构建').slice(0,200),instruction:String(input.instruction||'').slice(0,12000),model:String(input.model||'').slice(0,150),provider:String(input.provider||'').slice(0,100),screenshot:input.screenshot===true,status:'running',created_at:new Date().toISOString(),directory,events:[{time:new Date().toISOString(),message:'AI请求已创建'}]}
          jobs.set(id,job);await fs.writeFile(path.join(directory,'job.json'),JSON.stringify(job,null,2));json(res,{id})
        }else{
          const job=jobs.get(input.id);if(!job||job.kind!=='ai')throw Error('Unknown AI activity')
          const message=String(input.message||'').slice(0,2000)
          if(job.events.length<200)job.events.push({time:new Date().toISOString(),message})
          if(input.action==='stage'){job.status='running';delete job.completed_at;if(['capture','api','preview'].includes(input.phase))job.phase=input.phase}
          else if(input.action==='finish'){
            if(!['complete','failed','cancelled'].includes(input.status))throw Error('Invalid AI activity status')
            job.status=input.status;job.completed_at=new Date().toISOString();job.result={...job.result,summary:String(input.summary??job.result?.summary??'').slice(0,4000),operations:Number(input.operations??job.result?.operations??0),preview_only:true};if(job.status!=='complete')job.error=message;else delete job.error
            if(input.api_metrics)job.api_metrics=cleanApiMetrics(input.api_metrics)
            if(input.timings)job.timings={...job.timings,...cleanTimings(input.timings)}
          }else throw Error('Unknown AI activity action')
          await fs.writeFile(path.join(job.directory,'job.json'),JSON.stringify(job,null,2));json(res,{id:job.id})
        }
      } else if (req.method === 'POST' && url.pathname === '/__detail__/jobs') json(res, await launchJob(await body(req)), 202)
      else if (req.method === 'GET' && url.pathname === '/__detail__/jobs') json(res, [...jobs.values()].map(serialJob))
      else if (req.method === 'POST' && url.pathname === '/__detail__/cancel') { await cancel(); json(res, { ok: true }) }
      else if (req.method === 'GET' && url.pathname.startsWith('/__detail__/jobs/')) {
        const job = jobs.get(url.pathname.split('/').at(-1)); if (!job) throw new Error('Unknown job'); json(res, serialJob(job))
      } else if (req.method === 'GET' && url.pathname.startsWith('/__detail__/asset/')) {
        const file = assets.get(url.pathname.split('/').at(-1)); if (!file) throw new Error('Unknown artifact')
        res.setHeader('Content-Type', file.endsWith('.png') ? 'image/png' : file.endsWith('.jpg') ? 'image/jpeg' : file.endsWith('.md') ? 'text/markdown; charset=utf-8' : file.endsWith('.nbt') ? 'application/octet-stream' : 'application/json; charset=utf-8')
        res.setHeader('Cache-Control', file.endsWith('.jpg') ? 'private, max-age=3600, immutable' : 'no-store')
        createReadStream(file).on('error', () => { res.statusCode = 404; res.end() }).pipe(res)
      } else { json(res, { error: 'Unknown endpoint' }, 404) }
    } catch (error) { json(res, { error: error.message }, 400) }
    return true
  } })
  return { url: viewer.url+'control.html', frontend:viewer.frontend, output: outputRoot, close: () => {
    if(!closePromise){closing=true;closePromise=(async()=>{await Promise.all([cancel(),...Array.from(ownedChildren,terminate)]);await viewer.close()})()}
    return closePromise
  } }
}

async function main() {
  const { values } = parseArgs({ options: { workspace: { type: 'string' }, output: { type: 'string' },
    python: { type: 'string' }, port: { type: 'string', default: '0' }, 'no-open': { type: 'boolean' }, 'initial-preset':{type:'string'} } })
  if (!values.workspace) throw new Error('Usage: node detail-server.mjs --workspace repository [--no-open]')
  const app = await startDetailServer({ ...values,initialPreset:values['initial-preset'], port: Number(values.port) })
  console.log(JSON.stringify({ url: app.url, output: app.output }))
  if (!values['no-open']) {
    const command = process.platform === 'win32' ? 'cmd' : process.platform === 'darwin' ? 'open' : 'xdg-open'
    const args = process.platform === 'win32' ? ['/c', 'start', '', app.url] : [app.url]
    const child = spawn(command, args, { detached: true, stdio: 'ignore', windowsHide: true }); child.on('error', () => {}); child.unref()
  }
  const stop = async () => { await app.close(); process.exit(0) }
  process.on('SIGINT', stop); process.on('SIGTERM', stop)
}
if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) main().catch(error => { console.error(error.message); process.exitCode = 1 })
