"""ZIP the complete app (including .agents), verify hashes on extraction."""
import argparse,hashlib,json,zipfile
from pathlib import Path,PurePosixPath

def digest(file):
    h=hashlib.sha256()
    with file.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def valid_name(name):
    p=PurePosixPath(name)
    if p.is_absolute() or '..' in p.parts or '\\' in name or ':' in name:raise ValueError('Unsafe ZIP path: '+name)
    return p

def pack(source,output,kind="full"):
    source=source.resolve();output=output.resolve()
    if output.exists():raise FileExistsError(output)
    files=[]
    for file in sorted(source.rglob('*')):
        if file.is_symlink():raise ValueError('Symlink in portable package: '+str(file))
        if not file.is_file():continue
        relative=file.relative_to(source).as_posix();valid_name(relative)
        # Runtime probes can create engine bytecode in a tested directory.
        # Omit this disposable cache without deleting or changing the input.
        if relative.startswith('resources/app/.agents/skills/minecraft-nbt-modeler/') and '__pycache__' in PurePosixPath(relative).parts:continue
        is_runtime=not (relative.startswith('resources/app/') and not relative.startswith('resources/app/runtime/') or relative in {'portable-info.json','NBT工具.cmd','Portable说明.txt'})
        if kind=='application' and is_runtime or kind=='runtime' and not is_runtime:continue
        parts=PurePosixPath(relative).parts
        if any(p in {'.git','.github','.nbtcreator','nbt_models'} for p in parts) or file.name=='api-settings.json' or file.name=='.env' or file.name.startswith('.env.'):
            raise ValueError('Private/generated content in portable package: '+relative)
        files.append(dict(path=source.name+'/'+relative,bytes=file.stat().st_size,sha256=digest(file)))
    expected={f['path'] for f in files}
    requirements={'full':['NBTCreator.exe','resources/app/runtime/python/python.exe','resources/app/runtime/browser/chrome.exe','resources/app/.agents/skills/minecraft-nbt-modeler/SKILL.md'],'application':['resources/app/.agents/skills/minecraft-nbt-modeler/SKILL.md'],'runtime':['NBTCreator.exe','resources/app/runtime/python/python.exe','resources/app/runtime/browser/chrome.exe']}
    if kind in {'full','runtime'}:requirements[kind].append('resources/app/runtime/git/cmd/git.exe')
    for required in requirements[kind]:
        if source.name+'/'+required not in expected:raise ValueError('Missing portable dependency: '+required)
    output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as z:
        for item in files:z.write(source.parent/item['path'],item['path'])
    manifest=dict(schema_version=1,kind=kind,archive=output.name,sha256=digest(output),root=source.name,files=files)
    output.with_suffix('.manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    output.with_suffix(output.suffix+'.sha256').write_text(manifest['sha256']+'  '+output.name+'\n',encoding='ascii')
    print(json.dumps(dict(passed=True,archive=str(output),files=len(files),bytes=output.stat().st_size,sha256=manifest['sha256'])))

def unpack(archive,destination):
    manifest=json.loads(archive.with_suffix('.manifest.json').read_text(encoding='utf8'))
    if manifest['archive']!=archive.name or manifest['sha256']!=digest(archive):raise ValueError('Portable ZIP checksum mismatch')
    destination=destination.resolve();destination.mkdir(parents=True,exist_ok=False)
    expected={item['path']:item for item in manifest['files']}
    with zipfile.ZipFile(archive) as z:
        if len(z.namelist())!=len(expected) or set(z.namelist())!=set(expected):raise ValueError('ZIP manifest differs')
        for name in z.namelist():valid_name(name)
        z.extractall(destination)
    for name,item in expected.items():
        file=destination/name
        if file.stat().st_size!=item['bytes'] or digest(file)!=item['sha256']:raise ValueError('Extracted file checksum mismatch: '+name)
    print(json.dumps(dict(passed=True,directory=str(destination/manifest['root']),files=len(expected))))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['pack','unpack']);p.add_argument('--kind',choices=['full','application','runtime'],default='full');p.add_argument('--source',type=Path);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.command=='pack':pack(a.source,a.output,a.kind)
    else:unpack(a.source,a.output)
