"""Paired render evidence and spatial checks for ordinary SNBT candidates."""
from copy import deepcopy
import math

from nbt_agent import protocol
from nbt_agent.authoring_tasks import inside, owned
from nbt_building.review import verified_render
from nbt_collision import _Space, check_routes
from nbt_composition.object_scene import atomic
from nbt_composition.working_model import model_hash, point
from nbt_project.authoring_runs import check_references, identifier, open_baseline
from nbt_project.batches import sha
from nbt_project.prompts import inside as workspace_model
from nbt_refine import read_master


def vector(value):
    if not isinstance(value, list) or len(value) != 3 or any(type(n) not in (int, float) or abs(n) > 1e6 or not math.isfinite(n) for n in value):
        raise ValueError('机位与脚位须使用有限 XYZ 坐标')
    return value


def checked_source(workspace, source):
    file = workspace_model(workspace, source['source'])
    if sha(file) != source['source_sha256']:
        protocol.error('CANDIDATE_CHANGED', '审阅源文件已变化')
    model, walls = read_master(file)
    if sha(file) != source['source_sha256'] or model_hash(model, walls) != source['model_sha256']:
        protocol.error('CANDIDATE_CHANGED', '审阅模型回读不一致')
    return model


def affected_spaces(run, merge):
    positions = [point(row['pos']) for candidate in merge['candidates']
                 for row in run['packages'][candidate['package_id']]['candidate']['patches']]
    rooms = {room['id'] for room in run['spaces'] if any(inside(pos, room['box']) for pos in positions)}
    interfaces = []
    for interface in run['interfaces']:
        bounds = interface['box']
        neighborhood = dict(lo=[n - 1 for n in bounds['lo']], hi=[n + 1 for n in bounds['hi']])
        touched = [list(pos) for pos in positions if inside(pos, neighborhood)]
        if touched:
            rooms.update(interface['spaces'])
            interfaces.append(dict(id=interface['id'], spaces=interface['spaces'], positions=touched))
    return rooms, interfaces


def station_check(model, space, feet, use_face=None):
    if not space.standing(feet):
        return 'invalid_standing_pose'
    if not use_face:
        return None
    return check_block_face(model, space, feet, use_face)


def prepare_review(workspace, folder, run, merge, request):
    target = request.get('target', 'candidate')
    if target == 'draft':
        if not run['draft'] or run['draft']['merge_sha256'] != merge['merge_sha256']:
            protocol.error('MERGE_CHANGED', '没有同一批次的落盘制作版')
        after = dict(merge, source=run['draft']['source'], source_sha256=run['draft']['source_sha256'])
    elif target == 'candidate' and run['phase'] in ('baseline_bound', 'review_ready'):
        after = merge
    else:
        protocol.error('RUN_PHASE_CONFLICT', '当前阶段没有可审阅的同一批候选')
    working = open_baseline(workspace, run, check_parent=target == 'candidate')
    model = checked_source(workspace, after)
    collision = _Space(model)
    before_collision = _Space(working.model)
    affected, interfaces = affected_spaces(run, merge)
    rooms = {room['id']: room for room in run['spaces']}
    cameras, checks, seen = [], {}, set()
    if not 1 <= len(request['views']) <= 64:
        raise ValueError('审阅包须有 1～64 个机位')
    for row in request['views']:
        camera = deepcopy(row['camera'])
        key = identifier(camera['id'])
        if key.lower() != key or key in seen:
            raise ValueError('机位 ID 须唯一且使用小写')
        room = row.get('space')
        feet = row.get('feet')
        eye = vector(camera['eye'])
        vector(camera['target'])
        check = dict(space=room, status='outside_overview')
        if room:
            if room not in rooms or feet is None:
                raise ValueError('室内机位须标明已登记空间与脚位')
            feet = vector(feet)
            box = rooms[room]['box']
            if any(not box['lo'][i] <= feet[i] < box['hi'][i] + 1 for i in range(3)):
                raise ValueError('脚位超出空间范围')
            expected_eye = [feet[0], feet[1] + 1.62, feet[2]]
            if any(abs(a - b) > .01 for a, b in zip(eye, expected_eye)):
                raise ValueError('眼位须与实际脚位和玩家视高一致')
            before = station_check(working.model, before_collision, feet)
            after_check = station_check(model, collision, feet, row.get('use_face'))
            route = None
            if 'route_start' in row:
                start = vector(row['route_start'])
                route = check_routes(model, start, {key: feet}, max_poses=100000)
                if not route['passed']:
                    after_check = after_check or 'static_route_pending'
            check.update(status=after_check or before or 'standing', feet=feet, route=route,
                         before=before or 'standing', after=after_check or 'standing')
        if row.get('replaces'):
            check['replaces'] = identifier(row['replaces'])
        if room and row.get('focus'):
            from nbt_building.intent import visible_location
            focus = vector(row['focus'])
            visibility = visible_location(model, eye, focus, camera['target'], camera.get('fov', 60))
            check['focus'] = visibility
            if not visibility['passed']:
                check['status'] = visibility['failure']
        checks[key] = check
        seen.add(key)
        cameras.append(camera)
    before = dict(run['baseline'], geometry_sha256=working.model.fingerprint())
    for key, check in checks.items():
        alternative = check.get('replaces')
        if alternative and (alternative == key or alternative not in checks or checks[alternative]['space'] != check['space']):
            raise ValueError('替换机位须声明同一空间内的另一原机位')
    after_source = {name: after[name] for name in ('source', 'source_sha256', 'geometry_sha256', 'model_sha256')}
    required = {name for candidate in merge['candidates']
                for name in run['packages'][candidate['package_id']]['expected_views']}
    pack = dict(schema_version=1, merge_sha256=merge['merge_sha256'], target=target, before=before,
                after=after_source, rooms=sorted(affected), interfaces=interfaces, checks=checks,
                required_views=sorted(required), cameras_sha256=protocol.fingerprint('cameras', cameras))
    key = protocol.fingerprint('authoring_review_pack', pack)
    camera_file = folder / ('cameras-' + key + '.json')
    camera_bytes = protocol.canonical(cameras)
    if camera_file.exists() and camera_file.read_bytes() != camera_bytes:
        protocol.error('EVIDENCE_CHANGED', '固定机位文件已变化')
    if not camera_file.exists():
        atomic(camera_file, camera_bytes)
    pack.update(sha256=key, cameras=camera_file.relative_to(workspace).as_posix(), file_sha256=sha(camera_file))
    run.setdefault('review_packs', {})[key] = pack
    return dict(pack, render_commands={label: ['render', '--source', pack[label]['source'], '--cameras', pack['cameras']]
                                       for label in ('before', 'after')}, run_revision=run['revision'])


def check_block_face(model, space, feet, use_face):
    from nbt_collision import collision_cells
    from nbt_composition.scene_interfaces import FACES
    block = point(use_face['position'])
    axis, sign = FACES[use_face['face']]
    if axis == 1 or not model.in_bounds(block):
        raise ValueError('活动使用侧须声明模型内可水平接近的垂直面')
    plane = block[axis] + int(sign > 0)
    distance = (feet[axis] - plane) * sign
    if distance <= 0:
        return 'wrong_side'
    if distance > 2.5:
        return 'too_far'
    cells, reason = collision_cells(model.get(block))
    if reason or not cells:
        return 'unverified_working_face'
    probe = [feet[0], feet[1] + .5, feet[2]]
    face = [math.floor(2 * (v - origin)) for v, origin in zip(probe, block)]
    face[axis] = int(sign > 0)
    if tuple(face) not in cells:
        return 'outside_working_face'
    lo = [offset + n / 2 for offset, n in zip(block, face)]
    hi = [n + .5 for n in lo]
    lo[axis], hi[axis] = sorted((feet[axis], plane))
    return None if space.clear_box(lo, hi) else 'approach_obstructed'


def paired_images(workspace, pack, manifests):
    cameras = workspace_model(workspace, pack['cameras'])
    if sha(cameras) != pack['file_sha256']:
        protocol.error('EVIDENCE_CHANGED', '固定机位文件已变化')
    reports = {}
    config = None
    for side in ('before', 'after'):
        source = pack[side]
        render = manifests[side]
        checked_source(workspace, source)
        try:
            file, checksum, report, images = verified_render(workspace, cameras, source['source_sha256'],
                source['geometry_sha256'], render['path'], render['sha256'], workspace_model(workspace, source['source']))
        except (ValueError, OSError) as exc:
            protocol.error('EVIDENCE_INVALID', str(exc), details={'side': side})
        current = {key: report.get(key) for key in ('width', 'height', 'quality', 'pixel_ratio', 'frontend_sha256', 'browser_version')}
        if not current['frontend_sha256'] or (config is not None and current != config):
            protocol.error('RENDER_CONFIG_MISMATCH', '前后出图须使用同一预构建纹理、渲染设置和尺寸')
        config = current
        reports[side] = dict(path=file.relative_to(workspace).as_posix(), sha256=checksum, images=images)
    return reports


def record_observation(workspace, run, merge, request):
    pack = run.get('review_packs', {}).get(request['pack_sha256'])
    if not pack or pack['merge_sha256'] != merge['merge_sha256']:
        protocol.error('EVIDENCE_INVALID', '审阅包未绑定同一合模批次')
    if (run['phase'] == 'draft_saved') != (pack['target'] == 'draft'):
        protocol.error('RUN_PHASE_CONFLICT', '发布后须以落盘制作版登记新的图像证据')
    open_baseline(workspace, run, check_parent=pack['target'] == 'candidate')
    renders = paired_images(workspace, pack, request['manifests'])
    observed = {}
    for observation in request['observations']:
        view = observation['view']
        if view not in pack['checks'] or view in observed or any(not observation[key].strip() for key in ('before', 'after')):
            raise ValueError('每条观察须关联唯一机位，并记录前后图实际所见')
        observed[view] = observation
    useful = {key for key in observed if pack['checks'][key]['status'] in ('standing', 'outside_overview')}
    covered = {pack['checks'][key]['space'] for key in useful}
    history = run.get('reviews', {})
    earlier = [row for row in history.values() if row['merge_sha256'] == merge['merge_sha256'] and row['target'] == pack['target']]
    previous = max(earlier, key=lambda row: row['run_revision'], default={})
    expected = request.get('previous_review_sha256')
    if expected:
        if expected not in history or (previous and expected != previous['sha256']):
            protocol.error('EVIDENCE_INVALID', '须从同一候选最新观察或先前修订复验')
        previous = history[expected]
    issues = {row['id']: dict(row, state='missing_evidence') for row in previous.get('issues', [])
              if row['state'] != 'resolved'}
    seen = set()
    for row in request.get('issues', []):
        key = identifier(row['id'])
        if key in seen or row['view'] not in useful or not row['text'].strip() or row['status'] not in ('open', 'resolved'):
            raise ValueError('问题须关联已记录的有效机位与所见')
        if row['status'] == 'resolved' and key not in issues:
            raise ValueError('解决状态须对应上一回执中的实际问题')
        issues[key] = dict(row, state='resolved' if row['status'] == 'resolved' else 'persistent' if key in issues else 'new')
        seen.add(key)
    replaced = {pack['checks'][key].get('replaces') for key in useful}
    missing_views = sorted((set(pack['required_views']) | set(pack['checks'])) - useful - replaced)
    missing_rooms = sorted(set(pack['rooms']) - covered)
    ready = not missing_views and not missing_rooms and all(row['state'] == 'resolved' for row in issues.values())
    result = dict(pack_sha256=pack['sha256'], merge_sha256=merge['merge_sha256'], target=pack['target'], renders=renders,
                  observations=list(observed.values()), issues=list(issues.values()), missing_views=missing_views,
                  missing_rooms=missing_rooms, ready=ready, approval_created=False, game='not_checked',
                  run_revision=run['revision'])
    key = protocol.fingerprint('authoring_observation', result)
    result['sha256'] = key
    run.setdefault('reviews', {})[key] = result
    if pack['target'] == 'candidate':
        run['phase'] = 'review_ready' if ready else 'baseline_bound'
    elif ready:
        run['draft'].update(visual_review='observations_recorded', review_sha256=key)
    return result


def verify_review(workspace, run, merge, key):
    if key is None:
        return None
    review = run.get('reviews', {}).get(key)
    if not review or not review['ready'] or review['merge_sha256'] != merge['merge_sha256'] or review['target'] != 'candidate':
        protocol.error('EVIDENCE_INVALID', '发布需完整的当前合模候选观察回执')
    if any(row['merge_sha256'] == merge['merge_sha256'] and row['target'] == 'candidate' and
           row['run_revision'] > review['run_revision'] for row in run['reviews'].values()):
        protocol.error('EVIDENCE_CHANGED', '已有更新的候选观察回执')
    pack = run['review_packs'][review['pack_sha256']]
    if paired_images(workspace, pack, review['renders']) != review['renders']:
        protocol.error('EVIDENCE_CHANGED', '审阅证据已变化')
    return review


def dispatch(workspace, folder, run, action, request):
    if owned(run, request)['depth'] != 1:
        protocol.error('LEAD_REQUIRED', '整栋审阅由一级负责人登记')
    check_references(workspace, run)
    merge = run['merges'].get(request['merge_sha256'])
    if not merge or merge['references_sha256'] != (run['references'] or {}).get('sha256'):
        protocol.error('MERGE_CHANGED', '审阅需要当前已绑定的合模预检')
    if action == 'prepare_review':
        return prepare_review(workspace, folder, run, merge, request)
    return record_observation(workspace, run, merge, request)
