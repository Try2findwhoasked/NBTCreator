"""Standalone explicit-aperture/XYZ delivery integration; only synthetic fixtures."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
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
        request=dict(source=str(source),source_sha256=hashlib.sha256(original).hexdigest(),context=str(context),cameras='',settings=settings)
        file=out/'settings.json';write(file,request)
        result=convert_web_json(file);target=Path(result['output'])
        self.assertEqual(result['runtime_parts'],3);self.assertEqual(result['delivery_nbt'],6)
        descriptor=json.loads((target/'room_description.json').read_text(encoding='utf8'))
        self.assertEqual(descriptor['shape'],'l_shape');self.assertEqual({tuple(p) for p in descriptor['cells']},{tuple(p) for p in cells})
        self.assertEqual(verify_standalone(Path(result['release_dir']))['actual_nbt_files'],6);self.assertEqual(source.read_bytes(),original)

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
        model,_,config=room();model.put((15,3,18),'oak_fence')
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
        original=source.read_bytes();file=out/'settings.json';write(file,request)
        first=convert_web_json(file);target=Path(first['output'])
        self.assertEqual(target.name,'v02');self.assertEqual(source.read_bytes(),original)
        self.assertEqual(first['runtime_parts'],1);self.assertEqual(first['delivery_nbt'],2)
        self.assertEqual(json.loads((target/'room_description.json').read_text(encoding='utf8'))['shape'],'standalone')
        self.assertEqual(verify_standalone(Path(first['release_dir']))['source_geometry_sha256'],first['geometry_sha256'])
        job=out/'job';job.mkdir();write(job/'request.json',request);preview=preview_effect(request,job/'result')
        second=convert_web_json(preview['snapshot']);self.assertEqual(Path(second['output']).name,'v03')
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
        result=refine(review,plan,out/'revision')
        self.assertTrue(result['validation_passed']);self.assertEqual(result['delivery_nbt_files'],2)
        self.assertEqual(verify_standalone(out/'revision')['source_geometry_sha256'],result['refined_geometry_sha256'])
        revised,revised_walls=read_master(out/'revision/refined.master.json.gz')
        self.assertIn((2,6,9),revised_walls);self.assertEqual(revised.get((2,6,9)),'minecraft:cracked_stone_bricks')

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
        revised,new_walls=read_master(out/'layer-revision/refined.master.json.gz')
        self.assertEqual(revised.blocks,model.blocks);self.assertEqual(new_walls,walls-{(2,6,9)})
        changes=json.loads((out/'layer-revision/changes.json').read_text(encoding='utf8'))
        self.assertEqual(changes['changes'],[]);self.assertEqual(changes['wall_membership_changed'],[[2,6,9]])
        self.assertEqual(verify_standalone(out/'layer-revision')['source_geometry_sha256'],model.fingerprint())
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
        request['settings']['operations']=[layer_op([2,6,9])];write(file,request)
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
