import fs from 'node:fs/promises'
import path from 'node:path'
import {skill} from './paths.mjs'
const file=path.join(skill,'tool-catalog.json'),catalog=JSON.parse(await fs.readFile(file,'utf8'))
const javascript='// Generated from ../tool-catalog.json. Run node scripts/sync-capabilities.mjs after edits.\n'+'globalThis.NbtToolCatalog = '+JSON.stringify(catalog,null,2)+';\n'
const markdown='# 应用与skill共用工具接口\n\n本文件由tool-catalog.json生成，不手改工具清单。应用工具选择器、提示词工作台和Python/CLI读取同一份源；Electron无需启动即可调用。\n\n默认工作区为Agent调用时的项目目录，资产位于 `nbt_models/`。使用相对路径，或显式指定 --workspace。\n\n| kind | 名称 | 起始参数与限制 |\n| --- | --- | --- |\n'+Object.entries(catalog.tools).map(([kind,[label,,hint]])=>`| ${kind} | ${label} | ${hint} |`).join('\n')+'\n\nGUI的“建模工具”支持同样的有序operations。Agent使用control plan/preview或原refine流程调用，旧的专用API保持兼容。计划、预览、应用、导出和精修确认是不同阶段；能力清单不授予任何批准。\n\n统一入口：`node scripts/cli.mjs capabilities`；独立复制skill后使用 `python <skill>/scripts/nbt_capabilities.py`。各命令参数请用 --help 查询。\n\n## 无界面命令\n\n'+Object.entries(catalog.commands).map(([name,script])=>`- ${name} → scripts/${script}`).join('\n')+'\n\n工作区入口为 `python .agents/skills/nbtcreator-workspace/nbt.py <命令>`。`feedback scan` 扫描结构版本的评论索引，`feedback collect/archive` 校验或归档意见证据，详见 [Agent读取意见](agent-feedback.md)。\n'
for(const [target,content]of [[path.join(skill,'prompt-console/catalog.js'),javascript],[path.join(skill,'references/exposed-tools.md'),markdown]]){
 if(process.argv.includes('--check')){if(await fs.readFile(target,'utf8')!==content)throw Error('Generated interface drift: '+path.relative(skill,target))}else await fs.writeFile(target,content)
}
console.log(JSON.stringify({passed:true,tools:Object.keys(catalog.tools).length,mode:process.argv.includes('--check')?'check':'sync'}))
