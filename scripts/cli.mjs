import {spawnSync} from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import {root,skill,python} from './paths.mjs'
const input=process.argv.slice(2)
let cliWorkspace=process.cwd()
if(input[0]==='--workspace'){input.shift();const folder=input.shift();if(!folder)throw Error('--workspace requires a directory');cliWorkspace=path.resolve(folder)}
const [command,...args]=input
const scripts=JSON.parse(fs.readFileSync(path.join(skill,'tool-catalog.json'),'utf8')).commands
if(command==='doctor'){
 const run=spawnSync(python,['-c','import sys,numpy,PIL,json;print(json.dumps({"python":sys.executable,"version":sys.version,"numpy":numpy.__version__,"pillow":PIL.__version__}))'],{encoding:'utf8',windowsHide:true})
 const dependencies=fs.existsSync(path.join(skill,'assets/viewer/node_modules/vite'))
 console.log(JSON.stringify({ok:run.status===0&&dependencies,node:process.version,skill,viewer_dependencies:dependencies,python:run.status===0?JSON.parse(run.stdout):null,error:run.error?.message||run.stderr||null},null,2))
 process.exitCode=run.status===0&&dependencies?0:1
}else if(scripts[command]){
 const script=path.join(skill,'scripts',scripts[command])
 const pass=['inspect','snapshot','render','regress'].includes(command)?[command,...args]:args
 const run=spawnSync(python,['-B',script,...pass],{cwd:cliWorkspace,stdio:'inherit',windowsHide:true,shell:false})
 if(run.error)console.error(run.error.message)
 process.exitCode=run.status??1
}else{
 console.log('NBTCreator CLI: doctor | capabilities | '+Object.keys(scripts).join(' | '))
 console.log('Examples: node scripts/cli.mjs inspect --source full.master.json.gz; control --help; refine --help')
 process.exitCode=command?1:0
}
