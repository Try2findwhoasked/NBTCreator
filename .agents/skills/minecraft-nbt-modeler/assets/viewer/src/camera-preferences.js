import {normalizeCameraControls} from './camera-controls.mjs'

let current=normalizeCameraControls()
const frameIds=['viewer','project-preview-3d']
async function syncFrame(frame){
 try{
  const viewer=frame.contentWindow?.nbtModeler
  if(!viewer)return
  await viewer.ready
  if(frame.contentWindow?.nbtModeler===viewer)viewer.setControls(current)
 }catch{/* Navigation and failed model loads are handled by the owning preview. */}
}
// Capture also handles newly opened or reloaded previews, without changing
// their model, camera pose, selection, or native bridge permissions.
document.addEventListener('load',event=>{if(frameIds.includes(event.target.id))syncFrame(event.target)},true)
export function applyCameraPreferences(value){
 current=normalizeCameraControls(value)
 for(const id of frameIds){const frame=document.getElementById(id);if(frame)syncFrame(frame)}
}
