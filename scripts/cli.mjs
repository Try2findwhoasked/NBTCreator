import {spawnSync} from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import {root,skill,python} from './paths.mjs'
const input=process.argv.slice(2)
let cliWorkspace=process.cwd()
if(input[0]==='--workspace'){input.shift();const folder=input.shift();if(!folder)throw Error('--workspace requires a directory');cliWorkspace=path.resolve(folder)}
let [command,...args]=input
if(command==='task'){
 command='prompts'
 args=['task',...args]
}
const scripts=JSON.parse(fs.readFileSync(path.join(skill,'tool-catalog.json'),'utf8')).commands
if(command==='doctor'){
 const run=spawnSync(python,['-c','import sys,numpy,PIL,nbtlib,json;print(json.dumps({"python":sys.executable,"version":sys.version,"numpy":numpy.__version__,"pillow":PIL.__version__,"nbtlib":nbtlib.__version__}))'],{encoding:'utf8',windowsHide:true,timeout:15000})
 const git=spawnSync(process.env.NBTCREATOR_GIT||'git',['--version'],{encoding:'utf8',windowsHide:true,timeout:15000})
 const dependencies=fs.existsSync(path.join(skill,'assets/viewer/web-dist/frontend-manifest.json'))||
   fs.existsSync(path.join(skill,'assets/viewer/node_modules/vite'))
 const hints=[]
 if(run.status!==0)hints.push(`请检查 PATH 或 NBTCREATOR_PYTHON，并为该解释器安装依赖：python -m pip install -r "${path.join(skill,'requirements.txt')}"`)
 if(git.status!==0)hints.push('请检查 PATH 或 NBTCREATOR_GIT')
 if(!dependencies)hints.push('缺少预构建前端或源码开发依赖')
 console.log(JSON.stringify({ok:!hints.length,node:process.version,skill,viewer_dependencies:dependencies,
   python:run.status===0?JSON.parse(run.stdout):null,git:git.status===0?git.stdout.trim():null,
   error:run.error?.message||run.stderr?.trim()||git.error?.message||git.stderr?.trim()||null,hints},null,2))
 process.exitCode=hints.length?1:0
}else if(scripts[command]){
 const script=path.join(skill,'scripts',scripts[command])
 const pass=['inspect','snapshot','render','regress'].includes(command)?[command,...args]:args
 const run=spawnSync(python,['-B',script,...pass],{cwd:cliWorkspace,stdio:'inherit',windowsHide:true,shell:false})
 if(run.error)console.error(run.error.code==='ENOENT'?'Python 不可用。请检查 PATH 或 NBTCREATOR_PYTHON，再运行 doctor。':run.error.message)
 process.exitCode=run.status??1
}else{
 console.log('NBTCreator CLI: doctor | task | capabilities | '+Object.keys(scripts).join(' | '))
 console.log('Examples: node scripts/cli.mjs inspect --source full.master.json.gz; control --help; refine --help')
 process.exitCode=command?1:0
}
