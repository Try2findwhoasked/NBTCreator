import fs from 'node:fs/promises'
import path from 'node:path'
import { execFileSync } from 'node:child_process'
import { createRequire } from 'node:module'
import { skill } from '../paths.mjs'

const require = createRequire(path.join(skill, 'assets/viewer/package.json'))

export async function copyPinnedChromium(destination, env = process.env) {
  const pkg = require.resolve('playwright/package.json')
  const cli = path.join(path.dirname(pkg), 'cli.js')
  const options = { env, encoding: 'utf8', windowsHide: true }
  const browser = execFileSync(process.execPath, ['-e', 'console.log(require(process.argv[1]).chromium.executablePath())',
    require.resolve('playwright')], options).trim()
  if (!await fs.access(browser).then(() => true, () => false)) {
    execFileSync(process.execPath, [cli, 'install', 'chromium', '--no-shell'], { ...options, stdio: 'inherit' })
  }
  await fs.mkdir(path.dirname(destination), { recursive: true })
  await fs.cp(path.dirname(browser), destination, { recursive: true, errorOnExist: true, force: false,
    filter: file => !file.toLowerCase().endsWith('.log') })
}
