"""Standalone explicit-aperture/XYZ delivery integration; only synthetic fixtures."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
from shutil import copytree
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_assembly import Volume
from nbt_openings import open_declared_openings
from nbt_refine import save_master,read_master,prepare,record_user_approval,refine,validate,protections
from nbt_model import Model
from nbt_whole_validation import validate_whole
from nbt_standalone_delivery import export_standalone,verify_standalone
from nbt_detail_control import default_settings,preview_effect
from nbt_web_revision import convert_web_json
from nbt_library import register_building,audit_unit
from nbt_finalize import finalize

OUT=ROOT/'build/goal-acceptance-20261103/standalone/fixtures'


def write(file,data):
    file=Path(file);file.parent.mkdir(parents=True,exist_ok=True)
    file.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8')


def room(size=(24,12,28),entry=True):
    model=Volume(size)
    if entry:
        model.box((1,1,0),(size[0]-2,1,size[2]-2),'stone_bricks')
        model.box((2,1,2),(size[0]-3,size[1]-2,size[2]-3),'stone_bricks')
        model.box((3,2,3),(size[0]-4,size[1]-3,size[2]-4),'air')
        walls={p for p in model.blocks if p[1]>1 and (p[0] in (2,size[0]-3) or p[2] in (2,size[2]-3))}
        probes=[[8,4,8]];model.check_sealed(probes)
        openings=[dict(id='entry',lo=[6,2,2],hi=[8,5,2],facing='north')]
        open_declared_openings(model,openings,walls)
        start=[6.5,2,5.5];targets={'outside':[7.5,2,1.5],'inside':[10.5,2,8.5]}
    else:
        model.box((0,0,0),tuple(n-1 for n in size),'stone_bricks')
        model.box((1,1,1),tuple(n-2 for n in size),'air')
        walls={p for p in model.blocks if p[1]>0 and (p[0] in (0,size[0]-1) or p[2] in (0,size[2]-1))}
        probes=[[2,2,2]];model.check_sealed(probes);openings=[]
        start=[2.5,1,2.5];targets={'inside':[4.5,1,3.5]}
    config=dict(mode='standalone',openings=openings,start=start,targets=targets,interior_probes=probes,
                protected_paths=[],protected_boxes=[],max_changed_blocks=32,
                cameras=[dict(role='whole',id='overview',eye=[size[0]+10,size[1]+10,-12],target=[size[0]/2,3,size[2]/2],cuts=[]),
                         dict(role='entry',id='entry',eye=[start[0],start[1]+1.62,start[2]],target=[start[0]+1,start[1]+1,start[2]+3])])
    return model,walls,config


class Standalone(unittest.TestCase):
    def folder(self,name):
        target=OUT/name;target.mkdir(parents=True,exist_ok=False);return target

    def fixture(self,name,size=(24,12,28),entry=True):
        out=self.folder(name);version=out/'nbt_models/standalone/独立测试/v01';(version/'master').mkdir(parents=True)
        model,walls,config=room(size,entry)
        source=version/'master/master_geometry.json.gz';save_master(source,model,walls)
        context=version/'coordinates.json';write(context,config)
        register_building(source,'独立测试',mode='standalone')
        settings=default_settings();settings['max_changed_blocks']=32
        settings['operations']=[dict(kind='box',label='Synthetic wall edit',classification='inherit',lo=[2,6,9] if entry else [0,2,2],hi=[2,6,9] if entry else [0,2,2],state='cracked_stone_bricks')]
        request=dict(source=str(source),source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),context=str(context),cameras='',settings=settings)
        return out,model,walls,config,source,request

    def test_non48_small_closed_building_and_explicit_custom_entry(self):
        for size,entry,name in [((24,12,28),True,'custom'),((8,6,7),False,'small')]:
            model,walls,config=room(size,entry);before=model.fingerprint()
            report=validate_whole(model,config)
            self.assertTrue(report['passed']);self.assertEqual(report['mode'],'standalone')
            self.assertFalse(report['original_preopening_proof']);self.assertEqual(model.fingerprint(),before)
            if entry:self.assertIn((7,2,2),protections(model,config))
            model.seal_record=report['recapped_seal'];model.final_fingerprint=model.fingerprint()
            exported=export_standalone(model,walls,self.folder(name),file_prefix='2026-11-03_test_')
            self.assertEqual(exported['runtime_parts'],1);self.assertEqual(exported['actual_nbt_files'],2)

    def test_large_xyz_tiles_real_edge_dimensions_and_exact_reassembly(self):
        model,walls,config=room((55,52,50),False);report=validate(model,config)
        model.seal_record=report['recapped_seal'];model.final_fingerprint=model.fingerprint()
        out=self.folder('large');result=export_standalone(model,walls,out)
        self.assertEqual(result['runtime_parts'],8);self.assertEqual(result['actual_nbt_files'],16)
        parts=json.loads((out/'runtime/parts.json').read_text())['parts']
        edge=next(p for p in parts if p['index']==[1,1,1]);self.assertEqual(edge['size'],[7,4,2]);self.assertEqual(edge['offset'],[48,48,48])
        self.assertEqual(verify_standalone(out)['source_geometry_sha256'],model.fingerprint())
        with self.assertRaises(FileExistsError):export_standalone(model,walls,out)

    def test_explicit_standalone_l_footprint_omits_missing_corner_and_preserves_metadata(self):
        cells=[[0,0],[1,0],[0,1]];model=Volume((96,8,96))
        for cx,cz in cells:
            x,z=cx*48,cz*48
            model.box((x,0,z),(x+47,7,z+47),'stone_bricks')
            model.box((x+1,1,z+1),(x+46,6,z+46),'air')
        model.box((47,1,23),(48,4,25),'air')
        model.box((23,1,47),(25,4,48),'air')
        walls={p for p in model.blocks if p[1] not in (0,7)}
        config=dict(mode='standalone',cells=cells,openings=[],start=[45.5,1,24.5],
            targets={'east':[51.5,1,24.5],'south':[24.5,1,51.5]},
            interior_probes=[[24,3,24],[72,3,24],[24,3,72]])
        checks=validate_whole(model,config);self.assertTrue(checks['passed'])
        model.seal_record=checks['recapped_seal'];model.final_fingerprint=model.fingerprint()
        out=self.folder('l-footprint');direct=out/'direct'
        exported=export_standalone(model,walls,direct,active_cells=cells)
        self.assertEqual(exported['runtime_parts'],3);self.assertEqual(exported['actual_nbt_files'],6)
        manifest=json.loads((direct/'runtime/parts.json').read_text())
        self.assertEqual({tuple(p['index']) for p in manifest['parts']},{(0,0,0),(1,0,0),(0,0,1)})
        self.assertEqual({tuple(p) for p in manifest['active_cells']},{tuple(p) for p in cells})
        self.assertEqual(verify_standalone(direct)['source_geometry_sha256'],model.fingerprint())
        invalid=copy.deepcopy(model);invalid.begin_redesign();invalid.put((60,1,60),'stone')
        with self.assertRaisesRegex(ValueError,'excluded footprint'):validate_whole(invalid,config)
        with self.assertRaisesRegex(ValueError,'four-neighbour'):validate_whole(model,dict(config,cells=[[0,0],[1,1]]))
        with self.assertRaisesRegex(ValueError,'out-of-bounds'):validate_whole(model,dict(config,cells=[[2,0]]))
        version=out/'nbt_models/l_shape/独立L/v01';(version/'master').mkdir(parents=True)
        source=version/'master/master_geometry.json.gz';save_master(source,model,walls);original=source.read_bytes()
        context=version/'coordinates.json';write(context,config);register_building(source,'独立L',cells,mode='standalone')
        settings=default_settings();settings['operations']=[dict(kind='box',label='Synthetic L wall edit',classification='inherit',lo=[0,3,10],hi=[0,3,10],state='cracked_stone_bricks')]
        request=dict(source=str(source),source_sha256=hashlib.sha256(original).hexdigest(),context=str(context),cameras='',settings=settings,draft_only=False)
        file=out/'settings.json';write(file,request)
        result=convert_web_json(file);target=Path(result['output'])
        self.assertEqual(result['runtime_parts'],3);self.assertEqual(result['delivery_nbt'],6)
        descriptor=json.loads((target/'room_description.json').read_text(encoding='utf8'))
        self.assertEqual(descriptor['shape'],'l_shape');self.assertEqual({tuple(p) for p in descriptor['cells']},{tuple(p) for p in cells})
        self.assertEqual(verify_standalone(Path(result['release_dir']))['actual_nbt_files'],6);self.assertEqual(source.read_bytes(),original)

    def test_custom_footprint_survives_coordinate_loading_and_final_delivery(self):
        from nbt_detail_control import normalize_context
        from nbt_finalize import export_binary

        for stride, offsets in [(32, {0,32}), (64, {0,48,64,112})]:
            with self.subTest(stride=stride):
                model = Volume((stride*2, 4, stride))
                model.box((0,0,0),(stride*2-1,0,2),'stone')
                context = dict(mode='standalone', cells=[[0,0],[1,0]], cell_size=stride,
                               require_enclosure=False, start=[1.5,1,1.5],
                               targets={'other_cell':[stride+0.5,1,1.5]}, allow_empty_wall_mask=True)
                output = self.folder(f'custom-grid-{stride}')
                config_file = output/'coordinates.json'
                write(config_file, context)
                config = normalize_context(model, config_file, None, default_settings())
                self.assertEqual(config['cell_size'], stride)
                validated = validate_whole(model, config)
                result = export_binary(model, set(), config, validated, output/'export')
                self.assertTrue(result['binary_roundtrip'])
                packet = verify_standalone(output/'export')
                self.assertEqual(packet['cell_size'], stride)
                self.assertEqual({part['offset'][0] for part in packet['parts']}, offsets)
                self.assertTrue(all(max(part['size']) <= 48 for part in packet['parts']))
                excluded = Volume((stride*2, 4, stride*2))
                excluded.put((stride,0,stride),'stone')
                with self.assertRaisesRegex(ValueError, 'excluded footprint'):
                    validate_whole(excluded,dict(config,cells=[[0,0],[1,0],[0,1]]))

    def test_unknown_mode_leak_missing_declaration_and_missing_targets_refuse(self):
        model,walls,config=room();before=model.fingerprint()
        bad=copy.deepcopy(config);bad['mode']='unknown'
        with self.assertRaises(ValueError):validate(model,bad)
        bad=copy.deepcopy(config);bad.pop('openings')
        with self.assertRaises(ValueError):validate(model,bad)
        bad=copy.deepcopy(config);bad['ports']=None
        with self.assertRaisesRegex(ValueError,'uses openings'):validate(model,bad)
        bad=copy.deepcopy(config);bad['targets']={}
        with self.assertRaises(ValueError):validate(model,bad)
        with self.assertRaisesRegex(ValueError,'non-empty required route targets'):
            validate(model,dict(mode='saodg',targets={}))
        model.put((2,6,12),'air')
        with self.assertRaises(AssertionError):validate(model,config)
        self.assertNotEqual(model.fingerprint(),before)

    def test_unsupported_shape_and_required_connection_failure_are_not_hidden(self):
        model,_,config=room();model.put((15,3,18),'anvil')
        with self.assertRaisesRegex(ValueError,'route validation failed'):validate(model,config)
        model,_,config=room();config['route_legs']=[dict(name='blocked entry connection',start=config['start'],targets={'outside':config['targets']['outside']},validation_only_barriers=[dict(lo=[6,2,2],hi=[8,5,2])])]
        with self.assertRaisesRegex(ValueError,'Required standalone route leg failed'):validate(model,config)

    def test_empty_wall_mask_is_explicit_and_not_assumed(self):
        model,_,config=room((8,6,7),False);checks=validate(model,config);model.seal_record=checks['recapped_seal'];model.final_fingerprint=model.fingerprint()
        with self.assertRaises(ValueError):export_standalone(model,set(),OUT/'no-empty-policy')
        out=self.folder('explicit-empty');result=export_standalone(model,set(),out,allow_empty_wall_mask=True)
        self.assertTrue(result['delivery']['parts'][0]['empty_wall_layer'])
        self.assertEqual(verify_standalone(out)['actual_nbt_files'],2)
        with self.assertRaises(ValueError):export_standalone(model,{(3,3,3)},OUT/'air-wall')

    def test_verifier_rejects_stale_extra_nbt_and_changed_wall_declaration(self):
        model,walls,config=room((8,6,7),False);report=validate(model,config)
        model.seal_record=report['recapped_seal'];model.final_fingerprint=model.fingerprint()
        out=self.folder('verifier');export_standalone(model,walls,out)
        manifest=out/'delivery/delivery.json';original=manifest.read_bytes();data=json.loads(original)
        data['parts'][0]['empty_wall_layer']=True;write(manifest,data)
        with self.assertRaisesRegex(ValueError,'empty-wall'):verify_standalone(out)
        manifest.write_bytes(original)
        runtime_file=next((out/'runtime/parts').glob('*.nbt'));extra=out/'runtime/parts/stale'/runtime_file.name
        extra.parent.mkdir();extra.write_bytes(runtime_file.read_bytes())
        with self.assertRaisesRegex(ValueError,'Extra/missing runtime'):verify_standalone(out)

    def test_manual_converter_preview_and_next_version_preserve_source_and_metadata(self):
        out,model,walls,config,source,request=self.fixture('convert')
        original=source.read_bytes();file=out/'settings.json';write(file,dict(request,draft_only=False))
        first=convert_web_json(file);target=Path(first['output'])
        self.assertEqual(target.name,'v02');self.assertEqual(source.read_bytes(),original)
        self.assertEqual(first['runtime_parts'],1);self.assertEqual(first['delivery_nbt'],2)
        self.assertEqual(json.loads((target/'room_description.json').read_text(encoding='utf8'))['shape'],'standalone')
        self.assertEqual(verify_standalone(Path(first['release_dir']))['source_geometry_sha256'],first['geometry_sha256'])
        with self.assertRaisesRegex(ValueError,'STALE_PARENT'):convert_web_json(file)
        current=dict(request,source=first['master'],source_sha256=hashlib.sha256(Path(first['master']).read_bytes()).hexdigest(),
            context=str(target/'coordinates.json'),cameras=str(target/'cameras.json'))
        job=out/'job';job.mkdir();write(job/'request.json',current);preview=preview_effect(current,job/'result')
        second=convert_web_json(preview['snapshot']);self.assertEqual(Path(second['output']).name,'v03')
        self.assertTrue(second['draft_only']);self.assertEqual(second['delivery_nbt'],0)
        self.assertFalse(list(Path(second['output']).rglob('*.nbt')))
        self.assertFalse(list(target.rglob('approval.json')))
        result=audit_unit(target,[target/'master/model.snbt'],{},{});self.assertTrue(result['valid'],result)

    def test_synthetic_refine_protects_aperture_and_keeps_whole_revision(self):
        out,model,walls,config,source,request=self.fixture('refine')
        review=out/'review';prepare(source,config,review)
        plan=dict(style_note='Synthetic only',operations=request['settings']['operations'])
        with self.assertRaises(PermissionError):refine(review,plan,out/'not-approved')
        record_user_approval(review,'SYNTHETIC FIXTURE ONLY: test images checked, allow this synthetic test revision.',True)
        bad=dict(style_note='Synthetic only',operations=[dict(kind='box',label='block doorway',lo=[7,2,2],hi=[7,2,2],state='stone')])
        with self.assertRaisesRegex(ValueError,'protected'):refine(review,bad,out/'protected')
        revision=source.parent.parent.parent/'refined_v01'
        result=refine(review,plan,revision)
        self.assertTrue(result['validation_passed'])
        self.assertEqual(Path(result['master']),revision/'master/model.snbt')
        self.assertFalse(list(out.rglob('*.nbt')))
        released=finalize(out,result['master'],register_history=False)
        self.assertEqual(released['delivery_nbt'],2)
        self.assertEqual(verify_standalone(released['output'])['source_geometry_sha256'],result['refined_geometry_sha256'])
        revised,revised_walls=read_master(result['master'])
        self.assertIn((2,6,9),revised_walls);self.assertEqual(revised.get((2,6,9)),'minecraft:cracked_stone_bricks')

    def test_binary_source_wall_sidecar_is_bound_to_refinement_review(self):
        from nbt_snbt import write_binary

        out,model,walls,config,_,request=self.fixture('refine-wall-binding')
        source=out/'source/model.nbt'
        write_binary(source,model,walls)
        review=out/'review'
        prepare(source,config,review)
        record_user_approval(review,'Synthetic review for this test fixture only',True)
        sidecar=source.with_name('wall_mask.json')
        metadata=json.loads(sidecar.read_text(encoding='utf8'))
        metadata['wall_positions'].pop()
        write(sidecar,metadata)
        plan=dict(style_note='只换材',operations=request['settings']['operations'])
        with self.assertRaisesRegex(ValueError,'wall mask changed'):
            refine(review,plan,out/'revised')
        self.assertFalse((out/'revised').exists())

    def test_layer_only_refine_obeys_protection_budget_and_records_real_membership(self):
        out,model,walls,config,source,request=self.fixture('layer-refine')
        original=source.read_bytes();config['max_changed_blocks']=1
        review=out/'review';prepare(source,config,review)
        record_user_approval(review,'SYNTHETIC FIXTURE ONLY: verify layer-change policy in this synthetic model.',True)
        def layer_op(p):return dict(kind='box',label='Synthetic classification-only change',classification='body',lo=p,hi=p,state='stone_bricks')
        protected_plan=dict(style_note='Synthetic only',operations=[layer_op([5,3,2])])
        with self.assertRaisesRegex(ValueError,'保护区'):refine(review,protected_plan,out/'protected-layer')
        excessive=dict(style_note='Synthetic only',operations=[layer_op([2,6,9]),layer_op([2,6,10])])
        with self.assertRaisesRegex(ValueError,'超过上限'):refine(review,excessive,out/'excessive-layer')
        good=dict(style_note='Synthetic only',operations=[layer_op([2,6,9])])
        result=refine(review,good,out/'layer-revision')
        self.assertEqual(result['changed_blocks'],0);self.assertEqual(result['wall_membership_changes'],1);self.assertEqual(result['changed_positions'],1)
        revised,new_walls=read_master(result['master'])
        self.assertEqual(revised.blocks,model.blocks);self.assertEqual(new_walls,walls-{(2,6,9)})
        changes=json.loads((out/'layer-revision/changes.json').read_text(encoding='utf8'))
        self.assertEqual(changes['changes'],[]);self.assertEqual(changes['wall_membership_changed'],[[2,6,9]])
        self.assertEqual(result['refined_geometry_sha256'],model.fingerprint())
        self.assertFalse(list((out/'layer-revision').rglob('*.nbt')))
        self.assertFalse((out/'protected-layer').exists());self.assertFalse((out/'excessive-layer').exists());self.assertEqual(source.read_bytes(),original)

    def test_layer_only_manual_conversion_rejects_budget_and_preserves_legitimate_layer_change(self):
        out,model,walls,config,source,request=self.fixture('layer-convert')
        original=source.read_bytes();request['settings']['max_changed_blocks']=1
        def layer_op(p):return dict(kind='box',label='Synthetic classification-only change',classification='body',lo=p,hi=p,state='stone_bricks')
        request['settings']['operations']=[layer_op([2,6,9]),layer_op([2,6,10])]
        file=out/'settings.json';write(file,request)
        with self.assertRaisesRegex(ValueError,'超过上限'):convert_web_json(file)
        self.assertFalse((source.parent.parent.parent/'v02').exists())
        request['settings']['operations']=[layer_op([5,3,2])];write(file,request)
        with self.assertRaisesRegex(ValueError,'保护区'):convert_web_json(file)
        request['settings']['operations']=[layer_op([2,6,9])];write(file,dict(request,draft_only=False))
        result=convert_web_json(file);target=Path(result['output'])
        self.assertEqual(result['changed_blocks'],0);self.assertEqual(result['wall_membership_changes'],1);self.assertEqual(result['changed_positions'],1)
        revised,new_walls=read_master(target/'master/model.snbt')
        self.assertEqual(revised.blocks,model.blocks);self.assertEqual(new_walls,walls-{(2,6,9)})
        changes=json.loads((target/'changes.json').read_text(encoding='utf8'))
        self.assertEqual(changes['wall_membership_changed'],[[2,6,9]])
        self.assertEqual(source.read_bytes(),original);self.assertTrue(verify_standalone(Path(result['release_dir']))['exact_solid_reconstruction'])

    def test_nbt_source_explicit_mask_is_baseline_not_a_mass_layer_change(self):
        out,model,walls,config,gzip_source,request=self.fixture('nbt-mask-baseline')
        source=gzip_source.with_name('explicit-source.nbt')
        bounded=Model(model.size);bounded.blocks=dict(model.blocks);bounded.seal_record=model.seal_record;bounded.stage='opened';bounded.final_fingerprint=bounded.fingerprint();bounded.save(source)
        original=source.read_bytes();config['wall_positions']=[list(p) for p in sorted(walls)];write(request['context'],config)
        request.update(source=str(source),source_sha256=hashlib.sha256(source.read_bytes()).hexdigest())
        request['settings'].update(operations=[],max_changed_blocks=1)
        file=out/'settings.json';write(file,request)
        result=convert_web_json(file);target=Path(result['output'])
        self.assertEqual(result['changed_blocks'],0);self.assertEqual(result['wall_membership_changes'],0);self.assertEqual(result['changed_positions'],0)
        revised,new_walls=read_master(target/'master/model.snbt')
        self.assertEqual(revised.blocks,model.blocks);self.assertEqual(new_walls,walls);self.assertEqual(source.read_bytes(),original)

    def test_next_version_uses_new_wall_assignment_when_legacy_context_had_a_mask(self):
        from nbt_working_model import WorkingModel

        out,model,walls,config,source,request=self.fixture('legacy-mask-update')
        config['floor_context']=dict(wall_positions=[list(p) for p in sorted(walls)])
        write(request['context'],config)
        changed_wall=(2,6,9)
        request['settings']['operations']=[dict(kind='box',label='Test layer update',classification='body',
            lo=list(changed_wall),hi=list(changed_wall),state=model.get(changed_wall))]
        file=out/'settings.json';write(file,request)
        result=convert_web_json(file)
        revised=WorkingModel.open(out,result['master'])
        self.assertEqual(revised.walls,walls-{changed_wall})
        release=finalize(out,result['master'],register_history=False)
        self.assertEqual(read_master(release['nbt_master'])[1],revised.walls)

    def test_selecting_alternate_legacy_context_keeps_saved_protection_and_budget(self):
        out,_,_,config,source,request=self.fixture('legacy-context')
        reserved=[dict(lo=[10,2,10],hi=[10,2,10])]
        write(request['context'],dict(config,max_changed_blocks=1,reserved_boxes=reserved))
        alternate=out/'selected-context.json'
        write(alternate,dict(config,max_changed_blocks=100))
        request['context']=str(alternate)
        edit=dict(kind='box',label='Synthetic constrained edit',classification='body',state='stone')
        file=out/'settings.json'
        request['settings']['operations']=[dict(edit,lo=[10,2,10],hi=[10,2,10])]
        write(file,request)
        with self.assertRaisesRegex(ValueError,'RESERVED_SPACE'):
            convert_web_json(file)
        request['settings']['operations']=[dict(edit,lo=[13,2,10],hi=[14,2,10])]
        write(file,request)
        with self.assertRaisesRegex(ValueError,'超过上限'):
            convert_web_json(file)
        request['settings']['operations']=[dict(edit,lo=[13,2,10],hi=[13,2,10])]
        write(file,request)
        saved=convert_web_json(file)
        next_config=json.loads((Path(saved['output'])/'coordinates.json').read_text(encoding='utf8'))
        self.assertEqual(next_config['reserved_boxes'],reserved)
        self.assertEqual(next_config['max_changed_blocks'],1)
        self.assertTrue(source.is_file())

    def test_replacing_legacy_context_keeps_openings_enclosure_and_required_routes(self):
        from nbt_candidate import validate_candidate
        from nbt_detail_control import context_readiness,inspect_source
        from nbt_library import saved_coordinates_hash

        out,_,_,config,source,request=self.fixture('legacy-geometry-context')
        version=source.parents[1]
        original=source.with_name('config.json')
        Path(request['context']).rename(original)
        config['route_legs']=[dict(name='后厅路线',start=config['start'],targets={'far':[7.5,2,15.5]})]
        config['max_changed_blocks']=512
        write(original,config)
        info=inspect_source(source,0)
        self.assertTrue(info['editing_ready'])
        self.assertEqual(Path(info['context']),original)
        self.assertEqual(saved_coordinates_hash(source),hashlib.sha256(original.read_bytes()).hexdigest())
        alternate=out/'selected-context.json'
        # The nested legacy form must not override retained constraints when re-read.
        write(alternate,dict(mode='standalone',floor_context=dict(require_enclosure=False,openings=[],
            start=config['start'],targets={'near':[7.5,2,6.5]},route_legs=[]),cameras=config['cameras']))
        request['context']=str(alternate)
        request['settings']['max_changed_blocks']=512
        settings=out/'settings.json'
        source_bytes=source.read_bytes()

        edit=dict(kind='box',classification='body',state='stone_bricks')
        request['settings']['operations']=[dict(edit,label='封堵入口',lo=[6,2,2],hi=[8,5,2])]
        write(settings,request)
        with self.assertRaisesRegex(ValueError,'封堵入口'):
            convert_web_json(settings)

        for label,lo,hi,state,error in (
                ('外墙破损',[2,6,9],[2,6,9],'air','Exterior leak'),
                ('阻断后厅',[3,2,13],[20,9,13],'stone_bricks','Required standalone route leg failed')):
            with self.subTest(label=label):
                request['settings']['operations']=[dict(edit,label=label,lo=lo,hi=hi,state=state)]
                preview=preview_effect(request,out/label)
                check=validate_candidate(request,preview['snapshot'],out/(label+'校验'))
                self.assertFalse(check['passed'],check)
                self.assertIn(error,check['checks']['candidate_geometry']['error'])
                write(settings,request)
                with self.assertRaisesRegex((ValueError,AssertionError),error):
                    convert_web_json(settings)
        self.assertEqual([entry for entry in version.parent.iterdir() if entry.is_dir()],[version])

        write(alternate,dict(cameras=config['cameras']))
        self.assertTrue(context_readiness(read_master(source)[0],alternate,source)['ready'])
        request['settings']['operations']=[dict(edit,label='更新外墙表面',
            lo=[2,6,9],hi=[2,6,9],state='cracked_stone_bricks',classification='inherit')]
        write(settings,request)
        saved=convert_web_json(settings)
        next_config=json.loads((Path(saved['output'])/'coordinates.json').read_text(encoding='utf8'))
        for field in ('openings','interior_probes','start','targets','route_legs'):
            self.assertEqual(next_config[field],config[field])
        self.assertTrue(next_config['require_enclosure'])
        self.assertEqual(source.read_bytes(),source_bytes)

    def test_legacy_context_discovery_prefers_version_root_and_stays_inside_it(self):
        from nbt_detail_control import catalog,inspect_source
        from nbt_library import saved_coordinates,saved_coordinates_hash

        out,_,_,config,source,request=self.fixture('legacy-context-priority')
        version=source.parents[1]
        Path(request['context']).unlink()
        root_file=version/'context.json'
        adjacent=source.with_name('coordinates.json')
        write(root_file,config)
        write(adjacent,dict(config,targets={'near':config['start']}))
        write(version.parent/'coordinates.json',config)
        write(out/'coordinates.json',config)
        self.assertEqual(saved_coordinates(source),root_file)
        self.assertEqual(Path(inspect_source(source,0)['context']),root_file)
        item=next(item for item in catalog(out)['models'] if Path(item['source'])==source)
        self.assertEqual(Path(item['context']),root_file)
        self.assertEqual(saved_coordinates_hash(source),hashlib.sha256(root_file.read_bytes()).hexdigest())
        root_file.unlink()
        self.assertEqual(saved_coordinates(source),adjacent)
        self.assertEqual(Path(inspect_source(source,0)['context']),adjacent)
        adjacent.unlink()
        self.assertIsNone(saved_coordinates(source))
        self.assertFalse(inspect_source(source,0)['editing_ready'])
        metadata=version/'room_description.json'
        description=json.loads(metadata.read_text(encoding='utf8'))
        write(metadata,dict(description,context_file='../coordinates.json'))
        self.assertIsNone(saved_coordinates(source))
        custom=version/'legacy-layout/constraints.json'
        write(custom,config)
        write(metadata,dict(description,context_file=custom.relative_to(version).as_posix()))
        self.assertEqual(saved_coordinates(source),custom)
        self.assertTrue(inspect_source(source,0)['editing_ready'])

    def test_finalize_packages_the_effective_legacy_context_for_portable_readback(self):
        from nbt_detail_control import inspect_source
        from nbt_library import canonical_context

        for name,adjacent in (('context.json',False),('config.json',True)):
            with self.subTest(name=name,adjacent=adjacent):
                out,model,_,config,source,request=self.fixture('release-'+name)
                version=source.parents[1]
                old_path=(source.parent if adjacent else version)/name
                Path(request['context']).unlink()
                probes=config.pop('interior_probes')
                write(old_path,config)
                evidence=old_path.with_name('validation.json')
                write(evidence,dict(sealed_before_opening=dict(passed=True,probes=probes)))
                original_description=version/'room_description.json'
                description=json.loads(original_description.read_text(encoding='utf8'))
                write(original_description,dict(description,context_file=old_path.relative_to(version).as_posix()))
                original={file:file.read_bytes() for file in (old_path,evidence,original_description,source)}

                release=finalize(out,source,register_history=False)
                exported=Path(release['output'])
                expected_hash=hashlib.sha256((exported/'coordinates.json').read_bytes()).hexdigest()
                self.assertEqual(release['files']['coordinates.json']['sha256'],expected_hash)
                self.assertTrue(finalize(out,source,register_history=False)['unchanged'])
                self.assertEqual({file:file.read_bytes() for file in original},original)
                evidence.write_bytes(original[evidence]+b'\n')
                with self.assertRaisesRegex(ValueError,'坐标配置已变化'):
                    finalize(out,source,register_history=False)
                evidence.write_bytes(original[evidence])

                moved=out/'便携交付'
                copytree(exported,moved)
                description=json.loads((moved/'room_description.json').read_text(encoding='utf8'))
                self.assertEqual(description['context_file'],'coordinates.json')
                moved_context=moved/description['context_file']
                point_config=canonical_context(moved_context)
                self.assertEqual(point_config['interior_probes'],probes)
                self.assertTrue(inspect_source(moved/description['master'],0)['editing_ready'])
                readback,_=read_master(moved/description['master'])
                self.assertEqual(readback.blocks,model.blocks)
                self.assertTrue(validate_whole(readback,point_config)['routes']['passed'])
                self.assertEqual(verify_standalone(moved)['source_geometry_sha256'],model.fingerprint())
                with (exported/'coordinates.json').open('ab') as file:file.write(b'\n')
                with self.assertRaisesRegex(ValueError,'交付缺失或被修改'):
                    finalize(out,source,register_history=False)

    def test_legacy_working_copy_rejects_changed_recovered_probe_evidence(self):
        from nbt_working_model import WorkingModel

        out,_,_,source_config,source,request=self.fixture('legacy-stale-probe')
        probes=source_config.pop('interior_probes')
        write(request['context'],source_config)
        proof=source.parents[1]/'validation.json'
        write(proof,dict(before_opening=dict(passed=True,probes=probes)))
        alternate=out/'cameras-only.json'
        write(alternate,dict(cameras=source_config['cameras']))
        model=WorkingModel.open(out,source,alternate)
        self.assertEqual(model.validate()['whole_model']['recapped_seal']['probes'],probes)
        write(proof,dict(before_opening=dict(passed=True,probes=[[9,4,9]])))
        with self.assertRaisesRegex(ValueError,'STALE_CONTEXT'):
            model.save_draft()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path);args,remaining=parser.parse_known_args()
    if args.output:OUT=args.output.resolve()
    OUT.mkdir(parents=True,exist_ok=False)
    program=unittest.main(argv=[sys.argv[0],*remaining],verbosity=2,exit=False)
    result=program.result
    write(OUT/'results.json',dict(passed=result.wasSuccessful(),tests=result.testsRun,
                                  failures=[dict(test=str(test),detail=detail) for test,detail in result.failures],
                                  errors=[dict(test=str(test),detail=detail) for test,detail in result.errors],
                                  scope='Synthetic standalone workflow fixtures only; no actual user approval or game acceptance'))
    raise SystemExit(0 if result.wasSuccessful() else 1)
