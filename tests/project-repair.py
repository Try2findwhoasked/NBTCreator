from pathlib import Path
import gzip,json,sys,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_assembly import Volume
from nbt_refine import save_master,read_master
from nbt_project_repair import repair

class Recovery(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.folder=self.root/'nbt_models/bugged/single/room';self.folder.mkdir(parents=True);self.source=self.folder/'source.master.json.gz';self.model=Volume((8,8,8));self.model.box([0,0,0],[7,0,7],'stone');self.walls={(0,0,0)};save_master(self.source,self.model,self.walls)
 def corrupt(self,change):
  data=json.loads(gzip.decompress(self.source.read_bytes()));change(data);self.source.write_bytes(gzip.compress(json.dumps(data).encode()))
 def test_stale_hash_and_identical_duplicate_recover_without_geometry_or_layer_loss(self):
  self.corrupt(lambda d:(d.update(geometry_sha256='0'*64),d['blocks'].append(d['blocks'][0])))
  original=self.source.read_bytes();r=repair(self.root,self.source);self.assertEqual(r['status'],'recovered_candidate',r);self.assertEqual(r['category'],'single');self.assertEqual(len(r['changes']),2);m,w=read_master(self.root/r['candidate']);self.assertEqual(m.blocks,self.model.blocks);self.assertEqual(w,self.walls);self.assertEqual(self.source.read_bytes(),original);self.assertFalse(r['nbt_exported']);self.assertNotIn('bugged',Path(r['candidate']).parts)
 def test_conflicting_duplicates_invalid_states_and_bad_wall_masks_remain_quarantined(self):
  mutations=[lambda d:d['blocks'].append([d['blocks'][0][0],'gold_block']),lambda d:d['blocks'].append([[1,1,1],'not_a_real_block']),lambda d:d.update(wall_positions=[[1,1,1]]),lambda d:d['blocks'].append([[999,0,0],'stone'])]
  for change in mutations:
   save_master(self.source,self.model,self.walls);self.corrupt(change);original=self.source.read_bytes();r=repair(self.root,self.source,'square');self.assertEqual(r['status'],'failed',r);self.assertNotIn('candidate',r);self.assertTrue((self.root/r['report']).is_file());self.assertEqual(self.source.read_bytes(),original)
 def test_invalid_gzip_records_failure_and_explicit_category_is_preserved(self):
  self.source.write_bytes(b'invalid');r=repair(self.root,self.source);self.assertEqual(r['status'],'failed');self.assertTrue(r['source_unchanged'])
  save_master(self.source,self.model,self.walls);r=repair(self.root,self.source,'irregular');self.assertEqual(r['category'],'irregular');self.assertTrue((self.root/r['candidate']).exists())
 def test_readable_nbt_is_copied_to_master_and_entities_are_not_silently_dropped(self):
  from nbt_model import Model
  m=Model((8,8,8));m.box([0,0,0],[7,7,7],'stone');m.box([2,2,2],[5,5,5],'air');m.check_sealed([[3,3,3]])
  source=self.folder/'room.nbt';m.save(source);original=source.read_bytes();r=repair(self.root,source,'standalone');self.assertEqual(r['status'],'recovered_candidate',r);self.assertEqual(read_master(self.root/r['candidate'])[0].blocks,m.blocks);self.assertEqual(source.read_bytes(),original)
  payload=gzip.decompress(original);old=b'\x09\x00\x08entities\x0a\x00\x00\x00\x00';self.assertIn(old,payload);source.write_bytes(gzip.compress(payload.replace(old,b'\x09\x00\x08entities\x0a\x00\x00\x00\x01\x00')));r=repair(self.root,source);self.assertEqual(r['status'],'failed');self.assertIn('实体',r['error'])
 def test_changed_hash_and_external_paths_rejected(self):
  with self.assertRaisesRegex(ValueError,'已变化'):repair(self.root,self.source,source_sha256='0'*64)
  with self.assertRaises(ValueError):repair(self.root,Path(self.temp.name).parent/'external.nbt')
  with self.assertRaises(ValueError):repair(self.root,self.source,'../escape')

if __name__=='__main__':unittest.main(verbosity=2)
