import { spawn } from 'node:child_process'
import path from 'node:path'
import { python, skill } from '../paths.mjs'
import { failure, maxResponse } from './stdio.mjs'

function stop(child, tree) {
  if (!child.pid || child.exitCode !== null || child.signalCode !== null) return
  if (tree && process.platform === 'win32') {
    const taskkill = path.join(process.env.SystemRoot || 'C:\\Windows', 'System32', 'taskkill.exe')
    const killer = spawn(taskkill, ['/PID', String(child.pid), '/T', '/F'], { stdio: 'ignore', windowsHide: true })
    killer.on('error', () => child.kill())
    killer.on('exit', code => { if (code !== 0) child.kill() })
  } else if (tree) {
    try { process.kill(-child.pid, 'SIGKILL') } catch (error) { if (error.code !== 'ESRCH') child.kill() }
  } else child.kill()
}

// Commands and executable configuration come from the installation and its host.
export async function runPython(workspace, args, { input, signal, tree = false } = {}) {
  signal?.throwIfAborted()
  return new Promise((resolve, reject) => {
    const child = spawn(python, ['-B', ...args], {
      cwd: workspace, shell: false, windowsHide: true, detached: tree && process.platform !== 'win32',
      env: { ...process.env, PYTHONUTF8: '1', PYTHONIOENCODING: 'utf-8' }
    })
    let output = [], size = 0, diagnostics = '', problem
    function abort(error) {
      problem ??= error
      stop(child, tree)
    }
    const cancelled = () => abort(signal.reason)
    signal?.addEventListener('abort', cancelled, { once: true })
    child.on('error', error => {
      problem ??= failure('ENGINE_UNAVAILABLE', '启动 Python 失败，请检查 NBTCREATOR_PYTHON 或 PATH', { cause: error.code })
    })
    child.stdin.on('error', () => {})
    child.stdout.on('data', chunk => {
      if (problem) return
      size += chunk.length
      if (size > maxResponse) abort(failure('RESPONSE_TOO_LARGE', 'Python 返回超过 32 MiB'))
      else output.push(chunk)
    })
    child.stderr.setEncoding('utf8')
    child.stderr.on('data', chunk => { diagnostics = (diagnostics + chunk).slice(-4000) })
    child.once('close', code => {
      signal?.removeEventListener('abort', cancelled)
      if (problem) return reject(problem)
      const stdout = Buffer.concat(output, size).toString('utf8').trim()
      try {
        // The render CLI can report progress before printing its JSON receipt.
        resolve({ code, data: JSON.parse(stdout.slice(stdout.lastIndexOf('\n') + 1)) })
      } catch {
        if (diagnostics) process.stderr.write(diagnostics + '\n')
        reject(failure('ENGINE_FAILED', 'Python 没有返回结构化结果，请检查服务 stderr', { exit_code: code }))
      }
    })
    child.stdin.end(input === undefined ? undefined : JSON.stringify(input))
  })
}

export const engineScript = name => path.join(skill, 'scripts', name)
