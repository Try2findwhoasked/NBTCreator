from pathlib import Path
import copy
import hashlib
import json
import sys
import tempfile
import unittest
import shutil
import subprocess
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_assembly import Volume
from nbt_refine import save_master
from nbt_task import write_snapshot
from nbt_feedback_tasks import dispatch

def sha(file):return hashlib.sha256(Path(file).read_bytes()).hexdigest()

class FeedbackTasks(unittest.TestCase):
 def test_durable_retry_does_not_duplicate_group_or_require_unchanged_live_evidence(self):
  from nbt_agent_protocol import ProtocolError
  listing=self.call('list');member=listing['comments'][0];request=dict(self.request,request_id='feedback-retry-0001',revision=0,title='真实分组',members=[dict(key=member['key'],evidence_sha256=member['evidence_sha256'])]);result=dispatch(self.workspace,'create',request)
  self.assertEqual(dispatch(self.workspace,'create',request),result)
  with self.assertRaises(ProtocolError) as failure:dispatch(self.workspace,'create',dict(request,title='不同意图'))
  self.assertEqual(failure.exception.code,'IDEMPOTENCY_CONFLICT');self.source.write_bytes(b'changed after accepted operation');self.assertEqual(dispatch(self.workspace,'create',request),result)
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.workspace=Path(self.temp.name);self.version=self.workspace/'nbt_models/single/意见测试/v01';self.source=self.version/'master/master_geometry.json.gz';self.source.parent.mkdir(parents=True);model=Volume((8,6,8));model.box((0,0,0),(7,0,7),'stone_bricks');save_master(self.source,model,set());self.original=self.source.read_bytes();self.snapshot=self.version/'previews/snapshot.json';snap=write_snapshot(self.source,self.snapshot);self.hash=sha(self.source)
  self.folder=self.version/'修改意见';self.folder.mkdir();self.file=self.folder/'comments.json';binding=dict(kind='3d',source=str(self.source),source_sha256=self.hash,geometry_sha256=snap['geometry_sha256'],snapshot=str(self.snapshot),snapshot_sha256=sha(self.snapshot),size=[8,6,8]);notes=[]
  for i,text in enumerate(['保留这块地面','保留这块地面','删除这块地面','保留这块地面']):notes.append(dict(id=str(i),number=i+1,text=text,status='open',anchors=[dict(kind='voxel',number=i+1,position=[1 if i<3 else 5,0,1],state='minecraft:stone_bricks',geometry_sha256=snap['geometry_sha256'])],references=[]))
  self.file.write_text(json.dumps(dict(schema_version=2,binding=binding,notes=notes)),encoding='utf8');index=dict(schema_version=1,records=[dict(source='../master/master_geometry.json.gz',source_sha256=self.hash,feedback_file='comments.json',feedback_sha256=sha(self.file),notes=notes)]);(self.folder/'评论索引.json').write_text(json.dumps(index));self.original_comments=self.file.read_bytes();self.request=dict(source=str(self.source),source_sha256=self.hash)
 def call(self,action,**kwargs):return dispatch(self.workspace,action,dict(self.request,**kwargs))
 def create(self,keys=None,title='保留地面'):
  listing=self.call('list');members=[dict(key=item['key'],evidence_sha256=item['evidence_sha256']) for item in listing['comments'] if keys is None or item['key'] in keys];return self.call('create',revision=listing['revision'],title=title,category='构造',members=members)
 def test_same_location_duplicates_and_overlaps_are_distinguished(self):
  result=self.call('list');duplicate=result['suggestions']['duplicates'];self.assertEqual(len(duplicate),1);self.assertEqual(len(duplicate[0]),2);self.assertTrue(result['suggestions']['overlaps']);self.assertNotIn(result['comments'][3]['key'],duplicate[0]);self.assertEqual(self.file.read_bytes(),self.original_comments)
 def test_grouping_preserves_all_original_evidence_and_history(self):
  listing=self.call('list');group=self.create(listing['suggestions']['duplicates'][0]);task=group['tasks'][0];self.assertEqual(len(task['members']),2);self.assertEqual(group['revision'],1);evidence=self.call('evidence',id=task['id']);self.assertEqual(len(evidence['records']),2);self.assertEqual(evidence['records'][0]['note']['text'],'保留这块地面');self.assertEqual(self.file.read_bytes(),self.original_comments);self.assertEqual(self.source.read_bytes(),self.original);self.assertEqual(len(group['history']),1)
 def test_task_status_classification_conflicts_and_stale_revision(self):
  comments=self.call('list')['comments'];first=self.create([comments[0]['key']]);second=self.create([comments[2]['key']],title='另一个任务');a,b=second['tasks'];updated=self.call('update',revision=second['revision'],id=a['id'],patch=dict(status='blocked',category='通路',reason='同一位置需核对',conflicts=[b['id']]));self.assertEqual(updated['tasks'][0]['status'],'blocked')
  with self.assertRaisesRegex(ValueError,'其他页面'):self.call('update',revision=second['revision'],id=a['id'],patch={'status':'done'})
  with self.assertRaisesRegex(ValueError,'状态无效'):self.call('update',revision=updated['revision'],id=a['id'],patch={'status':'approved'})
  self.assertEqual(self.file.read_bytes(),self.original_comments)
 def test_merge_keeps_members_original_tasks_and_resets_completion(self):
  comments=self.call('list')['comments'];self.create([comments[0]['key']]);data=self.create([comments[2]['key']],title='待核对');a,b=data['tasks'];data=self.call('update',revision=data['revision'],id=a['id'],patch={'status':'done'});merged=self.call('merge',revision=data['revision'],ids=[a['id'],b['id']]);self.assertEqual(merged['tasks'][0]['status'],'todo');self.assertEqual(len(merged['tasks'][0]['members']),2);self.assertEqual(merged['tasks'][1]['merged_into'],a['id']);self.assertEqual(self.file.read_bytes(),self.original_comments)
 def test_changed_or_missing_evidence_refuses_creation_or_read(self):
  data=self.call('list');member=data['comments'][0];bad=dict(key=member['key'],evidence_sha256='0'*64)
  with self.assertRaisesRegex(ValueError,'变化'):self.call('create',revision=0,title='任务',members=[bad])
  group=self.create([member['key']]);task=group['tasks'][0];file=self.workspace/task['members'][0]['evidence_file'];file.write_text('tampered')
  with self.assertRaisesRegex(ValueError,'证据已缺失或被改动'):self.call('evidence',id=task['id'])
 def test_changed_original_note_is_visible_without_replacing_saved_evidence(self):
  data=self.call('list');group=self.create([data['comments'][0]['key']]);task=group['tasks'][0];record=json.loads(self.file.read_text());record['notes'][0]['status']='resolved';self.file.write_text(json.dumps(record));index=json.loads((self.folder/'评论索引.json').read_text());index['records'][0]['feedback_sha256']=sha(self.file);(self.folder/'评论索引.json').write_text(json.dumps(index));updated=self.call('list');self.assertTrue(updated['tasks'][0]['evidence_updates']);saved=self.call('evidence',id=task['id']);self.assertEqual(saved['records'][0]['note']['status'],'open')
 def test_source_binding_and_workspace_escape_are_rejected(self):
  with self.assertRaisesRegex(ValueError,'源建筑已变化'):dispatch(self.workspace,'list',dict(self.request,source_sha256='0'*64))
  with self.assertRaisesRegex(ValueError,'当前工作区'):dispatch(self.workspace,'list',dict(self.request,source='../outside.master.gz'))
 def test_unrelated_note_update_does_not_mark_group_members_changed(self):
  listing=self.call('list');group=self.create(listing['suggestions']['duplicates'][0]);record=json.loads(self.file.read_text());record['notes'][2]['status']='resolved';self.file.write_text(json.dumps(record));index=json.loads((self.folder/'评论索引.json').read_text());index['records'][0]['feedback_sha256']=sha(self.file);(self.folder/'评论索引.json').write_text(json.dumps(index));self.assertEqual(self.call('list')['tasks'][0]['evidence_updates'],[])
 def test_read_checks_artifact_bytes_while_preserving_original_comment_text(self):
  group=self.create([self.call('list')['comments'][0]['key']]);self.snapshot.write_text('changed snapshot');result=self.call('evidence',id=group['tasks'][0]['id']);self.assertEqual(result['records'][0]['note']['text'],'保留这块地面');self.assertEqual(next(item for item in result['records'][0]['assets'] if item['role']=='snapshot')['status'],'missing_or_changed')
 def test_evidence_paging_keeps_full_records_and_reports_remaining_pages(self):
  group=self.create();id=group['tasks'][0]['id'];first=self.call('evidence',id=id,offset=0,limit=1);second=self.call('evidence',id=id,offset=first['next_offset'],limit=1);self.assertEqual(first['total'],4);self.assertEqual(len(first['records']),1);self.assertNotEqual(first['records'][0]['note']['id'],second['records'][0]['note']['id'])
 def test_workspace_skill_updates_tasks_after_relocation_without_gui(self):
  from nbt_exposure import apply
  group=self.create([self.call('list')['comments'][0]['key']]);moved=self.workspace/'moved';moved.mkdir();shutil.copytree(self.workspace/'nbt_models',moved/'nbt_models');old=self.workspace/'nbt_models';backup=self.workspace/'old_data';self.assertTrue(old.resolve().is_relative_to(self.workspace.resolve()) and backup.resolve().is_relative_to(self.workspace.resolve()));old.rename(backup);apply(moved);request=moved/'request.json';request.write_text(json.dumps(dict(source=self.source.relative_to(self.workspace).as_posix(),source_sha256=self.hash,revision=group['revision'],id=group['tasks'][0]['id'],patch={'status':'working'})))
  run=subprocess.run([sys.executable,str(moved/'.agents/skills/nbtcreator-workspace/nbt.py'),'feedback-tasks','--workspace','.', 'update','--request',str(request)],cwd=moved,capture_output=True,text=True,encoding='utf8');self.assertEqual(run.returncode,0,run.stdout+run.stderr);self.assertEqual(json.loads(run.stdout)['tasks'][0]['status'],'working');self.assertEqual(json.loads((self.workspace/'old_data/single/意见测试/v01/修改意见/意见任务.json').read_text())['tasks'][0]['status'],'todo')
 def test_identical_text_on_opposite_faces_is_not_a_duplicate_candidate(self):
  record=json.loads(self.file.read_text());record['notes'][0]['anchors'][0]['normal']=[1,0,0];record['notes'][1]['anchors'][0]['normal']=[-1,0,0];self.file.write_text(json.dumps(record));index=json.loads((self.folder/'评论索引.json').read_text());index['records'][0]['feedback_sha256']=sha(self.file);(self.folder/'评论索引.json').write_text(json.dumps(index));self.assertEqual(self.call('list')['suggestions']['duplicates'],[])
 def add_image_notes(self):
  from PIL import Image
  image=self.version/'previews/入口.png';Image.new('RGB',(8,8),(120,130,140)).save(image);index=json.loads((self.folder/'评论索引.json').read_text());geometry=json.loads(self.snapshot.read_text())['geometry_sha256']
  for i,geom in enumerate([geometry,'f'*64]):
   file=self.folder/('image'+str(i)+'.json');binding=dict(kind='image',source=str(self.source),source_sha256=self.hash,geometry_sha256=geom,image=str(image),image_sha256=sha(image));note=dict(id='image-note-'+str(i),number=1,text='保留图片中的节点',status='open',anchors=[dict(kind='image',number=1,x=.5,y=.5)],references=[]);file.write_text(json.dumps(dict(binding=binding,notes=[note])));index['records'].append(dict(source='../master/master_geometry.json.gz',source_sha256=self.hash,feedback_file=file.name,feedback_sha256=sha(file)))
  (self.folder/'评论索引.json').write_text(json.dumps(index))
 def test_identical_image_bytes_at_different_geometry_versions_are_not_deduplicated(self):
  self.add_image_notes();result=self.call('list');keys={item['key'] for item in result['comments'] if item['kind']=='image'};self.assertEqual(len(keys),2);self.assertFalse(any(set(group)==keys for group in result['suggestions']['duplicates']))
 def test_manual_cross_view_group_keeps_image_pixels_separate_from_voxel_xyz(self):
  self.add_image_notes();comments=self.call('list')['comments'];keys=[next(item['key'] for item in comments if item['kind']==kind) for kind in ('3d','image')];group=self.create(keys);result=self.call('evidence',id=group['tasks'][0]['id']);self.assertEqual({record['binding']['kind'] for record in result['records']},{'3d','image'});image=next(record for record in result['records'] if record['binding']['kind']=='image');self.assertEqual(image['note']['anchors'][0]['x'],.5);self.assertNotIn('position',image['note']['anchors'][0]);self.assertEqual(self.file.read_bytes(),self.original_comments)
if __name__=='__main__':unittest.main(verbosity=2)
