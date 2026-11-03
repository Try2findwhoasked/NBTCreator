import fs from 'node:fs/promises'
import path from 'node:path'
import {randomUUID} from 'node:crypto'
import {portableRequest,absoluteRequest} from './portable-paths.mjs'

// A cached directory is a browsing aid. Inspect still validates the actual file
// before any model is opened or changed, and every session refreshes the index.
export function createCatalogStore({workspace,scan}){
 const directory=path.join(workspace,'.nbtcreator/cache'),file=path.join(directory,'project-catalog.json')
 let current,pending,writing=Promise.resolve()
 function persist(value){
  const cached={schema_version:1,indexed_at:value.indexed_at,catalog:{...value,workspace:'.',scan_root:'nbt_models',normalized_from:null,models:value.models.map(item=>portableRequest(item,workspace))}}
  writing=writing.catch(()=>{}).then(async()=>{await fs.mkdir(directory,{recursive:true});const temporary=file+'.'+randomUUID()+'.tmp';await fs.writeFile(temporary,JSON.stringify(cached));await fs.rename(temporary,file)})
  return writing
 }
 async function refresh(){
  if(pending)return pending
  pending=(async()=>{
   const value=await scan()
   if(value.migration_in_progress)return value
   const known=new Map((current?.models||[]).map(item=>[item.source,item]))
   value.models=value.models.map(item=>{const previous=known.get(item.source);return item.unverified&&previous&&!previous.unverified&&item.modified_ns===previous.modified_ns&&item.file_size===previous.file_size?{...item,geometry_sha256:previous.geometry_sha256,size:previous.size,unverified:false,unreadable:!!previous.unreadable,...(previous.error?{error:previous.error}:{})}:item})
   current={...value,indexed_at:new Date().toISOString()};await persist(current);return current
  })().finally(()=>{pending=null})
  return pending
 }
 async function initial(){
  if(current)return {catalog:current,cached:true}
  try{
   const value=JSON.parse(await fs.readFile(file,'utf8'))
   if(value.schema_version!==1||!Array.isArray(value.catalog?.models))throw Error('Invalid catalog cache')
   current={...value.catalog,workspace,scan_root:path.join(workspace,'nbt_models'),indexed_at:value.indexed_at,models:value.catalog.models.map(item=>({...absoluteRequest(item,workspace),project_name:item.project_key?item.project_name:path.basename(workspace)}))}
   return {catalog:current,cached:true}
  }catch{ return {catalog:await refresh(),cached:false} }
 }
 async function record(info){
  if(!current?.models.some(item=>item.source===info.source))return
  current={...current,models:current.models.map(item=>item.source===info.source?{...item,geometry_sha256:info.geometry_sha256,size:info.size,unverified:false,unreadable:false}:item)}
  await persist(current)
 }
 async function recordFailure(source,error){if(!current?.models.some(item=>item.source===source))return;current={...current,models:current.models.map(item=>item.source===source?{...item,unverified:false,unreadable:true,error}:item)};await persist(current)}
 return {initial,refresh,record,recordFailure}
}
