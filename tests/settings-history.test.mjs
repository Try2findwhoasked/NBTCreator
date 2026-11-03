import {test} from 'node:test'
import assert from 'node:assert/strict'
import {createSettingsHistory} from '../.agents/skills/minecraft-nbt-modeler/assets/viewer/src/settings-history.mjs'
test('history coalesces typing, restores immutable snapshots and truncates only the redo branch',()=>{
 const h=createSettingsHistory(),s={operations:[],strength:100};h.reset(s)
 h.record({...s,strength:101},'强度',{group:'strength',now:1000});h.record({...s,strength:102},'强度',{group:'strength',now:1100});assert.equal(h.entries.length,2)
 h.record({...s,strength:102,operations:[{label:'柱'}]},'添加柱',{now:1200});assert.equal(h.entries.length,3)
 const restored=h.travel(-1);restored.operations.push({label:'外部修改'});assert.deepEqual(h.current().operations,[]);assert.equal(h.travel(1).operations[0].label,'柱')
 h.travel(-1);h.rename(1,'候选 A');assert.equal(h.entries[1].label,'候选 A');h.record({...s,strength:120},'候选 B',{now:1300});assert.equal(h.entries.length,3);assert.equal(h.entries[1].label,'候选 A');assert.equal(h.travel(1),null)
 h.reset(s);assert.equal(h.entries.length,1);assert.equal(h.travel(-1),null)
})
test('history bounds memory and count without losing the immediate undo state',()=>{
 const h=createSettingsHistory({limit:4,byteLimit:180});h.reset({text:'a'.repeat(100)})
 for(let i=0;i<10;i++)h.record({text:'x'.repeat(100)+i},'step '+i)
 assert.equal(h.entries.length,2);assert.equal(h.travel(-1).text,'x'.repeat(100)+'8');assert.equal(h.travel(1).text,'x'.repeat(100)+'9')
 const count=createSettingsHistory({limit:4});count.reset({n:0});for(let i=1;i<10;i++)count.record({n:i},String(i));assert.equal(count.entries.length,4);assert.equal(count.cursor,3)
 assert.throws(()=>count.rename(0,''));assert.throws(()=>count.rename(0,'a'.repeat(161)))
})
