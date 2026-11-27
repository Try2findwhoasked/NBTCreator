"""Synthetic two-level inn and protocol calls used by authoring regressions."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from uuid import uuid4

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
ENGINE = Path(os.environ.get('NBTCREATOR_TEST_ENGINE_SCRIPTS') or ROOT / '.agents/skills/minecraft-nbt-modeler/scripts')
sys.path.insert(0, str(ENGINE))

from nbt_agent.machine import dispatch
from nbt_assembly import Volume
from nbt_project import batches
from nbt_refine import save_master


def box(lo, hi):
    return dict(lo=list(lo), hi=list(hi))


class Inn(unittest.TestCase):
    cli = False
    workspace_folder = None

    def setUp(self):
        if self.workspace_folder is None:
            temporary = tempfile.TemporaryDirectory()
            self.addCleanup(temporary.cleanup)
            self.workspace_folder = Path(temporary.name)
        self.workspace = self.workspace_folder.resolve()
        self.source = self.workspace / 'nbt_models/standalone/合成旅店/v01/master/model.snbt'
        self.source.parent.mkdir(parents=True)
        self.model = Volume((16, 10, 12))
        self.model.box((0, 0, 0), (15, 0, 11), 'oak_planks')
        self.model.box((0, 4, 0), (15, 4, 11), 'spruce_planks')
        self.model.put((3, 5, 3), 'oak_planks')
        self.model.put((0, 5, 0), 'oak_planks')
        self.model.put((4, 5, 4), 'oak_stairs')
        save_master(self.source, self.model, {(3, 5, 3)})
        (self.source.parents[1] / 'coordinates.json').write_text(json.dumps(dict(
            mode='standalone', openings=[], openings_policy='optional', require_enclosure=False,
            start=[2.5, 1, 2.5], targets={'hall': [10.5, 1, 8.5]},
            route_legs=[dict(name='attic', start=[2.5, 5, 7.5], targets={'landing': [10.5, 5, 7.5]})])), encoding='utf8')
        self.parent_hash = batches.sha(self.source)
        self.image = self.workspace / 'concept.png'
        Image.new('RGB', (32, 24), 'purple').save(self.image)
        self.pack = dict(images=[dict(id='concept', path=self.image.name, sha256=batches.sha(self.image), kind='concept',
                                      role='attic arrangement', source={'kind': 'synthetic'},
                                      crops=[dict(id='desk', pixels=[4, 4, 18, 20], role='desk joinery')])],
                         notes=[dict(image_id='concept', crop_id='desk', kind='correction', location='attic',
                                     text='The cabinet belongs beside the desk.', basis='Fixture dimensions')])
        batch = batches.dispatch(self.workspace, 'create', {'name': '合成旅店'})
        batch = batches.dispatch(self.workspace, 'run', dict(id=batch['id'], revision=batch['revision'], stage='authoring'))
        self.ids = dict(batch_id=batch['id'], run_id=batch['runs'][0]['id'])

    def request(self, method, **params):
        return dict(protocol_version=1, method='authoring.' + method, request_id=uuid4().hex,
                    params=dict(self.ids, **params))

    def send(self, request):
        if not self.cli:
            return dispatch(self.workspace, request)
        completed = subprocess.run(['node', str(ROOT / 'scripts/cli.mjs'), '--workspace', str(self.workspace),
                                    'machine', '--request', '-'], cwd=ROOT, text=True, encoding='utf8',
                                   input=json.dumps(request), capture_output=True)
        self.assertTrue(completed.stdout, completed.stderr)
        return json.loads(completed.stdout)

    def call(self, method, error=None, **params):
        reply = self.send(self.request(method, **params))
        if error:
            self.assertFalse(reply['ok'], reply)
            self.assertEqual(reply['error']['code'], error, reply)
            return reply['error']
        self.assertTrue(reply['ok'], reply)
        return reply['data']

    def baseline(self, *, protected=None):
        self.call('create', mode='existing_draft', task='Furnish the synthetic inn')
        refs = self.call('bind_reference', run_revision=1, pack=self.pack)
        spaces = [dict(id='hall', purpose='Approach the tables', box=box((1, 1, 1), (14, 3, 10))),
                  dict(id='attic', purpose='Read and store belongings', box=box((1, 5, 1), (14, 8, 10)))]
        return self.call('bind_baseline', run_revision=refs['revision'], source=str(self.source),
                         source_sha256=self.parent_hash, spaces=spaces, protected_boxes=protected or [],
                         interfaces=[dict(id='shared_floor', spaces=['hall', 'attic'], box=box((1, 4, 1), (14, 4, 10)))])

    def claim(self, key, owner='worker', revision=1):
        result = self.call('claim', package_id=key, package_revision=revision, owner=owner, ttl_seconds=60)
        return dict(package_id=key, package_revision=revision, lease_token=result['lease_token'], fence=result['lease']['fence'])

    def issue(self, parent, *specs, error=None):
        params = dict(parent, parent_id=parent['package_id'])
        del params['package_id']
        return self.call('issue', error=error, run_revision=self.call('inspect')['revision'], packages=list(specs), **params)

    def delegate(self, *, protected=None, gap=4, floor_edit=False):
        self.baseline(protected=protected)
        root = self.claim('root', 'lead')
        floor = 4 if floor_edit else 5
        self.issue(root, dict(id='upper', write_boxes=[box((1, floor, 1), (14, 8, 10))],
                              reference_refs=['concept'], interfaces=['shared_floor'], goal='Furnish the attic'))
        region = self.claim('upper', 'region')
        left = dict(id='desk_batch', write_boxes=[box((2, floor, 2), (5, 6, 4))],
                    read_boxes=[box((1, floor - 1, 1), (6, 7, 5)), box((3, floor - 1, 4), (5, 6, 6))],
                    reference_refs=['concept:desk'], interfaces=['shared_floor'], components=[
            dict(id=key, intent=purpose, position=[x, 5, 3], required=True) for key, purpose, x in
            [('desk', 'Writing', 3), ('chair', 'Sitting', 4), ('lantern', 'Lighting', 5), ('shelf', 'Storage', 2)]])
        right = dict(id='chest_batch', write_boxes=[box((5 + gap, 5, 2), (12, 6, 4))], components=[
            dict(id='chest', intent='Storage', position=[5 + gap, 5, 3], required=True),
            dict(id='bench', intent='Seating', position=[12, 5, 3], required=True)])
        self.invitations = {row['package_id']: row for row in self.issue(region, left, right)['invitations']}
        return root, region, left, right

    def submit(self, lease, spec, edits=None, error=None):
        if edits is None:
            edits = self.edits(spec)
        context = self.call('context', **lease)
        pages = [context['page_receipt']] + [self.call('context', page=page, **lease)['page_receipt']
                                             for page in range(1, context['pages'])]
        return self.call('submit', error=error, read_sha256=context['read_sha256'], patches=edits,
                         page_receipts=pages,
                         components=[dict(id=row['id'], status='complete') for row in spec['components']], **lease)

    def edits(self, spec):
        return [dict(pos=row['position'], before=['minecraft:oak_planks', True] if row['id'] == 'desk'
                     else ['minecraft:air', False], after=['minecraft:spruce_planks', False]) for row in spec['components']]

    def select(self, *receipts):
        return [dict(package_id=receipt['package_id'], sha256=receipt['candidate_sha256']) for receipt in receipts]

    def merge_params(self, root, selected):
        return dict(root, run_revision=self.call('inspect')['revision'], parent_source_sha256=self.parent_hash, candidates=selected)
