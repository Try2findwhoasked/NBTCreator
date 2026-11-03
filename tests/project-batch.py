import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];SCRIPTS=ROOT/'.agents/skills/minecraft-nbt-modeler/scripts';sys.path.insert(0,str(SCRIPTS))
import nbt_project_batch as batch


class Batch(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.workspace=Path(self.temp.name).resolve();self.sources=[]
  for name in ('第一厅','第二厅'):
   folder=self.workspace/'nbt_models/single'/name/'v1';run=subprocess.run([sys.executable,str(ROOT/'tests/make_fixture.py'),str(folder)],capture_output=True,text=True);self.assertEqual(run.returncode,0,run.stderr);self.sources.append(folder/'synthetic.master.json.gz')
  self.before=[file.read_bytes() for file in self.sources]
 def create(self,actions=None):return batch.create(self.workspace,dict(sources=[dict(source=str(file),label=file.parent.parent.name) for file in self.sources],actions=actions or ['check']))
 def test_checks_actual_models_and_keeps_reports_without_writing_assets_or_approvals(self):
  queue=self.create();result=batch.run(self.workspace,queue['id']);self.assertEqual(result['status'],'complete');self.assertEqual(result['progress']['complete'],2);self.assertEqual([s.read_bytes() for s in self.sources],self.before)
  for item in result['items']:
   report=json.loads((self.workspace/item['steps']['check']['report']).read_text(encoding='utf8'));self.assertTrue(report['passed']);self.assertFalse(report['asset_written']);self.assertFalse(report['runtime_verified']);self.assertIn('geometry_routes',report['checks'])
 def test_failure_does_not_stop_other_items_and_retry_only_reexecutes_failed_steps(self):
  self.sources[1].write_bytes(b'corrupt');queue=self.create();result=batch.run(self.workspace,queue['id']);self.assertEqual(result['progress']['failed'],1);self.assertEqual(result['progress']['complete'],1)
  self.sources[1].write_bytes(self.before[1]);batch.retry(self.workspace,queue['id']);result=batch.run(self.workspace,queue['id']);self.assertEqual(result['progress']['complete'],2);self.assertEqual([item['steps']['check']['attempts'] for item in result['items']],[1,2]);self.assertEqual(self.sources[0].read_bytes(),self.before[0])
 def test_missing_context_is_not_misreported_as_a_validated_route(self):
  (self.sources[1].parent/'coordinates.json').unlink();result=batch.run(self.workspace,self.create()['id']);self.assertEqual(result['progress']['failed'],1);step=result['items'][1]['steps']['check'];self.assertTrue(step['result']['checks']['file']['passed']);self.assertFalse(step['result']['checks']['context']['passed']);self.assertIn('缺少',step['error'])
 def test_changed_source_requires_explicit_retry_and_new_binding(self):
  queue=self.create();self.sources[0].write_bytes(self.before[0]+b'changed');result=batch.run(self.workspace,queue['id']);self.assertEqual(result['items'][0]['steps']['check']['status'],'failed');self.assertIn('排队后',result['items'][0]['steps']['check']['error']);self.assertEqual(result['items'][0]['steps']['check']['attempts'],1)
 def test_cancel_pending_and_resume_preserves_completed_work(self):
  queue=self.create();batch.dispatch(self.workspace,'cancel',dict(id=queue['id']));result=batch.run(self.workspace,queue['id']);self.assertEqual(result['status'],'cancelled');self.assertEqual(result['progress']['pending'],2);batch.retry(self.workspace,queue['id']);result=batch.run(self.workspace,queue['id']);self.assertEqual(result['progress']['complete'],2)
 def test_real_runner_lock_and_interruption_recovery(self):
  queue=self.create();file=batch.folder(self.workspace,queue['id'])/'queue.json';data=batch.load(self.workspace,queue['id']);data['status']='running';data['items'][0]['steps']['check']['status']='running';batch.write(file,data)
  code='import sys;sys.path.insert(0,sys.argv[1]);from nbt_project_batch import runner_lock;\nwith runner_lock(sys.argv[2]):\n print("locked",flush=True);sys.stdin.readline()'
  process=subprocess.Popen([sys.executable,'-c',code,str(SCRIPTS),str(self.workspace)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True);self.addCleanup(lambda:process.kill() if process.poll() is None else None);self.assertEqual(process.stdout.readline().strip(),'locked');self.assertEqual(batch.recover(self.workspace,queue['id'])['status'],'running')
  with self.assertRaisesRegex(ValueError,'已有批量任务'):batch.retry(self.workspace,queue['id'])
  process.communicate('\n',timeout=5);result=batch.recover(self.workspace,queue['id']);self.assertEqual(result['status'],'interrupted');self.assertEqual(result['items'][0]['steps']['check']['status'],'cancelled');batch.retry(self.workspace,queue['id']);self.assertEqual(batch.run(self.workspace,queue['id'])['progress']['complete'],2)
 def test_queue_paths_are_portable_and_outside_sources_commands_and_ids_are_rejected(self):
  for data in [dict(sources=[dict(source=str(ROOT/'README.md'))],actions=['check']),dict(sources=[dict(source=str(self.sources[0]))],actions=['execute']),dict(sources=[] ,actions=['preview'])]:
   with self.assertRaises(ValueError):batch.create(self.workspace,data)
  with self.assertRaises(ValueError):batch.load(self.workspace,'../source')
  queue=self.create();text=(batch.folder(self.workspace,queue['id'])/'queue.json').read_text(encoding='utf8');self.assertNotIn(str(self.workspace).replace('\\','\\\\'),text)
  relocated=self.workspace/'moved';shutil.copytree(self.workspace/'nbt_models',relocated/'nbt_models');shutil.copytree(self.workspace/'.nbtcreator',relocated/'.nbtcreator');batch.retry(relocated,queue['id']);self.assertEqual(batch.run(relocated,queue['id'])['progress']['complete'],2)
 def test_preview_cache_is_reused_and_progress_covers_both_actions(self):
  image=self.workspace/'.nbtcreator/cache/section-covers/generated/test/overview.png';image.parent.mkdir(parents=True);image.write_bytes(b'cache');queue=self.create(['preview','check'])
  with patch('nbt_cover.section_cover',return_value=dict(image=str(image),thumbnail=str(image),cached=True,section=True)) as render:
   result=batch.run(self.workspace,queue['id']);self.assertEqual(render.call_count,2);self.assertEqual(result['progress']['total'],4);self.assertEqual(result['progress']['complete'],4);self.assertTrue(result['items'][0]['steps']['preview']['result']['image'].startswith('.nbtcreator/'))


if __name__=='__main__':unittest.main(verbosity=2)
