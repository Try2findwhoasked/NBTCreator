"""Build a three-bay hall and preview a wavelet transfer through the shared CLI."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.agents/skills/minecraft-nbt-modeler/scripts'))

from nbt_collision import collision_cells
from nbt_composition.preflight import bounds
from nbt_refine import read_master
from nbt_composition.working_model import WorkingModel, digest, file_hash, write_json


def tile(depth, inward):
    return {
        0: 'spruce_slab[type=top,waterlogged=false]',
        1: f'spruce_stairs[facing={inward},half=top,shape=straight,waterlogged=false]',
        2: 'spruce_slab[type=double,waterlogged=false]',
    }[depth]


def fixture(workspace):
    cameras = [
        dict(id='overview', eye=[57, 26, -27], target=[27, 7, 11], fov=55),
        dict(id='left_seam', eye=[9, 5, -1], target=[16, 8.35, 4.5], fov=51),
        dict(id='right_seam', eye=[44, 5, -1], target=[37, 8.35, 4.5], fov=51),
        dict(id='underside', eye=[25.5, 5.5, -6], target=[26.5, 8.4, 5], fov=60),
        dict(id='reference', eye=[28, 5.5, 29], target=[26.5, 8.4, 18], fov=60),
    ]
    context = dict(mode='standalone', openings=[], require_routes=True,
                   start=[6.5, 2, 10.5], targets=[[46.5, 2, 10.5]],
                   max_changed_blocks=12000)
    host = WorkingModel(workspace, [54, 21, 23], context)

    def box(lo, hi, value, classification='body'):
        return dict(kind='box', label='廊屋方块', lo=lo, hi=hi, state=value, classification=classification)

    operations = [
        box([1, 0, 2], [52, 1, 20], 'stone_bricks'),
        box([3, 8, 5], [50, 8, 5], 'stripped_dark_oak_log[axis=x]'),
        box([3, 8, 17], [50, 8, 17], 'stripped_dark_oak_log[axis=x]'),
        box([3, 2, 6], [3, 8, 16], 'stone_bricks', 'wall'),
        box([50, 2, 6], [50, 8, 16], 'stone_bricks', 'wall'),
        dict(kind='auto_roof', label='廊屋双坡顶', lo=[3, 9, 4], hi=[50, 17, 18], ridge_axis='x', rise=5, roof='gable',
             thickness=1, finish='slabs', state='deepslate_tiles',
             slab_state='deepslate_tile_slab[type=bottom,waterlogged=false]'),
    ]
    for x in (3, 14, 39, 50):
        for z in (5, 17):
            operations.append(box([x, 2, z], [x, 2, z], 'polished_andesite'))
            operations.append(box([x, 3, z], [x, 7, z], 'stripped_spruce_log[axis=y]'))
    for x in range(3, 51):
        front = 1 if 14 <= x <= 39 else 2
        reference = (1, 2, 2, 1, 0, 0)[(38 - x) % 6] if 15 <= x <= 38 else front
        operations.extend((box([x, 8, 4], [x, 8, 4], tile(front, 'south')),
                           box([x, 8, 18], [x, 8, 18], tile(reference, 'north'))))
    # Construct the fixture before binding its retained constraints.
    host.apply_operations(operations)
    host.context['protected_boxes'] = [dict(lo=[1, 0, 2], hi=[52, 1, 20]),
                                       dict(lo=[3, 8, 4], hi=[14, 8, 4]),
                                       dict(lo=[39, 8, 4], hi=[50, 8, 4])]
    host.context['max_changed_blocks'] = 32
    host._baseline.blocks = dict(host.model.blocks)
    host._baseline_walls = set(host.walls)
    # Separately managed geometry makes the ownership check nonempty.
    host.install('stone_bench', dict(tool='structure', arguments=dict(
        name='石凳', size=[3, 1, 1], operations=[box([0, 0, 0], [2, 0, 0], 'andesite')])),
        position=[7, 2, 14])
    goal = dict(target=dict(start=[15, 8, 4], length=24, along='east', inward='south'),
                reference=dict(start=[38, 8, 18], length=24, along='west', inward='north'),
                ridge=dict(lo=[3, 14, 11], hi=[50, 15, 11]),
                materials=dict(slab='spruce_slab', stair='spruce_stairs'),
                levels=[1, 2], taper=4, strengths=[0.25, 0.75, 1, 1.25, 1.75])
    return host, goal, cameras


def half_geometry(model):
    occupied = set()
    for p, value in model.blocks.items():
        cells, reason = collision_cells(value)
        if reason:
            raise ValueError(f'Example has unknown collision shape at {p}: {value}')
        occupied.update(tuple(2*v+h for v, h in zip(p, cell)) for cell in cells)
    return occupied


def geometry_evidence(before, after, goal):
    """Independently enumerate the complete silhouettes from the disk models."""
    old, new = half_geometry(before), half_geometry(after)
    projections = {}
    for axis, name in enumerate('xyz'):
        a, b = ({p[:axis] + p[axis+1:] for p in cells} for cells in (old, new))
        projections[name] = dict(before=len(a), after=len(b), changed=len(a ^ b),
                                 before_sha256=digest(sorted(a)), after_sha256=digest(sorted(b)))
    ridge = goal['ridge']
    ridge_before, ridge_after = (
        sorted((p, v) for p, v in model.blocks.items()
               if all(a <= c <= b for a, b, c in zip(ridge['lo'], ridge['hi'], p)))
        for model in (before, after)
    )
    return dict(added_half_cells=len(new - old), removed_half_cells=len(old - new),
                bounds_half_before=bounds(old), bounds_half_after=bounds(new), projections=projections,
                ridge=dict(region=ridge, blocks=len(ridge_before), unchanged=ridge_before == ridge_after,
                           sha256=digest(ridge_before)))


def run(workspace, *, adopt=False):
    workspace = Path(workspace).resolve()
    workspace.mkdir(parents=True, exist_ok=False)
    fixture_host, goal, cameras = fixture(workspace)
    saved = fixture_host.save_draft(name_zh='三开间檐下廊屋')
    source = dict(source=saved['source'], source_sha256=saved['source_sha256'])

    def model(name, request):
        file = workspace / f'{name}.json'
        write_json(file, dict(source, **request))
        result = subprocess.run(
            ['node', str(ROOT / 'scripts/cli.mjs'), '--workspace', str(workspace), 'model', '--request', str(file)],
            capture_output=True, encoding='utf-8', cwd=ROOT,
        )
        if result.returncode:
            raise RuntimeError(result.stdout or result.stderr)
        return json.loads(result.stdout)['result']

    report = model('search', dict(actions=[dict(method='wavelet_eave', goal=goal,
                                               preview=dict(output='preview', cameras=cameras))]))['actions'][0]
    report_file = workspace / 'wavelet-eave-report.json'
    write_json(report_file, report)
    best = report['best']
    if best is None:
        raise RuntimeError(f'檐口样例没有合法候选。详见 {report_file}')
    before, old_walls = read_master(saved['source'])
    after, new_walls = read_master(report['preview']['source'])
    evidence = geometry_evidence(before, after, goal)
    changed = sorted(p for p in before.blocks.keys() | after.blocks.keys() if before.get(p) != after.get(p))
    protected = {p for p in before.blocks if any(all(a <= c <= b for a, b, c in zip(box['lo'], box['hi'], p))
                                                for box in fixture_host.context['protected_boxes'])}
    evidence.update(changed_positions=changed, protected_occupied=len(protected),
                    protected_changed=len(protected.intersection(changed)),
                    outside_bay_changed=len(set(changed) - set(map(tuple, report['curves']['target_positions']))),
                    wall_changes=len(old_walls ^ new_walls), before=source,
                    preview=dict(source=report['preview']['source'], source_sha256=file_hash(report['preview']['source'])),
                    ownership_changes=None)
    assert set(changed) == {tuple(row['pos']) for row in best['edits']}
    assert changed and not evidence['outside_bay_changed'] and not evidence['protected_changed']
    assert not evidence['wall_changes'] and evidence['ridge']['unchanged']
    assert evidence['bounds_half_before'] == evidence['bounds_half_after']
    assert all(not row['changed'] for row in evidence['projections'].values())

    action = dict(method='adopt_wavelet_eave', goal=goal, strength=best['strength'],
                  candidate_sha256=best['candidate_sha256'])
    adoption = dict(actions=[action], validate=True, save_draft={})
    adoption_file = workspace / 'adopt.json'
    write_json(adoption_file, dict(source, **adoption))
    if adopt:
        production = model('adopt', adoption)['saved']
        reopened = WorkingModel.open(workspace, production['source'], source_sha256=production['source_sha256'])
        old_owners, new_owners = fixture_host._owned_positions(), reopened._owned_positions()
        evidence['ownership_changes'] = sum(old_owners.get(p) != new_owners.get(p) for p in old_owners.keys() | new_owners.keys())
        evidence['owned_positions'] = len(old_owners)
        assert reopened.model.blocks == after.blocks and reopened.walls == new_walls and old_owners == new_owners
        evidence['saved'] = production
    evidence_file = workspace / 'readback-evidence.json'
    write_json(evidence_file, evidence)
    return dict(source=source, report=str(report_file), preview=report['preview'], evidence=str(evidence_file),
                adoption_request=str(adoption_file), strength=best['strength'], changed_positions=len(changed))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, required=True, help='尚不存在的合成创作工作区')
    parser.add_argument('--adopt', action='store_true', help='显式采用并保存合成示例的制作版')
    args = parser.parse_args()
    print(json.dumps(run(args.workspace, adopt=args.adopt), ensure_ascii=False, indent=2))
