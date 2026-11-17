"""Regression checks for shipped small motifs and their advertised fit sizes."""
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / '.agents/skills/minecraft-nbt-modeler/scripts'
sys.path.insert(0, str(SCRIPTS))
from nbt_structure_agent import dispatch, build, definitions
from nbt_pattern_panel import LIBRARY
from nbt_collision import collision_cells


def topology(mask):
    """Independent 8-connected ink / 4-connected interior-hole flood."""
    height, width = mask.shape
    result = {}
    for ink, key in ((True, 'components'), (False, 'holes')):
        remaining = {(y, x) for y in range(height) for x in range(width) if bool(mask[y, x]) == ink}
        count = 0
        while remaining:
            pending = [remaining.pop()]
            edge = False
            while pending:
                y, x = pending.pop()
                edge |= y in (0, height - 1) or x in (0, width - 1)
                for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)) + (((-1, -1), (-1, 1), (1, -1), (1, 1)) if ink else ()):
                    point = (y + dy, x + dx)
                    if point in remaining:
                        remaining.remove(point)
                        pending.append(point)
            count += ink or not edge
        result[key] = count
    return result


def projected(workspace, result):
    width, height = result['microfit']['unit_size_uv']
    surface = result['surface']
    factor = 1 if surface == 'floor' else 2
    pixels = np.zeros((height * factor, width * factor), dtype=bool)
    data = build(workspace, result['spec'])
    for x, y, z, index, wall in data['blocks']:
        value = data['palette'][index]
        cells, error = collision_cells(value)
        assert not error
        if surface == 'floor':
            if value == 'minecraft:quartz_block':
                pixels[z, x] = True
        elif surface == 'ceiling':
            if y == 0:
                for a, b, c in cells:
                    if b == 0:
                        pixels[z * 2 + c, x * 2 + a] = True
        elif z == 1:
            for a, b, c in cells:
                pixels[y * 2 + b, x * 2 + a] = True
    return pixels


class MicroPresets(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.workspace = Path(temp.name)
        self.patterns = {key: item for key, item in dispatch(self.workspace, 'pattern_list', {})['patterns'].items()
                         if key.startswith('micro-')}

    def test_assets_are_reproducible_binary_masks_and_discoverable(self):
        self.assertEqual(len(self.patterns), 14)
        subprocess.run([sys.executable, str(ROOT / 'scripts/build-micro-patterns.py'), '--check'],
                       cwd=ROOT, check=True, capture_output=True, text=True)
        for key, item in self.patterns.items():
            with self.subTest(preset=key):
                raw = (LIBRARY / item['file']).read_bytes()
                self.assertEqual(hashlib.sha256(raw).hexdigest(), item['sha256'])
                with Image.open(LIBRARY / item['file']) as image:
                    self.assertEqual(image.mode, 'L')
                    self.assertEqual(set(np.unique(np.asarray(image))), {0, 255})
                    source_topology = topology(np.asarray(image) > 127)
                    self.assertEqual(source_topology['components'], 1)
                self.assertTrue(item['microfit']['preferred'])
                for tool in ('pattern_compile', 'pattern_preview', 'pattern_microfit'):
                    self.assertIn(key, definitions()[tool]['parameters']['properties']['preset']['enum'])

    def test_recommended_surface_sizes_retain_topology_and_shape(self):
        for key, item in self.patterns.items():
            with Image.open(LIBRARY / item['file']) as image:
                source_topology = topology(np.asarray(image) > 127)
            for surface, size in item['microfit']['recommended_size_uv'].items():
                with self.subTest(preset=key, surface=surface, size=size):
                    result = dispatch(self.workspace, 'pattern_microfit', dict(preset=key, surface=surface, size_uv=size))
                    quality = result['microfit']
                    self.assertTrue(quality['topology_preserved'])
                    self.assertFalse(quality['stylized'])
                    self.assertGreaterEqual(quality['ink_overlap'], item['microfit']['minimum_ink_overlap'])
                    self.assertLessEqual(quality['raw_coverage_error'], item['microfit']['maximum_coverage_error'])
                    self.assertEqual(quality['result_topology'], source_topology)
                    self.assertEqual(topology(projected(self.workspace, result)), source_topology)

    def test_two_block_ring_uses_four_stairs_but_tiny_flat_ring_is_rejected(self):
        result = dispatch(self.workspace, 'pattern_microfit', dict(surface='wall', preset='micro-link', size_uv=[2, 2]))
        self.assertEqual(result['shape_counts'], {'stairs': 4})
        self.assertEqual(result['microfit']['ink_overlap'], 1)
        self.assertEqual(topology(projected(self.workspace, result)), dict(components=1, holes=1))
        for surface in ('floor', 'ceiling'):
            with self.subTest(surface=surface), self.assertRaisesRegex(ValueError, '拓扑|主纹与孔洞'):
                dispatch(self.workspace, 'pattern_microfit', dict(surface=surface, preset='micro-link', size_uv=[2, 2]))

    def test_detail_material_states_are_generated_and_tiling_reuses_exact_units(self):
        args = dict(surface='wall', preset='micro-palmette', size_uv=[6, 6])
        single = dispatch(self.workspace, 'pattern_microfit', args)
        self.assertGreater(single['shape_counts']['stairs'], 0)
        self.assertGreater(single['shape_counts']['slab'], 0)
        tiled = dispatch(self.workspace, 'pattern_microfit', dict(args, tile_counts=[3, 2], gap_uv=[1, 1]))
        one = build(self.workspace, single['spec'])
        many = build(self.workspace, tiled['spec'])
        unit = {(x, y, z): one['palette'][index] for x, y, z, index, wall in one['blocks'] if z == 1}
        actual = {(x, y, z): many['palette'][index] for x, y, z, index, wall in many['blocks'] if z == 1}
        expected = {(x + column * 7, y + row * 7, z): value
                    for column in range(3) for row in range(2) for (x, y, z), value in unit.items()}
        self.assertEqual(actual, expected)
        self.assertEqual(tiled['shape_counts'], {key: value * 6 for key, value in single['shape_counts'].items()})


if __name__ == '__main__':
    unittest.main()
