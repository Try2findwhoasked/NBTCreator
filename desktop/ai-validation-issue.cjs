function validationIssue(error){
 const message=String(error?.message??''),step=Number(message.match(/第(\d+)步/)?.[1]),identifier=message.match(/\b(classification|kind)="([a-z_]{1,40})"/i)
 const code=message.includes('共享引擎预检')?'invalid_geometry':message.includes('classification=')?'invalid_classification':message.includes('kind=')?'invalid_tool':message.includes('JSON')?'invalid_json':message.includes('上限')?'output_limit':message.includes('参数')?'invalid_parameter':'invalid_result'
 return {code,...(Number.isSafeInteger(step)&&step>=1&&step<=128?{step}:{}),...(identifier?{field:identifier[1],received:identifier[2]}:{})}
}
module.exports={validationIssue}
