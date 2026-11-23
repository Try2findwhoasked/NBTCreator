import assert from 'node:assert/strict'
import {spawnSync} from 'node:child_process'
import {createHash} from 'node:crypto'
import fs from 'node:fs/promises'
import path from 'node:path'
import {root, skill} from '../../scripts/paths.mjs'

const buildDir = path.join(root, 'build')
await fs.mkdir(buildDir, {recursive: true})
const output = await fs.mkdtemp(path.join(buildDir, 'contextual-facade-'))
const example = JSON.parse(await fs.readFile(path.join(skill, 'assets/examples/entry-pavilion.json'), 'utf8'))
const hash = bytes => createHash('sha256').update(bytes).digest('hex')
const writeJson = (file, value) => fs.writeFile(file, JSON.stringify(value, null, 2) + '\n')
const exists = file => fs.access(file).then(() => true, error => {
  if (error.code === 'ENOENT') return false
  throw error
})

const center = 17
const front = 3
const floor = 1
const depth = 3
const beamY = 6
const roofY = 7
const cameras = [
  {id: 'overview', role: '整体', eye: [40, 17, -26], target: [17.5, 3, 5], fov: 45},
  {id: 'elevation', role: '正立面', eye: [17.5, 4.5, -29], target: [17.5, 3.4, 4.5], fov: 48},
  {id: 'entry', role: '沿来路看完整门洞', eye: [17.5, 2.62, 0.5], target: [17.5, 3.05, 4.5], fov: 84},
  {id: 'interior', role: '从亭内看窗梁接合与顶构', eye: [17.5, 2.62, 10.25], target: [17.5, 3.6, 4.5], fov: 75},
]

function pavilion(width) {
  const request = structuredClone(example)
  const {plan} = request
  const [shell] = plan.parts
  const shellSpec = shell.recipe.arguments
  const left = center - Math.floor(width / 2)
  const right = left + width - 1
  // Retain the sample's stone floor, rear posts, two side rails and slab roof.
  // The generated facade owns the front posts and the entire entry wall.
  const original = shellSpec.operations
  shell.position = [left - 1, 0, 0]
  shellSpec.size = [width + 2, roofY + 1, 11]
  shellSpec.operations = [
    {...original[0], hi: [width + 1, 0, 10]},
    {...original[4], hi: [1, beamY, 9]},
    {...original[5], lo: [width, floor, 9], hi: [width, beamY, 9]},
    {...original[6], lo: [1, floor, front + depth]},
    {...original[7], lo: [width, floor, front + depth], hi: [width, floor, 8]},
    {...original[8], lo: [0, roofY, 2], hi: [width + 1, roofY, 10]},
  ]
  const facade = {
    pier_width: 1, opening: [3, 2], storeys: 1,
    material: plan.style.materials.stone, trim: 'stripped_spruce_wood', glass: 'light_blue_stained_glass',
    sill_material: 'stone_brick_slab[type=bottom,waterlogged=false]',
    contextual: {
      width, entry: {x: center - 1 - left, width: 3, height: 3},
      column_material: plan.style.materials.wood, beam_material: plan.style.materials.wood,
    },
  }
  plan.parts.push({id: 'facade', role: 'structure', position: [left, floor, front],
    recipe: {tool: 'facade_compile', arguments: facade}})
  plan.name = `入口亭 · ${width}格立面`
  plan.size = [35, 9, 12]
  // The facade supplies an already-open doorway. The sample is an open pavilion.
  plan.context.openings = []
  plan.context.start[0] = center + 0.5
  plan.context.targets.inside[0] = center + 0.5
  const [space] = plan.spaces
  space.lo[0] = center - 2
  space.hi[0] = center + 2
  space.samples[0][0] = center + 0.5
  for (const stop of plan.activities[0].stops) stop.feet[0] = center + 0.5
  plan.activities[0].stops[1].feet[2] = 4.5
  plan.views = [
    {id: 'overview', layer: 'massing', eye: cameras[0].eye, target: cameras[0].target, fov: cameras[0].fov},
    {id: 'entry', layer: 'structure', eye: cameras[2].eye, target: cameras[2].target, fov: cameras[2].fov},
    {id: 'interior', layer: 'detail', eye: cameras[3].eye, target: cameras[3].target, fov: cameras[3].fov,
      target_part: 'facade', sample_box: {lo: [center - 1, 4, 4], hi: [center + 1, 4, 5]}},
  ]
  return {request, facade, left, right}
}

function run(workspace, args, expected = 0) {
  const result = spawnSync(process.execPath, [path.join(root, 'scripts/cli.mjs'), '--workspace', workspace, ...args], {
    cwd: workspace, windowsHide: true, encoding: 'utf8', timeout: 180000, maxBuffer: 12 * 1024 * 1024,
  })
  if (result.error) throw result.error
  assert.equal(result.status, expected, result.stdout + result.stderr)
  return JSON.parse(result.stdout)
}

function samples(candidate, compiled) {
  const expected = []
  const add = (x, y, z, state, wall = false) => expected.push({pos: [x, y, z], value: [`minecraft:${state}`, wall]})
  for (let x = center - 1; x <= center + 1; x++) {
    for (let z = front - 1; z <= front + depth; z++) {
      add(x, 0, z, 'stone_bricks')
      for (let y = floor; y < floor + 3; y++) add(x, y, z, 'air')
    }
  }
  for (const {role, x: [start, stop]} of compiled.resolved_form.layout) {
    if (role !== 'corner' && role !== 'pier') continue
    for (let x = candidate.left + start; x <= candidate.left + stop; x++) {
      for (let y = floor; y < beamY; y++) {
        for (let z = front; z < front + depth; z++) add(x, y, z, 'spruce_log[axis=y]')
      }
    }
  }
  for (let x = candidate.left; x <= candidate.right; x++) {
    const timber = x === candidate.left || x === candidate.right ? 'stripped_spruce_wood' : 'spruce_log'
    for (let z = front; z < front + depth; z++) {
      add(x, beamY, z, `${timber}[axis=x]`)
      add(x, roofY, z, 'spruce_slab[type=bottom]')
    }
  }
  for (const {lo, hi} of compiled.openings.filter(row => row.kind === 'window')) {
    for (let x = candidate.left + lo[0]; x <= candidate.left + hi[0]; x++) {
      for (let y = floor + lo[1]; y <= floor + hi[1]; y++) {
        add(x, y, front, 'air')
        add(x, y, front + 1, 'light_blue_stained_glass', true)
        add(x, y, front + 2, 'air')
      }
      add(x, floor + lo[1] - 1, front, 'stone_brick_slab[type=bottom,waterlogged=false]', true)
    }
  }
  return expected
}

const cases = []
for (const [id, width, windows] of [['narrow', 9, 0], ['standard', 19, 2], ['wide', 31, 4], ['boundary', 6, null]]) {
  const workspace = path.join(output, id)
  await fs.mkdir(workspace)
  const candidate = pavilion(width)
  await writeJson(path.join(workspace, 'build.json'), candidate.request)
  if (windows === null) {
    const failure = run(workspace, ['architect', 'plan-build', '--request', 'build.json'], 1)
    assert.equal(failure.code, 'FACADE_FIT_FAILED')
    const [fit] = failure.conflicts
    assert.equal(fit.part, 'facade')
    assert.equal(fit.coordinate_space, 'recipe')
    assert.deepEqual([fit.width, fit.minimum_width, fit.corner_width, fit.left_available, fit.right_available], [6, 7, 1, 1, 0])
    assert.deepEqual(fit.entry_frame_x, [1, 5])
    assert.equal(await exists(path.join(workspace, 'nbt_models')), false)
    await writeJson(path.join(workspace, 'build-receipt.json'), failure)
    cases.push({id, width, failure})
    continue
  }

  const built = run(workspace, ['architect', 'plan-build', '--request', 'build.json'])
  assert.equal(built.checks.architecture.passed, true)
  assert.equal(built.checks.whole_model.routes.passed, true)
  assert.equal(built.approval_created, false)
  assert.equal(built.nbt_exported, false)
  const {source, source_sha256} = built.saved
  assert.equal(hash(await fs.readFile(source)), source_sha256)
  await writeJson(path.join(workspace, 'build-receipt.json'), built)

  await writeJson(path.join(workspace, 'facade.json'), candidate.facade)
  const {result: compiled} = run(workspace, ['components', 'agent', '--tool', 'facade_compile', '--request', 'facade.json'])
  assert.equal(compiled.openings.filter(row => row.kind === 'window').length, windows)
  assert.ok(compiled.construction_graph.joints.length > 0)
  assert.ok(compiled.construction_graph.joints.every(row => row.face_contact))
  await writeJson(path.join(workspace, 'facade-receipt.json'), compiled)

  const expected = samples(candidate, compiled)
  await writeJson(path.join(workspace, 'readback.json'), {source, source_sha256, validate: true, positions: expected.map(row => row.pos)})
  const {result: readback} = run(workspace, ['model', '--request', 'readback.json'])
  assert.equal(readback.validation.whole_model.routes.passed, true)
  assert.deepEqual(readback.model.samples.map(({pos, value}) => ({pos, value})), expected)
  await writeJson(path.join(workspace, 'readback-receipt.json'), readback)

  const cameraFile = path.join(workspace, 'cameras.json')
  await writeJson(cameraFile, cameras)
  const render = path.join(workspace, 'nbt_models/_workspaces/facade-preview')
  run(workspace, ['render', '--source', source, '--cameras', cameraFile, '--output', render, '--width', '960', '--height', '640'])
  const renderManifest = path.join(render, 'render_manifest.json')
  const manifest = JSON.parse(await fs.readFile(renderManifest, 'utf8'))
  assert.equal(manifest.status, 'complete')
  assert.equal(manifest.source_sha256, source_sha256)
  assert.equal(manifest.cameras_sha256, hash(await fs.readFile(cameraFile)))
  assert.deepEqual(manifest.images.map(row => row.image), cameras.map(camera => `${camera.id}.png`))
  for (const {image, sha256} of manifest.images) assert.equal(hash(await fs.readFile(path.join(render, image))), sha256)
  assert.equal(await exists(path.join(workspace, 'nbt_models/_exports')), false)
  cases.push({id, width, windows, source, source_sha256, checkedVoxels: expected.length,
    cameras_sha256: manifest.cameras_sha256, renderManifest, images: manifest.images.map(row => path.join(render, row.image))})
}

assert.equal(new Set(cases.filter(row => row.source).map(row => row.cameras_sha256)).size, 1)
await writeJson(path.join(output, 'results.json'), {passed: true, cases})
console.log(JSON.stringify({passed: true, output, cases: cases.map(({id, width, windows, checkedVoxels}) => ({id, width, windows, checkedVoxels}))}))
