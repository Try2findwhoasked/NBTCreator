"""Search bounded plan offsets or evaluate authored space-graph alternatives."""

from copy import deepcopy
from itertools import product
from math import prod

from nbt_building import layout_graph
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


def offsets(seed, resolved, variables):
    if prod(len(variable['offsets']) for variable in variables) > MAX_COMBINATIONS:
        raise ValueError(f'布局组合最多 {MAX_COMBINATIONS} 个，请缩小位移范围')
    bindings, occupied_paths = {}, set()
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

    for number, choices in enumerate(product(*(row['offsets'] for row in variables)), start=1):
        shifts = dict(zip(bindings, choices))
        candidate = deepcopy(seed)
        for name, (dx, dz) in shifts.items():
            if dx or dz:
                for path, (x, y, z) in bindings[name]:
                    at(candidate, path[:-1])[path[-1]] = [x + dx, y, z + dz]
        yield dict(id=f'layout-{number}', offsets=shifts), candidate


def check_spaces(plan, areas, adjacency):
    spaces = layout_graph.indexed(plan['spaces'])
    failures = []
    for rule in areas:
        room = spaces[rule['space']]
        area = prod(room['hi'][axis] - room['lo'][axis] + 1 for axis in (0, 2))
        if not rule['minimum'] <= area <= rule['maximum']:
            failures.append(dict(code='SPACE_AREA', space=room['id'], area=area, lo=room['lo'], hi=room['hi'],
                                 minimum=rule['minimum'], maximum=rule['maximum'],
                                 activity_ids=layout_graph.activity_ids(plan, spaces=[room['id']])))
    for rule in adjacency:
        left, right = (spaces[name] for name in rule['spaces'])
        gap = sum(max(0, left['lo'][axis] - right['hi'][axis] - 1,
                      right['lo'][axis] - left['hi'][axis] - 1) for axis in (0, 2))
        if gap > rule['max_gap']:
            failures.append(dict(code='SPACE_GAP', spaces=rule['spaces'], gap=gap, max_gap=rule['max_gap'],
                                 bounds=[dict(lo=room['lo'], hi=room['hi']) for room in (left, right)],
                                 activity_ids=layout_graph.activity_ids(plan, spaces=rule['spaces'])))
    return failures


def rejection(error, plan):
    code = getattr(error, 'code', 'LAYOUT_INVALID')
    receipt = dict(ok=False, code=code, error=str(error)[:400], conflicts=getattr(error, 'conflicts', []))
    issues, _ = summary('model', receipt)
    if code != 'DESIGN_INVALID':
        checks = getattr(error, 'quality', {}).get('evidence', {}).get('checks', [])
        if checks:
            more, _ = summary('model', dict(ok=False, code='DESIGN_INVALID', conflicts=checks))
            issues.update(more)
    activities = layout_graph.indexed(plan.get('activities', []))
    result = []
    for raw in list(issues.values())[:12]:
        issue = {key: value for key, value in raw.items() if key != 'evidence_pointer'}
        evidence = issue['evidence']
        feet = evidence.get('feet') or evidence.get('end') or evidence.get('start')
        related = ([issue['scope']] if issue['scope'] in activities else
                   layout_graph.activity_ids(plan, feet=feet))
        if related:
            issue['activity_ids'] = related
        result.append(issue)
    return dict(status='rejected', code=code, issues=result, issue_count=len(issues))


def evaluate(workspace, candidate, resolved, areas, adjacency, verify_revision, *, graph=None, boundary=None):
    entries, edges = {}, []
    failures = check_spaces(resolved, areas, adjacency)
    if graph is not None:
        graph_failures, edges = layout_graph.check_graph(resolved, boundary, graph['edges'])
        failures.extend(graph_failures)
    if failures:
        return dict(status='constraint_failed', issues=failures)
    if graph is not None:
        entries = layout_graph.bind_entries(candidate, resolved)
    result = _build(workspace, dict(plan=candidate), verify_revision)
    row = dict(status='passed', model_sha256=result['checks']['model_sha256'], plan_sha256=result['plan_sha256'])
    if graph is not None:
        row['circulation'] = layout_graph.collision_evidence(result['checks'], edges, entries)
    return row


def search(workspace, request):
    if ('variables' in request) == ('graph' in request):
        raise ValueError('布局请求须选择 variables 或 graph')
    seed = select(workspace, request)
    resolved_seed = resolve(seed)
    areas, adjacency = request.get('areas', []), request.get('adjacency', [])
    space_ids = layout_graph.indexed(resolved_seed['spaces']).keys()
    if any(row['space'] not in space_ids or row['minimum'] > row['maximum'] for row in areas):
        raise ValueError('布局面积条件引用不存在的空间或范围倒置')
    if any(len(set(row['spaces'])) != 2 or not set(row['spaces']) <= space_ids for row in adjacency):
        raise ValueError('布局邻接条件须引用两个不同的现有空间')
    graph = request.get('graph')
    boundary = None
    if graph is None:
        variations = offsets(seed, resolved_seed, request['variables'])
    else:
        if adjacency:
            raise ValueError('空间图在 graph.edges 声明邻接关系')
        layout_graph.validate_graph(resolved_seed, graph)
        boundary = layout_graph.footprint(resolved_seed)
        variations = ((dict(id=variant['id']), variant) for variant in graph['variants'])

    attempts, candidates, seen = [], [], set()
    with engine_revision_scope() as verify_revision:
        for row, variation in variations:
            attempts.append(row)
            actual = resolved_seed
            try:
                candidate = variation if graph is None else layout_graph.apply_variant(seed, variation)
                if graph is not None:
                    if issues := layout_graph.check_canvas(resolved_seed, variation):
                        row.update(status='constraint_failed', issues=issues)
                        continue
                actual = resolve(candidate)
                row.update(evaluate(workspace, candidate, actual, areas, adjacency, verify_revision,
                                        graph=graph, boundary=boundary))
            except ValueError as error:
                row.update(rejection(error, actual))
                continue
            if row['status'] != 'passed':
                continue
            layout_sha = row['plan_sha256']
            if graph is not None:
                extents = [{key: room[key] for key in ('id', 'lo', 'hi', 'feet_y')} for room in actual['spaces']]
                layout_sha = fingerprint([extents, row['circulation']])
            identity = (row['model_sha256'], layout_sha)
            if identity in seen:
                row['status'] = 'duplicate'
                continue
            seen.add(identity)
            if graph is None:
                row['distance'] = sum(abs(dx) + abs(dz) for dx, dz in row['offsets'].values())
            candidates.append(dict(row, plan=candidate))
        verify_revision()
    if graph is None:
        candidates.sort(key=lambda row: row['distance'])
    return dict(mode='graph' if graph is not None else 'offsets', seed_plan_sha256=fingerprint(seed),
                attempts=attempts, candidates=candidates[:request.get('limit', 3)], passed_count=len(candidates),
                read_only=True, approval_created=False, nbt_exported=False)
