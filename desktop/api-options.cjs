const bounds={temperature:[0,2],top_p:[0,1],presence_penalty:[-2,2],frequency_penalty:[-2,2],max_tokens:[1,32768],seed:[0,2147483647]}
function validateRequestOptions(value={}){
 if(!value||typeof value!=='object'||Array.isArray(value)||Object.keys(value).some(k=>!Object.hasOwn(bounds,k)&&!['stop','reasoning_effort','thinking'].includes(k)))throw Error('API请求JSON仅支持界面说明中的采样、长度和推理参数')
 const result={}
 for(const [key,v]of Object.entries(value)){
  if(v===null||v==='')continue
  if(Object.hasOwn(bounds,key)){const [lo,hi]=bounds[key];if(typeof v!=='number'||!Number.isFinite(v)||v<lo||v>hi||['max_tokens','seed'].includes(key)&&!Number.isInteger(v))throw Error('API参数超出范围：'+key)}
  else if(key==='stop'){if(!(typeof v==='string'&&v.length>0&&v.length<=1000)&&!(Array.isArray(v)&&v.length>=1&&v.length<=4&&v.every(s=>typeof s==='string'&&s.length>0&&s.length<=1000)))throw Error('stop须为1～4条不超过1000字的停止文本')}
  else if(key==='reasoning_effort'&&!['low','medium','high'].includes(v))throw Error('reasoning_effort须为low、medium或high')
  else if(key==='thinking'&&(!v||typeof v!=='object'||Array.isArray(v)||Object.keys(v).length!==1||!['enabled','disabled'].includes(v.type)))throw Error('thinking须为{"type":"enabled"}或{"type":"disabled"}')
  result[key]=structuredClone(v)
 }
 return result
}
module.exports={validateRequestOptions}
