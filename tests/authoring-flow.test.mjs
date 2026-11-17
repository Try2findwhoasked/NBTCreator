import test from 'node:test'
import assert from 'node:assert/strict'
import {authoringFlow} from '../.agents/skills/minecraft-nbt-modeler/assets/viewer/src/authoring-flow.mjs'

const loaded={info:{source:'building.snbt'}}
test('stale previews cannot offer save even when an old check passed',()=>{
 const flow=authoringFlow({...loaded,preview:{},candidateValidation:{passed:true}},false)
 assert.equal(flow.canSave,false)
 assert.equal(flow.action,'update-preview')
})
test('all transient and read-only modes prevent save and export guidance',()=>{
 for(const key of ['busy','previewBusy','commitBusy','sessionRestoring','versionComparing','transforming']){
  const flow=authoringFlow({...loaded,[key]:true},true,{draftOnly:false})
  assert.equal(flow.canSave,false,key)
  assert.equal(flow.action,null,key)
 }
})
test('check failures direct the user to diagnostics, not the happy path',()=>{
 const flow=authoringFlow({...loaded,candidateValidation:{passed:false}},true)
 assert.equal(flow.action,'checks')
 assert.equal(flow.tone,'warning')
})
test('checks never imply export or visual approval',()=>{
 const flow=authoringFlow({...loaded,candidateValidation:{passed:true}},true)
 assert.equal(flow.action,'save-authoring-version')
 assert.match(flow.title,/请确认画面/)
 assert.equal(authoringFlow(loaded,true).action,'validate-preview')
})
test('only a receipt reports saving and distinguishes draft from NBT',()=>{
 assert.equal(authoringFlow(loaded,true,{draftOnly:true}).title,'制作版已保存')
 assert.equal(authoringFlow(loaded,true,{draftOnly:false}).title,'NBT 已导出')
 assert.equal(authoringFlow({},false).action,'project')
 const savedParent=authoringFlow({...loaded,preview:{}},false,{draftOnly:true})
 assert.equal(savedParent.action,'open-saved')
 assert.equal(savedParent.canSave,false)
})
