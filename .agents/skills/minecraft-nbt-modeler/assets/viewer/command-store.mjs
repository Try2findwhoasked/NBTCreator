import fs from 'node:fs/promises'
import path from 'node:path'
import net from 'node:net'
import {createHash,randomUUID} from 'node:crypto'
import {commandDefinitions,defaultPreferences,validateCommandPreferences} from './src/command-contract.mjs'

export function createCommandStore(workspace,catalog){
 const file=path.resolve(workspace,'.nbtcreator/commands.json'),commands=commandDefinitions(catalog),canonical=fs.realpath(workspace).catch(()=>path.resolve(workspace));let writing=Promise.resolve()
 async function read(){
  try{if((await fs.stat(file)).size>64*1024)throw Error('命令配置文件过大');const value=JSON.parse(await fs.readFile(file,'utf8'));if(value.schema_version!==1||!Number.isSafeInteger(value.revision)||value.revision<0)throw Error('命令配置版本无效');return {...value,preferences:validateCommandPreferences(value.preferences,commands)}}catch(error){if(error.code!=='ENOENT')throw error;return {schema_version:1,revision:0,preferences:defaultPreferences()}}
 }
 async function lock(action){
  if(process.platform!=='win32')return action()
  const address='\\\\.\\pipe\\nbtcreator-commands-'+createHash('sha256').update((await canonical).toLowerCase()).digest('hex'),deadline=Date.now()+2500;let server
  for(;;){server=net.createServer(socket=>socket.destroy());try{await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(address,resolve)});break}catch(error){if(error.code!=='EADDRINUSE')throw error;if(Date.now()>deadline)throw Error('另一窗口正在保存命令配置，请稍后重试');await new Promise(resolve=>setTimeout(resolve,20))}}
  try{return await action()}finally{await new Promise(resolve=>server.close(resolve))}
 }
 function save(input){
  const next=writing.catch(()=>{}).then(()=>lock(async()=>{
   if(!input||Object.keys(input).some(k=>!['expected_revision','preferences'].includes(k))||!Number.isSafeInteger(input.expected_revision)||input.expected_revision<0)throw Error('命令配置请求无效')
   const preferences=validateCommandPreferences(input.preferences,commands),current=await read();if(current.revision!==input.expected_revision)throw Error('命令配置已由另一窗口修改，请重新读取后再保存')
   const value={schema_version:1,revision:current.revision+1,preferences};await fs.mkdir(path.dirname(file),{recursive:true});const temporary=file+'.'+randomUUID()+'.tmp';await fs.writeFile(temporary,JSON.stringify(value,null,2));await fs.rename(temporary,file);return value
  }));writing=next;return next
 }
 return {read,save}
}
