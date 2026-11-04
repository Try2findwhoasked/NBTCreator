from pathlib import Path
import base64,json,sys,tempfile,unittest,shutil
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_asset_batches import dispatch
from nbt_refine import save_master
from nbt_assembly import Volume
import nbt_components as components

class Batches(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)/'workspace';self.root.mkdir();self.model=self.root/'input.master.json.gz';m=Volume((8,8,8));m.put((2,1,2),'stone');save_master(self.model,m,{(2,1,2)})
  self.component=dict(schema_version=1,name='石柱',tags=['批量'],size=[2,3,2],anchor=[0,0,0],palette=['stone'],blocks=[[0,0,0,0,True]])
 def imported(self):
  return dispatch(self.root,'import',dict(name='测试批次',files=[dict(name='pillar.component.json',base64=base64.b64encode(json.dumps(self.component).encode()).decode())],paths=[str(self.model)]))
 def test_mixed_import_list_and_full_read_keep_walls_and_originals(self):
  original=self.model.read_bytes();r=self.imported();self.assertEqual(r['count'],2,r);self.assertFalse(r['errors']);self.assertTrue((self.root/r['manifest']).exists());data=dispatch(self.root,'read',dict(id=r['id'],include_data=True));self.assertEqual(data['count'],2);model=next(i for i in data['items'] if i['type']=='model');self.assertEqual(model['data']['wall_positions'],[[2,1,2]]);component=next(i for i in r['entries'] if i['type']=='component');self.assertEqual(components.load(self.root,component['component_id'])['name'],'石柱');self.assertEqual(self.model.read_bytes(),original);self.assertEqual(dispatch(self.root,'list',{})['items'][0]['id'],r['id'])
 def test_json_list_portable_with_workspace_and_tamper_is_rejected(self):
  r=self.imported();other=Path(self.temp.name)/'moved';shutil.copytree(self.root,other);self.assertEqual(dispatch(other,'read',dict(id=r['id']))['count'],2);entry=r['entries'][0];file=other/entry['path'];file.write_bytes(file.read_bytes()+b' ')
  with self.assertRaisesRegex(ValueError,'已变化'):dispatch(other,'read',dict(id=r['id']))
 def test_invalid_files_do_not_block_valid_items_and_generation_is_persisted(self):
  r=dispatch(self.root,'import',dict(files=[dict(name='bad.nbt',base64=base64.b64encode(b'broken').decode()),dict(name='one.json',base64=base64.b64encode(json.dumps(self.component).encode()).decode())]));self.assertEqual(r['count'],1);self.assertEqual(len(r['errors']),1);g=dispatch(self.root,'generate',dict(scope='components',name='构件清单'));self.assertEqual(dispatch(self.root,'read',dict(id=g['id']))['count'],1)
 def test_manifest_paths_types_hashes_and_limits(self):
  r=self.imported();data=json.loads((self.root/r['manifest']).read_text());data['entries'][0]['path']='../secret.json'
  with self.assertRaises(ValueError):dispatch(self.root,'read',dict(manifest=data))
  with self.assertRaises(ValueError):dispatch(self.root,'import',dict(files=[]))
  with self.assertRaises(ValueError):dispatch(self.root,'read',dict(id='../escape'))

if __name__=='__main__':unittest.main(verbosity=2)
