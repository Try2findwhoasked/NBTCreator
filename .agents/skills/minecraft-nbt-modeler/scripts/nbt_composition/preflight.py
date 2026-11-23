"""Compare a managed update against its exact host before selecting a candidate."""
from nbt_assets.components import PlacementBoundsError
from nbt_model import AIR_NAMES
from nbt_composition.working_model import ModelConflict, constraint_context, digest, model_hash


def bounds(points):
    points = iter(points)
    first = next(points, None)
    if first is None:
        return None
    lo, hi = list(first), list(first)
    for point in points:
        for axis, value in enumerate(point):
            lo[axis] = min(lo[axis], value)
            hi[axis] = max(hi[axis], value)
    return dict(lo=lo, hi=hi)


def route_summary(result, required):
    targets = []
    for row in result['targets']:
        target = {key: value for key, value in row.items() if key != 'path'}
        if 'path' in row:
            target.update(path_sha256=digest(row['path']), poses=len(row['path']))
        targets.append(target)
    return dict(passed=result['passed'], required=required, start=result['start'], targets=targets,
                failure=result.get('failure'))


def routes(host, model, instances):
    from nbt_collision import check_routes
    checks = {}
    required = bool(host.context.get('require_routes'))
    if required or host.context.get('start') and host.context.get('targets'):
        for index, (name, result) in enumerate(host._declared_host_routes(model)):
            key = ('main' if index == 0 else 'leg', '', name, index)
            checks[key] = route_summary(result, required)
    for identifier, row in instances.items():
        route = row['compiled'].get('policy', {}).get('routes')
        if route:
            result = check_routes(model, route['start'], route['targets'])
            checks[('instance', identifier, identifier, 0)] = route_summary(result, True)
    return checks


def interfaces(host, model, instances):
    checks = {}
    for identifier, instance in instances.items():
        for item in instance['compiled'].get('objects') or []:
            for name, surface in item.get('interfaces', {}).items():
                checks[(identifier, item['id'], name, '')] = dict(
                    surface=dict(bounds_half=bounds(surface['faces_half']), normal=surface['normal'],
                                 sha256=digest(surface['faces_half'])),
                    checks=[],
                )
    for row in host._assembly_checks(model, instances)['checks']:
        key = (row['instance'], row['object'], row.get('interface', ''), row.get('target') or '')
        checks.setdefault(key, dict(checks=[]))['checks'].append(row)
    return checks


def compare(before, after, names, failed):
    affected = []
    for key in sorted(before.keys() | after.keys()):
        old, new = before.get(key), after.get(key)
        if old != new:
            affected.append(dict(zip(names, key), before=old, after=new))
    failures = [dict(zip(names, key)) for key, value in sorted(after.items()) if failed(value)]
    return dict(status='checked' if before or after else 'not_declared',
                checked_before=len(before), checked_after=len(after), affected=affected, failures=failures)


def describe_error(error):
    return dict(code=getattr(error, 'code', 'UPDATE_INVALID'), message=str(error),
                conflicts=getattr(error, 'conflicts', [])[:32])


def candidate_state_sha256(host, geometry_sha, instances):
    data = {name: {key: value for key, value in instance.items() if key != 'preflight'}
            for name, instance in instances.items()}
    return digest([geometry_sha, data, constraint_context(host.context), host.kind, host._architecture, host.limits])


def evaluate_update(host, identifier, recipe, transform):
    """Stage the exact update once. Return geometry for adoption only if permitted."""
    if identifier not in host.instances:
        raise ValueError('受管实例不存在')
    host._unchanged()
    previous = host.instances[identifier]
    old_bounds = bounds(row['pos'] for row in previous['baseline'] if row['after'][0] not in AIR_NAMES)
    source_path = host.source
    if source_path and source_path.is_relative_to(host.workspace):
        source_path = source_path.relative_to(host.workspace)
    report = dict(
        schema_version=1, identifier=identifier, applicable=False, model_modified=False, approval_created=False,
        source=dict(path=source_path.as_posix() if source_path else None, sha256=host.source_sha256,
                    revision=host.parent_revision, working_sha256=host._content_token(), limits=dict(host.limits)),
        canvas_size=list(host.model.size),
        instance_bounds=dict(before=old_bounds, after=None),
        placement_bounds=dict(before=previous['compiled'].get('placement_bounds'), after=None),
        host_bounds=dict(before=bounds(host.model.blocks), after=None),
        routes=dict(status='not_checked'), interfaces=dict(status='not_checked'), problems=[],
    )
    try:
        _, proposed, values, edits, conflicts = host._stage_update(identifier, recipe, transform)
        report['placement_bounds']['after'] = proposed['compiled']['placement_bounds']
        report['instance_bounds']['after'] = bounds(pos for pos, value in values.items() if value[0] not in AIR_NAMES)
        report['proposal'] = dict(
            transform=proposed['transform'], recipe_sha256=digest(proposed['recipe']),
            content_sha256=proposed['compiled']['content_sha256'], engine_sha256=proposed['compiled']['engine_sha256'],
        )
        if conflicts:
            raise ModelConflict('INSTANCE_EDIT_CONFLICT', conflicts)
        staged = host._stage_edits(edits)
    except PlacementBoundsError as error:
        report['placement_bounds']['after'] = dict(lo=error.lo, hi=error.hi)
        report['problems'].append(dict(code='PLACEMENT_OUT_OF_BOUNDS', message=str(error)))
        return report, None, None
    except ValueError as error:
        report['problems'].append(describe_error(error))
        return report, None, None

    model, walls, difference, _ = staged
    instances = host.instances | {identifier: proposed}
    report['host_bounds']['after'] = bounds(model.blocks)
    report['changes'] = difference
    report['candidate_model_sha256'] = model_hash(model, walls)
    report['candidate_state_sha256'] = candidate_state_sha256(host, report['candidate_model_sha256'], instances)
    report['routes'] = compare(routes(host, host.model, host.instances), routes(host, model, instances),
                               ('kind', 'instance', 'name', 'index'), lambda result: result['required'] and not result['passed'])
    report['interfaces'] = compare(
        interfaces(host, host.model, host.instances), interfaces(host, model, instances),
        ('instance', 'object', 'interface', 'target'), lambda item: any(not row['passed'] for row in item['checks']),
    )
    if report['routes']['failures']:
        report['problems'].append(dict(code='ROUTE_FAILED', affected=report['routes']['failures']))
    if report['interfaces']['failures']:
        report['problems'].append(dict(code='ASSEMBLY_INVALID', affected=report['interfaces']['failures']))
    if not report['routes']['failures']:
        try:
            host._instance_policy(model, walls, instances)
        except ValueError as error:
            report['problems'].append(describe_error(error))
    host._unchanged()
    if report['problems']:
        return report, None, None
    report['applicable'] = True
    report['preflight_sha256'] = digest(report)
    return report, staged, instances
