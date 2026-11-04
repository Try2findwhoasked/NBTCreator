import fs from 'node:fs/promises'
import path from 'node:path'
// Electron's native capture works while the test window remains minimized.
// CDP page screenshots can wait indefinitely for a native compositor frame.
export function minimizedScreenshots(app,page){
 const verified=process.env.NBTCREATOR_TEST_EXE?app.evaluate(({app})=>app.getPath('exe')).then(actual=>{
  const normalize=value=>{const resolved=path.resolve(value);return process.platform==='win32'?resolved.toLowerCase():resolved}
  if(!actual||normalize(actual)!==normalize(process.env.NBTCREATOR_TEST_EXE))throw Error('Desktop acceptance launched a different executable: '+actual)
  console.log(JSON.stringify({verified_desktop_executable:actual}))
 }):Promise.resolve()
 page.screenshot=async(options={})=>{
  await verified
  const data=await app.evaluate(async({BrowserWindow},{clip})=>{
   const win=BrowserWindow.getAllWindows()[0]
   // Wake Chromium's compositor for capture without restoring the native window.
   // Keeping the page itself hidden can stall after resizing a minimized window.
   let timer
   const image=await Promise.race([win.webContents.capturePage(clip,{stayHidden:false,stayAwake:true}),new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error('Minimized capture timed out')),15000)})]).finally(()=>clearTimeout(timer))
   // Capture may briefly change the native minimized flag on Windows. Settle it
   // before returning so the test cannot continue in a restored window.
   if(!win.isMinimized()){
    win.minimize()
    const deadline=Date.now()+1500
    while(!win.isMinimized()&&Date.now()<deadline)await new Promise(resolve=>setTimeout(resolve,20))
    if(!win.isMinimized())throw Error('Test window did not return to minimized state after capture')
   }
   if(image.isEmpty())throw Error('Minimized capture returned an empty image')
   const bytes=image.toPNG()
   return bytes.toString('base64')
  },{clip:options.clip})
  const bytes=Buffer.from(data,'base64')
  if(options.path)await fs.writeFile(options.path,bytes)
  return bytes
 }
 return verified
}
