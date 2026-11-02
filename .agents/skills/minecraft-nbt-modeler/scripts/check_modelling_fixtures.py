"""Synthetic regression for modelling geometry, growth and destructive plans."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from nbt_model import Model, AIR
from nbt_tools import apply_modelling, modelling_plan
from nbt_refine import operation_candidates


class ModellingTest(unittest.TestCase):
    def setUp(self):
        self.model = Model((24, 24, 24))

    def op(self, kind, **kwargs):
        return dict(kind=kind, lo=[0, 0, 0], hi=[23, 23, 23], **kwargs)

    def test_geometry_primitives_and_csg(self):
        shapes = [dict(shape='sphere', centre=[12, 12, 12], radius=4),
                  dict(shape='ellipsoid', centre=[12, 12, 12], radii=[3, 5, 4]),
                  dict(shape='cylinder', centre=[12, 12, 12], radius=3, height=8),
                  dict(shape='cone', centre=[12, 12, 12], radius=4, height=8),
                  dict(shape='torus', centre=[12, 12, 12], major_radius=5, minor_radius=2),
                  dict(shape='polyline', points=[[2, 2, 2], [10, 10, 10]], radius=1),
                  dict(shape='bezier', points=[[2, 2, 2], [8, 15, 8], [20, 5, 20]], radius=1),
                  dict(shape='extrude', vertices=[[3, 3], [12, 3], [12, 12], [3, 12]], bottom=4, top=8)]
        for shape in shapes:
            with self.subTest(shape=shape['shape']):
                op = self.op('geometry', geometry=shape, state='stone')
                edits, _ = modelling_plan(self.model, op)
                self.assertTrue(edits)
                self.assertEqual(edits, operation_candidates(self.model, op))
                self.assertFalse(self.model.blocks)
        outer = dict(shape='box', min=[4, 4, 4], max=[10, 10, 10])
        inner = dict(shape='box', min=[5, 5, 5], max=[9, 9, 9])
        edits, _ = modelling_plan(self.model, self.op('geometry', geometry=dict(shape='difference', children=[outer, inner])))
        self.assertEqual(len(edits), 6**3-4**3)

    def test_copy_and_repeat_preserve_states(self):
        v = 'oak_stairs[facing=east]'
        self.model.put((2, 2, 2), v)
        op = dict(kind='repeat_region', lo=[2, 2, 2], hi=[2, 2, 2], offset=[2, 0, 0], count=3)
        edits, _ = modelling_plan(self.model, op)
        self.assertEqual([p for p, _ in edits], [(4, 2, 2), (6, 2, 2), (8, 2, 2)])
        self.assertTrue(all(value == self.model.get((2, 2, 2)) for _, value in edits))
        self.model.put((4, 2, 2), 'dirt')
        with self.assertRaises(ValueError): modelling_plan(self.model, op)

    def test_morphology(self):
        self.model.put((12, 12, 12), 'stone')
        walls, report = apply_modelling(self.model, self.op('morphology', mode='dilate', classification='wall'))
        self.assertEqual(len(walls), 6)
        self.assertEqual(report['changed'], 6)
        self.model = Model((24, 24, 24)); self.model.box((8, 8, 8), (12, 12, 12), 'stone')
        edits, _ = modelling_plan(self.model, self.op('morphology', mode='shell'))
        self.assertEqual(len(edits), 27)
        self.assertTrue(all(v == AIR for _, v in edits))
        for mode in ('opening', 'closing', 'erode'):
            edits, _ = modelling_plan(self.model, self.op('morphology', mode=mode))
            self.assertTrue(all(self.model.in_bounds(p) for p, _ in edits))

    def test_diffusion_barrier_and_seed(self):
        op = self.op('diffusion', seeds=[[12, 12, 12]], steps=2, state='moss_block', from_states=['air'])
        edits, _ = modelling_plan(self.model, op, [(13, 12, 12)])
        self.assertEqual(len(edits), 23)  # 25-cell Manhattan ball minus barrier and the tip behind it.
        self.assertNotIn((13, 12, 12), dict(edits))
        self.assertTrue(all(sum(abs(v-12) for v in p) <= 2 for p, _ in edits))
        with self.assertRaises(ValueError): modelling_plan(self.model, op, [(12, 12, 12)])

    def test_explosion_static_protection_and_determinism(self):
        self.model.box((0, 0, 0), (23, 23, 23), 'stone')
        before = self.model.fingerprint()
        op = self.op('explosion', centre=[12, 12, 12], radius=4, rays=12, seed=33)
        edits, report = modelling_plan(self.model, op, [(12, 12, 12)])
        self.assertGreater(len(edits), 100)
        self.assertNotIn((12, 12, 12), dict(edits))
        self.assertEqual(edits, modelling_plan(self.model, op, [(12, 12, 12)])[0])
        self.assertFalse(report['physics_simulated'])
        self.assertEqual(before, self.model.fingerprint())

    def test_scatter_spacing_support(self):
        self.model.box((0, 0, 0), (23, 0, 23), 'stone')
        edits, _ = modelling_plan(self.model, self.op('scatter', fraction=1, spacing=3, state='cobblestone'))
        self.assertTrue(edits)
        self.assertTrue(all(p[1] == 1 for p, _ in edits))
        self.assertTrue(all(sum((a[i]-b[i])**2 for i in range(3)) >= 9 for j, (a, _) in enumerate(edits) for b, _ in edits[j+1:]))

    def test_atomic_rejections(self):
        before = self.model.fingerprint()
        geometry = dict(shape='sphere', centre=[12, 12, 12], radius=3)
        op = self.op('geometry', geometry=geometry)
        with self.assertRaises(ValueError): apply_modelling(self.model, op, protected=[(12, 12, 12)])
        with self.assertRaises(ValueError): apply_modelling(self.model, dict(op, max_writes=1))
        with self.assertRaises(ValueError): apply_modelling(self.model, dict(op, hi=[25, 23, 23]))
        with self.assertRaises(ValueError): modelling_plan(self.model, self.op('replace', state='dirt'))
        self.assertEqual(before, self.model.fingerprint())
        self.model.stage = 'sealed'
        with self.assertRaises(ValueError): apply_modelling(self.model, op)

    def test_transform_coordinates_and_state(self):
        self.model.put((2, 2, 2), 'oak_log[axis=x]')
        op = dict(kind='transform_region', lo=[2, 2, 2], hi=[3, 2, 4],
                  destination=[10, 2, 10], quarter_turns=1)
        edits, _ = modelling_plan(self.model, op)
        self.assertIn((12, 2, 10), dict(edits))
        self.assertIn('axis=z', dict(edits)[(12, 2, 10)])
        mirror = dict(op, quarter_turns=0, mirror='x', move=True)
        edits, _ = modelling_plan(self.model, mirror)
        self.assertEqual(dict(edits)[(2, 2, 2)], AIR)
        self.assertIn('axis=x', dict(edits)[(11, 2, 10)])
        self.model.put((2, 2, 2), 'oak_stairs')
        with self.assertRaises(ValueError): modelling_plan(self.model, op)

    def test_read_only_cli(self):
        from nbt_refine import save_master
        with tempfile.TemporaryDirectory(prefix='nbt_modelling_fixture_') as temp:
            root = Path(temp); source = root/'source.master.json.gz'
            save_master(source, self.model, set())
            original = source.read_bytes()
            operation = root/'operation.json'; output = root/'plan.json'
            operation.write_text(json.dumps(self.op('geometry', geometry=dict(shape='sphere', centre=[12,12,12], radius=2))), encoding='utf8')
            command = [sys.executable, str(Path(__file__).with_name('nbt_tools.py')), '--source', str(source),
                       '--operation', str(operation), '--output', str(output)]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(output.read_text(encoding='utf8'))
            self.assertFalse(report['asset_written'])
            self.assertTrue(report['edits'])
            self.assertEqual(source.read_bytes(), original)
            self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ModellingTest))
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output/'regression.json').write_text(json.dumps(dict(passed=result.wasSuccessful(), tests=result.testsRun,
        failures=[str(t) for t, _ in result.failures], errors=[str(t) for t, _ in result.errors]), indent=2), encoding='utf8')
    return int(not result.wasSuccessful())


if __name__ == '__main__':
    raise SystemExit(main())
