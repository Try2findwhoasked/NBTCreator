export function translateComponent(operations,offset,size){
 if(!Array.isArray(offset)||offset.length!==3||!offset.every(Number.isInteger))throw Error('整体偏移XYZ须为整数')
 return operations.map(source=>{
  const op=structuredClone(source)
  for(const key of ['lo','hi','start','end'])if(op[key]){
   op[key]=op[key].map((v,i)=>v+offset[i])
   if(op[key].some((v,i)=>v<0||v>=size[i]))throw Error('整体移动后超出模型边界，请减小偏移')
  }
  return op
 })
}
