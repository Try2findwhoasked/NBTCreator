"""Synthetic orthographic registration and anchor-driven loft contracts."""
import hashlib
import json
from pathlib import Path
import subprocess
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image,ImageDraw

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_reference_views import register_reference,load_reference,fit_profile,save_fit,verify_fit
from nbt_review.reference_projection import compare_reference,verify_comparison
from nbt_review.reference_camera import prepare_cameras,verify_cameras


class ReferenceViews(unittest.TestCase):
 def setUp(self):
  temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name)
  folder=self.root/'inputs';folder.mkdir()
  views={}
  for name,u,v in [('front','x','-y'),('side','z','-y'),('top','x','z')]:
   file=folder/(name+'.png');Image.new('RGB',(64,64),'white').save(file)
   views[name]=dict(image='inputs/'+file.name,sha256=hashlib.sha256(file.read_bytes()).hexdigest(),
                    origin=[4,50] if name!='top' else [4,4],pixels_per_block=2,u_axis=u,v_axis=v,
                    origin_type='generated' if name=='side' else 'original',basis='合成参考资料')
  anchors=[];rows=[]
  for y,x0,x1 in [(0,4,12),(4,2,14),(8,5,13)]:
   row={}
   for edge,world in [('x_min',[x0,y,6]),('x_max',[x1,y,6]),('z_min',[8,y,2]),('z_max',[8,y,10])]:
    identifier=f'{edge}_{y}';row[edge]=identifier
    anchors.append(dict(id=identifier,part='tower',world=world,basis='合成锚点',confidence='measured',uncertainty=0,
      views=dict(front=[4+2*world[0],50-2*y],side=[4+2*world[2],50-2*y],top=[4+2*world[0],4+2*world[2]])))
   rows.append(row)
  self.rows=rows
  self.request=dict(output='nbt_models/_workspaces/reference-views/example',views=views,anchors=anchors,
                    assumptions=['背面为推定'])
 def test_registered_images_anchors_and_assumptions_are_hash_bound(self):
  result=register_reference(self.root,self.request)
  data=load_reference(result['manifest'],result['manifest_sha256'])
  self.assertEqual(len(data['anchors']),12);self.assertEqual(data['assumptions'],['背面为推定'])
  self.assertEqual(data['views']['top']['v_axis'],'z')
  self.assertEqual(data['views']['side']['origin_type'],'generated')
  image=Path(result['manifest']).parent/data['views']['front']['file'];image.write_bytes(image.read_bytes()+b'changed')
  with self.assertRaisesRegex(ValueError,'哈希|变化'):load_reference(result['manifest'],result['manifest_sha256'])
 def test_anchor_profile_generates_repeatable_bounded_loft_sections(self):
  result=register_reference(self.root,self.request)
  request=dict(reference=result['manifest'],reference_sha256=result['manifest_sha256'],part='tower',rows=self.rows,
               sample_step=1,vertices=16)
  first=fit_profile(request);second=fit_profile(request)
  self.assertEqual(first,second);self.assertEqual(first['geometry']['shape'],'loft')
  sections=first['geometry']['sections'];self.assertEqual([item['y'] for item in sections],[float(y) for y in range(9)])
  self.assertTrue(all(len(item['vertices'])==16 for item in sections))
  for section in sections:
   xs=[p[0] for p in section['vertices']]
   self.assertGreaterEqual(min(xs),2);self.assertLessEqual(max(xs),14)
  self.assertAlmostEqual(min(p[0] for p in sections[4]['vertices']),2)
  self.assertAlmostEqual(max(p[0] for p in sections[4]['vertices']),14)
  self.assertEqual(first['reference_sha256'],result['manifest_sha256'])
  from nbt_assembly import Volume
  from nbt_refine import operation_candidates
  model=Volume((20,10,16))
  operation=dict(kind='geometry',label='锚点放样',classification='body',lo=[0,0,0],hi=[19,8,15],
                 state='stone',geometry=first['geometry'])
  edits=operation_candidates(model,operation)
  self.assertGreater(len(edits),0)
  self.assertTrue(all(model.in_bounds(position) for position,_ in edits))
 def test_marked_corner_keeps_distinct_slopes_and_exact_anchor(self):
  result=register_reference(self.root,self.request);rows=[dict(row) for row in self.rows];rows[1]['corner']=True
  fitted=fit_profile(dict(reference=result['manifest'],reference_sha256=result['manifest_sha256'],part='tower',rows=rows,sample_step=1,vertices=16))
  first,second=fitted['controls']['x_min']
  self.assertLess(first[3]-first[2],0);self.assertGreater(second[1]-second[0],0)
  self.assertEqual(first[3],second[0]);self.assertEqual(first[3],2)
 def test_registered_anchors_build_a_coarse_model_and_reproject(self):
  from nbt_working_model import WorkingModel
  for anchor in self.request['anchors']:
   if anchor['world'][1]==8:
    original=next(item for item in self.request['anchors'] if item['id']==anchor['id'].replace('_8','_0'))
    anchor['world'][0]=original['world'][0];anchor['world'][2]=original['world'][2]
    x,y,z=anchor['world'];anchor['views']=dict(front=[4+2*x,50-2*y],side=[4+2*z,50-2*y],top=[4+2*x,4+2*z])
  registered=register_reference(self.root,self.request)
  fitted=fit_profile(dict(reference=registered['manifest'],reference_sha256=registered['manifest_sha256'],
      part='tower',rows=[self.rows[0],self.rows[2]],sample_step=1,vertices=16))
  working=WorkingModel(self.root,[20,10,16])
  working.apply_operations([dict(kind='geometry',label='参考粗模',classification='body',lo=[0,0,0],hi=[19,8,15],
                                  state='stone',geometry=fitted['geometry'])])
  saved=working.save_draft(name_zh='参考粗模')
  masks={}
  for view in ('front','side','top'):
   image=Image.new('L',(64,64),0);draw=ImageDraw.Draw(image)
   if view=='front':draw.rectangle((12,34,27,49),fill=255)
   elif view=='side':draw.rectangle((8,34,23,49),fill=255)
   else:
    for x in range(4,12):
     for z in range(2,10):
      if ((x+.5-8)/4)**2+((z+.5-6)/4)**2<=1:draw.rectangle((4+2*x,4+2*z,5+2*x,5+2*z),fill=255)
   file=self.root/'inputs'/('coarse-'+view+'.png');image.save(file)
   masks[view]=dict(file='inputs/'+file.name,sha256=hashlib.sha256(file.read_bytes()).hexdigest(),threshold=128)
  comparison=compare_reference(self.root,dict(source=saved['source'],source_sha256=saved['source_sha256'],
    reference=registered['manifest'],reference_sha256=registered['manifest_sha256'],masks=masks,regions=[],
    output='nbt_models/_workspaces/reference-reviews/coarse'))
  for view in ('front','side','top'):self.assertGreater(comparison['views'][view]['metrics']['silhouette_iou'],.75)
  self.assertFalse(comparison['approval_created']);self.assertFalse(saved['nbt_exported'])
 def test_saved_fit_recomputes_from_bound_reference_and_rejects_forgery(self):
  registered=register_reference(self.root,self.request)
  request=dict(reference=registered['manifest'],reference_sha256=registered['manifest_sha256'],part='tower',rows=self.rows,sample_step=1,vertices=16)
  saved=save_fit(self.root,request,'nbt_models/_workspaces/reference-fits/tower.json')
  self.assertTrue(verify_fit(self.root,saved['output'],saved['sha256'])['valid'])
  file=Path(saved['output']);data=json.loads(file.read_text(encoding='utf8'));data['geometry']['sections'][0]['vertices'][0][0]+=1
  file.write_text(json.dumps(data),encoding='utf8');forged=hashlib.sha256(file.read_bytes()).hexdigest()
  with self.assertRaisesRegex(ValueError,'不一致'):verify_fit(self.root,file,forged)
 def test_conflicting_scale_observations_and_anchor_rows_are_rejected(self):
  self.request['views']['side']['pixels_per_block']=3
  with self.assertRaisesRegex(ValueError,'尺度'):register_reference(self.root,self.request)
  self.request['views']['side']['pixels_per_block']=2
  self.request['anchors'][0]['views']['front']=[1,1]
  with self.assertRaisesRegex(ValueError,'锚点'):register_reference(self.root,self.request)
 def test_reference_changed_during_read_is_rejected(self):
  from nbt_reference_views import _image_bytes
  result=register_reference(self.root,self.request);manifest=Path(result['manifest']);front=manifest.parent/'images/front.png'
  def mutate(path):
   value=_image_bytes(path)
   if Path(path).name=='top.png':front.write_bytes(front.read_bytes()+b'changed')
   return value
  with patch('nbt_reference_views._image_bytes',side_effect=mutate):
   with self.assertRaisesRegex(ValueError,'变化'):load_reference(manifest,result['manifest_sha256'])

 def projection_request(self):
  from nbt_assembly import Volume
  from nbt_snbt import save_snbt
  registered=register_reference(self.root,self.request)
  model=Volume((16,10,16));model.put((4,0,6),'stone');model.put((5,0,6),'stone_slab[type=bottom,waterlogged=false]')
  source=self.root/'nbt_models/standalone/project/v01/master/model.snbt';source.parent.mkdir(parents=True)
  saved=save_snbt(source,model,set())
  masks={}
  for view in ('front','side','top'):
   image=Image.new('L',(64,64),0);draw=ImageDraw.Draw(image)
   if view=='front':draw.rectangle((12,48,13,49),fill=255);draw.rectangle((14,49,15,49),fill=255)
   elif view=='side':draw.rectangle((16,48,17,49),fill=255)
   else:draw.rectangle((12,16,15,17),fill=255)
   file=self.root/'inputs'/(view+'-mask.png');image.save(file)
   masks[view]=dict(file='inputs/'+file.name,sha256=hashlib.sha256(file.read_bytes()).hexdigest(),threshold=128)
  request=dict(source=str(source),source_sha256=saved['source_sha256'],reference=registered['manifest'],
               reference_sha256=registered['manifest_sha256'],masks=masks,regions=[dict(id='detail',view='front',lo=[10,46],hi=[18,52])],
               output='nbt_models/_workspaces/reference-reviews/exact')
  return request
 def test_projection_compares_real_half_blocks_and_writes_verifiable_overlays(self):
  request=self.projection_request();result=compare_reference(self.root,request)
  self.assertEqual(result['canvas_size'],[16,10,16]);self.assertEqual(result['occupied_bounds'],dict(lo=[4,0,6],hi=[5,0,6]))
  for view in ('front','side','top'):
   metrics=result['views'][view]['metrics']
   self.assertEqual(metrics['silhouette_iou'],1.0)
   self.assertEqual(metrics['reference_contour_coverage'],1.0);self.assertEqual(metrics['model_contour_coverage'],1.0)
   self.assertTrue((Path(result['report']).parent/result['views'][view]['overlay']).is_file())
  self.assertEqual(result['regions'][0]['metrics']['silhouette_iou'],1.0)
  self.assertTrue(verify_comparison(self.root,result['report'],result['report_sha256'])['valid'])
  mask=self.root/request['masks']['front']['file'];mask.write_bytes(mask.read_bytes()+b'changed')
  with self.assertRaisesRegex(ValueError,'变化|哈希'):verify_comparison(self.root,result['report'],result['report_sha256'])
 def test_projection_ignores_declared_occlusion_and_reports_no_evidence_separately(self):
  request=self.projection_request()
  file=self.root/request['masks']['front']['file'];mask=Image.open(file).convert('L');mask.putpixel((50,50),255);mask.save(file)
  request['masks']['front']['sha256']=hashlib.sha256(file.read_bytes()).hexdigest()
  ignored=Image.new('L',(64,64),0);ignored.putpixel((50,50),255);ignore_file=self.root/'inputs/ignore.png';ignored.save(ignore_file)
  request['masks']['front'].update(ignore_file='inputs/ignore.png',ignore_sha256=hashlib.sha256(ignore_file.read_bytes()).hexdigest())
  result=compare_reference(self.root,request)
  self.assertEqual(result['views']['front']['metrics']['silhouette_iou'],1.0)
  self.assertEqual(result['views']['front']['metrics']['ignored_pixels'],1)
 def test_one_block_tolerance_is_bidirectional_and_empty_reference_is_unknown(self):
  request=self.projection_request()
  front=self.root/request['masks']['front']['file'];image=Image.open(front).convert('L')
  shifted=Image.new('L',image.size,0);shifted.paste(image,(2,0));shifted.save(front)
  request['masks']['front']['sha256']=hashlib.sha256(front.read_bytes()).hexdigest()
  top=self.root/request['masks']['top']['file'];Image.new('L',(64,64),0).save(top)
  request['masks']['top']['sha256']=hashlib.sha256(top.read_bytes()).hexdigest()
  result=compare_reference(self.root,request)
  front_metrics=result['views']['front']['metrics']
  self.assertLess(front_metrics['silhouette_iou'],1.0)
  self.assertEqual(front_metrics['reference_contour_coverage'],1.0)
  self.assertEqual(front_metrics['model_contour_coverage'],1.0)
  self.assertIsNone(result['views']['top']['metrics']['reference_contour_coverage'])
 def test_projection_refuses_source_mutated_during_comparison(self):
  from nbt_review.reference_projection import _project
  request=self.projection_request();source=Path(request['source'])
  def mutate(*args):
   result=_project(*args);source.write_bytes(source.read_bytes()+b' ');return result
  with patch('nbt_review.reference_projection._project',side_effect=mutate):
   with self.assertRaisesRegex(ValueError,'变化'):compare_reference(self.root,request)
  self.assertFalse((self.root/request['output']/'comparison.json').exists())
 def test_projection_preserves_a_real_hole_as_a_separate_local_error(self):
  from nbt_assembly import Volume
  from nbt_snbt import save_snbt
  request=self.projection_request();model=Volume((16,10,16))
  for x in range(4,8):
   for y in range(4):
    if (x,y)!=(5,1):model.put((x,y,6),'stone')
  source=Path(request['source']);saved=save_snbt(source,model,set());request['source_sha256']=saved['source_sha256']
  for view in ('front','side','top'):
   image=Image.new('L',(64,64),0);draw=ImageDraw.Draw(image)
   if view=='front':
    draw.rectangle((12,42,19,49),fill=255);draw.rectangle((14,46,15,47),fill=0)
   elif view=='side':draw.rectangle((16,42,17,49),fill=255)
   else:draw.rectangle((12,16,19,17),fill=255)
   file=self.root/request['masks'][view]['file'];image.save(file);request['masks'][view]['sha256']=hashlib.sha256(file.read_bytes()).hexdigest()
  request['regions']=[dict(id='hole',view='front',lo=[14,46],hi=[15,47])]
  result=compare_reference(self.root,request)
  self.assertEqual(result['views']['front']['metrics']['silhouette_iou'],1.0)
  self.assertIsNone(result['regions'][0]['metrics']['silhouette_iou'])
  front=self.root/request['masks']['front']['file'];image=Image.open(front).convert('L');ImageDraw.Draw(image).rectangle((14,46,15,47),fill=255);image.save(front)
  request['masks']['front']['sha256']=hashlib.sha256(front.read_bytes()).hexdigest()
  request['output']='nbt_models/_workspaces/reference-reviews/filled-hole'
  result=compare_reference(self.root,request)
  self.assertEqual(result['regions'][0]['metrics']['silhouette_iou'],0.0)
 def test_assembly_projection_verification_binds_every_partition(self):
  from nbt_large_assembly import AssemblyVolume,save_assembly
  request=self.projection_request();model=AssemblyVolume((300,384,300))
  model.put((4,0,6),'stone');model.put((5,0,6),'stone_slab[type=bottom,waterlogged=false]')
  source=save_assembly(self.root/'nbt_models/standalone/assembly/v01/master',model,set(),
                       [dict(offset=[0,0,0],size=[8,8,8])])
  request.update(source=source['source'],source_sha256=source['source_sha256'])
  result=compare_reference(self.root,request)
  self.assertEqual(result['views']['front']['metrics']['silhouette_iou'],1.0)
  part=Path(source['source']).parent/'parts/part-0000.snbt';part.write_bytes(part.read_bytes()+b' ')
  with self.assertRaisesRegex(ValueError,'分区.*变化'):verify_comparison(self.root,result['report'],result['report_sha256'])
 def test_comparison_keeps_workspace_relative_mask_bindings_after_relocation(self):
  request=self.projection_request()
  for view in request['masks'].values():view['file']=str((self.root/view['file']).resolve())
  result=compare_reference(self.root,request)
  for view in result['views'].values():self.assertFalse(Path(view['mask']['file']).is_absolute())
  moved=tempfile.TemporaryDirectory();self.addCleanup(moved.cleanup);destination=Path(moved.name)/'project'
  shutil.copytree(self.root,destination)
  relative=Path(result['report']).resolve().relative_to(self.root.resolve())
  self.assertTrue(verify_comparison(destination,destination/relative,result['report_sha256'])['valid'])
 def test_registered_orthographic_cameras_match_anchor_pixels_and_expire(self):
  request=self.projection_request()
  cameras=prepare_cameras(self.root,dict(source=request['source'],source_sha256=request['source_sha256'],
       reference=request['reference'],reference_sha256=request['reference_sha256'],output='nbt_models/_workspaces/reference-cameras/example'))
  reference=load_reference(request['reference'],request['reference_sha256'])
  anchor=reference['anchors'][0]
  for name,entry in cameras['views'].items():
   camera=json.loads((Path(cameras['bundle']).parent/entry['file']).read_text(encoding='utf8'))[0]
   self.assertEqual(camera['projection'],'orthographic');self.assertEqual(camera['ortho_height'],32)
   eye,target,up=camera['eye'],camera['target'],camera['up']
   forward=[target[i]-eye[i] for i in range(3)];length=sum(v*v for v in forward)**.5;forward=[v/length for v in forward]
   right=[forward[1]*up[2]-forward[2]*up[1],forward[2]*up[0]-forward[0]*up[2],forward[0]*up[1]-forward[1]*up[0]]
   delta=[anchor['world'][i]-target[i] for i in range(3)]
   projected=[32+2*sum(delta[i]*right[i] for i in range(3)),32-2*sum(delta[i]*up[i] for i in range(3))]
   for observed,expected in zip(projected,anchor['views'][name]):self.assertAlmostEqual(observed,expected)
  self.assertTrue(verify_cameras(self.root,cameras['bundle'],cameras['bundle_sha256'])['valid'])
  Path(request['source']).write_bytes(Path(request['source']).read_bytes()+b' ')
  with self.assertRaisesRegex(ValueError,'变化|哈希'):verify_cameras(self.root,cameras['bundle'],cameras['bundle_sha256'])
 def test_rehashed_reference_evidence_cannot_claim_approval(self):
  request=self.projection_request();result=compare_reference(self.root,request)
  file=Path(result['report']);data=json.loads(file.read_text(encoding='utf8'));data['approval_created']=True
  file.write_text(json.dumps(data),encoding='utf8')
  with self.assertRaisesRegex(ValueError,'格式|批准'):verify_comparison(self.root,file,hashlib.sha256(file.read_bytes()).hexdigest())
  cameras=prepare_cameras(self.root,dict(source=request['source'],source_sha256=request['source_sha256'],reference=request['reference'],
      reference_sha256=request['reference_sha256'],output='nbt_models/_workspaces/reference-cameras/forged'))
  file=Path(cameras['bundle']);data=json.loads(file.read_text(encoding='utf8'));data['approval_created']=True
  file.write_text(json.dumps(data),encoding='utf8')
  with self.assertRaisesRegex(ValueError,'格式|批准'):verify_cameras(self.root,file,hashlib.sha256(file.read_bytes()).hexdigest())
 def test_cli_prepares_and_verifies_registered_material_cameras(self):
  request=self.projection_request()
  request=dict(source=request['source'],source_sha256=request['source_sha256'],reference=request['reference'],
               reference_sha256=request['reference_sha256'],output='nbt_models/_workspaces/reference-cameras/cli')
  file=self.root/'cameras-request.json';file.write_text(json.dumps(request),encoding='utf8')
  base=['node',str(ROOT/'scripts/cli.mjs'),'--workspace',str(self.root),'reference']
  run=subprocess.run([*base,'cameras','--request',str(file)],capture_output=True,text=True,encoding='utf8',timeout=45)
  self.assertEqual(run.returncode,0,run.stdout+run.stderr);result=json.loads(run.stdout)
  checked=subprocess.run([*base,'verify-cameras','--bundle',result['bundle'],'--sha256',result['bundle_sha256']],
                         capture_output=True,text=True,encoding='utf8',timeout=45)
  self.assertEqual(checked.returncode,0,checked.stdout+checked.stderr);self.assertTrue(json.loads(checked.stdout)['valid'])
  from nbt_review.reference_camera import checked_registered_camera
  camera=Path(result['bundle']).parent/result['views']['front']['file']
  with self.assertRaisesRegex(ValueError,'尺寸'):checked_registered_camera(self.root,result['bundle'],result['bundle_sha256'],camera,128,64)
 def test_registered_cameras_bind_explicit_lighting_parameters(self):
  request=self.projection_request()
  lighting=dict(direction=[.3,.8,.2],temperature_kelvin=4200,background=[.2,.3,.4],exposure=1.1)
  result=prepare_cameras(self.root,dict(source=request['source'],source_sha256=request['source_sha256'],
       reference=request['reference'],reference_sha256=request['reference_sha256'],lighting_options=lighting,
       output='nbt_models/_workspaces/reference-cameras/lighting'))
  camera=json.loads((Path(result['bundle']).parent/result['views']['front']['file']).read_text(encoding='utf8'))[0]
  self.assertEqual(camera['lighting_options'],lighting)
  self.assertTrue(verify_cameras(self.root,result['bundle'],result['bundle_sha256'])['valid'])
 def test_render_publication_rejects_stale_registered_camera_inputs(self):
  from nbt_task import inspect_source,publish_render_manifest
  request=self.projection_request()
  cameras=prepare_cameras(self.root,dict(source=request['source'],source_sha256=request['source_sha256'],
       reference=request['reference'],reference_sha256=request['reference_sha256'],output='nbt_models/_workspaces/reference-cameras/stale'))
  camera=Path(cameras['bundle']).parent/cameras['views']['front']['file']
  snapshot=inspect_source(request['source']);output=self.root/'render';output.mkdir()
  manifest=output/'render_manifest.json';manifest.write_text(json.dumps(dict(status='awaiting_input_check',images=[],duration_ms=0,width=64,height=64,
      cameras_sha256=hashlib.sha256(camera.read_bytes()).hexdigest())),encoding='utf8')
  reference=load_reference(request['reference'],request['reference_sha256'])
  image=Path(request['reference']).parent/reference['views']['front']['file'];image.write_bytes(image.read_bytes()+b'changed')
  with self.assertRaisesRegex(ValueError,'变化|哈希'):
   publish_render_manifest(output,Path(request['source']),snapshot,camera_file=camera,
      camera_bundle=Path(cameras['bundle']),camera_bundle_sha256=cameras['bundle_sha256'],workspace=self.root)
  self.assertEqual(json.loads(manifest.read_text(encoding='utf8'))['status'],'failed')
 def test_render_publication_rejects_camera_file_changed_after_render(self):
  from nbt_task import inspect_source,publish_render_manifest
  request=self.projection_request();snapshot=inspect_source(request['source'])
  camera=self.root/'camera.json';camera.write_text('[]',encoding='utf8');original=hashlib.sha256(camera.read_bytes()).hexdigest()
  output=self.root/'render';output.mkdir();manifest=output/'render_manifest.json'
  manifest.write_text(json.dumps(dict(status='awaiting_input_check',images=[],duration_ms=0,cameras_sha256=original)),encoding='utf8')
  camera.write_text('[1]',encoding='utf8')
  with self.assertRaisesRegex(ValueError,'camera|相机'):publish_render_manifest(output,Path(request['source']),snapshot,camera_file=camera)
  self.assertEqual(json.loads(manifest.read_text(encoding='utf8'))['status'],'failed')
 def test_shared_cli_registers_and_frozen_workspace_compiles_loft(self):
  from nbt_exposure import apply
  request=self.root/'register.json';request.write_text(json.dumps(self.request),encoding='utf8')
  run=subprocess.run(['node',str(ROOT/'scripts/cli.mjs'),'--workspace',str(self.root),'reference','register','--request',str(request)],
                     capture_output=True,text=True,encoding='utf8',timeout=45)
  self.assertEqual(run.returncode,0,run.stdout+run.stderr)
  registered=json.loads(run.stdout)
  fit=dict(reference=registered['manifest'],reference_sha256=registered['manifest_sha256'],part='tower',rows=self.rows,sample_step=1,vertices=16)
  request=self.root/'fit.json';request.write_text(json.dumps(fit),encoding='utf8')
  apply(self.root);facade=self.root/'.agents/skills/nbtcreator-workspace/nbt.py'
  output='nbt_models/_workspaces/reference-fits/tower.json'
  run=subprocess.run([sys.executable,str(facade),'reference','fit','--request',str(request),'--output',output],
                     cwd=self.root,capture_output=True,text=True,encoding='utf8',timeout=45)
  self.assertEqual(run.returncode,0,run.stdout+run.stderr)
  result=json.loads(run.stdout);data=json.loads((self.root/output).read_text(encoding='utf8'))
  self.assertEqual(result['sections'],9);self.assertEqual(data['geometry']['shape'],'loft')
  self.assertEqual(data['reference_sha256'],registered['manifest_sha256'])
  checked=subprocess.run([sys.executable,str(facade),'reference','verify-fit','--fit',output,'--sha256',result['sha256']],
                         cwd=self.root,capture_output=True,text=True,encoding='utf8',timeout=45)
  self.assertEqual(checked.returncode,0,checked.stdout+checked.stderr);self.assertTrue(json.loads(checked.stdout)['valid'])
 def test_cli_comparison_can_be_verified_and_detects_stale_input(self):
  request=self.projection_request();file=self.root/'compare.json';file.write_text(json.dumps(request),encoding='utf8')
  base=['node',str(ROOT/'scripts/cli.mjs'),'--workspace',str(self.root),'reference']
  run=subprocess.run([*base,'compare','--request',str(file)],capture_output=True,text=True,encoding='utf8',timeout=45)
  self.assertEqual(run.returncode,0,run.stdout+run.stderr)
  result=json.loads(run.stdout)
  check=subprocess.run([*base,'verify','--report',result['report'],'--sha256',result['report_sha256']],
                       capture_output=True,text=True,encoding='utf8',timeout=45)
  self.assertEqual(check.returncode,0,check.stdout+check.stderr);self.assertTrue(json.loads(check.stdout)['valid'])
  mask=self.root/request['masks']['front']['file'];mask.write_bytes(mask.read_bytes()+b'changed')
  stale=subprocess.run([*base,'verify','--report',result['report'],'--sha256',result['report_sha256']],
                       capture_output=True,text=True,encoding='utf8',timeout=45)
  self.assertNotEqual(stale.returncode,0)


if __name__=='__main__':unittest.main(verbosity=2)
