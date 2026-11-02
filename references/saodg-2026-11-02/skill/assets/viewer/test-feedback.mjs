import fs from 'node:fs/promises'
import path from 'node:path'
import assert from 'node:assert/strict'
import { parseArgs } from 'node:util'
import { createHash } from 'node:crypto'
import { createFeedbackStore } from './feedback-store.mjs'
const {values}=parseArgs({options:{output:{type:'string'}}})
if(!values.output)throw new Error('Provide --output new-directory')
const out=path.resolve(values.output);await fs.mkdir(out)
const source=path.join(out,'synthetic-source.json'),image=path.join(out,'synthetic-image.bin')
await fs.writeFile(source,'synthetic model');await fs.writeFile(image,'synthetic image')
const hash=bytes=>createHash('sha256').update(bytes).digest('hex')
const binding={source,image,source_sha256:hash(await fs.readFile(source)),image_sha256:hash(await fs.readFile(image)),geometry_sha256:hash('geometry'),camera:null,cuts:[]}
const store=createFeedbackStore(path.join(out,'feedback')),checks={}
assert.equal((await store.list(binding)).notes.length,0);checks.empty_store_is_readable=true
await Promise.all(Array.from({length:12},(_,i)=>store.add(binding,'Synthetic note '+i,{x:.25,y:.75})))
let record=await createFeedbackStore(path.join(out,'feedback')).list(binding)
assert.equal(record.notes.length,12);assert.equal(new Set(record.notes.map(n=>n.number)).size,12);checks.concurrent_writes_preserve_all_notes=true
await store.update(binding,record.notes[0].id,'resolved')
assert.equal((await store.list(binding)).notes[0].status,'resolved');checks.status_persisted=true
assert.throws(()=>store.add(binding,'',null));assert.throws(()=>store.add(binding,'bad',{x:2,y:.5}));checks.invalid_notes_refused=true
const exported=await store.export(binding);assert.ok((await fs.readFile(exported.markdown,'utf8')).includes('Synthetic note'));checks.markdown_export=true
const projectStore=createFeedbackStore(()=>path.join(out,'project','修改意见'),path.join(out,'feedback'))
assert.equal((await projectStore.list(binding)).notes.length,12);checks.legacy_comments_remain_readable=true
const moved=await projectStore.add(binding,'New project-local comment')
assert.ok(moved.file.includes('修改意见'));assert.equal((await store.list(binding)).notes.length,12);checks.project_local_writes_preserve_legacy_files=true
await fs.writeFile(source,'changed model')
await assert.rejects(()=>store.add(binding,'stale',null));assert.equal((await store.list(binding)).notes.length,12);checks.changed_source_refuses_new_notes=true
const fresh={...binding,source_sha256:hash(await fs.readFile(source))}
assert.equal((await store.list(fresh)).notes.length,0);checks.versions_are_separate=true
await fs.writeFile(image,'changed image')
await assert.rejects(()=>store.add(fresh,'stale picture',null));checks.changed_image_refuses_new_notes=true
const empty=await store.export(fresh);assert.equal(JSON.parse(await fs.readFile(empty.json)).notes.length,0);checks.empty_export_works=true
await fs.writeFile(source,'synthetic model');await fs.writeFile(image,'synthetic image')
const multi=await store.add(binding,'#13 repair wall\n#14 repair floor',null,[],[{kind:'image',number:13,x:.2,y:.3},{kind:'image',number:14,x:.8,y:.9}])
assert.equal(multi.notes.at(-1).anchors.length,2)
await assert.rejects(()=>store.add(binding,'duplicate',null,[],[{kind:'image',number:13,x:.1,y:.1}]))
assert.throws(()=>store.add(binding,'bad',null,[],[{kind:'image',number:15,x:2,y:.1}]))
assert.ok((await fs.readFile((await store.export(binding)).markdown,'utf8')).includes('#14：图片位置'))
checks.multiple_image_positions_persist_export_and_reject_collisions=true
const snapshot=path.join(out,'snapshot.json');await fs.writeFile(snapshot,'synthetic snapshot')
const three={...binding,kind:'3d',image:undefined,image_sha256:undefined,snapshot,snapshot_sha256:hash(await fs.readFile(snapshot)),size:[48,24,48]}
const view={camera:{eye:[60,60,60],target:[24,10,24],up:[0,1,0],fov:60},cuts:[],layer:'all'}
const anchors=[1,2].map(number=>({kind:'voxel',number,position:[number,4,5],state:'minecraft:stone',geometry_sha256:three.geometry_sha256,view}))
const voxels=await store.add(three,'#1 wall\n#2 ceiling',null,[],anchors)
assert.equal(voxels.notes.length,1);assert.deepEqual(voxels.notes[0].anchors[1].position,[2,4,5]);assert.ok(voxels.file.includes('3d_'))
assert.equal((await store.list(binding)).notes.length,13)
assert.throws(()=>store.add(three,'out of bounds',null,[],[{...anchors[0],number:3,position:[48,0,0]}]))
assert.throws(()=>store.add(three,'wrong version',null,[],[{...anchors[0],number:3,geometry_sha256:hash('different')}]))
const md=await fs.readFile((await store.export(three)).markdown,'utf8');assert.ok(md.includes('#2：方块坐标 (2, 4, 5)'))
const restored=await createFeedbackStore(path.join(out,'feedback')).list(three);assert.deepEqual(restored.notes[0].anchors,anchors)
checks.multiple_voxel_positions_version_binding_and_round_trip=true
await fs.writeFile(snapshot,'changed snapshot');await assert.rejects(()=>store.add(three,'stale 3d',null,[],[]));checks.changed_snapshot_refused=true
await fs.writeFile(out+'/results.json',JSON.stringify({passed:true,checks},null,2))
console.log(JSON.stringify({passed:true,checks:Object.keys(checks).length}))
