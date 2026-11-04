import {test} from 'node:test'
import assert from 'node:assert/strict'
import {workerExit,parseWorkerResult} from '../.agents/skills/minecraft-nbt-modeler/assets/viewer/backend-result.mjs'
test('empty native worker exit retains numeric status without blaming provider JSON',()=>{
 const exit=workerExit({phase:'preview',pid:123,code:-1073741502,stdout:'',stderr:''});assert.equal(exit.exit_hex,'0xc0000142');assert.equal(exit.stdout_bytes,0);assert.throws(()=>parseWorkerResult('',exit),/本地建模进程未返回结果.*0xc0000142/);assert.equal(exit.exit_code,-1073741502)
})
test('malformed worker output reports bounded byte counts without exposing request data',()=>{
 const raw='{"private-key":"secret-';const exit=workerExit({phase:'snapshot',code:0,stdout:raw,stderr:'private request'});assert.throws(()=>parseWorkerResult(raw,exit),error=>!error.message.includes('secret')&&/格式无效/.test(error.message));assert.equal(JSON.stringify(exit).includes('private'),false)
})
test('normal protocol and validation failure envelopes preserve their exact fields',()=>{
 const data={ok:true,result:{status:'candidate_failed',passed:false}},raw=JSON.stringify(data),exit=workerExit({phase:'validate',code:1,stdout:raw});assert.deepEqual(parseWorkerResult(raw,exit),data);assert.equal(workerExit({phase:'preview',code:null,signal:'SIGTERM'}).signal,'SIGTERM')
})
