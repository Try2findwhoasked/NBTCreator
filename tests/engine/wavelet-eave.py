"""Real geometry and binding regressions for a single-bay eave transfer."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('wavelet_eave_example', ROOT / 'scripts/examples/wavelet-eave.py')
example = importlib.util.module_from_spec(spec)
spec.loader.exec_module(example)

from nbt_model import Model
from nbt_refine import read_master
from nbt_registry import effective
from nbt_snbt import write_binary
from nbt_building.wavelet_eave import detail_bands
from nbt_composition.working_model import ModelConflict, WorkingModel, file_hash


class WaveletEaveTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.workspace = Path(temporary.name)

    def fixture(self):
        return example.fixture(self.workspace)[:2]

    def test_undecimated_reflected_bands_reconstruct_and_preserve_alignment(self):
        x = np.arange(96)
        short = np.cos(2 * np.pi * x / 6)
        long = np.cos(2 * np.pi * x / 48)
        before = 5 + short + long
        bands, residual = detail_bands(before, 4)
        np.testing.assert_allclose(bands.sum(axis=0) + residual, before, atol=1e-12)
        np.testing.assert_allclose(detail_bands(before[::-1], 4)[0], bands[:, ::-1], atol=1e-12)
        np.testing.assert_array_equal(detail_bands(np.ones(24), 4)[0], 0)
        interior = slice(16, -16)
        short_detail = detail_bands(short, 2)[0].sum(axis=0)[interior]
        long_detail = detail_bands(long, 2)[0].sum(axis=0)[interior]
        self.assertGreater(np.linalg.norm(short_detail) / np.linalg.norm(short[interior]), 0.85)
        self.assertLess(np.linalg.norm(long_detail) / np.linalg.norm(long[interior]), 0.05)
        self.assertGreater(np.corrcoef(short_detail, short[interior])[0, 1], 0.999)

    def test_public_cli_preview_and_explicit_adoption_of_actual_blocks(self):
        result = example.run(self.workspace / 'hall', adopt=True)
        evidence = json.loads(Path(result['evidence']).read_text(encoding='utf-8'))
        report = json.loads(Path(result['report']).read_text(encoding='utf-8'))
        before, old_walls = read_master(result['source']['source'])
        after, new_walls = read_master(result['preview']['source'])
        best = report['best']
        snapshot = json.loads(Path(result['preview']['receipt']).read_text(encoding='utf-8'))
        self.assertEqual(snapshot['preview_source_sha256'], file_hash(result['preview']['source']))
        self.assertEqual(snapshot['readback_measured'], best['measured'])
        self.assertEqual(snapshot['readback_checks']['projections'], best['projections'])
        self.assertEqual(snapshot['readback_checks']['backing_contacts'], best['checks']['backing_contacts'])
        self.assertEqual(result['changed_positions'], 12)
        self.assertEqual(best['strength'], 0.75)
        self.assertLess(best['error_after'], 0.15 * best['error_before'])
        self.assertEqual(before.blocks.keys(), after.blocks.keys())
        self.assertEqual(old_walls, new_walls)
        self.assertEqual(evidence['outside_bay_changed'], 0)
        self.assertEqual(evidence['protected_changed'], 0)
        self.assertEqual(evidence['ownership_changes'], 0)
        self.assertGreater(evidence['owned_positions'], 0)
        self.assertTrue(evidence['ridge']['unchanged'])
        self.assertEqual(evidence['bounds_half_before'], evidence['bounds_half_after'])
        self.assertTrue(all(p['before_sha256'] == p['after_sha256'] for p in evidence['projections'].values()))
        self.assertEqual((evidence['added_half_cells'], evidence['removed_half_cells']), (12, 12))
        self.assertEqual(best['checks']['routes'], 'required_passed')
        self.assertEqual([s['depth_step_half'] for s in best['checks']['seams']], [0, 0, 0, 0])
        self.assertTrue(all(s['required_half_faces'] == s['shared_half_faces']
                            for s in best['checks']['backing_contacts']))
        self.assertFalse(evidence['saved']['nbt_exported'])
        self.assertFalse(report['approval_created'])
        binary_fixture = self.workspace / 'roundtrip' / 'candidate.nbt'
        write_binary(binary_fixture, after, new_walls)
        binary, binary_walls = read_master(binary_fixture)
        self.assertEqual(binary.blocks, after.blocks)
        self.assertEqual(binary_walls, new_walls)

    def test_protection_budget_and_ownership_reject_without_writes(self):
        host, goal = self.fixture()
        goal['strengths'] = [0.75]
        host.context['protected_boxes'].append(dict(lo=[19, 8, 4], hi=[19, 8, 4]))
        before = host.inspect()
        report = host.wavelet_eave(goal, preview=dict(output='rejected'))
        self.assertEqual(report['status'], 'no_legal_candidates')
        self.assertEqual(report['rejection_counts'], {'PROTECTED_SPACE': 1})
        self.assertEqual(report['candidates'][0]['problem']['conflicts'], [dict(pos=[19, 8, 4])])
        self.assertFalse((self.workspace / 'rejected').exists())
        self.assertEqual(before, host.inspect())
        host.context['protected_boxes'].pop()
        host.context['max_changed_blocks'] = 10
        self.assertEqual(host.wavelet_eave(goal)['rejection_counts'], {'CHANGE_BUDGET': 1})
        host.context['max_changed_blocks'] = 32
        owned = dict(tool='structure', arguments=dict(name='既有檐件', size=[1, 1, 1], operations=[
            dict(kind='box', label='既有檐件', lo=[0, 0, 0], hi=[0, 0, 0], state='oak_stairs[facing=south,half=top]')]))
        host.install('reserved_eave', owned, [19, 8, 4], overwrite=True)
        self.assertEqual(host.wavelet_eave(goal)['rejection_counts'], {'MANAGED_EAVE_POSITION': 1})

    def test_can_preview_another_strength_without_changing_host(self):
        host, goal = self.fixture()
        before = host.inspect()
        report = host.wavelet_eave(goal, preview=dict(strength=1.75, output='alternate'))
        chosen = next(row for row in report['candidates'] if row['strength'] == 1.75)
        self.assertNotEqual(chosen['strength'], report['best']['strength'])
        self.assertEqual(report['preview']['candidate_sha256'], chosen['candidate_sha256'])
        self.assertEqual(before, host.inspect())
        report = host.wavelet_eave(goal, preview=dict(strength=0.25, output='rejected'))
        self.assertEqual(report['preview_problem']['code'], 'NO_QUANTIZED_DETAIL')
        self.assertFalse((self.workspace / 'rejected').exists())

    def test_no_candidate_when_a_projected_ray_would_change(self):
        host, goal = self.fixture()
        for x in (*range(3, 14), *range(40, 51)):
            host.model.put((x, 8, 4), example.tile(0, 'south'))
        host._baseline.blocks = dict(host.model.blocks)
        goal['strengths'] = [0.75]
        report = host.wavelet_eave(goal)
        self.assertEqual(report['rejection_counts'], {'EAVE_OUTLINE': 1})
        projections = report['candidates'][0]['projections']
        self.assertEqual(projections['x']['changed_rays'], 1)
        self.assertEqual(projections['y']['changed_rays'], 0)
        self.assertEqual(projections['z']['changed_rays'], 0)

    def test_candidate_cannot_break_seam_or_lose_new_backing_contact(self):
        host, goal = self.fixture()
        host.model.put((15, 8, 4), example.tile(2, 'south'))
        host.model.put((37, 8, 18), example.tile(0, 'north'))
        report = host.wavelet_eave(dict(goal, taper=1, strengths=[1.75]))
        self.assertEqual(report['rejection_counts'], {'EAVE_SEAM': 1})
        failed = report['candidates'][0]['problem']['conflicts']
        self.assertIn(dict(positions=[[15, 8, 4], [16, 8, 4]], shared_half_faces=2, depth_step_half=2), failed)

        host, goal = self.fixture()
        host.model.put((22, 8, 4), example.tile(0, 'south'))
        host.model.put((22, 8, 5), example.tile(0, 'south'))
        report = host.wavelet_eave(dict(goal, strengths=[0.75]))
        self.assertEqual(report['rejection_counts'], {'EAVE_SUPPORT': 1})
        failed = report['candidates'][0]['problem']['conflicts'][0]
        self.assertEqual(failed['pos'], [22, 8, 4])
        self.assertEqual(failed['backing'], [22, 8, 5])
        self.assertEqual((failed['required_half_faces'], failed['shared_half_faces']), (4, 2))

    def test_binary_reference_orientation_and_candidate_binding(self):
        host, goal = self.fixture()
        reference = self.workspace / 'reference.nbt'
        component = Model([24, 1, 1])
        for x in range(24):
            component.put((x, 0, 0), host.model.get((x + 15, 8, 18)))
        write_binary(reference, component, set())
        goal['reference'].update(start=[23, 0, 0], source=reference.name, source_sha256=file_hash(reference))
        for x in range(18, 36):
            host.model.put((x, 8, 4), example.tile(0, 'south'))
        # The old reference remains frozen in a separate real NBT.
        host.model.put((36, 8, 18), example.tile(0, 'north'))
        report = host.wavelet_eave(goal)
        self.assertEqual(report['curves']['reference'][:3], [0.5, 1, 1])
        best = report['best']
        generated_stairs = [p for p in best['edits'] if effective(p['after'][0])[0].endswith('_stairs')]
        self.assertTrue(generated_stairs)
        selection = dict(strength=best['strength'], candidate_sha256=best['candidate_sha256'])
        with self.assertRaisesRegex(ModelConflict, 'STALE_EAVE_CANDIDATE'):
            host.adopt_wavelet_eave(dict(goal, levels=[1]), **selection)
        original = reference.read_bytes()
        reference.write_bytes(original + b'changed')
        with self.assertRaisesRegex(ModelConflict, 'STALE_EAVE_REFERENCE'):
            host.adopt_wavelet_eave(goal, **selection)
        reference.write_bytes(original)
        x, y, z = generated_stairs[0]['pos']
        blocked = (x, y, z - 1)
        host.model.put(blocked, example.tile(1, 'east'))
        self.assertIn('EAVE_STAIR_NEIGHBOR', host.wavelet_eave(dict(goal, strengths=[best['strength']]))['rejection_counts'])
        host.model.put(blocked, 'air')
        host.adopt_wavelet_eave(goal, **selection)
        for row in generated_stairs:
            _, props = effective(host.model.get(tuple(row['pos'])))
            self.assertEqual(props, dict(facing='south', half='top', shape='straight', waterlogged='false'))

    def test_along_z_into_positive_x(self):
        host, goal = self.fixture()
        rotated = WorkingModel(self.workspace, [23, 21, 54])
        mapping = dict(north='west', south='east', east='north', west='south')

        def rotate(p):
            x, y, z = p
            return [z, y, 53 - x]

        for p, value in host.model.blocks.items():
            name, props = effective(value)
            if name.endswith('_stairs'):
                value = example.tile(1, mapping[props['facing']])
            rotated.model.put(rotate(p), value)
        rotated_goal = deepcopy(goal)
        for key in ('target', 'reference'):
            strip = rotated_goal[key]
            strip.update(start=rotate(strip['start']), along=mapping[strip['along']], inward=mapping[strip['inward']])
        a, b = [rotate(goal['ridge'][k]) for k in ('lo', 'hi')]
        rotated_goal['ridge'] = dict(lo=list(map(min, zip(a, b))), hi=list(map(max, zip(a, b))))
        normal, turned = host.wavelet_eave(goal)['best'], rotated.wavelet_eave(rotated_goal)['best']
        self.assertEqual(turned['measured'], normal['measured'])
        self.assertEqual([row['pos'] for row in turned['edits']], [rotate(row['pos']) for row in normal['edits']])


if __name__ == '__main__':
    unittest.main()
