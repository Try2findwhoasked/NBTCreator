"""Global-route protection and immutable large-model handoff fixtures."""
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_large_assembly import AssemblyVolume,save_assembly
from nbt_assembly_handoff import create_slice,merge_slices
from nbt_snbt import read_snbt,save_snbt
from nbt_working_model import WorkingModel,ModelConflict


class Handoff(unittest.TestCase):
 def setUp(self):
  temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name)
  model=AssemblyVolume((300,384,300))
  for x in range(8):
   for z in range(3):model.put((x,0,z),'stone')
  self.source=save_assembly(self.root/'nbt_models/standalone/handoff/v01/master',model,set(),
                            [dict(offset=[0,0,0],size=[8,5,3])])
  self.context=dict(mode='standalone',openings=[],start=[1.5,1,1.5],targets={'end':[6.5,1,1.5]})
 def request(self):
  return dict(source=self.source['source'],source_sha256=self.source['source_sha256'],context=self.context,
              region=dict(lo=[-1,0,0],hi=[7,4,2]),write_bounds=dict(lo=[2,0,0],hi=[5,4,2]),
              output='nbt_models/_workspaces/assembly-handoffs/slice-a')
 def test_slice_preserves_negative_origin_and_protects_full_route_and_read_only_neighbours(self):
  result=create_slice(self.root,self.request());manifest=Path(result['manifest'])
  self.assertEqual(hashlib.sha256(manifest.read_bytes()).hexdigest(),result['manifest_sha256'])
  record=json.loads(manifest.read_text(encoding='utf8'))
  self.assertEqual(record['origin'],[-1,0,0]);self.assertEqual(record['source_sha256'],self.source['source_sha256'])
  model,walls=read_snbt(result['baseline']);self.assertEqual(model.get((3,0,1)),'minecraft:stone');self.assertEqual(walls,set())
  self.assertTrue(record['routes']['passed']);self.assertEqual(len(record['assembly_partitions']),1)
  working=WorkingModel.open(self.root,result['baseline'],context=result['context'])
  with self.assertRaisesRegex(ValueError,'保护'):
   working.patch([dict(pos=[3,0,1],before=['minecraft:stone',False],after=['minecraft:air',False])])
  with self.assertRaisesRegex(ValueError,'保护'):
   working.patch([dict(pos=[1,1,0],before=['minecraft:air',False],after=['minecraft:gold_block',False])])
  working.patch([dict(pos=[4,4,0],before=['minecraft:air',False],after=['minecraft:gold_block',False])])
  self.assertEqual(working.model.get((4,4,0)),'minecraft:gold_block')
 def test_slice_rejects_stale_source_and_invalid_write_range_without_output(self):
  request=self.request();request['source_sha256']='0'*64
  with self.assertRaisesRegex(ValueError,'STALE_SOURCE'):create_slice(self.root,request)
  self.assertFalse((self.root/request['output']).exists())
  request=self.request();request['write_bounds']['lo']=[-1,0,0]
  with self.assertRaisesRegex(ValueError,'可写'):create_slice(self.root,request)
  self.assertFalse((self.root/request['output']).exists())

 def test_software_source_root_is_never_a_slice_workspace(self):
  with self.assertRaisesRegex(ValueError,'源码目录'):
   create_slice(ROOT,self.request())
 def test_unreachable_declared_global_route_prevents_slice_publication(self):
  request=self.request();request['context']=dict(self.context,targets={'missing':[299.5,1,299.5]})
  with self.assertRaisesRegex(ValueError,'路线'):create_slice(self.root,request)
  self.assertFalse((self.root/request['output']).exists())

 def test_interrupted_slice_publication_is_retryable_without_overwriting_files(self):
  from unittest.mock import patch
  import os
  real_link=os.link
  def fail_manifest(source,destination):
   if Path(destination).name=='slice.json':raise OSError('synthetic slice interruption')
   return real_link(source,destination)
  request=self.request()
  with patch('nbt_assembly_handoff.os.link',side_effect=fail_manifest):
   with self.assertRaisesRegex(OSError,'slice interruption'):create_slice(self.root,request)
  folder=self.root/request['output'];self.assertFalse((folder/'slice.json').exists())
  original=(folder/'baseline.snbt').read_bytes()
  result=create_slice(self.root,request)
  self.assertEqual((folder/'baseline.snbt').read_bytes(),original)
  self.assertEqual(create_slice(self.root,request)['manifest_sha256'],result['manifest_sha256'])

 def test_slice_retry_refuses_modified_partial_output(self):
  from unittest.mock import patch
  import os
  real_link=os.link
  def fail_manifest(source,destination):
   if Path(destination).name=='slice.json':raise OSError('synthetic slice interruption')
   return real_link(source,destination)
  request=self.request()
  with patch('nbt_assembly_handoff.os.link',side_effect=fail_manifest):
   with self.assertRaises(OSError):create_slice(self.root,request)
  folder=self.root/request['output'];baseline=folder/'baseline.snbt';baseline.write_bytes(b'changed')
  with self.assertRaisesRegex(ValueError,'变化|占用'):create_slice(self.root,request)
  self.assertEqual(baseline.read_bytes(),b'changed');self.assertFalse((folder/'slice.json').exists())

 def test_completed_slice_without_new_journal_remains_retryable(self):
  request=self.request();result=create_slice(self.root,request)
  (self.root/request['output']/'.slice-publication.json').unlink()
  again=create_slice(self.root,request)
  self.assertEqual(again['manifest_sha256'],result['manifest_sha256'])

 def edited_slice(self,name,lo,hi,changes):
  request=self.request();request['output']='nbt_models/_workspaces/assembly-handoffs/'+name
  request['write_bounds']=dict(lo=lo,hi=hi)
  result=create_slice(self.root,request);model,walls=read_snbt(result['baseline'])
  for position,value,wall in changes:
   local=tuple(position[i]-result['origin'][i] for i in range(3));model.put(local,value)
   if wall:walls.add(local)
   else:walls.discard(local)
  candidate=self.root/(name+'-candidate.snbt');receipt=save_snbt(candidate,model,walls)
  return dict(manifest=result['manifest'],manifest_sha256=result['manifest_sha256'],candidate=str(candidate),candidate_sha256=receipt['source_sha256'])

 def merge_request(self,slices):
  return dict(source=self.source['source'],source_sha256=self.source['source_sha256'],context=self.context,
              slices=slices,name_zh='协作组装')

 def test_four_slices_merge_once_with_global_route_and_keep_original(self):
  def create(item):
   i,x=item
   return self.edited_slice('slice-'+str(i),[x,0,0],[x+1,4,2],[([x,4,0],'gold_block',i==0)])
  with ThreadPoolExecutor(max_workers=4) as pool:
   slices=list(pool.map(create,enumerate((0,2,4,6))))
  original=Path(self.source['source']).read_bytes();request=self.merge_request(slices)
  result=merge_slices(self.root,request)
  self.assertFalse(result['saved']['history_pending']);self.assertFalse(result['saved']['nbt_exported'])
  model,walls=__import__('nbt_large_assembly').read_assembly(result['saved']['source'])
  for x in (0,2,4,6):self.assertEqual(model.get((x,4,0)),'minecraft:gold_block')
  self.assertEqual(walls,{(0,4,0)});self.assertEqual(Path(self.source['source']).read_bytes(),original)
  self.assertTrue(result['routes']['passed']);self.assertEqual(result['changed_positions'],4)
  self.assertEqual(result['slices'][0]['changed_bounds'],dict(lo=[0,4,0],hi=[0,4,0]))
  receipt=json.loads((Path(result['saved']['output'])/'editing/handoff.json').read_text(encoding='utf8'))
  self.assertEqual(receipt['changes_file'],'changes.json');self.assertEqual(len(receipt['slices']),4)
  again=merge_slices(self.root,request)
  self.assertEqual(again['saved']['source'],result['saved']['source'])

 def test_overlap_and_route_support_changes_are_rejected_without_publication(self):
  first=self.edited_slice('a',[2,0,0],[3,4,2],[([2,4,0],'gold_block',False)])
  second=self.edited_slice('b',[2,0,0],[3,4,2],[([2,4,0],'gold_block',False)])
  with self.assertRaisesRegex(ModelConflict,'SLICE_OVERLAP'):merge_slices(self.root,self.merge_request([first,second]))
  blocked=self.edited_slice('blocked',[2,0,0],[3,4,2],[([3,0,1],'air',False)])
  with self.assertRaisesRegex(ModelConflict,'SLICE_PROTECTED'):merge_slices(self.root,self.merge_request([blocked]))
  self.assertFalse(list((self.root/'nbt_models/standalone/handoff').glob('v_model_*')))

 def test_stale_or_out_of_scope_candidates_are_rejected(self):
  out=self.edited_slice('outside',[2,0,0],[3,4,2],[([4,4,0],'gold_block',False)])
  with self.assertRaisesRegex(ModelConflict,'SLICE_READ_ONLY'):merge_slices(self.root,self.merge_request([out]))
  out['candidate_sha256']='0'*64
  with self.assertRaisesRegex(ValueError,'哈希|变化'):merge_slices(self.root,self.merge_request([out]))
  self.assertFalse(list((self.root/'nbt_models/standalone/handoff').glob('v_model_*')))

 def test_changed_context_and_manifest_are_rejected_before_publication(self):
  entry=self.edited_slice('stale-context',[2,0,0],[3,4,2],[([2,4,0],'gold_block',False)])
  request=self.merge_request([entry]);request['context']=dict(self.context,protected_boxes=[dict(lo=[0,4,0],hi=[0,4,0])])
  with self.assertRaisesRegex(ModelConflict,'SLICE_STALE_CONTEXT'):merge_slices(self.root,request)
  request=self.merge_request([entry]);entry['manifest_sha256']='0'*64
  with self.assertRaisesRegex(ValueError,'哈希'):merge_slices(self.root,request)
  self.assertFalse(list((self.root/'nbt_models/standalone/handoff').glob('v_model_*')))

 def test_stale_partition_reports_its_global_bounds(self):
  entry=self.edited_slice('stale-part',[2,0,0],[3,4,2],[([2,4,0],'gold_block',False)])
  source=Path(self.source['source']);part=source.parent/json.loads(source.read_text(encoding='utf8'))['partitions'][0]['file']
  part.write_bytes(part.read_bytes()+b' ')
  with self.assertRaises(ModelConflict) as captured:merge_slices(self.root,self.merge_request([entry]))
  self.assertEqual(captured.exception.code,'SLICE_STALE_SOURCE')
  self.assertEqual(captured.exception.conflicts[0]['lo'],[0,0,0])
  self.assertEqual(captured.exception.conflicts[0]['hi'],[7,4,2])

 def test_frozen_slice_and_shared_cli_merge_keep_conflict_coordinates(self):
  from nbt_exposure import apply
  apply(self.root)
  request_path=self.root/'slice-request.json';request_path.write_text(json.dumps(self.request()),encoding='utf8')
  facade=self.root/'.agents/skills/nbtcreator-workspace/nbt.py'
  run=subprocess.run([sys.executable,str(facade),'assembly','slice','--request',str(request_path)],
                     cwd=self.root,capture_output=True,text=True,encoding='utf8',timeout=45)
  self.assertEqual(run.returncode,0,run.stdout+run.stderr)
  issued=json.loads(run.stdout);candidate,walls=read_snbt(issued['baseline'])
  candidate.put((3,4,0),'gold_block');file=self.root/'returned.snbt';saved=save_snbt(file,candidate,walls)
  entry=dict(manifest=issued['manifest'],manifest_sha256=issued['manifest_sha256'],candidate=str(file),candidate_sha256=saved['source_sha256'])
  request=self.merge_request([entry,entry]);merge_path=self.root/'merge-request.json';merge_path.write_text(json.dumps(request),encoding='utf8')
  command=['node',str(ROOT/'scripts/cli.mjs'),'--workspace',str(self.root),'assembly','merge','--request',str(merge_path)]
  failed=subprocess.run(command,capture_output=True,text=True,encoding='utf8',timeout=45)
  self.assertNotEqual(failed.returncode,0);error=json.loads(failed.stdout)
  self.assertEqual(error['code'],'SLICE_OVERLAP');self.assertEqual(error['conflicts'][0]['pos'],[2,4,0])
  request['slices']=[entry];merge_path.write_text(json.dumps(request),encoding='utf8')
  result=subprocess.run(command,capture_output=True,text=True,encoding='utf8',timeout=45)
  self.assertEqual(result.returncode,0,result.stdout+result.stderr)
  receipt=json.loads(result.stdout);self.assertEqual(receipt['changed_positions'],1)
  self.assertTrue(receipt['routes']['passed']);self.assertFalse(receipt['nbt_exported'])

 def test_candidate_changed_during_publication_is_rejected(self):
  from unittest.mock import patch
  from nbt_snbt import save_snbt as actual_save
  entry=self.edited_slice('changing',[2,0,0],[3,4,2],[([2,4,0],'gold_block',False)])
  def mutate(*args,**kwargs):
   result=actual_save(*args,**kwargs)
   file=Path(entry['candidate']);file.write_bytes(file.read_bytes()+b' ')
   return result
  with patch('nbt_large_assembly.save_snbt',side_effect=mutate):
   with self.assertRaisesRegex(ValueError,'回装期间.*变化'):merge_slices(self.root,self.merge_request([entry]))
  self.assertFalse(list((self.root/'nbt_models/standalone/handoff').glob('v_model_*')))

 def test_interrupted_head_publication_retries_same_version_and_records_history(self):
  from unittest.mock import patch
  entry=self.edited_slice('interrupted',[2,0,0],[3,4,2],[([2,4,0],'gold_block',False)])
  request=self.merge_request([entry])
  with patch('nbt_object_scene.atomic',side_effect=OSError('synthetic head interruption')):
   with self.assertRaisesRegex(OSError,'head interruption'):merge_slices(self.root,request)
  versions=list((self.root/'nbt_models/standalone/handoff').glob('v_model_*'))
  self.assertEqual(len(versions),1);self.assertTrue((versions[0]/'master/assembly.json').is_file())
  recovered=merge_slices(self.root,request)
  self.assertEqual(Path(recovered['saved']['output']).resolve(),versions[0].resolve());self.assertFalse(recovered['saved']['history_pending'])
  self.assertEqual(merge_slices(self.root,request)['saved']['source'],recovered['saved']['source'])

 def test_different_result_from_stale_parent_does_not_replace_newer_head(self):
  first=self.edited_slice('first',[2,0,0],[3,4,2],[([2,4,0],'gold_block',False)])
  second=self.edited_slice('second',[2,0,0],[3,4,2],[([3,4,0],'quartz_block',False)])
  saved=merge_slices(self.root,self.merge_request([first]))['saved']
  with self.assertRaisesRegex(ModelConflict,'STALE_PARENT'):merge_slices(self.root,self.merge_request([second]))
  restored,_=__import__('nbt_large_assembly').read_assembly(saved['source'])
  self.assertEqual(restored.get((2,4,0)),'minecraft:gold_block');self.assertEqual(restored.get((3,4,0)),'minecraft:air')

 def test_four_stair_slices_reject_headroom_conflict_then_pass_round_trip(self):
  model=AssemblyVolume((300,384,300))
  for x in range(8):
   y=(x+1)//2
   material='stone_slab[type=bottom,waterlogged=false]' if x%2 else 'stone'
   for z in range(3):model.put((x,y,z),material)
  self.source=save_assembly(self.root/'nbt_models/standalone/stairs/v01/master',model,set(),
                            [dict(offset=[0,0,0],size=[4,10,3]),dict(offset=[4,0,0],size=[4,10,3])])
  self.context=dict(mode='standalone',openings=[],start=[.5,1,1.5],targets={'top':[6.5,4,1.5]},
                    route_legs=[dict(name='返程',start=[6.5,4,1.5],targets={'bottom':[.5,1,1.5]})])
  slices=[]
  for i,x in enumerate((0,2,4,6)):
   request=self.request();request.update(region=dict(lo=[0,0,0],hi=[7,9,2]),
     write_bounds=dict(lo=[x,0,0],hi=[x+1,9,2]),output='nbt_models/_workspaces/assembly-handoffs/stair-'+str(i))
   created=create_slice(self.root,request);candidate,walls=read_snbt(created['baseline'])
   candidate.put((x,8,0),'gold_block')
   if i==1:candidate.put((3,3,1),'stone')
   file=self.root/('stair-'+str(i)+'.snbt');saved=save_snbt(file,candidate,walls)
   slices.append(dict(manifest=created['manifest'],manifest_sha256=created['manifest_sha256'],candidate=str(file),candidate_sha256=saved['source_sha256']))
  with self.assertRaisesRegex(ModelConflict,'SLICE_PROTECTED'):merge_slices(self.root,self.merge_request(slices))
  file=Path(slices[1]['candidate']);candidate,walls=read_snbt(file);candidate.put((3,3,1),'air')
  replacement=self.root/'stair-repaired.snbt';saved=save_snbt(replacement,candidate,walls)
  slices[1].update(candidate=str(replacement),candidate_sha256=saved['source_sha256'])
  result=merge_slices(self.root,self.merge_request(slices))
  self.assertTrue(result['routes']['passed']);self.assertTrue(result['routes']['legs'][0]['report']['passed'])
  self.assertEqual(result['changed_positions'],4)


if __name__=='__main__':unittest.main(verbosity=2)
