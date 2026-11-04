"""Bounded voxel modelling plans. Pure planning; asset writes use nbt_refine.

All geometry samples block centres in GLOBAL coordinates. Bounds are inclusive.
Diffusion is graph growth, explosions are static art operations, not physics.
"""
from collections import deque
import hashlib
import math

import numpy as np

from nbt_fields import Grid, bezier
from nbt_model import AIR, AIR_NAMES, state


KINDS = {'geometry', 'morphology', 'diffusion', 'explosion', 'scatter',
         'copy_region', 'repeat_region', 'transform_region', 'replace', 'paste_component', 'auto_road', 'selection_replace', 'align_region', 'array_region', 'auto_stairs', 'terrain_road', 'auto_roof'}
NEIGHBOURS = ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))


def xyz(value, integer=False):
    if len(value) != 3 or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in value):
        raise ValueError('Expected finite XYZ')
    if integer and any(type(v) is not int for v in value):
        raise ValueError('Expected integer XYZ')
    return tuple(value)


def positive(value):
    if isinstance(value, bool) or not math.isfinite(value) or value <= 0:
        raise ValueError('Expected positive finite dimension')
    return value


def steps(value):
    if type(value) is not int or not 0 <= value <= 128:
        raise ValueError('Steps/count must be an integer in 0..128')
    return value


def random_at(seed, p, salt=''):
    return int.from_bytes(hashlib.sha256(f'{seed}:{p}:{salt}'.encode()).digest()[:8], 'big') / 2**64


def transformed_state(value, turns, mirror):
    """Conservative state transform: refuse state families without explicit rules."""
    from nbt_registry import effective
    name, props = effective(value)
    if not props:
        return value
    if set(props)-{'axis', 'facing', 'waterlogged'}:
        raise ValueError('Transform does not support this state family: '+value)
    directions = ['north', 'east', 'south', 'west']
    if props.get('facing') in directions:
        direction = props['facing']
        if mirror == 'x': direction = {'east': 'west', 'west': 'east'}.get(direction, direction)
        if mirror == 'z': direction = {'north': 'south', 'south': 'north'}.get(direction, direction)
        props['facing'] = directions[(directions.index(direction)+turns)%4]
    if turns%2 and props.get('axis') in ('x', 'z'):
        props['axis'] = 'z' if props['axis'] == 'x' else 'x'
    return state(dict(Name=name, Properties=props))


def shape_mask(grid, spec, depth=0):
    """CSG + primitives; recursion is bounded, no expression evaluation."""
    if depth > 16:
        raise ValueError('CSG nesting exceeds 16')
    kind = spec['shape']
    if kind in ('union', 'intersection', 'difference'):
        children = spec['children']
        if not children or (kind == 'difference' and len(children) != 2):
            raise ValueError('CSG needs children; difference needs exactly two')
        masks = [shape_mask(grid, child, depth + 1) for child in children]
        if kind == 'difference':
            return masks[0] & ~masks[1]
        return (np.logical_or if kind == 'union' else np.logical_and).reduce(masks)
    if kind in ('section_sweep', 'loft', 'revolve'):
        from nbt_section_geometry import section_mask
        return section_mask(grid, spec)
    if kind == 'box':
        field = grid.box(xyz(spec['min']), xyz(spec['max']))
    elif kind in ('sphere', 'ellipsoid'):
        radii = [positive(spec['radius'])] * 3 if kind == 'sphere' else xyz(spec['radii'])
        for r in radii:
            positive(r)
        field = grid.ellipsoid(xyz(spec['centre']), radii, spec.get('rotation'))
    elif kind in ('cylinder', 'cone'):
        axis = spec.get('axis', 'y')
        if axis not in ('x', 'y', 'z'):
            raise ValueError('Axis must be x/y/z')
        i = 'xyz'.index(axis); c = xyz(spec['centre']); height = positive(spec['height'])
        v = (grid.x, grid.y, grid.z)
        t = (v[i] - c[i]) / height + .5
        radius = positive(spec['radius'])
        top = spec.get('top_radius', 0) if kind == 'cone' else radius
        if not math.isfinite(top) or top < 0:
            raise ValueError('Invalid top radius')
        radial = np.sqrt(sum((v[j] - c[j])**2 for j in range(3) if j != i))
        field = np.maximum(radial - (radius + np.clip(t, 0, 1)*(top-radius)), abs(v[i]-c[i])-height/2)
    elif kind == 'torus':
        field = grid.torus(xyz(spec['centre']), positive(spec['major_radius']), positive(spec['minor_radius']))
    elif kind in ('polyline', 'bezier'):
        points = [xyz(p) for p in spec['points']]
        if kind == 'bezier':
            samples = spec.get('samples', 64)
            if type(samples) is not int or not 2 <= samples <= 1024:
                raise ValueError('Bezier samples must be 2..1024')
            points = bezier(points, samples)
        radius = spec['radius']
        if not np.all(np.isfinite(radius)):
            raise ValueError('Invalid tube radius')
        field = grid.tube(points, radius)
    elif kind == 'extrude':
        vertices = spec['vertices']
        if any(len(p) != 2 or not all(math.isfinite(v) for v in p) for p in vertices):
            raise ValueError('Polygon vertices must be finite XZ pairs')
        bottom, top = spec['bottom'], spec['top']
        if not all(math.isfinite(v) for v in (bottom, top)):
            raise ValueError('Invalid extrusion heights')
        field = grid.extruded_polygon(vertices, bottom, top)
    else:
        raise ValueError('Unsupported shape: ' + str(kind))
    if not np.all(np.isfinite(field)):
        raise ValueError('Non-finite shape field')
    return grid.mask(field)


def modelling_plan(model, operation, protected=()):
    """Return sorted writes and statistics without mutating model or wall mask.

    Explicit bounds prevent accidental whole-world operations. Protected writes
    cause refusal (rather than clipping a shape or breaking a connected effect).
    """
    kind = operation['kind']
    if kind not in KINDS:
        raise ValueError('Unknown modelling operation')
    if type(operation.get('enabled',True)) is not bool:raise ValueError('Operation enabled must be a boolean')
    if not operation.get('enabled',True):return [],dict(kind=kind,skipped=True,reason='disabled',eligible=0,changed=0)
    lo, hi = xyz(operation['lo'], True), xyz(operation['hi'], True)
    if any(lo[i] > hi[i] for i in range(3)) or not model.in_bounds(lo) or not model.in_bounds(hi):
        raise ValueError('Operation bounds exceed model')
    size = tuple(hi[i]-lo[i]+1 for i in range(3))
    if math.prod(size) > 2_000_000:
        raise ValueError('Operation exceeds 2 million voxel planning limit')
    if kind == 'auto_roof':
        from nbt_roofs import roof_plan
        return roof_plan(model, operation, protected)
    if kind == 'terrain_road':
        from nbt_terrain_roads import terrain_road_plan
        return terrain_road_plan(model, operation, protected)
    if kind == 'auto_stairs':
        from nbt_stairs import stair_plan
        return stair_plan(model, operation, protected)
    if kind == 'array_region':
        from nbt_arrays import array_plan
        return array_plan(model, operation, protected)
    if kind == 'align_region':
        from nbt_alignment import alignment_plan
        return alignment_plan(model, operation, protected)
    if kind == 'selection_replace':
        from nbt_selection import selection_plan
        return selection_plan(model, operation, protected)
    if kind == 'paste_component':
        from nbt_components import paste_plan
        return paste_plan(model, operation, protected)
    if kind == 'auto_road':
        from nbt_roads import road_plan
        return road_plan(model, operation, protected)
    points = [(x, y, z) for x in range(lo[0], hi[0]+1) for y in range(lo[1], hi[1]+1) for z in range(lo[2], hi[2]+1)]
    domain = set(points); protected = set(map(tuple, protected))
    allowed = {state(v) for v in operation['from_states']} if 'from_states' in operation else None
    selected = {p for p in points if allowed is None or model.get(p) in allowed}
    seed = operation.get('seed', 0)
    if type(seed) is not int:
        raise ValueError('Seed must be an integer')
    edits = {}; extra = {}
    value = state(operation.get('state', 'stone'))
    if kind == 'geometry':
        coordinates = tuple(np.arange(lo[i], hi[i]+1, dtype=float).reshape(tuple(size[i] if j == i else 1 for j in range(3)))+.5 for i in range(3))
        mask = shape_mask(Grid(size, coordinates), operation['geometry'])
        chosen = {tuple(int(p[i])+lo[i] for i in range(3)) for p in np.argwhere(mask)} & selected
        mode = operation.get('mode', 'set')
        if mode not in ('set', 'add', 'subtract', 'intersect'):
            raise ValueError('Invalid geometry mode')
        if mode == 'intersect':
            edits = {p: AIR for p in selected-chosen}
        else:
            edits = {p: AIR if mode == 'subtract' else value for p in chosen if mode != 'add' or model.get(p) in AIR_NAMES}
    elif kind == 'transform_region':
        turns = operation.get('quarter_turns', 0); mirror = operation.get('mirror')
        if type(turns) is not int or mirror not in (None, 'x', 'z'):
            raise ValueError('Transform needs integer quarter_turns and optional x/z mirror')
        turns %= 4
        destination = xyz(operation['destination'], True)
        move = operation.get('move', False)
        if move and allowed is not None:
            raise ValueError('Move transform cannot filter source states')
        if move:
            edits = {p: AIR for p in domain}
        for p in sorted(selected):
            v = model.get(p)
            if v in AIR_NAMES and not operation.get('include_air', False):
                continue
            x, y, z = (p[i]-lo[i] for i in range(3)); sx, _, sz = size
            if mirror == 'x': x = sx-1-x
            if mirror == 'z': z = sz-1-z
            for _ in range(turns):
                x, z, sx, sz = sz-1-z, x, sz, sx
            q = (destination[0]+x, destination[1]+y, destination[2]+z)
            if not model.in_bounds(q):
                raise ValueError('Transform destination exceeds model')
            if not operation.get('overwrite', False) and not (move and q in domain) and model.get(q) not in AIR_NAMES:
                raise ValueError('Transform destination occupied')
            edits[q] = transformed_state(v, turns, mirror)
    elif kind in ('copy_region', 'repeat_region'):
        offset = xyz(operation['offset'], True)
        count = steps(operation.get('count', 1)) if kind == 'repeat_region' else 1
        if offset == (0, 0, 0) or count == 0:
            raise ValueError('Copy needs nonzero offset/count')
        for n in range(1, count+1):
            for p in sorted(selected):
                v = model.get(p)
                if v in AIR_NAMES and not operation.get('include_air', False):
                    continue
                q = tuple(p[i]+n*offset[i] for i in range(3))
                if not model.in_bounds(q):
                    raise ValueError('Copy destination exceeds model')
                if q in edits and edits[q] != v:
                    raise ValueError('Repeated copies overlap with conflicting states')
                if not operation.get('overwrite', False) and model.get(q) not in AIR_NAMES and model.get(q) != v:
                    raise ValueError('Copy destination occupied; declare overwrite explicitly')
                edits[q] = v
    elif kind == 'replace':
        if allowed is None:
            raise ValueError('Replace requires from_states')
        edits = {p: value for p in selected}
    elif kind == 'morphology':
        occupied = {p for p in selected if model.get(p) not in AIR_NAMES}
        mode = operation.get('mode', 'dilate'); iterations = steps(operation.get('iterations', 1))
        if mode not in ('dilate', 'erode', 'shell', 'opening', 'closing'):
            raise ValueError('Invalid morphology mode')
        def evolve(source, grow):
            for _ in range(iterations):
                if grow:
                    source = source | {tuple(p[i]+d[i] for i in range(3)) for p in source for d in NEIGHBOURS if tuple(p[i]+d[i] for i in range(3)) in domain}
                else:
                    source = {p for p in source if all(tuple(p[i]+d[i] for i in range(3)) in source for d in NEIGHBOURS)}
            return source
        result = evolve(occupied, mode in ('dilate', 'closing'))
        if mode in ('opening', 'closing'):
            result = evolve(result, mode == 'opening')
        if mode == 'shell':
            result = occupied-result
        # Never overwrite unrelated solids when growing a selected material.
        edits = {p: value for p in result-occupied if model.get(p) in AIR_NAMES}
        edits.update({p: AIR for p in occupied-result})
    elif kind == 'diffusion':
        seeds = {xyz(p, True) for p in operation['seeds']}
        if not seeds or not seeds <= selected-protected:
            raise ValueError('Diffusion seeds must be in eligible, unprotected domain')
        limit = steps(operation.get('steps', 8)); decay = operation.get('decay', 0)
        if not math.isfinite(decay) or not 0 <= decay <= 1:
            raise ValueError('Decay must be 0..1')
        reached = set(seeds); queue = deque((p, 0) for p in sorted(seeds))
        surface_only = operation.get('surface_only', False)
        eligible_domain = selected-protected
        def eligible(p):
            return p in eligible_domain and (not surface_only or any(model.get(tuple(p[i]+d[i] for i in range(3))) in AIR_NAMES for d in NEIGHBOURS))
        if any(not eligible(p) for p in seeds):
            raise ValueError('Seed is not on requested surface')
        while queue:
            p, distance = queue.popleft()
            if distance == limit:
                continue
            for d in NEIGHBOURS:
                q = tuple(p[i]+d[i] for i in range(3))
                if q not in reached and eligible(q) and random_at(seed, q) >= decay*(distance+1)/max(limit, 1):
                    reached.add(q); queue.append((q, distance+1))
        edits = {p: value for p in reached}
        extra['reached'] = len(reached)
    elif kind == 'scatter':
        fraction = operation.get('fraction', .1); spacing = steps(operation.get('spacing', 1))
        if not math.isfinite(fraction) or not 0 <= fraction <= 1:
            raise ValueError('Fraction must be 0..1')
        chosen = []; buckets = {}
        for p in sorted(selected-protected, key=lambda p: (random_at(seed, p), p)):
            if random_at(seed, p) >= fraction:
                continue
            if operation.get('supported', True) and (model.get(p) not in AIR_NAMES or model.get((p[0], p[1]-1, p[2])) in AIR_NAMES):
                continue
            bucket = tuple(v//max(spacing, 1) for v in p)
            nearby = (q for dx in (-1, 0, 1) for dy in (-1, 0, 1) for dz in (-1, 0, 1)
                      for q in buckets.get((bucket[0]+dx, bucket[1]+dy, bucket[2]+dz), ()))
            if any(sum((p[i]-q[i])**2 for i in range(3)) < spacing**2 for q in nearby):
                continue
            chosen.append(p)
            buckets.setdefault(bucket, []).append(p)
        edits = {p: value for p in chosen}
    elif kind == 'explosion':
        centre = xyz(operation['centre']); radius = positive(operation['radius'])
        roughness = operation.get('roughness', .15); rays = steps(operation.get('rays', 0))
        length = positive(operation.get('ray_length', radius*1.5))
        width = positive(operation.get('ray_width', .55))
        if not math.isfinite(roughness) or not 0 <= roughness < 1:
            raise ValueError('Roughness must be in [0,1)')
        if any(centre[i]-radius*(1+roughness) < lo[i] or centre[i]+radius*(1+roughness) > hi[i]+1 for i in range(3)):
            raise ValueError('Explosion envelope exceeds declared bounds')
        directions = []
        for n in range(rays):
            v = np.array([random_at(seed, (n, j, 0), 'ray')*2-1 for j in range(3)])
            norm = np.linalg.norm(v)
            if norm > 1e-9:
                directions.append(v/norm)
        for p in selected-protected:
            if model.get(p) in AIR_NAMES:
                continue
            v = np.array([p[i]+.5-centre[i] for i in range(3)]); distance = np.linalg.norm(v)
            # Continuous low-frequency lobes avoid independent salt/pepper holes.
            perturb = sum(math.sin((p[i]+.5)*.7+seed%1009+i*2.1) for i in range(3))/3
            hit = distance <= radius*(1+roughness*perturb)
            if not hit:
                hit = any(0 <= float(v@d) <= length and np.linalg.norm(v-d*float(v@d)) <= width for d in directions)
            if hit:
                edits[p] = AIR
        extra.update(static_effect=True, physics_simulated=False, protected_skipped=len(selected & protected))
    edits = {p: v for p, v in edits.items() if model.get(p) != v}
    if any(p in protected for p in edits):
        raise ValueError('Modelling operation touches protected geometry')
    budget = operation.get('max_writes', 100000)
    if type(budget) is not int or budget < 0 or len(edits) > budget:
        raise ValueError('Modelling write budget exceeded')
    return sorted(edits.items()), dict(kind=kind, eligible=len(selected), changed=len(edits), **extra)


def apply_modelling(model, operation, wall_positions=(), protected=()):
    """New-design API only; existing reviewed assets must use nbt_refine."""
    if model.stage != 'design':
        raise ValueError('Modelling writes require design stage')
    classification = operation.get('classification', 'body')
    if classification not in ('body', 'wall', 'inherit'):
        raise ValueError('Invalid wall classification')
    edits, report = modelling_plan(model, operation, protected)
    walls = set(wall_positions)
    for p, v in edits:
        model.put(p, v)
        if v in AIR_NAMES or classification == 'body':
            walls.discard(p)
        elif classification == 'wall':
            walls.add(p)
    return walls, report


def main():
    import argparse
    import json
    from pathlib import Path
    from nbt_refine import read_master
    parser = argparse.ArgumentParser(description='Read-only modelling plan; writes edits JSON, never assets')
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--operation', type=Path, required=True)
    parser.add_argument('--protected', type=Path, help='Optional JSON array of protected XYZ voxels')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    model, _ = read_master(args.source)
    operation = json.loads(args.operation.read_text(encoding='utf8'))
    protected = json.loads(args.protected.read_text(encoding='utf8')) if args.protected else []
    edits, report = modelling_plan(model, operation, protected)
    payload = dict(source_geometry_sha256=model.fingerprint(), operation=operation,
                   edits=edits, report=report, asset_written=False, runtime_verified=False)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf8') as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)
    print(json.dumps(report))


if __name__ == '__main__':
    main()
