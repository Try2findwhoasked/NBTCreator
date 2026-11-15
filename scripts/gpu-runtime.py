"""Isolated optional GPU environment; reuse pip cache and base NumPy/Pillow."""
import os,subprocess,sys,venv
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ENV=ROOT/'build/gpu-env'
PYTHON=ENV/('Scripts/python.exe' if os.name=='nt' else 'bin/python')

def main():
    action=sys.argv[1] if len(sys.argv)>1 else 'info'
    if action=='setup':
        if not PYTHON.exists():venv.EnvBuilder(with_pip=True,system_site_packages=True).create(ENV)
        return subprocess.call([str(PYTHON),'-m','pip','install','--only-binary=:all:','-r',str(ROOT/'config/requirements-gpu.txt')],cwd=ROOT)
    if not PYTHON.exists():raise SystemExit('GPU environment missing; run mise run gpu:setup')
    env=dict(os.environ,NBTCREATOR_PYTHON=str(PYTHON))
    if action=='info':
        return subprocess.call([str(PYTHON),'-B',str(ROOT/'.agents/skills/minecraft-nbt-modeler/scripts/nbt_compute.py')],cwd=ROOT,env=env)
    if action=='python':return subprocess.call([str(PYTHON),*sys.argv[2:]],cwd=ROOT,env=env)
    if action=='node':return subprocess.call(['node',*sys.argv[2:]],cwd=ROOT,env=env)
    raise SystemExit('Expected setup/info/python/node')

if __name__=='__main__':raise SystemExit(main())
