import fs from 'node:fs/promises'
import path from 'node:path'
import os from 'node:os'
import {spawnSync} from 'node:child_process'
import electron from 'electron'
const env={...process.env};delete env.ELECTRON_RUN_AS_NODE
const probe=spawnSync(electron,['--version'],{env,encoding:'utf8',windowsHide:true,timeout:30000}),result={platform:process.platform,os:os.release(),electron,exists:await fs.stat(electron).then(()=>true,()=>false),status:probe.status,signal:probe.signal,error:probe.error?.message,stdout:probe.stdout,stderr:probe.stderr}
const folder=path.resolve('build/electron-launch');await fs.mkdir(folder,{recursive:true});await fs.writeFile(path.join(folder,'results.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));if(probe.error||probe.status!==0)process.exitCode=1
