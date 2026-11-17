import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import path from 'node:path'
import {execFileSync} from 'node:child_process'
import {root, python} from '../../scripts/paths.mjs'

const output = await fs.mkdtemp(path.join(root, 'build/model-render-'))
const workspace = path.join(output, 'workspace')
await fs.mkdir(workspace)
execFileSync(python, ['-B', path.join(root, 'tests/support/working-model-fixture.py'), workspace, output], {cwd:root, windowsHide:true, encoding:'utf8'})
const fixture = JSON.parse(await fs.readFile(path.join(output, 'fixture.json'), 'utf8'))
const images = []
for (const stage of ['before', 'after']) {
  const candidate = fixture[stage]
  const destination = path.join(output, stage+'-textures')
  execFileSync(process.execPath, [path.join(root, 'scripts/cli.mjs'), '--workspace', workspace,
    'render', '--source', candidate.source, '--cameras', candidate.cameras, '--output', destination],
    {cwd:root, windowsHide:true, encoding:'utf8', timeout:120000})
  const manifest = JSON.parse(await fs.readFile(path.join(destination, 'render_manifest.json'), 'utf8'))
  assert.equal(manifest.status, 'complete')
  const names = await fs.readdir(destination)
  const image = path.join(destination, names.find(name => name.endsWith('.png')))
  const bytes = await fs.readFile(image)
  assert.equal(bytes.subarray(1,4).toString(), 'PNG')
  assert.ok(bytes.readUInt32BE(16) > 100)
  images.push(image)
}
assert.notEqual(fixture.before.model_sha256, fixture.after.model_sha256)
assert.deepEqual(JSON.parse(await fs.readFile(fixture.before.cameras,'utf8')), JSON.parse(await fs.readFile(fixture.after.cameras,'utf8')))
const result = {passed:true, output, images, sameCamera:true, sourceRoundtrip:true, nbtExported:false}
await fs.writeFile(path.join(output,'results.json'), JSON.stringify(result,null,2))
console.log(JSON.stringify(result))
