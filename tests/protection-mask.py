from pathlib import Path
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1];SCRIPTS=ROOT/'.agents/skills/minecraft-nbt-modeler/scripts';sys.path.insert(0,str(SCRIPTS))
from nbt_protection_view import mask,ProtectionConflict
from nbt_refine import read_master,protections
from nbt_detail_control import default_settings,preview_effect


class Protection(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.folder=Path(self.temp.name)/'fixture';r=subprocess.run([sys.executable,str(ROOT/'tests/make_fixture.py'),str(self.folder)],capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stderr);self.source=self.folder/'synthetic.master.json.gz';self.context=self.folder/'coordinates.json';self.original=self.source.read_bytes();self.hash=hashlib.sha256(self.original).hexdigest();config=json.loads(self.context.read_text());config['protected_boxes']=[dict(lo=[17,5,27],hi=[19,6,29])];config['protected_paths']=[[[7.5,4,8.5],[9.5,4,8.5]]];self.context.write_text(json.dumps(config));self.request=dict(source=str(self.source),source_sha256=self.hash,context=str(self.context))
 def test_compact_runs_equal_actual_enforced_protection_set_including_air_and_support(self):
  result=mask(self.request);shown={(x+i,y,z) for x,y,z,length in result['runs'] for i in range(length)};model,_=read_master(self.source);expected=protections(model,json.loads(self.context.read_text()));self.assertEqual(shown,expected);self.assertEqual(result['count'],len(expected));self.assertIn((7,3,8),shown);self.assertIn((17,5,27),shown);self.assertEqual(result['source_sha256'],self.hash);self.assertEqual(self.source.read_bytes(),self.original)
 def test_missing_context_and_changed_hash_do_not_claim_a_valid_mask(self):
  self.assertFalse(mask(dict(self.request,context=''))['available'])
  with self.assertRaisesRegex(ValueError,'改变'):mask(dict(self.request,source_sha256='0'*64))
 def test_actual_preview_failure_reports_exact_positions_and_keeps_source(self):
  settings=default_settings();settings['operations']=[dict(kind='box',label='台基底座',classification='body',lo=[17,5,27],hi=[19,5,29],state='gold_block',overwrite=True)]
  with self.assertRaises(ProtectionConflict) as caught:preview_effect(dict(self.request,settings=settings),self.folder/'preview')
  details=caught.exception.details;self.assertEqual(details['total'],9);self.assertEqual(len(details['positions']),9);self.assertIn([17,5,27],details['positions']);self.assertEqual(self.source.read_bytes(),self.original);self.assertFalse((self.folder/'preview').exists())
 def test_clip_protected_keeps_original_blocks_and_wall_membership(self):
  from nbt_detail_control import simulate_plan
  from nbt_assembly import Volume
  model=Volume((8,8,8));model.put((3,3,3),'minecraft:stone');model.put((4,3,3),'minecraft:stone')
  protected={(3,3,3),(5,3,3)};config=dict(mode='standalone',openings=[],protected_boxes=[dict(lo=list(p),hi=list(p)) for p in protected])
  op=dict(kind='box',label='裁剪测试',classification='body',lo=[3,3,3],hi=[6,3,3],state='gold_block',overwrite=True,skip_protected=True)
  result,walls,diff=simulate_plan(model,{(3,3,3),(4,3,3)},dict(operations=[op]),config)
  self.assertEqual(result.get((3,3,3)),'minecraft:stone');self.assertIn((3,3,3),walls);self.assertNotIn((4,3,3),walls)
  self.assertNotIn((5,3,3),result.blocks);self.assertEqual(result.get((6,3,3)),'minecraft:gold_block');self.assertEqual(diff['changed_blocks'],2)
  op['skip_protected']='yes'
  with self.assertRaises(ValueError):simulate_plan(model,set(),dict(operations=[op]),config)

 def test_backend_json_preserves_error_details_without_traceback_parsing(self):
  settings=default_settings();settings['operations']=[dict(kind='box',label='底座',classification='body',lo=[17,5,27],hi=[17,5,27],state='stone',overwrite=True)];file=self.folder/'request.json';file.write_text(json.dumps(dict(self.request,settings=settings)));run=subprocess.run([sys.executable,str(SCRIPTS/'nbt_detail_control.py'),'preview','--request',str(file),'--output',str(self.folder/'out')],capture_output=True,text=True,encoding='utf8');self.assertEqual(run.returncode,1);error=json.loads(run.stdout);self.assertEqual(error['details']['kind'],'protection_conflict');self.assertEqual(error['details']['positions'],[[17,5,27]])


if __name__=='__main__':unittest.main(verbosity=2)
