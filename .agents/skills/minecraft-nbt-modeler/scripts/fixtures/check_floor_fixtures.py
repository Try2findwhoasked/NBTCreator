"""Synthetic auto-floor detection, matching, protection and damage probes."""
import argparse
import copy
import json
from pathlib import Path

from nbt_model import Model, AIR_NAMES, state
from nbt_refine import save_master
from nbt_floors import detect_floors, slab_match, auto_floor_plan, apply_floor_damage


def fixture():
    m = Model((32, 20, 32))
    m.box((0, 0, 0), (31, 19, 31), 'stone_bricks')
    m.box((1, 4, 1), (30, 17, 30), 'air')
    m.box((16, 3, 1), (30, 3, 30), 'oak_planks')
    m.box((3, 3, 24), (6, 3, 28), 'blue_concrete')
    m.box((4, 4, 4), (7, 4, 7), 'stone_bricks')  # Unreachable table; not a floor.
    m.box((14, 6, 17), (25, 6, 28), 'oak_planks')
    for k in range(6):
        x = 8+k
        y = 4+k//2
        if y > 4: m.box((x, 4, 20), (x, y-1, 22), 'stone_bricks')
        m.box((x, y, 20), (x, y, 22), 'stone_brick_slab[type=bottom,waterlogged=false]' if k%2 == 0 else 'stone_bricks')
    context = dict(start=[2.5, 4, 12.5], targets={'work': [28.5, 4, 5.5], 'upper': [18.5, 7, 23.5]},
        interior_probes=[[12, 8, 8], [18, 10, 23]],
        ports=[dict(id='west', facing='west', min=[0, 4, 9], max=[0, 8, 14])])
    return m, context


def rejects(fn):
    try: fn()
    except (ValueError, AssertionError, FileExistsError, PermissionError): return True
    return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    out = parser.parse_args().output.resolve(); out.mkdir(parents=True)
    checks = {}
    model, context = fixture()
    original = model.fingerprint()
    floors, detection = detect_floors(model, context)
    checks['multiple_reachable_levels_detected'] = set(detection['levels']) == {3, 6}
    checks['roof_and_unreachable_table_excluded'] = not any(p[1] >= 18 or p[1] == 4 and 4 <= p[0] <= 7 and 4 <= p[2] <= 7 for p in floors)
    checks['detector_does_not_mutate_model_or_phase'] = model.fingerprint() == original and model.stage == 'design'
    checks['wood_stone_and_weathered_matches'] = all(slab_match(source)['state'] == state(target) for source, target in [
        ('oak_planks', 'oak_slab[type=bottom,waterlogged=false]'),
        ('stone_bricks', 'stone_brick_slab[type=bottom,waterlogged=false]'),
        ('cracked_stone_bricks', 'stone_brick_slab[type=bottom,waterlogged=false]'),
        ('mossy_stone_bricks', 'mossy_stone_brick_slab[type=bottom,waterlogged=false]')])
    checks['fallbacks_are_explicit'] = slab_match('cracked_stone_bricks')['match'] == 'family_fallback'
    checks['no_fictitious_dirt_concrete_slabs'] = slab_match('dirt') is None and slab_match('blue_concrete') is None
    checks['explicit_override_verified'] = slab_match('blue_concrete', {'blue_concrete': 'stone_slab'})['match'] == 'explicit_override'
    checks['invalid_override_refused'] = rejects(lambda: slab_match('stone', {'stone': 'oak_slab[type=top]'}))
    operation = dict(kind='auto_floor', profile='ruined', style_note='Synthetic old stone and timber store; small grouped depressions.',
                     seed=73, fraction=.12)
    edits, report = auto_floor_plan(model, operation, context)
    checks['slabs_and_pits_generated'] = report['slab_blocks'] > 0 and report['pit_columns'] > 0
    checks['multi_material_slab_matching_used'] = {v for _, v in edits if '_slab[' in v} == {
        state('oak_slab[type=bottom,waterlogged=false]'), state('stone_brick_slab[type=bottom,waterlogged=false]')}
    checks['unsupported_floor_left_intact'] = report['unmapped_states'].get('minecraft:blue_concrete', 0) > 0 and all(model.get(p) != 'minecraft:blue_concrete' for p, _ in edits)
    checks['plan_is_read_only'] = model.fingerprint() == original
    repeated, _ = auto_floor_plan(model, operation, context)
    checks['fixed_seed_repeats_full_plan'] = repeated == edits
    reordered = Model(model.size); reordered.blocks = dict(reversed(list(model.blocks.items())))
    checks['source_order_does_not_change_damage'] = auto_floor_plan(reordered, operation, context)[0] == edits
    checks['post_seal_and_routes_verified'] = report['post_seal']['passed'] and report['post_routes']['passed'] and report['original_necessary_paths_preserved']
    checks['door_threshold_and_throat_unchanged'] = not any(p[0] <= 4 and 8 <= p[2] <= 15 for p, _ in edits)
    checks['no_budget_overshoot'] = report['actual_blocks'] <= report['target_blocks']
    checks['connected_groups_instead_of_single_scatter'] = all(n >= 2 for groups in report['group_sizes'].values() for n in groups)
    checks['unrelated_ceiling_and_walls_unchanged'] = all(p[1] <= 6 and p[0] not in (0, 31) and p[2] not in (0, 31) for p, _ in edits)
    source_walls = {p for p in model.blocks if p[0] in (0, 31) or p[2] in (0, 31)}
    new_walls, applied = apply_floor_damage(model, operation, context, source_walls)
    checks['draft_apply_matches_plan'] = applied['result_geometry_sha256'] == model.fingerprint() and all(model.get(p) == v for p, v in edits)
    checks['wall_mask_preserved_and_floor_changes_are_body'] = new_walls == source_walls and not (new_walls & {p for p, _ in edits})
    model.check_sealed(context['interior_probes'])
    checks['post_apply_can_pass_normal_seal'] = model.seal_record['passed']
    checks['frozen_source_refuses_draft_api'] = rejects(lambda: apply_floor_damage(model, operation, context, source_walls))
    save_master(out/'floor_fixture.master.json.gz', model, new_walls)
    (out/'context.json').write_text(json.dumps(context, indent=2), encoding='utf8')
    (out/'operation.json').write_text(json.dumps(operation, indent=2), encoding='utf8')
    # New source instances keep evidence and tests independent.
    intact, ctx = fixture()
    none, maintained = auto_floor_plan(intact, dict(operation, profile='maintained', fraction=0), ctx)
    checks['maintained_profile_can_remain_intact'] = none == [] and maintained['actual_blocks'] == 0
    explicit_protected = {(x, y, z) for x in range(32) for y in range(20) for z in range(32)}
    none, guarded = auto_floor_plan(intact, operation, ctx, explicit_protected)
    checks['explicit_protection_never_relaxed'] = none == [] and guarded['eligible_blocks'] == 0
    fingerprint = intact.fingerprint()
    for label, invalid in [('bad_profile', dict(operation, profile='unknown')), ('bad_ratio', dict(operation, fraction=float('nan'))),
                           ('bad_slab', dict(operation, slab_overrides={'stone_bricks': 'stone'})),
                           ('no_reason', dict(operation, style_note='')), ('bad_field', dict(operation, unknown=True))]:
        checks[label+'_refused'] = rejects(lambda invalid=invalid: apply_floor_damage(intact, invalid, ctx))
    checks['invalid_input_leaves_source_unchanged'] = intact.fingerprint() == fingerprint
    checks['incomplete_detection_budget_refuses_result'] = rejects(lambda: detect_floors(intact, ctx, max_poses=10))
    thin, thin_context = fixture()
    thin.box((1, 0, 1), (30, 2, 30), 'air')
    # An enclosed cavity under a one-block deck cannot be opened by the default pit tool.
    _, thin_report = auto_floor_plan(thin, dict(operation, slab_share=0), thin_context)
    checks['thin_deck_not_excavated_into_lower_cavity'] = thin_report['pit_columns'] == 0
    leaking, ctx = fixture(); leaking.put((0, 9, 3), 'air')
    checks['unlisted_boundary_leak_rejected'] = rejects(lambda: detect_floors(leaking, ctx))
    unreachable = copy.deepcopy(context); unreachable['targets']['bad'] = [6.5, 5, 6.5]
    checks['unreachable_required_target_rejected'] = rejects(lambda: detect_floors(intact, unreachable))
    assert all(checks.values()), checks
    (out/'results.json').write_text(json.dumps(dict(passed=True, checks=checks, detection=detection, damage=report), indent=2)+'\n', encoding='utf8')
    print(json.dumps(dict(passed=True, checks=len(checks), report=str(out/'results.json'))))


if __name__ == '__main__': main()
