import {recipeSpacingTarget,recipeHasStyle} from '../components/component-recipe-controls.mjs'
import './library-asset-preview.css'

export function createAssetPreview({figure,overview,parameterHost,api,active,onState}){
 const frame=document.createElement('iframe')
 frame.id='asset-preview-viewer'
 frame.title='素材材质三维预览'
 frame.hidden=true
 const empty=document.createElement('p')
 empty.className='asset-preview-empty'
 const image=figure.querySelector('img')
 figure.prepend(frame,empty)
 const parameters=document.createElement('fieldset')
 parameters.id='asset-recipe-parameters'
 parameters.hidden=true
 parameters.innerHTML=`<legend>配方参数</legend>
 <label>生成名称<input id="asset-recipe-name" maxlength="80"></label>
 <div class="asset-recipe-size">${['x','y','z'].map((axis,index)=>`<label>${['宽 X','高 Y','深 Z'][index]}<input id="asset-recipe-${axis}" type="number" min="1" max="64" step="1"></label>`).join('')}</div>
 <label>主材<input id="asset-recipe-material"></label>
 <label>收边材质<input id="asset-recipe-accent"></label>
 <div class="asset-recipe-pair"><label>样式<select id="asset-recipe-style"><option value="classic">经典</option><option value="stepped">层叠</option><option value="open">通透</option></select></label>
 <label>节奏间距<input id="asset-recipe-spacing" type="number" min="1" max="64" step="1"></label></div>
 <details><summary>构造细节与高级参数</summary><label>构造参数 JSON<textarea id="asset-recipe-form" rows="5" maxlength="20000" spellcheck="false"></textarea></label>
 <label>装饰参数 JSON<textarea id="asset-recipe-ornament" rows="3" maxlength="20000" spellcheck="false"></textarea></label></details>`
 const refresh=document.createElement('button')
 refresh.type='button';refresh.id='asset-preview-refresh';refresh.textContent='更新预览'
 const status=document.createElement('p')
 status.id='asset-preview-status';status.setAttribute('role','status')
 parameterHost.insertBefore(parameters,parameterHost.querySelector(':scope>label'))
 overview.append(refresh,status)
 const $=id=>parameters.querySelector('#'+id)
 let item=null,signature='',epoch=0,loading=false,receipt=null,binding=null,cancelFrame=()=>{}
 const fingerprint=()=>JSON.stringify([...parameters.querySelectorAll('input,select,textarea')].map(field=>field.value))
 function report(text,error=false){status.textContent=text;status.classList.toggle('error',error)}
 function update(){refresh.disabled=loading||!item;onState()}
 function dirty(){receipt=null;binding=null;report('参数已改变，请更新预览后使用。');update()}
 parameters.addEventListener('input',dirty)
 parameters.addEventListener('change',dirty)
 function fill(args){
  $('asset-recipe-name').value=args.name??item.name
  for(const [index,axis]of ['x','y','z'].entries())$('asset-recipe-'+axis).value=args.size[index]
  $('asset-recipe-material').value=args.material??'stone_bricks'
  $('asset-recipe-accent').value=args.accent??'polished_andesite'
  $('asset-recipe-material').closest('label').hidden=args.kind==='railing'
  $('asset-recipe-accent').closest('label').hidden=args.kind==='railing'
  $('asset-recipe-style').value=args.style??'classic'
  $('asset-recipe-style').disabled=!recipeHasStyle(args,item.controls)
  const target=recipeSpacingTarget(args,item.controls)
  $('asset-recipe-spacing').disabled=!target
  $('asset-recipe-spacing').value=target?target.reduce((value,key)=>value?.[key],args)??3:3
  $('asset-recipe-form').value=JSON.stringify(args.form??{},null,2)
  $('asset-recipe-ornament').value=JSON.stringify(args.ornament??{},null,2)
 }
 function argumentsForPreview(){
  if(item.type!=='parametric_recipe')return undefined
  const args=structuredClone(item.arguments)
  const size=['x','y','z'].map(axis=>Number($('asset-recipe-'+axis).value))
  if(!size.every(value=>Number.isInteger(value)&&value>=1&&value<=64))throw Error('每轴尺寸须为1～64格的整数')
  const name=$('asset-recipe-name').value.trim()
  if(!name)throw Error('请填写生成名称')
  Object.assign(args,{name,size})
  if(args.kind!=='railing'){
   args.material=$('asset-recipe-material').value.trim()
   args.accent=$('asset-recipe-accent').value.trim()
  }
  if(!$('asset-recipe-style').disabled)args.style=$('asset-recipe-style').value
  for(const [field,key]of [['asset-recipe-form','form'],['asset-recipe-ornament','ornament']]){
   let value
   try{value=JSON.parse($(field).value)}catch{throw Error('请检查构造或装饰参数 JSON')}
   if(!value||Array.isArray(value)||typeof value!=='object')throw Error('构造和装饰参数须为 JSON 对象')
   if(Object.keys(value).length)args[key]=value
   else delete args[key]
  }
  const target=recipeSpacingTarget(args,item.controls)
  if(target&&!$('asset-recipe-spacing').disabled){
   const value=Number($('asset-recipe-spacing').value)
   if(!Number.isInteger(value)||value<1||value>64)throw Error('节奏间距须为1～64格的整数')
   let owner=args
   for(const key of target.slice(0,-1))owner=owner[key]??={}
   owner[target.at(-1)]=value
  }
  return args
 }
 async function generate(){
  if(!item)return
  const token=++epoch,current=item,fields=fingerprint()
  cancelFrame()
  receipt=null;binding=null;loading=true;report('正在生成实际预览…');update()
  try{
   const args=argumentsForPreview()
   const result=current.library_ref
    ?await api('asset-libraries/preview',{...current.library_ref,...(args?{arguments:args}:{})})
    :await api('components/agent',{tool:'structure_view',arguments:{id:current.id}})
   if(token!==epoch||!active()||fields!==fingerprint())return
   image.src=result.thumbnail
   empty.hidden=true
   frame.hidden=false;image.hidden=true
   await new Promise((resolve,reject)=>{
    const timer=setTimeout(()=>reject(Error('三维预览加载超时，请重试')),60000)
    cancelFrame=()=>{clearTimeout(timer);resolve()}
    frame.onload=()=>Promise.resolve(frame.contentWindow?.nbtModeler?.ready).then(()=>{clearTimeout(timer);resolve()},error=>{clearTimeout(timer);reject(error)})
    frame.src='/index.html?embedded=1&quality=balanced&model_key='+encodeURIComponent(result.model_key)
   })
   if(token!==epoch||!active()||fields!==fingerprint())return
   const viewer=frame.contentWindow?.nbtModeler
   if(viewer?.status!=='ready')throw Error('三维预览未能加载，请重试')
   await viewer.setCamera(result.cameras[0])
   if(token!==epoch||fields!==fingerprint())return
   frame.hidden=false;image.hidden=true
   receipt={...result,arguments:args};binding=fields
   figure.querySelector('#asset-meta').textContent=`${current.type==='parametric_recipe'?'可调配方':'构件'} · ${result.size.join(' × ')} · ${result.block_count} 格`
   if(innerWidth<700)frame.scrollIntoView({block:'nearest'})
   report(`${result.size.join(' × ')} 格 · ${result.block_count} 个方块 · 待看图审阅`)
  }catch(error){if(token===epoch){report(error.message,true);frame.hidden=true;image.hidden=!image.getAttribute('src');empty.hidden=!!image.getAttribute('src');empty.textContent='预览未生成'}}
  finally{if(token===epoch){loading=false;update()}}
 }
 refresh.onclick=()=>generate()
 return {
  async select(next){
   const nextSignature=JSON.stringify(next.library_ref??[next.id,next.content_sha256])
   const changed=nextSignature!==signature
   item=next
   if(changed){
    epoch++;signature=nextSignature;receipt=null;binding=null
    frame.src='about:blank';frame.hidden=true
    if(next.thumbnail){image.src=next.thumbnail;image.hidden=false}
    else{image.removeAttribute('src');image.hidden=true}
    empty.hidden=!!next.thumbnail;empty.textContent='正在准备素材预览…'
    if(next.type==='parametric_recipe')fill(next.arguments)
   }
   parameters.hidden=next.type!=='parametric_recipe'
   if(next.type==='parametric_recipe')parameters.append(refresh,status)
   else overview.append(refresh,status)
   await generate()
  },
  canUse(){return !!item&&(!item.library_ref||!!receipt&&binding===fingerprint())},
  request(){
   if(!item?.library_ref)return {content_sha256:item?.content_sha256}
   if(!receipt||binding!==fingerprint())throw Error('请先更新当前参数的预览')
   return {...item.library_ref,content_sha256:receipt.content_sha256,...(receipt.arguments?{arguments:structuredClone(receipt.arguments)}:{})}
  },
  close(){epoch++;cancelFrame();loading=false;receipt=null;binding=null;frame.src='about:blank';frame.hidden=true;update()},
  lock(value){parameters.disabled=value;refresh.disabled=value||loading||!item}
 }
}
