import fs from 'node:fs/promises'
import path from 'node:path'
import {createRequire} from 'node:module'
import {pathToFileURL} from 'node:url'
import {createHash} from 'node:crypto'
import {skill} from './paths.mjs'
export async function buildWeb(){
 const viewer=path.join(skill,'assets/viewer'),require=createRequire(path.join(viewer,'package.json'))
 const {build}=await import(pathToFileURL(require.resolve('vite')).href)
 const output=path.join(viewer,'web-dist')
 await build({root:viewer,configFile:false,logLevel:'warn',base:'/',build:{outDir:output,emptyOutDir:true,sourcemap:false,rolldownOptions:{input:{viewer:path.join(viewer,'index.html'),control:path.join(viewer,'control.html')}}}})
 const lodestone=path.resolve(path.dirname(require.resolve('@mattzh72/lodestone')),'..')
 await fs.cp(path.join(lodestone,'assets/default-pack'),path.join(output,'default-pack'),{recursive:true})
 const manifest={schema_version:1,entries:['index.html','control.html'],files:[]}
 async function walk(folder){for(const item of await fs.readdir(folder,{withFileTypes:true})){const file=path.join(folder,item.name);if(item.isDirectory())await walk(file);else{const bytes=await fs.readFile(file);manifest.files.push({path:path.relative(output,file).split(path.sep).join('/'),bytes:bytes.length,sha256:createHash('sha256').update(bytes).digest('hex')})}}}
 await walk(output);await fs.writeFile(path.join(output,'frontend-manifest.json'),JSON.stringify(manifest,null,2))
 console.log(JSON.stringify({frontend:'production',files:manifest.files.length,bytes:manifest.files.reduce((n,f)=>n+f.bytes,0)}))
 return output
}
if(process.argv[1]&&import.meta.url===pathToFileURL(path.resolve(process.argv[1])).href)await buildWeb()
