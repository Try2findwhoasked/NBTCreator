import path from 'node:path'
import {fileURLToPath,pathToFileURL} from 'node:url'
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../../../..')
export const toolkit=path.resolve(process.env.SAODG_NBT_TOOLKIT??path.join(root,'.agents/skills/minecraft-nbt-modeler'))
export const {launchRenderBrowser}=await import(pathToFileURL(path.join(toolkit,'assets/viewer/browser-launch.mjs')))
