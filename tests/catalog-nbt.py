"""Standalone full NBT discovery and workspace normalization, synthetic only."""
import sys,tempfile,unittest,shutil,json
from unittest.mock import patch
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_detail_control import catalog,inspect_source,source_snapshot,default_settings
from nbt_model import Model
from nbt_refine import save_master

class CatalogNbt(unittest.TestCase):
 def test_nested_runtime_and_master_are_same_version_without_a_descriptor(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t).resolve();folder=root/'nbt_models/single/测试厅/v1';self.fixture(folder)
   m=Model((12,12,12));m.box((0,0,0),(11,11,11),'stone_bricks');m.box((2,2,2),(9,9,9),'air')
   (folder/'master').mkdir();(folder/'runtime/parts').mkdir(parents=True);save_master(folder/'master/master.json.gz',m,set());shutil.copyfile(folder/'master/master.json.gz',folder/'runtime/parts/master_geometry.json.gz')
   self.assertEqual(len(catalog(root,root/'cache.json')['models']),1)
   other=root/'nbt_models/single/测试厅/v2/master';other.mkdir(parents=True);shutil.copyfile(folder/'master/master.json.gz',other/'master.json.gz')
   self.assertEqual(len(catalog(root,root/'cache.json')['models']),2)
 def test_index_only_does_not_decode_unopened_nbt_or_master_payloads(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t).resolve();m=self.fixture(root/'nbt_models/room');folder=root/'nbt_models/master';folder.mkdir();save_master(folder/'master.json.gz',m,set())
   with patch('nbt_detail_control.read_master',side_effect=AssertionError('must not decode NBT')),patch('nbt_detail_control.gzip.open',side_effect=AssertionError('must not decode master')):
    entries=catalog(root,root/'index.json',include_bugged=True,index_only=True)['models']
   self.assertEqual(len(entries),2);self.assertTrue(all(m['unverified'] for m in entries))
 def fixture(self,folder):
  folder.mkdir(parents=True);m=Model((12,12,12));m.box((0,0,0),(11,11,11),'stone_bricks');m.box((2,2,2),(9,9,9),'air');m.check_sealed([(5,5,5)]);m.save(folder/'room.nbt');return m
 def test_nbt_discovered_and_opened_from_cache_or_assets_folder(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t).resolve();m=self.fixture(root/'nbt_models/room')
   bad=root/'nbt_models/bad';bad.mkdir();(bad/'corrupt.nbt').write_bytes(b'invalid')
   for selected in [root,root/'nbt_models',root/'nbt_models/_workspaces',root/'nbt_models/room']:
    report=catalog(selected,root/'cache.json');self.assertEqual(len(report['models']),1);self.assertEqual(report['workspace'],str(root));self.assertEqual(report['models'][0]['size'],[12,12,12]);self.assertGreaterEqual(report['skipped'],1)
   info=inspect_source(root/'nbt_models/room/room.nbt');self.assertEqual(info['geometry_sha256'],m.fingerprint());self.assertEqual(info['wall_blocks'],0)
   view=source_snapshot(dict(source=str(root/'nbt_models/room/room.nbt'),context='',settings=default_settings()),root/'view');self.assertTrue(view['read_only_view']);snapshot=json.loads(Path(view['snapshot']).read_text());self.assertEqual(snapshot['verification']['routes'],'not_checked')
 def test_master_preferred_and_sparse_delivery_not_listed(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t).resolve();room=root/'nbt_models/room';m=self.fixture(room);save_master(room/'master.json.gz',m,set())
   (room/'delivery').mkdir();shutil.copyfile(room/'room.nbt',room/'delivery/copy.nbt')
   report=catalog(root,root/'cache.json');self.assertEqual(len(report['models']),1);self.assertTrue(report['models'][0]['source'].endswith('.json.gz'))
 def test_descriptor_with_relative_master_keeps_priority(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t).resolve();room=root/'nbt_models/room';m=self.fixture(room);save_master(room/'master.json.gz',m,set())
   (room/'room_description.json').write_text(json.dumps(dict(master='master.json.gz',name_zh='测试厅',audit={'compliant':True})),encoding='utf8')
   report=catalog(root,root/'cache.json');self.assertEqual(len(report['models']),1);self.assertTrue(report['models'][0]['source'].endswith('master.json.gz'))
 def test_project_shape_and_bugged_are_browseable_without_entering_default_catalog(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t).resolve();self.fixture(root/'nbt_models/项目甲/long/长廊/v1');self.fixture(root/'nbt_models/bugged/坏模型');(root/'nbt_models/bugged/坏模型/corrupt.nbt').write_bytes(b'broken')
   (root/'nbt_models/bugged/坏模型/room_description.json').write_text(json.dumps(dict(name_zh='待修复模型',master=str(root/'nbt_models/项目甲/long/长廊/v1/room.nbt'),audit={'compliant':False})),encoding='utf8')
   (root/'nbt_models/bugged/坏模型/refinement.json').write_text(json.dumps(dict(state='failed')),encoding='utf8')
   normal=catalog(root,root/'cache.json');self.assertEqual(len(normal['models']),1);self.assertEqual(normal['models'][0]['project_name'],'项目甲');self.assertEqual(normal['models'][0]['shape_group'],'long')
   all_models=catalog(root,root/'cache.json',include_bugged=True)['models'];self.assertEqual(len(all_models),3)
   broken=[m for m in all_models if m['bugged']];self.assertEqual(len(broken),2);self.assertTrue(all(m['shape_group']=='bugged' for m in broken));self.assertEqual(sum(m['unreadable'] for m in broken),1)
   self.assertTrue(next(m for m in broken if m['unreadable'])['error'])
 def test_delivery_and_authoring_versions_share_identity_without_losing_equal_geometry_versions(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t).resolve()
   for relative in ['single/测试厅/v1','single/测试厅/v2','_deliveries/batch/r001']:
    folder=root/'nbt_models'/relative;self.fixture(folder)
    (folder/'room_description.json').write_text(json.dumps(dict(name_zh='测试厅',shape='single',master='room.nbt',audit={'compliant':True})),encoding='utf8')
   entries=catalog(root,root/'cache.json')['models'];self.assertEqual(len(entries),3);self.assertEqual(len({m['object_key'] for m in entries}),1);self.assertEqual(sum(m['is_delivery'] for m in entries),1)
if __name__=='__main__':unittest.main(verbosity=2)
