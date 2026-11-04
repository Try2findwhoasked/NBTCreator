import {test} from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import os from 'node:os'
import path from 'node:path'
import {createCommandStore} from '../.agents/skills/minecraft-nbt-modeler/assets/viewer/command-store.mjs'
import {commandDefinitions,defaultPreferences,validateCommandPreferences,normalizeShortcut,eventShortcut,searchCommands} from '../.agents/skills/minecraft-nbt-modeler/assets/viewer/src/command-contract.mjs'
const catalog=JSON.parse(await fs.readFile(new URL('../.agents/skills/minecraft-nbt-modeler/tool-catalog.json',import.meta.url),'utf8')),commands=commandDefinitions(catalog)
test('commands derive every modelling kind from the shared catalogue; search prefers favorite then recent without duplicates',()=>{
 assert.deepEqual(commands.filter(c=>c.kind).map(c=>c.kind),Object.keys(catalog.tools));assert.equal(new Set(commands.map(c=>c.id)).size,commands.length)
 const p={favorites:['panel.4'],shortcuts:{},recent:['workspace.assets','panel.4']},found=searchCommands(commands,p);assert.equal(found[0].id,'panel.4');assert.equal(found[1].id,'workspace.assets');assert.equal(new Set(found.map(c=>c.id)).size,commands.length);assert.equal(searchCommands(commands,p,'建模工具步骤 box')[0].id,'operation.box');assert.deepEqual(searchCommands(commands,p,'nothing-matches-xyz'),[])
})
test('shortcut normalization, duplicates, system bindings and non-data command fields are rejected',()=>{
 assert.equal(normalizeShortcut('Shift+Ctrl+k'),'Ctrl+Shift+KeyK');assert.equal(eventShortcut({code:'KeyK',ctrlKey:true}),'Ctrl+KeyK');assert.equal(eventShortcut({code:'KeyK',ctrlKey:true,isComposing:true}),null);assert.equal(eventShortcut({code:'KeyW'}),null);assert.equal(eventShortcut({code:'KeyK',ctrlKey:true,repeat:true}),null)
 const draft=(id,key)=>({...defaultPreferences(),shortcuts:{[id]:key}})
 for(const key of ['F11','F5','Ctrl+KeyC','Ctrl+KeyZ','Alt+F4','Ctrl+Enter','KeyW','Ctrl+Shift+KeyI','Ctrl+Digit0'])assert.throws(()=>validateCommandPreferences(draft('panel.4',key),commands))
 assert.throws(()=>validateCommandPreferences(draft('panel.4','Ctrl+KeyK'),commands),/冲突/);assert.throws(()=>validateCommandPreferences({...defaultPreferences(),favorites:['run.shell']},commands));assert.throws(()=>validateCommandPreferences({...defaultPreferences(),execute:'arbitrary'},commands));assert.equal(validateCommandPreferences(draft('edit.undo',''),commands).shortcuts['edit.undo'],'');assert.equal(validateCommandPreferences(draft('panel.4','Alt+KeyL'),commands).shortcuts['panel.4'],'Alt+KeyL')
})
test('workspace command choices survive restart, remain independent and reject stale writers',async t=>{
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'nbt-commands-'));t.after(()=>fs.rm(root,{recursive:true,force:true}));const one=path.join(root,'one'),two=path.join(root,'two');await fs.mkdir(one);await fs.mkdir(two);const a=createCommandStore(one,catalog),b=createCommandStore(one,catalog),other=createCommandStore(two,catalog);assert.equal((await a.read()).revision,0)
 const preferences={favorites:['panel.4'],shortcuts:{'panel.4':'Alt+KeyL'},recent:['operation.box']};await a.save({expected_revision:0,preferences});assert.deepEqual((await b.read()).preferences,preferences);assert.deepEqual((await other.read()).preferences,defaultPreferences());await assert.rejects(b.save({expected_revision:0,preferences}),/另一窗口/)
 const attempts=await Promise.allSettled([a.save({expected_revision:1,preferences:{...preferences,favorites:[]}}),b.save({expected_revision:1,preferences:{...preferences,recent:[]}})]);assert.equal(attempts.filter(r=>r.status==='fulfilled').length,1);assert.equal((await a.read()).revision,2);assert.equal((await fs.readdir(path.join(one,'.nbtcreator'))).length,1)
 await assert.rejects(a.save({expected_revision:2,preferences:{...preferences,paths:['secret']}}));const saved=JSON.parse(await fs.readFile(path.join(one,'.nbtcreator/commands.json'),'utf8'));assert.deepEqual(Object.keys(saved).sort(),['preferences','revision','schema_version']);assert.ok(!JSON.stringify(saved).includes(root))
})
