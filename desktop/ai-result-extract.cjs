function extractResult(content,mode){
 if(typeof content!=='string')throw Error('API 未返回最终结果正文')
 let text=content.trim()
 // Strip only marked reasoning before the answer, never tags inside JSON data.
 while(/^<(think|analysis)>/i.test(text)){
  const tag=text.match(/^<(think|analysis)>/i)[1],end=text.toLowerCase().indexOf('</'+tag.toLowerCase()+'>')
  if(end<0)throw Error('思考段未结束，尚无完整最终结果')
  text=text.slice(end+tag.length+3).trim()
 }
 if(!text)throw Error('API 未返回最终结果正文')
 const object=value=>value&&typeof value==='object'&&!Array.isArray(value)
 if(mode!=='prompt')try{const value=JSON.parse(text);if(!object(value))throw Error('最终JSON必须是对象');return {text,parsed:value}}catch(error){if(error.message==='最终JSON必须是对象')throw error}
 const finalStarts=[...text.matchAll(/(?:^|\n)[ \t]*<final>/gi)]
 const finals=[...text.matchAll(/(?:^|\n)[ \t]*<final>[ \t]*(?:\r?\n)?([\s\S]*?)<\/final>(?=\s|$)/gi)]
 if(/(?:^|\n)[ \t]*<final>/i.test(text)&&!finals.length)throw Error('最终结果段尚未结束')
 if(finalStarts.length>1||finals.length>1)throw Error('存在多个最终结果段，请只返回一个结果')
 if(finals.length===1){text=finals[0][1].trim();if(!text)throw Error('最终结果段为空')}
 if(mode==='prompt')return {text,framed:finals.length===1}
 // A final wrapper may contain literal Markdown in JSON strings.
 if(finals.length)try{const value=JSON.parse(text);if(!object(value))throw Error('最终JSON必须是对象');return {text,parsed:value}}catch(error){if(error.message==='最终JSON必须是对象')throw error}
 const fences=[...text.matchAll(/```(?:json)?\s*([\s\S]*?)```/gi)]
 if(fences.length>1)throw Error('存在多个JSON代码块，请只返回一个最终结果')
 if(fences.length===1){try{const parsed=JSON.parse(fences[0][1]);if(object(parsed))return {text:fences[0][1].trim(),parsed}}catch{}throw Error('最终JSON代码块不完整或无效')}
 const values=[];let depth=0,start=-1,quoted=false,escaped=false
 for(let i=0;i<text.length;i++){
  const ch=text[i]
  if(depth===0){if(ch==='{'){start=i;depth=1;quoted=false;escaped=false}continue}
  if(quoted){if(escaped)escaped=false;else if(ch==='\\')escaped=true;else if(ch==='"')quoted=false;continue}
  if(ch==='"')quoted=true;else if(ch==='{')depth++;else if(ch==='}'&&!--depth){const raw=text.slice(start,i+1);try{const parsed=JSON.parse(raw);if(object(parsed))values.push({text:raw,parsed})}catch{}}
 }
 if(values.length!==1)throw Error(values.length?'存在多个JSON结果，不能猜测采用哪一个':'AI 未返回完整有效的最终JSON')
 if(depth!==0)throw Error('结果后还有未完成的JSON，不能采用残缺方案')
 return values[0]
}
module.exports={extractResult}
