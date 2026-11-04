// UI commands contain only fixed navigation/controls. Modelling tools remain in tool-catalog.json.
export const toolPanels=[
 ['整体效果',0],['修改范围',4],['建筑取材',6],['结构编辑',7],['建模工具',8],
 ['AI建模',9],['自动道路',10],['精确换块',5],['方块混搭',1],['自动地面',3],['长苔与裂纹',2]
]
export function commandDefinitions(catalog){
 const workspaces=[['project','项目管理'],['assets','资产管理'],['prompt','提示词方案'],['model','模型编辑'],['ai','AI 助手'],['tasks','任务记录']]
 return [
  {id:'commands.open',label:'搜索命令与工具',group:'应用',shortcut:'Ctrl+KeyK'},
  {id:'settings.open',label:'打开设置',group:'应用',target:'open-settings',shortcut:'Ctrl+Comma'},
  ...workspaces.map(([workspace,label],i)=>({id:'workspace.'+workspace,label,group:'工作区',workspace,shortcut:'Alt+Digit'+(i+1)})),
  ...toolPanels.map(([label,index])=>({id:'panel.'+index,label,group:'参数面板',panel:index,workspace:'model'})),
  ...Object.entries(catalog.tools).map(([kind,[label,,hint]])=>({id:'operation.'+kind,label:'添加：'+label,group:'建模工具步骤',kind,description:hint,workspace:'model',model:true})),
  ...[
   ['preview.update','更新效果预览','update-preview','Ctrl+Shift+KeyU'],
   ['preview.validate','检查当前效果','validate-preview'],
   ['edit.undo','撤销参数','undo-settings','Ctrl+KeyZ'],['edit.redo','重做参数','redo-settings','Ctrl+KeyY'],
   ['edit.history','查看操作历史','open-settings-history'],['view.3d','切换图片 / 3D','enable-3d'],
   ['view.material','3D 取材','pick-material'],['view.comment','3D 选点标注','pick-coordinate'],
   ['asset.capture','将选区保存为构件','save-selection-asset'],['asset.copy','复制选区并用手柄调整','copy-selection-3d'],
   ['asset.move','移动选区并用手柄调整','move-selection-3d']
  ].map(([id,label,target,shortcut])=>({id,label,target,shortcut,group:'模型操作',workspace:'model',model:true}))
 ]
}
const reserved=new Set(['Ctrl+KeyA','Ctrl+KeyC','Ctrl+KeyV','Ctrl+KeyX','Ctrl+KeyF','Ctrl+KeyS','Ctrl+KeyP','Ctrl+KeyR','Ctrl+Shift+KeyR','Ctrl+KeyW','Ctrl+Shift+KeyW','Ctrl+KeyQ','Ctrl+Shift+KeyI','Ctrl+Equal','Ctrl+Shift+Equal','Ctrl+Minus','Ctrl+Digit0','Alt+F4','F5','F11','F12'])
const owners={'Ctrl+KeyZ':'edit.undo','Ctrl+Shift+KeyZ':'edit.redo','Ctrl+KeyY':'edit.redo'}
export function normalizeShortcut(value){
 if(typeof value!=='string'||value.length>70)throw Error('快捷键格式无效')
 if(!value)return ''
 const parts=value.split('+'),key=parts.pop(),modifiers=new Set(parts)
 if(parts.length!==modifiers.size||parts.some(v=>!['Ctrl','Alt','Shift'].includes(v)))throw Error('快捷键仅支持 Ctrl、Alt、Shift 和一个按键')
 const code=/^[a-z]$/i.test(key)?'Key'+key.toUpperCase():/^\d$/.test(key)?'Digit'+key:key
 if(!/^(Key[A-Z]|Digit[0-9]|F[1-9]|F1[0-2]|Comma|Period|Slash|BracketLeft|BracketRight|Minus|Equal|Space|Home|End|PageUp|PageDown)$/.test(code))throw Error('请选择字母、数字、标点或 F1～F12；Esc、Enter 和方向键保留给当前控件')
 if(!modifiers.has('Ctrl')&&!modifiers.has('Alt')&&!/^F\d+$/.test(code))throw Error('请同时按 Ctrl 或 Alt，避免干扰输入和3D操作')
 return [...['Ctrl','Alt','Shift'].filter(v=>modifiers.has(v)),code].join('+')
}
export function eventShortcut(event){
 if(event.isComposing||event.repeat||event.metaKey||event.getModifierState?.('AltGraph')||!event.code)return null
 try{return normalizeShortcut([...(event.ctrlKey?['Ctrl']:[]),...(event.altKey?['Alt']:[]),...(event.shiftKey?['Shift']:[]),event.code].join('+'))||null}catch{return null}
}
export function shortcutLabel(shortcut){return shortcut.replace(/Key([A-Z])/g,'$1').replace(/Digit([0-9])/g,'$1').replace('Comma',',').replace('Period','.').replace('Slash','/').replace('BracketLeft','[').replace('BracketRight',']').replace('Minus','−').replace('Equal','=').replace('Space','空格')}
export function defaultPreferences(){return {favorites:[],shortcuts:{},recent:[]}}
export function validateCommandPreferences(value,commands){
 if(!value||typeof value!=='object'||Array.isArray(value)||Object.keys(value).some(k=>!['favorites','shortcuts','recent'].includes(k)))throw Error('命令配置只能包含收藏、快捷键和最近使用记录')
 const known=new Set(commands.map(c=>c.id)),result=defaultPreferences()
 for(const [field,max]of [['favorites',64],['recent',20]]){const list=value[field];if(!Array.isArray(list)||list.length>max||new Set(list).size!==list.length||list.some(id=>typeof id!=='string'||!known.has(id)))throw Error(field==='favorites'?'收藏命令无效':'最近命令记录无效');result[field]=[...list]}
 if(!value.shortcuts||typeof value.shortcuts!=='object'||Array.isArray(value.shortcuts)||Object.keys(value.shortcuts).some(id=>!known.has(id)))throw Error('快捷键命令无效')
 for(const [id,key]of Object.entries(value.shortcuts))result.shortcuts[id]=normalizeShortcut(key)
 const used=new Map()
 for(const command of commands){const key=result.shortcuts[command.id]??command.shortcut??'';if(!key)continue;if(reserved.has(key)||owners[key]&&owners[key]!==command.id)throw Error(shortcutLabel(key)+' 已保留给系统或文本编辑');if(used.has(key))throw Error(shortcutLabel(key)+' 与“'+used.get(key)+'”冲突');used.set(key,command.label)}
 return result
}
export function searchCommands(commands,preferences,query=''){
 const tokens=query.normalize('NFKC').toLowerCase().trim().split(/\s+/).filter(Boolean),score=command=>{
  const text=[command.label,command.group,command.description,command.id].join(' ').normalize('NFKC').toLowerCase();if(!tokens.every(token=>text.includes(token)))return -Infinity
  const recent=preferences.recent.indexOf(command.id);return (preferences.favorites.includes(command.id)?tokens.length?50:200:0)+(recent<0?0:40-recent)+tokens.reduce((n,t)=>n+(command.kind===t||command.id===t?300:0)+(command.label.toLowerCase().includes(t)?80:0),0)
 }
 return commands.map((command,i)=>({command,i,score:score(command)})).filter(item=>Number.isFinite(item.score)).sort((a,b)=>b.score-a.score||a.i-b.i).map(item=>item.command)
}
