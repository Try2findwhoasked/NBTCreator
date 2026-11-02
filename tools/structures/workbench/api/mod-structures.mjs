import fs from 'node:fs/promises'
import path from 'node:path'
import { randomUUID } from 'node:crypto'
import { spawn } from 'node:child_process'

export function modStructures({workspace,python,backend,asset,openPreview,json,body,dataRoot,env}){
  let catalog, saving=false
  async function invoke(args){
    return new Promise((resolve,reject)=>{
      const child=spawn(python,['-B',backend,...args,'--workspace',workspace],{cwd:workspace,windowsHide:true,shell:false,env})
      let stdout='',stderr='';child.stdout.setEncoding('utf8');child.stderr.setEncoding('utf8')
      child.stdout.on('data',chunk=>stdout+=chunk);child.stderr.on('data',chunk=>stderr+=chunk);child.on('error',reject)
      child.on('close',code=>{try{const result=JSON.parse(stdout);if(code!==0||!result.ok)throw new Error(result.error||stderr||'结构工具失败');resolve(result.result)}catch(error){reject(error)}})
    })
  }
  async function known(room){
    if(!catalog)catalog=await invoke(['catalog'])
    if(!catalog.rooms.some(item=>item.id===room))throw new Error('房间未在模组中登记，请刷新')
  }
  return async(req,res,url)=>{
    if(!url.pathname.startsWith('/api/mod/'))return false
    try{
      if(req.method==='GET'&&url.pathname==='/api/mod/catalog'){
        catalog=await invoke(['catalog']);json(res,catalog)
      }else if(req.method==='GET'&&url.pathname==='/api/mod/thumbnail'){
        const room=url.searchParams.get('room');await known(room)
        const result=await invoke(['thumbnail','--room',room,'--cache',path.join(dataRoot,'mod_structure_thumbs')])
        json(res,{...result,image:asset(result.image)})
      }else if(req.method==='POST'&&url.pathname==='/api/mod/snapshot'){
        const input=await body(req);await known(input.room)
        const target=path.join(dataRoot,'mod_structure_previews',randomUUID()+'.json')
        const result=await invoke(['snapshot','--room',input.room,'--output',target])
        json(res,{url:await openPreview(result.snapshot),...result})
      }else if(req.method==='POST'&&url.pathname==='/api/mod/apply'){
        if(saving)throw new Error('正在保存，请稍后再试')
        const input=await body(req);saving=true
        try{
          const directory=path.join(dataRoot,'mod_structure_changes',new Date().toISOString().replace(/[:.]/g,'-')+'_'+randomUUID());await fs.mkdir(directory,{recursive:true})
          const request=path.join(directory,'request.json');await fs.writeFile(request,JSON.stringify(input,null,2))
          const result=await invoke(['apply','--request',request,'--output',path.join(directory,'backup')]);if(result.catalog)catalog=result.catalog;json(res,result)
        }finally{saving=false}
      }else json(res,{error:'未知操作'},404)
    }catch(error){json(res,{error:error.message},400)}
    return true
  }
}
