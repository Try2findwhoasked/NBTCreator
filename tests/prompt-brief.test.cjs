const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs/promises'),os=require('node:os'),path=require('node:path')
const {createApiService}=require('../desktop/api-service.cjs'),{createCandidateValidator}=require('../desktop/ai-candidate-validator.cjs'),{buildInternalPrompt}=require('../desktop/internal-skill.cjs')
const project=Object.fromEntries(['name','theme','purpose','layout','circulation','style','ceiling','floor','wall','props'].map(key=>[key,'可交接的设计要求']))
test('ordinary prompt drafts return requirements without tool generation or a Python geometry process',async t=>{
 const directory=await fs.mkdtemp(path.join(os.tmpdir(),'nbt-brief-'));t.after(()=>fs.rm(directory,{recursive:true,force:true}));const calls=[]
 const api=createApiService({directory,safeStorage:{},validateCandidate:createCandidateValidator({root:path.resolve(__dirname,'..'),python:'missing-python-for-text-only.exe',directory,getWorkspace:()=>directory}),fetchImpl:async(_u,o)=>{calls.push(JSON.parse(o.body));return new Response(JSON.stringify({choices:[{finish_reason:'stop',message:{content:JSON.stringify({project_patch:project})}}]}))}})
 await api.save({enabled:true});const result=await api.generate({mode:'workbench',instruction:'写提示词并交接',context:{task:'brief',project:{size:[48,24,48]},operations:[{kind:'box',state:'stone'}]}})
 assert.equal(result.operations,undefined);assert.equal(result.project_patch.name,project.name);assert.equal(result.api_metrics.attempts,1);assert.equal(calls.length,1);assert.equal(JSON.parse(calls[0].messages[1].content).context.operations.length,0);assert.ok(!calls[0].messages[0].content.includes('geometry_parameters'));assert.ok(buildInternalPrompt('workbench',{task:'brief'}).length<1000);assert.equal((await fs.readdir(directory)).includes('ai-validation'),false)
})
test('model tool output is corrected into a requirements-only handoff instead of executed',async t=>{
 const directory=await fs.mkdtemp(path.join(os.tmpdir(),'nbt-brief-repair-'));t.after(()=>fs.rm(directory,{recursive:true,force:true}));let n=0
 const api=createApiService({directory,safeStorage:{},fetchImpl:async()=>{const reply={project_patch:project,...(++n===1?{operations:[{kind:'box',lo:[0,0,0],hi:[0,1,0],state:'stone'}]}:{})};return new Response(JSON.stringify({choices:[{finish_reason:'stop',message:{content:JSON.stringify(reply)}}]}))}})
 await api.save({enabled:true});const result=await api.generate({mode:'workbench',instruction:'编写设计',context:{task:'brief',project:{size:[48,24,48]},operations:[]}});assert.equal(n,2);assert.equal(result.operations,undefined)
})
