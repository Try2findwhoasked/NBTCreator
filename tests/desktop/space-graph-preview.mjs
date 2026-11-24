import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import path from 'node:path'
import { execFileSync } from 'node:child_process'
import { createHash } from 'node:crypto'
import { root, skill, python } from '../../scripts/paths.mjs'

const build = path.join(root, 'build')
await fs.mkdir(build, { recursive: true })
const output = await fs.mkdtemp(path.join(build, 'space-graph-preview-'))
const workspace = path.join(output, 'workspace')
await fs.mkdir(workspace)
const run = args => execFileSync(python, ['-B', ...args], {
  cwd: workspace, windowsHide: true, encoding: 'utf8', timeout: 180000,
  maxBuffer: 8 * 1024 * 1024, env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
})
const hash = bytes => createHash('sha256').update(bytes).digest('hex')
const read = async file => JSON.parse(await fs.readFile(file, 'utf8'))
const config = path.join(output, 'exposure.json')
await fs.writeFile(config, JSON.stringify({
  schema_version: 1, enabled_groups: ['core', 'architecture', 'modelling', 'rendering'],
}))
run([path.join(skill, 'scripts/nbt_exposure.py'), 'apply', '--config', config])
run([path.join(skill, 'assets/examples/reading-loft/run.py'), 'layouts', '--candidate', 'front'])

const examples = path.join(workspace, 'nbt_models/_workspaces/examples')
const [name] = await fs.readdir(examples)
const evidence = path.join(examples, name)
const layoutPath = path.join(evidence, 'layout-search-result.json')
const layout = await read(layoutPath)
assert.deepEqual(layout.attempts.map(({ id, status }) => [id, status]), [
  ['front', 'passed'], ['side', 'passed'], ['blocked', 'rejected'], ['wrong-side', 'rejected'],
])
const building = await read(path.join(evidence, 'plan-build-result.json'))
const candidate = layout.candidates[0]
assert.equal(building.plan_sha256, candidate.plan_sha256)
assert.equal(building.checks.model_sha256, candidate.model_sha256)
const source = building.saved.source
const sourceSha256 = hash(await fs.readFile(source))
const checked = await read(path.join(evidence, 'plan-check-result.json'))
assert.equal(checked.plan_sha256, candidate.plan_sha256)
assert.equal(checked.validation.whole_model.routes.passed, true)
assert.equal(checked.validation.architecture.passed, true)
const review = await read(path.join(evidence, 'review-prepare-result.json'))
assert.equal(review.coverage.coverage_passed, true)
assert.ok([layout, building, review.coverage].every(receipt => receipt.approval_created === false))
await assert.rejects(fs.access(path.join(workspace, 'nbt_models/_exports')), { code: 'ENOENT' })

const imagePaths = {}
for (const [label, directory, count] of [
  ['review', path.join(evidence, 'review/render'), 3],
  ['sections', path.join(evidence, 'sections'), 3],
]) {
  const manifest = await read(path.join(directory, 'render_manifest.json'))
  assert.equal(manifest.status, 'complete')
  assert.equal(manifest.source_sha256, sourceSha256)
  assert.equal(manifest.images.length, count)
  imagePaths[label] = []
  for (const item of manifest.images) {
    const image = path.join(directory, item.image)
    const bytes = await fs.readFile(image)
    assert.equal(hash(bytes), item.sha256)
    assert.equal(bytes.subarray(1, 4).toString(), 'PNG')
    imagePaths[label].push(image)
  }
}
const report = { passed: true, evidence, layout: layoutPath, source, sourceSha256, images: imagePaths,
  userApproval: 'pending', nbtExported: false }
await fs.writeFile(path.join(output, 'results.json'), JSON.stringify(report, null, 2))
console.log(JSON.stringify(report))
