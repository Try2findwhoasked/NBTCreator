"""Registry, connector transaction, provenance and read-only snapshot regressions."""
import argparse
import json
from pathlib import Path
from nbt_model import Model, state, load, check_full_block_routes
from nbt_registry import effective, registry
from nbt_collision import collision_cells
from nbt_connections import resolve_connections
from nbt_provenance import OperationTrace
from nbt_task import write_snapshot
from nbt_refine import save_master


def fails(fn):
    try:
        fn()
    except (ValueError, FileExistsError, AssertionError):
        return True
    return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    out = parser.parse_args().output
    out.mkdir(parents=True, exist_ok=True)
    checks = {}
    bad = ['stone_bricks[banana=yes]', 'not_a_real_slab[type=bottom]', 'oak_log[axis=sideways]',
           'stone[]', 'oak_log[axis=x,axis=y]', 'oak_log[axis=x', 'other:stone',
           {'Name': 'oak_log', 'Properties': {'axis': True}}, 'cherry_planks[waterlogged=false]']
    checks['invalid_states_rejected'] = all(fails(lambda v=v: state(v)) for v in bad)
    checks['invalid_geometry_cannot_certify'] = all(collision_cells(v)[1] is not None for v in bad[:3])
    unsupported = Model((4, 4, 4))
    unsupported.put((1, 0, 1), 'oak_fence')
    checks['simple_routes_do_not_invent_fence_floor'] = fails(lambda: check_full_block_routes(unsupported, (1, 1, 1), [(1, 1, 1)]))
    checks['defaults_are_version_derived'] = effective('oak_stairs')[1]['facing'] == 'north'
    checks['partial_properties_preserved'] = state('oak_log[axis=x]') == 'minecraft:oak_log[axis=x]'
    checks['all_registry_defaults_validate'] = all(
        effective(state(dict(Name=name, Properties=entry['default'])))[1] == entry['default']
        for name, entry in registry()['blocks'].items())
    m = Model((8, 8, 8))
    m.put((2, 2, 2), 'oak_fence')
    m.put((3, 2, 2), 'spruce_fence')
    m.put((2, 2, 3), 'nether_brick_fence')
    before = m.fingerprint()
    result = resolve_connections(m, [(2, 2, 2)])
    checks['wood_connects_wood_not_nether'] = (effective(m.get((2, 2, 2)))[1]['east'] == 'true'
                                            and effective(m.get((2, 2, 2)))[1]['south'] == 'false')
    checks['state_change_keeps_supplied_wall_ownership'] = result['wall_positions'] == [(2, 2, 2)]
    checks['connector_idempotence'] = resolve_connections(m)['changed_blocks'] == 0
    explicit = Model((8, 8, 8))
    explicit.put((2, 2, 2), 'iron_bars[east=false]')
    explicit.put((3, 2, 2), 'glass_pane')
    resolve_connections(explicit)
    checks['explicit_fields_preserved'] = effective(explicit.get((2, 2, 2)))[1]['east'] == 'false'
    ambiguous = Model((8, 8, 8))
    ambiguous.put((2, 2, 2), 'oak_fence')
    ambiguous.put((3, 2, 2), 'oak_fence_gate')
    old = ambiguous.fingerprint()
    checks['unresolved_is_atomic'] = fails(lambda: resolve_connections(ambiguous)) and ambiguous.fingerprint() == old
    # Complete synthetic enclosure: this is not an existing user asset.
    closed = Model((8, 8, 8))
    trace = OperationTrace(closed)
    with trace.operation('enclosure', 'synthetic closed shell'):
        closed.box((0, 0, 0), (7, 7, 7), 'stone')
        closed.box((1, 1, 1), (6, 6, 6), 'air')
    with trace.operation('detail', 'overwrite a shell coordinate'):
        closed.put((0, 2, 2), 'stone_bricks')
    checks['last_writer_and_carved_air_recorded'] = trace.owners[(0, 2, 2)] == 'detail' and trace.owners[(2, 2, 2)] == 'enclosure'
    trace.save(out / 'operations.json')
    trace.close()
    closed.check_sealed([(3, 3, 3)])
    checks['post_seal_connection_update_rejected'] = fails(lambda: resolve_connections(closed))
    closed.save(out / 'source.nbt')
    checks['valid_stateful_io_unchanged'] = load(out / 'source.nbt').blocks == closed.blocks
    original = (out / 'source.nbt').read_bytes()
    snapshot = write_snapshot(out / 'source.nbt', out / 'snapshot.json', out / 'operations.json')
    checks['snapshot_read_only_and_not_approval'] = ((out / 'source.nbt').read_bytes() == original
        and snapshot['verification']['design'] == 'pending_visual_review'
        and snapshot['verification']['seal'] == 'not_checked')
    checks['snapshot_preserves_versions'] = fails(lambda: write_snapshot(out / 'source.nbt', out / 'snapshot.json'))
    stale = json.loads((out / 'operations.json').read_text())
    stale['geometry_sha256'] = 'stale'
    (out / 'stale.json').write_text(json.dumps(stale))
    checks['stale_provenance_rejected'] = fails(lambda: write_snapshot(out / 'source.nbt', out / 'wrong.json', out / 'stale.json'))
    checks['failed_snapshot_not_written'] = not (out / 'wrong.json').exists()
    save_master(out / 'master.json.gz', closed, {(0, 2, 2)})
    snapshot = write_snapshot(out / 'master.json.gz', out / 'master.snapshot.json', out / 'operations.json')
    checks['global_master_and_explicit_mask_supported'] = snapshot['wall_positions'] == [(0, 2, 2)]
    assert all(checks.values()), checks
    report = dict(passed=True, checks=checks, registry_blocks=len(registry()['blocks']))
    (out / 'results.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf8')
    print(json.dumps(dict(passed=True, checks=len(checks))))


if __name__ == '__main__':
    main()
