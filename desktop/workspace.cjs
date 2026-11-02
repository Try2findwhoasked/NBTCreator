const path=require('node:path')
function normalizeWorkspace(folder){
 let current=path.resolve(folder),result=current
 while(true){if(path.basename(current).toLowerCase()==='nbt_models')result=path.dirname(current);const parent=path.dirname(current);if(parent===current)break;current=parent}
 return result
}
function selectWorkspace({explicit,environment,agentCwd,cwd,root,packaged,executable,config={},settingsDirectory,systemDirectory}){
 const source=agentCwd||cwd
 const forbidden=[packaged?root:null,packaged?path.dirname(executable):null,systemDirectory].filter(Boolean).map(p=>path.resolve(p).toLowerCase())
 const usable=p=>p&&path.isAbsolute(p)&&!forbidden.some(f=>path.resolve(p).toLowerCase()===f||path.resolve(p).toLowerCase().startsWith(f+path.sep))
 if(explicit||environment)return normalizeWorkspace(path.resolve(source||cwd,explicit||environment))
 if(agentCwd&&usable(agentCwd))return normalizeWorkspace(agentCwd)
 const remembered=config.workspace?(config.path_base==='settings'?path.resolve(settingsDirectory,config.workspace):path.resolve(config.workspace)):null
 if(config.workspace_source==='manual'&&usable(remembered))return normalizeWorkspace(remembered)
 if(usable(source))return normalizeWorkspace(source)
 return packaged?null:path.resolve(root)
}
module.exports={selectWorkspace,normalizeWorkspace}
