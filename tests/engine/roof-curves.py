"""Curved roof skins retain real contact, bounds, budgets and shared entry points."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / '.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_assembly import Volume
from nbt_collision import collision_cells
from nbt_structure_agent import dispatch, build
from nbt_tools import modelling_plan


class RoofCurves(unittest.TestCase):
    def setUp(self):
        self.model = Volume([35, 20, 31])
        self.operation = dict(kind='auto_roof', label='曲面屋顶', classification='body',
            lo=[0, 0, 0], hi=[34, 19, 30], footprint=[[3, 3], [31, 27]],
            roof='curved_hip', rise=9, eave_lift=1, corner_lift=2, max_writes=12000)

    def test_curvature_and_corner_lift_change_the_actual_surface(self):
        plain, _ = modelling_plan(self.model, dict(self.operation, eave_lift=0, corner_lift=0))
        lifted, _ = modelling_plan(self.model, self.operation)
        def top(edits, x, z):
            return max(y for (a, y, b), _ in edits if (a, b) == (x, z))
        self.assertGreater(top(lifted, 3, 3), top(plain, 3, 3))
        self.assertEqual(top(lifted, 17, 15), top(plain, 17, 15))
        self.assertGreater(top(lifted, 3, 3), top(lifted, 3, 15))
        self.assertEqual(self.model.blocks, {})

    def test_axis_report_matches_profiles_that_use_it(self):
        x, curved = modelling_plan(self.model, dict(self.operation, ridge_axis='x'))
        z, _ = modelling_plan(self.model, dict(self.operation, ridge_axis='z'))
        self.assertEqual(x, z)
        self.assertIsNone(curved['ridge_axis_applied'])
        gable = {key: value for key, value in self.operation.items() if key not in ('eave_lift', 'corner_lift')}
        x, report = modelling_plan(self.model, dict(gable, roof='gable', ridge_axis='x'))
        z, _ = modelling_plan(self.model, dict(gable, roof='gable', ridge_axis='z'))
        self.assertNotEqual(x, z)
        self.assertEqual(report['ridge_axis_applied'], 'x')

    def test_real_halfcell_skin_stays_face_connected_for_all_finishes(self):
        for finish in ('blocks', 'slabs', 'stairs'):
            edits, _ = modelling_plan(self.model, dict(self.operation, finish=finish, rise=15))
            cells = set()
            for position, value in edits:
                occupied, reason = collision_cells(value)
                self.assertIsNone(reason)
                cells.update(tuple(position[i] * 2 + cell[i] for i in range(3)) for cell in occupied)
            pending = [cells.pop()]
            while pending:
                x, y, z = pending.pop()
                for point in ((x-1,y,z),(x+1,y,z),(x,y-1,z),(x,y+1,z),(x,y,z-1),(x,y,z+1)):
                    if point in cells:
                        cells.remove(point)
                        pending.append(point)
            self.assertEqual(cells, set(), finish)

    def test_protection_occupied_destinations_bounds_and_budget_remain_atomic(self):
        edits, _ = modelling_plan(self.model, self.operation)
        point, value = edits[0]
        with self.assertRaises(ValueError):
            modelling_plan(self.model, self.operation, protected=[point])
        self.model.put(point, 'gold_block')
        with self.assertRaises(ValueError):
            modelling_plan(self.model, self.operation)
        self.assertEqual(self.model.get(point), 'minecraft:gold_block')
        self.model.put(point, 'air')
        for changes in (dict(max_writes=1), dict(rise=40), dict(curve_power=True),
                        dict(eave_lift=float('nan')), dict(roof='hip')):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                modelling_plan(self.model, dict(self.operation, **changes))
        self.assertEqual(self.model.blocks, {})

    def test_structure_agent_compiles_the_same_roof_candidate(self):
        with tempfile.TemporaryDirectory() as directory:
            spec = dict(name='曲面屋顶试件', size=list(self.model.size), anchor=[0,0,0],
                        operations=[self.operation], max_changed_blocks=12000)
            candidate = dispatch(Path(directory), 'structure_preview', dict(spec=spec))
            data = build(Path(directory), spec)
            expected = dict(modelling_plan(self.model, self.operation)[0])
            actual = {tuple(row[:3]): data['palette'][row[3]] for row in data['blocks']}
            self.assertEqual(actual, expected)
            self.assertTrue(candidate['content_sha256'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
