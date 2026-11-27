const {contextBridge,ipcRenderer}=require('electron')
contextBridge.exposeInMainWorld('nbtDesktop',Object.freeze({
  mcp: Object.freeze({
    status:()=>ipcRenderer.invoke('nbt:mcp-status'),
    listTools:()=>ipcRenderer.invoke('nbt:mcp-list'),
    callTool:input=>ipcRenderer.invoke('nbt:mcp-call',input),
    cancel:requestId=>ipcRenderer.invoke('nbt:mcp-cancel',requestId),
    readArtifact:uri=>ipcRenderer.invoke('nbt:mcp-artifact',uri),
    onStatus:callback=>{
      if(typeof callback!=='function')throw TypeError('MCP status listener must be a function')
      const listener=(_event,status)=>callback(status)
      ipcRenderer.on('nbt:mcp-status-event',listener)
      return ()=>ipcRenderer.removeListener('nbt:mcp-status-event',listener)
    }
  }),
  internalAIConfig:()=>ipcRenderer.invoke('nbt:internal-ai-config'),
  internalAISave:input=>ipcRenderer.invoke('nbt:internal-ai-save',input),
  internalAIImport:()=>ipcRenderer.invoke('nbt:internal-ai-import'),
  knowledgePreview:input=>ipcRenderer.invoke('nbt:knowledge-preview',input),
  chooseReferenceLibrary:()=>ipcRenderer.invoke('nbt:select-reference-library'),
  batchOpen:input=>ipcRenderer.invoke('nbt:batch-open',input),
  settingsOpenFolder:kind=>ipcRenderer.invoke('nbt:settings-open-folder',kind),
  appSettings:()=>ipcRenderer.invoke('nbt:app-settings'),
  appSettingsSave:input=>ipcRenderer.invoke('nbt:app-settings-save',input),
  updateAccess:()=>ipcRenderer.invoke('nbt:update-access'),
  updateAccessSave:input=>ipcRenderer.invoke('nbt:update-access-save',input),
  updateCheck:()=>ipcRenderer.invoke('nbt:update-check'),
  updateDownload:kind=>ipcRenderer.invoke('nbt:update-download',kind),
  updateStatus:()=>ipcRenderer.invoke('nbt:update-status'),
  updateFolder:()=>ipcRenderer.invoke('nbt:update-folder'),
  info:()=>ipcRenderer.invoke('nbt:info'),
  systemMenu:name=>ipcRenderer.invoke('nbt:system-menu',name),
  copyAgentPlan:text=>ipcRenderer.invoke('nbt:copy-agent-plan',text),
  chooseWorkspace:()=>ipcRenderer.invoke('nbt:workspace'),
  migrationSelect:kind=>ipcRenderer.invoke('nbt:migration-select',kind),
  migrationRun:(action,input)=>ipcRenderer.invoke('nbt:migration-run',action,input),
  migrationOpen:()=>ipcRenderer.invoke('nbt:migration-open'),
  chooseSource:()=>ipcRenderer.invoke('nbt:source'),
  apiConfig:()=>ipcRenderer.invoke('nbt:api-config'),
  apiSave:input=>ipcRenderer.invoke('nbt:api-save',input),
  apiModels:()=>ipcRenderer.invoke('nbt:api-models'),
  apiGenerate:(input,options)=>ipcRenderer.invoke('nbt:api-generate',input,options),
  apiCancel:requestId=>ipcRenderer.invoke('nbt:api-cancel',requestId?{requestId}:undefined),
  exposureConfig:()=>ipcRenderer.invoke('nbt:exposure-config'),
  exposureEdit:input=>ipcRenderer.invoke('nbt:exposure-edit',input)
}))
