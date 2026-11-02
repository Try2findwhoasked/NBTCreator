"""Regression probes for static route checks. Run with --output <report.json>."""
import json
from pathlib import Path
import sys
import time

import argparse
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output',type=Path,default=Path.cwd()/'nbt_models/_tests/toolkit_validation/collision_regression.json')
args=parser.parse_args()
from nbt_model import Model
from nbt_collision import check_routes, collision_cells, _Space


def corridor():
    model = Model((10, 8, 3))
    model.box((0, 0, 0), (9, 0, 2), 'stone_bricks')
    model.box((0, 1, 0), (9, 7, 0), 'stone_bricks')
    model.box((0, 1, 2), (9, 7, 2), 'stone_bricks')
    return model


def stair_route():
    model = corridor()
    model.put((3, 1, 1), 'stone_slab[type=bottom]')
    model.put((4, 1, 1), 'stone_brick_stairs[half=bottom,facing=east,shape=straight]')
    model.put((5, 1, 1), 'stone_slab[type=top]')
    model.put((6, 2, 1), 'stone_slab[type=bottom]')
    model.put((7, 2, 1), 'stone_brick_stairs[half=bottom,facing=east,shape=straight]')
    model.put((8, 2, 1), 'stone_bricks')
    return model


reports = {}
model = stair_route()
reports['slabs_stairs_ascending'] = check_routes(model, (1.5, 1, 1.5), {'upper': (8.5, 3, 1.5)})
assert reports['slabs_stairs_ascending']['passed']
reports['slabs_stairs_descending'] = check_routes(model, (8.5, 3, 1.5), [(1.5, 1, 1.5)])
assert reports['slabs_stairs_descending']['passed']
reports['exact_off_grid_feet'] = check_routes(model, (1.37, 1, 1.4), [(8.41, 3, 1.6)])
assert reports['exact_off_grid_feet']['passed']

# The valid staircase is now obstructed between floors, while endpoints stay valid.
blocked = stair_route()
blocked.put((5, 3, 1), 'stone_bricks')
reports['multi_level_head_obstruction'] = check_routes(blocked, (1.5, 1, 1.5), [(8.5, 3, 1.5)])
assert not reports['multi_level_head_obstruction']['passed']
assert reports['multi_level_head_obstruction']['targets'][0]['standing']

# A full-block riser is not silently treated as auto-step or jump.
riser = corridor()
riser.box((4, 1, 1), (9, 1, 1), 'stone_bricks')
reports['full_block_requires_jump'] = check_routes(riser, (1.5, 1, 1.5), [(8.5, 2, 1.5)])
assert not reports['full_block_requires_jump']['passed']
assert reports['full_block_requires_jump']['targets'][0]['standing']

unknown = corridor()
unknown.put((4, 0, 1), 'oak_fence')
reports['unknown_shape_cannot_certify'] = check_routes(unknown, (1.5, 1, 1.5), [(8.5, 1, 1.5)])
assert not reports['unknown_shape_cannot_certify']['passed']
assert reports['unknown_shape_cannot_certify']['unknown_shapes']

# A 1.8 player fits below Y=3 from feet Y=1, but not below Y=2.5.
ceiling = corridor()
ceiling.box((0, 3, 1), (9, 3, 1), 'stone_bricks')
reports['two_blocks_headroom'] = check_routes(ceiling, (1.5, 1, 1.5), [(8.5, 1, 1.5)])
assert reports['two_blocks_headroom']['passed']
ceiling.put((5, 2, 1), 'stone_slab[type=top]')
reports['one_and_half_blocks_headroom'] = check_routes(ceiling, (1.5, 1, 1.5), [(8.5, 1, 1.5)])
assert not reports['one_and_half_blocks_headroom']['passed']

# Known stair quadrants, including vertical reflection and inner/outer corner rules.
expected_east = {
    'straight': {(1, 0), (1, 1)},
    'inner_left': {(1, 0), (1, 1), (0, 0)},
    'inner_right': {(1, 0), (1, 1), (0, 1)},
    'outer_left': {(1, 0)},
    'outer_right': {(1, 1)},
}
shape_cases = 0
for facing in ('east', 'south', 'west', 'north'):
    turns = ('east', 'south', 'west', 'north').index(facing)
    for half in ('bottom', 'top'):
        for shape, expected in expected_east.items():
            expected = set(expected)
            for _ in range(turns):
                expected = {(1-z, x) for x, z in expected}
            cells, reason = collision_cells(f'minecraft:stone_brick_stairs[facing={facing},half={half},shape={shape}]')
            base_y = 0 if half == 'bottom' else 1
            assert reason is None
            assert {(x, z) for x, y, z in cells if y == 1-base_y} == expected
            assert len([p for p in cells if p[1] == base_y]) == 4
            shape_cases += 1

# Inverted outer corner: the lower quarter blocks the player's head only on its
# occupied side. This exercises real AABB clearance, rather than cell counts.
overhang = Model((5, 5, 5))
overhang.box((0, 0, 0), (4, 0, 4), 'stone_slab[type=bottom]')
overhang.put((2, 2, 2), 'stone_brick_stairs[facing=east,half=top,shape=outer_left]')
overhang_space = _Space(overhang)
assert overhang_space.standing((2.15, .5, 2.85))
assert not overhang_space.standing((2.85, .5, 2.15))
reports['inverted_outer_corner_clearance'] = check_routes(overhang, (1, .5, 2.85), [(2.15, .5, 2.85)])
assert reports['inverted_outer_corner_clearance']['passed']
assert collision_cells('minecraft:mud')[1] == 'unsupported_collision_shape'

# Half-block gaps must not become walking bridges when the 0.6 player loses support.
gap = corridor()
gap.put((4, 0, 1), 'air')
reports['unsupported_gap'] = check_routes(gap, (1.5, 1, 1.5), [(8.5, 1, 1.5)])
assert not reports['unsupported_gap']['passed']

large = Model((48, 48, 48))
large.box((0, 0, 0), (47, 0, 47), 'stone_bricks')
started = time.perf_counter()
reports['48_cube_floor'] = check_routes(large, (.5, 1, .5), [(47.5, 1, 47.5)])
elapsed = time.perf_counter()-started
assert reports['48_cube_floor']['passed']

out=args.output.resolve()
out.parent.mkdir(parents=True,exist_ok=True)
out.write_text(json.dumps(dict(shape_cases=shape_cases, benchmark_seconds=elapsed,
                              reports=reports), indent=2)+'\n', encoding='utf8')
print(json.dumps(dict(fixture_count=len(reports), shape_cases=shape_cases,
                     benchmark_seconds=elapsed,
                     outcomes={name: report['passed'] for name, report in reports.items()},
                     output=str(out)), indent=2))
