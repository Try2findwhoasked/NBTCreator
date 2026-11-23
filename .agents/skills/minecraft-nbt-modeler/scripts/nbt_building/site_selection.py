"""Bounded, single-building siting against a bound WorkingModel."""
from collections import Counter
from copy import copy, deepcopy
from itertools import product
from math import floor
from pathlib import Path
from time import perf_counter

from nbt_agent.structure import _schema
from nbt_assets.components import PlacementBoundsError, validate
from nbt_collision import FULL_CUBES, check_routes
from nbt_composition.change_policy import ChangePolicyError, reserved_position
from nbt_composition.object_scene import engine_hash, inside
from nbt_composition.whole_validation import requires_enclosure, validation_mode
from nbt_composition.working_model import (
    ModelConflict, WorkingModel, digest, empty_volume, file_hash, model_hash,
    value_at, world_position, write_json,
)
from nbt_extensions import compile_recipe
from nbt_geometry.terrain_roads import TerrainRoadError, terrain_road_plan
from nbt_model import AIR, AIR_NAMES, state
from nbt_refine import box_points, protections
from nbt_runtime.catalog import catalog


DIRECTIONS = dict(north=(0, 0, -1), east=(1, 0, 0), south=(0, 0, 1), west=(-1, 0, 0))
SOIL = ['grass_block', 'dirt', 'stone']
MAX_ROUTE_POSES = 20000


def add(a, b):
    return tuple(x + y for x, y in zip(a, b))


def feet(p):
    return [p[0] + .5, p[1] + 1, p[2] + .5]


def full_cube(value):
    name, _, properties = value.partition('[')
    return name.removeprefix('minecraft:') in FULL_CUBES and 'waterlogged=true' not in properties


class SiteRejected(ValueError):
    def __init__(self, code, **details):
        self.problem = dict(code=code, **details)


class SiteSelection:
    def __init__(self, host, goal):
        _schema(goal, catalog()['working_model']['actions']['site_selection']['properties']['goal'], '联合选址')
        if host.kind != 'building' or host.phase == 'sealed':
            raise ValueError('选址宿主须为非封闭的完整地形或工作模型')
        host._unchanged()
        self.host = host
        self.goal = deepcopy(goal)
        self.region = goal['region']
        self._bounds(self.region)
        lo, hi = self.region['lo'], self.region['hi']
        if (hi[0]-lo[0]+1)*(hi[2]-lo[2]+1) > 4096 or hi[1]-lo[1]+1 > 64:
            raise ValueError('选址范围最多 4096 个水平格与 64 层')
        self.junction = tuple(goal['junction'])
        if not inside(self.junction, self.region):
            raise ValueError('既有路口须位于求解范围')
        self.roads = goal['roads']
        for road in self.roads:
            self._bounds(road.get('corridor', self.region))
            if road.get('bridge_water') and not road.get('max_bridge_span'):
                raise ValueError('水上桥接须指定正的 max_bridge_span')
            self._material(road.get('state', 'stone_bricks'))
            if not state(road.get('stair_state', 'stone_brick_stairs')).split('[')[0].endswith('_stairs'):
                raise ValueError('接路过渡材质须为楼梯')
        self.choices = list(product(map(tuple, goal['anchor_xz']), goal['floor_ys'], goal['quarter_turns'], range(len(self.roads))))
        if len(self.choices) > goal['max_candidates'] or len(set(self.choices)) != len(self.choices):
            raise ValueError(f'候选组合共 {len(self.choices)} 项，须唯一且不超过 max_candidates')

        self.soil = {self._material(value) for value in goal.get('terrain_states', SOIL)}
        self.fill = self._material(goal.get('fill_state', 'dirt'))
        self.draft, self.recipe, self.component, self.compilation, self.building_binding = self._load_building(goal['building'])
        self.instance_id = goal.get('instance_id', 'site-building')
        if self.recipe and self.instance_id in host.instances:
            raise ValueError('宿主已有同名建筑实例')
        self._check_local_anchors()
        self.owned = host._owned_positions()
        self.protected = protections(host.model, host._protection_context()) | self.owned.keys() | host.walls
        self.reserved = list(host.context.get('reserved_boxes', []))
        for instance in host.instances.values():
            policy = instance['compiled'].get('policy', {})
            self.reserved.extend(policy.get('reserved_boxes', []))
            for box in policy.get('protected_boxes', []):
                self.protected.update(box_points(box['lo'], box['hi']))
        self.host_binding = dict(
            source=str(host.source) if host.source else None, source_sha256=host.source_sha256,
            version_sha256=host._version_binding[1] if host._version_binding else None,
            model_sha256=model_hash(host.model, host.walls), context_sha256=digest(host.context),
            limits=dict(host.limits), state_sha256=host._content_token(),
        )
        self.binding = dict(host=self.host_binding, building=self.building_binding, engine_sha256=engine_hash())
        self.design_phase = (
            host.phase == 'opened' and not host._version_binding and validation_mode(host.context) == 'standalone'
            and not requires_enclosure(host.context) and not any(
                host.context.get(key) for key in ('start', 'targets', 'route_legs', 'require_routes', 'openings', 'ports')
            ) and host.context.get('openings_policy', 'optional') != 'required'
        )

    def _bounds(self, box):
        if (any(a > b for a, b in zip(box['lo'], box['hi']))
                or not all(self.host.model.in_bounds(tuple(box[key])) for key in ('lo', 'hi'))
                or not all(inside(box[key], self.region) for key in ('lo', 'hi'))):
            raise ValueError('求解范围和道路走廊须为模型内的非空包含端点范围')

    @staticmethod
    def _material(value):
        value = state(value)
        if not full_cube(value):
            raise ValueError('土层、填方和路面须使用有已知碰撞的干燥整方块')
        return value

    def _load_building(self, spec):
        if 'recipe' in spec:
            recipe = deepcopy(spec['recipe'])
            component, result = compile_recipe(self.host.workspace, recipe)
            if component['content_sha256'] != spec['content_sha256']:
                raise ModelConflict('STALE_SITE_BUILDING', [dict(expected=spec['content_sha256'], actual=component['content_sha256'])])
            return None, recipe, component, result, dict(content_sha256=component['content_sha256'],
                                                          compilation_sha256=digest(result))
        draft = WorkingModel.open(self.host.workspace, spec['source'], source_sha256=spec['source_sha256'])
        if draft.phase == 'sealed':
            raise ValueError('选址建筑须为已有可走入口的粗案')
        values = draft.model.blocks
        palette = sorted(set(values.values()))
        indexes = {v: i for i, v in enumerate(palette)}
        component = validate(dict(schema_version=1, name='选址建筑', size=list(draft.model.size), anchor=[0, 0, 0],
                                  palette=palette, blocks=[[*p, indexes[v], p in draft.walls] for p, v in values.items()]))
        return draft, None, component, {}, dict(
            source=str(draft.source), source_sha256=draft.source_sha256,
            version_sha256=draft._version_binding[1] if draft._version_binding else None,
            model_sha256=model_hash(draft.model, draft.walls), context_sha256=digest(draft.context),
            content_sha256=component['content_sha256'],
        )

    def _unchanged(self):
        self.host._unchanged()
        if self.draft:
            self.draft._unchanged()
        else:
            component, compilation = compile_recipe(self.host.workspace, self.recipe)
            if (component['content_sha256'] != self.component['content_sha256']
                    or digest(compilation) != self.building_binding['compilation_sha256']):
                raise ModelConflict('STALE_SITE_BUILDING', [])

    def _check_local_anchors(self):
        size = self.component['size']
        anchor = tuple(self.goal['entrance']['floor'])
        direction = DIRECTIONS[self.goal['entrance']['facing']]
        cells = {tuple(row[:3]): self.component['palette'][row[3]] for row in self.component['blocks']}
        self.foundation_y = min((p[1] for p, v in cells.items() if v not in AIR_NAMES), default=None)
        base = [v for p, v in cells.items() if p[1] == self.foundation_y and v not in AIR_NAMES]
        if not base or any(not full_cube(v) for v in base):
            raise ValueError('建筑最底层的实体方块须为已知的干燥整方块')
        if not full_cube(cells.get(anchor, AIR)) or all(
                0 <= p < n for p, n in zip(add(anchor, direction), size)):
            raise ValueError('入口须为建筑外缘的实体地板，且朝向外侧')
        targets = self.goal['targets']
        if len({t['id'] for t in targets}) != len(targets) or any(
                not all(0 < v < n for v, n in zip(t['feet'], size)) or t['feet'] == feet(anchor) for t in targets):
            raise ValueError('工位须有唯一 ID 与建筑内独立于入口的脚位')

    def _pos(self, p, transform, continuous=False):
        return tuple(world_position(p, self.component, transform, continuous=continuous))

    def _surface(self, x, z):
        for y in range(self.host.model.size[1] - 1, -1, -1):
            p = x, y, z
            if self.host.model.get(p) not in AIR_NAMES:
                return p
        return None

    def _must_be_terrain(self, p):
        old = self.host.model.get(p)
        if old.split('[', 1)[0] in ('minecraft:water', 'minecraft:lava') or 'waterlogged=true' in old:
            raise SiteRejected('BUILDING_WATER_OR_FLUID', position=p, state=old)
        if old not in self.soil:
            raise SiteRejected('BUILDING_OBSTRUCTION', position=p, state=old)

    def _pad(self, values, bounds, base_y, apron, road_state):
        """Clear only declared terrain and require supported foundation + apron."""
        model = self.host.model
        lo, hi = bounds['lo'], bounds['hi']
        foundation = {p for p, pair in values.items() if p[1] == base_y and pair[0] not in AIR_NAMES}
        pads = foundation | {apron}
        excavation, fills, contacts = set(), set(), []
        for x, z in product(range(lo[0], hi[0] + 1), range(lo[2], hi[2] + 1)):
            p = x, base_y, z
            surface = self._surface(x, z)
            if surface is None:
                continue
            stop = surface[1] if p in foundation else min(hi[1], surface[1])
            for y in range(base_y, stop + 1):
                q = x, y, z
                old = model.get(q)
                if old in AIR_NAMES or q in values and old == values[q][0]:
                    continue
                self._must_be_terrain(q)
                if not inside(q, self.region) or y - base_y > self.goal['max_pad_cut']:
                    raise SiteRejected('PAD_CUT_LIMIT', position=q, floor_y=base_y)
                excavation.add(q)
        surface = self._surface(apron[0], apron[2])
        if surface:
            for y in range(apron[1], surface[1] + 1):
                q = apron[0], y, apron[2]
                if model.get(q) in AIR_NAMES:
                    continue
                if q == apron and model.get(q) == road_state:
                    continue
                self._must_be_terrain(q)
                if not inside(q, self.region) or y - apron[1] > self.goal['max_pad_cut']:
                    raise SiteRejected('PAD_CUT_LIMIT', position=q, floor_y=apron[1])
                if q != apron:
                    excavation.add(q)
        for x, y, z in sorted(pads):
            q = x, y - 1, z
            while inside(q, self.region) and model.get(q) in AIR_NAMES and y - q[1] <= self.goal['max_pad_fill']:
                fills.add(q)
                q = x, q[1] - 1, z
            if not model.in_bounds(q) or not inside(q, self.region):
                raise SiteRejected('SUPPORT_OUTSIDE_RANGE', position=q, supported_block=(x, y, z))
            support = model.get(q)
            if not full_cube(support):
                code = 'PAD_FILL_LIMIT' if support in AIR_NAMES else 'UNSUPPORTED_FOUNDATION'
                if support.split('[', 1)[0] in ('minecraft:water', 'minecraft:lava') or 'waterlogged=true' in support:
                    code = 'BUILDING_WATER_OR_FLUID'
                raise SiteRejected(code, position=q, supported_block=(x, y, z), state=support)
            contacts.append(dict(base=(x, y, z), terrain=q, terrain_state=support, fill_depth=y - q[1] - 1))
        edits = {p: [AIR, False] for p in excavation}
        edits.update({p: [self.fill, False] for p in fills})
        edits[apron] = [road_state, False]
        edits.update(values)
        if model.get(apron) in AIR_NAMES:
            fills.add(apron)
        return edits, excavation, fills, contacts

    def _guard(self, edits):
        model = self.host.model
        for p, value in sorted(edits.items()):
            if value == value_at(model, self.host.walls, p):
                continue
            if p == self.junction or p in self.protected:
                raise SiteRejected('PROTECTED_SPACE', position=p, state=model.get(p))
            if value[0] not in AIR_NAMES and reserved_position([p], self.reserved) is not None:
                raise SiteRejected('RESERVED_SPACE', position=p)

    def _check_routes(self, candidate, threshold, apron, targets, road, corridor, building):
        approach = feet(apron)
        for pose in road['walking_path']:
            if not inside(tuple(map(floor, pose)), corridor):
                raise SiteRejected('ROAD_WALK_OUTSIDE_CORRIDOR', position=pose, corridor=corridor)
        entry = check_routes(candidate, approach, {'threshold': feet(threshold)}, max_poses=MAX_ROUTE_POSES)
        door_path = entry['targets'][0].get('path', [])
        direct_columns = {(p[0], p[2]) for p in (threshold, apron)}
        if not entry['passed'] or any((floor(x), floor(z)) not in direct_columns for x, _, z in door_path):
            raise SiteRejected('ENTRY_CLEARANCE_OR_SUPPORT', position=threshold, approach=apron, route=entry)
        indoor = check_routes(candidate, feet(threshold), targets, max_poses=MAX_ROUTE_POSES)
        if not indoor['passed']:
            raise SiteRejected('INTERIOR_ROUTE_FAILED', position=threshold, route=indoor)
        paths = {}
        for item in indoor['targets']:
            for pose in item['path']:
                if not inside(tuple(map(floor, pose)), building):
                    raise SiteRejected('INDOOR_ROUTE_EXITS_BUILDING', position=pose, target=item['name'], route=indoor)
            paths[item['name']] = road['walking_path'] + door_path[1:] + item['path'][1:]
        return dict(passed=True, junction_feet=feet(self.junction), approach_feet=approach, threshold_feet=feet(threshold),
                    paths=paths, entry=entry, interior=indoor, runtime_verified=False)

    def _evaluate(self, index):
        started = perf_counter()
        xz, floor_y, turn, road_index = self.choices[index]
        position = [xz[0], floor_y + self.component['anchor'][1] - self.foundation_y, xz[1]]
        transform = dict(position=position, quarter_turns=turn)
        row = dict(id=f'candidate-{index+1:03d}', transform=transform, floor_y=floor_y,
                   local_foundation_y=self.foundation_y, road_option=road_index)
        state_candidate = None
        try:
            state_candidate = self._stage(row, transform, self.roads[road_index])
        except SiteRejected as error:
            row['problem'] = error.problem
        except PlacementBoundsError as error:
            row['problem'] = dict(code='BUILDING_OUTSIDE_RANGE', lo=error.lo, hi=error.hi)
        except TerrainRoadError as error:
            row['problem'] = dict(code='ROAD_INFEASIBLE', message=str(error), **error.details)
        except ChangePolicyError as error:
            row['problem'] = dict(code=error.kind, positions=list(error.positions), total=error.total)
        except ModelConflict as error:
            if error.code.startswith('STALE_') or error.code == 'CONTEXT_CONSTRAINT_MISMATCH':
                raise
            row['problem'] = dict(code=error.code, conflicts=error.conflicts)
        row['check_ms'] = round((perf_counter() - started) * 1000, 3)
        return row, state_candidate

    def _stage(self, row, transform, road_options):
        host = self.host
        recipe = self.recipe or dict(tool='site_draft', arguments={})
        values, compiled = host._place_compiled(recipe, transform, self.component, self.compilation)
        # Empty lower layers in the draft are padding. Keep the host foundation
        # support there even when a recipe explicitly includes its air cells.
        values = {p: pair for p, pair in values.items() if p[1] >= row['floor_y']}
        bounds = compiled['placement_bounds']
        row['building_bounds'] = bounds
        if not all(inside(bounds[key], self.region) for key in ('lo', 'hi')):
            raise SiteRejected('BUILDING_OUTSIDE_RANGE', **bounds)
        anchor = tuple(self.goal['entrance']['floor'])
        threshold = self._pos(anchor, transform)
        apron = self._pos(add(anchor, DIRECTIONS[self.goal['entrance']['facing']]), transform)
        outward = tuple(b-a for a, b in zip(threshold, apron))
        facing = next(name for name, direction in DIRECTIONS.items() if direction == outward)
        corridor = road_options.get('corridor', self.region)
        row.update(entrance_floor=threshold, entrance_facing=facing, approach_surface=apron)
        if not inside(apron, corridor) or not inside(self.junction, corridor):
            raise SiteRejected('ROAD_ENDPOINT_OUTSIDE_RANGE', start=self.junction, end=apron, corridor=corridor)
        if inside(self.junction, bounds):
            raise SiteRejected('BUILDING_OCCUPIES_JUNCTION', position=self.junction)
        road_state = state(road_options.get('state', 'stone_bricks'))
        apron_state = host.model.get(apron) if apron == self.junction else road_state
        edits, excavation, fills, contacts = self._pad(values, bounds, row['floor_y'], apron, apron_state)
        row['terrain_contact'] = contacts
        row['pad_earthwork'] = dict(cut_cells=len(excavation), fill_cells=len(fills))
        self._guard(edits)
        pad_model = empty_volume(host.model.size)
        pad_model.blocks = dict(host.model.blocks)
        for p, pair in edits.items():
            pad_model.put(p, pair[0])
        junction_state = pad_model.get(self.junction)
        if not full_cube(junction_state):
            raise SiteRejected('JUNCTION_NEEDS_DRY_SUPPORT', position=self.junction, state=junction_state)
        # The two authored deck cells are eligible road surfaces, while other
        # solids of those materials may only be edited if declared as terrain.
        options = dict(kind='terrain_road', **corridor, start=self.junction, end=apron, width=1,
                       max_writes=host.limits['max_written_positions'], terrain_states=sorted(self.soil),
                       state=road_state, stair_state=road_options.get('stair_state', 'stone_brick_stairs'),
                       max_bridge_span=road_options.get('max_bridge_span', 0))
        blocked = set(self.protected)
        for box in self.reserved:
            lo = [max(a, b) for a, b in zip(box['lo'], corridor['lo'])]
            hi = [min(a, b) for a, b in zip(box['hi'], corridor['hi'])]
            blocked.update(box_points(lo, hi))
        columns = product(range(bounds['lo'][0], bounds['hi'][0] + 1), range(bounds['lo'][2], bounds['hi'][2] + 1))
        road_edits, road = terrain_road_plan(pad_model, options, blocked, preserve_endpoints=True,
                                           bridge_water=road_options.get('bridge_water', False), excluded_columns=columns)
        row['road'] = road
        bridges = set(road['bridge_cells'])
        for p, value in road_edits:
            previous = pad_model.get(p)
            if previous not in AIR_NAMES and value in AIR_NAMES:
                excavation.add(p)
            if previous in AIR_NAMES and value not in AIR_NAMES and p not in bridges:
                fills.add(p)
            edits[p] = [value, False]
        self._guard(edits)
        changes = [dict(pos=p, before=value_at(host.model, host.walls, p), after=pair) for p, pair in sorted(edits.items())]
        staged = host._stage_edits(changes)
        candidate, walls, diff, _ = staged
        instances = host.instances
        if self.recipe:
            instance, _ = host._install_rows(self.instance_id, self.recipe, transform, values, compiled, self.owned, True)
            instances = instances | {self.instance_id: instance}
        host._check_edit_policies(candidate, walls, instances)
        assembly = host._assembly_checks(candidate, instances)
        if not assembly['passed']:
            raise SiteRejected('ASSEMBLY_INVALID', checks=[c for c in assembly['checks'] if not c['passed']])
        if not self.design_phase:
            try:
                host._check_candidate_building(staged, instances)
            except ValueError as error:
                if isinstance(error, (ModelConflict, ChangePolicyError)):
                    raise
                raise SiteRejected('HOST_VALIDATION_FAILED', message=str(error)) from error
        cut = sorted(p for p in excavation if host.model.get(p) != candidate.get(p))
        fill = sorted(p for p in fills if host.model.get(p) in AIR_NAMES and candidate.get(p) not in AIR_NAMES)
        row.update(earthwork=dict(cut_cells=len(cut), fill_cells=len(fill), cut_positions=cut, fill_positions=fill),
                   road_length_blocks=len(road['path'])-1, changes=diff)
        targets = {item['id']: self._pos(item['feet'], transform, continuous=True) for item in self.goal['targets']}
        row['route'] = self._check_routes(candidate, threshold, apron, targets, road, corridor, bounds)
        if self.draft:
            self._check_draft_context(candidate, bounds, transform)
        result_hash = model_hash(candidate, walls)
        row.update(model_sha256=result_hash,
                   score=len(cut) + len(fill) + row['road_length_blocks'],
                   candidate_sha256=digest([self.binding, self.goal, row['id'], result_hash, road['path'], row['route']['paths']]))
        return staged, instances

    def _check_draft_context(self, candidate, bounds, transform):
        context = self.draft.context
        for box in context.get('reserved_boxes', []):
            a, b = (self._pos(box[key], transform) for key in ('lo', 'hi'))
            region = dict(lo=[min(x, y) for x, y in zip(a, b)], hi=[max(x, y) for x, y in zip(a, b)])
            for p in box_points(region['lo'], region['hi']):
                if candidate.get(p) not in AIR_NAMES:
                    raise SiteRejected('BUILDING_RESERVED_SPACE', position=p)
        if context.get('require_routes') or context.get('start') and context.get('targets'):
            if not context.get('start') or not context.get('targets'):
                raise SiteRejected('BUILDING_REQUIRED_ROUTE_UNSPECIFIED', bounds=bounds)
            named = context['targets']
            items = named.items() if isinstance(named, dict) else enumerate(named)
            report = check_routes(candidate, self._pos(context['start'], transform, continuous=True),
                                  {str(name): self._pos(p, transform, continuous=True) for name, p in items},
                                  max_poses=MAX_ROUTE_POSES)
            if not report['passed']:
                raise SiteRejected('BUILDING_REQUIRED_ROUTE_FAILED', route=report)

    @staticmethod
    def _rank(row):
        earthwork = row['earthwork']
        return row['score'], earthwork['cut_cells'] + earthwork['fill_cells'], row['road_length_blocks'], row['id']

    def search(self, preview=None):
        started = perf_counter()
        if preview is not None:
            _schema(preview, catalog()['working_model']['actions']['site_selection']['properties']['preview'], '联合选址预览')
        wanted = preview.get('candidate_id') if preview else None
        if wanted:
            self._index(wanted)
        accepted, rejected, best, selected = [], [], None, None
        for index in range(len(self.choices)):
            row, staged = self._evaluate(index)
            if staged is None:
                rejected.append(row)
                continue
            accepted.append(row)
            if best is None or self._rank(row) < self._rank(best):
                best = row
                if preview and not wanted:
                    selected = row, staged
            if row['id'] == wanted:
                selected = row, staged
        self._unchanged()
        report = dict(schema_version=1, status='ranked' if best else 'no_legal_candidates', binding=self.binding,
                      goal=self.goal, evaluated=len(self.choices), eligible=len(accepted), best=best,
                      candidates=sorted(accepted, key=self._rank) + rejected, rejection_counts=dict(
                          Counter(row['problem']['code'] for row in rejected)),
                      check_ms=round((perf_counter() - started) * 1000, 3), model_modified=False, approval_created=False)
        if selected:
            row, staged = selected
            candidate = copy(self.host)
            self._apply(candidate, staged)
            output = (candidate.workspace / Path(preview['output'])).resolve()
            rendered = candidate.preview(output, preview.get('cameras', []))
            context_file = output / 'coordinates.json'
            write_json(context_file, candidate.context)
            receipt = output / 'site-selection.json'
            write_json(receipt, dict(binding=self.binding, goal=self.goal, candidate=row, approval_created=False,
                                     preview_source_sha256=file_hash(rendered['source']),
                                     snapshot_sha256=file_hash(rendered['snapshot']), context_sha256=file_hash(context_file)))
            report['preview'] = dict(rendered, candidate_sha256=row['candidate_sha256'], receipt=str(receipt))
        elif wanted:
            report['preview_problem'] = next(row['problem'] for row in rejected if row['id'] == wanted)
        return report

    def _index(self, candidate_id):
        if not isinstance(candidate_id, str) or candidate_id not in {
                f'candidate-{index+1:03d}' for index in range(len(self.choices))}:
            raise ValueError('指定选址候选超出本次请求')
        return int(candidate_id.removeprefix('candidate-')) - 1

    def _apply(self, host, staged):
        result = host._adopt_edits(*staged)
        if self.design_phase:
            host.phase = 'design'
        return result

    def adopt(self, candidate_id, candidate_sha256):
        row, staged = self._evaluate(self._index(candidate_id))
        self._unchanged()
        if staged is None or row['candidate_sha256'] != candidate_sha256:
            raise ModelConflict('STALE_SITE_CANDIDATE', [dict(id=candidate_id, problem=row.get('problem'))])
        return dict(self._apply(self.host, staged), candidate=row, binding=self.binding)
