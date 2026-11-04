from pathlib import Path
import json
import hashlib
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_assembly import Volume
from nbt_refine import save_master,read_master
from nbt_selection_edit import dispatch
from nbt_detail_control import simulate_plan

class SelectionEdit(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.folder=Path(self.temp.name);self.model=Volume((16,10,16));self.model.box((0,0,0),(15,0,15),'stone_bricks');self.model.box((4,1,4),(6,2,4),'oak_planks');self.walls={(4,1,4)};self.source=self.folder/'source.master.json.gz';save_master(self.source,self.model,self.walls);self.original=self.source.read_bytes();self.request=dict(source=str(self.source),source_sha256=hashlib.sha256(self.original).hexdigest(),lo=[4,1,4],hi=[7,4,7],geometry_sha256=self.model.fingerprint());self.config=dict(protected_boxes=[],protected_paths=[],max_changed_blocks=64)
 def compiled(self,operations,**kwargs):return dispatch('compile',dict(self.request,operations=operations,**kwargs))['operations']
 def test_exact_palette_runs_include_local_coordinates_and_wall_membership(self):
  data=dispatch('context',self.request);self.assertEqual(data['size'],[4,4,4]);self.assertEqual(data['solid_blocks'],6);self.assertTrue(data['air_omitted']);points={(x+i,y,z):[data['palette'][id],wall] for x,y,z,n,id,wall in data['runs'] for i in range(n)};self.assertEqual(len(points),6);self.assertEqual(points[(0,0,0)][1],1);self.assertNotIn((0,3,0),points);self.assertEqual(self.source.read_bytes(),self.original)
 def test_translation_changes_points_once_and_keeps_offsets_radii_and_vectors(self):
  op=dict(kind='geometry',label='球体',lo=[0,0,0],hi=[3,3,3],geometry=dict(shape='sphere',centre=[1.5,1.5,1.5],radius=1),state='stone',mode='add');compiled=self.compiled([op])[0];self.assertEqual(compiled['geometry']['centre'],[5.5,2.5,5.5]);self.assertEqual(compiled['geometry']['radius'],1);self.assertEqual(compiled['write_bounds']['lo'],[4,1,4]);self.assertEqual(compiled['lo'],[4,1,4])
 def test_copy_destination_outside_selection_is_rejected_on_actual_write(self):
  op=dict(kind='copy_region',label='复制木构',lo=[0,0,0],hi=[0,1,0],offset=[4,0,0],include_air=False,classification='inherit');operations=self.compiled([op])
  with self.assertRaisesRegex(ValueError,'实际写入超出限定选区'):simulate_plan(self.model,self.walls,dict(operations=operations),self.config)
  self.assertEqual(self.source.read_bytes(),self.original)
 def test_replace_scope_and_wall_mask_are_preserved_outside_region(self):
  ops=self.compiled([dict(kind='replace',label='木材换石材',lo=[0,0,0],hi=[3,3,3],from_states=['oak_planks'],state='andesite',classification='inherit')]);model,walls,diff=simulate_plan(self.model,self.walls,dict(operations=ops),self.config);self.assertEqual(diff['changed_blocks'],6);self.assertEqual(walls,self.walls);self.assertEqual(model.get((0,0,0)),self.model.get((0,0,0)));self.assertEqual(model.get((4,1,4)),'minecraft:andesite')
 def test_strict_pattern_tool_does_not_receive_scope_metadata(self):
  op=dict(kind='pattern',label='局部混搭',classification='inherit',lo=[0,0,0],hi=[3,3,3],action='replace',from_states=['oak_planks'],palette=[dict(state='stone_bricks',weight=1)],fraction=1,seed=1,mode='independent',scope='volume',shape_policy='preserve',preserve_properties=True,scale=2);model,walls,diff=simulate_plan(self.model,self.walls,dict(operations=self.compiled([op])),self.config);self.assertEqual(diff['changed_blocks'],6)
 def test_overwrite_off_protection_and_total_budget_still_reject_changes(self):
  op=dict(kind='replace',label='替换',lo=[0,0,0],hi=[3,3,3],from_states=['oak_planks'],state='stone',classification='inherit')
  with self.assertRaisesRegex(ValueError,'已有方块'):simulate_plan(self.model,self.walls,dict(operations=self.compiled([op],allow_overwrite=False)),self.config)
  with self.assertRaisesRegex(ValueError,'保护|protected'):simulate_plan(self.model,self.walls,dict(operations=self.compiled([op])),dict(self.config,protected_boxes=[dict(lo=[4,1,4],hi=[4,1,4])]))
  with self.assertRaisesRegex(ValueError,'上限'):simulate_plan(self.model,self.walls,dict(operations=self.compiled([op])),dict(self.config,max_changed_blocks=1))
 def test_snapshot_context_uses_candidate_and_refuses_tampering(self):
  from nbt_registry import effective,normalize
  self.model.put((5,3,5),'gold_block');snapshot=self.folder/'after.json';blocks=[[list(p),normalize(dict(Name=effective(value)[0],Properties=effective(value)[1]))] for p,value in sorted(self.model.blocks.items())];data=dict(source=str(self.source),source_sha256=self.request['source_sha256'],geometry_sha256=self.model.fingerprint(),preview_only=True,size=list(self.model.size),blocks=blocks,master_blocks=[[list(p),value] for p,value in sorted(self.model.blocks.items())],wall_positions=list(self.walls));snapshot.write_text(json.dumps(data));request=dict(self.request,geometry_sha256=self.model.fingerprint());result=dispatch('context',request,snapshot);self.assertEqual(result['solid_blocks'],7);data['master_blocks']=[];snapshot.write_text(json.dumps(data))
  with self.assertRaises(ValueError):dispatch('context',request,snapshot)
 def test_scope_and_executable_or_permission_fields_are_rejected(self):
  with self.assertRaisesRegex(ValueError,'已变化'):dispatch('context',dict(self.request,source_sha256='0'*64))
  with self.assertRaisesRegex(ValueError,'不能改变'):self.compiled([dict(kind='box',lo=[0,0,0],hi=[0,0,0],state='stone',overwrite=True)])
  with self.assertRaisesRegex(ValueError,'不能改变'):self.compiled([dict(kind='box',lo=[0,0,0],hi=[0,0,0],state='stone',script='exec')])
  with self.assertRaisesRegex(ValueError,'读取/编辑区域'):self.compiled([dict(kind='copy_region',lo=[-1,0,0],hi=[-1,0,0],offset=[1,0,0])])
if __name__=='__main__':unittest.main(verbosity=2)
