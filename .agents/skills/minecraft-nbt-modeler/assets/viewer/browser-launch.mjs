import fs from 'node:fs/promises'
import path from 'node:path'
import { createRequire } from 'node:module'

// The workspace keeps its own renderer implementation. Only the pinned optional
// Playwright dependency can come from the application/portable runtime binding.
const require = createRequire(process.env.NBTCREATOR_PLAYWRIGHT_MODULE
  ? path.join(path.resolve(process.env.NBTCREATOR_PLAYWRIGHT_MODULE), 'package.json')
  : import.meta.url)
const { chromium } = require('playwright')
const pinned = process.env.NBTCREATOR_PINNED_RENDER === '1'

async function browserPin() {
  const core = createRequire(require.resolve('playwright/package.json')).resolve('playwright-core/package.json')
  const meta = JSON.parse(await fs.readFile(core, 'utf8'))
  if (meta.version !== process.env.NBTCREATOR_PLAYWRIGHT_VERSION) throw Error('Playwright Core version differs from the frozen Playwright pin.')
  const registry = JSON.parse(await fs.readFile(path.join(path.dirname(core), 'browsers.json'), 'utf8'))
  const version = registry.browsers.find(item => item.name === 'chromium')?.browserVersion
  if (!version) throw Error('Missing Chromium version in Playwright registry.')
  if (process.env.NBTCREATOR_RENDER_CHROMIUM && version !== process.env.NBTCREATOR_RENDER_CHROMIUM) {
    throw Error('Chromium registry version differs from the synchronized installation.')
  }
  return version
}

async function exists(file) {
  try { await fs.access(file); return true } catch { return false }
}

export async function resolveRenderBrowser(executablePath) {
  executablePath ||= process.env.NBTCREATOR_BROWSER
  if (executablePath) {
    const configured=path.resolve(executablePath)
    if(await exists(configured))return configured
    throw new Error('Configured rendering browser is missing. Re-sync the workspace or check --browser-executable.')
  }
  if (await exists(chromium.executablePath())) return chromium.executablePath()
  if (pinned) throw Error('Pinned Chromium is missing at '+chromium.executablePath()+'. Inspect a trusted installation and its local browser cache with paths --runtime.')
  if (process.platform === 'win32') {
    const candidates = [
      path.join(process.env['PROGRAMFILES(X86)'] ?? 'C:/Program Files (x86)', 'Microsoft/Edge/Application/msedge.exe'),
      path.join(process.env.PROGRAMFILES ?? 'C:/Program Files', 'Microsoft/Edge/Application/msedge.exe'),
      path.join(process.env.PROGRAMFILES ?? 'C:/Program Files', 'Google/Chrome/Application/chrome.exe'),
      path.join(process.env.LOCALAPPDATA ?? '', 'Google/Chrome/Application/chrome.exe'),
    ]
    for (const candidate of candidates) {
      if (await exists(candidate)) return candidate
    }
  }
  throw new Error('No rendering browser found. Install Chromium with "npx playwright install chromium" in assets/viewer, or pass --browser-executable.')
}

export async function launchRenderBrowser(executablePath) {
  // A fresh, headless browser profile: never attach to a user's existing session.
  if (pinned && process.env.NBTCREATOR_RENDER_ELECTRON && process.versions.electron !== process.env.NBTCREATOR_RENDER_ELECTRON) {
    throw Error('Rendering requires Electron '+process.env.NBTCREATOR_RENDER_ELECTRON+'; found '+(process.versions.electron??'standalone Node'))
  }
  if (pinned && process.env.NBTCREATOR_RENDER_NODE_VERSION && process.versions.node !== process.env.NBTCREATOR_RENDER_NODE_VERSION) {
    throw Error('Bound Node version changed. Inspect the trusted installation with paths --runtime.')
  }
  const expected = pinned ? await browserPin() : null
  const browser = await chromium.launch({executablePath:await resolveRenderBrowser(executablePath),headless:true,timeout:15000})
  if (expected && browser.version() !== expected) {
    const actual = browser.version()
    await browser.close()
    throw Error('Rendering requires Chromium '+expected+'; found '+actual+'. Select the matching local cache.')
  }
  return browser
}

export async function probeRenderRuntime() {
  const browser = await launchRenderBrowser()
  try {
    return {browser:await resolveRenderBrowser(),browser_version:browser.version(),node_version:process.versions.node,
      electron:process.versions.electron??null,playwright_version:require('playwright/package.json').version}
  } finally {await browser.close()}
}
