import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { execFileSync } from 'node:child_process'
import fs from 'node:fs/promises'
import path from 'node:path'
import { pathToFileURL } from 'node:url'
import { root } from '../../scripts/paths.mjs'
import { minimizedScreenshots } from '../support/minimized-screenshots.mjs'

const skill = path.join(root, '.agents/skills/minecraft-nbt-modeler')
const viewer = path.join(skill, 'assets/viewer')
const { _electron } = await import(pathToFileURL(path.join(viewer, 'node_modules/playwright/index.mjs')))
const read = async file => JSON.parse(await fs.readFile(file, 'utf8'))
const build = path.join(root, 'build')
await fs.mkdir(build, { recursive: true })
const output = await fs.mkdtemp(path.join(build, 'whole-building-planning-'))
const workspace = path.join(output, 'workspace')
await fs.mkdir(workspace)

const { plan } = await read(path.join(skill, 'assets/examples/entry-pavilion.json'))
const box = (lo, hi) => ({ lo, hi })
const program = {
  schema_version: 1, size: plan.size, entry: plan.context.start,
  levels: [{ id: 'ground', feet_y: 1, ceiling_y: 5, footprint: [box([5, 1], [7, 8])] }],
  spaces: [{ id: 'entry', level: 'ground', purpose: '入口', min_area: 6 },
    { id: 'inside', level: 'ground', purpose: '内厅', min_area: 15 }],
  relations: [{ id: 'main_door', kind: 'door', from: 'entry', to: 'inside', min_width: 3 }],
}
const layout = {
  spaces: [{ id: 'entry', regions: [box([5, 1], [7, 2])] }, { id: 'inside', regions: [box([5, 4], [7, 8])] }],
  links: [{ id: 'main_door', opening: box([5, 3], [7, 3]) }],
}
const requestFile = path.join(output, 'plan-build.json')
await fs.writeFile(requestFile, JSON.stringify({ plan: { ...plan, planning: { program, layout } }, save_draft: {} }))
const saved = JSON.parse(execFileSync(process.execPath,
  [path.join(root, 'scripts/cli.mjs'), '--workspace', workspace, 'architect', 'plan-build', '--request', requestFile],
  { cwd: workspace, windowsHide: true, encoding: 'utf8', timeout: 60000 })).saved
const boundHash = createHash('sha256').update(await fs.readFile(saved.source)).digest('hex')

const env = { ...process.env, NBTCREATOR_AUTOMATION: '1' }
delete env.ELECTRON_RUN_AS_NODE
let app
try {
  app = await _electron.launch({ executablePath: path.join(root, 'node_modules/electron/dist/electron.exe'),
    args: [root, '--workspace', workspace, '--user-data-dir', path.join(output, 'profile')], env, timeout: 60000 })
  const page = await app.firstWindow()
  page.setDefaultTimeout(30000)
  await minimizedScreenshots(app, page)
  const errors = []
  page.on('pageerror', error => errors.push(error.message))
  await page.waitForFunction(() => window.detailControl?.state.catalogReady && !window.detailControl.state.busy)
  await page.evaluate(() => window.creatorWorkspace.select('project'))
  await page.setViewportSize({ width: 1260, height: 820 })
  async function open() {
    await page.locator('#project-library-menu>summary').click()
    await page.locator('#architect-tools-menu>summary').click()
    await page.locator('#open-building-planning').click()
  }
  await open()
  const dialog = page.locator('#building-planning-dialog')
  const control = key => dialog.locator('[data-' + key + ']')
  const waitStatus = pattern => dialog.getByRole('status').filter({ hasText: pattern }).waitFor()
  await control('sample').click()
  await control('check').click()
  await waitStatus('布局约束通过')
  assert.deepEqual(await control('level').locator('option').evaluateAll(nodes => nodes.map(n => n.value)), ['ground', 'upper'])
  await control('level').selectOption('upper')
  await control('view').selectOption('section')
  await control('cut').fill('8')
  assert.ok(await dialog.locator('canvas').evaluate(canvas => {
    const pixels = canvas.getContext('2d').getImageData(0, 0, canvas.width, canvas.height).data
    return pixels.some((channel, index) => index % 4 === 3 && channel !== 0)
  }))
  await page.screenshot({ path: path.join(output, 'planning-section.png') })

  await control('space').selectOption('archive')
  await control('target').fill('38')
  await control('target').press('Tab')
  await control('min').fill('38')
  await control('min').press('Tab')
  await control('check').click()
  await waitStatus('布局有未通过')
  await control('view').selectOption('floor')
  await dialog.getByRole('button', { name: /未通过.*space:archive:area/ }).click()
  assert.equal(await control('level').inputValue(), 'upper')
  await page.setViewportSize({ width: 760, height: 620 })
  assert.ok(await dialog.evaluate(element => element.scrollWidth <= element.clientWidth + 1))
  await control('sample').click()
  await control('space').selectOption('foyer')
  await control('lock').check()
  await control('search').click()
  await waitStatus('找到可行候选')
  await dialog.getByRole('button', { name: /^候选 2/ }).click()
  await control('use').click()
  const adopted = JSON.parse(await control('layout').inputValue())
  const demo = await read(path.join(skill, 'assets/examples/whole-building-planning.json'))
  assert.deepEqual(adopted.spaces.find(room => room.id === 'foyer'), demo.layout.spaces[0])

  await control('close').click()
  await page.evaluate(source => window.detailControl.openModel({ source }), saved.source)
  await page.waitForFunction(sha => window.detailControl.state.info?.source_sha256 === sha
    && !window.detailControl.state.busy, boundHash)
  await page.evaluate(() => window.creatorWorkspace.select('project'))
  await open()
  await control('actual').click()
  await waitStatus('制作版规划约束通过')
  assert.match(await control('report').textContent(), /内厅 · 净地面 15 格² · 可达 15 格²/)
  assert.ok(await fs.access(path.join(workspace, 'nbt_models/_exports')).then(() => false, () => true))
  assert.deepEqual(errors, [])
  console.log(JSON.stringify({ passed: true, output }))
} finally {
  await app?.close()
}
