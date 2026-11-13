import {packager} from '@electron/packager'
import fs from 'node:fs/promises'
import path from 'node:path'
import {root,python} from './paths.mjs'
import {execFileSync} from 'node:child_process'
import {buildWeb} from './build-web.mjs'
execFileSync(process.execPath,[path.join(root,'scripts/sync-capabilities.mjs'),'--check'],{stdio:'inherit'})
execFileSync(python,[path.join(root,'scripts/build-starter-effects.py'),'--check'],{stdio:'inherit',windowsHide:true})
await buildWeb()
const outIndex=process.argv.indexOf('--out')
const output=path.resolve(root,outIndex>=0?process.argv[outIndex+1]:'dist');await fs.mkdir(output,{recursive:true})
let electronZipDir
try{await fs.access(path.join(root,'build/downloads/electron-v45.2.1-win32-x64.zip'));electronZipDir=path.join(root,'build/downloads')}catch{}
const paths=await packager({dir:root,out:output,name:'NBTCreator',platform:'win32',arch:'x64',asar:false,overwrite:false,
  electronZipDir,
  ignore:[/^\/\.github(?:\/|$)/,/^\/\.git(?:\/|$)/,/(?:^|\/)(?:\.env(?:\.[^\/]*)?|api-settings\.json)(?:$|\/)/,/^\/references(?:\/|$)/,/^\/video_projects(?:\/|$)/,/^\/build(?:\/|$)/,/^\/logs(?:\/|$)/,/\.log$/,/^\/dist(?:\/|$)/,/^\/workspace(?:\/|$)/,/^\/nbt_models(?:\/|$)/,/^\/\.nbtcreator(?:\/|$)/,/^\/\.agents\/skills\/(?!minecraft-nbt-modeler(?:\/|$))/,/^\/tests(?:\/|$)/,/\/assets\/viewer\/node_modules\/vite(?:\/|$)/,/__pycache__/,/\.pyc$/,/\/\.vite(?:\/|$)/],
  prune:true,appVersion:JSON.parse(await fs.readFile(path.join(root,'package.json'),'utf8')).version,executableName:'NBTCreator',win32metadata:{CompanyName:'NBTCreator',FileDescription:'Minecraft NBT authoring workbench'}})
// Electron Packager omits lockfiles by default. The exported standalone Skill
// needs this particular lock to offer a reproducible fallback dependency install.
for(const app of paths)await fs.copyFile(path.join(root,'.agents/skills/minecraft-nbt-modeler/assets/viewer/package-lock.json'),path.join(app,'resources/app/.agents/skills/minecraft-nbt-modeler/assets/viewer/package-lock.json'))
console.log(JSON.stringify({outputs:paths,python_bundled:false,stage:'application-directory'}))
