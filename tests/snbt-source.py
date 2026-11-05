from pathlib import Path
import gzip,hashlib,json,subprocess,sys,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_assembly import Volume
from nbt_refine import read_master,save_master
from nbt_snbt import save_snbt,read_snbt,write_binary,root,convert,N
from nbt_finalize import finalize
from nbt_web_revision import convert_web_json
from nbt_detail_control import default_settings,catalog

class SnbtSource(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.workspace=Path(self.temp.name).resolve();self.version=self.workspace/'nbt_models/single/制作测试/v01';subprocess.run([sys.executable,str(ROOT/'tests/make_fixture.py'),str(self.version)],check=True,stdout=subprocess.DEVNULL);self.source=self.version/'synthetic.master.json.gz';self.model,self.walls=read_master(self.source)
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
 def draft(self):
  settings=default_settings();settings['operations']=[dict(kind='box',label='制作版新增石柱',lo=[16,1,16],hi=[16,4,16],state='stone_bricks',classification='body')];request=dict(source=str(self.source),context=str(self.version/'coordinates.json'),settings=settings,draft_only=True);file=self.workspace/'request.json';file.write_text(json.dumps(request),encoding='utf8');return convert_web_json(file)
 def test_draft_only_creates_snbt_and_history_without_binary_exports(self):
  result=self.draft();file=Path(result['master']);self.assertEqual(file.suffix,'.snbt');self.assertEqual(result['runtime_files'],[]);self.assertFalse(list(file.parents[1].rglob('*.nbt')));self.assertFalse((self.workspace/'nbt_models/_exports').exists());self.assertTrue(result['history'].get('commit'));self.assertEqual(read_master(file)[0].get((16,4,16)),'minecraft:stone_bricks')
 def test_finalize_uses_mirrored_tree_preserves_source_and_is_idempotent(self):
  draft=self.draft();file=Path(draft['master']);before=file.read_bytes();result=finalize(self.workspace,file);expected=self.workspace/'nbt_models/_exports'/file.parents[1].relative_to(self.workspace/'nbt_models');self.assertEqual(Path(result['output']),expected);self.assertEqual(file.read_bytes(),before);self.assertEqual(read_master(result['nbt_master'])[0].fingerprint(),draft['geometry_sha256']);self.assertTrue(result['runtime_files']);self.assertTrue(finalize(self.workspace,file)['unchanged']);self.assertFalse(any('_exports' in item['source'] for item in catalog(self.workspace/'nbt_models')['models']))
 def test_final_delivery_tamper_is_not_overwritten(self):
  result=finalize(self.workspace,Path(self.draft()['master']));target=Path(result['runtime_files'][0]);target.write_bytes(b'changed');self.assertRaisesRegex(ValueError,'修改',finalize,self.workspace,self.workspace/json.loads((Path(result['output'])/'release.json').read_text())['source']);self.assertEqual(target.read_bytes(),b'changed')

if __name__=='__main__':unittest.main(verbosity=2)
