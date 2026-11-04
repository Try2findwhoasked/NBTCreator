import fs from 'node:fs/promises'
import path from 'node:path'
import {randomUUID} from 'node:crypto'
const milliseconds=value=>typeof value==='string'&&/^\d+$/.test(value)?Number(BigInt(value)/1000000n):Math.trunc(Number(value)/1e6)
export const projectStampMatches=(mark,item)=>mark.bytes===item.file_size&&(mark.modified_ns&&typeof item.modified_ns==='string'?mark.modified_ns===item.modified_ns:mark.modified_ms===milliseconds(item.modified_ns))
export function createProjectStages(workspace){
 const root=path.resolve(workspace,'nbt_models'),file=path.join(workspace,'.nbtcreator/project-stages.json');let writing=Promise.resolve()
 async function read(){try{return JSON.parse(await fs.readFile(file,'utf8'))}catch(error){if(error.code!=='ENOENT')throw error;return {stages:{}}}}
 const key=source=>{const relative=path.relative(root,path.resolve(source));if(path.isAbsolute(relative)||relative==='..'||relative.startsWith('..'+path.sep))throw Error('只能标记当前建筑库的文件');return relative.split(path.sep).join('/')}
 async function apply(catalog){const data=await read();return {...catalog,models:catalog.models.map(item=>{const mark=data.stages[key(item.source)];return mark&&projectStampMatches(mark,item)?{...item,stage_auto:item.stage,stage:mark.stage,stage_manual:true}:item})}}
 function save(source,stage,expected){
  const operation=writing.catch(()=>{}).then(async()=>{
   if(!['auto','unrefined','refined','finalized','discarded'].includes(stage))throw Error('创作状态无效')
   const relative=key(source),stat=await fs.stat(source,{bigint:true}),data=await read(),actual={stage,bytes:Number(stat.size),modified_ms:Number(stat.mtimeNs/1000000n),modified_ns:stat.mtimeNs.toString()}
   if(expected&&(expected.bytes!==actual.bytes||(typeof expected.modified_ns==='string'?expected.modified_ns!==actual.modified_ns:expected.modified_ms!==actual.modified_ms)))throw Error('文件在选中后已变化，请刷新并重新选择')
   if(stage==='auto')delete data.stages[relative];else data.stages[relative]=actual
   await fs.mkdir(path.dirname(file),{recursive:true});const temporary=file+'.'+randomUUID()+'.tmp';await fs.writeFile(temporary,JSON.stringify(data,null,2));await fs.rename(temporary,file)
   return {stage,source}
  });writing=operation;return operation
 }
 return {apply,save}
}
