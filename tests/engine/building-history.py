from pathlib import Path
import copy,hashlib,json,os,shutil,subprocess,sys,tempfile,unittest
from unittest.mock import patch
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_assembly import Volume
from nbt_refine import save_master,read_master
from nbt_project.history import History,dispatch,resolve_git

class BuildingHistory(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.workspace=Path(self.temp.name).resolve();self.building=self.workspace/'nbt_models/standalone/版本测试';self.v1=self.building/'v01';self.v2=self.building/'v02';self.source=self.make(self.v1);self.original=self.source.read_bytes();self.history=History(self.workspace)
 def make(self,version,height=2):
  version.mkdir(parents=True);file=version/'master/source.master.json.gz';file.parent.mkdir();model=Volume((8,8,8));model.box((0,0,0),(7,height-1,7),'stone_bricks');save_master(file,model,set());(version/'coordinates.json').write_text(json.dumps(dict(mode='standalone',allow_empty_wall_mask=True)),encoding='utf8');(version/'note.md').write_text('版本说明',encoding='utf8');return file
 def record(self,source=None,**kwargs):return self.history.record(dict(source=str(source or self.source),**kwargs))
 def test_private_git_does_not_modify_project_repository(self):
  git=resolve_git();subprocess.run([git,'init',str(self.workspace)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);outer=(self.workspace/'.git/HEAD').read_bytes();self.record(set_current=True);self.assertEqual((self.workspace/'.git/HEAD').read_bytes(),outer);self.assertFalse((self.workspace/'.git/index').exists());self.assertTrue((self.workspace/'.nbtcreator/history/repository.git/HEAD').is_file());self.assertEqual(self.source.read_bytes(),self.original)
 def test_identical_checkpoint_is_idempotent_and_reads_text_from_objects(self):
  first=self.record(message='初稿');again=self.record(message='初稿');self.assertEqual(first['commit'],again['commit']);self.assertTrue(again['unchanged']);state,_=self.history.state();node=state['versions'][first['version']['id']];self.assertNotIn('text',node['files']['note.md']);self.assertEqual(self.history.get(first['version']['id'])['manifest']['files']['note.md']['text'],'版本说明')
 def test_legacy_inline_text_is_migrated_and_old_versions_can_be_restored(self):
  first=self.record(message='初稿');identifier=first['version']['id'];state,head=self.history.state();item=state['versions'][identifier]['files']['note.md'];item['text']='版本说明'
  raw=json.dumps(state,ensure_ascii=False,indent=2,sort_keys=True).encode();blob=self.history.run(['hash-object','-w','--stdin'],raw).stdout.decode().strip();tree=self.history.run(['mktree'],('100644 blob '+blob+'\tindex.json\n').encode()).stdout.decode().strip();commit=self.history.run(['commit-tree',tree,'-p',head,'-m','legacy']).stdout.decode().strip();self.history.run(['update-ref','refs/heads/history',commit,head])
  second=self.make(self.v2,height=3);self.history.record(dict(source=str(second),parent=identifier));migrated,_=self.history.state();self.assertNotIn('text',migrated['versions'][identifier]['files']['note.md']);self.assertEqual(self.history.get(identifier)['manifest']['files']['note.md']['text'],'版本说明');self.source.unlink();derived=self.history.derive(identifier);self.assertTrue(Path(derived['source']).is_file())
 def test_migration_rejects_missing_legacy_object_without_changing_head(self):
  first=self.record();identifier=first['version']['id'];state,head=self.history.state();item=state['versions'][identifier]['files']['note.md'];item['text']='版本说明';self.history.object_file(item['sha256']).unlink()
  with self.assertRaisesRegex(ValueError,'历史.*(缺失|损坏)'):self.history.commit(state,head,'migration')
  self.assertEqual(self.history.state()[1],head)
 def test_capacity_warning_reports_index_and_disk_space(self):
  self.record()
  with patch('nbt_project.history.MAX_STATE',100),patch('nbt_project.history.shutil.disk_usage',return_value=SimpleNamespace(free=100)):
   capacity=self.history.list()['index_capacity']
  self.assertTrue(capacity['warning']);self.assertTrue(capacity['disk_warning']);self.assertEqual(capacity['disk_free_bytes'],100)
 def test_omitted_text_can_be_read_on_demand_with_ownership_and_hash_checks(self):
  first=self.record();identifier=first['version']['id']
  with patch('nbt_project.history.MAX_PREVIEW_TOTAL',0):self.assertEqual(self.history.get(identifier)['manifest']['files']['note.md']['text_omitted'],'preview_limit')
  self.assertEqual(dispatch(self.workspace,'get',dict(id=identifier,name='note.md'))['text'],'版本说明')
  with self.assertRaises(ValueError):self.history.get_text(identifier,'../note.md')
  node=self.history.get(identifier)['manifest'];self.history.object_file(node['files']['note.md']['sha256']).write_bytes(b'bad')
  with self.assertRaisesRegex(ValueError,'损坏'):self.history.get_text(identifier,'note.md')
 def test_over_64m_legacy_index_migrates_and_accepts_a_new_version(self):
  first=self.record();identifier=first['version']['id'];state,head=self.history.state()
  note=self.v1/'large.txt';note.write_text('x'*(1024*1024),encoding='utf8');item=self.history.archive(note);item['text']=note.read_text(encoding='utf8')
  for n in range(65):state['versions'][identifier]['files'][f'legacy-{n:02}.txt']=item
  raw=json.dumps(state,ensure_ascii=False).encode('utf8');self.assertGreater(len(raw),64*1024*1024)
  blob=self.history.run(['hash-object','-w','--stdin'],raw).stdout.decode().strip();tree=self.history.run(['mktree'],('100644 blob '+blob+'\tindex.json\n').encode()).stdout.decode().strip();old=self.history.run(['commit-tree',tree,'-p',head,'-m','large legacy']).stdout.decode().strip();self.history.run(['update-ref','refs/heads/history',old,head]);del raw,state
  self.assertGreater(self.history.list()['index_capacity']['bytes'],64*1024*1024)
  second=self.make(self.v2,height=3);result=self.history.record(dict(source=str(second),parent=identifier));self.assertNotEqual(result['commit'],old)
  compact,_=self.history.state();self.assertLess(len(json.dumps(compact).encode()),1024*1024);self.assertNotIn('text',compact['versions'][identifier]['files']['legacy-00.txt']);self.assertEqual(self.history.get_text(identifier,'legacy-00.txt')['text'],item['text'])
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
