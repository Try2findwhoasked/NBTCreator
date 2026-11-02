// Explicit optional browser integration tests. No user models or existing browsers are modified.
import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import path from 'node:path'
import { parseArgs } from 'node:util'
import { createHash } from 'node:crypto'
import { renderBatch } from './render-batch.mjs'
import { createViewerServer } from './viewer-server.mjs'
import { launchRenderBrowser } from './browser-launch.mjs'
import { normalizeViews, includesBlock } from './src/view-contract.mjs'

const { values } = parseArgs({ options: { output: { type: 'string' } } })
if (!values.output) throw new Error('Usage: node test-render.mjs --output new-test-directory')
const root = path.resolve(values.output)
await fs.mkdir(root)
const hash = bytes => createHash('sha256').update(bytes).digest('hex')
const checks = {}
const source = path.join(root, 'synthetic-source.json')
await fs.writeFile(source, JSON.stringify({ fixture: true, no_human_approval: true }))
const whole = { eye: [14, 12, 15], target: [4, 3, 4] }
const inside = { eye: [4, 2.62, 1.5], target: [4, 3, 7] }
const blocks = [], walls = []
for (let x = 0; x < 8; x++) for (let y = 0; y < 8; y++) for (let z = 0; z < 8; z++) {
  if ([x, y, z].some(v => v === 0 || v === 7)) {
    blocks.push([[x, y, z], y === 0 ? 'minecraft:oak_planks' : 'minecraft:stone_bricks'])
    if (x === 0 || x === 7 || z === 0 || z === 7) walls.push([x, y, z])
  }
}
blocks.push([[3, 1, 4], 'minecraft:oak_stairs[facing=east,half=bottom,shape=straight,waterlogged=false]'])
const views = [
  { id: 'whole', role: '整体', ...whole }, { id: 'inside', role: '室内', ...inside },
  { id: 'inside_repeat', role: '重复室内', ...inside },
  { id: 'cut', role: '剖切', ...whole, cut_y: 3 },
  { id: 'walls', role: '墙层', ...whole, layer: 'walls' },
  { id: 'whole_restore', role: '还原整体', ...whole },
]
const snapshot = { name: 'Synthetic render regression', size: [8, 8, 8], blocks,
  wall_positions: walls, cameras: views.slice(0, 2), source, source_sha256: hash(await fs.readFile(source)),
  geometry_sha256: hash(JSON.stringify(blocks)), verification: { design: 'pending_visual_review', runtime: 'not_checked' } }
const model = path.join(root, 'model.json')
await fs.writeFile(model, JSON.stringify(snapshot))
for (const [name, invalid] of Object.entries({
  duplicate_ids: [{ ...whole, id: 'a' }, { ...inside, id: 'a' }],
  traversal: [{ ...whole, id: '../escape' }], invalid_camera: [{ eye: [1, 1, 1], target: [1, 1, 1] }],
  fractional_cut: [{ ...whole, cuts: [{ axis: 'y', position: 3.5 }] }], unknown_field: [{ ...whole, typoo: 1 }],
})) {
  assert.throws(() => normalizeViews(invalid, snapshot.size))
  checks[`rejects_${name}`] = true
}
assert.equal(includesBlock([1, 3, 1], [{ axis: 'y', position: 3, removed_side: 'above' }]), false)
assert.equal(includesBlock([1, 3, 1], [{ axis: 'y', position: 3, removed_side: 'below' }]), true)
checks.integer_boundary_semantics = true
const badCameras = path.join(root, 'bad-views.json')
await fs.writeFile(badCameras, JSON.stringify([{ ...whole, typo: true }]))
const badOutput = path.join(root, 'must-not-exist')
await assert.rejects(() => renderBatch({ model, cameras: badCameras, output: badOutput }))
await assert.rejects(() => fs.access(badOutput))
checks.invalid_request_creates_no_output = true
const cameras = path.join(root, 'views.json')
await fs.writeFile(cameras, JSON.stringify(views))
const output = path.join(root, 'batch')
const report = await renderBatch({ model, cameras, output, width: 640, height: 480 })
assert.equal(report.status, 'complete')
assert.deepEqual(report.images.map(image => image.mesh_builds), [1, 1, 1, 2, 3, 4])
assert.equal(report.images[0].sha256, report.images[5].sha256)
assert.equal(report.images[1].sha256, report.images[2].sha256)
assert.equal(new Set(report.images.map(image => image.sha256)).size, 4)
assert.equal(report.page_errors.length + report.resource_errors.length, 0)
assert.deepEqual(report.cleanup, { browser_closed: true, server_closed: true })
checks.batch_cameras_do_not_rebuild = true
checks.batch_cuts_layers_and_reset_are_exact = true
checks.same_camera_has_identical_png = true
checks.batch_resources_closed = true
const saved = await fs.readFile(path.join(output, 'whole.png'))
await assert.rejects(() => renderBatch({ model, cameras, output }))
assert.deepEqual(await fs.readFile(path.join(output, 'whole.png')), saved)
checks.no_overwrite = true
const failedOutput = path.join(root, 'failed-browser')
await assert.rejects(() => renderBatch({ model, cameras, output: failedOutput,
  browserExecutable: path.join(root, 'missing-browser.exe') }))
const failed = JSON.parse(await fs.readFile(path.join(failedOutput, 'render_manifest.json')))
assert.equal(failed.status, 'failed')
assert.equal(failed.cleanup.server_closed, true)
checks.failure_recorded_and_server_closed = true

let browser, viewer
try {
  viewer = await createViewerServer({ model })
  browser = await launchRenderBrowser()
  const page = await browser.newPage({ viewport: { width: 640, height: 480 } })
  await page.goto(viewer.url)
  await page.waitForFunction(() => Boolean(window.nbtModeler?.ready))
  await page.evaluate(() => window.nbtModeler.ready)
  const initial = await page.evaluate(() => window.nbtModeler.metadata())
  await page.getByRole('button', { name: '室内', exact: true }).click()
  await page.waitForFunction(serial => Number(document.querySelector('#preview').dataset.frameSerial) > serial, initial.rendered_frames)
  const afterInside = await page.evaluate(() => window.nbtModeler.metadata())
  const insidePng = await page.locator('#preview').screenshot()
  assert.equal(afterInside.mesh_builds, initial.mesh_builds)
  assert.ok(afterInside.camera.eye.every((value, i) => Math.abs(value - inside.eye[i]) < 1e-5))
  checks.ui_camera_repaints_without_download = true
  await page.getByRole('button', { name: '整体', exact: true }).click()
  await page.waitForFunction(serial => Number(document.querySelector('#preview').dataset.frameSerial) > serial, afterInside.rendered_frames)
  const afterWhole = await page.evaluate(() => window.nbtModeler.metadata())
  const wholePng = await page.locator('#preview').screenshot()
  assert.notEqual(hash(insidePng), hash(wholePng))
  assert.equal(afterWhole.mesh_builds, initial.mesh_builds)
  checks.ui_screenshot_changes_without_forced_repaint = true
  await page.locator('#cut-level').evaluate(element => { element.value = '3'; element.dispatchEvent(new Event('change')) })
  await page.waitForFunction(() => window.nbtModeler.metadata().cuts.length === 1)
  const cutState = await page.evaluate(() => window.nbtModeler.metadata())
  await page.getByRole('button', { name: '室内', exact: true }).click()
  await page.waitForFunction(serial => Number(document.querySelector('#preview').dataset.frameSerial) > serial, cutState.rendered_frames)
  const preserved = await page.evaluate(() => window.nbtModeler.metadata())
  assert.deepEqual(preserved.cuts, cutState.cuts)
  assert.equal(preserved.mesh_builds, cutState.mesh_builds)
  checks.ui_camera_preserves_cut_and_mesh = true
  const frames = preserved.rendered_frames
  await new Promise(resolve => setTimeout(resolve, 120))
  assert.equal((await page.evaluate(() => window.nbtModeler.metadata())).rendered_frames, frames)
  checks.idle_does_not_render_continuously = true
  const cameraDownload = page.waitForEvent('download')
  await page.getByRole('button', { name: '导出相机记录', exact: true }).click()
  const cameraFile = path.join(root, 'ui-camera.json')
  await (await cameraDownload).saveAs(cameraFile)
  const cameraRecord = JSON.parse(await fs.readFile(cameraFile))
  assert.deepEqual(cameraRecord.cuts, preserved.cuts)
  checks.interactive_camera_download_preserved = true
  const imageDownload = page.waitForEvent('download')
  await page.getByRole('button', { name: '下载截图', exact: true }).click()
  const imageFile = path.join(root, 'ui-image.png')
  await (await imageDownload).saveAs(imageFile)
  const png = await fs.readFile(imageFile)
  assert.equal(png.readUInt32BE(16), 640)
  assert.equal(png.readUInt32BE(20), 480)
  checks.interactive_png_download_preserved = true
  await page.screenshot({ path: path.join(root, 'interactive-proof.png') })
} finally {
  if (browser) await browser.close()
  if (viewer) await viewer.close()
}
const result = { passed: true, checks, batch_duration_ms: report.duration_ms }
await fs.writeFile(path.join(root, 'results.json'), JSON.stringify(result, null, 2) + '\n')
console.log(JSON.stringify({ passed: true, checks: Object.keys(checks).length, report: path.join(root, 'results.json') }))
