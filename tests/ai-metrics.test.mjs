import {test} from 'node:test'
import assert from 'node:assert/strict'
import {cleanApiMetrics,cleanTimings} from '../.agents/skills/minecraft-nbt-modeler/assets/viewer/ai-metrics.mjs'
test('diagnostic persistence strips payloads, arbitrary strings, invalid timings and excess attempts',()=>{
 const cleaned=cleanApiMetrics({attempts:2,prepare_ms:-1,service_total_ms:20,finish_reason:'secret',headers:{Authorization:'Bearer secret'},response:'private',calls:Array.from({length:5},()=>({attempt:1,status:'complete',headers_ms:10,read_ms:Infinity,elapsed_ms:20,request_bytes:100,body:'private',url:'private',finish_reason:'secret'}))})
 assert.equal(cleaned.calls.length,3);assert.equal(cleaned.prepare_ms,undefined);assert.equal(cleaned.finish_reason,undefined);assert.equal(cleaned.calls[0].read_ms,undefined);assert.equal(cleaned.calls[0].headers_ms,10)
 assert.ok(!JSON.stringify(cleaned).includes('private'));assert.ok(!JSON.stringify(cleaned).includes('secret'))
 assert.deepEqual(cleanTimings({capture_ms:30,preview_ms:40,request_total_ms:86400001,raw:'private'}),{capture_ms:30,preview_ms:40})
 for(const value of [null,undefined,1,'bad',[]])assert.equal(cleanApiMetrics(value),undefined)
 assert.doesNotThrow(()=>cleanApiMetrics({calls:[null,{},'bad']}))
 const reasoning=cleanApiMetrics({reasoning_tokens:10,reasoning_content:'private',calls:[{reasoning_tokens:10,reasoning_content:'private'},{reasoning_tokens:-1}]})
 assert.equal(reasoning.reasoning_tokens,10);assert.equal(reasoning.calls[0].reasoning_tokens,10);assert.equal(reasoning.calls[1].reasoning_tokens,undefined);assert.ok(!JSON.stringify(reasoning).includes('private'))
 const validation=cleanApiMetrics({calls:[{validation_status:'failed',validation_issue:{code:'invalid_classification',step:1,field:'classification',received:'structure',raw:'private'}},{validation_issue:{code:'private'}},{validation_status:'private',validation_issue:{code:'invalid_result',field:'Authorization',received:'Bearer secret'}}]})
 assert.deepEqual(validation.calls[0].validation_issue,{code:'invalid_classification',step:1,field:'classification',received:'structure'});assert.equal(validation.calls[1].validation_issue,undefined);assert.ok(!JSON.stringify(validation).includes('private'));assert.ok(!JSON.stringify(validation).includes('secret'))
})
