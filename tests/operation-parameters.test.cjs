const {test}=require('node:test'),assert=require('node:assert/strict')
const {validateOperation}=require('../desktop/operation-parameters.cjs')
test('mode requirements and nested coordinates reject invalid model parameters',()=>{
 const op={kind:'array_region',lo:[0,0,0],hi:[2,2,2],mode:'radial',centre:[10,2,10],radius:4,count:8}
 validateOperation(op)
 for(const patch of [{radius:0},{count:true},{centre:[1,2]},{mode:'path'},{mode:'constructor'}])assert.throws(()=>validateOperation({...op,...patch}))
 const anchor={kind:'align_region',lo:[0,0,0],hi:[2,2,2],mode:'anchor',source_anchor:[0,0,0],target_anchor:[4,0,0]}
 validateOperation(anchor);assert.throws(()=>validateOperation({...anchor,target_anchor:[true,0,0]}))
})

test('section geometry nested contract checks required fields and unknown keys',()=>{
 const base={kind:'geometry',lo:[0,0,0],hi:[15,15,15]},geometry={shape:'section_sweep',vertices:[[-1,-1],[1,-1],[1,1]],points:[[2,4,2],[10,4,2]]}
 validateOperation({...base,geometry})
 for(const patch of [{points:[[1,2],[3,4]]},{vertices:[[0,0],[1,1]]},{script:'x'}])assert.throws(()=>validateOperation({...base,geometry:{...geometry,...patch}}))
})
