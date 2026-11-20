import {BlockDefinition} from '@mattzh72/lodestone'

export function withBookshelfModels(pack){
 const source=pack.assets.blockstates?.chiseled_bookshelf
 if(!source?.multipart)return pack.resources
 // The bundled renderer accepts an implicit AND between different state keys.
 const multipart=source.multipart.map(part=>{
  const terms=part.when?.AND
  if(!Array.isArray(terms)||terms.length!==2)return part
  if(!terms[0]||!terms[1])return part
  const [side,slot]=terms,keys=Object.keys(slot)
  if(Object.keys(side).length!==1||typeof side.facing!=='string'||
     keys.length!==1||!/^slot_[0-5]_occupied$/.test(keys[0]))return part
  return {...part,when:{...side,...slot}}
 })
 const bookshelf=BlockDefinition.fromJson({...source,multipart})
 return {...pack.resources,getBlockDefinition(id){
  return String(id)==='minecraft:chiseled_bookshelf'?bookshelf:pack.resources.getBlockDefinition(id)
 }}
}
