import path from 'node:path'
import runtime from '../desktop/python-runtime.cjs'
import {fileURLToPath} from 'node:url'
export const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..')
export const skill=path.join(root,'.agents/skills/minecraft-nbt-modeler')
export const python=runtime.resolvePython(root)
if(process.versions.electron)runtime.configureRenderRuntime(root,process.execPath)
