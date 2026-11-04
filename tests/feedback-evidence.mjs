import fs from 'node:fs/promises'
import path from 'node:path'
import os from 'node:os'
import assert from 'node:assert/strict'
import {createHash} from 'node:crypto'
import {createFeedbackStore} from '../.agents/skills/minecraft-nbt-modeler/assets/viewer/feedback-store.mjs'

const sha=bytes=>createHash('sha256').update(bytes).digest('hex')
const temporary=await fs.mkdtemp(path.join(os.tmpdir(),'nbt-feedback-evidence-'))
try{
  const version=path.join(temporary,'nbt_models/single/test/v01'),master=path.join(version,'master')
  await fs.mkdir(master,{recursive:true})
  const source=path.join(master,'source.bin'),snapshot=path.join(temporary,'job-snapshot.json')
  await fs.writeFile(source,'synthetic master');await fs.writeFile(snapshot,'original synthetic snapshot')
  const binding={kind:'3d',source,version_dir:version,source_sha256:sha(await fs.readFile(source)),geometry_sha256:sha('same geometry'),snapshot,snapshot_sha256:sha(await fs.readFile(snapshot)),size:[48,12,48]}
  const store=createFeedbackStore(path.join(path.dirname(version),'修改意见'))
  const saved=await store.add(binding,'railing',null,[],[])
  const bytes=await fs.readFile(saved.file)
  const sidecar=JSON.parse(await fs.readFile(saved.file+'.evidence.json'))
  const snapshotEntry=sidecar.files.find(x=>x.role==='snapshot')
  assert.equal(sha(await fs.readFile(path.resolve(path.dirname(saved.file),snapshotEntry.path))),binding.snapshot_sha256)
  assert.equal(path.isAbsolute(snapshotEntry.path),false)
  const indexFile=path.join(version,'修改意见/评论索引.json')
  let index=JSON.parse(await fs.readFile(indexFile));assert.equal(index.records.length,1)
  assert.equal(index.records[0].notes[0].text,'railing')
  assert.equal(index.records[0].feedback_sha256,sha(bytes))
  await fs.unlink(snapshot)
  const newSnapshot=path.join(temporary,'reopened-snapshot.json')
  await fs.writeFile(newSnapshot,'a new snapshot of same geometry with different cameras')
  const reopened={...binding,snapshot:newSnapshot,snapshot_sha256:sha(await fs.readFile(newSnapshot))}
  await store.update(reopened,saved.notes[0].id,'resolved')
  const preserved=JSON.parse(await fs.readFile(saved.file+'.evidence.json'))
  assert.equal(preserved.files.find(x=>x.role==='snapshot').sha256,binding.snapshot_sha256)
  await store.export(reopened)
  index=JSON.parse(await fs.readFile(indexFile))
  assert.equal(index.records[0].notes[0].status,'resolved')
  assert.equal(index.records[0].feedback_sha256,sha(await fs.readFile(saved.file)))
  assert.equal(JSON.parse(await fs.readFile(saved.file)).binding.snapshot_sha256,binding.snapshot_sha256)
  console.log(JSON.stringify({passed:true,checks:11,scope:'version index and immutable old snapshot after cache deletion/reopen'}))
}finally{
  // Only the literal temporary fixture allocated above, never authoring assets.
  await fs.rm(temporary,{recursive:true,force:true})
}
