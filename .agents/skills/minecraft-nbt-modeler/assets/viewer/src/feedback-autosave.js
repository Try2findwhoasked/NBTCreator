// A stable note ID turns typing into revisions of one formal annotation.
// Each target is captured before IO, so a late response cannot move content
// into whichever building/view happens to be open when the request finishes.
export function createFeedbackAutosave({capture,save,saved=()=>{},message=()=>{},delay=650,eventTarget=window,beacon,clientId=crypto.randomUUID()}={}){
 const pending=new Map(),revisions=new Map(),last=new Map(),sequences=new Map(),captured=new Map()
 let timer,running=null,activeId=null,composing=false,disposed=false,lastError=null
 const signature=value=>JSON.stringify([value.target_id,value.note_id,value.text,value.anchors,value.references])
 function enqueue(){
  if(disposed||composing)return
  const value=capture();if(!value)return
  const id=value.note_id;revisions.set(id,Math.max(revisions.get(id)??0,value.expected_revision??0))
  const empty=!value.text.trim()&&!value.anchors.length
  if(empty&&!revisions.get(id)&&activeId!==id){pending.delete(id);lastError=null;return}
  const content=signature(value)
  if(content===last.get(id)&&activeId!==id){pending.delete(id);lastError=null;return}
  if(captured.get(id)!==content){sequences.set(id,(sequences.get(id)??0)+1);captured.set(id,content)}
  pending.set(id,{...structuredClone(value),client_id:clientId,sequence:sequences.get(id)});message('等待自动保存…',false,value)
 }
 async function drain(){
  if(running)return running
  running=(async()=>{
   while(pending.size){
    const [id,value]=pending.entries().next().value;pending.delete(id);activeId=id
    try{
     const result=await save({...value,expected_revision:revisions.get(id)??value.expected_revision??0})
     const note=result.notes.find(item=>item.id===id);if(!note)throw Error('标注保存结果缺少对应编号')
     revisions.set(id,note.revision??0);last.set(id,signature(value));lastError=null
     saved(result,value,note);message('已自动保存到当前建筑版本',false,value)
    }catch(error){lastError=error;message('自动保存未完成：'+error.message,true,value);throw error}
    finally{activeId=null}
   }
  })().finally(()=>{running=null;if(pending.size&&!disposed&&!lastError)timer=setTimeout(()=>drain().catch(()=>{}),0)})
  return running
 }
 function schedule(){clearTimeout(timer);try{enqueue()}catch(error){lastError=error;message('自动保存未完成：'+error.message,true);return}if(pending.size)timer=setTimeout(()=>drain().catch(()=>{}),delay)}
 async function flush(){clearTimeout(timer);enqueue();if(running)await running;if(pending.size)await drain();if(lastError)throw lastError}
 function composition(value){composing=value;if(!value)schedule()}
 function unload(){if(!beacon)return;clearTimeout(timer);try{enqueue();for(const [id,value]of pending){const payload={...value,expected_revision:revisions.get(id)??value.expected_revision??0};if(beacon(payload))pending.delete(id)}}catch{}}
 eventTarget?.addEventListener('pagehide',unload)
 return {schedule,flush,composition,revision:id=>revisions.get(id),get error(){return lastError},discard(id){pending.delete(id);revisions.delete(id);last.delete(id);lastError=null},get pending(){return !!running||pending.size>0},dispose(){disposed=true;clearTimeout(timer);eventTarget?.removeEventListener('pagehide',unload)}}
}
