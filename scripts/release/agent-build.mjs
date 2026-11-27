import fs from 'node:fs/promises'
import path from 'node:path'
import { execFileSync } from 'node:child_process'
import { parseArgs } from 'node:util'
import { root, skill, python } from '../paths.mjs'
import { buildWeb } from '../build-web.mjs'
import { copyPinnedChromium } from './chromium.mjs'

if (process.platform !== 'win32' || process.arch !== 'x64') throw Error('Build Agent package on Windows x64')
const { values } = parseArgs({ options: { out: { type: 'string', default: 'dist/agent' }, prebuilt: { type: 'boolean' } } })
const output = path.resolve(root, values.out)
const { name, version, license, engines } = JSON.parse(await fs.readFile(path.join(root, 'package.json'), 'utf8'))
const stage = path.join(output, 'NBTCreator-Agent-win32-x64')

execFileSync(process.execPath, [path.join(root, 'scripts/sync-capabilities.mjs'), '--check'], { stdio: 'inherit', windowsHide: true })
if (!values.prebuilt) {
  execFileSync(python, [path.join(root, 'scripts/assets/sync-asset-library.py'), '--check'], { stdio: 'inherit', windowsHide: true })
  await buildWeb()
}
await fs.mkdir(output, { recursive: true })
await fs.mkdir(stage)

async function copy(relative) {
  const source = path.join(root, relative)
  const destination = path.join(stage, relative)
  await fs.mkdir(path.dirname(destination), { recursive: true })
  await fs.cp(source, destination, { recursive: true, errorOnExist: true, force: false, filter(file) {
    const parts = path.relative(source, file).split(path.sep)
    const name = path.basename(file)
    return !parts.some(part => ['.git', '.vite', '.local-browsers', '__pycache__', 'node_modules', '.nbtcreator', 'nbt_models'].includes(part)) &&
      !/^(?:\.env(?:\..*)?|api-settings\.json)$|\.(?:log|pyc)$/i.test(name)
  } })
}

const skillPath = path.relative(root, skill)
const viewer = path.join(skillPath, 'assets/viewer')
const copies = ['LICENSE', 'desktop/python-runtime.cjs', 'scripts/paths.mjs', 'scripts/mcp',
  ...['scripts', 'references', 'config', 'constraint-extensions', 'constraint-presets.json', 'tool-catalog.json',
    'requirements.txt', 'SKILL.md'].map(item => path.join(skillPath, item)),
  ...['assets/extension-library', 'assets/examples', 'assets/ornament-patterns', 'assets/python',
    'assets/starter-tool-effects', 'assets/git-runtime.json'].map(item => path.join(skillPath, item)),
  ...['web-dist', 'package.json', 'package-lock.json', 'engine-session.mjs', 'browser-launch.mjs', 'viewer-server.mjs',
    'render-batch.mjs', 'src/view-contract.mjs', 'node_modules/playwright', 'node_modules/playwright-core'].map(item => path.join(viewer, item))]
for (const item of copies) await copy(item)
await copyPinnedChromium(path.join(stage, 'runtime/browser'))
await fs.writeFile(path.join(stage, 'package.json'), JSON.stringify({ name, version, type: 'module', license, engines, agentRuntime: true }, null, 2) + '\n')
await fs.writeFile(path.join(stage, 'NBTCreator-MCP.cmd'),
  '@echo off\r\nsetlocal\r\nnode "%~dp0scripts\\mcp\\server.mjs" %*\r\nexit /b %errorlevel%\r\n')
await fs.writeFile(path.join(stage, 'README.txt'),
  'NBTCreator Agent ' + version + ' (Windows x64)\r\n\r\n' +
  'Requires Node.js ' + engines.node + ' and a Python installation with the engine requirements.\r\n' +
  'python -m pip install -r .agents\\skills\\minecraft-nbt-modeler\\requirements.txt\r\n' +
  'Launch as an MCP stdio subprocess. Set an explicit creative workspace.\r\n' +
  'command: node\r\nargs: [absolute-path-to/scripts/mcp/server.mjs, --workspace, absolute-workspace]\r\n' +
  'NBTCreator-MCP.cmd is also provided for Windows terminals.\r\n' +
  'NBTCREATOR_PYTHON may point to a matching interpreter. Chromium and Playwright are included.\r\n' +
  'Add --allow-write for machine mutations. --package-session accepts a host-held authoring session JSON.\r\n')

execFileSync(python, [path.join(root, 'scripts/release/portable-archive.py'), 'pack', '--source', stage, '--kind', 'agent',
  '--output', path.join(output, `NBTCreator-Agent-${version}-windows-x64.zip`)], { stdio: 'inherit', windowsHide: true })
