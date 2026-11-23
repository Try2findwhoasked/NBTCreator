"""Regression for constrained, phase-ambiguous beam-frame candidates."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_beam_rhythm import z_amplitudes
from nbt_refine import read_master
from nbt_working_model import ModelConflict, WorkingModel, model_hash

EXAMPLE = ROOT / 'scripts/examples/beam-rhythm.py'


class BeamRhythm(unittest.TestCase):
    def setUp(self):
        workspace = tempfile.TemporaryDirectory()
        self.addCleanup(workspace.cleanup)
        self.root = Path(workspace.name)
        self.goal = dict(id='hall_frames', region=dict(lo=[4, 2, 0], hi=[17, 10, 71]),
                         origin_xy=[5, 2], span_x=13, post_height=7, beam_height=2,
                         count=9, target_pitch=6, pitches=[5, 6, 7], starts=list(range(9, 15)),
                         materials=dict(post='stripped_spruce_log', beam='dark_oak_log'), anchor_z=10)

    def host(self, context=None, **options):
        host = WorkingModel(self.root, [24, 12, 72], context, **options)
        host.apply_operations([dict(kind='box', label='地面', lo=[0, 1, 0], hi=[23, 1, 71], state='stone')])
        return host

    def test_fft_keeps_xy_traces_and_drops_z_phase(self):
        grid = np.zeros((2, 3, 72), dtype=bool)
        grid[0, 2, 9:58:6] = True
        grid[1, 2, 9:58:6] = True
        grid[1, 1, 5:58:5] = True
        amplitude = z_amplitudes(grid, 72)
        self.assertEqual(amplitude.shape, (2, 3, 37))
        np.testing.assert_allclose(amplitude, z_amplitudes(np.roll(grid, 1, axis=-1), 72), atol=1e-12)
        self.assertFalse(np.allclose(amplitude[0, 2], amplitude[1, 1]))

    def test_protected_phase_loses_and_preview_requires_explicit_adoption(self):
        host = self.host(dict(mode='standalone', protected_boxes=[dict(lo=[4, 2, 9], hi=[7, 8, 9])]))
        before = host.inspect()
        report = host.beam_rhythm(goal=self.goal, preview=dict(output='preview'))
        self.assertEqual(host.inspect(), before)
        self.assertEqual((report['evaluated'], report['eligible'], report['rejected']), (18, 15, 3))
        self.assertEqual(report['rejection_counts'], {'PROTECTED_SPACE': 3})
        rejected = next(row for row in report['candidates'] if (row['pitch'], row['start_z']) == (6, 9))
        self.assertEqual(rejected['problem']['total'], 7)
        self.assertIsNone(rejected.get('score'))
        best = report['best']
        self.assertEqual((best['pitch'], best['start_z']), (6, 10))
        self.assertEqual(best['measured']['starts_z'], list(range(10, 59, 6)))
        self.assertEqual(best['measured']['gaps'], [6] * 8)
        self.assertEqual(best['measured']['material_mismatches'], 0)
        self.assertAlmostEqual(best['errors']['spectrum'], 0)
        alternate_pitch = next(row for row in report['candidates'] if (row['pitch'], row['start_z']) == (5, 10))
        self.assertEqual(alternate_pitch['measured']['gap_delta'], [-1] * 8)
        self.assertGreater(alternate_pitch['errors']['spectrum'], best['errors']['spectrum'])
        preview_model, walls = read_master(report['preview']['source'])
        self.assertFalse(report['approval_created'])
        self.assertEqual(model_hash(preview_model, walls), best['model_sha256'])
        self.assertEqual(preview_model.get((5, 2, 10)), 'minecraft:stripped_spruce_log[axis=y]')
        self.assertEqual(preview_model.get((6, 9, 10)), 'minecraft:dark_oak_log[axis=x]')
        chosen = dict(pitch=6, start_z=10, candidate_sha256=best['candidate_sha256'])
        with self.assertRaisesRegex(ModelConflict, 'STALE_BEAM_RHYTHM_CANDIDATE'):
            host.adopt_beam_rhythm(goal=self.goal, **dict(chosen, start_z=11))
        self.assertEqual(host.inspect(), before)
        adopted = host.adopt_beam_rhythm(goal=self.goal, **chosen)
        self.assertEqual(adopted['model_sha256'], best['model_sha256'])
        self.assertEqual(len(host.instances), 9)
        self.assertTrue(host.validate()['assembly']['passed'])
        self.assertFalse((self.root / 'nbt_models').exists())

    def test_no_legal_candidates_returns_actionable_coordinates(self):
        host = self.host(dict(mode='standalone', reserved_boxes=[dict(lo=[5, 2, 9], hi=[5, 2, 10])]))
        report = host.beam_rhythm(goal=dict(self.goal, starts=[9, 10], pitches=[6]), preview=dict(output='unused'))
        self.assertEqual(report['status'], 'no_legal_candidates')
        self.assertIsNone(report['best'])
        self.assertEqual(report['rejection_counts'], {'RESERVED_SPACE': 2})
        self.assertEqual([row['problem']['conflicts'][0]['pos'] for row in report['candidates']],
                         [[5, 2, 9], [5, 2, 10]])
        self.assertFalse((self.root / 'unused').exists())

    def test_edit_boundary_and_nonwinning_preview(self):
        host = self.host()
        goal = dict(self.goal, count=2, pitches=[6], starts=[9, 10, 70])
        report = host.beam_rhythm(goal=goal, preview=dict(pitch=6, start_z=9, output='alternate'))
        self.assertEqual(report['best']['start_z'], 10)
        self.assertEqual(report['rejection_counts'], {'OUTSIDE_EDIT_REGION': 1})
        alternate = next(row for row in report['candidates'] if row['start_z'] == 9)
        self.assertEqual(report['preview']['candidate_sha256'], alternate['candidate_sha256'])
        receipt = json.loads(Path(report['preview']['receipt']).read_text(encoding='utf-8'))
        self.assertEqual(receipt['candidate']['frames'][0]['origin'], [5, 2, 9])
        self.assertEqual(receipt['candidate']['candidate_sha256'], alternate['candidate_sha256'])

    def test_support_routes_and_budget_are_checked_on_the_whole_candidate(self):
        goal = dict(self.goal, count=2, pitches=[6], starts=[9])
        empty = WorkingModel(self.root, [24, 12, 72])
        self.assertEqual(empty.beam_rhythm(goal=goal)['rejection_counts'], {'UNSUPPORTED_FRAME': 1})
        narrow = WorkingModel(self.root, [24, 12, 72])
        narrow.apply_operations([dict(kind='box', label='左基底', lo=[5, 1, 0], hi=[5, 1, 71], state='stone'),
                                 dict(kind='box', label='右基底', lo=[17, 1, 0], hi=[17, 1, 71], state='stone')])
        narrow.context.update(require_routes=True, start=[5.5, 2, 7.5], targets=[[5.5, 2, 12.5]])
        self.assertTrue(narrow._routes(narrow.model)['passed'])
        self.assertEqual(narrow.beam_rhythm(goal=goal)['rejection_counts'], {'ROUTE_FAILED': 1})
        host = self.host()
        host.context['max_changed_blocks'] = 1728 + 40
        self.assertEqual(host.beam_rhythm(goal=goal)['rejection_counts'], {'CHANGE_BUDGET': 1})

    def test_ties_use_anchor_then_changed_positions_and_source_is_bound(self):
        host = self.host()
        goal = dict(self.goal, count=2, pitches=[6], starts=[9, 10])
        best = host.beam_rhythm(goal=goal)['best']
        self.assertEqual(best['start_z'], 10)
        host.apply_operations([dict(kind='box', label='既有同材柱脚', lo=[5, 2, 9], hi=[5, 2, 9],
                                    state='stripped_spruce_log[axis=y]')])
        tied = deepcopy(goal)
        tied.pop('anchor_z')
        report = host.beam_rhythm(goal=tied)
        self.assertEqual(report['best']['start_z'], 9)
        self.assertEqual(report['candidates'][0]['score'], report['candidates'][1]['score'])
        with self.assertRaisesRegex(ModelConflict, 'STALE_BEAM_RHYTHM_CANDIDATE'):
            host.adopt_beam_rhythm(goal=goal, pitch=6, start_z=10, candidate_sha256=best['candidate_sha256'])

    def test_public_cli_example(self):
        spec = importlib.util.spec_from_file_location('beam_rhythm_example', EXAMPLE)
        example = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(example)
        summary = example.run(self.root / 'example', adopt=True)
        self.assertEqual(summary['selection'], dict(pitch=6, start_z=10))
        self.assertTrue(Path(summary['saved_source']).is_file(), json.dumps(summary))


if __name__ == '__main__':
    unittest.main()
