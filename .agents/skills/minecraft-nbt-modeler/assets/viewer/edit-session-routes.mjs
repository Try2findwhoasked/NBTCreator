import path from 'node:path'
import {createEditSessionStore} from './edit-session-store.mjs'

export function createEditSessionRoutes({workspace,body,json,localPath,openedSource,registerImages,bindings,sameSource}) {
  const store=createEditSessionStore(workspace)

  async function load(req) {
    const {source:requested}=await body(req)
    const source=localPath(requested)
    const info=openedSource(source)
    if(!info)throw Error('请先打开完整建筑再恢复编辑草稿')
    const result=await store.load(source)
    const view=result.state?.view
    if(view?.mode!=='images'||!view.image_hash||info.images?.some(image=>
      image.image_sha256===view.image_hash&&(!view.image_name||image.name===view.image_name)))return result

    try {
      const file=await store.imageEvidence(result.source_sha256,view.image_hash,view.image_name,info.geometry_sha256)
      if(file){
        result.image=(await registerImages([file],info))[0]
        result.image.restored=true
      }else result.warning='上次图片不在当前列表，且没有可用的图片证据；其文字和标记草稿仍保留'
    }catch(error){result.warning=error.message}
    return result
  }

  async function save(req) {
    const input=await body(req,32*1024*1024)
    input.source=localPath(input.source)
    if(!openedSource(input.source))throw Error('请先打开完整建筑再保存编辑草稿')
    const view=input.state?.view
    let warning
    if(view?.mode==='images'&&view.image_hash){
      const binding=[...bindings.values()].find(item=>item.image&&sameSource(item.source,input.source)
        &&item.source_sha256===input.source_sha256&&item.image_sha256===view.image_hash
        &&(!view.image_name||path.basename(item.image)===view.image_name))
      try {
        if(!binding)throw Error('请重新打开该图片以保存画面证据')
        await store.rememberImage(binding)
      }catch(error){warning='参数与文字草稿已存，但图片未归档：'+error.message}
    }
    return {...await store.save(input),...(warning?{warning}:{})}
  }

  const routes=new Map([
    ['GET /__detail__/edit-sessions/recent',async()=>({recent:await store.recent()})],
    ['POST /__detail__/edit-sessions/load',load],
    ['POST /__detail__/edit-sessions/save',save],
  ])
  return async (req,res,url)=>{
    const handler=routes.get(req.method+' '+url.pathname)
    if(!handler)return false
    json(res,await handler(req))
    return true
  }
}
