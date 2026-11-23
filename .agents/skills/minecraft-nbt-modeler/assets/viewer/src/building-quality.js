const labels = {
  completion: '建筑完成度', aesthetics: '美观度', circulation: '玩家通路合理性',
  style: '风格完成度', details: '细节质量',
}
const states = {
  pass: '静态必要路线与操作面通过', blocked: '存在必要通路或操作面阻塞', unsupported: '存在引擎能力缺口',
  pending: '待核查', undefined: '待定义', not_applicable: '不适用',
}

function element(tag, text) {
  const node = document.createElement(tag)
  node.textContent = text
  return node
}

function targetText(target) {
  const positions = target.positions ?? (target.position ? [target.position] : [])
  const part = target.interface ? `${target.part}.${target.interface}` : target.part
  return [part, target.activity, target.space, ...(target.parts ?? []), ...(target.spaces ?? []),
    ...positions.slice(0, 3).map(position => `(${position.join(', ')})`)].filter(Boolean).join(' · ')
}

export function initBuildingQuality({ api, source }) {
  const open = element('button', '整栋质量评分')
  open.id = 'building-quality-open'
  open.type = 'button'
  document.querySelector('.review-toolbar').append(open)
  const dialog = document.createElement('dialog')
  dialog.id = 'building-quality-dialog'
  dialog.className = 'review-help-dialog'
  dialog.innerHTML = `<header class="review-help-heading"><h2>整栋质量评分</h2><button type="button">关闭</button></header>
    <p>评估当前打开的制作版。实际看图记录可从审阅回执载入。</p>
    <details><summary>使用已有审阅或对照上一版</summary>
      <label>当前版审阅绑定（review_compare）<textarea data-review rows="3" spellcheck="false"></textarea></label>
      <label>上一版的制作源或建模失败回执绑定<textarea data-previous rows="3" spellcheck="false"></textarea></label>
    </details>
    <button type="button" class="primary" data-run>评估制作版</button>
    <p role="status"></p><div data-result></div><a download="building-quality.json" hidden>下载完整报告</a>`
  document.body.append(dialog)
  const run = dialog.querySelector('[data-run]')
  const status = dialog.querySelector('[role=status]')
  const result = dialog.querySelector('[data-result]')
  result.style.overflowWrap = 'anywhere'
  const download = dialog.querySelector('a')
  let binding

  function clear() {
    if (download.href) URL.revokeObjectURL(download.href)
    download.removeAttribute('href')
    download.hidden = true
    status.textContent = ''
    result.replaceChildren()
  }

  function showReport(report) {
    if (report.issues.length) {
      const list = document.createElement('ol')
      for (const issue of report.summary.priority_issues) {
        const row = element('li', `${issue.severity === 'blocker' ? '阻塞 · ' : ''}${issue.id} · ${issue.reason}`)
        const target = targetText(issue.target)
        if (target) row.append(element('p', target))
        row.append(element('p', issue.suggestion), element('p', issue.recheck))
        list.append(row)
      }
      result.append(element('h3', '优先处理'), list)
    }
    for (const [key, row] of Object.entries(report.dimensions)) {
      const score = row.score !== null ? `${row.score} 分`
        : row.interval ? `${row.interval.join('–')} 分` : (states[row.status] ?? '待核查')
      const coverage = row.coverage === null ? '' : ` · 证据覆盖 ${row.coverage}%`
      const sites = key === 'style' && row.applicable_sites
        ? ` · 达标 ${row.sites_at_standard}/${row.applicable_sites} 处`
        : ''
      result.append(element('p', `${labels[key]}　${score}${coverage}${sites}`))
    }
    if (report.review_gap) {
      const { reason, stale_views: views } = report.review_gap
      result.append(element('p', reason || (views.length ? `需要复查机位 ${views.join('、')}` : '部分评分仍缺少登记机位的观察。')))
    }
  }

  function showComparison(comparison) {
    result.append(element('h3', '续版复验'))
    const issueStates = {new: '新增', persistent: '持续', resolved_retested: '已复验解决', needs_review: '待复核'}
    for (const row of comparison.issues) result.append(element('p', `${issueStates[row.status]} · ${row.id}`))
    for (const [key, row] of Object.entries(comparison.dimensions)) {
      const delta = row.delta === null ? '待补齐相同条件的证据' : `${row.delta >= 0 ? '+' : ''}${row.delta} 分`
      result.append(element('p', `${labels[key]}　${delta}`))
    }
  }

  open.onclick = () => {
    const current = source()
    if (current?.source !== binding?.source || current?.source_sha256 !== binding?.source_sha256) {
      clear()
      dialog.querySelector('[data-review]').value = ''
      dialog.querySelector('[data-previous]').value = ''
    }
    binding = current
    run.disabled = !binding
    if (!binding) status.textContent = '请先打开建筑制作版。'
    dialog.showModal()
  }
  dialog.querySelector('header button').onclick = () => dialog.close()
  run.onclick = async () => {
    const current = binding
    clear()
    run.disabled = true
    status.textContent = '正在检查制作源与审阅证据…'
    try {
      const review = dialog.querySelector('[data-review]').value.trim()
      const previous = dialog.querySelector('[data-previous]').value.trim()
      const request = { ...current, ...(review ? { review: JSON.parse(review) } : {}) }
      const report = await api('architect/quality-check', request)
      const comparison = previous
        ? await api('architect/quality-compare', { ...request, previous: JSON.parse(previous) })
        : null
      if (current !== binding || current.source_sha256 !== source()?.source_sha256 || current.source !== source()?.source)
        throw Error('当前制作版已变化，请重新评估。')
      status.textContent = states[report.summary.gate]
      showReport(report)
      if (comparison) showComparison(comparison)
      dialog.querySelector('details').open = false
      download.href = URL.createObjectURL(new Blob([JSON.stringify(comparison ? { report, comparison } : report, null, 2)],
        { type: 'application/json' }))
      download.hidden = false
    } catch (error) {
      status.textContent = error.message
    } finally {
      run.disabled = !binding
    }
  }
}
