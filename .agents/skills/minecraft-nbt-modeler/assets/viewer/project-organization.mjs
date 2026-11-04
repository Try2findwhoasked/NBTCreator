import fs from 'node:fs/promises'
import path from 'node:path'
import {randomUUID} from 'node:crypto'
const empty=()=>({revision:0,menus:[],assignments:{}})
export function validateOrganization(data){
 if(!data||typeof data!=='object'||Object.keys(data).some(k=>!['revision','menus','assignments'].includes(k))||!Number.isSafeInteger(data.revision)||data.revision<0||!Array.isArray(data.menus)||data.menus.length>100||!data.assignments||typeof data.assignments!=='object'||Array.isArray(data.assignments)||Object.keys(data.assignments).length>10000)throw Error('菜单配置无效')
 const ids=new Set(),names=new Set()
 for(const menu of data.menus){if(!menu||Object.keys(menu).some(k=>!['id','name'].includes(k))||typeof menu.id!=='string'||!/^[a-f0-9-]{36}$/.test(menu.id)||typeof menu.name!=='string'||!menu.name.trim()||menu.name.length>60||ids.has(menu.id)||names.has(menu.name.trim()))throw Error('菜单名称须为1～60字，且不能重名');ids.add(menu.id);names.add(menu.name.trim())}
 for(const [key,value]of Object.entries(data.assignments)){if(!/^(model|effect):[^:]{1,2048}$/.test(key)||key.includes('..')||!value||Object.keys(value).some(k=>!['kind','menu'].includes(k))||!['auto','building','effect'].includes(value.kind)||typeof value.menu!=='string'||value.menu&&!ids.has(value.menu))throw Error('菜单条目配置无效')}
 return data
}
export function createProjectOrganization(workspace){
 const file=path.join(workspace,'.nbtcreator/project-organization.json');let queue=Promise.resolve()
 async function read(){try{return validateOrganization(JSON.parse(await fs.readFile(file,'utf8')))}catch(e){if(e.code==='ENOENT')return empty();throw e}}
 function save(input){const action=queue.catch(()=>{}).then(async()=>{const current=await read(),next=validateOrganization(input);if(next.revision!==current.revision)throw Error('菜单配置已变化，请刷新后重试');const value={...next,revision:current.revision+1};await fs.mkdir(path.dirname(file),{recursive:true});const temp=file+'.'+randomUUID()+'.tmp';await fs.writeFile(temp,JSON.stringify(value,null,2));await fs.rename(temp,file);return value});queue=action;return action}
 return {read,save}
}
