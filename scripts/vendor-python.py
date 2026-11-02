"""Build the private, pinned Windows Python runtime; never use an end-user pip."""
import argparse, hashlib, json, shutil, subprocess, urllib.request, zipfile
from pathlib import Path, PurePosixPath

ROOT=Path(__file__).resolve().parents[1]

def download(item,cache):
    file=cache/Path(item['url']).name
    if not file.exists():
        temporary=file.with_suffix(file.suffix+'.partial')
        with urllib.request.urlopen(item['url'],timeout=120) as source, temporary.open('wb') as target:
            shutil.copyfileobj(source,target)
        temporary.replace(file)
    if hashlib.sha256(file.read_bytes()).hexdigest()!=item['sha256']:
        raise ValueError('Download hash mismatch: '+file.name)
    return file

def extract(archive,directory):
    with zipfile.ZipFile(archive) as z:
        for item in z.infolist():
            name=PurePosixPath(item.filename)
            if name.is_absolute() or '..' in name.parts or '\\' in item.filename:
                raise ValueError('Invalid archive member')
        z.extractall(directory)

def vendor(destination,cache):
    lock=json.loads((ROOT/'config/portable-runtime.json').read_text(encoding='utf8'))
    destination=Path(destination).resolve();destination.mkdir(parents=True,exist_ok=False)
    cache=Path(cache).resolve();cache.mkdir(parents=True,exist_ok=True)
    extract(download(lock['python'],cache),destination)
    for wheel in lock['wheels']:
        extract(download(wheel,cache),destination/'Lib/site-packages')
    pth=list(destination.glob('python*._pth'))
    if len(pth)!=1:raise ValueError('Expected one embedded Python path file')
    pth[0].write_text('python314.zip\n.\nLib/site-packages\nimport site\n',encoding='utf8')
    # Embedded Python deliberately omits the script directory. Restore only the
    # explicitly invoked script's directory so copied workspace runtimes work too.
    (destination/'sitecustomize.py').write_text(
        'import os,sys\n'
        'if sys.argv and os.path.isfile(sys.argv[0]):\n'
        '    sys.path.insert(0,os.path.dirname(os.path.abspath(sys.argv[0])))\n',encoding='utf8')
    (destination/'runtime-lock.json').write_text(json.dumps(lock,indent=2)+'\n',encoding='utf8')
    subprocess.run([str(destination/'python.exe'),'-B','-c',
        'import sys,numpy,PIL;print("Bundled runtime:",sys.version.split()[0],numpy.__version__,PIL.__version__)'],check=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--destination',type=Path,required=True);p.add_argument('--cache',type=Path,required=True)
    a=p.parse_args();vendor(a.destination,a.cache)
