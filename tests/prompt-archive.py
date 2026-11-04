from pathlib import Path
import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_prompts import save,scan,read_prompt,read_handoff

class Prompts(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.workspace=Path(self.temp.name).resolve()
  self.payload=dict(session_id='a'*32,document=dict(project=dict(name='测试厅',stage='draft',buildingShape='single',source=''),operations=[]),text='完整提示词：不要把方案当作批准。',plan={'operations':[]},context={'start':None})
 def test_first_creation_goes_under_building_root_and_scan_is_only_index_metadata(self):
  r=save(self.workspace,self.payload);self.assertTrue(r['prompt'].startswith('nbt_models/single/测试厅/提示词方案/'));items=scan(self.workspace)['items'];self.assertEqual(len(items),1);self.assertNotIn('text',items[0]);self.assertEqual(read_prompt(self.workspace,r['index'],r['id'])['text'],self.payload['text']);self.assertFalse(any((self.workspace/'nbt_models').rglob('room_description.json')))
 def existing(self):
  source=self.workspace/'nbt_models/single/测试厅/v01/master/model.json.gz';source.parent.mkdir(parents=True);source.write_bytes(b'synthetic master');p=copy.deepcopy(self.payload);p['document']['project'].update(stage='plan',source=str(source));p['document']['source_sha256']=hashlib.sha256(source.read_bytes()).hexdigest();return source,p
 def test_existing_model_uses_actual_version_and_relative_paths(self):
  source,p=self.existing();p['text']='读取 '+str(source);r=save(self.workspace,p);self.assertTrue(r['index'].startswith('nbt_models/single/测试厅/v01/提示词方案/'));data=read_prompt(self.workspace,r['index'],r['id']);self.assertTrue(data['source_matches']);self.assertFalse(Path(data['document']['project']['source']).is_absolute());self.assertNotIn(str(self.workspace),data['text']);self.assertEqual(source.read_bytes(),b'synthetic master')
 def test_revisions_keep_old_files_and_identical_save_is_idempotent(self):
  first=save(self.workspace,self.payload);self.assertTrue(save(self.workspace,self.payload)['unchanged']);self.payload['text']='更新后的提示词';second=save(self.workspace,self.payload);self.assertNotEqual(first['revision'],second['revision']);self.assertTrue((self.workspace/first['prompt']).is_file());self.assertEqual(len(scan(self.workspace)['items']),1);self.assertEqual(read_prompt(self.workspace,second['index'],second['id'])['text'],self.payload['text'])
 def test_invalid_source_or_tampered_content_is_not_silently_read(self):
  source,p=self.existing();r=save(self.workspace,p);source.write_bytes(b'changed');self.assertFalse(read_prompt(self.workspace,r['index'],r['id'])['source_matches'])
  with self.assertRaisesRegex(ValueError,'已变化'):save(self.workspace,p)
  (self.workspace/r['prompt']).write_text('tampered',encoding='utf8')
  with self.assertRaisesRegex(ValueError,'产物已变化'):read_prompt(self.workspace,r['index'],r['id'])
 def test_workspace_escape_and_non_prompt_files_are_rejected(self):
  p=copy.deepcopy(self.payload);p['document']['project'].update(stage='plan',source='../outside/master.json.gz')
  with self.assertRaisesRegex(ValueError,'当前工作区'):save(self.workspace,p)
  with self.assertRaisesRegex(ValueError,'当前工作区'):read_prompt(self.workspace,'../index.json','a'*32)
 def test_generated_skill_finds_and_reads_after_workspace_relocation(self):
  from nbt_exposure import apply
  import shutil
  source,p=self.existing();r=save(self.workspace,p);apply(self.workspace);relocated=self.workspace/'relocated';relocated.mkdir();shutil.copytree(self.workspace/'nbt_models',relocated/'nbt_models');shutil.copytree(self.workspace/'.agents',relocated/'.agents');shutil.copytree(self.workspace/'.nbtcreator',relocated/'.nbtcreator');facade=relocated/'.agents/skills/nbtcreator-workspace/nbt.py'
  found=subprocess.run([sys.executable,str(facade),'prompts','scan'],cwd=relocated,capture_output=True,text=True,encoding='utf8');self.assertEqual(found.returncode,0,found.stderr);self.assertEqual(len(json.loads(found.stdout)['items']),1)
  run=subprocess.run([sys.executable,str(facade),'prompts','read','--index',r['index'],'--id',r['id']],cwd=relocated,capture_output=True,text=True,encoding='utf8');self.assertEqual(run.returncode,0,run.stderr);self.assertTrue(json.loads(run.stdout)['source_matches'])
 def test_existing_agent_handoff_is_discovered_and_bound_to_digest(self):
  folder=self.workspace/'nbt_models/single/旧建筑/v01/Agent交接/plan-123';folder.mkdir(parents=True);file=folder/'交给Agent.md';file.write_text('已有交接提示词',encoding='utf8');item=scan(self.workspace)['items'][0];self.assertEqual(item['kind'],'handoff');self.assertEqual(read_handoff(self.workspace,item['file'],item['sha256'])['text'],'已有交接提示词');file.write_text('changed')
  with self.assertRaisesRegex(ValueError,'已变化'):read_handoff(self.workspace,item['file'],item['sha256'])
 def test_concurrent_writers_and_terminated_owner_do_not_lose_or_block_records(self):
  script=ROOT/'.agents/skills/minecraft-nbt-modeler/scripts/nbt_prompts.py';processes=[]
  for id in ['a'*32,'b'*32]:
   payload=copy.deepcopy(self.payload);payload['session_id']=id;file=self.workspace/(id+'.json');file.write_text(json.dumps(payload));processes.append(subprocess.Popen([sys.executable,str(script),'--workspace',str(self.workspace),'save','--request',str(file)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf8'))
  for process in processes:
   stdout,stderr=process.communicate(timeout=10);self.assertEqual(process.returncode,0,stdout+stderr)
  self.assertEqual(len(scan(self.workspace)['items']),2)
  directory=self.workspace/'nbt_models/single/测试厅/提示词方案';code="import sys,time;sys.path.insert(0,sys.argv[1]);from nbt_prompts import index_lock;from pathlib import Path\nwith index_lock(Path(sys.argv[2]),Path(sys.argv[3])): print('locked',flush=True);time.sleep(60)"
  owner=subprocess.Popen([sys.executable,'-c',code,str(script.parent),str(self.workspace),str(directory)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
  try:self.assertEqual(owner.stdout.readline().strip(),'locked')
  finally:owner.terminate();owner.communicate(timeout=10)
  self.assertTrue(save(self.workspace,self.payload)['unchanged'])
if __name__=='__main__':unittest.main(verbosity=2)
