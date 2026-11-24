"""Offline tests driven by independent synthetic furniture specifications."""
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / '.agents/skills/minecraft-furniture-reference'
SCRIPT = SKILL / 'scripts/furniture.py'
sys.path.insert(0, str(ROOT / '.agents/skills/minecraft-nbt-modeler/scripts'))

from nbt_composition.working_model import WorkingModel
from nbt_snbt import save_snbt

module_spec = importlib.util.spec_from_file_location('furniture_workflow', SCRIPT)
furniture = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(furniture)


class FurnitureWorkflow(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)

    def run_cli(self, *args, error=None):
        run = subprocess.run([sys.executable, '-B', str(SCRIPT), *map(str, args)],
                             cwd=self.root, capture_output=True, encoding='utf-8', timeout=30)
        self.assertEqual(run.returncode, int(error is not None), run.stdout + run.stderr)
        if error:
            self.assertIn(error, run.stderr)

    def test_cli_replays_chair_table_and_cabinet(self):
        expected = {'chair': (3, 'spruce_stairs'), 'table': (10, 'birch_slab'),
                    'cabinet': (4, 'barrel')}
        for name, (count, material) in expected.items():
            with self.subTest(name=name):
                first, second = self.root / (name + '-a'), self.root / (name + '-b')
                self.run_cli('build', '--spec', SKILL / f'examples/{name}.json', '--output', first)
                self.run_cli('build', '--spec', first / 'spec.json', '--output', second)
                receipt = furniture.read(first / 'receipt.json')
                self.assertEqual(receipt['data_version'], 3465)
                self.assertFalse(receipt['in_game_verified'])
                ledger = furniture.read(first / 'main/ledger.json')
                self.assertEqual(len(ledger['states']), count)
                self.assertEqual(ledger['wall_positions'], [])
                self.assertTrue(any(row[-1].startswith('minecraft:' + material) for row in ledger['states']))
                self.run_cli('compare', first, second, '--output', self.root / f'{name}.json')
                (second / 'main/ledger.json').write_text('{}', encoding='utf-8')
                self.run_cli('compare', first, second, '--output', self.root / 'invalid.json',
                             error='Run file differs from receipt')

    def test_invalid_recipes_fail_before_output(self):
        cases = [
            (lambda rows: rows.append(rows[0]), 'overlapping regions'),
            (lambda rows: rows[0].update(hi=[20, 0, 0]), 'outside the model'),
            (lambda rows: rows[0].update(state='spruce_slab[type=vertical]'), 'vertical'),
            (lambda rows: rows[0].update(state='air'), 'non-air'),
        ]
        for mutation, error in cases:
            with self.subTest(error=error):
                spec = furniture.read(SKILL / 'examples/chair.json')
                mutation(spec['candidates']['main']['regions'])
                source = self.root / 'input.json'
                source.write_text(json.dumps(spec), encoding='utf-8')
                output = self.root / 'invalid'
                self.run_cli('build', '--spec', source, '--output', output, error=error)
                self.assertFalse(output.exists())

    def test_rejects_oversize_furniture_and_high_review_camera(self):
        for field, error in (('size', 'two blocks in Y'), ('cameras', 'at most 2 blocks')):
            with self.subTest(field=field):
                spec = furniture.read(SKILL / 'examples/chair.json')
                if field == 'size':
                    spec['size'][1] = 3
                else:
                    spec['cameras'][0]['eye'][1] = 2.01
                source = self.root / (field + '.json')
                furniture.write(source, spec)
                self.run_cli('build', '--spec', source, '--output', self.root / 'invalid', error=error)

    def test_exact_known_join_rejects_half_cell_gap(self):
        path = SKILL / 'examples/chair.json'
        spec = furniture.read(path)
        spec['parts'] = [p for p in spec['parts'] if p['id'] != 'post']
        spec['joins'] = [['seat', 'back']]
        spec['candidates']['main']['regions'] = [
            dict(part='seat', lo=[0, 0, 0], hi=[0, 0, 0], state='spruce_slab[type=bottom]'),
            dict(part='back', lo=[0, 0, 1], hi=[0, 0, 1], state='spruce_slab[type=top]'),
        ]
        source = self.root / 'input.json'
        furniture.write(source, spec)
        self.run_cli('build', '--spec', source, '--output', self.root / 'invalid',
                     error='no exact half-cell contact')

    def test_photo_bytes_must_match_frozen_hash(self):
        spec = furniture.read(SKILL / 'examples/chair.json')
        spec['source'] = dict(kind='photo', title='Synthetic hash test', url='https://example.invalid',
                              license='test-only', credit='test-only', sha256='0' * 64)
        source = self.root / 'input.json'
        photo = self.root / 'fixture.jpg'
        photo.write_bytes(b'independent synthetic byte fixture')
        furniture.write(source, spec)
        self.run_cli('build', '--spec', source, '--photo', photo, '--output', self.root / 'invalid',
                     error='Reference photo SHA256 mismatch')

    def test_host_preflight_checks_support_protection_and_standing(self):
        workspace = self.root
        host = workspace / 'nbt_models/standalone/test-room/v001/master/model.snbt'
        working = WorkingModel(workspace, [10, 5, 10])
        working.apply_operations([dict(kind='box', label='Host floor', lo=[0, 0, 0], hi=[9, 0, 9], state='stone')])
        save_snbt(host, working.model, working.walls)
        digest = furniture.sha(host)
        request = dict(source=str(host.relative_to(workspace)), source_sha256=digest,
                       position=[6, 1, 5], writable_box=dict(lo=[5, 1, 5], hi=[6, 3, 7]),
                       route_start=[1.5, 1, 1.5], route_targets={'passage': [1.5, 1, 8.5]},
                       quarter_turns=1)
        request_path = self.root / 'request.json'
        output = self.root / 'proposal.json'
        cmd = ('host-check', '--spec', SKILL / 'examples/chair.json', '--candidate', 'main',
               '--workspace', workspace, '--host', request_path)
        coordinates = host.parents[1] / 'coordinates.json'
        context = dict(mode='standalone', openings=[], start=request['route_start'],
                       targets=request['route_targets'])
        furniture.write(coordinates, context)
        furniture.write(request_path, request)
        self.run_cli(*cmd, '--output', output)
        report = furniture.read(output)
        self.assertEqual(len(report['exact_floor_supports']), 2)
        self.assertTrue(report['after']['passed'])
        self.assertEqual(report['placement']['operations'][0]['palette'][1],
                         'minecraft:spruce_stairs[facing=west,half=bottom,shape=straight,waterlogged=false]')

        def write_request(change):
            request_path.write_text(json.dumps(request | change), encoding='utf-8')

        write_request({'source_sha256': '0' * 64})
        self.run_cli(*cmd, '--output', self.root / 'stale.json', error='STALE_SOURCE')
        write_request({'writable_box': {'lo': [6, 1, 5], 'hi': [6, 3, 7]}})
        self.run_cli(*cmd, '--output', self.root / 'outside.json', error='outside the host writable box')
        write_request({'position': [6, 2, 5]})
        self.run_cli(*cmd, '--output', self.root / 'floating.json', error='Exact floor contact unavailable')
        write_request({'route_targets': {'stand': [5.5, 1, 5.5]}})
        self.run_cli(*cmd, '--output', self.root / 'blocked.json', error='failed after placement')
        write_request({})
        context['protected_boxes'] = [dict(lo=[5, 1, 5], hi=[5, 1, 5])]
        coordinates.write_text(json.dumps(context), encoding='utf-8')
        self.run_cli(*cmd, '--output', self.root / 'protected.json', error='保护')
        self.assertEqual(furniture.sha(host), digest)


if __name__ == '__main__':
    unittest.main()
