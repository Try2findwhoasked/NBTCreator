"""Vendor official MinGit with pinned archive integrity and its license files."""
import argparse,hashlib,json,os,subprocess,urllib.request,zipfile
from pathlib import Path,PurePosixPath
ROOT=Path(__file__).resolve().parents[1]

def vendor(destination,cache):
    lock=json.loads((ROOT/'config/portable-runtime.json').read_text(encoding='utf8'))['git']
    destination=Path(destination).resolve();cache=Path(cache).resolve();cache.mkdir(parents=True,exist_ok=True)
    archive=cache/Path(lock['url']).name
    if not archive.is_file():
        temporary=archive.with_suffix('.partial')
        with urllib.request.urlopen(urllib.request.Request(lock['url'],headers={'User-Agent':'NBTCreator-build'}),timeout=120) as source,temporary.open('wb') as target:
            import shutil
            shutil.copyfileobj(source,target)
        if hashlib.sha256(temporary.read_bytes()).hexdigest()!=lock['sha256']:raise ValueError('Downloaded MinGit archive is incomplete or has an unexpected SHA256; kept as partial')
        temporary.replace(archive)
    if hashlib.sha256(archive.read_bytes()).hexdigest()!=lock['sha256']:raise ValueError('MinGit archive SHA256 mismatch')
    destination.mkdir(parents=True,exist_ok=False)
    with zipfile.ZipFile(archive) as package:
        for item in package.infolist():
            name=PurePosixPath(item.filename)
            if name.is_absolute() or '..' in name.parts or '\\' in item.filename or ':' in item.filename or (item.external_attr>>16)&0o170000==0o120000:raise ValueError('Unsafe MinGit archive member')
        package.extractall(destination)
    executable=destination/'cmd/git.exe'
    env={k:v for k,v in os.environ.items() if not k.startswith('GIT_')};env.update(GIT_CONFIG_NOSYSTEM='1',GIT_CONFIG_GLOBAL=os.devnull)
    version=subprocess.check_output([str(executable),'--version'],env=env,encoding='utf8').strip()
    if version!='git version '+lock['version']:raise ValueError('Unexpected bundled Git version: '+version)
    receipt=dict(lock,executable='cmd/git.exe',executable_sha256=hashlib.sha256(executable.read_bytes()).hexdigest())
    expected=json.loads((ROOT/'.agents/skills/minecraft-nbt-modeler/assets/git-runtime.json').read_text(encoding='utf8'))
    if receipt['executable_sha256']!=expected['executable_sha256'] or not (destination/'LICENSE.txt').is_file():raise ValueError('Bundled Git executable or license does not match the pinned runtime')
    (destination/'runtime-lock.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf8')
    print(json.dumps(dict(passed=True,git=version,executable_sha256=receipt['executable_sha256'],destination=str(destination))))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--destination',type=Path,required=True);parser.add_argument('--cache',type=Path,required=True);args=parser.parse_args();vendor(args.destination,args.cache)
