"""Interior reachable-floor detection and bounded style-aware depressions.

Detection is geometric, not semantic recognition of furniture. Existing assets
still use the human-reviewed refinement entrypoint; no world or part is edited here.
"""
import argparse
from collections import Counter, deque
from functools import lru_cache
import json
import math
from pathlib import Path

from nbt_assembly import Volume
from nbt_collision import _Space, _position, EPS, check_routes
from nbt_model import AIR, AIR_NAMES, state
from nbt_registry import effective, registry
from nbt_weathering import _point, _full, _ring, _groups, _rng, neighbors

PROFILES = {
    'maintained': dict(fraction=0, slab_share=1, patch_size=[2, 3]),
    'worn': dict(fraction=.04, slab_share=.85, patch_size=[2, 4]),
    'ruined': dict(fraction=.08, slab_share=.7, patch_size=[2, 6]),
    'cavern': dict(fraction=.06, slab_share=.85, patch_size=[2, 5]),
}
ALIASES = {
    'stone_bricks': 'stone_brick_slab', 'mossy_stone_bricks': 'mossy_stone_brick_slab',
    'cracked_stone_bricks': 'stone_brick_slab', 'chiseled_stone_bricks': 'stone_brick_slab',
    'bricks': 'brick_slab', 'mud_bricks': 'mud_brick_slab',
    'deepslate_bricks': 'deepslate_brick_slab', 'cracked_deepslate_bricks': 'deepslate_brick_slab',
    'deepslate_tiles': 'deepslate_tile_slab', 'cracked_deepslate_tiles': 'deepslate_tile_slab',
    'deepslate': 'cobbled_deepslate_slab', 'nether_bricks': 'nether_brick_slab',
    'red_nether_bricks': 'red_nether_brick_slab', 'cracked_nether_bricks': 'nether_brick_slab',
    'chiseled_nether_bricks': 'nether_brick_slab', 'end_stone_bricks': 'end_stone_brick_slab',
    'polished_blackstone_bricks': 'polished_blackstone_brick_slab',
    'cracked_polished_blackstone_bricks': 'polished_blackstone_brick_slab',
    'chiseled_polished_blackstone': 'polished_blackstone_slab',
    'quartz_block': 'quartz_slab', 'quartz_bricks': 'quartz_slab', 'quartz_pillar': 'quartz_slab',
    'purpur_block': 'purpur_slab', 'purpur_pillar': 'purpur_slab',
    'prismarine_bricks': 'prismarine_brick_slab',
    'chiseled_sandstone': 'sandstone_slab', 'chiseled_red_sandstone': 'red_sandstone_slab',
}
FALLBACKS = {'deepslate', 'quartz_bricks', 'quartz_pillar', 'purpur_pillar'}


def slab_match(value, overrides=None):
    name, props = effective(value)
    if not _full(value) or props.get('waterlogged') == 'true':
        return None
    short = name.removeprefix('minecraft:')
    override = (overrides or {}).get(name, (overrides or {}).get(short))
    if override is not None:
        target, match = override, 'explicit_override'
    else:
        target = ALIASES.get(short)
        if short.endswith('_planks'):
            target = short[:-7] + '_slab'
        if short.endswith('_slab') and props.get('type') == 'double':
            target = short
        if target is None:
            target = short + '_slab'
        if ':' not in target:
            target = 'minecraft:' + target
        if target not in registry()['blocks']:
            return None
        match = 'family_fallback' if short.startswith(('cracked_', 'chiseled_')) or short in FALLBACKS else 'same_family'
    target_name, target_props = effective(target)
    if (not target_name.endswith('_slab') or target_props.get('type') != 'bottom'
            or target_props.get('waterlogged') != 'false'):
        raise ValueError('Floor slab overrides must be dry bottom slabs')
    return dict(state=state(dict(Name=target_name, Properties=target_props)), match=match)


def _clone(model):
    result = Volume(model.size)
    result.blocks = dict(model.blocks)
    return result


def _box(bounds):
    if not isinstance(bounds, dict) or set(bounds) != {'lo', 'hi'}:
        raise ValueError('Boxes require lo and hi')
    lo, hi = _point(bounds['lo']), _point(bounds['hi'])
    if any(lo[i] > hi[i] for i in range(3)):
        raise ValueError('Box bounds are reversed')
    return lo, hi


def _inside(point, bounds):
    return all(bounds[0][i] <= point[i] <= bounds[1][i] for i in range(3))


def _interior(model, context):
    capped = _clone(model)
    port_cells, ports = set(), context.get('ports', [])
    if not isinstance(ports, list):
        raise ValueError('ports must be a list')
    for port in ports:
        lo, hi = _point(port['min']), _point(port['max'])
        if (port['facing'] not in ('west', 'east', 'north', 'south')
                or any(lo[i] > hi[i] for i in range(3)) or not model.in_bounds(lo) or not model.in_bounds(hi)):
            raise ValueError('Invalid declared port')
        axis = 0 if port['facing'] in ('west', 'east') else 2
        if lo[axis] != hi[axis]:
            raise ValueError('A port must lie in one boundary plane')
        for x in range(lo[0], hi[0]+1):
            for y in range(lo[1], hi[1]+1):
                for z in range(lo[2], hi[2]+1):
                    p = (x, y, z)
                    port_cells.add(p)
                    if capped.get(p) in AIR_NAMES:
                        capped.put(p, 'stone')
    probes = context.get('interior_probes')
    if not isinstance(probes, list) or not probes:
        raise ValueError('Automatic floors require interior_probes covering intended chambers')
    seal = capped.check_sealed(probes)
    air = {_point(p) for p in probes}
    pending = deque(air)
    while pending:
        for p in neighbors(pending.popleft()):
            if p not in air and capped.in_bounds(p) and capped.get(p) in AIR_NAMES:
                air.add(p)
                pending.append(p)
    return air, port_cells, seal


def _walk(model, context, air, port_cells, limit):
    start = _position(context['start'])
    source_targets = context.get('targets', {})
    if isinstance(source_targets, list):
        source_targets = {str(i): p for i, p in enumerate(source_targets)}
    if not isinstance(source_targets, dict):
        raise ValueError('targets must be a name-to-feet map or a feet list')
    targets = {str(k): _position(v) for k, v in source_targets.items()}
    inward = dict(west=(1, 0), east=(-1, 0), north=(0, 1), south=(0, -1))
    for index, port in enumerate(context.get('ports', [])):
        lo, hi = port['min'], port['max']
        dx, dz = inward[port['facing']]
        p = [(lo[0]+hi[0])/2+.5+dx, lo[1], (lo[2]+hi[2])/2+.5+dz]
        name = f'__floor_port_{index}'
        if name in targets:
            raise ValueError('Reserved floor port target name')
        targets[name] = _position(p)
    if not targets:
        raise ValueError('Declare necessary targets or ports; empty route verification is not accepted')
    space = _Space(model)
    if space.unknown:
        raise ValueError('Automatic floors require supported static collision geometry; unknown shapes: ' + str(list(space.unknown)[:8]))
    allowed_air = air | port_cells

    def standing(p):
        head = (math.floor(p[0]), math.floor(p[1]+1), math.floor(p[2]))
        return head in allowed_air and space.standing(p)

    @lru_cache(maxsize=None)
    def node_standing(node):
        return standing(tuple(v*.5 for v in node))

    def anchors(p, forward):
        result = {}
        for x in {math.floor(p[0]*2+EPS), math.ceil(p[0]*2-EPS)}:
            for z in {math.floor(p[2]*2+EPS), math.ceil(p[2]*2-EPS)}:
                for y in (round(p[1]*2), round(p[1]*2)-1, round(p[1]*2)+1):
                    node = (x, y, z)
                    if not node_standing(node):
                        continue
                    q = tuple(v*.5 for v in node)
                    connector = space.connector(p, q) if forward else space.connector(q, p)
                    if connector:
                        result[node] = connector
        return result

    starts = anchors(start, True) if standing(start) else {}
    if not starts:
        raise ValueError('Start is not a supported interior feet pose')
    parent, root = {p: None for p in starts}, {p: p for p in starts}
    pending = deque(sorted(starts))
    while pending:
        node = pending.popleft()
        a = tuple(v*.5 for v in node)
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            for dy in (0, 1, -1):
                q = (node[0]+dx, node[1]+dy, node[2]+dz)
                if q not in parent and node_standing(q) and space.move(a, tuple(v*.5 for v in q)):
                    parent[q], root[q] = node, root[node]
                    pending.append(q)
                    if len(parent) > limit:
                        raise ValueError('Floor detection exceeded max_poses; restrict the source or raise the explicit limit')
    paths = []
    for name, p in targets.items():
        candidates = anchors(p, False) if standing(p) else {}
        hits = sorted(parent.keys() & candidates.keys())
        if not hits:
            raise ValueError(f'Necessary target is not reachable within declared interior: {name}')
        node = hits[0]
        chain, current = [], node
        while current is not None:
            chain.append(tuple(v*.5 for v in current))
            current = parent[current]
        path = starts[root[node]][:-1]+list(reversed(chain))+candidates[node][1:]
        paths.append(dict(name=name, feet=list(p), path=[list(v) for i, v in enumerate(path) if not i or v != path[i-1]]))
    return parent, dict(passed=True, start=list(start), targets=paths, reachable_poses=len(parent),
                       method='interior_restricted_half_grid_swept_player_aabb', runtime_verified=False)


def detect_floors(model, context, *, min_area=9, exclude_boxes=(), include_boxes=(), max_poses=250000):
    if type(min_area) is not int or min_area < 1 or type(max_poses) is not int or max_poses < 1:
        raise ValueError('min_area and max_poses must be positive integers')
    excludes, includes = list(map(_box, exclude_boxes)), list(map(_box, include_boxes))
    air, port_cells, seal = _interior(model, context)
    poses, routes = _walk(model, context, air, port_cells, max_poses)
    candidates = set()
    for (x, y, z), value in model.blocks.items():
        p = (x, y, z)
        if (not _full(value) or (x, y+1, z) not in air or (x, y+2, z) not in air
                or (2*x+1, 2*y+2, 2*z+1) not in poses):
            continue
        if any(_inside(p, b) for b in excludes) or (includes and not any(_inside(p, b) for b in includes)):
            continue
        candidates.add(p)
    remaining, floors, regions, small = set(candidates), set(), [], 0
    while remaining:
        first = min(remaining)
        remaining.remove(first)
        group, pending = {first}, [first]
        while pending:
            for p in neighbors(pending.pop(), True):
                if p in remaining:
                    remaining.remove(p); group.add(p); pending.append(p)
        if len(group) < min_area:
            small += len(group)
            continue
        floors.update(group)
        regions.append(dict(y=first[1], blocks=len(group),
                            lo=[min(p[i] for p in group) for i in range(3)], hi=[max(p[i] for p in group) for i in range(3)]))
    return floors, dict(source_geometry_sha256=model.fingerprint(), floors=[list(p) for p in sorted(floors)],
                        levels=sorted({p[1] for p in floors}), regions=regions, small_surface_blocks_skipped=small,
                        routes=routes, recapped_seal=seal,
                        limitations=['Geometric candidates, not semantic furniture recognition. Use exclude_boxes for large walkable worktops.',
                                     'Existing slabs/stairs are used for reachability but not damaged again; unknown shapes refuse certification.'])


def _protection(model, context, routes, depth, margin, protected):
    from nbt_refine import protections
    config = dict(context)
    paths = [r['path'] for r in routes['targets']]
    paths.extend(context.get('protected_paths', []))
    config['protected_paths'] = paths
    config['protected_boxes'] = [dict(lo=[b['lo'][0], b['lo'][1]-depth-1, b['lo'][2]], hi=b['hi'])
                                 for b in context.get('protected_boxes', [])]
    result = protections(model, config) | {_point(p) for p in protected}
    for path in paths:
        for a, b in zip(path, path[1:]+path[-1:]):
            lo = [math.floor(min(a[0], b[0])-.3-margin), math.floor(min(a[1], b[1])-.01)-depth-1,
                  math.floor(min(a[2], b[2])-.3-margin)]
            hi = [math.ceil(max(a[0], b[0])+.3+margin)-1, math.ceil(max(a[1], b[1])+1.8)-1,
                  math.ceil(max(a[2], b[2])+.3+margin)-1]
            for x in range(max(0, lo[0]), min(model.size[0]-1, hi[0])+1):
                for y in range(max(0, lo[1]), min(model.size[1]-1, hi[1])+1):
                    for z in range(max(0, lo[2]), min(model.size[2]-1, hi[2])+1):
                        result.add((x, y, z))
    for port in context.get('ports', []):
        lo, hi = list(port['min']), list(port['max'])
        dx, dz = dict(west=(1, 0), east=(-1, 0), north=(0, 1), south=(0, -1))[port['facing']]
        a = [min(lo[0], lo[0]+4*dx)-1, lo[1]-depth-2, min(lo[2], lo[2]+4*dz)-1]
        b = [max(hi[0], hi[0]+4*dx)+1, hi[1]+1, max(hi[2], hi[2]+4*dz)+1]
        for x in range(max(0, a[0]), min(model.size[0]-1, b[0])+1):
            for y in range(max(0, a[1]), min(model.size[1]-1, b[1])+1):
                for z in range(max(0, a[2]), min(model.size[2]-1, b[2])+1):
                    result.add((x, y, z))
    return result


def auto_floor_plan(model, operation, context, protected=()):
    supported = {'kind', 'label', 'classification', 'profile', 'style_note', 'fraction', 'slab_share',
                 'patch_size', 'pit_depth', 'rim_width', 'rim_cracks', 'seed', 'min_area', 'max_poses',
                 'include_boxes', 'exclude_boxes', 'slab_overrides', 'route_margin'}
    if not isinstance(operation, dict) or set(operation)-supported or operation.get('kind', 'auto_floor') != 'auto_floor':
        raise ValueError('Invalid auto_floor operation or unknown fields')
    if operation.get('classification', 'body') != 'body':
        raise ValueError('auto_floor edits belong to the body layer')
    profile = operation.get('profile')
    if profile not in PROFILES or not isinstance(operation.get('style_note'), str) or not operation['style_note'].strip():
        raise ValueError('Choose a floor profile and record its style_note')
    chosen = dict(PROFILES[profile]); chosen.update(operation)
    fraction, share = chosen['fraction'], chosen['slab_share']
    margin, depth = operation.get('route_margin', .5), operation.get('pit_depth', 1)
    if any(type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1 for v in (fraction, share)):
        raise ValueError('fraction and slab_share must be finite 0..1')
    if type(margin) not in (int, float) or not math.isfinite(margin) or not 0 <= margin <= 4:
        raise ValueError('route_margin must be 0..4')
    if type(depth) is not int or not 1 <= depth <= 8:
        raise ValueError('pit_depth must be 1..8')
    seed, rim_width, sizes = operation.get('seed', 0), operation.get('rim_width', 1), chosen['patch_size']
    if type(seed) is not int or type(rim_width) is not int or not 1 <= rim_width <= 3:
        raise ValueError('Invalid seed or rim_width')
    if not isinstance(sizes, (list, tuple)) or len(sizes) != 2 or any(type(n) is not int for n in sizes) or not 2 <= sizes[0] <= sizes[1] <= 512:
        raise ValueError('patch_size requires 2 <= min <= max <= 512')
    if type(operation.get('rim_cracks', False)) is not bool:
        raise ValueError('rim_cracks must be boolean')
    overrides = operation.get('slab_overrides', {})
    if not isinstance(overrides, dict):
        raise ValueError('slab_overrides must be a source-ID to slab-state map')
    for key, target in overrides.items():
        if '[' in state(key) or slab_match(state(key), {key: target}) is None:
            raise ValueError('Invalid slab override source')
    floors, detection = detect_floors(model, context, min_area=operation.get('min_area', 9),
        max_poses=operation.get('max_poses', 250000), exclude_boxes=operation.get('exclude_boxes', []),
        include_boxes=operation.get('include_boxes', []))
    protected = _protection(model, context, detection['routes'], depth, margin, protected)
    matches, unmapped = {}, Counter()
    for p in sorted(floors):
        match = slab_match(model.get(p), overrides)
        if match is None: unmapped[model.get(p)] += 1
        else: matches[p] = match
    eligible = set(matches)-protected
    target = round(len(eligible)*fraction)
    slab_target = round(target*share); pit_target = target-slab_target
    edits, damaged, rims, supports = {}, set(), set(), set()
    groups = {'slabs': [], 'pits': []}
    cracked = {'stone_bricks': 'cracked_stone_bricks', 'deepslate_bricks': 'cracked_deepslate_bricks',
               'deepslate_tiles': 'cracked_deepslate_tiles', 'nether_bricks': 'cracked_nether_bricks',
               'polished_blackstone_bricks': 'cracked_polished_blackstone_bricks'}

    def accept(group, pit):
        rim = _ring(group, rim_width)
        if not rim <= eligible or (group | rim) & (damaged | rims): return None
        pending, bases = {}, set()
        for x, y, z in sorted(group):
            bottom = (x, y-(depth if pit else 1), z)
            if not model.in_bounds(bottom) or not _full(model.get(bottom)) or bottom in edits: return None
            bases.add(bottom)
            for d in range(depth if pit else 1):
                q = (x, y-d, z)
                if not model.in_bounds(q) or q in protected or q in supports or not _full(model.get(q)): return None
                if any(n not in {(v[0], y-d, v[2]) for v in group} and
                       (not model.in_bounds(n) or not _full(model.get(n))) for n in neighbors(q, True)): return None
                pending[q] = AIR if pit else matches[(x, y, z)]['state']
        edits.update(pending); damaged.update(group); rims.update(rim); supports.update(bases)
        if operation.get('rim_cracks', False):
            for p in sorted(rim):
                name = effective(model.get(p))[0].removeprefix('minecraft:')
                if name in cracked: edits[p] = state(cracked[name])
        return rim

    pool = {p for p in eligible if _ring({p}, rim_width) <= eligible}
    for name, count in (('pits', pit_target), ('slabs', slab_target)):
        groups[name] = _groups(pool-damaged-rims, count, sizes, _rng(seed, 'auto_floor_'+name),
                              horizontal=True, accept=lambda group, pit=(name == 'pits'): accept(group, pit))
    if any(p in protected for p in edits) or any(p in edits and not _full(edits[p]) for p in supports):
        raise ValueError('Floor damage conflicts with protected routes or support')
    result = _clone(model)
    for p, value in edits.items(): result.put(p, value)
    _, _, post_seal = _interior(result, context)
    route_targets = {r['name']: r['feet'] for r in detection['routes']['targets']}
    post_routes = check_routes(result, context['start'], route_targets)
    if not post_routes['passed']: raise ValueError('Post-damage routes did not pass')
    result_space = _Space(result)
    for path in (r['path'] for r in detection['routes']['targets']):
        if any(not result_space.move(tuple(a), tuple(b)) for a, b in zip(path, path[1:]+path[-1:])):
            raise ValueError('A previously verified necessary path changed')
    final_edits = sorted((p, value) for p, value in edits.items() if value != model.get(p))
    report = dict(profile=profile, style_note=operation['style_note'], seed=seed,
        detection=detection, mapped_blocks=len(matches), unmapped_states=dict(sorted(unmapped.items())),
        material_matches={v: slab_match(v, overrides) for v in sorted({model.get(p) for p in matches})},
        protected_floor_blocks=len(floors & protected), protected_voxels=len(protected), eligible_blocks=len(eligible),
        target_blocks=target, actual_blocks=len(damaged), shortfall=max(0, target-len(damaged)),
        slab_blocks=sum(map(len, groups['slabs'])), pit_columns=sum(map(len, groups['pits'])),
        fraction=fraction, slab_share=share, patch_size=list(sizes), pit_depth=depth, route_margin=margin,
        group_sizes={k: [len(g) for g in value] for k, value in groups.items()},
        changed_voxels=len(final_edits), post_seal=post_seal, post_routes=post_routes,
        original_necessary_paths_preserved=True, runtime_verified=False,
        source_geometry_sha256=model.fingerprint(), source_unchanged=True,
        ratio_policy='Budget over mapped, detected and unprotected floors; no scattered remainder or removal of protection')
    return final_edits, report


def apply_floor_damage(model, operation, context, wall_positions=(), protected=()):
    if model.stage != 'design':
        raise ValueError('Draft floor application must precede sealing; existing assets use reviewed refinement')
    walls = {_point(p) for p in wall_positions}
    if any(not model.in_bounds(p) for p in walls): raise ValueError('Wall mask exceeds source')
    edits, report = auto_floor_plan(model, operation, context, protected)
    for p, value in edits:
        model.put(p, value); walls.discard(p)
    report['result_geometry_sha256'] = model.fingerprint()
    report['source_unchanged'] = report['result_geometry_sha256'] == report['source_geometry_sha256']
    return walls, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('detect', 'plan'):
        cmd = sub.add_parser(name); cmd.add_argument('--source', type=Path, required=True)
        cmd.add_argument('--context', type=Path, required=True); cmd.add_argument('--output', type=Path, required=True)
        if name == 'plan': cmd.add_argument('--operation', type=Path, required=True)
    cmd = sub.add_parser('apply'); cmd.add_argument('--review', type=Path, required=True)
    cmd.add_argument('--operation', type=Path, required=True); cmd.add_argument('--style-note', required=True)
    cmd.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    from nbt_refine import read_master, refine
    if args.command == 'apply':
        op = json.loads(args.operation.read_text(encoding='utf-8-sig')); op.setdefault('kind', 'auto_floor')
        result = refine(args.review, dict(style_note=args.style_note, operations=[op]), args.output)
        print(json.dumps(dict(state=result['state'], changed_blocks=result['changed_blocks'])))
        return
    model, _ = read_master(args.source); context = json.loads(args.context.read_text(encoding='utf-8-sig'))
    if args.command == 'detect':
        _, report = detect_floors(model, context); data = dict(report=report)
    else:
        op = json.loads(args.operation.read_text(encoding='utf-8-sig'))
        edits, report = auto_floor_plan(model, op, context)
        data = dict(report=report, operation=op, edits=[dict(position=list(p), state=v) for p, v in edits])
    if args.output.exists(): raise FileExistsError('Choose a new output directory')
    args.output.mkdir(parents=True)
    (args.output/'floor_report.json').write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    print(json.dumps(dict(output=str(args.output.resolve()), source_unchanged=True), ensure_ascii=False))


if __name__ == '__main__': main()
