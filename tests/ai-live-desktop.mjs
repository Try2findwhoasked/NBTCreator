// Explicit opt-in: uses the supplied profile's configured real API, in an isolated
// workspace. No model output becomes a published asset or exported NBT.
import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import path from 'node:path'
import {createRequire} from 'node:module'
import {spawnSync} from 'node:child_process'
import {root,skill,python} from '../scripts/paths.mjs'
import {minimizedScreenshots} from './minimized-screenshots.mjs'
const index=process.argv.indexOf('--profile');if(index<0||!process.argv[index+1])throw Error('显式提供 --profile <NBTCreator配置目录>；此检查会调用真实API')
const sourceProfile=path.resolve(process.argv[index+1]),output=path.join(root,'build','ai-live-'+Date.now()),profile=path.join(output,'profile'),workspace=path.join(output,'workspace')
const require=createRequire(path.join(skill,'assets/viewer/package.json')),{_electron}=require('playwright')
const applicationRoot=process.env.NBTCREATOR_TEST_EXE?path.join(path.dirname(process.env.NBTCREATOR_TEST_EXE),'resources/app'):root,validationPython=process.env.NBTCREATOR_TEST_EXE?path.join(applicationRoot,'runtime/python/python.exe'):python
await fs.mkdir(profile,{recursive:true});await fs.mkdir(workspace)
const cloned=['api-settings.json','Local State']
const cases=[
 {id:'draft',request:{mode:'workbench',instruction:'生成一座废弃的神庙初稿',context:{task:'draft',project:{name:'废弃神庙',buildingShape:'single',size:[48,24,48]},operations:[],existing_model:false}}},
 {id:'small_structure',request:{mode:'small_structure',instruction:'一座带基座、柱身和柱帽的残破石柱，保持粗壮支承，合并同材质区域。',context:{size:[32,16,32],lo:[8,4,8],hi:[15,10,15],allow_overwrite:false}}},
 {id:'component',request:{mode:'component',instruction:'一座可以复用的石制拱门，柱脚承托拱顶，中间净空可通行，少量磨损装饰。',context:{name:'实测石拱门',size:[12,10,8],references:[]}}}
]
let app,page;const results=[]
try{
 for(const name of cloned)await fs.copyFile(path.join(sourceProfile,name),path.join(profile,name))
 const env={...process.env,NBTCREATOR_AUTOMATION:'1'};delete env.ELECTRON_RUN_AS_NODE
 app=await _electron.launch({executablePath:process.env.NBTCREATOR_TEST_EXE||path.join(root,'node_modules/electron/dist/electron.exe'),args:[...(process.env.NBTCREATOR_TEST_EXE?[]:[root]),'--workspace',workspace,'--user-data-dir',profile],env,timeout:60000});page=await app.firstWindow();await minimizedScreenshots(app,page);await page.waitForFunction(()=>window.detailControl?.state.catalogReady)
 await app.evaluate(({net})=>{const original=net.fetch.bind(net);globalThis.liveReplies=[];globalThis.liveReads=[];net.fetch=async(...args)=>{const response=await original(...args);if(String(args[0]).includes('chat/completions')){const record={status:response.status};globalThis.liveReplies.push(record);const read=response.clone().json().then(value=>Object.assign(record,{finish_reason:value.choices?.[0]?.finish_reason,content:value.choices?.[0]?.message?.content,usage:value.usage}));globalThis.liveReads.push(read)}return response}})
 for(const item of cases){
  const started=Date.now();let result,error,preview
  try{
   result=await page.evaluate(request=>window.nbtDesktop.apiGenerate(request),item.request)
   if(result?.api_error)throw Error(result.api_error.message)
   if(item.id==='component'){
    preview=await page.evaluate(async spec=>{const response=await fetch('/__detail__/components/agent',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({tool:'structure_preview',arguments:{spec}})});const result=await response.json();if(!response.ok)throw Error(result.error);return result},result.spec)
    const file=path.join(output,'external-agent-request.json');await fs.writeFile(file,JSON.stringify({spec:result.spec}))
    const external=spawnSync(validationPython,[path.join(workspace,'.agents/skills/nbtcreator-workspace/nbt.py'),'components','--workspace',workspace,'agent','--tool','structure_preview','--request',file],{cwd:workspace,encoding:'utf8',windowsHide:true,timeout:30000})
    assert.equal(external.status,0,external.stderr);const externalPreview=JSON.parse(external.stdout).result;assert.equal(externalPreview.content_sha256,preview.content_sha256);preview.external_agent_cli_same_geometry=true
    await fs.copyFile(path.join(path.dirname(preview.source),'thumbnail.jpg'),path.join(output,'actual-component-preview.jpg'))
   }else{
    const file=path.join(output,item.id+'-candidate.json');await fs.writeFile(file,JSON.stringify({mode:'workbench',context:{task:'draft',project:{size:item.request.context.size??item.request.context.project.size}},result:{project_patch:result.project_patch??{},operations:result.operations??result.settings_patch.operations}}))
    const checked=spawnSync(validationPython,['-B',path.join(applicationRoot,'.agents/skills/minecraft-nbt-modeler/scripts/nbt_ai_validate.py'),'--request',file],{encoding:'utf8',windowsHide:true,timeout:30000});assert.equal(checked.status,0,checked.stderr);preview=JSON.parse(checked.stdout);assert.equal(preview.ok,true,preview.error)
   }
  }catch(e){error=e.message}
  const entry={id:item.id,passed:!error,elapsed_ms:Date.now()-started,attempts:result?.api_metrics?.attempts??result?.api_error?.api_metrics?.attempts,result,preview,error};results.push(entry);await fs.writeFile(path.join(output,'results.json'),JSON.stringify({passed:results.every(item=>item.passed),external_api_used:true,results},null,2));console.log(JSON.stringify({id:item.id,passed:entry.passed,attempts:entry.attempts,elapsed_ms:entry.elapsed_ms,error}))
 }
 await app.evaluate(async()=>Promise.allSettled(globalThis.liveReads));const replies=await app.evaluate(()=>globalThis.liveReplies);await fs.writeFile(path.join(output,'synthetic-model-replies.json'),JSON.stringify(replies,null,2));assert.ok(results.every(item=>item.passed),'真实调用有未通过项，查看 '+output)
 console.log(JSON.stringify({passed:true,cases:results.length,output}))
}finally{await app?.close();for(const name of cloned)await fs.unlink(path.join(profile,name)).catch(()=>{})}
