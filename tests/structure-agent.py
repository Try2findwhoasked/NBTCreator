import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SCRIPTS=ROOT/'.agents/skills/minecraft-nbt-modeler/scripts'
sys.path.insert(0,str(SCRIPTS))
from nbt_structure_agent import dispatch,build,definitions
from nbt_components import load,placement


class StructureAgent(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
  self.spec=dict(name='独立石柱',size=[5,8,5],tags=['支承'],operations=[dict(kind='box',label='主体',classification='body',lo=[1,0,1],hi=[3,6,3],state='stone_bricks'),dict(kind='box',label='墙饰',classification='wall',lo=[2,1,1],hi=[2,4,1],state='chiseled_stone_bricks')],camera=dict(azimuth=90,elevation=25))
 def test_data_only_preview_write_read_view_and_parameterized_placement(self):
  result=dispatch(self.root,'structure_preview',{'spec':self.spec})
  self.assertEqual(dispatch(self.root,'structure_list',{})['items'],[])
  self.assertTrue(Path(result['snapshot']).is_file());self.assertTrue(Path(result['thumbnail']).is_file());self.assertEqual(len(result['cameras']),1)
  self.assertEqual(result['verification']['design'],'pending_visual_review')
  stored=dispatch(self.root,'structure_write',{k:result[k] for k in ['preview_id','preview_sha256']});data=dispatch(self.root,'structure_read',{'id':stored['id']})
  self.assertEqual(Path(stored['thumbnail']).read_bytes(),Path(result['thumbnail']).read_bytes())
  self.assertEqual(sum(b[4] for b in data['blocks']),4);self.assertEqual(data['size'],[5,8,5])
  viewed=dispatch(self.root,'structure_view',{'id':stored['id']});self.assertEqual(viewed['content_sha256'],data['content_sha256'])
  args=dict(id=stored['id'],content_sha256=data['content_sha256'],position=[20,2,20],size=[48,24,48],quarter_turns=1,mirror='x')
  plan=dispatch(self.root,'structure_place',args);expected=placement(data,args['position'],args['size'],1,'x')
  self.assertEqual(plan['operations'],expected['operations']);self.assertFalse(plan['model_modified']);self.assertEqual({op['classification'] for op in plan['operations']},{'body','wall'})
 def test_preview_binding_and_asset_content_hashes_refuse_stale_data(self):
  result=dispatch(self.root,'structure_preview',{'spec':self.spec});draft=Path(result['source']).parent/'draft.json';draft.write_text('{}')
  with self.assertRaisesRegex(ValueError,'预览已改变'):dispatch(self.root,'structure_write',{k:result[k] for k in ['preview_id','preview_sha256']})
  self.assertEqual(dispatch(self.root,'structure_list',{})['items'],[])
  result=dispatch(self.root,'structure_preview',{'spec':self.spec});item=dispatch(self.root,'structure_write',{k:result[k] for k in ['preview_id','preview_sha256']})
  with self.assertRaisesRegex(ValueError,'变化'):dispatch(self.root,'structure_place',dict(id=item['id'],content_sha256='0'*64,position=[10,0,10],size=[48,24,48]))
 def test_same_engine_bounds_budget_states_and_no_execution_fields(self):
  for patch in [{'source':'private'},{'operations':[dict(self.spec['operations'][0],script='exec')]},{'operations':[dict(self.spec['operations'][0],write_group='foreign')]},{'operations':[dict(self.spec['operations'][0],state='not_a_block')]},{'operations':[dict(self.spec['operations'][0],hi=[5,6,3])]},{'max_changed_blocks':2},{'camera':{'azimuth':float('nan')}}]:
   with self.subTest(patch=patch),self.assertRaises((ValueError,AssertionError)):dispatch(self.root,'structure_preview',{'spec':dict(self.spec,**patch)})
  for tool,args in [('shell',{}),('structure_write',{'preview_id':'../bad','preview_sha256':'0'*64}),('structure_list',{'path':'elsewhere'})]:
   with self.assertRaises(ValueError):dispatch(self.root,tool,args)
 def test_all_preview_artifacts_are_bound_and_pattern_keeps_its_shared_strict_schema(self):
  for name in ('draft.master.json.gz','snapshot.json','thumbnail.jpg','cameras.json'):
   result=dispatch(self.root,'structure_preview',{'spec':self.spec});file=Path(result['source']).parent/name;file.write_bytes(file.read_bytes()+b'changed')
   with self.assertRaisesRegex(ValueError,'预览已改变'):dispatch(self.root,'structure_write',{k:result[k] for k in ['preview_id','preview_sha256']})
  spec=dict(self.spec,operations=[self.spec['operations'][0],dict(kind='pattern',label='连片换材',classification='inherit',lo=[0,0,0],hi=[4,7,4],action='replace',scope='surface',mode='independent',fraction=1,from_states=['stone_bricks'],palette=[dict(state='andesite',weight=1)],seed=2718)])
  data=build(self.root,spec);self.assertIn('minecraft:andesite',data['palette'])
 def test_existing_assets_are_composed_by_parameters_without_reemitting_voxels(self):
  result=dispatch(self.root,'structure_preview',{'spec':self.spec});item=dispatch(self.root,'structure_write',{k:result[k] for k in ['preview_id','preview_sha256']})
  spec=dict(name='组合双柱',size=[16,10,8],placements=[dict(id=item['id'],content_sha256=item['content_sha256'],position=[3,0,3]),dict(id=item['id'],content_sha256=item['content_sha256'],position=[11,0,3],quarter_turns=1)])
  built=build(self.root,spec);self.assertEqual(len(built['blocks']),len(load(self.root,item['id'])['blocks'])*2)
 def test_pattern_library_compiles_each_surface_and_preserves_mount_faces(self):
  from nbt_collision import collision_cells
  patterns=dispatch(self.root,'pattern_list',{})['patterns']
  basic={'checkerboard','horizontal-stripes','vertical-stripes','running-bond',
         'basket-weave','herringbone','diamond-lattice','greek-key','zigzag-band',
         'cross-tile','stepped-diamond','four-petal'}
  self.assertTrue(basic <= patterns.keys())
  for tool in ('pattern_compile','pattern_preview'):
   allowed=definitions()[tool]['parameters']['properties']['preset']['enum']
   self.assertEqual(set(allowed),set(patterns))
  self.assertEqual(set(definitions()['pattern_mount']['parameters']['properties']['object']['properties']['preset']['enum']),set(patterns))
  for key,preset in patterns.items():
   for surface in preset['surfaces']:
    with self.subTest(key=key,surface=surface):
     args=dict(preset=key,surface=surface,size_uv=preset['size_uv'])
     if surface=='cylinder':args['size_uv']=[12,24]
     if surface!='floor':args['shapes']=dict(stairs='quartz_stairs')
     if surface in ('wall','column','cylinder'):args['shapes']['slab']='quartz_slab'
     result=dispatch(self.root,'pattern_compile',args);data=build(self.root,result['spec'])
     self.assertEqual(result['sample_sha256'],preset['sha256'])
     if surface=='floor':
      self.assertEqual(len(data['blocks']),data['size'][0]*data['size'][2])
      self.assertTrue(all(b[1]==0 and len(collision_cells(data['palette'][b[3]])[0])==8 for b in data['blocks']))
     if surface=='ceiling':
      self.assertEqual(data['anchor'][1],1)
      self.assertGreater(sum(result['shape_counts'].values()),0)
      for x,y,z,index,wall in data['blocks']:
       if y==0:self.assertTrue(any(p[1]==1 for p in collision_cells(data['palette'][index])[0]))
     if key in basic:
      self.assertEqual(result,dispatch(self.root,'pattern_compile',args))
      self.assertGreater(len(data['palette']),1)
  previewed=dispatch(self.root,'pattern_preview',dict(preset='acanthus-capital',surface='column',size_uv=[32,22]))
  self.assertTrue(Path(previewed['thumbnail']).is_file())
  previewed=dispatch(self.root,'pattern_preview',dict(preset='checkerboard',surface='floor',size_uv=[32,32],repeat=[2,2]))
  self.assertTrue(Path(previewed['thumbnail']).is_file())
  with self.assertRaises(ValueError):
   dispatch(self.root,'pattern_compile',dict(preset='cosmati-floor',surface='floor',size_uv=[16,16],shapes=dict(slab='quartz_slab')))

 def test_pattern_detail_controls_budgets_and_frozen_facade(self):
  args=dict(preset='acanthus-capital',surface='column',size_uv=[64,44],max_changed_blocks=8192,shapes=dict(slab='quartz_slab',stairs='quartz_stairs'))
  result=dispatch(self.root,'pattern_compile',args)
  fit=result['fitting']
  self.assertEqual(fit['requested'],fit['matched']+fit['missing'])
  self.assertEqual(fit['subcells_per_block'],4)
  changed=dispatch(self.root,'pattern_compile',dict(args,preset_options=dict(invert=True)))
  self.assertNotEqual(result['content_sha256'],changed['content_sha256'])
  with self.assertRaisesRegex(ValueError,'预算|上限'):
   dispatch(self.root,'pattern_compile',dict(args,max_changed_blocks=1))
  from nbt_exposure import apply
  apply(self.root)
  request=self.root/'pattern.json';request.write_text(json.dumps(args))
  run=subprocess.run([sys.executable,str(self.root/'.agents/skills/nbtcreator-workspace/nbt.py'),'components','agent','--tool','pattern_compile','--request',str(request)],cwd=self.root,capture_output=True,text=True,encoding='utf8')
  self.assertEqual(run.returncode,0,(run.stdout+run.stderr)[-2000:])
  frozen=json.loads(run.stdout)['result']
  self.assertEqual(frozen['content_sha256'],result['content_sha256'])
  self.assertEqual(frozen['fitting'],fit)
  viewed=dispatch(self.root,'pattern_preview',dict(preset='cosmati-floor',surface='floor',size_uv=[16,16]))
  saved=dispatch(self.root,'structure_save',{k:viewed[k] for k in ('preview_id','preview_sha256')})
  from nbt_components import library_root
  record=json.loads((library_root(self.root)/'recipes'/(saved['id']+'.json')).read_text(encoding='utf8'))
  self.assertEqual(record['pattern_recipe']['sample_sha256'],viewed['sample_sha256'])
  self.assertEqual(record['pattern_recipe']['parameters']['preset'],'cosmati-floor')

 def test_stair_orientation_is_inferred_from_image_contours(self):
  from PIL import Image
  from nbt_collision import collision_cells
  from nbt_ornament_sample import match_silhouette
  masks={'wall':[(1,1,1,0),(1,1,0,1),(1,0,1,1),(0,1,1,1)],
         'ceiling':[(1,1,0,0),(0,0,1,1),(1,0,1,0),(0,1,0,1)]}
  for surface,variants in masks.items():
   orientations=set()
   for mask in variants:
    with self.subTest(surface=surface,mask=mask):
     image=Image.new('L',(6,6))
     for x in range(6):
      for y in range(6):image.putpixel((x,5-y),255*mask[x%2+2*(y%2)])
     file=self.root/'contour.png';image.save(file)
     args=dict(surface=surface,size_uv=[3,3],shapes=dict(stairs='quartz_stairs'),sample=dict(path=file.name,sha256=hashlib.sha256(file.read_bytes()).hexdigest(),noise_strength=0))
     result=dispatch(self.root,'pattern_compile',args);data=build(self.root,result['spec'])
     self.assertEqual(result['shape_counts'],{'stairs':9})
     self.assertEqual(result['fitting']['missing']+result['fitting']['extra'],0)
     self.assertEqual(len(result['stair_orientations']),1)
     orientations.update(result['stair_orientations'])
     for x,y,z,index,_ in data['blocks']:
      if (surface=='wall' and z==1) or (surface=='ceiling' and y==0):
       cells,_=collision_cells(data['palette'][index])
       projected={(a,b) for a,b,c in cells} if surface=='wall' else {(a,c) for a,b,c in cells if b==0}
       self.assertEqual(tuple(int(p in projected) for p in ((0,0),(1,0),(0,1),(1,1))),mask)
   self.assertEqual(len(orientations),4)
  # Same binary corner can fit two directions. Gray edge coverage decides.
  options=[('row',(1,1,0,0)),('column',(1,0,1,0))]
  self.assertEqual(match_silhouette((1,0,0,0),options,(1,.01,.49,0))[0],'column')

 def test_cli_agent_entry_uses_the_same_contract_and_does_not_require_electron(self):
  file=self.root/'request.json';file.write_text(json.dumps({'spec':self.spec}))
  run=subprocess.run([sys.executable,str(SCRIPTS/'nbt_components.py'),'--workspace',str(self.root),'agent','--tool','structure_preview','--request',str(file)],capture_output=True,text=True,encoding='utf8')
  self.assertEqual(run.returncode,0,run.stdout+run.stderr);result=json.loads(run.stdout)['result'];self.assertTrue(Path(result['thumbnail']).is_file())
  self.assertEqual(set(definitions()),{'structure_list','structure_read','structure_view','structure_preview','structure_write','structure_place','structure_save','parametric_list','parametric_compile','parametric_preview','parametric_contract','parametric_validate','parametric_surface','parametric_mount','parametric_layout','parametric_compose','parametric_regenerate','pattern_list','pattern_compile','pattern_preview','pattern_mount','pattern_cylinder_mount','pattern_create','pattern_assets','pattern_microfit','scene_compile','scene_save','scene_read','scene_update','mount_batch','surface_decorate','pattern_filter','tracery_compile','vault_compile','bay_compile','facade_compile','compute_info','field_compile','pattern_warp'})


if __name__=='__main__':unittest.main(verbosity=2)
