import copy
from pathlib import Path
import sys
import json
import subprocess
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'support'))
from authoring_fixture import Inn, ROOT
from nbt_composition.working_model import WorkingModel
from nbt_selection_edit import dispatch as selection_edit


class Runs(Inn):
    def test_one_block_high_wooden_table_uses_short_path(self):
        workspace = self.workspace / 'furniture'
        workspace.mkdir()
        table = WorkingModel(workspace, [3, 1, 2], kind='component')
        materials = ['oak_stairs[facing=west,half=top]', 'oak_slab[type=top]', 'oak_stairs[facing=east,half=top]']
        table.patch([dict(pos=[x, 0, z], before=['minecraft:air', False], after=[material, False])
                     for z in range(2) for x, material in enumerate(materials)])
        self.assertTrue(table.validate()['block_states'])
        preview = table.preview(workspace / 'preview', [dict(id='table', eye=[5, 3, 5], target=[1.5, .5, 1])])
        snapshot = json.loads(Path(preview['snapshot']).read_bytes())
        self.assertEqual(snapshot['size'], [3, 1, 2])
        self.assertEqual(len(snapshot['blocks']), 6)
        request = dict(source=str(self.source), source_sha256=self.parent_hash, lo=[6, 5, 7], hi=[8, 5, 8])
        file = workspace / 'selection.json'
        file.write_text(json.dumps(request), encoding='utf8')
        result = subprocess.run(['node', str(ROOT / 'scripts/cli.mjs'), '--workspace', str(self.workspace),
                                 'selection-edit', 'context', '--request', str(file)], encoding='utf8',
                                capture_output=True, check=True)
        self.assertEqual(json.loads(result.stdout)['size'], [3, 1, 2])
        operations = selection_edit('compile', dict(request, operations=[dict(kind='box', lo=[0, 0, 0], hi=[2, 0, 1],
                                    state='oak_slab[type=top]', classification='body')]))['operations']
        self.assertEqual(operations[0]['lo'], [6, 5, 7])
        self.assertEqual(list(workspace.rglob('authoring.json')), [])

    def test_concept_photo_and_stale_reference(self):
        self.call('create', mode='image_guided', task='Synthetic image guide')
        self.assertEqual(self.call('inspect')['reference_status'], 'required')
        wrong = copy.deepcopy(self.pack)
        wrong['images'][0]['sha256'] = '0' * 64
        self.call('bind_reference', run_revision=1, pack=wrong, error='REFERENCE_CHANGED')
        wrong = copy.deepcopy(self.pack)
        wrong['images'][0]['crops'][0]['pixels'] = [0, 0, 33, 24]
        self.call('bind_reference', run_revision=1, pack=wrong, error='VALIDATION_ERROR')
        result = self.call('bind_reference', run_revision=1, pack=self.pack)
        self.assertEqual(result['references']['images'][0]['pixels'], [32, 24])
        self.assertEqual(result['references']['images'][0]['crops'][0]['role'], 'desk joinery')
        self.image.write_bytes(b'changed')
        self.assertEqual(self.call('inspect')['reference_status'], 'changed')

    def test_text_only_and_idempotent_creation(self):
        create = self.request('create', mode='text_only', task='Synthetic text only')
        first = self.send(create)
        self.assertEqual(first['data']['phase'], 'references_bound')
        self.assertEqual(first['data']['reference_status'], 'not_applicable')
        self.assertEqual(first, self.send(create))
        create['params']['task'] = 'Changed'
        self.assertEqual(self.send(create)['error']['code'], 'IDEMPOTENCY_CONFLICT')


if __name__ == '__main__':
    unittest.main()
