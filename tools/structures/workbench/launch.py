"""Launch the independent SAODG structure workbench."""
import argparse
from pathlib import Path
import shutil
import subprocess
import sys


def main():
    here=Path(__file__).resolve().parent
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--workspace',type=Path,default=here.parents[2]);parser.add_argument('--port',type=int,default=0)
    parser.add_argument('--no-open',action='store_true');parser.add_argument('--library',action='store_true');parser.add_argument('--data-root',type=Path);args=parser.parse_args()
    if not shutil.which('node'):raise RuntimeError('请安装Node.js >=20.19')
    command=['node',str(here/'server.mjs'),'--workspace',str(args.workspace.resolve()),'--python',sys.executable,'--port',str(args.port)]
    if args.no_open:command.append('--no-open')
    if args.library:command.append('--library')
    if args.data_root:command+=['--data-root',str(args.data_root.resolve())]
    return subprocess.call(command)


if __name__=='__main__':raise SystemExit(main())
