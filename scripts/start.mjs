import {spawn} from 'node:child_process'
import electron from 'electron'
import {root} from './paths.mjs'
const env={...process.env,NBTCREATOR_AGENT_CWD:process.env.NBTCREATOR_AGENT_CWD||process.env.INIT_CWD||process.cwd()};delete env.ELECTRON_RUN_AS_NODE
const child=spawn(electron,[root,...process.argv.slice(2)],{cwd:env.NBTCREATOR_AGENT_CWD,env,stdio:'inherit',windowsHide:true,shell:false})
child.on('error',error=>{console.error(error.message);process.exitCode=1})
child.on('exit',code=>process.exitCode=code??1)
