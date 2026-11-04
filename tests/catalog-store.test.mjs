import {test} from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import os from 'node:os'
import path from 'node:path'
import {createCatalogStore} from '../.agents/skills/minecraft-nbt-modeler/assets/viewer/catalog-store.mjs'

test('cached catalog is immediately reusable, portable and explicitly refreshed',async t=>{
 const workspace=await fs.mkdtemp(path.join(os.tmpdir(),'nbt-catalog-'));t.after(()=>fs.rm(workspace,{recursive:true,force:true}))
 let scans=0
 const scan=async()=>({models:[{source:path.join(workspace,'nbt_models/room.nbt'),context:path.join(workspace,'nbt_models/context.json'),project_key:'',project_name:'old'}],scanned:++scans})
 const first=createCatalogStore({workspace,scan});assert.equal((await first.initial()).cached,false)
 const cached=JSON.parse(await fs.readFile(path.join(workspace,'.nbtcreator/cache/project-catalog.json'),'utf8'));assert.equal(cached.catalog.models[0].source,'nbt_models/room.nbt')
 const second=createCatalogStore({workspace,scan});const value=await second.initial();assert.equal(value.cached,true);assert.equal(scans,1);assert.equal(value.catalog.models[0].source,path.join(workspace,'nbt_models/room.nbt'))
 await second.refresh();assert.equal(scans,2)
 const moved=await fs.mkdtemp(path.join(os.tmpdir(),'nbt-moved-'));t.after(()=>fs.rm(moved,{recursive:true,force:true}));await fs.cp(path.join(workspace,'.nbtcreator'),path.join(moved,'.nbtcreator'),{recursive:true})
 const relocated=await createCatalogStore({workspace:moved,scan:()=>{throw Error('cache should load first')}}).initial();assert.equal(relocated.catalog.models[0].source,path.join(moved,'nbt_models/room.nbt'));assert.equal(relocated.catalog.models[0].project_name,path.basename(moved))
})
test('concurrent refreshes share a scan, and failed scans can be retried',async t=>{
 const workspace=await fs.mkdtemp(path.join(os.tmpdir(),'nbt-catalog-race-'));t.after(()=>fs.rm(workspace,{recursive:true,force:true}))
 let scans=0,release;const gate=new Promise(resolve=>release=resolve)
 const store=createCatalogStore({workspace,scan:async()=>{scans++;await gate;return {models:[]}}})
 const one=store.refresh(),two=store.refresh();release();await Promise.all([one,two]);assert.equal(scans,1)
 let attempts=0;const retry=createCatalogStore({workspace,scan:async()=>{if(!attempts++)throw Error('scan failed');return {models:[]}}})
 await assert.rejects(retry.refresh(),/scan failed/);assert.equal((await retry.refresh()).models.length,0)
})
test('opened model metadata survives refresh until the file stamp changes',async t=>{
 const workspace=await fs.mkdtemp(path.join(os.tmpdir(),'nbt-index-stamp-'));t.after(()=>fs.rm(workspace,{recursive:true,force:true}))
 const source=path.join(workspace,'nbt_models/room.nbt');let modified_ns=1
 const store=createCatalogStore({workspace,scan:async()=>({models:[{source,unverified:true,modified_ns,file_size:50}]})})
 await store.initial();await store.record({source,geometry_sha256:'verified',size:[12,8,12]})
 assert.equal((await store.refresh()).models[0].geometry_sha256,'verified')
 modified_ns=2;assert.equal((await store.refresh()).models[0].unverified,true)
})
