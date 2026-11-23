import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { createHash } from 'node:crypto'
import fs from 'node:fs/promises'
import path from 'node:path'
import { pathToFileURL } from 'node:url'
import { root, python } from '../../scripts/paths.mjs'
import { minimizedScreenshots } from '../support/minimized-screenshots.mjs'

const viewer = path.join(root, '.agents/skills/minecraft-nbt-modeler/assets/viewer')
const { _electron } = await import(pathToFileURL(path.join(viewer, 'node_modules/playwright/index.mjs')))
const build = path.join(root, 'build')
await fs.mkdir(build, { recursive: true })
const resume = process.argv.find(arg => arg.startsWith('--resume='))
const output = resume ? path.resolve(resume.slice('--resume='.length)) : await fs.mkdtemp(path.join(build, 'building-quality-'))
const workspace = path.join(output, 'workspace')
const run = (engine, args) => JSON.parse(execFileSync(engine, args, {
  cwd: workspace, windowsHide: true, encoding: 'utf8', timeout: 180000, maxBuffer: 8 * 1024 * 1024,
}))
const cli = args => run(process.execPath, [path.join(root, 'scripts/cli.mjs'), '--workspace', workspace, ...args])
let sequence = 0
async function invoke(group, action, data) {
  const file = path.join(output, `${action}-${Date.now()}-${sequence++}.json`)
  await fs.writeFile(file, JSON.stringify(data))
  return cli([group, action, '--request', file])
}
const hash = async file => createHash('sha256').update(await fs.readFile(file)).digest('hex')
const artifact = path.join(output, 'fixture.json')
await fs.mkdir(workspace, { recursive: true })
const heldOut = process.argv.includes('--held-out')
const quantitative = process.argv.includes('--style')
const fixtureMode = quantitative ? ['--style'] : heldOut ? ['--held-out'] : []
const cases = resume ? JSON.parse(await fs.readFile(artifact, 'utf8')) :
  run(python, ['-B', path.join(root, 'tests/support/building-quality-fixture.py'), workspace, ...fixtureMode])
if (!resume && !quantitative) {
  console.log(JSON.stringify({ output, phase: 'rendering' }))
  for (const [label, item] of Object.entries(cases)) {
    cli([...item.render_command, '--width', '800', '--height', '520'])
    item.manifest = path.join(workspace, item.render_manifest)
    item.manifest_sha256 = await hash(item.manifest)
    console.log(JSON.stringify({ label, manifest: item.manifest }))
  }
}
if (!resume) await fs.writeFile(artifact, JSON.stringify(cases, null, 2))
if (quantitative) {
  const reports = {}
  for (const [name, row] of Object.entries(cases)) {
    reports[name] = await invoke('architect', 'quality-check', { source: row.source, source_sha256: row.source_sha256 })
  }
  assert.deepEqual(Object.values(reports).map(report => report.dimensions.style.items[0].grade), [4, 3, 4, 2])
  assert.match(reports.shifted.issues.find(issue => issue.id === 'style.beam_rhythm.ceiling').reason, /\+1 格/)
  await desktopParity({ source: cases.shifted.source, source_sha256: cases.shifted.source_sha256 }, reports.shifted)
  await fs.writeFile(path.join(output, 'style-results.json'), JSON.stringify(reports, null, 2))
  console.log(JSON.stringify({ passed: true, output, axis: 'Z', cliMatchesDesktop: true }))
  process.exit(0)
}
if (heldOut || process.argv.includes('--render-only')) process.exit(0)

const a = cases.open
const renderBinding = item => ({ manifest: item.manifest, sha256: item.manifest_sha256 })
const blindGroup = `nbt_models/_workspaces/reference-reviews/calibration-${Date.now()}`
const blindRequest = { renders: [renderBinding(a), renderBinding(cases.palette)],
  scope: '同机位比较外墙配色对灰瓦、木架与入口主次的影响', crop: null }
const first = await invoke('reference', 'review-prepare', { ...blindRequest, output: `${blindGroup}/1` })
const second = await invoke('reference', 'review-prepare', { ...blindRequest, output: `${blindGroup}/2`,
  reverse_of: { binding: first.binding, binding_sha256: first.binding_sha256 } })
const blind = [first, second]
const [before, after] = await Promise.all(blind.map(row => fs.readFile(row.public, 'utf8').then(JSON.parse)))
for (const [index, view] of before.views.entries()) {
  assert.equal(view.images.A.sha256, after.views[index].images.B.sha256)
  assert.equal(view.images.B.sha256, after.views[index].images.A.sha256)
}
// The generated pairs remain available for independent human and Agent ratings.
await fs.writeFile(path.join(output, 'blind-pairs.json'), JSON.stringify(blind.map(row => ({
  public: row.public, public_sha256: row.public_sha256,
})), null, 2))

const sources = {}
for (const [name, entry] of Object.entries(cases)) {
  const source = { source: entry.source, source_sha256: entry.source_sha256 }
  const observations = ['outside', 'entry_player', 'frame', 'rear_eaves', 'cabinet', 'landing', 'counter']
    .map(image => ({ image, note: '自动化回归的评分字段样例。实际观察另行登记。' }))
  const score = (item, grade, images) => ({
    item, grade, images, reviewer: 'external_ai', observer: 'regression-fixture',
    note: '自动化断言使用的回归观察。', ...(grade < 4 && { suggestion: '核对登记部位的对照目标。' }),
  })
  const ratings = [
    score('aesthetics.materials_light', name === 'palette' ? 3 : 4, ['outside', 'frame']),
    score('circulation.file_books.stair_to_landing.turning_stops', 4, ['landing']),
    score('style.continuous_eaves.front', 4, ['outside']),
    score('style.continuous_eaves.rear', name === 'rear' ? 1 : 4, ['rear_eaves']),
    score('details.archive.joints', name === 'joint' ? 2 : 4, ['cabinet']),
  ]
  const { pack, pack_sha256, render_manifest } = entry
  const revision = await fs.readFile(path.join(workspace, pack, '..', 'review-notes.json'), 'utf8')
    .then(raw => JSON.parse(raw).revision, error => { if (error.code === 'ENOENT') return 0; throw error })
  const evidence = await invoke('architect', 'review-record', {
    pack, pack_sha256, render_manifest, revision, observations, issues: [], quality_observations: ratings,
  })
  assert.equal(evidence.quality.review.revision, revision + 1)
  assert.equal(evidence.quality.approval_created, false)
  const request = { ...source, review: evidence.review_compare }
  const report = await invoke('architect', 'quality-check', request)
  assert.deepEqual(report, evidence.quality)
  assert.equal(report.dimensions.circulation.coverage, 33.33)
  sources[name] = { request, report, ratings, observations }
}
const baseline = sources.open.request
const compare = (current, previous) => invoke('architect', 'quality-compare', { ...current, previous })
const style = await compare(sources.rear.request, baseline)
assert.equal(style.dimensions.style.delta, -37.5)
assert.equal(sources.rear.report.dimensions.style.sites_at_standard, 1)
assert.equal(style.issues.find(row => row.id === 'style.continuous_eaves.rear').status, 'new')
const details = await compare(baseline, sources.joint.request)
assert.equal(details.dimensions.details.comparable_items['details.archive.joints'].delta, 50)
assert.equal(details.issues.find(row => row.id === 'details.archive.joints').status, 'resolved_retested')
const palette = await compare(sources.palette.request, baseline)
assert.equal(palette.dimensions.aesthetics.comparable_items['aesthetics.materials_light'].delta, -25)
assert.equal(palette.dimensions.aesthetics.delta, null)
assert.equal(sources.palette.report.binding.checklist_sha256, sources.open.report.binding.checklist_sha256)
const previous = { ...baseline }
const renewed = await invoke('architect', 'review-record', {
  pack: a.pack, pack_sha256: a.pack_sha256, render_manifest: a.render_manifest, revision: sources.open.report.review.revision,
  observations: sources.open.observations, issues: [], quality_observations: sources.open.ratings,
})
assert.equal((await invoke('architect', 'quality-check', previous)).review_gap.status, 'stale')
baseline.review = renewed.review_compare

const { source, source_sha256 } = sources.open.request
const movement = await invoke('architect', 'review-compare', {
  ...renewed.review_compare, source, source_sha256, current_review: renewed.review_compare,
})
assert.equal(movement.quality.dimensions.style.delta, 0)

const damaged = path.join(workspace, sources.rear.report.review.render.path, '..', 'rear_eaves.png')
const original = await fs.readFile(damaged)
try {
  await fs.writeFile(damaged, Buffer.from('obsolete image'))
  const report = await invoke('architect', 'quality-check', sources.rear.request)
  assert.equal(report.review_gap.status, 'partial')
  assert.deepEqual(report.review_gap.stale_views, ['rear_eaves'])
  assert.equal(report.dimensions.style.coverage, 50)
  assert.deepEqual(report.dimensions.style.interval, [50, 100])
  assert.equal(report.dimensions.aesthetics.coverage, 25)
} finally {
  await fs.writeFile(damaged, original)
}

async function desktopParity(request, expected) {
  let app
  try {
    await fs.mkdir(path.join(workspace, '.nbtcreator'), { recursive: true })
    await fs.writeFile(path.join(workspace, '.nbtcreator/preferences.json'), JSON.stringify({ startPage: 'model', autoPreview: false }))
    const env = { ...process.env, NBTCREATOR_AUTOMATION: '1' }
    delete env.ELECTRON_RUN_AS_NODE
    app = await _electron.launch({ executablePath: path.join(root, 'node_modules/electron/dist/electron.exe'),
      args: [root, '--workspace', workspace, '--user-data-dir', path.join(output, 'profile')], env, timeout: 60000 })
    const page = await app.firstWindow()
    page.setDefaultTimeout(60000)
    await minimizedScreenshots(app, page)
    await page.waitForFunction(() => window.detailControl?.openModel && !window.detailControl.state.busy)
    await page.evaluate(source => window.detailControl.openModel({ source }), request.source)
    await page.waitForFunction(() => window.detailControl.state.info && !window.detailControl.state.busy)
    assert.equal(await page.evaluate(() => window.detailControl.state.info.source_sha256), request.source_sha256)
    const dialog = page.locator('#building-quality-dialog')
    await page.locator('#studio-panel-checks').click()
    await page.locator('#building-quality-open').click()
    if (request.review) {
      await dialog.locator('summary').click()
      await dialog.locator('[data-review]').fill(JSON.stringify(request.review))
    }
    await dialog.locator('[data-run]').click()
    await dialog.locator('a[download]').waitFor({ state: 'visible' })
    assert.equal(await dialog.evaluate(node => node.scrollWidth <= node.clientWidth + 1), true)
    const browserReport = await dialog.locator('a[download]').evaluate(async link => (await fetch(link.href)).json())
    assert.deepEqual(browserReport, expected)
    await page.screenshot({ path: path.join(output, 'desktop-quality.png') })
    assert.equal(await fs.access(path.join(workspace, 'nbt_models/_exports')).then(() => true, () => false), false)
  } finally {
    await app?.close()
  }
}
await desktopParity(baseline, await invoke('architect', 'quality-check', baseline))
await fs.writeFile(path.join(output, 'results.json'), JSON.stringify({ style, details, palette, sources }, null, 2))
console.log(JSON.stringify({ passed: true, output, blindPairs: blind.map(row => row.public), cliMatchesDesktop: true }))
