"""Workspace connections and citation checks for local architecture libraries."""

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
from urllib.parse import urlsplit, urlunsplit

import nbt_knowledge.architecture_books as books
from nbt_assets.libraries import atomic


MAX_CONNECTIONS = 16
ID = re.compile(r'[a-f0-9]{32}')
SHA = re.compile(r'[a-f0-9]{64}')
ERRORS = (OSError, ValueError, KeyError, TypeError, sqlite3.Error)


def inside(root, path):
    result = path.resolve()
    if not result.is_relative_to(root):
        raise ValueError('书库缓存路径越过工作区')
    return result


def cache(workspace):
    return inside(workspace, workspace/'.nbtcreator/retrieval/libraries')


@contextmanager
def write_lock(root):
    root.mkdir(parents=True, exist_ok=True)
    with inside(root, root/'.write.lock').open('a+b') as stream:
        if stream.seek(0, 2) == 0:
            stream.write(b'0')
            stream.flush()
        stream.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise ValueError('另一项书库更新正在进行，请稍后重试') from error
        yield


def directory(workspace, value):
    if not isinstance(value, str) or not value.strip() or len(value) > 1024 or value.startswith(('//', '\\\\')) or '://' in value:
        raise ValueError('请指定本地书库目录')
    path = Path(value)
    if not path.is_absolute() and (path.drive or '..' in path.parts or path.anchor):
        raise ValueError('相对书库路径必须位于当前工作区内')
    resolved = (workspace/path).resolve()
    if (not path.is_absolute() and not resolved.is_relative_to(workspace)) or str(resolved).startswith('\\\\'):
        raise ValueError('书库路径越过工作区或解析为网络目录')
    return resolved


def registrations(workspace):
    root = cache(workspace)
    file = inside(root, root/'connections.json')
    if not file.exists():
        return {}
    if file.stat().st_size > 64*1024:
        raise ValueError('书库连接配置过大')
    data = json.loads(file.read_text(encoding='utf8'))
    if not isinstance(data, dict) or data.get('schema_version') != 1 or not isinstance(data.get('libraries'), list) or len(data['libraries']) > MAX_CONNECTIONS:
        raise ValueError('书库连接配置无效')
    result = {}
    for item in data['libraries']:
        identifier = item.get('id') if isinstance(item, dict) else None
        if (not isinstance(identifier, str) or not ID.fullmatch(identifier) or identifier in result
            or not isinstance(item.get('path'), str) or not isinstance(item.get('name'), str)
            or not isinstance(item.get('workflows'), list) or len(item['workflows']) > 20
            or any(not isinstance(flow, str) for flow in item['workflows'])):
            raise ValueError('书库连接记录无效')
        result[identifier] = item
    return result


def index_path(workspace, identifier):
    root = cache(workspace)
    return inside(root, root/(identifier+'.sqlite'))


def status(workspace, item, flow):
    result = {key: item[key] for key in ('id', 'name', 'workflows')}
    result['enabled'] = flow in item['workflows']
    try:
        location = directory(workspace, item['path'])
        entries, receipt = books.manifest(location)
        current = index_path(workspace, item['id'])
        result.update(documents=len(entries), manifest_sha256=receipt)
        tutorial = next(iter(entries.values())).get('tutorial')
        if tutorial:
            result.update({key: tutorial[key] for key in ('package_kind', 'package_id', 'package_version')})
        if not current.is_file():
            result.update(status='not_indexed', message='书库尚未建立索引')
        elif books.index_manifest(current, tutorial=bool(tutorial)) != receipt:
            result.update(status='stale', message='书库清单已变化，请更新索引')
        else:
            result['status'] = 'ready'
    except (OSError, ValueError, KeyError, TypeError):
        result.update(status='unavailable', message='无法读取书库目录或清单')
    except sqlite3.Error:
        result.update(status='stale', message='书库索引无法读取，请更新索引')
    return result


def manage(workspace, flow, request):
    action = request.get('action', 'list')
    if action == 'list':
        return dict(libraries=[status(workspace, item, flow) for item in registrations(workspace).values()])
    if action not in ('add', 'build', 'enable', 'remove'):
        raise ValueError('书库操作须为 list、add、build、enable 或 remove')
    root = cache(workspace)
    with write_lock(root):
        items = registrations(workspace)
        indexed = None
        if action == 'add':
            location = directory(workspace, request.get('path'))
            stored = location.relative_to(workspace).as_posix() if location.is_relative_to(workspace) else str(location)
            identifier = hashlib.sha256(os.path.normcase(stored).encode('utf8')).hexdigest()[:32]
            if identifier not in items and len(items) >= MAX_CONNECTIONS:
                raise ValueError('每个工作区最多连接16个书库')
            name = request.get('name', location.name)
            if not isinstance(name, str) or not name.strip() or len(name) > 150:
                raise ValueError('书库名称须为1～150字')
            item = items.get(identifier) or dict(id=identifier, path=stored, name=name.strip(), workflows=[])
            index = index_path(workspace, identifier)
            _, receipt = books.manifest(location)
            if identifier not in items or not index.exists() or status(workspace, item, flow)['status'] != 'ready':
                indexed = books.build(location, index)
                if indexed['manifest_sha256'] != receipt:
                    raise ValueError('建索引时书库清单已变化，请重试')
            items[identifier] = item
            if flow not in item['workflows']:
                item['workflows'].append(flow)
        else:
            identifier = request.get('id')
            if not isinstance(identifier, str) or identifier not in items:
                raise ValueError('请选择已连接的书库')
            item = items[identifier]
            if action == 'build':
                location = directory(workspace, item['path'])
                indexed = books.build(location, index_path(workspace, identifier))
            elif action == 'remove':
                del items[identifier]
            else:
                enabled = request.get('enabled')
                if type(enabled) is not bool:
                    raise ValueError('请明确启用或停用此工作流的书库')
                item['workflows'] = [key for key in item['workflows'] if key != flow]
                if enabled:
                    item['workflows'].append(flow)
        if action != 'build':
            raw = json.dumps(dict(schema_version=1, libraries=list(items.values())), ensure_ascii=False, indent=2)
            atomic(inside(root, root/'connections.json'), (raw+'\n').encode('utf8'))
    if action == 'remove':
        return dict(id=identifier, removed=True)
    result = status(workspace, item, flow)
    if indexed:
        result['passages'] = indexed['passages']
    return result


def filters(request):
    parsed = request.get('filters', {})
    if not isinstance(parsed, dict) or set(parsed)-{'style', 'region', 'year'}:
        raise ValueError('书库筛选仅支持 style、region 和 year')
    for key in ('style', 'region'):
        if key in parsed and (not isinstance(parsed[key], str) or not 1 <= len(parsed[key].strip()) <= 80):
            raise ValueError('建筑风格或地区筛选须为1～80字')
    if 'year' in parsed:
        year = parsed['year']
        if not isinstance(year, list) or len(year) != 2 or any(type(n) is not int or not -9999 <= n <= 9999 for n in year) or year[0] > year[1]:
            raise ValueError('出版年代筛选须为 [起始年, 结束年]')
    return {key: value.strip() if isinstance(value, str) else value for key,value in parsed.items()}


def bibliography(book):
    data = {key: value for key,value in books.describe(book).items() if value and key not in ('title','sha256','source')}
    original = urlsplit(book['source']) if book['source'] else None
    if original and original.scheme in ('https','http') and original.hostname and original.username is None and original.password is None:
        data['source_url'] = urlunsplit(original._replace(query=''))
    return dict(data, library_id=book['library_id'], **({'version':book['version']} if book['version'] else {}))


def citation(item, document_id, book, receipt, hit):
    first, last = hit['line_start'], hit['line_end']
    return dict(
        id=f'knowledge:{document_id}:{receipt}:{book["sha256"]}:{first}:{last}',
        kind='knowledge', document_id=document_id, label=book['title'], heading=hit['heading'],
        sha256=book['sha256'], manifest_sha256=receipt, locator='library:'+item['name']+'/'+book['file'],
        line_start=first, line_end=last, text=hit['text'], clipped=hit['clipped'],
        passage_sha256=hashlib.sha256(hit['text'].encode('utf8')).hexdigest(),
        reference_type='architecture_library', library_name=item['name'],
        bibliography=bibliography(book), reason='已启用书库中的建筑术语或原文匹配',
        **({'tutorial': book['tutorial']} if 'tutorial' in book else {}),
    )


def search(workspace, flow, query, limit, request):
    criteria = filters(request)
    selected = request.get('library_id')
    items = registrations(workspace)
    if selected is not None and (not isinstance(selected, str) or selected not in items or flow not in items[selected]['workflows']):
        raise ValueError('请选择当前工作流已启用的书库')
    groups, errors = [], []
    for identifier, item in items.items():
        if flow not in item['workflows'] or selected is not None and identifier != selected:
            continue
        try:
            location = directory(workspace, item['path'])
            index = index_path(workspace, identifier)
            entries, receipt = books.manifest(location)
            matched = books.search(location, query.strip()[:300], limit=min(limit*2, 20), index=index, catalog=(entries,receipt), **criteria)
            groups.append([citation(item, f'library:{identifier}:{hit["book"]}', entries[hit['book']], receipt, hit)
                           for hit in matched['hits']])
            errors.extend(dict(id=identifier, name=item['name'], document_id=f'library:{identifier}:{document}',
                               message=message) for document, message in matched.get('document_errors', {}).items())
        except ERRORS:
            errors.append(dict(id=identifier, name=item['name'], message='书库或索引已变化、不可用，请检查来源或更新索引'))
    return groups, errors


def document(workspace, flow, document_id, receipt, sha256, items=None):
    parts = document_id.split(':') if isinstance(document_id, str) else []
    if len(parts) != 3 or parts[0] != 'library' or not ID.fullmatch(parts[1]) or not books.IDENTIFIER.fullmatch(parts[2]):
        raise ValueError('书库文档编号无效')
    if not isinstance(receipt, str) or not SHA.fullmatch(receipt) or not isinstance(sha256, str) or not SHA.fullmatch(sha256):
        raise ValueError('书库引用需要清单与原文哈希')
    items = registrations(workspace) if items is None else items
    item = items.get(parts[1])
    if not item or flow not in item['workflows']:
        raise ValueError('书库已移除或在本工作流停用，请重新检索')
    try:
        location = directory(workspace, item['path'])
        entries, live = books.manifest(location)
        book = entries.get(parts[2]) or (entries.get(int(parts[2])) if parts[2].isascii() and parts[2].isdigit() else None)
        if live != receipt or not book or book['sha256'] != sha256:
            raise ValueError('书库清单或原文已变化')
        _, text = books.source(location, book)
    except ERRORS as error:
        raise ValueError('书库原文已变化或不可用，请重新检索') from error
    return item, book, text


def verify_citations(workspace, flow, citations):
    documents = {}
    items = registrations(workspace)
    for selected in citations:
        key = (selected['document_id'], selected['manifest_sha256'], selected['sha256'])
        if key not in documents:
            item, book, text = document(workspace, flow, *key, items=items)
            documents[key] = (item, book, text)
        item, book, text = documents[key]
        if 'tutorial' in book and 'tutorial' not in selected:
            # Accept previously stored citations produced before tutorial metadata was projected.
            book = {field: value for field, value in book.items() if field != 'tutorial'}
        current = next((citation(item,key[0],book,key[1],dict(line_start=first,line_end=last,
                        heading=heading,text=passage,clipped=clipped))
                        for _,first,last,heading,passage,clipped in books.sections(book,text)
                        if first==selected['line_start'] and last==selected['line_end']),None)
        if current != selected:
            raise ValueError('书库片段或出处已变化，请重新检索')
