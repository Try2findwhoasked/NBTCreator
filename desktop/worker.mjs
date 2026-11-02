import path from 'node:path'
import {pathToFileURL,fileURLToPath} from 'node:url'
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..')
const {startDetailServer}=await import(pathToFileURL(path.join(root,'.agents/skills/minecraft-nbt-modeler/assets/viewer/detail-server.mjs')).href)
let server
process.parentPort.on('message',async({data})=>{
 try{
  if(data.type==='start'){
   server=await startDetailServer({workspace:data.workspace,output:data.output,python:data.python,port:0})
   process.parentPort.postMessage({type:'ready',url:server.url})
  }else if(data.type==='stop'){
   await server?.close();process.parentPort.postMessage({type:'stopped'});process.exit(0)
  }
 }catch(error){process.parentPort.postMessage({type:'error',error:error.stack||error.message})}
})
