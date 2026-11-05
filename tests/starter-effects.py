from pathlib import Path
import importlib.util,json,sys,tempfile,unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'.agents/skills/minecraft-nbt-modeler/scripts'))
import nbt_starter_effects as starter
import nbt_effect_assets as effects
import nbt_components as components


class StarterEffects(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.workspace=Path(self.temp.name);self.bundle=starter.catalog()
 def listing(self):return effects.dispatch(self.workspace,'list',{})['items']
 def test_blank_workspace_receives_only_effects_once_and_all_previews_are_complete(self):
  items=self.listing();self.assertEqual(len(items),len(self.bundle['items']));self.assertEqual(components.listing(self.workspace)['items'],[])
  before={p:p.read_bytes() for p in effects.root(self.workspace).rglob('*') if p.is_file()};self.assertEqual({item['id'] for item in self.listing()},{item['id'] for item in items});self.assertEqual(before,{p:p.read_bytes() for p in before})
  with patch('nbt_detail_control.simulate_plan',side_effect=AssertionError('Cached previews must not simulate')):
   for item in items:
    preview=effects.dispatch(self.workspace,'preview',dict(id=item['id'],content_sha256=item['content_sha256']));self.assertTrue(preview['precomputed']);self.assertGreater(preview['changed_blocks'],0);self.assertFalse(preview['nbt_exported']);self.assertTrue(Path(preview['thumbnail']).is_file())
    a=json.loads(Path(preview['before_snapshot']).read_text(encoding='utf8'));b=json.loads(Path(preview['after_snapshot']).read_text(encoding='utf8'));self.assertNotEqual(a['geometry_sha256'],b['geometry_sha256']);self.assertEqual(b['source'],'tool-effect-sample')
  self.assertFalse(list(self.workspace.rglob('*.nbt')));self.assertFalse(list(self.workspace.rglob('*.master.json.gz')))
 def test_existing_id_and_custom_effects_are_never_replaced(self):
  asset=dict(name='用户自己的混材',settings=dict(pattern=dict(enabled=True,fraction=.1)))
  custom=effects.save(self.workspace,asset);identifier=self.bundle['items'][0]['id'];collision=effects.file_for(self.workspace,identifier);collision.parent.mkdir(parents=True);collision.write_text(json.dumps(effects.validate(asset)),encoding='utf8');original=collision.read_bytes()
  items=self.listing();self.assertEqual(len(items),len(self.bundle['items'])+1);self.assertEqual(collision.read_bytes(),original);self.assertIn(custom['id'],[item['id'] for item in items])
 def test_archive_and_explicit_file_removal_do_not_resurrect_on_refresh(self):
  items=self.listing();first=items[0];effects.dispatch(self.workspace,'archive',dict(id=first['id'],archived=True));file=effects.file_for(self.workspace,first['id']);original=file.read_bytes();second=effects.file_for(self.workspace,items[1]['id']);second.unlink()
  self.assertTrue(next(item for item in self.listing() if item['id']==first['id'])['archived']);self.assertEqual(file.read_bytes(),original);self.assertFalse(second.exists())
 def test_changed_or_missing_cache_is_recomputed_without_trusting_stale_geometry(self):
  item=next(item for item in self.listing() if item['name']=='三格宽石砖步道');file=effects.file_for(self.workspace,item['id']);(file.parent/'preview/after.json').write_text('{}',encoding='utf8')
  preview=effects.dispatch(self.workspace,'preview',dict(id=item['id']));self.assertFalse(preview.get('precomputed',False));self.assertGreater(preview['changed_blocks'],0);self.assertFalse(preview['nbt_exported'])
 def test_corrupt_release_pack_is_rejected_before_any_asset_is_installed(self):
  with patch.object(starter,'sha',return_value='0'*64):
   with self.assertRaisesRegex(ValueError,'初始效果资料缺失'):self.listing()
  self.assertFalse(effects.root(self.workspace).exists())
 def test_generated_release_pack_matches_sources(self):
  spec=importlib.util.spec_from_file_location('starter_builder',ROOT/'scripts/build-starter-effects.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);self.assertEqual(len(module.check()['items']),len(self.bundle['items']))


if __name__=='__main__':unittest.main(verbosity=2)
