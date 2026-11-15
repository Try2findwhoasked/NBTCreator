"""Pattern authoring, ROI fitting, composition and native asset regressions."""
import base64
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
SCRIPTS=ROOT/'.agents/skills/minecraft-nbt-modeler/scripts'
sys.path.insert(0,str(SCRIPTS))
from nbt_structure_agent import dispatch
from nbt_selection_edit import sha


class PatternAssets(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name)

    def call(self,tool,**args):return dispatch(self.root,tool,args)

    def test_architectural_presets_are_visible_and_compile_on_each_advertised_surface(self):
        presets = ('roman-coffer', 'byzantine-cross-mosaic', 'ottoman-eight-point-star',
                   'egyptian-lotus-band', 'chinese-window-lattice', 'japanese-asanoha-lattice',
                   'art-deco-sunburst', 'gothic-pointed-tracery')
        manifest = self.call('pattern_list')['patterns']
        listing = {item['id']: item for item in self.call('pattern_assets', action='list')['items']}
        for key in presets:
            with self.subTest(preset=key):
                asset = listing['builtin:' + key]
                self.assertEqual(asset['fitting_defaults']['mode'], 'standard')
                self.assertEqual(asset['fitting_defaults']['size_uv'], [32, 32])
                self.assertEqual(asset['image_sha256'], manifest[key]['sha256'])
                for surface in manifest[key]['surfaces']:
                    args = dict(preset=key, surface=surface, size_uv=[12, 24] if surface == 'cylinder' else [32, 32])
                    result = self.call('pattern_compile', **args)
                    self.assertGreater(result['block_count'], 0)
                    self.assertEqual(result['sample_sha256'], asset['image_sha256'])
        subprocess.run([sys.executable, str(ROOT / 'scripts/build-interior-patterns.py'), '--check'],
                       cwd=ROOT, check=True, capture_output=True, text=True)

    def make(self,**patch):
        return self.call('pattern_create',**dict(dict(name='八瓣镂空花',resolution=[64,64],layers=[
            dict(kind='ellipse',bounds=[.4,.06,.6,.5],radial_count=8),
            dict(kind='ellipse',bounds=[.43,.43,.57,.57],blend='subtract')]),**patch))

    def test_small_bitmap_is_generated_as_image_then_fitted_on_all_surfaces(self):
        rows=['..##..','.#..#.','#....#','#....#','.#..#.','..##..']
        asset=self.make(layers=[dict(kind='bitmap',rows=rows)],resolution=[48,48])
        image=Image.open(asset['image']);self.assertEqual(image.size,(48,48))
        self.assertEqual(image.getpixel((0,0)),0);self.assertEqual(image.getpixel((20,0)),255)
        self.assertEqual(image.getpixel((20,20)),0)
        for surface in ('floor','wall','column','ceiling','cylinder'):
            with self.subTest(surface=surface):
                request=dict(surface=surface,size_uv=[13,24] if surface=='cylinder' else [24,24],**asset['fitting_input'])
                if surface!='floor':request['shapes']=dict(stairs='quartz_stairs')
                if surface in ('wall','column','cylinder'):request['shapes']['slab']='quartz_slab'
                result=self.call('pattern_compile',**request)
                self.assertGreater(result['block_count'],0);self.assertFalse(result['model_modified'])
        self.assertFalse(list(self.root.rglob('*.nbt')))

    def test_crop_in_shared_sampler_matches_separate_roi_image_and_preserves_colors(self):
        original=self.root/'reference.png';image=Image.new('RGB',(16,16),'white')
        for x in range(8,16):
            for y in range(16):image.putpixel((x,y),(0,0,0))
        for x in range(4):
            for y in range(8):image.putpixel((x,y),(255,0,0))
        image.save(original);before=original.read_bytes()
        roi=[0,0,.5,1];cropped=self.root/'roi.png';image.crop((0,0,8,16)).save(cropped)
        common=dict(surface='wall',size_uv=[16,24],shapes=dict(stairs='quartz_stairs',slab='quartz_slab'))
        colors=[dict(rgb='#FFFFFF',material='quartz_block'),dict(rgb='#FF0000',material='red_concrete')]
        result=self.call('pattern_compile',**common,sample=dict(path=original.name,sha256=sha(original),crop=roi,noise_strength=0,colors=colors,threshold=10))
        expected=self.call('pattern_compile',**common,sample=dict(path=cropped.name,sha256=sha(cropped),noise_strength=0,colors=colors,threshold=10))
        self.assertEqual(result['content_sha256'],expected['content_sha256'])
        self.assertEqual(original.read_bytes(),before)
        with self.assertRaisesRegex(ValueError,'crop'):
            self.call('pattern_compile',**common,sample=dict(path=original.name,sha256=sha(original),crop=[.8,0,.2,1]))

    def test_geometric_layers_compose_repeat_rotate_and_subtract_deterministically(self):
        first=self.make();second=self.make()
        self.assertEqual(first['image_sha256'],second['image_sha256']);self.assertNotEqual(first['id'],second['id'])
        image=Image.open(first['image']);self.assertLess(image.getpixel((32,32)),128)
        self.assertGreater(image.getpixel((32,7)),128)
        for blend,expected in [('union',255),('intersect',0),('subtract',255),('xor',255),('add',255)]:
            value=self.make(layers=[dict(kind='rect',bounds=[0,0,.4,1]),dict(kind='rect',bounds=[.2,0,1,1],blend=blend)])
            self.assertEqual(Image.open(value['image']).getpixel((10,32)),expected)
        # Curved strokes and transformed stencils are composable sources too.
        value=self.make(layers=[dict(kind='preset',preset='diamond-lattice',repeat=[2,2],rotation=45),
            dict(kind='bezier',points=[[0,.5],[.3,0],[.7,1],[1,.5]],stroke=.05,flip_y=True),
            dict(kind='polyline',points=[[.1,.1],[.9,.1],[.9,.9]],stroke=.02),
            dict(kind='polygon',points=[[.3,.3],[.7,.3],[.5,.7]],fill=False)])
        self.assertTrue(Path(value['thumbnail']).is_file())
        self.assertEqual(value['recipe']['sources'][0]['id'],'builtin:diamond-lattice')

    def test_asset_lifecycle_import_copy_recipe_and_checksum_bound_reuse(self):
        listed=self.call('pattern_assets',action='list')['items'];self.assertGreaterEqual(len(listed),20)
        self.assertFalse((self.root/'nbt_models/asset_library/patterns').exists())
        asset=self.make();self.assertEqual(asset['asset_type'],'ornament_pattern')
        loaded=self.call('pattern_assets',action='get',id=asset['id']);self.assertEqual(loaded['recipe']['generator'],'nbt_pattern_design')
        changed=self.call('pattern_assets',action='update',id=asset['id'],content_sha256=asset['content_sha256'],name='已改名',tags=['墙面'])
        self.assertEqual(changed['image_sha256'],asset['image_sha256'])
        with self.assertRaisesRegex(ValueError,'已变化'):
            self.call('pattern_assets',action='update',id=asset['id'],content_sha256=asset['content_sha256'],archived=True)
        # Renaming is metadata-only; the same image-bound stamp remains reusable.
        composite=self.make(layers=[dict(kind='asset',id=asset['id'],image_sha256=asset['image_sha256'])])
        self.assertEqual(composite['recipe']['sources'][0]['image_sha256'],asset['image_sha256'])
        copy=self.call('pattern_assets',action='copy',id=asset['id'],image_sha256=asset['image_sha256'],crop=[0,0,.5,1],name='半片花')
        self.assertEqual(copy['resolution'],[32,64]);self.assertTrue(Path(copy['file']).with_name('original.image').is_file())
        original=self.root/'photo.png';Image.new('RGB',(8,8),'white').save(original)
        imported=self.call('pattern_assets',action='import',name='导入',sample=dict(path=original.name,sha256=sha(original),crop=[0,0,.5,1]))
        self.assertEqual(imported['resolution'],[4,8]);self.assertEqual(imported['original_sha256'],sha(original))
        raw=base64.b64encode(original.read_bytes()).decode()
        upload=self.call('pattern_assets',action='import',name='上传',image_base64=raw)
        self.assertEqual(upload['resolution'],[8,8])
        archived=self.call('pattern_assets',action='update',id=asset['id'],content_sha256=changed['content_sha256'],archived=True)
        self.assertTrue(archived['archived']);self.assertTrue(Path(archived['image']).is_file())
        Path(copy['image']).write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'哈希'):
            self.call('pattern_assets',action='get',id=copy['id'])

    def test_invalid_and_executable_fields_and_outside_sources_are_rejected(self):
        for layer in [dict(kind='shell',command='whoami'),dict(kind='rect',script='code'),dict(kind='bitmap',rows=['##','#']),dict(kind='bezier',points=[[0,0],[1,1]]),dict(kind='asset',id='0'*32,image_sha256='0'*64)]:
            with self.subTest(layer=layer),self.assertRaises((ValueError,OSError)):
                self.make(layers=[layer])
        with self.assertRaisesRegex(ValueError,'为空'):
            self.make(layers=[dict(kind='rect'),dict(kind='rect',blend='subtract')])
        outside=self.root.parent/(self.root.name+'-outside.png');Image.new('L',(4,4),255).save(outside);self.addCleanup(outside.unlink)
        with self.assertRaisesRegex(ValueError,'工作区内'):
            self.call('pattern_assets',action='import',name='越界',sample=dict(path='../'+outside.name,sha256=sha(outside)))
        with self.assertRaisesRegex(ValueError,'不适用'):
            self.call('pattern_assets',action='list',image_base64='data')
        with self.assertRaisesRegex(ValueError,'其中一种'):
            self.call('pattern_assets',action='import',name='无源')

    def test_frozen_facade_exposes_generation_crop_and_assets(self):
        from nbt_exposure import apply
        apply(self.root)
        request=dict(name='小徽记',resolution=[32,32],layers=[dict(kind='bitmap',rows=['.#.','###','.#.'])])
        file=self.root/'request.json';file.write_text(json.dumps(request))
        run=subprocess.run([sys.executable,str(self.root/'.agents/skills/nbtcreator-workspace/nbt.py'),'components','agent','--tool','pattern_create','--request',str(file)],cwd=self.root,capture_output=True,text=True,encoding='utf8')
        self.assertEqual(run.returncode,0,(run.stdout+run.stderr)[-2000:])
        asset=json.loads(run.stdout)['result']
        self.assertTrue(Path(asset['image']).is_file())
        self.assertEqual(self.call('pattern_assets',action='get',id=asset['id'])['image_sha256'],asset['image_sha256'])


if __name__=='__main__':unittest.main(verbosity=2)
