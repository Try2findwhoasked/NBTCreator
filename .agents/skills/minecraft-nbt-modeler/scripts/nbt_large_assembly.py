"""Checked, sparse global view of separately stored SNBT authoring partitions.

This reader does not publish, edit, or export an assembly. Callers must bind
the manifest and every referenced part again before publishing derived work.
"""
import hashlib
import json
import os
import argparse
from copy import deepcopy
from pathlib import Path, PurePosixPath
import re
import tempfile

from nbt_assembly import Volume
from nbt_model import AIR_NAMES, Model, state
from nbt_snbt import MAX_SOURCE_BYTES, read_snbt, save_snbt

MAX_MANIFEST_BYTES = 4 * 1024 * 1024
MAX_AXIS = 4096
MAX_PARTITIONS = 2048
MAX_BLOCKS = 4_000_000
SHA = re.compile(r'^[0-9a-f]{64}$')


class AssemblyVolume(Model):
    """Sparse author-space geometry; a whole assembly is not one NBT export."""
    def __init__(self, size):
        if len(size) != 3 or any(type(n) is not int or not 1 <= n <= MAX_AXIS for n in size):
            raise ValueError('组装画布尺寸无效')
        self.size = tuple(size)
        self.blocks = {}
        self.stage = 'design'
        self.seal_record = None
        self.opened = set()
        self.final_fingerprint = None

    def save(self, path):
        raise ValueError('组装主稿不能导出为单份 NBT；请使用受支持的分区交付流程')


def _sha_file(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def _triplet(value, label, minimum, maximum):
    if not isinstance(value, list) or len(value) != 3 or any(type(v) is not int or not minimum <= v <= maximum for v in value):
        raise ValueError(label + '须为三个有效整数')
    return tuple(value)


def _part_path(root, name):
    if not isinstance(name, str) or not name or '\\' in name or ':' in name:
        raise ValueError('组装分区路径无效')
    relative = PurePosixPath(name)
    if relative.is_absolute() or any(part in ('.', '..') for part in relative.parts) or relative.suffix.lower() != '.snbt':
        raise ValueError('组装分区路径须为清单内的相对 SNBT 路径')
    candidate = root
    for part in relative.parts:
        candidate = candidate / part
        if candidate.is_symlink() or (hasattr(candidate,'is_junction') and candidate.is_junction()):
            raise ValueError('组装分区路径不能包含符号链接或联接')
    if not candidate.resolve().is_relative_to(root) or not candidate.is_file():
        raise ValueError('组装分区路径不存在或超出清单目录')
    return candidate


def is_assembly_source(path):
    """Recognize the reserved assembly format without treating all JSON as a source."""
    path = Path(path)
    if path.suffix.lower() != '.json' or not path.is_file() or path.stat().st_size > MAX_MANIFEST_BYTES:
        return False
    try:
        with path.open('rb') as stream:
            raw = stream.read(MAX_MANIFEST_BYTES + 1)
        data = json.loads(raw) if len(raw) <= MAX_MANIFEST_BYTES else None
    except (OSError, ValueError, UnicodeDecodeError):
        return False
    return isinstance(data, dict) and data.get('format') == 'nbtcreator-assembly'


def assembly_manifest(path):
    """Validate the manifest and paths without decoding partition contents."""
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_MANIFEST_BYTES:
        raise ValueError('组装清单不存在、为符号链接或超过大小上限')
    path = path.resolve()
    with path.open('rb') as stream:
        raw = stream.read(MAX_MANIFEST_BYTES + 1)
    if len(raw) > MAX_MANIFEST_BYTES:
        raise ValueError('组装清单超过大小上限')
    try:
        data = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        raise ValueError('组装清单 JSON 无效') from None
    if not isinstance(data, dict) or set(data) != {'format', 'schema_version', 'size', 'partitions'} or data['format'] != 'nbtcreator-assembly' or type(data['schema_version']) is not int or data['schema_version'] != 1:
        raise ValueError('组装清单格式或版本无效')
    size = _triplet(data['size'], '组装画布尺寸', 1, MAX_AXIS)
    parts = data['partitions']
    if not isinstance(parts, list) or not 1 <= len(parts) <= MAX_PARTITIONS:
        raise ValueError('组装分区数量无效')
    checked=[];paths=set()
    for entry in parts:
        if not isinstance(entry, dict) or set(entry) != {'file', 'offset', 'size', 'sha256'}:
            raise ValueError('组装分区字段无效')
        offset = _triplet(entry['offset'], '分区偏移', -MAX_AXIS, MAX_AXIS)
        declared = _triplet(entry['size'], '分区尺寸', 1, 294)
        if any(offset[i] >= size[i] or offset[i] + declared[i] <= 0 for i in range(3)):
            raise ValueError('组装分区与画布不相交')
        sha = entry['sha256']
        if not isinstance(sha, str) or not SHA.fullmatch(sha):
            raise ValueError('组装分区哈希无效')
        file = _part_path(path.parent, entry['file'])
        if file in paths:
            raise ValueError('组装分区路径重复')
        paths.add(file);checked.append((file,sha,offset,declared))
    return path,raw,data,checked


def assembly_source_matches(path, expected_sha, expected_parts):
    """Check that a previously inspected manifest and every part still match."""
    try:
        path,raw,data,checked=assembly_manifest(path)
        if hashlib.sha256(raw).hexdigest() != expected_sha:
            return False
        recorded = [dict(file=entry['file'], sha256=entry['sha256']) for entry in data['partitions']]
        if recorded != expected_parts:
            return False
        for file,sha,_,_ in checked:
            if _sha_file(file) != sha:
                return False
        return not path.is_symlink() and _sha_file(path) == expected_sha
    except (OSError, ValueError, TypeError, KeyError, UnicodeDecodeError):
        return False


def read_assembly(path):
    """Return (global sparse model, explicit walls) after verifying all bytes."""
    path,raw,data,files = assembly_manifest(path)
    size = _triplet(data['size'], '组装画布尺寸', 1, MAX_AXIS)
    parts = data['partitions']
    model = AssemblyVolume(size)
    walls, checked, owners, metadata = set(), [], {}, []
    for index, (entry, (file,sha,offset,declared)) in enumerate(zip(parts,files)):
        if _sha_file(file) != sha:
            raise ValueError('组装分区哈希不一致：' + entry['file'])
        part, mask = read_snbt(file)
        if _sha_file(file) != sha:
            raise ValueError('读取期间组装分区发生变化：' + entry['file'])
        if part.size != declared or not getattr(part, '_wall_mask_declared', False):
            raise ValueError('组装分区尺寸不一致或缺少显式墙层')
        if len(model.blocks) + len(part.blocks) > MAX_BLOCKS:
            raise ValueError('组装主稿方块数超过读取上限')
        for local, value in part.blocks.items():
            point = tuple(offset[i] + local[i] for i in range(3))
            if not model.in_bounds(point):
                raise ValueError('组装分区方块越界：' + str(point))
            if point in model.blocks:
                raise ValueError('组装分区方块重叠：' + str(point))
            model.blocks[point] = value
            owners[point] = index
            if local in mask:
                walls.add(point)
        metadata.append(dict(palette=deepcopy(part._snbt_palette), extras=deepcopy(part._snbt_extras)))
        checked.append((file, sha))
    with path.open('rb') as stream:
        unchanged = stream.read(MAX_MANIFEST_BYTES + 1) == raw
    if not unchanged or any(_sha_file(file) != sha for file, sha in checked):
        raise ValueError('读取期间组装清单或分区发生变化')
    model._wall_mask_declared = True
    model._assembly_binding = (path, hashlib.sha256(raw).hexdigest(), tuple((entry['file'], entry['sha256']) for entry in parts))
    model._assembly_layout = [dict(offset=list(entry['offset']),size=list(entry['size'])) for entry in parts]
    model._assembly_owners = owners
    model._assembly_metadata = metadata
    return model, walls


def verify_assembly_binding(model):
    """Reject changes to any input after a checked assembly was read."""
    binding = getattr(model, '_assembly_binding', None)
    if not binding:
        raise ValueError('组装模型没有可验证的来源绑定')
    return verify_assembly_files(binding)


def verify_assembly_files(binding):
    """Recheck an immutable binding retained separately from a working copy."""
    path, expected, parts = binding
    try:
        if path.is_symlink() or _sha_file(path) != expected:
            raise ValueError('组装清单发生变化')
        for name, sha in parts:
            file = _part_path(path.parent, name)
            if _sha_file(file) != sha:
                raise ValueError('组装分区发生变化：' + name)
        if path.is_symlink() or _sha_file(path) != expected:
            raise ValueError('组装清单发生变化')
    except OSError as error:
        raise ValueError('组装来源不可读取或发生变化') from error
    return True


def save_assembly(destination, model, walls, partitions, *, ownership=None, metadata=None, before_publish=None):
    """Publish an independently verified assembly into a new directory only.

    A manifest appears only after all parts have been written and read back.
    An interrupted publication can leave an unregistered directory, but never
    overwrites an existing directory or source.
    """
    destination = Path(destination)
    if destination.exists() or destination.is_symlink():
        raise ValueError('组装输出目录已存在，请选择新目录')
    size = _triplet(list(model.size), '组装画布尺寸', 1, MAX_AXIS)
    if not isinstance(partitions, list) or not 1 <= len(partitions) <= MAX_PARTITIONS:
        raise ValueError('组装分区数量无效')
    if ownership is not None and not isinstance(ownership, dict):
        raise ValueError('组装分区归属无效')
    if metadata is not None and (not isinstance(metadata, list) or len(metadata) != len(partitions)):
        raise ValueError('组装分区元数据无效')
    blocks = dict(model.blocks)
    wall_set = set(walls)
    if len(blocks) > MAX_BLOCKS:
        raise ValueError('组装主稿方块数超过写入上限')
    if not wall_set <= blocks.keys():
        raise ValueError('组装墙层必须指向实体方块')
    specs, buckets = [], {}
    for index, spec in enumerate(partitions):
        if not isinstance(spec, dict) or set(spec) != {'offset', 'size'}:
            raise ValueError('组装分区字段无效')
        offset = _triplet(spec['offset'], '分区偏移', -MAX_AXIS, MAX_AXIS)
        part_size = _triplet(spec['size'], '分区尺寸', 1, 294)
        lo = tuple(max(0, offset[i]) for i in range(3))
        hi = tuple(min(size[i], offset[i] + part_size[i]) for i in range(3))
        if any(lo[i] >= hi[i] for i in range(3)):
            raise ValueError('组装分区与画布不相交')
        specs.append((offset, part_size))
        for x in range(lo[0] // 64, (hi[0] - 1) // 64 + 1):
            for y in range(lo[1] // 64, (hi[1] - 1) // 64 + 1):
                for z in range(lo[2] // 64, (hi[2] - 1) // 64 + 1):
                    buckets.setdefault((x, y, z), []).append(index)
    models = [Volume(part_size) for _, part_size in specs]
    masks = [set() for _ in specs]
    for point, value in blocks.items():
        if not isinstance(point, tuple) or len(point) != 3 or any(type(v) is not int or not 0 <= v < size[i] for i, v in enumerate(point)):
            raise ValueError('组装方块坐标无效或越界')
        if not isinstance(value, str) or state(value) != value or value in AIR_NAMES:
            raise ValueError('组装方块状态无效或为空气')
        matches = []
        for index in buckets.get(tuple(v // 64 for v in point), []):
            offset, part_size = specs[index]
            local = tuple(point[i] - offset[i] for i in range(3))
            if all(0 <= local[i] < part_size[i] for i in range(3)):
                matches.append((index, local))
        if len(matches) > 1 and ownership is not None:
            previous = ownership.get(point)
            if previous is not None:
                matches = [item for item in matches if item[0] == previous]
            else:
                matches = matches[:1]
        if len(matches) != 1:
            raise ValueError('组装方块未被唯一分区覆盖：' + str(point))
        index, local = matches[0]
        models[index].blocks[local] = value
        if point in wall_set:
            masks[index].add(local)
    destination.parent.mkdir(parents=True, exist_ok=True)
    parent = destination.parent.resolve()
    destination = parent / destination.name
    with tempfile.TemporaryDirectory(prefix='.assembly-', dir=parent) as temporary:
        stage = Path(temporary)
        (stage / 'parts').mkdir()
        entries = []
        for index, ((offset, part_size), part, mask) in enumerate(zip(specs, models, masks)):
            name = f'parts/part-{index:04d}.snbt'
            meta = metadata[index] if metadata is not None else {}
            if not isinstance(meta, dict) or set(meta) - {'palette', 'extras'}:
                raise ValueError('组装分区元数据无效')
            receipt = save_snbt(stage / name, part, mask, palette=meta.get('palette'), extras=meta.get('extras'))
            entries.append(dict(file=name, offset=list(offset), size=list(part_size), sha256=receipt['source_sha256']))
        raw = (json.dumps(dict(format='nbtcreator-assembly', schema_version=1, size=list(size), partitions=entries),
                          ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n').encode('utf8')
        manifest = stage / 'assembly.json'
        manifest.write_bytes(raw)
        checked, checked_walls = read_assembly(manifest)
        if checked.blocks != blocks or checked_walls != wall_set:
            raise ValueError('组装主稿回读不一致')
        if tuple(model.size) != size or model.blocks != blocks or set(walls) != wall_set:
            raise ValueError('发布期间组装候选发生变化')
        if before_publish is not None:
            before_publish()
        try:
            destination.mkdir()
        except FileExistsError:
            raise ValueError('组装输出目录已存在，请选择新目录') from None
        os.rename(stage / 'parts', destination / 'parts')
        if before_publish is not None:
            before_publish()
        # Linking the verified manifest makes it visible atomically and refuses
        # an unexpected pre-existing destination on both Windows and POSIX.
        os.link(manifest, destination / 'assembly.json')
        result, result_walls = read_assembly(destination / 'assembly.json')
        if result.blocks != blocks or result_walls != wall_set:
            raise ValueError('发布后的组装主稿回读不一致')
    return dict(source=str(destination / 'assembly.json'), source_sha256=hashlib.sha256(raw).hexdigest(),
                geometry_sha256=result.fingerprint(), partitions=len(entries), blocks=len(blocks), wall_positions=len(wall_set))


def _workspace_path(workspace, value):
    if not isinstance(value, str) or not value or '\x00' in value:
        raise ValueError('工作区路径无效')
    supplied = Path(value)
    if '..' in supplied.parts:
        raise ValueError('工作区路径不能包含上级目录')
    candidate = supplied if supplied.is_absolute() else workspace / supplied
    # Windows may spell the same workspace with a short 8.3 path. Inspect the
    # supplied path before resolving that alias so links are not hidden.
    for part in (candidate,*candidate.parents):
        if part.is_symlink() or (hasattr(part,'is_junction') and part.is_junction()):
            raise ValueError('工作区路径不能包含符号链接或联接')
    candidate = candidate.resolve()
    try:
        relative = candidate.relative_to(workspace)
    except ValueError:
        raise ValueError('路径必须位于当前工作区内') from None
    current = workspace
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError('工作区路径不能包含符号链接')
    if not current.resolve().is_relative_to(workspace):
        raise ValueError('路径越出当前工作区')
    return current


def require_creative_workspace(workspace):
    workspace=Path(workspace).resolve()
    engine=Path(__file__).resolve().parents[1]
    software=engine.parents[2] if engine.parent.name=='skills' else None
    if (workspace==software or workspace==engine or workspace.is_relative_to(engine) or
        ((workspace/'desktop/main.cjs').is_file() and (workspace/'.agents/skills/minecraft-nbt-modeler/tool-catalog.json').is_file())):
        raise ValueError('软件源码目录或安装资源不是创作工作区')
    if not workspace.is_dir():raise ValueError('创作工作区不存在')
    return workspace


def import_assembly(workspace, request):
    """Copy explicitly selected, hash-bound SNBT parts into a new source version."""
    workspace = require_creative_workspace(workspace)
    if not isinstance(request, dict) or set(request) - {'size', 'output', 'partitions', 'set_current'}:
        raise ValueError('组装导入请求或工作区无效')
    size = _triplet(request.get('size'), '组装画布尺寸', 1, MAX_AXIS)
    parts = request.get('partitions')
    if not isinstance(parts, list) or not 1 <= len(parts) <= MAX_PARTITIONS:
        raise ValueError('组装分区数量无效')
    if type(request.get('set_current', False)) is not bool:
        raise ValueError('当前工作版选项须为布尔值')
    destination = _workspace_path(workspace, request.get('output'))
    models_root = workspace / 'nbt_models'
    if not destination.is_relative_to(models_root) or destination.name != 'master' or destination.parent == models_root or any(part in {'_exports', '_migration', '_workspaces'} for part in destination.relative_to(models_root).parts):
        raise ValueError('组装输出须为 nbt_models 内新建筑版本的 master 目录')
    if destination.exists() or destination.is_symlink():
        raise ValueError('组装输出目录已存在，请选择新目录')
    selected = []
    for entry in parts:
        if not isinstance(entry, dict) or set(entry) != {'source', 'sha256', 'offset'}:
            raise ValueError('组装导入分区字段无效')
        source = _workspace_path(workspace, entry['source'])
        sha = entry['sha256']
        offset = _triplet(entry['offset'], '分区偏移', -MAX_AXIS, MAX_AXIS)
        if source.suffix.lower() != '.snbt' or not source.is_file() or not isinstance(sha, str) or not SHA.fullmatch(sha):
            raise ValueError('组装分区须为已有 SNBT 和有效 SHA256')
        if source.stat().st_size > MAX_SOURCE_BYTES:
            raise ValueError('选定的 SNBT 分区超过256MiB')
        if _sha_file(source) != sha:
            raise ValueError('选定的组装分区哈希不一致：' + entry['source'])
        selected.append((source, sha, offset))
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.assembly-import-', dir=destination.parent) as temporary:
        stage = Path(temporary); (stage / 'parts').mkdir()
        entries = []
        for index, (source, sha, offset) in enumerate(selected):
            name = f'parts/part-{index:04d}.snbt'
            target = stage / name
            with source.open('rb') as original, target.open('xb') as output:
                copied = 0
                for chunk in iter(lambda: original.read(1024*1024), b''):
                    copied += len(chunk)
                    if copied > MAX_SOURCE_BYTES:
                        raise ValueError('导入期间 SNBT 分区超过256MiB')
                    output.write(chunk)
            if _sha_file(target) != sha or _sha_file(source) != sha:
                raise ValueError('导入期间选定的组装分区发生变化')
            model, _ = read_snbt(target)
            if not getattr(model, '_wall_mask_declared', False):
                raise ValueError('组装分区缺少显式墙层')
            entries.append(dict(file=name, offset=list(offset), size=list(model.size), sha256=sha))
        raw = (json.dumps(dict(format='nbtcreator-assembly', schema_version=1, size=list(size), partitions=entries),
                          ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n').encode('utf8')
        manifest = stage / 'assembly.json'; manifest.write_bytes(raw)
        model, walls = read_assembly(manifest)
        if any(_sha_file(source) != sha for source, sha, _ in selected):
            raise ValueError('发布前选定的组装分区发生变化')
        try:
            destination.mkdir()
        except FileExistsError:
            raise ValueError('组装输出目录已存在，请选择新目录') from None
        os.rename(stage / 'parts', destination / 'parts')
        if any(_sha_file(source) != sha for source, sha, _ in selected):
            raise ValueError('发布期间选定的组装分区发生变化；未登记组装清单')
        os.link(manifest, destination / 'assembly.json')
        saved, saved_walls = read_assembly(destination / 'assembly.json')
        if saved.blocks != model.blocks or saved_walls != walls:
            raise ValueError('导入后的组装主稿回读不一致')
    from nbt_history import record_produced_version
    history = record_produced_version(workspace, destination / 'assembly.json', message='导入组装制作源', actor='import', set_current=request.get('set_current', False))
    return dict(source=str(destination / 'assembly.json'), source_sha256=hashlib.sha256(raw).hexdigest(),
                geometry_sha256=saved.fingerprint(), size=list(size), partitions=len(entries), blocks=len(saved.blocks),
                wall_positions=len(saved_walls), history=history, history_pending=history.get('recorded') is False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, default=Path.cwd())
    sub = parser.add_subparsers(dest='action', required=True)
    create = sub.add_parser('import', help='Import selected hash-bound SNBT parts into a new authoring version')
    create.add_argument('--request', type=Path, required=True)
    sliced = sub.add_parser('slice', help='Issue a route-protected collaborative edit slice')
    sliced.add_argument('--request', type=Path, required=True)
    merge = sub.add_parser('merge', help='Validate and merge returned slices into a new draft')
    merge.add_argument('--request', type=Path, required=True)
    inspect = sub.add_parser('inspect', help='Verify an assembly and report its global geometry')
    inspect.add_argument('--source', type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.action in ('import','slice','merge'):
            if args.request.stat().st_size > MAX_MANIFEST_BYTES:
                raise ValueError('组装请求过大')
            request=json.loads(args.request.read_text(encoding='utf-8-sig'))
            if args.action == 'import':result=import_assembly(args.workspace,request)
            else:
                from nbt_assembly_handoff import create_slice,merge_slices
                result=(create_slice if args.action=='slice' else merge_slices)(args.workspace,request)
        else:
            source = _workspace_path(args.workspace.resolve(), str(args.source))
            model, walls = read_assembly(source)
            result = dict(source=str(source), source_sha256=model._assembly_binding[1], geometry_sha256=model.fingerprint(),
                          size=list(model.size), partitions=len(model._assembly_binding[2]), blocks=len(model.blocks), wall_positions=len(walls))
        print(json.dumps(result, ensure_ascii=False)); return 0
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(json.dumps(dict(error=str(error),code=getattr(error,'code','ASSEMBLY_INVALID'),
                              conflicts=getattr(error,'conflicts',[])), ensure_ascii=False)); return 1


if __name__ == '__main__':
    raise SystemExit(main())
