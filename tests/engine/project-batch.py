import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2];SCRIPTS=ROOT/'.agents/skills/minecraft-nbt-modeler/scripts';sys.path.insert(0,str(SCRIPTS))
import nbt_project.queues as batch


class Batch(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.workspace=Path(self.temp.name).resolve();self.sources=[]
  for name in ('第一厅','第二厅'):
   folder=self.workspace/'nbt_models/single'/name/'v1';run=subprocess.run([sys.executable,str(ROOT/'tests/support/make_fixture.py'),str(folder)],capture_output=True,text=True);self.assertEqual(run.returncode,0,run.stderr);self.sources.append(folder/'synthetic.master.json.gz')
  self.before=[file.read_bytes() for file in self.sources]
 def create(self,actions=None):return batch.create(self.workspace,dict(sources=[dict(source=str(file),label=file.parent.parent.name) for file in self.sources],actions=actions or ['check']))
 def test_checks_actual_models_and_keeps_reports_without_writing_assets_or_approvals(self):
  queue=self.create();result=batch.run(self.workspace,queue['id']);self.assertEqual(result['status'],'complete');self.assertEqual(result['progress']['complete'],2);self.assertEqual([s.read_bytes() for s in self.sources],self.before)
  for item in result['items']:
   report=json.loads((self.workspace/item['steps']['check']['report']).read_text(encoding='utf8'));self.assertTrue(report['passed']);self.assertFalse(report['asset_written']);self.assertFalse(report['runtime_verified']);self.assertEqual(report['checks']['geometry_routes']['status'],'passed')

 def test_reports_stage_skips_and_components_separately_from_route_success(self):
  from nbt_refine import read_master,save_master
  from nbt_composition.whole_validation import validate_whole
  from nbt_composition.working_model import WorkingModel

  context=dict(mode='standalone',openings=[],require_enclosure=True,interior_probes=[[2,2,2]],
               start=[2.5,1,2.5],targets={'far':[5.5,1,5.5]})
  draft=WorkingModel(self.workspace,[8,6,8],context)
  draft.apply_operations([
   dict(kind='box',label='外壳',classification='wall',lo=[0,0,0],hi=[7,5,7],state='stone'),
   dict(kind='box',label='内部空间',classification='body',lo=[1,1,1],hi=[6,4,6],state='air'),
   dict(kind='box',label='阻断通行',classification='body',lo=[4,1,1],hi=[4,4,6],state='stone')])
  with self.assertRaisesRegex(ValueError,'route validation failed'):
   validate_whole(draft.model,context)
  design=draft.save_draft('断路草稿')
  draft.seal()
  sealed=draft.save_draft()
  component=WorkingModel(self.workspace,[3,3,3],kind='component')
  component.apply_operations([dict(kind='box',label='构件',classification='body',lo=[1,0,1],hi=[1,2,1],state='stone')])
  component=component.save_draft('独立构件')
  blocked=self.sources[1]
  model,walls=read_master(blocked)
  model.box((2,4,15),(45,13,15),'stone')
  save_master(blocked,model,walls)
  self.sources=[Path(saved['source']) for saved in (design,sealed,component)]+self.sources
  result=batch.run(self.workspace,self.create()['id'])
  self.assertEqual(result['progress']['complete'],4)
  self.assertEqual(result['progress']['failed'],1)
  for item,status,passed,overall,reason in zip(result['items'],
        ('not_checked','not_checked','not_applicable','passed','failed'),
        (None,None,None,True,False),(None,None,True,True,False),
        ('not_checked_in_design_phase','not_checked_in_sealed_phase','not_applicable_to_component',None,None)):
   step=item['steps']['check']
   report=batch.read_json(self.workspace/step['report'])
   check=report['checks']['geometry_routes']
   self.assertEqual(check['status'],status)
   self.assertIs(check['passed'],passed)
   self.assertIs(report['passed'],overall)
   self.assertEqual(check.get('reason'),reason)
   self.assertEqual(step['result']['checks']['geometry_routes']['status'],status)
   self.assertIs(step['result']['passed'],overall)
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
  code='import sys;sys.path.insert(0,sys.argv[1]);from nbt_project.queues import runner_lock;\nwith runner_lock(sys.argv[2]):\n print("locked",flush=True);sys.stdin.readline()'
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
  with patch('nbt_review.cover.section_cover',return_value=dict(image=str(image),thumbnail=str(image),cached=True,section=True)) as render:
   result=batch.run(self.workspace,queue['id']);self.assertEqual(render.call_count,2);self.assertEqual(result['progress']['total'],4);self.assertEqual(result['progress']['complete'],4);self.assertTrue(result['items'][0]['steps']['preview']['result']['image'].startswith('.nbtcreator/'))

 def test_retry_does_not_mix_completed_preview_with_changed_coordinates(self):
  self.sources=self.sources[:1];source=self.sources[0]
  context=source.parent/'coordinates.json'
  image=self.workspace/'overview.png';image.write_bytes(b'fixture')
  queue=self.create(['preview','check'])
  identifier=queue['id']
  with patch('nbt_review.cover.section_cover',return_value=dict(image=str(image),thumbnail=str(image))):
   with patch.object(batch,'check_source',side_effect=OSError('synthetic check failure')):
    result=batch.run(self.workspace,identifier)
   preview=result['items'][0]['steps']['preview']
   self.assertEqual(preview['status'],'complete')
   old_report=self.workspace/preview['report']
   config=json.loads(context.read_text(encoding='utf8'))
   config['max_changed_blocks']=1
   context.write_text(json.dumps(config),encoding='utf8')
   self.assertEqual(batch.retry(self.workspace,identifier)['progress']['pending'],2)
   result=batch.run(self.workspace,identifier)
  self.assertEqual(result['progress']['complete'],2)
  self.assertEqual(result['items'][0]['steps']['preview']['attempts'],2)
  self.assertTrue(old_report.is_file())

 def test_context_change_between_queue_and_run_requires_retry(self):
  queue=self.create()
  context=self.sources[0].parent/'coordinates.json'
  context.write_bytes(context.read_bytes()+b'\n')
  result=batch.run(self.workspace,queue['id'])
  self.assertEqual(result['items'][0]['steps']['check']['status'],'failed')
  self.assertIn('排队后',result['items'][0]['steps']['check']['error'])

 def test_recovered_probes_are_bound_before_running_and_rebound_on_retry(self):
  from nbt_library import saved_coordinates_hash

  self.sources=self.sources[:1]
  source=self.sources[0]
  context=source.parent/'coordinates.json'
  config=batch.read_json(context);del config['interior_probes'];batch.write(context,config)
  proof=source.parent/'validation.json'
  first=[[12,8,12]]
  second=[[14,8,14]]
  primary_hash=hashlib.sha256(context.read_bytes()).hexdigest()
  self.assertNotEqual(saved_coordinates_hash(source),primary_hash)

  for name,probes in [('added',first),('changed',second),('deleted',None)]:
   with self.subTest(case=name):
    before=batch.stamp(source)
    queue=self.create()
    if probes is None:proof.unlink()
    else:batch.write(proof,dict(sealed_before_opening=dict(passed=True,probes=probes)))
    self.assertNotEqual(batch.stamp(source),before)
    self.assertEqual(hashlib.sha256(context.read_bytes()).hexdigest(),primary_hash)
    step=batch.run(self.workspace,queue['id'])['items'][0]['steps']['check']
    self.assertEqual(step['status'],'failed')
    self.assertIn('排队后',step['error'])
    self.assertNotIn('report',step)
    batch.retry(self.workspace,queue['id'])
    step=batch.run(self.workspace,queue['id'])['items'][0]['steps']['check']
    report=batch.read_json(self.workspace/step['report'])
    if probes is None:
     self.assertIn('interior_probes',report['checks']['context']['details']['missing'])
    else:
     self.assertTrue(report['passed'])
     self.assertEqual(report['checks']['geometry_routes']['details']['recapped_seal']['probes'],probes)

  for recovered in (False,True):
   with self.subTest(old_stamp=True,recovered=recovered):
    if recovered:batch.write(proof,dict(sealed_before_opening=dict(passed=True,probes=first)))
    queue=self.create()
    stored=batch.load(self.workspace,queue['id'])
    stored['items'][0]['stamp'].update(coordinates=primary_hash,context=primary_hash)
    batch.write(batch.folder(self.workspace,queue['id'])/'queue.json',stored)
    step=batch.run(self.workspace,queue['id'])['items'][0]['steps']['check']
    self.assertIn('排队后',step['error'])
    batch.retry(self.workspace,queue['id'])
    self.assertEqual(batch.run(self.workspace,queue['id'])['progress']['complete'],int(recovered))

 def test_broken_optional_description_reports_context_failure_without_marking_geometry_passed(self):
  self.sources=self.sources[:1]
  source=self.sources[0]
  (source.parent/'coordinates.json').unlink()
  (source.parent/'room_description.json').write_text('{"context_file":',encoding='utf8')
  result=batch.run(self.workspace,self.create()['id'])
  step=result['items'][0]['steps']['check']
  report=batch.read_json(self.workspace/step['report'])
  self.assertTrue(report['checks']['file']['passed'])
  self.assertIn('room_description.json',report['checks']['context']['details']['errors'][0])
  self.assertEqual(report['checks']['geometry_routes']['status'],'not_checked')
  self.assertFalse(report['passed'])


if __name__=='__main__':unittest.main(verbosity=2)
