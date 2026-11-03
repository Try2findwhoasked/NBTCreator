const fs=require('node:fs/promises'),path=require('node:path')
const defaults={zoom:100,autoPreview:true,quality:'fast',startPage:'model',density:'comfortable',showHints:true,previewDelay:1400,showSelection:true,imageLimit:8,rememberWindow:true,windowWidth:1500,windowHeight:1000}
function validate(value){
 if(!value||Object.keys(value).some(k=>!Object.hasOwn(defaults,k))||!Number.isInteger(value.zoom)||value.zoom<75||value.zoom>150||typeof value.autoPreview!=='boolean'||!['fast','balanced'].includes(value.quality))throw Error('应用配置无效')
 if(!['model','prompt','tasks'].includes(value.startPage)||!['comfortable','compact'].includes(value.density)||!['showHints','showSelection','rememberWindow'].every(k=>typeof value[k]==='boolean')||!Number.isInteger(value.previewDelay)||value.previewDelay<200||value.previewDelay>5000||![8,16,32].includes(value.imageLimit)||!Number.isInteger(value.windowWidth)||value.windowWidth<900||value.windowWidth>7680||!Number.isInteger(value.windowHeight)||value.windowHeight<650||value.windowHeight>4320)throw Error('应用或窗口配置无效')
 return value
}
function createAppSettings(directory){
 const folder=()=>typeof directory==='function'?directory():directory,file=()=>path.join(folder(),'preferences.json')
 async function load(){try{return validate({...defaults,...JSON.parse(await fs.readFile(file(),'utf8'))})}catch(e){if(e.code==='ENOENT')return {...defaults};throw e}}
 async function save(input){const value=validate({...await load(),...input});await fs.mkdir(folder(),{recursive:true});const temporary=file()+'.'+require('node:crypto').randomUUID()+'.tmp';await fs.writeFile(temporary,JSON.stringify(value,null,2));await fs.rename(temporary,file());return value}
 return {load,save}
}
module.exports={createAppSettings,validate,defaults}
