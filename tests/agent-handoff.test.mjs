import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import os from 'node:os'
import path from 'node:path'
import {handoffInfo,writeHandoff} from '../.agents/skills/minecraft-nbt-modeler/assets/viewer/agent-handoff.mjs'

test('review discovery never associates a different source or stale version',async t=>{
  const workspace=await fs.mkdtemp(path.join(os.tmpdir(),'nbt-handoff-'))
  t.after(()=>fs.rm(workspace,{recursive:true,force:true}))
  const info={workdir:workspace,source:path.join(workspace,'source.master.json.gz'),source_sha256:'current'}
  const empty=await handoffInfo(info)
  assert.equal(empty.review,'')
  await assert.rejects(fs.access(empty.directory))
  async function review(name,source,hash){const dir=path.join(empty.directory,'review-'+name);await fs.mkdir(dir,{recursive:true});await fs.writeFile(path.join(dir,'review.json'),JSON.stringify({source,source_sha256:hash}));return dir}
  const expected=await review('valid',info.source,'current')
  await review('stale',info.source,'previous')
  await review('other',path.join(workspace,'other.master.json.gz'),'current')
  assert.equal((await handoffInfo(info)).review,expected)
  assert.equal((await handoffInfo({...info,source_sha256:'new'})).review,'')
})

test('handoff is portable, preserves requests and does not invent approval',async t=>{
  const workspace=await fs.mkdtemp(path.join(os.tmpdir(),'nbt-handoff-'))
  t.after(()=>fs.rm(workspace,{recursive:true,force:true}))
  const workdir=path.join(workspace,'nbt_models','building'),directory=path.join(workdir,'Agent交接','plan-test')
  await fs.mkdir(directory,{recursive:true})
  const requestFile=path.join(workspace,'request.json'),bytes='{"source":"nbt_models/building/source.master.json.gz","path_base":"workspace"}'
  await fs.writeFile(requestFile,bytes)
  const args={workspace,info:{workdir,source:path.join(workdir,'source.master.json.gz')},request:{source_sha256:'source-hash',context:path.join(workdir,'coordinates.json')},result:{bundle:path.join(directory,'bundle.json'),plan:path.join(directory,'plan.json')},requestFile}
  const result=await writeHandoff(args)
  assert.ok(result.handoff_text.includes('nbt_models/building/source.master.json.gz'))
  assert.ok(result.handoff_text.includes('保留原文件'))
  assert.equal(await fs.readFile(path.join(directory,'request.json'),'utf8'),bytes)
  assert.equal(await fs.readFile(result.handoff_file,'utf8'),result.handoff_text)
  assert.equal(result.handoff_text.includes(workspace),false)
  await assert.rejects(fs.access(path.join(directory,'approval.json')))
  await assert.rejects(writeHandoff(args),{code:'EEXIST'})
  assert.equal(await fs.readFile(result.handoff_file,'utf8'),result.handoff_text)
})
