const {app,BrowserWindow,ipcMain,dialog,utilityProcess,Menu,safeStorage,net,clipboard,shell}=require('electron')
const {createAppSettings}=require('./app-settings.cjs')
const {createUpdater}=require('./updater.cjs')
const {createInternalAI}=require('./internal-ai.cjs')
const {createApiService}=require('./api-service.cjs')
const {createWorkspaceApi}=require('./workspace-api.cjs')
const {selectWorkspace,normalizeWorkspace}=require('./workspace.cjs')
const {spawn}=require('node:child_process')
const path=require('node:path')
const fs=require('node:fs/promises')
const root=path.resolve(__dirname,'..')
const automationMinimized=process.env.NBTCREATOR_AUTOMATION==='1'&&process.env.NBTCREATOR_AUTOMATION_VISIBLE!=='1'
let window,worker,serverUrl,closing=false,workspace,frontend
async function flushEditor(){
 if(!window||window.isDestroyed()||window.webContents.isDestroyed())return
 let timer
 try{await Promise.race([window.webContents.executeJavaScript('window.nbtEditSession?.flush()'),new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error('编辑草稿保存超时')),3500)})])}
 catch(error){console.error('Editor draft flush: '+error.message)}finally{clearTimeout(timer)}
}
const {resolvePython,configureRenderRuntime}=require('./python-runtime.cjs')
const python=resolvePython(root)
configureRenderRuntime(root,app.isPackaged?process.execPath:null)
const arg=(name)=>{const i=process.argv.indexOf(name);return i<0?null:process.argv[i+1]}
if(arg('--user-data-dir'))app.setPath('userData',path.resolve(arg('--user-data-dir')))
function allowed(event){if(!window||event.sender!==window.webContents||event.senderFrame!==window.webContents.mainFrame||!serverUrl||new URL(event.senderFrame.url).origin!==new URL(serverUrl).origin)throw Error('Unexpected IPC sender')}
async function recordConfig(){let value=path.relative(app.getPath('userData'),workspace);if(path.isAbsolute(value))value=workspace;await fs.writeFile(path.join(app.getPath('userData'),'settings.json'),JSON.stringify({workspace:value,path_base:'settings',workspace_source:'manual'},null,2))}
async function exposure(command,config,documents=[]){
 const args=['-B',path.join(root,'.agents/skills/minecraft-nbt-modeler/scripts/nbt_exposure.py'),command,'--workspace',workspace]
 if(config){const file=path.join(app.getPath('userData'),'exposure-pending.json');await fs.writeFile(file,JSON.stringify(config));args.push('--config',file)}
 for(const document of documents)args.push('--document',document)
 return new Promise((resolve,reject)=>{const child=spawn(python,args,{cwd:workspace,shell:false,windowsHide:true});let output='',error='';child.stdout.on('data',d=>output+=d);child.stderr.on('data',d=>error+=d);child.on('error',reject);child.on('close',code=>{try{if(code!==0)throw Error(error||'Skill暴露配置失败');resolve(JSON.parse(output))}catch(e){reject(e)}})})
}
async function startBackend(){
 return new Promise((resolve,reject)=>{
  const instance=utilityProcess.fork(path.join(__dirname,'worker.mjs'),[],{cwd:root,stdio:'pipe'})
  worker=instance;let settled=false
  const timeout=setTimeout(()=>{instance.kill();reject(Error('Backend start timeout'))},30000)
  instance.stdout?.on('data',data=>process.stdout.write(data));instance.stderr?.on('data',data=>process.stderr.write(data))
  instance.on('message',message=>{
   if(message.type==='ready'){settled=true;clearTimeout(timeout);serverUrl=message.url;frontend=message.frontend;resolve(message.url)}
   if(message.type==='error'){clearTimeout(timeout);if(!settled)reject(Error(message.error));else dialog.showErrorBox('NBTCreator 后端错误',message.error)}
  })
  instance.on('exit',code=>{clearTimeout(timeout);if(!settled)reject(Error('Backend exited: '+code));else if(!closing&&worker===instance)dialog.showErrorBox('NBTCreator','建模服务已退出，请重新启动应用。')})
  instance.postMessage({type:'start',workspace,python,frontendMode:arg('--frontend')||(app.isPackaged?'production':'auto'),output:path.join(workspace,'nbt_models/_workspaces/desktop')})
 })
}
async function stopBackend(){
 const active=worker;if(!active)return;worker=null
 await new Promise(resolve=>{const timer=setTimeout(()=>{active.kill();resolve()},5000);active.once('exit',()=>{clearTimeout(timer);resolve()});active.postMessage({type:'stop'})})
}
function trustedDestination(url){try{return serverUrl&&new URL(url).origin===new URL(serverUrl).origin}catch{return false}}
async function boot(){
 if(app.isPackaged){
  let info;try{info=JSON.parse(await fs.readFile(path.join(path.dirname(process.execPath),'portable-info.json'),'utf8'))}catch{}
  if(info?.runtime_id){let runtime;try{runtime=JSON.parse(await fs.readFile(path.join(path.dirname(process.execPath),'runtime-info.json'),'utf8'))}catch{}if(runtime?.runtime_id!==info.runtime_id)throw Error('应用与运行环境不匹配：请将配套 runtime 包解压到同一目录，或使用完整 portable 包。')}
 }

 await fs.mkdir(app.getPath('userData'),{recursive:true})
 const preferences=createAppSettings(()=>path.join(workspace,'.nbtcreator')),updater=createUpdater({directory:app.getPath('userData'),version:app.getVersion(),safeStorage,fetchImpl:(...args)=>net.fetch(...args)})
 let initialPreferences
 const internalAI=createInternalAI({workspace:()=>workspace,skill:path.join(root,'.agents/skills/minecraft-nbt-modeler')})
 let api
 const workspaceApi=createWorkspaceApi({cancel:()=>api?.cancel()})
 api=createApiService({workflowContext:key=>workspaceApi.guardContext(()=>internalAI.context(key)),directory:app.getPath('userData'),safeStorage,fetchImpl:(...args)=>net.fetch(...args)})
 await api.load()
 for(const [channel,handler]of Object.entries({'api-config':()=>api.publicConfig(),'api-save':input=>api.save(input),'api-models':()=>api.models(),'api-cancel':()=>api.cancel()}))ipcMain.handle('nbt:'+channel,(event,input)=>{allowed(event);return workspaceApi.run(()=>handler(input))})
 // Electron serializes thrown errors without custom fields. Return a bounded
 // failure envelope so the renderer can preserve this request's measurements.
 ipcMain.handle('nbt:api-generate',async(event,input)=>{allowed(event);try{return await workspaceApi.run(()=>api.generate(input))}catch(error){return {api_error:{message:error.message,api_metrics:error.api_metrics}}}})
 let config={};try{config=JSON.parse(await fs.readFile(path.join(app.getPath('userData'),'settings.json'),'utf8'))}catch{}
 workspace=selectWorkspace({explicit:arg('--workspace'),environment:process.env.NBTCREATOR_WORKSPACE,agentCwd:process.env.NBTCREATOR_AGENT_CWD,cwd:process.cwd(),root,packaged:app.isPackaged,executable:app.getPath('exe'),config,settingsDirectory:app.getPath('userData'),systemDirectory:process.env.WINDIR})
 if(!workspace){const choice=await dialog.showOpenDialog({title:'选择项目根目录或nbt_models（自动识别）',properties:['openDirectory','createDirectory']});if(choice.canceled){app.quit();return}workspace=normalizeWorkspace(choice.filePaths[0]);await recordConfig()}
 const localPreferences=path.join(workspace,'.nbtcreator/preferences.json')
 try{await fs.access(localPreferences)}catch(e){if(e.code!=='ENOENT')throw e;try{const legacy=JSON.parse(await fs.readFile(path.join(app.getPath('userData'),'preferences.json'),'utf8'));await preferences.save(legacy)}catch(e){if(e.code!=='ENOENT')console.error('Legacy preferences:',e.message)}}
 initialPreferences=await preferences.load()
 await fs.mkdir(path.join(workspace,'nbt_models'),{recursive:true})
 await exposure('apply')
 ipcMain.handle('nbt:exposure-config',event=>{allowed(event);return exposure('show')})
 ipcMain.handle('nbt:exposure-save',(event,input)=>{allowed(event);return exposure('apply',input)})
 ipcMain.handle('nbt:exposure-import',async event=>{allowed(event);const selected=await dialog.showOpenDialog(window,{title:'添加知识文件（复制到当前工作区）',properties:['openFile','multiSelections'],filters:[{name:'Markdown / TXT',extensions:['md','txt']}]});return selected.canceled?null:exposure('import',undefined,selected.filePaths)})
 ipcMain.handle('nbt:knowledge-preview',async(event,input)=>{
  allowed(event)
  if(input?.scope==='internal')return internalAI.preview(input.id)
  if(input?.scope!=='external')throw Error('Unknown knowledge scope')
  if(input.entry)return {title:'当前工作区对外Skill入口',recipient:'由外部Codex/文件式Skill Agent读取，不自动发给内部API。',text:await fs.readFile(path.join(workspace,'.agents/skills/nbtcreator-workspace/SKILL.md'),'utf8')}
  const config=await exposure('show');let file,title
  if(input.group){const group=config.groups.find(g=>g.id===input.group);if(!group||!group.files.includes(input.file))throw Error('Unknown skill reference');file=path.join(root,'.agents/skills/minecraft-nbt-modeler/references',input.file);title=input.file}
  else {const doc=config.custom_knowledge.find(d=>d.id===input.id);if(!doc)throw Error('Unknown skill document');file=path.join(workspace,'.nbtcreator',doc.path);title=doc.label}
  return {title,recipient:'供当前工作区的Codex/文件式Skill Agent阅读；不会因为暴露而自动发送给内部API。',text:await fs.readFile(file,'utf8')}
 })
 ipcMain.handle('nbt:internal-ai-config',event=>{allowed(event);return internalAI.show()})
 ipcMain.handle('nbt:internal-ai-save',(event,input)=>{allowed(event);return internalAI.save(input)})
 ipcMain.handle('nbt:internal-ai-import',async event=>{allowed(event);const selected=await dialog.showOpenDialog(window,{title:'添加内部AI资料（选中后会在生成时发送到API）',properties:['openFile','multiSelections'],filters:[{name:'Markdown / TXT',extensions:['md','txt']}]});return selected.canceled?null:internalAI.importDocuments(selected.filePaths)})
 await startBackend()
 window=new BrowserWindow({width:initialPreferences.rememberWindow?initialPreferences.windowWidth:1500,height:initialPreferences.rememberWindow?initialPreferences.windowHeight:1000,minWidth:900,minHeight:650,frame:true,show:false,title:'NBTCreator',webPreferences:{preload:path.join(__dirname,'preload.cjs'),contextIsolation:true,nodeIntegration:false,sandbox:true,backgroundThrottling:!automationMinimized}})
 if(automationMinimized){window.on('restore',()=>window.minimize());window.minimize()}
 window.on('close',event=>{if(!closing){event.preventDefault();app.quit()}})
 ipcMain.handle('nbt:app-settings',async event=>{allowed(event);return {...await preferences.load(),version:app.getVersion(),workspace,python,electron:process.versions.electron,node:process.versions.node,platform:process.platform,arch:process.arch,packaged:app.isPackaged,configDirectory:path.join(workspace,'.nbtcreator'),userDirectory:app.getPath('userData'),applicationDirectory:root,assetsDirectory:path.join(workspace,'nbt_models'),skillEntry:path.join(workspace,'.agents/skills/nbtcreator-workspace/SKILL.md')}})
 let resizeTimer
 window.on('resize',()=>{clearTimeout(resizeTimer);resizeTimer=setTimeout(async()=>{try{const p=await preferences.load(),b=window.getBounds();if(p.rememberWindow&&!window.isMaximized()&&b.width>=900&&b.height>=650)await preferences.save({windowWidth:b.width,windowHeight:b.height})}catch(e){console.error(e.message)}},400)})
 ipcMain.handle('nbt:batch-open',(event,input)=>{allowed(event);return workspaceApi.run(()=>require('./batch-links.cjs').openBatchLink({workspace,input,shell,simulate:automationMinimized,locate:async request=>{const response=await net.fetch(new URL('/__detail__/batches/locate',serverUrl).href,{method:'POST',headers:{'content-type':'application/json',origin:new URL(serverUrl).origin},body:JSON.stringify(request),redirect:'error'});const data=await response.json();if(!response.ok)throw Error(data.error||'批次入口无法读取');return data}}))})
 ipcMain.handle('nbt:settings-open-folder',async(event,kind)=>{allowed(event);const folders={workspace,config:path.join(workspace,'.nbtcreator'),assets:path.join(workspace,'nbt_models'),user:app.getPath('userData')};if(!Object.hasOwn(folders,kind))throw Error('Unknown directory');await fs.mkdir(folders[kind],{recursive:true});return shell.openPath(folders[kind])})
 ipcMain.handle('nbt:app-settings-save',async(event,input)=>{allowed(event);const saved=await preferences.save(input);window.webContents.setZoomFactor(saved.zoom/100);return saved})
 for(const [name,handler]of Object.entries({'update-access':()=>updater.access(),'update-access-save':input=>updater.saveAccess(input),'update-check':()=>updater.check(),'update-download':kind=>updater.download(kind),'update-status':()=>updater.status(),'update-folder':async()=>{await fs.mkdir(updater.folder(),{recursive:true});return shell.openPath(updater.folder())}}))ipcMain.handle('nbt:'+name,(event,input)=>{allowed(event);return handler(input)})
 window.webContents.setWindowOpenHandler(()=>({action:'deny'}))
 window.webContents.on('will-navigate',(event,url)=>{if(!trustedDestination(url))event.preventDefault()})
 window.webContents.on('will-attach-webview',event=>event.preventDefault())
 window.webContents.session.setPermissionRequestHandler((_contents,_permission,callback)=>callback(false))
 window.webContents.session.on('will-download',(_event,item)=>{if(!trustedDestination(item.getURL())&&!item.getURL().startsWith('blob:'+new URL(serverUrl).origin))item.cancel()})
 ipcMain.handle('nbt:copy-agent-plan',(event,text)=>{
  allowed(event)
  if(typeof text!=='string'||Buffer.byteLength(text,'utf8')>1024*1024)throw Error('Invalid handoff text')
  clipboard.writeText(text);return true
 })
 ipcMain.handle('nbt:info',event=>{allowed(event);return {version:app.getVersion(),workspace,python,frontend,skill:'.agents/skills/nbtcreator-workspace/SKILL.md',migration:'shared-engine'}})
 ipcMain.handle('nbt:source',async event=>{allowed(event);const result=await dialog.showOpenDialog(window,{title:'选择完整 NBT 或主模型',properties:['openFile'],filters:[{name:'NBT / Master',extensions:['nbt','gz']}]});return result.canceled?null:result.filePaths[0]})
 let switchingWorkspace=false
 ipcMain.handle('nbt:workspace',async event=>{
  allowed(event);const selection=await dialog.showOpenDialog(window,{title:'选择项目根目录或nbt_models（自动识别）',defaultPath:workspace,properties:['openDirectory','createDirectory']})
  if(selection.canceled)return null
  const next=normalizeWorkspace(selection.filePaths[0])
  const response=await dialog.showMessageBox(window,{type:'question',buttons:['切换工作区','取消'],defaultId:1,cancelId:1,message:'切换将结束当前服务及未完成任务。请先保存参数和意见。',detail:'实际项目目录：'+next+'\n建筑目录：'+path.join(next,'nbt_models')+'\n同时同步Skill脚本、数据和知识库。已有目标知识配置保留；新工作区携带当前知识组。'})
  if(response.response!==0)return null
  if(switchingWorkspace)throw Error('正在切换工作区，请稍后重试')
  const previous=workspace
  switchingWorkspace=true
  let suspended=false
  try{
   await flushEditor()
   await workspaceApi.suspend();suspended=true
   const currentExposure=await exposure('show')
   await stopBackend();workspace=next
   await fs.mkdir(path.join(workspace,'nbt_models'),{recursive:true})
   let targetHasConfig=false;try{await fs.access(path.join(workspace,'.nbtcreator/skill-exposure.json'));targetHasConfig=true}catch{}
   if(!targetHasConfig)for(const item of currentExposure.custom_knowledge??[]){const from=path.resolve(previous,'.nbtcreator',item.path),to=path.resolve(workspace,'.nbtcreator',item.path);const bytes=await fs.readFile(from);await fs.mkdir(path.dirname(to),{recursive:true});try{const existing=await fs.readFile(to);if(!bytes.equals(existing))throw Error('目标自定义知识文件已有不同内容，未覆盖')}catch(e){if(e.code!=='ENOENT')throw e;await fs.writeFile(to,bytes)}}
   await exposure('apply',targetHasConfig?undefined:{schema_version:1,enabled_groups:currentExposure.enabled_groups,custom_knowledge:currentExposure.custom_knowledge??[]})
   await recordConfig();await startBackend();workspaceApi.resume();await window.loadURL(serverUrl);window.webContents.setZoomFactor((await preferences.load()).zoom/100);return workspace
  }catch(error){if(suspended){await workspaceApi.suspend();await stopBackend();workspace=previous;await recordConfig();await startBackend();workspaceApi.resume();await window.loadURL(serverUrl)}throw error}
  finally{workspaceApi.resume();switchingWorkspace=false}
 })
 const systemMenus=Menu.buildFromTemplate([{label:'项目',submenu:[{label:'选择工作区…',click:()=>window.webContents.executeJavaScript('window.nbtDesktop.chooseWorkspace()')},{label:'打开 NBT / 主模型…',click:()=>window.webContents.executeJavaScript('document.getElementById("desktop-source").click()')},{type:'separator'},{role:'quit'}]},{label:'视图',submenu:[{role:'reload'},{role:'toggleDevTools'},{type:'separator'},{role:'resetZoom'},{role:'zoomIn'},{role:'zoomOut'},{role:'togglefullscreen'}]}])
 Menu.setApplicationMenu(systemMenus)
 window.setMenuBarVisibility(false)
 ipcMain.handle('nbt:system-menu',(event,name)=>{
  allowed(event)
  const index=name==='project'?0:name==='view'?1:-1
  if(index<0)throw Error('Unknown system menu')
  systemMenus.items[index].submenu.popup({window})
 })
 await window.loadURL(serverUrl);window.webContents.setZoomFactor(initialPreferences.zoom/100);window.setTitle('NBTCreator · NBT 建筑工作台');if(automationMinimized)window.minimize();else window.show()
}
app.on('before-quit',event=>{if(!closing){event.preventDefault();closing=true;flushEditor().finally(()=>stopBackend()).finally(()=>app.quit())}})
app.on('window-all-closed',()=>app.quit())
app.whenReady().then(boot).catch(error=>{console.error(error.stack||error.message);if(!process.env.NBTCREATOR_AUTOMATION)dialog.showErrorBox('NBTCreator 启动失败',error.stack||error.message);app.quit()})
