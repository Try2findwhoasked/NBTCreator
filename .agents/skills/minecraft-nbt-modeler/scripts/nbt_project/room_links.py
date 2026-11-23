"""Explicit associations for legacy rooms that have no room metadata."""

from pathlib import Path, PurePosixPath

from nbt_project.constraints import valid_constraint_id
from nbt_project.history import now
from nbt_project.queues import write
from nbt_project.prompts import index_lock
from nbt_project.rooms import enclosed, read_small
from nbt_project.web_paths import workspace_path


LINKS_FILE = 'nbt_models/_workspaces/room-constraint-links.json'


def link_file(workspace):
    return enclosed(workspace / 'nbt_models', workspace / LINKS_FILE)


def read_links(workspace):
    file = link_file(workspace)
    if not file.is_file():
        return {}
    data = read_small(file)
    if not isinstance(data, dict) or data.get('schema_version') != 1 or not isinstance(data.get('items'), dict):
        raise ValueError('旧房间约束关联格式无效')
    for key, entry in data['items'].items():
        parts = PurePosixPath(key).parts
        if (len(parts) < 2 or parts[0] != 'nbt_models' or '..' in parts or '\\' in key or ':' in key
                or not isinstance(entry, dict) or not valid_constraint_id(entry.get('constraint_id'))):
            raise ValueError('旧房间约束关联记录无效')
    return data['items']


def add_room_links(workspace, request):
    from nbt_detail_control import catalog

    workspace = Path(workspace).resolve()
    bindings = request.get('items')
    identifier = request.get('constraint_id')
    if (set(request) - {'action', 'items', 'constraint_id'} or not valid_constraint_id(identifier)
            or not isinstance(bindings, list) or not 1 <= len(bindings) <= 1000):
        raise ValueError('请选择 1～1000 间旧房间与一条已登记约束')
    file = link_file(workspace)
    file.parent.mkdir(parents=True, exist_ok=True)
    with index_lock(workspace, file.parent):
        indexed = catalog(workspace, include_bugged=True, index_only=True)
        rule = next((item for item in indexed.get('constraint_groups', []) if item['id'] == identifier and not item['archived']), None)
        if rule is None:
            raise ValueError('所选约束已失效，请刷新建筑库')
        models = {Path(item['source']): item for item in indexed['models']}
        existing = read_links(workspace)
        rooms = set()
        for binding in bindings:
            if (not isinstance(binding, dict) or set(binding) != {'source','file_size','modified_ns'}
                    or not isinstance(binding['source'], str) or not binding['source']):
                raise ValueError('选中的房间版本无效')
            path = workspace_path(workspace, binding['source'])
            item = models.get(path)
            if not item or binding['file_size'] != item.get('file_size') or binding['modified_ns'] != item.get('modified_ns'):
                raise ValueError('选中的建筑版本已有变化，请刷新后重新选择')
            key = item.get('legacy_room_key')
            if not key:
                raise ValueError('无法从所选版本确认旧房间目录')
            if rule['project_key'] not in (None, item['project_key']):
                raise ValueError('所选约束与房间的项目范围不一致')
            if rule['folder'] and not PurePosixPath(key).is_relative_to(PurePosixPath(rule['folder'])):
                raise ValueError('所选约束与房间的目录范围不一致')
            if item.get('constraint_ids') and not (existing.get(key, {}).get('constraint_id') == identifier and set(item['constraint_ids']) == {identifier}):
                raise ValueError('选中的旧房间已有规则引用，请刷新后重新选择')
            rooms.add(key)
        changed = [key for key in sorted(rooms) if existing.get(key, {}).get('constraint_id') != identifier]
        if changed:
            for key in changed:
                existing[key] = dict(constraint_id=identifier, updated_at=now())
            write(file, dict(schema_version=1, items=existing))
        return dict(rooms=len(rooms), changed=len(changed))
