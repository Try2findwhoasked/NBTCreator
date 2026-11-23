import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import path from 'node:path'
import {execFileSync} from 'node:child_process'
import {createHash} from 'node:crypto'
import {root, python} from '../../scripts/paths.mjs'

const output = await fs.mkdtemp(path.join(root, 'build/architecture-preview-'))
const workspace = path.join(output, 'workspace')
const hash = bytes => createHash('sha256').update(bytes).digest('hex')
const run = (exe, args) => JSON.parse(execFileSync(exe, args, {cwd: workspace, windowsHide: true, encoding: 'utf8', timeout: 180000}))
await fs.mkdir(workspace)
const fixture = run(python, ['-B', path.join(root, 'tests/support/architecture-fixture.py'), workspace])
const results = []
for (const candidate of fixture.cases) {
  const frozen = [python, ['-B', path.join(workspace, '.agents/skills/nbtcreator-workspace/nbt.py')]]
  const cli = [process.execPath, [path.join(root, 'scripts/cli.mjs'), '--workspace', workspace]]
  const invoke = async (entry, action, request) => {
    const file = path.join(candidate.input, `${action}-${Date.now()}.json`)
    await fs.writeFile(file, JSON.stringify(request))
    return run(entry[0], [...entry[1], 'architect', action, '--request', file])
  }
  let plan = candidate.plan
  if (candidate.layout) {
    const layout = await invoke(frozen, 'layout-search', candidate.layout)
    assert.equal(layout.read_only, true)
    assert.equal(layout.attempts.length, 12)
    assert.ok(layout.passed_count >= 2)
    const issues = layout.attempts.flatMap(row => row.issues ?? [])
    assert.ok(issues.some(row => row.target === 'stair_landing'))
    assert.ok(issues.some(row => row.target === 'return_desk.intake' && row.evidence.reason === 'wrong_side'))
    assert.ok(layout.attempts.some(row => row.status === 'passed' && row.offsets.stair[0] === -1))
    const selected = layout.candidates[0]
    assert.deepEqual(selected.offsets, {cabinet: [0, 5], operator: [0, -3], stair: [0, 0]})
    assert.equal(selected.plan.parts.some(part => part.id === 'front_frame'), false)
    const positions = new Map(selected.plan.parts.map(part => [part.id, part.position]))
    plan = {
      ...plan,
      context: selected.plan.context,
      stairs: selected.plan.stairs,
      activities: selected.plan.activities,
      parts: plan.parts.map(part => positions.has(part.id) ? {...part, position: positions.get(part.id)} : part),
    }
  }
  const savedPlan = await invoke(cli, 'plan-save', {plan, revision: 0})
  const building = await invoke(candidate.id === 'wood' ? frozen : cli, 'plan-build', {plan_id: savedPlan.id, revision: savedPlan.revision, save_draft: {}})
  const source = building.saved.source
  const source_sha256 = hash(await fs.readFile(source))
  assert.equal(building.checks.architecture.passed, true)
  assert.equal(building.checks.whole_model.routes.passed, true)
  assert.equal((await invoke(frozen, 'plan-check', {source, source_sha256})).plan_sha256, savedPlan.sha256)
  const review = await invoke(cli, 'review-prepare', {source, source_sha256, output: `nbt_models/_workspaces/reviews/${candidate.id}`})
  assert.equal(review.coverage.coverage_passed, true)
  const render = run(cli[0], [...cli[1], ...review.render_command])
  const renderDir = path.join(workspace, `nbt_models/_workspaces/reviews/${candidate.id}/render`)
  const manifest = JSON.parse(await fs.readFile(path.join(renderDir, 'render_manifest.json'), 'utf8'))
  assert.equal(manifest.status, 'complete')
  assert.equal(manifest.source_sha256, source_sha256)
  assert.equal(manifest.images.length, plan.views.length)
  const images = []
  for (const item of manifest.images) {
    const image = path.join(renderDir, item.image)
    const bytes = await fs.readFile(image)
    assert.equal(hash(bytes), item.sha256)
    assert.equal(bytes.subarray(1, 4).toString(), 'PNG')
    images.push(image)
  }
  const game = await invoke(frozen, 'game-checklist', {source, source_sha256})
  assert.ok(game.checks.every(row => row.state === 'not_checked'))
  results.push({id: candidate.id, source, source_sha256, plan_sha256: savedPlan.sha256, review, images, renderManifest: path.join(renderDir, 'render_manifest.json')})
}
assert.equal(new Set(results.map(row => row.source_sha256)).size, fixture.cases.length)
assert.equal(await fs.access(path.join(workspace, 'nbt_models/_exports')).then(() => true, () => false), false)
const report = {passed: true, workspace, output, cases: results, actualImagesGenerated: true, visualObservations: 'awaiting_actual_inspection', nbtExported: false, gameExecutionWitnessed: false}
await fs.writeFile(path.join(output, 'results.json'), JSON.stringify(report, null, 2))
console.log(JSON.stringify({passed: true, output, images: results.flatMap(row => row.images), noAutomaticApproval: true}))
