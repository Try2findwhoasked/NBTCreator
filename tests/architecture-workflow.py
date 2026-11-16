"""Building plans are executable, version-bound and checked against actual geometry."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_architect import dispatch
from nbt_architecture_plan import fingerprint,normalize,resolve
from nbt_working_model import WorkingModel,file_hash


def box_part(identifier,lo,size,role='structure',material='structure'):
    return dict(id=identifier,role=role,position=lo,recipe=dict(tool='structure',arguments=dict(name=identifier,size=size,
        anchor=[0,0,0],operations=[dict(kind='box',label=identifier,classification='body',lo=[0,0,0],hi=[v-1 for v in size],state={'design_ref':'style.materials.'+material})])))


def plan(wood=False):
    palette=dict(structure='spruce_planks' if wood else 'stone_bricks',wall='calcite' if wood else 'stone_bricks',
        roof='oxidized_cut_copper' if wood else 'deepslate_tiles',floor='smooth_stone',glass='light_blue_stained_glass')
    parts=[box_part('porch',[13,1,0],[5,1,2],role='floor',material='floor'),
        box_part('platform',[4,4,20],[5,1,6]),box_part('left',[11,2,12],[3,3,3]),
        box_part('right',[21,2,12],[3,5,3]),box_part('roof_post',[21,2,21],[3,6,3])]
    result=dict(schema_version=1,name='木光样本馆' if wood else '石构档案馆',size=[28,18,30],
        levels=dict(ground=dict(feet_y=2),gallery=dict(feet_y=5)),
        style=dict(name='轻型折面木构' if wood else '厚墙石构',materials=palette,parameters=dict(beam_width=3),principles=['同类支承共享材质','跨高梁与屋面落座有实际接口']),
        context=dict(mode='standalone',openings=[dict(id='entry',lo=[14,2,1],hi=[16,5,1],facing='north')],
            interior_probes=[[15,4,8],[6,7,22]],start=[15.5,2,.5],targets=dict(hall=[15.5,2,8.5],gallery=[6.5,5,22.5]),max_changed_blocks=30000),
        spaces=[dict(id='hall',purpose='展陈和操作',lo=[2,2,2],hi=[25,10,27],feet_y={'design_ref':'levels.ground.feet_y'},samples=[[15.5,2,8.5]],min_clearance=3),
            dict(id='gallery',purpose='登高阅览',lo=[4,5,20],hi=[8,10,25],feet_y={'design_ref':'levels.gallery.feet_y'},samples=[[6.5,5,22.5]],min_clearance=3)],
        envelope=dict(wall={'design_ref':'style.materials.wall'},floor={'design_ref':'style.materials.floor'},roof={'design_ref':'style.materials.roof'},
            volumes=[dict(id='hall_volume',lo_xz=[2,2],hi_xz=[25,27],feet_y=2,eaves_y=11,roof=dict(kind='gable',rise=4,axis='z'))],
            glazing=[dict(lo=[1,3,5],hi=[1,7,24],state={'design_ref':'style.materials.glass'})],
            interfaces=[dict(id='roof_seat',face='down',lo=[21,11,21],hi=[23,15,23])]),
        parts=parts,
        stairs=[dict(id='gallery_stair',kind='stair_system',operation=dict(kind='auto_stairs',label='通向阅览廊',classification='body',lo=[4,1,2],hi=[8,7,19],
            start=[6,2,3],end=[6,5,19],width=3,mode='straight',state='stone_bricks',slab_state='stone_brick_slab[type=bottom]'),foundation_y=2,support_spacing=4,support_material={'design_ref':'style.materials.structure'})],
        connections=[dict(id='main_beam',kind='beam_link',axis='x',width={'design_ref':'style.parameters.beam_width'},height=1,
            **{'from':dict(part='left',interface='up'),'to':dict(part='right',interface='up')},material={'design_ref':'style.materials.structure'}),
            dict(id='roof_bearing',kind='bearing_block',width=1,depth=3,max_gap=8,
                **{'from':dict(part='roof_post',interface='up'),'to':dict(part='envelope',interface='roof_seat')},material={'design_ref':'style.materials.structure'})],
        rules=[dict(id='support_palette',kind='palette',parts=['left','right','platform','roof_post'],roles=['structure'])],
        views=[dict(id='overall',layer='massing',eye=[46,30,-32],target=[14,7,15],fov=50),
            dict(id='beam',layer='structure',feet=[15.5,2,8.5],target_part='main_beam',fov=65,minimum_visible=.1),
            dict(id='reading',layer='detail',feet=[6.5,5,22.5],target_part='left',fov=65,minimum_visible=.1)])
    if wood:
        # A lower front volume and an offset taller rear lantern change section
        # and silhouette, not merely the stone case's palette.
        result['envelope']['volumes']=[dict(id='front',lo_xz=[2,2],hi_xz=[25,16],feet_y=2,eaves_y=11,roof=dict(kind='flat',rise=0)),
            dict(id='rear',lo_xz=[2,16],hi_xz=[25,27],feet_y=2,eaves_y=14,roof=dict(kind='hip',rise=2))]
        result['envelope']['interfaces'][0].update(lo=[21,14,21],hi=[23,16,23])
    return result


class ArchitectureWorkflow(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);self.workspace=Path(temporary.name)

    def make(self,wood=False):
        return dispatch(self.workspace,'plan-build',dict(plan=plan(wood),save_draft={}))

    def test_two_different_building_systems_compile_seal_open_and_roundtrip(self):
        first=self.make();second=self.make(True)
        for result in (first,second):
            self.assertTrue(result['checks']['architecture']['passed'])
            self.assertTrue(result['checks']['whole_model']['routes']['passed'])
            saved=result['saved'];reopened=WorkingModel.open(self.workspace,saved['source'])
            self.assertEqual(reopened.architecture['sha256'],result['plan_sha256'])
            self.assertTrue(reopened.validate()['architecture']['passed'])
            self.assertFalse((self.workspace/'nbt_models/_exports').exists())
        self.assertNotEqual(first['checks']['model_sha256'],second['checks']['model_sha256'])

    def test_saved_plan_and_shared_design_references_are_revision_bound(self):
        original=plan();record=dispatch(self.workspace,'plan-save',dict(plan=original,revision=0))
        self.assertEqual(dispatch(self.workspace,'plan-get',dict(id=record['id']))['sha256'],record['sha256'])
        with self.assertRaisesRegex(ValueError,'父修订'):dispatch(self.workspace,'plan-save',dict(plan=original,id=record['id'],revision=0))
        broken=deepcopy(original);broken['style']['parameters']['bad']={'design_ref':'style.parameters.bad'}
        with self.assertRaisesRegex(ValueError,'循环'):resolve(normalize(broken))

    def test_manual_material_and_space_obstruction_cannot_silently_pass_architecture(self):
        result=self.make();source=result['saved']['source'];before=file_hash(source);working=WorkingModel.open(self.workspace,source)
        working.model.put((11,2,12),'gold_block')
        with self.assertRaisesRegex(ValueError,'DESIGN_INVALID'):working.validate()
        self.assertEqual(file_hash(source),before)

    def test_public_capabilities_and_frozen_entry_discover_the_workflow(self):
        from nbt_exposure import apply
        apply(self.workspace,dict(schema_version=1,enabled_groups=['core','modelling']))
        entry=self.workspace/'.agents/skills/nbtcreator-workspace/nbt.py'
        run=subprocess.run([sys.executable,'-B',str(entry),'capabilities','--architecture'],cwd=self.workspace,capture_output=True,text=True,encoding='utf8')
        self.assertEqual(run.returncode,0,run.stderr)
        self.assertIn('plan-build',json.loads(run.stdout)['architecture']['actions'])


    def test_source_rebuild_keeps_history_and_rejects_stale_plan_identity(self):
        first=self.make();source=first['saved']['source'];before=file_hash(source);changed=plan()
        changed['style']['materials']['structure']='polished_andesite'
        second=dispatch(self.workspace,'plan-build',dict(plan=changed,source=source,source_sha256=before,
            expected_plan_sha256=first['plan_sha256'],save_draft={}))
        self.assertNotEqual(first['saved']['revision'],second['saved']['revision'])
        self.assertEqual(file_hash(source),before)
        self.assertEqual(WorkingModel.open(self.workspace,second['saved']['source']).architecture['sha256'],second['plan_sha256'])
        with self.assertRaisesRegex(ValueError,'父指纹'):
            dispatch(self.workspace,'plan-build',dict(plan=changed,source=second['saved']['source'],source_sha256=file_hash(second['saved']['source']),expected_plan_sha256=first['plan_sha256']))

    def test_actual_room_obstruction_is_checked_on_free_host_edits(self):
        result=self.make();working=WorkingModel.open(self.workspace,result['saved']['source'])
        working.model.put((15,2,8),'stone')
        with self.assertRaises(ValueError):working.validate()
        self.assertEqual(working.architecture['sha256'],result['plan_sha256'])

    def test_three_scale_cameras_are_bound_to_the_source_and_detect_bad_poses(self):
        result=self.make();source=result['saved']['source']
        prepared=dispatch(self.workspace,'review-prepare',dict(source=source,source_sha256=file_hash(source),output='nbt_models/_workspaces/reviews/good'))
        self.assertTrue(prepared['coverage']['coverage_passed'],prepared['coverage']['views'])
        self.assertEqual({row['layer'] for row in prepared['coverage']['views']},{'massing','structure','detail'})
        working=WorkingModel.open(self.workspace,source);binding=working.architecture
        binding['plan']['views'][1]['feet']=[11.5,2,12.5]
        binding['sha256']=fingerprint(binding['plan']);working._architecture=binding
        revised=working.save_draft()
        bad=dispatch(self.workspace,'review-prepare',dict(source=revised['source'],source_sha256=file_hash(revised['source']),output='nbt_models/_workspaces/reviews/bad'))
        self.assertFalse(bad['coverage']['coverage_passed'])
        self.assertFalse(next(row for row in bad['coverage']['views'] if row['id']=='beam')['standing'])

    def test_unperformed_game_checks_remain_unverified_and_require_evidence(self):
        result=self.make();source=result['saved']['source'];request=dict(source=source,source_sha256=file_hash(source))
        checklist=dispatch(self.workspace,'game-checklist',request)
        self.assertTrue(all(row['state']=='not_checked' for row in checklist['checks']))
        self.assertFalse(checklist['game_execution_witnessed']);self.assertFalse(checklist['nbt_exported'])
        checks=[dict(id=row['id'],state='passed',note='synthetic fixture',evidence=[]) for row in checklist['checks']]
        with self.assertRaisesRegex(ValueError,'实际证据'):
            dispatch(self.workspace,'game-record',dict(request,runtime_build='test-only',checks=checks))

    def test_style_dimensions_and_ratios_check_current_recipe_arguments(self):
        spec=plan();spec['rules'] += [
            dict(id='gallery_width',kind='argument',parts=['platform'],argument_path=['size','0'],value=5),
            dict(id='pillar_proportion',kind='ratio',parts=['left'],numerator=['size','1'],denominator=['size','0'],minimum=.9,maximum=1.1)]
        result=dispatch(self.workspace,'plan-build',dict(plan=spec,save_draft={}))
        model=WorkingModel.open(self.workspace,result['saved']['source'])
        model.instances['part_platform']['recipe']['arguments']['graph']['objects'][0]['recipe']['arguments']['size'][0]=4
        with self.assertRaisesRegex(ValueError,'DESIGN_INVALID'):model.validate()
        model=WorkingModel.open(self.workspace,result['saved']['source'])
        model.instances['part_left']['recipe']['arguments']['graph']['objects'][0]['recipe']['arguments']['size'][1]=6
        with self.assertRaisesRegex(ValueError,'DESIGN_INVALID'):model.validate()

    def test_stair_support_and_railing_are_real_geometry_and_rechecked_after_edits(self):
        spec=plan();spec['stairs'][0]['railing']=dict(state='spruce_fence',kerb_material='stone_bricks')
        result=dispatch(self.workspace,'plan-build',dict(plan=spec,save_draft={}))
        model=WorkingModel.open(self.workspace,result['saved']['source']);receipt=model.architecture['systems']['gallery_stair']
        self.assertTrue(receipt['supports_generated']);self.assertTrue(receipt['railings_generated'])
        rails=[(p,v) for p,v in model.model.blocks.items() if 'spruce_fence' in v]
        self.assertGreater(len(rails),10)
        for p,value in rails:
            self.assertNotEqual(model.model.get((p[0],p[1]-1,p[2])),'minecraft:air')
        p=receipt['accessory_positions'][0];model.model.put(tuple(p),'air')
        with self.assertRaisesRegex(ValueError,'DESIGN_INVALID'):model.validate()
        model=WorkingModel.open(self.workspace,result['saved']['source'])
        feet=receipt['feet'][len(receipt['feet'])//2];model.model.put((int(feet[0]),int(feet[1])+1,int(feet[2])),'stone')
        with self.assertRaises(ValueError):model.validate()

    def test_invalid_contract_references_and_polygons_fail_before_publication(self):
        for modify in (
            lambda p:p['views'][0].update(target_part='missing'),
            lambda p:p['views'][0].update(feet=[1,2,3]),
            lambda p:p['connections'][0].update(depth=2),
            lambda p:p['rules'][0].update(parts=['missing']),
            lambda p:p['style']['parameters'].update(beam_width=-3),
            lambda p:p['envelope']['volumes'][0].update(polygon=[[2,2],[26,28],[2,28],[26,2]]),
            lambda p:p['envelope']['glazing'][0].update(lo=[15,3,8],hi=[15,4,8]),
        ):
            with self.subTest(modify=modify):
                spec=plan();modify(spec)
                with self.assertRaises(ValueError):dispatch(self.workspace,'plan-build',dict(plan=spec,save_draft={}))
        self.assertFalse((self.workspace/'nbt_models/_drafts').exists())
        self.assertFalse(list(self.workspace.rglob('model-version.json')))

    def test_global_protection_reservation_and_budget_are_not_bypassed_by_scratch(self):
        for key in ('protected_boxes','reserved_boxes'):
            spec=plan();spec['context'][key]=[dict(lo=[11,2,12],hi=[13,4,14])]
            with self.assertRaises(ValueError):dispatch(self.workspace,'plan-build',dict(plan=spec,save_draft={}))
        with self.assertRaises(ValueError):dispatch(self.workspace,'plan-build',dict(plan=plan(),limits=dict(max_changed_positions=20),save_draft={}))
        self.assertFalse(list(self.workspace.rglob('model-version.json')))

    def test_rebuild_preserves_manual_geometry_and_rejects_manual_owned_conflicts(self):
        result=self.make();model=WorkingModel.open(self.workspace,result['saved']['source'])
        model.model.put((18,2,22),'gold_block');revised=model.save_draft()
        rebuilt=dispatch(self.workspace,'plan-build',dict(plan=plan(),source=revised['source'],source_sha256=file_hash(revised['source']),expected_plan_sha256=result['plan_sha256'],save_draft={}))
        self.assertEqual(WorkingModel.open(self.workspace,rebuilt['saved']['source']).model.get((18,2,22)),'minecraft:gold_block')
        model=WorkingModel.open(self.workspace,rebuilt['saved']['source']);model.model.put((11,2,12),'polished_andesite');model.phase='design';model.model.stage='design'
        edited=model.save_draft();before=file_hash(edited['source'])
        with self.assertRaisesRegex(ValueError,'INSTANCE_EDIT_CONFLICT'):
            dispatch(self.workspace,'plan-build',dict(plan=plan(),source=edited['source'],source_sha256=before,expected_plan_sha256=result['plan_sha256'],save_draft={}))
        self.assertEqual(file_hash(edited['source']),before)
        with self.assertRaisesRegex(ValueError,'STALE_SOURCE'):
            dispatch(self.workspace,'plan-build',dict(plan=plan(),source=edited['source'],source_sha256='0'*64,expected_plan_sha256=result['plan_sha256']))

    def synthetic_render(self,prepared):
        # Test transport and binding only; these blank PNGs are not visual evidence.
        from PIL import Image
        from nbt_task import write_snapshot
        directory=self.workspace/prepared['pack'];directory=directory.parent/'synthetic-render'
        directory.mkdir();write_snapshot(Path(prepared['source']),directory/'snapshot.json')
        snapshot=json.loads((directory/'snapshot.json').read_text(encoding='utf8'))
        cameras=json.loads(Path(prepared['cameras']).read_text(encoding='utf8'));images=[]
        for camera in cameras:
            identifier=camera['id'];path=directory/(identifier+'.png');Image.new('RGB',(64,64),(0,0,0)).save(path)
            metadata=dict(id=identifier,image=path.name,image_sha256=file_hash(path),snapshot_sha256=file_hash(directory/'snapshot.json'),requested_view=camera)
            (directory/(identifier+'.json')).write_text(json.dumps(metadata),encoding='utf8')
            images.append(dict(image=path.name,metadata=identifier+'.json',sha256=file_hash(path)))
        manifest=dict(status='complete',source_sha256=snapshot['source_sha256'],geometry_sha256=snapshot['geometry_sha256'],
            cameras_sha256=file_hash(prepared['cameras']),snapshot_file='snapshot.json',snapshot_sha256=file_hash(directory/'snapshot.json'),images=images,width=64,height=64)
        file=directory/'render_manifest.json';file.write_text(json.dumps(manifest),encoding='utf8');return file

    def test_review_records_check_real_file_bindings_and_relocate_without_auto_resolving(self):
        original=self.make();source=original['saved']['source']
        pack=dispatch(self.workspace,'review-prepare',dict(source=source,source_sha256=file_hash(source),output='nbt_models/_workspaces/reviews/fixture'))
        manifest=self.synthetic_render(pack)
        request=dict(pack=pack['pack'],pack_sha256=pack['pack_sha256'],render_manifest=str(manifest),revision=0,
            observations=[dict(image=row['id'],note='Blank transport fixture; no visual judgment.') for row in pack['coverage']['views']],
            issues=[dict(id='pillar-review',layer='structure',part='left',positions=[[11,2,12]],text='Transport fixture; verify relocation only.',images=['beam'])])
        notes=dispatch(self.workspace,'review-record',request)
        self.assertFalse(notes['approval_created']);self.assertTrue(notes['coverage_complete'])
        changed=plan();changed['parts'][2]['recipe']['arguments']['size'][1]=4;changed['parts'][2]['recipe']['arguments']['operations'][0]['hi'][1]=3
        new=dispatch(self.workspace,'plan-build',dict(plan=changed,source=source,source_sha256=file_hash(source),expected_plan_sha256=original['plan_sha256'],save_draft={}))
        compared=dispatch(self.workspace,'review-compare',dict(pack=pack['pack'],pack_sha256=pack['pack_sha256'],notes_sha256=notes['sha256'],source=new['saved']['source'],source_sha256=file_hash(new['saved']['source'])))
        issue=compared['issues'][0]
        self.assertEqual(issue['state'],'needs_new_visual_observation');self.assertFalse(issue['old_positions_are_current'])
        self.assertNotEqual(issue['current_bounds'],issue['previous_bounds'])
        self.assertEqual(file_hash(self.workspace/notes['path']),notes['sha256'])
        meta=manifest.parent/'beam.json';metadata=json.loads(meta.read_text(encoding='utf8'));metadata['snapshot_sha256']='0'*64;meta.write_text(json.dumps(metadata),encoding='utf8')
        with self.assertRaisesRegex(ValueError,'元数据'):dispatch(self.workspace,'review-record',dict(request,revision=1))
        with self.assertRaisesRegex(ValueError,'图像证据'):dispatch(self.workspace,'review-compare',dict(pack=pack['pack'],pack_sha256=pack['pack_sha256'],notes_sha256=notes['sha256'],source=new['saved']['source'],source_sha256=file_hash(new['saved']['source'])))

    def test_actual_extents_and_proportions_detect_manual_geometry_changes(self):
        spec=plan();spec['rules'] += [dict(id='pillar_extent',kind='extent',parts=['left'],expected_size=[3,3,3]),
            dict(id='pillar_ratio',kind='proportion',parts=['left'],numerator_axis='y',denominator_axis='x',minimum=.9,maximum=1.1)]
        result=dispatch(self.workspace,'plan-build',dict(plan=spec,save_draft={}))
        model=WorkingModel.open(self.workspace,result['saved']['source'])
        for x in range(11,14):
            for z in range(12,15):model.model.put((x,2,z),'air')
        from nbt_architecture_plan import check_model
        checks=check_model(model,model.architecture)['checks']
        self.assertFalse(next(row for row in checks if row['id']=='pillar_extent')['passed'])
        self.assertFalse(next(row for row in checks if row['id']=='pillar_ratio')['passed'])
        with self.assertRaises(ValueError):model.validate()

    def test_catalogue_and_workflow_registries_are_consistent(self):
        from nbt_catalog import catalog
        from nbt_architecture import ARCHITECT_ACTIONS
        from nbt_architecture_plan import DESIGN_CHECKS
        contract=catalog()['architecture']
        self.assertEqual(set(contract['actions']),set(ARCHITECT_ACTIONS))
        self.assertEqual(set(contract['plan']['properties']['rules']['items']['properties']['kind']['enum']),set(DESIGN_CHECKS))
        for action in ('plan-save','plan-build'):self.assertEqual(contract['actions'][action]['properties']['plan'],contract['plan'])

    def test_requirements_and_ordered_activities_bind_to_real_geometry(self):
        from nbt_architecture_plan import check_model
        spec = plan()
        spec['requirements'] = [dict(id='display', text='入口旁有可用展陈区', origin='user',
                                     reason='本次展馆用途', spaces=['hall'], parts=['left'])]
        spec['activities'] = [dict(id='visitor', actor='访客', purpose='进入后查看展品', stops=[
            dict(space='hall', feet=[15.5, 2, 8.5]), dict(space='hall', feet=[18.5, 2, 8.5]),
        ])]
        result = dispatch(self.workspace, 'plan-build', dict(plan=spec, save_draft={}))
        model = WorkingModel.open(self.workspace, result['saved']['source'])
        checks = check_model(model, model.architecture)['checks']
        self.assertTrue(next(row for row in checks if row['kind'] == 'activity_routes')['passed'])
        binding = model.architecture
        binding['plan']['activities'][0]['stops'][1]['feet'] = [11.5, 2, 12.5]
        binding['sha256'] = fingerprint(binding['plan'])
        checks = check_model(model, binding)['checks']
        self.assertFalse(next(row for row in checks if row['kind'] == 'activity_routes')['passed'])
        for x in range(11, 14):
            for y in range(2, 5):
                for z in range(12, 15):
                    model.model.put((x, y, z), 'air')
        checks = check_model(model, model.architecture)['checks']
        self.assertFalse(next(row for row in checks if row['kind'] == 'requirement_targets')['passed'])

    def test_invalid_intent_references_fail_before_publication(self):
        for extras in (
            dict(requirements=[dict(id='r', text='用途', origin='user', reason='要求', parts=['missing'])]),
            dict(activities=[dict(id='a', actor='访客', purpose='查看', stops=[
                dict(space='hall', feet=[15.5, 2, 8.5]), dict(space='hall', feet=[28, 2, 8.5])])]),
            dict(review_locations=[dict(id='entry', purpose='门口', position=[14, 3, 1], views=['missing'])]),
        ):
            with self.subTest(extras=extras), self.assertRaises(ValueError):
                normalize(dict(plan(), **extras))
        self.assertFalse(list(self.workspace.rglob('model-version.json')))

    def test_activity_uses_the_rotated_real_face_at_working_height(self):
        from nbt_architecture_intent import check_use_face
        from nbt_collision import _Space
        spec = plan()
        shelf = box_part('desk', [18, 2, 6], [1, 2, 1])
        shelf.update(quarter_turns=1, interfaces=[dict(id='service', face='north', lo=[0, 0, 0], hi=[0, 1, 0])])
        spec['parts'].append(shelf)
        face = dict(part='desk', interface='service', height=1.25, max_distance=2)
        stop = dict(space='hall', feet=[20.5, 2, 6.5], use_face=face)
        spec['activities'] = [dict(id='return', actor='访客', purpose='交卷',
                                   stops=[dict(space='hall', feet=[15.5, 2, 8.5]), stop])]
        draft = dispatch(self.workspace, 'plan-build', dict(plan=spec, save_draft={}))
        model = WorkingModel.open(self.workspace, draft['saved']['source'])
        space = _Space(model.model)
        result = check_use_face(model, model.architecture, space, stop)
        self.assertTrue(result['passed'])
        self.assertEqual((result['face'], result['distance']), ('east', 1.5))
        for feet, reason in [([17.5, 2, 6.5], 'wrong_side'), ([21.5, 2, 6.5], 'too_far'),
                             ([20.5, 2, 8.5], 'outside_working_face')]:
            with self.subTest(feet=feet):
                self.assertEqual(check_use_face(model, model.architecture, space, dict(stop, feet=feet))['reason'], reason)
        for fields, reason in [(dict(height=2.5), 'outside_working_face'),
                               (dict(interface='absent'), 'missing_or_unverified_interface')]:
            self.assertEqual(check_use_face(model, model.architecture, space, dict(stop, use_face=dict(face, **fields)))['reason'], reason)
        model.model.put((19, 3, 6), 'glass')
        self.assertEqual(check_use_face(model, model.architecture, _Space(model.model), stop)['reason'], 'approach_obstructed')

    def test_location_coverage_requires_the_assigned_image_observation(self):
        from nbt_architecture_intent import observed_locations, visible_location
        from nbt_assembly import Volume
        model = Volume([12, 8, 12])
        eye, target = [5.5, 3.5, 1.5], [5.5, 3.5, 8.5]
        self.assertTrue(visible_location(model, eye, target, target, 60)['passed'])
        model.put((5, 3, 5), 'stone')
        self.assertFalse(visible_location(model, eye, target, target, 60)['passed'])
        self.assertFalse(visible_location(model, eye, [10.5, 3.5, 1.5], target, 60)['passed'])
        pack = dict(review_locations=[dict(id='entry', views=['entry_view'],
                    candidates=[dict(view='entry_view', passed=True)])])
        self.assertEqual(observed_locations(pack, [dict(image='entry_view', note='fixture')]), ([], ['entry']))
        covered = [dict(image='entry_view', note='fixture', locations=['entry'])]
        self.assertEqual(observed_locations(pack, covered), (['entry'], []))
        with self.assertRaises(ValueError):
            observed_locations(pack, [dict(image='other', note='fixture', locations=['entry'])])

    def test_declared_openings_update_authored_shell_part_baselines_for_rebuild(self):
        from nbt_assembly import Volume
        from nbt_construction_systems import enclosure
        spec = plan()
        voxels, _ = enclosure(Volume(spec['size']), resolve(spec)['envelope'], 30000)
        palette = sorted({value for value, _ in voxels.values()})
        indices = {value: index for index, value in enumerate(palette)}
        operations = []
        for wall in (False, True):
            rows = [[*position, indices[value]] for position, (value, is_wall) in voxels.items() if is_wall == wall]
            operations.append(dict(kind='paste_component', label='Authored enclosure',
                classification='wall' if wall else 'body', lo=[0,0,0], hi=[27,17,29], palette=palette, voxels=rows))
        spec.pop('envelope')
        spec['connections'] = spec['connections'][:1]
        spec['parts'].insert(0, dict(id='shell', role='envelope', position=[0,0,0],
            interfaces=[dict(id='base',face='down',lo=[2,1,2],hi=[2,1,2])],
            recipe=dict(tool='structure',arguments=dict(name='Authored shell',size=spec['size'],
                anchor=[0,0,0],operations=operations))))
        first = dispatch(self.workspace,'plan-build',dict(plan=spec,save_draft={}))
        source = first['saved']['source']
        model = WorkingModel.open(self.workspace,source)
        carved = [row for row in model.instances['part_shell']['baseline']
                  if 14 <= row['pos'][0] <= 16 and 2 <= row['pos'][1] <= 5 and row['pos'][2] == 1]
        self.assertTrue(carved)
        self.assertTrue(all(row['after'] == ['minecraft:air',False] for row in carved))
        rebuilt = dispatch(self.workspace,'plan-build',dict(plan=spec,source=source,
            source_sha256=file_hash(source),expected_plan_sha256=first['plan_sha256'],save_draft={}))
        self.assertTrue(rebuilt['checks']['architecture']['passed'])

    def test_public_review_flow_tracks_missing_location_observations(self):
        spec = plan()
        spec['views'].append(dict(spec['views'][2], id='second_detail'))
        spec['review_locations'] = [dict(id='hall_operation', purpose='Transport fixture target',
                                        position=[15.65, 3.858, 9], views=['beam'])]
        result = dispatch(self.workspace, 'plan-build', dict(plan=spec, save_draft={}))
        source = result['saved']['source']
        prepared = dispatch(self.workspace, 'review-prepare', dict(source=source,
            source_sha256=file_hash(source), output='nbt_models/_workspaces/reviews/locations'))
        self.assertTrue(prepared['coverage']['review_locations'][0]['passed'])
        manifest = self.synthetic_render(prepared)
        observations = [dict(image=row['id'], note='Blank transport fixture only.')
                        for row in prepared['coverage']['views'] if row['id'] != 'second_detail']
        request = dict(pack=prepared['pack'], pack_sha256=prepared['pack_sha256'],
                       render_manifest=str(manifest), observations=observations, issues=[], revision=0)
        missing = dispatch(self.workspace, 'review-record', request)
        self.assertFalse(missing['coverage_complete'])
        self.assertEqual(missing['missing_locations'], ['hall_operation'])
        self.assertIn('待看 hall_operation', ' '.join(missing['delivery_summary']))
        self.assertIn('机位已记录观察 0/4', ' '.join(prepared['coverage']['delivery_summary']))
        next(row for row in observations if row['image'] == 'beam')['locations'] = ['hall_operation']
        recorded = dispatch(self.workspace, 'review-record', dict(request, revision=1))
        self.assertTrue(recorded['coverage_complete'])
        self.assertFalse(recorded['approval_created'])
        self.assertIn('审阅位置已记录观察 1/1', ' '.join(recorded['delivery_summary']))
        self.assertIn('机位已记录观察 3/4，待看 second_detail', ' '.join(recorded['delivery_summary']))

    def test_scene_policies_survive_plan_rebuild_and_cannot_be_dropped(self):
        spec=plan();part=spec['parts'][2];recipe=deepcopy(part['recipe'])
        part['recipe']=dict(tool='scene_compile',arguments=dict(graph=dict(schema_version=1,name='受保护柱',size=[3,3,3],
            objects=[dict(id='body',lo=[0,0,0],recipe=recipe,interfaces=[dict(id='up',face='up',lo=[0,0,0],hi=[2,2,2])])],
            protected_boxes=[dict(lo=[0,0,0],hi=[2,0,2])],reserved_boxes=[dict(lo=[1,1,1],hi=[1,1,1])])))
        # A reserved box cannot contain the initial solid. Use an empty extension
        # of the component instead, then verify its translated policy later.
        graph=part['recipe']['arguments']['graph'];graph['size']=[4,4,4];graph['reserved_boxes']=[dict(lo=[3,1,1],hi=[3,2,2])]
        first=dispatch(self.workspace,'plan-build',dict(plan=spec,save_draft={}))
        rebuilt=dispatch(self.workspace,'plan-build',dict(plan=spec,source=first['saved']['source'],source_sha256=file_hash(first['saved']['source']),expected_plan_sha256=first['plan_sha256'],save_draft={}))
        model=WorkingModel.open(self.workspace,rebuilt['saved']['source'])
        self.assertTrue(model.architecture['retained_policies'])
        model.model.put((14,3,13),'stone')
        with self.assertRaises(ValueError):model.validate()
        changed=deepcopy(spec);changed['parts'][2]['recipe']['arguments']['graph'].pop('protected_boxes')
        changed['parts'][2]['recipe']['arguments']['graph']['objects'][0]['recipe']['arguments']['operations'][0]['state']='polished_andesite'
        with self.assertRaises(ValueError):dispatch(self.workspace,'plan-build',dict(plan=changed,source=rebuilt['saved']['source'],source_sha256=file_hash(rebuilt['saved']['source']),expected_plan_sha256=rebuilt['plan_sha256']))

    def test_game_observation_records_do_not_create_game_or_export_certification(self):
        result=self.make();source=result['saved']['source'];base=dict(source=source,source_sha256=file_hash(source))
        checklist=dispatch(self.workspace,'game-checklist',base)
        checks=[dict(id=row['id'],state='not_checked',note='No game execution in this test.',evidence=[]) for row in checklist['checks']]
        recorded=dispatch(self.workspace,'game-record',dict(base,runtime_build='test-fixture-only',checks=checks))
        self.assertFalse(recorded['game_execution_witnessed']);self.assertFalse(recorded['approval_created'])
        self.assertTrue((self.workspace/recorded['path']).is_file())
        self.assertFalse((self.workspace/'nbt_models/_exports').exists())

    def test_project_standard_snapshot_is_preserved_without_claiming_text_was_verified(self):
        from nbt_architect import FIELDS
        standard=dispatch(self.workspace,'standards-save',dict(revision=0,fields={key:'石构规范' if key=='name' else '保留本次文字设计依据' for key in FIELDS}))
        spec=plan();spec['standards_snapshot']=standard
        result=dispatch(self.workspace,'plan-build',dict(plan=spec,save_draft={}))
        dispatch(self.workspace,'standards-save',dict(revision=1,fields=dict(standard['fields'],name='新的规范')))
        checked=dispatch(self.workspace,'plan-check',dict(source=result['saved']['source'],source_sha256=file_hash(result['saved']['source'])))
        self.assertEqual(checked['plan']['standards_snapshot']['revision'],1)
        self.assertEqual(checked['validation']['architecture']['textual_standards'],'bound_snapshot_only')
        spec['standards_snapshot']['fields']['style']='未更新哈希'
        with self.assertRaisesRegex(ValueError,'哈希'):normalize(spec)

if __name__=='__main__':unittest.main(verbosity=2)
