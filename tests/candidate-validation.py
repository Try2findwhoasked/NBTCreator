"""Exact preview/request binding and whole-candidate acceptance; synthetic inputs only."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
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
    def test_interrupted_refinement_output_is_preserved_but_not_catalogued_as_ready(self):
        context=json.loads(Path(self.request['context']).read_text())
        context['cameras'][1]['eye']=[8.5,3.62,8.5];context['cameras'][1]['target']=[12,4,12]
        review=self.root/'review';prepare(self.source,context,review)
        record_user_approval(review,'Synthetic fixture only; never an approval for author assets.',True)
        output=self.root/'nbt_models/single/未完成测试/refined_v02'
        plan=dict(style_note='Synthetic failed-output lifecycle',operations=self.request['settings']['operations'])
        with self.assertRaisesRegex(ValueError,'Entry thumbnail'):
            refine(review,plan,output)
        self.assertTrue((output/'refined.master.json.gz').is_file())
        self.assertEqual(json.loads((output/'refinement.json').read_text())['state'],'writing')
        self.assertEqual(catalog(self.root)['models'],[])


if __name__=='__main__':unittest.main(verbosity=2)
