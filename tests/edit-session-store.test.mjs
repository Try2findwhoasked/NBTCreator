import {test} from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import os from 'node:os'
import path from 'node:path'
import {createHash,randomUUID} from 'node:crypto'
import {createEditSessionStore,validateSessionState} from '../.agents/skills/minecraft-nbt-modeler/assets/viewer/edit-session-store.mjs'
const digest=data=>createHash('sha256').update(data).digest('hex')
function state(){return {settings:{operations:[],structure:{},replace:{},pattern:{},weathering:{},floor:{}},operations_text:'[]',controls:{'whole-region':false,'lo-x':'5'},view:{mode:'3d',quality:'fast',camera:{eye:[10,8,10],target:[5,2,5],up:[0,1,0],fov:60},cuts:[{axis:'y',position:6,removed_side:'above'}],layer:'all',cut:5,show_selection:true,image_hash:null,comparison:'before'},drafts:[]}}
async function fixture(t){const root=await fs.mkdtemp(path.join(os.tmpdir(),'nbt-sessions-'));t.after(()=>fs.rm(root,{recursive:true,force:true}));const source=path.join(root,'nbt_models/single/room/v1/master/master.json.gz');await fs.mkdir(path.dirname(source),{recursive:true});await fs.writeFile(source,'model-one');return {root,source,hash:digest('model-one')}}
test('drafts are portable, bounded data and never modify source assets',async t=>{
 const {root,source,hash}=await fixture(t),store=createEditSessionStore(root),client_id=randomUUID(),draft=state();draft.drafts=[[hash+':3d:'+digest('geometry'),{text:'#1 修改支承',points:[{kind:'voxel',number:1,position:[5,2,5],state:'minecraft:stone',source_sha256:hash,geometry_sha256:digest('geometry')}]}]]
 assert.equal((await store.load(source)).status,'empty');assert.equal(await store.recent(),null)
 await store.save({source,source_sha256:hash,expected_revision:0,client_id,sequence:1,state:draft});assert.deepEqual((await store.load(source)).state,draft)
 const index=JSON.parse(await fs.readFile(path.join(root,'.nbtcreator/edit-sessions/index.json'),'utf8'));assert.equal(Object.values(index.sources)[0].source,'nbt_models/single/room/v1/master/master.json.gz');assert.equal(await fs.readFile(source,'utf8'),'model-one')
 const moved=root+'-moved';await fs.rename(root,moved);t.after(()=>fs.rm(moved,{recursive:true,force:true}));const other=createEditSessionStore(moved),relocated=path.join(moved,path.relative(root,source));assert.equal((await other.recent()).source,relocated);assert.deepEqual((await other.load(relocated)).state,draft)
})
test('source changes retain old draft, and reverting source finds its exact draft',async t=>{
 const {root,source,hash}=await fixture(t),store=createEditSessionStore(root),client_id=randomUUID();await store.save({source,source_sha256:hash,expected_revision:0,client_id,sequence:1,state:state()})
 await fs.writeFile(source,'model-two');assert.equal((await store.load(source)).status,'source_changed');await assert.rejects(store.save({source,source_sha256:hash,expected_revision:1,client_id,sequence:2,state:state()}),/源建筑已变化/)
 await store.save({source,source_sha256:digest('model-two'),expected_revision:0,client_id,sequence:3,state:state()});const files=(await fs.readdir(path.join(root,'.nbtcreator/edit-sessions'))).filter(n=>n!=='index.json');assert.equal(files.length,2)
 await fs.writeFile(source,'model-one');assert.equal((await store.load(source)).status,'found')
})
test('newer same-editor saves win even when a closing beacon arrives out of order',async t=>{
 const {root,source,hash}=await fixture(t),store=createEditSessionStore(root),client_id=randomUUID(),base={source,source_sha256:hash,client_id};const a=state(),b=state();b.operations_text='[{unfinished'
 await store.save({...base,expected_revision:0,sequence:2,state:b});await store.save({...base,expected_revision:0,sequence:1,state:a});assert.equal((await store.load(source)).state.operations_text,b.operations_text)
 await assert.rejects(store.save({...base,client_id:randomUUID(),expected_revision:0,sequence:1,state:a}),/另一个窗口/)
 const current=await store.load(source);await store.save({...base,client_id:randomUUID(),expected_revision:current.revision,sequence:1,state:a});assert.equal((await store.load(source)).state.operations_text,'[]')
})
test('invalid routes, credentials, foreign comments and malformed view state are rejected',async t=>{
 const {root,source,hash}=await fixture(t),store=createEditSessionStore(root);await assert.rejects(store.load('../outside'))
 for(const patch of [{api_key:'secret'},{view:{...state().view,camera:{eye:[NaN,0,0],target:[0,0,0],up:[0,1,0],fov:60}}},{drafts:[[digest('foreign')+':'+digest('image'),{text:'foreign',points:[]}]]},{controls:{'../source':'bad'}},{settings:{...state().settings,approval:'yes'}}])assert.throws(()=>validateSessionState({...state(),...patch},hash))
 const payload={source,source_sha256:hash,client_id:randomUUID(),expected_revision:0,sequence:1,state:state()};await assert.rejects(store.save({...payload,source:'//host/share'}));assert.equal(await fs.readFile(source,'utf8'),'model-one')
})
test('independent Windows backend instances cannot commit the same base revision', {skip:process.platform!=='win32'},async t=>{
 const {root,source,hash}=await fixture(t),a=createEditSessionStore(root),b=createEditSessionStore(root)
 const payload={source,source_sha256:hash,expected_revision:0,sequence:1,state:state()}
 const results=await Promise.allSettled([a.save({...payload,client_id:randomUUID()}),b.save({...payload,client_id:randomUUID()})]);assert.equal(results.filter(r=>r.status==='fulfilled').length,1);assert.equal(results.filter(r=>r.status==='rejected').length,1);assert.equal((await a.load(source)).revision,1)
})
test('a full-size component can persist once without repeated formatted JSON',async t=>{
 const {root,source,hash}=await fixture(t),store=createEditSessionStore(root),draft=state();draft.operations_text=null;draft.settings.operations=[{kind:'paste_component',label:'65536格构件',classification:'body',lo:[0,0,0],hi:[63,15,63],palette:['minecraft:stone'],voxels:Array.from({length:65536},(_,i)=>[i%64,Math.floor(i/4096),Math.floor(i/64)%64,0])}]
 await store.save({source,source_sha256:hash,expected_revision:0,client_id:randomUUID(),sequence:1,state:draft});const restored=await store.load(source);assert.equal(restored.state.operations_text,null);assert.equal(restored.state.settings.operations[0].voxels.length,65536);assert.ok(Buffer.byteLength(JSON.stringify(restored.state))<3*1024*1024)
})
test('camera recovery accepts finite world coordinates beyond the model bounds',()=>{
 const draft=state();draft.view.camera.eye=[30000001,-50000000,1];draft.view.camera.target=[30000002,-50000000,1]
 assert.equal(validateSessionState(draft,digest('model-one')),draft)
})

test('named AI component keeps one angle in its version-bound draft and rejects arbitrary view metadata',async t=>{
 const {root,source,hash}=await fixture(t),store=createEditSessionStore(root),draft=state()
 const op={kind:'box',label:'柱身',classification:'body',state:'stone_bricks',lo:[4,2,4],hi:[5,7,5]}
 draft.settings.operations=[op];draft.ai_component={start:0,base:[structuredClone(op)],applied:[structuredClone(op)],offset:[0,0,0],overwrite:false,quarter_turns:1,structure_name:'带帽石柱',camera:{azimuth:90,elevation:25}}
 await store.save({source,source_sha256:hash,expected_revision:0,client_id:randomUUID(),sequence:1,state:draft});assert.deepEqual((await store.load(source)).state.ai_component,draft.ai_component)
 for(const patch of [{quarter_turns:4},{quarter_turns:.5},{structure_name:'x'.repeat(121)},{camera:[{azimuth:0,elevation:0}]},{camera:{azimuth:0,elevation:NaN}},{camera:{azimuth:0,elevation:0,script:'exec'}}])assert.throws(()=>validateSessionState({...draft,ai_component:{...draft.ai_component,...patch}},hash))
})
test('image evidence remains bound to its original pixels after the source image changes',async t=>{
 const {root,hash}=await fixture(t),store=createEditSessionStore(root),image=path.join(root,'preview.png'),bytes=Buffer.from('original image evidence'),imageHash=digest(bytes),geometry=digest('geometry')
 await fs.writeFile(image,bytes)
 const archived=await store.rememberImage({image,image_sha256:imageHash,source_sha256:hash,geometry_sha256:geometry,camera:null,cuts:[]})
 await fs.writeFile(image,'replacement image')
 assert.equal(await store.imageEvidence(hash,imageHash,'preview.png',geometry),archived);assert.deepEqual(await fs.readFile(archived),bytes)
 await assert.rejects(store.rememberImage({image,image_sha256:imageHash,source_sha256:hash,geometry_sha256:geometry}),/图片已变化/)
 await assert.rejects(store.imageEvidence(hash,imageHash,'preview.png',digest('other geometry')),/不匹配/)
 assert.equal(await store.imageEvidence(hash,digest('absent'),'preview.png',geometry),null)
 await assert.rejects(store.imageEvidence(hash,imageHash,'../preview.png',geometry),/参数无效/)
})

test('AI candidate is tied to source and its settings without preserving credentials or absolute bindings',async t=>{const {root,source,hash}=await fixture(t),store=createEditSessionStore(root),draft=state();draft.ai_candidate={schema_version:1,source_sha256:hash,settings:structuredClone(draft.settings),can_apply:true,result:{mode:'structure',summary:'恢复的候选',settings_patch:{lo:[4,4,4],hi:[5,5,5],structure:{enabled:true,mode:'fill',state:'stone'}}}};await store.save({source,source_sha256:hash,expected_revision:0,client_id:randomUUID(),sequence:1,state:draft});assert.deepEqual((await store.load(source)).state.ai_candidate,draft.ai_candidate);for(const patch of [{source_sha256:digest('other')},{api_key:'secret'},{result:{...draft.ai_candidate.result,settings_patch:{source:'other'}}}])assert.throws(()=>validateSessionState({...draft,ai_candidate:{...draft.ai_candidate,...patch}},hash))})
