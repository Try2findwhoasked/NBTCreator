import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import path from 'node:path'
import http from 'node:http'
import {spawnSync} from 'node:child_process'
import {createRequire} from 'node:module'
import {root,skill,python} from '../scripts/paths.mjs'
import {minimizedScreenshots} from './minimized-screenshots.mjs'
const require=createRequire(path.join(skill,'assets/viewer/package.json')),{_electron}=require('playwright')
const output=path.join(root,'build','agent-simulation-'+Date.now()),workspace=path.join(output,'workspace');await fs.mkdir(workspace,{recursive:true})
const appRoot=process.env.NBTCREATOR_TEST_EXE?path.join(path.dirname(process.env.NBTCREATOR_TEST_EXE),'resources/app'):root,engine=path.join(appRoot,'.agents/skills/minecraft-nbt-modeler'),runtime=process.env.NBTCREATOR_TEST_EXE?path.join(appRoot,'runtime/python/python.exe'):python
const box={kind:'box',label:'石柱',classification:'body',lo:[2,1,2],hi:[3,4,3],state:'stone_bricks'},size=[16,10,16],region={size,lo:[0,0,0],hi:[15,9,15],allow_overwrite:false}
const project=Object.fromEntries(['name','theme','purpose','layout','circulation','style','ceiling','floor','wall','props'].map(key=>[key,'模拟石构设计']))
const draft={mode:'workbench',context:{task:'draft',project:{size},operations:[],existing_model:false}},component={mode:'component',context:{name:'模拟石柱',size,references:[]}},local={mode:'structure',context:region},small={mode:'small_structure',context:{...region,lo:[4,2,4],hi:[11,8,11]}},controls=operations=>({mode:'workbench',context:{project:{size},operations,existing_model:true}})
const validDraft={project_patch:project,operations:[box]},validComponent={operations:[box]},validLocal={settings_patch:{lo:box.lo,hi:box.hi,structure:{enabled:true,mode:'fill',state:{Name:'minecraft:oak_log',Properties:{axis:'y'}},classification:'body',thickness:1,offset:[0,0,0]}}}
const selection={mode:'selection_edit',context:{...region,selection:{schema_version:1,geometry_sha256:'a'.repeat(64),size,palette:[],runs:[],solid_blocks:0,air_omitted:true}}}
const cases=[
 {id:'text_final_only',input:{mode:'prompt'},replies:['<think>计划</think>\n<final>保留净空与支承。</final>'],verify:r=>assert.equal(r.text,'保留净空与支承。')},
 {id:'local_standard_state',input:local,replies:[validLocal],verify:r=>assert.equal(r.settings_patch.structure.state,'minecraft:oak_log[axis=y]')},
 {id:'small_compact_and_translation',input:small,replies:[{boxes:[[0,0,0,0,3,0,'stone']]}],verify:r=>assert.deepEqual(r.settings_patch.operations[0].lo,[4,2,4])},
 {id:'draft_classification_repair',input:draft,replies:[{...validDraft,operations:[{...box,classification:'structure'}]},validDraft],feedback:/classification.*structure/},
 {id:'draft_version_registry_repair',input:draft,replies:[{...validDraft,operations:[{...box,state:'tuff_bricks'},{...box,lo:[5,1,5],hi:[5,2,5],state:'stone[bogus=x]'}]},validDraft],feedback:/tuff_bricks.*bogus/},
 {id:'draft_actual_geometry_repair',input:draft,replies:[{...validDraft,operations:[{kind:'auto_stairs',label:'无上升台阶',classification:'body',lo:[0,0,0],hi:[15,9,15],start:[2,1,2],end:[12,1,2]}]},validDraft],feedback:/第1步.*above start/},
 {id:'component_wrapped_metadata',input:component,replies:[{operations:[{type:'box',lo:box.lo,hi:box.hi,state:{Name:'minecraft:stone_bricks'},common:{label:'柱体',classification:'body'}}]}]},
 {id:'component_geometry_then_preview',input:component,replies:[{operations:[{...box,kind:'frame'}]},validComponent],feedback:/Frame must lie/},
 {id:'selection_data_only',input:selection,replies:[{operations:[{...box,classification:'inherit'}]}],verify:r=>assert.equal(r.settings_patch.baseline_geometry_sha256,'a'.repeat(64))},
 {id:'delta_nullable_mirror',input:controls([{...box,kind:'transform_region',destination:[8,1,8],mirror:null,quarter_turns:0}]),replies:[{operation_patch:{changes:[{step:1,set:{mirror:'x'}}]}}],verify:r=>assert.equal(r.operations[0].mirror,'x')},
 {id:'delta_scalar_to_xyz',input:controls([{...box,kind:'pattern',scale:6,palette:['stone']}]),replies:[{operation_patch:{changes:[{step:1,set:{scale:[2,3,4]}}]}}],verify:r=>assert.deepEqual(r.operations[0].scale,[2,3,4])},
 {id:'truncated_json_repair',input:component,replies:['{"operations":[',validComponent],finish:['length','stop']},
 {id:'unknown_field_repair',input:controls([]),replies:[{operations:[{...box,script:'not executable'}]},{operations:[box]}],feedback:/未开放字段.*script/},
 {id:'persistent_invalid_stops',input:component,replies:['bad json'],error:/JSON/,attempts:3},
 {id:'repeated_truncation_stops',input:component,replies:['{"operations":['],finish:['length'],error:/上限/,attempts:2},
 {id:'http_auth_no_format_retry',input:{mode:'prompt'},status:401,replies:['private provider body'],error:/401/,attempts:1}
]
let current,calls=[],app,page;const records=[],errors=[]
const server=http.createServer(async(req,res)=>{let raw='';for await(const chunk of req)raw+=chunk;const body=JSON.parse(raw);calls.push(body);if(current.status){res.writeHead(current.status);res.end('private provider body');return}const index=Math.min(calls.length-1,current.replies.length-1),value=current.replies[index];res.setHeader('Content-Type','application/json');res.end(JSON.stringify({choices:[{finish_reason:current.finish?.[Math.min(calls.length-1,current.finish.length-1)]??'stop',message:{reasoning_content:'private reasoning excluded',content:typeof value==='string'?value:JSON.stringify(value)}}]}))})
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve))
const api=async(action,body)=>page.evaluate(async({action,body})=>{const response=await fetch('/__detail__/'+action,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const result=await response.json();if(!response.ok)throw Error(result.error);return result},{action,body})
try{
 const env={...process.env,NBTCREATOR_AUTOMATION:'1'};delete env.ELECTRON_RUN_AS_NODE
 app=await _electron.launch({executablePath:process.env.NBTCREATOR_TEST_EXE||path.join(root,'node_modules/electron/dist/electron.exe'),args:[...(process.env.NBTCREATOR_TEST_EXE?[]:[root]),'--workspace',workspace,'--user-data-dir',path.join(output,'profile')],env,timeout:60000});page=await app.firstWindow();await minimizedScreenshots(app,page);page.on('pageerror',error=>errors.push(error.message));await page.waitForFunction(()=>window.detailControl?.state.catalogReady)
 await page.evaluate(baseUrl=>window.nbtDesktop.apiSave({enabled:true,provider:'compatible',baseUrl,model:'simulation',outputCharLimit:0}),`http://127.0.0.1:${server.address().port}`)
 for(const item of cases){
  current=item;calls=[];const input={...item.input,instruction:item.id},result=await page.evaluate(input=>window.nbtDesktop.apiGenerate(input),input)
  if(item.error){assert.match(result.api_error?.message??'',item.error);assert.equal(calls.length,item.attempts)}else{
   assert.ok(!result.api_error,JSON.stringify(result.api_error));assert.equal(calls.length,item.replies.length);item.verify?.(result)
   if(item.feedback)assert.match(calls[1].messages.at(-1).content,item.feedback)
   if(item.input.mode==='component'){
    const preview=await api('components/agent',{tool:'structure_preview',arguments:{spec:result.spec}});assert.ok(preview.block_count>0);assert.equal(preview.model_modified,false)
    const file=path.join(output,item.id+'-external.json');await fs.writeFile(file,JSON.stringify({spec:result.spec}));const cli=spawnSync(runtime,[path.join(workspace,'.agents/skills/nbtcreator-workspace/nbt.py'),'components','--workspace',workspace,'agent','--tool','structure_preview','--request',file],{cwd:workspace,encoding:'utf8',windowsHide:true,timeout:30000});assert.equal(cli.status,0,cli.stdout+cli.stderr);assert.equal(JSON.parse(cli.stdout).result.content_sha256,preview.content_sha256)
    const saved=await api('components/agent',{tool:'structure_write',arguments:{preview_id:preview.preview_id,preview_sha256:preview.preview_sha256}});const read=await api('components/agent',{tool:'structure_read',arguments:{id:saved.id}});assert.equal(read.content_sha256,preview.content_sha256)
   }
  }
  for(const request of calls){assert.equal(request.messages[1].content,calls[0].messages[1].content);assert.ok(!JSON.stringify(request).includes(workspace));assert.ok(!JSON.stringify(request).includes('private reasoning excluded'))}
  records.push({id:item.id,passed:true,attempts:calls.length,metrics:result.api_metrics??result.api_error?.api_metrics});console.log(JSON.stringify({id:item.id,passed:true,attempts:calls.length}))
 }
 assert.deepEqual(errors,[])
 await fs.writeFile(path.join(output,'results.json'),JSON.stringify({passed:true,external_api_used:false,mock_http_real_electron:true,real_python_engine:true,external_agent_preview_and_read:true,cases:records},null,2));console.log(JSON.stringify({passed:true,cases:records.length,output}))
}catch(error){await fs.writeFile(path.join(output,'results.json'),JSON.stringify({passed:false,case:current?.id,error:error.message,cases:records},null,2));throw error}finally{await app?.close();server.closeAllConnections();await new Promise(resolve=>server.close(resolve))}
