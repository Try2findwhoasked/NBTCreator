from pathlib import Path
import copy,json,sys,tempfile,unittest,uuid,shutil
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_architect import dispatch,FIELDS,validate_standard
from nbt_history import file_hash,History
from nbt_assembly import Volume
from nbt_snbt import save_snbt
from nbt_task import write_snapshot
from nbt_prompts import save,read_prompt
from nbt_finalize import finalize

class ArchitectTools(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.w=Path(self.temp.name).resolve();self.root=self.w/'nbt_models/standalone/审查工坊';self.source=self.make('v01');self.new=self.make('v02',3)
 def make(self,version,height=2):
  folder=self.root/version;file=folder/'master/model.snbt';file.parent.mkdir(parents=True);model=Volume((48,16,48));model.box((0,0,0),(47,15,47),'stone_bricks');model.box((2,4,2),(45,13,45),'air');walls={p for p in model.blocks if 4<=p[1]<=13 and (p[0] in (0,1,46,47) or p[2] in (0,1,46,47))};
  if height>2:model.put((20,4,20),'andesite')
  save_snbt(file,model,walls);(folder/'coordinates.json').write_text(json.dumps(dict(cells=[[0,0]],door_y=4,ports=[],start=[5.5,4,5.5],targets={'centre':[24.5,4,24.5]},interior_probes=[[12,8,12]],protected_boxes=[],protected_paths=[],cameras=[])),encoding='utf8');return file
 def call(self,action,**params):return dispatch(self.w,action,params)
 def norms(self):return self.call('standards-save',revision=0,fields={key:'统一采用石砖' if key=='materials' else '石构山城' if key=='name' else '' for key in FIELDS})
 def test_interrupted_standards_commit_can_resume_existing_revision_archive(self):
  with patch('nbt_architect.write',side_effect=OSError('interrupted')):
   with self.assertRaises(OSError):self.norms()
  result=self.norms();self.assertEqual(result['revision'],1);self.assertEqual(self.call('standards-get'),result)
 def feedback(self):
  folder=self.source.parents[1]/'修改意见';folder.mkdir();snapshot=self.source.parents[1]/'previews/snapshot.json';snap=write_snapshot(self.source,snapshot);binding=dict(kind='3d',source=str(self.source),source_sha256=file_hash(self.source),geometry_sha256=snap['geometry_sha256'],snapshot=str(snapshot),snapshot_sha256=file_hash(snapshot),size=[48,16,48]);note=dict(id='test',number=1,text='入口保留两格通路',status='open',anchors=[dict(kind='voxel',position=[1,0,1],state='minecraft:stone_bricks',geometry_sha256=snap['geometry_sha256'])],references=[]);file=folder/'comments.json';file.write_text(json.dumps(dict(schema_version=2,binding=binding,notes=[note])),encoding='utf8');index=dict(schema_version=1,records=[dict(source='../master/model.snbt',source_sha256=file_hash(self.source),feedback_file='comments.json',feedback_sha256=file_hash(file),notes=[note])]);(folder/'评论索引.json').write_text(json.dumps(index),encoding='utf8');return file
 def cross_request(self):return dict(source=str(self.new),source_sha256=file_hash(self.new),reference_source=str(self.source))
 def test_cross_version_discovery_also_finds_unregistered_legacy_sources(self):
  with patch('nbt_refine.read_master',side_effect=AssertionError('discovery must not load models')):
   result=self.call('cross-list',source=str(self.new),source_sha256=file_hash(self.new))
  self.assertEqual([item['absolute_source'] for item in result['versions']],[str(self.source)]);self.assertFalse(result['truncated'])
 def test_standards_are_revisioned_and_prompt_snapshots_do_not_follow_latest(self):
  first=self.norms();validate_standard(first);request=dict(session_id=uuid.uuid4().hex,document=dict(project=dict(name='小屋',stage='draft',buildingShape='single'),design_standard=first),text='规范：统一采用石砖',plan={},context={});saved=save(self.w,request)
  fields=copy.deepcopy(first['fields']);fields['materials']='统一采用木材';self.call('standards-save',revision=first['revision'],fields=fields)
  self.assertEqual(read_prompt(self.w,saved['index'],saved['id'])['document']['design_standard'],first)
  self.assertEqual(len(list((self.w/'nbt_models/_workspaces/project_design/revisions').glob('*.json'))),2)
  with self.assertRaisesRegex(ValueError,'刷新'):self.call('standards-save',revision=first['revision'],fields=fields)
  request['document']['design_standard']['fields']['materials']='tampered'
  with self.assertRaisesRegex(ValueError,'哈希'):save(self.w,request)
 def test_delivery_checks_and_continue_keep_finalized_bytes_and_annotations_untouched(self):
  annotation=self.feedback();original=annotation.read_bytes();result=finalize(self.w,self.source);target=Path(result['output']);before={str(p.relative_to(target)):p.read_bytes() for p in target.rglob('*') if p.is_file()};source=self.source.read_bytes()
  checked=self.call('deliveries',sources=[str(self.source)])['items'][0];self.assertEqual(checked['status'],'finalized')
  derived=self.call('continue',source=str(self.source),source_sha256=file_hash(self.source));self.assertTrue(derived['source'].endswith('.snbt'));self.assertNotEqual(Path(derived['source']),self.source);self.assertEqual(self.source.read_bytes(),source);self.assertEqual(annotation.read_bytes(),original);self.assertEqual(before,{str(p.relative_to(target)):p.read_bytes() for p in target.rglob('*') if p.is_file()});self.assertFalse((Path(derived['source']).parents[1]/'修改意见').exists());self.assertTrue(History(self.w).get(derived['version']['id'])['manifest']['parent'])
  (target/'master/model.nbt').write_bytes(b'broken');self.assertEqual(self.call('deliveries',sources=[str(self.source)])['items'][0]['status'],'changed')
  with self.assertRaises(ValueError):self.call('continue',source=str(self.source),source_sha256=file_hash(self.source))
 def test_cross_review_binds_both_versions_and_does_not_copy_or_resolve_original_notes(self):
  annotation=self.feedback();original=annotation.read_bytes();request=self.cross_request();data=self.call('cross-list',**request);item=data['items'][0];self.assertTrue(item['evidence_valid'])
  saved=self.call('cross-save',**request,reference_sha256=data['reference_sha256'],revision=data['revision'],key=item['key'],content_sha256=item['content_sha256'],state='accepted',note='已在新版查看入口');self.assertEqual(saved['items'][0]['review']['state'],'accepted');self.assertEqual(annotation.read_bytes(),original);self.assertFalse((self.new.parents[1]/'修改意见/评论索引.json').exists())
  with self.assertRaisesRegex(ValueError,'刷新'):self.call('cross-save',**request,reference_sha256=data['reference_sha256'],revision=data['revision'],key=item['key'],content_sha256=item['content_sha256'],state='accepted')
  self.new.write_text(self.new.read_text().replace('stone_bricks','andesite'),encoding='utf8');self.assertEqual(self.call('cross-list',**self.cross_request())['items'][0]['review']['state'],'pending')
  self.assertTrue((self.new.parents[1]/'修改意见/跨版本核对.json').is_file())
 def test_changed_evidence_and_foreign_buildings_cannot_inherit_review(self):
  file=self.feedback();request=self.cross_request();data=self.call('cross-list',**request);item=data['items'][0];file.write_text('{}')
  with self.assertRaises((ValueError,KeyError)):self.call('cross-save',**request,reference_sha256=data['reference_sha256'],revision=data['revision'],key=item['key'],content_sha256=item['content_sha256'],state='accepted')
  foreign=self.w/'nbt_models/standalone/另一座/v01/master/model.snbt';foreign.parent.mkdir(parents=True);shutil.copyfile(self.source,foreign)
  with self.assertRaisesRegex(ValueError,'同一建筑'):self.call('cross-list',source=str(foreign),source_sha256=file_hash(foreign),reference_source=str(self.source))
 def test_workspace_escape_and_manifest_escape_are_not_followed(self):
  result=self.call('deliveries',sources=['../outside.snbt']);self.assertEqual(result['items'][0]['status'],'unavailable')
  result=finalize(self.w,self.source);manifest=Path(result['output'])/'release.json';data=json.loads(manifest.read_text(encoding='utf8'));data['files']['../../other.nbt']={'sha256':'0'*64};manifest.write_text(json.dumps(data),encoding='utf8');self.assertEqual(self.call('deliveries',sources=[str(self.source)])['items'][0]['status'],'unavailable')

if __name__=='__main__':unittest.main(verbosity=2)
