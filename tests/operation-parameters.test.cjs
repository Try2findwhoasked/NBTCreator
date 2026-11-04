const {test}=require('node:test'),assert=require('node:assert/strict')
const {validateOperation}=require('../desktop/operation-parameters.cjs')
test('mode requirements and nested coordinates reject invalid model parameters',()=>{
 const op={kind:'array_region',lo:[0,0,0],hi:[2,2,2],mode:'radial',centre:[10,2,10],radius:4,count:8}
 validateOperation(op)
 for(const patch of [{radius:0},{count:true},{centre:[1,2]},{mode:'path'},{mode:'constructor'}])assert.throws(()=>validateOperation({...op,...patch}))
 const anchor={kind:'align_region',lo:[0,0,0],hi:[2,2,2],mode:'anchor',source_anchor:[0,0,0],target_anchor:[4,0,0]}
 validateOperation(anchor);assert.throws(()=>validateOperation({...anchor,target_anchor:[true,0,0]}))
})
