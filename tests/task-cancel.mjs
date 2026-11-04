// Cancel real Python work, including plan preflight and non-job service work.
import fs from 'node:fs/promises'
import path from 'node:path'
import {fileURLToPath} from 'node:url'
import {parseArgs} from 'node:util'
import {execFileSync} from 'node:child_process'
import {createHash} from 'node:crypto'
import assert from 'node:assert/strict'
import {startDetailServer} from '../.agents/skills/minecraft-nbt-modeler/assets/viewer/detail-server.mjs'

const {values}=parseArgs({options:{output:{type:'string'},python:{type:'string'}}})
if(!values.output)throw Error('Provide --output new-directory')
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..'),out=path.resolve(values.output),python=values.python??'python'
await fs.mkdir(out)
const workspace=path.join(out,'workspace'),fixture=path.join(workspace,'nbt_models/square/取消测试/v01')
const made=JSON.parse(execFileSync(python,['-B','-c',`
import json,sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from nbt_assembly import Volume
from nbt_model import Model
from nbt_refine import save_master
from nbt_detail_control import default_settings
p=Path(sys.argv[2]);(p/'master').mkdir(parents=True)
m=Volume((144,32,144));stone='minecraft:stone_bricks'
m.blocks={(x,y,z):stone for x in range(144) for y in range(24) for z in range(144)}
m.box((0,31,0),(143,31,143),stone)
m.box((0,24,0),(0,30,143),stone);m.box((143,24,0),(143,30,143),stone)
m.box((0,24,0),(143,30,0),stone);m.box((0,24,143),(143,30,143),stone)
probes=[[24,25,24],[120,25,120]];m.check_sealed(probes)
walls={point for point in m.blocks if point[1]==31 or point[0] in (0,143) or point[2] in (0,143)}
save_master(p/'master/master_geometry.json.gz',m,walls)
context=dict(validation_mode='saodg',cells=[[x,z] for x in range(3) for z in range(3)],door_y=24,ports=[],start=[24.5,24,24.5],targets={'far':[120.5,24,120.5]},interior_probes=probes,cameras=[dict(role='whole',eye=[200,90,200],target=[72,24,72]),dict(role='entry',eye=[24.5,25.62,24.5],target=[60,25.6,60])])
(p/'coordinates.json').write_text(json.dumps(context),encoding='utf8')
s=default_settings();s['style_note']='Synthetic real-work cancellation; no asset approval'
for value in s.values():
 if isinstance(value,dict) and 'enabled' in value:value['enabled']=False
tiny=Model((8,8,8));tiny.box((0,0,0),(7,7,7),stone);tiny.box((1,1,1),(6,6,6),'air');tiny.check_sealed([[3,3,3]])
save_master(p/'master/tiny.master.json.gz',tiny,set(tiny.blocks))
(p/'settings.json').write_text(json.dumps(s),encoding='utf8')
print(json.dumps(dict(blocks=len(m.blocks),size=list(m.size))))
`,path.join(root,'.agents/skills/minecraft-nbt-modeler/scripts'),fixture],{encoding:'utf8',windowsHide:true,timeout:180000,maxBuffer:1024*1024}))
assert.ok(made.blocks>500000)
const source=path.join(fixture,'master/master_geometry.json.gz'),tiny=path.join(fixture,'master/tiny.master.json.gz'),context=path.join(fixture,'coordinates.json')
const settings=JSON.parse(await fs.readFile(path.join(fixture,'settings.json'),'utf8')),sha=data=>createHash('sha256').update(data).digest('hex'),before=sha(await fs.readFile(source))
let server;const checks={},observations=[]
const alive=pid=>{try{process.kill(pid,0);return true}catch(error){if(error.code==='ESRCH')return false;throw error}}
async function until(read,accept,timeout=60000){const deadline=Date.now()+timeout;while(Date.now()<deadline){const value=await read();if(accept(value))return value;await new Promise(resolve=>setTimeout(resolve,20))}throw Error('Timed out observing real task state')}
async function matchingPids(){
 const response=await fetch(new URL('/__detail__/workers',server.url));assert.equal(response.status,200)
 const {items}=await response.json();return items.filter(item=>item.phase==='inspect'&&typeof item.source==='string'&&path.resolve(item.source).toLowerCase()===source.toLowerCase()).map(item=>item.pid)
}

try{
 server=await startDetailServer({workspace,output:path.join(out,'jobs'),python})
 const api=async(route,body)=>{const response=await fetch(new URL('/__detail__/'+route,server.url),body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{});const data=await response.json();if(!response.ok)throw Error(data.error);return data}
 const request={source,context,settings}
 async function cancelled(kind,phase){
  const {id}=await api('jobs',{kind,request:structuredClone(request)})
  const live=await until(()=>api('jobs/'+id),job=>job.status==='running'&&job.phase===phase&&Number.isSafeInteger(job.backend_pid))
  assert.equal(alive(live.backend_pid),true)
  observations.push({id,kind,phase,pid:live.backend_pid,live_before_cancel:true})
  await api('cancel',{})
  const job=await api('jobs/'+id)
  assert.equal(job.status,'cancelled');assert.equal(job.cancel_requested,true);assert.ok(job.completed_at);assert.equal(job.result,undefined)
  assert.equal(alive(live.backend_pid),false)
  const persisted=JSON.parse(await fs.readFile(path.join(job.directory,'job.json'),'utf8'))
  assert.equal(persisted.status,'cancelled');assert.ok((await fs.stat(path.join(job.directory,'request.json'))).isFile())
  const log=path.join(job.directory,phase==='inspect'?'inspect.log':'backend.log');assert.ok((await fs.stat(log)).isFile())
  return job
 }
 const preflight=await cancelled('plan','inspect')
 await assert.rejects(fs.access(path.join(fixture,'Agent交接')))
 checks.preflight_inspect_cancelled_before_plan_or_handoff=true
 checks.actual_python_pid_exit_and_diagnostics_preserved=true
 async function nextTask(){
  const {id}=await api('jobs',{kind:'snapshot',request:{source:tiny,context:'',settings}})
  const job=await until(()=>api('jobs/'+id),job=>job.status!=='running')
  assert.equal(job.status,'complete',job.error);assert.ok((await fs.stat(job.result.snapshot)).isFile())
  return id
 }
 await nextTask();checks.slot_is_reusable_immediately_after_cancel=true
 await cancelled('preview','preview');checks.real_processing_cancelled_not_failed=true
 await nextTask();checks.slot_reusable_after_processing_cancel=true
 const failed=await api('jobs',{kind:'preview',request:{source:tiny,context:path.join(fixture,'missing-context.json'),settings}})
 const failure=await until(()=>api('jobs/'+failed.id),job=>job.status!=='running')
 assert.equal(failure.status,'failed');assert.equal(failure.cancel_requested,undefined)
 checks.actual_failure_remains_distinct_from_cancel=true
 // Non-job /inspect is not activeJob, but close still owns and stops its child.
 const pending=api('inspect',{source}).then(value=>({value}),error=>({error:error.message}))
 const pids=await until(async()=>matchingPids(),pids=>pids.length>0)
 assert.ok(pids.every(alive));observations.push({kind:'non-job inspect',pids,live_before_close:true})
 await server.close();await pending
 assert.ok(pids.every(pid=>!alive(pid)));checks.close_stops_owned_nonjob_python=true
 assert.equal(sha(await fs.readFile(source)),before);checks.original_large_fixture_unchanged=true
 await fs.writeFile(path.join(out,'results.json'),JSON.stringify({passed:true,checks,fixture:made,observations,preflight_directory:preflight.directory},null,2))
 console.log(JSON.stringify({passed:true,checks:Object.keys(checks).length,output:out}))
}finally{await server?.close()}
