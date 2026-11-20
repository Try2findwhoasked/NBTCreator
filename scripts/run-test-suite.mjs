import {spawnSync} from 'node:child_process'
import {readFileSync} from 'node:fs'
import path from 'node:path'
import {root} from './paths.mjs'

const {scripts} = JSON.parse(readFileSync(path.join(root,'package.json'),'utf8'))
const suites = Object.keys(scripts)
  .filter(name=>name.startsWith('test:')&&name!=='test:suite')
  .map(name=>name.slice('test:'.length)).sort()
const [suite,...args] = process.argv.slice(2)

if(suite==='--list'){
  console.log(suites.join('\n'))
}else if(!suite||suite==='--help'||suite==='-h'){
  console.log('运行测试用 mise run test -- <测试套件> [参数]')
  console.log('用 mise run test -- --list 列出套件')
}else if(!suites.includes(suite)){
  console.error(`未知测试套件 ${suite}。运行 mise run test -- --list 查看名称。`)
  process.exitCode=1
}else{
  const npm = process.env.npm_execpath
  if(!npm){
    console.error('请通过 mise run test 启动测试。')
    process.exitCode=1
  }else{
    const forwarded = args.length ? ['--',...args] : []
    const run = spawnSync(process.execPath,[npm,'run',`test:${suite}`,...forwarded],{cwd:root,stdio:'inherit',windowsHide:true})
    if(run.error)console.error(run.error.message)
    process.exitCode=run.status??1
  }
}
