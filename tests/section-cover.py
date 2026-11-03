"""Geometry-bound section selection and persistent cache; synthetic images only."""
import json
import hashlib
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_cover import section_cover


class SectionCover(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
  self.root=Path(self.temp.name);self.folder=self.root/'model/version/master';self.folder.mkdir(parents=True)
  self.source=self.folder/'master.json.gz';self.source.write_bytes(b'index-only')
  self.cache=self.root/'cache';self.geometry='a'*64
 def image(self,name,**metadata):
  file=self.folder/'previews'/f'{name}.png';file.parent.mkdir(exist_ok=True)
  Image.new('RGB',(600,400),'#557799').save(file)
  file.with_suffix('.json').write_text(json.dumps({'geometry_sha256':self.geometry,**metadata}),encoding='utf8')
  return file
 def test_section_overview_beats_recent_closeup_and_wall_layer(self):
  self.image('overview',id='overview',layer='all',cuts=[dict(axis='y',position=8,removed_side='above')])
  self.image('local_section',id='node',layer='all',cuts=[dict(axis='x',position=8,removed_side='above')])
  self.image('ceiling',id='ceiling',layer='all',cuts=[])
  self.image('walls',id='overview',layer='walls',cuts=[dict(axis='y',position=8,removed_side='above')])
  result=section_cover(self.source,self.geometry,self.cache)
  self.assertEqual(Path(result['image']).name,'overview.png');self.assertTrue(result['section'])
  with Image.open(result['thumbnail']) as thumb:self.assertLessEqual(thumb.width,384)
 def test_warm_cache_does_not_decode_images_and_detects_new_section(self):
  self.image('whole',id='whole',layer='all',cuts=[])
  first=section_cover(self.source,self.geometry,self.cache)
  with patch('PIL.Image.open',side_effect=AssertionError('do not decode cached PNG')):
   warm=section_cover(self.source,self.geometry,self.cache)
  self.assertTrue(warm['cached']);self.assertEqual(warm['thumbnail'],first['thumbnail'])
  self.image('new_section',requested_view=dict(id='overview',layer='all',cut_y=8))
  changed=section_cover(self.source,self.geometry,self.cache)
  self.assertFalse(changed['cached']);self.assertTrue(changed['section']);self.assertTrue(changed['image'].endswith('new_section.png'))
 def test_other_geometry_is_never_shown_and_negative_cache_refreshes(self):
  self.image('wrong',geometry_sha256='b'*64,id='overview',cuts=[dict(axis='y',position=8,removed_side='above')])
  result=section_cover(self.source,self.geometry,self.cache);self.assertIsNone(result['image'])
  self.assertTrue(section_cover(self.source,self.geometry,self.cache)['cached'])
  self.image('matching',id='whole',layer='all')
  self.assertTrue(section_cover(self.source,self.geometry,self.cache)['image'].endswith('matching.png'))
 def test_metadata_change_invalidates_selection_and_deleted_image_is_not_returned(self):
  whole=self.image('whole',id='overview',layer='all')
  alternate=self.image('alternate',id='entry',layer='all')
  first=section_cover(self.source,self.geometry,self.cache);self.assertTrue(first['image'].endswith('whole.png'))
  alternate.with_suffix('.json').write_text(json.dumps(dict(geometry_sha256=self.geometry,id='overview',layer='all',cuts=[dict(axis='y',position=8,removed_side='above')])),encoding='utf8')
  second=section_cover(self.source,self.geometry,self.cache);self.assertTrue(second['section']);self.assertTrue(second['image'].endswith('alternate.png'))
  alternate.unlink();self.assertEqual(section_cover(self.source,self.geometry,self.cache)['image'],str(whole.resolve()))
 def test_source_change_and_missing_thumbnail_invalidate_cache(self):
  self.image('section',id='overview',layer='all',cuts=[dict(axis='y',position=8,removed_side='above')])
  first=section_cover(self.source,self.geometry,self.cache);Path(first['thumbnail']).unlink()
  self.assertFalse(section_cover(self.source,self.geometry,self.cache)['cached'])
  self.source.write_bytes(b'changed');self.assertFalse(section_cover(self.source,self.geometry,self.cache)['cached'])
 def test_source_hash_allows_unindexed_and_legacy_png_json_without_model_read(self):
  file=self.image('legacy',id='overview',cuts=[dict(axis='y',position=8,removed_side='above')])
  metadata=file.with_suffix('.json');metadata.unlink()
  Path(str(file)+'.json').write_text(json.dumps(dict(source_nbt_sha256=hashlib.sha256(self.source.read_bytes()).hexdigest(),cut=dict(axis='y',position=8,removed_side='above'))),encoding='utf8')
  with patch('nbt_refine.read_master',side_effect=AssertionError('browsing cannot decode a model')):
   result=section_cover(self.source,None,self.cache)
  self.assertEqual(result['image'],str(file.resolve()));self.assertTrue(result['section'])
  self.source.write_bytes(b'new version');self.assertIsNone(section_cover(self.source,None,self.cache)['image'])
 def test_deep_runtime_previews_discovered_and_other_version_not_used(self):
  section=self.image('section',id='overview',cuts=[dict(axis='y',position=8,removed_side='above')])
  deep=self.folder/'refined/runtime/parts/master.json.gz';deep.parent.mkdir(parents=True);deep.write_bytes(b'index-only')
  self.assertEqual(section_cover(deep,self.geometry,self.cache)['image'],str(section.resolve()))
  self.image('changed',geometry_sha256='b'*64,source_geometry_sha256=self.geometry)
  section.unlink();self.assertIsNone(section_cover(deep,self.geometry,self.cache)['image'])
 def test_corrupt_image_falls_back_to_valid_image(self):
  valid=self.image('valid',id='whole')
  broken=self.image('broken',id='overview',cuts=[dict(axis='y',position=8,removed_side='above')]);broken.write_bytes(b'broken')
  self.assertEqual(section_cover(self.source,self.geometry,self.cache)['image'],str(valid.resolve()))
 def test_missing_cover_only_generated_on_explicit_open_and_reused(self):
  from nbt_model import Model
  from nbt_refine import save_master
  model=Model((12,8,12));model.box((0,0,0),(11,7,11),'stone_bricks');model.box((1,1,1),(10,6,10),'air')
  save_master(self.source,model,set());original=self.source.read_bytes();geometry=model.fingerprint()
  self.assertIsNone(section_cover(self.source,geometry,self.cache)['image'])
  first=section_cover(self.source,geometry,self.cache,generate=True)
  self.assertTrue(first['generated']);self.assertTrue(first['section']);self.assertTrue(Path(first['thumbnail']).is_file())
  with patch('nbt_refine.read_master',side_effect=AssertionError('cache should skip decoding')):
   warm=section_cover(self.source,geometry,self.cache)
  self.assertEqual(warm['image'],first['image']);self.assertEqual(self.source.read_bytes(),original)

if __name__=='__main__':unittest.main(verbosity=2)
