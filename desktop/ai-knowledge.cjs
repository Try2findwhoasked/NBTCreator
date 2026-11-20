// Deterministic, local excerpt selection. Rules/instructions never pass through this reducer.
const crypto=require('node:crypto')
const BUDGET=12000,PER_DOCUMENT=4000
function terms(query){const chunks=query.toLowerCase().match(/[a-z0-9_]+|[\u3400-\u9fff]+/g)??[];return [...new Set(chunks.flatMap(chunk=>/[\u3400-\u9fff]/.test(chunk)?[chunk,...Array.from({length:Math.max(0,chunk.length-1)},(_,i)=>chunk.slice(i,i+2))]:[chunk]))].slice(0,128)}
function excerpts(documents,query=''){
 const unique=[],seen=new Set()
 for(const document of documents){const hash=crypto.createHash('sha256').update(document.content).digest('hex');if(!seen.has(hash)){seen.add(hash);unique.push(document)}}
 const words=terms(query),share=Math.min(PER_DOCUMENT,Math.floor(BUDGET/Math.max(1,unique.length)))
 return unique.map(document=>{
  if(document.content.length<=share)return document
  const lines=document.content.split('\n'),chunks=[],chunkLimit=Math.max(1,Math.min(800,Math.floor((share-80)/2)));let offset=0
  let content='',start=1,end=1
  const flush=()=>{if(!content)return;const lower=content.toLowerCase();chunks.push({start,end,content,score:words.reduce((n,w)=>n+(lower.includes(w)?w.length:0),0),index:offset++});content=''}
  lines.forEach((line,index)=>{let rest=line+'\n';while(rest.length){if(!content)start=index+1;end=index+1;const take=Math.min(rest.length,chunkLimit-content.length);content+=rest.slice(0,take);rest=rest.slice(take);if(content.length===chunkLimit)flush()}})
  flush()
  const ranked=[chunks[0],...chunks.slice(1).sort((a,b)=>b.score-a.score||a.index-b.index)],selected=[];let used=0
  for(const chunk of ranked){const cost=chunk.content.length+40;if(used+cost>share)continue;selected.push(chunk);used+=cost}
  selected.sort((a,b)=>a.index-b.index)
  return {...document,content:selected.map(c=>`[L${c.start}-${c.end}]\n${c.content}`).join('\n'),excerpted:true,original_chars:document.content.length,omitted:true}
 })
}
module.exports={excerpts,BUDGET,PER_DOCUMENT}
