import {test} from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import os from 'node:os'
import path from 'node:path'
import {randomUUID} from 'node:crypto'
import {createProjectOrganization} from '../.agents/skills/minecraft-nbt-modeler/assets/viewer/project-organization.mjs'
import {organizationKind,organizationKey} from '../.agents/skills/minecraft-nbt-modeler/assets/viewer/src/project-organization.js'
test('menus persist per workspace, protect concurrent writes, and classify independently of files',async t=>{
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'nbt-menus-'));t.after(()=>fs.rm(root,{recursive:true,force:true}));const store=createProjectOrganization(root),id=randomUUID(),data=await store.read();data.menus.push({id,name:'城堡素材'});data.assignments['model:single/01/v1/master.json.gz']={kind:'effect',menu:id};const saved=await store.save(data);assert.equal(saved.revision,1);assert.deepEqual(await createProjectOrganization(root).read(),saved);await assert.rejects(store.save(data),/变化/);assert.equal(organizationKind({relative_path:'single/01/v1/master.json.gz'},saved),'effect');assert.equal(organizationKind({relative_path:'effects/sample/master.json.gz'},saved),'effect');assert.equal(organizationKind({relative_path:'single/hall/v1/master.json.gz'},saved),'building');assert.equal(organizationKind({effect_file:{name:'foo.json'}},saved),'effect');assert.deepEqual((await createProjectOrganization(path.join(root,'other')).read()).menus,[])
 const bad=structuredClone(saved);bad.assignments['model:../escape']={kind:'building',menu:''};await assert.rejects(store.save(bad));const duplicate=structuredClone(saved);duplicate.menus.push({id:randomUUID(),name:'城堡素材'});await assert.rejects(store.save(duplicate));assert.equal((await store.read()).revision,1)
})

test('classification and menu identity group saved versions of the same object',()=>{const first={object_key:'["project","square","城堡"]',relative_path:'square/castle/v1/master.json.gz'},second={...first,relative_path:'square/castle/v2/master.json.gz'};assert.equal(organizationKey(first),organizationKey(second));const data={assignments:{[organizationKey(first)]:{kind:'effect',menu:'demo'}}};assert.equal(organizationKind(second,data),'effect')})
