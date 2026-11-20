import {spawnSync} from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import {root,skill,python} from './paths.mjs'

function launchError(error,workspace){
 if(error.code!=='ENOENT'&&error.code!=='ENOTDIR')return error.message
 // A missing cwd and a missing executable can both be reported as ENOENT.
 try{
  if(!fs.statSync(workspace).isDirectory())return `工作区路径 ${workspace} 不是目录。请传入已有目录。`
 }catch(problem){
  if(problem.code==='ENOENT')return `工作区目录 ${workspace} 不存在。请先创建该目录，或传入已有目录。`
  if(problem.code==='ENOTDIR')return `工作区路径 ${workspace} 中有一部分不是目录。请传入已有目录。`
  return `无法访问工作区目录 ${workspace}（${problem.code}）。`
 }
 return error.code==='ENOENT'?'Python 不可用。请检查 PATH 或 NBTCREATOR_PYTHON，再运行 doctor。':error.message
}

const input=process.argv.slice(2)
let cliWorkspace=process.cwd()
if(input[0]==='--workspace'){input.shift();const folder=input.shift();if(!folder)throw Error('--workspace requires a directory');cliWorkspace=path.resolve(folder)}
let [command,...args]=input
const {commands:scripts,command_prefixes:prefixes={},command_aliases:aliases={}}=JSON.parse(fs.readFileSync(path.join(skill,'tool-catalog.json'),'utf8'))
if(Object.hasOwn(aliases,command)){
 const [target,...prefix]=aliases[command]
 command=target
 args=[...prefix,...args]
}
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
}else if(Object.hasOwn(scripts,command)){
 const script=path.join(skill,'scripts',scripts[command])
 const pass=[...(prefixes[command]??[]),...args]
 const run=spawnSync(python,['-B',script,...pass],{cwd:cliWorkspace,stdio:'inherit',windowsHide:true,shell:false})
 if(run.error)console.error(launchError(run.error,cliWorkspace))
 process.exitCode=run.status??1
}else{
 if(command&&!['-h','--help'].includes(command)){
  console.error(`未知命令 ${command}。用 --help 查看命令，或用 capabilities --routes 速查入口。`)
  process.exitCode=1
 }else{
  console.log('Usage: nbt [--workspace <directory>] <command> [options]')
  console.log('Commands: '+['doctor',...Object.keys(scripts),...Object.keys(aliases)].join(' | '))
  console.log('用 capabilities --routes 速查入口，用 <命令> --help 查看参数。')
 }
}
