import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import path from 'node:path'
import os from 'node:os'
import {createAssetGroups} from '../../.agents/skills/minecraft-nbt-modeler/assets/viewer/asset-groups.mjs'

test('workspace asset folders keep source files in place and reject stale writes',async()=>{
 const workspace=await fs.mkdtemp(path.join(os.tmpdir(),'nbt-asset-groups-'))
 try{
  const source=path.join(workspace,'nbt_models/asset_library/patterns/example/pattern.png')
  await fs.mkdir(path.dirname(source),{recursive:true});await fs.writeFile(source,'unchanged')
  const store=createAssetGroups(workspace),id='00000000-0000-4000-8000-000000000001'
  assert.deepEqual(await store.read(),{revision:0,groups:[],assignments:{}})
  const saved=await store.save({revision:0,groups:[{id,kind:'patterns',name:'墙面'}],assignments:{'patterns:example':id}})
  assert.equal(saved.revision,1);assert.equal((await store.read()).assignments['patterns:example'],id)
  assert.equal(await fs.readFile(source,'utf8'),'unchanged')
  await assert.rejects(store.save({revision:0,groups:[],assignments:{}}),/已变化/)
  await assert.rejects(store.save({revision:1,groups:[{id,kind:'patterns',name:'墙面'}],assignments:{'effects:example':id}}),/归组记录无效/)
 }finally{if(workspace.startsWith(os.tmpdir()+path.sep))await fs.rm(workspace,{recursive:true,force:true})}
})
