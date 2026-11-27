"""Persist the host's concept gallery and explicit user choice before modelling."""

from nbt_agent.creation_execution import read
from nbt_agent.creation_inputs import fields, text
from nbt_agent.protocol import error, fingerprint
from nbt_project.queues import write
from nbt_review.reference_pack import reference_issues, register_pack
from nbt_review.reference_views import IDENTIFIER


def status(file, state, *, workspace=None):
    roles = state['options'].get('reference_roles')
    if not roles:
        return None
    current = read(file) if file.is_file() else {}
    if current.get('roles') != roles:
        current = dict(roles=roles)
    covered = {row['role'] for row in current.get('gallery', {}).get('images', [])}
    missing = [role for role in roles if role not in covered]
    if missing:
        return dict(current, phase='awaiting_gallery', missing_roles=missing)
    phase = 'awaiting_choice'
    if 'choice' in current:
        phase = 'awaiting_import'
    if 'pack' in current:
        phase = 'ready'
        if workspace is not None and (issues := reference_issues(workspace, current['pack'])):
            return dict(current, phase='reference_changed', image_issues=issues)
    return dict(current, phase=phase)


def update(job, file, state, action, request):
    current = status(file, state)
    if current is None:
        raise ValueError('请在 creation start 声明 reference_roles')
    if state['attempts']:
        raise ValueError('已有建模候选；若要换参考，请发布新任务修订')
    phase = current.pop('phase')
    current.pop('missing_roles', None)
    if action == 'reference_show':
        fields(request, ('images',))
        images = request['images']
        if not isinstance(images, list) or not 1 <= len(images) <= 32:
            raise ValueError('图集须包含 1～32 张已向用户展示的图片')
        identifiers = set()
        for image in images:
            fields(image, ('id', 'role', 'label'), ('sha256',))
            identifier = text(image['id'], 80)
            if not IDENTIFIER.fullmatch(identifier) or identifier in identifiers:
                raise ValueError('已展示图片须有唯一的有效 ID')
            identifiers.add(identifier)
            text(image['role'], 120)
            text(image['label'], 500)
            if 'sha256' in image:
                checksum = text(image['sha256'], 64)
                if len(checksum) != 64 or any(c not in '0123456789abcdef' for c in checksum):
                    raise ValueError('已展示图片的 SHA256 无效')
        gallery = dict(images=images, sha256=fingerprint('creation_gallery', images))
        if current.get('gallery') != gallery:
            current = dict(roles=current['roles'], gallery=gallery)
    elif action == 'reference_choose':
        fields(request, ('gallery_sha256', 'user_choice', 'adopted'), ('pending_rooms', 'expected_views'))
        if phase == 'awaiting_gallery':
            error('REFERENCE_CHOICE_REQUIRED', '先展示外观及全部必选房间的参考图')
        gallery = current['gallery']
        if gallery['sha256'] != request['gallery_sha256']:
            error('REFERENCE_CHANGED', '请使用刚向用户展示的图集哈希')
        text(request['user_choice'], 4000)
        adopted = request['adopted']
        images = {image['id']: image['role'] for image in gallery['images']}
        if not isinstance(adopted, dict) or set(adopted) != set(current['roles']):
            raise ValueError('请逐项记录必选部位采用的图片和设计')
        for role, item in adopted.items():
            fields(item, ('image_id', 'design'))
            if images.get(text(item['image_id'], 80)) != role:
                raise ValueError('采用项须引用该部位已展示的图片')
            text(item['design'])
        for key, label in (('pending_rooms', '待补房间'), ('expected_views', '预期机位')):
            items = request.get(key, [])
            if not isinstance(items, list) or len(items) > 32:
                raise ValueError(label+'须为至多 32 项的列表')
            for item in items:
                text(item, 300)
        if current.get('choice') != request:
            current.pop('pack', None)
            current['choice'] = request
    else:
        fields(request, ('pack',))
        if 'choice' not in current:
            error('REFERENCE_CHOICE_REQUIRED', '先登记用户对已展示图集的选择')
        selected = {item['image_id'] for item in current['choice']['adopted'].values()}
        try:
            pack = register_pack(job.workspace, request['pack'])
        except (KeyError, TypeError, AttributeError) as failure:
            raise ValueError('参考包字段无效，请核对图片、裁片与说明结构') from failure
        imported = {image['id']: image for image in pack['images']}
        if imported.keys() != selected:
            raise ValueError('导入的图片 ID 须与用户选择一致')
        for image in current['gallery']['images']:
            if image['id'] in selected and (
                imported[image['id']]['role'] != image['role'] or
                'sha256' in image and imported[image['id']]['sha256'] != image['sha256']
            ):
                error('REFERENCE_CHANGED', '导入图的部位或字节与已展示图不一致')
        current['pack'] = pack
    job.live()
    write(file, current)
    return status(file, state)


def require_ready(workspace, current):
    if current is None:
        return
    if current['phase'] != 'ready':
        error('REFERENCE_CHOICE_REQUIRED', '先展示外观及重点房间、取得用户选择并导入选定图片',
              details={'phase': current['phase']})
    issues = reference_issues(workspace, current['pack'])
    if issues:
        error('REFERENCE_CHANGED', '选定的参考文件已变化，请找回登记时的文件',
              details={'images': issues})
