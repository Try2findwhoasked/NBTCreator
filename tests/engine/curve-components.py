"""Source-bound conversion of reusable components into curve masks."""
import hashlib
import json
from copy import deepcopy
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'.agents/skills/minecraft-nbt-modeler/scripts'),str(ROOT/'tests/support')]
from nbt_components import store,load,component_file,validate


def sha(file):return hashlib.sha256(Path(file).read_bytes()).hexdigest()


class CurveComponents(unittest.TestCase):
 def setUp(self):
  temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.workspace=Path(temp.name).resolve()
  self.component=store(self.workspace,dict(schema_version=1,name='合成纹样',size=[2,2,1],anchor=[0,0,0],
   palette=['stone','blackstone'],blocks=[[0,0,0,0,True],[1,0,0,0,True],[0,1,0,1,False]]))
 def request(self):
  source=dict(kind='local',id=self.component['id'],content_sha256=self.component['content_sha256'])
  spec=dict(kind='raise',state='stone_bricks',height=1,wall=False,role='rim')
  return dict(name='组合样段',size=[4,2],layers=[dict(id='band',source=source,slice_z=0,origin=[0,0],counts=[2,1],spacing=[2,1],
   mapping=[dict(index=0,wall=True,symbol='R'),dict(index=1,wall=False,symbol=None)],palette={'R':spec})],
   overlaps=[],output='nbt_models/_workspaces/curve-masks/sample')
 def mutate_component(self):
  file=component_file(self.workspace,self.component['id']);data=load(self.workspace,self.component['id']);data.pop('id');data.pop('content_sha256')
  data['blocks'][0][3]=1;file.write_text(json.dumps(validate(data),ensure_ascii=False),encoding='utf8')
 def library(self,payload,asset_type):
  import nbt_asset_libraries as libraries
  folder=self.workspace/'library-source';folder.mkdir();raw=libraries.encode(payload);(folder/'asset.json').write_bytes(raw)
  manifest=dict(schema_version=1,kind=libraries.FORMAT,id='test.curves',name='合成曲面库',version='1.0.0',license='CC0-1.0',
   assets=[dict(id='sample',name='合成素材',type=asset_type,path='asset.json',bytes=len(raw),sha256=libraries.digest(raw))])
  (folder/'library.json').write_bytes(libraries.encode(manifest))
  source=libraries.dispatch(self.workspace,'add',dict(source=str(folder)))['source']
  row=next(item for item in libraries.browse(self.workspace)['items'] if item['source_id']==source['id'])
  ref={key:row[key] for key in ('id','sha256','source_id','version','manifest_sha256')}
  return libraries,source,ref
 def test_local_component_slice_repeats_and_binds_source(self):
  from nbt_mounting.curve_components import compose_curve_mask,verify_curve_mask
  from nbt_curved_surface import _mask
  request=self.request();result=compose_curve_mask(self.workspace,request)
  data=json.loads(Path(result['mask']).read_text(encoding='utf8'))
  self.assertEqual(data['layers'][0]['rows'],['RRRR','....'])
  self.assertFalse(result['approval_created']);self.assertFalse(result['nbt_exported'])
  self.assertTrue(verify_curve_mask(self.workspace,result['mask'],result['mask_sha256'])['valid'])
  _mask(Path(result['mask']),result['mask_sha256'],self.workspace)
  self.mutate_component()
  with self.assertRaisesRegex(ValueError,'变化|哈希|内容'):verify_curve_mask(self.workspace,result['mask'],result['mask_sha256'])
  with self.assertRaisesRegex(ValueError,'变化|哈希|内容'):_mask(Path(result['mask']),result['mask_sha256'],self.workspace)
 def test_explicit_layer_connection_scope_survives_source_bound_composition(self):
  from nbt_mounting.curve_components import compose_curve_mask,verify_curve_mask
  request=self.request();request['layers'][0]['connections']={'raised':False,'recess':False}
  result=compose_curve_mask(self.workspace,request);data=json.loads(Path(result['mask']).read_text(encoding='utf8'))
  self.assertEqual(data['layers'][0]['connections'],{'raised':False,'recess':False})
  self.assertTrue(verify_curve_mask(self.workspace,result['mask'],result['mask_sha256'])['valid'])
 def test_archived_local_component_invalidates_bound_mask(self):
  from nbt_components import update
  from nbt_mounting.curve_components import compose_curve_mask,verify_curve_mask
  result=compose_curve_mask(self.workspace,self.request());update(self.workspace,self.component['id'],archived=True)
  with self.assertRaisesRegex(ValueError,'归档'):verify_curve_mask(self.workspace,result['mask'],result['mask_sha256'])
 def test_source_mapping_and_bounds_cannot_silently_drop_or_clip(self):
  from nbt_mounting.curve_components import compose_curve_mask
  request=self.request();request['layers'][0]['mapping'].pop()
  with self.assertRaisesRegex(ValueError,'映射'):compose_curve_mask(self.workspace,request)
  self.assertFalse((self.workspace/request['output']).exists())
  request=self.request();request['layers'][0]['origin']=[1,0]
  with self.assertRaisesRegex(ValueError,'越界|裁切'):compose_curve_mask(self.workspace,request)
  self.assertFalse((self.workspace/request['output']).exists())
  request=self.request();request['layers'][0]['mapping'][1]['wall']=True
  with self.assertRaisesRegex(ValueError,'映射'):compose_curve_mask(self.workspace,request)
  self.assertFalse((self.workspace/request['output']).exists())
 def test_software_source_root_is_not_a_creative_workspace(self):
  from nbt_mounting.curve_components import compose_curve_mask
  with self.assertRaisesRegex(ValueError,'不是创作工作区'):compose_curve_mask(ROOT,self.request())
 def test_existing_output_directory_is_never_overwritten(self):
  from nbt_mounting.curve_components import compose_curve_mask
  request=self.request();destination=self.workspace/request['output'];destination.mkdir(parents=True)
  marker=destination/'keep.txt';marker.write_text('用户内容',encoding='utf8')
  with self.assertRaisesRegex(ValueError,'新目录|存在'):compose_curve_mask(self.workspace,request)
  self.assertEqual(marker.read_text(encoding='utf8'),'用户内容')
 def test_workspace_knowledge_selector_exposes_only_selected_curve_routes(self):
  from nbt_exposure import apply
  index=self.workspace/'.agents/skills/nbtcreator-workspace/knowledge.md'
  apply(self.workspace,dict(schema_version=1,enabled_groups=['core']))
  before=index.read_text(encoding='utf8')
  for name in ('curved-surface.md','orthographic-reference.md','large-assembly.md'):self.assertNotIn(name,before)
  apply(self.workspace,dict(schema_version=1,enabled_groups=['core','modelling']))
  selected=index.read_text(encoding='utf8')
  for name in ('curved-surface.md','orthographic-reference.md','large-assembly.md'):self.assertIn(name,selected)
  self.assertIn('曲面纹样与构件复用',selected);self.assertIn('大型组装与协作切片',selected)
 def test_explicit_asset_layers_can_overlap_on_a_real_curved_host(self):
  from nbt_mounting.curve_components import compose_curve_mask
  from nbt_curved_surface import plan_curve,verify_curve
  from curved_surface_fixture import create_curve_fixture
  request=self.request();request['size']=[2,2];request['layers'][0]['counts']=[1,1]
  request['layers'][0]['support_expectations']={'R':dict(state='blackstone',wall=True)}
  window=deepcopy(request['layers'][0]);window['id']='window';window.pop('support_expectations')
  window['mapping'][0]['symbol']='W';window['palette']={'W':dict(kind='inlay',state='blackstone',wall=True,depth=1,backing=1,role='window')}
  request['layers'].append(window);request['overlaps']=[['band','window']]
  result=compose_curve_mask(self.workspace,request);fixture=create_curve_fixture(self.workspace)
  fixture.update(mask=result['mask'],mask_sha256=result['mask_sha256'],mapping=dict(u_start=.01,u_span=.02,y_start=2,max_distance=2),
   output='nbt_models/_workspaces/curve-samples/from-overlapping-assets')
  candidate=plan_curve(self.workspace,fixture)
  self.assertEqual(candidate['summary']['layers'],2);self.assertGreater(candidate['summary']['overlapping_uv'],0)
  self.assertGreater(len(candidate['summary']['support_replacements']),0)
  self.assertTrue(verify_curve(self.workspace,candidate['plan'],candidate['plan_sha256'])['valid'])
  self.mutate_component()
  with self.assertRaisesRegex(ValueError,'变化|哈希|内容'):verify_curve(self.workspace,candidate['plan'],candidate['plan_sha256'])
 def test_cross_layer_overlap_requires_explicit_permission(self):
  from nbt_mounting.curve_components import compose_curve_mask
  request=self.request();other=deepcopy(request['layers'][0]);other['id']='second';request['layers'].append(other)
  with self.assertRaisesRegex(ValueError,'重叠'):compose_curve_mask(self.workspace,request)
  self.assertFalse((self.workspace/request['output']).exists())
  request['overlaps']=[['band','second']];result=compose_curve_mask(self.workspace,request)
  self.assertFalse(result['approval_created']);self.assertEqual(result['layers'],2)
 def test_rehashed_composition_cannot_forge_a_mask(self):
  from nbt_mounting.curve_components import compose_curve_mask,verify_curve_mask
  result=compose_curve_mask(self.workspace,self.request());mask=Path(result['mask']);data=json.loads(mask.read_text(encoding='utf8'))
  data['layers'][0]['rows'][0]='R.RR'
  receipt=Path(result['manifest']);proof=json.loads(receipt.read_text(encoding='utf8'))
  body={key:value for key,value in data.items() if key!='composition'}
  canonical=(json.dumps(body,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode('utf8')
  proof['body_sha256']=hashlib.sha256(canonical).hexdigest();receipt.write_text(json.dumps(proof),encoding='utf8')
  data['composition']['sha256']=sha(receipt);mask.write_text(json.dumps(data),encoding='utf8')
  with self.assertRaisesRegex(ValueError,'不一致|哈希'):verify_curve_mask(self.workspace,mask,sha(mask))
 def test_source_change_during_composition_does_not_publish(self):
  from nbt_mounting.curve_components import compose_curve_mask,_component
  calls=0
  def mutate(*args):
   nonlocal calls
   value=_component(*args);calls+=1
   if calls==1:self.mutate_component()
   return value
  request=self.request()
  with patch('nbt_mounting.curve_components._component',side_effect=mutate):
   with self.assertRaisesRegex(ValueError,'变化|哈希|内容'):compose_curve_mask(self.workspace,request)
  self.assertFalse((self.workspace/request['output']).exists())
 def test_source_change_during_final_publication_removes_only_new_output(self):
  from nbt_mounting.curve_components import compose_curve_mask,_component
  calls=0
  def mutate(*args):
   nonlocal calls
   value=_component(*args);calls+=1
   if calls==2:self.mutate_component()
   return value
  request=self.request()
  with patch('nbt_mounting.curve_components._component',side_effect=mutate):
   with self.assertRaisesRegex(ValueError,'变化|哈希|内容'):compose_curve_mask(self.workspace,request)
  self.assertFalse((self.workspace/request['output']).exists())
 def test_source_change_during_candidate_planning_prevents_publication(self):
  from nbt_mounting.curve_components import compose_curve_mask
  from nbt_curved_surface import plan_curve,_calculate
  from curved_surface_fixture import create_curve_fixture
  request=self.request();request['size']=[2,2];request['layers'][0]['counts']=[1,1]
  mask=compose_curve_mask(self.workspace,request);fixture=create_curve_fixture(self.workspace)
  fixture.update(mask=mask['mask'],mask_sha256=mask['mask_sha256'],mapping=dict(u_start=.01,u_span=.02,y_start=2,max_distance=2),
   output='nbt_models/_workspaces/curve-samples/source-race')
  original=Path(fixture['source']).read_bytes()
  def mutate(*args):
   value=_calculate(*args);self.mutate_component();return value
  with patch('nbt_curved_surface._calculate',side_effect=mutate):
   with self.assertRaisesRegex(ValueError,'变化|哈希|内容'):plan_curve(self.workspace,fixture)
  self.assertFalse((self.workspace/fixture['output']).exists());self.assertEqual(Path(fixture['source']).read_bytes(),original)
 def test_repeated_identical_cells_are_counted_and_conflicts_rejected(self):
  from nbt_mounting.curve_components import compose_curve_mask
  request=self.request();request['size']=[3,2];request['layers'][0]['spacing']=[1,1]
  result=compose_curve_mask(self.workspace,request);proof=json.loads(Path(result['manifest']).read_text(encoding='utf8'))
  self.assertEqual(proof['stats'][0]['merged_cells'],1)
  other=store(self.workspace,dict(schema_version=1,name='不同符号',size=[2,1,1],anchor=[0,0,0],
   palette=['stone','blackstone'],blocks=[[0,0,0,0,False],[1,0,0,1,False]]))
  request=self.request();request.update(size=[3,1],output='nbt_models/_workspaces/curve-masks/conflict')
  request['layers'][0].update(source=dict(kind='local',id=other['id'],content_sha256=other['content_sha256']),spacing=[1,1],
   mapping=[dict(index=0,wall=False,symbol='R'),dict(index=1,wall=False,symbol='S')],
   palette={'R':dict(kind='raise',state='stone',height=1,wall=False,role='rim'),
            'S':dict(kind='raise',state='gold_block',height=1,wall=False,role='accent')})
  with self.assertRaisesRegex(ValueError,'不同动作重叠'):compose_curve_mask(self.workspace,request)
  self.assertFalse((self.workspace/request['output']).exists())
 def test_composed_mask_remains_bound_after_workspace_relocation(self):
  from nbt_mounting.curve_components import compose_curve_mask,verify_curve_mask
  result=compose_curve_mask(self.workspace,self.request())
  with tempfile.TemporaryDirectory() as parent:
   moved=Path(parent)/'creative';shutil.copytree(self.workspace,moved)
   mask=moved/Path(result['mask']).relative_to(self.workspace)
   self.assertTrue(verify_curve_mask(moved,mask,result['mask_sha256'])['valid'])
 def test_connected_component_is_resolved_offline_and_disabling_invalidates(self):
  from nbt_mounting.curve_components import compose_curve_mask,verify_curve_mask
  payload=load(self.workspace,self.component['id']);payload.pop('id')
  libraries,source,ref=self.library(payload,'component');ref['content_sha256']=payload['content_sha256']
  request=self.request();request['layers'][0]['source']=dict(kind='library',ref=ref)
  original_fetch=libraries.fetch
  def offline(location,*args,**kwargs):
   if libraries.remote(location):raise AssertionError('离线构件解析不得访问网络')
   return original_fetch(location,*args,**kwargs)
  with patch.object(libraries,'fetch',side_effect=offline):
   result=compose_curve_mask(self.workspace,request)
   self.assertTrue(verify_curve_mask(self.workspace,result['mask'],result['mask_sha256'])['valid'])
  from nbt_exposure import apply
  apply(self.workspace);facade=self.workspace/'.agents/skills/nbtcreator-workspace/nbt.py'
  command=[sys.executable,str(facade),'curve','verify-mask','--mask',result['mask'],'--sha256',result['mask_sha256']]
  run=subprocess.run(command,cwd=self.workspace,capture_output=True,text=True,encoding='utf8',timeout=90)
  self.assertEqual(run.returncode,0,run.stdout+run.stderr);self.assertTrue(json.loads(run.stdout)['valid'])
  libraries.dispatch(self.workspace,'enable',dict(id=source['id'],enabled=False))
  with self.assertRaisesRegex(ValueError,'移除|停用|来源'):verify_curve_mask(self.workspace,result['mask'],result['mask_sha256'])
  run=subprocess.run(command,cwd=self.workspace,capture_output=True,text=True,encoding='utf8',timeout=90)
  self.assertNotEqual(run.returncode,0);self.assertRegex(run.stdout,'移除|停用|来源')
 def test_library_version_change_invalidates_mask_and_rollback_restores_it(self):
  from nbt_mounting.curve_components import compose_curve_mask,verify_curve_mask
  payload=load(self.workspace,self.component['id']);payload.pop('id')
  libraries,source,ref=self.library(payload,'component');ref['content_sha256']=payload['content_sha256']
  request=self.request();request['layers'][0]['source']=dict(kind='library',ref=ref)
  result=compose_curve_mask(self.workspace,request)
  manifest=self.workspace/'library-source/library.json';data=json.loads(manifest.read_text(encoding='utf8'))
  data['version']='1.1.0';manifest.write_bytes(libraries.encode(data))
  libraries.dispatch(self.workspace,'refresh',dict(id=source['id']))
  with self.assertRaisesRegex(ValueError,'版本|变化|更新'):verify_curve_mask(self.workspace,result['mask'],result['mask_sha256'])
  libraries.dispatch(self.workspace,'rollback',dict(id=source['id']))
  self.assertTrue(verify_curve_mask(self.workspace,result['mask'],result['mask_sha256'])['valid'])
 def test_bundled_component_is_resolved_without_network(self):
  import nbt_asset_libraries as libraries
  from nbt_mounting.curve_components import compose_curve_mask,verify_curve_mask
  row=next(item for item in libraries.browse(self.workspace)['items'] if item['source_id']=='bundled' and item['type']=='component')
  ref={key:row[key] for key in ('id','sha256','source_id','version','manifest_sha256')}
  data=libraries.read_asset(self.workspace,ref)['data'];ref['content_sha256']=data['content_sha256']
  z=data['blocks'][0][2];pairs={(block[3],block[4]) for block in data['blocks'] if block[2]==z}
  request=self.request();request['size']=data['size'][:2];layer=request['layers'][0]
  layer.update(source=dict(kind='library',ref=ref),slice_z=z,origin=[0,0],counts=[1,1],spacing=[1,1],
               mapping=[dict(index=index,wall=wall,symbol='R') for index,wall in sorted(pairs)])
  original_fetch=libraries.fetch
  def offline(location,*args,**kwargs):
   if libraries.remote(location):raise AssertionError('内置构件解析不得访问网络')
   return original_fetch(location,*args,**kwargs)
  with patch.object(libraries,'fetch',side_effect=offline):
   result=compose_curve_mask(self.workspace,request)
   self.assertTrue(verify_curve_mask(self.workspace,result['mask'],result['mask_sha256'])['valid'])
  from nbt_exposure import apply
  apply(self.workspace);facade=self.workspace/'.agents/skills/nbtcreator-workspace/nbt.py'
  run=subprocess.run([sys.executable,str(facade),'curve','verify-mask','--mask',result['mask'],'--sha256',result['mask_sha256']],
   cwd=self.workspace,capture_output=True,text=True,encoding='utf8',timeout=90)
  self.assertEqual(run.returncode,0,run.stdout+run.stderr);self.assertTrue(json.loads(run.stdout)['valid'])
 def test_parameterized_library_source_binds_arguments_and_compiled_content(self):
  import nbt_asset_libraries as libraries
  from nbt_mounting.curve_components import compose_curve_mask,verify_curve_mask
  recipe=dict(schema_version=1,kind='nbtcreator.parametric-recipe',
              arguments=dict(kind='pillar',name='合成柱',size=[3,3,3],material='stone'))
  libraries,source,ref=self.library(recipe,'parametric_recipe');arguments=dict(size=[3,5,3])
  resolved=libraries.read_asset(self.workspace,ref);component,_,_=libraries.materialize(self.workspace,resolved,arguments)
  ref.update(arguments=arguments,content_sha256=component['content_sha256'])
  selected={(block[3],block[4]) for block in component['blocks'] if block[2]==0}
  request=self.request();request['size']=[3,5];layer=request['layers'][0]
  layer.update(source=dict(kind='library',ref=ref),slice_z=0,origin=[0,0],counts=[1,1],spacing=[1,1],
               mapping=[dict(index=index,wall=wall,symbol='R') for index,wall in sorted(selected)])
  result=compose_curve_mask(self.workspace,request)
  self.assertTrue(verify_curve_mask(self.workspace,result['mask'],result['mask_sha256'])['valid'])
  bad=self.request();bad['size']=[3,5];bad['layers'][0].update(layer)
  bad['layers'][0]['source']['ref']['content_sha256']='0'*64;bad['output']='nbt_models/_workspaces/curve-masks/stale'
  with self.assertRaisesRegex(ValueError,'变化|更新|STALE|预览'):compose_curve_mask(self.workspace,bad)
  self.assertFalse((self.workspace/bad['output']).exists())
 def test_bundled_ornament_reports_quantization_on_real_eccentric_host(self):
  import nbt_asset_libraries as libraries
  from nbt_mounting.curve_components import compose_curve_mask
  from nbt_curved_surface import plan_curve,verify_curve
  from curved_surface_fixture import create_curve_fixture
  row=next(item for item in libraries.browse(self.workspace)['items']
           if item['source_id']=='bundled' and item['id'].endswith('/ornate-pattern-meander-frieze'))
  ref={key:row[key] for key in ('id','sha256','source_id','version','manifest_sha256')}
  asset=libraries.read_asset(self.workspace,ref)['data'];ref['content_sha256']=asset['content_sha256']
  selected={(block[3],block[4]) for block in asset['blocks'] if block[2]==1}
  request=self.request();request['name']='内置纹样合成探针';request['size']=asset['size'][:2]
  request['layers'][0].update(source=dict(kind='library',ref=ref),slice_z=1,origin=[0,0],counts=[1,1],spacing=[1,1],
   mapping=[dict(index=index,wall=wall,symbol='R') for index,wall in sorted(selected)],
   palette={'R':dict(kind='raise',state='gold_block',height=1,wall=True,role='ornament')})
  mask=compose_curve_mask(self.workspace,request);fixture=create_curve_fixture(self.workspace)
  fixture.update(mask=mask['mask'],mask_sha256=mask['mask_sha256'],
   mapping=dict(u_start=0,u_span=.25,y_start=2,max_distance=2,u_subsamples=2),
   output='nbt_models/_workspaces/curve-samples/bundled-ornament')
  result=plan_curve(self.workspace,fixture)
  self.assertGreater(result['summary']['truncated'],0);self.assertFalse(result['continuity']['passed'])
  self.assertFalse(result['approval_created']);self.assertTrue(verify_curve(self.workspace,result['plan'],result['plan_sha256'])['valid'])
 def test_shared_cli_and_frozen_candidate_verify_component_provenance(self):
  from curved_surface_fixture import create_curve_fixture
  from nbt_exposure import apply
  request=self.request();request['size']=[2,2];request['layers'][0]['counts']=[1,1]
  file=self.workspace/'compose-request.json';file.write_text(json.dumps(request),encoding='utf8')
  base=['node',str(ROOT/'scripts/cli.mjs'),'--workspace',str(self.workspace),'curve']
  run=subprocess.run([*base,'compose','--request',str(file)],cwd=ROOT,capture_output=True,text=True,encoding='utf8',timeout=90)
  self.assertEqual(run.returncode,0,run.stdout+run.stderr);result=json.loads(run.stdout)
  fixture=create_curve_fixture(self.workspace);fixture.update(mask=result['mask'],mask_sha256=result['mask_sha256'],
   mapping=dict(u_start=.01,u_span=.02,y_start=2,max_distance=2),output='nbt_models/_workspaces/curve-samples/from-asset')
  plan_request=self.workspace/'asset-plan.json';plan_request.write_text(json.dumps(fixture),encoding='utf8')
  run=subprocess.run([*base,'plan','--request',str(plan_request),'--compact'],cwd=ROOT,capture_output=True,text=True,encoding='utf8',timeout=90)
  self.assertEqual(run.returncode,0,run.stdout+run.stderr);plan=json.loads(run.stdout)
  apply(self.workspace);facade=self.workspace/'.agents/skills/nbtcreator-workspace/nbt.py'
  mask_verify=[sys.executable,str(facade),'curve','verify-mask','--mask',result['mask'],'--sha256',result['mask_sha256']]
  run=subprocess.run(mask_verify,cwd=self.workspace,capture_output=True,text=True,encoding='utf8',timeout=90)
  self.assertEqual(run.returncode,0,run.stdout+run.stderr);self.assertTrue(json.loads(run.stdout)['valid'])
  verify=[sys.executable,str(facade),'curve','verify','--plan',plan['plan'],'--sha256',plan['plan_sha256']]
  run=subprocess.run(verify,cwd=self.workspace,capture_output=True,text=True,encoding='utf8',timeout=90)
  self.assertEqual(run.returncode,0,run.stdout+run.stderr);self.assertTrue(json.loads(run.stdout)['valid'])
  self.mutate_component()
  run=subprocess.run(mask_verify,cwd=self.workspace,capture_output=True,text=True,encoding='utf8',timeout=90)
  self.assertNotEqual(run.returncode,0);self.assertRegex(run.stdout,'变化|哈希|内容')
  run=subprocess.run(verify,cwd=self.workspace,capture_output=True,text=True,encoding='utf8',timeout=90)
  self.assertNotEqual(run.returncode,0);self.assertRegex(run.stdout,'变化|哈希|内容')


if __name__=='__main__':unittest.main(verbosity=2)
