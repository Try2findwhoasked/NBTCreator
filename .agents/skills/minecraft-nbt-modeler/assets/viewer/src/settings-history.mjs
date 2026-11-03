// Candidate parameter history. Snapshots never contain model data or approvals.
export function createSettingsHistory({limit=60,byteLimit=12*1024*1024}={}){
 let entries=[],cursor=-1,sequence=0
 const pack=(value,label,group,now)=>({id:++sequence,json:JSON.stringify(value),label,group,at:now})
 const bytes=entry=>new TextEncoder().encode(entry.json).byteLength
 const current=()=>cursor<0?null:JSON.parse(entries[cursor].json)
 function reset(value,label='打开建筑'){entries=[pack(value,label,'',Date.now())];cursor=0}
 function record(value,label='调整参数',{group='',now=Date.now()}={}){
  const next=pack(value,label,group,now)
  if(entries[cursor]?.json===next.json)return false
  const coalesce=cursor>0&&cursor===entries.length-1&&group&&entries[cursor].group===group&&now-entries[cursor].at<700
  entries=entries.slice(0,cursor+1)
  if(coalesce)entries[cursor]=next
  else {entries.push(next);cursor=entries.length-1}
  // Retain at least the previous and current states for a large component.
  let total=entries.reduce((sum,e)=>sum+bytes(e),0)
  while(entries.length>2&&(entries.length>limit||total>byteLimit)){total-=bytes(entries.shift());cursor--}
  return true
 }
 function jump(index){if(!Number.isInteger(index)||index<0||index>=entries.length)return null;cursor=index;return current()}
 function rename(index,label){if(!entries[index]||typeof label!=='string'||!label.trim()||label.length>160)throw Error('历史名称须为1～160个字符');entries[index].label=label.trim()}
 return {reset,record,jump,rename,current,travel:delta=>jump(cursor+delta),get cursor(){return cursor},get entries(){return entries.map(({id,label,at},index)=>({id,label,at,index,current:index===cursor}))}}
}
