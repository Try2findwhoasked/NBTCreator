// Local-only acceptance: mock HTTP, actual Electron/Python, exported Agent CLI.
import fs from 'node:fs/promises'
import path from 'node:path'
import {spawn,execFileSync} from 'node:child_process'
import {createHash} from 'node:crypto'
import {root} from './paths.mjs'
const option=name=>{const index=process.argv.indexOf(name);return index<0?null:process.argv[index+1]}
const directory=option('--directory'),output=path.join(root,'build','agent-acceptance-'+Date.now()),executable=directory?path.resolve(root,directory,'NBTCreator-win32-x64/NBTCreator.exe'):null
await fs.mkdir(output,{recursive:true});if(executable)await fs.access(executable)
const report={passed:false,external_api_used:false,commit:execFileSync('git',['rev-parse','HEAD'],{cwd:root,encoding:'utf8'}).trim(),executable,started_at:new Date().toISOString(),suites:[]}
const sha=bytes=>createHash('sha256').update(bytes).digest('hex')
if(executable){
 const files=execFileSync('git',['ls-files','-z','desktop','.agents/skills/minecraft-nbt-modeler'],{cwd:root,encoding:'utf8'}).split('\0').filter(Boolean)
 for(const name of files)assertSame(sha(await fs.readFile(path.join(root,name))),sha(await fs.readFile(path.join(path.dirname(executable),'resources/app',name))),name)
 report.packaged_sources_verified=files.length
}
function assertSame(a,b,label){if(a!==b)throw Error('目录包与当前实现不同：'+label)}
const persist=()=>fs.writeFile(path.join(output,'results.json'),JSON.stringify(report,null,2))
async function run(id,args){
 const started=Date.now(),log=path.join(output,id+'.log'),stream=await fs.open(log,'w'),env={...process.env,NBTCREATOR_AUTOMATION:'1',OPENBLAS_NUM_THREADS:'1',OMP_NUM_THREADS:'1'};delete env.ELECTRON_RUN_AS_NODE
 if(executable)env.NBTCREATOR_TEST_EXE=executable
 const entry={id,status:'running',log};report.suites.push(entry);await persist()
 const child=spawn(process.execPath,args,{cwd:root,env,windowsHide:true,shell:false});let text='',writes=Promise.resolve(),timedOut=false
 const append=chunk=>{text+=chunk.toString();writes=writes.then(()=>stream.write(chunk))};child.stdout.on('data',append);child.stderr.on('data',append)
 const timer=setTimeout(()=>{timedOut=true;if(child.exitCode===null)try{execFileSync('taskkill',['/PID',String(child.pid),'/T','/F'],{windowsHide:true,stdio:'ignore'})}catch{}},300000)
 const exit=await new Promise(resolve=>{child.on('error',error=>resolve({error:error.message}));child.on('close',(code,signal)=>resolve({code,signal}))});clearTimeout(timer);await writes;await stream.close()
 Object.assign(entry,{...exit,status:!timedOut&&exit.code===0?'passed':'failed',elapsed_ms:Date.now()-started,timed_out:timedOut})
 const summary=text.trim().split(/\r?\n/).reverse().find(line=>line.startsWith('{')&&line.includes('"passed"'))
 if(summary)try{entry.result=JSON.parse(summary)}catch{}
 await persist();console.log(JSON.stringify({suite:id,status:entry.status,elapsed_ms:entry.elapsed_ms,output:entry.result?.output}))
 if(entry.status!=='passed')throw Error('模拟验收失败：'+id+'，详见 '+log)
}
try{
 await run('build',['scripts/build-web.mjs'])
 const pkg=JSON.parse(await fs.readFile(path.join(root,'package.json'),'utf8'));await run('protocols',pkg.scripts['test:api'].split(' ').slice(1))
 for(const [id,file] of [['outputs','agent-simulation-desktop.mjs'],['adoption','api-desktop.mjs'],['selection','selection-edit-desktop.mjs'],['assets','structure-agent-desktop.mjs'],['desktop','desktop-smoke.mjs']])await run(id,['tests/'+file])
 if(directory)await run('private-runtime',['tests/portable-smoke.mjs','--directory',directory])
 report.passed=true;report.completed_at=new Date().toISOString();await persist();console.log(JSON.stringify({passed:true,suites:report.suites.length,external_api_used:false,output}))
}catch(error){report.error=error.message;await persist();throw error}
