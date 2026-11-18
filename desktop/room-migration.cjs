const fs=require('node:fs/promises')
const path=require('node:path')
const {execFile}=require('node:child_process')
const {promisify}=require('node:util')
const runFile=promisify(execFile)

function createRoomMigration({root,python,dataDirectory,download}){
 const bundled=path.join(root,'tools/constraint-room-migration/migrate.py')
 let source='',target='',plan=null,script='',active=false,verified=''
 async function run(file,action,args){
  let stdout
  try{
   ({stdout}=await runFile(python,['-B',file,action,...args],{
    windowsHide:true,timeout:60*60*1000,maxBuffer:8*1024*1024,
    env:{...process.env,PYTHONIOENCODING:'utf-8',NBTCREATOR_MIGRATION_ENGINE:path.join(root,'.agents/skills/minecraft-nbt-modeler/scripts')}
   }))
  }catch(error){throw Error(String(error.stderr||'迁移工具执行失败').trim())}
  return JSON.parse(stdout)
 }
 function select(kind,folder){
  if(active)throw Error('请等待当前迁移步骤结束')
  if(kind==='source'){source=folder;target=''}
  else if(kind==='target'&&source)target=path.join(folder,path.basename(source)+'-迁移版')
  else throw Error('无效的迁移路径类型')
  plan=null;verified=''
  return {source,target}
 }
 async function execute(action,input){
  if(active)throw Error('已有迁移步骤正在运行')
  if(!source||!target)throw Error('请先选择旧工作区和新工作区位置')
  active=true
  try{
   if(action==='plan'){
    plan=null;verified=''
    script=input?.download===true?await download(await fs.readFile(bundled)):bundled
    plan=await run(script,'plan',['--source',source,'--target',target])
    return plan
   }
   if(action==='apply'&&plan&&script){
    const owners=input?.owners??{}
    if(typeof owners!=='object'||Array.isArray(owners)||Object.keys(owners).length>plan.rooms.length)throw Error('归属清单无效')
    const directory=path.join(dataDirectory,'migration')
    await fs.mkdir(directory,{recursive:true})
    const scratch=await fs.mkdtemp(path.join(directory,'request-'))
    const file=path.join(scratch,'request.json')
    try{
     await fs.writeFile(file,JSON.stringify({plan,owners}))
     const result=await run(script,'apply',['--request',file])
     if(result.passed!==true||result.target!==plan.target)throw Error('迁移工具未完成验证')
     verified=result.target
     return result
    }finally{await fs.unlink(file).catch(()=>{});await fs.rmdir(scratch).catch(()=>{})}
   }
   throw Error('请先完成迁移预检')
  }finally{active=false}
 }
 return {select,execute,verified:()=>verified}
}

module.exports={createRoomMigration}
