const fs=require('node:fs/promises')
const path=require('node:path')

// Only registered, freshly verified IDs cross IPC; script files are revealed, never executed.
async function openBatchLink({workspace,input,locate,shell,simulate=false}){
 if(!input||typeof input!=='object'||Object.keys(input).some(key=>!['id','kind','item_id','mode'].includes(key)))throw Error('无效批次入口')
 if(!/^[a-f0-9]{32}$/.test(input.id)||!['workspace','model','artifact'].includes(input.kind)||!['open','reveal'].includes(input.mode||'open')||input.kind!=='workspace'&&!/^[a-f0-9]{32}$/.test(input.item_id))throw Error('无效批次或产物编号')
 const result=await locate({id:input.id,kind:input.kind,item_id:input.item_id})
 const base=await fs.realpath(path.join(workspace,'nbt_models')),file=await fs.realpath(result.path),relative=path.relative(base,file)
 if(!relative||relative==='..'||relative.startsWith('..'+path.sep)||path.isAbsolute(relative))throw Error('批次产物不在当前建筑库内')
 const stat=await fs.stat(file),directory=input.kind==='workspace'
 if(directory?!stat.isDirectory():!stat.isFile())throw Error('批次产物类型已变化')
 const permitted=new Set(['.html','.htm','.png','.jpg','.jpeg','.webp','.pdf','.zip'])
 const action=input.mode==='reveal'||!directory&&!permitted.has(path.extname(file).toLowerCase())?'reveal':'open'
 if(!simulate){if(action==='reveal')shell.showItemInFolder(file);else{const error=await shell.openPath(file);if(error)throw Error(error)}}
 return {path:file,action}
}
module.exports={openBatchLink}
