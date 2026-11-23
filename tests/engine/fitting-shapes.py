"""Fine silhouettes preserve thin geometry, state transforms and public boundaries."""
from hashlib import sha256
import json
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_fit_shapes import FIT_SHAPES, FitShape, fine_options, project_shape
from nbt_pattern.microfit import options_for
from nbt_model import state
from nbt_modeling_session import engine_revision
from nbt_refine import read_master
from nbt_registry import effective
from nbt_structure_agent import dispatch, build
from nbt_tools import transformed_state
from nbt_working_model import WorkingModel


class FittingShapes(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    def request(self, pixels, **options):
        source = self.root/'mask.png'
        Image.fromarray(np.flipud(pixels).astype(np.uint8)*255).resize((128,128),Image.Resampling.NEAREST).save(source)
        return dict(surface='wall',size_uv=[1,1],micro_alignment='fixed',
            sample=dict(path=source.name,sha256=sha256(source.read_bytes()).hexdigest(),noise_strength=0),**options)

    def compile(self, pixels, **options):
        return dispatch(self.root,'pattern_microfit',self.request(pixels,**options))

    def test_trapdoor_preserves_three_pixel_thickness_and_open_orientation(self):
        options,factor = fine_options(state('quartz_block'),dict(trapdoor='spruce_trapdoor'),'wall')
        self.assertEqual(factor,16)
        masks = {effective(value)[1]['open']+'/'+effective(value)[1]['facing']+'/'+effective(value)[1]['half']:
                 np.asarray(mask).reshape(16,16) for value,mask in options if value and '_trapdoor' in value}
        self.assertEqual(int(masks['false/north/bottom'].sum()),48)
        self.assertTrue(masks['false/north/bottom'][:3,:].all())
        self.assertFalse(masks['false/north/bottom'][3:,:].any())
        self.assertTrue(masks['true/east/bottom'][:,:3].all())
        self.assertTrue(masks['true/west/bottom'][:,13:].all())

    def test_wall_projection_uses_post_and_low_or_tall_side_height(self):
        candidates = FIT_SHAPES['wall']('cobblestone_wall','wall')
        for up,height,expected in (('false','low',84),('false','tall',96),('true','low',128)):
            candidate = next(shape for shape in candidates if all(effective(shape.value)[1][k]==v
                for k,v in dict(up=up,north=height,east='none',west='none').items()))
            self.assertEqual(sum(project_shape(candidate,'wall')),expected)
        self.assertTrue(all(effective(shape.value)[1]['north']!='none' for shape in candidates))

    def test_horizontal_thin_strip_selects_trapdoor_and_beats_half_block_fit(self):
        pixels = np.zeros((16,16),dtype=bool);pixels[:3,:] = True
        fine = self.compile(pixels,shapes=dict(slab='quartz_slab',stairs='quartz_stairs',trapdoor='spruce_trapdoor'))
        self.assertEqual(fine['shape_counts'],dict(trapdoor=1))
        self.assertEqual(fine['microfit']['ink_overlap'],1)
        self.assertEqual(fine['microfit']['subcells_per_block'],256)
        self.assertFalse(fine['microfit']['collision_validated'])
        coarse = self.compile(pixels,shapes=dict(slab='quartz_slab',stairs='quartz_stairs'))
        self.assertGreater(fine['microfit']['ink_overlap'],coarse['microfit']['ink_overlap'])
        self.assertEqual(coarse['microfit']['subcells_per_block'],4)

    def test_vertical_center_stroke_selects_stone_wall(self):
        pixels = np.zeros((16,16),dtype=bool);pixels[:,4:12] = True
        result = self.compile(pixels,shapes=dict(wall='cobblestone_wall'))
        self.assertEqual(result['shape_counts'],dict(wall=1))
        self.assertEqual(result['microfit']['ink_overlap'],1)
        data = build(self.root,result['spec'])
        value = next(value for value in data['palette'] if '_wall[' in value)
        _,props = effective(value)
        self.assertEqual(props['north'],'low')
        rotated = effective(transformed_state(value,1,None))[1]
        self.assertEqual(rotated['east'],'low')
        self.assertEqual(rotated['north'],'none')

    def test_ceiling_open_trapdoor_uses_visible_strip_and_touches_backing(self):
        pixels = np.zeros((16,16),dtype=bool);pixels[:,:3] = True
        request = self.request(pixels,shapes=dict(trapdoor='spruce_trapdoor'))
        request['surface'] = 'ceiling'
        result = dispatch(self.root,'pattern_microfit',request)
        self.assertEqual(result['shape_counts'],dict(trapdoor=1))
        self.assertEqual(result['microfit']['ink_overlap'],1)
        value = next(value for value in build(self.root,result['spec'])['palette'] if '_trapdoor[' in value)
        self.assertEqual(effective(value)[1]['open'],'true')

    def test_real_recipe_install_save_and_snbt_readback_preserve_states(self):
        pixels = np.zeros((16,16),dtype=bool);pixels[:3,:] = True
        args = self.request(pixels,shapes=dict(trapdoor='spruce_trapdoor'))
        before = set(self.root.rglob('*'))
        model = WorkingModel(self.root,[8,8,8],kind='component')
        model.install('thin_panel',dict(tool='pattern_microfit',arguments=args),[3,2,3],quarter_turns=1)
        self.assertEqual(set(self.root.rglob('*')),before)
        saved = model.save_draft('薄构件拟合')
        reread,_ = read_master(saved['source'])
        values = [value for value in reread.blocks.values() if '_trapdoor[' in value]
        self.assertEqual(len(values),1)
        self.assertEqual(effective(values[0])[1]['facing'],'east')
        self.assertIn('thin_panel',WorkingModel.open(self.root,saved['source']).instances)
        self.assertFalse((self.root/'nbt_models/_exports').exists())

    def test_unsupported_surfaces_and_standard_mode_reject_explicitly(self):
        pixels = np.zeros((16,16),dtype=bool);pixels[:3,:] = True
        args = self.request(pixels,shapes=dict(trapdoor='spruce_trapdoor'))
        with self.assertRaisesRegex(ValueError,'pattern_microfit'):
            dispatch(self.root,'pattern_compile',args)
        for surface in ('floor','cylinder'):
            with self.subTest(surface=surface),self.assertRaises(ValueError):
                dispatch(self.root,'pattern_microfit',dict(args,surface=surface))
        with self.assertRaisesRegex(ValueError,'石墙拟合'):
            fine_options(state('stone'),dict(wall='cobblestone_wall'),'ceiling')

    def test_invalid_materials_water_and_unknown_public_families_are_rejected(self):
        pixels = np.ones((16,16),dtype=bool)
        for shapes in (dict(wall='stone'),dict(trapdoor='spruce_trapdoor[waterlogged=true]'),dict(button='stone_button'),dict(pane='glass_pane[waterlogged=true]'),dict(bars='iron_bars[waterlogged=true]')):
            with self.subTest(shapes=shapes),self.assertRaises(ValueError):
                self.compile(pixels,shapes=shapes)

    def test_registry_extensions_are_validated_and_invalidate_engine_identity(self):
        before = engine_revision()
        def provider(material,surface):
            return [FitShape(state(material),((0,0,0,4,16,16),))]
        FIT_SHAPES.register('test_panel',provider,version='test-panel-v1')
        self.addCleanup(lambda:FIT_SHAPES.unregister('test_panel'))
        self.assertNotEqual(before,engine_revision())
        options,factor = options_for(state('stone'),dict(test_panel='stone'),'wall')
        self.assertEqual(factor,16)
        self.assertEqual(sum(options[1][1]),64)
        with self.assertRaises(ValueError):
            FIT_SHAPES.register('test_panel',provider)
        with self.assertRaisesRegex(ValueError,'像素边界'):
            project_shape(FitShape(state('stone'),((0,0,0,17,16,16),)),'wall')

    def test_default_half_grid_candidates_are_unchanged(self):
        options,factor = options_for(state('quartz_block'),dict(stairs='quartz_stairs',slab='quartz_slab'),'wall')
        self.assertEqual((len(options),factor),(8,2))
        self.assertTrue(all(len(mask)==4 for _,mask in options))

    def test_wall_connections_and_trapdoor_hinges_follow_rotation_and_mirror(self):
        wall = state('cobblestone_wall[north=low,east=tall,south=none,west=low,up=false]')
        mirrored = effective(transformed_state(wall,0,'x'))[1]
        self.assertEqual((mirrored['east'],mirrored['west']),('low','tall'))
        self.assertEqual(mirrored['up'],'false')
        value = wall
        for _ in range(4):value = transformed_state(value,1,None)
        self.assertEqual(effective(value),effective(wall))
        door = state('spruce_trapdoor[facing=east,half=top,open=true,powered=true]')
        props = effective(transformed_state(door,1,'x'))[1]
        self.assertEqual(props['facing'],'north')
        self.assertEqual((props['half'],props['open'],props['powered']),('top','true','true'))
        with self.assertRaisesRegex(ValueError,'Transform does not support'):
            transformed_state('oak_door',1,None)


    def fit_mask(self, pixels, shapes):
        image=self.root/'exact-mask.png'
        Image.fromarray(np.flipud(pixels).astype('uint8')*255).save(image)
        height,width=pixels.shape
        return dispatch(self.root,'pattern_microfit',dict(surface='wall',size_uv=[width//16,height//16],
            micro_alignment='fixed',shapes=shapes,sample=dict(path=image.name,sha256=sha256(image.read_bytes()).hexdigest(),noise_strength=0,fit='stretch')))

    def test_panes_bars_and_fence_fit_distinct_thin_stroke_widths(self):
        for family,material,lo,hi in (('pane','glass_pane',7,9),('bars','iron_bars',7,9),('fence','oak_fence',6,10)):
            with self.subTest(family=family):
                pixels=np.zeros((16,16),dtype=bool);pixels[:,lo:hi]=True
                result=self.fit_mask(pixels,{family:material})
                self.assertEqual(result['shape_counts'],{family:1})
                self.assertEqual(result['microfit']['ink_overlap'],1)
                self.assertEqual(result['microfit']['unsupported_positions'],0)

    def test_snow_carpet_and_pressure_plate_need_real_support_in_the_fitted_unit(self):
        for family,material,height,lo,hi in (('snow','snow',2,0,16),('carpet','red_carpet',1,0,16),('pressure_plate','stone_pressure_plate',1,1,15)):
            with self.subTest(family=family):
                pixels=np.zeros((32,16),dtype=bool);pixels[:16,:]=True;pixels[16:16+height,lo:hi]=True
                result=self.fit_mask(pixels,{family:material})
                self.assertEqual(result['shape_counts'],dict(full=1,**{family:1}))
                self.assertEqual(result['microfit']['ink_overlap'],1)
                values=build(self.root,result['spec'])['palette']
                if family=='snow':self.assertIn(state('snow[layers=1]'),values)
                # An identical unsupported layer cannot pass the same fit budget.
                image=self.root/'unsupported.png';Image.fromarray(np.flipud(pixels[16:,:]).astype('uint8')*255).save(image)
                with self.assertRaises(ValueError):
                    dispatch(self.root,'pattern_microfit',dict(surface='wall',size_uv=[1,1],micro_alignment='fixed',
                        micro_max_error=.01,shapes={family:material},sample=dict(path=image.name,sha256=sha256(image.read_bytes()).hexdigest(),noise_strength=0,fit='stretch')))

    def test_end_rod_and_chain_can_attach_to_a_real_neighbor(self):
        pixels=np.zeros((32,16),dtype=bool);pixels[:16,:]=True
        pixels[16,6:10]=True;pixels[17:,7:9]=True
        result=self.fit_mask(pixels,dict(end_rod='end_rod'))
        self.assertEqual(result['shape_counts'],dict(full=1,end_rod=1))
        self.assertEqual(result['microfit']['ink_overlap'],1)
        image=self.root/'chain.png';pixels=np.zeros((64,32),dtype=bool);pixels[:32,:]=True;pixels[32:,13:19]=True
        Image.fromarray(np.flipud(pixels).astype('uint8')*255).save(image)
        result=dispatch(self.root,'pattern_microfit',dict(surface='wall',size_uv=[1,2],micro_alignment='fixed',
            shapes=dict(chain='chain'),sample=dict(path=image.name,sha256=sha256(image.read_bytes()).hexdigest(),noise_strength=0,fit='stretch')))
        self.assertEqual(result['shape_counts'],dict(full=1,chain=1))
        self.assertEqual(result['microfit']['projection_resolution'],32)
        self.assertEqual(result['microfit']['ink_overlap'],1)
        self.assertTrue(result['microfit']['approximate_states'])

    def test_new_connection_and_layer_states_survive_transforms(self):
        for value in ('glass_pane[north=true,east=false,south=false,west=true]',
                      'iron_bars[north=true,east=false,south=false,west=false]',
                      'oak_fence[north=true,east=false,south=false,west=false]'):
            props=effective(transformed_state(value,1,None))[1]
            self.assertEqual(props['east'],'true')
            self.assertEqual(props['north'],effective(value)[1]['west'])
        for value in ('snow[layers=7]','stone_pressure_plate[powered=true]','heavy_weighted_pressure_plate[power=9]','chain[axis=x]','end_rod[facing=up]'):
            state(transformed_state(value,1,'z'))
        self.assertEqual(effective(transformed_state('chain[axis=x]',1,None))[1]['axis'],'z')

    def test_complex_existing_solution_is_seeded_and_preserves_all_seventeen_holes(self):
        result=dispatch(self.root,'pattern_microfit',dict(surface='wall',preset='gothic-rose',size_uv=[8,8],
            material='stone_bricks',micro_alignment='fixed',quality_profile='ornate',
            shapes=dict(slab='stone_brick_slab',stairs='stone_brick_stairs',wall='stone_brick_wall')))
        quality=result['microfit']
        self.assertEqual(quality['result_topology']['holes'],17)
        self.assertTrue(quality['topology_preserved'])
        self.assertGreaterEqual(quality['shape_search']['seed_candidates_evaluated'],1)
        self.assertEqual(quality['quality_sampling_resolution'],32)
        with self.assertRaisesRegex(ValueError,'纹样量化质量未达标'):
            dispatch(self.root,'pattern_microfit',dict(surface='wall',preset='gothic-rose',size_uv=[8,8],
                material='stone_bricks',micro_alignment='fixed',quality_profile='ornate',min_quality_score=100,
                shapes=dict(slab='stone_brick_slab',stairs='stone_brick_stairs',wall='stone_brick_wall')))

    def test_matching_wall_is_in_automatic_candidates_without_an_explicit_shapes_field(self):
        pixels=np.zeros((16,16),bool);pixels[:,4:12]=True
        result=dispatch(self.root,'pattern_microfit',dict(self.request(pixels),material='stone_bricks'))
        self.assertEqual(result['shape_counts'],dict(wall=1))
        self.assertFalse(result['microfit']['auto_wall_search']['fallback'])
        self.assertEqual(result['microfit']['projection_resolution'],16)

    def test_automatic_wall_preserves_complex_lattice_topology_with_consistent_targets(self):
        result=dispatch(self.root,'pattern_microfit',dict(surface='wall',preset='chinese-window-lattice',size_uv=[12,12],
            material='stone_bricks',micro_alignment='fixed',quality_profile='ornate',min_quality_score=80))
        quality=result['microfit']
        self.assertEqual(quality['result_topology']['holes'],12)
        self.assertEqual(quality['source_topology']['holes'],12)
        self.assertTrue(quality['visual_quality']['passed'])
        self.assertGreaterEqual(quality['visual_quality']['score'],80)
        self.assertTrue(quality['auto_wall_search']['attempted'])


if __name__=='__main__':
    unittest.main(verbosity=2)
