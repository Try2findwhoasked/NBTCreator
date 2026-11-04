from pathlib import Path
import hashlib
import json
import sys
import tempfile
import time
import unittest
import shutil
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_batches import dispatch,workspace_root
from nbt_assembly import Volume
from nbt_refine import save_master

class Batches(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.workspace=Path(self.temp.name).resolve()
 def call(self,action,**payload):return dispatch(self.workspace,action,payload)
 def model(self,name='新房间',version='v01'):
  folder=self.workspace/'nbt_models/single'/name/version;folder.mkdir(parents=True);model=Volume((8,6,8));model.box((0,0,0),(7,0,7),'stone_bricks');source=folder/'master/master_geometry.json.gz';source.parent.mkdir();save_master(source,model,set());return source
 def test_new_batches_have_stable_process_workspace_under_batches_and_no_nested_project(self):
  task=self.call('create',name='30个房间');directory=Path(task['absolute_workspace']);self.assertTrue(directory.is_relative_to(self.workspace/'nbt_models/_workspaces/batches'));self.assertTrue((directory/'scripts').is_dir());self.assertTrue((directory/'intermediate').is_dir());self.assertFalse((directory/'.agents').exists());self.assertEqual(workspace_root(directory),self.workspace);self.assertEqual(self.call('list')['tasks'][0]['id'],task['id'])
 def test_real_models_and_gallery_are_linked_with_hashes_and_actual_addresses(self):
  task=self.call('create',name='交付');source=self.model();gallery=Path(task['absolute_workspace'])/'deliverables/gallery.html';gallery.write_text('<h1>图册</h1>',encoding='utf8');result=self.call('record',id=task['id'],revision=task['revision'],models=[dict(source=str(source),name='新房间')],artifacts=[dict(path=str(gallery),role='gallery')],status='review');self.assertEqual(len(result['models']),1);self.assertTrue(result['models'][0]['is_new']);self.assertEqual(result['artifacts'][0]['absolute_path'],str(gallery));located=self.call('locate',id=task['id'],kind='artifact',item_id=result['artifacts'][0]['id']);self.assertEqual(located['path'],str(gallery));self.assertEqual(result['approval'],'not_granted_by_registration')
 def test_intermediate_sources_never_register_as_formal_or_promote_delivery_copy(self):
  task=self.call('create',name='过程');source=self.model();intermediate=Path(task['absolute_workspace'])/'intermediate/draft.json.gz';intermediate.write_bytes(source.read_bytes())
  with self.assertRaisesRegex(ValueError,'完整主模型'):self.call('record',id=task['id'],revision=task['revision'],models=[dict(source=str(intermediate),kind='formal')])
  data=self.call('record',id=task['id'],revision=task['revision'],models=[dict(source=str(intermediate),kind='intermediate')]);self.assertFalse(data['models'][0]['is_new']);self.assertEqual(data['models'][0]['kind'],'intermediate')
 def test_highlights_only_cover_fresh_registered_versions_and_ack_is_persistent(self):
  old=self.model('旧房');task=self.call('create',name='新到达');new=self.model('新房');result=self.call('record',id=task['id'],revision=task['revision'],models=[dict(source=str(old)),dict(source=str(new))]);self.assertFalse(result['models'][0]['is_new']);self.assertTrue(result['models'][1]['is_new']);self.call('ack',id=task['id'],all=True);self.assertFalse(self.call('get',id=task['id'])['is_new']);self.assertFalse(any(item['is_new'] for item in self.call('get',id=task['id'])['models']))
 def test_file_overwrite_hash_change_and_stale_revision_are_reported(self):
  task=self.call('create',name='哈希');source=self.model();result=self.call('record',id=task['id'],revision=task['revision'],models=[dict(source=str(source))]);source.write_bytes(b'changed')
  with self.assertRaisesRegex(ValueError,'缺失或变化'):self.call('locate',id=task['id'],kind='model',item_id=result['models'][0]['id'])
  with self.assertRaisesRegex(ValueError,'批次已更新'):self.call('record',id=task['id'],revision=task['revision'],status='review')
 def test_legacy_discovery_and_import_do_not_mark_all_history_new(self):
  source=self.model();folder=self.workspace/'nbt_models/_workspaces/2026-11-04_legacy';folder.mkdir(parents=True);catalog=folder/'2026-11-04_legacy_catalog.json';catalog.write_text(json.dumps([dict(name_zh='旧房',master=str(source))]),encoding='utf8');gallery=folder/'2026-11-04_legacy_gallery.html';gallery.write_text('<h1>旧图册</h1>',encoding='utf8');before=source.read_bytes();found=self.call('discover');self.assertEqual(len(found['candidates']),1);self.assertFalse((folder/'task.json').exists());task=self.call('import',name='旧批次',workspace_dir=str(folder),catalog=str(catalog),gallery=str(gallery));self.assertFalse(task['is_new']);self.assertEqual(source.read_bytes(),before);self.assertEqual(len(task['models']),1);self.assertEqual(len(task['artifacts']),2)
 def test_unique_runs_keep_per_attempt_locations_and_reject_workspace_escape(self):
  task=self.call('create',name='多次尝试');first=self.call('run',id=task['id'],revision=task['revision'],stage='draft');second=self.call('run',id=task['id'],revision=first['revision'],stage='draft');self.assertNotEqual(first['runs'][0]['directory'],second['runs'][1]['directory']);self.assertTrue((self.workspace/second['runs'][1]['directory']).is_dir())
  with self.assertRaisesRegex(ValueError,'当前工作区'):self.call('record',id=task['id'],revision=second['revision'],artifacts=[dict(path='../secret.txt')])
 def test_orphan_manifest_after_interrupted_index_write_can_be_recovered(self):
  task=self.call('create',name='恢复');index=self.workspace/'nbt_models/_workspaces/batches/index.json';data=json.loads(index.read_text());data['tasks']=[];index.write_text(json.dumps(data));self.assertEqual(len(self.call('discover')['candidates']),1);recovered=self.call('import',name='恢复',workspace_dir=task['workspace_dir']);self.assertEqual(recovered['id'],task['id']);self.assertEqual(len(self.call('list')['tasks']),1)
 def test_failed_index_commit_preserves_previous_readable_registration(self):
  task=self.call('create',name='中断');source=self.model()
  with patch('nbt_batches.write_index',side_effect=OSError('simulated interrupted commit')):
   with self.assertRaises(OSError):self.call('record',id=task['id'],revision=task['revision'],models=[dict(source=str(source))])
  previous=self.call('get',id=task['id']);self.assertEqual(previous['revision'],task['revision']);self.assertEqual(previous['models'],[]);self.assertEqual(self.call('list')['errors'],[])
 def test_relative_registration_survives_workspace_relocation(self):
  task=self.call('create',name='可移植');source=self.model();task=self.call('record',id=task['id'],revision=task['revision'],models=[dict(source=str(source))]);destination=self.workspace/'relocated';shutil.copytree(self.workspace/'nbt_models',destination/'nbt_models');moved=dispatch(destination,'get',dict(id=task['id'],verify=True));self.assertTrue(moved['models'][0]['absolute_source'].startswith(str(destination)));self.assertEqual(moved['models'][0]['file_status'],'verified')
if __name__=='__main__':unittest.main(verbosity=2)
