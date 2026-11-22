"""Actual local/HTTP libraries: immutable updates, offline use, failures and isolation."""
from copy import deepcopy
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from threading import Barrier, BrokenBarrierError, Lock, Thread
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.agents/skills/minecraft-nbt-modeler/scripts'))
import nbt_asset_libraries as libraries
from nbt_asset_libraries import dispatch, encode, digest, LibraryError
from nbt_structure_agent import dispatch as agent


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args): pass

    def do_GET(self):
        if self.path == '/redirect.json':
            self.send_response(302); self.send_header('Location', '/library.json'); self.end_headers(); return
        if self.path == '/cross-origin.json':
            self.send_response(302); self.send_header('Location', 'https://example.invalid/library.json'); self.end_headers(); return
        if self.path == '/moved.json':
            self.send_response(302); self.send_header('Location', '/nested/library.json'); self.end_headers(); return
        if self.path == '/too-big.json':
            self.send_response(200); self.send_header('Content-Length', '999999999'); self.end_headers(); return
        super().do_GET()


class Libraries(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name); self.workspace = self.root / 'workspace'; self.workspace.mkdir()
        self.pack = self.root / 'pack'; self.pack.mkdir()
        self.recipe = dict(schema_version=1, kind='nbtcreator.parametric-recipe',
                           arguments=dict(kind='pillar', name='外部方柱', size=[3, 12, 3], material='stone'))
        self.data = dict(schema_version=1, kind=libraries.FORMAT, id='test.external', name='外部构件',
                         version='1.0.0', license='CC0-1.0', assets=[])
        self.write_pack()

    def write_pack(self, value=None):
        value = self.recipe if value is None else value
        raw = encode(value); (self.pack / 'pillar.json').write_bytes(raw)
        entry = dict(id='pillar', name='外部方柱', type='parametric_recipe', path='pillar.json', bytes=len(raw), sha256=digest(raw))
        if not self.data['assets']: self.data['assets'] = [entry]
        else: self.data['assets'][0] = entry
        self.save_manifest()

    def save_manifest(self):
        raw = encode(self.data); (self.pack / 'library.json').write_bytes(raw)
        (self.pack / 'registry.json').write_bytes(encode(dict(schema_version=1, kind=libraries.REGISTRY, libraries=[dict(
            id=self.data['id'], name=self.data['name'], version=self.data['version'], path='library.json', manifest_sha256=digest(raw))])))

    def call(self, action, **request): return dispatch(self.workspace, action, request)

    def add(self, source=None): return self.call('add', source=source or str(self.pack))['source']

    def server(self, handler=QuietHandler):
        server = ThreadingHTTPServer(('127.0.0.1', 0), partial(handler, directory=str(self.pack)))
        worker = Thread(target=server.serve_forever, daemon=True); worker.start()
        self.addCleanup(server.server_close); self.addCleanup(server.shutdown)
        return f'http://127.0.0.1:{server.server_port}/'

    def assert_code(self, code, action, **request):
        with self.assertRaises(LibraryError) as caught: self.call(action, **request)
        self.assertEqual(caught.exception.code, code)

    def test_engine_compatibility_version_matches_application(self):
        package = json.loads((ROOT / 'package.json').read_text(encoding='utf8'))
        lock = json.loads((ROOT / 'package-lock.json').read_text(encoding='utf8'))
        self.assertEqual(libraries.APP_VERSION, tuple(int(part) for part in package['version'].split('.')))
        self.assertEqual(lock['version'], package['version'])
        self.assertEqual(lock['packages']['']['version'], package['version'])

    def test_local_pack_discovery_namespaces_and_compile_shared_engine(self):
        self.assertFalse((self.workspace / '.nbtcreator').exists())
        initial = self.call('list'); self.assertFalse((self.workspace / '.nbtcreator').exists())
        self.assertGreaterEqual(len(initial['items']), 54)
        listing = self.call('discover', source=str(self.pack / 'registry.json'))
        item = listing['items'][0]
        source = self.call('add', source=item['source'], manifest_sha256=item['manifest_sha256'])['source']
        self.assertEqual(source['library_id'], 'test.external')
        rows = agent(self.workspace, 'parametric_list', dict(kind='pillar'))['object_library']
        row = next(r for r in rows if r['id'] == 'test.external/pillar')
        result = agent(self.workspace, 'parametric_compile', row['arguments'])
        self.assertGreater(result['block_count'], 0)
        self.assertFalse(result['approval_created'])
        self.assertFalse((self.workspace / 'nbt_models').exists())

    def test_remote_registry_then_actual_http_assets_and_fully_offline_reads(self):
        base = self.server()
        result = self.call('discover', source=base + 'registry.json')['items'][0]
        source = self.call('add', source=result['source'], manifest_sha256=result['manifest_sha256'])['source']
        with patch.object(libraries, 'fetch', wraps=libraries.fetch) as fetch:
            rows = self.call('list')['items']
            row = next(r for r in rows if r['id'] == 'test.external/pillar')
            read = self.call('read', id=row['id'], sha256=row['sha256'])
            self.assertEqual(read['data']['arguments']['size'], [3, 12, 3])
            self.assertTrue(all(not libraries.remote(args.args[0]) for args in fetch.call_args_list))
        self.assertEqual(source['source'], base + 'library.json')

    def test_remote_files_download_concurrently_with_a_bounded_worker_count(self):
        gate = Barrier(4, timeout=5); lock = Lock(); stats = dict(active=0, peak=0)
        class ParallelHandler(QuietHandler):
            def do_GET(handler):
                if not handler.path.startswith('/asset-'): return super().do_GET()
                with lock:
                    stats['active'] += 1; stats['peak'] = max(stats['peak'], stats['active'])
                try:
                    try: gate.wait()
                    except BrokenBarrierError: handler.send_error(503); return
                    super().do_GET()
                finally:
                    with lock: stats['active'] -= 1
        self.data['assets'] = []
        for index in range(4):
            name = f'asset-{index}.json'; raw = encode(dict(self.recipe, arguments=dict(self.recipe['arguments'], name=f'并发柱{index}')))
            (self.pack / name).write_bytes(raw)
            self.data['assets'].append(dict(id=f'pillar-{index}', name=f'并发柱{index}', type='parametric_recipe', path=name, bytes=len(raw), sha256=digest(raw)))
        self.save_manifest(); source = self.add(self.server(ParallelHandler) + 'library.json')
        self.assertEqual(stats['peak'], 4)
        self.assertEqual(source['count'], 4)
        self.assertEqual(len([row for row in self.call('list')['items'] if row['library_id']=='test.external']), 4)

    def test_failure_keeps_active_snapshot_and_reports_error(self):
        source = self.add(); old = source['active']
        self.data['version'] = '1.1.0'; self.write_pack()
        (self.pack / 'pillar.json').write_bytes(b'{}')
        # Force this new version to need a new, invalid blob rather than reuse old content.
        self.data['assets'][0]['sha256'] = 'f' * 64; self.save_manifest()
        self.assert_code('HASH_MISMATCH', 'refresh', id=source['id'])
        current = self.call('list')
        self.assertEqual(current['sources'][0]['active'], old)
        self.assertEqual(current['sources'][0]['error']['code'], 'HASH_MISMATCH')
        self.assertTrue(any(r['id'] == 'test.external/pillar' for r in current['items']))

    def test_upgrade_stale_read_rollback_disable_remove_and_workspace_isolation(self):
        source = self.add(); original = next(r for r in self.call('list')['items'] if r['library_id'] == 'test.external')
        self.data['version'] = '1.1.0'; self.recipe['arguments']['material'] = 'gold_block'; self.write_pack()
        updated = self.call('refresh', id=source['id'])['source']
        self.assertNotEqual(source['active'], updated['active'])
        self.assert_code('STALE_ASSET', 'read', id=original['id'], sha256=original['sha256'])
        self.call('rollback', id=source['id'])
        self.assertEqual(self.call('read', id=original['id'], sha256=original['sha256'])['data']['arguments']['material'], 'stone')
        self.call('enable', id=source['id'], enabled=False)
        self.assert_code('NOT_FOUND', 'read', id=original['id'], sha256=original['sha256'])
        self.assertFalse(any(r['library_id'] == 'test.external' for r in dispatch(self.root, 'list', {})['items']))
        self.call('remove', id=source['id']); self.assertEqual(self.call('list')['sources'], [])

    def test_immutable_release_and_identity_downgrade_protection(self):
        source = self.add()
        self.data['name'] = '不同内容'; self.save_manifest()
        self.assert_code('VERSION_REUSED', 'refresh', id=source['id'])
        self.data['id'] = 'changed.id'; self.save_manifest()
        self.assert_code('IDENTITY_CHANGED', 'refresh', id=source['id'])
        self.data['id'] = 'test.external'; self.data['version'] = '0.9.0'; self.save_manifest()
        self.assert_code('DOWNGRADE', 'refresh', id=source['id'])

    def test_rollback_does_not_allow_a_republished_version_to_change_content(self):
        source = self.add()
        self.data['version'] = '1.1.0'; self.recipe['arguments']['material'] = 'gold_block'; self.write_pack()
        self.call('refresh', id=source['id']); self.call('rollback', id=source['id'])
        self.data['description'] = '同版本换了内容'; self.save_manifest()
        self.assert_code('VERSION_REUSED', 'refresh', id=source['id'])
        self.assertEqual(self.call('list')['sources'][0]['version'], '1.0.0')

    def test_corrupt_active_manifest_can_be_repaired_without_removing_connection(self):
        source = self.add()
        file = libraries.cache_root(self.workspace) / 'blobs' / (source['active'] + '.json')
        file.write_bytes(b'{}')
        self.assertTrue(self.call('list')['errors'])
        self.call('refresh', id=source['id'])
        self.assertEqual(self.call('list')['errors'], [])
        self.assertEqual(self.call('list')['sources'][0]['id'], source['id'])

    def test_library_removed_or_refreshed_during_read_has_a_stable_error(self):
        source = self.add(); previous = self.call('list')
        asset = next(row for row in previous['items'] if row['library_id'] == 'test.external')
        # A manifest-only release retains asset bytes, but provenance still needs
        # to bind the version that was selected rather than mix two snapshots.
        self.data['version'] = '1.1.0'; self.save_manifest(); self.call('refresh', id=source['id'])
        with patch.object(libraries, 'listing', return_value=previous):
            self.assert_code('STALE_ASSET', 'read', id=asset['id'], sha256=asset['sha256'])
        self.call('remove', id=source['id'])
        with patch.object(libraries, 'listing', return_value=previous):
            self.assert_code('NOT_FOUND', 'read', id=asset['id'], sha256=asset['sha256'])

    def test_duplicate_sources_library_ids_and_pinned_discovery(self):
        discovered = self.call('discover', source=str(self.pack / 'registry.json'))['items'][0]
        self.data['name'] = '已改变'; self.save_manifest()
        self.assert_code('HASH_MISMATCH', 'add', source=discovered['source'], manifest_sha256=discovered['manifest_sha256'])
        self.assertEqual(self.call('list')['sources'], [])
        self.add(); self.assert_code('DUPLICATE_SOURCE', 'add', source=str(self.pack))
        base = self.server(); self.assert_code('DUPLICATE_LIBRARY', 'add', source=base + 'library.json')

    def test_traversal_windows_names_credentials_and_remote_origin(self):
        for path in ('../private.json', '/absolute.json', 'a/../../private.json', 'a\\b.json', 'https://example.com/data.json', '%2e%2e/data.json', 'a//b.json', 'con.json', 'a/nul.json', 'a/data.json?token=x'):
            with self.subTest(path=path):
                self.data['assets'][0]['path'] = path; self.save_manifest()
                self.assert_code('UNSAFE_PATH', 'add', source=str(self.pack))
        for url, code in [('https://user:secret@example.com/library.json', 'UNSAFE_URL'), ('https://example.com/library.json?secret=x', 'UNSAFE_URL'), ('http://example.com/library.json', 'INSECURE_TRANSPORT')]:
            self.assert_code(code, 'discover', source=url)
        self.write_pack(); base = self.server()
        self.assert_code('UNSAFE_REDIRECT', 'discover', source=base + 'cross-origin.json')
        self.assert_code('SIZE_LIMIT', 'discover', source=base + 'too-big.json')
        self.assertEqual(self.call('discover', source=base + 'redirect.json')['items'][0]['id'], 'test.external')

    def test_schema_duplicates_dependency_cycles_unsupported_assets_and_compatibility(self):
        variants = [
            ('UNSUPPORTED_SCHEMA', dict(schema_version=2)),
            ('INCOMPATIBLE', dict(compatibility=dict(minecraft='1.21'))),
            ('INCOMPATIBLE', dict(compatibility=dict(app_min='99.0.0'))),
            ('INVALID_VERSION', dict(version='v1.0.0')),
        ]
        for code, fields in variants:
            data = dict(self.data, **fields)
            with self.assertRaises(LibraryError) as caught: libraries.manifest(encode(data))
            self.assertEqual(caught.exception.code, code)
        for code, change in [('INVALID_DEPENDENCY', dict(requires=['missing'])), ('INVALID_DEPENDENCY', dict(requires=['pillar'])), ('UNSUPPORTED_ASSET', dict(type='python'))]:
            data = deepcopy(self.data); data['assets'][0].update(change)
            with self.assertRaises(LibraryError) as caught: libraries.manifest(encode(data))
            self.assertEqual(caught.exception.code, code)
        data = deepcopy(self.data); data['assets'].append(deepcopy(data['assets'][0]))
        with self.assertRaises(LibraryError): libraries.manifest(encode(data))
        with self.assertRaises(LibraryError): libraries.decode(b'{"schema_version":1,"schema_version":2}')
        self.recipe['arguments']['execute'] = 'arbitrary.py'; self.write_pack()
        with self.assertRaises(ValueError): self.add()
        self.assertEqual(self.call('list')['sources'], [])

    def test_component_import_retains_pending_review_and_original_hash(self):
        component = dict(schema_version=1, name='外部构件', size=[1, 1, 1], anchor=[0, 0, 0], palette=['stone'], blocks=[[0, 0, 0, 0, False]])
        self.write_pack(component); self.data['assets'][0]['type'] = 'component'; self.save_manifest()
        self.add(); row = next(r for r in self.call('list')['items'] if r['library_id'] == 'test.external')
        imported = self.call('import', id=row['id'], sha256=row['sha256'])
        from nbt_components import load, listing
        item = load(self.workspace, imported['item']['id'])
        self.assertEqual(item['review_status'], 'pending_visual_review')
        self.assertFalse(imported['nbt_exported']); self.assertFalse(imported['approval_created'])
        origin = libraries.cache_root(self.workspace) / 'imports' / (item['id'] + '.json')
        self.assertEqual(json.loads(origin.read_text(encoding='utf8'))['sha256'], row['sha256'])
        self.assertEqual(listing(self.workspace)['errors'], [])

    def test_cache_tampering_is_quarantined_without_hiding_bundled_pack_and_refresh_repairs(self):
        source = self.add(); key = self.data['assets'][0]['sha256']
        (libraries.cache_root(self.workspace) / 'blobs' / (key + '.json')).write_bytes(b'{}')
        result = self.call('list')
        self.assertTrue(result['errors']); self.assertGreaterEqual(len(result['items']), 54)
        self.assertFalse(any(r['library_id'] == 'test.external' for r in result['items']))
        self.call('refresh', id=source['id'])
        self.assertEqual(self.call('list')['errors'], [])

    def test_public_cli_uses_workspace_and_same_cached_recipes(self):
        self.add()
        run = subprocess.run(['node', str(ROOT / 'scripts/cli.mjs'), '--workspace', str(self.workspace), 'asset-libraries', 'list'],
                             capture_output=True, text=True, encoding='utf8')
        self.assertEqual(run.returncode, 0, run.stderr)
        result = json.loads(run.stdout)['result']
        self.assertTrue(any(item['id'] == 'test.external/pillar' for item in result['items']))

    def test_same_origin_manifest_redirect_uses_final_directory_for_assets(self):
        nested = self.pack / 'nested'; nested.mkdir()
        for name in ('library.json', 'pillar.json'): (self.pack / name).replace(nested / name)
        source = self.add(self.server() + 'moved.json')
        self.assertEqual(source['library_id'], 'test.external')
        self.assertTrue(any(row['id'] == 'test.external/pillar' for row in self.call('list')['items']))

    def test_remote_unicode_and_space_paths_are_encoded_for_http(self):
        folder = self.pack / '中文 目录'; folder.mkdir()
        (self.pack / 'pillar.json').replace(folder / '柱 体.json')
        self.data['assets'][0]['path'] = '中文 目录/柱 体.json'; self.save_manifest()
        (self.pack / 'library.json').replace(self.pack / '资产 清单.json')
        source = self.add(self.server() + '资产 清单.json')
        self.assertEqual(source['library_id'], 'test.external')
        self.assertTrue(any(row['id'] == 'test.external/pillar' for row in self.call('list')['items']))

    def test_recipe_cannot_smuggle_a_workspace_file_reference(self):
        self.recipe['arguments']['ornament'] = dict(sample=dict(path='private.png', sha256='a' * 64))
        self.write_pack()
        with self.assertRaises(ValueError): self.add()
        self.assertEqual(self.call('list')['sources'], [])

    def test_desktop_backend_does_not_resolve_remote_urls_as_model_paths(self):
        base = self.server(); request = self.root / 'remote-request.json'
        request.write_bytes(encode(dict(source=base + 'registry.json')))
        run = subprocess.run([sys.executable, '-B', str(ROOT / '.agents/skills/minecraft-nbt-modeler/scripts/nbt_detail_control.py'),
            'asset-libraries', '--workspace', str(self.workspace), '--action', 'discover', '--request', str(request)],
            capture_output=True, text=True, encoding='utf8')
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertEqual(json.loads(run.stdout)['result']['items'][0]['source'], base + 'library.json')

    def test_corrupt_state_cannot_hide_offline_bundled_recipes_or_be_silently_overwritten(self):
        self.add(); file = libraries.cache_root(self.workspace) / 'state.json'; file.write_bytes(b'{bad')
        result = self.call('list')
        self.assertTrue(result['errors']); self.assertGreaterEqual(len(result['items']), 54)
        self.assert_code('INVALID_JSON', 'add', source=str(self.pack))
        self.assertEqual(file.read_bytes(), b'{bad')

    def test_concurrent_writer_is_refused_and_released_for_next_operation(self):
        source = self.add()
        with libraries.write_lock(self.workspace):
            self.assert_code('LOCK_BUSY', 'remove', id=source['id'])
        self.call('remove', id=source['id'])
        self.assertEqual(self.call('list')['sources'], [])

    def reference(self, item):
        return {key:item[key] for key in ('id','sha256','source_id','version','manifest_sha256')}

    def test_browse_retains_bundled_and_connected_editions_without_importing(self):
        self.data['id']='nbtcreator.modular'
        self.data['assets'][0]['id']='pillar-square';self.save_manifest()
        source=self.add()
        listing=self.call('browse')
        matching=[row for row in listing['items'] if row['id']=='nbtcreator.modular/pillar-square']
        self.assertEqual({row['source_id'] for row in matching},{'bundled',source['id']})
        for item in matching:
            read=self.call('read',**self.reference(item))
            self.assertEqual(read['asset']['source_id'],item['source_id'])
            self.assertEqual(read['data']['arguments']['size'],item['arguments']['size'])
        self.assertEqual(len(self.call('list')['items']),1)
        from nbt_components import listing as local_components
        self.assertEqual(local_components(self.workspace)['items'],[])

    def test_browse_keyword_returns_small_version_bound_candidates(self):
        query=self.call('browse',query='方柱',limit=2)
        self.assertTrue(query['offline']);self.assertTrue(query['items']);self.assertLessEqual(len(query['items']),2)
        match=query['items'][0];self.assertNotIn('arguments',match);self.assertNotIn('thumbnail',match)
        read=self.call('read',**self.reference(match));self.assertEqual(read['asset']['sha256'],match['sha256'])
        self.assertEqual(self.call('browse',query='zephyrquillnorecipe')['items'],[])

    def test_bound_preview_place_and_explicit_copy_share_current_parameters(self):
        self.add()
        item=next(row for row in self.call('browse')['items'] if row['library_id']=='test.external')
        ref=self.reference(item);before=(self.pack/'pillar.json').read_bytes()
        args=dict(size=[3,10,3],material='gold_block')
        preview=self.call('preview',**ref,arguments=args)
        self.assertEqual(preview['size'],[3,10,3]);self.assertFalse(preview['approval_created'])
        from nbt_components import listing as local_components,load
        self.assertEqual(local_components(self.workspace)['items'],[])
        ready=dict(ref,arguments=args,content_sha256=preview['content_sha256'])
        placed=self.call('place',**ready,position=[5,1,5],size=[16,24,16])
        self.assertTrue(placed['operations']);self.assertFalse(placed['model_modified'])
        self.assert_code('STALE_ASSET','place',**dict(ready,content_sha256='0'*64),position=[5,1,5],size=[16,24,16])
        copied=self.call('copy',**ready)
        self.assertFalse(copied['nbt_exported']);self.assertFalse(copied['approval_created'])
        local=load(self.workspace,copied['item']['id'])
        self.assertEqual(local['content_sha256'],preview['content_sha256'])
        self.assertEqual(local['review_status'],'pending_visual_review')
        self.assertEqual((self.pack/'pillar.json').read_bytes(),before)

    def test_bound_operations_refuse_disabled_and_replaced_source_versions(self):
        source=self.add()
        item=next(row for row in self.call('browse')['items'] if row['library_id']=='test.external')
        ref=self.reference(item)
        thumbnail=self.call('thumbnail',**ref)
        self.assertTrue(Path(thumbnail['thumbnail']).is_file())
        self.call('enable',id=source['id'],enabled=False)
        self.assert_code('NOT_FOUND','thumbnail',**ref)
        self.assert_code('NOT_FOUND','preview',**ref)
        self.call('enable',id=source['id'],enabled=True)
        self.data['version']='1.1.0';self.save_manifest();self.call('refresh',id=source['id'])
        self.assert_code('STALE_ASSET','preview',**ref)
        self.call('rollback',id=source['id'])
        self.assertEqual(self.call('read',**ref)['asset']['version'],'1.0.0')

    def test_thumbnails_are_cached_and_browse_never_uses_the_network(self):
        self.add()
        item=next(row for row in self.call('browse')['items'] if row['library_id']=='test.external')
        first=self.call('thumbnail',**self.reference(item))
        original=libraries.fetch
        def offline(source,*args,**kwargs):
            self.assertFalse(libraries.remote(source))
            return original(source,*args,**kwargs)
        with patch.object(libraries,'fetch',side_effect=offline),patch('nbt_components.thumbnail',side_effect=AssertionError('cached thumbnail was regenerated')):
            second=self.call('thumbnail',**self.reference(item))
            self.assertEqual(second['thumbnail'],first['thumbnail'])
            rows=self.call('browse')['items']
            cached=next(row for row in rows if row['library_id']=='test.external')
            self.assertEqual(cached['thumbnail'],first['thumbnail'])


if __name__ == '__main__': unittest.main(verbosity=2)
