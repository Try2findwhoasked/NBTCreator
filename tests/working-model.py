"""Whole-host composition, three-way updates and immutable draft publication."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / '.agents/skills/minecraft-nbt-modeler/scripts'
sys.path.insert(0, str(SCRIPTS))
from nbt_working_model import WorkingModel, ModelConflict, model_hash, value_at, verify_version, file_hash
from nbt_refine import read_master


def block_recipe(width=2, material='stone', wall=False):
    return dict(tool='structure', arguments=dict(name='可替换嵌板', size=[width, 2, 1], anchor=[0, 0, 0],
        operations=[dict(kind='box', label='实际嵌板', classification='wall' if wall else 'body',
            lo=[0, 0, 0], hi=[width-1, 1, 0], state=material)]))


class WorkingModels(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def new(self, **kw):
        return WorkingModel(self.root, [64 if kw.get('kind') == 'component' else 96, 12, 16], **kw)

    def put(self, m, pos, material, wall=False):
        p = tuple(pos)
        return m.patch([dict(pos=list(p), before=value_at(m.model, m.walls, p), after=[material, wall])])

    def test_compose_across_storage_seam_without_changing_free_geometry(self):
        m = self.new()
        self.put(m, [2, 1, 2], 'oak_planks')
        m.install('seam', block_recipe(4), [46, 1, 4])
        self.assertEqual([m.model.get((x, 1, 4)) for x in range(46, 50)], ['minecraft:stone'] * 4)
        m.update('seam', block_recipe(2, 'quartz_block'))
        self.assertEqual(m.model.get((2, 1, 2)), 'minecraft:oak_planks')
        self.assertEqual(m.model.get((48, 1, 4)), 'minecraft:air')
        self.assertEqual(m.inspect('seam')['instances']['seam']['owned_positions'], 4)

    def test_embedded_replacement_restores_each_original_material_and_wall(self):
        m = self.new()
        self.put(m, [46, 1, 4], 'sandstone', True)
        self.put(m, [47, 1, 4], 'diorite', False)
        m.install('inlay', block_recipe(2), [46, 1, 4], overwrite=True)
        m.update('inlay', block_recipe(1))
        self.assertEqual(value_at(m.model, m.walls, (47, 1, 4)), ['minecraft:diorite', False])
        m.remove('inlay')
        self.assertEqual(value_at(m.model, m.walls, (46, 1, 4)), ['minecraft:sandstone', True])

    def test_manual_air_and_wall_changes_report_three_values_and_are_atomic(self):
        for after in (['minecraft:air', False], ['minecraft:stone', True]):
            m = self.new()
            m.install('panel', block_recipe(), [46, 1, 4])
            self.put(m, [46, 1, 4], *after)
            before, instances = model_hash(m.model, m.walls), deepcopy(m.instances)
            with self.assertRaises(ModelConflict) as error:
                m.update('panel', block_recipe(1, 'quartz_block'))
            conflict = error.exception.conflicts[0]
            self.assertEqual(conflict['pos'], [46, 1, 4])
            self.assertEqual(conflict['current'], after)
            self.assertEqual(model_hash(m.model, m.walls), before)
            self.assertEqual(m.instances, instances)
            m.detach('panel')
            self.assertEqual(value_at(m.model, m.walls, (46, 1, 4)), after)

    def test_equal_new_result_merges_and_moving_cannot_destroy_unrelated_solids(self):
        m = self.new()
        m.install('panel', block_recipe(), [46, 1, 4])
        self.put(m, [46, 1, 4], 'quartz_block')
        m.update('panel', block_recipe(2, 'quartz_block'))
        self.put(m, [60, 1, 4], 'gold_block')
        before = model_hash(m.model, m.walls)
        with self.assertRaises(ModelConflict):
            m.update('panel', transform=dict(position=[60, 1, 4]))
        self.assertEqual(model_hash(m.model, m.walls), before)

    def test_same_value_install_does_not_acquire_existing_host_blocks(self):
        m = self.new()
        self.put(m,[46,1,4],'stone')
        m.install('same',block_recipe(1),[46,1,4])
        self.assertEqual(m.inspect('same')['instances']['same']['owned_positions'],1)
        with self.assertRaisesRegex(ModelConflict,'INSTANCE_EDIT_CONFLICT'):
            m.update('same',block_recipe(1,'quartz_block'))
        m.remove('same')
        self.assertEqual(m.model.get((46,1,4)),'minecraft:stone')

    def test_global_budget_combines_multiple_individually_small_installs(self):
        m = self.new(limits=dict(max_changed_positions=6))
        m.install('first', block_recipe(), [46, 1, 4])
        before = model_hash(m.model, m.walls)
        with self.assertRaisesRegex(ValueError, '超过上限'):
            m.install('second', block_recipe(), [50, 1, 4])
        self.assertEqual(model_hash(m.model, m.walls), before)
        self.assertNotIn('second', m.instances)

    def test_idempotent_writes_and_wall_only_changes_have_separate_budgets(self):
        m = self.new(limits=dict(max_changed_positions=10, max_written_positions=2))
        self.put(m, [46, 1, 4], 'stone')
        operation = dict(kind='box', label='重复写入', classification='body', lo=[46, 1, 4], hi=[46, 1, 4], state='stone')
        with self.assertRaisesRegex(ValueError, '操作写入量'):
            m.apply_operations([operation] * 3)
        result = self.put(m, [46, 1, 4], 'stone', True)
        self.assertEqual(result['changed_blocks'], 0)
        self.assertEqual(result['wall_membership_changes'], 1)

    def test_protection_reserved_space_and_explicit_patch_before_values(self):
        m = self.new(context=dict(mode='standalone', openings=[], protected_boxes=[dict(lo=[46, 1, 4], hi=[46, 2, 4])]))
        with self.assertRaisesRegex(ValueError, '保护'):
            m.install('panel', block_recipe(), [46, 1, 4])
        self.assertFalse(m.instances)
        with self.assertRaisesRegex(ModelConflict, 'PATCH_BASE_MISMATCH'):
            m.patch([dict(pos=[1, 1, 1], before=['minecraft:stone', False], after=['minecraft:air', False])])
        m.context['reserved_boxes'] = [dict(lo=[10, 1, 1], hi=[10, 3, 1])]
        with self.assertRaisesRegex(ModelConflict, 'RESERVED_SPACE'):
            m.install('reserved', block_recipe(), [10, 1, 1])

    def test_draft_roundtrip_reopens_managed_instances_and_never_exports(self):
        m = self.new(kind='component')
        m.install('panel', block_recipe(), [46, 1, 4])
        saved = m.save_draft('测试组合')
        version = Path(saved['output'])
        self.assertFalse(saved['history_pending'], saved)
        verify_version(version)
        self.assertFalse(list(version.rglob('*.nbt')))
        self.assertFalse((self.root / 'nbt_models/_exports').exists())
        actual, walls = read_master(saved['source'])
        self.assertEqual(model_hash(actual, walls), model_hash(m.model, m.walls))
        reopened = WorkingModel.open(self.root, saved['source'])
        reopened.update('panel', block_recipe(1))
        next_version = reopened.save_draft()
        self.assertNotEqual(next_version['revision'], saved['revision'])
        self.assertEqual(WorkingModel.open(self.root, next_version['source']).model.get((47, 1, 4)), 'minecraft:air')

    def test_same_voxels_different_recipe_produce_distinct_immutable_versions(self):
        m = self.new(kind='component')
        m.install('panel', block_recipe(), [46, 1, 4])
        first = m.save_draft('配方版本')
        original = Path(first['source']).read_bytes()
        reopened = WorkingModel.open(self.root, first['source'])
        recipe = block_recipe()
        recipe['arguments']['name'] = '同形状的新配方说明'
        reopened.update('panel', recipe)
        second = reopened.save_draft()
        self.assertEqual(Path(second['source']).read_bytes(), original)
        self.assertNotEqual(first['revision'], second['revision'])
        self.assertNotEqual(first['history']['version']['id'], second['history']['version']['id'])
        verify_version(Path(first['output']))

    def test_stale_parent_and_tampered_core_are_rejected(self):
        m = self.new(kind='component')
        first = m.save_draft('并发版本')
        a = WorkingModel.open(self.root, first['source'])
        b = WorkingModel.open(self.root, first['source'])
        self.put(a, [46, 1, 4], 'stone')
        self.put(b, [47, 1, 4], 'stone')
        a.save_draft()
        with self.assertRaisesRegex(ModelConflict, 'STALE_PARENT'):
            b.save_draft()
        (Path(first['output']) / 'coordinates.json').write_text('{}', encoding='utf8')
        with self.assertRaisesRegex(ValueError, '文件已变化'):
            WorkingModel.open(self.root, first['source'])

    def test_history_failure_is_retryable_without_duplicate_version(self):
        m = self.new(kind='component')
        with patch('nbt_history.record_produced_version', side_effect=ValueError('synthetic history failure')):
            first = m.save_draft('恢复测试')
        self.assertTrue(first['history_pending'])
        second = m.save_draft('恢复测试')
        self.assertFalse(second['history_pending'])
        self.assertEqual(first['revision'], second['revision'])
        self.assertEqual(len(list((self.root / 'nbt_models/standalone/恢复测试').glob('v_model_*'))), 1)
        self.put(m,[3,1,3],'stone')
        self.assertFalse(m.save_draft()['history_pending'])
        with patch('nbt_history.record_produced_version',return_value=dict(recorded=False,error='synthetic unavailable history')):
            pending = self.new(kind='component').save_draft('真实返回错误封装')
        self.assertTrue(pending['history_pending'])

    def test_failure_before_publication_exposes_no_partial_version(self):
        m = self.new(kind='component')
        with patch('nbt_working_model.os.rename', side_effect=OSError('synthetic rename failure')):
            with self.assertRaises(OSError):
                m.save_draft('发布失败')
        self.assertFalse(list((self.root / 'nbt_models').rglob('*.snbt')))
        self.assertFalse(list((self.root / '.nbtcreator/model-staging').iterdir()))

    def room(self):
        context = dict(mode='standalone',openings=[dict(id='entry',lo=[5,1,0],hi=[6,3,0],facing='north')],
            interior_probes=[[5,2,5]],start=[5.5,1,1.5],targets={'far':[5.5,1,8.5]},cameras=[
                dict(role='whole',eye=[20,15,20],target=[6,3,6]),
                dict(role='entry',eye=[5.5,2.62,1.5],target=[5.5,2.62,8.5])])
        m = WorkingModel(self.root,[12,8,12],context)
        m.apply_operations([dict(kind='box',label='真实外壳',classification='wall',lo=[0,0,0],hi=[11,7,11],state='stone'),
            dict(kind='box',label='内部空间',classification='body',lo=[1,1,1],hi=[10,6,10],state='air')])
        m.install('panel',block_recipe(),[2,1,5])
        m.seal()
        m.open_declared()
        return m

    def test_complete_building_keeps_preopening_source_and_checks_real_routes(self):
        m = self.room()
        saved = m.save_draft('封闭开洞测试')
        version = Path(saved['output'])
        self.assertTrue((version/'master/preopening.snbt').is_file())
        closed,_ = read_master(version/'master/preopening.snbt')
        self.assertEqual(closed.get((5,1,0)),'minecraft:stone')
        self.assertEqual(read_master(saved['source'])[0].get((5,1,0)),'minecraft:air')
        self.assertTrue(m.validate()['whole_model']['routes']['passed'])

    def test_desktop_save_preserves_instances_and_stales_another_working_copy(self):
        from nbt_web_revision import convert_web_json
        from nbt_detail_control import default_settings
        m = self.room()
        first = m.save_draft('桌面共用保存')
        other = WorkingModel.open(self.root,first['source'])
        settings = default_settings()
        settings['operations'] = [dict(kind='box',label='人工改动实例',classification='body',lo=[2,1,5],hi=[2,1,5],state='gold_block')]
        request = self.root/'desktop-request.json'
        request.write_text(json.dumps(dict(source=first['source'],source_sha256=file_hash(first['source']),
            context=str(Path(first['output'])/'coordinates.json'),settings=settings,draft_only=True)),encoding='utf8')
        saved = convert_web_json(request)
        self.assertTrue(saved['draft_only'])
        self.assertFalse(saved['history_pending'])
        edited = WorkingModel.open(self.root,saved['master'])
        self.assertIn('panel',edited.instances)
        with self.assertRaisesRegex(ModelConflict,'INSTANCE_EDIT_CONFLICT'):
            edited.update('panel',block_recipe(1,'quartz_block'))
        self.put(other,[8,1,8],'gold_block')
        with self.assertRaisesRegex(ModelConflict,'STALE_PARENT'):
            other.save_draft()

    def test_same_session_can_save_twice_and_retry_head_publication(self):
        m = self.new(kind='component')
        first = m.save_draft('连续制作')
        self.put(m,[46,1,4],'stone')
        second = m.save_draft()
        self.assertNotEqual(first['revision'],second['revision'])
        self.assertEqual(m.save_draft()['revision'],second['revision'])
        another = self.new(kind='component')
        with patch('nbt_object_scene.atomic',side_effect=OSError('synthetic head failure')):
            with self.assertRaises(OSError):
                another.save_draft('指针恢复')
        retried = another.save_draft('指针恢复')
        self.assertFalse(retried['history_pending'])
        self.assertEqual(len(list((self.root/'nbt_models/standalone/指针恢复').glob('v_model_*'))),1)

    def test_cli_uses_shared_api_and_rejects_stale_source_requests(self):
        request = self.root / 'request.json'
        request.write_text(json.dumps(dict(size=[12, 8, 12], kind='component', actions=[dict(method='install', identifier='pillar',
            recipe=block_recipe(), position=[4, 1, 4])], save_draft=dict(name_zh='接口测试'))), encoding='utf8')
        run = subprocess.run([sys.executable, '-B', str(SCRIPTS / 'nbt_working_model.py'), '--workspace', str(self.root), '--request', str(request)], capture_output=True, text=True, encoding='utf8')
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertFalse(json.loads(run.stdout)['result']['saved']['history_pending'],run.stdout)
        source = json.loads(run.stdout)['result']['saved']['source']
        request.write_text(json.dumps(dict(source=source, source_sha256='0'*64)), encoding='utf8')
        run = subprocess.run([sys.executable, '-B', str(SCRIPTS / 'nbt_working_model.py'), '--workspace', str(self.root), '--request', str(request)], capture_output=True, text=True, encoding='utf8')
        self.assertEqual(json.loads(run.stdout)['code'], 'STALE_SOURCE')

    def test_actual_node_and_frozen_workspace_entry_share_the_model_contract(self):
        from nbt_exposure import apply
        request=self.root/'request.json'
        request.write_text(json.dumps(dict(size=[12,8,12],kind='component',actions=[dict(method='install',identifier='panel',
            recipe=block_recipe(),position=[4,1,4])],save_draft=dict(name_zh='完整入口'))),encoding='utf8')
        run=subprocess.run(['node',str(ROOT/'scripts/cli.mjs'),'--workspace',str(self.root),'model','--request',str(request)],capture_output=True,text=True,encoding='utf8')
        self.assertEqual(run.returncode,0,run.stdout+run.stderr)
        first=json.loads(run.stdout)['result']['saved']
        apply(self.root,dict(schema_version=1,enabled_groups=['core','modelling'],custom_knowledge=[]))
        facade=self.root/'.agents/skills/nbtcreator-workspace/nbt.py'
        request.write_text(json.dumps(dict(source=first['source'],source_sha256=file_hash(first['source']),actions=[dict(method='update',identifier='panel',recipe=block_recipe(1))],save_draft={})),encoding='utf8')
        run=subprocess.run([sys.executable,'-B',str(facade),'model','--request',str(request)],cwd=self.root,capture_output=True,text=True,encoding='utf8')
        self.assertEqual(run.returncode,0,run.stdout+run.stderr)
        second=json.loads(run.stdout)['result']['saved']
        self.assertNotEqual(first['revision'],second['revision'])
        self.assertIn('统一', (self.root/'.agents/skills/nbtcreator-workspace/SKILL.md').read_text(encoding='utf8'))

    def test_two_processes_from_the_same_parent_publish_only_one_head(self):
        from concurrent.futures import ThreadPoolExecutor
        m=self.new(kind='component')
        first=m.save_draft('并发进程')
        requests=[]
        for number in (1,2):
            request=self.root/f'request-{number}.json'
            request.write_text(json.dumps(dict(source=first['source'],source_sha256=file_hash(first['source']),actions=[dict(method='install',identifier=f'panel{number}',
                recipe=block_recipe(),position=[40+number*4,1,4])],save_draft={})),encoding='utf8')
            requests.append(request)
        def execute(request):
            return subprocess.run([sys.executable,'-B',str(SCRIPTS/'nbt_working_model.py'),'--workspace',str(self.root),'--request',str(request)],capture_output=True,text=True,encoding='utf8')
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(execute,requests))
        self.assertEqual(sorted(run.returncode for run in results),[0,1],[run.stdout+run.stderr for run in results])
        failed=next(json.loads(run.stdout) for run in results if run.returncode)
        self.assertEqual(failed['code'],'STALE_PARENT')


    def test_unowned_manual_equal_result_never_becomes_owned(self):
        m = self.new(kind='component')
        for y in (1, 2):
            self.put(m, [1,y,1], 'stone', True)
        m.install('panel', block_recipe(1, wall=True), [1,1,1])
        for y in (1, 2):
            self.put(m, [1,y,1], 'gold_block')
        result = m.update('panel', block_recipe(1, 'gold_block'))
        self.assertEqual(result['changed_positions'], 0)
        self.assertEqual(m.inspect('panel')['instances']['panel']['owned_positions'], 0)
        saved = m.save_draft('宿主归属')
        reopened = WorkingModel.open(self.root, saved['source'])
        reopened.remove('panel')
        self.assertEqual(value_at(reopened.model, reopened.walls, (1,1,1)), ['minecraft:gold_block', False])

    def test_bound_constraints_cannot_be_replaced_or_mutated(self):
        context = dict(mode='standalone', openings=[], max_changed_blocks=1,
            protected_boxes=[dict(lo=[1,1,1],hi=[1,1,1])])
        first = self.new(kind='component', context=context).save_draft('保护约束')
        with self.assertRaisesRegex(ValueError, 'CONTEXT'):
            WorkingModel.open(self.root, first['source'], dict(mode='standalone', openings=[]))
        m = WorkingModel.open(self.root, first['source'])
        m.context['protected_boxes'] = []
        with self.assertRaisesRegex(ValueError, 'CONTEXT'):
            self.put(m, [1,1,1], 'stone')

    def test_replaying_an_old_result_never_rewinds_either_head(self):
        m = self.new(kind='component')
        a = m.save_draft('重放旧版')
        self.put(m, [1,1,1], 'stone')
        b = m.save_draft()
        self.put(m, [2,1,1], 'stone')
        c = m.save_draft()
        replay = WorkingModel.open(self.root, a['source'])
        self.put(replay, [1,1,1], 'stone')
        self.assertEqual(replay.save_draft()['revision'], b['revision'])
        self.assertEqual(m._read_head(m._building)['revision'], c['revision'])
        self.assertEqual(m._history_source(m._building), Path(c['source']).relative_to(m.workspace).as_posix())

    def test_pending_history_ancestors_are_recorded_before_children(self):
        from nbt_history import History
        m = self.new(kind='component')
        a = m.save_draft('待补历史')
        self.put(m, [1,1,1], 'stone')
        with patch('nbt_history.record_produced_version', return_value=dict(recorded=False,error='offline')):
            b = m.save_draft()
        self.assertTrue(b['history_pending'])
        self.put(m, [2,1,1], 'stone')
        c = m.save_draft()
        self.assertFalse(c['history_pending'])
        data = History(self.root).list(c['source'])
        versions = {item['absolute_source']:item for item in data['versions']}
        self.assertEqual(versions[b['source']]['parent'], a['history']['version']['id'])
        self.assertEqual(versions[c['source']]['parent'], versions[b['source']]['id'])
        self.assertIn(versions[c['source']]['id'], data['current'].values())
        retry = WorkingModel.open(self.root, a['source'])
        self.put(retry, [1,1,1], 'stone')
        self.assertFalse(retry.save_draft()['history_pending'])

    def test_history_selection_and_derive_invalidate_old_model_head(self):
        from nbt_history import History
        m = self.new(kind='component')
        a = m.save_draft('历史切头')
        self.put(m, [1,1,1], 'stone')
        b = m.save_draft()
        history = History(self.root)
        derived = history.derive(a['history']['version']['id'])
        stale = WorkingModel.open(self.root, b['source'])
        self.put(stale, [2,1,1], 'stone')
        with self.assertRaisesRegex(ModelConflict, 'STALE_PARENT'):
            stale.save_draft()
        continued = WorkingModel.open(self.root, derived['source'])
        self.put(continued, [3,1,1], 'stone')
        c = continued.save_draft()
        self.assertFalse(c['history_pending'])
        history.current(a['history']['version']['id'])
        self.assertEqual(continued._read_head(continued._building)['source'],
            Path(a['source']).relative_to(continued.workspace).as_posix())

    def legacy_room(self):
        from nbt_refine import save_master
        m = self.room()
        version = self.root / 'nbt_models/standalone/旧房/v01'
        source = version / 'master/model.snbt'
        save_master(source, m.model, m.walls)
        (version/'coordinates.json').write_text(json.dumps(m.context), encoding='utf8')
        (version/'room_description.json').write_text(json.dumps(dict(name_zh='旧房',shape='standalone',mode='standalone')), encoding='utf8')
        return source

    def test_legacy_desktop_cannot_publish_from_a_stale_parent(self):
        from nbt_web_revision import convert_web_json
        from nbt_detail_control import default_settings
        source = self.legacy_room()
        m = WorkingModel.open(self.root, source)
        self.put(m, [3,2,3], 'gold_block')
        first = m.save_draft()
        settings = default_settings()
        settings['operations'] = [dict(kind='box',label='修改',classification='body',lo=[6,2,6],hi=[6,2,6],state='stone')]
        request = self.root/'manual.json'
        request.write_text(json.dumps(dict(source=str(source),source_sha256=file_hash(source),
            context=str(source.parent.parent/'coordinates.json'),settings=settings,draft_only=True)),encoding='utf8')
        with self.assertRaisesRegex(ValueError,'STALE_PARENT'):
            convert_web_json(request)
        self.assertEqual(m._read_head(m._building)['revision'], first['revision'])
        self.assertFalse((source.parent.parent.parent/'v02').exists())

    def test_managed_identity_cannot_fall_back_to_legacy_or_evidence_source(self):
        m = self.room()
        first = m.save_draft('受管身份')
        version = Path(first['output'])
        with self.assertRaisesRegex(ValueError,'SOURCE'):
            WorkingModel.open(self.root, version/'master/preopening.snbt')
        (version/'model-version.json').unlink()
        with self.assertRaisesRegex(ValueError,'清单'):
            WorkingModel.open(self.root, first['source'])

    def test_finalize_rejects_a_damaged_managed_version_before_export(self):
        from nbt_finalize import finalize
        first = self.room().save_draft('定稿绑定')
        (Path(first['output'])/'model-instances.json').write_text('{}', encoding='utf8')
        with self.assertRaisesRegex(ValueError,'文件已变化'):
            finalize(self.root, first['source'])
        self.assertFalse((self.root/'nbt_models/_exports').exists())

    def test_saved_free_voxels_enforce_reserved_space_and_required_routes(self):
        m = self.new(context=dict(mode='standalone',openings=[],
            reserved_boxes=[dict(lo=[2,1,2],hi=[2,1,2])]))
        m.model.put((2,1,2), 'stone')
        with self.assertRaisesRegex(ValueError,'RESERVED'):
            m.save_draft('留白检查')
        m = WorkingModel(self.root,[6,5,3],context=dict(mode='standalone',openings=[],
            require_routes=True,start=[1.5,1,1.5],targets={'end':[4.5,1,1.5]}))
        m.model.box((0,0,0),(5,0,2),'stone')
        m.model.box((3,1,0),(3,4,2),'stone')
        with self.assertRaisesRegex(ValueError,'ROUTE'):
            m.save_draft('路线检查')

    def test_legacy_floor_context_protection_is_effective(self):
        source = self.legacy_room()
        context = source.parent.parent/'coordinates.json'
        data = json.loads(context.read_text(encoding='utf8'))
        data['floor_context'] = dict(protected_boxes=[dict(lo=[3,1,3],hi=[3,1,3])])
        context.write_text(json.dumps(data),encoding='utf8')
        m = WorkingModel.open(self.root,source)
        with self.assertRaisesRegex(ValueError,'保护'):
            self.put(m,[3,1,3],'gold_block')

    def test_sealed_draft_reopens_and_carves_through_real_cli(self):
        m = WorkingModel(self.root,[7,6,7],context=dict(mode='standalone',
            openings=[dict(id='door',lo=[3,1,0],hi=[3,3,0],facing='north')],interior_probes=[[3,2,3]]))
        m.apply_operations([dict(kind='box',label='外壳',classification='wall',lo=[0,0,0],hi=[6,5,6],state='stone'),
            dict(kind='box',label='内部',classification='body',lo=[1,1,1],hi=[5,4,5],state='air')])
        m.seal()
        first = m.save_draft('封闭接续')
        request = self.root/'open.json'
        request.write_text(json.dumps(dict(source=first['source'],source_sha256=file_hash(first['source']),
            actions=[dict(method='open_declared')],positions=[[3,1,0]])),encoding='utf8')
        run = subprocess.run([sys.executable,'-B',str(SCRIPTS/'nbt_working_model.py'),'--workspace',str(self.root),'--request',str(request)],capture_output=True,text=True,encoding='utf8')
        self.assertEqual(run.returncode,0,run.stdout+run.stderr)
        self.assertEqual(json.loads(run.stdout)['result']['model']['samples'][0]['value'],['minecraft:air',False])

    def test_binary_wall_sidecar_changes_invalidate_the_working_copy(self):
        from nbt_assembly import Volume
        from nbt_snbt import write_binary
        model = Volume([4,4,4])
        model.put((1,1,1),'stone')
        source = self.root/'external/model.nbt'
        write_binary(source,model,{(1,1,1)})
        working = WorkingModel.open(self.root,source,kind='component')
        file = source.parent/'wall_mask.json'
        data = json.loads(file.read_text(encoding='utf8'))
        data['wall_positions'] = []
        file.write_text(json.dumps(data),encoding='utf8')
        with self.assertRaisesRegex(ValueError,'STALE_SOURCE'):
            working.save_draft('墙层失效')

    def test_desktop_component_draft_uses_component_validation(self):
        from nbt_web_revision import convert_web_json
        from nbt_detail_control import default_settings
        m = self.new(kind='component')
        m.install('panel',block_recipe(),[4,1,4])
        first = m.save_draft('独立构件')
        settings = default_settings()
        settings['operations'] = [dict(kind='box',label='添格',classification='body',lo=[8,1,4],hi=[8,1,4],state='gold_block')]
        request = self.root/'component.json'
        request.write_text(json.dumps(dict(source=first['source'],source_sha256=file_hash(first['source']),
            context=str(Path(first['output'])/'coordinates.json'),settings=settings,draft_only=True)),encoding='utf8')
        from nbt_detail_control import inspect_source, source_snapshot
        self.assertTrue(inspect_source(first['source'])['editing_ready'])
        baseline = source_snapshot(json.loads(request.read_text(encoding='utf8')),self.root/'baseline')
        self.assertFalse(baseline['read_only_view'])
        result = convert_web_json(request)
        reopened = WorkingModel.open(self.root,result['master'])
        self.assertEqual(reopened.kind,'component')
        self.assertIn('panel',reopened.instances)
        self.assertEqual(reopened.model.get((8,1,4)),'minecraft:gold_block')
        self.assertFalse((self.root/'nbt_models/_exports').exists())

    def test_flat_legacy_source_uses_its_version_description(self):
        from nbt_refine import save_master
        source = self.legacy_room()
        flat = source.parent.parent/'building.master.json.gz'
        model,walls = read_master(source)
        save_master(flat,model,walls)
        result = WorkingModel.open(self.root,flat).save_draft()
        self.assertFalse(result['history_pending'])

    def test_standalone_48_draft_can_be_derived_with_instances(self):
        from nbt_history import History
        m = WorkingModel(self.root,[48,6,48],kind='component')
        m.install('panel',block_recipe(),[4,1,4])
        first = m.save_draft('方形独立构件')
        # Older managed drafts recorded mode only in coordinates.json.
        description = Path(first['output'])/'room_description.json'
        metadata = json.loads(description.read_text(encoding='utf8'))
        metadata.pop('mode',None)
        description.write_text(json.dumps(metadata),encoding='utf8')
        m.save_draft()
        result = History(self.root).derive(first['history']['version']['id'])
        reopened = WorkingModel.open(self.root,result['source'])
        self.assertIn('panel',reopened.instances)
        self.assertEqual(reopened.context['mode'],'standalone')
        self.assertNotEqual(reopened.parent_revision,first['revision'])

    def test_old_pending_history_with_missing_parent_is_repaired_from_manifest(self):
        from nbt_history import History
        m = self.new(kind='component')
        a = m.save_draft('修复历史父链')
        self.put(m,[1,1,1],'stone')
        b = m.save_draft()
        history = History(self.root)
        with history.lock():
            data,head = history.state()
            data['versions'][b['history']['version']['id']]['parent'] = None
            history.commit(data,head,'simulate legacy interrupted ancestry')
        retried = m.save_draft()
        self.assertFalse(retried['history_pending'])
        self.assertEqual(history.get(b['history']['version']['id'])['version']['parent'],a['history']['version']['id'])

    def test_constraints_and_budget_survive_cli_reopen(self):
        m = self.new(kind='component',limits=dict(max_changed_positions=2))
        first = m.save_draft('跨会话预算')
        m = WorkingModel.open(self.root,first['source'],limits=dict(max_changed_positions=100))
        self.assertEqual(m.limits['max_changed_positions'],2)
        self.put(m,[1,1,1],'stone')
        self.put(m,[2,1,1],'stone')
        with self.assertRaisesRegex(ValueError,'上限'):
            self.put(m,[3,1,1],'stone')

    def test_interrupted_head_retry_cannot_rewind_another_publication(self):
        m = self.new(kind='component')
        a = m.save_draft('中断重放')
        self.put(m,[1,1,1],'stone')
        with patch('nbt_object_scene.atomic',side_effect=OSError('head interrupted')):
            with self.assertRaises(OSError):
                m.save_draft()
        other = WorkingModel.open(self.root,a['source'])
        self.put(other,[2,1,1],'stone')
        c = other.save_draft()
        retried = m.save_draft()
        self.assertFalse(retried['history_pending'])
        self.assertEqual(m._read_head(m._building)['revision'],c['revision'])
        self.assertEqual(m._history_source(m._building),Path(c['source']).relative_to(m.workspace).as_posix())

    def test_history_selection_preflights_managed_files_before_committing(self):
        from nbt_history import History
        m = self.new(kind='component')
        a = m.save_draft('选择版本检查')
        self.put(m,[1,1,1],'stone')
        b = m.save_draft()
        history = History(self.root)
        before = history.state()[1]
        (Path(a['output'])/'model-instances.json').write_text('{}',encoding='utf8')
        with self.assertRaisesRegex(ValueError,'文件已变化'):
            history.current(a['history']['version']['id'])
        self.assertEqual(history.state()[1],before)
        self.assertEqual(m._read_head(m._building)['revision'],b['revision'])

    def test_desktop_and_cli_from_the_same_parent_have_one_winner(self):
        from concurrent.futures import ThreadPoolExecutor
        from nbt_detail_control import default_settings
        m = self.room()
        a = m.save_draft('桌面命令并发')
        cli_request = self.root/'cli-race.json'
        cli_request.write_text(json.dumps(dict(source=a['source'],source_sha256=file_hash(a['source']),
            actions=[dict(method='patch',changes=[dict(pos=[8,1,8],before=['minecraft:air',False],after=['minecraft:gold_block',False])])],
            save_draft={})),encoding='utf8')
        settings = default_settings()
        settings['operations'] = [dict(kind='box',label='桌面并发',classification='body',lo=[7,1,7],hi=[7,1,7],state='stone')]
        desktop_request = self.root/'desktop-race.json'
        desktop_request.write_text(json.dumps(dict(source=a['source'],source_sha256=file_hash(a['source']),
            context=str(Path(a['output'])/'coordinates.json'),settings=settings,draft_only=True)),encoding='utf8')
        commands = [
            [sys.executable,'-B',str(SCRIPTS/'nbt_working_model.py'),'--workspace',str(self.root),'--request',str(cli_request)],
            [sys.executable,'-B',str(SCRIPTS/'nbt_web_revision.py'),'--input',str(desktop_request)]]
        def execute(command):
            return subprocess.run(command,capture_output=True,text=True,encoding='utf8')
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(execute,commands))
        self.assertEqual(sorted(item.returncode for item in results),[0,1],[item.stdout+item.stderr for item in results])
        failed = next(item for item in results if item.returncode)
        self.assertIn('STALE_PARENT',failed.stdout)
        head = m._read_head(m._building)
        self.assertEqual(head['source'],m._history_source(m._building))
        reopened = WorkingModel.open(self.root,head['source'])
        self.assertIn('panel',reopened.instances)


if __name__ == '__main__':
    unittest.main(verbosity=2)
