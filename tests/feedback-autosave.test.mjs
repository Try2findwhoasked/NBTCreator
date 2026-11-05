import {test} from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import os from 'node:os'
import path from 'node:path'
import {createHash,randomUUID} from 'node:crypto'
import {createFeedbackStore} from '../.agents/skills/minecraft-nbt-modeler/assets/viewer/feedback-store.mjs'
import {createFeedbackAutosave} from '../.agents/skills/minecraft-nbt-modeler/assets/viewer/src/feedback-autosave.js'
const sha=v=>createHash('sha256').update(v).digest('hex')
async function fixture(t){const root=await fs.mkdtemp(path.join(os.tmpdir(),'nbt-feedback-auto-'));t.after(()=>fs.rm(root,{recursive:true,force:true}));const version=path.join(root,'nbt_models/single/测试/v01'),source=path.join(version,'master/source.json'),image=path.join(version,'preview.png');await fs.mkdir(path.dirname(source),{recursive:true});await fs.writeFile(source,'source');await fs.writeFile(image,'image');return {root,version,source,image,binding:{workdir:path.dirname(version),version_dir:version,source,image,source_sha256:sha('source'),image_sha256:sha('image'),geometry_sha256:sha('geometry')}}}
test('autosave revises one formal note, retries idempotently and rejects stale writes',async t=>{
 const f=await fixture(t),store=createFeedbackStore(b=>path.join(b.version_dir,'修改意见')),id=randomUUID(),input={note_id:id,expected_revision:0,text:'第一稿',anchors:[],references:[]}
 let record=await store.upsert(f.binding,input);assert.equal(record.notes.length,1);assert.ok(record.file.startsWith(f.version+path.sep));assert.equal(record.notes[0].revision,1)
 record=await store.upsert(f.binding,{...input,expected_revision:1,text:'修改后的同一条'});assert.equal(record.notes.length,1);assert.equal(record.notes[0].revision,2)
 const before=await fs.readFile(record.file);record=await store.upsert(f.binding,{...input,text:'修改后的同一条'});assert.deepEqual(await fs.readFile(record.file),before)
 await assert.rejects(()=>store.upsert(f.binding,{...input,expected_revision:1,text:'过时的覆盖'}),e=>e.code==='feedback_conflict')
 assert.equal((await store.list(f.binding)).notes[0].text,'修改后的同一条');assert.equal(await fs.readFile(f.source,'utf8'),'source')
 const index=JSON.parse(await fs.readFile(path.join(f.version,'修改意见/评论索引.json'),'utf8'));assert.equal(index.records[0].notes[0].text,'修改后的同一条')
})
test('same geometry in another version has a separate formal note directory',async t=>{
 const f=await fixture(t),store=createFeedbackStore(b=>path.join(b.version_dir,'修改意见'));await store.upsert(f.binding,{note_id:randomUUID(),expected_revision:0,text:'只属于 v01',anchors:[]})
 const version=path.join(path.dirname(f.version),'v02'),source=path.join(version,'master/source.json');await fs.mkdir(path.dirname(source),{recursive:true});await fs.copyFile(f.source,source)
 const binding={...f.binding,version_dir:version,source};assert.equal((await store.list(binding)).notes.length,0)
 const second=await store.upsert(binding,{note_id:randomUUID(),expected_revision:0,text:'只属于 v02',anchors:[]});assert.ok(second.file.startsWith(version+path.sep));assert.equal((await store.list(f.binding)).notes[0].text,'只属于 v01')
})
test('legacy notes migrate on edit without deleting originals or duplicating the version index',async t=>{
 const f=await fixture(t),legacy=path.join(f.binding.workdir,'修改意见'),old=createFeedbackStore(legacy),record=await old.add(f.binding,'旧标注',{x:.2,y:.5}),original=await fs.readFile(record.file)
 const store=createFeedbackStore(b=>path.join(b.version_dir,'修改意见'),()=>[legacy]);assert.equal((await store.list(f.binding)).notes.length,1)
 const updated=await store.upsert(f.binding,{note_id:record.notes[0].id,expected_revision:0,text:'在当前版本内更新',anchors:[{kind:'image',number:1,x:.2,y:.5}],references:[]})
 assert.ok(updated.file.startsWith(f.version+path.sep));assert.deepEqual(await fs.readFile(record.file),original)
 const index=JSON.parse(await fs.readFile(path.join(f.version,'修改意见/评论索引.json'),'utf8'));assert.equal(index.records.length,1);assert.ok(!index.records[0].feedback_file.includes('..'))
})
test('legacy shared hash directories do not leak notes into another identical-content version',async t=>{
 const f=await fixture(t),legacy=path.join(f.binding.workdir,'修改意见'),old=createFeedbackStore(legacy);await old.add(f.binding,'只属于原版的旧标注')
 const version=path.join(path.dirname(f.version),'v02'),source=path.join(version,'master/source.json');await fs.mkdir(path.dirname(source),{recursive:true});await fs.copyFile(f.source,source)
 const store=createFeedbackStore(b=>path.join(b.version_dir,'修改意见'),()=>[legacy]);assert.equal((await store.list({...f.binding,source,version_dir:version})).notes.length,0);assert.equal((await store.list(f.binding)).notes.length,1)
})
test('two stores cannot silently overwrite a concurrently edited note',async t=>{
 const f=await fixture(t),a=createFeedbackStore(b=>path.join(b.version_dir,'修改意见')),b=createFeedbackStore(x=>path.join(x.version_dir,'修改意见')),id=randomUUID();await a.upsert(f.binding,{note_id:id,expected_revision:0,text:'原文',anchors:[]})
 const updates=await Promise.allSettled([a.upsert(f.binding,{note_id:id,expected_revision:1,text:'窗口一',anchors:[]}),b.upsert(f.binding,{note_id:id,expected_revision:1,text:'窗口二',anchors:[]})]);assert.equal(updates.filter(r=>r.status==='fulfilled').length,1);assert.equal(updates.find(r=>r.status==='rejected').reason.code,'feedback_conflict')
})
test('queued typing uses one ID and the next server revision while a save is in flight',async()=>{
 const id=randomUUID();let text='第一稿',release,started;const begin=new Promise(r=>started=r),gate=new Promise(r=>release=r),calls=[],notes=new Map()
 const controller=createFeedbackAutosave({eventTarget:new EventTarget(),capture:()=>({target_id:'view',target_key:'version',note_id:id,expected_revision:0,text,anchors:[],references:[]}),save:async p=>{calls.push(p);if(calls.length===1){started();await gate}const note={id,revision:(notes.get(id)?.revision??0)+1,text:p.text};notes.set(id,note);return {notes:[note]}}})
 const first=controller.flush();await begin;text='连续修改';controller.schedule();release();await first;await controller.flush();assert.equal(calls.length,2);assert.equal(calls[1].expected_revision,1);assert.equal(notes.size,1);assert.equal(notes.get(id).text,'连续修改');controller.dispose()
})
test('IME composition is saved only after compositionend',async()=>{
 const id=randomUUID(),calls=[];let text='';const controller=createFeedbackAutosave({eventTarget:new EventTarget(),capture:()=>text?{target_id:'v',note_id:id,text,anchors:[],references:[]}:null,save:async p=>{calls.push(p);return {notes:[{id,revision:calls.length}]}}})
 controller.composition(true);text='中间拼音';controller.schedule();await controller.flush();assert.equal(calls.length,0);text='完整中文标注';controller.composition(false);await controller.flush();assert.equal(calls.length,1);assert.equal(calls[0].text,text);controller.dispose()
})
test('a final close-time write arriving first cannot be replaced by its older in-flight request',async t=>{
 const f=await fixture(t),store=createFeedbackStore(b=>path.join(b.version_dir,'修改意见')),id=randomUUID(),client_id=randomUUID(),base={note_id:id,expected_revision:0,client_id,anchors:[]}
 await store.upsert(f.binding,{...base,sequence:2,text:'关闭前的最新内容'});await store.upsert(f.binding,{...base,sequence:1,text:'更早的请求'})
 assert.equal((await store.list(f.binding)).notes[0].text,'关闭前的最新内容')
 await store.upsert(f.binding,{...base,sequence:3,text:'同一会话继续编辑'});assert.equal((await store.list(f.binding)).notes[0].revision,2)
})
