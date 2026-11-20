"""Exact preview/request binding and whole-candidate acceptance; synthetic inputs only."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_model import Model, ports
from nbt_refine import save_master
from nbt_detail_control import default_settings,preview_effect,digest
from nbt_candidate import validate_candidate
from nbt_detail_control import inspect_source,source_snapshot
from nbt_refine import prepare,record_user_approval,refine
from nbt_detail_control import catalog


def make_fixture(directory):
    directory=Path(directory).resolve();directory.mkdir(parents=True,exist_ok=True)
    source=directory/'master/master_geometry.json.gz';source.parent.mkdir()
    model=Model((48,16,48));model.box((0,0,0),(47,15,47),'stone_bricks');model.box((1,2,1),(46,14,46),'air')
    model.check_sealed([(24,3,24)]);model.open_ports(ports(['north'],2),2)
    walls={p for p in model.blocks if p[0] in (0,47) or p[2] in (0,47)}
    save_master(source,model,walls)
    context=dict(cells=[[0,0]],ports=ports(['north'],2),door_y=2,start=[24.5,2,1.5],targets={'end':[24.5,2,42.5]},interior_probes=[[24,3,24]],
                 protected_boxes=[dict(lo=[10,1,10],hi=[12,5,12])],protected_paths=[],
                 cameras=[dict(id='overview',role='whole',eye=[70,40,-30],target=[24,5,24],cuts=[dict(axis='y',position=13,removed_side='above')]),
                          dict(id='entry',role='entry',eye=[24.5,3.62,1.5],target=[24.5,4,20])])
    (directory/'coordinates.json').write_text(json.dumps(context),encoding='utf8')
    settings=default_settings();settings['style_note']='Synthetic candidate check';settings['operations']=[dict(kind='box',label='bounded pillar',lo=[8,2,8],hi=[8,4,8],state='stone_bricks',classification='body')]
    request=dict(source=str(source),source_sha256=digest(source),context=str(directory/'coordinates.json'),settings=settings,cameras='')
    (directory/'request.json').write_text(json.dumps(request),encoding='utf8')
    (directory/'room_description.json').write_text(json.dumps(dict(name_zh='候选检查测试',shape='single',display_name='候选检查测试-单格',master='master/master_geometry.json.gz',size=[48,16,48],cells=[[0,0]],audit=dict(compliant=True))),encoding='utf8')
    return request


class Candidate(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='nbt-candidate-test-');self.root=Path(self.temp.name).resolve()
        self.request=make_fixture(self.root);self.source=Path(self.request['source']);self.hash=digest(self.source)
    def tearDown(self):
        self.assertEqual(digest(self.source),self.hash);self.temp.cleanup()
    def preview(self,request=None):return preview_effect(request or self.request,self.root/'preview')
    def check(self,request=None,snapshot=None):
        return validate_candidate(request or self.request,snapshot or self.root/'preview/after.json',self.root/'checked')
    def test_valid_candidate_has_report_and_no_asset_or_approval(self):
        self.preview();result=self.check();self.assertTrue(result['passed'],result)
        self.assertEqual(result['changed_blocks'],3)
        self.assertEqual({p.name for p in (self.root/'checked').iterdir()},{'validation.json'})
        record=json.loads(Path(result['validation']).read_text())
        self.assertTrue(record['checks']['candidate_geometry']['details']['routes']['passed'])
        self.assertFalse(result['approval_created']);self.assertFalse(result['asset_written'])
    def test_changed_settings_and_budget_cannot_reuse_prior_success(self):
        self.preview();self.request['settings']['max_changed_blocks']=2
        result=self.check();self.assertFalse(result['passed']);self.assertFalse(result['checks']['change_budget']['passed'])
        issue=next(item for item in result['diagnostics']['issues'] if item['code']=='candidate_change_budget');self.assertIsNone(issue['bounds']);self.assertFalse(issue['automatic_repair']);self.assertEqual(result['diagnostics']['source_sha256'],self.hash)
    def test_stale_parameters_reject_exact_snapshot(self):
        self.preview();self.request['settings']['operations'][0]['state']='gold_block'
        result=self.check();self.assertFalse(result['passed']);self.assertFalse(result['checks']['preview_matches_request']['passed'])
    def test_candidate_that_blocks_route_is_not_just_planned(self):
        self.request['settings']['operations']=[dict(kind='box',label='blocked corridor',lo=[1,2,20],hi=[46,14,20],state='stone_bricks',classification='body')]
        self.preview();result=self.check();self.assertFalse(result['passed']);self.assertTrue(result['checks']['baseline_geometry']['passed']);self.assertFalse(result['checks']['candidate_geometry']['passed'])
    def test_candidate_that_leaks_is_rejected(self):
        self.request['settings']['operations']=[dict(kind='box',label='wall leak',lo=[0,8,30],hi=[0,8,30],state='air',classification='wall')]
        self.preview();result=self.check();self.assertFalse(result['passed']);self.assertFalse(result['checks']['candidate_geometry']['passed'])
    def test_changed_protection_refuses_candidate_without_removing_it(self):
        self.preview();context=json.loads(Path(self.request['context']).read_text());context['protected_boxes'].append(dict(lo=[8,2,8],hi=[8,4,8]));Path(self.request['context']).write_text(json.dumps(context))
        result=self.check();self.assertFalse(result['passed']);self.assertFalse(result['checks']['protected_geometry']['passed'])
    def test_legacy_candidate_checks_saved_budget_and_reserved_space(self):
        context=Path(self.request['context'])
        config=json.loads(context.read_text())
        self.preview()
        config.update(max_changed_blocks=1,reserved_boxes=[dict(lo=[8,2,8],hi=[8,2,8])])
        context.write_text(json.dumps(config),encoding='utf8')
        result=self.check()
        self.assertFalse(result['checks']['change_budget']['passed'])
        self.assertFalse(result['checks']['candidate_geometry']['passed'])
        # A large enough budget must still preserve the reserved box.
        config['max_changed_blocks']=3
        context.write_text(json.dumps(config),encoding='utf8')
        result=validate_candidate(self.request,self.root/'preview/after.json',self.root/'reserved-check')
        self.assertFalse(result['passed'])
        self.assertIn('RESERVED_SPACE',result['checks']['candidate_geometry']['error'])

    def test_binary_wall_sidecar_counts_as_explicit_ownership(self):
        from nbt_refine import read_master
        from nbt_snbt import write_binary

        source=self.root/'binary-source'/'model.nbt'
        model,walls=read_master(self.source)
        write_binary(source,model,walls)
        request=dict(self.request,source=str(source),source_sha256=digest(source))
        self.preview(request)
        self.assertTrue(self.check(request)['passed'])
        sidecar=source.with_name('wall_mask.json')
        data=json.loads(sidecar.read_text(encoding='utf8'))
        data['wall_positions'].pop()
        sidecar.write_text(json.dumps(data),encoding='utf8')
        result=validate_candidate(request,self.root/'preview/after.json',self.root/'changed-wall')
        self.assertFalse(result['passed'])
        self.assertIn('wall mask has changed',result['checks']['inputs']['error'])

    def test_render_marks_completed_child_output_failed_when_preview_changes(self):
        import nbt_task

        snapshot=Path(self.preview()['snapshot'])
        cameras=self.root/'cameras.json'
        cameras.write_text(json.dumps([dict(id='overview',eye=[70,40,-30],target=[24,5,24])]),encoding='utf8')
        frontend=self.root/'assets/viewer/web-dist/frontend-manifest.json'
        frontend.parent.mkdir(parents=True)
        frontend.write_text('{}',encoding='utf8')
        output=self.root/'render'
        manifest=output/'render_manifest.json'
        images=[dict(image='overview.png')]

        def render(*args,**kwargs):
            output.mkdir()
            manifest.write_text(json.dumps(dict(status='complete',images=images)),encoding='utf8')
            snapshot.write_bytes(snapshot.read_bytes()+b'\n')
            return 0

        argv=['nbt.py','render','--snapshot',str(snapshot),'--cameras',str(cameras),'--output',str(output)]
        with (patch.object(nbt_task,'ROOT',self.root),patch.object(sys,'argv',argv),
              patch('nbt_render_runtime.render_environment',return_value={}),
              patch.object(nbt_task.subprocess,'call',side_effect=render)):
            with self.assertRaisesRegex(ValueError,'changed while rendering'):
                nbt_task.main()
        report=json.loads(manifest.read_text(encoding='utf8'))
        self.assertEqual(report['status'],'failed')
        self.assertEqual(report['images'],images)
        self.assertIn('changed while rendering',report['error'])

    def test_tampered_display_and_repeated_output_rejected(self):
        self.preview();file=self.root/'preview/after.json';data=json.loads(file.read_text());data['blocks'][0][1]='minecraft:gold_block';file.write_text(json.dumps(data))
        result=self.check();self.assertFalse(result['passed']);self.assertFalse(result['checks']['inputs']['passed'])
        with self.assertRaises(FileExistsError):self.check()
    def test_incomplete_or_malformed_context_is_read_only_not_unopenable(self):
        context=Path(self.request['context']);data=json.loads(context.read_text());del data['start'];context.write_text(json.dumps(data))
        info=inspect_source(self.source);self.assertFalse(info['editing_ready']);self.assertIn('start',info['context_readiness']['missing'])
        viewed=source_snapshot(self.request,self.root/'read-only');self.assertTrue(viewed['read_only_view']);self.assertIn('start',viewed['context_warning'])
        with self.assertRaises(ValueError):preview_effect(self.request,self.root/'must-not-preview')
        context.write_text('[]')
        info=inspect_source(self.source);self.assertFalse(info['editing_ready'])
        viewed=source_snapshot(self.request,self.root/'malformed-read-only');self.assertTrue(viewed['read_only_view'])

    def test_broken_legacy_description_keeps_the_source_viewable_but_blocks_edits(self):
        version=self.root/'nbt_models/single/只读建筑/v01'
        request=make_fixture(version)
        source=Path(request['source'])
        context=Path(request['context'])
        replacement=version/'replacement.json'
        context.rename(replacement)
        (version/'room_description.json').write_text('{"context_file":',encoding='utf8')
        item=next(item for item in catalog(self.root,index_only=True)['models'] if Path(item['source'])==source)
        self.assertFalse(item['unreadable'])
        info=inspect_source(source,0)
        self.assertFalse(info['editing_ready'])
        self.assertIn('room_description.json',info['context_readiness']['errors'][0])
        self.assertGreater(info['solid_blocks'],0)
        viewed=source_snapshot(dict(request,context=str(replacement)),self.root/'read-only-description')
        self.assertTrue(viewed['read_only_view'])
        self.assertIn('room_description.json',viewed['context_warning'])
        with self.assertRaisesRegex(ValueError,'room_description.json'):
            preview_effect(dict(request,context=str(replacement)),self.root/'must-not-preview-description')

    def test_context_requirements_follow_enclosure_and_opening_policy(self):
        from nbt_assembly import Volume
        from nbt_detail_control import context_readiness
        from nbt_whole_validation import validate_whole

        context=Path(self.request['context'])
        model=Volume((8,6,8))
        model.box((0,0,0),(7,0,7),'stone')
        outdoor=dict(mode='standalone',require_enclosure=False,start=[2.5,1,2.5],targets=[[5.5,1,2.5]])
        context.write_text(json.dumps(outdoor),encoding='utf8')
        self.assertTrue(context_readiness(model,context)['ready'])
        self.assertTrue(validate_whole(model,outdoor)['passed'])

        closed=dict(outdoor,require_enclosure=True)
        context.write_text(json.dumps(closed),encoding='utf8')
        self.assertCountEqual(context_readiness(model,context)['missing'],['openings','interior_probes'])
        model.box((0,1,0),(7,5,7),'stone')
        model.box((1,1,1),(6,4,6),'air')
        closed.update(interior_probes=[[3,2,3]],openings=[])
        context.write_text(json.dumps(closed),encoding='utf8')
        self.assertTrue(context_readiness(model,context)['ready'])
        self.assertTrue(validate_whole(model,closed)['recapped_seal']['passed'])

        required=dict(outdoor,openings_policy='required')
        context.write_text(json.dumps(required),encoding='utf8')
        self.assertFalse(context_readiness(model,context)['ready'])

    def test_interrupted_refinement_output_is_preserved_but_not_catalogued_as_ready(self):
        context=json.loads(Path(self.request['context']).read_text())
        context['cameras'][1]['eye']=[8.5,3.62,8.5];context['cameras'][1]['target']=[12,4,12]
        review=self.root/'review';prepare(self.source,context,review)
        record_user_approval(review,'Synthetic fixture only; never an approval for author assets.',True)
        output=self.root/'nbt_models/single/未完成测试/refined_v02'
        plan=dict(style_note='Synthetic failed-output lifecycle',operations=self.request['settings']['operations'])
        with self.assertRaisesRegex(ValueError,'Entry thumbnail'):
            refine(review,plan,output)
        self.assertTrue((output/'validation.json').is_file())
        self.assertFalse((output/'master/model.snbt').exists())
        self.assertFalse(list(output.rglob('*.nbt')))
        self.assertEqual(json.loads((output/'refinement.json').read_text())['state'],'writing')
        self.assertEqual(catalog(self.root)['models'],[])


if __name__=='__main__':unittest.main(verbosity=2)
