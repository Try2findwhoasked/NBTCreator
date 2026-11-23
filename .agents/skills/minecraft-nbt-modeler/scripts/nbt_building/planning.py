"""Data-only planning program and integer floor layouts for whole buildings."""
from collections import defaultdict, deque
from math import floor

from nbt_agent.structure import _schema
from nbt_building.plan import fingerprint
from nbt_runtime.catalog import catalog


MAX_RASTER_CELLS = 500_000
CARDINAL = ((1, 0), (0, 1), (-1, 0), (0, -1))


def index(rows, label):
    indexed = {row['id']: row for row in rows}
    if len(indexed) != len(rows):
        raise ValueError(f'{label}ID重复')
    return indexed


def box_area(box):
    return (box['hi'][0] - box['lo'][0] + 1) * (box['hi'][1] - box['lo'][1] + 1)


def cells(boxes):
    return {
        (x, z)
        for box in boxes
        for x in range(box['lo'][0], box['hi'][0] + 1)
        for z in range(box['lo'][1], box['hi'][1] + 1)
    }


def result(identifier, kind, expected, actual, passed, *, positions=(), level=None, source=None, reason=None):
    row = dict(id=identifier, kind=kind, expected=expected, actual=actual, passed=passed is True,
               status='pending' if passed is None else 'passed' if passed else 'failed')
    if positions:
        row['positions'] = [list(p) for p in positions]
    if level is not None:
        row['level'] = level
    if source is not None:
        row['source'] = source
    if reason is not None:
        row['reason'] = reason
    return row


def contacts(left, right, allowed, *, wall_only=False):
    """Group parallel potential crossings by wall/transition column."""
    lines = defaultdict(dict)
    for x, z in sorted(left):
        for dx, dz in CARDINAL:
            axis = 0 if dx else 1
            mx, mz = x + dx, z + dz
            key = (axis, mx if dx else mz, dx or dz)
            index_along = mz if dx else mx
            if not wall_only and (mx, mz) in right:
                lines[key][index_along] = ((x, z), (mx, mz), (mx, mz))
            fx, fz = mx + dx, mz + dz
            if (mx, mz) in allowed and (fx, fz) in right:
                lines[key][index_along] = ((x, z), (mx, mz), (fx, fz))
    return lines


def best_run(lines, allowed=None):
    best = []
    for key in sorted(lines):
        previous = None
        run = []
        for i, crossing in sorted(lines[key].items()):
            if allowed is not None and crossing[1] not in allowed:
                continue
            if previous is None or i != previous + 1:
                run = []
            run.append(crossing)
            if len(run) > len(best):
                best = run.copy()
            previous = i
    return best


def largest_square(region):
    extents = {}
    maximum = 0
    for x, z in sorted(region):
        square = 1 + min(extents.get((x - 1, z), 0), extents.get((x, z - 1), 0),
                         extents.get((x - 1, z - 1), 0))
        extents[x, z] = square
        maximum = max(maximum, square)
    return maximum


def connected(start, goal, graph):
    visited = {start}
    pending = deque([start])
    while pending:
        current = pending.popleft()
        if current == goal:
            return True
        unseen = graph[current] - visited
        visited.update(unseen)
        pending.extend(sorted(unseen))
    return False


class PlanningLayout:
    def __init__(self, program, layout):
        properties = catalog()['architecture']['actions']['layout-check']['properties']
        _schema(program, properties['program'], '整栋规划任务书')
        _schema(layout, properties['layout'], '整栋建筑布局')
        self.program = program
        self.layout = layout
        self.size = program['size']
        self.levels = index(program['levels'], '楼层')
        self.spaces = index(program['spaces'], '功能空间')
        self.relations = index(program['relations'], '空间连接')
        self.placements = index(layout['spaces'], '空间布置')
        self.links = index(layout.get('links', ()), '连接布置')
        self._validate_references()
        self._validate_bounds()
        self.footprints = {key: cells(level['footprint']) for key, level in self.levels.items()}
        self.voids = {key: cells(level.get('voids', ())) for key, level in self.levels.items()}
        self.reserved = {key: cells(level.get('reserved', ())) for key, level in self.levels.items()}
        for key, footprint in self.footprints.items():
            if (self.voids[key] | self.reserved[key]) - footprint:
                raise ValueError(f'楼层{key}的挑空或保留区超出占地')
        self.usable = {key: footprint - self.voids[key] - self.reserved[key]
                       for key, footprint in self.footprints.items()}
        self.regions = {key: cells(self.placements.get(key, {}).get('regions', ()))
                        for key in self.spaces}
        self.by_level = defaultdict(set)
        for key, room in self.spaces.items():
            self.by_level[room['level']].update(self.regions[key])
        self.portal_runs = {}

    def _validate_references(self):
        if 'entry_space' in self.program and self.program['entry_space'] not in self.spaces:
            raise ValueError('规划入口引用未知空间')
        for key in sorted(self.placements.keys() - self.spaces.keys()):
            raise ValueError(f'布置引用未知空间：{key}')
        for key in sorted(self.links.keys() - self.relations.keys()):
            raise ValueError(f'布置引用未知连接：{key}')
        for key, room in self.spaces.items():
            if room['level'] not in self.levels:
                raise ValueError(f'空间{key}引用未知楼层')
            low, high = room.get('min_area', 1), room.get('max_area', self.size[0] * self.size[2])
            if low > high or not low <= room.get('target_area', low) <= high:
                raise ValueError(f'空间{key}的面积目标与上下限冲突')
        for key, relation in self.relations.items():
            left, right = relation['from'], relation['to']
            if left == right or left not in self.spaces or right not in self.spaces:
                raise ValueError(f'连接{key}的空间引用无效')
            same_level = self.spaces[left]['level'] == self.spaces[right]['level']
            kind = relation['kind']
            if (kind in ('door', 'adjacent', 'wall') and not same_level) or (kind == 'stair' and same_level):
                raise ValueError(f'连接{key}的通行类型与楼层不符')
            fields = {
                'door': {'opening'}, 'stair': {'from_feet', 'to_feet', 'stair'},
                'adjacent': set(), 'wall': set(), 'route': set(),
            }[kind]
            if set(self.links.get(key, ())) - fields - {'id'}:
                raise ValueError(f'连接{key}包含不适用的布置字段')
            if ('min_width' in relation and kind not in ('door', 'adjacent', 'wall')
                    or 'max_length' in relation and kind not in ('route', 'stair')):
                raise ValueError(f'连接{key}包含不适用的量化字段')

    def _validate_bounds(self):
        if len({level['feet_y'] for level in self.levels.values()}) != len(self.levels):
            raise ValueError('楼层脚位标高重复')
        area = 0
        boxes = []
        points = [self.program['entry']]
        for level in self.levels.values():
            foot, ceiling = level['feet_y'], level['ceiling_y']
            if foot * 2 != int(foot * 2) or not 0 < foot < ceiling <= self.size[1]:
                raise ValueError(f"楼层{level['id']}的脚位或顶界无效")
            boxes.extend(level['footprint'])
            boxes.extend(level.get('voids', ()))
            boxes.extend(level.get('reserved', ()))
            boxes.extend(level.get('envelope', ()))
        for placement in self.placements.values():
            boxes.extend(placement['regions'])
            if 'feet' in placement:
                points.append(placement['feet'])
        for link in self.links.values():
            if 'opening' in link:
                boxes.append(link['opening'])
            points.extend(link[key] for key in ('from_feet', 'to_feet') if key in link)
        for box in boxes:
            if any(not 0 <= lo <= hi < limit for lo, hi, limit in
                   zip(box['lo'], box['hi'], (self.size[0], self.size[2]))):
                raise ValueError('规划平面矩形越出画布或上下界倒置')
            area += box_area(box)
        if area > MAX_RASTER_CELLS:
            raise ValueError(f'规划平面展开超过{MAX_RASTER_CELLS}格')
        if any(any(not 0 <= coordinate < limit for coordinate, limit in zip(point, self.size))
               for point in points):
            raise ValueError('规划脚位越出画布')

    def feet_y(self, space):
        return self.levels[self.spaces[space]['level']]['feet_y']

    def contains(self, space, feet):
        return bool(feet and feet[1] == self.feet_y(space)
                    and (floor(feet[0]), floor(feet[2])) in self.regions[space])

    def feet(self, key):
        declared = self.placements.get(key, {}).get('feet')
        if declared is not None or not self.regions[key]:
            return declared
        x, z = min(self.regions[key])
        return [x + .5, self.feet_y(key), z + .5]

    def positions(self, key, region):
        return [[x, self.feet_y(key), z] for x, z in sorted(region)[:8]]

    def room_results(self):
        earlier = []
        for key, room in self.spaces.items():
            region = self.regions[key]
            level_id = room['level']
            low, high = room.get('min_area', 1), room.get('max_area', self.size[0] * self.size[2])
            prefix = f'space:{key}:'
            metadata = dict(level=level_id, source=room.get('source'))
            yield result(prefix + 'placed', 'space_placed', True, bool(region), bool(region), **metadata)
            if not region:
                continue
            outside = region - self.usable[level_id]
            yield result(prefix + 'bounds', 'space_bounds', 0, len(outside), not outside,
                         positions=self.positions(key, outside), **metadata)
            level = self.levels[level_id]
            overlap = set()
            for other in earlier:
                previous = self.levels[self.spaces[other]['level']]
                if max(level['feet_y'], previous['feet_y']) < min(level['ceiling_y'], previous['ceiling_y']):
                    overlap.update(region & self.regions[other])
            earlier.append(key)
            yield result(prefix + 'overlap', 'space_overlap', 0, len(overlap), not overlap,
                         positions=self.positions(key, overlap), **metadata)
            yield result(prefix + 'area', 'net_area', dict(min=low, max=high), len(region),
                         low <= len(region) <= high, positions=self.positions(key, region)[:1], **metadata)
            if 'min_span' in room:
                span = largest_square(region)
                yield result(prefix + 'span', 'usable_square_span', room['min_span'], span,
                             span >= room['min_span'], positions=self.positions(key, region)[:1], **metadata)
            if 'min_headroom' in room:
                height = level['ceiling_y'] - level['feet_y']
                yield result(prefix + 'headroom', 'headroom', room['min_headroom'], height,
                             height >= room['min_headroom'], positions=self.positions(key, region)[:1], **metadata)
            if 'feet' in self.placements[key]:
                feet = self.feet(key)
                yield result(prefix + 'feet', 'space_feet', True, feet, self.contains(key, feet),
                             positions=[feet], **metadata)

    def connection_results(self):
        travel = defaultdict(set)
        routes = []
        for key, rule in self.relations.items():
            left, right, kind = rule['from'], rule['to'], rule['kind']
            level = self.spaces[left]['level']
            link = self.links.get(key, {})
            fields = dict(level=level, source=rule.get('source'))
            if kind == 'route':
                routes.append((key, left, right, fields))
                continue
            if kind == 'stair':
                a, b = link.get('from_feet'), link.get('to_feet')
                passed = self.contains(left, a) and self.contains(right, b)
                row = result(f'relation:{key}', kind, True, passed, passed,
                             positions=[p for p in (a, b) if p], **fields)
            else:
                wall_only = kind in ('door', 'wall')
                permitted = self.usable[level] - self.by_level[level]
                lines = contacts(self.regions[left], self.regions[right], permitted, wall_only=wall_only)
                opening = link.get('opening')
                opening_cells = cells([opening]) if opening else set() if kind == 'door' else None
                run = best_run(lines, opening_cells)
                need = rule.get('min_width', 1)
                actual = len(run)
                passed = actual >= need
                if kind == 'door':
                    self.portal_runs[key] = (lines, opening_cells)
                row = result(f'relation:{key}', kind, need, actual, passed,
                             positions=self.positions(left, {crossing[1] for crossing in run}), **fields)
            if passed and kind in ('door', 'stair'):
                travel[left].add(right)
                travel[right].add(left)
            yield row
        if 'entry_space' in self.program:
            entry = self.program['entry_space']
            feet = self.program['entry']
            inside = self.contains(entry, feet)
            yield result('entry:placement', 'entry_in_space', True, inside, inside,
                         positions=[feet], level=self.spaces[entry]['level'])
            for space in self.spaces:
                if space == entry:
                    continue
                ok = connected(entry, space, travel)
                yield result(f'entry:route:{space}', 'entry_reachability', True, ok, ok,
                             positions=[p for p in (feet, self.feet(space)) if p],
                             level=self.spaces[space]['level'])
        for key, left, right, fields in routes:
            ok = connected(left, right, travel)
            yield result(f'relation:{key}', 'route', True, ok, ok,
                         positions=[p for p in (self.feet(left), self.feet(right)) if p], **fields)

    def drawing(self):
        return dict(size=self.size, entry=self.program['entry'], levels=list(self.levels.values()),
                    spaces=[dict(id=key, level=room['level'], name=room['purpose'],
                                 kind=room.get('kind', 'room'),
                                 regions=self.placements.get(key, {}).get('regions', []),
                                 feet=self.feet(key)) for key, room in self.spaces.items()],
                    links=[dict(row, kind=self.relations[key]['kind'],
                                level=self.spaces[self.relations[key]['from']]['level'])
                           for key, row in self.links.items()])

    def assess(self):
        checks = list(self.room_results()) + list(self.connection_results())
        area_deviation = sum(abs(len(self.regions[key]) - room['target_area'])
                             for key, room in self.spaces.items() if 'target_area' in room)
        allocated = sum(map(len, self.regions.values()))
        circulation = sum(len(self.regions[key]) for key, room in self.spaces.items()
                          if room.get('kind') == 'circulation')
        return dict(schema_version=1, stage='layout', passed=all(row['passed'] for row in checks), checks=checks,
                    drawing=self.drawing(), program_sha256=fingerprint(self.program),
                    layout_sha256=fingerprint(self.layout),
                    metrics=dict(area_target_deviation=area_deviation, allocated_area=allocated,
                                 circulation_area=circulation))


def assess_layout(program, layout):
    return PlanningLayout(program, layout).assess()


def check(workspace, request):
    if 'source' not in request:
        return assess_layout(request['program'], request['layout'])
    from nbt_building.planning_geometry import assess_geometry
    from nbt_building.review import load_model

    model = load_model(workspace, request)
    binding = model.architecture
    if 'planning' not in binding['plan']:
        raise ValueError('当前制作源没有整栋规划绑定')
    report = assess_geometry(model, binding['plan']['planning'], binding)
    report.update(source_sha256=request['source_sha256'], plan_sha256=binding['sha256'])
    return report
