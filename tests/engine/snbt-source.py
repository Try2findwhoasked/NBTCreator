from pathlib import Path
import gzip,hashlib,json,subprocess,sys,tempfile,unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_assembly import Volume
from nbt_refine import read_master,save_master
from nbt_snbt import save_snbt,read_snbt,write_binary,root,convert,N
from nbt_finalize import finalize
from nbt_web_revision import convert_web_json
from nbt_detail_control import default_settings,catalog
import nbt_snbt

class ParsedSourceCache(unittest.TestCase):
 def setUp(self):
  temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);self.folder=Path(temporary.name)
  nbt_snbt.clear_parsed_sources();self.addCleanup(nbt_snbt.clear_parsed_sources)
  self.model=Volume((8,8,8));self.model.box([0,0,0],[7,0,7],'stone_bricks');self.walls={(0,0,0)}
 def test_checked_save_rename_and_identical_copy_parse_once_without_shared_mutation(self):
  file=self.folder/'model.snbt'
  with patch.object(N,'parse_nbt',wraps=N.parse_nbt) as parsed:
   save_snbt(file,self.model,self.walls);model,mask=read_snbt(file)
   alias=self.folder/'copy.snbt';alias.write_bytes(file.read_bytes());copy,copy_mask=read_snbt(alias)
   self.assertEqual(parsed.call_count,1)
  model.put((0,0,0),'gold_block');mask.clear();model._snbt_palette.clear()
  self.assertEqual(copy.blocks,self.model.blocks);self.assertEqual(copy_mask,self.walls)
  self.assertEqual(read_snbt(file)[0].blocks,self.model.blocks)
 def test_same_size_and_identical_file_stamps_cannot_hide_changed_bytes(self):
  file=self.folder/'model.snbt';save_snbt(file,self.model,self.walls);stamp=file.stat()
  raw=file.read_bytes();updated=raw.replace(b'stone_bricks',b'quartz_block');self.assertEqual(len(raw),len(updated))
  file.write_bytes(updated)
  with patch.object(Path,'stat',return_value=stamp):model,_=read_snbt(file)
  self.assertNotEqual(model.fingerprint(),self.model.fingerprint());self.assertTrue(model._snbt_metadata_stale)
  self.assertEqual(set(model.blocks.values()),{'minecraft:quartz_block'})
 def test_cached_extras_are_deeply_isolated_and_invalid_changes_still_refuse(self):
  file=self.folder/'model.snbt';self.model._snbt_extras={'custom':N.Compound({'label':N.String('original')})}
  save_snbt(file,self.model,self.walls);model,_=read_snbt(file)
  model._snbt_extras['custom']['label']=N.String('changed')
  self.assertEqual(read_snbt(file)[0]._snbt_extras['custom']['label'],'original')
  file.write_bytes(file.read_bytes().replace(b'3465',b'3466',1))
  self.assertRaisesRegex(ValueError,'3465',read_snbt,file)
 def test_count_and_byte_limits_evict_or_skip_without_changing_decoded_sources(self):
  files=[]
  for i,state in enumerate(('stone_bricks','gold_block','quartz_block')):
   model=Volume((2,2,2));model.put((0,0,0),state);file=self.folder/f'{i}.snbt';save_snbt(file,model,set());files.append(file)
  nbt_snbt.clear_parsed_sources()
  with patch.object(nbt_snbt,'MAX_PARSED_ENTRIES',2),patch.object(N,'parse_nbt',wraps=N.parse_nbt) as parsed:
   for file in files:read_snbt(file)
   self.assertEqual(read_snbt(files[0])[0].get((0,0,0)),'minecraft:stone_bricks')
   self.assertEqual(parsed.call_count,4)
   self.assertLessEqual(len(nbt_snbt._parsed_sources),2)
  nbt_snbt.clear_parsed_sources()
  with patch.object(nbt_snbt,'MAX_PARSED_BYTES',1),patch.object(N,'parse_nbt',wraps=N.parse_nbt) as parsed:
   first=read_snbt(files[0]);second=read_snbt(files[0])
   self.assertEqual(first[0].blocks,second[0].blocks);self.assertEqual(parsed.call_count,2)
   self.assertEqual(nbt_snbt._parsed_bytes,0)
 def test_file_size_limit_is_rechecked_on_a_warm_content_hit(self):
  file=self.folder/'model.snbt';save_snbt(file,self.model,self.walls)
  with patch.object(nbt_snbt,'MAX_SOURCE_BYTES',file.stat().st_size-1):
   self.assertRaisesRegex(ValueError,'256MiB',read_snbt,file)
 def test_small_source_read_does_not_allocate_the_file_size_limit(self):
  import tracemalloc
  file=self.folder/'model.snbt';save_snbt(file,self.model,self.walls)
  tracemalloc.start()
  try:
   self.assertEqual(nbt_snbt._source_bytes(file),file.read_bytes())
   self.assertLess(tracemalloc.get_traced_memory()[1],1024*1024)
  finally:
   tracemalloc.stop()

class SnbtSource(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.workspace=Path(self.temp.name).resolve();self.version=self.workspace/'nbt_models/single/制作测试/v01';subprocess.run([sys.executable,str(ROOT/'tests/support/make_fixture.py'),str(self.version)],check=True,stdout=subprocess.DEVNULL);self.source=self.version/'synthetic.master.json.gz';self.model,self.walls=read_master(self.source)
 def test_source_round_trip_preserves_geometry_properties_and_explicit_walls(self):
  self.model.put((7,4,7),'minecraft:oak_stairs[facing=east,half=top,shape=straight,waterlogged=false]');file=self.version/'master/model.snbt';save_snbt(file,self.model,self.walls);model,walls=read_master(file);self.assertEqual(model.blocks,self.model.blocks);self.assertEqual(walls,self.walls);self.assertIs(type(root(file)['DataVersion']),N.Int)
 def test_canonical_text_and_append_only_palette_keep_diff_stable(self):
  file=self.version/'master/model.snbt';save_snbt(file,self.model,self.walls);original=file.read_bytes();model,walls=read_snbt(file);save_snbt(file,model,walls);self.assertEqual(file.read_bytes(),original);palette=[str(p) for p in root(file)['palette']];model.put((7,4,7),'minecraft:oak_planks');save_snbt(file,model,walls);self.assertEqual([str(p) for p in root(file)['palette']][:len(palette)],palette)
 def test_manual_text_edit_recomputes_geometry_instead_of_trusting_stale_metadata(self):
  file=self.version/'model.snbt';save_snbt(file,self.model,self.walls);text=file.read_text();file.write_text(text.replace('stone_bricks','polished_andesite'),encoding='utf8');model,_=read_snbt(file);self.assertNotEqual(model.fingerprint(),self.model.fingerprint());self.assertTrue(model._snbt_metadata_stale)
 def test_old_gzip_source_stays_untouched_and_can_be_converted(self):
  before=self.source.read_bytes();file=self.version/'master/model.snbt';convert(self.source,file);self.assertEqual(self.source.read_bytes(),before);self.assertEqual(read_master(file)[0].fingerprint(),self.model.fingerprint());self.assertRaises(ValueError,convert,self.source,file)
 def test_fast_catalog_does_not_treat_snbt_as_gzip(self):
  file=self.version/'master/model.snbt';save_snbt(file,self.model,self.walls)
  description=self.version/'room_description.json';data=json.loads(description.read_text());data['master']='master/model.snbt';description.write_text(json.dumps(data),encoding='utf8')
  items=catalog(self.workspace,index_only=True)['models'];entry=next(item for item in items if item['source']==str(file.resolve()))
  self.assertFalse(entry['unreadable']);self.assertTrue(entry['unverified'])
 def test_entities_are_rejected_without_silent_loss(self):
  file=self.version/'model.snbt';save_snbt(file,self.model,self.walls);data=root(file);data['entities']=N.List[N.Compound]([N.Compound({'id':N.String('minecraft:pig')})]);file.write_text(data.snbt(),encoding='utf8');before=file.read_bytes();self.assertRaisesRegex(ValueError,'实体',read_snbt,file);self.assertEqual(file.read_bytes(),before)
 def test_binary_delivery_has_real_java_types_and_independent_readback(self):
  target=self.workspace/'binary/model.nbt';write_binary(target,self.model,self.walls);model,walls=read_master(target);self.assertEqual(model.blocks,self.model.blocks);self.assertEqual(walls,self.walls)
  from generate_sealed_models import read_nbt
  decoded=read_nbt(target);self.assertEqual(decoded['DataVersion'],3465);self.assertNotIn('nbtcreator',decoded);self.assertEqual(decoded['size'],list(self.model.size))
 def test_half_block_preview_reads_snbt_and_keeps_legacy_nbt(self):
  from nbt_model import Model

  model=Model((4,4,4))
  model.box((0,0,0),(3,0,3),'stone_bricks')
  model.box((1,1,1),(1,2,1),'andesite')
  snbt=self.workspace/'model.snbt'
  save_snbt(snbt,model,set())
  script=ROOT/'.agents/skills/minecraft-nbt-modeler/scripts/nbt_preview.py'
  binary=self.workspace/'legacy.nbt'
  model._write_nbt(binary)
  for index,(flag,source) in enumerate((('--nbt',snbt),('--source',snbt),('--nbt',binary))):
   with self.subTest(flag=flag,source=source.name):
    before=source.read_bytes()
    image=self.workspace/f'cut-{index}.png'
    run=subprocess.run([sys.executable,'-B',str(script),flag,str(source),'--output',str(image),
                       '--eye','8,6,8','--target','2,0.5,2','--cut','y:1.5:above','--width','96','--height','64'],
                       capture_output=True,text=True,encoding='utf8',errors='replace')
    self.assertEqual(run.returncode,0,run.stdout+run.stderr)
    metadata=json.loads(Path(str(image)+'.json').read_text(encoding='utf8'))
    self.assertTrue(image.read_bytes().startswith(b'\x89PNG'))
    self.assertGreater(metadata['visible_structure_pixels'],0)
    self.assertEqual(metadata['cut'],dict(axis='y',position=1.5,removed_side='above'))
    self.assertEqual(metadata['geometry']['occupied_half_cells'],132)
    self.assertEqual(Path(metadata['source']),source)
    self.assertEqual(metadata['source_sha256'],hashlib.sha256(before).hexdigest())
    if source==binary:
     self.assertEqual(metadata['source_nbt_sha256'],metadata['source_sha256'])
    self.assertEqual(source.read_bytes(),before)
  self.assertEqual(list(self.workspace.rglob('*.nbt')),[binary])

 def draft_request(self,draft_only=True):
  settings=default_settings()
  settings['operations']=[dict(kind='box',label='制作版新增石柱',lo=[16,1,16],hi=[16,4,16],state='stone_bricks',classification='body')]
  request=dict(source=str(self.source),context=str(self.version/'coordinates.json'),settings=settings,draft_only=draft_only)
  file=self.workspace/'request.json'
  file.write_text(json.dumps(request),encoding='utf8')
  return file
 def draft(self,draft_only=True):
  return convert_web_json(self.draft_request(draft_only))
 def test_control_revision_with_only_request_saves_next_version(self):
  request=self.draft_request()
  scripts=ROOT/'.agents/skills/minecraft-nbt-modeler/scripts'
  run=subprocess.run([sys.executable,'-B',str(scripts/'nbt_detail_control.py'),'revision','--request',str(request)],
                     cwd=self.workspace,capture_output=True,text=True,encoding='utf8',errors='replace')
  self.assertEqual(run.returncode,0,run.stdout+run.stderr)
  result=json.loads(run.stdout)['result']
  self.assertEqual(Path(result['master']),self.version.parent/'v02/master/model.snbt')
  self.assertTrue(Path(result['master']).is_file())
  self.assertEqual(result['delivery_nbt'],0)
 def test_draft_only_creates_snbt_and_history_without_binary_exports(self):
  result=self.draft();file=Path(result['master']);self.assertEqual(file.suffix,'.snbt');self.assertEqual(result['runtime_files'],[]);self.assertFalse(list(file.parents[1].rglob('*.nbt')));self.assertFalse((self.workspace/'nbt_models/_exports').exists());self.assertTrue(result['history'].get('commit'));self.assertEqual(read_master(file)[0].get((16,4,16)),'minecraft:stone_bricks')
 def test_finalize_uses_mirrored_tree_preserves_source_and_is_idempotent(self):
  draft=self.draft();file=Path(draft['master']);before=file.read_bytes();result=finalize(self.workspace,file);expected=self.workspace/'nbt_models/_exports'/file.parents[1].relative_to(self.workspace/'nbt_models');self.assertEqual(Path(result['output']),expected);self.assertEqual(file.read_bytes(),before);self.assertEqual(read_master(result['nbt_master'])[0].fingerprint(),draft['geometry_sha256']);self.assertTrue(result['runtime_files']);self.assertTrue(finalize(self.workspace,file)['unchanged']);self.assertFalse(any('_exports' in item['source'] for item in catalog(self.workspace/'nbt_models')['models']))
 def test_final_delivery_tamper_is_not_overwritten(self):
  result=finalize(self.workspace,Path(self.draft()['master']));target=Path(result['runtime_files'][0]);target.write_bytes(b'changed');self.assertRaisesRegex(ValueError,'修改',finalize,self.workspace,self.workspace/json.loads((Path(result['output'])/'release.json').read_text())['source']);self.assertEqual(target.read_bytes(),b'changed')
 def test_failed_finalization_does_not_occupy_the_release_path(self):
  from nbt_finalize import release_path
  file=Path(self.draft()['master'])
  def fail_after_write(model,walls,config,checks,target):
   target.mkdir()
   (target/'partial.nbt').write_bytes(b'fixture')
   raise OSError('synthetic export failure')
  with patch('nbt_finalize.export_binary',side_effect=fail_after_write):
   self.assertRaisesRegex(OSError,'synthetic export failure',finalize,self.workspace,file)
  self.assertFalse(release_path(self.workspace,file).exists())
  self.assertTrue(Path(finalize(self.workspace,file)['nbt_master']).is_file())
 def test_repeating_finalization_rejects_changed_source_context(self):
  file=Path(self.draft()['master'])
  result=finalize(self.workspace,file)
  context=file.parents[1]/'coordinates.json'
  data=json.loads(context.read_text(encoding='utf8'))
  data['protected_boxes']=[dict(lo=[0,0,0],hi=[1,1,1])]
  context.write_text(json.dumps(data),encoding='utf8')
  self.assertRaisesRegex(ValueError,'坐标配置已变化',finalize,self.workspace,file)
  self.assertTrue(Path(result['nbt_master']).is_file())
 def test_immediate_export_requires_the_saved_source_bytes(self):
  from nbt_finalize import release_path
  file=Path(self.draft()['master']);expected=hashlib.sha256(file.read_bytes()).hexdigest()
  file.write_bytes(file.read_bytes()+b'\n')
  with self.assertRaisesRegex(ValueError,'已保存制作源发生变化'):
   finalize(self.workspace,file,expected_source_sha256=expected)
  self.assertFalse(release_path(self.workspace,file).exists())
 def test_finalize_cli_rejects_changed_reviewed_inputs_without_exporting(self):
  from nbt_finalize import release_path
  source=Path(self.draft()['master']);context=source.parents[1]/'coordinates.json'
  command=['node',str(ROOT/'scripts/cli.mjs'),'--workspace',str(self.workspace),'finalize','--source',str(source)]
  def call(*options):
   run=subprocess.run([*command,*options],capture_output=True,encoding='utf8',timeout=30)
   return run.returncode,json.loads(run.stdout)
  status,reviewed=call('--inspect-inputs');self.assertEqual(status,0)
  self.assertEqual(call()[0],1)
  arguments=('--source-sha256',reviewed['source_sha256'],'--inputs-sha256',reviewed['inputs_sha256'])
  context.write_bytes(context.read_bytes()+b'\n')
  status,result=call(*arguments);self.assertEqual(status,1);self.assertIn('保护配置',result['error'])
  self.assertFalse(release_path(self.workspace,source).exists())
  source.write_bytes(source.read_bytes()+b'\n')
  status,result=call(*arguments);self.assertEqual(status,1);self.assertIn('制作源发生变化',result['error'])
  self.assertFalse(release_path(self.workspace,source).exists())

 def test_failed_explicit_export_keeps_the_published_authoring_version(self):
  with patch('nbt_finalize.export_binary',side_effect=OSError('synthetic export failure')):
   with self.assertRaisesRegex(ValueError,'制作版已保存.*synthetic export failure'):
    self.draft(draft_only=False)
  version=self.version.parent/'v02'
  result=json.loads((version/'conversion.json').read_text(encoding='utf8'))
  self.assertEqual(result['status'],'complete')
  self.assertEqual(result['release_status'],'failed')
  source=Path(result['master'])
  self.assertTrue(any(Path(item['source'])==source for item in catalog(self.workspace)['models']))
  self.assertTrue(finalize(self.workspace,source)['binary_roundtrip'])

if __name__=='__main__':unittest.main(verbosity=2)
