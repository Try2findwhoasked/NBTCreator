import registry from '../../../references/block-registry-1.20.1.json' with {type:'json'}
// Match the engine's conservative state-family rules, including implicit defaults.
export function rotateState(value,turns){
 if(!turns)return value
 const match=/^((?:minecraft:)?[a-z0-9_]+)(?:\[([^\[\]]+)\])?$/.exec(value)
 if(!match)throw Error('方块状态格式无效：'+value)
 const name=match[1].includes(':')?match[1]:'minecraft:'+match[1],entry=registry.blocks[name]
 if(!entry)throw Error('未知方块：'+name)
 const props={...entry.default}
 for(const item of (match[2]??'').split(',').filter(Boolean)){const [key,v,...extra]=item.split('=');if(extra.length||!entry.properties[key]?.includes(v))throw Error('方块属性无效：'+value);props[key]=v}
 if(Object.keys(props).some(k=>!['axis','facing','waterlogged'].includes(k)))throw Error('旋转暂不支持这种方块状态：'+value)
 const directions=['north','east','south','west']
 if(directions.includes(props.facing))props.facing=directions[(directions.indexOf(props.facing)+turns)%4]
 if(turns%2&&['x','z'].includes(props.axis))props.axis=props.axis==='x'?'z':'x'
 const pairs=Object.keys(props).sort().map(k=>k+'='+props[k])
 return name+(pairs.length?'['+pairs.join(',')+']':'')
}
export function rotateAIComponent(operations,turns=0){
 if(!Number.isInteger(turns)||turns<0||turns>3)throw Error('旋转须为0°、90°、180°或270°')
 if(!turns)return structuredClone(operations)
 const lo=[0,1,2].map(i=>Math.min(...operations.map(op=>op.lo[i]))),hi=[0,1,2].map(i=>Math.max(...operations.map(op=>op.hi[i])))
 const point=p=>{let [x,y,z]=p.map((n,i)=>n-lo[i]),sx=hi[0]-lo[0]+1,sz=hi[2]-lo[2]+1;for(let k=0;k<turns;k++)[x,z,sx,sz]=[sz-1-z,x,sz,sx];return [x+lo[0],y+lo[1],z+lo[2]]}
 return operations.map(source=>{if(!['box','beam','frame'].includes(source.kind))throw Error('只能旋转AI方块、梁或边框步骤');const op=structuredClone(source),a=point(op.lo),b=point(op.hi);op.lo=a.map((n,i)=>Math.min(n,b[i]));op.hi=a.map((n,i)=>Math.max(n,b[i]));for(const key of ['start','end'])if(op[key])op[key]=point(op[key]);op.state=rotateState(op.state,turns);return op})
}
