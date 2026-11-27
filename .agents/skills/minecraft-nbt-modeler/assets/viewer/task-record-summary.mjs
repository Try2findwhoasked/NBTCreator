export const labels = {
  batch: '批量预览与检查', ai: 'AI 构建 / 方案', plan: '生成修改方案', preview: '效果预览',
  open: '打开建筑', snapshot: '载入3D模型', render: '纹理出图', revision: '导出建筑新版本',
  prepare: '生成审阅图', apply: '已确认精修', preset: '保存参数', validate: '检查候选效果',
  compare: '只读版本对比', 'walk-inspect': '玩家尺度与通路检查'
}
export const statuses = { running: '运行中', complete: '已完成', failed: '失败', cancelled: '已取消' }

export const downloadFields = [
  ['master_download', 'SNBT 制作源', 'model.snbt'],
  ['plan_download', '操作计划', 'plan.json'],
  ['validation_download', '候选检查报告', 'validation.json'],
  ['difference_download', '差异报告', 'difference.json'],
  ['report_download', '通路检查报告', 'walk-inspection.json']
]

export function effectiveStatus(job) {
  const result = job.result
  const failed = job.kind === 'validate' && result?.passed === false ||
    job.kind === 'walk-inspect' && result?.report?.passed === false ||
    job.kind === 'batch' && result?.progress?.failed > 0
  return failed ? 'failed' : job.status
}

export function summarizeJob(job, revision) {
  const { id, kind, label, phase, status, created_at, completed_at, directory, screenshot } = job
  const result = job.result ?? {}
  const error = job.error?.slice(0, 500)
  const downloadCount = (result.nbt_downloads?.length ?? 0) +
    downloadFields.filter(([key]) => result[key]).length
  return { id, kind, label, phase, status, created_at, completed_at, directory, screenshot, error,
    source: job.source ?? result.source, last_message: job.events?.at(-1)?.message, downloadCount, revision,
    result: {
      output: result.output, draft_only: result.draft_only, passed: result.passed,
      changed_blocks: result.changed_blocks, wall_membership_changes: result.wall_membership_changes,
      operations: Array.isArray(result.operations) ? result.operations.length : result.operations,
      summary: typeof result.summary === 'string' ? result.summary.slice(0, 1000) : undefined,
      preview_only: result.preview_only, runtime_count: result.runtime_files?.length,
      report: kind === 'walk-inspect' && result.report ? {
        passed: result.report.passed, search_limit_reached: result.report.search_limit_reached,
        target_count: result.report.targets?.length ?? 0
      } : undefined,
      progress: kind === 'batch' && result.progress ? { failed: result.progress.failed } : undefined
    }
  }
}

export function matchesJob(job, query, filter) {
  const status = effectiveStatus(job)
  if (filter !== 'all' && status !== filter) return false
  return !query || [job.kind, job.label, job.instruction, labels[job.kind], status, statuses[status],
    job.source, job.directory, job.result?.output, job.error]
    .some(value => String(value ?? '').toLowerCase().includes(query))
}
