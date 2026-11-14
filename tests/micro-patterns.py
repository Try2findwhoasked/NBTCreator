"""Small-unit fitting must retain visible features before it is repeated."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np
from PIL import Image,ImageDraw

ROOT=Path(__file__).resolve().parents[1];SCRIPTS=ROOT/'.agents/skills/minecraft-nbt-modeler/scripts'
sys.path.insert(0,str(SCRIPTS))
from nbt_structure_agent import dispatch,build
from nbt_microfit import regions
from nbt_collision import collision_cells
from nbt_cylinder_pattern import cylinder_geometry,touches_backing
from nbt_tools import transformed_state
from nbt_assembly import Volume
from nbt_refine import save_master
from nbt_selection_edit import sha


class MicroPatterns(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name)
        image=Image.new('L',(32,32));ImageDraw.Draw(image).rectangle([0,0,31,31],outline=255,width=2)
        self.source=self.root/'thin-ring.png';image.save(self.source)
        self.sample=dict(path=self.source.name,sha256=sha(self.source),noise_strength=0)

    def call(self,**args):
        return dispatch(self.root,'pattern_microfit',dict(surface='wall',size_uv=[2,2],sample=self.sample,**args))

    def test_two_block_ring_retains_hole_that_standard_sampling_loses(self):
        with self.assertRaisesRegex(ValueError,'没有生成可见'):
            dispatch(self.root,'pattern_compile',dict(surface='wall',size_uv=[2,2],sample=self.sample,shapes=dict(stairs='quartz_stairs',slab='quartz_slab')))
        result=self.call();self.assertEqual(result['spec']['size'],[2,2,2])
        self.assertEqual(result['shape_counts'],{'stairs':4})
        self.assertEqual(result['microfit']['source_topology']['holes'],1)
        self.assertEqual(result['microfit']['result_topology'],dict(holes=1,components=1))
        self.assertTrue(result['microfit']['stylized'])
        data=build(self.root,result['spec']);pixels=np.zeros((4,4),dtype=bool)
        for x,y,z,index,_ in data['blocks']:
            if z!=1:continue
            for a,b,c in collision_cells(data['palette'][index])[0]:pixels[2*y+b,2*x+a]=True
        self.assertEqual(len(regions(pixels,False)),1)
        self.assertEqual(len(regions(pixels)),1)
        self.assertTrue(np.array_equal(pixels,np.fliplr(pixels)))
        self.assertTrue(np.array_equal(pixels,np.flipud(pixels)))
        bar=Image.new('L',(16,16));ImageDraw.Draw(bar).rectangle([0,8,15,15],fill=255)
        file=self.root/'half-bar.png';bar.save(file)
        tiny=dispatch(self.root,'pattern_microfit',dict(surface='wall',size_uv=[1,1],sample=dict(path=file.name,sha256=sha(file),noise_strength=0)))
        self.assertEqual(tiny['shape_counts'],{'slab':1})
        self.assertEqual(tiny['slab_orientations'],{'bottom':1})
        self.assertEqual(tiny['microfit']['ink_overlap'],1)

    def test_layout_copies_identical_fitted_units_without_resampling(self):
        first=self.call();tiled=self.call(tile_counts=[3,2],gap_uv=[1,1])
        self.assertEqual(tiled['spec']['size'],[8,5,2])
        self.assertEqual(tiled['microfit']['placement'],'fit_once_then_copy')
        self.assertEqual(tiled['microfit']['raw_coverage_error'],first['microfit']['raw_coverage_error'])
        a=build(self.root,first['spec']);b=build(self.root,tiled['spec'])
        unit={(x,y):a['palette'][i] for x,y,z,i,_ in a['blocks'] if z==1}
        actual={(x,y):b['palette'][i] for x,y,z,i,_ in b['blocks'] if z==1}
        self.assertEqual(len(actual),6*len(unit))
        for col in range(3):
            for row in range(2):
                self.assertEqual({(x-col*3,y-row*3):value for (x,y),value in actual.items() if col*3<=x<col*3+2 and row*3<=y<row*3+2},unit)

    def test_floor_and_ceiling_obey_their_real_shape_limits(self):
        for surface in ('floor','ceiling'):
            with self.assertRaisesRegex(ValueError,'尺寸无法'):
                dispatch(self.root,'pattern_microfit',dict(surface=surface,size_uv=[2,2],sample=self.sample))
            result=dispatch(self.root,'pattern_microfit',dict(surface=surface,size_uv=[3,3],sample=self.sample))
            self.assertTrue(result['microfit']['topology_preserved'])
            data=build(self.root,result['spec'])
            if surface=='floor':
                self.assertEqual(data['size'][1],1)
                self.assertTrue(all(len(collision_cells(v)[0])==8 for v in data['palette']))
            else:
                for x,y,z,index,_ in data['blocks']:
                    if y==0:self.assertTrue(any(p[1]==1 for p in collision_cells(data['palette'][index])[0]))

    def test_cylinder_wrap_rotates_each_micro_unit_without_stretching(self):
        result=dispatch(self.root,'pattern_microfit',dict(surface='cylinder',diameter=9,size_uv=[2,2],sample=self.sample,tile_counts=[4,3]))
        self.assertEqual(result['cylinder']['diameter'],9)
        self.assertEqual(result['cylinder']['height'],8)
        self.assertEqual(result['shape_counts'],{'stairs':4*4*3})
        self.assertEqual(len(result['stair_orientations']),8)
        core,ring=cylinder_geometry(9);faces={(f['x'],f['z']):f for f in ring}
        data=build(self.root,result['spec'])
        for x,y,z,index,_ in data['blocks']:
            if (x,z) not in core:self.assertTrue(touches_backing(data['palette'][index],faces[x,z]))
        # The existing bound cylinder interface accepts the same micro recipe.
        model=Volume((24,16,24));lo=[5,2,5]
        for x,z in core:
            for y in range(8):model.put((lo[0]+x,lo[1]+y,lo[2]+z),'stone_bricks')
        source=self.root/'column.snbt';save_master(source,model,set())
        context=self.root/'context.json';context.write_text(json.dumps(dict(mode='standalone',openings=[])))
        target=dict(source=source.name,source_sha256=sha(source),geometry_sha256=model.fingerprint(),context=context.name,context_sha256=sha(context),lo=lo,hi=[15,9,15])
        proposal=dict(surface='cylinder',fit_mode='micro',diameter=9,size_uv=[2,2],sample=self.sample,tile_counts=[4,3])
        mounted=dispatch(self.root,'pattern_cylinder_mount',dict(target=target,object=proposal))
        self.assertEqual(mounted['changed_blocks'],48);self.assertEqual(mounted['pattern']['microfit']['unit_size_uv'],[2,2])
        self.assertEqual(sha(source),target['source_sha256'])

    def test_unreadable_units_noise_and_size_or_error_escape_are_rejected(self):
        cases=[dict(size_uv=[13,4]),dict(micro_max_error=.1),dict(repeat=[2,2]),dict(sample=dict(self.sample,noise_strength=1))]
        for patch in cases:
            with self.subTest(patch=patch),self.assertRaises(ValueError):
                request=dict(surface='wall',size_uv=[2,2],sample=self.sample);request.update(patch)
                dispatch(self.root,'pattern_microfit',request)
        with self.assertRaisesRegex(ValueError,'铺排后'):
            dispatch(self.root,'pattern_microfit',dict(surface='wall',size_uv=[6,6],sample=self.sample,tile_counts=[16,16]))
        self.assertFalse(list(self.root.rglob('draft.master.json.gz')))

    def test_preview_unit_recipe_and_micro_first_default_drawing(self):
        result=self.call(preview=True,tile_counts=[3,3])
        self.assertTrue(Path(result['thumbnail']).is_file())
        record=json.loads((Path(result['source']).parent/'draft.json').read_text(encoding='utf8'))
        self.assertEqual(record['pattern_recipe']['microfit']['unit_size_uv'],[2,2])
        asset=dispatch(self.root,'pattern_create',dict(name='微型环',layers=[dict(kind='ellipse'),dict(kind='ellipse',bounds=[.3,.3,.7,.7],blend='subtract')]))
        self.assertEqual(asset['resolution'],[16,16])
        simple=dispatch(self.root,'pattern_microfit',dict(surface='wall',size_uv=[4,4],**asset['fitting_input']))
        self.assertTrue(simple['microfit']['topology_preserved'])
        self.assertEqual(simple['microfit']['preserved_symmetry_axes'],['x','y'])
        data=build(self.root,simple['spec']);pixels=np.zeros((8,8),dtype=bool)
        for x,y,z,index,_ in data['blocks']:
            if z==1:
                for a,b,c in collision_cells(data['palette'][index])[0]:pixels[y*2+b,x*2+a]=True
        self.assertTrue(np.array_equal(pixels,np.fliplr(pixels)))
        self.assertTrue(np.array_equal(pixels,np.flipud(pixels)))

    def test_planar_mount_uses_unit_layout_and_maintains_source_binding(self):
        model=Volume((24,20,24));model.box([2,2,12],[20,18,12],'stone_bricks')
        source=self.root/'wall.snbt';save_master(source,model,set())
        context=self.root/'context.json';context.write_text(json.dumps(dict(mode='standalone',openings=[])))
        surface=dict(source=source.name,source_sha256=sha(source),geometry_sha256=model.fingerprint(),context=context.name,context_sha256=sha(context),lo=[2,2,12],hi=[20,18,12],normal='south')
        queried=dispatch(self.root,'parametric_surface',dict(surface=surface))
        proposal=dict(surface='wall',fit_mode='micro',size_uv=[2,2],sample=self.sample,tile_counts=[2,2])
        result=dispatch(self.root,'pattern_mount',dict(surface=surface,surface_sha256=queried['surface_sha256'],object=proposal,anchor_uv=[8,3]))
        self.assertEqual(result['pattern']['microfit']['unit_size_uv'],[2,2]);self.assertFalse(result['model_modified'])
        self.assertTrue(result['pattern']['microfit']['backing_reused'])
        self.assertEqual(result['changed_blocks'],16)
        self.assertEqual({op['lo'][2]+b[2] for op in result['operations'] for b in op['voxels']},{13})
        self.assertEqual(sha(source),surface['source_sha256'])

    def test_frozen_facade_discovers_and_executes_microfit(self):
        from nbt_exposure import apply
        apply(self.root)
        args=dict(surface='wall',size_uv=[2,2],sample=self.sample,tile_counts=[2,2])
        file=self.root/'micro.json';file.write_text(json.dumps(args))
        run=subprocess.run([sys.executable,str(self.root/'.agents/skills/nbtcreator-workspace/nbt.py'),'components','agent','--tool','pattern_microfit','--request',str(file)],cwd=self.root,capture_output=True,text=True,encoding='utf8')
        self.assertEqual(run.returncode,0,(run.stdout+run.stderr)[-2000:])
        result=json.loads(run.stdout)['result'];self.assertEqual(result['microfit']['unit_size_uv'],[2,2])
        self.assertEqual(result['microfit']['tile_counts'],[2,2])


if __name__=='__main__':unittest.main(verbosity=2)
