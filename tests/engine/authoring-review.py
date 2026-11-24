import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

from PIL import Image, ImageChops

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'support'))
from authoring_fixture import Inn, ROOT, box
from nbt_assembly import Volume
from nbt_project.batches import sha
from nbt_refine import save_master


class Review(Inn):
    def preview(self):
        root, self.region, self.left, right = self.delegate(floor_edit=True)
        self.call('heartbeat', ttl_seconds=600, **root)
        self.call('heartbeat', ttl_seconds=600, **self.region)
        floor = dict(pos=[3, 4, 3], before=['minecraft:spruce_planks', False], after=['minecraft:red_wool', False])
        selected = self.select(self.submit(self.claim(self.left['id']), self.left, self.edits(self.left) + [floor]),
                               self.submit(self.claim(right['id']), right))
        merge = self.call('plan_merge', **self.merge_params(root, selected))
        return root, selected, merge['merge_sha256']

    def review_call(self, method, root, merge, **kwargs):
        return self.call(method, **root, merge_sha256=merge, run_revision=self.call('inspect')['revision'], **kwargs)

    def views(self):
        return [dict(space='hall', feet=[3.5, 1, 6.5], route_start=[2.5, 1, 2.5],
                     camera=dict(id='ceiling', eye=[3.5, 2.62, 6.5], target=[3.5, 4.2, 3.5])),
                dict(space='attic', feet=[3.5, 5, 6.5], route_start=[2.5, 5, 7.5],
                     camera=dict(id='furnishings', eye=[3.5, 6.62, 6.5], target=[3.5, 5.5, 3.5])),
                dict(camera=dict(id='arrival', eye=[-7, 4, 7], target=[7, 3, 6]))]

    def render(self, pack, side, output):
        command = ['node', str(ROOT / 'scripts/cli.mjs'), '--workspace', str(self.workspace),
                   *pack['render_commands'][side], '--output', str(output), '--width', '480', '--height', '320']
        result = subprocess.run(command, cwd=self.workspace, encoding='utf8', capture_output=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        manifest = output / 'render_manifest.json'
        return dict(path=str(manifest), sha256=sha(manifest))

    def test_shared_floor_dual_side_review_and_same_camera_evidence_binding(self):
        root, selected, merge = self.preview()
        pack = self.review_call('prepare_review', root, merge, views=self.views())
        self.assertEqual(pack['rooms'], ['attic', 'hall'])
        self.assertEqual(pack['interfaces'][0]['id'], 'shared_floor')
        self.assertIn([3, 4, 3], pack['interfaces'][0]['positions'])
        self.assertTrue(all(pack['checks'][key]['route']['passed'] for key in ('ceiling', 'furnishings')))
        output = self.workspace / 'nbt_models/review-fixture'
        manifests = {side: self.render(pack, side, output / side) for side in ('before', 'after')}
        with Image.open(output / 'before/ceiling.png') as before, Image.open(output / 'after/ceiling.png') as after:
            self.assertIsNotNone(ImageChops.difference(before.convert('RGB'), after.convert('RGB')).getbbox())
        observations = [dict(view='ceiling', before='Uniform plank underside', after='Red wool visible at the floor change'),
                        dict(view='furnishings', before='Sparse attic floor', after='Placed spruce furnishings'),
                        dict(view='arrival', before='Two open levels', after='Two open levels with furniture along the upper platform')]
        partial = self.review_call('record_observation', root, merge, pack_sha256=pack['sha256'], manifests=manifests,
                                   observations=observations[1:])
        self.assertEqual(partial['missing_rooms'], ['hall'])
        after = Path(manifests['after']['path'])
        wrong = after.with_name('wrong.json')
        changed = json.loads(after.read_bytes())
        changed['quality'] = 'high'
        wrong.write_text(json.dumps(changed), encoding='utf8')
        self.review_call('record_observation', root, merge, pack_sha256=pack['sha256'],
                         manifests=dict(manifests, after=dict(path=str(wrong), sha256=sha(wrong))),
                         observations=observations, error='RENDER_CONFIG_MISMATCH')
        wrong.unlink()
        image = after.parent / 'ceiling.png'
        original = image.read_bytes()
        image.unlink()
        self.review_call('record_observation', root, merge, pack_sha256=pack['sha256'], manifests=manifests,
                         observations=observations, error='EVIDENCE_INVALID')
        image.write_bytes(original)
        issue = dict(id='ceiling_color', view='ceiling', text='The rug changes the hall ceiling', status='open')
        flagged = self.review_call('record_observation', root, merge, pack_sha256=pack['sha256'],
                                   manifests=manifests, observations=observations, issues=[issue])
        self.assertEqual(flagged['issues'][0]['state'], 'new')
        self.assertFalse(flagged['ready'])
        self.call('save_draft', **self.merge_params(root, selected), merge_sha256=merge,
                  review_sha256=flagged['sha256'], error='EVIDENCE_INVALID')
        parent = dict(self.region)
        parent['parent_id'] = parent.pop('package_id')
        self.call('reissue', **parent, run_revision=self.call('inspect')['revision'], target_id=self.left['id'],
                  target_revision=1, package=self.left)
        rug = dict(pos=[2, 5, 4], before=['minecraft:air', False], after=['minecraft:red_carpet', False])
        repaired = self.submit(self.claim(self.left['id'], revision=2), self.left, self.edits(self.left) + [rug])
        selected = self.select(repaired) + selected[1:]
        merge = self.call('plan_merge', **self.merge_params(root, selected))['merge_sha256']
        pack = self.review_call('prepare_review', root, merge, views=self.views())
        manifests['after'] = self.render(pack, 'after', output / 'repaired')
        with Image.open(output / 'before/ceiling.png') as before, Image.open(output / 'repaired/ceiling.png') as repaired_ceiling:
            self.assertIsNone(ImageChops.difference(before.convert('RGB'), repaired_ceiling.convert('RGB')).getbbox())
        observations[0]['after'] = 'Uniform plank underside restored'
        observations[1]['after'] = 'Carpet placed above the intact floor'
        recorded = self.review_call('record_observation', root, merge, pack_sha256=pack['sha256'],
                                    manifests=manifests, observations=observations, previous_review_sha256=flagged['sha256'],
                                    issues=[dict(issue, status='resolved', text='Both sides were compared after moving the rug')])
        self.assertEqual(recorded['issues'][0]['state'], 'resolved')
        self.assertTrue(recorded['ready'])
        self.assertEqual(self.call('inspect')['phase'], 'review_ready')
        draft = self.call('save_draft', **self.merge_params(root, selected), merge_sha256=merge,
                          review_sha256=recorded['sha256'], name_zh='合成旅店')
        self.assertEqual(draft['visual_review'], 'pending')
        final = self.review_call('prepare_review', root, merge, views=self.views(), target='draft')
        self.review_call('record_observation', root, merge, pack_sha256=final['sha256'], manifests=manifests,
                         observations=observations, error='EVIDENCE_INVALID')
        manifests['after'] = self.render(final, 'after', output / 'draft')
        saved_review = self.review_call('record_observation', root, merge, pack_sha256=final['sha256'],
                                        manifests=manifests, observations=observations)
        self.assertTrue(saved_review['ready'])
        self.assertFalse(saved_review['approval_created'])
        if os.environ.get('NBTCREATOR_SYNTHETIC_REVIEW_OUTPUT'):
            shutil.copytree(output, os.environ['NBTCREATOR_SYNTHETIC_REVIEW_OUTPUT'])

    def test_walkable_wrong_side(self):
        root, _, merge = self.preview()
        views = self.views()
        views[1]['use_face'] = dict(position=[3, 5, 3], face='north')
        pack = self.review_call('prepare_review', root, merge, views=views)
        self.assertTrue(pack['checks']['furnishings']['route']['passed'])
        self.assertEqual(pack['checks']['furnishings']['status'], 'wrong_side')

    def test_industrial_cross_zone_parallel_crossings(self):
        self.source = self.workspace / 'nbt_models/standalone/合成工业桥廊/v01/master/model.snbt'
        self.source.parent.mkdir(parents=True)
        model = Volume((16, 7, 12))
        for lo, hi in [((0, 0, 0), (3, 0, 11)), ((12, 0, 0), (15, 0, 11)),
                       ((4, 0, 2), (11, 0, 2)), ((4, 0, 9), (11, 0, 9))]:
            model.box(lo, hi, 'stone_bricks')
        save_master(self.source, model, set())
        self.parent_hash = sha(self.source)
        coordinates = self.source.parents[1] / 'coordinates.json'
        coordinates.write_text(json.dumps(dict(mode='standalone', openings=[], openings_policy='optional',
            require_enclosure=False, require_routes=True, start=[2.5, 1, 5.5], targets={'east': [13.5, 1, 5.5]})), encoding='utf8')
        self.call('create', mode='text_only', task='Keep a crossing available while installing a machine stop')
        self.call('bind_baseline', run_revision=1, source=str(self.source), source_sha256=self.parent_hash,
                  spaces=[dict(id='west', purpose='Approach from west', box=box((0, 1, 0), (3, 5, 11))),
                          dict(id='east', purpose='Approach from east', box=box((12, 1, 0), (15, 5, 11)))],
                  interfaces=[dict(id='crossing', box=box((4, 0, 2), (11, 0, 9)), spaces=['west', 'east'])])
        root = self.claim('root')
        self.call('heartbeat', ttl_seconds=600, **root)
        self.issue(root, *(dict(id=f'lane_{z}', write_boxes=[box((6, 1, z), (8, 2, z))]) for z in (2, 9)))
        candidates = []
        for z in (2, 9):
            area = self.claim(f'lane_{z}')
            leaf = dict(id=f'stop_{z}', write_boxes=[box((7, 1, z), (7, 2, z))],
                        components=[dict(id=f'machine_{z}', intent='Crossing machine stop', position=[7, 1, z])])
            self.issue(area, leaf)
            lease = self.claim(leaf['id'])
            self.submit(lease, leaf, [dict(pos=[8, 1, z], before=['minecraft:air', False],
                         after=['minecraft:iron_block', False])], error='WRITE_OUT_OF_SCOPE')
            candidates.append(self.submit(lease, leaf, [dict(pos=[7, y, z], before=['minecraft:air', False],
                              after=['minecraft:iron_block', False]) for y in (1, 2)]))
        blocked = self.call('plan_merge', error='ROUTE_FAILED', **self.merge_params(root, self.select(*candidates)))
        self.assertEqual(blocked['details']['conflicts'][0]['targets'][0]['name'], 'east')
        merge = self.call('plan_merge', **self.merge_params(root, self.select(candidates[0])))
        views = [dict(space='west', feet=[2.5, 1, 2.5], camera=dict(id='west_join', eye=[2.5, 2.62, 2.5], target=[7.5, 1.5, 2.5])),
                 dict(space='east', feet=[13.5, 1, 2.5], route_start=[2.5, 1, 5.5],
                      camera=dict(id='east_join', eye=[13.5, 2.62, 2.5], target=[7.5, 1.5, 2.5]))]
        pack = self.review_call('prepare_review', root, merge['merge_sha256'], views=views)
        self.assertEqual(pack['rooms'], ['east', 'west'])
        self.assertTrue(pack['checks']['east_join']['route']['passed'])
        output = self.workspace / 'nbt_models/industrial-review'
        for side in ('before', 'after'):
            self.render(pack, side, output / side)
        if os.environ.get('NBTCREATOR_SYNTHETIC_INDUSTRIAL_OUTPUT'):
            shutil.copytree(output, os.environ['NBTCREATOR_SYNTHETIC_INDUSTRIAL_OUTPUT'])


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--desktop-fixture':
        fixture = Review()
        fixture.workspace_folder = Path(sys.argv[2])
        fixture.setUp()
        root, _, merge = fixture.preview()
        pack = fixture.review_call('prepare_review', root, merge, views=fixture.views())
        output = fixture.workspace / 'nbt_models/review-fixture'
        manifests = {side: fixture.render(pack, side, output / side) for side in ('before', 'after')}
        fixture.review_call('record_observation', root, merge, pack_sha256=pack['sha256'], manifests=manifests,
                            observations=[dict(view=view, before='Fixture before', after='Fixture after') for view in pack['checks']])
        fixture.call('release', **root)
        print(json.dumps(fixture.ids))
    else:
        unittest.main()
