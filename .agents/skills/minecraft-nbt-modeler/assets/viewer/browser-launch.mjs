import fs from 'node:fs/promises'
import path from 'node:path'
import { createRequire } from 'node:module'

// The workspace keeps its own renderer implementation. Only the pinned optional
// Playwright dependency can come from the application/portable runtime binding.
const require = createRequire(process.env.NBTCREATOR_PLAYWRIGHT_MODULE
  ? path.join(path.resolve(process.env.NBTCREATOR_PLAYWRIGHT_MODULE), 'package.json')
  : import.meta.url)
const { chromium } = require('playwright')

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
  return chromium.launch({executablePath:await resolveRenderBrowser(executablePath),headless:true})
}
