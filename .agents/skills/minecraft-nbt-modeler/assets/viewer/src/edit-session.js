// Per-workspace persistence, independent of Electron and ephemeral HTTP ports.
export function createEditSessionController({api,capture,restore,enabled=()=>true,message=()=>{}}){
 const eventTarget=window
 const client=crypto.randomUUID(),revisions=new Map();let loading=false,pending=null,sequence=0,timer,queue=Promise.resolve(),last='',lastSaved='',closed=false,notice='',noticeError=false,activeSource=null,generation=0
 const key=value=>value.source+'\n'+value.source_sha256
 function checkpoint(force=false){if(loading||!enabled()||closed)return;const value=capture();if(!value||value.source!==activeSource)return;const json=JSON.stringify(value);if(!force&&json===last)return;last=json;pending={...value,client_id:client,sequence:++sequence}}
 function write(){if(!pending||!enabled())return queue;const value=pending;pending=null;queue=queue.catch(()=>{}).then(async()=>{const result=await api('edit-sessions/save',{...value,expected_revision:revisions.get(key(value))??0});revisions.set(key(value),result.revision);lastSaved=JSON.stringify({source:value.source,source_sha256:value.source_sha256,state:value.state});message(((result.warning||notice)?(result.warning||notice)+'；':'')+'草稿已自动保存 · '+new Date(result.updated_at).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'}),noticeError);return result}).catch(error=>{message('草稿未保存：'+error.message,true);throw error});return queue}
 function schedule(){clearTimeout(timer);timer=setTimeout(()=>{try{checkpoint();write().catch(()=>{})}catch(error){message('草稿未保存：'+error.message,true)}},600)}
 async function flush(){clearTimeout(timer);checkpoint();await write();return true}
 async function beforeOpen(){checkpoint();generation++;loading=true;activeSource=null;clearTimeout(timer);try{await write()}catch{}finally{pending=null;last=''}}
 async function opened(info,apply=true){
  const epoch=generation
  notice='';noticeError=false
  try{if(!enabled()){activeSource=info.source;message('编辑草稿自动保存与恢复已关闭');return null}
   const result=await api('edit-sessions/load',{source:info.source});if(epoch!==generation)return null;if(result.source_sha256!==info.source_sha256)throw Error('建筑源已变化，请重新打开后恢复草稿')
   revisions.set(key(info),result.revision)
   activeSource=info.source
   if(result.status==='found'&&apply){await restore(result.state,{image:result.image});if(result.warning){notice=result.warning;message(notice)}else message('已恢复上次编辑；候选与评论草稿未视为导出或已保存意见')}
   else if(result.status==='source_changed'){notice='源建筑已变化：旧版本草稿保留，未自动套用';message(notice)}
   return result
  }catch(error){if(epoch!==generation)return null;notice='草稿恢复未完成：'+error.message;noticeError=true;message(notice,true);return null}
  finally{if(epoch===generation){loading=false;last='';schedule()}}
 }
 const poll=setInterval(()=>{if(!enabled()||loading||closed)return;try{checkpoint();write().catch(()=>{})}catch(error){message('草稿未保存：'+error.message,true)}},1500)
 function unload(){if(!enabled()||closed)return;try{checkpoint();if(pending){const value={...pending,expected_revision:revisions.get(key(pending))??0},text=JSON.stringify(value);if(new Blob([text]).size<60*1024)navigator.sendBeacon('/__detail__/edit-sessions/save',new Blob([text],{type:'application/json'}))}}catch{}}
 eventTarget.addEventListener('beforeunload',unload)
 return {checkpoint,schedule,flush,beforeOpen,opened,resume(){loading=false},get loading(){return loading},get source(){return activeSource},get saved(){return lastSaved},dispose(){closed=true;clearInterval(poll);clearTimeout(timer);eventTarget.removeEventListener('beforeunload',unload)}}
}
