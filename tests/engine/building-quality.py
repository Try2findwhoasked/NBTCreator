"""Regress the shared building rubric using authored reading-loft geometry."""
from copy import deepcopy
from pathlib import Path
import json
import os
import runpy
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / '.agents/skills/minecraft-nbt-modeler'
sys.path[:0] = [str(SKILL / 'scripts'), str(SKILL / 'assets/examples/reading-loft')]

from plan import box, part, reading_loft
from nbt_building.plan import check_model, fingerprint
from nbt_building.quality import assess, route_state
from nbt_building.quality_review import comparisons
from nbt_building.review import load_model
from nbt_building.workflow import dispatch
from nbt_model import AIR_NAMES


class BuildingQuality(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.workspace = Path(cls.temp.name)
        cls.plan = reading_loft()
        result = dispatch(cls.workspace, 'plan-build', dict(plan=cls.plan, save_draft={}))
        cls.binding = {key: result['saved'][key] for key in ('source', 'source_sha256')}
        cls.report = result['quality']

    def cli(self, action, request, compact=None):
        path = self.workspace / 'request.json'
        path.write_text(json.dumps(request, ensure_ascii=False), encoding='utf8')
        run = subprocess.run([sys.executable, '-B', str(SKILL / 'scripts/nbt_architect.py'),
                              '--workspace', str(self.workspace), action, '--request', str(path),
                              *(['--compact-report', str(compact)] if compact else [])],
                             capture_output=True, text=True, encoding='utf8',
                             env=dict(os.environ, PYTHONIOENCODING='utf-8'))
        return run.returncode, json.loads(run.stdout)

    def test_normal_readback_and_missing_visuals(self):
        report = dispatch(self.workspace, 'plan-check', self.binding)['quality']
        self.assertEqual(report, self.report)
        self.assertEqual(report['summary']['gate'], 'pass')
        self.assertEqual(report['activities']['file_books']['status'], 'pass')
        self.assertEqual(report['dimensions']['aesthetics']['status'], 'pending')
        self.assertEqual(report['dimensions']['aesthetics']['coverage'], 0)
        circulation = report['dimensions']['circulation']
        self.assertEqual(circulation['coverage'], 25)
        clearances = [row for row in circulation['items'] if row['id'].endswith('.clearance')]
        self.assertEqual(len(clearances), 3)
        for index, row in enumerate(clearances):
            comfort = row['evidence'][0]
            self.assertEqual((comfort['width'], comfort['height']), (1.2, 1.8))
            self.assertEqual([segment['segment'] for segment in comfort['segments']], [index])
            self.assertEqual(row['weight_denominator'], 12)
        self.assertEqual(circulation['interval'][1] - circulation['interval'][0], 75)
        self.assertFalse(report['approval_created'])

    def test_unverified_leg_keeps_usable_segment_evidence_and_activity_gate(self):
        model = load_model(self.workspace, self.binding)
        validation = model.validate()
        activity = next(row for row in validation['architecture']['checks'] if row['kind'] == 'activity_routes')
        activity['segments'][1]['report'].update(passed=False, search_limit_reached=True)
        review = dict(binding={}, items={
            'circulation.file_books.desk_to_stair.wayfinding': dict(grade=4),
            'circulation.file_books.stair_to_landing.wayfinding': dict(grade=4),
        })
        report = assess(model.architecture['plan'], model.architecture['sha256'], model.model.fingerprint(),
                        validation=validation, review=review, volume=model.model)
        scores = report['dimensions']['circulation']
        self.assertEqual(scores['status'], 'pending')
        self.assertIsNone(scores['score'])
        self.assertIsNone(scores['interval'])
        self.assertEqual(scores['coverage'], 25)
        by_id = {row['id']: row for row in scores['items']}
        self.assertEqual(by_id['circulation.file_books.desk_to_stair.wayfinding']['grade'], 4)
        self.assertIsNone(by_id['circulation.file_books.stair_to_landing.wayfinding']['grade'])
        self.assertEqual(by_id['circulation.file_books.landing_to_shelf.clearance']['status'], 'measured')
        self.assertIn('activity.file_books.segment.stair_to_landing', {row['id'] for row in report['issues']})

    def test_failed_candidates_keep_existing_exit_code_and_localize_blockage(self):
        for spec, code in ((dict(blocked=True), 'ROUTE_FAILED'), (dict(wrong_side=True), 'DESIGN_INVALID')):
            with self.subTest(spec=spec):
                path = self.workspace / 'nbt_models' / (code + '.json')
                status, compact = self.cli('plan-build', dict(plan=reading_loft(**spec)), path)
                raw = json.loads(path.read_text(encoding='utf8'))
                self.assertEqual(status, 1)
                self.assertEqual(compact['code'], code)
                self.assertEqual(compact['quality_summary']['gate'], 'blocked')
                report = raw['quality']
                self.assertIsNone(report['binding']['source_sha256'])
                self.assertTrue(report['binding']['geometry_sha256'])
                self.assertIsNone(report['dimensions']['circulation']['score'])
                if spec.get('blocked'):
                    self.assertTrue(any(row['target']['position'] == [5.5, 5, 19.5]
                                        for row in report['issues']))
                    comparison = dispatch(self.workspace, 'quality-compare', dict(self.binding,
                        previous=dict(report=str(path), report_sha256=compact['report']['sha256'])))
                    self.assertTrue(any(row['status'] == 'resolved_retested' and
                                        row['previous']['target']['position'] == [5.5, 5, 19.5]
                                        for row in comparison['issues'] if row['previous']))
                else:
                    issue = next(row for row in report['issues'] if row['reason'] == 'wrong_side')
                    self.assertEqual(issue['target']['position'], [13.5, 2, 11.5])
                    self.assertEqual(issue['target']['interface'], 'intake')
                    self.assertIn('completion.return_books', issue['related_items'])
                    activity = next(row for row in report['evidence']['checks'] if row['kind'] == 'activity_routes')
                    self.assertTrue(all(row['passed'] for row in activity['segments']))

    def test_absent_and_partial_facility(self):
        for parts, grade in ((['return_desk', 'archive_cabinet'], 0), (['archive_cabinet'], 2)):
            model = load_model(self.workspace, self.binding)
            binding = model.architecture
            for part in parts:
                for row in model.instances[binding['parts'][part]]['baseline']:
                    if row['owned'] and row['after'][0] not in AIR_NAMES:
                        model.model.blocks.pop(tuple(row['pos']), None)
            validation = dict(architecture=check_model(model, binding))
            report = assess(binding['plan'], binding['sha256'], model.model.fingerprint(),
                            validation=validation, volume=model.model)
            measured = report['dimensions']['completion']['items'][0]
            self.assertEqual(measured['grade'], grade, measured)
            self.assertEqual({row['part'] for row in measured['evidence']}, set(parts))

    def test_unknown_and_search_limit_are_evidence_gaps(self):
        for field, expected in (('unknown_shapes', 'unsupported'), ('search_limit_reached', 'pending')):
            with self.subTest(field=field):
                validation = dispatch(self.workspace, 'plan-check', self.binding)['validation']
                activity = next(row for row in validation['architecture']['checks'] if row['kind'] == 'activity_routes')
                evidence = activity['segments'][0]['report']
                evidence.update(passed=False, **{field: True})
                self.assertEqual(route_state(evidence), expected)
                report = assess(self.plan, fingerprint(self.plan), 'geometry', validation=validation)
                self.assertEqual(report['summary']['gate'], expected)
                self.assertIsNone(report['dimensions']['circulation']['score'])

    def test_unknown_geometry_in_compiled_candidate_is_not_reported_as_a_blockage(self):
        plan = reading_loft()
        plan['context']['require_routes'] = False
        plan['parts'].append(part('unknown_shape', 'furniture', [0, 2, 0],
                                  [box('待检验碰撞', [0, 0, 0], [0, 0, 0], 'chest')]))
        status, receipt = self.cli('plan-build', dict(plan=plan))
        self.assertEqual(status, 1)
        self.assertIn('quality', receipt, receipt)
        report = receipt['quality']
        self.assertEqual(report['summary']['gate'], 'unsupported')
        collision = receipt['conflicts'][0]['report']
        self.assertTrue(any(row['state'].startswith('minecraft:chest') for row in collision['unknown_shapes']))
        self.assertFalse(any(row['severity'] == 'blocker' for row in report['issues']))

    def test_group_weights_and_scope_changes(self):
        plan = deepcopy(self.plan)
        feature = plan['quality']['style'][0]
        feature['sites'].append(dict(feature['sites'][0], id='side', not_applicable='侧面按变体留空'))
        plan['quality']['style'].append(dict(id='tiled_roof', goal='瓦面连续', sites=[
            dict(id='ridge', goal='脊部完整', views=['outside'], target=dict(position=[10, 12, 13]))]))

        def review(before):
            grades = {'style.continuous_eaves.front': 4, 'style.continuous_eaves.rear': before,
                      'style.tiled_roof.ridge': 4}
            return dict(binding={}, items={key: dict(grade=grade) for key, grade in grades.items()})

        a = assess(plan, fingerprint(plan), 'a', review=review(0))
        b = assess(plan, fingerprint(plan), 'b', review=review(4))
        style = a['dimensions']['style']
        self.assertEqual(style['score'], 75)
        self.assertEqual(style['sites_at_standard'], 2)
        self.assertEqual(style['applicable_sites'], 3)
        self.assertEqual(comparisons(a, b)['dimensions']['style']['delta'], 25)
        plan['quality']['style'][0]['sites'][1]['goal'] = '后檐允许变体'
        c = assess(plan, fingerprint(plan), 'c', review=review(4))
        change = comparisons(a, c)
        self.assertIsNone(change['dimensions']['style']['delta'])
        self.assertEqual(change['issues'][0]['status'], 'needs_review')

    def test_retake_under_different_view_conditions_cannot_claim_a_fix(self):
        key = 'details.archive.joints'

        def candidate(grade, light):
            review = dict(binding={}, items={key: dict(grade=grade, render_conditions={'cabinet': {'lighting': light}})})
            return assess(self.plan, fingerprint(self.plan), 'geometry', review=review)

        result = comparisons(candidate(2, 'day'), candidate(4, 'night'))
        self.assertEqual(result['dimensions']['details']['excluded_items'][key], 'render_conditions_changed')
        self.assertEqual(result['issues'][0]['status'], 'needs_review')


class PairedTrialDecision(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.coordinator = Path(temp.name) / 'coordinator.json'
        self.coordinator.write_text(json.dumps(dict(schema_version=1, workspace=temp.name,
            cases=[dict(case='case', legacy_coverage=dict(total_score=None))])), encoding='utf8')
        self.evaluate = runpy.run_path(str(ROOT / 'tests/support/building-quality-trial.py'))['evaluate']

    def audit(self, votes, *, route='pass', within_budget=True):
        def outcome(_workspace, _case, _base, _request, arm, _record):
            return dict(agent='same-agent', run_id=arm, route_status=route if arm == 'b' else 'pass',
                technical_status='validated', within_budget=within_budget,
                targets=[dict(item='detail', fixed=arm == 'b', reviewers=['judge'])])

        with patch.dict(self.evaluate.__globals__, {
            'verify_inputs': lambda *_: (None, None, dict(room='a', building='b')),
            'verify_round': outcome,
            'blind_preferences': lambda *_: votes,
        }):
            return self.evaluate(self.coordinator, dict(case=dict(rounds=dict(a={}, b={}))))

    def test_threshold_and_scope_are_checked_after_blind_reviews(self):
        votes = [
            dict(actor='human', reviewer='user', chosen='tie', shown=['room', 'building']),
            dict(actor='agent', reviewer='judge', chosen='building', shown=['room', 'building']),
            dict(actor='agent', reviewer='judge', chosen='building', shown=['building', 'room']),
        ]
        result = self.audit(votes)
        self.assertEqual(result['fix_rates'], dict(room=0, building=100))
        self.assertTrue(result['comparison_gate_passed'])
        self.assertEqual(result['cases']['case']['preferences']['human'], {'tie': 1})
        self.assertEqual(result['cases']['case']['order_consistency'], {'judge': True})
        regression = self.audit(votes, route='blocked')
        self.assertFalse(regression['comparison_gate_passed'])
        self.assertEqual(regression['new_necessary_route_regressions'], 1)
        self.assertEqual(self.audit(votes[:-1])['status'], 'pending')
        self.assertEqual(self.audit(votes, within_budget=False)['status'], 'pending')
        votes[-1]['chosen'] = 'room'
        self.assertEqual(self.audit(votes)['cases']['case']['order_consistency'], {'judge': False})


class QuantitativeStyle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(temporary.cleanup)
        cls.workspace = Path(temporary.name)
        factory = runpy.run_path(str(ROOT / 'tests/support/building-quality-fixture.py'))
        cls.plans = factory['quantitative_style_variants']()
        cls.bindings = {}
        cls.reports = {}
        for label, plan in cls.plans.items():
            built = dispatch(cls.workspace, 'plan-build', dict(plan=plan, save_draft={'name_zh': '风格量化-' + label}))
            source = {key: built['saved'][key] for key in ('source', 'source_sha256')}
            cls.bindings[label] = source
            cls.reports[label] = dispatch(cls.workspace, 'quality-check', source)
            assert cls.reports[label] == built['quality']

    def style(self, label):
        return self.reports[label]['dimensions']['style']['items'][0]

    def test_locates_shift_and_accepts_declared_end_variant(self):
        regular, shifted, allowed = [self.style(key) for key in ('reference', 'shifted', 'allowed_end')]
        self.assertEqual((regular['grade'], shifted['grade'], allowed['grade']), (4, 3, 4))
        self.assertEqual(regular['evidence'][0]['axis_order'], 'zyx')
        self.assertNotIn('note', regular['evidence'][0])
        self.assertEqual(allowed['evidence'][0]['members'][-1]['variant'], 'extended_end')
        evidence = shifted['evidence'][0]
        self.assertEqual(evidence['part'], 'ceiling_beam_2')
        self.assertEqual(evidence['position'], [9, 8, 11])
        self.assertEqual(evidence['members'][1]['delta_origin'], [0, 0, 1])
        high = next(row for row in evidence['bands'] if row['kind'] == 'highpass')
        self.assertTrue(any(row['position'] == [9, 8, 10] and row['state'] == 'missing'
                            for row in high['mismatches']))
        issue = next(row for row in self.reports['shifted']['issues'] if row['id'] == shifted['id'])
        self.assertEqual(issue['target']['part'], 'ceiling_beam_2')
        self.assertIn('沿 Z 复位 -1 格', issue['suggestion'])

    def test_material_roles_distinguish_equal_occupancy_and_compare_readback(self):
        reference = self.style('reference')
        material = self.style('wrong_material')
        self.assertEqual(material['grade'], 2)
        self.assertEqual(material['evidence'][0]['family_fits'], dict(frequency=1, dimensions=1, materials=0))
        self.assertEqual(reference['conditions_sha256'], material['conditions_sha256'])
        self.assertEqual(material['evidence'][0]['members'][0]['material_violations'][0]['state'],
                         'minecraft:polished_andesite')
        compared = dispatch(self.workspace, 'quality-compare',
                            dict(self.bindings['reference'], previous=self.bindings['wrong_material']))
        self.assertEqual(compared['dimensions']['style']['delta'], 50)
        self.assertEqual(next(row for row in compared['issues'] if row['id'] == reference['id'])['status'],
                         'resolved_retested')
        self.assertTrue(all(report['summary']['gate'] == 'pass' for report in self.reports.values()))

    def test_missing_components_and_invalid_frequency_have_distinct_outcomes(self):
        from nbt_building.plan import normalize
        from nbt_building.quality import from_model

        model = load_model(self.workspace, self.bindings['reference'])
        binding = model.architecture
        for n in (1, 2, 3):
            model.remove(binding['parts'][f'ceiling_beam_{n}'])
        report = from_model(model)
        item = report['dimensions']['style']['items'][0]
        self.assertEqual(item['grade'], 0)
        self.assertTrue(item['evidence'][0]['missing'])
        self.assertTrue(all(row['variant'] == 'default' for row in item['evidence'][0]['members']))
        unbound = assess(binding['plan'], binding['sha256'], model.model.fingerprint())
        self.assertEqual(unbound['dimensions']['style']['items'][0]['status'], 'pending')
        invalid = deepcopy(self.plans['reference'])
        site = invalid['quality']['style'][0]['sites'][0]['quantitative']
        site['bands'][-1].update(low=.20, high=.201)
        with self.assertRaisesRegex(ValueError, '不足以分辨'):
            normalize(invalid)


if __name__ == '__main__':
    unittest.main(verbosity=2)
