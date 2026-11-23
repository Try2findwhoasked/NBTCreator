"""Search bounded block-grid variations of a coarse architectural plan."""

from copy import deepcopy
from itertools import product
from math import prod

from nbt_building.plan import _build, fingerprint, resolve, select
from nbt_review.diagnostic_delta import summary
from nbt_runtime.modeling_session import engine_revision_scope


MAX_COMBINATIONS = 24


def index_by_id(plan, field, identifier):
    for index, row in enumerate(plan.get(field, [])):
        if row['id'] == identifier:
            return index
    raise ValueError(f'布局目标不存在 {field}/{identifier}')


def paths_for(plan, target):
    kind, identifier = target['kind'], target['id']
    if ('index' in target) != (kind == 'stop'):
        raise ValueError('只有活动站位需要 index')
    if kind == 'part':
        return [('parts', index_by_id(plan, 'parts', identifier), 'position')]
    if kind == 'stair':
        prefix = ('stairs', index_by_id(plan, 'stairs', identifier), 'operation')
        operation = at(plan, prefix)
        return [(*prefix, key) for key in ('lo', 'hi', 'start', 'end', 'centre') if key in operation]
    if kind == 'stop':
        activity = index_by_id(plan, 'activities', identifier)
        if target['index'] >= len(plan['activities'][activity]['stops']):
            raise ValueError(f'活动站位序号越界 {identifier}/{target["index"]}')
        return [('activities', activity, 'stops', target['index'], 'feet')]
    if kind == 'route-target':
        if identifier not in plan['context']['targets']:
            raise ValueError('布局路线目标不存在 ' + identifier)
        return [('context', 'targets', identifier)]
    if kind == 'review-location':
        return [('review_locations', index_by_id(plan, 'review_locations', identifier), 'position')]
    space = index_by_id(plan, 'spaces', identifier)
    if kind == 'space-extent':
        return [('spaces', space, 'hi')]
    return [
        ('spaces', space, 'lo'),
        ('spaces', space, 'hi'),
        *(('spaces', space, 'samples', index)
          for index in range(len(plan['spaces'][space]['samples']))),
        *(('activities', index, 'stops', stop_index, 'feet')
          for index, activity in enumerate(plan.get('activities', []))
          for stop_index, stop in enumerate(activity['stops']) if stop['space'] == identifier),
    ]


def at(plan, path):
    for key in path:
        plan = plan[key]
    return plan


def check_spaces(plan, areas, adjacency):
    spaces = {room['id']: room for room in plan['spaces']}
    failures = []
    for rule in areas:
        room = spaces[rule['space']]
        area = prod(room['hi'][axis] - room['lo'][axis] + 1 for axis in (0, 2))
        if not rule['minimum'] <= area <= rule['maximum']:
            failures.append(dict(code='SPACE_AREA', space=room['id'], area=area,
                                 minimum=rule['minimum'], maximum=rule['maximum']))
    for rule in adjacency:
        left, right = (spaces[name] for name in rule['spaces'])
        gap = sum(max(0, left['lo'][axis] - right['hi'][axis] - 1,
                      right['lo'][axis] - left['hi'][axis] - 1) for axis in (0, 2))
        if gap > rule['max_gap']:
            failures.append(dict(code='SPACE_GAP', spaces=rule['spaces'], gap=gap, max_gap=rule['max_gap']))
    return failures


def search(workspace, request):
    seed = select(workspace, request)
    resolved = resolve(seed)
    variables = request['variables']
    areas, adjacency = request.get('areas', []), request.get('adjacency', [])
    if prod(len(variable['offsets']) for variable in variables) > MAX_COMBINATIONS:
        raise ValueError(f'布局组合最多 {MAX_COMBINATIONS} 个，请缩小位移范围')
    space_ids = {room['id'] for room in seed['spaces']}
    if any(row['space'] not in space_ids or row['minimum'] > row['maximum'] for row in areas):
        raise ValueError('布局面积条件引用不存在的空间或范围倒置')
    if any(len(set(row['spaces'])) != 2 or not set(row['spaces']) <= space_ids for row in adjacency):
        raise ValueError('布局邻接条件须引用两个不同的现有空间')

    bindings = {}
    occupied_paths = set()
    for variable in variables:
        identifier = variable['id']
        if identifier in bindings or len({tuple(offset) for offset in variable['offsets']}) != len(variable['offsets']):
            raise ValueError('布局变量 ID 或位移重复 ' + identifier)
        paths = []
        for target in variable['targets']:
            for path in paths_for(resolved, target):
                if path in occupied_paths:
                    raise ValueError('多个布局目标会修改同一字段 ' + '/'.join(map(str, path)))
                occupied_paths.add(path)
                paths.append(path)
        bindings[identifier] = [(path, at(resolved, path)) for path in paths]

    attempts, candidates = [], []
    seen = set()
    with engine_revision_scope() as verify_revision:
        for number, offsets in enumerate(product(*(row['offsets'] for row in variables)), start=1):
            shifts = dict(zip(bindings, offsets))
            row = dict(id=f'layout-{number}', offsets=shifts)
            attempts.append(row)
            candidate = deepcopy(seed)
            for name, (dx, dz) in shifts.items():
                if dx or dz:
                    for path, (x, y, z) in bindings[name]:
                        at(candidate, path[:-1])[path[-1]] = [x + dx, y, z + dz]
            try:
                actual = resolve(candidate)
                if failures := check_spaces(actual, areas, adjacency):
                    row.update(status='constraint_failed', issues=failures)
                    continue
                result = _build(workspace, dict(plan=candidate), verify_revision)
            except ValueError as error:
                evidence = dict(ok=False, code=getattr(error, 'code', 'LAYOUT_INVALID'),
                                error=str(error)[:400], conflicts=getattr(error, 'conflicts', []))
                issues, _ = summary('model', evidence)
                details = list(issues.values())[:12]
                for issue in details:
                    del issue['evidence_pointer']
                row.update(status='rejected', code=evidence['code'], issues=details)
                continue
            geometry = result['checks']['model_sha256']
            identity = (geometry, result['plan_sha256'])
            if identity in seen:
                row.update(status='duplicate', model_sha256=geometry)
                continue
            seen.add(identity)
            distance = sum(abs(dx) + abs(dz) for dx, dz in shifts.values())
            row.update(status='passed', model_sha256=geometry, distance=distance)
            candidates.append(dict(row, plan=candidate, plan_sha256=result['plan_sha256']))
        verify_revision()
    candidates.sort(key=lambda row: row['distance'])
    return dict(seed_plan_sha256=fingerprint(seed), attempts=attempts,
                candidates=candidates[:request.get('limit', 3)], passed_count=len(candidates),
                read_only=True, approval_created=False, nbt_exported=False)
