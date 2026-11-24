"""Role-scoped briefs, prompt templates and summaries for authoring packages."""
import hmac
from nbt_agent import protocol
from nbt_agent.authoring_tasks import overlaps, owned
from nbt_project.authoring_runs import check_references


PROMPTS = {
    'lead': (
        '你负责整栋建筑的用途、区域连接和候选合模。',
        '用整栋空间承诺冻结必要路线、公共结构与验收条件，再给二级签发区域简报、写区和接口。',
        '以同一基线预检各区候选，核对原路线、接口两侧和实图，保存一个可审阅的整栋版本。',
        '交付空间覆盖、阻塞、实图和源引用。精修批准和定稿按现有入口。',
    ),
    'region': (
        '你负责本区用途与构件协作。按玩家活动组织构件批次，每件注明用途、落点、承托和机位。',
        '保留共享接口、必经路线和本区限制。需要跨区写入时交由一级协调。',
        '核对构件回传和只读依赖，提交区域承诺、候选哈希、覆盖和阻塞位置。',
        '本区的几何也使用有独立写区的叶子工作包。',
    ),
    'component': (
        '你负责此构件批次。先读必需方块页，核对旧状态、墙层、支点和使用侧。',
        '参考裁片用于理解所见轮廓。新状态须符合 Minecraft Java 1.20.1。',
        '用全局 XYZ 和 [state, wall] 回传旧值、目标值及必要页回执。逐件列接点、站位和复验机位。',
        '范围或父源变化时要求重新签发，收到局部反馈时按具体坐标复验。',
    ),
}

BASE_ACTIONS = ('claim', 'heartbeat', 'release', 'brief', 'context', 'block_state')
ROLE_ACTIONS = {'lead': ('inspect', 'issue', 'plan_merge', 'prepare_review', 'record_observation', 'save_draft'),
                'region': ('issue', 'reissue', 'report_region'), 'component': ('submit',)}


def valid_invite(package, session):
    invite = session.get('claim_token')
    return isinstance(invite, str) and package.get('claim_key') and hmac.compare_digest(invite, package['claim_key'])


def scoped_schema(workspace, session):
    import json
    from nbt_project.authoring_runs import run_folder
    from nbt_project.prompts import inside
    folder = run_folder(workspace, session)
    run = json.loads(inside(workspace, folder / 'authoring.json').read_bytes())
    package = run['packages'].get(session['package_id'])
    if not package:
        protocol.error('PACKAGE_ACCESS_DENIED', '工作包会话不存在')
    if session['package_revision'] != package['revision']:
        protocol.error('REVISION_CONFLICT', '会话使用过期工作包修订')
    if not valid_invite(package, session):
        protocol.check_lease(package, session, required=True)
    return {'authoring.' + action for action in BASE_ACTIONS + ROLE_ACTIONS[package['role']]}


def scoped_request(workspace, run, action, request, session):
    package = (run or {}).get('packages', {}).get(session.get('package_id'))
    if not package or any(request[key] != session.get(key) for key in ('batch_id', 'run_id')):
        protocol.error('PACKAGE_ACCESS_DENIED', '会话不属于当前制作运行或工作包')
    permitted = BASE_ACTIONS + ROLE_ACTIONS[package['role']]
    if action not in permitted:
        protocol.error('PACKAGE_ACCESS_DENIED', '当前工作包角色无权使用此动作', details={'action': action})
    if any(request[key] != package['id'] for key in ('package_id', 'parent_id') if key in request):
        protocol.error('PACKAGE_ACCESS_DENIED', '会话不能读取或变更其他工作包')
    if session.get('package_revision') != package['revision'] or (
            'package_revision' in request and request['package_revision'] != package['revision']):
        protocol.error('REVISION_CONFLICT', '会话或请求使用过期工作包修订')
    normalized = dict(request)
    if action == 'claim':
        if not valid_invite(package, session):
            protocol.error('PACKAGE_ACCESS_DENIED', '领取需要本包邀请凭据')
    else:
        if not isinstance(session.get('lease_token'), str) or type(session.get('fence')) is not int:
            protocol.error('LEASE_REQUIRED', '请先领取并为会话绑定租约')
        for key in ('lease_token', 'fence'):
            if key in normalized and normalized[key] != session.get(key):
                protocol.error('PACKAGE_ACCESS_DENIED', '请求租约不属于本会话')
            if action != 'inspect':
                normalized[key] = session.get(key)
        if action == 'inspect':
            protocol.check_lease(package, session, required=True)
    return action, normalized


def references_for(run, refs):
    pack = run['references'] or {'images': [], 'notes': []}
    rows = []
    for ref in refs:
        key, _, crop_id = ref.partition(':')
        image = next((item for item in pack['images'] if item['id'] == key), None)
        if image is None:
            raise ValueError('工作包引用了未登记的参考图')
        # A whole image carries its crops. A crop reference exposes only its own annotations.
        if crop_id:
            crops = [crop for crop in image['crops'] if crop['id'] == crop_id]
            if not crops:
                raise ValueError('工作包引用了未登记的裁片')
            image = dict(image, crops=crops)
        notes = [note for note in pack['notes'] if note['image_id'] == key and
                 (not crop_id or note.get('crop_id') == crop_id)]
        rows.append(dict(ref=ref, image=image, notes=notes))
    return rows


def authorized_refs(run, parent, refs):
    references_for(run, refs)
    if parent['depth'] == 1:
        return
    allowed = set(parent.get('reference_refs', []))
    if any(ref not in allowed and ref.split(':', 1)[0] not in allowed for ref in refs):
        protocol.error('REFERENCE_OUT_OF_SCOPE', '子工作包引用的参考图超出上级授权')


def summary(package):
    candidate = package.get('candidate')
    report = package.get('region_report')
    status = package['status']
    if status == 'in_progress':
        status = 'claimed' if protocol.lease_active(package) else 'pending'
    return dict(id=package['id'], depth=package['depth'], revision=package['revision'],
                status=status, candidate_sha256=package.get('candidate_sha256'),
                changed_positions=len(candidate['patches']) if candidate else 0,
                components=candidate['components'] if candidate else [], report=report)


def projection(workspace, folder, run, request):
    from nbt_project.authoring_runs import open_baseline
    package = owned(run, request)
    check_references(workspace, run)
    working = open_baseline(workspace, run, check_parent=run['phase'] != 'draft_saved')
    section = request.get('section', 'brief')
    depth = package['depth']
    role = package['role']
    role_refs = ([image['id'] for image in (run['references'] or {}).get('images', [])]
                 if depth == 1 else package.get('reference_refs', []))
    result = dict(package_id=package['id'], parent_id=package['parent_id'], revision=package['revision'], role=role,
                  section=section, source_binding=package['source_binding'])
    if section == 'references':
        ref = request.get('ref')
        if ref and ref not in role_refs and ref.split(':', 1)[0] not in role_refs:
            protocol.error('REFERENCE_OUT_OF_SCOPE', '所请求的参考图或裁片未授权给此工作包')
        references = references_for(run, [ref] if ref else role_refs)
        from nbt_review.reference_pack import crop_evidence
        for row in references:
            if ':' in row['ref']:
                row['image'] = crop_evidence(workspace, folder, row['image'], row['image']['crops'][0])
        result['references'] = references
    elif section == 'feedback':
        children = [summary(row) for row in run['packages'].values() if row['parent_id'] == package['id']]
        result.update(summary=summary(package), children=children,
                      report=package.get('region_report'), child_count=len(children))
        if depth == 1:
            result['reviews'] = [{key: row[key] for key in ('sha256', 'ready', 'missing_rooms', 'missing_views', 'issues')}
                                 for row in run.get('reviews', {}).values()]
    elif section == 'brief':
        fields = ('write_boxes', 'read_boxes', 'protected_boxes', 'components', 'expected_views', 'goal', 'required_checks')
        result.update({key: package[key] for key in fields if key in package})
        result['budget'] = dict(max_written_positions=working.limits['max_written_positions'], max_changed_positions=working._budget())
        result['reference_refs'] = role_refs
        result['prompt'] = list(PROMPTS[role])
        result['tools'] = ['authoring.' + action for action in BASE_ACTIONS + ROLE_ACTIONS[role]]
        if depth == 1:
            constraints = {key: working.context[key] for key in ('mode', 'start', 'targets', 'openings', 'route_legs',
                           'protected_boxes', 'protected_paths', 'reserved_boxes') if key in working.context}
            result.update(task=run['task'], spaces=run['spaces'], interfaces=run['interfaces'], constraints=constraints,
                          size=list(working.model.size), layout=run.get('layout'))
        elif depth == 2:
            spaces = [row for row in run['spaces'] if any(overlaps(row['box'], box) for box in package['write_boxes'])]
            result['spaces'] = spaces
            space_ids = {room['id'] for room in spaces}
            result['interfaces'] = [row for row in run['interfaces'] if space_ids.intersection(row['spaces'])]
        else:
            result.update(read_pages=list(range(len(package['read_boxes']))),
                          required_pages=package.get('required_pages', []), interface_refs=package.get('interfaces', []))
    else:
        raise ValueError('工作包视图须为 brief、references 或 feedback')
    if request.get('ref') and section != 'references':
        raise ValueError('单项引用只用于参考图视图')
    return dict(result, payload_bytes=len(protocol.canonical(result)))


def report_region(run, request):
    package = owned(run, request)
    if package['depth'] != 2:
        protocol.error('REGION_REQUIRED', '区域回执只由二级负责人登记')
    if not request['summary'].strip():
        raise ValueError('说明本区覆盖范围和阻塞')
    selected = set()
    for candidate in request['candidates']:
        child = run['packages'].get(candidate['package_id'], {})
        if (child.get('parent_id') != package['id'] or child['id'] in selected or
                child.get('candidate_sha256') != candidate['sha256']):
            protocol.error('CANDIDATE_CHANGED', '区域回执只引用本区的当前叶子候选')
        selected.add(child['id'])
    result = dict(package_id=package['id'], summary=request['summary'], candidates=request['candidates'],
                  blockers=request.get('blockers', []), revision=(package.get('region_report') or {}).get('revision', 0) + 1)
    result['sha256'] = protocol.fingerprint('region_report', result)
    package['region_report'] = result
    return result


def block_state(workspace, run, request):
    owned(run, request)
    check_references(workspace, run)
    from nbt_project.authoring_runs import open_baseline
    open_baseline(workspace, run)
    from nbt_registry import effective, normalize
    from nbt_collision import collision_cells
    name, props = effective(request['state'])
    value = normalize(dict(Name=name, Properties=props))
    cells, reason = collision_cells(value)
    return dict(state=value, collision_half_cells=sorted(cells or []), collision_reason=reason)
