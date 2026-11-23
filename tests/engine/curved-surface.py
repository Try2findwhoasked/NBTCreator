"""Eccentric loft surface sampling and protected relief candidates."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_reference_views import register_reference,save_fit
from nbt_working_model import WorkingModel
from nbt_refine import read_master
from nbt_curved_surface import plan_curve,verify_curve


class CurvedSurface(unittest.TestCase):
 def setUp(self):
  spec=importlib.util.spec_from_file_location('reference_fixture',ROOT/'tests/engine/reference-views.py')
  module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
  self.fixture=module.ReferenceViews('test_anchor_profile_generates_repeatable_bounded_loft_sections')
  self.fixture.setUp();self.addCleanup(self.fixture.doCleanups);self.root=self.fixture.root
  # Use a non-circular section whose centre shifts with height.
  for anchor in self.fixture.request['anchors']:
   if anchor['id'].startswith('z_min'):anchor['world'][2]=3
   if anchor['id'].startswith('z_max'):anchor['world'][2]=9
   x,y,z=anchor['world'];anchor['views']=dict(front=[4+2*x,50-2*y],side=[4+2*z,50-2*y],top=[4+2*x,4+2*z])
  registered=register_reference(self.root,self.fixture.request)
  fit=save_fit(self.root,dict(reference=registered['manifest'],reference_sha256=registered['manifest_sha256'],
      part='tower',rows=[self.fixture.rows[0],self.fixture.rows[2]],sample_step=1,vertices=32),
      'nbt_models/_workspaces/reference-fits/curve.json')
  self.fit=fit
  working=WorkingModel(self.root,[20,10,16])
  geometry=json.loads(Path(fit['output']).read_text(encoding='utf8'))['geometry']
  working.apply_operations([dict(kind='geometry',label='曲面宿主',classification='wall',lo=[0,0,0],hi=[19,8,15],
                                  state='stone_bricks',geometry=geometry)])
  self.source=working.save_draft(name_zh='曲面宿主')
  self.mask=self.root/'inputs/curve-mask.json'
  self.write_mask(dict(schema_version=1,name='合成曲面饰面',rows=['R.C..I..'],palette={
    'R':dict(kind='raise',state='stone_brick_slab[type=bottom,waterlogged=false]',height=1,wall=False,role='rim'),
    'C':dict(kind='cut',depth=1,backing=1,role='groove'),
    'I':dict(kind='inlay',depth=2,backing=1,state='gold_block',wall=True,role='relief')}))
 def write_mask(self,data):
  self.mask.write_text(json.dumps(data,ensure_ascii=False),encoding='utf8')
 def request(self):
  return dict(source=self.source['source'],source_sha256=self.source['source_sha256'],
    profile=self.fit['output'],profile_sha256=self.fit['sha256'],mask=str(self.mask),
    mask_sha256=hashlib.sha256(self.mask.read_bytes()).hexdigest(),
    mapping=dict(u_start=0,u_span=1,y_start=2,max_distance=2),
    output='nbt_models/_workspaces/curve-samples/sample',
    cameras=[dict(id='oblique',eye=[22,14,-8],target=[8,4,6])])
 def test_one_candidate_contains_backed_groove_inlay_and_supported_rim(self):
  before=Path(self.source['source']).read_bytes();result=plan_curve(self.root,self.request())
  self.assertFalse(result['approval_created']);self.assertFalse(result['nbt_exported'])
  self.assertEqual(Path(self.source['source']).read_bytes(),before)
  self.assertEqual(result['summary']['pixels'],3)
  self.assertEqual({item['kind'] for item in result['samples']},{'raise','cut','inlay'})
  candidate,walls=read_master(result['candidate'])
  for sample in result['samples']:
   self.assertEqual(sum(abs(v) for v in sample['face_normal']),1)
   self.assertGreaterEqual(sample['backing_verified'],sample.get('backing_required',0))
   for change in sample['changes']:
    self.assertEqual(candidate.get(tuple(change['pos'])),change['after'][0])
    self.assertEqual(tuple(change['pos']) in walls,change['after'][1])
 def test_insufficient_backing_or_stale_mask_refuses_publication(self):
  from nbt_snbt import save_snbt
  sample=next(item for item in plan_curve(self.root,self.request())['samples'] if item['kind']=='cut')
  model,walls=read_master(self.source['source']);back=tuple(sample['host'][i]-sample['face_normal'][i] for i in range(3))
  model.put(back,'air');walls.discard(back)
  source=self.root/'nbt_models/standalone/thin/v01/master/model.snbt';saved=save_snbt(source,model,walls)
  data=json.loads(self.mask.read_text(encoding='utf8'));data['rows']=['..C.....'];data['palette']={'C':data['palette']['C']}
  self.write_mask(data);request=self.request();request.update(source=str(source),source_sha256=saved['source_sha256'],output='nbt_models/_workspaces/curve-samples/thin')
  with self.assertRaisesRegex(ValueError,'背衬|厚度|支承'):plan_curve(self.root,request)
  self.assertFalse((self.root/request['output']).exists())
  request=self.request();request['output']='nbt_models/_workspaces/curve-samples/stale';request['mask_sha256']='0'*64
  with self.assertRaisesRegex(ValueError,'哈希'):plan_curve(self.root,request)
  self.assertFalse((self.root/request['output']).exists())
 def test_protected_surface_is_rejected_without_modifying_source(self):
  result=plan_curve(self.root,self.request());point=result['samples'][0]['changes'][0]['pos']
  request=self.request();request['output']='nbt_models/_workspaces/curve-samples/protected'
  original,walls=read_master(self.source['source'])
  protected=WorkingModel(self.root,list(original.size),context=dict(mode='standalone',openings=[],protected_boxes=[dict(lo=point,hi=point)]))
  protected.model.blocks=dict(original.blocks);protected.walls=set(walls);saved=protected.save_draft(name_zh='受保护宿主')
  request.update(source=saved['source'],source_sha256=saved['source_sha256'])
  before=Path(saved['source']).read_bytes()
  with self.assertRaisesRegex(ValueError,'CURVE_PROTECTED'):plan_curve(self.root,request)
  self.assertFalse((self.root/request['output']).exists());self.assertEqual(Path(saved['source']).read_bytes(),before)
 def test_disconnected_uv_stroke_is_reported_instead_of_claiming_continuity(self):
  data=json.loads(self.mask.read_text(encoding='utf8'));data['rows']=['RR'];data['palette']={'R':data['palette']['R']}
  self.write_mask(data);request=self.request();request['mapping'].update(u_start=.02,u_span=.9)
  result=plan_curve(self.root,request)
  self.assertGreater(result['continuity']['broken_pairs'],0)
  self.assertFalse(result['continuity']['passed'])
 def test_inlay_cannot_replace_another_raised_elements_backing(self):
  data=json.loads(self.mask.read_text(encoding='utf8'));data['rows']=['RI']
  data['palette']={'R':data['palette']['R'],'I':dict(data['palette']['I'],depth=1)}
  self.write_mask(data);request=self.request();request['mapping'].update(u_start=.01,u_span=.01)
  with self.assertRaisesRegex(ValueError,'CURVE_BACKING_CONFLICT'):plan_curve(self.root,request)
  self.assertFalse((self.root/request['output']).exists())
 def test_explicit_effective_recess_depth_checks_deeper_unchanged_backing(self):
  working=WorkingModel(self.root,[20,10,16])
  for pos in ((3,2,3),(2,2,3),(2,2,2),(1,2,3)):working.model.put(pos,'stone')
  saved=working.save_draft(name_zh='曲面相邻切口宿主')
  data=dict(schema_version=1,name='相邻切口',rows=['WW'],palette={'W':dict(kind='inlay',state='blackstone',
   wall=True,depth=1,backing=1,role='window')})
  self.write_mask(data);request=self.request();request.update(source=saved['source'],source_sha256=saved['source_sha256'])
  request['mapping'].update(u_start=0,u_span=.2);before=Path(saved['source']).read_bytes()
  def surface(sections,y,u):return [u,0],[1,0]
  def faces(model,expected,normal,y,maximum):
   return ((3,2,3),(1,0,0),0) if expected[0]<.1 else ((2,2,3),(0,0,1),0)
  with patch('nbt_curved_surface._actual_face',side_effect=faces),patch('nbt_curved_surface._surface_point',side_effect=surface):
   with self.assertRaisesRegex(ValueError,'CURVE_BACKING_CONFLICT'):plan_curve(self.root,request)
   self.assertFalse((self.root/request['output']).exists())
   data['palette']['W']['max_effective_depth']=2;self.write_mask(data);request['mask_sha256']=hashlib.sha256(self.mask.read_bytes()).hexdigest()
   result=plan_curve(self.root,request)
   first=result['samples'][0]['faces'][0]
   self.assertEqual(first['effective_depth'],2);self.assertEqual(first['backing_positions'],[[1,2,3]])
   self.assertEqual(first['air_depth_full_voxels'],0)
   self.assertEqual(result['summary']['effective_depth'],dict(maximum=2,max_air_full_voxels=0,extended_faces=1,checked_faces=2))
   self.assertTrue(verify_curve(self.root,result['plan'],result['plan_sha256'])['valid'])
   data['rows']=['WX'];data['palette']['X']=dict(data['palette']['W']);self.write_mask(data)
   request['mask_sha256']=hashlib.sha256(self.mask.read_bytes()).hexdigest();request['output']='nbt_models/_workspaces/curve-samples/other-symbol'
   with self.assertRaisesRegex(ValueError,'CURVE_BACKING_CONFLICT'):plan_curve(self.root,request)
   self.assertFalse((self.root/request['output']).exists())
   data['rows']=['WW'];data['palette'].pop('X');self.write_mask(data)
   from nbt_snbt import save_snbt
   thin,walls=read_master(saved['source']);thin.put((1,2,3),'air');walls.discard((1,2,3))
   thin_file=self.root/'nbt_models/standalone/effective-thin/v01/master/model.snbt';thin_saved=save_snbt(thin_file,thin,walls)
   request.update(mask_sha256=hashlib.sha256(self.mask.read_bytes()).hexdigest(),source=str(thin_file),source_sha256=thin_saved['source_sha256'],
    output='nbt_models/_workspaces/curve-samples/effective-thin')
   with self.assertRaisesRegex(ValueError,'CURVE_BACKING_CONFLICT'):plan_curve(self.root,request)
   self.assertFalse((self.root/request['output']).exists())
   layered=dict(schema_version=2,name='有效深度分层',layers=[
    dict(id='window',rows=['WW'],palette={'W':data['palette']['W']}),
    dict(id='band',rows=['R.'],palette={'R':dict(kind='raise',state='stone_bricks',height=1,wall=False,role='band')},
         support_expectations={'R':dict(state='blackstone',wall=True)})],overlaps=[['band','window']])
   self.write_mask(layered);request.update(mask_sha256=hashlib.sha256(self.mask.read_bytes()).hexdigest(),source=saved['source'],
    source_sha256=saved['source_sha256'],output='nbt_models/_workspaces/curve-samples/effective-layered')
   combined=plan_curve(self.root,request)
   window=next(sample for sample in combined['samples'] if sample['layer']=='window' and sample['uv']==[0,0])
   self.assertEqual(window['faces'][0]['effective_depth'],2);self.assertEqual(len(combined['summary']['support_replacements']),1)
   self.assertEqual(combined['summary']['effective_depth'],dict(maximum=2,max_air_full_voxels=0,extended_faces=1,checked_faces=2))
   self.assertTrue(verify_curve(self.root,combined['plan'],combined['plan_sha256'])['valid'])
   cut=dict(schema_version=1,name='空气深槽',rows=['CC'],palette={'C':dict(kind='cut',depth=1,backing=1,max_effective_depth=2,role='groove')})
   self.write_mask(cut);request.update(mask_sha256=hashlib.sha256(self.mask.read_bytes()).hexdigest(),
    output='nbt_models/_workspaces/curve-samples/effective-cut')
   cut_result=plan_curve(self.root,request)
   self.assertEqual(cut_result['samples'][0]['faces'][0]['air_depth_full_voxels'],2)
   self.assertEqual(cut_result['summary']['effective_depth']['max_air_full_voxels'],2)
  self.assertEqual(Path(saved['source']).read_bytes(),before)
 def test_effective_recess_depth_requires_explicit_bounded_integer(self):
  for value in (0,7,True,'2'):
   data=json.loads(self.mask.read_text(encoding='utf8'));data['rows']=['..C.....'];data['palette']={'C':data['palette']['C']}
   data['palette']['C']['max_effective_depth']=value;self.write_mask(data);request=self.request()
   with self.subTest(value=value):
    with self.assertRaisesRegex(ValueError,'最大实际切深'):plan_curve(self.root,request)
    self.assertFalse((self.root/request['output']).exists())
 def test_same_stroke_can_share_a_voxel_with_explicit_merge_diagnostics(self):
  data=json.loads(self.mask.read_text(encoding='utf8'));data['rows']=['RR'];data['palette']={'R':data['palette']['R']}
  self.write_mask(data);request=self.request();request['mapping'].update(u_start=.01,u_span=.01)
  result=plan_curve(self.root,request)
  self.assertGreater(result['summary']['merged_writes'],0);self.assertTrue(result['continuity']['passed'])
  self.assertTrue(verify_curve(self.root,result['plan'],result['plan_sha256'])['valid'])
 def test_one_uv_cell_can_sample_a_wider_curved_band(self):
  data=json.loads(self.mask.read_text(encoding='utf8'));data['rows']=['R.......'];data['palette']={'R':data['palette']['R']}
  self.write_mask(data);request=self.request();request['mapping']['u_subsamples']=4
  result=plan_curve(self.root,request)
  self.assertGreater(len(result['samples'][0]['faces']),1)
  self.assertGreater(result['summary']['changed_positions'],1)
  self.assertTrue(verify_curve(self.root,result['plan'],result['plan_sha256'])['valid'])
 def test_opt_in_connector_is_in_candidate_and_recomputed_by_verifier(self):
  from nbt_curved_surface import _surface_point
  geometry=json.loads(Path(self.fit['output']).read_text(encoding='utf8'))['geometry']['sections']
  first,_=_surface_point(geometry,2.5,.05)
  working=WorkingModel(self.root,[20,10,16]);working.model.put((2,2,1),'stone');working.model.put((2,2,3),'stone')
  saved=working.save_draft(name_zh='连接回归宿主')
  data=json.loads(self.mask.read_text(encoding='utf8'));data['rows']=['RR'];data['palette']={'R':dict(kind='raise',
   state='stone_bricks',height=1,wall=False,role='rim')};self.write_mask(data)
  request=self.request();request.update(source=saved['source'],source_sha256=saved['source_sha256'])
  request['mapping'].update(u_start=0,u_span=.2,connect_raised=dict(max_new_blocks=2))
  before=Path(saved['source']).read_bytes()
  def faces(model,expected,normal,y,maximum):
   return ((2,2,1),(0,0,1),0) if expected==first else ((2,2,3),(1,0,0),0)
  with patch('nbt_curved_surface._actual_face',side_effect=faces):
   result=plan_curve(self.root,request)
   self.assertTrue(result['continuity']['passed']);self.assertEqual(result['summary']['connectors_added'],1)
   self.assertEqual(result['summary']['raw_writes'],result['summary']['requested_positions']+result['summary']['merged_writes'])
   self.assertEqual(result['samples'][0]['connectors'][0]['pos'],[3,2,2])
   self.assertTrue(verify_curve(self.root,result['plan'],result['plan_sha256'])['valid'])
   file=Path(result['plan']);proof=json.loads(file.read_text(encoding='utf8'))
   proof['samples'][0]['connectors'][0]['endpoint_hosts'][0][0]+=1
   file.write_text(json.dumps(proof),encoding='utf8')
   with self.assertRaisesRegex(ValueError,'采样.*不一致'):verify_curve(self.root,file,hashlib.sha256(file.read_bytes()).hexdigest())
  self.assertEqual(Path(saved['source']).read_bytes(),before)
 def test_multi_block_connector_option_is_bound_in_candidate_proof(self):
  working=WorkingModel(self.root,[20,10,16]);working.model.put((2,2,1),'stone');working.model.put((5,2,1),'stone')
  saved=working.save_draft(name_zh='短连接宿主')
  data=json.loads(self.mask.read_text(encoding='utf8'));data['rows']=['RR'];data['palette']={'R':dict(kind='raise',
   state='stone_bricks',height=1,wall=False,role='band')};self.write_mask(data)
  request=self.request();request.update(source=saved['source'],source_sha256=saved['source_sha256'])
  request['mapping'].update(u_start=0,u_span=.2,connect_raised=dict(max_new_blocks=2,max_bridge_steps=2));before=Path(saved['source']).read_bytes()
  def surface(sections,y,u):return [u,0],[0,1]
  def faces(model,expected,normal,y,maximum):return ((2,2,1),(0,0,1),0) if expected[0]<.1 else ((5,2,1),(0,0,1),0)
  with patch('nbt_curved_surface._actual_face',side_effect=faces),patch('nbt_curved_surface._surface_point',side_effect=surface):
   result=plan_curve(self.root,request);self.assertEqual(result['summary']['connectors_added'],2)
   self.assertTrue(result['continuity']['passed'])
   self.assertEqual(result['samples'][0]['connectors'][0]['path'],[[3,2,2],[4,2,2]])
   self.assertTrue(verify_curve(self.root,result['plan'],result['plan_sha256'])['valid'])
  self.assertEqual(Path(saved['source']).read_bytes(),before)
 def test_explicit_bridge_path_is_bound_and_replayed(self):
  working=WorkingModel(self.root,[20,10,16]);working.model.put((2,2,1),'stone');working.model.put((4,3,1),'stone')
  saved=working.save_draft(name_zh='路径选择宿主')
  data=dict(schema_version=1,name='斜向连接',rows=['R.','.R'],palette={'R':dict(kind='raise',state='stone_bricks',height=1,wall=False,role='band')})
  self.write_mask(data);request=self.request();request.update(source=saved['source'],source_sha256=saved['source_sha256'])
  request['mapping'].update(u_start=0,u_span=.2,connect_raised=dict(max_new_blocks=2,max_bridge_steps=2));before=Path(saved['source']).read_bytes()
  def surface(sections,y,u):return [u,0],[0,1]
  def faces(model,expected,normal,y,maximum):return ((2,2,1),(0,0,1),0) if y==2 else ((4,3,1),(0,0,1),0)
  with patch('nbt_curved_surface._actual_face',side_effect=faces),patch('nbt_curved_surface._surface_point',side_effect=surface):
   from nbt_working_model import ModelConflict
   with self.assertRaises(ModelConflict) as error:plan_curve(self.root,request)
   self.assertEqual(error.exception.code,'CURVE_CONNECT_AMBIGUOUS');conflict=error.exception.conflicts[0]
   self.assertEqual(len(conflict['paths']),3);self.assertFalse((self.root/request['output']).exists())
   choice=dict(endpoints=conflict['endpoints'],path=conflict['paths'][0]);request['mapping']['connect_raised']['path_choices']=[choice]
   result=plan_curve(self.root,request);self.assertTrue(result['continuity']['passed'])
   selected=[item for sample in result['samples'] for item in sample.get('connectors',[])]
   self.assertEqual(len(selected),2);self.assertTrue(all(item['selection']=='explicit' for item in selected))
   self.assertTrue(verify_curve(self.root,result['plan'],result['plan_sha256'])['valid'])
   file=Path(result['plan']);proof=json.loads(file.read_text(encoding='utf8'))
   proof['mapping']['connect_raised']['path_choices'][0]['path']=conflict['paths'][1]
   file.write_text(json.dumps(proof),encoding='utf8')
   with self.assertRaisesRegex(ValueError,'采样.*不一致'):verify_curve(self.root,file,hashlib.sha256(file.read_bytes()).hexdigest())
  self.assertEqual(Path(saved['source']).read_bytes(),before)
 def test_connector_configuration_has_a_bounded_explicit_budget(self):
  for key in ('connect_raised','connect_recess'):
   for invalid in (None,True,{},dict(max_new_blocks=0),dict(max_new_blocks=65),dict(max_new_blocks=True)):
    request=self.request();request['mapping'][key]=invalid
    with self.subTest(key=key,invalid=invalid):
     with self.assertRaisesRegex(ValueError,'预算'):plan_curve(self.root,request)
     self.assertFalse((self.root/request['output']).exists())
  for steps in (0,4,True,'2'):
   request=self.request();request['mapping']['connect_raised']=dict(max_new_blocks=4,max_bridge_steps=steps)
   with self.subTest(steps=steps):
    with self.assertRaisesRegex(ValueError,'中间格'):plan_curve(self.root,request)
    self.assertFalse((self.root/request['output']).exists())
 def test_opt_in_recess_connector_replays_depth_and_backing(self):
  working=WorkingModel(self.root,[20,10,16])
  for x in (2,3,4):
   for z in (2,3):working.model.put((x,2,z),'stone')
  saved=working.save_draft(name_zh='凹槽连接回归宿主')
  data=json.loads(self.mask.read_text(encoding='utf8'));data['rows']=['CC'];data['palette']={'C':dict(kind='cut',depth=1,backing=1,role='groove')}
  self.write_mask(data);request=self.request();request.update(source=saved['source'],source_sha256=saved['source_sha256'])
  request['mapping'].update(u_start=0,u_span=.2,connect_recess=dict(max_new_blocks=2));before=Path(saved['source']).read_bytes()
  def surface(sections,y,u):return ([2.5,2] if u<.1 else [4.5,2]),[0,-1]
  def faces(model,expected,normal,y,maximum):
   return ((2,2,2),(0,0,-1),0) if expected[0]<3 else ((4,2,2),(0,0,-1),0)
  with patch('nbt_curved_surface._actual_face',side_effect=faces),patch('nbt_curved_surface._surface_point',side_effect=surface):
   result=plan_curve(self.root,request);self.assertTrue(result['continuity']['passed'])
   self.assertEqual(result['summary']['recess_connectors_added'],1)
   connector=result['samples'][0]['connectors'][0]
   self.assertEqual(connector['backing'],[[3,2,3]]);self.assertEqual(connector['writes'][0]['after'],['minecraft:air',False])
   self.assertTrue(verify_curve(self.root,result['plan'],result['plan_sha256'])['valid'])
   file=Path(result['plan']);proof=json.loads(file.read_text(encoding='utf8'))
   proof['samples'][0]['connectors'][0]['backing'][0][2]+=1;file.write_text(json.dumps(proof),encoding='utf8')
   with self.assertRaisesRegex(ValueError,'采样.*不一致'):verify_curve(self.root,file,hashlib.sha256(file.read_bytes()).hexdigest())
  self.assertEqual(Path(saved['source']).read_bytes(),before)
 def layered_mask(self):
  return dict(schema_version=2,name='叠放样段',layers=[
   dict(id='band',rows=['R.......'],palette={'R':dict(kind='raise',state='stone_bricks',height=1,wall=False,role='band')},
        support_expectations={'R':dict(state='blackstone',wall=True)}),
   dict(id='window',rows=['W.......'],palette={'W':dict(kind='inlay',state='blackstone',wall=True,depth=1,backing=1,role='window')})],
   overlaps=[['band','window']])
 def test_layered_band_over_window_binds_final_full_support(self):
  self.write_mask(self.layered_mask());request=self.request();before=Path(self.source['source']).read_bytes()
  result=plan_curve(self.root,request);self.assertEqual(result['summary']['layers'],2)
  self.assertEqual(result['summary']['overlapping_uv'],1)
  self.assertEqual(result['summary']['overlap_details'],[dict(layers=['band','window'],uv=[0,0])])
  band=next(sample for sample in result['samples'] if sample['layer']=='band')
  window=next(sample for sample in result['samples'] if sample['layer']=='window')
  self.assertEqual(band['host'],window['host'])
  candidate,walls=read_master(result['candidate']);host=tuple(band['host'])
  self.assertEqual(candidate.get(host),'minecraft:blackstone');self.assertIn(host,walls)
  self.assertTrue(verify_curve(self.root,result['plan'],result['plan_sha256'])['valid'])
  self.assertEqual(Path(self.source['source']).read_bytes(),before);self.assertFalse(result['approval_created'])
  cli_request=dict(request,output='nbt_models/_workspaces/curve-samples/layered-cli')
  request_file=self.root/'layered-request.json';request_file.write_text(json.dumps(cli_request),encoding='utf8')
  run=subprocess.run(['node',str(ROOT/'scripts/cli.mjs'),'--workspace',str(self.root),'curve','plan','--request',str(request_file),'--compact'],
   capture_output=True,text=True,encoding='utf8',timeout=90)
  self.assertEqual(run.returncode,0,run.stdout+run.stderr);cli_result=json.loads(run.stdout)
  from nbt_exposure import apply
  apply(self.root);facade=self.root/'.agents/skills/nbtcreator-workspace/nbt.py'
  run=subprocess.run([sys.executable,str(facade),'curve','verify','--plan',cli_result['plan'],'--sha256',cli_result['plan_sha256']],
   cwd=self.root,capture_output=True,text=True,encoding='utf8',timeout=90)
  self.assertEqual(run.returncode,0,run.stdout+run.stderr);self.assertTrue(json.loads(run.stdout)['valid'])
  file=Path(result['plan']);proof=json.loads(file.read_text(encoding='utf8'))
  proof['summary']['support_replacements'][0]['after'][0]='minecraft:gold_block';file.write_text(json.dumps(proof),encoding='utf8')
  with self.assertRaisesRegex(ValueError,'采样.*不一致'):verify_curve(self.root,file,hashlib.sha256(file.read_bytes()).hexdigest())
 def test_layered_overlap_and_support_are_explicit_and_protected(self):
  data=self.layered_mask();data['overlaps']=[];self.write_mask(data);request=self.request()
  with self.assertRaisesRegex(ValueError,'重叠'):plan_curve(self.root,request)
  self.assertFalse((self.root/request['output']).exists())
  data=self.layered_mask();data['layers'][0].pop('support_expectations');self.write_mask(data);request=self.request()
  with self.assertRaisesRegex(ValueError,'支承|背衬|CURVE_LAYER_SUPPORT'):plan_curve(self.root,request)
  self.assertFalse((self.root/request['output']).exists())
  data=self.layered_mask();data['layers'][0]['support_expectations']['R']['state']='gold_block';self.write_mask(data);request=self.request()
  with self.assertRaisesRegex(ValueError,'支承|背衬|CURVE_LAYER_SUPPORT'):plan_curve(self.root,request)
  self.assertFalse((self.root/request['output']).exists())
  data=self.layered_mask();data['layers'][0]['support_expectations']['R']['wall']=False;self.write_mask(data);request=self.request()
  with self.assertRaisesRegex(ValueError,'CURVE_LAYER_SUPPORT'):plan_curve(self.root,request)
  self.assertFalse((self.root/request['output']).exists())
  data=self.layered_mask();data['layers'][0]['support_expectations']['R']['state']='stone_brick_slab[type=bottom,waterlogged=false]'
  self.write_mask(data);request=self.request()
  with self.assertRaisesRegex(ValueError,'完整|支承'):plan_curve(self.root,request)
  self.assertFalse((self.root/request['output']).exists())
 def test_layered_quantization_cannot_bypass_explicit_overlap_permission(self):
  data=self.layered_mask();data['layers'][1]['rows']=['.W......'];data['overlaps']=[];self.write_mask(data)
  request=self.request();request['mapping'].update(u_start=.01,u_span=.01)
  with self.assertRaisesRegex(ValueError,'CURVE_LAYER_SUPPORT|重叠'):plan_curve(self.root,request)
  self.assertFalse((self.root/request['output']).exists())
 def test_layered_overlap_details_are_bounded_and_counted(self):
  from nbt_curved_surface import _mask
  data=self.layered_mask();data['layers'][0]['rows']=['R'*20]*20;data['layers'][1]['rows']=['W'*20]*20
  self.write_mask(data);parsed,_=_mask(self.mask,hashlib.sha256(self.mask.read_bytes()).hexdigest())
  self.assertEqual(parsed['overlapping_uv'],400);self.assertEqual(parsed['overlap_pairs'],400)
  self.assertEqual(len(parsed['overlap_details']),256);self.assertTrue(parsed['overlap_details_truncated'])
 def test_layer_can_explicitly_skip_one_connection_policy(self):
  data=self.layered_mask();data['layers'][0]['connections']={'raised':False}
  data['layers'][1]['connections']={'recess':True};self.write_mask(data);request=self.request()
  request['mapping'].update(connect_raised=dict(max_new_blocks=2),connect_recess=dict(max_new_blocks=2))
  result=plan_curve(self.root,request)
  self.assertEqual(result['summary']['connection_skips'],[dict(layer='band',kind='raised')])
  self.assertTrue(verify_curve(self.root,result['plan'],result['plan_sha256'])['valid'])
  data['layers'][0]['connections']={'raised':True};self.write_mask(data);request=self.request()
  request['output']='nbt_models/_workspaces/curve-samples/missing-connection-budget'
  with self.assertRaisesRegex(ValueError,'连接.*预算'):plan_curve(self.root,request)
  self.assertFalse((self.root/request['output']).exists())
 def test_layered_explicit_bridge_choices_are_scoped_and_replayed(self):
  working=WorkingModel(self.root,[20,10,16])
  for host in ((2,2,1),(4,3,1),(9,2,1)):working.model.put(host,'stone')
  saved=working.save_draft(name_zh='分层路径选择')
  action=dict(kind='raise',state='stone_bricks',height=1,wall=False,role='band')
  data=dict(schema_version=2,name='分层路径',layers=[dict(id='band',rows=['R..','.R.'],palette={'R':action}),
   dict(id='aux',rows=['..S','...'],palette={'S':action})],overlaps=[])
  self.write_mask(data);request=self.request();request.update(source=saved['source'],source_sha256=saved['source_sha256'])
  choice=dict(endpoints=[[2,2,2],[4,3,2]],path=[[3,2,2],[4,2,2]])
  request['mapping'].update(u_start=0,u_span=.3,connect_raised=dict(max_new_blocks=2,max_bridge_steps=2,path_choices=[choice]))
  def surface(sections,y,u):return [u,0],[0,1]
  def faces(model,expected,normal,y,maximum):
   return ((4,3,1),(0,0,1),0) if y==3 else ((2,2,1),(0,0,1),0) if expected[0]<.1 else ((9,2,1),(0,0,1),0)
  with patch('nbt_curved_surface._actual_face',side_effect=faces),patch('nbt_curved_surface._surface_point',side_effect=surface):
   with self.assertRaisesRegex(ValueError,'layer'):plan_curve(self.root,request)
   self.assertFalse((self.root/request['output']).exists())
   choice['layer']='band';data['layers'][0]['connections']={'raised':False};self.write_mask(data)
   request['mask_sha256']=hashlib.sha256(self.mask.read_bytes()).hexdigest()
   with self.assertRaisesRegex(ValueError,'已跳过'):plan_curve(self.root,request)
   self.assertFalse((self.root/request['output']).exists())
   data['layers'][0].pop('connections');self.write_mask(data);request['mask_sha256']=hashlib.sha256(self.mask.read_bytes()).hexdigest()
   result=plan_curve(self.root,request)
   self.assertEqual(result['summary']['connectors_added'],2);self.assertTrue(result['continuity']['passed'])
   self.assertTrue(verify_curve(self.root,result['plan'],result['plan_sha256'])['valid'])
 def test_layered_sampling_limit_is_global_not_per_layer(self):
  data=self.layered_mask();data['layers'][0]['rows']=['R'*64]*64;data['layers'][1]['rows']=['W'*64]*64
  self.write_mask(data);request=self.request();request['mapping']['u_subsamples']=2
  with patch('nbt_curved_surface._actual_face') as search:
   with self.assertRaisesRegex(ValueError,'8192'):plan_curve(self.root,request)
   search.assert_not_called()
  self.assertFalse((self.root/request['output']).exists())
 def test_layered_recess_error_identifies_the_source_layer(self):
  from nbt_curved_surface import _calculate_layers
  from nbt_working_model import ModelConflict
  error=ModelConflict('CURVE_RECESS_DISCONNECTED',[dict(reason='曲面凹槽笔画无法连接',symbol='W',uv=[1,2])])
  mask=dict(layers=[dict(id='windows',rows=['W'],connections={})])
  mapping=dict(u_start=0,u_span=.25,y_start=0,max_distance=2)
  with patch('nbt_curved_surface._calculate_single',side_effect=error):
   with self.assertRaises(ModelConflict) as raised:_calculate_layers(None,None,mask,mapping)
  self.assertEqual(raised.exception.code,'CURVE_RECESS_DISCONNECTED')
  self.assertEqual(raised.exception.conflicts[0]['layer'],'windows')
  self.assertNotIn('layer',error.conflicts[0])
 def test_layered_protected_hosts_and_conflicting_writes_are_atomic(self):
  data=self.layered_mask();self.write_mask(data);baseline=plan_curve(self.root,self.request())
  host=next(sample['host'] for sample in baseline['samples'] if sample['layer']=='window')
  original,walls=read_master(self.source['source'])
  from nbt_snbt import save_snbt
  source=self.root/'nbt_models/standalone/protected/v01/master/model.snbt';saved=save_snbt(source,original,walls)
  request=self.request();request.update(source=str(source),source_sha256=saved['source_sha256'],
   context=dict(mode='standalone',openings=[],protected_boxes=[dict(lo=host,hi=host)]),
   output='nbt_models/_workspaces/curve-samples/layer-protected')
  before=source.read_bytes()
  with self.assertRaisesRegex(ValueError,'CURVE_PROTECTED'):plan_curve(self.root,request)
  self.assertFalse((self.root/request['output']).exists());self.assertEqual(source.read_bytes(),before)
  data=self.layered_mask();data['layers'][0]=dict(id='first',rows=['X.......'],palette={'X':dict(kind='inlay',
   state='gold_block',wall=True,depth=1,backing=1,role='accent')});data['overlaps']=[['first','window']]
  self.write_mask(data);request=self.request();request['output']='nbt_models/_workspaces/curve-samples/layer-conflict'
  with self.assertRaisesRegex(ValueError,'CURVE_LAYER_CONFLICT'):plan_curve(self.root,request)
  self.assertFalse((self.root/request['output']).exists())
 def test_layered_cut_cannot_consume_another_layers_backing(self):
  data=dict(schema_version=2,name='分层背衬',layers=[
   dict(id='shallow',rows=['C.......'],palette={'C':dict(kind='cut',depth=1,backing=1,role='groove')}),
   dict(id='deep',rows=['D.......'],palette={'D':dict(kind='cut',depth=2,backing=1,role='groove')})],overlaps=[['shallow','deep']])
  self.write_mask(data);request=self.request()
  with self.assertRaisesRegex(ValueError,'CURVE_LAYER_SUPPORT|背衬'):plan_curve(self.root,request)
  self.assertFalse((self.root/request['output']).exists())
 def test_layered_identical_declared_writes_merge_with_accounting(self):
  spec=dict(kind='inlay',state='blackstone',wall=True,depth=1,backing=1,role='window')
  data=dict(schema_version=2,name='共享写入',layers=[dict(id='first',rows=['W.......'],palette={'W':spec}),
   dict(id='second',rows=['W.......'],palette={'W':spec})],overlaps=[['first','second']])
  self.write_mask(data);result=plan_curve(self.root,self.request());summary=result['summary']
  self.assertEqual(summary['cross_layer_shared_writes'],1)
  self.assertEqual(summary['raw_writes'],summary['requested_positions']+summary['merged_writes'])
  self.assertTrue(verify_curve(self.root,result['plan'],result['plan_sha256'])['valid'])
 def test_layered_connector_budget_applies_across_all_layers(self):
  working=WorkingModel(self.root,[20,10,16])
  for host in ((2,2,1),(2,2,3),(7,2,1),(7,2,3)):working.model.put(host,'stone')
  saved=working.save_draft(name_zh='分层连接预算')
  spec=dict(kind='raise',state='stone_bricks',height=1,wall=False,role='band')
  data=dict(schema_version=2,name='预算',layers=[dict(id='first',rows=['RR..'],palette={'R':spec}),
   dict(id='second',rows=['..SS'],palette={'S':spec})],overlaps=[])
  self.write_mask(data);request=self.request();request.update(source=saved['source'],source_sha256=saved['source_sha256'])
  request['mapping'].update(u_start=0,u_span=.4,connect_raised=dict(max_new_blocks=1));before=Path(saved['source']).read_bytes()
  def surface(sections,y,u):return [u,0],[0,1]
  def faces(model,expected,normal,y,maximum):
   return (((2,2,1),(0,0,1),0) if expected[0]<.1 else ((2,2,3),(1,0,0),0) if expected[0]<.2 else
           ((7,2,1),(0,0,1),0) if expected[0]<.3 else ((7,2,3),(1,0,0),0))
  with patch('nbt_curved_surface._actual_face',side_effect=faces),patch('nbt_curved_surface._surface_point',side_effect=surface):
   with self.assertRaisesRegex(ValueError,'总预算'):plan_curve(self.root,request)
  self.assertFalse((self.root/request['output']).exists());self.assertEqual(Path(saved['source']).read_bytes(),before)
 def test_layered_recess_write_budget_applies_across_all_layers(self):
  working=WorkingModel(self.root,[20,10,16])
  for x in (2,3,4,8,9,10):
   for z in (2,3):working.model.put((x,2,z),'stone')
  saved=working.save_draft(name_zh='分层凹槽预算')
  spec=dict(kind='cut',depth=1,backing=1,role='groove')
  data=dict(schema_version=2,name='凹槽预算',layers=[dict(id='first',rows=['CC..'],palette={'C':spec}),
   dict(id='second',rows=['..DD'],palette={'D':spec})],overlaps=[])
  self.write_mask(data);request=self.request();request.update(source=saved['source'],source_sha256=saved['source_sha256'])
  request['mapping'].update(u_start=0,u_span=.4,connect_recess=dict(max_new_blocks=1));before=Path(saved['source']).read_bytes()
  def surface(sections,y,u):
   x=2 if u<.1 else 4 if u<.2 else 8 if u<.3 else 10
   return [x+.5,2],[0,-1]
  def faces(model,expected,normal,y,maximum):return ((int(expected[0]),2,2),(0,0,-1),0)
  with patch('nbt_curved_surface._actual_face',side_effect=faces),patch('nbt_curved_surface._surface_point',side_effect=surface):
   with self.assertRaisesRegex(ValueError,'总预算'):plan_curve(self.root,request)
  self.assertFalse((self.root/request['output']).exists());self.assertEqual(Path(saved['source']).read_bytes(),before)
 def test_disconnected_subsamples_within_one_pixel_are_reported(self):
  data=json.loads(self.mask.read_text(encoding='utf8'));data['rows']=['R'];data['palette']={'R':data['palette']['R']}
  self.write_mask(data);request=self.request();request['mapping']['u_subsamples']=4
  result=plan_curve(self.root,request)
  self.assertFalse(result['continuity']['passed'])
  self.assertGreater(result['continuity']['fragmented_pixels'],0)
  self.assertTrue(verify_curve(self.root,result['plan'],result['plan_sha256'])['valid'])
 def test_disconnected_diagonal_stroke_is_reported(self):
  data=json.loads(self.mask.read_text(encoding='utf8'));data['rows']=['R.','.R'];data['palette']={'R':data['palette']['R']}
  self.write_mask(data);request=self.request();request['mapping']['u_span']=.9
  result=plan_curve(self.root,request)
  self.assertFalse(result['continuity']['passed'])
  self.assertGreater(result['continuity']['broken_pairs'],0)
 def test_stroke_connected_through_another_mask_cell_is_not_a_break(self):
  from nbt_curved_surface import _continuity
  def sample(u,v,positions):
   return dict(uv=[u,v],symbol='R',changes=[dict(pos=pos,after=['minecraft:stone',False]) for pos in positions])
  samples=[sample(0,0,[[0,0,0]]),sample(1,0,[[2,0,0]]),sample(0,1,[[0,1,0]]),
           sample(1,1,[[1,0,0],[0,1,0]])]
  result=_continuity(samples,['RR','RR'],False)
  self.assertTrue(result['passed'])
  self.assertEqual(result['disconnected_strokes'],0)
 def test_vertically_adjacent_bottom_slabs_do_not_touch(self):
  from nbt_curved_surface import _continuity
  slab='minecraft:stone_brick_slab[type=bottom,waterlogged=false]'
  samples=[dict(uv=[0,y],symbol='R',changes=[dict(pos=[0,y,0],after=[slab,False])]) for y in (0,1)]
  result=_continuity(samples,['R','R'],False)
  self.assertFalse(result['passed']);self.assertEqual(result['disconnected_strokes'],1)
 def test_oversized_sampling_report_fails_before_creating_candidate_directory(self):
  request=self.request()
  with patch('nbt_curved_surface.MAX_MANIFEST',2048):
   with self.assertRaisesRegex(ValueError,'报告过大'):plan_curve(self.root,request)
  self.assertFalse((self.root/request['output']).exists())
 def test_excessive_face_sampling_is_refused_before_search(self):
  data=json.loads(self.mask.read_text(encoding='utf8'));data['rows']=['R'*64]*64;data['palette']={'R':data['palette']['R']}
  self.write_mask(data);request=self.request();request['mapping']['u_subsamples']=3
  with patch('nbt_curved_surface._actual_face') as search:
   with self.assertRaisesRegex(ValueError,'采样.*上限'):plan_curve(self.root,request)
   search.assert_not_called()
  self.assertFalse((self.root/request['output']).exists())
 def test_candidate_can_bind_a_review_observation_and_expires_with_it(self):
  from PIL import Image
  from nbt_task import write_snapshot
  from nbt_review.blind_review import prepare_review,record_review
  def sha(file):return hashlib.sha256(Path(file).read_bytes()).hexdigest()
  def write(file,data):Path(file).write_text(json.dumps(data,ensure_ascii=False),encoding='utf8')
  view=dict(id='front',role='正面',eye=[8,5,-24],target=[8,4,6],up=[0,1,0],fov=60,
            projection='orthographic',ortho_height=16,lighting='day',layer='all',cuts=[])
  camera=self.root/'review-camera.json';write(camera,[view]);manifests=[]
  for index,color in enumerate(('red','blue')):
   folder=self.root/f'review-render-{index}';folder.mkdir();snapshot=folder/'snapshot.json'
   data=write_snapshot(Path(self.source['source']),snapshot);image=folder/'front.png';Image.new('RGB',(64,64),color).save(image)
   meta=dict(id='front',camera={k:view[k] for k in ('eye','target','up','fov','projection','ortho_height')},
    requested_view=view,cuts=[],layer='all',lighting='day',quality='balanced',pixel_ratio=1,width=64,height=64,
    source_sha256=data['source_sha256'],geometry_sha256=data['geometry_sha256'],snapshot_sha256=sha(snapshot),
    image='front.png',image_sha256=sha(image))
   write(folder/'front.json',meta);manifest=folder/'render_manifest.json'
   write(manifest,dict(status='complete',source=self.source['source'],source_sha256=data['source_sha256'],
    geometry_sha256=data['geometry_sha256'],snapshot_file='snapshot.json',snapshot_sha256=sha(snapshot),camera_file=str(camera),
    cameras_sha256=sha(camera),width=64,height=64,quality='balanced',pixel_ratio=1,views=[view],
    images=[dict(image='front.png',metadata='front.json',sha256=sha(image),metadata_sha256=sha(folder/'front.json'))]))
   manifests.append(manifest)
  pack=prepare_review(self.root,dict(renders=[dict(manifest=str(f),sha256=sha(f)) for f in manifests],
   scope='合成审阅',crop=None,output='nbt_models/_workspaces/reference-reviews/curve-review'))
  record=record_review(self.root,dict(public=pack['public'],public_sha256=pack['public_sha256'],decision='inconclusive',actor='agent',
   observations=[dict(view='view-01',note='装饰需要调整',remaining='需要复核',part='侧面')],
   output='nbt_models/_workspaces/reference-reviews/curve-observation.json'))
  request=self.request();request['review_feedback']=dict(binding=pack['binding'],binding_sha256=pack['binding_sha256'],
    record=record['record'],record_sha256=record['record_sha256'],observation=0)
  from nbt_review.blind_review import _pair
  record_file=Path(record['record']);record_bytes=record_file.read_bytes();calls=0
  def mutate_during_binding(*args):
   nonlocal calls
   value=_pair(*args);calls+=1
   if calls==3:record_file.write_bytes(record_bytes+b' ')
   return value
  with patch('nbt_review.blind_review._pair',side_effect=mutate_during_binding):
   with self.assertRaisesRegex(ValueError,'变化|哈希'):plan_curve(self.root,request)
  self.assertFalse((self.root/request['output']).exists());record_file.write_bytes(record_bytes)
  result=plan_curve(self.root,request);self.assertTrue(verify_curve(self.root,result['plan'],result['plan_sha256'])['valid'])
  proof=json.loads(Path(result['plan']).read_text(encoding='utf8'))
  self.assertEqual(proof['review_feedback']['observation'],0);self.assertFalse(result['approval_created'])
  from nbt_snbt import save_snbt
  model,walls=read_master(self.source['source']);alternate=self.root/'nbt_models/standalone/other/v01/master/model.snbt'
  saved=save_snbt(alternate,model,walls);unrelated=dict(request,source=str(alternate),source_sha256=saved['source_sha256'],
   output='nbt_models/_workspaces/curve-samples/unrelated')
  with self.assertRaisesRegex(ValueError,'不属于'):plan_curve(self.root,unrelated)
  self.assertFalse((self.root/unrelated['output']).exists())
  cli_request=dict(request,output='nbt_models/_workspaces/curve-samples/review-cli')
  request_file=self.root/'review-curve-request.json';request_file.write_text(json.dumps(cli_request),encoding='utf8')
  run=subprocess.run(['node',str(ROOT/'scripts/cli.mjs'),'--workspace',str(self.root),'curve','plan','--request',str(request_file),'--compact'],
   capture_output=True,text=True,encoding='utf8',timeout=60)
  self.assertEqual(run.returncode,0,run.stdout+run.stderr);cli_result=json.loads(run.stdout)
  from nbt_exposure import apply
  apply(self.root);facade=self.root/'.agents/skills/nbtcreator-workspace/nbt.py'
  run=subprocess.run([sys.executable,str(facade),'curve','verify','--plan',cli_result['plan'],'--sha256',cli_result['plan_sha256']],
   cwd=self.root,capture_output=True,text=True,encoding='utf8',timeout=60)
  self.assertEqual(run.returncode,0,run.stdout+run.stderr);self.assertTrue(json.loads(run.stdout)['valid'])
  folder=self.root/'review-render-candidate';folder.mkdir();snapshot=folder/'snapshot.json'
  data=write_snapshot(Path(result['candidate']),snapshot);image=folder/'front.png';Image.new('RGB',(64,64),'green').save(image)
  meta=dict(id='front',camera={k:view[k] for k in ('eye','target','up','fov','projection','ortho_height')},requested_view=view,
   cuts=[],layer='all',lighting='day',quality='balanced',pixel_ratio=1,width=64,height=64,source_sha256=data['source_sha256'],
   geometry_sha256=data['geometry_sha256'],snapshot_sha256=sha(snapshot),image='front.png',image_sha256=sha(image))
  write(folder/'front.json',meta);manifest=folder/'render_manifest.json'
  write(manifest,dict(status='complete',source=result['candidate'],source_sha256=data['source_sha256'],geometry_sha256=data['geometry_sha256'],
   snapshot_file='snapshot.json',snapshot_sha256=sha(snapshot),camera_file=str(camera),cameras_sha256=sha(camera),width=64,height=64,
   quality='balanced',pixel_ratio=1,views=[view],images=[dict(image='front.png',metadata='front.json',sha256=sha(image),metadata_sha256=sha(folder/'front.json'))]))
  revised=prepare_review(self.root,dict(renders=[dict(manifest=str(f),sha256=sha(f)) for f in (manifests[0],manifest)],
   scope='复核合成候选',crop=None,output='nbt_models/_workspaces/reference-reviews/curve-revised'))
  revised_record=record_review(self.root,dict(public=revised['public'],public_sha256=revised['public_sha256'],decision='inconclusive',actor='agent',
   observations=[dict(view='view-01',note='仍有断笔',remaining='继续调整')],output='nbt_models/_workspaces/reference-reviews/revised-record.json'))
  from nbt_curved_surface import record_curve_followup,verify_curve_followup
  followup_request=dict(plan=result['plan'],plan_sha256=result['plan_sha256'],status='unresolved',
   remaining='继续调整断笔',review_feedback=dict(binding=revised['binding'],binding_sha256=revised['binding_sha256'],
    record=revised_record['record'],record_sha256=revised_record['record_sha256'],observation=0),
   output='nbt_models/_workspaces/reference-reviews/followup.json')
  invalid=dict(followup_request,remaining='',output='nbt_models/_workspaces/reference-reviews/invalid-followup.json')
  with self.assertRaisesRegex(ValueError,'未解决项'):record_curve_followup(self.root,invalid)
  self.assertFalse((self.root/invalid['output']).exists())
  invalid=dict(followup_request,review_feedback=request['review_feedback'],output='nbt_models/_workspaces/reference-reviews/unrelated-followup.json')
  with self.assertRaisesRegex(ValueError,'不属于'):record_curve_followup(self.root,invalid)
  self.assertFalse((self.root/invalid['output']).exists())
  recropped=prepare_review(self.root,dict(renders=[dict(manifest=str(f),sha256=sha(f)) for f in (manifests[0],manifest)],
   scope='不同裁切的合成候选',crop=[0,0,32,32],output='nbt_models/_workspaces/reference-reviews/curve-recropped'))
  recropped_record=record_review(self.root,dict(public=recropped['public'],public_sha256=recropped['public_sha256'],decision='inconclusive',actor='agent',
   observations=[dict(view='view-01',note='局部不同',remaining='需同范围复核')],output='nbt_models/_workspaces/reference-reviews/recropped-record.json'))
  invalid=dict(followup_request,review_feedback=dict(binding=recropped['binding'],binding_sha256=recropped['binding_sha256'],
   record=recropped_record['record'],record_sha256=recropped_record['record_sha256'],observation=0),
   output='nbt_models/_workspaces/reference-reviews/recropped-followup.json')
  with self.assertRaisesRegex(ValueError,'裁切|相机'):record_curve_followup(self.root,invalid)
  self.assertFalse((self.root/invalid['output']).exists())
  from nbt_curved_surface import _review_feedback
  mask_bytes=self.mask.read_bytes();calls=0
  def mutate_mask_after_initial_verification(*args):
   nonlocal calls
   value=_review_feedback(*args);calls+=1
   if calls==3:self.mask.write_bytes(mask_bytes+b' ')
   return value
  followup=record_curve_followup(self.root,followup_request)
  with patch('nbt_curved_surface._review_feedback',side_effect=mutate_mask_after_initial_verification):
   with self.assertRaisesRegex(ValueError,'哈希|变化'):verify_curve_followup(self.root,followup['record'],followup['record_sha256'])
  self.mask.write_bytes(mask_bytes)
  self.assertTrue(verify_curve_followup(self.root,followup['record'],followup['record_sha256'])['valid'])
  self.assertFalse(followup['approval_created'])
  followup_file=Path(followup['record']);followup_bytes=followup_file.read_bytes();forged=json.loads(followup_bytes)
  forged['approval_created']=True;write(followup_file,forged)
  with self.assertRaisesRegex(ValueError,'记录无效'):verify_curve_followup(self.root,followup_file,sha(followup_file))
  followup_file.write_bytes(followup_bytes)
  cli_request=dict(followup_request,output='nbt_models/_workspaces/reference-reviews/followup-cli.json')
  request_file=self.root/'curve-followup-request.json';write(request_file,cli_request)
  run=subprocess.run(['node',str(ROOT/'scripts/cli.mjs'),'--workspace',str(self.root),'curve','review-record','--request',str(request_file)],
   capture_output=True,text=True,encoding='utf8',timeout=90)
  self.assertEqual(run.returncode,0,run.stdout+run.stderr);cli_followup=json.loads(run.stdout)
  run=subprocess.run([sys.executable,str(facade),'curve','review-verify','--record',cli_followup['record'],'--sha256',cli_followup['record_sha256']],
   cwd=self.root,capture_output=True,text=True,encoding='utf8',timeout=90)
  self.assertEqual(run.returncode,0,run.stdout+run.stderr);self.assertTrue(json.loads(run.stdout)['valid'])
  revised_file=Path(revised_record['record']);revised_bytes=revised_file.read_bytes();revised_file.write_bytes(revised_bytes+b' ')
  with self.assertRaisesRegex(ValueError,'变化|哈希'):verify_curve_followup(self.root,followup['record'],followup['record_sha256'])
  revised_file.write_bytes(revised_bytes)
  Path(record['record']).write_bytes(Path(record['record']).read_bytes()+b' ')
  with self.assertRaisesRegex(ValueError,'变化|哈希'):verify_curve(self.root,result['plan'],result['plan_sha256'])
 def test_candidate_evidence_binds_original_mask_profile_and_preview(self):
  result=plan_curve(self.root,self.request())
  self.assertTrue(verify_curve(self.root,result['plan'],result['plan_sha256'])['valid'])
  candidate=Path(result['candidate']);candidate.write_bytes(candidate.read_bytes()+b' ')
  with self.assertRaisesRegex(ValueError,'哈希|变化'):verify_curve(self.root,result['plan'],result['plan_sha256'])
 def test_rehashed_forged_surface_normal_is_recomputed_and_rejected(self):
  result=plan_curve(self.root,self.request());file=Path(result['plan'])
  proof=json.loads(file.read_text(encoding='utf8'));proof['samples'][0]['host'][0]+=1
  file.write_text(json.dumps(proof),encoding='utf8');forged=hashlib.sha256(file.read_bytes()).hexdigest()
  with self.assertRaisesRegex(ValueError,'采样.*不一致'):verify_curve(self.root,file,forged)
 def test_eccentric_retreat_with_a_corner_samples_each_actual_height(self):
  from nbt_reference_views import load_reference
  original=json.loads(Path(self.fit['output']).read_text(encoding='utf8'))
  reference=self.root/original['reference'];registered=load_reference(reference,original['reference_sha256'])
  rows=[dict(row) for row in self.fixture.rows];rows[1]['corner']=True
  fit=save_fit(self.root,dict(reference=str(reference),reference_sha256=original['reference_sha256'],part='tower',
      rows=rows,sample_step=1,vertices=32),'nbt_models/_workspaces/reference-fits/stepped.json')
  geometry=json.loads(Path(fit['output']).read_text(encoding='utf8'))['geometry']
  working=WorkingModel(self.root,[20,10,16]);working.apply_operations([dict(kind='geometry',label='退台宿主',
      classification='wall',lo=[0,0,0],hi=[19,8,15],state='stone_bricks',geometry=geometry)])
  source=working.save_draft(name_zh='退台宿主')
  data=json.loads(self.mask.read_text(encoding='utf8'));data['rows']=['R.......']*4;data['palette']={'R':data['palette']['R']};self.write_mask(data)
  request=self.request();request.update(source=source['source'],source_sha256=source['source_sha256'],profile=fit['output'],profile_sha256=fit['sha256'],
      output='nbt_models/_workspaces/curve-samples/stepped')
  result=plan_curve(self.root,request)
  self.assertEqual([sample['host'][1] for sample in result['samples']],[2,3,4,5])
  self.assertGreater(len({tuple(sample['host'][i] for i in (0,2)) for sample in result['samples']}),1)
  self.assertTrue(verify_curve(self.root,result['plan'],result['plan_sha256'])['valid'])
 def test_shared_cli_plan_and_frozen_verifier_use_the_same_candidate(self):
  from nbt_exposure import apply
  request=self.root/'curve-request.json';request.write_text(json.dumps(self.request()),encoding='utf8')
  command=['node',str(ROOT/'scripts/cli.mjs'),'--workspace',str(self.root),'curve','plan','--request',str(request),'--compact']
  run=subprocess.run(command,capture_output=True,text=True,encoding='utf8',timeout=60)
  self.assertEqual(run.returncode,0,run.stdout+run.stderr);result=json.loads(run.stdout)
  self.assertNotIn('samples',result);self.assertEqual(result['summary']['pixels'],3)
  apply(self.root);facade=self.root/'.agents/skills/nbtcreator-workspace/nbt.py'
  run=subprocess.run([sys.executable,str(facade),'curve','verify','--plan',result['plan'],'--sha256',result['plan_sha256']],
      cwd=self.root,capture_output=True,text=True,encoding='utf8',timeout=60)
  self.assertEqual(run.returncode,0,run.stdout+run.stderr);self.assertTrue(json.loads(run.stdout)['valid'])


class CurvedConnectors(unittest.TestCase):
 def setUp(self):
  temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name)
  self.working=WorkingModel(self.root,[8,6,8]);self.spec=dict(kind='raise',state='minecraft:stone_bricks',height=1,wall=False,role='rim')
  self.p=(2,2,2);self.q=(3,2,3);self.hosts=[(2,2,1),(2,2,3)]
  for pos in self.hosts:self.working.model.put(pos,'stone')
  self.changes={};self.owners={};self.samples=[]
  for uv,pos,host,face in [([0,0],self.p,self.hosts[0],(0,0,1)),([1,0],self.q,self.hosts[1],(1,0,0))]:
   change=dict(pos=list(pos),before=['minecraft:air',False],after=['minecraft:stone_bricks',False]);self.changes[pos]=change;self.owners[pos]='R'
   self.samples.append(dict(uv=uv,symbol='R',kind='raise',faces=[dict(host=list(host),face_normal=list(face))],
                            changes=[change],effective_writes=1))
  self.mask=dict(rows=['RR'],palette={'R':self.spec});self.supports=list(self.hosts)
 def connect(self,protected=None,limit=4,steps=1,choices=None):
  from nbt_mounting.curved_connect import connect_raised
  return connect_raised(self.working,self.mask,self.samples,self.changes,self.owners,protected or set(),self.supports,limit,False,steps,choices)
 def test_unique_corner_bridge_is_supported_by_actual_endpoints(self):
  before=dict(self.working.model.blocks);result=self.connect()
  self.assertEqual([item['pos'] for item in result],[[3,2,2]])
  self.assertEqual({tuple(x) for x in result[0]['endpoint_hosts']},set(self.hosts))
  self.assertEqual(self.working.model.blocks,before)
  self.assertEqual(self.changes[(3,2,2)]['after'],['minecraft:stone_bricks',False])
 def test_explicit_two_block_bridge_has_a_bounded_unique_path(self):
  self.working=WorkingModel(self.root,[8,6,8]);self.changes={};self.owners={};self.samples=[];self.supports=[]
  for index,x in enumerate((2,5)):
   pos=(x,2,2);host=(x,2,1);self.working.model.put(host,'stone');self.supports.append(host)
   change=dict(pos=list(pos),before=['minecraft:air',False],after=['minecraft:stone_bricks',False])
   self.changes[pos]=change;self.owners[pos]='R';self.samples.append(dict(uv=[index,0],symbol='R',kind='raise',
    faces=[dict(host=list(host),face_normal=[0,0,1])],changes=[change],effective_writes=1))
  before=dict(self.changes)
  with self.assertRaisesRegex(ValueError,'无法连接'):self.connect(steps=1)
  self.assertEqual(self.changes,before)
  with self.assertRaisesRegex(ValueError,'预算'):self.connect(limit=1,steps=2)
  self.assertEqual(self.changes,before)
  result=self.connect(limit=2,steps=2)
  self.assertEqual([item['pos'] for item in result],[[3,2,2],[4,2,2]])
  self.assertTrue(all(item['path']==[[3,2,2],[4,2,2]] for item in result))
 def test_multi_block_path_does_not_cross_a_protected_cell(self):
  from nbt_working_model import ModelConflict
  self.working=WorkingModel(self.root,[8,6,8]);self.changes={};self.owners={};self.samples=[];self.supports=[]
  for index,x in enumerate((2,5)):
   pos=(x,2,2);host=(x,2,1);self.working.model.put(host,'stone');self.supports.append(host)
   change=dict(pos=list(pos),before=['minecraft:air',False],after=['minecraft:stone_bricks',False])
   self.changes[pos]=change;self.owners[pos]='R';self.samples.append(dict(uv=[index,0],symbol='R',kind='raise',
    faces=[dict(host=list(host),face_normal=[0,0,1])],changes=[change],effective_writes=1))
  before=dict(self.changes)
  with self.assertRaisesRegex(ModelConflict,'CURVE_PROTECTED'):self.connect({(4,2,2)},limit=2,steps=2)
  self.assertEqual(self.changes,before);self.assertTrue(all('connectors' not in sample for sample in self.samples))
 def test_three_intermediate_cells_are_the_explicit_upper_bound(self):
  self.working=WorkingModel(self.root,[8,6,8]);self.changes={};self.owners={};self.samples=[];self.supports=[]
  for index,x in enumerate((2,6)):
   pos=(x,2,2);host=(x,2,1);self.working.model.put(host,'stone');self.supports.append(host)
   change=dict(pos=list(pos),before=['minecraft:air',False],after=['minecraft:stone_bricks',False])
   self.changes[pos]=change;self.owners[pos]='R';self.samples.append(dict(uv=[index,0],symbol='R',kind='raise',
    faces=[dict(host=list(host),face_normal=[0,0,1])],changes=[change],effective_writes=1))
  result=self.connect(limit=3,steps=3)
  self.assertEqual([item['pos'] for item in result],[[3,2,2],[4,2,2],[5,2,2]])
 def test_multiple_shortest_bridge_paths_are_not_guessed(self):
  self.working=WorkingModel(self.root,[8,6,8]);self.changes={};self.owners={};self.samples=[];self.supports=[]
  for index,pos in enumerate(((2,2,2),(4,3,2))):
   host=(pos[0],pos[1],pos[2]-1);self.working.model.put(host,'stone');self.supports.append(host)
   change=dict(pos=list(pos),before=['minecraft:air',False],after=['minecraft:stone_bricks',False])
   self.changes[pos]=change;self.owners[pos]='R';self.samples.append(dict(uv=[index,0],symbol='R',kind='raise',
    faces=[dict(host=list(host),face_normal=[0,0,1])],changes=[change],effective_writes=1))
  before=dict(self.changes)
  from nbt_working_model import ModelConflict
  with self.assertRaisesRegex(ModelConflict,'歧义') as error:self.connect(limit=2,steps=2)
  self.assertEqual(error.exception.code,'CURVE_CONNECT_AMBIGUOUS')
  self.assertEqual(len(error.exception.conflicts[0]['paths']),3)
  self.assertEqual(self.changes,before)
 def test_explicit_ambiguous_path_is_checked_and_bound(self):
  self.working=WorkingModel(self.root,[8,6,8]);self.changes={};self.owners={};self.samples=[];self.supports=[]
  for index,pos in enumerate(((2,2,2),(4,3,2))):
   host=(pos[0],pos[1],pos[2]-1);self.working.model.put(host,'stone');self.supports.append(host)
   change=dict(pos=list(pos),before=['minecraft:air',False],after=['minecraft:stone_bricks',False])
   self.changes[pos]=change;self.owners[pos]='R';self.samples.append(dict(uv=[index,0],symbol='R',kind='raise',
    faces=[dict(host=list(host),face_normal=[0,0,1])],changes=[change],effective_writes=1))
  before=dict(self.changes);endpoints=[[2,2,2],[4,3,2]]
  invalid=[dict(endpoints=endpoints,path=[[3,2,2],[2,3,2]])]
  with self.assertRaisesRegex(ValueError,'指定.*路径|路径.*无效'):self.connect(limit=2,steps=2,choices=invalid)
  self.assertEqual(self.changes,before)
  choice=[dict(endpoints=endpoints,path=[[3,2,2],[4,2,2]])]
  from nbt_working_model import ModelConflict
  with self.assertRaisesRegex(ModelConflict,'CURVE_PROTECTED'):self.connect({(4,2,2)},limit=2,steps=2,choices=choice)
  with self.assertRaisesRegex(ValueError,'预算'):self.connect(limit=1,steps=2,choices=choice)
  self.assertEqual(self.changes,before)
  result=self.connect(limit=2,steps=2,choices=choice)
  self.assertEqual([item['pos'] for item in result],choice[0]['path'])
  self.assertTrue(all(item['selection']=='explicit' for item in result))
 def test_unused_explicit_path_is_rejected_without_partial_writes(self):
  choice=[dict(endpoints=[[0,0,0],[2,0,0]],path=[[1,0,0]])];before=dict(self.changes)
  with self.assertRaisesRegex(ValueError,'未使用|过期'):self.connect(limit=4,steps=1,choices=choice)
  self.assertEqual(self.changes,before);self.assertTrue(all('connectors' not in sample for sample in self.samples))
 def test_duplicate_or_out_of_bounds_explicit_path_is_rejected(self):
  repeated=[dict(endpoints=[[2,2,2],[3,2,3]],path=[[3,2,2]]),
            dict(endpoints=[[3,2,3],[2,2,2]],path=[[3,2,2]])]
  with self.assertRaisesRegex(ValueError,'重复'):self.connect(choices=repeated)
  invalid=[dict(endpoints=[[2,2,2],[3,2,3]],path=[[8,2,2]])]
  with self.assertRaisesRegex(ValueError,'坐标'):self.connect(choices=invalid)
 def test_unique_shortest_bridge_reuses_a_sampled_block_in_the_same_stroke(self):
  self.working=WorkingModel(self.root,[8,6,8]);self.changes={};self.owners={};self.samples=[];self.supports=[]
  rows=[([0,0],[(2,2,2)]),([1,0],[(4,3,2),(4,2,2)])]
  for uv,positions in rows:
   faces=[];edits=[]
   for pos in positions:
    host=(pos[0],pos[1],pos[2]-1);self.working.model.put(host,'stone');self.supports.append(host)
    change=dict(pos=list(pos),before=['minecraft:air',False],after=['minecraft:stone_bricks',False])
    self.changes[pos]=change;self.owners[pos]='R';edits.append(change);faces.append(dict(host=list(host),face_normal=[0,0,1]))
   self.samples.append(dict(uv=uv,symbol='R',kind='raise',faces=faces,changes=edits,effective_writes=len(edits)))
  result=self.connect(limit=1,steps=2)
  self.assertEqual([item['pos'] for item in result],[[3,2,2]])
  self.assertEqual(result[0]['reused'],[[4,2,2]])
 def test_ambiguous_or_protected_bridges_refuse_without_partial_changes(self):
  from nbt_working_model import ModelConflict
  before=dict(self.changes)
  with self.assertRaisesRegex(ModelConflict,'CURVE_PROTECTED'):self.connect({(3,2,2)})
  self.assertEqual(self.changes,before);self.assertEqual(len(self.samples[0]['changes']),1)
  self.working.model.put(self.hosts[1],'air');self.hosts[1]=(3,2,4);self.working.model.put(self.hosts[1],'stone')
  self.samples[1]['faces'][0].update(host=list(self.hosts[1]),face_normal=[0,0,-1]);self.supports=list(self.hosts)
  with self.assertRaisesRegex(ValueError,'歧义'):self.connect()
  self.assertEqual(self.changes,before)
 def test_bridging_budget_and_existing_other_write_are_enforced(self):
  from nbt_working_model import ModelConflict
  with self.assertRaisesRegex(ValueError,'预算'):self.connect(limit=0)
  bridge=(3,2,2);self.changes[bridge]=dict(pos=list(bridge),before=['minecraft:air',False],after=['minecraft:gold_block',False]);self.owners[bridge]='I'
  with self.assertRaisesRegex(ModelConflict,'CURVE_OVERLAP'):self.connect()
  self.assertEqual(self.changes[bridge]['after'],['minecraft:gold_block',False])
 def test_multi_layer_raise_is_not_silently_treated_as_single_layer(self):
  self.spec['height']=2
  old=self.changes.pop(self.q);self.owners.pop(self.q);self.q=(3,2,2);old['pos']=list(self.q)
  self.changes[self.q]=old;self.owners[self.q]='R';self.working.model.put((4,2,2),'stone')
  self.samples[1]['faces'][0].update(host=[4,2,2],face_normal=[-1,0,0])
  with self.assertRaisesRegex(ValueError,'仅支持单层'):self.connect()
  self.assertEqual(len(self.changes),2)
 def test_half_slab_bridge_cannot_claim_contact_through_air_gap(self):
  slab='minecraft:stone_brick_slab[type=bottom,waterlogged=false]';self.spec['state']=slab
  self.q=(3,3,2);self.hosts[1]=(2,3,2);self.working.model.put(self.hosts[1],'stone')
  old=self.changes.pop((3,2,3));self.owners.pop((3,2,3));old['pos']=list(self.q);old['after'][0]=slab
  self.changes[self.q]=old;self.owners[self.q]='R';self.samples[1]['faces'][0].update(host=list(self.hosts[1]),face_normal=[1,0,0])
  self.changes[self.p]['after'][0]=slab
  with self.assertRaisesRegex(ValueError,'无法连接'):self.connect()
  self.assertEqual(len(self.changes),2)
 def test_connector_cannot_merge_distinct_mask_strokes(self):
  pos=(3,3,2);host=(4,3,2);self.working.model.put(host,'stone')
  change=dict(pos=list(pos),before=['minecraft:air',False],after=['minecraft:stone_bricks',False])
  self.changes[pos]=change;self.owners[pos]='R';self.samples.append(dict(uv=[3,0],symbol='R',kind='raise',
   faces=[dict(host=list(host),face_normal=[-1,0,0])],changes=[change],effective_writes=1))
  self.mask['rows']=['RR.R'];before=dict(self.changes)
  with self.assertRaisesRegex(ValueError,'不同.*笔画'):self.connect()
  self.assertEqual(self.changes,before)
 def test_later_protected_stroke_does_not_leave_an_earlier_connector(self):
  from nbt_working_model import ModelConflict
  self.mask['rows']=['RR.RR']
  for uv,pos,host,face in [([3,0],(5,3,4),(5,3,3),(0,0,1)),([4,0],(6,3,5),(5,3,5),(1,0,0))]:
   self.working.model.put(host,'stone');change=dict(pos=list(pos),before=['minecraft:air',False],after=['minecraft:stone_bricks',False])
   self.changes[pos]=change;self.owners[pos]='R';self.supports.append(host)
   self.samples.append(dict(uv=uv,symbol='R',kind='raise',faces=[dict(host=list(host),face_normal=list(face))],changes=[change],effective_writes=1))
  before=dict(self.changes);supports=list(self.supports)
  with self.assertRaisesRegex(ModelConflict,'CURVE_PROTECTED'):self.connect({(6,3,4)})
  self.assertEqual(self.changes,before);self.assertEqual(self.supports,supports)
  self.assertTrue(all('connectors' not in sample for sample in self.samples))
 def test_connector_cannot_destroy_a_mask_hole(self):
  self.working=WorkingModel(self.root,[16,6,8]);self.changes={};self.owners={};self.samples=[];self.supports=[]
  self.mask['rows']=['RRR','R.R','RRR']
  order=[(0,0),(1,0),(2,0),(2,1),(2,2),(1,2),(0,2),(0,1)]
  for index,uv in enumerate(order):
   x=2 if index==0 else index+3;pos=(x,2,2);host=(x,2,1);self.working.model.put(host,'stone')
   change=dict(pos=list(pos),before=['minecraft:air',False],after=['minecraft:stone_bricks',False])
   self.changes[pos]=change;self.owners[pos]='R';self.supports.append(host)
   self.samples.append(dict(uv=list(uv),symbol='R',kind='raise',faces=[dict(host=list(host),face_normal=[0,0,1])],
                            changes=[change],effective_writes=1))
  before=dict(self.changes)
  with self.assertRaisesRegex(ValueError,'孔洞|空腔'):self.connect()
  self.assertEqual(self.changes,before)


class CurvedRecessConnectors(unittest.TestCase):
 def setUp(self):
  temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name)
  self.working=WorkingModel(self.root,[8,7,8]);self.spec=dict(kind='cut',depth=1,backing=1,role='groove')
  self.hosts=[(2,2,2),(4,2,2)];self.normal=(0,0,-1);self.middle=(3,2,2)
  for x in (2,3,4):
   for z in (2,3,4):self.working.model.put((x,2,z),'stone')
  self.samples=[];self.changes={};self.owners={};self.supports=[];self.mask=dict(rows=['CC'],palette={'C':self.spec})
  self.rebuild_endpoints()
 def rebuild_endpoints(self):
  self.samples=[];self.changes={};self.owners={};self.supports=[]
  for index,host in enumerate(self.hosts):
   edits=[]
   for depth in range(self.spec['depth']+self.spec['backing']):
    pos=tuple(host[i]-self.normal[i]*depth for i in range(3))
    if depth>=self.spec['depth']:self.supports.append(pos);continue
    value=[self.spec['state'],self.spec['wall']] if self.spec['kind']=='inlay' and depth==self.spec['depth']-1 else ['minecraft:air',False]
    change=dict(pos=list(pos),before=['minecraft:stone',False],after=value)
    edits.append(change);self.changes[pos]=change;self.owners[pos]='C'
   self.samples.append(dict(uv=[index,0],symbol='C',kind=self.spec['kind'],
    faces=[dict(host=list(host),face_normal=list(self.normal),expected_xz=[host[0]+.5,host[2]],analytic_normal_xz=[0,-1])],
    changes=edits,effective_writes=len(edits)))
 def connect(self,protected=None,limit=8):
  from nbt_mounting.curved_recess import connect_recesses
  return connect_recesses(self.working,self.mask,self.samples,self.changes,self.owners,protected or set(),self.supports,limit,False)
 def test_cut_bridge_checks_actual_face_and_preserves_backing(self):
  before=dict(self.working.model.blocks);result=self.connect()
  self.assertEqual(result[0]['pos'],list(self.middle));self.assertEqual(result[0]['face_normal'],list(self.normal))
  self.assertEqual(result[0]['backing'],[[3,2,3]])
  self.assertEqual(self.changes[self.middle]['after'],['minecraft:air',False])
  self.assertEqual(self.working.model.get((3,2,3)),'minecraft:stone');self.assertEqual(self.working.model.blocks,before)
 def test_depth_two_inlay_bridges_air_and_material_without_cutting_backing(self):
  self.spec.update(kind='inlay',depth=2,state='minecraft:gold_block',wall=True);self.rebuild_endpoints()
  result=self.connect();self.assertEqual(result[0]['backing'],[[3,2,4]])
  self.assertEqual(self.changes[(3,2,2)]['after'],['minecraft:air',False])
  self.assertEqual(self.changes[(3,2,3)]['after'],['minecraft:gold_block',True])
  self.assertNotIn((3,2,4),self.changes)
 def test_recess_budget_protection_and_insufficient_backing_are_atomic(self):
  from nbt_working_model import ModelConflict
  self.spec.update(kind='inlay',depth=2,state='minecraft:gold_block',wall=True);self.rebuild_endpoints();before=dict(self.changes)
  with self.assertRaisesRegex(ValueError,'预算'):self.connect(limit=1)
  with self.assertRaisesRegex(ModelConflict,'CURVE_PROTECTED'):self.connect({(3,2,3)})
  self.working.model.put((3,2,4),'air')
  with self.assertRaisesRegex(ValueError,'背衬|厚度'):self.connect()
  self.assertEqual(self.changes,before);self.assertTrue(all('connectors' not in sample for sample in self.samples))
 def test_recess_does_not_carve_an_existing_support(self):
  from nbt_working_model import ModelConflict
  self.supports.append(self.middle);before=dict(self.changes)
  with self.assertRaisesRegex(ModelConflict,'CURVE_BACKING_CONFLICT'):self.connect()
  self.assertEqual(self.changes,before)
 def test_recess_failure_in_later_stroke_leaves_all_edits_unchanged(self):
  from nbt_working_model import ModelConflict
  self.mask['rows']=['CC.CC']
  for x in (2,3,4):
   for z in (2,3):self.working.model.put((x,4,z),'stone')
  for index,x in ((3,2),(4,4)):
   host=(x,4,2);backing=(x,4,3);change=dict(pos=list(host),before=['minecraft:stone',False],after=['minecraft:air',False])
   self.changes[host]=change;self.owners[host]='C';self.supports.append(backing)
   self.samples.append(dict(uv=[index,0],symbol='C',kind='cut',faces=[dict(host=list(host),face_normal=[0,0,-1],
    expected_xz=[x+.5,2],analytic_normal_xz=[0,-1])],changes=[change],effective_writes=1))
  before=dict(self.changes);supports=list(self.supports)
  with self.assertRaisesRegex(ModelConflict,'CURVE_PROTECTED'):self.connect({(3,4,2)})
  self.assertEqual(self.changes,before);self.assertEqual(self.supports,supports)
  self.assertTrue(all('connectors' not in sample for sample in self.samples))
 def test_recess_rejects_a_host_face_opposite_to_the_fitted_normal(self):
  self.samples[1]['faces'][0]['analytic_normal_xz']=[0,1];before=dict(self.changes)
  with self.assertRaisesRegex(ValueError,'法向'):self.connect()
  self.assertEqual(self.changes,before)
 def test_ambiguous_recess_faces_are_not_guessed(self):
  self.hosts=[(2,2,2),(3,3,2)]
  for y in (2,3):
   for x in (2,3):
    for z in (2,3):self.working.model.put((x,y,z),'stone')
  self.rebuild_endpoints();before=dict(self.changes)
  with self.assertRaisesRegex(ValueError,'歧义'):self.connect()
  self.assertEqual(self.changes,before)
 def test_inlay_material_must_connect_separately_from_void(self):
  self.spec.update(kind='inlay',depth=1,state='minecraft:stone_brick_slab[type=bottom,waterlogged=false]',wall=True)
  self.hosts=[(2,2,2),(2,4,2)]
  for y in (2,3,4):
   for z in (2,3):self.working.model.put((2,y,z),'stone')
  self.rebuild_endpoints();before=dict(self.changes)
  with self.assertRaisesRegex(ValueError,'无法连接'):self.connect()
  self.assertEqual(self.changes,before)
 def test_connected_void_does_not_hide_disconnected_inlay_material(self):
  self.spec.update(kind='inlay',depth=1,state='minecraft:stone_brick_slab[type=bottom,waterlogged=false]',wall=True)
  self.hosts=[(2,2,2),(2,3,2)]
  for y in (2,3):
   for z in (2,3):self.working.model.put((2,y,z),'stone')
  self.rebuild_endpoints();before=dict(self.changes)
  with self.assertRaisesRegex(ValueError,'无法连接'):self.connect()
  self.assertEqual(self.changes,before)
 def test_disconnected_recess_reports_real_endpoints_and_material_gap(self):
  from nbt_working_model import ModelConflict
  self.spec.update(kind='inlay',depth=1,state='minecraft:stone_brick_slab[type=bottom,waterlogged=false]',wall=True)
  self.hosts=[(2,2,2),(2,3,2)]
  for y in (2,3):
   for z in (2,3):self.working.model.put((2,y,z),'stone')
  self.rebuild_endpoints();before=dict(self.changes);supports=list(self.supports)
  with self.assertRaises(ModelConflict) as raised:self.connect()
  self.assertEqual(raised.exception.code,'CURVE_RECESS_DISCONNECTED')
  detail=raised.exception.conflicts[0]
  self.assertEqual(detail['cut_components'],1);self.assertEqual(detail['material_components'],2)
  self.assertEqual(detail['endpoints'][0]['from_uv'],[0,0]);self.assertEqual(detail['endpoints'][0]['to_uv'],[1,0])
  self.assertEqual(detail['endpoints'][0]['hosts'],[[2,2,2],[2,3,2]])
  self.assertTrue(detail['endpoints'][0]['cut_connected']);self.assertFalse(detail['endpoints'][0]['material_connected'])
  self.assertEqual(self.changes,before);self.assertEqual(self.supports,supports)
 def test_disconnected_recess_details_are_bounded_and_distinguish_plain_cut(self):
  from nbt_mounting.curved_recess import _disconnected_endpoints
  edges=[];cut_index={}
  for x in range(20):
   a=(x*4,0,0);b=(x*4+2,0,0);cut_index[a]=x*2;cut_index[b]=x*2+1
   left=dict(host=a,normal=(0,0,1),cut={a});right=dict(host=b,normal=(0,0,1),cut={b})
   edges.append(((x,0),(x+1,0),left,right))
  details,truncated=_disconnected_endpoints(list(reversed(edges)),cut_index,{},False)
  self.assertTrue(truncated);self.assertEqual(len(details),16)
  self.assertEqual(details[0]['from_uv'],[0,0]);self.assertIsNone(details[0]['material_connected'])


class ActualEccentricConnectors(unittest.TestCase):
 def test_shared_cli_and_frozen_verifier_bind_real_curved_host(self):
  sys.path.insert(0,str(ROOT/'tests/support'))
  from curved_surface_fixture import create_curve_fixture
  from nbt_exposure import apply
  with tempfile.TemporaryDirectory() as temp:
   workspace=Path(temp);request=create_curve_fixture(workspace);original=Path(request['source']).read_bytes()
   file=workspace/'curve-request.json';file.write_text(json.dumps(request,ensure_ascii=False),encoding='utf8')
   run=subprocess.run(['node',str(ROOT/'scripts/cli.mjs'),'--workspace',str(workspace),'curve','plan','--request',str(file),'--compact'],
    cwd=ROOT,capture_output=True,text=True,encoding='utf8',timeout=90)
   self.assertEqual(run.returncode,0,run.stdout+run.stderr);result=json.loads(run.stdout)
   self.assertGreater(result['summary']['connectors_added'],0)
   self.assertFalse(result['continuity']['passed'])
   self.assertEqual({item['symbol'] for item in result['continuity']['stroke_details']},{'C','W'})
   self.assertFalse(result['approval_created']);self.assertFalse(result['nbt_exported'])
   self.assertEqual(Path(request['source']).read_bytes(),original)
   proof=json.loads(Path(result['plan']).read_text(encoding='utf8'))
   connectors=[connector for sample in proof['samples'] for connector in sample.get('connectors',[])]
   self.assertEqual(len(connectors),result['summary']['connectors_added'])
   self.assertTrue(all(len(connector['endpoint_hosts'])==2 for connector in connectors))
   apply(workspace);facade=workspace/'.agents/skills/nbtcreator-workspace/nbt.py'
   run=subprocess.run([sys.executable,str(facade),'curve','verify','--plan',result['plan'],'--sha256',result['plan_sha256']],
    cwd=workspace,capture_output=True,text=True,encoding='utf8',timeout=90)
   self.assertEqual(run.returncode,0,run.stdout+run.stderr);self.assertTrue(json.loads(run.stdout)['valid'])
 def test_real_eccentric_surface_can_use_unique_two_block_bridge(self):
  sys.path.insert(0,str(ROOT/'tests/support'))
  from curved_surface_fixture import create_curve_fixture
  from nbt_exposure import apply
  with tempfile.TemporaryDirectory() as temp:
   workspace=Path(temp);request=create_curve_fixture(workspace);original=Path(request['source']).read_bytes()
   mask=Path(request['mask']);data=json.loads(mask.read_text(encoding='utf8'));data['rows']=['..RR....']
   data['palette']={'R':dict(kind='raise',state='gold_block',height=1,wall=True,role='band')}
   mask.write_text(json.dumps(data),encoding='utf8')
   request.update(mask_sha256=hashlib.sha256(mask.read_bytes()).hexdigest(),
    mapping=dict(u_start=0,u_span=.125,y_start=5,max_distance=2,u_subsamples=1,connect_raised=dict(max_new_blocks=6)),
    output='nbt_models/_workspaces/curve-samples/multistep-real')
   with self.assertRaisesRegex(ValueError,'无法连接'):plan_curve(workspace,request)
   self.assertFalse((workspace/request['output']).exists())
   request['mapping']['connect_raised']['max_bridge_steps']=3
   file=workspace/'multistep-request.json';file.write_text(json.dumps(request),encoding='utf8')
   run=subprocess.run(['node',str(ROOT/'scripts/cli.mjs'),'--workspace',str(workspace),'curve','plan','--request',str(file),'--compact'],
    cwd=ROOT,capture_output=True,text=True,encoding='utf8',timeout=90)
   self.assertEqual(run.returncode,0,run.stdout+run.stderr);result=json.loads(run.stdout)
   self.assertTrue(result['continuity']['passed']);self.assertEqual(result['summary']['connectors_added'],2)
   self.assertEqual(Path(request['source']).read_bytes(),original);apply(workspace)
   facade=workspace/'.agents/skills/nbtcreator-workspace/nbt.py'
   run=subprocess.run([sys.executable,str(facade),'curve','verify','--plan',result['plan'],'--sha256',result['plan_sha256']],
    cwd=workspace,capture_output=True,text=True,encoding='utf8',timeout=90)
   self.assertEqual(run.returncode,0,run.stdout+run.stderr);self.assertTrue(json.loads(run.stdout)['valid'])
 def test_real_surface_cut_and_inlay_connectors_use_actual_backing(self):
  sys.path.insert(0,str(ROOT/'tests/support'))
  from curved_surface_fixture import create_curve_fixture
  from nbt_exposure import apply
  with tempfile.TemporaryDirectory() as temp:
   workspace=Path(temp);base=create_curve_fixture(workspace)
   original=Path(base['source']).read_bytes();palette=json.loads(Path(base['mask']).read_text(encoding='utf8'))['palette'];results=[]
   for symbol,kind in (('C','cut'),('W','inlay')):
    row='.'*6+symbol+'.'*25;mask=workspace/'inputs'/(kind+'.json')
    mask.write_text(json.dumps(dict(schema_version=1,name='合成连接',rows=[row,row],palette={symbol:palette[symbol]})),encoding='utf8')
    request=dict(base,mask=str(mask),mask_sha256=hashlib.sha256(mask.read_bytes()).hexdigest(),
     mapping=dict(u_start=0,u_span=.25,y_start=1,max_distance=2,u_subsamples=2,connect_recess=dict(max_new_blocks=8)),
     output='nbt_models/_workspaces/curve-samples/'+kind)
    file=workspace/(kind+'-request.json');file.write_text(json.dumps(request),encoding='utf8')
    run=subprocess.run(['node',str(ROOT/'scripts/cli.mjs'),'--workspace',str(workspace),'curve','plan','--request',str(file),'--compact'],
     cwd=ROOT,capture_output=True,text=True,encoding='utf8',timeout=90)
    self.assertEqual(run.returncode,0,run.stdout+run.stderr);result=json.loads(run.stdout)
    self.assertTrue(result['continuity']['passed']);self.assertEqual(result['summary']['recess_connectors_added'],1)
    proof=json.loads(Path(result['plan']).read_text(encoding='utf8'))
    connector=next(item for sample in proof['samples'] for item in sample.get('connectors',[]))
    self.assertEqual(connector['kind'],kind);self.assertGreaterEqual(len(connector['backing']),1)
    self.assertFalse(result['approval_created']);self.assertFalse(result['nbt_exported']);results.append(result)
   self.assertEqual(Path(base['source']).read_bytes(),original);apply(workspace)
   facade=workspace/'.agents/skills/nbtcreator-workspace/nbt.py'
   for result in results:
    run=subprocess.run([sys.executable,str(facade),'curve','verify','--plan',result['plan'],'--sha256',result['plan_sha256']],
     cwd=workspace,capture_output=True,text=True,encoding='utf8',timeout=90)
    self.assertEqual(run.returncode,0,run.stdout+run.stderr);self.assertTrue(json.loads(run.stdout)['valid'])
 def test_mixed_real_surface_replays_raised_and_recess_connections_together(self):
  sys.path.insert(0,str(ROOT/'tests/support'))
  from curved_surface_fixture import create_curve_fixture
  from nbt_exposure import apply
  with tempfile.TemporaryDirectory() as temp:
   workspace=Path(temp);request=create_curve_fixture(workspace)
   mask=Path(request['mask']);data=json.loads(mask.read_text(encoding='utf8'));rows=[]
   for y,row in enumerate(data['rows']):
    row=list(row);row[10]='C' if y in (2,3) else '.';row[16]='.';row[19]='W' if y in (4,5) else '.'
    rows.append(''.join(row))
   data['rows']=rows;mask.write_text(json.dumps(data,ensure_ascii=False),encoding='utf8')
   request['mask_sha256']=hashlib.sha256(mask.read_bytes()).hexdigest()
   request['mapping']['connect_recess']=dict(max_new_blocks=64)
   original=Path(request['source']).read_bytes();file=workspace/'combined-request.json';file.write_text(json.dumps(request),encoding='utf8')
   run=subprocess.run(['node',str(ROOT/'scripts/cli.mjs'),'--workspace',str(workspace),'curve','plan','--request',str(file),'--compact'],
    cwd=ROOT,capture_output=True,text=True,encoding='utf8',timeout=90)
   self.assertEqual(run.returncode,0,run.stdout+run.stderr);result=json.loads(run.stdout)
   self.assertTrue(result['continuity']['passed']);self.assertGreater(result['summary']['recess_connectors_added'],0)
   self.assertGreater(result['summary']['connectors_added'],result['summary']['recess_connectors_added'])
   self.assertGreater(result['summary']['truncated'],0) # A connected sample is not automatically a good design.
   self.assertEqual(Path(request['source']).read_bytes(),original);self.assertFalse(result['approval_created'])
   apply(workspace);facade=workspace/'.agents/skills/nbtcreator-workspace/nbt.py'
   run=subprocess.run([sys.executable,str(facade),'curve','verify','--plan',result['plan'],'--sha256',result['plan_sha256']],
    cwd=workspace,capture_output=True,text=True,encoding='utf8',timeout=90)
   self.assertEqual(run.returncode,0,run.stdout+run.stderr);self.assertTrue(json.loads(run.stdout)['valid'])
 def test_unsafe_mixed_repair_leaves_no_partial_candidate(self):
  sys.path.insert(0,str(ROOT/'tests/support'))
  from curved_surface_fixture import create_curve_fixture
  from nbt_exposure import apply
  from nbt_working_model import ModelConflict
  with tempfile.TemporaryDirectory() as temp:
   workspace=Path(temp);request=create_curve_fixture(workspace);original=Path(request['source']).read_bytes()
   request['mapping']['connect_recess']=dict(max_new_blocks=64)
   with self.assertRaises(ModelConflict) as raised:plan_curve(workspace,request)
   self.assertEqual(raised.exception.code,'CURVE_RECESS_DISCONNECTED')
   self.assertIsNone(raised.exception.conflicts[0]['material_components'])
   self.assertTrue(raised.exception.conflicts[0]['endpoints'])
   file=workspace/'disconnected-request.json';file.write_text(json.dumps(request),encoding='utf8')
   apply(workspace);facade=workspace/'.agents/skills/nbtcreator-workspace/nbt.py'
   commands=[['node',str(ROOT/'scripts/cli.mjs'),'--workspace',str(workspace),'curve','plan','--request',str(file),'--compact'],
             [sys.executable,str(facade),'curve','plan','--request',str(file),'--compact']]
   for command in commands:
    run=subprocess.run(command,cwd=workspace,capture_output=True,text=True,encoding='utf8',timeout=90)
    self.assertNotEqual(run.returncode,0);error=json.loads(run.stdout)
    self.assertEqual(error['code'],'CURVE_RECESS_DISCONNECTED');self.assertTrue(error['conflicts'][0]['endpoints'])
   self.assertFalse((workspace/request['output']).exists());self.assertEqual(Path(request['source']).read_bytes(),original)
 def test_real_surface_effective_depth_is_explicit_and_frozen_replayable(self):
  sys.path.insert(0,str(ROOT/'tests/support'))
  from curved_surface_fixture import create_curve_fixture
  from nbt_exposure import apply
  with tempfile.TemporaryDirectory() as temp:
   workspace=Path(temp);request=create_curve_fixture(workspace);original=Path(request['source']).read_bytes()
   mask=Path(request['mask']);data=json.loads(mask.read_text(encoding='utf8'));row='....W' + '.'*27
   data['rows']=[row,row];data['palette']={'W':data['palette']['W']};mask.write_text(json.dumps(data),encoding='utf8')
   request.update(mask_sha256=hashlib.sha256(mask.read_bytes()).hexdigest(),
    mapping=dict(u_start=0,u_span=1,y_start=1,max_distance=2,u_subsamples=2),
    output='nbt_models/_workspaces/curve-samples/effective-real')
   with self.assertRaisesRegex(ValueError,'CURVE_BACKING_CONFLICT'):plan_curve(workspace,request)
   self.assertFalse((workspace/request['output']).exists())
   data['palette']['W']['max_effective_depth']=3;mask.write_text(json.dumps(data),encoding='utf8')
   request['mask_sha256']=hashlib.sha256(mask.read_bytes()).hexdigest();file=workspace/'effective-request.json';file.write_text(json.dumps(request),encoding='utf8')
   run=subprocess.run(['node',str(ROOT/'scripts/cli.mjs'),'--workspace',str(workspace),'curve','plan','--request',str(file),'--compact'],
    cwd=ROOT,capture_output=True,text=True,encoding='utf8',timeout=90)
   self.assertEqual(run.returncode,0,run.stdout+run.stderr);result=json.loads(run.stdout);depth=result['summary']['effective_depth']
   self.assertEqual(depth['maximum'],2);self.assertEqual(depth['max_air_full_voxels'],0);self.assertGreater(depth['extended_faces'],0)
   self.assertEqual(Path(request['source']).read_bytes(),original);self.assertFalse(result['approval_created'])
   apply(workspace);facade=workspace/'.agents/skills/nbtcreator-workspace/nbt.py'
   run=subprocess.run([sys.executable,str(facade),'curve','verify','--plan',result['plan'],'--sha256',result['plan_sha256']],
    cwd=workspace,capture_output=True,text=True,encoding='utf8',timeout=90)
   self.assertEqual(run.returncode,0,run.stdout+run.stderr);self.assertTrue(json.loads(run.stdout)['valid'])
 def test_layered_real_surface_replays_connected_band_over_replaced_support(self):
  sys.path.insert(0,str(ROOT/'tests/support'))
  from curved_surface_fixture import create_curve_fixture
  from nbt_exposure import apply
  with tempfile.TemporaryDirectory() as temp:
   workspace=Path(temp);request=create_curve_fixture(workspace);original=Path(request['source']).read_bytes()
   old=json.loads(Path(request['mask']).read_text(encoding='utf8'));band=[];window=[]
   for y,row in enumerate(old['rows']):
    band.append(''.join('R' if item=='R' else '.' for item in row))
    window.append(''.join('W' if y in (2,3) and (item=='R' or column==6) else '.' for column,item in enumerate(row)))
   data=dict(schema_version=2,name='合成分层',layers=[
    dict(id='band',rows=band,palette={'R':old['palette']['R']},support_expectations={'R':dict(state='blackstone',wall=True)}),
    dict(id='window',rows=window,palette={'W':old['palette']['W']})],overlaps=[['band','window']])
   mask=workspace/'inputs/layered.json';mask.write_text(json.dumps(data,ensure_ascii=False),encoding='utf8')
   request.update(mask=str(mask),mask_sha256=hashlib.sha256(mask.read_bytes()).hexdigest())
   file=workspace/'layered-request.json';file.write_text(json.dumps(request),encoding='utf8')
   run=subprocess.run(['node',str(ROOT/'scripts/cli.mjs'),'--workspace',str(workspace),'curve','plan','--request',str(file),'--compact'],
    cwd=ROOT,capture_output=True,text=True,encoding='utf8',timeout=90)
   self.assertEqual(run.returncode,0,run.stdout+run.stderr);result=json.loads(run.stdout)
   self.assertGreater(result['summary']['connectors_added'],0);self.assertGreater(len(result['summary']['support_replacements']),0)
   self.assertFalse(result['continuity']['passed']);self.assertEqual(Path(request['source']).read_bytes(),original)
   apply(workspace);facade=workspace/'.agents/skills/nbtcreator-workspace/nbt.py'
   run=subprocess.run([sys.executable,str(facade),'curve','verify','--plan',result['plan'],'--sha256',result['plan_sha256']],
    cwd=workspace,capture_output=True,text=True,encoding='utf8',timeout=90)
   self.assertEqual(run.returncode,0,run.stdout+run.stderr);self.assertTrue(json.loads(run.stdout)['valid'])


if __name__=='__main__':unittest.main(verbosity=2)
