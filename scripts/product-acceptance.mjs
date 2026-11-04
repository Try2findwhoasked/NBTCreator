import fs from 'node:fs/promises'
import path from 'node:path'
import {spawn,execFileSync} from 'node:child_process'
import {createHash} from 'node:crypto'
import {root,python} from './paths.mjs'

const argv=process.argv.slice(2),option=(name,fallback)=>{const i=argv.indexOf(name);return i<0?fallback:argv[i+1]}
if(!option('--directory'))throw Error('Usage: npm run test:product -- --directory dist/<full-directory> [--workspace <project>] [--jobs 1|2]')
const directory=path.resolve(root,option('--directory')),workspace=path.resolve(root,option('--workspace',root))
const jobs=Number(option('--jobs','2'));if(![1,2].includes(jobs))throw Error('Use one or two simultaneous suites')
const output=path.resolve(root,option('--out','build/product-acceptance-'+Date.now()))
await fs.mkdir(output,{recursive:true})
const app=path.join(directory,'NBTCreator-win32-x64'),executable=path.join(app,'NBTCreator.exe')
await fs.access(executable)
const plan=JSON.parse(await fs.readFile(path.join(root,'config/product-acceptance.json'),'utf8'))
const suites=[{id:'private-runtime',runtime:'node',args:['tests/portable-smoke.mjs','--directory',directory]},...plan.suites]
const ids=new Set(suites.map(s=>s.id));if(ids.size!==suites.length)throw Error('Duplicate suite identifier')
for(const requirement of plan.requirements)for(const id of requirement.suites)if(!ids.has(id))throw Error('Missing suite '+id)
const digest=bytes=>createHash('sha256').update(bytes).digest('hex')
const tracked=execFileSync('git',['ls-files','-z'],{cwd:root,encoding:'utf8'}).split('\0').filter(Boolean)
async function snapshot(){const files={};for(const name of tracked){if(!/^(desktop\/|scripts\/|config\/|tests\/|docs\/|\.agents\/skills\/minecraft-nbt-modeler\/|package(?:-lock)?\.json$|AGENTS\.md$|README\.md$)/.test(name))continue;files[name]=digest(await fs.readFile(path.join(root,name)))}return files}
const before=await snapshot(),commit=execFileSync('git',['rev-parse','HEAD'],{cwd:root,encoding:'utf8'}).trim()
// Verify the executed application contains this implementation, rather than a
// previously green application which happens to share its version number.
const packagedHashes={}
for(const [name,sha]of Object.entries(before))if(name.startsWith('desktop/')||name.startsWith('.agents/skills/minecraft-nbt-modeler/')){
 const packaged=path.join(app,'resources/app',name)
 const actual=digest(await fs.readFile(packaged));if(actual!==sha)throw Error('Packaged source differs: '+name)
 packagedHashes[name]=actual
}
const sourceManifest=path.join(root,'.agents/skills/minecraft-nbt-modeler/assets/viewer/web-dist/frontend-manifest.json')
const packagedManifest=path.join(app,'resources/app/.agents/skills/minecraft-nbt-modeler/assets/viewer/web-dist/frontend-manifest.json')
if(digest(await fs.readFile(sourceManifest))!==digest(await fs.readFile(packagedManifest)))throw Error('Frontend build differs from packaged application')
const report={schema_version:1,passed:false,commit,started_utc:new Date().toISOString(),directory,workspace,source_sha256:before,packaged_source_sha256:packagedHashes,external_api_used:false,actual_user_visual_approval:false,suites:[],requirements:[]}
const records=new Map(),active=new Map();let cursor=0
async function persist(){const temp=path.join(output,'progress.tmp');await fs.writeFile(temp,JSON.stringify({...report,active:[...active.values()]},null,2));await fs.rename(temp,path.join(output,'progress.json'))}
let writes=Promise.resolve();function progress(){writes=writes.then(persist);return writes}
async function run(suite){
 const args=suite.args.map(a=>a.replaceAll('{output}',output).replaceAll('{workspace}',workspace))
 const executablePath=suite.runtime==='python'?python:process.execPath
 const file=path.join(output,suite.id+'.log'),handle=await fs.open(file,'w')
 const started=Date.now(),env={...process.env,NBTCREATOR_AUTOMATION:'1',OPENBLAS_NUM_THREADS:'1',OMP_NUM_THREADS:'1'}
 delete env.ELECTRON_RUN_AS_NODE;if(suite.desktop)env.NBTCREATOR_TEST_EXE=executable
 const record={id:suite.id,status:'running',args,runtime:suite.runtime,log:file,started_utc:new Date().toISOString()}
 report.suites.push(record);records.set(suite.id,record)
 const child=spawn(executablePath,args,{cwd:root,env,windowsHide:true,shell:false})
 active.set(suite.id,{id:suite.id,pid:child.pid,started_utc:record.started_utc})
 let buffer='',timedOut=false,spawnError=null,logWrites=Promise.resolve()
 const append=chunk=>{const text=chunk.toString();buffer=(buffer+text).slice(-4*1024*1024);logWrites=logWrites.then(()=>handle.write(text))}
 child.stdout.on('data',append);child.stderr.on('data',append)
 const timeout=setTimeout(()=>{timedOut=true;if(child.exitCode!==null)return;try{if(process.platform==='win32')execFileSync('taskkill',['/PID',String(child.pid),'/T','/F'],{windowsHide:true,stdio:'ignore'});else child.kill('SIGTERM')}catch(error){spawnError=error.message}},900000)
 const completion=new Promise(resolve=>{child.once('error',error=>{spawnError=error.message;resolve({code:null,signal:null})});child.once('close',(code,signal)=>resolve({code,signal}))})
 console.log(JSON.stringify({event:'started',id:suite.id,pid:child.pid}));await progress()
 const exit=await completion
 clearTimeout(timeout);await logWrites;await handle.close();active.delete(suite.id)
 Object.assign(record,{status:exit.code===0&&!timedOut&&!spawnError?'passed':'failed',exit_code:exit.code,signal:exit.signal,timed_out:timedOut,elapsed_ms:Date.now()-started,...(spawnError?{error:spawnError}:{})})
 if(suite.receipt&&record.status==='passed')try{
  const found=buffer.split(/\r?\n/).flatMap(line=>{try{const value=JSON.parse(line);return value.passed===true&&value.output?[value]:[]}catch{return[]}}).at(-1)
  if(!found)throw Error('No successful evidence receipt in output')
  const receipt=path.join(found.output,'results.json'),data=JSON.parse(await fs.readFile(receipt,'utf8'))
  if(data.passed!==true||Object.values(data.checks??{}).some(value=>value===false))throw Error('Evidence receipt contains a failed check')
  Object.assign(record,{receipt,receipt_sha256:digest(await fs.readFile(receipt)),checks:data.checks})
 }catch(error){record.status='failed';record.error=error.message}
 await progress();console.log(JSON.stringify({event:'finished',id:suite.id,status:record.status,elapsed_ms:record.elapsed_ms,log:file}))
}
async function worker(){while(cursor<suites.length)await run(suites[cursor++])}
await Promise.all(Array.from({length:jobs},worker))
const after=await snapshot();report.changed_inputs=Object.keys(before).filter(name=>before[name]!==after[name]);report.inputs_unchanged=!report.changed_inputs.length
report.requirements=plan.requirements.map(requirement=>({...requirement,passed:requirement.suites.every(id=>records.get(id)?.status==='passed')}))
report.passed=report.inputs_unchanged&&report.requirements.every(r=>r.passed)&&report.suites.every(s=>s.status==='passed')
report.finished_utc=new Date().toISOString();await writes
await fs.writeFile(path.join(output,'results.json'),JSON.stringify(report,null,2))
console.log(JSON.stringify({passed:report.passed,suites:report.suites.length,failed:report.suites.filter(s=>s.status!=='passed').map(s=>s.id),requirements:report.requirements.length,output}))
process.exitCode=report.passed?0:1
