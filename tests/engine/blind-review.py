"""Anonymous same-camera review evidence and stale-input regressions."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_assembly import Volume
from nbt_snbt import save_snbt
from nbt_task import write_snapshot
from nbt_review.blind_review import prepare_review,record_review,verify_review


def sha(file):return hashlib.sha256(Path(file).read_bytes()).hexdigest()
def write(file,data):Path(file).write_text(json.dumps(data,ensure_ascii=False),encoding='utf8')


class BlindReview(unittest.TestCase):
 def setUp(self):
  temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name).resolve()
  self.camera=self.root/'cameras.json';self.view=dict(id='front',role='正面',eye=[2,2,-10],target=[2,2,2],up=[0,1,0],fov=60,
      projection='orthographic',ortho_height=8,lighting='day',layer='all',cuts=[])
  write(self.camera,[self.view]);self.manifests=[]
  for i,color in enumerate(('red','blue')):
   folder=self.root/f'nbt_models/standalone/审阅/v0{i+1}';source=folder/'master/model.snbt';source.parent.mkdir(parents=True)
   model=Volume((5,5,5));model.put((2,2,2),'stone' if i==0 else 'gold_block');save_snbt(source,model,set())
   output=self.root/f'render-{i}';output.mkdir();snapshot=output/'snapshot.json';data=write_snapshot(source,snapshot)
   image=output/'front.png';Image.new('RGB',(64,64),color).save(image)
   meta=dict(id='front',camera={k:self.view[k] for k in ('eye','target','up','fov','projection','ortho_height')},
             requested_view=self.view,cuts=[],layer='all',lighting='day',quality='balanced',pixel_ratio=1,width=64,height=64,
             source_sha256=data['source_sha256'],geometry_sha256=data['geometry_sha256'],snapshot_sha256=sha(snapshot),
             image='front.png',image_sha256=sha(image))
   write(output/'front.json',meta)
   manifest=output/'render_manifest.json';write(manifest,dict(status='complete',source=str(source),source_sha256=data['source_sha256'],
      geometry_sha256=data['geometry_sha256'],snapshot_file='snapshot.json',snapshot_sha256=sha(snapshot),camera_file=str(self.camera),
      cameras_sha256=sha(self.camera),width=64,height=64,quality='balanced',pixel_ratio=1,views=[self.view],
      images=[dict(image='front.png',metadata='front.json',sha256=sha(image),metadata_sha256=sha(output/'front.json'))]))
   self.manifests.append(manifest)
 def request(self):
  return dict(renders=[dict(manifest=str(file),sha256=sha(file)) for file in self.manifests],scope='比较整体轮廓',
              crop=[8,8,56,56],output='nbt_models/_workspaces/reference-reviews/blind')
 def test_anonymous_pack_preserves_pixels_and_binds_all_inputs(self):
  result=prepare_review(self.root,self.request());public=Path(result['public']);data=json.loads(public.read_text(encoding='utf8'))
  raw=public.read_text(encoding='utf8')
  for source in self.manifests:self.assertNotIn(str(source),raw)
  self.assertNotIn('source_sha256',raw);self.assertEqual(data['scope'],'比较整体轮廓')
  self.assertEqual(data['views'][0]['images']['A']['size'],[48,48])
  colors=set()
  for label in ('A','B'):
   file=public.parent/data['views'][0]['images'][label]['file']
   with Image.open(file) as image:colors.add(image.convert('RGB').getpixel((1,1)))
  self.assertEqual(colors,{(255,0,0),(0,0,255)})
  self.assertTrue(verify_review(self.root,result['binding'],result['binding_sha256'])['valid'])
  Path(self.manifests[0].parent/'front.png').write_bytes(b'changed')
  with self.assertRaisesRegex(ValueError,'变化|哈希'):verify_review(self.root,result['binding'],result['binding_sha256'])
 def test_mismatched_camera_or_changed_render_is_rejected_before_output(self):
  data=json.loads(self.manifests[1].read_text(encoding='utf8'));data['views'][0]['ortho_height']=9;write(self.manifests[1],data)
  with self.assertRaisesRegex(ValueError,'相机|机位'):prepare_review(self.root,self.request())
  self.assertFalse((self.root/self.request()['output']).exists())
 def test_blind_observations_are_version_bound_and_never_approval(self):
  pack=prepare_review(self.root,self.request())
  request=dict(public=pack['public'],public_sha256=pack['public_sha256'],decision='A',actor='agent',
               observations=[dict(view='view-01',note='左侧轮廓更接近',remaining='顶部细节未核对')],
               output='nbt_models/_workspaces/reference-reviews/observation.json')
  result=record_review(self.root,request);self.assertFalse(result['approval_created'])
  self.assertTrue(verify_review(self.root,pack['binding'],pack['binding_sha256'],result['record'],result['record_sha256'])['valid'])
  image=Path(pack['public']).parent/'A/view-01.png';image.write_bytes(b'changed')
  with self.assertRaisesRegex(ValueError,'变化|哈希'):verify_review(self.root,pack['binding'],pack['binding_sha256'],result['record'],result['record_sha256'])
 def test_review_observation_can_record_actionable_context(self):
  pack=prepare_review(self.root,self.request())
  request=dict(public=pack['public'],public_sha256=pack['public_sha256'],decision='inconclusive',actor='agent',
   observations=[dict(view='view-01',note='槽底看起来像贴条',remaining='尚未核对侧面',part='东侧槽口',
                      reference_region='原参考正面左下角',expected='槽底退入并保留背板',recheck='同机位及侧面剖切')],
   output='nbt_models/_workspaces/reference-reviews/actionable.json')
  result=record_review(self.root,request)
  self.assertTrue(verify_review(self.root,pack['binding'],pack['binding_sha256'],result['record'],result['record_sha256'])['valid'])
  self.assertFalse(result['approval_created'])
  saved=json.loads(Path(result['record']).read_text(encoding='utf8'))['observations'][0]
  self.assertEqual(saved['expected'],'槽底退入并保留背板')
  request['output']='nbt_models/_workspaces/reference-reviews/invalid-actionable.json'
  request['observations'][0]['recheck']='  '
  with self.assertRaisesRegex(ValueError,'观察字段'):record_review(self.root,request)
  self.assertFalse((self.root/request['output']).exists())
 def test_observation_reference_region_binds_registered_image_and_bounds(self):
  from nbt_reference_views import register_reference
  folder=self.root/'reference-input';folder.mkdir();views={}
  for name,u,v in [('front','x','-y'),('side','z','-y'),('top','x','z')]:
   file=folder/(name+'.png');Image.new('RGB',(64,64),'white').save(file)
   views[name]=dict(image=str(file),sha256=sha(file),origin=[0,63] if name!='top' else [0,0],
    pixels_per_block=1,u_axis=u,v_axis=v,origin_type='original',basis='合成参考')
  ref=register_reference(self.root,dict(output='nbt_models/_workspaces/reference-views/review-ref',views=views,
   anchors=[dict(id='origin',part='tower',world=[1,1,1],basis='合成锚点',confidence='measured',uncertainty=0,
    views=dict(front=[1,62],side=[1,62],top=[1,1]))],assumptions=[]))
  pack=prepare_review(self.root,self.request())
  region=dict(manifest=ref['manifest'],sha256=ref['manifest_sha256'],view='front',lo=[2,3],hi=[20,30])
  request=dict(public=pack['public'],public_sha256=pack['public_sha256'],decision='inconclusive',actor='agent',
   observations=[dict(view='view-01',note='观察槽口',remaining='未复核',reference=region)],
   output='nbt_models/_workspaces/reference-reviews/region.json')
  result=record_review(self.root,request)
  self.assertTrue(verify_review(self.root,pack['binding'],pack['binding_sha256'],result['record'],result['record_sha256'])['valid'])
  saved=json.loads(Path(result['record']).read_text(encoding='utf8'))['observations'][0]['reference']
  self.assertFalse(Path(saved['manifest']).is_absolute())
  from nbt_exposure import apply
  apply(self.root);facade=self.root/'.agents/skills/nbtcreator-workspace/nbt.py'
  cli_request=dict(request,output='nbt_models/_workspaces/reference-reviews/region-cli.json')
  request_file=self.root/'region-request.json';write(request_file,cli_request)
  run=subprocess.run([sys.executable,str(facade),'reference','review-record','--request',str(request_file)],
   cwd=self.root,capture_output=True,text=True,encoding='utf8',timeout=60)
  self.assertEqual(run.returncode,0,run.stdout+run.stderr);cli_record=json.loads(run.stdout)
  self.assertTrue(verify_review(self.root,pack['binding'],pack['binding_sha256'],cli_record['record'],cli_record['record_sha256'])['valid'])
  from nbt_reference_views import load_reference
  record_file=Path(result['record']);original=record_file.read_bytes();calls=0
  def mutate_during_reference_verification(*args):
   nonlocal calls
   value=load_reference(*args);calls+=1
   if calls==2:record_file.write_bytes(original+b' ')
   return value
  with patch('nbt_reference_views.load_reference',side_effect=mutate_during_reference_verification):
   with self.assertRaisesRegex(ValueError,'记录.*变化'):verify_review(self.root,pack['binding'],pack['binding_sha256'],result['record'],result['record_sha256'])
  record_file.write_bytes(original)
  request['output']='nbt_models/_workspaces/reference-reviews/out-of-bounds.json';region['hi']=[64,30]
  with self.assertRaisesRegex(ValueError,'区域|范围'):record_review(self.root,request)
  self.assertFalse((self.root/request['output']).exists())
  image=Path(ref['manifest']).parent/'images/front.png';image.write_bytes(image.read_bytes()+b'changed')
  with self.assertRaisesRegex(ValueError,'变化|哈希'):verify_review(self.root,pack['binding'],pack['binding_sha256'],result['record'],result['record_sha256'])
 def test_render_metadata_changes_are_rejected_even_when_images_are_unchanged(self):
  meta=self.manifests[0].parent/'front.json';data=json.loads(meta.read_text(encoding='utf8'));data['camera']['ortho_height']=99;write(meta,data)
  with self.assertRaisesRegex(ValueError,'元数据|哈希'):prepare_review(self.root,self.request())
 def test_nonfinite_camera_coordinates_never_match(self):
  from nbt_review.blind_review import _camera_matches
  camera={k:self.view[k] for k in ('eye','target','up','fov','projection','ortho_height')}
  camera['eye']=[float('inf'),2,-10]
  self.assertFalse(_camera_matches(camera,camera))
 def test_anonymized_png_removes_identifying_metadata(self):
  from PIL.PngImagePlugin import PngInfo
  image=self.manifests[0].parent/'front.png';info=PngInfo();info.add_text('source','PRIVATE_MODEL_ID')
  Image.new('RGB',(64,64),'red').save(image,pnginfo=info)
  metadata=self.manifests[0].parent/'front.json';data=json.loads(metadata.read_text(encoding='utf8'));data['image_sha256']=sha(image);write(metadata,data)
  manifest=json.loads(self.manifests[0].read_text(encoding='utf8'));manifest['images'][0].update(sha256=sha(image),metadata_sha256=sha(metadata));write(self.manifests[0],manifest)
  pack=prepare_review(self.root,self.request());public=Path(pack['public']);record=json.loads(public.read_text(encoding='utf8'))
  for label in ('A','B'):
   self.assertNotIn(b'PRIVATE_MODEL_ID',(public.parent/record['views'][0]['images'][label]['file']).read_bytes())
  self.assertNotIn('PRIVATE_MODEL_ID',public.read_text(encoding='utf8'))
 def test_alpha_only_changes_are_visible_and_counted_in_the_difference(self):
  for index,alpha in enumerate((255,0)):
   image=self.manifests[index].parent/'front.png';Image.new('RGBA',(64,64),(100,100,100,alpha)).save(image)
   metadata=self.manifests[index].parent/'front.json';data=json.loads(metadata.read_text(encoding='utf8'));data['image_sha256']=sha(image);write(metadata,data)
   manifest=json.loads(self.manifests[index].read_text(encoding='utf8'));manifest['images'][0].update(sha256=sha(image),metadata_sha256=sha(metadata));write(self.manifests[index],manifest)
  pack=prepare_review(self.root,self.request());public=Path(pack['public']);record=json.loads(public.read_text(encoding='utf8'))
  self.assertEqual(record['views'][0]['changed_pixels'],48*48)
  with Image.open(public.parent/record['views'][0]['images']['diff']['file']) as image:
   self.assertEqual(image.convert('RGBA').getpixel((1,1)),(255,0,255,255))
  self.assertTrue(verify_review(self.root,pack['binding'],pack['binding_sha256'])['valid'])
 def test_rehashed_forged_public_camera_is_detected(self):
  pack=prepare_review(self.root,self.request());public=Path(pack['public']);binding=Path(pack['binding'])
  data=json.loads(public.read_text(encoding='utf8'));data['views'][0]['settings']['camera']['ortho_height']=99;write(public,data)
  private=json.loads(binding.read_text(encoding='utf8'));private['public_sha256']=sha(public);write(binding,private)
  with self.assertRaisesRegex(ValueError,'相机|机位'):verify_review(self.root,binding,sha(binding))
 def test_rehashed_forged_difference_image_is_detected(self):
  pack=prepare_review(self.root,self.request());public=Path(pack['public']);binding=Path(pack['binding'])
  data=json.loads(public.read_text(encoding='utf8'));image=public.parent/data['views'][0]['images']['diff']['file']
  Image.new('RGBA',(48,48),(0,255,0,255)).save(image);data['views'][0]['images']['diff']['sha256']=sha(image);write(public,data)
  private=json.loads(binding.read_text(encoding='utf8'));private['public_sha256']=sha(public);write(binding,private)
  with self.assertRaisesRegex(ValueError,'差异'):verify_review(self.root,binding,sha(binding))
 def test_rehashed_observation_cannot_claim_user_approval(self):
  pack=prepare_review(self.root,self.request())
  request=dict(public=pack['public'],public_sha256=pack['public_sha256'],decision='A',actor='agent',
               observations=[dict(view='view-01',note='候选比较',remaining='')],
               output='nbt_models/_workspaces/reference-reviews/forged.json')
  result=record_review(self.root,request);file=Path(result['record']);data=json.loads(file.read_text(encoding='utf8'))
  data['approval_created']=True;write(file,data)
  with self.assertRaisesRegex(ValueError,'记录|批准'):verify_review(self.root,pack['binding'],pack['binding_sha256'],file,sha(file))
 def test_observation_changed_during_verification_is_rejected(self):
  from nbt_review.blind_review import _pair
  pack=prepare_review(self.root,self.request())
  request=dict(public=pack['public'],public_sha256=pack['public_sha256'],decision='A',actor='agent',
               observations=[dict(view='view-01',note='候选比较',remaining='')],
               output='nbt_models/_workspaces/reference-reviews/race.json')
  result=record_review(self.root,request);file=Path(result['record']);calls=0
  def mutate(*args):
   nonlocal calls
   value=_pair(*args);calls+=1
   if calls==2:file.write_bytes(file.read_bytes()+b' ')
   return value
  with patch('nbt_review.blind_review._pair',side_effect=mutate):
   with self.assertRaisesRegex(ValueError,'记录.*变化'):verify_review(self.root,pack['binding'],pack['binding_sha256'],file,result['record_sha256'])
 def test_shared_and_frozen_cli_keep_review_and_approval_separate(self):
  from nbt_exposure import apply
  request=self.root/'prepare.json';write(request,self.request())
  base=['node',str(ROOT/'scripts/cli.mjs'),'--workspace',str(self.root),'reference']
  run=subprocess.run([*base,'review-prepare','--request',str(request)],capture_output=True,text=True,encoding='utf8',timeout=45)
  self.assertEqual(run.returncode,0,run.stdout+run.stderr);pack=json.loads(run.stdout)
  observation=dict(public=pack['public'],public_sha256=pack['public_sha256'],decision='tie',actor='agent',
     observations=[dict(view='view-01',note='均需继续检查',remaining='顶部未见')],
     output='nbt_models/_workspaces/reference-reviews/frozen-observation.json')
  request=self.root/'record.json';write(request,observation);apply(self.root)
  facade=self.root/'.agents/skills/nbtcreator-workspace/nbt.py'
  run=subprocess.run([sys.executable,str(facade),'reference','review-record','--request',str(request)],
                     cwd=self.root,capture_output=True,text=True,encoding='utf8',timeout=45)
  self.assertEqual(run.returncode,0,run.stdout+run.stderr);record=json.loads(run.stdout);self.assertFalse(record['approval_created'])
  verification=dict(binding=pack['binding'],binding_sha256=pack['binding_sha256'],record=record['record'],record_sha256=record['record_sha256'])
  request=self.root/'verify.json';write(request,verification)
  run=subprocess.run([*base,'review-verify','--request',str(request)],capture_output=True,text=True,encoding='utf8',timeout=45)
  self.assertEqual(run.returncode,0,run.stdout+run.stderr);self.assertTrue(json.loads(run.stdout)['valid'])


if __name__=='__main__':unittest.main(verbosity=2)
