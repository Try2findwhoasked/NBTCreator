from pathlib import Path
import copy,hashlib,json,os,shutil,subprocess,sys,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_assembly import Volume
from nbt_refine import save_master,read_master
from nbt_history import History,dispatch,resolve_git

class BuildingHistory(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.workspace=Path(self.temp.name).resolve();self.building=self.workspace/'nbt_models/standalone/版本测试';self.v1=self.building/'v01';self.v2=self.building/'v02';self.source=self.make(self.v1);self.original=self.source.read_bytes();self.history=History(self.workspace)
 def make(self,version,height=2):
  version.mkdir(parents=True);file=version/'master/source.master.json.gz';file.parent.mkdir();model=Volume((8,8,8));model.box((0,0,0),(7,height-1,7),'stone_bricks');save_master(file,model,set());(version/'coordinates.json').write_text(json.dumps(dict(mode='standalone',allow_empty_wall_mask=True)),encoding='utf8');(version/'note.md').write_text('版本说明',encoding='utf8');return file
 def record(self,source=None,**kwargs):return self.history.record(dict(source=str(source or self.source),**kwargs))
 def test_private_git_does_not_modify_project_repository(self):
  git=resolve_git();subprocess.run([git,'init',str(self.workspace)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);outer=(self.workspace/'.git/HEAD').read_bytes();self.record(set_current=True);self.assertEqual((self.workspace/'.git/HEAD').read_bytes(),outer);self.assertFalse((self.workspace/'.git/index').exists());self.assertTrue((self.workspace/'.nbtcreator/history/repository.git/HEAD').is_file());self.assertEqual(self.source.read_bytes(),self.original)
 def test_identical_checkpoint_is_idempotent_and_keeps_text_in_git(self):
  first=self.record(message='初稿');again=self.record(message='初稿');self.assertEqual(first['commit'],again['commit']);self.assertTrue(again['unchanged']);state,_=self.history.state();node=state['versions'][first['version']['id']];self.assertEqual(node['files']['note.md']['text'],'版本说明');self.assertNotIn('text',node['files']['master/source.master.json.gz'])
 def test_parent_actor_tasks_and_current_are_separate_from_acceptance(self):
  a=self.record(set_current=True);b=self.make(self.v2,height=3);r=self.history.record(dict(source=str(b),parent=a['version']['id'],actor='external_agent',message='按标注增厚地板',tasks=['task-id']));self.assertEqual(r['version']['parent'],a['version']['id']);self.assertEqual(r['version']['acceptance'],'pending_user_review');self.assertEqual(r['current'],a['version']['id']);self.assertEqual(r['version']['tasks'],['task-id']);self.history.current(r['version']['id']);self.assertEqual(self.history.list(str(b))['current'][r['version']['building']],r['version']['id'])
 def test_continue_from_old_version_never_replaces_it_or_copies_annotations(self):
  (self.v1/'修改意见').mkdir();(self.v1/'修改意见/评论索引.json').write_text(json.dumps(dict(records=[dict(notes=[dict(id='note',status='open')])])),encoding='utf8');a=self.record();result=self.history.derive(a['version']['id'],'从第一版尝试新方案');self.assertNotEqual(Path(result['source']),self.source);self.assertEqual(Path(result['source']).suffix,'.snbt');self.assertEqual(self.source.read_bytes(),self.original);self.assertEqual(result['parent'],a['version']['id']);self.assertFalse((Path(result['source']).parents[1]/'修改意见').exists());self.assertEqual(read_master(result['source'])[0].fingerprint(),read_master(self.source)[0].fingerprint())
 def test_history_survives_workspace_relocation(self):
  a=self.record();moved=self.workspace/'relocated';shutil.copytree(self.workspace/'nbt_models',moved/'nbt_models');shutil.copytree(self.workspace/'.nbtcreator',moved/'.nbtcreator');other=History(moved);node=other.get(a['version']['id']);self.assertTrue(node['version']['source_matches']);result=other.derive(a['version']['id']);self.assertTrue(Path(result['source']).is_relative_to(moved/'nbt_models'))
 def test_corrupt_artifact_refuses_derive_before_allocating_output(self):
  a=self.record();node=self.history.get(a['version']['id'])['manifest'];obj=self.history.object_file(node['files'][node['source_file']]['sha256']);obj.write_bytes(b'corrupt');before=set(self.building.iterdir());self.assertRaisesRegex(ValueError,'归档',self.history.derive,a['version']['id']);self.assertEqual(set(self.building.iterdir()),before)
 def test_missing_source_can_be_restored_without_checkout_or_overwrite(self):
  a=self.record();geometry=read_master(self.source)[0].fingerprint();self.source.unlink();self.assertFalse(self.history.list()['versions'][0]['source_exists']);result=self.history.derive(a['version']['id']);self.assertEqual(read_master(result['source'])[0].fingerprint(),geometry);self.assertFalse(self.source.exists())
 def test_foreign_parent_and_outside_paths_are_rejected(self):
  a=self.record();other=self.workspace/'nbt_models/standalone/另一建筑/v01';b=self.make(other);self.assertRaisesRegex(ValueError,'同一建筑',self.history.record,dict(source=str(b),parent=a['version']['id']));self.assertRaisesRegex(ValueError,'nbt_models',self.history.record,dict(source=str(ROOT/'package.json')))
 def test_changed_existing_path_does_not_replace_its_history(self):
  a=self.record();model=read_master(self.source)[0];model.put((1,5,1),'stone');save_master(self.source,model,set());b=self.record();self.assertNotEqual(a['version']['id'],b['version']['id']);self.assertEqual(len(self.history.list()['versions']),2);self.assertFalse(self.history.get(a['version']['id'])['version']['source_matches'])

if __name__=='__main__':unittest.main(verbosity=2)
