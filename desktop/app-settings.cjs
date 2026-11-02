const fs=require('node:fs/promises'),path=require('node:path')
const defaults={zoom:100,autoPreview:true,quality:'fast'}
function validate(value){
 if(!value||Object.keys(value).some(k=>!Object.hasOwn(defaults,k))||!Number.isInteger(value.zoom)||value.zoom<75||value.zoom>150||typeof value.autoPreview!=='boolean'||!['fast','balanced'].includes(value.quality))throw Error('应用配置无效')
 return value
}
function createAppSettings(directory){
 const file=path.join(directory,'preferences.json')
 async function load(){try{return validate({...defaults,...JSON.parse(await fs.readFile(file,'utf8'))})}catch(e){if(e.code==='ENOENT')return {...defaults};throw e}}
 async function save(value){validate(value);await fs.mkdir(directory,{recursive:true});await fs.writeFile(file+'.tmp',JSON.stringify(value,null,2));await fs.rename(file+'.tmp',file);return value}
 return {load,save}
}
module.exports={createAppSettings,validate}
