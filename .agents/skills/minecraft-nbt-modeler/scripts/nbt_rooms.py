"""Workspace layout and stable room identity."""
import json
import re
from pathlib import Path
from nbt_catalog import catalog

GROUPS = '约束'
ROOMS = '房间'
ROOM_FILE = '房间.json'
RULE_FILE = '约束.json'
LAYOUT = '.layout.json'
UNASSIGNED = '未归组'
IDENTIFIER = re.compile(r'(?:constraint|room)-[a-f0-9]{32}\Z')
SHAPE_NAMES = set(catalog()['building_shapes'])


def read_small(file):
    if file.stat().st_size > 4 * 1024 * 1024:
        raise ValueError('项目资料超过 4 MiB')
    return json.loads(file.read_text(encoding='utf-8-sig'))


def enclosed(root, file):
    root, file = Path(root).resolve(), Path(file)
    resolved = file.resolve()
    if not resolved.is_relative_to(root) or resolved != file.absolute():
        raise ValueError('项目目录不可越界或使用链接')
    return resolved


def model_root(workspace):
    workspace = Path(workspace).resolve()
    return enclosed(workspace, workspace / 'nbt_models')


def project_folder(workspace, folder):
    base = model_root(workspace)
    path = enclosed(base, Path(workspace).resolve() / folder)
    if not path.is_dir():
        raise ValueError('找不到项目目录')
    return path


def relative(workspace, file):
    return Path(file).resolve().relative_to(Path(workspace).resolve()).as_posix()


def has_layout(project):
    marker = Path(project) / GROUPS / LAYOUT
    if not marker.is_file():
        return False
    value = read_small(enclosed(project, marker))
    if value != {'schema_version': 1}:
        raise ValueError('房间目录布局版本不受支持')
    return True


def init_layout(project):
    from nbt_project_batch import write
    project = Path(project).resolve()
    marker = enclosed(project, project / GROUPS / LAYOUT)
    if not has_layout(project):
        write(marker, {'schema_version': 1})


def empty_project(project):
    """Existing shape- or named-project trees keep their compatibility writer."""
    return not any(item.name == '项目约束.json' or item.is_dir() and not item.name.startswith(('.', '_'))
                   for item in Path(project).iterdir())


def layout_project(workspace, folder):
    """Resolve a physical room path or a logical legacy scope to a layout root."""
    base = model_root(workspace)
    from nbt_web_paths import workspace_path
    path = enclosed(base, workspace_path(workspace, folder))
    for candidate in (path, *path.parents):
        if not candidate.is_relative_to(base):
            break
        if has_layout(candidate):
            return candidate
    return None


def component_name(value, limit=28):
    clean = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', value).strip(' .')[:limit].rstrip(' .')
    return clean or '未命名'


def numbered_directory(root, identifier, name=None):
    if not isinstance(identifier, str) or not IDENTIFIER.fullmatch(identifier):
        raise ValueError('项目编号无效')
    root = Path(root)
    matches = [path for path in root.glob('*--' + identifier) if path.is_dir()] if root.is_dir() else []
    if len(matches) > 1:
        raise ValueError('项目目录存在重复编号')
    if matches:
        return enclosed(root, matches[0])
    return enclosed(root, root / (component_name(name) + '--' + identifier)) if name else None


def constraint_dirs(project):
    groups = enclosed(project, Path(project) / GROUPS)
    if groups.is_dir():
        for entry in sorted(groups.iterdir()):
            if entry.is_dir() and entry.name != UNASSIGNED and (entry / RULE_FILE).is_file():
                yield enclosed(groups, entry)


def room_dirs(project):
    groups = enclosed(project, Path(project) / GROUPS)
    if groups.is_dir():
        for group in sorted(groups.iterdir()):
            if group.is_dir():
                home = enclosed(groups, group / ROOMS)
                if home.is_dir():
                    for room in sorted(home.iterdir()):
                        if room.is_dir() and (room / ROOM_FILE).is_file():
                            yield enclosed(home, room)


def room_info(project, room):
    room = enclosed(project, room)
    item = read_small(enclosed(room, room / ROOM_FILE))
    if not isinstance(item, dict) or item.get('schema_version') != 1:
        raise ValueError('房间登记格式无效')
    rid, owner, refs = item.get('id'), item.get('owner_constraint_id'), item.get('constraint_ids')
    if not isinstance(rid, str) or not re.fullmatch(r'room-[a-f0-9]{32}', rid) or not room.name.endswith('--' + rid):
        raise ValueError('房间编号与目录不符')
    if not isinstance(item.get('name'), str) or not item['name'].strip():
        raise ValueError('房间名称无效')
    if not isinstance(refs, list) or len(refs) > 16 or any(not isinstance(ref, str) or not re.fullmatch(r'constraint-[a-f0-9]{32}', ref) for ref in refs):
        raise ValueError('房间约束引用无效')
    if len(set(refs)) != len(refs) or (owner is not None and owner not in refs):
        raise ValueError('房间归属与引用不一致')
    group = room.parent.parent
    if room.parent.name != ROOMS or group.parent != Path(project) / GROUPS or (
        owner is None and group.name != UNASSIGNED or owner is not None and not group.name.endswith('--' + owner)
    ):
        raise ValueError('房间归属与目录不一致')
    if item.get('shape') not in SHAPE_NAMES:
        raise ValueError('房间归档形状无效')
    return item


def enclosing_room(project, path):
    path = Path(path)
    for candidate in (path, *path.parents):
        if not candidate.is_relative_to(project):
            break
        if (candidate / ROOM_FILE).is_file():
            return candidate, room_info(project, candidate)
    return None


def owner_group(workspace, project, owner):
    from nbt_constraints import directory_records
    groups=Path(project)/GROUPS
    if owner is None:
        return enclosed(groups,groups/UNASSIGNED)
    group=next((directory for directory,record in directory_records(project)
                if record['snapshot']['id']==owner and not record.get('archived',False)),None)
    if group is None:
        raise ValueError('实体归属须为当前项目的可用约束')
    return group


def update_room(workspace, request, *, move=False):
    from nbt_constraint_registry import builtin_constraints
    from nbt_constraints import directory_records
    from nbt_project_batch import write
    from nbt_prompts import index_lock
    from nbt_web_paths import workspace_path

    folder=request.get('folder')
    if not isinstance(folder,str) or not folder:
        raise ValueError('请选择房间')
    workspace=Path(workspace).resolve()
    project=layout_project(workspace,folder)
    if project is None:raise ValueError('请选择新布局中的房间')
    with index_lock(workspace,project/GROUPS):
        room=workspace_path(workspace,folder)
        before=room_info(project,room)
        revision=before.get('revision',0)
        if type(request.get('revision')) is not int or request['revision']!=revision:
            raise ValueError('房间资料已更新，请刷新后再编辑')
        name=request.get('name',before['name'])
        refs=request.get('constraint_ids',before['constraint_ids'])
        if not isinstance(name,str) or not 1<=len(name.strip())<=120:
            raise ValueError('请填写有效的房间名称')
        if not isinstance(refs,list) or len(refs)>16 or any(not isinstance(ref,str) or not re.fullmatch(r'constraint-[a-f0-9]{32}',ref) for ref in refs):
            raise ValueError('房间引用无效')
        available=set(builtin_constraints())|{record['snapshot']['id'] for _,record in directory_records(project) if not record.get('archived')}
        if set(refs)-available-set(before['constraint_ids']):raise ValueError('包含未登记的房间引用')
        owner=request.get('owner_constraint_id') if move else before['owner_constraint_id']
        if owner is not None and owner not in refs:raise ValueError('请保留归属约束的引用')
        after=dict(before,name=name.strip(),constraint_ids=list(dict.fromkeys(refs)),owner_constraint_id=owner,revision=revision+1)
        if not move or owner==before['owner_constraint_id']:
            write(enclosed(room,room/ROOM_FILE),after)
            return dict(after,folder=relative(workspace,room))
        new=enclosed(project,owner_group(workspace,project,owner)/ROOMS/room.name)
        if new.exists():raise ValueError('目标房间目录已经存在')
        mapping_file=enclosed(model_root(workspace),model_root(workspace)/'_migration/room-layout.json')
        data=read_small(mapping_file) if mapping_file.is_file() else dict(schema_version=1,source_workspace=str(workspace),aliases={},files={})
        old_path,new_path=relative(workspace,room),relative(workspace,new)
        for key,path in list(data['aliases'].items()):
            if path==old_path or path.startswith(old_path+'/'):
                data['aliases'][key]=new_path+path[len(old_path):]
        data['aliases'][old_path]=new_path
        new.parent.mkdir(parents=True,exist_ok=True)
        room.rename(new)
        try:
            write(enclosed(new,new/ROOM_FILE),after)
            write(mapping_file,data)
        except Exception:
            write(enclosed(new,new/ROOM_FILE),before)
            new.rename(room)
            raise
        return dict(after,folder=new_path)


def register_room(workspace, request):
    from nbt_project_batch import write
    from nbt_prompts import index_lock

    project = project_folder(workspace, request.get('project', 'nbt_models'))
    project_key = relative(workspace, project)
    if not has_layout(project):
        if not empty_project(project):
            raise ValueError('旧项目请先在设置中预检并迁移副本')
        init_layout(project)
    session, name = request.get('session_id'), request.get('name')
    shape, owner, refs = request.get('shape'), request.get('owner_constraint_id'), request.get('constraint_ids', [])
    if not isinstance(session, str) or not re.fullmatch(r'[a-f0-9]{32}', session):
        raise ValueError('房间编号无效')
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 120 or shape not in SHAPE_NAMES:
        raise ValueError('请填写房间名称和归档形状')
    if not isinstance(refs, list) or len(refs) > 16 or any(not isinstance(ref, str) or not re.fullmatch(r'constraint-[a-f0-9]{32}', ref) for ref in refs):
        raise ValueError('房间约束引用无效')
    if len(set(refs)) != len(refs) or (owner is not None and owner not in refs):
        raise ValueError('请在已选约束中指定归属')
    rooms_root = project / GROUPS
    rid = 'room-' + session
    with index_lock(workspace, rooms_root):
        existing = [path for path in room_dirs(project) if path.name.endswith('--' + rid)]
        if len(existing) > 1:
            raise ValueError('存在重复的房间编号')
        if existing:
            return dict(room_info(project, existing[0]), folder=relative(workspace, existing[0]))
        group=owner_group(workspace,project,owner)
        home = enclosed(project, group / ROOMS / (component_name(name) + '--' + rid))
        record = dict(schema_version=1, revision=1, id=rid, name=name.strip(), shape=shape, owner_constraint_id=owner, constraint_ids=refs)
        write(home / ROOM_FILE, record)
        return dict(record, folder=relative(workspace, home), project=project_key)
