import fs from 'node:fs/promises'
import path from 'node:path'
import {randomUUID} from 'node:crypto'

const kinds=new Set(['components','effects','patterns'])
const empty=()=>({revision:0,groups:[],assignments:{}})
export function validateAssetGroups(value){
 if(!value||typeof value!=='object'||Array.isArray(value)||Object.keys(value).some(key=>!['revision','groups','assignments'].includes(key))||!Number.isSafeInteger(value.revision)||value.revision<0||!Array.isArray(value.groups)||value.groups.length>200||!value.assignments||typeof value.assignments!=='object'||Array.isArray(value.assignments)||Object.keys(value.assignments).length>10000)throw Error('素材分组配置无效')
 const ids=new Set(),names=new Set()
 for(const group of value.groups){if(!group||Object.keys(group).some(key=>!['id','kind','name'].includes(key))||typeof group.id!=='string'||!/^[a-f0-9-]{36}$/.test(group.id)||!kinds.has(group.kind)||typeof group.name!=='string'||!group.name.trim()||group.name.length>60||ids.has(group.id)||names.has(group.kind+':'+group.name.trim()))throw Error('素材分组名称无效或重复');ids.add(group.id);names.add(group.kind+':'+group.name.trim())}
 for(const [key,id]of Object.entries(value.assignments)){const colon=key.indexOf(':');if(colon<0||!kinds.has(key.slice(0,colon))||key.length>2048||/[\x00-\x1f]/.test(key)||typeof id!=='string'||!ids.has(id)||value.groups.find(group=>group.id===id)?.kind!==key.slice(0,colon))throw Error('素材归组记录无效')}
 return value
}
export function createAssetGroups(workspace){
 const file=path.join(workspace,'.nbtcreator/asset-groups.json');let queue=Promise.resolve()
 async function read(){try{return validateAssetGroups(JSON.parse(await fs.readFile(file,'utf8')))}catch(error){if(error.code==='ENOENT')return empty();throw error}}
 function save(input){const action=queue.catch(()=>{}).then(async()=>{const previous=await read(),next=validateAssetGroups(input);if(next.revision!==previous.revision)throw Error('素材分组已变化，请刷新后重试');const value={...next,revision:previous.revision+1};await fs.mkdir(path.dirname(file),{recursive:true});const temporary=file+'.'+randomUUID()+'.tmp';await fs.writeFile(temporary,JSON.stringify(value,null,2));await fs.rename(temporary,file);return value});queue=action;return action}
 return {read,save}
}
