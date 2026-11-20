import {test} from 'node:test'
import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import {withBookshelfModels} from '../../.agents/skills/minecraft-nbt-modeler/assets/viewer/src/render-pack.mjs'

const assetFile=new URL('../../.agents/skills/minecraft-nbt-modeler/assets/viewer/node_modules/@mattzh72/lodestone/assets/default-pack/assets.json',import.meta.url)

test('the bookshelf resolves all six empty or occupied faces from the bundled assets',()=>{
 const assets=JSON.parse(readFileSync(assetFile,'utf8'))
 const pack={assets,resources:{getBlockDefinition:id=>id}}
 const resources=withBookshelfModels(pack)
 const book=resources.getBlockDefinition('minecraft:chiseled_bookshelf')
 for(const [facing,angle] of [['north',0],['east',90],['south',180],['west',270]]){
  const slots=Object.fromEntries(Array.from({length:6},(_,id)=>[`slot_${id}_occupied`,id===2?'true':'false']))
  const variants=book.getModelVariants({facing,...slots})
  assert.equal(variants.length,7)
  assert.equal(variants.filter(row=>row.model.includes('_empty_slot_')).length,5)
  assert.ok(variants.some(row=>row.model.endsWith('_occupied_slot_top_right')))
  assert.ok(variants.every(row=>row.y===angle))
 }
 assert.equal(resources.getBlockDefinition('minecraft:bookshelf'),'minecraft:bookshelf')
})
