"""Workspace image references and explicitly attributed interpretations."""
import io

from PIL import Image

from nbt_agent.protocol import error, fingerprint
from nbt_composition.object_scene import atomic
from nbt_project.batches import sha
from nbt_project.web_paths import workspace_path
from nbt_review.reference_views import IDENTIFIER, MAX_IMAGE, _hash, _image_bytes, load_reference


def bound_file(workspace, value):
    if not isinstance(value, str) or not value:
        raise ValueError('需要工作区文件路径')
    file = workspace_path(workspace, value)
    if not file.is_relative_to(workspace) or not file.is_file():
        error('EVIDENCE_INVALID', '证据必须是当前工作区内的文件', details={'path': value})
    return file


def register_pack(workspace, request):
    if set(request) - {'images', 'notes', 'calibration'}:
        raise ValueError('参考包包含未知字段')
    images = request['images']
    if not isinstance(images, list) or not 1 <= len(images) <= 32:
        raise ValueError('参考包须包含 1～32 张图片')
    records = {}
    total_bytes = 0
    for image in images:
        identifier = image['id']
        if not IDENTIFIER.fullmatch(identifier) or identifier in records:
            raise ValueError('图片 ID 无效或重复')
        kind, role = image['kind'], image['role']
        if kind not in ('photo', 'concept', 'part_detail', 'orthographic') or not role.strip():
            raise ValueError('图片种类或用途无效')
        file = bound_file(workspace, image['path'])
        raw, size, extension = _image_bytes(file)
        total_bytes += len(raw)
        if total_bytes > MAX_IMAGE * 2:
            raise ValueError('一份参考包的图片总量最多128MiB')
        if extension not in ('.png', '.jpg'):
            raise ValueError('参考包接受 PNG 或 JPEG')
        checksum = _hash(raw)
        if checksum != image['sha256']:
            error('REFERENCE_CHANGED', '参考图字节与登记哈希不一致', details={'id': identifier})
        source = image['source']
        if not isinstance(source, dict) or not source:
            raise ValueError('需要记录图像的已知出处')
        crops = image.get('crops', [])
        crop_ids = set()
        for crop in crops:
            bounds = crop['pixels']
            if (not isinstance(bounds, list) or len(bounds) != 4 or any(type(n) is not int for n in bounds)
                    or not (0 <= bounds[0] < bounds[2] <= size[0] and 0 <= bounds[1] < bounds[3] <= size[1])):
                raise ValueError('裁片须使用图像内的半开像素坐标')
            if not IDENTIFIER.fullmatch(crop['id']) or crop['id'] in crop_ids or not crop['role'].strip():
                raise ValueError('裁片 ID 或用途无效')
            crop_ids.add(crop['id'])
        records[identifier] = dict(id=identifier, path=file.relative_to(workspace).as_posix(), sha256=checksum,
                                   pixels=size, kind=kind, role=role, source=source, crops=crops)
    notes = request.get('notes', [])
    for note in notes:
        image = records.get(note['image_id'])
        if (image is None or note['kind'] not in ('observation', 'proposal', 'assumption', 'correction')
                or not note['location'].strip() or not note['text'].strip()):
            raise ValueError('参考说明须关联图片、部位、内容和说明类别')
        if note.get('crop_id') and note['crop_id'] not in {crop['id'] for crop in image['crops']}:
            raise ValueError('参考说明所指的裁片不存在')
        if note['kind'] == 'correction' and not note.get('basis', '').strip():
            raise ValueError('校正须说明依据')
    pack = dict(schema_version=1, images=list(records.values()), notes=notes)
    if 'calibration' in request:
        calibration = request['calibration']
        file = bound_file(workspace, calibration['path'])
        load_reference(file, calibration['sha256'])
        pack['calibration'] = dict(path=file.relative_to(workspace).as_posix(), sha256=calibration['sha256'])
    return dict(pack, sha256=fingerprint('reference_pack', pack))


def reference_issues(workspace, pack):
    issues = []
    for image in (pack or {}).get('images', []):
        try:
            file = bound_file(workspace, image['path'])
            valid = file.stat().st_size <= MAX_IMAGE and sha(file) == image['sha256']
        except (ValueError, OSError):
            valid = False
        if not valid:
            issues.append(dict(id=image['id'], path=image['path'], code='REFERENCE_CHANGED'))
    calibration = (pack or {}).get('calibration')
    if calibration:
        try:
            load_reference(bound_file(workspace, calibration['path']), calibration['sha256'])
        except (ValueError, OSError):
            issues.append(dict(id='calibration', path=calibration['path'], code='REFERENCE_CHANGED'))
    return issues


def crop_evidence(workspace, folder, image, crop):
    """Materialize just the granted pixels for the scoped host to share."""
    file = bound_file(workspace, image['path'])
    raw, _, _ = _image_bytes(file)
    if _hash(raw) != image['sha256']:
        error('REFERENCE_CHANGED', '裁片的原参考图已变化', details={'id': image['id']})
    output = io.BytesIO()
    with Image.open(io.BytesIO(raw)) as source:
        source.crop(crop['pixels']).save(output, 'PNG')
    content = output.getvalue()
    checksum = _hash(content)
    from nbt_project.prompts import inside
    destination = inside(workspace, folder / 'reference-crops' / (checksum + '.png'))
    if destination.exists():
        if sha(destination) != checksum:
            error('REFERENCE_CHANGED', '已登记裁片的内容发生变化')
    else:
        destination.parent.mkdir(exist_ok=True)
        atomic(destination, content)
    left, top, right, bottom = crop['pixels']
    return dict(id=image['id'], kind=image['kind'], role=crop['role'], crops=[crop], pixels=[right - left, bottom - top],
                source_sha256=image['sha256'], sha256=checksum, path=destination.relative_to(workspace).as_posix())
