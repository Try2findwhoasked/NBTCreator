const integerVector=(v,label)=>{if(!Array.isArray(v)||v.length!==3||!v.every(Number.isInteger))throw Error(label+'须为三个整数');return [...v]}
export function componentBounds(component,position,turns=0,mirror=null){
 const size=integerVector(component.size,'构件尺寸'),anchor=integerVector(component.anchor,'构件锚点');position=integerVector(position,'放置坐标')
 if(size.some((n,i)=>n<1||n>64||anchor[i]<0||anchor[i]>=n)||!Number.isInteger(turns)||![null,'x','z'].includes(mirror))throw Error('构件变换参数无效')
 turns=(turns%4+4)%4
 let [x,y,z]=anchor,[sx,,sz]=size;if(mirror==='x')x=sx-1-x;if(mirror==='z')z=sz-1-z
 for(let i=0;i<turns;i++)[x,z,sx,sz]=[sz-1-z,x,sz,sx]
 const transformedAnchor=[x,y,z],shape=[sx,size[1],sz],lo=position.map((n,i)=>n-transformedAnchor[i]),hi=lo.map((n,i)=>n+shape[i]-1)
 return {lo,hi,size:shape,anchor:transformedAnchor,position,turns,mirror}
}
export function surfacePosition(component,picked,turns=0,mirror=null,grid=1){
 const position=integerVector(picked.position,'表面坐标'),normal=integerVector(picked.normal,'表面法线')
 if(normal.filter(n=>n!==0).length!==1||!normal.some(n=>Math.abs(n)===1)||!Number.isInteger(grid)||grid<1||grid>16)throw Error('请选择方块的一个平面，网格步长须为1～16格')
 const bounds=componentBounds(component,[0,0,0],turns,mirror),axis=normal.findIndex(n=>n!==0)
 for(let i=0;i<3;i++)position[i]=i===axis?(normal[i]>0?position[i]+1+bounds.anchor[i]:position[i]-bounds.size[i]+bounds.anchor[i]):Math.round(position[i]/grid)*grid
 return position
}
export function snapPosition(position,grid=1){
 if(!Array.isArray(position)||position.length!==3||!position.every(Number.isFinite)||!Number.isInteger(grid)||grid<1||grid>16)throw Error('网格吸附参数无效')
 return position.map(n=>Math.round(n/grid)*grid)
}
