"""Small-unit fitting must retain visible features before it is repeated."""
import json
from itertools import product
from math import cos,sin,pi
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
from nbt_microfit import regions,options_for,reference
from nbt_model import state
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

    def fitted_pixels(self,result):
        width,height=result['microfit']['unit_size_uv'];surface=result['surface']
        pixels=np.zeros((height*2,width*2),dtype=bool)
        data=build(self.root,result['spec'])
        for x,y,z,index,_ in data['blocks']:
            if surface=='ceiling':
                if y!=0:continue
                projected={(a,c) for a,b,c in collision_cells(data['palette'][index])[0] if b==0}
                for a,c in projected:pixels[z*2+c,x*2+a]=True
            else:
                if z!=1:continue
                for a,b,c in collision_cells(data['palette'][index])[0]:pixels[y*2+b,x*2+a]=True
        return pixels

    def native_scroll(self):
        points=[]
        for i in range(61):
            angle=i/60*2.8*pi;radius=.405-i/60*.36
            points.append([.5+radius*cos(angle),.5+radius*sin(angle)])
        return dispatch(self.root,'pattern_create',dict(name='原始失败卷草',resolution=[32,32],
            layers=[dict(kind='polyline',points=points,stroke=.11)]))

    def rectangular_stencil(self):
        rows=['########','##....##','######..','..##....']
        asset=dispatch(self.root,'pattern_create',dict(name='方图内的横向回折',resolution=[16,16],
            layers=[dict(kind='bitmap',rows=rows)]))
        return asset,np.array([[c=='#' for c in row] for row in reversed(rows)])

    def test_auto_alignment_recovers_original_native_scroll_without_editing(self):
        asset=self.native_scroll();sample=asset['fitting_input']['sample'];file=self.root/sample['path']
        before=file.read_bytes();request=dict(surface='wall',size_uv=[8,8],sample=sample)
        with self.assertRaisesRegex(ValueError,'孔洞0→1'):
            dispatch(self.root,'pattern_microfit',dict(request,micro_alignment='fixed'))
        result=dispatch(self.root,'pattern_microfit',request);quality=result['microfit'];alignment=quality['alignment']
        self.assertTrue(alignment['applied']);self.assertFalse(alignment['baseline_accepted'])
        self.assertEqual(quality['result_topology'],dict(components=1,holes=0))
        self.assertEqual(len(regions(self.fitted_pixels(result),False)),0)
        self.assertLessEqual(alignment['candidates_solved'],7)
        self.assertLessEqual(alignment['candidates_probed'],81)
        self.assertFalse(alignment['source_modified']);self.assertEqual(file.read_bytes(),before)
        repeated=dispatch(self.root,'pattern_microfit',request)
        self.assertEqual(result['content_sha256'],repeated['content_sha256'])
        self.assertEqual(result['microfit']['alignment'],repeated['microfit']['alignment'])
        self.assertEqual(result['spec']['size'],[8,8,2])
        tiled=dispatch(self.root,'pattern_microfit',dict(request,tile_counts=[2,1]))
        self.assertEqual(tiled['microfit']['alignment'],alignment)
        data=build(self.root,tiled['spec']);placed={(x,y):data['palette'][i] for x,y,z,i,_ in data['blocks'] if z==1}
        unit={(x,y):value for (x,y),value in placed.items() if x<8}
        self.assertEqual({(x-9,y):value for (x,y),value in placed.items() if x>=9},unit)
        cylinder=dispatch(self.root,'pattern_microfit',dict(request,surface='cylinder',diameter=9,tile_counts=[2,1]))
        self.assertEqual(cylinder['microfit']['alignment'],alignment)
        self.assertEqual(cylinder['shape_counts']['stairs'],result['shape_counts']['stairs']*2)

    def test_auto_aspect_adapts_square_image_to_rectangular_half_grid(self):
        asset,pixels=self.rectangular_stencil();sample=asset['fitting_input']['sample']
        result=dispatch(self.root,'pattern_microfit',dict(surface='wall',size_uv=[4,2],sample=sample))
        quality=result['microfit'];alignment=quality['alignment']
        self.assertEqual(alignment['ratio_mode'],'adapt')
        self.assertEqual(alignment['aspect_adjustment'],2)
        self.assertEqual(quality['ink_overlap'],1);self.assertEqual(quality['raw_coverage_error'],0)
        np.testing.assert_array_equal(self.fitted_pixels(result),pixels)
        explicit=dispatch(self.root,'pattern_microfit',dict(surface='wall',size_uv=[4,2],sample=dict(sample,fit='contain')))
        self.assertEqual(explicit['microfit']['alignment']['ratio_mode'],'contain')
        self.assertEqual(explicit['microfit']['alignment']['aspect_adjustment'],1)

    def test_aligned_palette_follows_the_same_source_mapping_as_geometry(self):
        asset,pixels=self.rectangular_stencil()
        alpha=Image.open(self.root/asset['fitting_input']['sample']['path']).convert('L')
        rgba=Image.new('RGBA',alpha.size,(255,0,0,255))
        ImageDraw.Draw(rgba).rectangle((8,0,15,15),fill=(0,0,255,255));rgba.putalpha(alpha)
        path=self.root/'colored-border.png';rgba.save(path)
        sample=dict(path=path.name,sha256=sha(path),noise_strength=0,channel='alpha',colors=[
            dict(rgb='#ff0000',material='red_concrete'),dict(rgb='#0000ff',material='blue_concrete')])
        result=dispatch(self.root,'pattern_microfit',dict(surface='wall',size_uv=[4,2],sample=sample))
        self.assertTrue(result['microfit']['alignment']['applied'])
        np.testing.assert_array_equal(self.fitted_pixels(result),pixels)
        data=build(self.root,result['spec']);values={(x,y):data['palette'][i] for x,y,z,i,_ in data['blocks'] if z==1}
        self.assertEqual(values[0,1],state('red_concrete'))
        self.assertEqual(values[3,1],state('blue_concrete'))
        self.assertEqual(values[1,0],state('red_concrete'))

    def test_auto_aligned_recipe_mounts_with_the_same_geometry_and_source_binding(self):
        asset=self.native_scroll();model=Volume((24,20,24));model.box([2,2,12],[20,18,12],'stone_bricks')
        source=self.root/'aligned-wall.snbt';save_master(source,model,set())
        context=self.root/'context.json';context.write_text(json.dumps(dict(mode='standalone',openings=[])))
        surface=dict(source=source.name,source_sha256=sha(source),geometry_sha256=model.fingerprint(),
            context=context.name,context_sha256=sha(context),lo=[2,2,12],hi=[20,18,12],normal='south')
        queried=dispatch(self.root,'parametric_surface',dict(surface=surface))
        compiled=dispatch(self.root,'pattern_microfit',dict(surface='wall',size_uv=[8,8],**asset['fitting_input']))
        result=dispatch(self.root,'pattern_mount',dict(surface=surface,surface_sha256=queried['surface_sha256'],
            object=compiled['mount_object'],anchor_uv=[8,3]))
        self.assertEqual(result['pattern']['microfit']['alignment'],compiled['microfit']['alignment'])
        self.assertTrue(result['pattern']['microfit']['backing_reused'])
        self.assertEqual(sha(source),surface['source_sha256'])
        self.assertFalse(result['model_modified'])

    def test_every_representable_half_block_stroke_keeps_its_exact_geometry(self):
        for surface in ('wall','ceiling'):
            shapes=dict(stairs='quartz_stairs')
            if surface=='wall':shapes['slab']='quartz_slab'
            options,factor=options_for(state('quartz_block'),shapes,surface)
            for value,mask in options:
                if value is None:continue
                with self.subTest(surface=surface,value=value):
                    target=np.array(mask,dtype=np.uint8).reshape(2,2)*255
                    path=self.root/'stroke.png'
                    Image.fromarray(np.flipud(target)).resize((32,32),Image.Resampling.NEAREST).save(path)
                    request=dict(surface=surface,size_uv=[1,1],sample=dict(path=path.name,sha256=sha(path),noise_strength=0))
                    result=dispatch(self.root,'pattern_microfit',request)
                    np.testing.assert_array_equal(self.fitted_pixels(result),target>0)
                    self.assertEqual(result['microfit']['ink_overlap'],1)
                    self.assertEqual(result['microfit']['raw_coverage_error'],0)
                    self.assertEqual(result['microfit']['contour_error'],0)
                    self.assertFalse(result['microfit']['stylized'])

    def test_joint_stair_and_slab_search_retains_small_scroll_detail(self):
        image=Image.new('L',(64,64));points=[]
        for i in range(121):
            angle=i/120*2.8*pi;radius=26-i/120*23
            points.append((32+radius*cos(angle),32+radius*sin(angle)))
        ImageDraw.Draw(image).line(points,fill=255,width=7)
        path=self.root/'scroll.png';image.save(path)
        request=dict(surface='wall',size_uv=[3,3],micro_alignment='fixed',sample=dict(path=path.name,sha256=sha(path),noise_strength=0))
        result=dispatch(self.root,'pattern_microfit',request);quality=result['microfit']
        self.assertEqual(quality['shape_search']['method'],'bounded_beam')
        self.assertLessEqual(quality['shape_search']['candidates_evaluated'],105)
        self.assertGreater(quality['ink_overlap'],quality['shape_search']['baseline_ink_overlap']+.03)
        self.assertLess(quality['contour_error'],quality['shape_search']['baseline_contour_error'])
        self.assertEqual(quality['result_topology'],dict(components=1,holes=0))
        self.assertGreater(result['shape_counts'].get('stairs',0),0)
        self.assertGreater(result['shape_counts'].get('slab',0),0)
        coverage=reference(self.root,request['sample'],3,3,2)[0];pixels=self.fitted_pixels(result)
        overlap=np.minimum(pixels,coverage).sum()/np.maximum(pixels,coverage).sum()
        self.assertAlmostEqual(quality['ink_overlap'],overlap)
        repeated=dispatch(self.root,'pattern_microfit',request)
        self.assertEqual(result['content_sha256'],repeated['content_sha256'])
        full=dispatch(self.root,'pattern_microfit',dict(request,full_blocks_only=True))
        self.assertGreater(quality['ink_overlap'],full['microfit']['ink_overlap'])
        # At eight blocks the legacy per-block choices accidentally close the
        # scroll's narrow entrance. Joint stair/slab choices retain that gap.
        large=dispatch(self.root,'pattern_microfit',dict(request,size_uv=[8,8]))
        self.assertFalse(large['microfit']['shape_search']['baseline_topology_preserved'])
        self.assertEqual(large['microfit']['source_topology']['holes'],0)
        self.assertEqual(len(regions(self.fitted_pixels(large),False)),0)
        self.assertEqual(len(regions(self.fitted_pixels(large))),1)

    def test_higher_ink_overlap_cannot_trade_away_existing_fine_edges(self):
        image=Image.new('L',(64,64))
        ImageDraw.Draw(image).line([(44,54),(40,17),(6,42),(14,21),(52,40)],fill=255,width=10)
        path=self.root/'angled-strokes.png';image.save(path)
        result=dispatch(self.root,'pattern_microfit',dict(surface='wall',size_uv=[3,3],
            sample=dict(path=path.name,sha256=sha(path),noise_strength=0)))
        quality=result['microfit'];baseline=quality['shape_search']
        self.assertTrue(baseline['baseline_topology_preserved'])
        self.assertGreaterEqual(quality['ink_overlap']+1e-12,baseline['baseline_ink_overlap'])
        self.assertLessEqual(quality['contour_error'],baseline['baseline_contour_error']+1e-12)

    def test_small_unit_search_matches_exhaustive_real_shape_optimum(self):
        image=Image.new('L',(64,64))
        ImageDraw.Draw(image).line([(8,56),(8,8),(44,8),(44,32),(28,32)],fill=255,width=10)
        path=self.root/'key.png';image.save(path)
        sample=dict(path=path.name,sha256=sha(path),noise_strength=0)
        result=dispatch(self.root,'pattern_microfit',dict(surface='wall',size_uv=[2,2],sample=sample,micro_alignment='fixed'))
        quality=result['microfit'];self.assertEqual(quality['shape_search']['method'],'exhaustive')
        self.assertEqual(quality['preserved_symmetry_axes'],[])
        coverage,ink,void,topology=reference(self.root,sample,2,2,2)
        # Independent oracle: rasterize actual collision geometry, not the
        # solver's precomputed silhouette table or its candidate scores.
        values=[None,'quartz_block','quartz_slab[type=bottom]','quartz_slab[type=top]']
        values += [f'quartz_stairs[facing={facing},half={half},shape=straight]'
                   for facing in ('east','west') for half in ('bottom','top')]
        best=0
        for combination in product(values,repeat=4):
            pixels=np.zeros((4,4),dtype=bool)
            for (x,y),value in zip(((0,0),(0,1),(1,0),(1,1)),combination):
                if value is not None:
                    for a,b,c in collision_cells(value)[0]:pixels[y*2+b,x*2+a]=True
            if any(not pixels[p] for p in ink) or any(pixels[p] for p in void):continue
            if len(regions(pixels))!=topology['components'] or len(regions(pixels,False))!=topology['holes']:continue
            if np.abs(pixels-coverage).mean()>.65:continue
            best=max(best,float(np.minimum(pixels,coverage).sum()/np.maximum(pixels,coverage).sum()))
        self.assertAlmostEqual(quality['ink_overlap'],best)

    def test_low_threshold_keeps_transparent_and_black_background_empty(self):
        for mode in ('L','RGBA'):
            with self.subTest(mode=mode):
                image=Image.new(mode,(32,32),0 if mode=='L' else (255,255,255,0))
                ImageDraw.Draw(image).rectangle((0,16,31,31),fill=255 if mode=='L' else (255,255,255,255))
                path=self.root/'low-threshold.png';image.save(path)
                result=dispatch(self.root,'pattern_microfit',dict(surface='wall',size_uv=[1,1],
                    sample=dict(path=path.name,sha256=sha(path),noise_strength=0,threshold=1)))
                self.assertEqual(result['shape_counts'],dict(slab=1))
                self.assertEqual(result['slab_orientations'],dict(bottom=1))
                self.assertEqual(result['microfit']['ink_overlap'],1)

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

    def test_cylinder_corners_keep_all_eighteen_rings_without_reducing_copies(self):
        from nbt_cylinder_fit import half_cells,topology,components
        result=dispatch(self.root,'pattern_microfit',dict(surface='cylinder',diameter=7,size_uv=[2,2],
            sample=self.sample,tile_counts=[6,3],gap_uv=[0,1]))
        self.assertEqual(result['microfit']['tile_counts'],[6,3])
        self.assertEqual(result['shape_counts'],dict(stairs=72,slab=18))
        self.assertEqual(result['microfit']['world_geometry']['corner_connector_blocks'],18)
        data=build(self.root,result['spec']);core,ring=cylinder_geometry(7)
        blocks={(x,y,z):data['palette'][i] for x,y,z,i,_ in data['blocks'] if (x,z) not in core}
        cells=half_cells(blocks);actual=topology(cells)
        self.assertEqual(actual['face_components'],18);self.assertEqual(actual['handles'],18)
        self.assertEqual(sorted(len(g) for g in components(cells)),[24]*9+[32]*9)
        # Topology fixtures also guard the Euler/air computation itself.
        solid={(x,y,z) for x in range(3) for y in range(3) for z in range(3)}
        hollow=solid-{(1,1,1)}
        self.assertEqual(topology(solid)['handles'],0)
        self.assertEqual(topology(hollow)['cavities'],1)
        self.assertEqual(topology(hollow)['handles'],0)
        self.assertEqual(topology({(0,0,0),(1,1,1)})['face_components'],2)
        self.assertEqual(topology({(0,0,0),(1,1,1)})['handles'],0)
        # Corner repair is an ordinary candidate: real protected bridge cells
        # remain subject to the existing mount guard, including its budget.
        model=Volume((24,16,24));lo=[5,2,5]
        for x,z in core:
            for y in range(8):model.put((lo[0]+x,lo[1]+y,lo[2]+z),'stone_bricks')
        source=self.root/'column-corner.snbt';save_master(source,model,set());before=source.read_bytes()
        context=self.root/'corner-context.json';context.write_text(json.dumps(dict(mode='standalone',openings=[])))
        target=dict(source=source.name,source_sha256=sha(source),geometry_sha256=model.fingerprint(),
            context=context.name,context_sha256=sha(context),lo=lo,hi=[13,9,13])
        proposal=result['mount_object']
        mounted=dispatch(self.root,'pattern_cylinder_mount',dict(target=target,object=proposal))
        self.assertEqual(mounted['changed_blocks'],90)
        faces={(f['x'],f['z']) for f in ring};connector=next(p for p in blocks if (p[0],p[2]) not in faces)
        point=[lo[i]+connector[i] for i in range(3)]
        with self.assertRaisesRegex(ValueError,'留白'):
            dispatch(self.root,'pattern_cylinder_mount',dict(target=target,object=proposal,reserved_boxes=[dict(lo=point,hi=point)]))
        with self.assertRaisesRegex(ValueError,'预算'):
            dispatch(self.root,'pattern_cylinder_mount',dict(target=target,object=proposal,max_changed_blocks=89))
        self.assertEqual(source.read_bytes(),before)

    def test_unreadable_units_noise_and_size_or_error_escape_are_rejected(self):
        cases=[dict(size_uv=[13,4]),dict(micro_max_error=.1),dict(repeat=[2,2]),dict(sample=dict(self.sample,noise_strength=1)),dict(micro_alignment='unbounded')]
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
