import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
SCRIPTS=ROOT/'.agents/skills/minecraft-nbt-modeler/scripts'
sys.path.insert(0,str(SCRIPTS))
import nbt_recipes as recipes
import nbt_components as components
from nbt_assembly import Volume
from nbt_tools import modelling_plan
from nbt_refine import operation_candidates
from nbt_change_policy import enforce_overwrite,enforce_changes


def recipe():
 return dict(schema_version=1,asset_type='recipe',name='可调石柱',tags=['支承'],parameters=dict(height=dict(type='integer',label='柱高',default=4,min=1,max=20),material=dict(type='block',default='stone_bricks')),operations=[dict(kind='box',label='柱身',classification='body',lo=[0,0,0],hi=[0,{'param':'height','add':-1},0],state={'param':'material'})])


def theme(mapping=None,preserve=True):return dict(schema_version=1,asset_type='theme',name='深色石构',mapping=mapping or {'stone_bricks':'deepslate_bricks'},preserve_shape=preserve)


class Reusable(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.workspace=Path(self.temp.name)
 def test_compile_rejects_changed_recipe_or_theme_and_reports_bound_revisions(self):
  saved=recipes.store(self.workspace,recipe());t=recipes.store(self.workspace,theme());request=dict(id=saved['id'],revision_sha256=saved['revision_sha256'],theme=t['id'],theme_revision_sha256=t['revision_sha256'],values={},position=[4,2,4],size=[24,16,24]);result=recipes.dispatch(self.workspace,'compile',request);self.assertEqual(result['recipe_revision_sha256'],saved['revision_sha256']);self.assertEqual(result['theme_revision_sha256'],t['revision_sha256'])
  changed=recipe();changed['operations'][0]['state']='gold_block';updated=recipes.store(self.workspace,changed,saved['id']);self.assertNotEqual(updated['revision_sha256'],saved['revision_sha256'])
  with self.assertRaisesRegex(ValueError,'配方已被'):recipes.dispatch(self.workspace,'compile',request)
  request['revision_sha256']=updated['revision_sha256'];recipes.store(self.workspace,theme({'stone_bricks':'andesite'}),t['id'])
  with self.assertRaisesRegex(ValueError,'材质主题已被'):recipes.dispatch(self.workspace,'compile',request)
  self.assertEqual(recipes.load(self.workspace,saved['id'])['revision_sha256'],updated['revision_sha256'])
  cli=subprocess.run([sys.executable,str(SCRIPTS/'nbt_recipes.py'),'--workspace',str(self.workspace),'compile','--id',saved['id'],'--position','4,2,4','--size','24,16,24','--revision-sha256',saved['revision_sha256']],capture_output=True,text=True,encoding='utf8');self.assertNotEqual(cli.returncode,0);self.assertIn('配方已被',cli.stdout)
 def test_parameters_expand_at_position_and_shared_engine_keeps_collision_protection_budget(self):
  data=recipe();before=copy.deepcopy(data);patch=recipes.instantiate(data,{'height':6,'material':'gold_block'},[4,2,4],[24,16,24]);self.assertEqual(patch['hi'],[4,7,4]);self.assertEqual(data,before)
  model=Volume((24,16,24));op=patch['operations'][0];edits=operation_candidates(model,op,set());self.assertEqual(len(edits),6);owners={};enforce_overwrite(model,set(),op,edits,owners)
  model.put((4,3,4),'stone')
  with self.assertRaisesRegex(ValueError,'已有方块'):enforce_overwrite(model,set(),op,edits,{})
  op['overwrite']=True
  with self.assertRaisesRegex(ValueError,'保护'):enforce_changes(model.blocks,dict(edits),set(),set(),protected={(4,3,4)})
  with self.assertRaisesRegex(ValueError,'超过上限'):enforce_changes({},dict(edits),set(),set(),maximum=2)
 def test_capture_rebases_geometry_without_changing_radius_or_delta_and_parameterizes_local_value(self):
  ops=[dict(kind='geometry',label='圆柱',lo=[8,3,8],hi=[14,9,14],geometry=dict(shape='cylinder',centre=[11,6,11],radius=2,height=5,axis='y'),state='stone'),dict(kind='copy_region',label='复制',lo=[8,3,8],hi=[14,9,14],offset=[8,0,0],overwrite=False)]
  result=recipes.capture(ops,'双柱',bindings=[dict(path=[0,'geometry','radius'],name='radius',label='半径')]);data=result['asset'];self.assertEqual(result['origin'],[8,3,8]);self.assertEqual(data['parameters']['radius']['default'],2)
  expanded=recipes.instantiate(data,{'radius':1},[2,2,2],[40,16,40]);self.assertEqual(expanded['operations'][0]['geometry']['centre'],[5,5,5]);self.assertEqual(expanded['operations'][1]['offset'],[8,0,0]);self.assertEqual(expanded['hi'],[16,8,8]);self.assertEqual(ops[0]['geometry']['centre'],[11,6,11])
  extrusion=dict(kind='geometry',lo=[8,3,8],hi=[14,9,14],geometry=dict(shape='extrude',vertices=[[8,8],[10,8],[10,10]],bottom=3,top=8));shifted=recipes.translate_operation(extrusion,[-8,-3,-8]);self.assertEqual(shifted['geometry']['vertices'],[[0,0],[2,0],[2,2]]);self.assertEqual(shifted['geometry']['top'],5)
 def test_invalid_values_unknown_operations_untrusted_permissions_and_path_traversal_are_rejected(self):
  for values in ({'height':True},{'height':0},{'material':'not_a_block'},{'unknown':1}):
   with self.assertRaises(ValueError):recipes.instantiate(recipe(),values,[1,1,1],[24,16,24])
  for change in ({'kind':'eval','code':'print(1)'},{'write_group':'12345678-1234-1234-1234-123456789abc'},{'shell':'powershell'}):
   value=recipe();value['operations'][0].update(change)
   with self.assertRaises(ValueError):recipes.validate(value)
  value=recipe();value['operations'][0]['state']={'param':'missing'}
  with self.assertRaises(ValueError):recipes.validate(value)
  with self.assertRaises(ValueError):recipes.load(self.workspace,'../outside')
  with self.assertRaises(ValueError):recipes.instantiate(recipe(),{},[23,14,23],[24,16,24])
 def test_material_theme_preserves_state_properties_shape_and_single_pass_mapping(self):
  t=recipes.validate(theme({'oak_log':'spruce_log','spruce_log':'birch_log'}));self.assertEqual(recipes.remap_state('oak_log[axis=x]',t),'minecraft:spruce_log[axis=x]')
  steps=[dict(kind='box',state='stone_bricks'),dict(kind='paste_component',palette=['stone_bricks','air'])];changed=recipes.remap_operations(steps,theme());self.assertEqual(changed[0]['state'],'minecraft:deepslate_bricks');self.assertEqual(changed[1]['palette'],['minecraft:deepslate_bricks','minecraft:air']);self.assertEqual(steps[0]['state'],'stone_bricks')
  with self.assertRaisesRegex(ValueError,'碰撞形状'):recipes.remap_state('stone_bricks',recipes.validate(theme({'stone_bricks':'stone_brick_slab'})))
  self.assertEqual(recipes.remap_state('stone_bricks',recipes.validate(theme({'stone_bricks':'stone_brick_slab'},False))).split('[')[0],'minecraft:stone_brick_slab')
 def component(self):return dict(schema_version=1,name='双层柱',size=[1,2,1],anchor=[0,0,0],palette=['oak_log[axis=x]'],blocks=[[0,0,0,0,True],[0,1,0,0,False]])
 def test_batch_grid_uses_each_anchor_preserves_walls_rotation_theme_and_source_data(self):
  component=self.component();before=copy.deepcopy(component);patch=components.batch_placement(component,[3,2,3],[24,16,24],[2,1,3],[4,0,5],1,'x',False,theme({'oak_log':'spruce_log'}));self.assertEqual(patch['copies'],6);self.assertEqual(len(patch['operations']),12);self.assertEqual(patch['hi'],[7,3,13]);self.assertEqual({op['classification'] for op in patch['operations']},{'body','wall'});self.assertEqual(patch['operations'][0]['palette'],['minecraft:spruce_log[axis=z]']);self.assertEqual(component,before)
  self.assertEqual(len({tuple(op['lo']) for op in patch['operations']}),6)
 def test_batch_limits_overlap_and_world_bounds_are_explicit(self):
  for counts,spacing,pos in [([65,1,1],[1,0,0],[1,1,1]),([2,1,1],[0,0,0],[1,1,1]),([2,1,1],[30,0,0],[1,1,1])]:
   with self.assertRaises(ValueError):components.batch_placement(self.component(),pos,[24,16,24],counts,spacing)
  with self.assertRaisesRegex(ValueError,'重叠'):components.batch_placement(self.component(),[3,2,3],[24,16,24],[1,2,1],[0,1,0])
  patch=components.batch_placement(self.component(),[10,2,10],[24,16,24],[2,1,1],[-3,0,0]);self.assertEqual(patch['lo'],[7,2,10])
 def test_portable_library_archive_import_and_cli_read_same_data_after_move(self):
  saved=recipes.store(self.workspace,recipe());theme_saved=recipes.store(self.workspace,theme());self.assertEqual(len(recipes.listing(self.workspace)['items']),2)
  archived=recipes.dispatch(self.workspace,'archive',dict(id=saved['id'],archived=True));self.assertTrue(archived['archived'])
  with self.assertRaises(ValueError):recipes.instantiate(recipes.load(self.workspace,saved['id']),{},[0,0,0],[24,16,24])
  recipes.dispatch(self.workspace,'archive',dict(id=saved['id'],archived=False));moved=self.workspace/'moved';shutil.copytree(self.workspace/'.nbtcreator',moved/'.nbtcreator');self.assertEqual(recipes.load(moved,saved['id'])['revision_sha256'],saved['revision_sha256'])
  run=subprocess.run([sys.executable,str(SCRIPTS/'nbt_recipes.py'),'compile','--id',saved['id'],'--position','5,2,5','--size','24,16,24','--theme',theme_saved['id']],cwd=moved,capture_output=True,text=True,encoding='utf8');self.assertEqual(run.returncode,0,run.stdout+run.stderr);result=json.loads(run.stdout)['result'];self.assertEqual(result['operations'][0]['state'],'minecraft:deepslate_bricks');self.assertEqual(result['lo'],[5,2,5])
  source=components.store(moved,self.component());run=subprocess.run([sys.executable,str(SCRIPTS/'nbt_components.py'),'batch','--id',source['id'],'--position','5,2,5','--size','24,16,24','--counts','2,1,1','--spacing','4,0,0'],cwd=moved,capture_output=True,text=True,encoding='utf8');self.assertEqual(run.returncode,0,run.stdout+run.stderr);self.assertEqual(json.loads(run.stdout)['result']['copies'],2)
 def test_warm_listing_reads_index_instead_of_operation_voxels_and_refreshes_changes(self):
  saved=recipes.store(self.workspace,recipe());recipes.listing(self.workspace)
  with patch('nbt_recipes.load',side_effect=AssertionError('warm list must use metadata cache')):self.assertEqual(recipes.listing(self.workspace)['items'][0]['id'],saved['id'])
  value=recipes.load(self.workspace,saved['id']);value['name']='更新名称';recipes.store(self.workspace,value,saved['id']);self.assertEqual(recipes.listing(self.workspace)['items'][0]['name'],'更新名称')
  text=(self.workspace/'.nbtcreator/reusable/index/catalog.json').read_text(encoding='utf8');self.assertNotIn(str(self.workspace),text);self.assertNotIn('operations',json.loads(text)[saved['id']]['summary'])
 def test_parameter_bounds_include_repeat_and_rotated_target_not_only_source_box(self):
  op=dict(kind='repeat_region',label='阵列',lo=[0,0,0],hi=[1,1,1],offset=[3,0,0],count=4)
  data=dict(schema_version=1,asset_type='recipe',name='阵列',operations=[op]);self.assertEqual(recipes.instantiate(data,{},[2,2,2],[24,16,24])['hi'],[15,3,3])
  with self.assertRaisesRegex(ValueError,'边界'):recipes.instantiate(data,{},[16,2,2],[24,16,24])
  op=dict(kind='transform_region',label='旋转',lo=[0,0,0],hi=[2,1,0],destination=[5,0,0],quarter_turns=1);data['operations']=[op];self.assertEqual(recipes.instantiate(data,{},[2,2,2],[24,16,24])['hi'],[7,3,4])


if __name__=='__main__':unittest.main(verbosity=2)
