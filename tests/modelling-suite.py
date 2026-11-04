"""Run hyphenated modelling fixtures explicitly (unittest discovery skips them)."""
from pathlib import Path
import subprocess
import sys
root=Path(__file__).resolve().parents[1]
for fixture in sorted((root/'tests').glob('modelling-*.py')):
    if fixture.name=='modelling-suite.py': continue
    subprocess.run([sys.executable,str(fixture)],cwd=root,check=True)
