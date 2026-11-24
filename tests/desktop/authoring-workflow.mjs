import assert from 'node:assert/strict'
import {spawnSync} from 'node:child_process'
import fs from 'node:fs/promises'
import {createRequire} from 'node:module'
import path from 'node:path'
import {root, skill, python} from '../../scripts/paths.mjs'
import {minimizedScreenshots} from '../support/minimized-screenshots.mjs'

const require = createRequire(path.join(skill, 'assets/viewer/package.json'))
const {_electron} = require('playwright')
const output = path.join(root, 'build', `authoring-desktop-${Date.now()}`)
const workspace = path.join(output, 'workspace')
const env = {...process.env, NBTCREATOR_AUTOMATION: '1', PYTHONIOENCODING: 'utf-8'}
delete env.ELECTRON_RUN_AS_NODE
const fixture = spawnSync(python, ['-B', path.join(root, 'tests/engine/authoring-review.py'), '--desktop-fixture', workspace],
  {cwd: root, encoding: 'utf8', env, windowsHide: true, timeout: 120000})
assert.equal(fixture.status, 0, fixture.stdout + fixture.stderr)
const ids = JSON.parse(fixture.stdout)
await fs.mkdir(path.join(workspace, '.nbtcreator'), {recursive: true})
await fs.writeFile(path.join(workspace, '.nbtcreator/preferences.json'), JSON.stringify({startPage:'project', autoPreview:false}))

let app
const errors = []
async function launch() {
  app = await _electron.launch({executablePath: path.join(root, 'node_modules/electron/dist/electron.exe'),
    args: [root, '--workspace', workspace, '--user-data-dir', path.join(output, 'profile')], env, timeout: 60000})
  const page = await app.firstWindow()
  await minimizedScreenshots(app, page)
  page.setDefaultTimeout(45000)
  page.on('pageerror', error => errors.push(error.message))
  await page.waitForFunction(() => document.querySelector('.project-card') && !window.detailControl?.state.busy)
  await page.locator('#batch-workspaces-open').evaluate(node => node.click())
  await page.waitForFunction(() => [...document.querySelectorAll('.authoring-workflow button')].some(button => !button.disabled))
  await page.getByRole('button', {name: '读取制作运行'}).evaluate(node => node.click())
  try { await page.locator('[data-package-id="chest_batch"]').waitFor({timeout: 12000}) }
  catch (error) {
    console.error(await page.locator('.authoring-workflow').textContent().catch(() => ''))
    throw error
  }
  return page
}

try {
  let page = await launch()
  const tree = '[data-package-id="root"] [data-package-id="upper"] [data-package-id="chest_batch"]'
  assert.match(await page.locator(tree).textContent(), /写区 9, 5, 2 → 12, 6, 4/)
  await page.getByRole('img', {name: 'attic arrangement'}).scrollIntoViewIfNeeded()
  await page.waitForFunction(() => document.querySelector('img[alt="attic arrangement"]')?.naturalWidth === 32)
  await app.close()
  app = null
  page = await launch()
  await page.getByRole('button', {name: '保存为可编辑制作版'}).waitFor()
  const original = await fs.readFile(path.join(workspace, 'concept.png'))
  await fs.writeFile(path.join(workspace, 'concept.png'), 'replaced')
  await page.getByRole('button', {name: '读取制作运行'}).evaluate(node => node.click())
  await page.getByText('参考图已变化，请恢复冻结图像或开启新运行。').waitFor()
  assert.equal(await page.getByRole('button', {name: '保存为可编辑制作版'}).isDisabled(), true)
  await fs.writeFile(path.join(workspace, 'concept.png'), original)
  await page.getByRole('button', {name: '读取制作运行'}).evaluate(node => node.click())
  await page.waitForFunction(() => [...document.querySelectorAll('.authoring-workflow button')]
    .some(button => button.textContent === '保存为可编辑制作版' && !button.disabled))
  await page.getByRole('button', {name: '保存为可编辑制作版'}).evaluate(node => node.click())
  await page.getByText('落盘版待出图复验').waitFor()
  await page.getByRole('button', {name: '打开制作版'}).evaluate(node => node.click())
  await page.waitForFunction(() => document.body.dataset.workspace === 'model' &&
    window.detailControl?.state.info?.source.includes('v_model_'))
  const envelope = await page.evaluate(async params => {
    const response = await fetch('/__detail__/authoring/inspect', {method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({params})})
    return response.json()
  }, ids)
  assert.equal(envelope.data.phase, 'draft_saved')
  assert.equal(envelope.data.draft.approval_created, false)
  assert.equal(envelope.data.draft.nbt_exported, false)
  assert.deepEqual(errors, [])
  console.log(JSON.stringify({passed: true, workflow: 'authoring', output}))
} finally {
  await app?.close()
}
