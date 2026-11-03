import {test} from 'node:test'
import assert from 'node:assert/strict'
import {cleanApiMetrics,cleanTimings} from '../.agents/skills/minecraft-nbt-modeler/assets/viewer/ai-metrics.mjs'
test('diagnostic persistence strips payloads, arbitrary strings, invalid timings and excess attempts',()=>{
 const cleaned=cleanApiMetrics({attempts:2,prepare_ms:-1,service_total_ms:20,finish_reason:'secret',headers:{Authorization:'Bearer secret'},response:'private',calls:Array.from({length:5},()=>({attempt:1,status:'complete',headers_ms:10,read_ms:Infinity,elapsed_ms:20,request_bytes:100,body:'private',url:'private',finish_reason:'secret'}))})
 assert.equal(cleaned.calls.length,2);assert.equal(cleaned.prepare_ms,undefined);assert.equal(cleaned.finish_reason,undefined);assert.equal(cleaned.calls[0].read_ms,undefined);assert.equal(cleaned.calls[0].headers_ms,10)
 assert.ok(!JSON.stringify(cleaned).includes('private'));assert.ok(!JSON.stringify(cleaned).includes('secret'))
 assert.deepEqual(cleanTimings({capture_ms:30,preview_ms:40,request_total_ms:86400001,raw:'private'}),{capture_ms:30,preview_ms:40})
 for(const value of [null,undefined,1,'bad',[]])assert.equal(cleanApiMetrics(value),undefined)
 assert.doesNotThrow(()=>cleanApiMetrics({calls:[null,{},'bad']}))
})
