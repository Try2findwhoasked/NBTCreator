"""Check a planned building against the actual state and collision geometry."""
from collections import defaultdict
from math import dist, floor

from nbt_building.planning import PlanningLayout, best_run, cells, contacts, largest_square, result
from nbt_collision import _Space, check_routes, reachable_floor_centers


MAX_REACHABLE_POSES = 80_000


def pose(point, y):
    return (point[0] + .5, y, point[1] + .5)


def crosses_portal(space, crossing, y):
    a, middle, b = (pose(point, y) for point in crossing)
    points = [a, tuple((x + y) * .5 for x, y in zip(a, middle)), middle,
              tuple((x + y) * .5 for x, y in zip(middle, b)), b]
    return space.standing(a) and all(space.move(x, y) for x, y in zip(points, points[1:]))


def attach_layout(plan):
    binding = plan['planning']
    if not isinstance(binding, dict) or set(binding) != {'program', 'layout'}:
        raise ValueError('建筑规划绑定必须包括任务书和布局')
    layout = PlanningLayout(binding['program'], binding['layout'])
    if layout.size != plan['size']:
        raise ValueError('规划任务书与建筑方案的画布不一致')
    stairs = {row['id'] for row in plan['stairs']}
    for key, connection in layout.links.items():
        if 'stair' in connection and connection['stair'] not in stairs:
            raise ValueError(f'跨层连接{key}引用未知楼梯系统')
    return layout


def before_build(plan):
    from nbt_composition.working_model import ModelConflict

    assessment = attach_layout(plan).assess()
    if not assessment['passed']:
        raise ModelConflict('LAYOUT_INVALID', [row for row in assessment['checks'] if not row['passed']])


def assess_geometry(model, planning, binding):
    from itertools import chain

    layout = PlanningLayout(planning['program'], planning['layout'])
    assessed = layout.assess()
    space = _Space(model.model)
    reached, reachability = reachable_floor_centers(model.model, layout.program['entry'],
                                                    space=space, max_poses=MAX_REACHABLE_POSES)
    unknown = bool(space.unknown)
    limited = reachability['search_limit_reached']
    wall_columns = defaultdict(set)
    for x, y, z in model.walls:
        wall_columns[y].add((x, z))
    rows, rooms, route_length = [], {}, 0
    entry = layout.program['entry']
    if 'max_extent' in layout.program:
        blocks = model.model.blocks
        maximum = layout.program['max_extent']
        dimensions = []
        extreme = []
        for axis in range(3):
            if blocks:
                low = min(blocks, key=lambda point: (point[axis], point))
                high = max(blocks, key=lambda point: (point[axis], point))
                dimensions.append(high[axis] - low[axis] + 1)
                if dimensions[-1] > maximum[axis]:
                    extreme.extend((low, high))
            else:
                dimensions.append(0)
        rows.append(result('geometry:massing:extent', 'building_extent', maximum, dimensions,
                           all(actual <= cap for actual, cap in zip(dimensions, maximum)),
                           positions=extreme))
    for level, spec in layout.levels.items():
        if 'envelope' not in spec:
            continue
        allowed = cells(spec['envelope'])
        outside = [point for point in model.model.blocks
                   if spec['feet_y'] <= point[1] < spec['ceiling_y'] and (point[0], point[2]) not in allowed]
        rows.append(result(f'geometry:level:{level}:envelope', 'building_footprint', 0, len(outside),
                           not outside, positions=sorted(outside)[:8], level=level))
    rows.append(result('geometry:entry', 'entry', True, reachability['start_standing'],
                       None if unknown else reachability['start_standing'],
                       positions=[entry], reason='unsupported_collision' if unknown else None))
    walkable, supported = {}, {}
    for key, room in layout.spaces.items():
        level = room['level']
        feet = layout.feet_y(key)
        net = {cell for cell in layout.regions[key] - wall_columns[floor(feet)]
               if space.supported(pose(cell, feet))}
        clear = {cell for cell in net if space.standing(pose(cell, feet))}
        accessible = {cell for cell in clear if pose(cell, feet) in reached}
        walkable[key] = clear
        supported[key] = net
        rooms[key] = dict(net_area=len(net), standable_area=len(clear),
                          reachable_area=len(accessible) if not (unknown or limited) else None)
        bounds = dict(min=room.get('min_area', 1),
                      max=room.get('max_area', model.model.size[0] * model.model.size[2]))
        within = bounds['min'] <= len(net) <= bounds['max']
        prefix = f'geometry:space:{key}:'
        fields = dict(level=level, source=room.get('source'))
        loc = layout.regions[key] - net if len(net) < bounds['min'] else net
        rows.append(result(prefix+'area', 'net_area', bounds, len(net), None if unknown else within,
                           positions=layout.positions(key, loc), **fields,
                           reason='unsupported_collision' if unknown else None))
        if 'min_span' in room:
            measured = largest_square(net)
            rows.append(result(prefix+'span', 'usable_square_span', room['min_span'], measured,
                               None if unknown else measured >= room['min_span'],
                               positions=layout.positions(key, loc), **fields,
                               reason='unsupported_collision' if unknown else None))
        if 'min_headroom' in room:
            height = room['min_headroom']
            inadequate = set()
            for cell in clear:
                x, y, z = pose(cell, feet)
                if not space.clear_box((x - .3, y, z - .3), (x + .3, y + height, z + .3)):
                    inadequate.add(cell)
            rows.append(result(prefix+'headroom', 'headroom', dict(min=height, blocked=0), len(inadequate),
                               None if unknown else bool(clear) and not inadequate,
                               positions=layout.positions(key, inadequate or clear), **fields,
                               reason='unsupported_collision' if unknown else None))
        minimum = room.get('min_reachable_area', 1)
        sufficient = len(accessible) >= minimum
        status = None if unknown or (limited and not sufficient) else sufficient
        rows.append(result(prefix+'access', 'entry_reachability', minimum, len(accessible), status,
                           positions=layout.positions(key, clear or net or layout.regions[key]),
                           reason='unsupported_collision' if unknown else 'search_limit' if status is None else None,
                           **fields))
    for level, mask in layout.voids.items():
        if not mask:
            continue
        feet = layout.levels[level]['feet_y']
        obstruction = {cell for cell in mask - layout.reserved[level] if space.supported(pose(cell, feet))}
        positions = [[x, feet, z] for x, z in sorted(obstruction)[:8]]
        rows.append(result(f'geometry:level:{level}:void', 'floor_void', 0, len(obstruction),
                           None if unknown else not obstruction, positions=positions, level=level,
                           reason='unsupported_collision' if unknown else None))

    def endpoint(key):
        if 'feet' in layout.placements.get(key, {}):
            return layout.feet(key)
        xz = walkable[key]
        return pose(min(xz), layout.feet_y(key)) if xz else layout.feet(key)

    for key, rule in layout.relations.items():
        left, right, kind = rule['from'], rule['to'], rule['kind']
        level = layout.spaces[left]['level']
        fields = dict(level=level, source=rule.get('source'))
        identifier = f'geometry:relation:{key}'
        link = layout.links.get(key, {})
        if kind in ('adjacent', 'wall'):
            allowed = layout.usable[level] - layout.by_level[level]
            if kind == 'wall':
                allowed &= wall_columns[floor(layout.feet_y(left))]
            run = best_run(contacts(supported[left], supported[right], allowed, wall_only=kind == 'wall'))
            width = rule.get('min_width', 1)
            rows.append(result(identifier, kind, width, len(run), None if unknown else len(run) >= width,
                               positions=layout.positions(left, {crossing[1] for crossing in run}), **fields,
                               reason='unsupported_collision' if unknown else None))
            continue
        if kind == 'door':
            lines, opening = layout.portal_runs.get(key, ({}, set()))
            y = layout.feet_y(left)
            verified = {line: {n: crossing for n, crossing in crosses.items()
                             if crossing[1] in opening and crosses_portal(space, crossing, y)}
                        for line, crosses in lines.items()}
            actual = len(best_run(verified))
            expected = rule.get('min_width', 1)
            rows.append(result(identifier, kind, expected, actual, None if unknown else actual >= expected,
                               positions=layout.positions(left, opening), **fields,
                               reason='unsupported_collision' if unknown else None))
            continue
        a, b = ((link.get('from_feet'), link.get('to_feet')) if kind == 'stair'
                else (endpoint(left), endpoint(right)))
        locations = [p for p in (a, b) if p]
        if not a or not b:
            rows.append(result(identifier, kind, True, False, False, positions=locations, **fields,
                               reason='missing_endpoint'))
            continue
        stairs = binding.get('systems', {}).get(link.get('stair'), {}).get('feet', [])
        if link.get('stair') and len(stairs) < 2:
            rows.append(result(identifier, kind, True, False, False, positions=locations, **fields,
                               reason='missing_bound_stair'))
            continue
        if stairs and abs(stairs[-1][1] - a[1]) < abs(stairs[0][1] - a[1]):
            stairs = reversed(stairs)
        stops = list(chain([a], stairs, [b]))
        distances = []
        reason = None
        for start, stop in zip(stops, stops[1:]):
            report = check_routes(model.model, start, [stop], max_poses=MAX_REACHABLE_POSES)
            if not report['passed']:
                reason = ('unsupported_collision' if report['unknown_shapes'] else
                          'search_limit' if report['search_limit_reached'] else 'blocked_route')
                locations = [start, stop]
                break
            path = report['targets'][0]['path']
            distances.append(sum(dist(p, q) for p, q in zip(path, path[1:])))
        distance = round(sum(distances), 3) if reason is None else None
        expected = rule.get('max_length', True)
        passed = (None if reason in ('unsupported_collision', 'search_limit') else
                  reason is None and ('max_length' not in rule or distance <= expected))
        if distance is not None:
            route_length += distance
        rows.append(result(identifier, kind, expected, distance if 'max_length' in rule else reason is None,
                           passed, positions=locations, **fields, reason=reason))
    return dict(assessed, stage='geometry', geometry_sha256=model.model.fingerprint(),
                passed=assessed['passed'] and all(row['passed'] for row in rows),
                layout_checks=assessed['checks'], checks=rows, spaces=rooms,
                metrics=dict(assessed['metrics'], measured_route_length=round(route_length, 3),
                             reachable_poses=reachability['reachable_poses']),
                reachability_complete=not (unknown or limited))
