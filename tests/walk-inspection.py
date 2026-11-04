from pathlib import Path
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_assembly import Volume
from nbt_refine import save_master
from nbt_collision import check_routes
from nbt_walk_view import inspect_walk


class WalkInspection(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.folder=Path(self.temp.name)
  self.model=Volume((10,5,3));self.model.box((0,0,0),(9,0,2),'stone_bricks')
  self.source=self.folder/'floor.master.json.gz';save_master(self.source,self.model,set());self.original=self.source.read_bytes()
  self.request=dict(source=str(self.source),source_sha256=hashlib.sha256(self.original).hexdigest(),start=[1.5,1,1.5],targets={'终点':[8.5,1,1.5]})
 def test_routes_have_real_swept_paths_and_player_size_without_writes(self):
  data=inspect_walk(self.request);self.assertTrue(data['report']['passed']);self.assertEqual(data['poses'][0]['hi'],[1.8,2.8,1.8]);self.assertTrue(data['poses'][0]['supported']);self.assertEqual(data['report']['targets'][0]['path'][0],self.request['start']);self.assertEqual(self.source.read_bytes(),self.original);self.assertFalse(data['asset_written'])
 def test_low_ceiling_and_missing_support_have_distinct_diagnostics(self):
  self.model.put((1,2,1),'stone_bricks');save_master(self.source,self.model,set());self.request['source_sha256']=hashlib.sha256(self.source.read_bytes()).hexdigest()
  data=inspect_walk(self.request);self.assertFalse(data['report']['passed']);self.assertTrue(data['poses'][0]['collisions']);self.assertTrue(data['poses'][0]['supported']);self.assertFalse(data['poses'][0]['clear'])
  data=inspect_walk(dict(self.request,start=[4.5,2,1.5]));self.assertTrue(data['poses'][0]['clear']);self.assertFalse(data['poses'][0]['supported'])
 def test_candidate_is_checked_instead_of_base_and_stale_binding_rejected(self):
  self.model.box((4,1,0),(4,4,2),'stone_bricks');snapshot=self.folder/'candidate.json';snapshot.write_text(json.dumps(dict(preview_only=True,source_sha256=self.request['source_sha256'],size=list(self.model.size),geometry_sha256=self.model.fingerprint(),master_blocks=[[list(p),v] for p,v in self.model.blocks.items()])))
  result=inspect_walk(dict(self.request,geometry_sha256=self.model.fingerprint()),snapshot);self.assertFalse(result['report']['passed']);self.assertTrue(result['inspected_snapshot']);self.assertTrue(all(p['standing'] for p in result['poses']));self.assertEqual(result['report']['targets'][0]['reason'],'unreachable_with_walking_and_half_block_steps')
  with self.assertRaisesRegex(ValueError,'画面已变化'):inspect_walk(dict(self.request,geometry_sha256='0'*64),snapshot)
  data=json.loads(snapshot.read_text());data['master_blocks']=[];snapshot.write_text(json.dumps(data))
  with self.assertRaisesRegex(ValueError,'指纹'):inspect_walk(self.request,snapshot)
 def test_invalid_missing_context_and_resource_limits_do_not_claim_unreachable(self):
  with self.assertRaisesRegex(ValueError,'脚底'):inspect_walk(dict(self.request,start=[float('nan'),1,1]))
  with self.assertRaisesRegex(ValueError,'32'):inspect_walk(dict(self.request,targets=[[1,1,1]]*33))
  data=check_routes(self.model,self.request['start'],self.request['targets'],max_poses=2);self.assertTrue(data['search_limit_reached']);self.assertFalse(data['passed']);self.assertEqual(data['targets'][0]['reason'],'search_limit_reached')
 def test_context_is_optional_but_can_supply_authored_positions(self):
  context=self.folder/'coordinates.json';context.write_text(json.dumps(dict(start=self.request['start'],targets=self.request['targets'])))
  request={k:v for k,v in self.request.items() if k not in ('start','targets')};data=inspect_walk(dict(request,context=str(context)));self.assertTrue(data['report']['passed']);self.assertTrue(data['context_sha256'])
  with self.assertRaisesRegex(ValueError,'填写'):inspect_walk(request)
 def test_same_cli_contract_writes_only_a_report_and_retains_source(self):
  request=self.folder/'request.json';request.write_text(json.dumps(self.request));output=self.folder/'report'
  run=subprocess.run([sys.executable,str(ROOT/'.agents/skills/minecraft-nbt-modeler/scripts/nbt_detail_control.py'),'walk-inspect','--request',str(request),'--output',str(output)],capture_output=True,text=True,encoding='utf8');self.assertEqual(run.returncode,0,run.stdout+run.stderr);self.assertTrue(json.loads(run.stdout)['result']['report']['passed']);self.assertTrue((output/'walk-inspection.json').is_file());self.assertEqual(self.source.read_bytes(),self.original)
 def test_generated_workspace_skill_exposes_and_executes_the_same_inspector(self):
  from nbt_exposure import apply
  apply(self.folder);facade=self.folder/'.agents/skills/nbtcreator-workspace/nbt.py'
  request=self.folder/'request.json';request.write_text(json.dumps(dict(self.request,source=self.source.name)))
  run=subprocess.run([sys.executable,str(facade),'control','walk-inspect','--request','request.json','--output','report'],cwd=self.folder,capture_output=True,text=True,encoding='utf8');self.assertEqual(run.returncode,0,run.stdout+run.stderr);self.assertTrue(json.loads(run.stdout)['result']['report']['passed'])
  cap=subprocess.run([sys.executable,str(facade),'capabilities'],cwd=self.folder,capture_output=True,text=True,encoding='utf8');self.assertEqual(cap.returncode,0,cap.stderr);self.assertIn('walk-inspect',json.loads(cap.stdout)['inspection_tools']);self.assertEqual(self.source.read_bytes(),self.original)


if __name__=='__main__':unittest.main(verbosity=2)
