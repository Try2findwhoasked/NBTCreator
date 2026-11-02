import fs from 'node:fs/promises'
import {createHash} from 'node:crypto'
import path from 'node:path'
import {execFileSync} from 'node:child_process'
import {createRequire} from 'node:module'
import {root,skill,python} from './paths.mjs'
if(process.platform!=='win32'||process.arch!=='x64')throw Error('Build portable on Windows x64')
const index=process.argv.indexOf('--out'),out=path.resolve(root,index<0?'dist/portable':process.argv[index+1])
const version=JSON.parse(await fs.readFile(path.join(root,'package.json'),'utf8')).version
execFileSync(process.execPath,[path.join(root,'scripts/package.mjs'),'--out',out],{stdio:'inherit'})
const app=path.join(out,'NBTCreator-win32-x64'),appRoot=path.join(app,'resources/app')
execFileSync(python,[path.join(root,'scripts/vendor-python.py'),'--destination',path.join(appRoot,'runtime/python'),'--cache',path.join(root,'build/downloads')],{stdio:'inherit'})
const require=createRequire(path.join(skill,'assets/viewer/package.json'))
const cli=path.join(path.dirname(require.resolve('playwright/package.json')),'cli.js')
const env={...process.env,PLAYWRIGHT_BROWSERS_PATH:path.join(root,'build/portable-browser')}
execFileSync(process.execPath,[cli,'install','chromium','--no-shell'],{env,stdio:'inherit'})
const browser=execFileSync(process.execPath,['-e',"console.log(require(process.argv[1]).chromium.executablePath())",require.resolve('playwright')],{env,encoding:'utf8'}).trim()
await fs.cp(path.dirname(browser),path.join(appRoot,'runtime/browser'),{recursive:true,errorOnExist:true,force:false})
const lock=JSON.parse(await fs.readFile(path.join(root,'config/portable-runtime.json'),'utf8'))
const runtimeId=createHash('sha256').update(JSON.stringify({lock,electron:JSON.parse(await fs.readFile(path.join(root,'package.json'),'utf8')).devDependencies.electron,playwright:JSON.parse(await fs.readFile(require.resolve('playwright/package.json'),'utf8')).version})).digest('hex').slice(0,16)
await fs.writeFile(path.join(app,'runtime-info.json'),JSON.stringify({runtime_id:runtimeId},null,2))
await fs.writeFile(path.join(app,'portable-info.json'),JSON.stringify({version,runtime_id:runtimeId,platform:'win32',arch:'x64',python:lock.python.version,packages:lock.wheels.map(({name,version})=>({name,version})),browser:'Playwright pinned Chromium',node:'Electron built-in Node',commit:process.env.GITHUB_SHA??execFileSync('git',['rev-parse','HEAD'],{encoding:'utf8'}).trim()},null,2)+'\n')
await fs.writeFile(path.join(app,'NBT工具.cmd'),'@echo off\r\nsetlocal\r\nset ELECTRON_RUN_AS_NODE=1\r\n"%~dp0NBTCreator.exe" "%~dp0resources\\app\\scripts\\cli.mjs" %*\r\nexit /b %errorlevel%\r\n')
await fs.writeFile(path.join(app,'Portable说明.txt'),'NBTCreator '+version+' Windows x64 Portable\r\n\r\n解压完整文件夹后运行 NBTCreator.exe，无需安装 Python、Node 或浏览器。\r\n首次启动选择 Agent 项目根目录，建筑与 Skill 保存在该工作区；API 配置保存在当前 Windows 用户配置目录。\r\n请保留 resources、runtime 和 .agents 文件，勿只复制 exe。\r\n无界面调用可使用 NBT工具.cmd，例如 NBT工具.cmd capabilities。\r\n这是免安装目录包；完整批量渲染使用包内 Chromium。\r\n')
const archive=path.join(out,`NBTCreator-${version}-windows-x64-portable.zip`)
execFileSync(python,[path.join(root,'scripts/portable-archive.py'),'pack','--source',app,'--output',archive],{stdio:'inherit'})

for(const kind of ['application','runtime']){
 const suffix=kind==='application'?'app-update':'runtime'
 execFileSync(python,[path.join(root,'scripts/portable-archive.py'),'pack','--source',app,'--kind',kind,'--output',path.join(out,`NBTCreator-${version}-windows-x64-${suffix}.zip`)],{stdio:'inherit'})
}
