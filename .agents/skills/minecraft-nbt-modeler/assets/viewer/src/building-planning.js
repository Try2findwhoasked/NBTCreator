import './building-planning.css'
import demo from '../../examples/whole-building-planning.json'

const colors = ['#386b83', '#786348', '#607754', '#765b7f', '#8b6359', '#4c7480']
const statusText = { passed: '通过', failed: '未通过', pending: '待测' }
const searchText = {
  found: '找到可行候选', infeasible: '搜索范围内无可行布局',
  budget_exhausted: '已用完搜索预算', input_required: '需补齐固定停靠点',
}
const reasonText = {
  missing_stair_landings: '需指定楼梯上下端脚位', landing_height_mismatch: '停靠点与楼层标高不符',
  fixed_region_misses_landing: '锁定区域未包含固定停靠点', unsupported_collision: '含未认证的碰撞形状',
  search_limit: '通路检查达到预算', blocked_route: '实际路线受阻', missing_endpoint: '缺失脚位',
  missing_bound_stair: '制作源缺少指定梯段', connection_in_search_branch: '试排分支中连接不足',
  capacity_in_search_branch: '试排分支中可用格不足', anchor_in_search_branch: '试排分支中固定站位受阻',
  condition_in_search_branch: '试排分支未满足条件',
}
const ruleText = {
  search_capacity: '剩余布局容量', space_placed: '空间已落位', space_bounds: '边界和保留区', space_overlap: '空间重叠',
  net_area: '净地面格数', usable_square_span: '可用方形跨度', space_feet: '指定站位',
  door: '直通门可穿越宽度', adjacent: '相邻界线', wall: '实际共墙', stair: '跨层连接', route: '指定路线',
  entry: '入口站位', entry_in_space: '入口所属空间', entry_reachability: '从入口可达',
  floor_void: '挑空楼层填占', building_extent: '整栋外包尺寸', building_footprint: '围护占地越界', headroom: '指定净高', stair_anchors: '固定楼梯停靠点', fixed_landing: '锁定空间与停靠点',
}
function saveJSON(name, data) {
  const href = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }))
  const link = document.createElement('a')
  link.href = href
  link.download = name
  link.click()
  setTimeout(() => URL.revokeObjectURL(href), 500)
}

const byId = (items, id) => items?.find(row => row.id === id)
const json = value => JSON.stringify(value, null, 2)
const measure = value => value === true ? '是' : value === false ? '否' : value == null ? '—' :
  typeof value === 'object' ? (value.min !== undefined ? value.min + '–' + value.max : JSON.stringify(value)) : String(value)

function node(tag, text) {
  const item = document.createElement(tag)
  if (text !== undefined) item.textContent = text
  return item
}

function floorGraphic(canvas, drawing, levelId, section, sectionZ, marks) {
  const ctx = canvas.getContext('2d')
  ctx.clearRect(0, 0, canvas.width, canvas.height)
  if (!drawing) return
  const [width, height, depth] = drawing.size
  const vertical = section ? height : depth
  const scale = Math.min((canvas.width - 66) / width, (canvas.height - 52) / vertical)
  const x = value => 38 + value * scale
  const y = value => section ? canvas.height - 30 - value * scale : 20 + value * scale
  const gridText = getComputedStyle(canvas).color
  function rect(left, bottom, right, top, fill, stroke) {
    const leftPx = x(left)
    const topPx = y(section ? top : bottom)
    const w = (right - left) * scale, h = (top - bottom) * scale
    ctx.fillStyle = fill
    ctx.fillRect(leftPx, topPx, w, h)
    if (stroke) {
      ctx.strokeStyle = stroke
      ctx.strokeRect(leftPx, topPx, w, h)
    }
  }
  const selectedLevel = byId(drawing.levels, levelId)
  if (section) {
    for (const level of drawing.levels) {
      const footY = y(level.feet_y)
      ctx.strokeStyle = '#84939d'
      ctx.beginPath()
      ctx.moveTo(x(0), footY)
      ctx.lineTo(x(width), footY)
      ctx.stroke()
      ctx.fillStyle = gridText
      ctx.font = '12px system-ui'
      ctx.fillText(String(level.feet_y), 8, footY + 4)
    }
  } else if (selectedLevel) {
    for (const box of selectedLevel.footprint) rect(...box.lo, box.hi[0] + 1, box.hi[1] + 1, '#eff1ee', '#9aa39c')
    for (const box of selectedLevel.voids ?? []) rect(...box.lo, box.hi[0] + 1, box.hi[1] + 1, '#f5e9c8', '#ad8b41')
    for (const box of selectedLevel.reserved ?? []) rect(...box.lo, box.hi[0] + 1, box.hi[1] + 1, '#dacbeb', '#9075a3')
  }
  drawing.spaces.forEach((room, index) => {
    const level = byId(drawing.levels, room.level)
    if (!section && room.level !== levelId) return
    let label = true
    for (const box of room.regions) {
      if (section && (sectionZ < box.lo[1] || sectionZ > box.hi[1])) continue
      const start = section ? level.feet_y : box.lo[1]
      const stop = section ? level.ceiling_y : box.hi[1] + 1
      rect(box.lo[0], start, box.hi[0] + 1, stop, colors[index % colors.length], '#f9f7f1')
      if (label && (box.hi[0] - box.lo[0] + 1) * scale > 38 && (stop - start) * scale > 18) {
        const labelWidth = (box.hi[0] - box.lo[0] + 1) * scale - 12
        ctx.fillStyle = '#fff'
        ctx.font = '13px system-ui'
        ctx.fillText(room.name, x(box.lo[0]) + 6, y(section ? stop : start) + 17, labelWidth)
        label = false
      }
    }
  })
  if (!section) {
    for (const link of drawing.links) {
      if (link.level === levelId && link.opening) {
        const box = link.opening
        rect(...box.lo, box.hi[0] + 1, box.hi[1] + 1, '#e2a95a', '#725222')
      }
    }
  }
  const points = marks.length ? marks : [drawing.entry]
  for (const [px, py, pz] of points) {
    if (section ? Math.floor(pz) !== sectionZ : !marks.length && py !== selectedLevel?.feet_y) continue
    ctx.beginPath()
    ctx.arc(x(Math.floor(px) + .5), y(section ? py : Math.floor(pz) + .5), marks.length ? 6 : 4, 0, Math.PI * 2)
    ctx.fillStyle = marks.length ? '#d44738' : '#fff'
    ctx.fill()
    ctx.lineWidth = 2
    ctx.strokeStyle = marks.length ? '#fff' : '#253f4a'
    ctx.stroke()
    ctx.lineWidth = 1
  }
  ctx.font = '12px system-ui'
  ctx.fillStyle = gridText
  ctx.fillText(section ? 'X → · 剖切 Z = ' + sectionZ : 'X → · Z ↓', 38, canvas.height - 7)
}

export function initBuildingPlanning({ api, context, openMenu }) {
  const launch = node('button', '整栋建筑规划')
  launch.id = 'open-building-planning'
  launch.type = 'button'
  const dialog = node('dialog')
  dialog.id = 'building-planning-dialog'
  dialog.className = 'architect-dialog'
  dialog.setAttribute('aria-labelledby', 'building-planning-title')
  dialog.innerHTML = '<header><h2 id="building-planning-title">整栋建筑规划</h2><button type="button" data-close>关闭</button></header>' +
    '<section class="architect-body planning-body"><div class="planning-actions" data-inputs>' +
    '<button type="button" data-sample>载入示例</button><label>导入布局请求<input type="file" data-import accept=".json,application/json"></label>' +
    '<button type="button" data-check>检查布局</button><button type="button" data-search>生成候选</button>' +
    '<button type="button" data-actual>核对当前制作版</button></div>' +
    '<div class="planning-columns"><div><fieldset data-area-editor hidden><legend>房间面积</legend><label>空间<select data-space></select></label>' +
    '<div class="planning-area"><label>最小面积<input data-min type="number" step="1" min="1"></label>' +
    '<label>目标面积<input data-target type="number" step="1" min="1"></label>' +
    '<label>最大面积<input data-max type="number" step="1" min="1"></label></div>' +
    '<label class="planning-lock"><input type="checkbox" data-lock>生成候选时保留此空间</label></fieldset>' +
    '<details data-author open><summary>任务书与布局 JSON</summary>' +
    '<label>任务书 JSON<textarea data-program rows="8" spellcheck="false"></textarea></label>' +
    '<label>布局 JSON<textarea data-layout rows="7" spellcheck="false"></textarea></label></details></div>' +
    '<div><div class="planning-views"><label>图面<select data-view><option value="floor">逐层平面</option>' +
    '<option value="section">建筑剖面</option></select></label><label>楼层<select data-level></select></label>' +
    '<label data-cut-label hidden>剖切 Z<input data-cut type="number" step="1" min="0"></label></div>' +
    '<canvas width="660" height="370" aria-label="整栋规划平面与剖面"></canvas>' +
    '<div data-candidates class="planning-candidates"></div><div class="planning-actions">' +
    '<button type="button" data-use hidden>采用当前布局</button><button type="button" data-download hidden>下载当前布局</button>' +
    '<label data-bind-label hidden>绑定建筑方案模板<input type="file" data-bind accept=".json,application/json"></label></div>' +
    '<div data-report></div></div></div></section><footer><p role="status" class="architect-status"></p></footer>'
  document.body.append(dialog)
  const pick = key => dialog.querySelector('[data-' + key + ']')
  const program = pick('program'), layout = pick('layout')
  const level = pick('level'), view = pick('view'), cut = pick('cut')
  const canvas = dialog.querySelector('canvas')
  const status = dialog.querySelector('[role="status"]')
  const fixed = new Set()
  let busy = false, options = [], selected = 0, current = null, currentProgram = null, currentLayout = null, marks = []

  const readProgram = () => JSON.parse(program.value)
  const readLayout = () => JSON.parse(layout.value || '{"spaces":[]}')
  const request = () => ({ program: readProgram(), layout: readLayout() })
  const source = () => {
    const state = context()
    const info = state.info
    return !state.versionComparing && info?.source && info?.source_sha256
      ? { source: info.source, source_sha256: info.source_sha256 } : null
  }
  function draw() {
    const section = view.value === 'section'
    pick('cut-label').hidden = !section
    level.closest('label').hidden = section
    floorGraphic(canvas, current?.drawing, level.value, section, Number(cut.value || 0), marks)
  }
  function focus(row) {
    marks = row.positions ?? []
    if (row.level) level.value = row.level
    else if (marks.length && current?.drawing) {
      const floors = current.drawing.levels
      const nearest = floors.reduce((a, b) => Math.abs(a.feet_y - marks[0][1]) <=
        Math.abs(b.feet_y - marks[0][1]) ? a : b)
      level.value = nearest.id
    }
    if (view.value === 'section' && marks.length) cut.value = Math.floor(marks[0][2])
    if (marks.length) status.textContent = '定位 ' + row.id + ' · XYZ ' + marks[0].join(', ')
    draw()
  }
  function present(report, userProgram = null, userLayout = null) {
    current = report
    currentProgram = userProgram
    currentLayout = userLayout
    marks = []
    const previous = level.value
    const floors = report?.drawing?.levels ?? []
    level.replaceChildren(...floors.map(row => new Option(row.id + ' · Y ' + row.feet_y, row.id)))
    if (floors.some(row => row.id === previous)) level.value = previous
    cut.max = (report?.drawing?.size[2] ?? 1) - 1
    cut.value = Math.min(Number(cut.value || 0), Number(cut.max))
    const target = pick('report')
    target.replaceChildren()
    if (report?.spaces) {
      for (const [id, area] of Object.entries(report.spaces)) {
        const room = byId(report.drawing.spaces, id)
        target.append(node('p', room.name + ' · 净地面 ' + area.net_area + ' 格² · 可达 ' + measure(area.reachable_area) + ' 格²'))
      }
    }
    for (const row of [...(report?.checks ?? [])].sort((a, b) => Number(a.passed) - Number(b.passed))) {
      const item = node('button', (statusText[row.status] ?? row.status) + ' · ' + (ruleText[row.kind] ?? row.kind) +
        ' · ' + row.id + ' · 目标 ' + measure(row.expected) + ' / 实测 ' + measure(row.actual) +
        (row.reason ? ' · ' + (reasonText[row.reason] ?? row.reason) : ''))
      item.type = 'button'
      item.className = 'planning-finding'
      item.dataset.status = row.status
      item.disabled = !row.positions?.length
      item.onclick = () => focus(row)
      target.append(item)
    }
    pick('use').hidden = !userLayout || options.length === 0
    pick('download').hidden = !userLayout || !userProgram
    pick('bind-label').hidden = pick('download').hidden || !report.passed
    draw()
  }
  function showOptions() {
    const results = pick('candidates')
    results.replaceChildren()
    options.forEach((candidate, index) => {
      const m = candidate.report.metrics
      const label = '候选 ' + (index + 1) + ' · 面积偏差 ' + m.area_target_deviation +
        ' 格² · 交通面积 ' + m.circulation_area + ' 格² · 改动空间 ' + candidate.changed_spaces
      const item = node('button', label)
      item.type = 'button'
      item.setAttribute('aria-pressed', String(index === selected))
      item.onclick = () => {
        selected = index
        present(candidate.report, readProgram(), candidate.layout)
        showOptions()
      }
      results.append(item)
    })
  }
  function updateAreaFields() {
    let rooms
    try { rooms = readProgram().spaces } catch { rooms = [] }
    const usable = Array.isArray(rooms) ? rooms.filter(row => row?.id && row.purpose) : []
    const old = pick('space').value
    pick('space').replaceChildren(...usable.map(room => new Option(room.purpose, room.id)))
    if (usable.some(room => room.id === old)) pick('space').value = old
    pick('area-editor').hidden = usable.length === 0
    const room = byId(usable, pick('space').value)
    for (const field of ['min', 'target', 'max']) pick(field).value = room?.[field + '_area'] ?? ''
    pick('lock').checked = fixed.has(room?.id)
  }
  function clearResults() {
    options = []
    selected = 0
    status.textContent = ''
    showOptions()
    present(null)
  }
  function load(value) {
    if (!value.program || !value.layout) throw Error('需要包含 program 与 layout 的规划请求。')
    program.value = json(value.program)
    layout.value = json(value.layout)
    pick('author').open = false
    fixed.clear()
    clearResults()
    updateAreaFields()
  }
  async function run(task) {
    if (busy) return
    busy = true
    dialog.setAttribute('aria-busy', 'true')
    dialog.querySelector('.planning-body').inert = true
    status.textContent = '正在检查…'
    try { await task() }
    catch (error) {
      clearResults()
      status.textContent = error.message
    } finally {
      busy = false
      dialog.setAttribute('aria-busy', 'false')
      dialog.querySelector('.planning-body').inert = false
    }
  }

  launch.onclick = () => {
    openMenu()
    pick('actual').disabled = !source()
    dialog.showModal()
    draw()
  }
  pick('close').onclick = () => { if (!busy) dialog.close() }
  dialog.addEventListener('cancel', event => { if (busy) event.preventDefault() })
  pick('sample').onclick = () => load(demo)
  pick('import').onchange = event => run(async () => {
    const file = event.target.files?.[0]
    if (!file) return
    if (file.size > 1024 * 1024) throw Error('规划文件超过 1 MiB。')
    load(JSON.parse(await file.text()))
    event.target.value = ''
    status.textContent = '已导入布局请求。'
  })
  program.oninput = () => { clearResults(); updateAreaFields() }
  layout.oninput = clearResults
  pick('space').onchange = updateAreaFields
  for (const field of ['min', 'target', 'max']) {
    pick(field).onchange = () => {
      const data = readProgram(), room = byId(data.spaces, pick('space').value)
      if (!room) return
      const key = field + '_area', value = pick(field).value
      if (value) room[key] = Number(value)
      else delete room[key]
      program.value = json(data)
      clearResults()
    }
  }
  pick('lock').onchange = () => {
    const key = pick('space').value
    if (pick('lock').checked) fixed.add(key)
    else fixed.delete(key)
    clearResults()
  }
  level.onchange = view.onchange = cut.oninput = draw
  pick('check').onclick = () => run(async () => {
    clearResults()
    const data = request()
    const report = await api('architect/layout-check', data)
    present(report, data.program, data.layout)
    status.textContent = report.passed ? '布局约束通过。' : '布局有未通过的约束。'
  })
  pick('search').onclick = () => run(async () => {
    const data = request()
    clearResults()
    const found = await api('architect/program-layout-search', { program: data.program, baseline: data.layout, locked: [...fixed] })
    options = found.candidates
    if (options.length) {
      present(options[0].report, data.program, options[0].layout)
      showOptions()
    } else present({ checks: found.checks })
    status.textContent = searchText[found.status] + ' · 检查 ' + found.attempts + ' 次'
  })
  pick('actual').onclick = () => run(async () => {
    const active = source()
    if (!active) throw Error('请打开有规划绑定的 SNBT 制作版。')
    const report = await api('architect/layout-check', active)
    if (source()?.source_sha256 !== active.source_sha256 || source()?.source !== active.source)
      throw Error('制作版已变化，请重新核对。')
    clearResults()
    present(report)
    status.textContent = report.passed ? '制作版规划约束通过。' : '制作版有未通过或待测的约束。'
  })
  pick('use').onclick = () => {
    layout.value = json(currentLayout)
    status.textContent = '已采用选中的布局。'
  }
  pick('download').onclick = () => saveJSON('building-layout.json', { program: currentProgram, layout: currentLayout })
  pick('bind').onchange = event => run(async () => {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return
    if (file.size > 1024 * 1024) throw Error('建筑方案模板超过 1 MiB。')
    const input = JSON.parse(await file.text())
    const prepared = await api('architect/layout-prepare',
      { program: currentProgram, layout: currentLayout, plan: input.plan ?? input })
    saveJSON('plan-build.json', { plan: prepared.plan })
    status.textContent = '已绑定布局并下载建筑方案请求。'
  })
  return launch
}
