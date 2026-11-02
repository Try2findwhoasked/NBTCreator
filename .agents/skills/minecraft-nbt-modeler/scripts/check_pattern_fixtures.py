"""Synthetic weighted-pattern invariants; does not modify or approve user assets."""
import argparse
import copy
import json
from pathlib import Path
import subprocess
import sys

from nbt_assembly import Volume, LogicalAssembly
from nbt_model import Model, state
from nbt_registry import effective
from nbt_patterns import pattern_plan, apply_pattern, _sampler
from nbt_refine import operation_candidates, save_master


def rejected(action):
    try:
        action()
    except (ValueError, FileExistsError, PermissionError, AssertionError):
        return True
    return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    out = parser.parse_args().output.resolve()
    out.mkdir(parents=True)
    checks = {}
    model = Volume((96, 8, 48))
    model.box((0, 0, 0), (95, 7, 47), 'stone_bricks')
    operation = dict(kind='pattern', label='Synthetic weighted masonry', lo=[0, 0, 0], hi=[95, 7, 47],
                     seed=2147, from_states=['stone_bricks'], palette=[
                         dict(state='stone_bricks', weight=70), dict(state='cracked_stone_bricks', weight=20),
                         dict(state='mossy_stone_bricks', weight=10)])
    source = model.fingerprint()
    edits, report = pattern_plan(model, operation)
    checks['plan_is_read_only_and_repeatable'] = model.fingerprint() == source and edits == pattern_plan(model, operation)[0]
    checks['weighted_expected_proportions'] = all(abs(report['sampled_states'][state(name)] / report['sampled'] - p) < .015
        for name, p in [('stone_bricks', .7), ('cracked_stone_bricks', .2), ('mossy_stone_bricks', .1)])
    reordered = Volume(model.size)
    reordered.blocks = dict(reversed(list(model.blocks.items())))
    checks['independent_of_source_dictionary_order'] = pattern_plan(reordered, operation)[0] == edits
    combined = []
    for low, high in ((0, 47), (48, 95)):
        part = dict(operation, lo=[low, 0, 0], hi=[high, 7, 47])
        combined.extend(pattern_plan(model, part)[0])
    checks['same_global_coordinates_across_storage_boundary'] = combined == edits
    protected = {(47, y, z) for y in range(8) for z in range(48)}
    safe, safe_report = pattern_plan(model, operation, protected)
    checks['protection_preserved_and_reported'] = not (set(p for p, _ in safe) & protected) and safe_report['protected_skipped'] == len(protected)
    half = dict(operation, fraction=.5)
    _, half_report = pattern_plan(model, half)
    checks['coverage_is_separate_from_material_weights'] = abs(half_report['sampled'] / half_report['eligible'] - .5) < .02 and abs(half_report['sampled_states'][state('stone_bricks')] / half_report['sampled'] - .7) < .02
    zero = dict(operation, fraction=0)
    checks['zero_fraction_is_noop'] = pattern_plan(model, zero)[0] == []
    zeros = dict(operation, palette=[dict(state='stone_bricks', weight=0), dict(state='granite', weight=1)])
    checks['zero_weight_never_selected'] = set(v for _, v in pattern_plan(model, zeros)[0]) == {state('granite')}
    scale_a = dict(operation, palette=[dict(state='granite', weight=7), dict(state='andesite', weight=3)])
    scale_b = dict(scale_a, palette=[dict(state='granite', weight=70), dict(state='andesite', weight=30)])
    checks['weights_are_relative'] = pattern_plan(model, scale_a)[0] == pattern_plan(model, scale_b)[0]
    cluster = dict(scale_a, mode='clustered', scale=5)
    cluster_edits, cluster_report = pattern_plan(model, cluster)
    cluster_map, independent_map = dict(cluster_edits), dict(pattern_plan(model, scale_a)[0])
    neighbors = [((x, 3, z), (x + 1, 3, z)) for x in range(95) for z in range(48)]
    agreement = lambda values: sum(values[a] == values[b] for a, b in neighbors) / len(neighbors)
    checks['clustered_has_spatial_coherence'] = agreement(cluster_map) > agreement(independent_map) + .15
    checks['clustered_repeatable'] = pattern_plan(model, cluster)[0] == cluster_edits
    draws = [_sampler(seed, 'clustered', [6, 6, 6])('material', (3, 2, 4)) for seed in range(2048)]
    checks['noise_does_not_bias_weight_thresholds'] = abs(sum(v < .7 for v in draws) / len(draws) - .7) < .04
    regional = []
    for low, high in ((0, 47), (48, 95)):
        regional.extend(pattern_plan(model, dict(cluster, lo=[low, 0, 0], hi=[high, 7, 47]))[0])
    checks['clustered_continuous_across_cut'] = regional == cluster_edits
    small = Model((8, 8, 8))
    fill = dict(kind='pattern', action='fill', lo=[0, 0, 0], hi=[7, 0, 7], seed=31, palette=['stone_bricks', 'granite'])
    walls, fill_report = apply_pattern(small, fill)
    checks['draft_fill_supported'] = len(small.blocks) == 64 and fill_report['changed'] == 64 and small.stage == 'design'
    cube = Model((3, 3, 3))
    cube.box((0, 0, 0), (2, 2, 2), 'stone')
    surface = dict(kind='pattern', lo=[0, 0, 0], hi=[2, 2, 2], scope='surface', palette=['granite'])
    changed, _ = pattern_plan(cube, surface)
    checks['surface_excludes_buried_blocks'] = len(changed) == 26 and (1, 1, 1) not in dict(changed)
    mask = dict(surface, mask_positions=[[0, 0, 0], [2, 2, 2]])
    checks['explicit_coordinate_mask'] = set(p for p, _ in pattern_plan(cube, mask)[0]) == {(0, 0, 0), (2, 2, 2)}
    stairs = Model((8, 8, 8))
    stairs.put((1, 1, 1), 'oak_stairs[facing=east,half=top,shape=inner_left]')
    stairs.put((2, 1, 1), 'oak_stairs[facing=west,half=bottom,shape=straight]')
    operation_stairs = dict(kind='pattern', lo=[0, 0, 0], hi=[7, 7, 7], from_states=['oak_stairs[half=top]'], palette=['spruce_stairs'])
    result, _ = pattern_plan(stairs, operation_stairs)
    props = effective(result[0][1])[1]
    checks['selector_matches_subset_and_preserves_states'] = len(result) == 1 and props['facing'] == 'east' and props['half'] == 'top' and props['shape'] == 'inner_left'
    slab = Model((3, 3, 3))
    slab.put((1, 1, 1), 'stone_brick_slab[type=top]')
    result, _ = pattern_plan(slab, dict(surface, scope='volume', palette=['andesite_slab']))
    checks['slab_half_preserved'] = effective(result[0][1])[1]['type'] == 'top'
    override = dict(operation_stairs, shape_policy='any', palette=['spruce_stairs[facing=north]'])
    checks['explicit_target_property_wins'] = effective(pattern_plan(stairs, override)[0][0][1])[1]['facing'] == 'north'
    bad_shape = dict(operation_stairs, palette=['stone'])
    checks['shape_change_refused_by_default'] = rejected(lambda: pattern_plan(stairs, bad_shape))
    walls = {(0, 0, 0)}
    _, inherit_report = apply_pattern(cube, mask, walls)
    new_walls, _ = apply_pattern(cube, dict(mask, palette=['andesite']), walls)
    checks['wall_ownership_inherited_for_recolor'] = new_walls == walls
    new_walls, _ = apply_pattern(cube, dict(mask, palette=['granite'], classification='body'), walls)
    checks['body_override_removes_wall_membership'] = not new_walls
    same_walls, same_report = apply_pattern(cube, dict(mask, palette=['granite'], classification='body'), walls)
    checks['same_material_write_can_change_ownership'] = not same_walls and same_report['changed'] == 0 and same_report['wall_membership_changed'] == 1
    checks['applied_report_does_not_claim_source_unchanged'] = not fill_report['source_unchanged'] and not fill_report['plan_only']
    generator_walls, generator_report = apply_pattern(cube, dict(mask, palette=['andesite']), (p for p in walls))
    checks['wall_mask_generator_is_not_consumed_twice'] = generator_walls == walls and generator_report['wall_membership_changed'] == 0
    sparse = LogicalAssembly([(0, 0), (1, 0), (0, 1)], 8)
    sparse_fill = dict(fill, hi=[95, 0, 95])
    _, sparse_report = apply_pattern(sparse, sparse_fill)
    checks['sparse_footprint_does_not_fill_missing_cell'] = len(sparse.blocks) == 48*48*3 and sparse_report['footprint_skipped'] == 48*48
    translated = Model((48, 8, 48))
    translated.box((0, 0, 0), (47, 7, 47), 'stone_bricks')
    local = dict(cluster, hi=[47, 7, 47], coordinate_origin=[48, 0, 0])
    local_changes = [((p[0] + 48, p[1], p[2]), v) for p, v in pattern_plan(translated, local)[0]]
    checks['coordinate_origin_preserves_sampling_phase'] = local_changes == [(p, v) for p, v in cluster_edits if p[0] >= 48]
    invalid = [dict(surface, seed=True), dict(surface, fraction=float('nan')),
               dict(surface, palette=[dict(state='granite', weight=-1)]), dict(surface, palette=[dict(state='granite', weight=0)]),
               dict(surface, palette=['air']), dict(surface, palette=['not_a_real_slab']), dict(surface, scale=0),
               dict(surface, unexpected=True), dict(surface, lo=[-1, 0, 0]), dict(surface, mask_positions=[[0, 0, 0], [0, 0, 0]])]
    fingerprint = cube.fingerprint()
    checks['invalid_requests_leave_source_unchanged'] = all(rejected(lambda op=op: apply_pattern(cube, op)) for op in invalid) and cube.fingerprint() == fingerprint
    checks['refinement_dispatch_reuses_planner'] = operation_candidates(model, operation) == edits
    # Frozen models cannot be mutated by the draft API.
    sealed = Model((8, 8, 8))
    sealed.box((0, 0, 0), (7, 7, 7), 'stone')
    sealed.box((1, 1, 1), (6, 6, 6), 'air')
    sealed.check_sealed([(3, 3, 3)])
    checks['draft_api_refuses_frozen_model'] = rejected(lambda: apply_pattern(sealed, fill))
    source_file = out/'source.master.json.gz'
    save_master(source_file, sealed, set())
    operation_file = out/'operation.json'
    operation_file.write_text(json.dumps(dict(surface, hi=[7, 7, 7])), encoding='utf8')
    script = Path(__file__).with_name('nbt_patterns.py')
    run = subprocess.run([sys.executable, '-B', str(script), 'plan', '--source', str(source_file), '--operation', str(operation_file), '--output', str(out/'readonly_plan')], capture_output=True, text=True)
    checks['readonly_cli_exports_plan_not_asset'] = run.returncode == 0 and (out/'readonly_plan/pattern_plan.json').is_file() and not list((out/'readonly_plan').glob('*.nbt'))
    missing_review = out/'missing_review'
    missing_review.mkdir()
    run = subprocess.run([sys.executable, '-B', str(script), 'apply', '--review', str(missing_review), '--operation', str(operation_file), '--output', str(out/'unauthorized'), '--style-note', 'Synthetic test only'], capture_output=True, text=True)
    checks['cli_does_not_bypass_review'] = run.returncode != 0 and not (out/'unauthorized').exists()
    assert all(checks.values()), checks
    report = dict(passed=True, checks=checks, weighted=report, clustered=cluster_report,
                  neighbor_agreement=dict(independent=agreement(independent_map), clustered=agreement(cluster_map)))
    (out/'results.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf8')
    print(json.dumps(dict(passed=True, checks=len(checks), report=str(out/'results.json'))))


if __name__ == '__main__':
    main()
