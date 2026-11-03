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
 def test_existing_assets_are_composed_by_parameters_without_reemitting_voxels(self):
  result=dispatch(self.root,'structure_preview',{'spec':self.spec});item=dispatch(self.root,'structure_write',{k:result[k] for k in ['preview_id','preview_sha256']})
  spec=dict(name='组合双柱',size=[16,10,8],placements=[dict(id=item['id'],content_sha256=item['content_sha256'],position=[3,0,3]),dict(id=item['id'],content_sha256=item['content_sha256'],position=[11,0,3],quarter_turns=1)])
  built=build(self.root,spec);self.assertEqual(len(built['blocks']),len(load(self.root,item['id'])['blocks'])*2)
 def test_cli_agent_entry_uses_the_same_contract_and_does_not_require_electron(self):
  file=self.root/'request.json';file.write_text(json.dumps({'spec':self.spec}))
  run=subprocess.run([sys.executable,str(SCRIPTS/'nbt_components.py'),'--workspace',str(self.root),'agent','--tool','structure_preview','--request',str(file)],capture_output=True,text=True,encoding='utf8')
  self.assertEqual(run.returncode,0,run.stdout+run.stderr);result=json.loads(run.stdout)['result'];self.assertTrue(Path(result['thumbnail']).is_file())
  self.assertEqual(set(definitions()),{'structure_list','structure_read','structure_view','structure_preview','structure_write','structure_place'})


if __name__=='__main__':unittest.main(verbosity=2)
