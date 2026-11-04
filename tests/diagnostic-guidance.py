from pathlib import Path
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1];SCRIPTS=ROOT/'.agents/skills/minecraft-nbt-modeler/scripts';sys.path.insert(0,str(SCRIPTS))
from nbt_assembly import Volume
from nbt_refine import save_master
from nbt_walk_view import inspect_walk
from nbt_diagnostics import explain
from nbt_protection_view import ProtectionConflict

class Guidance(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.model=Volume((10,5,3));self.model.box((0,0,0),(9,0,2),'stone_bricks');self.source=self.root/'source.master.json.gz'
 def inspect(self,start=[1.5,1,1.5]):
  save_master(self.source,self.model,set());self.before=self.source.read_bytes();return inspect_walk(dict(source=str(self.source),source_sha256=hashlib.sha256(self.before).hexdigest(),start=start,targets={'门口':[8.5,1,1.5]}))
 def test_passing_route_has_no_invented_issues_or_repairs(self):
  result=self.inspect();self.assertTrue(result['report']['passed']);self.assertEqual(result['diagnostics']['issues'],[]);self.assertFalse(result['diagnostics']['asset_written']);self.assertEqual(self.source.read_bytes(),self.before)
 def test_body_collision_support_and_boundary_have_separate_locatable_explanations(self):
  self.model.put((1,2,1),'stone_bricks');result=self.inspect();issue=next(v for v in result['diagnostics']['issues'] if v['code']=='pose_collision');self.assertEqual(issue['target'],'起点');self.assertTrue(issue['bounds']);self.assertGreater(issue['evidence']['collision_cells'],0);self.assertFalse(issue['automatic_repair']);unsupported=self.inspect([4.5,2,1.5]);self.assertIn('pose_support',[v['code'] for v in unsupported['diagnostics']['issues']]);edge=self.inspect([0,1,1.5]);self.assertIn('pose_bounds',[v['code'] for v in edge['diagnostics']['issues']])
 def test_failed_search_never_claims_a_specific_wall_should_be_deleted(self):
  self.model.box((4,1,0),(4,4,2),'stone_bricks');result=self.inspect();issue=next(v for v in result['diagnostics']['issues'] if v['code']=='route_not_found');self.assertEqual(issue['certainty'],'incomplete');self.assertNotIn('blocking_positions',issue['evidence']);self.assertIn('唯一阻挡',issue['explanation']);self.assertEqual(self.source.read_bytes(),self.before)
 def test_search_limit_and_unknown_collision_do_not_become_unreachable_certification(self):
  result=self.inspect();report=result['report'];report['targets'][0].update(reachable=False,reason='search_limit_reached');report['unknown_shapes']=[dict(state='minecraft:test',reason='unsupported_collision_shape',count=1)];issues=explain('walk',result)['issues'];self.assertIn('route_search_limit',[v['code'] for v in issues]);self.assertIn('collision_unknown',[v['code'] for v in issues]);self.assertNotIn('route_not_found',[v['code'] for v in issues])
 def test_protection_conflict_explains_air_routes_without_relaxing_permission(self):
  error=ProtectionConflict('台基',[(2,3,4),(2,3,5)]);issue=error.details['diagnostics']['issues'][0];self.assertEqual(issue['code'],'protected_write');self.assertEqual(issue['evidence']['total'],2);self.assertEqual(issue['bounds']['lo'],[1.5,2.5,3.5]);self.assertIn('空气',' '.join(issue['suggestions']));self.assertFalse(issue['automatic_repair'])
 def test_candidate_failures_keep_raw_evidence_and_no_inferred_coordinates(self):
  result=explain('candidate',dict(source_sha256='a'*64,checks=dict(change_budget=dict(passed=False,error='budget 9 > 2; [1,2,3]'),inputs_unchanged=dict(passed=True),wall_ownership=dict(passed=False,error='missing mask'))));self.assertEqual(len(result['issues']),2);self.assertTrue(all(v['bounds'] is None for v in result['issues']));self.assertEqual(result['source_sha256'],'a'*64);self.assertIn('[1,2,3]',result['issues'][0]['evidence']['error'])
 def test_cli_explains_saved_report_without_revalidating_or_writing_a_model(self):
  result=self.inspect([4.5,2,1.5]);file=self.root/'report.json';file.write_bytes(json.dumps(result).encode());run=subprocess.run([sys.executable,str(SCRIPTS/'nbt_diagnostics.py'),'--kind','walk','--report',str(file)],capture_output=True,text=True,encoding='utf8');self.assertEqual(run.returncode,0,run.stderr);data=json.loads(run.stdout);self.assertFalse(data['report_reverified']);self.assertEqual(data['input_report_sha256'],hashlib.sha256(file.read_bytes()).hexdigest());self.assertEqual(self.source.read_bytes(),self.before)
if __name__=='__main__':unittest.main(verbosity=2)
