"""Lease-fenced delegation of edits to bounded regions of a whole model."""
import hashlib
import hmac
from uuid import uuid4

from nbt_agent import protocol
from nbt_composition.object_scene import inside
from nbt_composition.working_model import point, value_at
from nbt_model import AIR_NAMES
from nbt_project.authoring_runs import check_references, check_revision, identifier, open_baseline
from nbt_selection_edit import encode_context


def overlaps(a, b):
    return all(a['lo'][i] <= b['hi'][i] and b['lo'][i] <= a['hi'][i] for i in range(3))


def boxes(raw, bounds):
    if not isinstance(raw, list) or len(raw) > 32:
        raise ValueError('每组范围最多 32 个整数 XYZ 盒')
    result = []
    for box in raw:
        lo, hi = point(box['lo']), point(box['hi'])
        if any(a > b for a, b in zip(lo, hi)) or not any(inside(lo, b) and inside(hi, b) for b in bounds):
            protocol.error('SCOPE_EXCEEDED', '范围在上级授权盒之外或端点顺序有误', details={'box': box})
        result.append(dict(lo=list(lo), hi=list(hi)))
    return result


def new_package(key, parent, binding, write, read, protected, **spec):
    depth = parent['depth'] + 1 if parent else 1
    return dict(id=key, parent_id=parent['id'] if parent else None, depth=depth, revision=1,
                role=('lead', 'region', 'component')[depth - 1], status='pending', source_binding=binding,
                write_boxes=write, read_boxes=read, protected_boxes=protected, read_key=uuid4().hex, **spec)


def public_package(package):
    result = protocol.redact({key: value for key, value in package.items() if key not in ('read_key', 'claim_key', 'candidate')})
    if result['status'] == 'in_progress':
        result['status'] = 'claimed'
    return result


def fields(row, allowed):
    if not isinstance(row, dict) or set(row) - set(allowed.split()):
        protocol.error('INVALID_REQUEST', '工作包记录包含未知字段',
                       details={'allowed': allowed.split()})


def strings(value):
    return isinstance(value, list) and all(isinstance(part, str) and part.strip() for part in value)


def owned(run, request, field='package_id'):
    package = run['packages'].get(request[field])
    if package is None:
        protocol.error('PACKAGE_NOT_FOUND', '工作包不存在')
    check_revision(package, request['package_revision'])
    protocol.check_lease(package, request, required=True)
    return package


def issue_package(workspace, run, request):
    from nbt_agent.authoring_views import authorized_refs
    parent = owned(run, request, 'parent_id')
    if parent['depth'] == 3:
        protocol.error('PACKAGE_DEPTH', '第三级工作包不能再签发')
    raw = request['packages']
    if not 1 <= len(raw) <= 32 or len(run['packages']) + len(raw) > 256:
        raise ValueError('每次签发 1～32 个工作包，每个运行最多 256 包')
    model_box = run['packages']['root']['write_boxes'][0]
    siblings = [record for record in run['packages'].values() if record['parent_id'] == parent['id']]
    issued = []
    component_ids = {row['id'] for package in run['packages'].values() for row in package.get('components', [])}
    for spec in raw:
        fields(spec, 'id write_boxes read_boxes protected_boxes components expected_views interfaces reference_refs goal required_checks required_pages')
        key = identifier(spec['id'])
        if key in run['packages']:
            protocol.error('PACKAGE_EXISTS', '工作包 ID 已存在', details={'id': key})
        write = boxes(spec['write_boxes'], parent['write_boxes'])
        if not write:
            raise ValueError('工作包须有至少一个写区')
        for box in write:
            for sibling in siblings:
                if any(overlaps(box, other) for other in sibling['write_boxes']):
                    protocol.error('WRITE_SCOPE_OVERLAP', '兄弟包的写区相交', details={'other': sibling['id'], 'box': box})
        default_read = [dict(lo=[max(a - 1, 0) for a in box['lo']],
                             hi=[min(b + 1, limit) for b, limit in zip(box['hi'], model_box['hi'])]) for box in write]
        read = boxes(spec.get('read_boxes', default_read), parent['read_boxes'])
        boxes(write, read)
        protected = parent['protected_boxes'] + boxes(spec.get('protected_boxes', []), parent['read_boxes'])
        components = spec.get('components', [])
        views = spec.get('expected_views', [])
        interfaces = spec.get('interfaces', [])
        refs = spec.get('reference_refs', [])
        checks = spec.get('required_checks', [])
        goal = spec.get('goal', '')
        pages = spec.get('required_pages', list(range(len(read))) if parent['depth'] == 2 else [])
        if (not isinstance(components, list) or len(components) > 64 or
                not all(strings(value) for value in (views, interfaces, refs, checks)) or not isinstance(goal, str) or
                not isinstance(pages, list) or any(type(page) is not int or not 0 <= page < len(read) for page in pages) or
                len(set(pages)) != len(pages)):
            raise ValueError('构件、接口及机位列表格式无效')
        if parent['depth'] == 2 and not pages:
            raise ValueError('叶子至少须核对一个真实方块页')
        if parent['depth'] == 2:
            boxes(write, [read[page] for page in pages])
        authorized_refs(run, parent, refs)
        if not set(interfaces) <= {item['id'] for item in run['interfaces']}:
            raise ValueError('工作包接口须引用已登记的共享接口')
        if parent['depth'] == 2 and not set(interfaces) <= set(parent.get('interfaces', [])):
            protocol.error('SCOPE_EXCEEDED', '子包共享接口必须来自上级授权')
        if parent['depth'] == 2 and not components:
            raise ValueError('第三级工作包须登记负责的构件')
        for component in components:
            fields(component, 'id intent position required support use_side views')
            component_id = identifier(component['id'])
            if (component_id in component_ids or not component['intent'].strip() or
                    type(component.get('required', True)) is not bool or
                    not any(inside(point(component['position']), box) for box in write)):
                raise ValueError('构件 ID 须唯一且须标明用途及写区内的位置')
            component_ids.add(component_id)
        new = new_package(key, parent, run['baseline'], write, read, protected,
                          components=components, interfaces=interfaces, expected_views=views,
                          reference_refs=refs, goal=goal, required_checks=checks, required_pages=pages)
        new['claim_key'] = uuid4().hex
        siblings.append(new)
        run['packages'][key] = new
        issued.append(public_package(new))
    return dict(run_revision=run['revision'], packages=issued,
                invitations=[dict(batch_id=run['batch_id'], run_id=run['id'], package_id=row['id'],
                                  package_revision=row['revision'], claim_token=run['packages'][row['id']]['claim_key'])
                             for row in issued])


def reissue_package(workspace, run, request):
    parent = owned(run, request, 'parent_id')
    target = run['packages'].get(request['target_id'])
    if not target or target['parent_id'] != parent['id'] or target['depth'] != 3:
        protocol.error('PACKAGE_ACCESS_DENIED', '区域负责人只可重新签发本区叶子工作包')
    check_revision(target, request['target_revision'])
    spec = request['package']
    if spec.get('id') != target['id']:
        raise ValueError('重新签发须保留原工作包 ID')
    del run['packages'][target['id']]
    receipt = issue_package(workspace, run, dict(request, packages=[spec]))
    revised = run['packages'][target['id']]
    revised['revision'] = target['revision'] + 1
    revised['lease_epoch'] = target.get('lease_epoch', 0)
    archived = public_package(target)
    if target.get('candidate'):
        archived['candidate'] = target['candidate']
    run.setdefault('superseded_packages', []).append(archived)
    parent.pop('region_report', None)
    run['phase'] = 'baseline_bound'
    receipt['packages'] = [public_package(revised)]
    receipt['invitations'][0]['package_revision'] = revised['revision']
    return receipt


def read_fingerprint(package):
    return protocol.fingerprint('authoring_context', [package['id'], package['revision'], package['source_binding'],
                                                     package['read_boxes']])


def page_proof(package, read_sha256, page, content_sha256):
    payload = [read_sha256, page, package['lease']['fence'], content_sha256]
    return hmac.new(package['read_key'].encode('ascii'), protocol.canonical(payload), hashlib.sha256).hexdigest()


def package_context(workspace, run, request):
    package = owned(run, request)
    check_references(workspace, run)
    working = open_baseline(workspace, run)
    page = request.get('page', 0)
    if not 0 <= page < len(package['read_boxes']):
        raise ValueError('读取页超出工作包范围')
    box = package['read_boxes'][page]
    try:
        summary = encode_context(working.model, working.walls, box['lo'], box['hi'], exact_states=True)
    except ValueError as exc:
        axis = max(range(3), key=lambda i: box['hi'][i] - box['lo'][i])
        middle = (box['lo'][axis] + box['hi'][axis]) // 2
        first = dict(lo=list(box['lo']), hi=list(box['hi']))
        second = dict(lo=list(box['lo']), hi=list(box['hi']))
        first['hi'][axis], second['lo'][axis] = middle, middle + 1
        protocol.error('CONTEXT_LIMIT', str(exc), details={'page': page, 'box': box, 'suggested_boxes': [first, second]})
    working._unchanged()
    read_sha256 = read_fingerprint(package)
    selection_sha256 = protocol.fingerprint('selection', [box, summary])
    receipt = dict(page=page, content_sha256=selection_sha256,
                   proof=page_proof(package, read_sha256, page, selection_sha256)) if package.get('read_key') else None
    return dict(package_id=package['id'], package_revision=package['revision'], page=page, pages=len(package['read_boxes']),
                box=box, origin=box['lo'], read_sha256=read_sha256, page_receipt=receipt, selection=summary,
                payload_bytes=len(protocol.canonical(summary)), size=list(working.model.size))


def verify_pages(package, request):
    seen = set()
    for receipt in request.get('page_receipts', []):
        fields(receipt, 'page content_sha256 proof')
        page, content, proof = receipt['page'], receipt['content_sha256'], receipt['proof']
        if (type(page) is not int or not 0 <= page < len(package['read_boxes']) or page in seen or
                not isinstance(content, str) or not isinstance(proof, str) or not package.get('read_key') or
                not hmac.compare_digest(page_proof(package, request['read_sha256'], page, content), proof)):
            protocol.error('READ_PAGE_INVALID', '读取页回执不属于当前工作包、修订或租约', details={'page': page})
        seen.add(page)
    missing = sorted(set(package.get('required_pages', [])) - seen)
    if missing:
        protocol.error('READ_PAGE_REQUIRED', '请先读取缺少的真实方块页', details={'pages': missing})


def check_scope(package, position):
    details = {'package_id': package['id'], 'pos': list(position)}
    if not any(inside(position, box) for box in package['write_boxes']):
        protocol.error('WRITE_OUT_OF_SCOPE', '补丁坐标超出工作包写区', details=dict(details, write_boxes=package['write_boxes']))
    if any(inside(position, box) for box in package['protected_boxes']):
        protocol.error('PROTECTED_POSITION', '补丁触及上级保护位置', details=details)


def submit_patch(workspace, run, request):
    package = owned(run, request)
    if package['depth'] != 3 or package['status'] != 'in_progress':
        protocol.error('PACKAGE_PHASE_CONFLICT', '只有已领取的第三级工作包可提交候选')
    if request['read_sha256'] != read_fingerprint(package):
        protocol.error('READ_BINDING_CHANGED', '局部读取指纹与当前工作包不一致')
    verify_pages(package, request)
    working = open_baseline(workspace, run)
    patches = request['patches']
    if not 1 <= len(patches) <= min(32768, working.limits['max_written_positions']):
        protocol.error('WRITE_BUDGET', '候选补丁行数超出写入上限或为空')
    completed = request['components']
    for row in completed:
        fields(row, 'id status contacts feet views notes')
    if (len(completed) != len(package['components']) or
            {row['id'] for row in completed} != {row['id'] for row in package['components']} or
            any(row['status'] not in ('complete', 'deferred') for row in completed)):
        raise ValueError('须逐项回传已登记的构件完成情况')
    required = {row['id'] for row in package['components'] if row.get('required', True)}
    missing = [row['id'] for row in completed if row['status'] == 'deferred' and row['id'] in required]
    if missing:
        protocol.error('REQUIRED_COMPONENT_DEFERRED', '必做构件缺少回传', details={'components': missing})
    positions = set()
    for row in patches:
        fields(row, 'pos before after')
        pos = point(row['pos'])
        check_scope(package, pos)
        if pos in positions or row['before'] == row['after']:
            raise ValueError('候选坐标须唯一且须有实际变化')
        for pair in (row['before'], row['after']):
            if (not isinstance(pair, list) or len(pair) != 2 or not isinstance(pair[0], str) or
                    type(pair[1]) is not bool or (pair[0] in AIR_NAMES and pair != ['minecraft:air', False])):
                raise ValueError('补丁值须为 [方块状态, 墙层]，空气为 [minecraft:air, false]')
        positions.add(pos)
    from nbt_composition.change_policy import ChangePolicyError
    try:
        working.patch(patches)
    except ChangePolicyError as exc:
        protocol.error(exc.kind, str(exc), details={'total': exc.total, 'positions': list(exc.positions)[:32]})
    candidate = dict(package_id=package['id'], package_revision=package['revision'], read_sha256=request['read_sha256'],
                     patches=patches, components=completed, evidence=request.get('evidence', []),
                     read_pages=sorted(receipt['page'] for receipt in request.get('page_receipts', [])))
    checksum = protocol.fingerprint('patch_candidate', candidate)
    package.update(status='submitted', candidate=candidate, candidate_sha256=checksum)
    package.pop('lease', None)
    return dict(package_id=package['id'], status='submitted', candidate_sha256=checksum, changed_positions=len(positions))


def dispatch(workspace, run, action, request):
    after_save_lease = (run['phase'] == 'draft_saved' and action in ('claim', 'heartbeat', 'release') and
                        request.get('package_id') == 'root')
    if run['phase'] not in ('baseline_bound', 'review_ready') and not after_save_lease:
        protocol.error('RUN_PHASE_CONFLICT', '当前运行无法变更工作包')
    check_references(workspace, run)
    if action in ('issue', 'reissue'):
        open_baseline(workspace, run)
        return issue_package(workspace, run, request) if action == 'issue' else reissue_package(workspace, run, request)
    if action == 'submit':
        return submit_patch(workspace, run, request)
    package = run['packages'].get(request['package_id'])
    if package is None:
        protocol.error('PACKAGE_NOT_FOUND', '工作包不存在')
    check_revision(package, request['package_revision'])
    if package['status'] not in ('pending', 'in_progress'):
        protocol.error('PACKAGE_PHASE_CONFLICT', '工作包已关闭')
    if action != 'release' and not after_save_lease:
        open_baseline(workspace, run)
    receipt = protocol.lease_action(package, action, request)
    receipt['status'] = 'claimed' if receipt['status'] == 'in_progress' else receipt['status']
    return receipt
