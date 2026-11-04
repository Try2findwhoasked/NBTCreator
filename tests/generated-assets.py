from pathlib import Path
import json,sys,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_structure_agent import dispatch
from nbt_asset_batches import dispatch as batches
import nbt_components as library

class GeneratedAssets(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
  self.spec=dict(name='脚本石柱',size=[4,6,4],operations=[dict(kind='box',label='柱',classification='wall',lo=[1,0,1],hi=[1,4,1],state='stone')])
 def test_direct_spec_save_creates_real_preview_library_and_bound_manifest(self):
  item=dispatch(self.root,'structure_save',dict(spec=self.spec));self.assertEqual(item['review_status'],'pending_visual_review');self.assertFalse(item['nbt_exported']);self.assertFalse(item['approval_created']);self.assertTrue(Path(item['thumbnail']).is_file());self.assertEqual(len(library.load(self.root,item['id'])['blocks']),5);manifest=batches(self.root,'read',dict(id=item['batch_id'],include_data=True));self.assertEqual(manifest['items'][0]['data']['blocks'],library.load(self.root,item['id'])['blocks']);self.assertTrue((self.root/item['batch_manifest']).exists())
 def test_receipt_retry_does_not_duplicate_and_changed_preview_rejected(self):
  draft=dispatch(self.root,'structure_preview',dict(spec=self.spec));args={k:draft[k] for k in ('preview_id','preview_sha256')};a=dispatch(self.root,'structure_save',args);b=dispatch(self.root,'structure_save',args);self.assertEqual(a['id'],b['id']);self.assertEqual(len(library.listing(self.root)['items']),1);Path(draft['thumbnail']).write_bytes(b'changed')
  with self.assertRaises(ValueError):dispatch(self.root,'structure_save',args)
 def test_organize_is_idempotent_and_keeps_ids_archived_state_and_drafts(self):
  item=dispatch(self.root,'structure_save',dict(spec=self.spec));library.update(self.root,item['id'],archived=True);original=library.component_file(self.root,item['id']).read_bytes();drafts=list((self.root/'nbt_models/_workspaces/structure_agent').glob('*/draft.json'));r=batches(self.root,'organize',{});self.assertEqual(r['count'],1);self.assertTrue(batches(self.root,'organize',{})['reused']);self.assertEqual(library.component_file(self.root,item['id']).read_bytes(),original);self.assertEqual(list((self.root/'nbt_models/_workspaces/structure_agent').glob('*/draft.json')),drafts)
 def test_batch_partial_failure_raw_component_and_no_fake_review(self):
  result=batches(self.root,'save',dict(assets=[dict(spec=self.spec),dict(spec=dict(self.spec,size=[0,0,0]))]));self.assertEqual(result['count'],1);self.assertEqual(len(result['errors']),1);self.assertEqual(batches(self.root,'read',dict(id=result['batch_id']))['count'],1)
  component=library.load(self.root,result['items'][0]['id']);raw=dispatch(self.root,'structure_save',dict(component=component));self.assertNotEqual(raw['id'],component['id'])
  with self.assertRaises(ValueError):dispatch(self.root,'structure_save',dict(spec=self.spec,component=component))
  with self.assertRaises(ValueError):dispatch(self.root,'structure_save',dict(component=dict(component,review_status='approved')))

if __name__=='__main__':unittest.main(verbosity=2)
