import fs from 'node:fs/promises'
import path from 'node:path'
import assert from 'node:assert/strict'
import {skill} from './paths.mjs'
const file=path.join(skill,'tool-catalog.json'),catalog=JSON.parse(await fs.readFile(file,'utf8'))
for(const [name,args] of Object.entries(catalog.command_prefixes)){
  assert.ok(Object.hasOwn(catalog.commands,name),`Unknown command prefix: ${name}`)
  assert.ok(Array.isArray(args)&&args.every(arg=>typeof arg==='string'&&arg.length>0),`Invalid command prefix: ${name}`)
}
for(const [name,target] of Object.entries(catalog.command_aliases)){
  assert.ok(name!=='doctor'&&!Object.hasOwn(catalog.commands,name),`Command alias conflicts: ${name}`)
  assert.ok(Array.isArray(target)&&Object.hasOwn(catalog.commands,target[0])&&target.every(arg=>typeof arg==='string'&&arg.length>0),`Invalid command alias: ${name}`)
}
for(const entries of Object.values(catalog.tool_routes)){
  for(const {title,call,call_kind='命令',contract,guide,input,result,next} of entries){
    assert.ok([title,call,input,result].every(value=>typeof value==='string'&&value.trim()),'速查路线应注明起点、输入和产物')
    assert.ok(['命令','JSON 字段','多步流程'].includes(call_kind),`未知调用类型: ${title}`)
    if(call_kind==='命令')assert.ok(Object.hasOwn(catalog.commands,call.split(' ')[0])||
      Object.hasOwn(catalog.command_aliases,call.split(' ')[0]),`未知速查命令: ${call}`)
    if(contract!==undefined)assert.ok(typeof contract==='string'&&contract.trim(),`缺少字段查询: ${title}`)
    if(next!==undefined)assert.ok(typeof next==='string'&&next.trim(),`缺少接续动作: ${title}`)
    if(guide!==undefined)assert.ok(/^[a-z0-9-]+\.md$/.test(guide)&&
      (await fs.stat(path.join(skill,'references',guide))).isFile(),`未知路线指南: ${guide}`)
  }
}
const partInterfaces=plan=>plan.properties.parts.items.properties.interfaces
const architecture=catalog.architecture
const authored=partInterfaces(architecture.plan)
const literal=structuredClone(authored.items.anyOf[0])
for(const [key,field] of Object.entries(literal.properties)){
  const schema=field.anyOf[0]
  if(schema.type==='array')schema.items=schema.items.anyOf[0]
  literal.properties[key]=schema
}
const scene=catalog.agent_tools.scene_compile.parameters.properties.graph.properties.objects.items.properties.interfaces.items
assert.deepEqual(literal,scene,'建筑接口的字面量字段必须与对象图一致')
for(const action of ['plan-save','plan-build']){
  assert.deepEqual(partInterfaces(architecture.actions[action].properties.plan),authored,action+' 建筑接口必须与主方案一致')
  assert.deepEqual(architecture.actions[action].properties.plan.properties.views.items.properties.sample_box,
    architecture.plan.properties.views.items.properties.sample_box,action+' 局部取景范围必须与主方案一致')
}
const sceneTools=catalog.agent_tools
const relationLocks=sceneTools.scene_compile.parameters.properties.graph.properties.relation_locks
assert.deepEqual(sceneTools.scene_save.parameters.properties.graph.properties.relation_locks,relationLocks)
assert.deepEqual(sceneTools.scene_update.parameters.properties.add_locks,relationLocks)
assert.deepEqual(sceneTools.scene_update.parameters.properties.release_locks,sceneTools.scene_save.parameters.properties.release_locks)
const javascript='// Generated from ../tool-catalog.json. Run node scripts/sync-capabilities.mjs after edits.\n'+'globalThis.NbtToolCatalog = '+JSON.stringify(catalog,null,2)+';\n'
const markdown='# 应用与skill共用工具接口\n\n本文件由tool-catalog.json生成，不手改工具清单。应用工具选择器、提示词工作台和Python/CLI读取同一份源；Electron无需启动即可调用。\n\n默认工作区为Agent调用时的项目目录，资产位于 `nbt_models/`。使用相对路径，或显式指定 --workspace。\n\n| kind | 名称 | 起始参数与限制 |\n| --- | --- | --- |\n'+Object.entries(catalog.tools).map(([kind,[label,,hint]])=>`| ${kind} | ${label} | ${hint} |`).join('\n')+'\n\nGUI的“建模工具”支持同样的有序operations。每步 enabled 为可选布尔开关，省略等于 true；false 保留在设置/计划中，但编译与执行跳过，不写任何方块。名称由 label 保存，数组顺序决定执行顺序。Agent使用control plan/preview或原refine流程调用，旧的专用API保持兼容。计划、预览、应用、导出和精修确认是不同阶段；能力清单不授予任何批准。\n\n统一入口：`mise run nbt -- capabilities`；独立复制skill后使用 `python <skill>/scripts/nbt_capabilities.py`。各命令参数请用 --help 查询。overwrite/write_group是可选操作元数据，见tool-catalog.json的optional_operation_fields；未提供时保留原工具行为。AI与构件放置的显式覆盖开关不能越过保护和预算。\n\n## 无界面命令\n\n'+Object.entries(catalog.commands).map(([name,script])=>`- ${name} → scripts/${script}`).join('\n')+'\n\n工作区入口为 `mise run nbt -- <命令>`。`feedback scan` 扫描结构版本的评论索引，`feedback collect/archive` 校验或归档意见证据，详见 [Agent读取意见](agent-feedback.md)。\n\n外部Agent改模后的版本登记和评论核对见 [任务回传](agent-task-return.md)，agent-tasks get/record 与应用共用源哈希；确定性检查的通俗解释与定位见 [检查结果解释](diagnostic-guidance.md)，diagnostics 只解释已保存报告，不重新验证或自动修复；按任务挑选资料片段和复用资产见 [本地参考检索](reference-retrieval.md)，retrieve search/bundle/read 共用来源哈希；选区自然语言工具步骤见 [选区编辑](selection-edit.md)，selection-edit context/compile 共用真实方块摘要、坐标平移与写入范围约束；构件的保存、整理、导入及候选放置见 [构件资产](component-assets.md)；参数化工具序列、材质主题和XYZ网格阵列见 [配方与主题](reusable-recipes.md)，recipes compile与components batch仅返回候选步骤；批量创作的过程目录、模型关联与交付图册见 [制作批次](batch-workspaces.md)，batches create/record/list/get/locate 在应用外也可使用；项目多选、只读批量预览与检查、进度及重试见 [项目批量任务](project-batch.md)；内部 API 与外部 Agent 共用的各区域创作参数见 [AI创作偏好](ai-creative-preferences.md)。\n'
const aliasesMarkdown='\n兼容入口\n\n'+Object.entries(catalog.command_aliases).map(([name,args])=>`- \`${name}\` → \`${args.join(' ')}\``).join('\n')+'\n'
const cellCode=value=>'`'+value.replaceAll('|','\\|')+'`'
const routeMarkdown='\n## 创作速查\n\n从创作项目根目录用生成 Skill 所示前缀执行 `capabilities --routes` 单独查询这张表。已知命令可查 `<命令> --help`。工作区有同名任务时，前缀会指向文件任务。专题从已启用的知识中选读。\n\n'+
  Object.entries(catalog.tool_routes).map(([category,entries])=>
    `### ${category}\n\n| 任务 | 起点 | 契约或示例 | 输入 | 产物与接续 |\n| --- | --- | --- | --- | --- |\n`+
    entries.map(({title,call,call_kind='命令',contract,guide,input,result,next})=>{
      const reference=[contract&&cellCode(contract),guide&&`[请求与用例](${guide})`].filter(Boolean).join('<br>')
      return `| ${title} | ${call_kind} ${cellCode(call)} | ${reference} | ${input} | ${result}${next?`<br>${next}`:''} |`
    }).join('\n')
  ).join('\n\n')+
  '\n\n### 路径和状态\n\n'+
  '源码入口的全局 `--workspace <目录>` 放在子命令之前，启动器在所选创作目录执行。一些 Python 子命令另有自己的 `--workspace`，用子命令帮助核对。相对 `--request` 文件路径从命令工作目录解析；JSON 内的建筑或工作模型资源相对于创作工作区，control 和 selection-edit 的资源相对于命令工作目录。文件内明确以元数据为基准的引用仍从该元数据所在目录解析。完整 capabilities 的 `cli_path_bases` 给出这几个基准。\n\n'+
  '先看进程退出码，再看该命令的业务状态和源绑定。参数用法错误通常退出 2。建筑或工作模型执行失败退出 1，检查 `error`、`code` 和 `conflicts`；过期绑定还可查看 `recovery`。候选 validate 生成失败报告时仍可返回 `ok:true`，但 `result.passed:false` 且退出 1。紧凑任务回执用 `source_matches`、`next` 和 `expand` 判断可否接续。看图确认及显式定稿需各自的用户授权。\n'
const agentMarkdown='\n## 共用结构 Agent 工具\n\n'+'`'+catalog.agent_contract.cli+'`'+'\n\n内部 API 与外部 CLI 调用同一 Python 实现；参数 Schema 见 capabilities.agent_tools。预览、保存新资产、候选放置和显式 NBT 导出保持独立。\n\n| 工具 | 用途 |\n| --- | --- |\n'+Object.entries(catalog.agent_tools).map(([name,tool])=>`| ${name} | ${tool.description} |`).join('\n')+'\n'
for(const [target,content]of [[path.join(skill,'prompt-console/catalog.js'),javascript],[path.join(skill,'references/exposed-tools.md'),markdown+aliasesMarkdown+routeMarkdown+agentMarkdown+'\n\n## 外部 Agent 机器接口\n\n`machine --schema` 返回 tool-catalog.json 的 machine_protocol 契约；`machine --request <JSON>` 使用统一请求与错误封装。任务领取、超时重领、幂等重试和批注独立接口见 [机器接口说明](agent-protocol.md)。\n']]){
 if(process.argv.includes('--check')){if(await fs.readFile(target,'utf8')!==content)throw Error('Generated interface drift: '+path.relative(skill,target))}else await fs.writeFile(target,content)
}
console.log(JSON.stringify({passed:true,tools:Object.keys(catalog.tools).length,mode:process.argv.includes('--check')?'check':'sync'}))
