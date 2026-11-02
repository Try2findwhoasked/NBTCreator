import fs from 'node:fs/promises'
import path from 'node:path'
import { createHash, randomUUID } from 'node:crypto'
import { createReadStream } from 'node:fs'
async function digest(file){
  const hash=createHash('sha256')
  for await(const bytes of createReadStream(file))hash.update(bytes)
  return hash.digest('hex')
}
export function savedEffects({workspace,skillRoot,initial}){
  const preferences=path.join(workspace,'build/nbt_control/preferences.json')
  let root=initial, files=new Map()
  async function validate(value){
    if(typeof value!=='string'||!path.isAbsolute(value)||value.startsWith('\\\\')||value.startsWith('//'))throw new Error('请填写本机的完整文件夹路径')
    const resolved=path.resolve(value)
    await fs.mkdir(resolved,{recursive:true})
    const real=await fs.realpath(resolved), skill=await fs.realpath(skillRoot)
    if(real===skill||real.startsWith(skill+path.sep))throw new Error('请选择 skill 文件夹以外的保存位置')
    return real
  }
  return {
    async init(){
      try{const data=JSON.parse(await fs.readFile(preferences,'utf8'));const old=path.join(workspace,'build');const chosen=path.resolve(data.output);root=await validate(chosen===old||chosen.startsWith(old+path.sep)?path.join(workspace,'nbt_models','_workspaces','effects'):chosen)}catch(error){if(error.code!=='ENOENT')throw error}
      return root
    },
    async set(value){
      const next=await validate(value)
      await fs.mkdir(path.dirname(preferences),{recursive:true})
      const temporary=preferences+'.'+randomUUID()+'.tmp'
      await fs.writeFile(temporary,JSON.stringify({output:next},null,2));await fs.rename(temporary,preferences)
      root=next;files.clear();return root
    },
    async scan(){
      files.clear();let truncated=false, visited=0
      async function walk(directory){
        let entries
        try{entries=await fs.readdir(directory,{withFileTypes:true})}catch(error){if(error.code==='ENOENT')return;throw error}
        for(const entry of entries){
          if(++visited>12000||files.size>=2000){truncated=true;break}
          if(entry.isSymbolicLink()||entry.name.startsWith('.')||['node_modules','system','cache'].includes(entry.name))continue
          const file=path.join(directory,entry.name)
          if(entry.isDirectory())await walk(file)
          else if(/\.(json|gz|png|jpg|jpeg|webp|nbt|md|zip)$/i.test(entry.name)){
            const stat=await fs.stat(file),id=createHash('sha256').update(file).digest('hex')
            files.set(id,{id,path:file,name:path.relative(root,file),size:stat.size,mtime:stat.mtimeMs})
          }
        }
      }
      await walk(root)
      return {root,files:[...files.values()].sort((a,b)=>b.mtime-a.mtime),truncated}
    },
    async save(request,name){
      const title=(name||'建筑效果').trim()
      if(!title||title.length>80||/[<>:"/\\|?*\x00-\x1f]/.test(title))throw new Error('效果名称不能包含路径符号，且最多80字')
      await validate(root)
      const file=path.join(root,title+'_'+new Date().toISOString().replace(/[:.]/g,'-')+'_'+randomUUID().slice(0,8)+'.json')
      await fs.writeFile(file,JSON.stringify(request,null,2),{flag:'wx'})
      return {path:file,name:path.basename(file)}
    },
    async references(ids){
      if(!Array.isArray(ids)||ids.length>30)throw new Error('一条意见最多引用30个效果文件')
      const result=[]
      for(const id of new Set(ids)){
        const file=files.get(id);if(!file)throw new Error('引用文件已不在当前保存位置，请刷新效果文件列表')
        const before=await fs.stat(file.path)
        if(before.size!==file.size||before.mtimeMs!==file.mtime)throw new Error('引用文件已改动，请刷新文件列表后重新引用')
        const sha256=await digest(file.path),after=await fs.stat(file.path)
        if(after.mtimeMs!==before.mtimeMs||after.size!==before.size)throw new Error('引用文件正在改动，请稍后重试')
        result.push({name:file.name,path:file.path,sha256,size:file.size})
      }
      return result
    }
  }
}
