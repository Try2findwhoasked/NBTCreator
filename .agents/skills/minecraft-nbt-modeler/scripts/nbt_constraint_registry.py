"""Read-only view of built-in and workspace constraint snapshots."""

import copy
import json
from functools import lru_cache
from pathlib import Path


PRESETS = Path(__file__).resolve().parents[1] / 'constraint-presets.json'
SAODG = PRESETS.parent / 'constraint-extensions/saodg.json'


@lru_cache(maxsize=2)
def read_presets(file, size, modified, changed):
    from nbt_constraints import checksum, validate_snapshot

    data = json.loads(file.read_text(encoding='utf-8'))
    if data.get('schema_version') != 1 or not isinstance(data.get('items'), list):
        raise ValueError('内置约束注册文件格式无效')
    items = {}
    for definition in data['items']:
        snapshot = dict(definition, schema_version=1)
        snapshot['sha256'] = checksum(snapshot)
        validate_snapshot(snapshot)
        if snapshot['id'] in items:
            raise ValueError('内置约束编号重复')
        items[snapshot['id']] = snapshot
    return items


def builtin_constraints():
    result = {}
    for file in (PRESETS, SAODG):
        info = file.stat()
        items = read_presets(file, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
        if result.keys() & items.keys():
            raise ValueError('内置约束编号重复')
        result.update(items)
    return result


def query(workspace, request):
    from nbt_constraints import dispatch, list_result, valid_constraint_id

    folders = request.get('folders', [])
    if (set(request) - {'folders', 'summary', 'id'} or type(request.get('summary', False)) is not bool
            or 'id' in request and not valid_constraint_id(request['id'])
            or not isinstance(folders, list) or len(folders) > 32 or any(not isinstance(folder, str) for folder in folders)):
        raise ValueError('约束注册器查询无效')
    options = {key: request[key] for key in ('summary', 'id') if key in request}
    builtins = builtin_constraints()
    items = list_result({'items': list(builtins.values())}, options)['items']
    groups = [dict(scope=None, source='builtin', items=copy.deepcopy(items))]
    if request.get('id') in builtins:
        return {'groups': groups}
    for folder in dict.fromkeys(folders):
        try:
            result = dispatch(workspace, 'constraints-list', dict(options, folder=folder, include_references=True))
            groups.append(dict(scope=folder, source='workspace', items=result['items']))
        except (OSError, ValueError, KeyError, TypeError) as error:
            groups.append(dict(scope=folder, source='workspace', items=[], error=str(error)))
    return {'groups': groups}
