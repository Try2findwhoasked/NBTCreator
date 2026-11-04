"""Collect version-bound feedback for an Agent; archive evidence without changing original records."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import uuid

from nbt_web_paths import project_paths


def sha(file):
    digest = hashlib.sha256()
    with Path(file).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def read(file):
    return json.loads(Path(file).read_text(encoding='utf-8-sig'))


def relative(file, directory):
    return os.path.relpath(file, directory).replace('\\', '/')


def resolve_asset(original, expected, role, feedback_file, sidecar, workspace):
    candidates = [feedback_file.parent/item['path'] for item in sidecar.get('files', [])
                  if item.get('role') == role and item.get('sha256') == expected]
    if original:
        candidates.append(Path(original))
        # A bounded relocation fallback for ordinary author files. Migrated job
        # evidence is located through the verified migration manifest below.
        parts = str(original).replace('\\', '/').split('/')
        if 'nbt_models' in parts:
            candidates.append(workspace.joinpath(*parts[parts.index('nbt_models'):]))
    for manifest in (workspace/'nbt_models/_migration').glob('*/migration.json'):
        for item in read(manifest).get('records', []):
            if item.get('source_sha256') == expected:
                candidates.append(workspace/item['target'])
    for candidate in dict.fromkeys(candidates):
        if candidate.is_file() and not candidate.is_symlink() and sha(candidate) == expected:
            return dict(role=role, path=str(candidate.resolve()), sha256=expected, status='verified')
    return dict(role=role, original_path=original, sha256=expected, status='missing_or_changed')


def archive_evidence(record_file, source, record, assets):
    if any(item['status'] != 'verified' for item in assets):
        raise ValueError('意见证据缺失或已变化；未归档，原记录保持不变')
    version = project_paths(source)['version']
    folder = version/'修改意见/证据'/record['binding']['source_sha256']
    folder.mkdir(parents=True, exist_ok=True)
    files = []
    for item in assets:
        current = Path(item['path'])
        if item['role'] == 'source':
            target = current
        else:
            if current.stat().st_size > 256*1024*1024:
                raise ValueError('意见证据须不超过256MiB')
            target = folder/(item['sha256']+current.suffix)
            if not target.exists():
                temporary = target.with_name(target.name+'.'+uuid.uuid4().hex+'.tmp')
                shutil.copyfile(current, temporary)
                if sha(temporary) != item['sha256']:
                    raise ValueError('复制过程中意见证据发生变化')
                # Content addressed files are immutable; do not replace them.
                try:
                    with target.open('xb') as output, temporary.open('rb') as stream:
                        shutil.copyfileobj(stream, output)
                except FileExistsError:
                    pass
                finally:
                    temporary.unlink(missing_ok=True)
            if sha(target) != item['sha256']:
                raise ValueError('已归档证据被修改')
        files.append(dict(role=item['role'], path=relative(target, record_file.parent), sha256=item['sha256']))
    sidecar = dict(schema_version=1, paths_relative_to='feedback_file',
                   source_sha256=record['binding']['source_sha256'],
                   geometry_sha256=record['binding']['geometry_sha256'], files=files)
    target = Path(str(record_file)+'.evidence.json')
    temporary = target.with_name(target.name+'.'+uuid.uuid4().hex+'.tmp')
    temporary.write_text(json.dumps(sidecar, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    temporary.replace(target)
    return str(target)


def update_index(source, record_file, record):
    directory = project_paths(source)['version']/'修改意见'
    directory.mkdir(parents=True, exist_ok=True)
    target = directory/'评论索引.json'
    index = read(target) if target.is_file() else dict(schema_version=1, paths_relative_to='index_file', records=[])
    if index.get('schema_version') != 1 or not isinstance(index.get('records'), list):
        raise ValueError('评论索引无效，未覆盖')
    binding = record['binding']
    item = dict(source=relative(source, directory), source_sha256=binding['source_sha256'],
                geometry_sha256=binding['geometry_sha256'], kind='3d' if binding.get('kind')=='3d' else 'image',
                feedback_file=relative(record_file, directory), feedback_sha256=sha(record_file),
                evidence_index=relative(str(record_file)+'.evidence.json', directory),
                notes=[{k:note[k] for k in ('id','status','text','anchors','point') if k in note} for note in record.get('notes', [])],
                updated_at=record.get('updated_at'))
    index['records'] = [r for r in index['records'] if r.get('feedback_file') != item['feedback_file']] + [item]
    temporary = target.with_name(target.name+'.'+uuid.uuid4().hex+'.tmp')
    temporary.write_text(json.dumps(index, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    temporary.replace(target)
    return str(target)


def scan(workspace, version=None):
    workspace = Path(workspace).resolve()
    indexes, visited = [], 0
    root = Path(version).resolve() if version else workspace/'nbt_models'
    for directory, dirs, names in os.walk(root, followlinks=False):
        dirs[:] = [name for name in dirs if name not in {'_workspaces','_tests','_migration','.git','node_modules','任务证据','任务历史','提示词方案'}
                   and not (Path(directory)/name).is_symlink()]
        visited += len(names)+len(dirs)
        if visited > 100000:
            raise ValueError('评论索引扫描超过100000项，请使用 --version 缩小范围')
        if '评论索引.json' not in names:
            continue
        file = Path(directory)/'评论索引.json'
        if file.is_symlink():
            continue
        index = read(file)
        if index.get('schema_version') != 1 or not isinstance(index.get('records'), list):
            raise ValueError('评论索引格式无效：'+str(file))
        records = []
        for entry in index['records']:
            source = (file.parent/entry['source']).resolve()
            record_file = (file.parent/entry['feedback_file']).resolve()
            valid = source.is_file() and record_file.is_file() and sha(source)==entry.get('source_sha256') and sha(record_file)==entry.get('feedback_sha256')
            records.append(dict(entry, source=str(source), feedback_file=str(record_file), verified=valid))
        indexes.append(dict(index_file=str(file), version_dir=str(file.parent.parent), records=records))
    return dict(schema_version=1, indexes=indexes, versions=len(indexes),
                notes=sum(len(r.get('notes', [])) for i in indexes for r in i['records']),
                verified=all(r['verified'] for i in indexes for r in i['records']),
                boundary='Comment indexes are design data, not approval. Use collect to verify all evidence.')


def version_source(version):
    version = Path(version).resolve()
    index = version/'修改意见/评论索引.json'
    if index.is_file():
        candidates = {str((index.parent/item['source']).resolve()) for item in read(index).get('records', [])}
        if len(candidates) == 1:
            return Path(candidates.pop())
        if len(candidates) > 1:
            raise ValueError('此版本索引包含多个源，请用 --source 指定')
    master = version/'master/master_geometry.json.gz'
    if master.is_file():
        return master
    raise ValueError('版本中未找到唯一源模型，请用 --source 指定')


def collect(source, workspace, archive=False):
    from nbt_refine import read_master
    source, workspace = Path(source).resolve(), Path(workspace).resolve()
    source_hash = sha(source)
    model, _ = read_master(source)
    info = project_paths(source)
    roots = [info['workdir']/'修改意见'/source_hash, info['version']/'修改意见'/source_hash,
             workspace/'build/nbt_feedback'/source_hash]
    indexed = info['version']/'修改意见/评论索引.json'
    candidates = [file for root in dict.fromkeys(roots) for file in sorted(root.glob('*.json')) if not file.name.endswith('.evidence.json')]
    if indexed.is_file():
        for item in read(indexed).get('records', []):
            if item.get('source_sha256') == source_hash:
                file = (indexed.parent/item['feedback_file']).resolve()
                if not file.is_file() or sha(file)!=item.get('feedback_sha256'):
                    raise ValueError('索引中的评论文件缺失或已变化：'+str(file))
                candidates.append(file)
    records = []
    for file in dict.fromkeys(p.resolve() for p in candidates):
        original_hash = sha(file)
        record = read(file)
        binding = record.get('binding', {})
        if binding.get('source_sha256') != source_hash:
            raise ValueError('意见目录与绑定源哈希不符：'+str(file))
        index = Path(str(file)+'.evidence.json')
        sidecar = read(index) if index.is_file() else {}
        if sidecar and (sidecar.get('source_sha256') != source_hash or sidecar.get('geometry_sha256') != binding.get('geometry_sha256')):
            raise ValueError('证据索引与原意见版本不符：'+str(file))
        assets = [dict(role='source', path=str(source), sha256=source_hash, status='verified')]
        role = 'snapshot' if binding.get('kind') == '3d' else 'image'
        assets.append(resolve_asset(binding.get(role), binding.get(role+'_sha256'), role, file, sidecar, workspace))
        for note in record.get('notes', []):
            for ref in note.get('references', []):
                key = 'reference:'+note['id']+':'+ref['sha256']
                assets.append(resolve_asset(ref.get('path'), ref['sha256'], key, file, sidecar, workspace))
        errors = []
        locations = []
        image_size = None
        if role == 'image' and assets[1]['status'] == 'verified':
            from PIL import Image
            with Image.open(assets[1]['path']) as image:
                image_size = list(image.size)
        for note in record.get('notes', []):
            anchors = note.get('anchors', [])
            if not anchors and note.get('point'):
                anchors = [dict(kind='image', number=note.get('number'), **note['point'])]
            for anchor in anchors:
                if anchor.get('kind') == 'image' and image_size:
                    locations.append(dict(note_id=note.get('id'), number=anchor.get('number'), kind='image',
                                          image=assets[1]['path'], image_size=image_size,
                                          image_pixel=[anchor['x']*image_size[0],anchor['y']*image_size[1]],
                                          voxel_position=None))
                elif anchor.get('kind') == 'voxel':
                    locations.append(dict(note_id=note.get('id'), number=anchor.get('number'), kind='voxel',
                                          position=anchor.get('position'),state=anchor.get('state'),
                                          geometry_matches_source=anchor.get('geometry_sha256')==model.fingerprint()))
        if role == 'snapshot' and assets[1]['status'] == 'verified':
            snapshot = read(assets[1]['path'])
            if snapshot.get('source_sha256') != source_hash or snapshot.get('geometry_sha256') != binding.get('geometry_sha256'):
                errors.append('snapshot_version_mismatch')
            blocks = {tuple(p): state for p, state in snapshot.get('blocks', [])}
            for note in record.get('notes', []):
                for anchor in note.get('anchors', []):
                    if anchor.get('geometry_sha256') != binding.get('geometry_sha256') or blocks.get(tuple(anchor.get('position', []))) != anchor.get('state'):
                        errors.append('anchor_state_or_version_mismatch:'+str(note.get('id')))
        entry = dict(feedback_file=str(file.resolve()), feedback_sha256=original_hash,
                     binding=binding, notes=record.get('notes', []), assets=assets,
                     locations=locations,
                     errors=errors, verified=not errors and all(item['status']=='verified' for item in assets),
                     geometry_matches_source=binding.get('geometry_sha256') == model.fingerprint())
        if archive:
            if errors:
                raise ValueError('意见锚点或快照版本不符，未归档')
            entry['evidence_index'] = archive_evidence(file, source, record, assets)
            entry['comment_index'] = update_index(source, file, record)
        if sha(file) != original_hash:
            raise ValueError('读取期间原意见发生变化')
        records.append(entry)
    if sha(source) != source_hash:
        raise ValueError('读取期间原模型发生变化')
    return dict(schema_version=1, source=str(source), source_sha256=source_hash,
                geometry_sha256=model.fingerprint(), records=records,
                notes=sum(len(r['notes']) for r in records), verified=all(r['verified'] for r in records),
                boundary='Design feedback only. Image points are not voxel XYZ. No approval or model change.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['scan', 'collect', 'archive'])
    choice=parser.add_mutually_exclusive_group()
    choice.add_argument('--source', type=Path)
    choice.add_argument('--version', type=Path, help='Structure version folder, containing 修改意见/评论索引.json')
    parser.add_argument('--workspace', type=Path, default=Path.cwd())
    parser.add_argument('--output', type=Path, help='New report directory; omitted scan prints indexes as JSON')
    args = parser.parse_args()
    if args.command == 'scan':
        if args.source:
            parser.error('scan 使用 --version 或 --workspace，读取意见请使用 collect')
        result=scan(args.workspace,args.version)
        if args.output:
            args.output.mkdir(parents=True, exist_ok=False)
            (args.output/'comment-indexes.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
        print(json.dumps(result,ensure_ascii=False))
        return 0 if result['verified'] else 1
    if not args.output or not (args.source or args.version):
        parser.error('collect/archive 需要 --source 或 --version，以及 --output 全新报告目录')
    if args.output.exists():
        raise FileExistsError('选择全新报告目录，保留原审阅资料')
    source = args.source or version_source(args.version)
    result = collect(source, args.workspace, archive=args.command=='archive')
    args.output.mkdir(parents=True)
    (args.output/'feedback.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    lines = ['# 已保存的建筑修改意见', '', result['boundary'], '']
    for record in result['records']:
        lines += ['## '+record['feedback_file'], '', '证据校验：'+str(record['verified']), '']
        for note in record['notes']:
            lines += ['### 意见 '+str(note.get('id'))+' · '+note.get('status', 'open'), '', '> '+note.get('text', '').replace('\n', '\n> '), '']
            for location in record['locations']:
                if location['note_id']==note.get('id'):
                    lines += ['- 位置：'+json.dumps(location,ensure_ascii=False)]
            for anchor in note.get('anchors', []):
                lines += ['- 标记：'+json.dumps(anchor, ensure_ascii=False)]
    (args.output/'feedback.md').write_text('\n'.join(lines)+'\n', encoding='utf8')
    print(json.dumps(dict(notes=result['notes'], verified=result['verified'], report=str((args.output/'feedback.json').resolve())), ensure_ascii=False))
    return 0 if result['verified'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
