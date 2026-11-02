import fs from 'node:fs/promises'
import path from 'node:path'
import {createHash} from 'node:crypto'
import {root} from './paths.mjs'
const base=path.join(root,'references/saodg-2026-11-02')
const manifest=JSON.parse(await fs.readFile(path.join(base,'manifest.json'),'utf8'))
for(const file of manifest.files){const bytes=await fs.readFile(path.join(base,file.path));if(createHash('sha256').update(bytes).digest('hex')!==file.sha256)throw Error('Reference changed: '+file.path)}
const verification=JSON.parse(await fs.readFile(path.join(root,'references/archive-verification.json'),'utf8'))
const zip=await fs.readFile(path.join(root,'references/saodg-2026-11-02.zip'))
if(createHash('sha256').update(zip).digest('hex')!==verification.archive_sha256)throw Error('Reference ZIP changed')
console.log(JSON.stringify({passed:true,files:manifest.files.length,zip_sha256:verification.archive_sha256}))
