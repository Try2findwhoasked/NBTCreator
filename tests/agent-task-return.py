from pathlib import Path
import hashlib
import json
import sys
import tempfile
import unittest
import shutil
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_agent_tasks import dispatch
from nbt_assembly import Volume
from nbt_refine import save_master
from nbt_task import write_snapshot

def sha(file):return hashlib.sha256(file.read_bytes()).hexdigest()
class Returns(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name).resolve();self.base=self.root/'nbt_models/single/回传测试';self.source=self.model('v01');self.hash=sha(self.source);snapshot=self.source.parent.parent/'previews/snapshot.json';data=write_snapshot(self.source,snapshot);folder=self.source.parent.parent/'修改意见';folder.mkdir();self.comments=folder/'comments.json';note=dict(id='1',number=1,text='地面换材，保留支承',status='open',anchors=[dict(kind='voxel',position=[1,0,1],state='minecraft:stone_bricks',geometry_sha256=data['geometry_sha256'])],references=[]);self.comments.write_bytes(json.dumps(dict(schema_version=2,binding=dict(kind='3d',source=str(self.source),source_sha256=self.hash,geometry_sha256=data['geometry_sha256'],snapshot=str(snapshot),snapshot_sha256=sha(snapshot),size=[8,6,8]),notes=[note])).encode());(folder/'评论索引.json').write_bytes(json.dumps(dict(schema_version=1,records=[dict(source='../master/master_geometry.json.gz',source_sha256=self.hash,feedback_file='comments.json',feedback_sha256=sha(self.comments),notes=[note])])).encode());self.original=self.comments.read_bytes()
 def model(self,version,name='回传测试'):
  file=self.root/'nbt_models/single'/name/version/'master/master_geometry.json.gz';file.parent.mkdir(parents=True);model=Volume((8,6,8));model.box((0,0,0),(7,0,7),'stone_bricks');model.put((1,0,1),'andesite' if version!='v01' else 'stone_bricks');save_master(file,model,set());return file
 def call(self,action,**request):return dispatch(self.root,action,request)
 def create(self):return self.call('create',source=str(self.source),source_sha256=self.hash,name='回传测试')
 def record(self,task,source=None):
  source=source or self.model('v02');comment=task['comments'][0];return self.call('record',id=task['id'],revision=task['revision'],new_source=str(source),new_source_sha256=sha(source),summary='局部地面换材，原版保留',comments=[dict(key=comment['key'],content_sha256=comment['content_sha256'],status='addressed',note='原坐标地面替换为安山岩')])
 def test_create_and_discover_use_same_object_versions_without_loading_or_accepting_them(self):
  task=self.create();target=self.model('v02');found=self.call('discover',id=task['id']);self.assertEqual(found['candidates'][0]['absolute_source'],str(target));self.assertFalse(found['candidates'][0]['verified']);self.assertEqual(task['returns'],[]);self.assertTrue(task['comments'][0]['verified']);self.assertEqual(self.comments.read_bytes(),self.original)
 def test_record_binds_next_version_and_keeps_claims_separate_from_manual_review(self):
  task=self.create();result=self.record(task);returned=result['returns'][0];self.assertEqual(returned['acceptance'],'pending_user_review');self.assertEqual(returned['review'],{});review=self.call('review',id=task['id'],revision=result['revision'],return_id=returned['id'],comment_key=task['comments'][0]['key'],state='accepted',note='已看实际前后差异，地面符合要求');self.assertEqual(review['returns'][0]['review'][task['comments'][0]['key']]['state'],'accepted');self.assertEqual(self.comments.read_bytes(),self.original);self.assertEqual(sha(self.source),self.hash);self.assertEqual(review['approval'],'not_granted_by_task_registration')
 def test_foreign_object_same_version_and_bad_hash_cannot_be_registered(self):
  task=self.create()
  with self.assertRaisesRegex(ValueError,'同一建筑'):self.record(task,self.model('v02','其他建筑'))
  with self.assertRaisesRegex(ValueError,'同一建筑'):self.record(task,self.source)
  target=self.model('v03')
  with self.assertRaisesRegex(ValueError,'哈希'):self.call('record',id=task['id'],revision=task['revision'],new_source=str(target),new_source_sha256='0'*64,summary='无效')
 def test_stale_revision_and_overwritten_return_are_rejected(self):
  task=self.create();result=self.record(task)
  with self.assertRaisesRegex(ValueError,'任务已更新'):self.call('review',id=task['id'],revision=task['revision'],return_id=result['returns'][0]['id'],comment_key=task['comments'][0]['key'],state='accepted')
  Path(result['returns'][0]['absolute_source']).write_bytes(b'changed')
  with self.assertRaisesRegex(ValueError,'被覆盖'):self.call('get',id=task['id'])
 def test_changed_original_comment_evidence_refuses_stale_completion_claim(self):
  task=self.create();changed=json.loads(self.original);changed['notes'][0]['text']='取消换材';self.comments.write_bytes(json.dumps(changed).encode())
  with self.assertRaisesRegex(ValueError,'证据|评论文件'):self.record(task)
 def test_origin_plan_is_bound_and_changed_plan_is_not_silently_reused(self):
  plan=self.source.parent.parent/'plan.json';plan.write_bytes(b'{"operations":[]}');task=self.call('create',source=str(self.source),source_sha256=self.hash,name='来源',origins=[dict(role='plan',path=str(plan))]);self.assertEqual(task['origins'][0]['sha256'],sha(plan));plan.write_bytes(b'changed')
  with self.assertRaisesRegex(ValueError,'计划或校验包'):self.call('get',id=task['id'])
 def test_relative_registration_survives_workspace_move(self):
  result=self.record(self.create());destination=self.root/'moved';shutil.copytree(self.root/'nbt_models',destination/'nbt_models');moved=dispatch(destination,'get',dict(id=result['id']));self.assertTrue(moved['absolute_source'].startswith(str(destination)));self.assertEqual(moved['returns'][0]['source_sha256'],result['returns'][0]['source_sha256'])
if __name__=='__main__':unittest.main(verbosity=2)
