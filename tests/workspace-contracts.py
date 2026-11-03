"""Synthetic checks for shared catalogue, relocation and non-destructive migration."""
import json,sys,tempfile,unittest,shutil,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];ENGINE=ROOT/'.agents/skills/minecraft-nbt-modeler';sys.path.insert(0,str(ENGINE/'scripts'))
from nbt_capabilities import capabilities
from nbt_exposure import apply as expose,import_knowledge
from nbt_workspace import migrate
from nbt_request_paths import read_request,metadata_path
from nbt_detail_control import default_settings,compile_plan,preview_effect
from nbt_refine import save_master
from nbt_assembly import Volume

class Contracts(unittest.TestCase):
 def test_exposed_paths_are_callable_after_relocation_and_locate_importable_api(self):
  with tempfile.TemporaryDirectory() as temp:
   old=Path(temp)/'old';new=Path(temp)/'new';expose(old)
   shutil.copytree(old,new);shutil.rmtree(old)
   command=[sys.executable,str(new/'.agents/skills/nbtcreator-workspace/nbt.py'),'paths']
   run=subprocess.run(command,cwd=new,capture_output=True,text=True,encoding='utf8')
   self.assertEqual(run.returncode,0,run.stderr);data=json.loads(run.stdout)
   self.assertTrue(Path(data['engine']).is_relative_to(new.resolve()))
   self.assertTrue((Path(data['scripts'])/'nbt_openings.py').is_file())
   self.assertEqual(Path(data['workspace']),new.resolve());self.assertEqual(len(data['runtime_bundle_sha256']),64)
   imported=subprocess.run([sys.executable,'-c','import sys;sys.path.insert(0,sys.argv[1]);from nbt_openings import open_declared_openings;print(callable(open_declared_openings))',data['scripts']],capture_output=True,text=True)
   self.assertEqual(imported.returncode,0,imported.stderr);self.assertEqual(imported.stdout.strip(),'True')
 def test_catalogue_and_generic_gui_operations(self):
  c=capabilities();self.assertEqual(len(c['tools']),19)
  s=default_settings();s['operations']=[dict(kind='box',label='same engine',classification='body',lo=[4,4,4],hi=[4,5,4],state='stone')]
  self.assertEqual(compile_plan(s,(48,16,48))['operations'],s['operations'])
  s['operations'][0]['kind']='run_python'
  with self.assertRaises(ValueError):compile_plan(s,(48,16,48))
 def test_exposure_keeps_core_and_does_not_remove_knowledge(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);result=expose(root,dict(schema_version=1,enabled_groups=['architecture']))
   self.assertIn('core',result['enabled_groups'])
   text=(root/'.agents/skills/nbtcreator-workspace/SKILL.md').read_text(encoding='utf8')
   self.assertIn('architecture-knowledge-base.md',text);self.assertNotIn('micro-props.md',text)
   self.assertTrue((ENGINE/'references/micro-props.md').is_file())
   self.assertNotIn(str(ENGINE),text)
 def test_request_relative_survives_whole_workspace_move(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);old=root/'old';new=root/'new';(old/'nbt_models/room').mkdir(parents=True)
   (old/'nbt_models/room/model.nbt').write_bytes(b'fixture')
   request=dict(path_base='workspace',source='nbt_models/room/model.nbt',context='',settings={})
   (old/'request.json').write_text(json.dumps(request),encoding='utf8');shutil.copytree(old,new)
   loaded=read_request(new/'request.json',workspace=new);self.assertEqual(Path(loaded['source']).read_bytes(),b'fixture');self.assertTrue(Path(loaded['source']).is_relative_to(new.resolve()))
 def test_legacy_paths_remain_accepted(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);f=root/'request.json';f.write_text(json.dumps({'source':str(root/'master.gz')}),encoding='utf8')
   self.assertEqual(read_request(f)['source'],str((root/'master.gz').resolve()))
 def test_migration_verified_and_metadata_rebased(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);old=root/'old';new=root/'agent';room=old/'nbt_models/single/房间/v01';room.mkdir(parents=True)
   master=room/'master.json.gz';master.write_bytes(b'unchanged')
   (room/'room_description.json').write_text(json.dumps({'master':str(master)}),encoding='utf8')
   cache=old/'nbt_models/_workspaces';cache.mkdir();(cache/'approval.json').write_text('synthetic evidence',encoding='utf8')
   result=migrate(old,new);self.assertEqual(result['status'],'complete');self.assertEqual(result['files'],3)
   description=new/'nbt_models/single/房间/v01/room_description.json';data=json.loads(description.read_text(encoding='utf8'));self.assertEqual(metadata_path(description,data['master']).read_bytes(),b'unchanged')
   self.assertEqual(master.read_bytes(),b'unchanged');self.assertEqual(migrate(old,new),result)
 def test_migration_refuses_conflict_before_copy(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);old=root/'old';new=root/'new';(old/'nbt_models').mkdir(parents=True);(new/'nbt_models').mkdir(parents=True)
   (old/'nbt_models/a.nbt').write_bytes(b'old');(new/'nbt_models/a.nbt').write_bytes(b'new')
   with self.assertRaises(ValueError):migrate(old,new)
   self.assertEqual((old/'nbt_models/a.nbt').read_bytes(),b'old');self.assertEqual((new/'nbt_models/a.nbt').read_bytes(),b'new')
 def test_exposed_skill_moves_with_workspace_and_runs_without_old_directory(self):
  with tempfile.TemporaryDirectory() as temp:
   old=Path(temp)/'old';new=Path(temp)/'new';expose(old,dict(schema_version=1,enabled_groups=['props']))
   shutil.copytree(old,new);shutil.rmtree(old)
   run=subprocess.run([sys.executable,str(new/'.agents/skills/nbtcreator-workspace/nbt.py'),'capabilities'],cwd=new,capture_output=True,text=True,encoding='utf8')
   self.assertEqual(run.returncode,0,run.stderr);self.assertEqual(len(json.loads(run.stdout)['tools']),19)
   text=(new/'.agents/skills/nbtcreator-workspace/SKILL.md').read_text(encoding='utf8');self.assertIn('.nbtcreator/runtimes',text);self.assertNotIn(str(ROOT),text)
 def test_custom_knowledge_copied_selected_and_portable(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);workspace=root/'project';doc=root/'建筑规范.md';doc.write_text('梁端需要承托。',encoding='utf8')
   result=import_knowledge(workspace,[doc]);item=result['custom_knowledge'][0];self.assertTrue((workspace/'.nbtcreator'/item['path']).is_file());self.assertIn('建筑规范',(workspace/'.agents/skills/nbtcreator-workspace/SKILL.md').read_text(encoding='utf8'))
   item['enabled']=False;expose(workspace,dict(schema_version=1,enabled_groups=['core'],custom_knowledge=[item]));self.assertNotIn('建筑规范',(workspace/'.agents/skills/nbtcreator-workspace/SKILL.md').read_text(encoding='utf8'));self.assertTrue(doc.is_file());self.assertTrue((workspace/'.nbtcreator'/item['path']).is_file())
if __name__=='__main__':unittest.main(verbosity=2)
