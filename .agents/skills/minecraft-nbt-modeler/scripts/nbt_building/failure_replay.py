"""Rebuild plan subsets against one passing, immutable building version."""
from copy import deepcopy
from itertools import combinations
from pathlib import Path

from nbt_building import plan, workflow
from nbt_building.quality import BLOCKING_CODES, route_state
from nbt_composition.object_scene import atomic
from nbt_composition.working_model import ModelConflict, verify_version
from nbt_project.history import file_hash
from nbt_project.prompts import digest, encode, inside, relative
from nbt_project.web_paths import project_paths
from nbt_runtime.modeling_session import ModellingSession, canonical, engine_revision


FIXED_FIELDS = {'schema_version', 'size', 'context'}
ROW_FIELDS = {'parts', 'stairs', 'connections', 'rules', 'spaces', 'activities',
              'views', 'requirements', 'review_locations'}
DETERMINATE_NEGATIVES = {'pass', 'different_failure'}
REPLAY_ERRORS = (ValueError, OSError, TypeError, KeyError)


def deltas(baseline, failed):
    """Keep ID-stable rows separate when doing so preserves array ordering."""
    for field in sorted(baseline.keys() | failed.keys()):
        before, after = baseline.get(field), failed.get(field)
        if plan.fingerprint(before) == plan.fingerprint(after) and (field in baseline) == (field in failed):
            continue
        if (field in ROW_FIELDS and before is not None and after is not None
                and [row['id'] for row in before] == [row['id'] for row in after]):
            for old, new in zip(before, after):
                if plan.fingerprint(old) != plan.fingerprint(new):
                    yield dict(id=f"{field}.{old['id']}", edits=[dict(field=field, id=old['id'], value=new)])
        else:
            edit = dict(field=field)
            if field in failed:
                edit['value'] = after
            yield dict(id=field, edits=[edit])


def validate_groups(baseline, groups):
    fields = plan.contract()['plan']['properties'].keys() - FIXED_FIELDS
    ids = set()
    edited = {}
    for group in groups:
        if group['id'] in ids:
            raise ValueError('回放差分组 ID 重复：' + group['id'])
        ids.add(group['id'])
        for edit in group['edits']:
            field, row_id = edit['field'], edit.get('id')
            if field not in fields:
                raise ValueError('回放差分不可修改此方案字段：' + field)
            seen = edited.setdefault(field, set())
            if row_id in seen or None in seen or (row_id is None and seen):
                raise ValueError('回放差分的修改位置重叠：' + field)
            seen.add(row_id)
            if row_id is None:
                if 'value' not in edit and field not in baseline:
                    raise ValueError('回放差分删除的字段不存在：' + field)
            elif (field not in ROW_FIELDS or not any(row['id'] == row_id for row in baseline.get(field, []))
                  or not isinstance(edit.get('value'), dict) or edit['value'].get('id') != row_id):
                raise ValueError('回放差分须按原 ID 替换完整记录：' + field + '.' + row_id)


def assemble(baseline, groups):
    candidate = deepcopy(baseline)
    for group in groups:
        for edit in group['edits']:
            field = edit['field']
            if 'id' in edit:
                rows = candidate[field]
                index = next(i for i, row in enumerate(rows) if row['id'] == edit['id'])
                rows[index] = deepcopy(edit['value'])
            elif 'value' in edit:
                candidate[field] = deepcopy(edit['value'])
            else:
                del candidate[field]
    return candidate


def scope(candidate, criterion):
    activity = next((row for row in candidate.get('activities', [])
                     if row['id'] == criterion['activity']), None)
    if activity is None:
        raise ValueError('回放活动缺失：' + criterion['activity'])
    stops = activity['stops']
    index = criterion['index']
    if criterion['kind'] == 'route_segment':
        if index + 1 >= len(stops):
            raise ValueError('回放活动缺少所选路段')
        location = dict(from_space=stops[index]['space'], to_space=stops[index + 1]['space'])
    else:
        if index >= len(stops) or 'use_face' not in stops[index]:
            raise ValueError('回放活动缺少所选操作面')
        use = stops[index]['use_face']
        location = dict(space=stops[index]['space'], part=use['part'],
                        object=use.get('object', 'body'), interface=use['interface'])
        if any(location[key] != criterion.get(key, 'body') for key in ('part', 'object', 'interface')):
            raise ValueError('回放活动的操作面已改变')
    return dict(spaces=[stop['space'] for stop in stops], location=location)


def route_endpoints(candidate, criterion):
    activity = next(row for row in candidate['activities'] if row['id'] == criterion['activity'])
    start, end = activity['stops'][criterion['index']:criterion['index'] + 2]
    return dict(start=start['feet'], end=end['feet'])


def observe(checks, prefix, criterion):
    for i, activity in enumerate(checks):
        if activity.get('kind') != 'activity_routes' or activity['id'] != criterion['activity']:
            continue
        is_route = criterion['kind'] == 'route_segment'
        collection, index_field = ('segments', 'index') if is_route else ('use_faces', 'stop_index')
        for j, item in enumerate(activity[collection]):
            if item[index_field] != criterion['index']:
                continue
            if is_route:
                route = item['report']
                state = route_state(route)
                target, = route['targets']
                reason = ('invalid_start_pose' if state == 'blocked' and not route['start_standing']
                          else target.get('reason'))
                evidence = dict(start=route['start'], end=target['feet'], space=target['name'],
                                geometry_sha256=route['geometry_sha256'])
            else:
                reason = item.get('reason')
                state = ('pass' if item['passed'] else 'pending' if reason == 'missing_or_unverified_interface'
                         else 'blocked')
                evidence = {key: item[key] for key in ('part', 'interface', 'feet', 'face', 'distance', 'plane',
                                                       'height', 'max_distance') if key in item}
                evidence['object'] = item.get('object', 'body')
            return dict(state=state, reason=reason, evidence=evidence, pointer=f'{prefix}/{i}/{collection}/{j}')
    return None


def error_receipt(error):
    receipt = dict(ok=False, code=getattr(error, 'code', 'ARCHITECT_INVALID'), error=str(error),
                   conflicts=getattr(error, 'conflicts', []))
    if hasattr(error, 'quality'):
        receipt['quality'] = error.quality
    return receipt


def evaluate(workspace, revision, candidate, criterion, location, failed_endpoints):
    try:
        candidate = plan.normalize(candidate)
        if scope(candidate, criterion) != location:
            raise ValueError('回放活动的有序空间或所选检查位置已改变')
        receipt = workflow.dispatch(workspace, 'plan-build', dict(revision, plan=candidate))
        checks = receipt['checks']['architecture']['checks']
        observed = observe(checks, '/checks/architecture/checks', criterion)
        result = dict(status='pass', plan_sha256=receipt['plan_sha256'],
                      model_sha256=receipt['checks']['model_sha256'], observation=observed)
        return result, receipt
    except REPLAY_ERRORS as error:
        receipt = error_receipt(error)
        code = receipt['code']
        observed = None
        if code in BLOCKING_CODES:
            checks = receipt.get('quality', {}).get('evidence', {}).get('checks', [])
            observed = observe(checks, '/quality/evidence/checks', criterion)
            if observed is None and code == 'DESIGN_INVALID':
                observed = observe(receipt['conflicts'], '/conflicts', criterion)
        status = 'unreplayable'
        if observed and observed['state'] in ('blocked', 'pass'):
            matches = observed['state'] == 'blocked' and observed['reason'] == criterion['reason']
            if matches and failed_endpoints:
                matches = all(observed['evidence'][key] == feet for key, feet in failed_endpoints.items())
            status = 'same_failure' if matches else 'different_failure'
        result = dict(status=status, code=code, observation=observed, plan_sha256=plan.fingerprint(candidate))
        if not getattr(error, 'conflicts', None):
            result['detail'] = str(error)
        return result, receipt


def reduce_groups(full, check):
    """First drop chunks, then certify against every proper subset still in scope."""
    best = full
    partitions = 2
    while len(best) >= partitions:
        for i in range(partitions):
            lo, hi = i * len(best) // partitions, (i + 1) * len(best) // partitions
            candidate = best[:lo] + best[hi:]
            result = check(candidate)
            if result is None:
                return best
            if result['status'] == 'same_failure':
                best = candidate
                partitions = max(2, partitions - 1)
                break
        else:
            if partitions == len(best):
                break
            partitions = min(len(best), partitions * 2)

    # A multi-group removal may reproduce a failure even when every single
    # removal passes. Try smaller subsets while budget permits.
    while True:
        for candidate in proper_subsets(best):
            result = check(candidate)
            if result is None:
                return best
            if result['status'] == 'same_failure':
                best = candidate
                break
        else:
            return best


def proper_subsets(groups):
    for size in range(len(groups)):
        yield from combinations(groups, size)


def coverage(best, attempts):
    remaining = set(best)
    relevant = [row for indices, row in attempts.items() if len(indices) < len(best) and remaining.issuperset(indices)]
    definitive = [row for row in relevant if row['status'] in DETERMINATE_NEGATIVES]
    single_removals = sum(len(row['groups']) == len(best) - 1 for row in definitive)
    total = (1 << len(best)) - 1
    return dict(total_proper_subsets=str(total), checked_proper_subsets=len(relevant),
                determinate_proper_subsets=len(definitive), unresolved_proper_subsets=len(relevant) - len(definitive),
                single_removal_minimal=single_removals == len(best), inclusion_minimal=len(definitive) == total)


def output_path(workspace, name):
    plan.root(workspace)
    base = workspace / 'nbt_models/_workspaces/failure_replays'
    output = inside(workspace, base / name)
    if output.parent != base or any((parent / 'model-version.json').is_file() for parent in output.parents):
        raise ValueError('回放包路径须位于当前工作区的独立回放目录')
    if output.exists():
        raise ValueError('回放包目录已存在：' + str(output))
    return output


def publish(workspace, output, replay, report, receipts):
    output.mkdir(parents=True, exist_ok=False)
    files = {}
    for name, value in dict(receipts, replay=replay).items():
        raw = (canonical(value) + '\n').encode('utf8') if name == 'replay' else encode(value)
        file = output / f'{name}.json'
        with file.open('xb') as stream:
            stream.write(raw)
        files[name] = dict(path=file.name, sha256=digest(raw))
    report = dict(report, files=files)
    raw = encode(report)
    atomic(output / 'report.json', raw)
    return dict(report, bundle=dict(path=relative(workspace, output), report_sha256=digest(raw)))


def run(workspace, request):
    output = output_path(workspace, request['output']) if 'output' in request else None
    budget = request['max_checks']
    revision = {key: request[key] for key in ('source', 'source_sha256', 'expected_plan_sha256')}
    criterion = request['failure']
    report = dict(schema_version=1, status='unreplayable', max_checks=budget,
                  baseline_checks=0, candidate_checks=0, checks=[], remaining_groups=None,
                  approval_created=False, asset_written=False, nbt_exported=False)
    try:
        with ModellingSession(workspace):
            return replay(workspace, request, revision, criterion, report, output)
    except REPLAY_ERRORS as error:
        report.update(status='unreplayable', error=error_receipt(error), remaining_groups=None)
        return report


def replay(workspace, request, revision, criterion, report, output):
    if ('groups' in request) == ('failed_plan' in request):
        raise ValueError('回放须选择失败方案 failed_plan 或受控差分 groups')
    source = inside(workspace, revision['source'])
    revision['source'] = relative(workspace, source)
    manifest = project_paths(source)['version'] / 'model-version.json'
    if file_hash(source) != revision['source_sha256']:
        raise ModelConflict('STALE_SOURCE', [dict(source=revision['source'])])
    version_hash = file_hash(manifest)
    source_request = {key: revision[key] for key in ('source', 'source_sha256')}
    report['baseline_checks'] += 1
    baseline_receipt = workflow.dispatch(workspace, 'plan-check', source_request)
    if baseline_receipt['plan_sha256'] != revision['expected_plan_sha256']:
        raise ValueError('回放基线方案指纹与制作源不符')
    baseline = baseline_receipt['plan']
    validation = baseline_receipt['validation']
    if validation['phase'] != 'opened':
        raise ValueError('回放基线必须是已开洞并通过检查的建筑制作版')
    location = scope(baseline, criterion)
    observed = observe(validation['architecture']['checks'], '/validation/architecture/checks', criterion)
    if not observed or observed['state'] != 'pass':
        raise ValueError('回放基线未通过所选活动检查')

    if 'failed_plan' in request:
        failed = plan.normalize(request['failed_plan'])
        groups = list(deltas(baseline, failed))
    else:
        groups = request['groups']
    if not 1 <= len(groups) <= 128:
        raise ValueError('回放须包含 1 至 128 个方案差分组')
    validate_groups(baseline, groups)
    full = tuple(range(len(groups)))
    failed = plan.normalize(assemble(baseline, groups))
    failed_hash = plan.fingerprint(failed)
    if failed_hash == revision['expected_plan_sha256']:
        raise ValueError('回放差分未改变建筑方案')
    if scope(failed, criterion) != location:
        raise ValueError('原始失败方案改变了回放活动的有序空间或所选检查位置')
    failed_endpoints = route_endpoints(failed, criterion) if criterion['kind'] == 'route_segment' else None
    replay_request = dict(revision, failure=criterion, groups=groups, max_checks=request['max_checks'])
    binding = dict(revision, source_version_sha256=version_hash, baseline_model_sha256=validation['model_sha256'],
                   failed_plan_sha256=failed_hash, groups_sha256=plan.fingerprint(groups),
                   failure=criterion, scope=location, max_checks=request['max_checks'],
                   engine_sha256=plan.fingerprint(engine_revision()))
    if failed_endpoints:
        binding['route_endpoints'] = failed_endpoints
    binding_sha = plan.fingerprint(binding)
    report.update(binding=binding, binding_sha256=binding_sha, group_ids=[group['id'] for group in groups])
    if request.get('expected_binding_sha256', binding_sha) != binding_sha:
        raise ValueError('回放包绑定不符，源版本、方案、差分、判据、预算或引擎已变化')

    attempts = {}
    receipts = {'baseline-check': baseline_receipt}
    budget_exhausted = False

    def check(indices):
        nonlocal budget_exhausted
        if indices in attempts:
            return attempts[indices]
        if len(attempts) >= report['max_checks']:
            budget_exhausted = True
            return None
        selected = [groups[i] for i in indices]
        candidate = assemble(baseline, selected)
        result, receipt = evaluate(workspace, revision, candidate, criterion, location, failed_endpoints)
        result.update(check=len(attempts) + 1, groups=[group['id'] for group in selected])
        attempts[indices] = result
        report['checks'].append(result)
        report['candidate_checks'] += 1
        if not indices:
            receipts['baseline-rebuild'] = receipt
        if indices == full:
            receipts['original'] = receipt
        if result['status'] == 'same_failure':
            receipts['reduced'] = receipt
        return result

    rebuilt = check(())
    if rebuilt.get('model_sha256') != validation['model_sha256'] or rebuilt['status'] != 'pass':
        report['detail'] = '方案零差分重建未通过，或与固定基线制作源的方块与墙层不一致'
    elif (initial := check(full)) is not None:
        report.update(status=initial['status'], original_check=initial['check'])
        if initial['status'] == 'same_failure':
            best = reduce_groups(full, check)
            report.update(remaining_groups=attempts[best]['groups'],
                          reduced_check=attempts[best]['check'], minimality=coverage(best, attempts))
    if budget_exhausted:
        report['status'] = 'budget_exhausted'
    verify_version(manifest.parent)
    if file_hash(source) != revision['source_sha256'] or file_hash(manifest) != version_hash:
        raise ModelConflict('STALE_SOURCE', [dict(source=revision['source'])])
    report['trace_sha256'] = plan.fingerprint(report['checks'])
    if output:
        try:
            return publish(workspace, output, dict(replay_request, expected_binding_sha256=binding_sha),
                           report, receipts)
        except OSError as error:
            report['bundle_error'] = error_receipt(error)
    return report
