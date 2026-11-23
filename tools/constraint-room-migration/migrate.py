"""Inventory, copy and verify the constraint-room layout in a separate workspace."""
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sys
import tempfile

ENGINE = os.environ.get('NBTCREATOR_MIGRATION_ENGINE') or (
    Path(__file__).resolve().parents[2] / '.agents/skills/minecraft-nbt-modeler/scripts'
)
sys.path.insert(0, str(ENGINE))

from nbt_project.constraints import archive_directory_revision, dispatch, save_directory_rule
from nbt_detail_control import catalog
from nbt_project.queues import write
from nbt_project.prompts import read_prompt, scan
from nbt_project.rooms import GROUPS, ROOMS, ROOM_FILE, SHAPE_NAMES, UNASSIGNED, component_name, enclosed, init_layout, room_info
from nbt_project.web_paths import project_paths, workspace_path

STATE = Path('nbt_models/_migration/constraint-room-progress.json')
MAPPING = Path('nbt_models/_migration/room-layout.json')
ACTIVE = Path('nbt_models/_migration/active.json')
REBUILT_DIRS = {'.nbtcreator/cache', '.nbtcreator/runtimes'}
REBUILT_FILES = {'.nbtcreator/facade-manifest.json', '.nbtcreator/render-runtime.json',
                 'nbt_models/_workspaces/catalog_metadata.json', 'nbt_models/_workspaces/catalog_metadata_index.json',
                 'nbt_models/_workspaces/catalog_metadata_projects.json'}


def payload_hash(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def file_hash(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def linked(path):
    return path.is_symlink() or path.is_junction()


def roots(source, target):
    source, target = Path(source).resolve(), Path(target).resolve()
    if source.name.lower() == 'nbt_models':
        source = source.parent
    if not (source / 'nbt_models').is_dir():
        raise ValueError('请选择含有 nbt_models 的旧工作区')
    if target.is_relative_to(source) or source.is_relative_to(target):
        raise ValueError('目标工作区须位于旧工作区之外')
    return source, target


def inventory(source):
    records = []
    for category in ('nbt_models', '.nbtcreator'):
        parent = source / category
        if not parent.is_dir():
            continue
        if linked(parent):
            raise ValueError('工作区包含链接目录，请先整理')
        for directory, dirs, names in os.walk(parent):
            dirs[:]=sorted(name for name in dirs if Path(directory,name).relative_to(source).as_posix() not in REBUILT_DIRS)
            for name in [*dirs, *names]:
                if linked(Path(directory) / name):
                    raise ValueError('工作区包含链接，请先整理：' + str(Path(directory, name).relative_to(source)))
            for name in sorted(names):
                file = Path(directory) / name
                key = file.relative_to(source).as_posix()
                if key in REBUILT_FILES or key in (ACTIVE.as_posix(),STATE.as_posix(),MAPPING.as_posix()) or name.endswith('.lock'):
                    continue
                info = file.stat()
                records.append((key, info.st_size, info.st_mtime_ns))
    return records


def project_prefix(key):
    parts = PurePosixPath(key).parts
    return '/'.join(parts[:next((i for i, part in enumerate(parts[1:], 1)
                                if part in SHAPE_NAMES or part == 'bugged'), len(parts))])


def legacy_rules(source, files):
    records = {}
    for key, _, _ in files:
        if key == 'nbt_models/_workspaces/project_design/constraints.json':
            scope, project = '', 'nbt_models/_workspaces/project_design'
        elif key.startswith('nbt_models/') and key.endswith('/项目约束.json'):
            scope = str(PurePosixPath(key).parent)
            project = project_prefix(scope)
        else:
            continue
        for snapshot in dispatch(source, 'constraints-list', {'folder': scope})['items']:
            if snapshot['id'] in records and records[snapshot['id']]['snapshot'] != snapshot:
                raise ValueError('不同旧约束使用同一个编号，请先整理')
            archive=source/PurePosixPath(key).parent
            if scope:archive/='.project-constraints'
            archive=archive/'constraint-revisions'/snapshot['id']
            records[snapshot['id']] = dict(snapshot=snapshot, project=project, archive=archive)
    return records


def room_locations(source, listed):
    rooms = {}
    for item in listed['models']:
        file = Path(item['source'])
        old = project_paths(file)['workdir']
        if not old.is_relative_to(source / 'nbt_models'):
            continue
        # A loose model at a shape or project root forms its own room.
        shape = item.get('shape_group')
        prefix = 'nbt_models' + ('/' + item['project_key'] if item['project_key'] else '')
        if old == source / prefix or (old.name in SHAPE_NAMES | {'bugged'} and old.parent == source / prefix):
            old = file
        key = old.relative_to(source).as_posix()
        room=rooms.setdefault(key,dict(source=key,project=prefix,id='room-'+payload_hash(key)[:32],
                                      name=item.get('object_name') or item['name'],shape=shape if shape in SHAPE_NAMES else 'standalone',
                                      suggestions=[]))
        room['suggestions']=sorted(set(room['suggestions'])|set(item.get('constraint_ids',[])))
    return sorted(rooms.values(),key=lambda room:room['source'])


def matching_room(rooms, key):
    return next((room for room in rooms if key==room['source'] or key.startswith(room['source']+'/')),None)


def preview(source, target):
    source,target=roots(source,target)
    files=inventory(source)
    with tempfile.TemporaryDirectory(prefix='nbt-room-plan-') as scratch:
        listed=catalog(source,cache_path=Path(scratch)/'catalog.json',include_bugged=True,index_only=True)
    if listed.get('migration_in_progress'):
        raise ValueError('旧工作区仍有迁移任务在运行')
    if listed.get('layout_projects'):
        raise ValueError('这个工作区已经使用约束房间布局')
    rules=legacy_rules(source,files)
    rooms=room_locations(source,listed)
    ordered=sorted(rooms,key=lambda room:-len(room['source']))
    for item in scan(source)['items']:
        if item.get('kind')!='workbench':
            continue
        room=matching_room(ordered,item.get('source') or item['index'])
        if room is None:
            continue
        archived=read_prompt(source,item['index'],item['id'])
        room['suggestions']=sorted(set(room['suggestions']) | {
            constraint['id'] for constraint in archived['document'].get('constraints',[]) if constraint['id'] in rules
        })
    return dict(schema_version=1,source=str(source),target=str(target),fingerprint=payload_hash(files),
                count=len(files),bytes=sum(info[1] for info in files),rooms=rooms,
                constraints=[dict(id=item['snapshot']['id'],name=item['snapshot']['name'],project=item['project']) for item in rules.values()])


@contextmanager
def migration_lock(target):
    from nbt_project.prompts import index_lock
    directory=target/'nbt_models/_migration'
    directory.mkdir(parents=True,exist_ok=True)
    with index_lock(target,directory):
        yield


def apply(proposal, owners):
    source,target=roots(proposal['source'],proposal['target'])
    current=preview(source,target)
    if proposal.get('schema_version')!=1 or current['fingerprint']!=proposal.get('fingerprint'):
        raise ValueError('旧工作区有改动，请重新预检')
    files=inventory(source)
    constraints=legacy_rules(source,files)
    if not isinstance(owners,dict) or set(owners)-{room['id'] for room in current['rooms']}:
        raise ValueError('房间归属确认清单无效')
    choices={};aliases={}
    for room in current['rooms']:
        owner=owners.get(room['id'])
        if owner is not None and (not isinstance(owner,str) or owner not in constraints or constraints[owner]['project']!=room['project']):
            raise ValueError('房间归属必须选择同一项目的约束')
        group=component_name(constraints[owner]['snapshot']['name'])+'--'+owner if owner else UNASSIGNED
        choices[room['id']]=owner
        aliases[room['source']]=(PurePosixPath(room['project'])/GROUPS/group/ROOMS/(component_name(room['name'])+'--'+room['id'])).as_posix()
        if (source/room['source']).is_file():
            aliases[room['source']]+='/'+Path(room['source']).name
    job=payload_hash([current['source'],current['target'],current['fingerprint'],choices])
    if target.exists():
        if not (target/STATE).is_file() or read_json(target/STATE).get('job')!=job:
            raise ValueError('目标目录已存在，请选择用于本次迁移的独立目录')
    else:
        target.mkdir(parents=True)
        write(target/STATE,dict(job=job,status='copying'))
    with migration_lock(target):
        if read_json(target/STATE).get('status')=='complete':
            result=verify(target)
            write(target/ACTIVE,dict(status='complete'))
            return result
        write(target/ACTIVE,dict(status='writing'))
        completed={}
        for key,_,_ in files:
            old=enclosed(source,source/key)
            parts=key.split('/')
            dest=key
            for end in range(len(parts),1,-1):
                redirect=aliases.get('/'.join(parts[:end]))
                if redirect:
                    dest='/'.join([redirect,*parts[end:]])
                    break
            new=enclosed(target,target/dest)
            digest=file_hash(old)
            if new.exists() and file_hash(new)!=digest:
                raise ValueError('目标已有不同内容：'+dest)
            if not new.exists():
                new.parent.mkdir(parents=True,exist_ok=True)
                provisional=new.with_name('.migration-'+payload_hash(dest)[:16]+'.tmp')
                shutil.copy2(old,provisional)
                if file_hash(provisional)!=digest:
                    raise ValueError('复制期间源文件有变化：'+key)
                provisional.replace(new)
            completed[dest]=digest
        projects={room['project'] for room in current['rooms']}|{item['project'] for item in constraints.values()}
        if not projects:projects={'nbt_models'}
        for project in sorted(projects):
            init_layout(enclosed(target,target/project))
        ordered=sorted(current['rooms'],key=lambda room:-len(room['source']))
        for entry in constraints.values():
            snapshot=entry['snapshot'];room=matching_room(ordered,snapshot.get('folder',''))
            group=save_directory_rule(target/entry['project'],snapshot,scoped_room=room['id'] if room else None)
            for revision_file in entry['archive'].glob('*.json'):
                revision=read_json(enclosed(source,revision_file))
                if revision.get('id')!=snapshot['id']:raise ValueError('旧约束的修订编号与目录不符')
                archive_directory_revision(group,revision)
        for room in current['rooms']:
            location=target/aliases[room['source']]
            if (source/room['source']).is_file():location=location.parent
            owner=choices[room['id']]
            refs=list(dict.fromkeys(([owner] if owner else [])+room['suggestions']))[:16]
            write(location/ROOM_FILE,dict(schema_version=1,revision=1,id=room['id'],shape=room['shape'],name=room['name'],
                                         owner_constraint_id=owner,constraint_ids=refs))
        if payload_hash(inventory(source))!=current['fingerprint']:
            raise ValueError('复制期间旧工作区有改动，请核对后重新预检')
        write(target/MAPPING,dict(schema_version=1,source_workspace=str(source),aliases=aliases,files=completed,
                                  rooms={room['source']:{'id':room['id'],'project':room['project']} for room in current['rooms']}))
        verified=verify(target)
        write(target/STATE,dict(job=job,status='complete'))
        write(target/ACTIVE,dict(status='complete'))
        return verified


def verify(target):
    target=Path(target).resolve()
    mapping=read_json(enclosed(target,target/MAPPING))
    for key,expected in mapping['files'].items():
        if file_hash(enclosed(target,workspace_path(target,key)))!=expected:
            raise ValueError('迁移副本的文件校验失败：'+key)
    for key,expected in mapping.get('rooms',{}).items():
        location=workspace_path(target,key)
        if location.is_file():location=location.parent
        if room_info(target/expected['project'],location)['id']!=expected['id']:
            raise ValueError('迁移副本的房间编号校验失败：'+key)
    return dict(passed=True,target=str(target),files=len(mapping['files']),rooms=len(mapping.get('rooms',mapping['aliases'])),
                mapping=MAPPING.as_posix())


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['plan','apply','verify'])
    parser.add_argument('--source')
    parser.add_argument('--target')
    parser.add_argument('--request',type=Path)
    args=parser.parse_args()
    try:
        if args.action=='plan':result=preview(args.source,args.target)
        elif args.action=='verify':result=verify(args.target)
        else:
            payload=read_json(args.request)
            result=apply(payload['plan'],payload.get('owners',{}))
        print(json.dumps(result,ensure_ascii=True))
    except (ValueError,OSError,KeyError,TypeError) as error:
        print(str(error),file=sys.stderr);return 1
    return 0


if __name__=='__main__':sys.exit(main())
