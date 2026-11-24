from pathlib import Path
import json
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'support'))
from authoring_fixture import Inn, ROOT, box


class Delegation(Inn):
    def test_scoped_cli_permissions_and_actual_read_pages(self):
        root, region, left, right = self.delegate()
        leaf = self.invitations[left['id']]
        session_file = self.workspace / 'leaf-session.json'
        session_file.write_text(json.dumps(leaf), encoding='utf8')
        cli = ['node', str(ROOT / 'scripts/cli.mjs'), '--workspace', str(self.workspace), 'machine',
               '--package-session', str(session_file)]
        completed = subprocess.run([*cli, '--schema'], capture_output=True, encoding='utf8', check=True)
        self.assertEqual(set(json.loads(completed.stdout)['methods']), {'authoring.' + name for name in
                         ('claim', 'heartbeat', 'release', 'brief', 'context', 'block_state', 'submit')})

        def scoped(method, scope=leaf, expected=None, **params):
            reply = self.send_scoped(self.request(method, **params), scope)
            if expected:
                self.assertEqual(reply['error']['code'], expected, reply)
                return reply['error']
            self.assertTrue(reply['ok'], reply)
            return reply['data']

        claim = scoped('claim', owner='fixture desk worker')
        leaf.update(lease_token=claim['lease_token'], fence=claim['lease']['fence'])
        session_file.write_text(json.dumps(leaf), encoding='utf8')
        denied = subprocess.run([*cli, '--request', '-'], input=json.dumps(self.request('inspect', view='full')),
                                capture_output=True, encoding='utf8')
        self.assertEqual(denied.returncode, 1)
        self.assertEqual(json.loads(denied.stdout)['error']['code'], 'PACKAGE_ACCESS_DENIED')
        brief = scoped('brief')
        self.assertEqual(brief['role'], 'component')
        self.assertEqual(brief['reference_refs'], ['concept:desk'])
        self.assertNotIn('spaces', brief)
        self.assertNotIn('lease_token', json.dumps(brief))
        self.assertGreater(brief['payload_bytes'], 0)
        crop = scoped('brief', section='references', ref='concept:desk')['references'][0]['image']
        self.assertEqual(crop['crops'][0]['id'], 'desk')
        self.assertEqual(crop['pixels'], [14, 16])
        self.assertNotEqual(crop['path'], self.image.name)
        self.assertTrue((self.workspace / crop['path']).is_file())
        scoped('brief', expected='REFERENCE_OUT_OF_SCOPE', section='references', ref='concept')
        scoped('inspect', expected='PACKAGE_ACCESS_DENIED', view='full')
        scoped('context', expected='PACKAGE_ACCESS_DENIED', package_id=right['id'])
        scoped('issue', expected='PACKAGE_ACCESS_DENIED', run_revision=self.call('inspect')['revision'], packages=[left])
        scoped('save_draft', expected='PACKAGE_ACCESS_DENIED', run_revision=1, parent_source_sha256=self.parent_hash,
               candidates=[], merge_sha256='0' * 64)
        scoped('context', expected='INVALID_REQUEST', role='lead')
        self.assertEqual(scoped('block_state', state='oak_planks')['state'], 'minecraft:oak_planks')
        region_scope = dict(self.ids, **region)
        area = scoped('brief', scope=region_scope)
        self.assertEqual([row['id'] for row in area['spaces']], ['attic'])
        self.assertEqual([row['id'] for row in area['interfaces']], ['shared_floor'])
        scoped('issue', scope=region_scope, expected='SCOPE_EXCEEDED', run_revision=self.call('inspect')['revision'],
               packages=[dict(id='ground', write_boxes=[box((1, 1, 1), (1, 1, 1))])])
        page1, page2 = scoped('context'), scoped('context', page=1)
        self.assertEqual(page1['read_sha256'], page2['read_sha256'])
        self.assertIn('minecraft:oak_stairs', page1['selection']['palette'])
        params = dict(read_sha256=page1['read_sha256'], patches=self.edits(left),
                      components=[dict(id=row['id'], status='complete') for row in left['components']])
        missing = scoped('submit', expected='READ_PAGE_REQUIRED', page_receipts=[page1['page_receipt']], **params)
        self.assertEqual(missing['details']['pages'], [1])
        forged = dict(page2['page_receipt'], page=0)
        scoped('submit', expected='READ_PAGE_INVALID', page_receipts=[forged], **params)
        request = self.request('submit', page_receipts=[page1['page_receipt'], page2['page_receipt']], **params)
        submitted = self.send_scoped(request, leaf)
        self.assertTrue(submitted['ok'], submitted)
        self.assertEqual(self.send_scoped(request, leaf), submitted)
        report = scoped('report_region', scope=region_scope, summary='Attic writing area complete', candidates=self.select(submitted['data']))
        feedback = self.call('brief', **root, section='feedback')
        self.assertEqual(feedback['children'][0]['report']['sha256'], report['sha256'])
        refit = scoped('reissue', scope=region_scope, run_revision=self.call('inspect')['revision'],
                       target_id=left['id'], target_revision=1, package=left)
        self.assertEqual(refit['packages'][0]['revision'], 2)
        scoped('context', expected='REVISION_CONFLICT')
        self.call('plan_merge', error='CANDIDATE_CHANGED', **self.merge_params(root, self.select(submitted['data'])))

    def send_scoped(self, request, session):
        from nbt_agent.machine import dispatch
        return dispatch(self.workspace, request, session=session)

    def test_three_levels_multi_component_with_fences(self):
        _, region, left, right = self.delegate(gap=2)
        self.issue(region, dict(left, id='collision'), error='WRITE_SCOPE_OVERLAP')
        with patch('nbt_agent.protocol.time.time', return_value=100):
            first = self.claim(left['id'])
        with patch('nbt_agent.protocol.time.time', return_value=161):
            self.call('context', error='LEASE_EXPIRED', **first)
            worker = self.claim(left['id'])
        with patch('nbt_agent.protocol.time.time', return_value=162):
            self.assertGreater(worker['fence'], first['fence'])
            self.call('context', error='LEASE_NOT_OWNER', **first)
            self.call('context', error='LEASE_FENCE_CONFLICT', **dict(worker, fence=first['fence']))
            self.issue(worker, dict(left, id='fourth'), error='PACKAGE_DEPTH')
            self.call('plan_merge', error='LEAD_REQUIRED', **self.merge_params(worker, []))
            bad = [dict(pos=right['components'][0]['position'], before=['minecraft:air', False],
                        after=['minecraft:stone', False])]
            self.submit(worker, left, bad, error='WRITE_OUT_OF_SCOPE')
            context = self.call('context', **worker)
            self.assertIn(1, {run[-1] for run in context['selection']['runs']})
            self.assertEqual(self.submit(worker, left)['changed_positions'], 4)
        packages = self.call('inspect', view='full')['packages']
        self.assertEqual([package['depth'] for package in packages], [3, 3, 1, 2])
        self.assertTrue(all('token' not in (package.get('lease') or {}) for package in packages))


if __name__ == '__main__':
    unittest.main()
