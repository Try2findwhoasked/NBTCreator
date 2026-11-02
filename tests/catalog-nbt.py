"""Standalone full NBT discovery and workspace normalization, synthetic only."""
import sys,tempfile,unittest,shutil,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_detail_control import catalog,inspect_source,source_snapshot,default_settings
from nbt_model import Model
from nbt_refine import save_master

class CatalogNbt(unittest.TestCase):
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
if __name__=='__main__':unittest.main(verbosity=2)
