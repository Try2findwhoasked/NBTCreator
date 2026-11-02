import path from 'node:path'
import {fileURLToPath} from 'node:url'
export const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..')
export const skill=path.join(root,'.agents/skills/minecraft-nbt-modeler')
export const python=process.env.NBTCREATOR_PYTHON || 'python'
