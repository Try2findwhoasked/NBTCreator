import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.agents/skills/minecraft-nbt-modeler/scripts'))
import nbt_components as components
from nbt_assembly import Volume
from nbt_refine import save_master
from nbt_tools import modelling_plan
from nbt_task import write_snapshot


class Components(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.workspace=Path(self.temp.name).resolve()
  self.model=Volume((24,16,24));self.model.box((0,0,0),(23,0,23),'stone_bricks');self.model.box((3,1,3),(3,4,3),'oak_log[axis=y]')
  self.walls={(3,1,3)};self.source=self.workspace/'source.master.json.gz';save_master(self.source,self.model,self.walls);self.original=self.source.read_bytes()
 def captured(self):return components.capture(self.workspace,self.source,'柱子',[3,1,3],[3,4,3],tags=['木构','支承'])
 def test_capture_preserves_source_layers_and_uses_bottom_center_anchor(self):
  item=self.captured();data=components.load(self.workspace,item['id']);self.assertEqual(data['size'],[1,4,1]);self.assertEqual(data['anchor'],[0,0,0]);self.assertEqual(len(data['blocks']),4);self.assertEqual(sum(b[4] for b in data['blocks']),1)
  self.assertTrue(Path(item['thumbnail']).is_file());self.assertEqual(self.source.read_bytes(),self.original)
  plan=components.placement(data,[10,1,10],list(self.model.size));self.assertEqual({op['classification'] for op in plan['operations']},{'body','wall'})
  total=[]
  for operation in plan['operations']:total+=modelling_plan(self.model,operation)[0]
  self.assertEqual({p for p,_ in total},{(10,y,10) for y in range(1,5)})
 def test_collision_protection_bounds_and_write_budget_remain_enforced(self):
  data=components.load(self.workspace,self.captured()['id']);plan=components.placement(data,[10,1,10],list(self.model.size));op=plan['operations'][0]
  self.model.put((10,2,10),'stone')
  with self.assertRaisesRegex(ValueError,'冲突'):modelling_plan(self.model,op)
  op['overwrite']=True
  with self.assertRaisesRegex(ValueError,'保护'):modelling_plan(self.model,op,{(10,2,10)})
  op['max_writes']=0
  with self.assertRaises(ValueError):modelling_plan(self.model,op)
  with self.assertRaisesRegex(ValueError,'边界'):components.placement(data,[23,15,23],list(self.model.size))
 def test_portable_index_is_reused_and_refreshes_after_rename_archive(self):
  item=self.captured();components.listing(self.workspace)
  with patch('nbt_components.load',side_effect=AssertionError('warm list must not parse voxels')):
   self.assertEqual(len(components.listing(self.workspace)['items']),1)
  components.update(self.workspace,item['id'],name='木柱',tags=['可复用'],archived=True)
  row=components.listing(self.workspace)['items'][0];self.assertEqual(row['name'],'木柱');self.assertTrue(row['archived'])
  with self.assertRaisesRegex(ValueError,'回收站'):components.placement(components.load(self.workspace,item['id']),[10,1,10],list(self.model.size))
  components.update(self.workspace,item['id'],archived=False)
  moved=self.workspace/'moved';shutil.copytree(self.workspace/'.nbtcreator',moved/'.nbtcreator')
  self.assertTrue(Path(components.listing(moved)['items'][0]['file']).is_relative_to(moved))
  self.assertNotIn(str(self.workspace), (moved/'.nbtcreator/components/index/catalog.json').read_text(encoding='utf8'))
 def test_snapshot_capture_requires_unchanged_source_and_snapshot(self):
  snapshot=self.workspace/'snapshot.json';write_snapshot(self.source,snapshot);digest=hashlib.sha256(snapshot.read_bytes()).hexdigest()
  components.capture(self.workspace,self.source,'快照',[3,1,3],[3,4,3],snapshot=snapshot,snapshot_sha256=digest)
  snapshot.write_text('{}')
  with self.assertRaises(ValueError):components.capture(self.workspace,self.source,'错位',[3,1,3],[3,4,3],snapshot=snapshot,snapshot_sha256=digest)
 def test_import_and_operation_reject_forged_hash_duplicates_and_invalid_states(self):
  data=components.load(self.workspace,self.captured()['id']);data['blocks'][0][0]=999
  with self.assertRaises(ValueError):components.store(self.workspace,data)
  data=components.load(self.workspace,self.captured()['id']);data['content_sha256']='0'*64
  with self.assertRaisesRegex(ValueError,'哈希'):components.store(self.workspace,data)
  data=components.load(self.workspace,self.captured()['id']);data['palette'][0]='minecraft:not_a_block'
  with self.assertRaises(ValueError):components.store(self.workspace,data)
  with self.assertRaises(ValueError):components.load(self.workspace,'../source')
  op=dict(kind='paste_component',lo=[1,1,1],hi=[2,2,2],palette=['stone'],voxels=[[0,0,0,0],[0,0,0,0]])
  with self.assertRaisesRegex(ValueError,'重复'):modelling_plan(self.model,op)
 def test_rotation_and_mirror_transform_positions_and_known_state_orientation(self):
  item=self.captured();data=components.load(self.workspace,item['id']);data['palette']=['minecraft:oak_log[axis=x]'];data.pop('content_sha256')
  plan=components.placement(data,[10,1,10],list(self.model.size),quarter_turns=1,mirror='x')
  self.assertIn('axis=z',plan['operations'][0]['palette'][0])
  self.assertEqual(self.source.read_bytes(),self.original)


if __name__=='__main__':unittest.main(verbosity=2)
