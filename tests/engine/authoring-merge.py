from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'support'))
from authoring_fixture import Inn, box
from nbt_composition.working_model import WorkingModel, model_hash
from nbt_refine import read_master


class Merge(Inn):
    def candidates(self, **options):
        root, _, left, right = self.delegate(**options)
        first = self.submit(self.claim(left['id']), left)
        second = self.submit(self.claim(right['id']), right)
        return root, self.select(first, second)

    def test_atomic_merge_roundtrip_and_parent_race(self):
        self.cli = True
        root, selected = self.candidates()
        merge = self.call('plan_merge', **self.merge_params(root, selected))
        self.assertEqual(merge['visual_review'], 'pending')
        params = dict(self.merge_params(root, selected), merge_sha256=merge['merge_sha256'], name_zh='合成旅店')
        self.call('save_draft', error='VISUAL_REVIEW_REQUIRED', **params)
        self.assertEqual(list(self.source.parents[2].glob('v_model_*')), [])
        request = self.request('save_draft', technical_trial='pending_visual_review', **params)
        saved = self.send(request)
        self.assertTrue(saved['ok'], saved)
        self.assertEqual(saved, self.send(request))
        self.assertEqual(len(list(self.source.parents[2].glob('v_model_*'))), 1)
        model, walls = read_master(self.workspace / saved['data']['source'])
        self.assertEqual(model_hash(model, walls), merge['model_sha256'])
        self.assertNotIn((3, 5, 3), walls)
        self.assertEqual(model.get((9, 5, 3)), 'minecraft:spruce_planks')
        self.assertFalse(saved['data']['approval_created'])

    def test_parent_advance_blocks_entire_merge(self):
        root, selected = self.candidates()
        params = self.merge_params(root, selected)
        merge = self.call('plan_merge', **params)
        other = WorkingModel.open(self.workspace, self.source)
        other.patch([dict(pos=[0, 5, 0], before=['minecraft:oak_planks', False], after=['minecraft:stone', False])])
        other.save_draft(name_zh='合成旅店')
        self.call('save_draft', error='STALE_PARENT', **dict(self.merge_params(root, selected),
                  merge_sha256=merge['merge_sha256'], technical_trial='pending_visual_review', name_zh='合成旅店'))
        self.assertEqual(len(list(self.source.parents[2].glob('v_model_*'))), 1)

    def test_dependency_change_blocks_entire_merge(self):
        root, selected = self.candidates(gap=1)
        reply = self.call('plan_merge', error='READ_DEPENDENCY_CHANGED', **self.merge_params(root, selected))
        self.assertEqual(reply['details']['dependencies'][0]['reader'], 'desk_batch')
        self.assertEqual(list(self.source.parents[2].glob('v_model_*')), [])

    def test_old_wall_layer_and_protected_position(self):
        _, _, left, _ = self.delegate(protected=[box((4, 5, 3), (4, 5, 3))])
        worker = self.claim(left['id'])
        edits = [dict(pos=[3, 5, 3], before=['minecraft:oak_planks', False], after=['minecraft:stone', False])]
        self.submit(worker, left, edits, error='PATCH_BASE_MISMATCH')
        edits[0].update(pos=[4, 5, 3], before=['minecraft:air', False])
        self.submit(worker, left, edits, error='PROTECTED_POSITION')

    def test_union_budget_and_duplicate_candidate_rejected(self):
        import json
        file = self.source.parents[1] / 'coordinates.json'
        coordinates = json.loads(file.read_bytes())
        file.write_text(json.dumps(dict(coordinates, max_changed_blocks=5)), encoding='utf8')
        root, selected = self.candidates()
        reply = self.call('plan_merge', error='CHANGE_BUDGET', **self.merge_params(root, selected))
        self.assertEqual(reply['details']['total'], 6)
        self.call('plan_merge', error='CANDIDATE_CHANGED', **self.merge_params(root, [selected[0]] * 2))
        self.assertEqual(list(self.source.parents[2].glob('v_model_*')), [])


if __name__ == '__main__':
    unittest.main()
