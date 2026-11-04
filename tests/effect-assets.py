from pathlib import Path
import json,sys,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_effect_assets import dispatch
from nbt_asset_batches import dispatch as batches
from nbt_asset_organization import organize
from nbt_refine import read_master
import nbt_components as components

class Effects(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.asset=dict(name='石砖步道',settings=dict(operations=[dict(kind='auto_road',label='步道',classification='body',lo=[0,0,0],hi=[47,15,47],start=[6,3,6],end=[20,3,20],width=3,depth=1,route='straight',state='stone_bricks')]))
 def test_agent_save_read_and_real_before_after_preview(self):
  item=dispatch(self.root,'save',dict(asset=self.asset));self.assertTrue((self.root/item['manifest']).is_file());loaded=dispatch(self.root,'get',dict(id=item['id']));self.assertEqual(loaded['settings'],self.asset['settings']);preview=dispatch(self.root,'preview',dict(id=item['id']));self.assertGreater(preview['changed_blocks'],0);self.assertTrue(Path(preview['thumbnail']).is_file());before=read_master(Path(preview['before_snapshot']).with_name('before.master.json.gz'))[0];after=read_master(Path(preview['after_snapshot']).with_name('after.master.json.gz'))[0];self.assertNotEqual(before.fingerprint(),after.fingerprint());self.assertFalse(preview['nbt_exported']);self.assertEqual(batches(self.root,'read',dict(manifest=json.loads((self.root/item['manifest']).read_text())))['items'][0]['type'],'effect')
 def test_full_panel_patterns_use_same_engine(self):
  from nbt_detail_control import default_settings
  for panel in ['pattern','weathering','floor','replace','structure']:
   settings=default_settings();settings[panel]['enabled']=True
   for key in ['lo','hi','whole_region','max_changed_blocks']:settings.pop(key)
   item=dispatch(self.root,'save',dict(asset=dict(name=panel,settings=settings)));preview=dispatch(self.root,'preview',dict(id=item['id']));self.assertTrue(Path(preview['after_snapshot']).is_file());self.assertGreaterEqual(preview['changed_blocks'],0)
 def test_effect_json_batch_import_and_generated_manifest(self):
  from nbt_effect_assets import file_for
  item=dispatch(self.root,'save',dict(asset=self.asset));result=batches(self.root,'import',dict(paths=[str(file_for(self.root,item['id']))]));self.assertEqual(result['count'],1);self.assertEqual(result['entries'][0]['type'],'effect');listing=batches(self.root,'generate',dict(scope='effects',name='效果清单'));self.assertEqual(batches(self.root,'read',dict(id=listing['id']))['count'],2)
 def test_partial_panel_settings_preview_and_compile_without_filling_target_values(self):
  settings=dict(pattern=dict(enabled=True,fraction=.02,palette=[dict(state='andesite',weight=1)]));item=dispatch(self.root,'save',dict(asset=dict(name='局部混材配置',settings=settings)));self.assertEqual(dispatch(self.root,'compile',dict(id=item['id']))['settings'],settings);preview=dispatch(self.root,'preview',dict(id=item['id']));self.assertGreater(preview['changed_blocks'],0);self.assertFalse(preview['nbt_exported'])
 def test_local_floor_level_translates_with_recipe_origin(self):
  from nbt_recipes import translate_operation
  op=dict(kind='weathering',lo=[0,1,0],hi=[15,2,15],floor=dict(levels=[1],fraction=.1));moved=translate_operation(op,[4,3,4]);self.assertEqual(moved['floor']['levels'],[4]);self.assertEqual(op['floor']['levels'],[1]);self.assertEqual(moved['lo'],[4,4,4])
 def test_forbidden_bindings_and_stale_content_rejected(self):
  for settings in [dict(source='secret'),dict(max_changed_blocks=99999),dict(lo=[0,0,0]),dict(operations=[dict(self.asset['settings']['operations'][0],write_group='a'*36)])]:
   with self.assertRaises(ValueError):dispatch(self.root,'save',dict(asset=dict(name='非法',settings=settings)))
  item=dispatch(self.root,'save',dict(asset=self.asset))
  with self.assertRaises(ValueError):dispatch(self.root,'compile',dict(id=item['id'],content_sha256='0'*64))
  self.assertEqual(dispatch(self.root,'compile',dict(id=item['id']))['settings'],self.asset['settings'])
 def test_legacy_settings_and_recipe_defaults_are_migrated_idempotently(self):
  import nbt_recipes as recipes
  file=self.root/'nbt_models/_workspaces/effects/01.json';file.parent.mkdir(parents=True);file.write_text(json.dumps(dict(settings=self.asset['settings'],source='old.master')))
  recipes.store(self.root,dict(schema_version=1,asset_type='recipe',name='参数梁',tags=['01'],parameters={'width':dict(type='integer',default=3)},operations=[dict(kind='box',label='梁',classification='body',lo=[1,3,1],hi=[{'param':'width'},3,1],state='stone')]))
  result=organize(self.root);self.assertEqual(len(result['migrated_effects']),1);self.assertEqual(len(result['migrated_recipes']),1);self.assertTrue(file.is_file());self.assertEqual(organize(self.root)['migrated_recipes'],[]);item=dispatch(self.root,'get',dict(id=result['migrated_recipes'][0]['effect_id']));self.assertTrue(item['source_recipe_id']);compiled=dispatch(self.root,'compile',dict(id=item['id'],position=[4,3,4]));self.assertEqual(compiled['settings']['operations'][0]['lo'],[5,6,5])
 def test_semantic_organization_keeps_ids_geometry_and_backup(self):
  item=components.store(self.root,dict(schema_version=1,name='石柱',tags=['起步资产库','01'],size=[2,3,2],anchor=[0,0,0],palette=['stone'],blocks=[[0,0,0,0,False]]));file=components.component_file(self.root,item['id']);legacy=json.loads(file.read_text());legacy['tags']=['起步资产库','01'];file.write_text(json.dumps(legacy));before=components.load(self.root,item['id']);report=organize(self.root);after=components.load(self.root,item['id']);self.assertEqual(report['changed'],1);self.assertEqual(after['tags'],['建筑骨架']);self.assertEqual(before['content_sha256'],after['content_sha256']);self.assertEqual(organize(self.root)['changed'],0);self.assertTrue(list((self.root/'nbt_models/asset_library/_migration').glob('*/*.json')))

if __name__=='__main__':unittest.main(verbosity=2)
