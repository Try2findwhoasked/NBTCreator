from pathlib import Path
import copy,json,sys,tempfile,unittest,uuid
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_architect import dispatch
from nbt_project.constraints import validate_snapshot,validate_selection
from nbt_prompts import save,read_prompt

class ProjectConstraints(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.workspace=Path(self.temp.name)
 def call(self,action,**request):return dispatch(self.workspace,action,request)
 def create(self,**changes):
  return self.call('constraints-save',revision=0,name='L形32格网格',rules={'buildingShape':'l_shape','size':[64,24,64],'cell_size':32,'cells':[[0,0],[0,1],[1,1]],'footprint':'缺角留作庭院'},actor='agent',**changes)
 def test_empty_project_has_no_implicit_constraints_or_writes(self):
  self.assertEqual(self.call('constraints-list')['items'],[]);self.assertFalse((self.workspace/'nbt_models').exists())
 def test_registry_lists_selectable_builtin_and_workspace_rules_and_keeps_snapshots(self):
  saved=self.create()['saved']
  reply=self.call('constraints-registry',folders=[''],summary=True)['groups']
  self.assertEqual([group['source'] for group in reply],['builtin','workspace'])
  self.assertEqual(reply[1]['items'][0]['id'],saved['id'])
  square=next(item for item in reply[0]['items'] if item['name']=='2×2 方形')
  self.assertNotIn('rules',square)
  selected=self.call('constraints-registry',folders=[''],id=square['id'])['groups'][0]['items'][0]
  validate_snapshot(selected)
  self.assertEqual(selected['sha256'],square['sha256'])
  self.assertEqual(selected['rules']['cells'],[[0,0],[1,0],[0,1],[1,1]])
  self.assertEqual(selected['rules']['cell_size'],48)
  extension=next(item for item in reply[0]['items'] if item['name']=='SAODG 房间接入')
  snapshot=self.call('constraints-registry',id=extension['id'])['groups'][0]['items'][0]
  validate_snapshot(snapshot)
  self.assertEqual(validate_selection([snapshot,selected])['opening_size'],[6,5])
  self.assertTrue(snapshot['rules']['require_enclosure'])
  self.assertNotIn('integration',selected['rules'])
  self.assertEqual(len(self.call('constraints-list')['items']),1)
 def test_agent_and_ui_share_revisioned_records_and_old_prompts_keep_snapshots(self):
  first=self.create();item=first['saved'];validate_snapshot(item);self.assertEqual(item['actor'],'agent')
  request=dict(session_id=uuid.uuid4().hex,document=dict(schema_version=1,project=dict(name='庭院',stage='draft',buildingShape='standalone',size=[32,24,32]),constraints=[item]),text='采用L形32格网格',plan={},context={})
  saved=save(self.workspace,request);changed=self.call('constraints-save',revision=first['revision'],id=item['id'],name='L形新要求',rules={**item['rules'],'requirements':'净高至少4格'})
  self.assertEqual(changed['saved']['revision'],2)
  self.assertEqual(read_prompt(self.workspace,saved['index'],saved['id'])['document']['constraints'],[item])
  removed=self.call('constraints-delete',revision=changed['revision'],id=item['id']);self.assertEqual(removed['items'],[])
  self.assertEqual(read_prompt(self.workspace,saved['index'],saved['id'])['document']['constraints'],[item]);self.assertEqual(len(list(self.workspace.rglob('constraint-revisions/*/*.json'))),2)
 def test_selected_policy_is_stored_in_cli_handoff_context(self):
  created=self.call('constraints-save',revision=0,name='露天入口',rules={
      'require_enclosure':False,'openings_policy':'required','opening_size':[3,4]})
  project=dict(name='庭院',stage='draft',buildingShape='standalone',size=[16,8,16])
  request=dict(session_id=uuid.uuid4().hex, document=dict(schema_version=1,project=project,
      constraints=[created['saved']]),text='庭院与通行洞口',context={'require_enclosure':True})
  result=save(self.workspace,request)
  self.assertEqual(read_prompt(self.workspace,result['index'],result['id'])['context'],
      dict(require_enclosure=False,openings_policy='required',opening_size=[3,4]))
 def test_stale_writes_duplicate_names_invalid_rules_and_forged_snapshots_fail(self):
  created=self.create();item=created['saved']
  with self.assertRaisesRegex(ValueError,'刷新'):self.call('constraints-save',revision=0,name='另一项',rules={'requirements':'留出通路'})
  with self.assertRaisesRegex(ValueError,'同名'):self.call('constraints-save',revision=1,name=item['name'],rules={'requirements':'留出通路'})
  for rules in ({'size':[True,24,32]},{'cells':[[0,0]]},{'cell_size':32,'size':[32,24,32],'cells':[[1,0]]},{'cell_size':32,'cells':[[0,0],[0,0]]},{'source':'../escape'},{'requirements':''},{'size_policy':'fixed'}):
   with self.subTest(rules=rules),self.assertRaises(ValueError):self.call('constraints-save',revision=1,name='非法',rules=rules)
  tampered=copy.deepcopy(item);tampered['rules']['size']=[96,24,96]
  with self.assertRaisesRegex(ValueError,'哈希'):validate_selection([tampered])
 def test_conflicts_existing_geometry_and_out_of_bounds_cells_are_rejected(self):
  first=self.create();item=first['saved'];second=self.call('constraints-save',revision=1,name='1×1',rules={'size':[32,24,32]})['saved']
  with self.assertRaisesRegex(ValueError,'冲突'):validate_selection([item,second])
  reference=self.call('constraints-save',revision=2,name='参考尺寸',rules={'size':[64,24,64],'size_policy':'reference'})['saved']
  with self.assertRaisesRegex(ValueError,'冲突'):validate_selection([item,reference])
  with self.assertRaisesRegex(ValueError,'已有建筑'):validate_selection([item],dict(source='existing.snbt',buildingShape='single',size=[32,24,32]))
  cells=self.call('constraints-save',revision=3,name='横向两格',rules={'cells':[[0,0],[1,0]],'cell_size':32})['saved']
  with self.assertRaisesRegex(ValueError,'超出'):validate_selection([cells],dict(size=[32,24,32]))
 def test_interrupted_new_save_leaves_library_retryable(self):
  with patch('nbt_project.constraints.write',side_effect=OSError('interrupted')):
   with self.assertRaises(OSError):self.create()
  result=self.create();self.assertEqual(result['saved']['revision'],1);validate_snapshot(result['saved'])
 def test_workspaces_are_isolated_and_snapshot_identity_is_bound(self):
  first=self.create()['saved'];other=self.workspace/'other';self.assertEqual(dispatch(other,'constraints-list',{})['items'],[])
  forged=copy.deepcopy(first);forged['revision']+=1
  with self.assertRaisesRegex(ValueError,'哈希'):validate_snapshot(forged)
  with self.assertRaisesRegex(ValueError,'重复'):validate_selection([first,first])
 def test_folder_files_follow_the_project_tree_and_keep_independent_revisions(self):
  raw='nbt_models/SAODG'
  single=raw+'/single';corner=raw+'/l_shape'
  for folder in (single,corner):(self.workspace/folder).mkdir(parents=True)
  self.assertEqual(self.call('constraints-list',folder=single)['items'],[])
  self.assertFalse((self.workspace/single/'项目约束.json').exists())
  first=self.create(folder=corner)
  self.call('constraints-save',folder=single,revision=0,name=first['saved']['name'],rules={'requirements':'四边留通道'})
  self.assertEqual(self.call('constraints-list',folder=raw)['items'],[])
  self.assertEqual(self.call('constraints-list',folder=corner)['items'],[first['saved']])
  self.assertEqual(self.call('constraints-list')['items'],[])
  self.assertTrue((self.workspace/corner/'项目约束.json').is_file())
  self.assertEqual(first['saved']['folder'],corner)
  with self.assertRaisesRegex(ValueError,'不存在'):self.call('constraints-delete',folder=single,revision=1,id=first['saved']['id'])
  with self.assertRaisesRegex(ValueError,'哈希'):validate_snapshot(dict(first['saved'],folder=single))
  for folder in ('nbt_models/../SAODG','nbt_models/_workspaces','D:/SAODG','nbt_models/not-yet-created'):
   with self.subTest(folder=folder),self.assertRaises(ValueError):self.call('constraints-list',folder=folder)

if __name__=='__main__':unittest.main(verbosity=2)
