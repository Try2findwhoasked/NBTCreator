const {app,BrowserWindow,ipcMain,dialog,utilityProcess,Menu,safeStorage,net}=require('electron')
const {createApiService}=require('./api-service.cjs')
const {selectWorkspace,normalizeWorkspace}=require('./workspace.cjs')
const {spawn}=require('node:child_process')
const path=require('node:path')
const fs=require('node:fs/promises')
const root=path.resolve(__dirname,'..')
let window,worker,serverUrl,closing=false,workspace,frontend
const python=process.env.NBTCREATOR_PYTHON||'python'
const arg=(name)=>{const i=process.argv.indexOf(name);return i<0?null:process.argv[i+1]}
if(arg('--user-data-dir'))app.setPath('userData',path.resolve(arg('--user-data-dir')))
function allowed(event){if(!window||event.sender!==window.webContents||event.senderFrame!==window.webContents.mainFrame||!serverUrl||new URL(event.senderFrame.url).origin!==new URL(serverUrl).origin)throw Error('Unexpected IPC sender')}
async function recordConfig(){let value=path.relative(app.getPath('userData'),workspace);if(path.isAbsolute(value))value=workspace;await fs.writeFile(path.join(app.getPath('userData'),'settings.json'),JSON.stringify({workspace:value,path_base:'settings',workspace_source:'manual'},null,2))}
async function exposure(command,config){
 const args=['-B',path.join(root,'.agents/skills/minecraft-nbt-modeler/scripts/nbt_exposure.py'),command,'--workspace',workspace]
 if(config){const file=path.join(app.getPath('userData'),'exposure-pending.json');await fs.writeFile(file,JSON.stringify(config));args.push('--config',file)}
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
 await fs.mkdir(app.getPath('userData'),{recursive:true})
 const api=createApiService({directory:app.getPath('userData'),safeStorage,fetchImpl:(...args)=>net.fetch(...args)})
 await api.load()
 for(const [channel,handler]of Object.entries({'api-config':()=>api.publicConfig(),'api-save':input=>api.save(input),'api-models':()=>api.models(),'api-generate':input=>api.generate(input),'api-cancel':()=>api.cancel()}))ipcMain.handle('nbt:'+channel,(event,input)=>{allowed(event);return handler(input)})
 let config={};try{config=JSON.parse(await fs.readFile(path.join(app.getPath('userData'),'settings.json'),'utf8'))}catch{}
 workspace=selectWorkspace({explicit:arg('--workspace'),environment:process.env.NBTCREATOR_WORKSPACE,agentCwd:process.env.NBTCREATOR_AGENT_CWD,cwd:process.cwd(),root,packaged:app.isPackaged,executable:app.getPath('exe'),config,settingsDirectory:app.getPath('userData'),systemDirectory:process.env.WINDIR})
 if(!workspace){const choice=await dialog.showOpenDialog({title:'选择项目根目录或nbt_models（自动识别）',properties:['openDirectory','createDirectory']});if(choice.canceled){app.quit();return}workspace=normalizeWorkspace(choice.filePaths[0]);await recordConfig()}
 await fs.mkdir(path.join(workspace,'nbt_models'),{recursive:true})
 await exposure('apply')
 ipcMain.handle('nbt:exposure-config',event=>{allowed(event);return exposure('show')})
 ipcMain.handle('nbt:exposure-save',(event,input)=>{allowed(event);return exposure('apply',input)})
 await startBackend()
 window=new BrowserWindow({width:1500,height:1000,minWidth:900,minHeight:650,show:false,title:'NBTCreator',webPreferences:{preload:path.join(__dirname,'preload.cjs'),contextIsolation:true,nodeIntegration:false,sandbox:true}})
 window.webContents.setWindowOpenHandler(()=>({action:'deny'}))
 window.webContents.on('will-navigate',(event,url)=>{if(!trustedDestination(url))event.preventDefault()})
 window.webContents.on('will-attach-webview',event=>event.preventDefault())
 window.webContents.session.setPermissionRequestHandler((_contents,_permission,callback)=>callback(false))
 window.webContents.session.on('will-download',(_event,item)=>{if(!trustedDestination(item.getURL())&&!item.getURL().startsWith('blob:'+new URL(serverUrl).origin))item.cancel()})
 ipcMain.handle('nbt:info',event=>{allowed(event);return {version:app.getVersion(),workspace,python,frontend,skill:'.agents/skills/nbtcreator-workspace/SKILL.md',migration:'shared-engine'}})
 ipcMain.handle('nbt:source',async event=>{allowed(event);const result=await dialog.showOpenDialog(window,{title:'选择完整 NBT 或主模型',properties:['openFile'],filters:[{name:'NBT / Master',extensions:['nbt','gz']}]});return result.canceled?null:result.filePaths[0]})
 ipcMain.handle('nbt:workspace',async event=>{
  allowed(event);const selection=await dialog.showOpenDialog(window,{title:'选择项目根目录或nbt_models（自动识别）',defaultPath:workspace,properties:['openDirectory','createDirectory']})
  if(selection.canceled)return null
  const next=normalizeWorkspace(selection.filePaths[0])
  const response=await dialog.showMessageBox(window,{type:'question',buttons:['切换工作区','取消'],defaultId:1,cancelId:1,message:'切换将结束当前服务及未完成任务。请先保存参数和意见。',detail:'实际项目目录：'+next+'\n建筑目录：'+path.join(next,'nbt_models')+'\n同时同步Skill脚本、数据和知识库。已有目标知识配置保留；新工作区携带当前知识组。'})
  if(response.response!==0)return null
  const currentExposure=await exposure('show')
  const previous=workspace
  await stopBackend();workspace=next
  try{
   await fs.mkdir(path.join(workspace,'nbt_models'),{recursive:true})
   let targetHasConfig=false;try{await fs.access(path.join(workspace,'.nbtcreator/skill-exposure.json'));targetHasConfig=true}catch{}
   await exposure('apply',targetHasConfig?undefined:{schema_version:1,enabled_groups:currentExposure.enabled_groups})
   await recordConfig();await startBackend();await window.loadURL(serverUrl);return workspace
  }catch(error){workspace=previous;await startBackend();await window.loadURL(serverUrl);throw error}
 })
 Menu.setApplicationMenu(Menu.buildFromTemplate([{label:'项目',submenu:[{label:'选择工作区…',click:()=>window.webContents.executeJavaScript('window.nbtDesktop.chooseWorkspace()')},{type:'separator'},{role:'quit'}]},{label:'视图',submenu:[{role:'reload'},{role:'toggleDevTools'},{type:'separator'},{role:'resetZoom'},{role:'zoomIn'},{role:'zoomOut'},{role:'togglefullscreen'}]}]))
 await window.loadURL(serverUrl);window.setTitle('NBTCreator · NBT 建筑工作台');window.show()
}
app.on('before-quit',event=>{if(!closing){event.preventDefault();closing=true;stopBackend().finally(()=>app.quit())}})
app.on('window-all-closed',()=>app.quit())
app.whenReady().then(boot).catch(error=>{console.error(error.stack||error.message);if(!process.env.NBTCREATOR_AUTOMATION)dialog.showErrorBox('NBTCreator 启动失败',error.stack||error.message);app.quit()})
