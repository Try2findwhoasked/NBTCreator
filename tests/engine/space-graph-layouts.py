"""Space-graph candidates share a programme and must pass physical checks."""

from copy import deepcopy
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / '.agents/skills/minecraft-nbt-modeler'
sys.path[:0] = [str(SKILL / 'scripts'), str(SKILL / 'assets/examples/reading-loft')]
from layouts import reading_loft_layouts
from nbt_project.architect import dispatch


class Layouts(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.workspace = Path(directory.name)
        self.request = reading_loft_layouts()

    def search(self, request=None):
        return dispatch(self.workspace, 'layout-search', self.request if request is None else request)

    def test_two_circulations_and_physical_failures(self):
        before = deepcopy(self.request)
        result = self.search()
        self.assertEqual(self.request, before)
        self.assertEqual(list(self.workspace.iterdir()), [])
        self.assertEqual(result['mode'], 'graph')
        self.assertEqual(result['passed_count'], 2)
        self.assertTrue(result['read_only'])
        self.assertFalse(result['approval_created'] or result['nbt_exported'])
        front, side = result['candidates']
        self.assertEqual([front['id'], side['id']], ['front', 'side'])
        self.assertNotEqual(front['model_sha256'], side['model_sha256'])
        for field in ('name', 'size', 'envelope', 'levels', 'requirements'):
            self.assertEqual(front['plan'][field], side['plan'][field])
        for row, face, intake, landing in (
            (front, 'north', [13.5, 2, 8.5], [5.5, 5, 19.5]),
            (side, 'south', [6.5, 2, 10.5], [7.5, 5, 22.5]),
        ):
            circulation = row['circulation']
            entry = circulation['entry_routes']['file_books']
            self.assertEqual(entry['start'], self.request['plan']['context']['start'])
            self.assertEqual(entry['end'], intake)
            self.assertGreater(entry['steps'], 0)
            self.assertEqual(circulation['edges'][0]['gap'], 0)
            self.assertEqual(circulation['edges'][1]['route']['end'], landing)
            self.assertEqual(circulation['stairs'], [dict(id='archive_stair', passed=True)])
            faces = circulation['activities']['file_books']['use_faces']
            self.assertEqual(faces[0]['face'], face)
            self.assertTrue(all(item['passed'] for item in faces))
        attempts = {row['id']: row for row in result['attempts']}
        blocked, wrong = attempts['blocked'], attempts['wrong-side']
        self.assertEqual((blocked['status'], blocked['code']), ('rejected', 'ROUTE_FAILED'))
        issue = next(row for row in blocked['issues'] if row['target'] == 'stair_landing')
        self.assertEqual(issue['evidence']['feet'], [5.5, 5, 19.5])
        self.assertEqual(issue['activity_ids'], ['file_books'])
        issue, = wrong['issues']
        self.assertEqual((wrong['code'], issue['target']), ('DESIGN_INVALID', 'return_desk.intake'))
        self.assertEqual(issue['evidence']['reason'], 'wrong_side')
        self.assertEqual(issue['evidence']['feet'], [13.5, 2, 11.5])
        self.assertEqual(issue['activity_ids'], ['file_books'])

    def test_footprint_canvas_and_diagonal_fail_with_locations(self):
        self.request['graph']['variants'] = [
            dict(id='canvas', spaces=[dict(id='hall', hi=[21, 9, 18])]),
            dict(id='footprint', spaces=[dict(id='hall', lo=[1, 2, 5])]),
            dict(id='diagonal', spaces=[dict(id='entry_bay', lo=[2, 2, 3], hi=[3, 9, 4],
                                            samples=[[2.5, 2, 3.5]]),
                                        dict(id='hall', lo=[4, 2, 5])]),
            dict(id='stop', stops=[dict(activity='file_books', index=0, feet=[2.5, 2, 3.5])]),
        ]
        self.request.pop('areas')
        result = self.search()
        self.assertEqual(result['candidates'], [])
        canvas, footprint, diagonal, stop = (row['issues'][0] for row in result['attempts'])
        self.assertEqual((canvas['code'], canvas['hi']), ('SPACE_BOUNDS', [21, 9, 18]))
        self.assertEqual((footprint['code'], footprint['position']), ('SPACE_OUTSIDE_FOOTPRINT', [1, 2, 5]))
        self.assertEqual((diagonal['code'], diagonal['gap']), ('SPACE_ADJACENCY', None))
        self.assertEqual((stop['code'], stop['position']), ('STOP_OUTSIDE_SPACE', [2.5, 2, 3.5]))
        for issue in (canvas, footprint, diagonal, stop):
            self.assertEqual(issue['activity_ids'], ['file_books'])

    def test_polygon_footprint_rejects_an_in_bounds_space(self):
        volume, = self.request['plan']['envelope']['volumes']
        volume['polygon'] = [[2, 3], [19, 3], [19, 26], [2, 26], [2, 16], [4, 16], [4, 9], [2, 9]]
        self.request['graph']['variants'] = [dict(id='notch')]
        result = self.search()
        issue, = result['attempts'][0]['issues']
        self.assertEqual((issue['code'], issue['position']), ('SPACE_OUTSIDE_FOOTPRINT', [2, 2, 9]))

    def test_saved_seed_offset_requests_and_combination_limit(self):
        plan = self.request['plan']
        saved = dispatch(self.workspace, 'plan-save', dict(plan=plan, revision=0))
        request = dict(plan_id=saved['id'], revision=saved['revision'], limit=1, variables=[
            dict(id='cabinet', targets=[dict(kind='part', id='archive_cabinet')], offsets=[[0, -5], [0, 0]]),
        ])
        result = self.search(request)
        self.assertEqual(result['mode'], 'offsets')
        self.assertEqual(result['seed_plan_sha256'], saved['sha256'])
        self.assertEqual([row['status'] for row in result['attempts']], ['rejected', 'passed'])
        candidate, = result['candidates']
        self.assertEqual(candidate['offsets'], {'cabinet': [0, 0]})
        request['variables'].append(dict(
            id='desk', targets=[dict(kind='part', id='return_desk')], offsets=[[i, 0] for i in range(13)]))
        with self.assertRaisesRegex(ValueError, '最多 24'):
            self.search(request)

    def test_invalid_graph_contract(self):
        with self.assertRaisesRegex(ValueError, 'variables 或 graph'):
            self.search(dict(self.request, variables=[
                dict(id='test', targets=[dict(kind='part', id='return_desk')], offsets=[[0, 0]])]))
        with self.assertRaisesRegex(ValueError, 'variables 或 graph'):
            self.search(dict(plan=self.request['plan']))
        edge = self.request['graph']['edges'][1]
        edge['spaces'].reverse()
        with self.assertRaisesRegex(ValueError, '空间顺序'):
            self.search()
        edge['spaces'].reverse()
        self.request['graph']['variants'].append(dict(id='front'))
        with self.assertRaisesRegex(ValueError, 'variants ID 重复'):
            self.search()


if __name__ == '__main__':
    unittest.main()
