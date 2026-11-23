"""Parametric UV stencil components and explicit asymmetric end rules."""
import sys
import tempfile
import unittest
import json
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_agent.structure import dispatch,build


class CurveStencils(unittest.TestCase):
 def setUp(self):
  temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name).resolve()
 def compile(self,profile,size,**form):
  args=dict(kind='curve_stencil',size=size,material='stone',form=dict(profile=profile,**form))
  result=dispatch(self.root,'parametric_compile',args);component=build(self.root,result['spec'])
  return result,component,{(block[0],block[1]) for block in component['blocks']}
 def test_all_six_profiles_are_deterministic_flat_candidates(self):
  cases=[('curve_ring_segment',[12,5,1],dict(curve_width=3,curve_offset=1)),
   ('curve_dark_seam',[12,3,1],dict(curve_width=1,curve_offset=1)),
   ('curve_rib',[5,12,1],dict(curve_width=2,curve_offset=1)),
   ('curve_window_column',[6,14,1],dict(curve_width=3,curve_offset=1,curve_window_height=3,curve_gap=1,curve_count=3,curve_start=0)),
   ('curve_diagonal_band',[12,9,1],dict(curve_width=2,curve_start=1,curve_rise=4)),
   ('curve_skirt_segment',[12,6,1],dict(curve_left_bottom=0,curve_right_bottom=1,curve_left_top=3,curve_right_top=2))]
  for profile,size,form in cases:
   with self.subTest(profile=profile):
    first,component,points=self.compile(profile,size,**form);second,copy,_=self.compile(profile,size,**form)
    self.assertTrue(points);self.assertEqual(first['content_sha256'],second['content_sha256'])
    self.assertEqual(component['content_sha256'],copy['content_sha256']);self.assertEqual(component['size'],size)
    self.assertTrue(all(block[2]==0 for block in component['blocks']))
    self.assertFalse(first['approval_created']);self.assertEqual(first['verification']['design'],'pending_visual_review')
 def test_diagonal_direction_and_end_caps_are_explicit(self):
  _,_,up=self.compile('curve_diagonal_band',[9,7,1],curve_width=2,curve_start=0,curve_rise=4)
  _,_,down=self.compile('curve_diagonal_band',[9,7,1],curve_width=2,curve_start=4,curve_rise=-4)
  self.assertIn((0,0),up);self.assertIn((8,4),up);self.assertIn((0,4),down);self.assertIn((8,0),down)
  _,_,square=self.compile('curve_ring_segment',[12,4,1],curve_width=4,curve_offset=0)
  _,_,capped=self.compile('curve_ring_segment',[12,4,1],curve_width=4,curve_offset=0,
   curve_cap_start='low_step',curve_cap_end='high_step',curve_cap_length=2)
  self.assertLess(len(capped),len(square));self.assertNotIn((0,0),capped);self.assertNotIn((11,3),capped)
  self.assertIn((6,0),capped);self.assertIn((6,3),capped)
 def test_window_rhythm_and_skirt_asymmetry_are_preserved(self):
  _,_,windows=self.compile('curve_window_column',[6,14,1],curve_width=2,curve_offset=1,
   curve_window_height=3,curve_gap=1,curve_count=3,curve_start=0)
  self.assertEqual({y for _,y in windows},{0,1,2,4,5,6,8,9,10})
  _,_,skirt=self.compile('curve_skirt_segment',[12,6,1],curve_left_bottom=0,curve_right_bottom=1,curve_left_top=3,curve_right_top=2)
  self.assertIn((0,0),skirt);self.assertNotIn((0,5),skirt);self.assertIn((9,5),skirt);self.assertNotIn((10,5),skirt)
 def test_invalid_shapes_never_clip_or_guess(self):
  cases=[('curve_diagonal_band',[6,4,1],dict(curve_width=2,curve_start=2,curve_rise=3)),
   ('curve_window_column',[5,5,1],dict(curve_width=2,curve_offset=0,curve_window_height=3,curve_gap=1,curve_count=2,curve_start=0)),
   ('curve_ring_segment',[6,4,2],dict(curve_width=2,curve_offset=0)),
   ('curve_rib',[4,6,1],dict(curve_width=2,curve_offset=3)),
   ('curve_skirt_segment',[6,4,1],dict(curve_left_bottom=4,curve_right_bottom=3,curve_left_top=0,curve_right_top=0)),
   ('curve_ring_segment',[6,4,1],dict(curve_width=3,curve_offset=0,curve_cap_start='low_step',curve_cap_end='high_step',curve_cap_length=4)),
   ('curve_ring_segment',[6,4,1],dict(curve_width=1,curve_offset=0,curve_cap_start='low_step',curve_cap_length=1)),
   ('curve_rib',[4,6,1],dict(curve_width=2,curve_offset=1,curve_rise=2))]
  for profile,size,form in cases:
   with self.subTest(profile=profile,form=form):
    with self.assertRaises(ValueError):self.compile(profile,size,**form)
 def test_flat_stencil_cannot_claim_support_or_accept_air(self):
  args=dict(kind='curve_stencil',size=[6,4,1],material='air',form=dict(profile='curve_ring_segment',curve_width=2,curve_offset=0))
  with self.assertRaisesRegex(ValueError,'完整方块'):dispatch(self.root,'parametric_compile',args)
  args['material']='stone';args['style']='classic'
  with self.assertRaisesRegex(ValueError,'不使用'):dispatch(self.root,'parametric_compile',args)
 def test_compile_and_preview_share_the_same_schema_and_listing(self):
  from nbt_agent.structure import definitions
  definitions=definitions()
  self.assertEqual(definitions['parametric_compile']['parameters'],definitions['parametric_preview']['parameters'])
  listing=dispatch(self.root,'parametric_list',dict(kind='curve_stencil'))
  self.assertEqual(listing['kinds'][0]['mount'],'curve_uv_xy');self.assertEqual(listing['kinds'][0]['styles'],{})
  self.assertIn('curve_diagonal_band',listing['form_profiles']['curve_stencil'])
 def test_stencil_preview_is_a_real_unapproved_planar_candidate(self):
  args=dict(kind='curve_stencil',size=[12,8,1],material='stone',
            form=dict(profile='curve_diagonal_band',curve_width=2,curve_start=1,curve_rise=4))
  result=dispatch(self.root,'parametric_preview',args)
  self.assertTrue(Path(result['thumbnail']).is_file());self.assertTrue(Path(result['snapshot']).is_file())
  self.assertEqual(result['size'],[12,8,1]);self.assertFalse(result['approval_created'])
  self.assertEqual(result['verification']['design'],'pending_visual_review')
 def test_bundled_six_recipes_resolve_with_bound_content(self):
  import nbt_assets.libraries as libraries
  expected={'curve-ring-segment','curve-dark-seam','curve-vertical-rib','curve-window-column','curve-diagonal-band','curve-skirt-segment'}
  listing=libraries.browse(self.root);items=[row for row in listing['items'] if row['source_id']=='bundled' and row.get('arguments',{}).get('kind')=='curve_stencil']
  self.assertEqual({row['asset_id'] for row in items},expected)
  for row in items:
   with self.subTest(asset=row['id']):
    ref={key:row[key] for key in ('id','sha256','source_id','version','manifest_sha256')}
    source=libraries.read_asset(self.root,ref);component,_,arguments=libraries.materialize(self.root,source)
    resolved=libraries.asset_action(self.root,'resolve',dict(ref,content_sha256=component['content_sha256'],arguments=arguments))
    self.assertEqual(resolved['component']['content_sha256'],component['content_sha256'])
    self.assertFalse(resolved['approval_created'])
 def test_older_engine_rejects_new_library_before_decoding_assets(self):
  import nbt_assets.libraries as libraries
  from unittest.mock import patch
  raw=(ROOT/'.agents/skills/minecraft-nbt-modeler/assets/extension-library/library.json').read_bytes()
  with patch.object(libraries,'APP_VERSION',(4,3,0)):
   with self.assertRaises(libraries.LibraryError) as error:libraries.manifest(raw)
  self.assertEqual(error.exception.code,'INCOMPATIBLE')
 def test_bound_diagonal_recipe_composes_without_implicit_mirroring(self):
  import nbt_assets.libraries as libraries
  from nbt_mounting.curve_components import compose_curve_mask,verify_curve_mask
  import json
  row=next(item for item in libraries.browse(self.root)['items'] if item['source_id']=='bundled' and item['asset_id']=='curve-diagonal-band')
  ref={key:row[key] for key in ('id','sha256','source_id','version','manifest_sha256')}
  form=dict(row['arguments']['form'],curve_start=8,curve_rise=-7)
  data,_,args=libraries.materialize(self.root,libraries.read_asset(self.root,ref),dict(form=form))
  ref.update(arguments=args,content_sha256=data['content_sha256'])
  pairs=sorted({(block[3],block[4]) for block in data['blocks'] if block[2]==0})
  layer=dict(id='band',source=dict(kind='library',ref=ref),slice_z=0,origin=[0,0],counts=[1,1],spacing=[1,1],
   mapping=[dict(index=index,wall=wall,symbol='R') for index,wall in pairs],
   palette={'R':dict(kind='raise',state='stone_bricks',height=1,wall=False,role='band')})
  result=compose_curve_mask(self.root,dict(name='反向斜带',size=data['size'][:2],layers=[layer],overlaps=[],
   output='nbt_models/_workspaces/curve-masks/reverse-band'))
  rows=json.loads(Path(result['mask']).read_text(encoding='utf8'))['layers'][0]['rows']
  left=[y for y,line in enumerate(rows) if line[0]=='R'];right=[y for y,line in enumerate(rows) if line[-1]=='R']
  self.assertGreater(min(left),max(right));self.assertTrue(verify_curve_mask(self.root,result['mask'],result['mask_sha256'])['valid'])
  self.assertFalse(result['approval_created'])
 def test_shared_and_frozen_cli_compile_identical_stencil(self):
  from nbt_exposure import apply
  args=dict(kind='curve_stencil',name='可复现斜带',size=[18,12,1],material='stone_bricks',
   form=dict(profile='curve_diagonal_band',curve_width=3,curve_start=1,curve_rise=7))
  request=self.root/'stencil-request.json';request.write_text(json.dumps(args,ensure_ascii=False),encoding='utf8')
  common=['components','agent','--tool','parametric_compile','--request',str(request)]
  shared=subprocess.run(['node',str(ROOT/'scripts/cli.mjs'),'--workspace',str(self.root),*common],
   cwd=ROOT,capture_output=True,text=True,encoding='utf8',timeout=90)
  self.assertEqual(shared.returncode,0,shared.stdout+shared.stderr);before=json.loads(shared.stdout)['result']
  apply(self.root);facade=self.root/'.agents/skills/nbtcreator-workspace/nbt.py'
  frozen=subprocess.run([sys.executable,str(facade),*common],cwd=self.root,capture_output=True,text=True,encoding='utf8',timeout=90)
  self.assertEqual(frozen.returncode,0,frozen.stdout+frozen.stderr);after=json.loads(frozen.stdout)['result']
  self.assertEqual(after['content_sha256'],before['content_sha256']);self.assertEqual(after['recipe_sha256'],before['recipe_sha256'])
  self.assertFalse(after['approval_created'])


if __name__=='__main__':unittest.main(verbosity=2)
