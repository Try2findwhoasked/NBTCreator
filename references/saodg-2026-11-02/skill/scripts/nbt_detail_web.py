"""Launch the local browser detail console with the same Python environment."""
import argparse
from pathlib import Path
import shutil
import subprocess
import sys


def main():
    root=Path(__file__).resolve().parents[1]
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace',type=Path,default=root.parents[2])
    parser.add_argument('--output',type=Path)
    parser.add_argument('--port',type=int,default=0)
    parser.add_argument('--no-open',action='store_true')
    parser.add_argument('--initial-preset',type=Path)
    parser.add_argument('--library',action='store_true',help='Open the graphical existing-structure selector')
    parser.add_argument('--mod-structures',action='store_true',help='Manage structures registered in the mod resources')
    args=parser.parse_args()
    if args.library or args.mod_structures:
        launcher=root.parents[2]/'tools/structures/workbench/launch.py'
        if not launcher.is_file():raise RuntimeError('结构工作台已独立存放，请使用仓库根目录的 启动结构工作台.cmd')
        command=[sys.executable,str(launcher),'--workspace',str(args.workspace.resolve()),'--port',str(args.port)]
        if args.library:command.append('--library')
        if args.no_open:command.append('--no-open')
        if args.output:command.extend(['--data-root',str(args.output.resolve())])
        return subprocess.call(command)
    viewer=root/'assets/viewer'
    if not shutil.which('node'): raise RuntimeError('Install Node.js >=20.19 to use the browser console')
    if not (viewer/'node_modules/vite').is_dir(): raise RuntimeError(f'Run npm ci --prefix "{viewer}" first')
    command=['node',str(viewer/'detail-server.mjs'),'--workspace',str(args.workspace.resolve()),'--python',sys.executable,'--port',str(args.port)]
    if args.output: command.extend(['--output',str(args.output.resolve())])
    if args.no_open: command.append('--no-open')
    if args.initial_preset:command.extend(['--initial-preset',str(args.initial_preset.resolve())])
    return subprocess.call(command)


if __name__=='__main__': raise SystemExit(main())
