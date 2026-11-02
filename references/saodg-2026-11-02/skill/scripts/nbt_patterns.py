"""Explicit weighted block patterns on the whole model; conversions never opt in implicitly."""
import argparse
from bisect import bisect
from collections import Counter
from functools import lru_cache
import hashlib
import itertools
import json
import math
from pathlib import Path
from statistics import NormalDist

from nbt_model import AIR_NAMES, compound, state
from nbt_registry import effective, registry
from nbt_collision import collision_cells

DELTAS = ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))


def _point(value):
    if not isinstance(value, (list, tuple)) or len(value) != 3 or any(type(v) is not int for v in value):
        raise ValueError('Expected integer XYZ coordinates')
    return tuple(value)


def _number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f'{label} must be a finite number')
    return value


def _uniform(seed, channel, position):
    digest = hashlib.sha256(f'{seed}:{channel}:{tuple(position)}'.encode()).digest()
    return (int.from_bytes(digest[:8], 'big') >> 11) / 2**53


def _sampler(seed, mode, scale):
    normal = NormalDist()

    @lru_cache(maxsize=65536)
    def gaussian(channel, vertex):
        u = min(1 - 2**-53, max(2**-53, _uniform(seed, channel, vertex)))
        return normal.inv_cdf(u)

    def sample(channel, position):
        if mode == 'independent':
            return _uniform(seed, channel, position)
        t = [(position[i] + .5) / scale[i] for i in range(3)]
        base = [math.floor(v) for v in t]
        blends = [v - math.floor(v) for v in t]
        blends = [v*v*(3 - 2*v) for v in blends]
        value, variance = 0.0, 0.0
        for corner in itertools.product((0, 1), repeat=3):
            weight = math.prod(blends[i] if corner[i] else 1 - blends[i] for i in range(3))
            vertex = tuple(base[i] + corner[i] for i in range(3))
            value += weight * gaussian(channel, vertex)
            variance += weight*weight
        # Variance normalization plus the Gaussian CDF retains uniform marginals;
        # ordinary interpolated uniform noise would bias palette weights toward 0.5.
        return min(1 - 2**-53, normal.cdf(value / math.sqrt(variance)))

    return sample


def pattern_plan(model, operation, protected=()):
    """Return (edits, report) without changing geometry, stage, wall masks or sources.

    Probabilities are expected proportions, not exact quotas. All sampling uses
    global coordinates and independent coverage/material channels, never iteration order.
    """
    supported = {'kind', 'label', 'classification', 'action', 'lo', 'hi', 'from_states',
                 'palette', 'fraction', 'seed', 'mode', 'scale', 'coordinate_origin',
                 'scope', 'mask_positions', 'preserve_properties', 'shape_policy'}
    if not isinstance(operation, dict) or set(operation) - supported:
        raise ValueError('Unknown pattern fields or invalid operation object')
    if operation.get('kind', 'pattern') != 'pattern':
        raise ValueError('Expected kind=pattern')
    action = operation.get('action', 'replace')
    scope = operation.get('scope', 'volume')
    mode = operation.get('mode', 'independent')
    classification = operation.get('classification', 'inherit')
    shape_policy = operation.get('shape_policy', 'preserve' if action == 'replace' else 'any')
    if action not in ('replace', 'fill') or scope not in ('volume', 'surface') or mode not in ('independent', 'clustered'):
        raise ValueError('Invalid action, scope or random mode')
    if shape_policy not in ('preserve', 'any') or classification not in ('inherit', 'wall', 'body'):
        raise ValueError('Invalid shape_policy or classification')
    preserve = operation.get('preserve_properties', True)
    if type(preserve) is not bool:
        raise ValueError('preserve_properties must be boolean')
    lo, hi = _point(operation['lo']), _point(operation['hi'])
    if any(lo[i] > hi[i] or lo[i] < 0 or hi[i] >= model.size[i] for i in range(3)):
        raise ValueError('Pattern bounds must be ordered and within the complete source')
    origin = _point(operation.get('coordinate_origin', [0, 0, 0]))
    fraction = _number(operation.get('fraction', 1.0), 'fraction')
    if not 0 <= fraction <= 1:
        raise ValueError('fraction must be 0..1')
    seed = operation.get('seed', 0)
    if type(seed) is not int:
        raise ValueError('seed must be an integer')
    scale = operation.get('scale', 6)
    scale = [scale]*3 if isinstance(scale, (int, float)) else scale
    if not isinstance(scale, (list, tuple)) or len(scale) != 3 or any(_number(v, 'scale') < 1 for v in scale):
        raise ValueError('scale must contain three finite values >=1, or one scalar')
    raw_palette = operation['palette']
    if not isinstance(raw_palette, list) or not 1 <= len(raw_palette) <= 4096:
        raise ValueError('palette must contain 1..4096 entries')
    merged = {}
    for entry in raw_palette:
        if isinstance(entry, str):
            value, weight = state(entry), 1
        elif isinstance(entry, dict) and set(entry) <= {'state', 'weight'} and 'state' in entry:
            value, weight = state(entry['state']), _number(entry.get('weight', 1), 'weight')
        else:
            raise ValueError('Palette entries are states or {state, weight} objects')
        if weight < 0 or value.split('[')[0] in AIR_NAMES:
            raise ValueError('Weights must be nonnegative; pattern targets cannot be air')
        merged.setdefault(value, []).append(weight)
    maximum = max(weight for weights in merged.values() for weight in weights)
    if maximum <= 0:
        raise ValueError('At least one palette weight must be positive')
    weighted = [(value, math.fsum(weight / maximum for weight in weights)) for value, weights in merged.items()]
    weighted = [(value, weight) for value, weight in weighted if weight > 0]
    total = math.fsum(weight for _, weight in weighted)
    probabilities = [weight / total for _, weight in weighted]
    cdf, cumulative = [], 0.0
    for probability in probabilities:
        cumulative += probability
        cdf.append(cumulative)
    cdf[-1] = 1.0
    selectors = operation.get('from_states')
    if action == 'fill' and selectors is not None:
        raise ValueError('fill does not accept from_states; use replace for source filtering')
    if selectors is not None:
        if not isinstance(selectors, list) or not selectors:
            raise ValueError('from_states must be a non-empty state selector list')
        selectors = [compound(state(v)) for v in selectors]
    protected = {_point(p) for p in protected}
    if 'mask_positions' in operation:
        if not isinstance(operation['mask_positions'], (list, tuple)):
            raise ValueError('mask_positions must be an XYZ list')
        points = [_point(p) for p in operation['mask_positions']]
        if len(set(points)) != len(points) or any(any(p[i] < lo[i] or p[i] > hi[i] for i in range(3)) for p in points):
            raise ValueError('Mask positions must be unique and inside pattern bounds')
        points = sorted(points)
    else:
        points = itertools.product(*(range(lo[i], hi[i] + 1) for i in range(3)))
    sample = _sampler(seed, mode, scale)

    @lru_cache(maxsize=8192)
    def matches(value):
        name, props = effective(value)
        if selectors is None:
            return action == 'fill' or name not in AIR_NAMES
        return any(name == selector['Name'] and all(props.get(k) == v for k, v in selector.get('Properties', {}).items())
                   for selector in selectors)

    @lru_cache(maxsize=8192)
    def resolve(value, target):
        old_name, old_props = effective(value)
        data = compound(target)
        props = {}
        if preserve:
            allowed = registry()['blocks'][data['Name']]['properties']
            props.update({key: val for key, val in old_props.items() if val in allowed.get(key, ())})
        props.update(data.get('Properties', {}))  # Explicit target properties win.
        after = state(dict(Name=data['Name'], Properties=props))
        if effective(after) == (old_name, old_props):
            return state(value)
        if shape_policy == 'preserve':
            before_cells, before_reason = collision_cells(value)
            after_cells, after_reason = collision_cells(after)
            if before_reason or after_reason or set(before_cells) != set(after_cells):
                raise ValueError(f'Pattern cannot certify unchanged collision shape: {value} -> {after}; use explicit shape_policy=any only with separate validation')
        return after

    edits, sampled, resulting = [], Counter(), Counter()
    eligible = skipped = sampled_count = excluded = geometry_changed = 0
    before_hash = model.fingerprint()
    occupied_cells = getattr(model, 'cells', None)
    for p in points:
        if not model.in_bounds(p) or (occupied_cells is not None and (p[0] // 48, p[2] // 48) not in occupied_cells):
            excluded += 1
            continue
        value = model.get(p)
        if not matches(value):
            continue
        if scope == 'surface' and (value in AIR_NAMES or not any(model.get(tuple(p[i] + d[i] for i in range(3))) in AIR_NAMES for d in DELTAS)):
            continue
        if p in protected:
            skipped += 1
            continue
        eligible += 1
        global_position = tuple(p[i] + origin[i] for i in range(3))
        if fraction < 1 and sample('coverage', global_position) >= fraction:
            resulting[value] += 1
            continue
        target_index = min(bisect(cdf, sample('material', global_position)), len(weighted) - 1)
        after = resolve(value, weighted[target_index][0])
        sampled[after] += 1
        resulting[after] += 1
        sampled_count += 1
        if after != value:
            geometry_changed += 1
        if after != value or classification != 'inherit':
            edits.append((p, after))
    report = dict(kind='pattern', action=action, scope=scope, mode=mode, seed=seed, scale=list(scale),
                  coordinate_origin=list(origin), fraction=fraction, shape_policy=shape_policy,
                  preserve_properties=preserve, classification=classification,
                  palette_probabilities=[dict(state=v, probability=probabilities[i]) for i, (v, _) in enumerate(weighted)],
                  eligible=eligible, protected_skipped=skipped, footprint_skipped=excluded,
                  sampled=sampled_count, changed=geometry_changed, candidate_writes=len(edits),
                  sampled_states=dict(sorted(sampled.items())), resulting_states=dict(sorted(resulting.items())),
                  source_geometry_sha256=before_hash, source_unchanged=model.fingerprint() == before_hash,
                  plan_only=True,
                  ratio_policy='Expected probabilities; not exact quotas. Changed counts exclude same-state samples.',
                  collision_scope='Authoring shape approximation only; no game, connectivity or sealing certification')
    return edits, report


def apply_pattern(model, operation, wall_positions=(), protected=()):
    """Draft-generation API. Finish WallMask tracking before calling; return new mask/report.

    Existing reviewed assets use the CLI apply/refinement path, never this as an approval bypass.
    """
    if model.stage != 'design':
        raise ValueError('Apply patterns on the whole draft before sealing; reviewed assets use refinement')
    walls = {_point(p) for p in wall_positions}
    original_walls = set(walls)
    if any(not model.in_bounds(p) for p in walls):
        raise ValueError('Wall mask exceeds source bounds')
    edits, report = pattern_plan(model, operation, protected)
    classification = operation.get('classification', 'inherit')
    for p, value in edits:
        model.put(p, value)
        if classification == 'wall':
            walls.add(p)
        elif classification == 'body':
            walls.discard(p)
    report['result_geometry_sha256'] = model.fingerprint()
    report['source_unchanged'] = report['result_geometry_sha256'] == report['source_geometry_sha256']
    report['wall_membership_changed'] = len(walls ^ original_walls)
    report['plan_only'] = False
    return walls, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    plan = sub.add_parser('plan', help='Read-only edit plan; no changed model is exported')
    plan.add_argument('--source', type=Path, required=True)
    apply = sub.add_parser('apply', help='Delegate to reviewed whole-model refinement')
    apply.add_argument('--review', type=Path, required=True)
    apply.add_argument('--style-note', required=True)
    for command in (plan, apply):
        command.add_argument('--operation', type=Path, required=True)
        command.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    operation = json.loads(args.operation.read_text(encoding='utf-8-sig'))
    operation.setdefault('kind', 'pattern')
    operation.setdefault('label', 'Explicit whole-model block pattern')
    if args.command == 'apply':
        from nbt_refine import refine
        result = refine(args.review, dict(style_note=args.style_note, operations=[operation]), args.output)
        print(json.dumps({k: result[k] for k in ('state', 'changed_blocks')}, ensure_ascii=False))
    else:
        from nbt_refine import read_master
        model, _ = read_master(args.source)
        edits, report = pattern_plan(model, operation)
        if args.output.exists():
            raise FileExistsError('Choose a new plan directory')
        args.output.mkdir(parents=True)
        (args.output / 'pattern_plan.json').write_text(json.dumps(dict(report=report, operation=operation,
            edits=[dict(position=list(p), state=value) for p, value in edits]), ensure_ascii=False, indent=2) + '\n', encoding='utf8')
        print(json.dumps(dict(changed=report['changed'], candidate_writes=len(edits), source_unchanged=True, output=str(args.output.resolve())), ensure_ascii=False))


if __name__ == '__main__':
    main()
