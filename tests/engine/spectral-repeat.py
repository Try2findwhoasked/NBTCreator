"""Check measured section spectra through the public parametric tool entry points."""
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_agent.structure import build, dispatch


def recipe(labels=(0, 1, 1), cells=None):
    cells = cells or [[[0, 0, 0]], [[1, 0, 1], [0, 1, 1]]]
    channels = []
    for index, section in enumerate(cells):
        freq = np.fft.rfft(np.array(labels) == index, norm='forward')
        channels.append(dict(cells=section, coefficients=[[c.real.item(), c.imag.item()] for c in freq]))
    spectrum = dict(samples=len(labels), height=2, depth=2, channels=channels,
                    palette=['stone', 'birch_stairs[facing=east,half=top]'])
    return dict(kind='spectral_repeat', name='频谱测试', size=[7, 2, 2], period=len(labels), phase=0,
                spectrum=spectrum)


class SpectralRepeat(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def result(self, args):
        return dispatch(self.root, 'parametric_compile', args)

    def assert_labels(self, args, labels):
        compiled = self.result(args)
        actual = build(self.root, compiled['spec'])
        sections = []
        for x in range(args['size'][0]):
            sections.append({(y, z, actual['palette'][i]) for xx, y, z, i, _ in actual['blocks'] if xx == x})
        keys = [{(0, 0, 'minecraft:stone')},
                {(1, 0, 'minecraft:birch_stairs[facing=east,half=top]'),
                 (0, 1, 'minecraft:birch_stairs[facing=east,half=top]')}, set()]
        self.assertEqual(sections, [keys[i] for i in labels])
        self.assertEqual(compiled['block_count'], sum(map(len, sections)))
        return compiled

    def test_odd_even_empty_columns_and_clipped_end(self):
        self.assert_labels(recipe(), [0, 1, 1, 0, 1, 1, 0])
        even = recipe((2, 0, 1, 2), [[[0, 0, 0]], [[1, 0, 1], [0, 1, 1]], []])
        self.assert_labels(even, [2, 0, 1, 2, 2, 0, 1])
        self.assertEqual(list(self.root.iterdir()), [])

    def test_phase_modulo_and_resampling(self):
        args = dict(recipe(), period=5, phase=1)
        positive = self.assert_labels(args, [1, 0, 0, 1, 1, 1, 0])
        self.assertEqual(positive['content_sha256'], self.result(dict(args, phase=-4))['content_sha256'])
        self.assert_labels(dict(args, phase=-1), [0, 1, 1, 1, 0, 0, 1])
        self.assert_labels(dict(args, period=2, phase=0), [0, 1, 0, 1, 0, 1, 0])

    def test_invalid_spectrum_does_not_create_a_candidate(self):
        def reject(edit):
            args = recipe()
            edit(args, args['spectrum'], args['spectrum']['channels'][0])
            with self.assertRaises(ValueError):
                self.result(args)

        reject(lambda a, s, c: a.update(phase=True))
        reject(lambda a, s, c: a.pop('period'))
        reject(lambda a, s, c: a.update(material='gold_block'))
        reject(lambda a, s, c: a.update(kind='table'))
        reject(lambda a, s, c: a.update(max_changed_blocks=1))
        reject(lambda a, s, c: a.update(size=[13, 3, 2]))
        reject(lambda a, s, c: c['cells'].append([0, 0, 1]))
        reject(lambda a, s, c: c['cells'].append([0, 1, 9]))
        reject(lambda a, s, c: c['cells'].append([3, 0, 0]))
        reject(lambda a, s, c: s.update(palette=['air', 'oak_planks']))
        reject(lambda a, s, c: s.update(palette=['unknown_block', 'oak_planks']))
        reject(lambda a, s, c: c['coefficients'][0].__setitem__(1, .5))
        reject(lambda a, s, c: c['coefficients'].append([0, 0]))
        reject(lambda a, s, c: c.update(coefficients=s['channels'][1]['coefficients']))
        reject(lambda a, s, c: c.update(coefficients=[[.5, 0], [0, 0]]))
        even = recipe((0, 1, 0, 0))
        even['spectrum']['channels'][0]['coefficients'][-1][1] = .2
        with self.assertRaisesRegex(ValueError, '奈奎斯特'):
            self.result(even)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_preview_and_hard_constraints(self):
        args = recipe()
        expected = self.result(args)['content_sha256']
        preview = dispatch(self.root, 'parametric_preview', args)
        self.assertEqual(preview['content_sha256'], expected)
        self.assertTrue(Path(preview['thumbnail']).is_file())
        self.assertFalse(preview['approval_created'])
        validated = dispatch(self.root, 'parametric_validate',
                             dict(proposal=args, constraints=dict(kind='spectral_repeat', max_blocks=24)))
        self.assertEqual(validated['content_sha256'], expected)
        listing = dispatch(self.root, 'parametric_list', dict(kind='spectral_repeat'))
        self.assertEqual(listing['kinds'][0]['mount'], 'repeat_x')
        self.assertEqual(listing['kinds'][0]['styles'], {})


if __name__ == '__main__':
    unittest.main()
