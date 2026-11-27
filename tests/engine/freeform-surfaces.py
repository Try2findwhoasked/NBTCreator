"""Analytic surface fitting, voxel geometry and shared tool entry points."""
from copy import deepcopy
from io import BytesIO
import itertools
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_agent.structure import build, dispatch
from nbt_composition.working_model import WorkingModel
from nbt_engine_session import serve


def saddle():
    return dict(v0=[[2.5, 6.5, 2.5], [17.5, 13.5, 2.5]],
                v1=[[2.5, 13.5, 17.5], [17.5, 6.5, 17.5]],
                u0=[[2.5, 6.5, 2.5], [2.5, 13.5, 17.5]],
                u1=[[17.5, 13.5, 2.5], [17.5, 6.5, 17.5]])


def flat_patch(y=5.5):
    return dict(control_points=[[[x, y, z] for z in (3.25, 7.75)] for x in (3.25, 7.75)])


def positions(result):
    return {tuple(block[:3]) for block in result['spec']['operations'][0]['voxels']}


class FreeformSurfaces(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.workspace = Path(directory.name)

    def call(self, tool, **arguments):
        return dispatch(self.workspace, tool, arguments)

    def cli(self, tool, arguments):
        request = self.workspace / f'{tool}.json'
        request.write_text(json.dumps(arguments), encoding='utf8')
        run = subprocess.run(['node', str(ROOT / 'scripts/cli.mjs'), '--workspace', str(self.workspace),
                              'components', 'agent', '--tool', tool, '--request', request.name],
                             capture_output=True, text=True, encoding='utf8', timeout=60)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        return json.loads(run.stdout)['result']

    def test_bivariate_fit_recovers_polynomial_in_all_three_coordinates(self):
        # Analytic polynomial coefficients give an independent quadratic control net.
        samples = [dict(uv=[u, v], position=[2 + 8*u + v*v, 4 + 2*u*v, 2 + 6*v + 4*u*u])
                   for u, v in itertools.product(np.linspace(0, 1, 5).tolist(), repeat=2)]
        result = self.call('surface_fit', degree=[2, 2], samples=samples, max_error=1e-9)
        expected = [[[2 + 4*i + (j == 2), 4 + i*j/2, 2 + 3*j + 4*(i == 2)]
                     for j in range(3)] for i in range(3)]
        np.testing.assert_allclose(result['patch']['control_points'], expected, atol=1e-10, rtol=0)
        self.assertEqual(result['fit']['rank'], 9)
        self.assertEqual(result['fit']['uv_bounds'], [[0, 0], [1, 1]])
        self.assertLess(result['fit']['rmse'], 1e-10)

    def test_edge_curves_are_degree_elevated_and_interior_fit_preserves_them(self):
        boundaries = saddle()
        boundaries['v0'].insert(1, [10, 14, 2.5])
        coons = self.call('surface_fit', boundaries=boundaries, degree=[3, 2])
        base = np.array(coons['patch']['control_points'])
        np.testing.assert_allclose(base[1:3, 0], [[7.5, 11.5, 2.5], [12.5, 83/6, 2.5]], atol=1e-10)
        np.testing.assert_allclose(base[:, -1], [[2.5, 13.5, 17.5], [7.5, 67/6, 17.5],
                                                 [12.5, 53/6, 17.5], [17.5, 6.5, 17.5]], atol=1e-10)
        source = self.call('surface_fit', boundaries=saddle(), degree=[2, 2],
                           samples=[dict(uv=[0.5, 0.5], position=[10, 11, 10])])
        net = np.array(source['patch']['control_points'])
        self.assertTrue(source['locked_boundaries'])
        np.testing.assert_allclose(net[:, 0], [[2.5, 6.5, 2.5], [10, 10, 2.5], [17.5, 13.5, 2.5]])
        np.testing.assert_allclose(net[0, :], [[2.5, 6.5, 2.5], [2.5, 10, 10], [2.5, 13.5, 17.5]])
        np.testing.assert_allclose(net[1, 1], [10, 14, 10])
        self.assertEqual(source['fit']['solved_controls'], 1)
        self.assertLess(source['fit']['max_error'], 1e-10)

    def test_rank_error_gate_and_mismatched_boundary_fail_without_writes(self):
        boundaries = saddle()
        boundaries['v0'].reverse()
        samples = [dict(uv=[u, u], position=[4*u, 5, 4*u]) for u in (0, 0.25, 0.5, 1)]
        contradictory = [dict(uv=[0.5, 0.5], position=[10, 14, 10])]
        for arguments, error in [(dict(boundaries=boundaries), '端点'),
                                 (dict(degree=[1, 1], samples=samples), 'UV 分布'),
                                 (dict(boundaries=saddle(), samples=contradictory, max_error=0.1), '超过'),
                                 (dict(), '须提供')]:
            with self.subTest(error=error), self.assertRaisesRegex(ValueError, error):
                self.call('surface_fit', **arguments)
        self.assertEqual(list(self.workspace.iterdir()), [])

    def test_planar_cell_coverage_and_symmetric_distance_thickness(self):
        args = dict(size=[12]*3, patch=flat_patch())
        thin = self.call('surface_compile', **args)
        self.assertEqual(positions(thin), {(x, 5, z) for x in range(3, 8) for z in range(3, 8)})
        self.assertEqual(thin['tessellation']['segments_uv'], [1, 1])
        thick = self.call('surface_compile', **args, thickness=2.2)
        self.assertEqual({y for x, y, z in positions(thick) if (x, z) == (5, 5)}, {4, 5, 6})
        self.assertIn((2, 5, 5), positions(thick))
        self.assertNotIn((2, 6, 5), positions(thick))
        self.assertTrue(thick['face_connected'])
        on_boundary = self.call('surface_compile', size=[12]*3, patch=flat_patch(y=5))
        self.assertEqual({y for _, y, _ in positions(on_boundary)}, {4, 5})

    def test_vertical_fold_is_not_limited_to_a_height_map(self):
        patch = dict(control_points=[[[3, 3, z] for z in (2.5, 7.5)],
                                     [[11, 5, z] for z in (2.5, 7.5)],
                                     [[3, 11, z] for z in (2.5, 7.5)]])
        result = self.call('surface_compile', size=[14]*3, patch=patch, tolerance=0.05)
        self.assertTrue(result['face_connected'])
        self.assertLessEqual(result['tessellation']['max_deviation_bound'], 0.05)
        heights = sorted(y for x, y, z in positions(result) if (x, z) == (4, 4))
        self.assertGreater(heights[-1] - heights[0], 3)
        self.assertNotIn(6, heights)

    def test_rejects_a_clipped_or_degenerate_shell_and_invalid_component_options(self):
        args = dict(size=[12]*3, patch=flat_patch())
        bad = deepcopy(args['patch'])
        bad['control_points'][1] = bad['control_points'][0]
        ragged = deepcopy(args['patch'])
        ragged['control_points'][1].append([5, 6, 7])
        for change, error in [(dict(size=[7]*3), '画布'), (dict(thickness=8), '厚度'),
                              (dict(patch=bad), '退化'), (dict(patch=ragged), '矩形'),
                              (dict(max_changed_blocks=2), '预算'), (dict(material='oak_stairs'), '完整方块')]:
            with self.subTest(error=error), self.assertRaisesRegex(ValueError, error):
                self.call('surface_compile', **(args | change))
        self.assertEqual(list(self.workspace.iterdir()), [])

    def test_cli_saddle_round_trip_preview_scene_and_working_model(self):
        fit = self.cli('surface_fit', dict(boundaries=saddle()))
        args = dict(patch=fit['patch'], size=[20, 16, 20], thickness=1.5, classification='wall', anchor=[0, 0, 0])
        compiled = self.cli('surface_compile', args)
        self.assertEqual(compiled, self.call('surface_compile', **args))
        self.assertEqual(compiled['content_sha256'], build(self.workspace, compiled['spec'])['content_sha256'])
        self.assertTrue(compiled['face_connected'])
        self.assertFalse((self.workspace / 'nbt_models').exists())

        stream = BytesIO()
        requests = [dict(id=tool, method='agent', params=dict(tool=tool, arguments=arguments))
                    for tool, arguments in [('surface_fit', dict(boundaries=saddle())), ('surface_compile', args)]]
        serve(self.workspace, BytesIO(''.join(json.dumps(request) + '\n' for request in requests).encode()), stream)
        self.assertEqual([json.loads(reply)['result'] for reply in stream.getvalue().splitlines()], [fit, compiled])

        recipe = compiled['recipe']
        scene = self.call('scene_compile', graph=dict(schema_version=1, name='鞍形屋面', size=[24]*3,
                          objects=[dict(id='roof', lo=[0, 0, 0], recipe=recipe)]))
        self.assertEqual(scene['block_count'], compiled['block_count'])
        model = WorkingModel(self.workspace, [24]*3)
        model.install('roof', recipe, [1, 1, 1])
        self.assertEqual(set(model.model.blocks), {tuple(v+1 for v in p) for p in positions(compiled)})
        self.assertEqual(set(model.walls), set(model.model.blocks))

        preview = self.cli('structure_preview', dict(spec=compiled['spec']))
        self.assertEqual(preview['content_sha256'], compiled['content_sha256'])
        with Image.open(preview['thumbnail']) as image:
            self.assertEqual(image.format, 'JPEG')
            image.verify()


if __name__ == '__main__':
    unittest.main(verbosity=2)
