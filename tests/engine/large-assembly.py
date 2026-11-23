"""Synthetic multi-part source integrity and global-coordinate regressions."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_assembly import Volume
from nbt_snbt import save_snbt
from nbt_composition.large_assembly import AssemblyVolume, read_assembly, save_assembly, verify_assembly_binding


class LargeAssembly(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.parts = self.root / 'parts'
        self.parts.mkdir()
        self.manifest = self.root / 'assembly.json'

    def part(self, name, position, material='stone', wall=False, offset=(0, 0, 0)):
        model = Volume((4, 4, 4))
        model.put(position, material)
        path = self.parts / (name + '.snbt')
        save_snbt(path, model, {position} if wall else set())
        return dict(file='parts/' + path.name, offset=list(offset), size=list(model.size),
                    sha256=hashlib.sha256(path.read_bytes()).hexdigest())

    def write(self, parts, size=(300, 384, 300)):
        self.manifest.write_text(json.dumps(dict(format='nbtcreator-assembly', schema_version=1,
                                                 size=list(size), partitions=parts)), encoding='utf8')

    def test_sparse_global_positions_and_explicit_walls_roundtrip(self):
        self.write([self.part('a', (3, 3, 3), wall=True, offset=(0, 290, 0)),
                    self.part('b', (1, 1, 1), material='gold_block', offset=(298, 294, 298))])
        model, walls = read_assembly(self.manifest)
        self.assertEqual(model.size, (300, 384, 300))
        self.assertEqual(model.get((3, 293, 3)), 'minecraft:stone')
        self.assertEqual(model.get((299, 295, 299)), 'minecraft:gold_block')
        self.assertEqual(walls, {(3, 293, 3)})
        self.assertEqual(len(model.blocks), 2)

    def test_negative_offset_is_allowed_only_for_in_bounds_voxels(self):
        self.write([self.part('a', (1, 1, 1), offset=(-1, -1, -1))])
        self.assertEqual(read_assembly(self.manifest)[0].get((0, 0, 0)), 'minecraft:stone')
        self.write([self.part('b', (0, 0, 0), offset=(-1, 0, 0))])
        with self.assertRaisesRegex(ValueError, '越界'): read_assembly(self.manifest)

    def test_overlapping_voxels_are_rejected_even_if_values_match(self):
        self.write([self.part('a', (1, 1, 1)), self.part('b', (1, 1, 1))])
        with self.assertRaisesRegex(ValueError, '重叠'): read_assembly(self.manifest)

    def test_tampering_and_path_escape_are_rejected(self):
        part = self.part('a', (1, 1, 1)); self.write([part])
        (self.parts / 'a.snbt').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, '哈希'): read_assembly(self.manifest)
        part['file'] = '../outside.snbt'; self.write([part])
        with self.assertRaisesRegex(ValueError, '路径'): read_assembly(self.manifest)

    def test_partition_mutation_during_read_is_rejected(self):
        part = self.part('a', (1, 1, 1)); self.write([part])
        from nbt_snbt import read_snbt
        def mutate(path):
            result = read_snbt(path)
            path.write_bytes(path.read_bytes() + b' ')
            return result
        with patch('nbt_composition.large_assembly.read_snbt', side_effect=mutate):
            with self.assertRaisesRegex(ValueError, '变化'): read_assembly(self.manifest)

    def test_bound_model_detects_later_partition_or_manifest_mutation(self):
        part = self.part('a', (1, 1, 1)); self.write([part])
        model, _ = read_assembly(self.manifest)
        self.assertTrue(verify_assembly_binding(model))
        (self.parts / 'a.snbt').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, '变化'): verify_assembly_binding(model)
        self.write([part], size=(300, 383, 300))
        with self.assertRaisesRegex(ValueError, '变化'): verify_assembly_binding(model)

    def test_undeclared_wall_layer_and_invalid_dimensions_are_rejected(self):
        part = self.part('a', (1, 1, 1)); self.write([part])
        from nbt_snbt import read_snbt
        def missing_wall(path):
            model, walls = read_snbt(path)
            model._wall_mask_declared = False
            return model, walls
        with patch('nbt_composition.large_assembly.read_snbt', side_effect=missing_wall):
            with self.assertRaisesRegex(ValueError, '显式墙层'): read_assembly(self.manifest)
        self.write([part], size=(True, 384, 300))
        with self.assertRaisesRegex(ValueError, '尺寸'): read_assembly(self.manifest)

    def test_symlinked_partition_is_rejected(self):
        part = self.part('a', (1, 1, 1)); link = self.parts / 'link.snbt'
        try:
            link.symlink_to(self.parts / 'a.snbt')
        except OSError as error:
            self.skipTest('creating symlinks is not available: ' + str(error))
        part['file'] = 'parts/link.snbt'; self.write([part])
        with self.assertRaisesRegex(ValueError, '符号链接'): read_assembly(self.manifest)

    def test_symlink_check_applies_to_any_partition_component(self):
        part = self.part('a', (1, 1, 1)); self.write([part])
        original = Path.is_symlink
        with patch.object(Path, 'is_symlink', lambda path: path.name == 'parts' or original(path)):
            with self.assertRaisesRegex(ValueError, '符号链接'): read_assembly(self.manifest)
        if hasattr(Path,'is_junction'):
            original_junction=Path.is_junction
            with patch.object(Path,'is_junction',lambda path:path.name=='parts' or original_junction(path)):
                with self.assertRaisesRegex(ValueError,'联接'):read_assembly(self.manifest)

    def test_new_partitioned_source_roundtrips_and_never_overwrites(self):
        model = AssemblyVolume((300, 384, 300))
        model.put((3, 293, 3), 'stone'); model.put((299, 295, 299), 'gold_block')
        walls = {(3, 293, 3)}
        specs = [dict(offset=[0, 0, 0], size=[294, 294, 294]),
                 dict(offset=[294, 294, 294], size=[6, 90, 6])]
        target = self.root / 'new'
        result = save_assembly(target, model, walls, specs)
        loaded, loaded_walls = read_assembly(Path(result['source']))
        self.assertEqual(loaded.blocks, model.blocks); self.assertEqual(loaded_walls, walls)
        before = Path(result['source']).read_bytes()
        with self.assertRaisesRegex(ValueError, '存在'): save_assembly(target, model, walls, specs)
        self.assertEqual(Path(result['source']).read_bytes(), before)

    def test_missing_or_ambiguous_partition_refuses_publication(self):
        model = AssemblyVolume((300, 384, 300)); model.put((1, 1, 1), 'stone')
        for name, specs in [('missing', [dict(offset=[10, 0, 0], size=[4, 4, 4])]),
                            ('ambiguous', [dict(offset=[0, 0, 0], size=[4, 4, 4]), dict(offset=[1, 0, 0], size=[4, 4, 4])])]:
            with self.subTest(name=name):
                target = self.root / name
                with self.assertRaisesRegex(ValueError, '分区'): save_assembly(target, model, set(), specs)
                self.assertFalse(target.exists())

    def test_interrupted_manifest_publish_never_exposes_a_readable_source(self):
        model = AssemblyVolume((8, 8, 8)); model.put((1, 1, 1), 'stone')
        target = self.root / 'interrupted'
        with patch('nbt_composition.large_assembly.os.link', side_effect=OSError('synthetic interruption')):
            with self.assertRaisesRegex(OSError, 'interruption'):
                save_assembly(target, model, set(), [dict(offset=[0, 0, 0], size=[8, 8, 8])])
        self.assertFalse((target / 'assembly.json').exists())
        self.assertEqual(model.get((1, 1, 1)), 'minecraft:stone')

    def test_render_snapshot_binds_all_partitions_and_rejects_later_mutation(self):
        from nbt_task import inspect_source, preview_source_matches, publish_render_manifest
        model = AssemblyVolume((300, 384, 300)); model.put((299, 295, 299), 'stone')
        result = save_assembly(self.root / 'source', model, {(299, 295, 299)},
                               [dict(offset=[294, 294, 294], size=[6, 90, 6])])
        source = Path(result['source']); snapshot = inspect_source(source)
        self.assertEqual(snapshot['source_kind'], 'assembly')
        self.assertEqual(snapshot['assembly_partitions'][0]['sha256'], json.loads(source.read_text())['partitions'][0]['sha256'])
        self.assertTrue(preview_source_matches(source, snapshot))
        self.assertFalse(preview_source_matches(source, {k: v for k, v in snapshot.items() if k != 'assembly_partitions'}))
        output = self.root / 'render'; output.mkdir()
        manifest = output / 'render_manifest.json'
        manifest.write_text(json.dumps(dict(status='awaiting_input_check', images=[], duration_ms=0)), encoding='utf8')
        part = source.parent / snapshot['assembly_partitions'][0]['file']
        part.write_bytes(part.read_bytes() + b' ')
        self.assertFalse(preview_source_matches(source, snapshot))
        with self.assertRaisesRegex(ValueError, 'changed'):
            publish_render_manifest(output, source, snapshot)
        self.assertEqual(json.loads(manifest.read_text(encoding='utf8'))['status'], 'failed')

    def test_history_archives_all_partitions_and_restores_after_source_changes(self):
        from nbt_project.history import History
        model = AssemblyVolume((300, 384, 300)); model.put((299, 295, 299), 'stone')
        result = save_assembly(self.root / 'nbt_models/standalone/large/v01/master', model, {(299, 295, 299)},
                               [dict(offset=[294, 294, 294], size=[6, 90, 6])])
        source = Path(result['source']); history = History(self.root)
        recorded = history.record(dict(source=str(source), message='组装主稿', set_current=True))
        identifier = recorded['version']['id']
        self.assertEqual(recorded['version']['size'], [300, 384, 300])
        self.assertTrue(history.get(identifier)['version']['source_matches'])
        part = source.parent / json.loads(source.read_text(encoding='utf8'))['partitions'][0]['file']
        part.write_bytes(part.read_bytes() + b' ')
        self.assertFalse(history.list(str(source))['versions'][0]['source_matches'])
        with self.assertRaisesRegex(ValueError, '变化'): history.current(identifier)
        restored = history.derive(identifier)
        restored_model, restored_walls = read_assembly(restored['source'])
        self.assertEqual(restored_model.blocks, model.blocks)
        self.assertEqual(restored_walls, {(299, 295, 299)})
        self.assertEqual(restored['parent'], identifier)
        self.assertEqual(part.read_bytes()[-1:], b' ')
        sha=json.loads(source.read_text(encoding='utf8'))['partitions'][0]['sha256']
        part.write_bytes(history.object_file(sha).read_bytes())
        self.assertTrue(history.get(identifier)['version']['source_matches'])
        moved=part.with_name('moved.snbt');part.rename(moved)
        self.assertFalse(history.get(identifier)['version']['source_matches'])
        moved.rename(part);part.unlink()
        self.assertFalse(history.get(identifier)['version']['source_matches'])
        recovered=history.derive(identifier)
        self.assertEqual(read_assembly(recovered['source'])[0].blocks,model.blocks)

    def test_history_refuses_partition_changed_during_archiving(self):
        from nbt_project.history import History
        model = AssemblyVolume((300, 384, 300)); model.put((299, 295, 299), 'stone')
        result = save_assembly(self.root / 'nbt_models/standalone/race/v01/master', model, set(),
                               [dict(offset=[294, 294, 294], size=[6, 90, 6])])
        source = Path(result['source']); history = History(self.root); archive = history.archive
        def mutate_after_archive(file):
            item = archive(file)
            if Path(file).name == 'part-0000.snbt':
                Path(file).write_bytes(Path(file).read_bytes() + b' ')
            return item
        with patch.object(history, 'archive', side_effect=mutate_after_archive):
            with self.assertRaisesRegex(ValueError, '变化'): history.record(dict(source=str(source)))
        self.assertEqual(history.list()['versions'], [])

    def test_cli_imports_selected_parts_registers_history_and_refuses_overwrite(self):
        first = self.part('a', (3, 3, 3), wall=True, offset=(0, 290, 0))
        second = self.part('b', (1, 1, 1), material='gold_block', offset=(298, 294, 298))
        request = dict(size=[300, 384, 300], output='nbt_models/standalone/imported/v01/master',
                       partitions=[dict(source=item['file'], sha256=item['sha256'], offset=item['offset']) for item in (first, second)])
        file = self.root / 'request.json'; file.write_text(json.dumps(request), encoding='utf8')
        command = ['node', str(ROOT / 'scripts/cli.mjs'), '--workspace', str(self.root), 'assembly', 'import', '--request', str(file)]
        run = subprocess.run(command, capture_output=True, text=True, encoding='utf8', timeout=45)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        result = json.loads(run.stdout); source = Path(result['source'])
        model, walls = read_assembly(source)
        self.assertEqual(model.size, (300, 384, 300)); self.assertEqual(len(model.blocks), 2)
        self.assertEqual(walls, {(3, 293, 3)}); self.assertFalse(result['history_pending'])
        from nbt_project.history import History
        self.assertTrue(History(self.root).list(str(source))['versions'][0]['source_matches'])
        from nbt_detail_control import catalog, inspect_source, source_snapshot, default_settings
        listing = catalog(self.root, index_only=True)['models']
        selected = [item for item in listing if Path(item['source']) == source]
        self.assertEqual(len(selected), 1); self.assertTrue(selected[0]['unverified'])
        self.assertFalse(any(Path(item['source']).name.startswith('part-') for item in listing))
        information = inspect_source(source)
        self.assertEqual(information['size'], [300,384,300]); self.assertFalse(information['editing_ready'])
        preview = source_snapshot(dict(source=str(source),settings=default_settings()), self.root/'read-only')
        self.assertTrue(preview['read_only_view'])
        self.assertEqual(json.loads(Path(preview['snapshot']).read_text(encoding='utf8'))['source_kind'], 'assembly')
        unchanged = source.read_bytes()
        repeat = subprocess.run(command, capture_output=True, text=True, encoding='utf8', timeout=45)
        self.assertNotEqual(repeat.returncode, 0); self.assertEqual(source.read_bytes(), unchanged)
        request['output'] = 'nbt_models/standalone/imported/v02/master'; request['partitions'][0]['sha256'] = '0' * 64
        file.write_text(json.dumps(request), encoding='utf8')
        stale = subprocess.run(command, capture_output=True, text=True, encoding='utf8', timeout=45)
        self.assertNotEqual(stale.returncode, 0); self.assertFalse((self.root / request['output'] / 'assembly.json').exists())

    def test_full_catalog_rechecks_parts_instead_of_reusing_manifest_only_cache(self):
        from nbt_detail_control import catalog
        model=AssemblyVolume((300,384,300));model.put((299,295,299),'stone')
        result=save_assembly(self.root/'nbt_models/standalone/catalog/v01/master',model,set(),
                             [dict(offset=[294,294,294],size=[6,90,6])])
        source=Path(result['source'])
        first=catalog(self.root)
        self.assertEqual(len([row for row in first['models'] if Path(row['source'])==source]),1)
        part=source.parent/json.loads(source.read_text())['partitions'][0]['file']
        part.write_bytes(part.read_bytes()+b' ')
        second=catalog(self.root)
        self.assertFalse(any(Path(row['source'])==source and not row['unreadable'] for row in second['models']))
        self.assertTrue(any('哈希' in item['reason'] for item in second['errors']))

    def test_frozen_workspace_imports_overlapping_bounds_without_losing_distinct_voxels(self):
        from nbt_exposure import apply
        first = self.part('a', (0, 0, 0), wall=True)
        second = self.part('b', (1, 1, 1), material='gold_block')
        request = dict(size=[300, 384, 300], output='nbt_models/standalone/frozen/v01/master',
                       partitions=[dict(source=item['file'], sha256=item['sha256'], offset=item['offset']) for item in (first, second)])
        request_path = self.root / 'request.json'; request_path.write_text(json.dumps(request), encoding='utf8')
        apply(self.root)
        command = [sys.executable, str(self.root / '.agents/skills/nbtcreator-workspace/nbt.py'),
                   'assembly', 'import', '--request', str(request_path)]
        run = subprocess.run(command, cwd=self.root, capture_output=True, text=True, encoding='utf8', timeout=60)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        result = json.loads(run.stdout); model, walls = read_assembly(result['source'])
        self.assertEqual(len(model.blocks), 2); self.assertEqual(walls, {(0, 0, 0)})
        self.assertFalse(result['history_pending'])

    def test_cli_import_rejects_paths_outside_the_workspace(self):
        from nbt_composition.large_assembly import import_assembly
        source = self.part('a', (0, 0, 0))
        request = dict(size=[300, 384, 300], output='nbt_models/standalone/test/v01/master',
                       partitions=[dict(source='../outside.snbt', sha256=source['sha256'], offset=[0, 0, 0])])
        with self.assertRaisesRegex(ValueError, '路径|工作区'): import_assembly(self.root, request)
        self.assertFalse((self.root / request['output']).exists())
        with self.assertRaisesRegex(ValueError, '源码目录'): import_assembly(ROOT, request)

    def test_model_cli_patches_global_coordinates_and_keeps_source_unchanged(self):
        model = AssemblyVolume((300, 384, 300)); model.put((299, 295, 299), 'stone')
        result = save_assembly(self.root / 'nbt_models/standalone/large/v01/master', model, {(299, 295, 299)},
                               [dict(offset=[294, 294, 294], size=[6, 90, 6])])
        source = Path(result['source']); original = source.read_bytes()
        request = dict(source=str(source), source_sha256=result['source_sha256'], positions=[[299,295,299]],
                       actions=[dict(method='patch', changes=[dict(pos=[299,295,299], before=['minecraft:stone',True],
                                                                    after=['minecraft:gold_block',False])])])
        file = self.root / 'model-request.json'; file.write_text(json.dumps(request), encoding='utf8')
        run = subprocess.run(['node', str(ROOT/'scripts/cli.mjs'), '--workspace', str(self.root),
                              'model', '--request', str(file)], capture_output=True, text=True, encoding='utf8', timeout=45)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        response = json.loads(run.stdout)
        self.assertEqual(response['result']['model']['samples'][0]['value'], ['minecraft:gold_block',False])
        self.assertEqual(source.read_bytes(), original)
        self.assertEqual(read_assembly(source)[0].get((299,295,299)), 'minecraft:stone')

    def test_working_model_rejects_partition_mutation_after_open(self):
        from nbt_composition.working_model import WorkingModel, ModelConflict
        model = AssemblyVolume((300,384,300)); model.put((299,295,299), 'stone')
        result = save_assembly(self.root / 'nbt_models/standalone/large/v01/master', model, set(),
                               [dict(offset=[294,294,294], size=[6,90,6])])
        source = Path(result['source'])
        working = WorkingModel.open(self.root, source, source_sha256=result['source_sha256'])
        part = source.parent / json.loads(source.read_text(encoding='utf8'))['partitions'][0]['file']
        part.write_bytes(part.read_bytes()+b' ')
        with self.assertRaisesRegex(ModelConflict, 'STALE_SOURCE'):
            working.patch([dict(pos=[299,295,299],before=['minecraft:stone',False],after=['minecraft:gold_block',False])])

    def test_working_model_saves_and_reopens_assembly_with_overlapping_part_bounds(self):
        from nbt_composition.working_model import WorkingModel, verify_version
        from nbt_composition.large_assembly import import_assembly
        first = self.part('a', (0,0,0), wall=True)
        second = self.part('b', (1,1,1), material='gold_block')
        request = dict(size=[300,384,300], output='nbt_models/standalone/large/v01/master',
                       partitions=[dict(source=row['file'], sha256=row['sha256'], offset=row['offset']) for row in (first,second)])
        source = import_assembly(self.root, request)
        original = Path(source['source']).read_bytes()
        working = WorkingModel.open(self.root, source['source'], source_sha256=source['source_sha256'])
        working.patch([dict(pos=[1,1,1],before=['minecraft:gold_block',False],after=['minecraft:stone',True]),
                       dict(pos=[2,2,2],before=['minecraft:air',False],after=['minecraft:quartz_block',False])])
        saved = working.save_draft(name_zh='测试组装')
        self.assertFalse(saved['history_pending'], saved)
        self.assertFalse(saved['nbt_exported'])
        self.assertEqual(Path(source['source']).read_bytes(), original)
        manifest = verify_version(saved['output']); self.assertEqual(manifest['master'], 'master/assembly.json')
        with patch('nbt_composition.large_assembly.read_assembly',side_effect=AssertionError('must not decode all parts')):
            self.assertEqual(verify_version(saved['output'])['revision'],manifest['revision'])
        reopened = WorkingModel.open(self.root, saved['source'], source_sha256=saved['source_sha256'])
        self.assertEqual(reopened.model.get((1,1,1)), 'minecraft:stone')
        self.assertEqual(reopened.model.get((2,2,2)), 'minecraft:quartz_block')
        self.assertEqual(reopened.walls, {(0,0,0),(1,1,1)})
        self.assertTrue(Path(saved['source']).is_file())
        self.assertFalse(list(Path(saved['output']).rglob('*.nbt')))
        from nbt_project.history import History
        history = History(self.root)
        identifier = saved['history']['version']['id']
        derived = history.derive(identifier)
        restored = WorkingModel.open(self.root, derived['source'], source_sha256=derived['version']['source_sha256'])
        self.assertEqual(restored.model.blocks, reopened.model.blocks)
        self.assertEqual(restored.walls, reopened.walls)

    def test_save_preserves_partition_extras_and_candidate_preview(self):
        from nbt_composition.working_model import WorkingModel
        from nbt_composition.large_assembly import import_assembly
        from nbt_snbt import N, root
        part_model = Volume((4,4,4)); part_model.put((1,1,1),'stone')
        part_model._snbt_extras = {'custom':N.Compound({'name':N.String('retained')})}
        source = self.parts/'custom.snbt'; save_snbt(source,part_model,{(1,1,1)})
        request = dict(size=[300,384,300], output='nbt_models/standalone/custom/v01/master',
                       partitions=[dict(source='parts/custom.snbt',sha256=hashlib.sha256(source.read_bytes()).hexdigest(),offset=[0,0,0])])
        imported = import_assembly(self.root, request)
        working = WorkingModel.open(self.root, imported['source'], source_sha256=imported['source_sha256'])
        working.patch([dict(pos=[1,1,1],before=['minecraft:stone',True],after=['minecraft:gold_block',True])])
        preview = working.preview(self.root/'preview', [dict(id='test',eye=[8,8,8],target=[1,1,1])])
        snapshot = json.loads(Path(preview['snapshot']).read_text(encoding='utf8'))
        self.assertEqual(snapshot['source_kind'], 'assembly'); self.assertEqual(snapshot['wall_positions'], [[1,1,1]])
        saved = working.save_draft(name_zh='元数据测试')
        manifest = json.loads(Path(saved['source']).read_text(encoding='utf8'))
        part = Path(saved['source']).parent/manifest['partitions'][0]['file']
        self.assertEqual(str(root(part)['custom']['name']), 'retained')
        self.assertEqual(read_assembly(saved['source'])[0].get((1,1,1)), 'minecraft:gold_block')

    def test_changed_assembly_during_candidate_save_is_not_published(self):
        from nbt_composition.working_model import WorkingModel, ModelConflict
        from nbt_snbt import save_snbt as real_save_snbt
        model = AssemblyVolume((300,384,300)); model.put((299,295,299), 'stone')
        imported = save_assembly(self.root/'nbt_models/standalone/race/v01/master', model, set(),
                                 [dict(offset=[294,294,294],size=[6,90,6])])
        source = Path(imported['source']); working = WorkingModel.open(self.root,source,source_sha256=imported['source_sha256'])
        part = source.parent/json.loads(source.read_text(encoding='utf8'))['partitions'][0]['file']
        def tamper(*args, **kwargs):
            result = real_save_snbt(*args, **kwargs)
            part.write_bytes(part.read_bytes()+b' ')
            return result
        with patch('nbt_composition.large_assembly.save_snbt',side_effect=tamper):
            with self.assertRaisesRegex(ModelConflict,'STALE_SOURCE'):working.save_draft(name_zh='并发测试')
        self.assertFalse(list(source.parents[2].glob('v_model_*')))

    def test_managed_version_integrity_rejects_modified_partition_without_full_decode(self):
        from nbt_composition.working_model import WorkingModel,verify_version
        model=AssemblyVolume((300,384,300));model.put((299,295,299),'stone')
        source=save_assembly(self.root/'nbt_models/standalone/version/v01/master',model,set(),
                             [dict(offset=[294,294,294],size=[6,90,6])])
        saved=WorkingModel.open(self.root,source['source'],source_sha256=source['source_sha256']).save_draft(name_zh='版本校验')
        manifest=Path(saved['source']);part=manifest.parent/json.loads(manifest.read_text())['partitions'][0]['file']
        part.write_bytes(part.read_bytes()+b' ')
        with patch('nbt_composition.large_assembly.read_assembly',side_effect=AssertionError('must not decode all parts')):
            with self.assertRaisesRegex(ValueError,'变化|哈希'):verify_version(saved['output'])

    def test_model_cli_saves_and_previews_a_hash_bound_assembly_candidate(self):
        model = AssemblyVolume((300,384,300)); model.put((299,295,299), 'stone')
        source = save_assembly(self.root/'nbt_models/standalone/cli/v01/master', model, {(299,295,299)},
                               [dict(offset=[294,294,294],size=[6,90,6])])
        recipe = dict(tool='structure',arguments=dict(name='命令构件',size=[1,1,1],anchor=[0,0,0],
                      operations=[dict(kind='box',label='构件',classification='body',lo=[0,0,0],hi=[0,0,0],state='stone')]))
        request = dict(source=source['source'], source_sha256=source['source_sha256'],
                       positions=[[299,295,299]], cameras=[dict(id='test',eye=[308,303,285],target=[298,295,298])],
                       actions=[dict(method='patch',changes=[dict(pos=[299,295,299],before=['minecraft:stone',True],
                                                                  after=['minecraft:gold_block',False])]),
                                dict(method='install',identifier='fixture',recipe=recipe,position=[296,295,296]),
                                dict(method='update',identifier='fixture',transform=dict(position=[297,295,297]))],
                       save_draft=dict(name_zh='命令测试'))
        file = self.root/'model-request.json'; file.write_text(json.dumps(request),encoding='utf8')
        run = subprocess.run(['node',str(ROOT/'scripts/cli.mjs'),'--workspace',str(self.root),'model',
                              '--request',str(file),'--output',str(self.root/'candidate')],
                             capture_output=True,text=True,encoding='utf8',timeout=45)
        self.assertEqual(run.returncode,0,run.stdout+run.stderr)
        result = json.loads(run.stdout)['result']; saved = result['saved']; preview = result['preview']
        self.assertFalse(saved['history_pending']); self.assertFalse(saved['nbt_exported'])
        self.assertEqual(read_assembly(saved['source'])[0].get((299,295,299)), 'minecraft:gold_block')
        self.assertEqual(read_assembly(preview['source'])[0].get((299,295,299)), 'minecraft:gold_block')
        self.assertEqual(read_assembly(saved['source'])[0].get((296,295,296)), 'minecraft:air')
        self.assertEqual(read_assembly(saved['source'])[0].get((297,295,297)), 'minecraft:stone')
        self.assertEqual(json.loads(Path(preview['snapshot']).read_text(encoding='utf8'))['source_kind'], 'assembly')
        self.assertEqual(read_assembly(source['source'])[0].get((299,295,299)), 'minecraft:stone')

    def test_model_reuses_component_install_and_box_operations_above_294(self):
        from nbt_composition.working_model import WorkingModel
        model = AssemblyVolume((300,384,300)); model.put((299,295,299), 'stone')
        source = save_assembly(self.root/'nbt_models/standalone/operations/v01/master', model, set(),
                               [dict(offset=[294,294,294],size=[6,90,6])])
        working = WorkingModel.open(self.root,source['source'],source_sha256=source['source_sha256'])
        recipe = dict(tool='structure',arguments=dict(name='测试小构件',size=[1,1,1],anchor=[0,0,0],
            operations=[dict(kind='box',label='构件',classification='body',lo=[0,0,0],hi=[0,0,0],state='stone')]))
        working.install('fixture',recipe,[296,295,296])
        working.apply_operations([dict(kind='box',label='高处分区',classification='wall',
                                       lo=[298,296,298],hi=[298,296,298],state='gold_block')])
        self.assertEqual(working.model.get((296,295,296)),'minecraft:stone')
        self.assertEqual(working.model.get((298,296,298)),'minecraft:gold_block')
        self.assertIn((298,296,298),working.walls)
        saved=working.save_draft(name_zh='工具测试')
        restored=WorkingModel.open(self.root,saved['source'],source_sha256=saved['source_sha256'])
        self.assertIn('fixture',restored.instances)
        self.assertEqual(restored.model.get((298,296,298)),'minecraft:gold_block')

    def test_routes_cross_a_partition_and_blocked_candidate_is_rejected(self):
        from nbt_collision import check_routes
        from nbt_composition.working_model import WorkingModel, ModelConflict
        model = AssemblyVolume((300,384,300))
        for x in range(290,299):
            for z in range(3): model.put((x,0,z),'stone')
        specs=[dict(offset=[288,0,0],size=[6,6,6]),dict(offset=[294,0,0],size=[6,6,6])]
        source=save_assembly(self.root/'nbt_models/standalone/route/v01/master',model,set(),specs)
        context=dict(mode='standalone',openings=[],require_routes=True,start=[291.5,1,1.5],targets={'end':[297.5,1,1.5]})
        working=WorkingModel.open(self.root,source['source'],context=context,source_sha256=source['source_sha256'])
        self.assertTrue(check_routes(working.model,context['start'],context['targets'])['passed'])
        changes=[dict(pos=[294,y,z],before=['minecraft:air',False],after=['minecraft:stone',False])
                 for y in range(1,4) for z in range(3)]
        with self.assertRaisesRegex(ModelConflict,'ROUTE_FAILED'):working.patch(changes)
        self.assertEqual(working.model.get((294,1,1)),'minecraft:air')

    def test_sparse_collision_rows_match_dense_queries_without_materializing_empty_rows(self):
        import nbt_collision
        model=AssemblyVolume((8,6,8))
        for x in range(8):
            for z in range(8):model.put((x,0,z),'stone')
        model.put((4,1,4),'stone')
        dense=nbt_collision._Space(model)
        with patch.object(nbt_collision,'SPARSE_ROW_THRESHOLD',1):
            sparse=nbt_collision._Space(model)
            for p in ([2.5,1,2.5],[4.5,1,4.5],[7.5,1,7.5]):
                self.assertEqual(sparse.standing(p),dense.standing(p))
            self.assertEqual(sparse.clear_box([1,1,1],[3,3,3]),dense.clear_box([1,1,1],[3,3,3]))
            self.assertLess(len(sparse.rows),sparse.sy*sparse.sz)

    def test_maximum_sparse_canvas_does_not_allocate_dense_collision_rows(self):
        import nbt_collision, tracemalloc
        model=AssemblyVolume((4096,4096,4096)); model.put((1,0,1),'stone')
        tracemalloc.start()
        try:
            space=nbt_collision._Space(model)
            self.assertTrue(space.standing([1.5,1,1.5]))
            self.assertLess(len(space.rows),100)
            self.assertLess(tracemalloc.get_traced_memory()[1],5*1024*1024)
        finally:
            tracemalloc.stop()

    def test_shared_walk_inspector_crosses_partitions_and_binds_every_part(self):
        from nbt_review.walk_view import inspect_walk
        from nbt_collision import check_routes
        model = AssemblyVolume((300,384,300))
        for x in range(290,299):
            for z in range(3): model.put((x,0,z),'stone')
        specs=[dict(offset=[288,0,0],size=[6,6,6]),dict(offset=[294,0,0],size=[6,6,6])]
        saved=save_assembly(self.root/'nbt_models/standalone/walk/v01/master',model,set(),specs)
        request=dict(source=saved['source'],source_sha256=saved['source_sha256'],
                     start=[291.5,1,1.5],targets={'end':[297.5,1,1.5]})
        file=self.root/'walk.json';file.write_text(json.dumps(request),encoding='utf8')
        output=self.root/'walk-output'
        run=subprocess.run(['node',str(ROOT/'scripts/cli.mjs'),'--workspace',str(self.root),'control','walk-inspect',
                            '--request',str(file),'--output',str(output)],capture_output=True,text=True,encoding='utf8',timeout=45)
        self.assertEqual(run.returncode,0,run.stdout+run.stderr)
        result=json.loads((output/'walk-inspection.json').read_text(encoding='utf8'))
        self.assertTrue(result['report']['passed']); self.assertEqual(result['source_kind'],'assembly')
        self.assertEqual(len(result['assembly_partitions']),2)
        source=Path(saved['source']);part=source.parent/json.loads(source.read_text())['partitions'][0]['file']
        def mutate(*args,**kwargs):
            report=check_routes(*args,**kwargs);part.write_bytes(part.read_bytes()+b' ');return report
        with patch('nbt_collision.check_routes',side_effect=mutate):
            with self.assertRaisesRegex(ValueError,'变化'):inspect_walk(request)

    def test_assembly_finalization_is_explicitly_rejected_before_export(self):
        from nbt_finalize import finalize
        model=AssemblyVolume((300,384,300));model.put((1,1,1),'stone')
        source=save_assembly(self.root/'nbt_models/standalone/export/v01/master',model,set(),
                             [dict(offset=[0,0,0],size=[4,4,4])])
        with self.assertRaisesRegex(ValueError,'组装.*定稿'):
            finalize(self.root,source['source'])
        self.assertFalse((self.root/'nbt_models/_exports').exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
