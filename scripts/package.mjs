import {packager} from '@electron/packager'
import fs from 'node:fs/promises'
import path from 'node:path'
import {root} from './paths.mjs'
import {execFileSync} from 'node:child_process'
execFileSync(process.execPath,[path.join(root,'scripts/sync-capabilities.mjs'),'--check'],{stdio:'inherit'})
const outIndex=process.argv.indexOf('--out')
const output=path.resolve(root,outIndex>=0?process.argv[outIndex+1]:'dist');await fs.mkdir(output,{recursive:true})
let electronZipDir
try{await fs.access(path.join(root,'build/downloads/electron-v45.2.1-win32-x64.zip'));electronZipDir=path.join(root,'build/downloads')}catch{}
const paths=await packager({dir:root,out:output,name:'NBTCreator',platform:'win32',arch:'x64',asar:false,overwrite:false,
  electronZipDir,
  ignore:[/^\/references(?:\/|$)/,/^\/build(?:\/|$)/,/^\/dist(?:\/|$)/,/^\/workspace(?:\/|$)/,/^\/nbt_models(?:\/|$)/,/^\/\.nbtcreator(?:\/|$)/,/^\/\.agents\/skills\/nbtcreator-workspace(?:\/|$)/,/^\/tests(?:\/|$)/,/__pycache__/,/\.pyc$/,/\/\.vite(?:\/|$)/],
  prune:true,appVersion:JSON.parse(await fs.readFile(path.join(root,'package.json'),'utf8')).version,executableName:'NBTCreator',win32metadata:{CompanyName:'NBTCreator',FileDescription:'NBT Creator migration prototype'}})
console.log(JSON.stringify({outputs:paths,python_bundled:false,stage:'migration-prototype'}))
