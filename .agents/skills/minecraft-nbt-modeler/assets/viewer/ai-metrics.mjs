// Logs accept only bounded measurements, never API payloads, headers or errors.
const number=(v,max=Number.MAX_SAFE_INTEGER)=>Number.isSafeInteger(v)&&v>=0&&v<=max
function copyNumbers(value,keys,max){return Object.fromEntries(keys.filter(key=>number(value?.[key],max)).map(key=>[key,value[key]]))}
export function cleanTimings(value){return copyNumbers(value,['setup_ms','capture_ms','api_roundtrip_ms','request_total_ms','preview_ms'],86400000)}
export function cleanApiMetrics(value){
 if(!value||typeof value!=='object'||Array.isArray(value))return undefined
 const clean=copyNumbers(value,['attempts','prompt_tokens','completion_tokens','reasoning_tokens','total_tokens','input_text_chars','output_chars','operation_changes'])
 Object.assign(clean,copyNumbers(value,['prepare_ms','validation_ms','service_total_ms'],86400000))
 clean.retried_compact=value.retried_compact===true
 if(['stop','length','content_filter','tool_calls','function_call','unknown'].includes(value.finish_reason))clean.finish_reason=value.finish_reason
 if(Array.isArray(value.calls))clean.calls=value.calls.slice(0,3).map(call=>{
  const item=copyNumbers(call,['attempt','max_tokens','input_text_chars','request_bytes','response_bytes','prompt_tokens','completion_tokens','reasoning_tokens','total_tokens','http_status'])
  Object.assign(item,copyNumbers(call,['elapsed_ms','headers_ms','read_ms','response_parse_ms'],86400000))
  if(['complete','failed','cancelled','timeout'].includes(call?.status))item.status=call.status
  if(['stop','length','content_filter','tool_calls','function_call','unknown'].includes(call?.finish_reason))item.finish_reason=call.finish_reason
  if(['passed','failed'].includes(call?.validation_status))item.validation_status=call.validation_status
  const issue=call?.validation_issue
  if(['invalid_geometry','invalid_classification','invalid_tool','invalid_json','output_limit','invalid_parameter','invalid_result'].includes(issue?.code)){
   item.validation_issue={code:issue.code,...(number(issue.step,128)&&issue.step>0?{step:issue.step}:{})}
   if(['classification','kind'].includes(issue.field)&&typeof issue.received==='string'&&/^[a-z_]{1,40}$/i.test(issue.received))Object.assign(item.validation_issue,{field:issue.field,received:issue.received})
  }
  return item
 })
 return clean
}
