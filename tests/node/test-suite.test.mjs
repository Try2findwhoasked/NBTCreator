import assert from 'node:assert/strict'
import {spawnSync} from 'node:child_process'
import {readFileSync} from 'node:fs'
import path from 'node:path'
import {test} from 'node:test'
import {fileURLToPath} from 'node:url'
import {suiteCommands, suites} from '../suites.mjs'

const root = fileURLToPath(new URL('../../', import.meta.url))
const runner = path.join(root, 'tests/run-suite.mjs')

test('all npm compatibility entries reference discoverable suites', () => {
  const {scripts} = JSON.parse(readFileSync(path.join(root, 'package.json'), 'utf8'))
  const result = spawnSync(process.execPath, [runner, '--list'], {encoding: 'utf8'})
  assert.equal(result.status, 0, result.stderr)
  const names = result.stdout.trim().split(/\r?\n/)
  assert.deepEqual(names, Object.keys(suites).sort())
  for (const [key, command] of Object.entries(scripts)) {
    if (!key.startsWith('test:') || key === 'test:suite') continue
    const name = key.slice('test:'.length)
    assert.ok(names.includes(name), name)
    assert.equal(command, `node tests/run-suite.mjs ${name}`)
  }
})

test('prebuilt source and packaged Electron use the appropriate retrieval checks', () => {
  const full = suiteCommands('retrieval')
  assert.deepEqual(full[0], [process.execPath, 'scripts/build-web.mjs'])
  assert.deepEqual(suiteCommands('retrieval', '--prebuilt'), full.slice(1))
  assert.deepEqual(suiteCommands('retrieval', '--desktop-only'), [
    [process.execPath, 'tests/desktop/retrieval-desktop.mjs'],
  ])
})

test('unknown suites and empty selections fail before running commands', () => {
  for (const args of [['constructor'], ['--desktop-only', 'api']]) {
    const result = spawnSync(process.execPath, [runner, ...args], {encoding: 'utf8'})
    assert.equal(result.status, 1)
    assert.match(result.stderr, new RegExp(args.at(-1)))
  }
})
