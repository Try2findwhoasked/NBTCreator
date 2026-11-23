"""Resolve an authoring project's root and allocate a new sibling version."""
from pathlib import Path
from functools import lru_cache
import json
import re
from datetime import datetime, timezone, timedelta
VERSION=re.compile(r'^(v|detail_v|refined_v)(\d+)$',re.I)
INFRA={'master','masters','runtime','parts','revision','delivery'}

@lru_cache(maxsize=32)
def path_map(file, size, modified_ns):
    if size>16*1024*1024:raise ValueError('迁移路径映射过大')
    data=json.loads(file.read_text(encoding='utf-8'))
    if data.get('schema_version')!=1 or not isinstance(data.get('aliases'),dict):
        raise ValueError('迁移路径映射格式无效')
    return data


def workspace_path(workspace,value):
    workspace=Path(workspace).resolve()
    model_root=workspace/'nbt_models'
    source=(workspace/Path(value)).resolve()
    mapping_file=model_root/'_migration/room-layout.json'
    if source.is_relative_to(model_root) and source.exists() or not mapping_file.is_file():
        return source
    stat=mapping_file.stat()
    mapping=path_map(mapping_file,stat.st_size,stat.st_mtime_ns)
    old_workspace=Path(mapping.get('source_workspace','')).resolve()
    if source.is_relative_to(model_root):
        key=source.relative_to(workspace).as_posix()
    elif source.is_relative_to(old_workspace/'nbt_models'):
        key=source.relative_to(old_workspace).as_posix()
    else:
        return source
    # Prefix lookup keeps historical relative paths valid when a room moves.
    parts=key.split('/')
    for end in range(len(parts),1,-1):
        alias=mapping['aliases'].get('/'.join(parts[:end]))
        if alias:
            target=(workspace/alias/Path(*parts[end:])).resolve()
            if not target.is_relative_to(model_root):raise ValueError('迁移路径越出工作区')
            return target
    if not source.is_relative_to(model_root):
        return (workspace/key).resolve()
    return source

def prior_workspace_paths(workspace, path):
    workspace=Path(workspace).resolve()
    relative=Path(path).resolve().relative_to(workspace).as_posix()
    file=workspace/'nbt_models/_migration/room-layout.json'
    if not file.is_file():return []
    stat=file.stat()
    return [workspace/key for key,target in path_map(file,stat.st_size,stat.st_mtime_ns)['aliases'].items()
            if target==relative and (workspace/key).resolve().is_relative_to(workspace/'nbt_models')]

def project_paths(source):
    source=Path(source).resolve()
    parent=source.parent
    while parent.name in INFRA:parent=parent.parent
    if parent.parent.name=='versions':return dict(workdir=parent.parent.parent,version=parent,prefix=None,width=2)
    match=VERSION.fullmatch(parent.name)
    if parent.name.startswith('v_model_') or parent.name.startswith(('版本_','v_')) and (parent/'room_description.json').is_file():return dict(workdir=parent.parent,version=parent,prefix=None,width=2)
    if match:return dict(workdir=parent.parent,version=parent,prefix=match[1],width=len(match[2]))
    if parent.name=='refined':return dict(workdir=parent.parent,version=parent,prefix='refined_v',width=1)
    return dict(workdir=parent,version=parent,prefix=None,width=2)
def reserve_version(source,workdir=None):
    info=project_paths(source);root=Path(workdir).resolve() if workdir else info['workdir']
    skill=Path(__file__).resolve().parents[2]
    if root==skill or skill in root.parents or root==Path(root.anchor):raise ValueError('请选择实际建筑工作文件夹')
    root.mkdir(parents=True,exist_ok=True)
    if info['prefix']:
        prefix=info['prefix'];numbers=[int(m.group(1)) for p in root.iterdir() if (m:=re.fullmatch(re.escape(prefix)+r'(\d+)',p.name))]
        number=max(numbers,default=0)+1
        while True:
            target=root/(prefix+str(number).zfill(info['width']))
            try:target.mkdir();return root,target
            except FileExistsError:number+=1
    base=root/'versions';base.mkdir(exist_ok=True)
    stamp=datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d_%H%M%S_web_edit')
    number=1
    while True:
        target=base/(stamp if number==1 else stamp+'_'+str(number))
        try:target.mkdir();return root,target
        except FileExistsError:number+=1
