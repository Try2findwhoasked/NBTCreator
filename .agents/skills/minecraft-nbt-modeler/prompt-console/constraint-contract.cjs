/* Shared data-only contract for project constraints, usable by the renderer and Node. */
(() => {
 const create=catalog=>{
 const clone=value=>JSON.parse(JSON.stringify(value));
 const keys=Object.keys(catalog.project_constraints.rules.properties);
 const object=value=>value&&typeof value==='object'&&!Array.isArray(value);
 const integer=(value,max)=>Number.isInteger(value)&&value>0&&value<=max;
 const same=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
 const labels={buildingShape:'归档形状',size:'整体尺寸',size_policy:'尺寸要求',footprint:'占地要求',cell_size:'网格边长',cells:'可建网格',integration:'接入方式',require_enclosure:'密闭检查',openings_policy:'通行洞口',opening_size:'洞口尺寸'};
 const openingPolicies={optional:'按设计决定',required:'至少一个声明洞口',none:'不设置通行洞口'};
 const contextKeys=['cells','cell_size','require_enclosure','openings_policy','opening_size'];
 function geometryRules(value,integration){
  if(value.require_enclosure!==undefined&&typeof value.require_enclosure!=='boolean')throw Error('密闭检查须为布尔值');
  if(value.openings_policy!==undefined&&!Object.hasOwn(openingPolicies,value.openings_policy))throw Error('通行洞口策略无效');
  if(value.opening_size!==undefined&&(!Array.isArray(value.opening_size)||value.opening_size.length!==2||!value.opening_size.every(n=>integer(n,294))||value.openings_policy==='none'))throw Error('洞口尺寸须为净宽、净高两个 1～294 格的整数，并允许设置洞口');
  if(integration==='saodg'&&(value.require_enclosure===false||value.opening_size!==undefined&&!same(value.opening_size,[6,5])||value.cell_size!==undefined&&value.cell_size!==48))throw Error('SAODG 接入要求密闭检查、48 格网格及 6 × 5 格标准洞口');
 }
 function validFolder(folder){
  if(typeof folder!=='string'||folder.length>500)return false;
  const [root,...parts]=folder.split('/');
  return root==='nbt_models'&&parts.every(part=>part&&!/^[._]|[<>:"\\|?*\x00-\x1f]|[ .]$/.test(part)&&!['bugged','未分类','项目约束.json'].includes(part));
 }
 function rules(value){
  if(!object(value)||!Object.keys(value).length||Object.keys(value).some(key=>!keys.includes(key)))throw Error('约束规则为空或包含未知字段');
  if(value.buildingShape!==undefined&&!Object.hasOwn(catalog.building_shapes,value.buildingShape))throw Error('约束的归档形状无效');
  if(value.size!==undefined&&(!Array.isArray(value.size)||value.size.length!==3||!value.size.every(n=>integer(n,4096))))throw Error('约束尺寸须为三个1～4096的整数');
  if(value.size_policy!==undefined&&(!['fixed','reference'].includes(value.size_policy)||!value.size))throw Error('尺寸约束方式需要同时指定尺寸');
  if(value.integration!==undefined&&!['standalone','saodg'].includes(value.integration))throw Error('接入扩展无效');
  geometryRules(value,value.integration);
  for(const key of ['footprint','requirements'])if(value[key]!==undefined&&(typeof value[key]!=='string'||!value[key].trim()||value[key].length>4000))throw Error('约束说明须为1～4000字');
  if(value.cell_size!==undefined&&!integer(value.cell_size,512))throw Error('网格边长须为1～512的整数');
  if(value.cells!==undefined){
   if(!integer(value.cell_size,512)||!Array.isArray(value.cells)||!value.cells.length||value.cells.length>256||value.cells.some(cell=>!Array.isArray(cell)||cell.length!==2||!cell.every(n=>Number.isInteger(n)&&n>=0&&n<4096))||new Set(value.cells.map(cell=>JSON.stringify(cell))).size!==value.cells.length)throw Error('有效网格须为不重复的非负整数XZ坐标，并指定网格边长');
   if(value.size&&value.cells.some(([x,z])=>(x+1)*value.cell_size>value.size[0]||(z+1)*value.cell_size>value.size[2]))throw Error('有效网格超出约束尺寸');
  }
  return clone(value);
 }
 function snapshot(value){
  if(!object(value)||Object.keys(value).some(key=>!catalog.project_constraints.snapshot_fields.includes(key))||value.schema_version!==1||!/^constraint-[a-f0-9]{32}$/.test(value.id??'')||!integer(value.revision,Number.MAX_SAFE_INTEGER)||typeof value.name!=='string'||!value.name.trim()||value.name.length>80||!/^[a-f0-9]{64}$/.test(value.sha256??''))throw Error('项目约束快照无效');
  if(value.actor!==undefined&&!['human','agent'].includes(value.actor)||value.updated_at!==undefined&&(typeof value.updated_at!=='string'||value.updated_at.length>80))throw Error('项目约束修订信息无效');
  if(value.folder!==undefined&&!validFolder(value.folder))throw Error('约束的项目文件夹无效');
  rules(value.rules);return clone(value);
 }
 function resolve(selected=[]){
  if(!Array.isArray(selected)||selected.length>16)throw Error('每个方案最多引用16项项目约束');
  const result={},owners={},seen=new Set();
  for(const item of selected){snapshot(item);if(seen.has(item.id))throw Error('不能重复引用同一项目约束');seen.add(item.id);
   const normalized={...item.rules,...(item.rules.size&&!item.rules.size_policy?{size_policy:'fixed'}:{})};
   for(const [key,value]of Object.entries(normalized)){
    if(key==='requirements')continue;
    if(Object.hasOwn(result,key)&&!same(result[key],value))throw Error('「'+owners[key]+'」和「'+item.name+'」的'+labels[key]+'冲突，请保留其中一项。');
    result[key]=clone(value);owners[key]=item.name;
   }
  }
  if(result.size&&!result.size_policy)result.size_policy='fixed';
  if(Object.keys(result).length)rules(result);
  return result;
 }
 function effective(project,selected=[]){
  const result=clone(project),bound=resolve(selected);
  for(const key of ['buildingShape','size','size_policy','footprint'])if(bound[key]!==undefined){
   if(project.source&&['size','buildingShape'].includes(key)&&!same(project[key],bound[key]))throw Error('项目约束与已有建筑的'+key+'不符');
   result[key]=clone(bound[key]);
  }
  result.context={...result.context};
  for(const key of contextKeys)if(bound[key]!==undefined)result.context[key]=clone(bound[key]);
  if(bound.integration){
   if(project.source&&(project.context?.mode??project.integration)!==bound.integration)throw Error('接入约束与已有建筑不符');
   result.integration=bound.integration;
  }
  if(result.integration==='saodg'||bound.integration){
   result.context.mode=result.integration;
   if(result.integration==='saodg')result.size_policy='fixed';
  }
  geometryRules(result.context,result.context.mode);
  if(bound.cells&&bound.cells.some(([x,z])=>(x+1)*bound.cell_size>result.size[0]||(z+1)*bound.cell_size>result.size[2]))throw Error('项目约束的有效网格超出当前尺寸');
  return result;
 }
 function describe(value){
  const lines=[];
  if(value.buildingShape)lines.push('归档形状为'+catalog.building_shapes[value.buildingShape].label);
  if(value.size)lines.push((value.size_policy==='reference'?'参考尺寸为 ':'固定尺寸为 ')+value.size.join(' × ')+' 方块（X × Y × Z）');
  if(value.cell_size)lines.push('每格边长 '+value.cell_size+' 方块');
  if(value.cells)lines.push('可建网格坐标（X,Z）为 '+value.cells.map(([x,z])=>`(${x},${z})`).join('、'));
  if(value.integration)lines.push(value.integration==='saodg'?'启用 SAODG 接入扩展':'使用独立建筑上下文');
  if(value.require_enclosure!==undefined)lines.push(value.require_enclosure?'要求验证围护密闭':'无需验证围护密闭');
  if(value.openings_policy!==undefined)lines.push('通行洞口：'+openingPolicies[value.openings_policy]);
  if(value.opening_size)lines.push('洞口净宽 × 净高为 '+value.opening_size.join(' × ')+' 格');
  if(value.footprint)lines.push(value.footprint);
  if(value.requirements)lines.push(value.requirements);
  return lines;
 }
 function text(selected=[]){
  resolve(selected);if(!selected.length)return '';
  return '# 已选项目约束\n按方案引用的版本建模。\n'+selected.map(item=>'## '+item.name+'（第 '+item.revision+' 版）\n'+describe(item.rules).map(line=>'- '+line).join('\n')).join('\n');
 }
 const contract={rules,snapshot,resolve,effective,describe,text};
 return contract;
 };
 if(globalThis.NbtToolCatalog)globalThis.NbtConstraintContract=create(globalThis.NbtToolCatalog);
 if(typeof module==='object'&&module.exports)module.exports={create};
})();
