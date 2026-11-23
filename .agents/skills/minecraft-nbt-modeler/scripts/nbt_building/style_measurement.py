"""Measure authored style targets in a fixed ZYX voxel region."""
from itertools import chain
from math import floor, prod

import numpy as np

METHOD = 'style-geometry-z-v1'
MAX_REGION_VOXELS = 1_048_576
MAX_PLAN_VOXELS = 8 * MAX_REGION_VOXELS
EPSILON = 1e-12


def size(lo, hi):
    return [b - a + 1 for a, b in zip(lo, hi)]


def inside_box(inner, outer):
    return all(a <= b <= c <= d for a, b, c, d in
               zip(outer['lo'], inner['lo'], inner['hi'], outer['hi']))


def band_mask(frequencies, band):
    return ((frequencies >= band.get('low', 0) - EPSILON) &
            (frequencies <= band.get('high', .5) + EPSILON))


def validate(config, plan_size, parts, materials, site):
    region = config['region']
    canvas = {'lo': [0, 0, 0], 'hi': [n - 1 for n in plan_size]}
    if not inside_box(region, canvas):
        raise ValueError('风格量化采样范围越界或倒置：' + site)
    extent = size(**region)
    if extent[2] < 2 or prod(extent) > MAX_REGION_VOXELS:
        raise ValueError('风格量化范围至少含两层 Z，且最多 1048576 格：' + site)
    frequencies = np.fft.rfftfreq(extent[2])
    kinds = set()
    for band in config['bands']:
        kind = band['kind']
        fields = {'lowpass': {'high'}, 'highpass': {'low'}, 'bandpass': {'low', 'high'}}[kind]
        if (kind in kinds or set(band) - {'kind'} != fields or
                band.get('low', 0) >= band.get('high', .5) or
                ('low' in band and band['low'] <= 0) or
                ('high' in band and band['high'] >= .5) or
                not band_mask(frequencies, band).any()):
            raise ValueError('风格频带重复、参数无效或采样长度不足以分辨所选频段：' + site)
        kinds.add(kind)
    names = set()
    for member in config['members']:
        name = member['part']
        if name in names or name not in parts or set(member['roles']) - materials.keys():
            raise ValueError('风格量化构件重复、不存在或引用未知材质角色：' + name)
        names.add(name)
        variants = {variant['id'] for variant in member.get('variants', [])}
        if 'default' in variants or len(variants) != len(member.get('variants', [])):
            raise ValueError('风格量化变体 ID 重复或使用保留名 default：' + name)
        boxes = chain(member['boxes'], *(variant['boxes'] for variant in member.get('variants', [])))
        if any(not inside_box(box, region) for box in boxes):
            raise ValueError('风格量化目标体素盒超出采样范围：' + name)
    return prod(extent)


def bounds(points):
    return dict(lo=points.min(axis=0).tolist(), hi=points.max(axis=0).tolist())


def box_slices(box, origin):
    return tuple(slice(a - offset, b - offset + 1) for a, b, offset in
                 reversed(list(zip(box['lo'], box['hi'], origin))))


def reference(boxes):
    box = dict(lo=[min(b['lo'][i] for b in boxes) for i in range(3)],
               hi=[max(b['hi'][i] for b in boxes) for i in range(3)])
    mask = np.zeros(size(**box)[::-1], dtype=bool)
    for fill in boxes:
        mask[box_slices(fill, box['lo'])] = True
    return box, mask


def within(points, box):
    return points[np.all((points >= box['lo']) & (points <= box['hi']), axis=1)]


def indices(points, origin):
    return tuple((points - origin).T[::-1])


def match_variant(points, member):
    variants = [dict(id='default', boxes=member['boxes'])]
    if len(points):
        variants.extend(member.get('variants', []))
    best = None
    for variant in variants:
        box, mask = reference(variant['boxes'])
        hits = np.count_nonzero(mask[indices(within(points, box), box['lo'])])
        difference = len(points) + np.count_nonzero(mask) - 2 * hits
        if best is None or difference < best[0]:
            best = (difference, variant['id'], box, mask)
    return best


def member_evidence(model, binding, plan, member, region, actual, expected):
    from nbt_building.plan import actual_part, effective_name, material_role_names

    identifier = member['part']
    try:
        _, occupied = actual_part(model, binding, identifier)
    except ValueError:
        occupied = ()
    points = np.asarray(sorted(occupied), dtype=np.int64).reshape(-1, 3)
    difference, variant, target, mask = match_variant(points, member)
    expected[box_slices(target, region['lo'])] |= mask
    actual[indices(within(points, region), region['lo'])] = True
    allowed = material_role_names(plan, member['roles'])
    violations = []
    correct = 0
    for pos in points.tolist():
        state = model.model.get(tuple(pos))
        if effective_name(state) in allowed:
            correct += 1
        elif len(violations) < 8:
            violations.append(dict(position=pos, state=state))
    target_size = size(**target)
    row = dict(part=identifier, variant=variant, expected_bounds=target, expected_size=target_size,
               occupied=len(points), different_voxels=int(difference), material_roles=member['roles'],
               allowed_materials=sorted(allowed), matching_material_voxels=correct,
               material_fit=correct / len(points) if len(points) else 0, material_violations=violations,
               actual_bounds=None, actual_size=None, delta_size=None, delta_origin=None,
               size_fit=0, placement_fit=0)
    if len(points):
        measured = bounds(points)
        measured_size = size(**measured)
        offset = [a - b for a, b in zip(measured['lo'], target['lo'])]
        tail_offset = [a - b for a, b in zip(measured['hi'], target['hi'])]
        row.update(actual_bounds=measured, actual_size=measured_size, delta_origin=offset,
                   delta_size=[a - b for a, b in zip(measured_size, target_size)],
                   size_fit=sum(min(a, b) / max(a, b) for a, b in zip(measured_size, target_size)) / 3,
                   placement_fit=1 / (1 + max(map(abs, offset + tail_offset))))
    row['dimension_fit'] = (row['size_fit'] + row['placement_fit']) / 2
    return row


def band_evidence(actual, expected, region, bands):
    n = actual.shape[0]
    frequencies = np.fft.rfftfreq(n)
    actual_fft = np.fft.rfft(actual, axis=0)
    expected_fft = np.fft.rfft(expected, axis=0)
    mismatches = np.flatnonzero(actual != expected)
    result = []
    for band in bands:
        selected = band_mask(frequencies, band)
        mask = selected[:, None, None]
        left = np.fft.irfft(actual_fft * mask, n=n, axis=0)
        right = np.fft.irfft(expected_fft * mask, n=n, axis=0)
        residual = left - right
        magnitude = np.linalg.norm(left.ravel()) + np.linalg.norm(right.ravel())
        error = np.linalg.norm(residual.ravel()) / magnitude if magnitude > EPSILON else 0
        weights = np.abs(residual.ravel()[mismatches])
        strongest = np.argsort(-weights, kind='stable')[:8]
        points = []
        for rank in strongest:
            if weights[rank] <= EPSILON:
                break
            flat = mismatches[rank]
            z, y, x = np.unravel_index(flat, actual.shape)
            position = [int(v) + origin for v, origin in zip((x, y, z), region['lo'])]
            points.append(dict(position=position, state='unexpected' if actual[z, y, x] else 'missing',
                               response=round(float(residual[z, y, x]), 8)))
        result.append(dict(band, frequencies_per_block=frequencies[selected].tolist(),
                           fit=max(0., 1 - float(error)), mismatches=points))
    return result


def finding(members, bands):
    worst = min(members, key=lambda row: (row['dimension_fit'] + row['material_fit'], -row['different_voxels']))
    part = worst['part']
    positions = [point['position'] for band in bands for point in band['mismatches']]
    if not worst['occupied']:
        note = f'预期构件 {part} 缺失。'
        suggestion = '在登记的构件范围添加该构件并核对材质角色。'
        position = worst['expected_bounds']['lo']
    elif (worst['delta_origin'][2] and worst['delta_size'][2] == 0):
        shift = worst['delta_origin'][2]
        note = f'构件 {part} 沿 Z 偏移 {shift:+d} 格。'
        suggestion = f'按登记构造检查该构件，沿 Z 复位 {-shift:+d} 格后复验。'
        position = worst['actual_bounds']['lo']
    elif worst['material_violations']:
        note = f'构件 {part} 的方块不符合已登记材质角色。'
        suggestion = '检查列出的方块状态，并按登记材质角色替换相应构件材料。'
        position = worst['material_violations'][0]['position']
    else:
        note = f'构件 {part} 或所在部位的占用范围与登记构造有偏差。'
        suggestion = '从原始方块复核列出的尺寸与占用坐标，按已登记构造调整。'
        position = positions[0] if positions else worst['actual_bounds']['lo']
    return dict(note=note, suggestion=suggestion, position=position, part=part)


def measure(model, binding, plan, config):
    region = config['region']
    shape = size(**region)[::-1]
    actual = np.zeros(shape, dtype=bool)
    expected = np.zeros(shape, dtype=bool)
    members = [member_evidence(model, binding, plan, row, region, actual, expected) for row in config['members']]
    bands = band_evidence(actual, expected, region, config['bands'])
    fits = dict(frequency=sum(b['fit'] for b in bands) / len(bands),
                dimensions=sum(m['dimension_fit'] for m in members) / len(members),
                materials=sum(m['material_fit'] for m in members) / len(members))
    result = dict(method=METHOD, axis='z', axis_order='zyx', region=region, bands=bands, members=members,
                  family_fits=fits, missing=not any(member['occupied'] for member in members))
    if min(fits.values()) < 1 - EPSILON:
        result.update(finding(members, bands))
    return result


def grade(proof, observed=None):
    fits = list(proof['family_fits'].values())
    if observed is not None:
        fits.append(observed['grade'] / 4)
    score = 0 if proof['missing'] else sum(fits) / len(fits)
    proof['fit'] = round(score, 8)
    return min(4, floor(4 * score + EPSILON))
