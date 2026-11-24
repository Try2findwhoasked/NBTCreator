"""Regression for fixture replay, external candidates and frozen task checks."""

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import runpy
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
BENCHMARK = runpy.run_path(str(ROOT / 'tests/support/building-generation-benchmark.py'))


class BuildingGenerationBenchmark(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        directory = tempfile.TemporaryDirectory()
        cls.addClassCleanup(directory.cleanup)
        cls.output = Path(directory.name).resolve()
        BENCHMARK['run'](cls.output)
        cls.workspace = cls.output / 'workspace'
        cls.report = BENCHMARK['read'](cls.output / 'report.json')
        cls.case = 'blocked-stair'
        cls.blocked = cls.report['cases'][cls.case]

    def test_four_fixtures_use_equal_budget_and_real_geometry(self):
        expected = dict(first_pass_count=2, final_pass_count=4, repair_rounds=2, candidates_evaluated=6)
        self.assertEqual(self.report['counts'], dict(technical=expected, building=expected))
        self.assertEqual(self.report['case_count'], 4)
        self.assertIsNone(self.report['public_review_archive'])
        changes = {'open-activity': None, 'blocked-stair': 18, 'wrong-side': 0, 'cabinet-trim': 3}
        for case, row in self.report['cases'].items():
            self.assertEqual(row['visual'], dict(status='render_not_requested', scores=None))
            self.assertEqual(row['budget']['candidate_attempts_per_case'], 2)
            for arm, result in row['arms'].items():
                with self.subTest(case=case, arm=arm):
                    path = self.output / result['input']['path']
                    self.assertEqual(sha256(path.read_bytes()).hexdigest(), result['input']['sha256'])
                    packet = BENCHMARK['read'](path)
                    self.assertEqual(packet['budget'], row['budget'])
                    self.assertEqual(result['operator']['kind'], 'fixture')
                    final = result['attempts'][-1]
                    self.assertTrue(final['passed'])
                    self.assertTrue(all(final['preservation'].values()))
                    self.assertEqual(final['hits']['activity_segments'], [True] * 3)
                    self.assertEqual(final['changed_positions'], changes[case])
                    self.assertFalse(Path(final['source']['source']).is_absolute())
                    if case == 'cabinet-trim':
                        self.assertTrue(final['hits']['local_edit'])
                        self.assertFalse(Path(packet['starting_source']['source']).is_absolute())
                        self.assertEqual(final['parent_source_sha256'], packet['starting_source']['source_sha256'])
        self.assertFalse(self.report['approval_created'])
        self.assertFalse((self.workspace / 'nbt_models/_exports').exists())

    def test_failures_cannot_be_hidden_by_walkable_segments_or_changed_contract(self):
        wrong = self.report['cases']['wrong-side']['arms']['technical']['attempts'][0]
        self.assertEqual(wrong['hits']['activity_segments'], [True] * 3)
        self.assertEqual(wrong['hits']['use_faces']['return_desk.intake']['reason'], 'wrong_side')
        self.assertEqual(self.blocked['arms']['building']['attempts'][0]['error'], 'ROUTE_FAILED')
        packet = BENCHMARK['read'](self.output / self.blocked['arms']['technical']['input']['path'])
        candidate = deepcopy(packet['starting_plan'])
        candidate['context']['require_routes'] = False
        self.assertFalse(BENCHMARK['fixed_conditions'](candidate, packet['starting_plan'], self.case)['context'])

    def test_local_scope_counts_wall_layer_changes(self):
        task = self.report['cases']['cabinet-trim']['task']
        cells = {tuple(pos) for pos in task['edit']['positions']}
        outside = (0, 0, 0)
        before = dict(blocks={p: task['edit']['previous_state'] for p in cells} | {outside: 'minecraft:stone'},
                      walls={outside})
        after = dict(blocks={p: task['edit']['state'] for p in cells} | {outside: 'minecraft:stone'}, walls=set())
        hits, preservation = BENCHMARK['local_conditions'](task, before, after)
        self.assertTrue(hits['local_edit'])
        self.assertFalse(preservation['untouched_outside_edit'])
        self.assertFalse(preservation['wall_membership_unchanged'])

    def test_external_layout_is_rebuilt_and_manifest_enforces_budget_and_input(self):
        run = self.blocked['arms']['building']
        input_ref = run['input']
        packet = BENCHMARK['read'](self.output / input_ref['path'])
        plan = BENCHMARK['scripted_plan'](self.case, packet, 2)
        cabinet = next(part for part in plan['parts'] if part['id'] == 'archive_cabinet')
        cabinet['position'][0] += 1
        manifest = self.output / 'external.json'
        submission = BENCHMARK['write'](self.output / 'layout.json', dict(plan=plan, offsets={'cabinet': [1, 5]}))
        choices = dict(input_sha256=input_ref['sha256'], candidates=[submission['path']])
        group = dict(operator=dict(kind='layout', id='local-layout-regression'), cases={self.case: choices})
        data = dict(schema_version=1, arms=dict(technical=None, building=group))
        _, before, _, _ = BENCHMARK['build'](self.workspace, dict(plan=packet['starting_plan']))
        row = dict(packets={'building': packet}, budget=packet['budget'], before=before,
                   inputs={'building': input_ref})
        cases = {self.case: row}
        save = BENCHMARK['write']
        parse = BENCHMARK['external_candidates']
        save(manifest, data)
        external = parse(manifest, cases)['building']
        result = BENCHMARK['run_arm'](self.workspace, self.case, 'building', packet['starting_plan'], row, external)
        self.assertTrue(result['first_pass'], result)
        self.assertEqual(result['attempts'][0]['submission'], submission)
        self.assertNotEqual(result['attempts'][0]['source']['model_sha256'], run['attempts'][-1]['source']['model_sha256'])
        choices['candidates'] *= 3
        save(manifest, data)
        with self.assertRaisesRegex(ValueError, '超预算'):
            parse(manifest, cases)
        choices.update(input_sha256='0' * 64, candidates=[])
        save(manifest, data)
        with self.assertRaisesRegex(ValueError, '其他输入'):
            parse(manifest, cases)


if __name__ == '__main__':
    unittest.main(verbosity=2)
