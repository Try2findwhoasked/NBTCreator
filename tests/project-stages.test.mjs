import {test} from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import os from 'node:os'
import path from 'node:path'
import {createProjectStages} from '../.agents/skills/minecraft-nbt-modeler/assets/viewer/project-stages.mjs'
test('manual creation status persists, is portable and expires when the source changes',async t=>{
 const workspace=await fs.mkdtemp(path.join(os.tmpdir(),'nbt-stage-'));t.after(()=>fs.rm(workspace,{recursive:true,force:true}))
 const source=path.join(workspace,'nbt_models/room.nbt');await fs.mkdir(path.dirname(source));await fs.writeFile(source,'original')
 const stat=await fs.stat(source,{bigint:true}),catalog={models:[{source,file_size:Number(stat.size),modified_ns:stat.mtimeNs.toString(),stage:'refined'}]},stages=createProjectStages(workspace)
 await stages.save(source,'finalized');let item=(await stages.apply(catalog)).models[0];assert.equal(item.stage,'finalized');assert.equal(item.stage_auto,'refined');assert.equal(item.stage_manual,true)
 const data=JSON.parse(await fs.readFile(path.join(workspace,'.nbtcreator/project-stages.json'),'utf8'));assert.deepEqual(Object.keys(data.stages),['room.nbt'])
 assert.equal((await stages.apply({models:[{...catalog.models[0],file_size:999}]})).models[0].stage,'refined')
 await stages.save(source,'discarded');assert.equal((await createProjectStages(workspace).apply(catalog)).models[0].stage,'discarded')
 await stages.save(source,'auto');assert.equal((await stages.apply(catalog)).models[0].stage,'refined')
 await assert.rejects(stages.save(path.join(workspace,'outside.nbt'),'finalized'),/当前建筑库/)
 await assert.rejects(stages.save(source,'approved'),/无效/);assert.equal(await fs.readFile(source,'utf8'),'original')
})

test("nanosecond strings keep the exact file version across millisecond rounding boundaries",async()=>{const {projectStampMatches}=await import("../.agents/skills/minecraft-nbt-modeler/assets/viewer/project-stages.mjs");const modified_ns="1763721405123000000",mark={bytes:10,modified_ms:1763721405123,modified_ns};assert.equal(projectStampMatches(mark,{file_size:10,modified_ns}),true);assert.equal(projectStampMatches(mark,{file_size:10,modified_ns:"1763721405123000100"}),false);assert.equal(projectStampMatches({bytes:10,modified_ms:1763721405123},{file_size:10,modified_ns}),true)})
