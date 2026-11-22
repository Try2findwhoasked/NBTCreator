"""Versioned data-only asset libraries. Network access is explicit, never on listing."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeoutError
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import time
from urllib.parse import quote, urljoin, urlsplit, urlunsplit
from urllib.request import build_opener, HTTPRedirectHandler, Request
import uuid

FORMAT = 'nbtcreator.asset-library'
REGISTRY = 'nbtcreator.asset-registry'
BUNDLED = Path(__file__).resolve().parents[1] / 'assets/extension-library'
MAX_MANIFEST = 2 * 1024 * 1024
MAX_ASSET = 8 * 1024 * 1024
MAX_TOTAL = 32 * 1024 * 1024
LIMIT = 512
DOWNLOAD_WORKERS = 4
APP_VERSION = (4, 3, 2)
ACTIONS = ('list', 'browse', 'discover', 'add', 'refresh', 'enable', 'remove', 'rollback',
           'read', 'import', 'thumbnail', 'preview', 'resolve', 'place', 'copy')


class LibraryError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.details = dict(code=code)


def fail(code, message):
    raise LibraryError(code, message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def encode(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n').encode('utf8')


def decode(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result: fail('INVALID_JSON', 'JSON 含重复字段')
            result[key] = value
        return result
    try:
        return json.loads(raw.decode('utf-8-sig'), object_pairs_hook=pairs,
                          parse_constant=lambda _: fail('INVALID_JSON', 'JSON 不接受非有限数值'))
    except (UnicodeError, ValueError, RecursionError):
        fail('INVALID_JSON', '无法读取资产 JSON')


def obj(value, required, optional=()):
    if not isinstance(value, dict) or set(required) - set(value) or set(value) - set(required) - set(optional):
        fail('INVALID_SCHEMA', '资产字段缺失或含未支持字段')


def text(value, limit=120):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        fail('INVALID_SCHEMA', '资产文字为空或过长')
    return value


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-z0-9][a-z0-9._-]{0,95}', value):
        fail('INVALID_ID', '库或资产编号须为小写英文、数字、点、横线或下划线')
    return value


def sha(value):
    if not isinstance(value, str) or not re.fullmatch('[a-f0-9]{64}', value):
        fail('INVALID_HASH', '须提供完整 SHA256')
    return value


def version(value):
    if not isinstance(value, str) or not re.fullmatch(r'(0|[1-9][0-9]{0,5})\.(0|[1-9][0-9]{0,5})\.(0|[1-9][0-9]{0,5})', value):
        fail('INVALID_VERSION', '版本须为不带前后缀的三段数字')
    return tuple(map(int, value.split('.')))


def relative(value):
    if not isinstance(value, str) or len(value) > 240 or not value.endswith('.json') or any(c in value for c in ('\\', ':', '%', '?', '#', '\x00')):
        fail('UNSAFE_PATH', '资产路径须为相对 JSON 路径')
    parts = value.split('/')
    if any(part in ('', '.', '..') or part.endswith((' ', '.')) for part in parts) or PurePosixPath(value).is_absolute():
        fail('UNSAFE_PATH', '资产路径不能越过库目录')
    if any(re.fullmatch(r'(?i:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?', part) or any(ord(c) < 32 or c in '<>"|*' for c in part) for part in parts):
        fail('UNSAFE_PATH', '资产路径含 Windows 不支持的名称')
    return value


def remote(location):
    return isinstance(location, str) and location.startswith(('https://', 'http://'))


def checked_url(location):
    try:
        parsed = urlsplit(location)
        port = parsed.port
    except ValueError:
        fail('UNSAFE_URL', '远端地址无效')
    if parsed.scheme not in ('https', 'http') or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        fail('UNSAFE_URL', '远端地址须为不含凭据、查询和片段的 HTTP(S) 地址')
    if parsed.scheme == 'http' and parsed.hostname not in ('localhost', '127.0.0.1', '::1'):
        fail('INSECURE_TRANSPORT', '远端库须使用 HTTPS；HTTP 仅用于本机服务')
    if port is not None and not 1 <= port <= 65535:
        fail('UNSAFE_URL', '远端端口无效')
    return parsed


def origin(location):
    p = checked_url(location)
    return p.scheme, p.hostname, p.port or (443 if p.scheme == 'https' else 80)


def resolved_path(value):
    """Resolve links before comparing, normalizing Windows path aliases.

    Windows can return an extended-length prefix when another downloader creates
    a missing parent during resolve(). It names the same resolved file, but
    pathlib treats its drive as different from an ordinary drive-letter path.
    """
    path = Path(value).resolve()
    if os.name == 'nt':
        raw = str(path)
        if raw.startswith('\\\\?\\UNC\\'): return Path('\\\\' + raw[8:])
        if raw.startswith('\\\\?\\') and re.match(r'[A-Za-z]:\\', raw[4:]): return Path(raw[4:])
    return path


class Redirects(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        if origin(newurl) != origin(request.full_url):
            fail('UNSAFE_REDIRECT', '库重定向须保持同源；请使用最终地址连接')
        return super().redirect_request(request, fp, code, msg, headers, newurl)


def location(value):
    text(value, 2048)
    if remote(value):
        parsed = checked_url(value)
        return urlunsplit((parsed.scheme, parsed.netloc, quote(parsed.path, safe="/%:@!$&'()*+,;=-._~"), '', ''))
    p = Path(value)
    if not p.is_absolute() or value.startswith(('\\\\', '//')):
        fail('UNSAFE_PATH', '本地库须为绝对目录或清单文件路径')
    p = resolved_path(p)
    if p.is_dir(): p = p / 'library.json'
    return str(p)


def child_location(parent, name):
    relative(name)
    if remote(parent):
        value = urljoin(parent, quote(name, safe='/'))
        if origin(value) != origin(parent): fail('UNSAFE_PATH', '资产地址越界')
        return value
    root = resolved_path(Path(parent).parent)
    value = resolved_path(root / name)
    if not value.is_relative_to(root): fail('UNSAFE_PATH', '资产符号链接越过库目录')
    return str(value)


def fetch(source, limit, final_location=None, deadline=None):
    try:
        if remote(source):
            checked_url(source)
            remaining = deadline - time.monotonic() if deadline is not None else 60
            if remaining <= 0: fail('TIME_LIMIT', '库刷新超过60秒，请稍后重试')
            request = Request(source, headers={'User-Agent': 'NBTCreator-AssetLibrary/1', 'Accept-Encoding': 'identity'})
            with build_opener(Redirects()).open(request, timeout=min(10, remaining)) as stream:
                if final_location is not None: final_location.append(stream.geturl())
                if stream.headers.get('Content-Encoding', 'identity') != 'identity':
                    fail('UNSUPPORTED_ENCODING', '库服务器须提供未压缩的 JSON')
                if stream.headers.get('Content-Length') and int(stream.headers['Content-Length']) > limit:
                    fail('SIZE_LIMIT', '资产数据超过大小限制')
                chunks = []; size = 0; read_deadline = time.monotonic() + 60
                if deadline is not None: read_deadline = min(read_deadline, deadline)
                while size <= limit:
                    if time.monotonic() > read_deadline: fail('TIME_LIMIT', '库文件读取超过60秒')
                    chunk = stream.read1(min(65536, limit + 1 - size))
                    if not chunk: break
                    chunks.append(chunk); size += len(chunk)
                raw = b''.join(chunks)
        else:
            if final_location is not None: final_location.append(source)
            with Path(source).open('rb') as stream: raw = stream.read(limit + 1)
    except LibraryError:
        raise
    except (OSError, ValueError):
        if deadline is not None and time.monotonic() >= deadline: fail('TIME_LIMIT', '库刷新超过60秒，请稍后重试')
        # Do not expose URLs, proxy errors or server responses (which may contain secrets).
        fail('SOURCE_UNAVAILABLE', '库来源不可用，请检查地址、网络或文件权限；已缓存版本仍保留')
    if len(raw) > limit: fail('SIZE_LIMIT', '资产数据超过大小限制')
    return raw


def header(data, kind):
    if not isinstance(data, dict) or type(data.get('schema_version')) is not int or data['schema_version'] != 1 or data.get('kind') != kind:
        fail('UNSUPPORTED_SCHEMA', '不支持的拓展清单类型或版本')


def manifest(raw):
    data = decode(raw)
    header(data, FORMAT)
    obj(data, ('schema_version', 'kind', 'id', 'name', 'version', 'license', 'assets'), ('description', 'compatibility'))
    identifier(data['id']); text(data['name']); text(data['license']); version(data['version'])
    if 'description' in data: text(data['description'], 2000)
    compatibility = data.get('compatibility', {})
    obj(compatibility, (), ('minecraft', 'app_min', 'app_max'))
    if compatibility.get('minecraft', '1.20.1') != '1.20.1': fail('INCOMPATIBLE', '库面向的 Minecraft 版本不兼容')
    if 'app_min' in compatibility and APP_VERSION < version(compatibility['app_min']): fail('INCOMPATIBLE', '请升级应用后再连接该库')
    if 'app_max' in compatibility and APP_VERSION > version(compatibility['app_max']): fail('INCOMPATIBLE', '库不支持当前应用版本')
    assets = data['assets']
    if not isinstance(assets, list) or not 1 <= len(assets) <= LIMIT: fail('SIZE_LIMIT', '每库须包含1～512项资产')
    seen = {}; paths = set(); total = 0
    for entry in assets:
        obj(entry, ('id', 'name', 'type', 'path', 'sha256', 'bytes'), ('category', 'tags', 'requires', 'status'))
        key = identifier(entry['id']); text(entry['name'], 80); relative(entry['path']); sha(entry['sha256'])
        if entry['type'] not in ('parametric_recipe', 'component'): fail('UNSUPPORTED_ASSET', '当前仅支持参数化配方和构件 JSON')
        if key in seen or entry['path'].casefold() in paths: fail('DUPLICATE_ID', '库含重复资产编号或文件路径')
        if type(entry['bytes']) is not int or not 1 <= entry['bytes'] <= MAX_ASSET: fail('SIZE_LIMIT', '单项资产须在8MiB以内')
        if 'category' in entry: text(entry['category'], 80)
        if 'status' in entry and entry['status'] not in ('draft', 'stable', 'recommended', 'deprecated'): fail('INVALID_SCHEMA', '资产状态无效')
        tags = entry.get('tags', [])
        if not isinstance(tags, list) or len(tags) > 16: fail('INVALID_SCHEMA', '资产最多16个标签')
        for tag in tags: text(tag, 32)
        deps = entry.get('requires', [])
        if not isinstance(deps, list) or len(deps) > 32 or len(set(map(str, deps))) != len(deps): fail('INVALID_DEPENDENCY', '资产依赖须为无重复的库内编号列表')
        for dep in deps: identifier(dep)
        seen[key] = entry; paths.add(entry['path'].casefold()); total += entry['bytes']
    if total > MAX_TOTAL: fail('SIZE_LIMIT', '每库资产总量最多32MiB')
    pending = set(seen); done = set()
    while pending:
        ready = {key for key in pending if set(seen[key].get('requires', [])) <= done}
        if not ready: fail('INVALID_DEPENDENCY', '资产依赖缺失或存在循环；跨库依赖暂不支持')
        pending -= ready; done |= ready
    return data


def payload(entry, raw):
    if len(raw) != entry['bytes'] or digest(raw) != entry['sha256']: fail('HASH_MISMATCH', '资产大小或 SHA256 与清单不一致')
    data = decode(raw)
    if entry['type'] == 'component':
        from nbt_components import validate
        return validate(data)
    obj(data, ('schema_version', 'kind', 'arguments'), ('controls',))
    header(data, 'nbtcreator.parametric-recipe')
    from nbt_structure_agent import _schema, definitions
    _schema(data['arguments'], definitions()['parametric_compile']['parameters'], '拓展配方')
    if 'sample' in data['arguments'].get('ornament', {}):
        fail('UNSUPPORTED_REFERENCE', '拓展配方须自包含；本地图源纹样请先编译为构件再发布')
    controls = data.get('controls', {})
    obj(controls, (), ('style', 'spacing'))
    if any(type(value) is not bool for value in controls.values()): fail('INVALID_SCHEMA', '配方控件须为布尔值')
    return data


def cache_root(workspace):
    workspace = resolved_path(workspace)
    root = resolved_path(workspace / '.nbtcreator/asset-libraries')
    if not root.is_relative_to(workspace): fail('UNSAFE_PATH', '拓展缓存不能越过工作区')
    return root


def atomic(file, raw):
    file.parent.mkdir(parents=True, exist_ok=True)
    temporary = file.with_name('.' + file.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with temporary.open('xb') as stream:
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, file)
    finally:
        temporary.unlink(missing_ok=True)


def state(workspace):
    file = cache_root(workspace) / 'state.json'
    if not file.exists(): return dict(schema_version=1, sources=[])
    value = decode(fetch(str(file), MAX_MANIFEST))
    obj(value, ('schema_version', 'sources'))
    if type(value['schema_version']) is not int or value['schema_version'] != 1 or not isinstance(value['sources'], list) or len(value['sources']) > 32: fail('INVALID_STATE', '拓展库配置损坏')
    seen = set()
    for entry in value['sources']:
        obj(entry, ('id', 'source', 'enabled', 'active', 'history', 'library_id', 'name', 'version', 'count'), ('error', 'release_hashes'))
        if not isinstance(entry['id'], str) or not re.fullmatch('[a-f0-9]{32}', entry['id']) or entry['id'] in seen or type(entry['enabled']) is not bool:
            fail('INVALID_STATE', '拓展库连接配置损坏')
        seen.add(entry['id']); location(entry['source']); sha(entry['active']); identifier(entry['library_id']); text(entry['name']); version(entry['version'])
        if type(entry['count']) is not int or not 1 <= entry['count'] <= LIMIT or not isinstance(entry['history'], list) or len(entry['history']) > 3:
            fail('INVALID_STATE', '拓展库缓存版本配置损坏')
        for key in entry['history']: sha(key)
        releases = entry.get('release_hashes', {})
        if not isinstance(releases, dict) or len(releases) > 4: fail('INVALID_STATE', '拓展库版本绑定损坏')
        for release, key in releases.items():
            version(release); sha(key)
            if key not in [entry['active'], *entry['history']]: fail('INVALID_STATE', '拓展库版本绑定不属于缓存历史')
        if 'error' in entry:
            obj(entry['error'], ('code', 'message')); text(entry['error']['code']); text(entry['error']['message'], 2000)
    return value


@contextmanager
def write_lock(workspace):
    root = cache_root(workspace)
    file = resolved_path(root / '.write.lock')
    if not file.is_relative_to(root): fail('UNSAFE_PATH', '缓存锁路径越界')
    with file.open('a+b') as stream:
        if stream.seek(0, 2) == 0: stream.write(b'0'); stream.flush()
        try:
            stream.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            fail('LOCK_BUSY', '另一项拓展库操作正在进行，请稍后重试')
        try: yield
        finally:
            stream.seek(0)
            if os.name == 'nt': msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else: fcntl.flock(stream, fcntl.LOCK_UN)


def blob(workspace, raw):
    key = digest(raw)
    root = cache_root(workspace)
    file = resolved_path(root / 'blobs' / (key + '.json'))
    if not file.is_relative_to(root): fail('UNSAFE_PATH', '缓存路径越界')
    atomic(file, raw)
    return key


def cached(workspace, key, limit=MAX_ASSET):
    sha(key)
    root = cache_root(workspace)
    file = resolved_path(root / 'blobs' / (key + '.json'))
    if not file.is_relative_to(root): fail('UNSAFE_PATH', '缓存路径越界')
    raw = fetch(str(file), limit)
    if digest(raw) != key: fail('CACHE_CORRUPT', '拓展缓存损坏，请刷新该库')
    return raw


def load_snapshot(workspace, source):
    data = manifest(cached(workspace, source['active'], MAX_MANIFEST))
    return data, [(entry, payload(entry, cached(workspace, entry['sha256']))) for entry in data['assets']]


def bundled():
    file = BUNDLED / 'library.json'
    data = manifest(fetch(str(file), MAX_MANIFEST))
    if data['id'] != 'nbtcreator.modular': fail('IDENTITY_CHANGED', '应用自带库编号无效')
    return data, [(entry, payload(entry, fetch(child_location(str(file), entry['path']), MAX_ASSET))) for entry in data['assets']]


def discover(source):
    source = location(source)
    actual = []; raw = fetch(source, MAX_MANIFEST, actual); source = actual[0]; data = decode(raw)
    if isinstance(data, dict) and data.get('kind') == FORMAT:
        data = manifest(raw)
        return dict(items=[dict(id=data['id'], name=data['name'], version=data['version'], source=source, manifest_sha256=digest(raw))])
    header(data, REGISTRY)
    obj(data, ('schema_version', 'kind', 'libraries'), ('name',))
    if 'name' in data: text(data['name'])
    rows = data['libraries']
    if not isinstance(rows, list) or not 1 <= len(rows) <= 32: fail('SIZE_LIMIT', '清单须包含1～32个库')
    result = []; seen = set()
    for row in rows:
        obj(row, ('id', 'name', 'version', 'path', 'manifest_sha256'))
        identifier(row['id']); text(row['name']); version(row['version']); sha(row['manifest_sha256'])
        if row['id'] in seen: fail('DUPLICATE_ID', '清单含重复库编号')
        seen.add(row['id'])
        result.append(dict(id=row['id'], name=row['name'], version=row['version'], source=child_location(source, row['path']), manifest_sha256=row['manifest_sha256']))
    return dict(items=result)


def cache_asset(workspace, source, asset, deadline):
    if time.monotonic() >= deadline: fail('TIME_LIMIT', '库刷新超过60秒，请稍后重试')
    try: content = cached(workspace, asset['sha256'])
    except (OSError, ValueError): content = fetch(child_location(source, asset['path']), MAX_ASSET, deadline=deadline)
    payload(asset, content)
    if time.monotonic() >= deadline: fail('TIME_LIMIT', '库刷新超过60秒，请稍后重试')
    blob(workspace, content)


def synchronize(workspace, config, entry, expected=None):
    deadline = time.monotonic() + 60
    actual = []; raw = fetch(entry['source'], MAX_MANIFEST, actual, deadline=deadline)
    if expected and digest(raw) != sha(expected): fail('HASH_MISMATCH', '库清单已变化，请重新查看远端清单')
    data = manifest(raw)
    for other in config['sources']:
        if other['id'] != entry['id'] and other.get('library_id') == data['id']: fail('DUPLICATE_LIBRARY', '此库已连接；请刷新已有来源')
    releases = dict(entry.get('release_hashes', {}))
    if entry.get('active'):
        # The atomic state binds active version and hash even when its cached
        # manifest is damaged. A verified refresh can therefore repair that blob.
        if entry['library_id'] != data['id']: fail('IDENTITY_CHANGED', '来源的库编号已变化，请另建连接')
        if version(data['version']) < version(entry['version']): fail('DOWNGRADE', '远端版本较旧，请使用回退功能选择已缓存版本')
        releases[entry['version']] = entry['active']
        if 'release_hashes' not in entry:
            # Read older connection files without losing their rollback bindings.
            for key in entry.get('history', []):
                try: previous = manifest(cached(workspace, key, MAX_MANIFEST))
                except (OSError, ValueError): continue
                releases.setdefault(previous['version'], key)
    if data['version'] in releases and digest(raw) != releases[data['version']]:
        fail('VERSION_REUSED', '相同版本的清单已改变，发布者须提高版本号')
    # Bounded I/O avoids paying a full network round trip serially for every
    # small JSON file. Cache writes stay content-addressed; state activates only
    # after every future succeeds. Errors cancel queued work, preserving active.
    executor = ThreadPoolExecutor(max_workers=DOWNLOAD_WORKERS, thread_name_prefix='nbt-assets')
    futures = [executor.submit(cache_asset, workspace, actual[0], asset, deadline) for asset in data['assets']]
    try:
        for future in as_completed(futures, timeout=max(.01, deadline - time.monotonic())): future.result()
    except FuturesTimeoutError:
        fail('TIME_LIMIT', '库刷新超过60秒，请稍后重试')
    finally:
        for future in futures: future.cancel()
        executor.shutdown(wait=True, cancel_futures=True)
    key = blob(workspace, raw)
    previous = entry.get('active')
    if previous and previous != key:
        entry['history'] = ([previous] + [k for k in entry.get('history', []) if k not in (previous, key)])[:3]
    entry.update(active=key, library_id=data['id'], name=data['name'], version=data['version'], count=len(data['assets']))
    releases[data['version']] = key
    reachable = {key, *entry.get('history', [])}
    entry['release_hashes'] = {release: value for release, value in releases.items() if value in reachable}
    entry.pop('error', None)


def row(library_data, entry, data, source_id):
    qualified = library_data['id'] + '/' + entry['id']
    result = dict(id=qualified, asset_id=entry['id'], library_id=library_data['id'], source_id=source_id,
                  name=entry['name'], type=entry['type'], category=entry.get('category', '未分类'),
                  status=entry.get('status', 'stable'), tags=entry.get('tags', []), sha256=entry['sha256'],
                  version=library_data['version'], license=library_data['license'])
    if entry['type'] == 'parametric_recipe':
        result.update(arguments=deepcopy(data['arguments']), controls=deepcopy(data.get('controls', {})))
        result['arguments'].setdefault('name', entry['name'])
    else: result.update(size=data['size'], anchor=data['anchor'], block_count=len(data['blocks']), content_sha256=data['content_sha256'])
    return result


def snapshot_manifest(workspace, source_id):
    if source_id == 'bundled':
        raw = fetch(str(BUNDLED / 'library.json'), MAX_MANIFEST)
        data = manifest(raw)
        if data['id'] != 'nbtcreator.modular': fail('IDENTITY_CHANGED', '应用自带库编号无效')
        return data, digest(raw)
    source = next((item for item in state(workspace)['sources'] if item['id'] == source_id), None)
    if source is None or not source['enabled']: fail('NOT_FOUND', '拓展来源已移除或停用')
    data = manifest(cached(workspace, source['active'], MAX_MANIFEST))
    if data['id'] != source['library_id'] or data['version'] != source['version']:
        fail('INVALID_STATE', '拓展库版本记录与清单不一致，请刷新来源')
    return data, source['active']


def snapshot_payload(workspace, source_id, entry):
    if source_id == 'bundled':
        raw = fetch(child_location(str(BUNDLED / 'library.json'), entry['path']), MAX_ASSET)
    else:
        raw = cached(workspace, entry['sha256'])
    return payload(entry, raw)


def preview_engine():
    from nbt_modeling_session import canonical, engine_revision
    return digest(canonical(engine_revision()).encode('utf8'))


def thumbnail_paths(workspace, asset_sha256, engine):
    root = cache_root(workspace)
    key = digest(encode(dict(asset_sha256=asset_sha256, engine=engine, thumbnail_version=1)))
    image = resolved_path(root / 'previews' / (key + '.jpg'))
    receipt = image.with_suffix('.json')
    if not image.is_relative_to(root): fail('UNSAFE_PATH', '预览缓存路径越界')
    return image, receipt


def checked_thumbnail(workspace, asset_sha256, engine):
    image, receipt = thumbnail_paths(workspace, asset_sha256, engine)
    try:
        record = decode(fetch(str(receipt), MAX_MANIFEST))
        if digest(fetch(str(image), MAX_ASSET)) == record['image_sha256']:
            return str(image)
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return None


def browse(workspace, *, query=None, limit=6):
    """The UI catalogue retains bundled and connected editions side by side."""
    if query is not None:
        if not isinstance(query,str) or not query.strip() or len(query)>300:fail('INVALID_REQUEST','输入1～300字的资产名称或标签')
        if type(limit) is not int or not 1<=limit<=32:fail('INVALID_REQUEST','资产检索数量须为1～32')
        from nbt_text_search import score
    errors = []
    try: config = state(workspace)
    except (OSError, ValueError) as error:
        config = dict(sources=[])
        errors.append(dict(source_id='configuration', error=str(error), code=getattr(error, 'code', 'INVALID_STATE')))
    sources = [dict(id='bundled', name='应用自带', enabled=True, bundled=True)] + deepcopy(config['sources'])
    items = []
    engine = preview_engine() if query is None else None
    for source in sources:
        if not source['enabled']: continue
        try:
            data, key = snapshot_manifest(workspace, source['id'])
            prepared = []
            for entry in data['assets']:
                if query is not None:
                    vocabulary=' '.join((entry['name'],entry.get('category',''),entry['id'].replace('-',' '),*entry.get('tags',[])))
                    rank=score(query,vocabulary)
                    if any(name in query for name in ('螺旋梯','螺旋楼梯','盘旋楼梯')):
                        rank=max(rank,score('旋梯',entry['name']))
                    if rank<=0:continue
                content = snapshot_payload(workspace, source['id'], entry)
                item = row(data, entry, content, source['id'])
                item.update(manifest_sha256=key, source_name='应用自带' if source['id']=='bundled' else data['name'],
                            review_status='pending_visual_review')
                if engine is not None:item['thumbnail']=checked_thumbnail(workspace,entry['sha256'],engine)
                if entry['type'] == 'parametric_recipe': item['size'] = deepcopy(item['arguments']['size'])
                if query is None:prepared.append(item)
                else:
                    fields=('id','source_id','version','manifest_sha256','sha256','name','type','tags','size','review_status')
                    prepared.append((rank,{field:item[field] for field in fields}))
            source.update(version=data['version'], library_id=data['id'], active=key, count=len(prepared))
            items.extend(prepared)
        except (OSError, ValueError) as error:
            errors.append(dict(source_id=source['id'], error=str(error), code=getattr(error, 'code', 'INVALID_ASSET')))
    if query is not None:
        ranked=sorted(items,key=lambda pair:(-pair[0],pair[1]['id'],pair[1]['source_id']))
        return dict(items=[item for _,item in ranked[:limit]],errors=errors,offline=True,query=query)
    return dict(items=items, sources=sources, errors=errors, offline=True)


def listing(workspace=None):
    errors = []
    try: config = state(workspace) if workspace is not None else dict(sources=[])
    except (OSError, ValueError) as error:
        config = dict(sources=[])
        errors.append(dict(source_id='configuration', code=getattr(error, 'code', 'INVALID_STATE'), error=str(error)))
    items = []; sources = deepcopy(config['sources'])
    override = False
    for source in sources:
        if not source.get('enabled', True): continue
        try:
            data, assets = load_snapshot(workspace, source)
            items.extend(row(data, entry, value, source['id']) for entry, value in assets)
            if data['id'] == 'nbtcreator.modular': override = True
        except (OSError, ValueError) as error:
            errors.append(dict(source_id=source['id'], code=getattr(error, 'code', 'INVALID_ASSET'), error=str(error)))
    if not override:
        try:
            data, assets = bundled()
            items = [row(data, entry, value, 'bundled') for entry, value in assets] + items
        except (OSError, ValueError) as error:
            errors.append(dict(source_id='bundled', code=getattr(error, 'code', 'INVALID_ASSET'), error=str(error)))
    return dict(items=items, sources=sources, errors=errors, offline=True)


def recipes(workspace=None, kind=None):
    result = listing(workspace)
    rows = []
    for item in result['items']:
        if item['type'] != 'parametric_recipe' or kind is not None and item['arguments']['kind'] != kind: continue
        # Preserve public recipe IDs for the official pack, qualify all other packs.
        if item['library_id'] == 'nbtcreator.modular': item['id'] = item['asset_id']
        rows.append(item)
    return rows


def read_asset(workspace, request):
    key = request.get('id'); expected = sha(request.get('sha256'))
    binding = ('source_id', 'version', 'manifest_sha256')
    if any(field in request for field in binding):
        if any(field not in request for field in binding): fail('INVALID_REQUEST', '来源、版本和清单哈希须一同提供')
        source_id = request['source_id']
        if source_id != 'bundled' and (not isinstance(source_id, str) or not re.fullmatch('[a-f0-9]{32}', source_id)):
            fail('INVALID_ID', '来源编号无效')
        version(request['version']); sha(request['manifest_sha256'])
        data, manifest_key = snapshot_manifest(workspace, source_id)
        if data['version'] != request['version'] or manifest_key != request['manifest_sha256']:
            fail('STALE_ASSET', '来源版本已变化，请重新载入并预览素材')
        entry = next((item for item in data['assets'] if data['id']+'/'+item['id']==key), None)
        if entry is None: fail('NOT_FOUND', '来源中已无此素材')
        if entry['sha256'] != expected: fail('STALE_ASSET', '素材内容已更新，请重新载入')
        content = snapshot_payload(workspace, source_id, entry)
        asset = row(data, entry, content, source_id)
        asset.update(manifest_sha256=manifest_key, source_name='应用自带' if source_id=='bundled' else data['name'])
        return dict(asset=asset, data=content, approval_created=False)
    for item in listing(workspace)['items']:
        if item['id'] != key: continue
        if item['sha256'] != expected: fail('STALE_ASSET', '资产已更新，请重新选择')
        if item['source_id'] == 'bundled': data, assets = bundled()
        else:
            source = next((s for s in state(workspace)['sources'] if s['id'] == item['source_id']), None)
            if source is None or not source['enabled']: fail('NOT_FOUND', '读取期间拓展库已移除或停用')
            if source['version'] != item['version']: fail('STALE_ASSET', '读取期间库版本已更新，请重新选择')
            data, assets = load_snapshot(workspace, source)
        for entry, value in assets:
            if entry['id'] == item['asset_id'] and entry['sha256'] == expected:
                return dict(asset=item, data=value, approval_created=False)
        fail('STALE_ASSET', '读取期间资产已更新，请重新选择')
    fail('NOT_FOUND', '资产未连接、已停用或不可用')


def materialize(workspace, result, arguments=None):
    asset = result['asset']
    if asset['type'] == 'component':
        if arguments is not None: fail('INVALID_REQUEST', '固定构件不接受配方参数，请先复制到本地编辑')
        return deepcopy(result['data']), None, None
    from nbt_structure_agent import dispatch as agent, build
    args = deepcopy(result['data']['arguments'])
    args.setdefault('name', asset['name'])
    if arguments is not None:
        if not isinstance(arguments, dict): fail('INVALID_REQUEST', '配方参数须为对象')
        args.update(deepcopy(arguments))
    if args.get('kind') != result['data']['arguments']['kind']:
        fail('INVALID_REQUEST', '请从素材库选择需要的构件类型')
    ornament = args.get('ornament', {})
    if isinstance(ornament, dict) and 'sample' in ornament: fail('UNSUPPORTED_REFERENCE', '当前拓展配方不接受本地图源引用')
    compiled = agent(workspace, 'parametric_compile', args)
    return build(workspace, compiled['spec']), compiled['spec'], args


def asset_action(workspace, action, request):
    if any(field not in request for field in ('source_id', 'version', 'manifest_sha256')):
        fail('INVALID_REQUEST', '使用素材须同时提供来源、版本和清单哈希')
    result = read_asset(workspace, request)
    if action == 'thumbnail':
        engine = preview_engine()
        image, receipt = thumbnail_paths(workspace, result['asset']['sha256'], engine)
        cached_image = checked_thumbnail(workspace, result['asset']['sha256'], engine)
        if not cached_image:
            from nbt_components import thumbnail
            data, _, _ = materialize(workspace, result)
            image.parent.mkdir(parents=True, exist_ok=True)
            temporary = image.with_name('.'+uuid.uuid4().hex+'.jpg')
            try:
                thumbnail(data, temporary)
                raw = temporary.read_bytes(); atomic(image, raw)
                atomic(receipt, encode(dict(image_sha256=digest(raw), content_sha256=data['content_sha256'],
                    size=data['size'], anchor=data['anchor'], block_count=len(data['blocks']))))
            finally: temporary.unlink(missing_ok=True)
        metadata = decode(fetch(str(receipt), MAX_MANIFEST))
        return dict(metadata, thumbnail=str(image), approval_created=False)
    data, spec, args = materialize(workspace, result, request.get('arguments'))
    if action == 'preview':
        from nbt_structure_agent import preview
        candidate = preview(workspace, data, spec)
        return dict(candidate, anchor=data['anchor'], library_asset=result['asset'], arguments=args, approval_created=False)
    if action in ('resolve', 'place', 'copy'):
        if sha(request.get('content_sha256')) != data['content_sha256']:
            fail('STALE_ASSET', '素材参数或内容已变化，请重新预览后使用')
        if action == 'resolve': return dict(component=data, library_asset=result['asset'], approval_created=False)
    if action == 'place':
        from nbt_components import batch_placement
        from nbt_recipes import load as load_theme
        theme = load_theme(workspace, request['theme']) if request.get('theme') else None
        placed = batch_placement(data, request['position'], request['size'], request.get('counts'), request.get('spacing'),
            request.get('quarter_turns', 0), request.get('mirror'), request.get('overwrite', False), theme)
        return dict(placed, library_asset=result['asset'], approval_created=False)
    from nbt_components import store
    item = store(workspace, dict(data, review_status='pending_visual_review'))
    root = cache_root(workspace)
    origin = resolved_path(root / 'imports' / (item['id']+'.json'))
    if not origin.is_relative_to(root): fail('UNSAFE_PATH', '来源记录路径越界')
    atomic(origin, encode(dict(result['asset'], arguments=args, content_sha256=data['content_sha256'])))
    return dict(item=item, nbt_exported=False, approval_created=False)


def dispatch(workspace, action, request):
    if action not in ACTIONS or not isinstance(request, dict): fail('INVALID_REQUEST', '未知拓展库操作')
    reference_fields = ('id', 'sha256', 'source_id', 'version', 'manifest_sha256')
    fields = {'list': (), 'browse': ('query','limit'), 'discover': ('source',), 'add': ('source', 'manifest_sha256'),
              'refresh': ('id', 'manifest_sha256'), 'enable': ('id', 'enabled'), 'remove': ('id',),
              'rollback': ('id',), 'read': reference_fields, 'import': reference_fields,
              'thumbnail': reference_fields, 'preview': (*reference_fields, 'arguments'),
              'resolve': (*reference_fields, 'arguments', 'content_sha256'),
              'copy': (*reference_fields, 'arguments', 'content_sha256'),
              'place': (*reference_fields, 'arguments', 'content_sha256', 'position', 'size', 'quarter_turns', 'mirror',
                        'overwrite', 'counts', 'spacing', 'theme', 'source', 'source_sha256')}
    obj(request, (), fields[action])
    if 'manifest_sha256' in request: sha(request['manifest_sha256'])
    if action == 'list': return listing(workspace)
    if action == 'browse':
        if request and not isinstance(request.get('query'),str):fail('INVALID_REQUEST','请提供资产检索词')
        return browse(workspace,**request)
    if action == 'discover': return discover(request.get('source'))
    if action in ('thumbnail', 'preview', 'resolve', 'place', 'copy'): return asset_action(workspace, action, request)
    if action in ('read', 'import'):
        result = read_asset(workspace, request)
        if action == 'read': return result
        if result['asset']['type'] != 'component': fail('INVALID_REQUEST', '参数化配方请在生成资产中预览后保存')
        from nbt_components import store
        data = dict(result['data'], review_status='pending_visual_review')
        item = store(workspace, data)
        root = cache_root(workspace)
        origin_file = resolved_path(root / 'imports' / (item['id'] + '.json'))
        if not origin_file.is_relative_to(root): fail('UNSAFE_PATH', '来源记录路径越界')
        atomic(origin_file, encode(result['asset']))
        return dict(item=item, nbt_exported=False, approval_created=False)
    root = cache_root(workspace); root.mkdir(parents=True, exist_ok=True)
    with write_lock(workspace):
        config = state(workspace)
        if action == 'add':
            source = location(request.get('source'))
            if any(s['source'] == source for s in config['sources']): fail('DUPLICATE_SOURCE', '来源已连接，请刷新已有库')
            if len(config['sources']) >= 32: fail('SIZE_LIMIT', '最多连接32个拓展库')
            entry = dict(id=uuid.uuid4().hex, source=source, enabled=True, history=[])
            synchronize(workspace, config, entry, request.get('manifest_sha256'))
            config['sources'].append(entry)
        else:
            entry = next((s for s in config['sources'] if s['id'] == request.get('id')), None)
            if entry is None: fail('NOT_FOUND', '未找到拓展库连接')
            if action == 'refresh':
                try: synchronize(workspace, config, entry, request.get('manifest_sha256'))
                except (OSError, ValueError) as error:
                    entry['error'] = dict(code=getattr(error, 'code', 'INVALID_ASSET'), message=str(error))
                    atomic(root / 'state.json', encode(config)); raise
            elif action == 'enable':
                if type(request.get('enabled')) is not bool: fail('INVALID_REQUEST', '启用状态须为布尔值')
                entry['enabled'] = request['enabled']
            elif action == 'remove': config['sources'].remove(entry)
            elif action == 'rollback':
                if not entry.get('history'): fail('NOT_FOUND', '没有可回退的缓存版本')
                target = entry['history'][0]
                data, _ = load_snapshot(workspace, dict(entry, active=target))
                entry['history'] = [entry['active']] + entry['history'][1:]
                entry.update(active=target, name=data['name'], version=data['version'], count=len(data['assets']))
                entry.pop('error', None)
        atomic(root / 'state.json', encode(config))
    return dict(source=entry, nbt_exported=False, approval_created=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, default=Path.cwd())
    parser.add_argument('action', choices=ACTIONS)
    parser.add_argument('--request', type=Path)
    args = parser.parse_args()
    try:
        request = decode(fetch(str(args.request), MAX_MANIFEST)) if args.request else {}
        print(json.dumps(dict(ok=True, result=dispatch(args.workspace, args.action, request)), ensure_ascii=False)); return 0
    except Exception as error:
        print(json.dumps(dict(ok=False, error=str(error), code=getattr(error, 'code', 'INVALID_ASSET')), ensure_ascii=False)); return 1


if __name__ == '__main__': raise SystemExit(main())
