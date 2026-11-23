import {spawnSync} from 'node:child_process'
import {root} from '../scripts/paths.mjs'
import {suiteCommands, suites} from './suites.mjs'

function main(argv) {
  const mode = ['--prebuilt', '--desktop-only'].includes(argv[0]) ? argv.shift() : ''
  const [name, ...args] = argv

  if (name === '--list') {
    console.log(Object.keys(suites).sort().join('\n'))
    return 0
  }
  if (!name || name === '--help' || name === '-h') {
    console.log('运行测试用 mise run test -- [--prebuilt|--desktop-only] <测试套件> [参数]')
    console.log('用 mise run test -- --list 列出套件')
    return 0
  }

  const commands = suiteCommands(name, mode)
  if (!commands) {
    console.error(`未知测试套件 ${name}。运行 mise run test -- --list 查看名称。`)
    return 1
  }
  if (!commands.length) {
    console.error(`${name} 没有适用于 ${mode} 的检查。`)
    return 1
  }

  for (const [index, [executable, ...commandArgs]] of commands.entries()) {
    if (index === commands.length - 1) commandArgs.push(...args)
    const result = spawnSync(executable, commandArgs, {cwd: root, stdio: 'inherit', windowsHide: true})
    if (result.error) console.error(result.error.message)
    if (result.status !== 0) return result.status ?? 1
  }
  return 0
}

process.exitCode = main(process.argv.slice(2))
