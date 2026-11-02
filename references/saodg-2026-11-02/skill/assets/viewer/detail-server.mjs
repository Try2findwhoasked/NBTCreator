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

const here = path.dirname(fileURLToPath(import.meta.url))
const backend = path.resolve(here, '../../scripts/nbt_detail_control.py')
const json = (res, value, status = 200) => {
  res.statusCode = status; res.setHeader('Content-Type', 'application/json; charset=utf-8')
  res.setHeader('Cache-Control', 'no-store'); res.end(JSON.stringify(value))
}
async function body(req) {
  req.setEncoding('utf8')
  let text = ''
  for await (const chunk of req) {
    text += chunk
    if (Buffer.byteLength(text) > 1024*1024) throw new Error('Request exceeds 1 MiB')
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

export async function startDetailServer({ workspace, output, python = 'python', port = 0, initialPreset }) {
  workspace = path.resolve(workspace)
  let outputRoot = path.resolve(output ?? path.join(workspace, 'nbt_models/_workspaces', dateStamp()+'_detail_control_web'))
  const skillRoot = path.resolve(here, '../..')
  if (outputRoot === skillRoot || outputRoot.startsWith(skillRoot+path.sep)) throw new Error('Keep jobs outside the skill installation')
  const effects=savedEffects({workspace,skillRoot,initial:outputRoot})
  outputRoot=await effects.init()
  const jobs = new Map(), snapshots = new Map(), assets = new Map()
  const bindings = new Map(), modelInfo = new Map()
  const feedback = createFeedbackStore(binding=>{if(!binding.workdir)throw new Error('请重新打开建筑以识别修改意见目录');return path.join(binding.workdir,'修改意见')},path.join(workspace,'build/nbt_feedback'))
  async function registerSnapshot(file,source){
    const bytes=await fs.readFile(file),snapshot=JSON.parse(bytes),id=randomUUID()
    const info=modelInfo.get(source) ?? await invoke(['inspect','--source',source])
    modelInfo.set(source,info)
    bindings.set(id,{kind:'3d',workdir:info.workdir,source,source_sha256:snapshot.source_sha256,geometry_sha256:snapshot.geometry_sha256,
      size:snapshot.size,snapshot:file,snapshot_sha256:createHash('sha256').update(bytes).digest('hex')})
    return id
  }
  let activeJob = null
  async function invoke(args, logPath, onSpawn) {
    return new Promise((resolve, reject) => {
      const child = spawn(python, ['-B', backend, ...args], { cwd: workspace, windowsHide: true, shell: false })
      onSpawn?.(child)
      let stdout = '', stderr = ''
      child.stdout.setEncoding('utf8'); child.stderr.setEncoding('utf8')
      child.stdout.on('data', chunk => { stdout += chunk.toString('utf8') })
      child.stderr.on('data', chunk => { stderr += chunk.toString('utf8') })
      child.on('error', reject)
      child.on('close', async code => {
        try {
          if (logPath) await fs.writeFile(logPath, stdout+'\n'+stderr)
          const data = JSON.parse(stdout)
          if (code !== 0 || !data.ok) throw new Error(data.error ?? stderr ?? 'Backend failed')
          resolve(data.result)
        } catch (error) { reject(new Error(error.message + (stderr ? '\n'+stderr : ''))) }
      })
    })
  }
  function asset(file) {
    const id = randomUUID(); assets.set(id, path.resolve(file)); return `/__detail__/asset/${id}`
  }
  async function registerImages(files, info) {
    if (!files.length) return []
    const system = path.join(outputRoot,'system'); await fs.mkdir(system,{recursive:true})
    const requestFile = path.join(system,'thumbs-'+randomUUID()+'.json')
    await fs.writeFile(requestFile,JSON.stringify(files))
    const result = await invoke(['thumbnails','--request',requestFile,'--cache',path.join(workspace,'nbt_models/_workspaces/cache/thumbs')])
    const images=[]
    for (const image of result.images) {
      const url=asset(image.image), id=url.split('/').at(-1)
      let camera=null, cuts=[]
      try { const meta=JSON.parse(await fs.readFile(image.image.replace(/\.png$/i,'.json'),'utf8')); camera=meta.camera ?? null; cuts=meta.cuts ?? [] } catch {}
      bindings.set(id,{workdir:info.workdir,source:info.source,source_sha256:info.source_sha256,geometry_sha256:info.geometry_sha256,
        image:image.image,image_sha256:image.image_sha256,camera,cuts})
      images.push({id,source:info.source,geometry_sha256:info.geometry_sha256,path:image.image,name:path.basename(image.image),url,thumbnail:asset(image.thumbnail),thumbnail_bytes:image.thumbnail_bytes,image_sha256:image.image_sha256,source_sha256:info.source_sha256})
    }
    return images
  }
  async function launchJob(input) {
    if (activeJob) throw new Error('A job is already running; wait or cancel it first')
    const kind = input.kind
    if (!['plan', 'prepare', 'render', 'snapshot', 'apply', 'preset', 'preview', 'revision'].includes(kind)) throw new Error('Unknown job kind')
    const request = input.request
    request.source = localPath(request.source)
    request.context = localPath(request.context)
    if (request.cameras) request.cameras = localPath(request.cameras)
    const id = randomUUID()
    const directory = path.join(outputRoot, 'jobs', id)
    await fs.mkdir(directory, { recursive: true })
    const requestPath = path.join(directory, 'request.json')
    await fs.writeFile(requestPath, JSON.stringify(request, null, 2))
    const job = { id, kind, status: 'running', created_at: new Date().toISOString(), directory }
    jobs.set(id, job); activeJob = job
    ;(async () => {
      try {
        let result
        if (kind === 'preset') result = { status: 'preset_saved', download: asset(requestPath) }
        else {
          const args = [kind, '--request', requestPath, '--output', path.join(directory, 'result')]
          if (kind === 'apply') args.push('--bundle', localPath(input.bundle), '--review', localPath(input.review))
          result = await invoke(args, path.join(directory, 'backend.log'), child => { job.child = child })
        }
        result.source=request.source
        if(result.baseline_snapshot){const key=randomUUID();snapshots.set(key,result.baseline_snapshot);result.baseline_key=key;result.baseline_feedback_id=await registerSnapshot(result.baseline_snapshot,request.source)}
        if (result.snapshot) {
          const key = randomUUID(); snapshots.set(key, result.snapshot); result.model_key = key
          result.feedback_id=await registerSnapshot(result.snapshot,request.source)
        }
        if (result.images?.length) {
          const source=result.preview_source ?? request.source
          const info=modelInfo.get(source) ?? await invoke(['inspect','--source',source])
          modelInfo.set(source,info)
          result.images=await registerImages(result.images,info)
        } else result.images=[]
        if (result.plan) result.plan_download = asset(result.plan)
        if(result.runtime_files)result.nbt_downloads=result.runtime_files.map(file=>({name:path.basename(file),url:asset(file)}))
        job.result = result; job.status = 'complete'
      } catch (error) { job.error = error.message; job.status = 'failed' }
      finally {
        job.completed_at = new Date().toISOString(); delete job.child
        activeJob = null
        await fs.writeFile(path.join(directory, 'job.json'), JSON.stringify(job, null, 2))
      }
    })()
    return { id }
  }
  function serialJob(job) {
    const { child, ...rest } = job
    return rest
  }
  async function cancel() {
    const child = activeJob?.child
    if (!child || child.exitCode !== null) return
    if (process.platform === 'win32') {
      await new Promise(resolve => {
        const kill = spawn('taskkill.exe', ['/PID', String(child.pid), '/T', '/F'], { windowsHide: true, shell: false })
        kill.on('close', resolve); kill.on('error', resolve)
      })
    } else child.kill('SIGTERM')
  }
  const viewer = await createViewerServer({ port, modelResolver: key => snapshots.get(key), apiHandler: async (req, res, url) => {
    if (!url.pathname.startsWith('/__detail__/')) return false
    try {
      if (req.method === 'GET' && url.pathname === '/__detail__/init') {
        const [catalog, defaults] = await Promise.all([invoke(['catalog','--workspace',workspace]), invoke(['defaults'])])
        json(res, { catalog, defaults, workspace, output: outputRoot, features:{web_revision:true,project_feedback:true},
          initial_request:initialPreset ? JSON.parse(await fs.readFile(initialPreset,'utf8')) : null })
      } else if (req.method === 'GET' && url.pathname.startsWith('/__detail__/prompt/')) {
        const name=url.pathname.slice('/__detail__/prompt/'.length)
        if(!['index.html','core.js','app.js','style.css'].includes(name))throw new Error('Unknown prompt asset')
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
        await fs.writeFile(requestPath,JSON.stringify(input))
        json(res,await invoke(['prompt','--request',requestPath]))
      } else if (req.method === 'POST' && url.pathname === '/__detail__/inspect') {
        const input = await body(req)
        const source=localPath(input.source)
        const result = await invoke(['inspect', '--source', source,'--image-limit',String(input.image_limit ?? 8)])
        modelInfo.set(source,result)
        result.images = await registerImages(result.images,result)
        json(res, result)
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
  return { url: viewer.url+'control.html', output: outputRoot, close: async () => { await cancel(); await viewer.close() } }
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
