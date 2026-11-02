import path from 'node:path'
export function portableRequest(request,workspace){
 const value=structuredClone(request)
 for(const key of ['source','context','cameras','review'])if(value[key]&&path.isAbsolute(value[key])){
  const relative=path.relative(workspace,value[key])
  if(!path.isAbsolute(relative)&&relative!=='..'&&!relative.startsWith('..'+path.sep))value[key]=relative.split(path.sep).join('/')||'.'
 }
 value.path_base='workspace';return value
}
export function absoluteRequest(request,workspace){
 const value=structuredClone(request)
 for(const key of ['source','context','cameras','review'])if(value[key])value[key]=path.resolve(workspace,value[key])
 return value
}
