"""Read-only sparse model differences shared by the CLI and desktop viewer."""
from collections import defaultdict, deque
from pathlib import Path
import hashlib
import json
from nbt_model import AIR


def describe(before, after, old_walls, new_walls):
    """Lossless X runs, including wall-only changes; all bounds are inclusive XYZ."""
    old_walls, new_walls = set(map(tuple, old_walls)), set(map(tuple, new_walls))
    counts = dict(added=0, removed=0, replaced=0, wall=0)
    rows, chunks = defaultdict(list), {}
    layer_changes = 0
    for p in before.blocks.keys() | after.blocks.keys():
        a, b = before.blocks.get(p, AIR), after.blocks.get(p, AIR)
        aw, bw = p in old_walls and p in before.blocks, p in new_walls and p in after.blocks
        layer_changes += aw != bw
        if a == b and aw == bw:
            continue
        if a == b:
            kind = 'wall'
        elif a.split('[')[0] in ('minecraft:air', 'minecraft:cave_air', 'minecraft:void_air') and b.split('[')[0] not in ('minecraft:air', 'minecraft:cave_air', 'minecraft:void_air'):
            kind = 'added'
        elif b.split('[')[0] in ('minecraft:air', 'minecraft:cave_air', 'minecraft:void_air') and a.split('[')[0] not in ('minecraft:air', 'minecraft:cave_air', 'minecraft:void_air'):
            kind = 'removed'
        else:
            kind = 'replaced'
        counts[kind] += 1
        x, y, z = p
        rows[(kind, y, z, aw, bw)].append(x)
        key = tuple(n // 16 for n in p)
        item = chunks.setdefault(key, dict(lo=list(p), hi=list(p), count=0))
        item['count'] += 1
        item['lo'] = [min(a, b) for a, b in zip(item['lo'], p)]
        item['hi'] = [max(a, b) for a, b in zip(item['hi'], p)]
    runs = []
    for (kind, y, z, aw, bw), xs in sorted(rows.items()):
        xs.sort()
        start = previous = xs[0]
        for x in xs[1:] + [None]:
            if x != previous + 1:
                runs.append([kind, start, y, z, previous - start + 1, aw, bw])
                start = x
            previous = x
    regions, remaining = [], set(chunks)
    for seed in sorted(chunks):
        if seed not in remaining:
            continue
        remaining.remove(seed)
        queue, members = deque([seed]), []
        while queue:
            key = queue.popleft()
            members.append(chunks[key])
            for axis in range(3):
                for step in (-1, 1):
                    neighbor = list(key)
                    neighbor[axis] += step
                    neighbor = tuple(neighbor)
                    if neighbor in remaining:
                        remaining.remove(neighbor)
                        queue.append(neighbor)
        regions.append(dict(lo=[min(m['lo'][i] for m in members) for i in range(3)],
                            hi=[max(m['hi'][i] for m in members) for i in range(3)],
                            count=sum(m['count'] for m in members)))
    regions.sort(key=lambda r: (-r['count'], r['lo']))
    bounds = dict(lo=[min(r['lo'][i] for r in regions) for i in range(3)],
                  hi=[max(r['hi'][i] for r in regions) for i in range(3)]) if regions else None
    return dict(schema_version=1, counts=counts, changed_blocks=sum(counts[k] for k in ('added', 'removed', 'replaced')),
                wall_membership_changes=layer_changes, changed_positions=sum(counts.values()),
                before_size=list(before.size), after_size=list(after.size), bounds=bounds,
                regions=regions, region_grouping='connected_16_block_chunks', runs=runs,
                alignment='local_xyz_origin', model_modified=False, validation_performed=False)


def compare_sources(request, output):
    from nbt_refine import read_master
    from nbt_task import inspect_source
    source, reference = Path(request['source']).resolve(), Path(request['reference_source']).resolve()
    def digest(file):
        with file.open('rb') as stream:
            return hashlib.file_digest(stream, 'sha256').hexdigest()
    hashes = [digest(reference), digest(source)]
    for key, expected in [('reference_sha256', hashes[0]), ('source_sha256', hashes[1])]:
        if request.get(key) and request[key] != expected:
            raise ValueError('对比源已变化，请刷新建筑后重试：' + key)
    before, old_walls = read_master(reference)
    after, new_walls = read_master(source)
    result = describe(before, after, old_walls, new_walls)
    result.update(before_source_sha256=hashes[0], after_source_sha256=hashes[1],
                  before_geometry_sha256=before.fingerprint(), after_geometry_sha256=after.fingerprint())
    snapshots = [inspect_source(reference), inspect_source(source)]
    if hashes != [digest(reference), digest(source)] or any(s['source_sha256'] != h or s['geometry_sha256'] != m.fingerprint() for s, h, m in zip(snapshots, hashes, (before, after))):
        raise ValueError('对比过程中源建筑发生变化，请重试')
    sx, sy, sz = after.size
    snapshots[1]['cameras'] = [dict(id='whole', role='whole', eye=[sx*1.5, sy*1.5, -sz], target=[sx/2, sy/2, sz/2], cuts=[])]
    target = Path(output).resolve()
    target.mkdir(parents=True, exist_ok=False)
    for name, data in [('before.json', snapshots[0]), ('after.json', snapshots[1]), ('difference.json', result)]:
        (target / name).write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf8')
    return dict(status='versions_compared', source=str(source), reference_source=str(reference),
                snapshot=str(target / 'after.json'), baseline_snapshot=str(target / 'before.json'),
                difference=str(target / 'difference.json'), size=list(after.size), reference_size=list(before.size),
                source_sha256=hashes[1], reference_sha256=hashes[0], geometry_sha256=after.fingerprint(),
                cameras=snapshots[1]['cameras'], reference_cameras=snapshots[0]['cameras'],
                changed_blocks=result['changed_blocks'], wall_membership_changes=result['wall_membership_changes'],
                changed_positions=result['changed_positions'], counts=result['counts'],
                model_modified=False, validation_performed=False, output=str(target))
