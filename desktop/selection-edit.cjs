const catalog=require('../.agents/skills/minecraft-nbt-modeler/tool-catalog.json')
const object=value=>value&&typeof value==='object'&&!Array.isArray(value)
function cleanSelectionContext(input){
 if(!object(input)||!Array.isArray(input.size)||!input.size.every(n=>Number.isSafeInteger(n)&&n>0)||input.size.length!==3)throw Error('需要模型尺寸与局部选区')
 for(const key of ['lo','hi'])if(!Array.isArray(input[key])||input[key].length!==3||!input[key].every(Number.isSafeInteger))throw Error('选区须为整数XYZ')
 const size=input.hi.map((n,i)=>n-input.lo[i]+1)
 if(input.lo.some((n,i)=>n<0||n>input.hi[i]||input.hi[i]>=input.size[i])||size.reduce((a,b)=>a*b,1)>65536)throw Error('选择边界内至多65536格的局部范围')
 const data=input.selection
 if(!object(data)||data.schema_version!==1||JSON.stringify(data.size)!==JSON.stringify(size)||!/^[a-f0-9]{64}$/.test(data.geometry_sha256)||data.air_omitted!==true||!Array.isArray(data.palette)||data.palette.length>512||!data.palette.every(s=>typeof s==='string'&&s.length<=250&&/^(?:minecraft:)?[a-z0-9_]+(?:\[[a-z0-9_=,]+\])?$/.test(s))||!Array.isArray(data.runs)||data.runs.length>4096||Buffer.byteLength(JSON.stringify(data))>128*1024)throw Error('完整选区摘要无效或过大，请重新读取或缩小选区')
 const rows=new Map();let count=0
 for(const run of data.runs){if(!Array.isArray(run)||run.length!==6||!run.every(Number.isSafeInteger))throw Error('选区方块段无效');const [x,y,z,length,id,wall]=run;if(x<0||y<0||z<0||y>=size[1]||z>=size[2]||length<1||x+length>size[0]||id<0||id>=data.palette.length||![0,1].includes(wall))throw Error('选区方块段超出局部范围');const key=y+','+z;if(!rows.has(key))rows.set(key,[]);rows.get(key).push([x,x+length]);count+=length}
 for(const spans of rows.values()){spans.sort((a,b)=>a[0]-b[0]);if(spans.some((span,i)=>i&&span[0]<spans[i-1][1]))throw Error('选区方块段重复')}
 if(count!==data.solid_blocks||typeof input.allow_overwrite!=='boolean')throw Error('选区方块计数或覆盖参数无效')
 return {size:[...input.size],lo:[...input.lo],hi:[...input.hi],allow_overwrite:input.allow_overwrite,selection:structuredClone(data)}
}
function validateSelectionResult(result,context){
 if(!object(result)||Object.keys(result).some(k=>!['summary','coordinate_space','operations'].includes(k))||result.coordinate_space!=='local'||typeof result.summary!=='string'||!result.summary.trim()||result.summary.length>4000||!Array.isArray(result.operations)||result.operations.length>32)throw Error('选区编辑须返回相对坐标与0～32个工具步骤（无可行步骤时说明原因）')
 function data(value,depth=0){if(depth>16)throw Error('工具参数嵌套过深');if(Array.isArray(value)){if(value.length>65536)throw Error('工具数组过长');value.forEach(v=>data(v,depth+1))}else if(object(value)){for(const [key,v]of Object.entries(value)){if(['code','script','python','shell','__proto__','constructor'].includes(key))throw Error('工具只能返回数据');data(v,depth+1)}}else if(typeof value==='number'){if(!Number.isFinite(value)||Math.abs(value)>65536)throw Error('工具数值无效')}else if(typeof value==='string'){if(value.length>4000)throw Error('工具文字过长')}else if(value!==null&&typeof value!=='boolean')throw Error('工具参数须为JSON数据')}
 for(const op of result.operations){if(!object(op)||!catalog.tools[op.kind])throw Error('未知选区编辑工具');const allowed=new Set(['kind',...Object.keys(catalog.common),...Object.keys(catalog.tools[op.kind][1]),'include_boxes']);for(const key of ['overwrite','write_group','write_bounds','max_writes'])allowed.delete(key);if(Object.keys(op).some(key=>!allowed.has(key)))throw Error('AI步骤不能改变覆盖、保护或预算');data(op);if(op.label!==undefined&&(typeof op.label!=='string'||!op.label.trim()||op.label.length>250))throw Error('工具说明无效');if(op.classification!==undefined&&!['body','wall','inherit'].includes(op.classification))throw Error('工具归属无效');if(op.enabled!==undefined&&typeof op.enabled!=='boolean')throw Error('启用开关无效')}
 return {summary:result.summary,settings_patch:{lo:context.lo,hi:context.hi,operations:structuredClone(result.operations),baseline_geometry_sha256:context.selection.geometry_sha256}}
}
module.exports={cleanSelectionContext,validateSelectionResult}
