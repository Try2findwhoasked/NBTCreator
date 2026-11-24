const labels = {planned: '待绑定参考图', references_bound: '待绑定制作源', baseline_bound: '制作与复验',
  review_ready: '候选审阅完成', draft_saved: '制作版已保存', pending: '待领取', claimed: '已领取',
  submitted: '已回传', checked: '已预检', adopted: '已采纳'}

function element(tag, text, className) {
  const node = document.createElement(tag)
  if (text) node.textContent = text
  if (className) node.className = className
  return node
}

const bounds = box => `${box.lo.join(', ')} → ${box.hi.join(', ')}`

function image(row, label) {
  const area = element('figure')
  if (row.url) {
    const img = element('img')
    img.src = row.url
    img.alt = label
    img.loading = 'lazy'
    img.addEventListener('error', () => img.replaceWith(element('p', '图像已变化或无法读取')))
    area.append(img)
  }
  area.append(element('figcaption', label))
  return area
}

function drawPackages(run) {
  const nodes = new Map(run.packages.map(pack => [pack.id, element('li')]))
  const tree = element('ul', '', 'authoring-package-tree')
  for (const pack of run.packages) {
    const node = nodes.get(pack.id)
    node.dataset.packageId = pack.id
    node.append(element('strong', `${pack.id} · ${labels[pack.status] ?? pack.status}`))
    if (pack.write_boxes.length) node.append(element('p', `写区 ${pack.write_boxes.map(bounds).join(' / ')}`))
    if (pack.depth > 1 && pack.read_boxes.length) node.append(element('p', `读取 ${pack.read_boxes.map(bounds).join(' / ')}`))
    if (pack.protected_boxes.length) node.append(element('p', `保护 ${pack.protected_boxes.map(bounds).join(' / ')}`))
    if (pack.components?.length) node.append(element('p', pack.components.map(row => `${row.id} · ${row.intent}`).join(' / ')))
    node.append(element('ul'))
  }
  for (const pack of run.packages) {
    const parent = nodes.get(pack.parent_id)
    const container = parent?.lastChild ?? tree
    container.append(nodes.get(pack.id))
  }
  return tree
}

export function mountAuthoringWorkflow(detail, task, {api, button, openDraft, getDraft}) {
  const attempts = task.runs ?? []
  if (!attempts.length) return
  const section = element('section', '', 'authoring-workflow')
  section.append(element('h4', '参考图与分区建模'))
  const actions = element('div', '', 'batch-link-actions')
  const body = element('div')
  section.append(actions, body)
  detail.append(section)

  for (const attempt of attempts.filter(row => row.stage === 'authoring')) {
    const command = async (method, params, requestId = crypto.randomUUID()) => {
      const reply = await api(`authoring/${method}`, {request_id: requestId,
        params: {batch_id: task.id, run_id: attempt.id, ...params}})
      if (!reply.ok) {
        const error = reply.error
        throw Object.assign(new Error(error.message), {code: error.code, details: error.details})
      }
      return reply.data
    }

    async function withLead(run, action) {
      const packageRevision = run.packages.find(pack => pack.id === 'root').revision
      const claim = await command('claim', {package_id: 'root', package_revision: packageRevision, owner: '桌面工作台'})
      const lease = {package_id: 'root', package_revision: packageRevision, lease_token: claim.lease_token, fence: claim.lease.fence}
      try { return await action(lease) }
      finally { await command('release', lease).catch(() => {}) }
    }

    async function load() {
      body.replaceChildren(element('p', '正在读取制作运行…'))
      try { draw(await command('inspect', {view: 'full'})) }
      catch (error) { body.replaceChildren(element('p', error.message)) }
    }

    function draw(run) {
      body.replaceChildren(element('p', `${labels[run.phase] ?? run.phase} · ${run.task}`))
      const stale = new Set(run.reference_issues.map(row => row.id))
      if (stale.size) body.append(element('p', '参考图已变化，请恢复冻结图像或开启新运行。', 'authoring-conflict'))
      for (const row of run.references?.images ?? []) {
        body.append(image(row, `${row.role}${stale.has(row.id) ? ' · 已失效' : ''}`))
      }
      if (run.spaces.length) {
        const spaces = element('ul')
        for (const room of run.spaces) spaces.append(element('li', `${room.id} · ${room.purpose} · ${bounds(room.box)}`))
        body.append(spaces)
      }
      if (run.packages.length) body.append(drawPackages(run))
      const failure = element('p', '', 'authoring-conflict')
      failure.setAttribute('role', 'status')
      body.append(failure)
      const root = run.packages.find(pack => pack.id === 'root')
      const candidates = run.packages.filter(pack => ['submitted', 'checked'].includes(pack.status))
        .map(pack => ({package_id: pack.id, sha256: pack.candidate_sha256}))
      const disabled = Boolean(stale.size || root?.status !== 'pending')
      const execute = action => async () => {
        try { await action() }
        catch (error) {
          const positions = error.details?.dependencies ?? error.details?.conflicts
          failure.textContent = positions?.length ? `${error.message} ${JSON.stringify(positions.slice(0, 8))}` : error.message
        }
      }
      if (!run.draft && candidates.length) {
        body.append(button('预检全部已回传工作包', execute(async () => {
          await withLead(run, lease => command('plan_merge', {...lease, run_revision: run.revision,
            parent_source_sha256: run.baseline.source_sha256, candidates}))
          await load()
        }), {disabled}))
      }
      for (const merge of run.merges) {
        const card = element('article', '', 'batch-linked-item')
        card.append(element('strong', `合模候选 · ${merge.difference.changed_blocks} 格`))
        const reviews = run.reviews.filter(row => row.merge_sha256 === merge.merge_sha256)
        const candidate = reviews.filter(row => row.target === 'candidate').sort((a,b) => b.run_revision - a.run_revision)[0]
        const draftReview = reviews.filter(row => row.target === 'draft').sort((a,b) => b.run_revision - a.run_revision)[0]
        const shown = draftReview ?? candidate
        if (shown) {
          if (shown.missing_rooms.length) card.append(element('p', `待复验空间 ${shown.missing_rooms.join('、')}`))
          for (const issue of shown.issues) card.append(element('p', `${issue.id} · ${issue.text}`))
          const pair = element('div', '', 'authoring-images')
          for (const row of shown.observations) {
            pair.append(image(shown.renders.before.images[row.view], `${row.view} · ${row.before}`),
              image(shown.renders.after.images[row.view], `${row.view} · ${row.after}`))
          }
          card.append(pair)
        } else card.append(element('p', '待登记实景观察'))
        if (run.phase === 'review_ready' && candidate?.ready) {
          card.append(button('保存为可编辑制作版', execute(async () => {
            await withLead(run, lease => command('save_draft', {...lease, run_revision: run.revision,
              parent_source_sha256: run.baseline.source_sha256, candidates: merge.candidates,
              merge_sha256: merge.merge_sha256, review_sha256: candidate.sha256}))
            await load()
          }), {disabled}))
        }
        body.append(card)
      }
      if (run.draft) {
        const source = getDraft(run.draft.absolute_source) ?? {source: run.draft.absolute_source,
          name_zh: task.name, object_name: task.name, relative_path: run.draft.source, unverified: true}
        body.append(element('p', run.draft.source), element('p', run.draft.visual_review === 'pending' ? '落盘版待出图复验' : '已有落盘版实景观察'))
        if (source) body.append(button('打开制作版', () => openDraft(source)))
      }
    }
    actions.append(button(attempts.length === 1 ? '读取制作运行' : `读取运行 ${attempt.id.slice(0, 8)}`, load))
  }
  if (!actions.childElementCount) section.remove()
}
