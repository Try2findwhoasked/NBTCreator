const fs=require('node:fs'),path=require('node:path')
process.env.PYTHONUTF8='1'
process.env.PYTHONIOENCODING='utf-8'
function resolvePython(root,override=process.env.NBTCREATOR_PYTHON){
 if(override)return override
 const bundled=path.join(root,'runtime','python','python.exe')
 return fs.existsSync(bundled)?bundled:'python'
}
function configureRenderRuntime(root,nodeExecutable){
 if(nodeExecutable&&!process.env.NBTCREATOR_NODE){process.env.NBTCREATOR_NODE=nodeExecutable;process.env.NBTCREATOR_NODE_IS_ELECTRON='1'}
 const browser=path.join(root,'runtime','browser','chrome.exe')
 if(!process.env.NBTCREATOR_BROWSER&&fs.existsSync(browser))process.env.NBTCREATOR_BROWSER=browser
}
module.exports={resolvePython,configureRenderRuntime}
