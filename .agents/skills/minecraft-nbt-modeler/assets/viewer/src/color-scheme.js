import './color-scheme.css'
export const colorSchemes={
 blue:{label:'清爽蓝',accent:'#326b91',soft:'#e5eff5',bg:'#f3f6f8',panel:'#ffffff',input:'#f7f9fb',line:'#d5dfe6',text:'#243746',muted:'#526575'},
 green:{label:'森林绿',accent:'#257a62',soft:'#e2f0e9',bg:'#f1f5f2',panel:'#ffffff',input:'#f6faf7',line:'#d9e5dd',text:'#293e36',muted:'#52695d'},
 violet:{label:'紫罗兰',accent:'#7756c1',soft:'#eee7fb',bg:'#f5f3f8',panel:'#ffffff',input:'#faf8fd',line:'#e3deeb',text:'#393049',muted:'#6c607c'},
 sand:{label:'暖沙色',accent:'#956126',soft:'#f6ead5',bg:'#f7f4ed',panel:'#fffdf8',input:'#fcf9f2',line:'#e8e0d2',text:'#443a2e',muted:'#71634f'},
 graphite:{label:'石墨灰',accent:'#536776',soft:'#e5ebef',bg:'#f2f4f5',panel:'#ffffff',input:'#f8fafb',line:'#dde3e7',text:'#303d46',muted:'#596975'}
}
let active='blue'
function paint(document,name){const p=colorSchemes[name]??colorSchemes.blue,root=document.documentElement;root.dataset.colorScheme=name;for(const key of ['accent','bg','panel','input','line','text','muted'])root.style.setProperty('--ui-'+key,p[key]);root.style.setProperty('--ui-accent-soft',p.soft);for(const [key,value]of Object.entries({bg:p.bg,panel:p.panel,line:p.line,muted:p.muted,accent:p.accent}))root.style.setProperty('--'+key,value)}
export function applyColorScheme(name){active=Object.hasOwn(colorSchemes,name)?name:'blue';paint(document,active);for(const frame of document.querySelectorAll('iframe'))try{if(frame.contentDocument)paint(frame.contentDocument,active)}catch{}}
document.addEventListener('load',event=>{if(event.target.tagName==='IFRAME')try{if(event.target.contentDocument)paint(event.target.contentDocument,active)}catch{}},true)
