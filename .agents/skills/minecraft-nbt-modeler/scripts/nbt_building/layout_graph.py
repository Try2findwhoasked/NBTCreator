"""Bind an authored space graph and coarse placements to a building plan."""

from copy import deepcopy
from itertools import product

from nbt_building.construction_systems import polygon_contains
from nbt_building.plan import fingerprint


def indexed(rows):
    return {row['id']: row for row in rows}


def footprint(plan):
    """Project the fixed envelope volumes onto the XZ block grid."""
    volumes = plan.get('envelope', {}).get('volumes', [])
    if not volumes:
        return None
    return {
        (x, z) for volume in volumes
        for x in range(max(0, volume['lo_xz'][0]), min(plan['size'][0], volume['hi_xz'][0] + 1))
        for z in range(max(0, volume['lo_xz'][1]), min(plan['size'][2], volume['hi_xz'][1] + 1))
        if not volume.get('polygon') or polygon_contains(x + .5, z + .5, volume['polygon'])
    }


def activity_ids(plan, *, spaces=(), feet=None):
    return [
        row['id'] for row in plan.get('activities', [])
        if any(stop['space'] in spaces or stop['feet'] == feet for stop in row['stops'])
    ]


def validate_graph(seed, graph):
    if not isinstance(seed['context']['targets'], dict):
        raise ValueError('空间图种子的 context.targets 需要具名目标')
    rooms = indexed(seed['spaces'])
    activities = indexed(seed.get('activities', []))
    for key in ('edges', 'variants'):
        if len(indexed(graph[key])) != len(graph[key]):
            raise ValueError(f'空间图 {key} ID 重复')
    for edge in graph['edges']:
        left, right = edge['spaces']
        if left == right or not {left, right} <= rooms.keys():
            raise ValueError('空间图边须引用两个不同的现有空间：' + edge['id'])
        if edge['kind'] == 'adjacent':
            if {'activity', 'segment'} & edge.keys():
                raise ValueError('同层邻接边含跨层字段：' + edge['id'])
        else:
            activity = activities.get(edge.get('activity'))
            segment = edge.get('segment')
            if ('max_gap' in edge or activity is None or segment is None
                    or segment + 1 >= len(activity['stops'])):
                raise ValueError('跨层边须引用已有活动及路段：' + edge['id'])
            if [stop['space'] for stop in activity['stops'][segment:segment + 2]] != edge['spaces']:
                raise ValueError('跨层边空间顺序须与活动路段一致：' + edge['id'])


def changes(rows, existing, key):
    seen = set()
    for row in rows:
        identifier = row[key]
        if identifier in seen or identifier not in existing:
            raise ValueError(f'候选放置引用不存在或重复：{key}/{identifier}')
        seen.add(identifier)
        yield identifier, {name: value for name, value in row.items() if name != key}


def apply_variant(seed, variant):
    plan = deepcopy(seed)
    for section in ('spaces', 'parts', 'stairs'):
        by_id = indexed(plan[section])
        for identifier, patch in changes(variant.get(section, []), by_id, 'id'):
            row = by_id[identifier]
            if section == 'stairs':
                row['operation'].update(patch)
            else:
                row.update(patch)
    targets = plan['context']['targets']
    for identifier, patch in changes(variant.get('route_targets', []), targets, 'id'):
        targets[identifier] = patch['feet']
    activities = indexed(plan.get('activities', []))
    seen = set()
    for row in variant.get('stops', []):
        identifier, index = row['activity'], row['index']
        if (identifier, index) in seen or identifier not in activities or index >= len(activities[identifier]['stops']):
            raise ValueError(f'候选活动站位不存在或重复：{identifier}/{index}')
        seen.add((identifier, index))
        activities[identifier]['stops'][index]['feet'] = row['feet']
    return plan


def check_canvas(seed, variant):
    """Localize patched bounds before plan resolution can reject them."""
    rooms = indexed(seed['spaces'])
    issues = []
    for patch in variant.get('spaces', []):
        identifier = patch['id']
        original = rooms[identifier]
        lo, hi = (patch.get(key, original[key]) for key in ('lo', 'hi'))
        if not all(0 <= a <= b < n for a, b, n in zip(lo, hi, seed['size'])) or (
                (lo[1], hi[1]) != (original['lo'][1], original['hi'][1])):
            issues.append(dict(code='SPACE_BOUNDS', space=identifier, lo=lo, hi=hi,
                               size=seed['size'], fixed_y=[original['lo'][1], original['hi'][1]],
                               activity_ids=activity_ids(seed, spaces=[identifier])))
    return issues


def side_gap(left, right):
    """Measure a gap only across a shared horizontal side, with positive overlap."""
    gaps = [max(left['lo'][i] - right['hi'][i], right['lo'][i] - left['hi'][i]) for i in (0, 2)]
    if (gaps[0] > 0) == (gaps[1] > 0):
        return None
    return max(gaps) - 1


def check_graph(plan, boundary, edges):
    rooms = indexed(plan['spaces'])
    activities = indexed(plan.get('activities', []))
    failures, evidence = [], []
    for room in rooms.values():
        if boundary is None:
            continue
        cells = product(range(room['lo'][0], room['hi'][0] + 1), range(room['lo'][2], room['hi'][2] + 1))
        outside = next((cell for cell in cells if cell not in boundary), None)
        if outside is not None:
            failures.append(dict(code='SPACE_OUTSIDE_FOOTPRINT', space=room['id'], lo=room['lo'], hi=room['hi'],
                                 position=[outside[0], room['feet_y'], outside[1]],
                                 activity_ids=activity_ids(plan, spaces=[room['id']])))
    for activity in activities.values():
        for index, stop in enumerate(activity['stops']):
            room = rooms[stop['space']]
            if not all(a <= coordinate < b + 1 for a, b, coordinate in zip(room['lo'], room['hi'], stop['feet'])):
                failures.append(dict(code='STOP_OUTSIDE_SPACE', space=room['id'], stop_index=index,
                                     position=stop['feet'], lo=room['lo'], hi=room['hi'],
                                     activity_ids=[activity['id']]))
    for edge in edges:
        left, right = (rooms[name] for name in edge['spaces'])
        levels = [left['feet_y'], right['feet_y']]
        row = dict(edge, levels=levels)
        if edge['kind'] == 'adjacent':
            gap = side_gap(left, right)
            maximum = edge.get('max_gap', 0)
            if levels[0] != levels[1] or gap is None or gap > maximum:
                failures.append(dict(row, code='SPACE_ADJACENCY', gap=gap, max_gap=maximum,
                                     bounds=[dict(lo=room['lo'], hi=room['hi']) for room in (left, right)],
                                     activity_ids=activity_ids(plan, spaces=edge['spaces'])))
            else:
                evidence.append(dict(row, gap=gap, max_gap=maximum))
        else:
            stops = activities[edge['activity']]['stops'][edge['segment']:edge['segment'] + 2]
            feet = [stop['feet'] for stop in stops]
            if levels[0] == levels[1] or [pose[1] for pose in feet] != levels:
                failures.append(dict(row, code='VERTICAL_LEVELS', feet=feet, activity_ids=[edge['activity']]))
            else:
                evidence.append(row)
    return failures, evidence


def bind_entries(plan, resolved):
    """Require the existing host collision pass to reach each first activity stop."""
    names = {}
    targets = plan['context']['targets']
    for activity in resolved.get('activities', []):
        identifier, feet = activity['id'], activity['stops'][0]['feet']
        matches = [key for key, pose in resolved['context']['targets'].items() if pose == feet]
        if matches:
            names[identifier] = matches[0]
            continue
        key = 'layout-entry-' + identifier
        while key in targets and targets[key] != feet:
            key += '-'
        targets[key] = feet
        names[identifier] = key
    return names


def witness(report, target):
    path = target['path']
    return dict(start=report['start'], end=target['feet'], steps=len(path) - 1,
                path_sha256=fingerprint(path))


def collision_evidence(checks, edges, entries):
    host = checks['whole_model']['routes']
    destinations = {row['name']: row for row in host['targets']}
    rows = checks['architecture']['checks']
    activities = {
        row['id']: dict(
            segments=[witness(segment['report'], segment['report']['targets'][0]) for segment in row['segments']],
            use_faces=row['use_faces'],
        )
        for row in rows if row['kind'] == 'activity_routes'
    }
    return dict(
        entry_routes={name: witness(host, destinations[target]) for name, target in entries.items()},
        activities=activities,
        edges=[dict(edge, route=activities[edge['activity']]['segments'][edge['segment']])
               if edge['kind'] == 'vertical' else edge for edge in edges],
        stairs=[dict(id=row['id'], passed=row['passed']) for row in rows if row['kind'] == 'stair_segments'],
    )
