"""Quantitative building planning uses the same constraints for every layout."""
from copy import deepcopy
import json
from pathlib import Path
from runpy import run_path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.agents/skills/minecraft-nbt-modeler/scripts'))

from nbt_building.planning import assess_layout
from nbt_building.planning_geometry import assess_geometry
from nbt_composition.working_model import ModelConflict, WorkingModel, file_hash
from nbt_model import state
from nbt_project.architect import dispatch


def rect(x0, z0, x1, z1):
    return dict(lo=[x0, z0], hi=[x1, z1])


def example():
    program = dict(
        schema_version=1, size=[12, 10, 10], entry=[1.5, 1, 2.5],
        levels=[
            dict(id='ground', feet_y=1, ceiling_y=4, footprint=[rect(1, 1, 10, 8)]),
            dict(id='gallery', feet_y=5, ceiling_y=9, footprint=[rect(1, 1, 10, 8)],
                 voids=[rect(1, 1, 6, 4)]),
        ],
        spaces=[
            dict(id='entry', level='ground', purpose='门厅', min_area=9, target_area=10),
            dict(id='hall', level='ground', purpose='主厅', min_area=9),
            dict(id='archive', level='gallery', purpose='档案室', min_area=6),
        ],
        relations=[
            dict(id='entry_door', kind='door', min_width=2, **{'from': 'entry', 'to': 'hall'}),
            dict(id='main_stair', kind='stair', **{'from': 'hall', 'to': 'archive'}),
        ],
    )
    layout = dict(
        spaces=[
            dict(id='entry', regions=[rect(1, 1, 3, 3), rect(2, 3, 3, 4)]),
            dict(id='hall', regions=[rect(5, 1, 8, 4)]),
            dict(id='archive', regions=[rect(7, 4, 9, 6)]),
        ],
        links=[
            dict(id='entry_door', opening=rect(4, 2, 4, 3)),
            dict(id='main_stair', from_feet=[8.5, 1, 4.5], to_feet=[8.5, 5, 5.5]),
        ],
    )
    return program, layout


def checks(report):
    return {row['id']: row for row in report['checks']}


class WholeBuildingPlanning(unittest.TestCase):
    def test_area_uses_union_and_upper_void_does_not_reduce_lower_area(self):
        program, layout = example()
        report = assess_layout(program, layout)
        self.assertTrue(report['passed'], report)
        rows = checks(report)
        self.assertEqual(rows['space:entry:area']['actual'], 11)
        self.assertEqual(rows['space:archive:area']['actual'], 9)
        self.assertEqual(rows['relation:entry_door']['actual'], 2)
        self.assertEqual(report['metrics']['area_target_deviation'], 1)
        self.assertEqual(report, assess_layout(program, deepcopy(layout)))

    def test_failed_area_overlap_void_and_door_have_distinct_evidence(self):
        program, layout = example()
        program['spaces'][0]['min_area'] = 12
        program['spaces'][0]['target_area'] = 12
        layout['spaces'][1]['regions'] = [rect(3, 1, 8, 4)]
        layout['spaces'][2]['regions'] = [rect(6, 4, 9, 6)]
        report = assess_layout(program, layout)
        self.assertFalse(report['passed'])
        rows = checks(report)
        self.assertEqual(rows['space:entry:area']['status'], 'failed')
        self.assertEqual(rows['space:hall:overlap']['positions'][0], [3, 1, 1])
        self.assertEqual(rows['space:archive:bounds']['positions'], [[6, 5, 4]])
        self.assertEqual(rows['relation:entry_door']['actual'], 0)

    def test_missing_or_invalid_geometry_is_actionable(self):
        program, layout = example()
        layout['spaces'].pop()
        layout['links'].pop(0)
        report = assess_layout(program, layout)
        self.assertEqual(checks(report)['space:archive:placed']['status'], 'failed')
        self.assertEqual(checks(report)['relation:entry_door']['actual'], 0)
        layout['spaces'][0]['id'] = 'unknown'
        with self.assertRaisesRegex(ValueError, 'unknown'):
            assess_layout(program, layout)


    def test_public_build_and_readback_distinguish_room_area_and_door(self):
        sample = ROOT / '.agents/skills/minecraft-nbt-modeler/assets/examples/entry-pavilion.json'
        plan = json.loads(sample.read_text(encoding='utf8'))['plan']
        program = dict(
            schema_version=1, size=plan['size'], entry=plan['context']['start'],
            levels=[dict(id='ground', feet_y=1, ceiling_y=5, footprint=[rect(1, 0, 11, 10)])],
            spaces=[dict(id='entry', level='ground', purpose='入口', min_area=6),
                    dict(id='inside', level='ground', purpose='内厅', min_area=15)],
            relations=[dict(id='main_door', kind='door', min_width=3, **{'from': 'entry', 'to': 'inside'})],
        )
        layout = dict(spaces=[dict(id='entry', regions=[rect(5, 1, 7, 2)]),
                              dict(id='inside', regions=[rect(5, 4, 7, 8)])],
                      links=[dict(id='main_door', opening=rect(5, 3, 7, 3))])
        plan['planning'] = dict(program=program, layout=layout)
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            built = dispatch(workspace, 'plan-build', dict(plan=plan, save_draft={}))
            source = built['saved']['source']
            request = dict(source=source, source_sha256=file_hash(source))
            readback = dispatch(workspace, 'layout-check', request)
            self.assertTrue(readback['passed'], readback)
            self.assertEqual(readback['spaces']['inside']['net_area'], 15)
            self.assertEqual(readback['spaces']['inside']['reachable_area'], 15)
            self.assertEqual(checks(readback)['geometry:relation:main_door']['actual'], 3)
            checked = dispatch(workspace, 'plan-check', request)
            self.assertEqual(checked['validation']['architecture']['planning']['layout_sha256'],
                             readback['layout_sha256'])
            with self.assertRaisesRegex(ModelConflict, 'STALE_SOURCE'):
                dispatch(workspace, 'layout-check', dict(request, source_sha256='0' * 64))

            model = WorkingModel.open(workspace, source)
            model.model.blocks[(6, 1, 3)] = state('stone_bricks')
            actual = assess_geometry(model, plan['planning'], model.architecture)
            self.assertFalse(actual['passed'])
            self.assertEqual(actual['spaces']['inside']['reachable_area'], 15)
            self.assertEqual(checks(actual)['geometry:relation:main_door']['actual'], 1)

            model.model.blocks[(6, 1, 6)] = state('stone_bricks')
            actual = assess_geometry(model, plan['planning'], model.architecture)
            self.assertEqual(actual['spaces']['inside']['net_area'], 15)
            self.assertEqual(actual['spaces']['inside']['reachable_area'], 14)

            model.model.blocks[(4, 1, 6)] = state('spruce_button[face=floor,facing=north,powered=false]')
            actual = assess_geometry(model, plan['planning'], model.architecture)
            self.assertEqual(checks(actual)['geometry:relation:main_door']['status'], 'pending')
            self.assertIsNone(actual['spaces']['inside']['reachable_area'])

            invalid = deepcopy(plan)
            invalid['planning']['program']['spaces'][1]['min_area'] = 16
            versions = tuple(workspace.glob('nbt_models/**/model.snbt'))
            with self.assertRaisesRegex(ModelConflict, 'LAYOUT_INVALID'):
                dispatch(workspace, 'plan-build', dict(plan=invalid, save_draft={}))
            self.assertEqual(versions, tuple(workspace.glob('nbt_models/**/model.snbt')))


    def test_search_honors_locked_rooms_and_fixed_stair_landings(self):
        program, layout = example()
        program['entry_space'] = 'entry'
        request = dict(program=program, baseline=layout, locked=['entry', 'archive'], candidate_limit=3)
        found = dispatch(Path.cwd(), 'layout-search', request)
        self.assertEqual(found['status'], 'found')
        self.assertEqual(found, dispatch(Path.cwd(), 'layout-search', request))
        for candidate in found['candidates']:
            slots = {row['id']: row for row in candidate['layout']['spaces']}
            self.assertEqual(slots['entry'], layout['spaces'][0])
            self.assertEqual(slots['archive'], layout['spaces'][2])
            self.assertIn(layout['links'][1], candidate['layout']['links'])
            self.assertTrue(candidate['report']['passed'])

        missing = dispatch(Path.cwd(), 'layout-search', dict(program=program))
        self.assertEqual(missing['status'], 'input_required')
        self.assertEqual(missing['checks'][0]['reason'], 'missing_stair_landings')

    def test_search_budget_differs_from_exhausting_the_supported_domain(self):
        program, layout = example()
        program['spaces'][1]['min_area'] = 80
        limited = dispatch(Path.cwd(), 'layout-search', dict(program=program, baseline=layout, max_steps=1))
        self.assertEqual(limited['status'], 'budget_exhausted')
        impossible = dispatch(Path.cwd(), 'layout-search', dict(program=program, baseline=layout, locked=['entry']))
        self.assertEqual(impossible['status'], 'infeasible')
        self.assertEqual(impossible['termination'], 'exhausted')

    def test_selected_layout_prepares_a_buildable_candidate(self):
        sample = ROOT / '.agents/skills/minecraft-nbt-modeler/assets/examples/entry-pavilion.json'
        plan = json.loads(sample.read_text(encoding='utf8'))['plan']
        program = dict(
            schema_version=1, size=plan['size'], entry=plan['context']['start'], entry_space='entry',
            levels=[dict(id='ground', feet_y=1, ceiling_y=5, footprint=[rect(5, 1, 7, 8)])],
            spaces=[dict(id='entry', level='ground', purpose='入口', min_area=6),
                    dict(id='inside', level='ground', purpose='内厅', min_area=15, max_area=15)],
            relations=[dict(id='main_door', kind='door', min_width=3, **{'from': 'entry', 'to': 'inside'})],
        )
        baseline = dict(spaces=[dict(id='entry', regions=[rect(5, 1, 7, 2)])])
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            found = dispatch(workspace, 'layout-search', dict(program=program, baseline=baseline, locked=['entry']))
            self.assertEqual(found['status'], 'found')
            candidate = found['candidates'][0]['layout']
            prepared = dispatch(workspace, 'layout-prepare', dict(program=program, layout=candidate, plan=plan))
            self.assertEqual(prepared['plan']['context'], plan['context'])
            self.assertEqual(prepared['plan']['planning']['layout'], candidate)
            self.assertEqual([room['id'] for room in prepared['plan']['spaces']], ['entry', 'inside', 'walk'])
            built = dispatch(workspace, 'plan-build', dict(plan=prepared['plan']))
            self.assertTrue(built['checks']['architecture']['planning']['passed'])


    def test_multilevel_reading_loft_rechecks_stair_void_and_extent(self):
        sample = ROOT / '.agents/skills/minecraft-nbt-modeler/assets/examples/reading-loft/plan.py'
        plan = run_path(sample)['reading_loft']()
        program = dict(
            schema_version=1, size=plan['size'], entry=plan['context']['start'], max_extent=list(plan['size']),
            levels=[
                dict(id='ground', feet_y=2, ceiling_y=5, footprint=[rect(2, 3, 18, 18)]),
                dict(id='upper', feet_y=5, ceiling_y=10, footprint=[rect(2, 3, 18, 25)],
                     voids=[rect(8, 4, 11, 8)]),
            ],
            spaces=[
                dict(id='hall', level='ground', purpose='收卷厅', min_area=80, min_reachable_area=80),
                dict(id='loft', level='upper', purpose='归卷夹层', min_area=25, min_reachable_area=25),
            ],
            relations=[dict(id='loft_access', kind='stair', **{'from': 'hall', 'to': 'loft'})],
        )
        layout = dict(
            spaces=[dict(id='hall', regions=[rect(2, 3, 18, 18)]),
                    dict(id='loft', regions=[rect(3, 19, 9, 24)])],
            links=[dict(id='loft_access', stair='archive_stair',
                        from_feet=[5.5, 2, 4.5], to_feet=[5.5, 5, 19.5])],
        )
        plan['planning'] = dict(program=program, layout=layout)
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            built = dispatch(workspace, 'plan-build', dict(plan=plan, save_draft={}))
            source = built['saved']['source']
            good = dispatch(workspace, 'layout-check', dict(source=source, source_sha256=file_hash(source)))
            self.assertTrue(good['passed'], good)
            self.assertEqual(checks(good)['geometry:relation:loft_access']['status'], 'passed')
            self.assertEqual(checks(good)['geometry:level:upper:void']['actual'], 0)

            model = WorkingModel.open(workspace, source)
            model.model.blocks[(9, 4, 7)] = state('stone_bricks')
            model.model.blocks[(5, 5, 19)] = state('stone_bricks')
            stricter = deepcopy(plan['planning'])
            stricter['program']['max_extent'][1] = 8
            report = assess_geometry(model, stricter, model.architecture)
            rows = checks(report)
            self.assertEqual(rows['geometry:relation:loft_access']['reason'], 'blocked_route')
            self.assertEqual(rows['geometry:level:upper:void']['positions'], [[9, 5, 7]])
            self.assertFalse(rows['geometry:massing:extent']['passed'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
