// Batch artifact rendering, not UI automation of an existing user browser.
import fs from 'node:fs/promises'
import path from 'node:path'
import { pathToFileURL } from 'node:url'
import { parseArgs } from 'node:util'
import { createHash } from 'node:crypto'
import { createViewerServer } from './viewer-server.mjs'
import { launchRenderBrowser } from './browser-launch.mjs'
import { normalizeViews } from './src/view-contract.mjs'

const hash = bytes => createHash('sha256').update(bytes).digest('hex')
const writeJson = (file, value) => fs.writeFile(file, JSON.stringify(value, null, 2) + '\n', { flag: 'wx' })
async function deadline(promise, timeout) {
  let timer
  try {
    return await Promise.race([promise, new Promise((_, reject) => {
      timer = setTimeout(() => reject(new Error('Render operation timed out')), timeout)
    })])
  } finally { clearTimeout(timer) }
}

export async function renderBatch(options) {
  const width = Number(options.width ?? 960)
  const height = Number(options.height ?? 640)
  const timeout = Number(options.timeout ?? 60000)
  const quality = options.quality ?? 'balanced'
  const prefix = options.filePrefix ?? ''
  if (![width, height].every(v => Number.isInteger(v) && v >= 64 && v <= 4096)) throw new Error('Image dimensions must be 64..4096')
  if (!Number.isInteger(timeout) || timeout < 1000 || timeout > 300000) throw new Error('timeout must be 1000..300000 ms per view')
  if (!['balanced', 'high'].includes(quality)) throw new Error('quality must be balanced/high')
  if (prefix && !/^[a-z0-9][a-z0-9_-]*_$/.test(prefix)) throw new Error('file-prefix must be a portable lowercase prefix ending in underscore')
  const model = path.resolve(options.model)
  const output = path.resolve(options.output)
  const snapshotBytes = await fs.readFile(model)
  const snapshot = JSON.parse(snapshotBytes)
  const cameraBytes = options.cameras ? await fs.readFile(options.cameras) : null
  const views = normalizeViews(cameraBytes ? JSON.parse(cameraBytes) : snapshot.cameras, snapshot.size)
  // Python reserves a new output directory and places snapshot.json in it.
  // A standalone Node call may instead reference a snapshot outside a new directory.
  await fs.mkdir(output, { recursive: true })
  const existing = await fs.readdir(output)
  if (existing.some(name => path.join(output, name) !== model)) throw new Error('Render output must be new or contain only its input snapshot; never overwrite a previous batch')
  const lock = path.join(output, '.render.lock')
  await fs.writeFile(lock, String(process.pid), { flag: 'wx' })
  let viewer, browser
  const warnings = [], pageErrors = [], resourceErrors = [], images = []
  const started = performance.now()
  const report = {
    format_version: 1, status: 'running', source: snapshot.source, source_sha256: snapshot.source_sha256,
    geometry_sha256: snapshot.geometry_sha256, snapshot_sha256: hash(snapshotBytes),
    cameras_sha256: cameraBytes ? hash(cameraBytes) : null, width, height, quality, pixel_ratio: 1,
    scope: 'Texture preview only; no collision, runtime, lighting or visual-design certification',
    images, warnings, page_errors: pageErrors, resource_errors: resourceErrors,
    cleanup: { browser_closed: false, server_closed: false },
    views,
  }
  try {
    const frozenSnapshot = path.join(output, 'snapshot.json')
    if (frozenSnapshot !== model) await fs.writeFile(frozenSnapshot, snapshotBytes, { flag: 'wx' })
    report.snapshot_file = 'snapshot.json'
    viewer = await createViewerServer({ model: frozenSnapshot, port: 0 })
    browser = await launchRenderBrowser(options.browserExecutable)
    report.browser_version = browser.version()
    const context = await browser.newContext({ viewport: { width, height }, deviceScaleFactor: 1, acceptDownloads: false })
    const page = await context.newPage()
    page.setDefaultTimeout(timeout)
    page.on('pageerror', error => pageErrors.push(error.message))
    page.on('response', response => {
      if (response.status() >= 400) resourceErrors.push({ url: response.url(), status: response.status() })
    })
    page.on('requestfailed', request => resourceErrors.push({ url: request.url(), error: request.failure()?.errorText }))
    page.on('console', message => {
      if (['warning', 'warn', 'error'].includes(message.type())) warnings.push({ level: message.type(), text: message.text() })
    })
    await page.goto(`${viewer.url}?quality=${quality}&pixelRatio=1`, { timeout, waitUntil: 'domcontentloaded' })
    await page.waitForFunction(() => Boolean(window.nbtModeler?.ready), undefined, { timeout })
    await deadline(page.evaluate(() => window.nbtModeler.ready), timeout)
    report.initialization_ms = await page.evaluate(() => window.nbtModeler.initialization_ms)
    for (const view of views) {
      const viewStarted = performance.now()
      // Timeouts apply to this specific capture, not to an unbounded browser job.
      const captured = await deadline(page.evaluate(view => window.nbtModeler.capture(view), view), timeout)
      if (pageErrors.length || resourceErrors.length || warnings.some(message => message.level === 'error')) {
        throw new Error('Viewer or resource errors: ' + JSON.stringify({ pageErrors, resourceErrors, consoleErrors: warnings.filter(message => message.level === 'error') }))
      }
      if (!captured.dataUrl.startsWith('data:image/png;base64,')) throw new Error('Expected a PNG canvas capture')
      const bytes = Buffer.from(captured.dataUrl.split(',')[1], 'base64')
      if (bytes.subarray(1, 4).toString() !== 'PNG' || bytes.readUInt32BE(16) !== width || bytes.readUInt32BE(20) !== height) {
        throw new Error('PNG dimensions differ from the requested viewport')
      }
      const file = `${prefix}${view.id}.png`
      const metadataFile = `${prefix}${view.id}.json`
      const metadata = {
        ...captured.metadata, id: view.id, role: view.role, requested_view: view,
        snapshot_sha256: report.snapshot_sha256, image: file, image_sha256: hash(bytes),
        duration_ms: performance.now() - viewStarted,
      }
      await fs.writeFile(path.join(output, file), bytes, { flag: 'wx' })
      await writeJson(path.join(output, metadataFile), metadata)
      images.push({ image: file, metadata: metadataFile, sha256: metadata.image_sha256,
        mesh_builds: metadata.mesh_builds, rendered_frames: metadata.rendered_frames, duration_ms: metadata.duration_ms })
    }
    if (hash(await fs.readFile(model)) !== report.snapshot_sha256) throw new Error('Snapshot changed during rendering')
    if (snapshot.source && hash(await fs.readFile(snapshot.source)) !== snapshot.source_sha256) throw new Error('Source model changed during rendering')
    report.status = 'complete'
  } catch (error) {
    report.status = 'failed'
    report.error = error.message
    throw error
  } finally {
    try { if (browser) await browser.close(); report.cleanup.browser_closed = true }
    finally {
      try { if (viewer) await viewer.close(); report.cleanup.server_closed = true }
      finally {
        report.duration_ms = performance.now() - started
        await writeJson(path.join(output, 'render_manifest.json'), report)
        await fs.unlink(lock)
      }
    }
  }
  return report
}

async function main() {
  const { values } = parseArgs({ options: {
    model: { type: 'string' }, cameras: { type: 'string' }, output: { type: 'string' },
    width: { type: 'string' }, height: { type: 'string' }, quality: { type: 'string' },
    timeout: { type: 'string' }, 'file-prefix': { type: 'string' }, 'browser-executable': { type: 'string' },
  } })
  if (!values.model || !values.output) throw new Error('Usage: node render-batch.mjs --model snapshot.json --output new-directory [--cameras views.json]')
  const report = await renderBatch({ ...values, filePrefix: values['file-prefix'], browserExecutable: values['browser-executable'] })
  console.log(JSON.stringify({ status: report.status, images: report.images.length, duration_ms: report.duration_ms,
    manifest: path.resolve(values.output, 'render_manifest.json') }))
}
if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  main().catch(error => { console.error(`render-batch: ${error.message}`); process.exitCode = 1 })
}
