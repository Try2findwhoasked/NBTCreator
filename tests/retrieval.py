from pathlib import Path
import hashlib
import json
import sys
import tempfile
import unittest
import shutil
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_retrieval import dispatch
from nbt_components import store,load,update
from nbt_structure_agent import build

def strings(value):
 if isinstance(value,str):return [value]
 if isinstance(value,list):return [text for item in value for text in strings(item)]
 if isinstance(value,dict):return [text for item in value.values() for text in strings(item)]
 return []

class Retrieval(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.query=dict(workflow='component',query='水渠桥 支承',size=[4,6,10]);self.asset=store(self.root,dict(schema_version=1,name='水渠桥',tags=['支承','水渠'],size=[9,4,3],anchor=[4,0,1],palette=['stone_bricks'],blocks=[[x,0,1,0,False] for x in range(9)]));self.original=(self.root/'.nbtcreator/components'/f'{self.asset["id"]}.json').read_bytes()
  content='## 桥面支承\n水渠桥必须在两侧有支承；保留桥下排水空间。\n\n## 无关的仓库\n仓库储物架。\n';self.docid=hashlib.sha256(content.encode()).hexdigest();base=self.root/'.nbtcreator/internal-ai';(base/'knowledge').mkdir(parents=True);(base/'knowledge'/f'{self.docid}.md').write_bytes(content.encode('utf8'));self.config=dict(schema_version=1,documents=[dict(id=self.docid,label='桥梁规范',path=f'knowledge/{self.docid}.md')],workflows=dict(component=dict(knowledge=[self.docid]),prompt=dict(knowledge=[])));(base/'config.json').write_text(json.dumps(self.config),encoding='utf8')
 def call(self,action,**request):return dispatch(self.root,action,dict(self.query,**request))
 def bundle(self):
  found=self.call('search');return self.call('bundle',selected=[found['assets'][0]['id'],found['knowledge'][0]['id']])
 def test_search_suggests_actual_rotation_and_only_task_selected_references(self):
  result=self.call('search');self.assertEqual(result['assets'][0]['rotations'],[1]);self.assertEqual(result['assets'][0]['asset_id'],self.asset['id']);self.assertEqual(result['knowledge'][0]['label'],'桥梁规范');self.assertIn('桥下排水',result['knowledge'][0]['text']);self.assertEqual(self.call('search',size=[2,3,2])['assets'],[]);self.assertEqual(self.call('search',workflow='prompt')['knowledge'],[])
 def test_bundle_is_hash_bound_and_sends_citable_fragments_without_local_paths_or_voxels(self):
  bundle=self.bundle();read=self.call('read',id=bundle['id'],sha256=bundle['sha256']);self.assertEqual(read['sources'][0]['citation'],'R1');self.assertEqual(read['sources'][1]['line_start'],1);self.assertTrue(all(str(self.root) not in text for text in strings(read)));self.assertNotIn('blocks',read['references'][0]);self.assertFalse(read['asset_written']);self.assertEqual(self.original,(self.root/'.nbtcreator/components'/f'{self.asset["id"]}.json').read_bytes())
 def test_revoked_knowledge_and_changed_content_refuse_old_bundle(self):
  bundle=self.bundle();self.config['workflows']['component']['knowledge']=[];(self.root/'.nbtcreator/internal-ai/config.json').write_text(json.dumps(self.config),encoding='utf8')
  with self.assertRaisesRegex(ValueError,'取消'):self.call('read',id=bundle['id'],sha256=bundle['sha256'])
 def test_archived_assets_and_wrong_workflow_or_tampered_bundle_are_rejected(self):
  bundle=self.bundle()
  with self.assertRaisesRegex(ValueError,'工作流'):self.call('read',workflow='prompt',id=bundle['id'],sha256=bundle['sha256'])
  with self.assertRaises(ValueError):self.call('read',id='../secret',sha256=bundle['sha256'])
  file=self.root/'.nbtcreator/retrieval/bundles'/f'{bundle["id"]}.json';original=file.read_bytes();file.write_bytes(original+b' ')
  with self.assertRaisesRegex(ValueError,'已变化'):self.call('read',id=bundle['id'],sha256=bundle['sha256'])
  file.write_bytes(original);update(self.root,self.asset['id'],archived=True)
  with self.assertRaisesRegex(ValueError,'回收'):self.call('read',id=bundle['id'],sha256=bundle['sha256'])
 def test_source_read_requires_current_selection_and_actual_hash(self):
  found=self.call('search');source=found['knowledge'][0];doc=self.call('source',document_id=source['document_id'],sha256=source['sha256']);self.assertIn('无关的仓库',doc['text'])
  with self.assertRaises(ValueError):self.call('source',workflow='prompt',document_id=self.docid,sha256=self.docid)
 def test_rotated_recolored_asset_reuse_generates_actual_geometry_and_preserves_original(self):
  result=build(self.root,dict(name='金色水渠桥',size=self.query['size'],placements=[dict(id=self.asset['id'],content_sha256=self.asset['content_sha256'],position=[1,0,4],quarter_turns=1,material_map={'minecraft:stone_bricks':'gold_block'})]));self.assertEqual(result['palette'],['minecraft:gold_block']);self.assertEqual(len(result['blocks']),9);self.assertEqual({b[2] for b in result['blocks']},set(range(9)));self.assertEqual(load(self.root,self.asset['id'])['palette'],['minecraft:stone_bricks']);self.assertEqual(self.original,(self.root/'.nbtcreator/components'/f'{self.asset["id"]}.json').read_bytes())
 def test_invalid_materials_and_unselected_or_empty_bundle_are_rejected(self):
  with self.assertRaises(ValueError):self.call('bundle',selected=[])
  with self.assertRaises(ValueError):self.call('bundle',selected=['asset:'+'0'*32])
  with self.assertRaises(ValueError):build(self.root,dict(name='无效',size=[4,6,10],placements=[dict(id=self.asset['id'],content_sha256=self.asset['content_sha256'],position=[1,0,4],quarter_turns=1,material_map={'stone_bricks':'not_a_block'})]))
 def test_relative_bundle_survives_relocation_and_forged_line_metadata_is_rejected(self):
  bundle=self.bundle();file=self.root/'.nbtcreator/retrieval/bundles'/f'{bundle["id"]}.json';self.assertTrue(all(str(self.root) not in text for text in strings(json.loads(file.read_bytes()))));destination=self.root/'relocated';shutil.copytree(self.root/'.nbtcreator',destination/'.nbtcreator');moved=dispatch(destination,'read',dict(workflow='component',id=bundle['id'],sha256=bundle['sha256']));self.assertEqual(moved['references'][0]['id'],self.asset['id']);forged=json.loads(file.read_bytes());forged['sources'][1]['line_start']+=1;raw=json.dumps(forged).encode();file.write_bytes(raw)
  with self.assertRaisesRegex(ValueError,'片段'):self.call('read',id=bundle['id'],sha256=hashlib.sha256(raw).hexdigest())
if __name__=='__main__':unittest.main(verbosity=2)
