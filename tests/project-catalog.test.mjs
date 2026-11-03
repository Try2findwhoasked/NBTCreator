import {test} from 'node:test'
import assert from 'node:assert/strict'
import {filterProjects,projectStage} from '../.agents/skills/minecraft-nbt-modeler/assets/viewer/src/project-catalog.js'

const models=[
 {source:'draft',project_key:'A',shape_group:'long',object_key:'A/long/hall',modified_ns:50,intermediate:true},
 {source:'broken',project_key:'A',shape_group:'long',object_key:'A/long/hall',modified_ns:60,unreadable:true},
 {source:'v1',project_key:'A',shape_group:'long',object_key:'A/long/hall',modified_ns:10},
 {source:'v2',project_key:'A',shape_group:'long',object_key:'A/long/hall',modified_ns:20},
 {source:'bad-only',project_key:'B',shape_group:'bugged',object_key:'B/bugged/room',unreadable:true},
]
const sources=options=>filterProjects(models,options).map(item=>item.source)
test('latest remains a saved usable version, and broken-only objects remain discoverable',()=>{
 assert.deepEqual(sources(),['v2','bad-only'])
 assert.deepEqual(sources({version:'older'}),['draft','broken','v1'])
 assert.deepEqual(sources({version:'intermediate'}),['draft'])
 assert.deepEqual(sources({version:'all',readability:'unreadable'}),['broken','bad-only'])
})
test('project, shape, object and version filters compose without hiding bugged categories',()=>{
 assert.deepEqual(sources({project:'B',shape:'bugged'}),['bad-only'])
 assert.deepEqual(sources({object:'A/long/hall',version:'all',readability:'readable'}),['draft','v1','v2'])
 assert.deepEqual(sources({project:'A',shape:'bugged'}),[])
 assert.deepEqual(sources({query:'missing'}),[])
})
test('quarantine metadata is pending until opened and is not labelled as checked readable',()=>{
 const pending=[{source:'pending.nbt',group:'quarantine',project_key:'A',shape_group:'bugged',unverified:true}]
 assert.equal(filterProjects(pending).length,1)
 assert.equal(filterProjects(pending,{readability:'readable'}).length,0)
 assert.equal(filterProjects(pending,{readability:'unverified'}).length,1)
})
test('a recently copied delivery never replaces the authoring version of the same object',()=>{
 const base={object_key:'single/hall',project_key:'',shape_group:'single'}
 const entries=[{...base,source:'delivery',is_delivery:true,modified_ns:99999},{...base,source:'v2',version:'v2',modified_ns:500},{...base,source:'v10',version:'v10',modified_ns:100}]
 assert.deepEqual(filterProjects(entries).map(item=>item.source),['v10'])
 assert.equal(filterProjects(entries,{version:'all'}).length,3)
})
test('timestamped revisions follow the version directory rather than copied file timestamps',()=>{
 const base={object_key:'single/hall'}
 const entries=[{...base,source:'older',version:'v_2026-11-01_120000/refined_v09',modified_ns:9999},{...base,source:'newer',version:'v_2026-11-02_120000/refined_v02',modified_ns:50},{...base,source:'latest',version:'v_2026-11-02_120000/refined_v03',modified_ns:10}]
 assert.deepEqual(filterProjects(entries).map(item=>item.source),['latest'])
 assert.deepEqual(filterProjects([{...base,source:'copied-base',version:'v_2026-11-02_120000',modified_ns:99999},entries[2]]).map(item=>item.source),['latest'])
 assert.deepEqual(filterProjects([{...base,source:'draft-a',version:'v_2026-11-02_120000_draft04a',modified_ns:99999},{...base,source:'draft-b',version:'v_2026-11-02_120000_draft04b',modified_ns:1}]).map(item=>item.source),['draft-b'])
})
test('multiple filter choices combine within groups and intersect between groups',()=>{
 const items=[{source:'a',object_key:'a',project_key:'one',shape_group:'single',relative_path:'single/room/v1/master.json.gz'}, {source:'b',object_key:'b',project_key:'two',shape_group:'long',relative_path:'long/room/refined_v02/master.json.gz'}, {source:'c',object_key:'c',project_key:'two',shape_group:'long',stage:'finalized'}, {source:'d',object_key:'d',project_key:'three',shape_group:'cross',relative_path:'cross/room/final/master.json.gz'}]
 assert.equal(projectStage(items[0]),'unrefined');assert.equal(projectStage(items[1]),'refined');assert.equal(projectStage(items[3]),'unrefined')
 assert.deepEqual(filterProjects(items,{project:['one','two'],shape:['single','long'],stage:['refined','finalized'],readability:['readable','unverified'],version:['latest','older']}).map(item=>item.source),['b','c'])
 assert.equal(filterProjects(items,{stage:[]}).length,0)
})

test('discarded versions are hidden by default and do not replace the latest usable version',()=>{
 const items=[{source:'v1',object_key:'room',version:'v1'}, {source:'v2',object_key:'room',version:'v2',stage:'discarded'}, {source:'only-discarded',object_key:'other',stage:'discarded'}]
 assert.equal(projectStage(items[1]),'discarded')
 assert.deepEqual(filterProjects(items).map(item=>item.source),['v1'])
 assert.deepEqual(filterProjects(items,{version:'all'}).map(item=>item.source),['v1'])
 assert.deepEqual(filterProjects(items,{stage:['discarded']}).map(item=>item.source),['v2','only-discarded'])
 assert.deepEqual(filterProjects(items,{stage:['unrefined','discarded'],version:'all'}).map(item=>item.source),['v1','v2','only-discarded'])
 assert.equal(filterProjects(items,{stage:'all',version:'all'}).length,3)
})
