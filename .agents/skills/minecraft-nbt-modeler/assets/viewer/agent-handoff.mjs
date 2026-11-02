import fs from 'node:fs/promises'
import path from 'node:path'

export async function handoffInfo(info) {
  const directory = path.join(info.workdir, 'Agent交接')
  const matches = []
  try {
    for (const item of await fs.readdir(directory, {withFileTypes:true})) {
      if (!item.isDirectory() || !/^review(?:[-_]|$)/.test(item.name)) continue
      const review = path.join(directory, item.name)
      try {
        const record = JSON.parse(await fs.readFile(path.join(review, 'review.json'), 'utf8'))
        if (path.resolve(record.source) === path.resolve(info.source) && record.source_sha256 === info.source_sha256) {
          matches.push({review, time:(await fs.stat(path.join(review, 'review.json'))).mtimeMs})
        }
      } catch {}
    }
  } catch (error) { if (error.code !== 'ENOENT') throw error }
  matches.sort((a,b)=>b.time-a.time)
  return {directory, review:matches[0]?.review ?? ''}
}

export async function writeHandoff({workspace,info,request,result,requestFile}) {
  const relative = file => {
    if (!file) return '未提供，需核对真实模型后补齐'
    const value = path.relative(workspace,file)
    return (path.isAbsolute(value) || value === '..' || value.startsWith('..'+path.sep) ? file : value).split(path.sep).join('/')
  }
  const directory = path.dirname(result.bundle)
  const shared = path.join(info.workdir,'Agent交接')
  const sharedRequest = path.join(directory,'request.json')
  await fs.writeFile(sharedRequest,await fs.readFile(requestFile),{flag:'wx'})
  const text = `请使用当前工作区的 .agents/skills/nbtcreator-workspace/SKILL.md 处理以下建筑修改任务。\n\n`+
    `项目内路径相对于当前工作区根目录；外部文件保留原路径。\n`+
    `- 源建筑：${relative(info.source)}\n- 源 SHA256：${request.source_sha256}\n`+
    `- 保护配置：${relative(request.context)}\n- 参数请求：${relative(sharedRequest)}\n`+
    `- 操作计划：${relative(result.plan)}\n- 计划校验包：${relative(result.bundle)}\n`+
    `- 共用交接文件夹：${relative(shared)}\n- 已关联审阅目录：${relative(request.review)}\n`+
    `- 已保存的修改意见：${relative(path.join(info.workdir,'修改意见'))}（若存在，读取与当前源版本匹配的意见）\n\n`+
    `请先读取源、参数和计划，解释实际要改的内容。文字备注与评论是需求，参数 JSON 是可执行工具设置。核对真实坐标、保护范围、变化预算和对应看图确认。\n`+
    `已有真实确认且对应源/配置一致时沿用；否则先提供审阅图并等待用户确认。本交接文件及“生成方案”操作本身不构成批准。不要伪造确认，也不要把候选统计写成已执行结果。\n\n`+
    `由你调用工具完成修改后，在源建筑所属工作文件夹内另建下一版本目录，保留原文件；交付完整主模型、NBT、验证记录和预览图。不要只覆盖旧文件，也不要把聊天方案当成已经完成的建筑。应用刷新建筑列表后应能选择新版本。\n\n`+
    `审阅目录未提供时，可从共用交接文件夹内查找与源哈希和保护配置匹配的 review-* 审阅记录；必须验证内容，不按目录名猜测已批准。
如需回到应用执行同一计划，可使用该共用交接文件夹里的审阅与确认资料；源或保护配置变化后重新审阅。\n`
  const file = path.join(directory,'交给Agent.md')
  await fs.writeFile(file,text,{flag:'wx'})
  return {handoff_text:text,handoff_file:file,handoff_root:shared}
}
