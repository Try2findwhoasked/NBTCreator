"""Read-only, geometry-bound section covers with persistent thumbnail caching."""
import hashlib
import json
import os
from pathlib import Path
import uuid

PROFILE = 'section-overview-v2'


def _stamp(file):
    stat = file.stat()
    return [stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns]


def _candidates(source):
    candidates = set()
    for parent in list(source.parents)[:5]:
        if parent.name in {'nbt_models', 'single', 'long', 'square', 'standalone', 'bugged'}:
            break
        candidates.update(parent.glob('*.png'))
        for root in parent.glob('previews*'):
            if root.is_dir():
                candidates.update(root.rglob('*.png'))
    result = []
    for image in sorted(candidates):
        # The texture renderer uses name.json; the offline renderer name.png.json.
        for metadata in (image.with_suffix('.json'), Path(str(image)+'.json')):
            try:
                result.append([str(image), _stamp(image), str(metadata), _stamp(metadata)])
            except OSError:
                continue
    return result


def _rank(metadata):
    requested = metadata.get('requested_view') or {}
    if not isinstance(requested, dict):
        requested = {}
    layer = metadata.get('layer', requested.get('layer', 'all'))
    if layer == 'walls':
        return None
    cuts = metadata.get('cuts', requested.get('cuts', [])) or metadata.get('cut')
    section = bool(cuts) or requested.get('cut_y') is not None or metadata.get('cut_y') is not None
    label = ' '.join(str(metadata.get(key, requested.get(key, ''))) for key in ('id', 'role')).lower()
    overview = any(word in label for word in ('overview', 'whole', 'section', 'cutaway', '剖', '截面', '整体', '全景', '总览'))
    return [int(section), int(overview), int(layer == 'all'), int(metadata.get('quality') in ('balanced', 'high'))]


def section_cover(source, geometry, cache, generate=False):
    """Never decode a model or render while browsing its existing image cover."""
    source, cache = Path(source).resolve(), Path(cache).resolve()
    cache.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(json.dumps([str(source), geometry, PROFILE]).encode()).hexdigest()
    index = cache / (key + '.json')
    stamp = _stamp(source)
    candidates = _candidates(source)
    generated = cache/'generated'/hashlib.sha256(json.dumps([str(source), stamp, PROFILE]).encode()).hexdigest()/'overview.png'
    try:
        candidates.append([str(generated), _stamp(generated), str(generated.with_suffix('.json')), _stamp(generated.with_suffix('.json'))])
    except OSError:
        pass
    signature = hashlib.sha256(json.dumps(candidates).encode()).hexdigest()
    try:
        previous = json.loads(index.read_text(encoding='utf8'))
        if previous['source_stamp'] == stamp and previous['signature'] == signature:
            result = previous['result']
            if (not result['image'] and not generate) or (result['image'] and Path(result['image']).is_file() and Path(result['thumbnail']).is_file()):
                return dict(result, cached=True)
    except (OSError, ValueError, KeyError, TypeError):
        pass
    matched = []
    source_hash = None
    for image, image_stamp, metadata_path, _ in candidates:
        try:
            metadata = json.loads(Path(metadata_path).read_text(encoding='utf-8-sig'))
            if not isinstance(metadata, dict):
                continue
            recorded_geometry = metadata.get('geometry_sha256') or metadata.get('source_geometry_sha256')
            if geometry and recorded_geometry:
                if geometry != recorded_geometry:
                    continue
            else:
                recorded_source = metadata.get('source_sha256') or metadata.get('source_nbt_sha256')
                if not recorded_source:
                    continue
                if source_hash is None:
                    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
                if recorded_source != source_hash:
                    continue
            rank = _rank(metadata)
            if rank is not None:
                # Prefer the local version when otherwise equivalent, then a recent image.
                local = int(Path(image).is_relative_to(source.parent))
                matched.append(([*rank, local, image_stamp[1]], image, image_stamp, metadata.get('generated_cover', False)))
        except (OSError, ValueError, TypeError):
            continue
    if not matched and generate:
        _generate(source, geometry, generated, stamp)
        return section_cover(source, geometry, cache)
    result = dict(image=None, thumbnail=None, profile=PROFILE, section=False, generated=False)
    for rank, image, image_stamp, is_generated in sorted(matched, key=lambda item:item[0], reverse=True):
        thumb_key = hashlib.sha256(json.dumps([image, image_stamp, PROFILE]).encode()).hexdigest()
        target = cache / (thumb_key + '.jpg')
        if not target.is_file():
            from PIL import Image
            temporary = target.with_name(target.stem + '.' + uuid.uuid4().hex + '.tmp')
            try:
                try:
                    with Image.open(image) as original:
                        thumb = original.convert('RGB')
                        thumb.thumbnail((384, 240))
                        thumb.save(temporary, 'JPEG', quality=80, optimize=True)
                except OSError:
                    continue
                os.replace(temporary, target)
            finally:
                temporary.unlink(missing_ok=True)
        result = dict(image=image, thumbnail=str(target), profile=PROFILE, section=bool(rank[0]), generated=bool(is_generated))
        break
    if not result['image'] and generate:
        _generate(source, geometry, generated, stamp)
        return section_cover(source, geometry, cache)
    if _stamp(source) != stamp:
        raise ValueError('生成预览期间建筑文件发生变化，请刷新后重试')
    temporary = index.with_name(index.stem + '.' + uuid.uuid4().hex + '.tmp')
    temporary.write_text(json.dumps(dict(source_stamp=stamp, signature=signature, result=result)), encoding='utf8')
    os.replace(temporary, index)
    return dict(result, cached=False)


def _generate(source, geometry, target, stamp):
    """Explicit-open fallback only; never called by library thumbnail browsing."""
    from nbt_refine import read_master
    from nbt_preview import make_grid, render
    import numpy as np
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    model, _ = read_master(source)
    actual = model.fingerprint()
    if geometry and geometry != actual:
        raise ValueError('模型索引已过期，请刷新建筑库后再预览')
    sx, sy, sz = model.size
    if sx*sy*sz > 4_000_000:
        raise ValueError('模型较大，请使用 3D 预览')
    height = max(1, min(sy-1, round(sy*.55)))
    cuts = [dict(axis='y', position=height, removed_side='above')]
    grid, colors, _ = make_grid(model, cuts=cuts)
    center = np.array([sx/2, height*.4, sz/2], dtype=float)
    span = max(sx, sz, sy)
    eye = center + np.array([span*.95, span*.9, -span*.95])
    image, _ = render(grid, colors, eye, center, 384, 240)
    if _stamp(source) != stamp or hashlib.sha256(source.read_bytes()).hexdigest() != source_hash:
        raise ValueError('生成预览期间建筑文件发生变化，请刷新后重试')
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(uuid.uuid4().hex+'.png')
    try:
        image.save(temporary)
        os.replace(temporary,target)
    finally:
        temporary.unlink(missing_ok=True)
    target.with_suffix('.json').write_text(json.dumps(dict(geometry_sha256=actual, source_sha256=source_hash,
        id='overview', layer='all', cuts=cuts, generated_cover=True,
        renderer='nbt_preview_half_voxel_v1')), encoding='utf8')
