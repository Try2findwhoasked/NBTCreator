import fs from 'node:fs/promises'
import path from 'node:path'
import assert from 'node:assert/strict'
import {parseArgs} from 'node:util'
import {savedEffects} from './saved-effects.mjs'
const {values}=parseArgs({options:{output:{type:'string'}}})
if(!values.output)throw new Error('Provide --output new-directory')
const out=path.resolve(values.output);await fs.mkdir(out)
const skill=path.join(out,'skill');await fs.mkdir(skill)
const initial=path.join(out,'first'),target=path.join(out,'自选效果目录')
const create=()=>savedEffects({workspace:out,skillRoot:skill,initial})
const store=create();assert.equal(await store.init(),initial)
await store.set(target);assert.equal(await create().init(),target)
const request={settings:{strength:50},source:'SYNTHETIC ONLY'}
const a=await store.save(request,'苔痕方案'),b=await store.save(request,'苔痕方案')
assert.notEqual(a.path,b.path);assert.deepEqual(JSON.parse(await fs.readFile(a.path)),request)
const scan=await store.scan();assert.equal(scan.files.length,2)
const refs=await store.references([scan.files[0].id]);assert.ok(refs[0].sha256);assert.ok(refs[0].path.startsWith(target))
await assert.rejects(()=>store.references(['unknown']))
await fs.appendFile(scan.files[0].path,'changed');await assert.rejects(()=>store.references([scan.files[0].id]))
await assert.rejects(()=>store.set(skill));await assert.rejects(()=>store.save(request,'../escape'))
await store.set(initial);await store.scan();await assert.rejects(()=>store.references([scan.files[0].id]))
await fs.writeFile(path.join(out,'results.json'),JSON.stringify({passed:true,checks:8},null,2))
console.log(JSON.stringify({passed:true,checks:8}))
