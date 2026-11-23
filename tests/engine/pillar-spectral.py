"""Pillar-end recipes, existing Bezier entry points, and exact FFT boundaries."""
import copy,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_structure_agent import dispatch,build
from nbt_pattern.assets import load
from nbt_selection_edit import sha
from nbt_pattern.spectral import smooth,kernel_for
from nbt_modeling_session import ModellingSession


class PillarSpectral(unittest.TestCase):
    def setUp(self):
        directory=tempfile.TemporaryDirectory();self.addCleanup(directory.cleanup);self.root=Path(directory.name)
    def call(self,tool,args):return dispatch(self.root,tool,args)
    def column(self,**form):return dict(kind='pillar',size=[13,32,13],material='quartz_block',accent='smooth_sandstone',form=dict(base_height=10,capital_height=10,**form))
    def geometry(self,result):
        d=build(self.root,result['spec']);return {tuple(b[:3]):d['palette'][b[3]] for b in d['blocks']}
    def test_profiles_and_bezier_remain_connected_and_plain_is_unchanged(self):
        from nbt_building.pillar_ends import PROFILES
        plain=self.call('parametric_compile',self.column())
        self.assertEqual(plain['content_sha256'],self.call('parametric_compile',self.column(base_profile='plain',capital_profile='plain'))['content_sha256'])
        hashes=set()
        for profile in PROFILES:
            f=dict(base_profile=profile,capital_profile=profile)
            if profile=='bezier':f.update(base_curve=[1,.4,.8,.5],capital_curve=[.5,.8,.4,1])
            result=self.call('parametric_compile',self.column(**f));points=set(self.geometry(result));seen={next(iter(points))};pending=list(seen)
            while pending:
                x,y,z=pending.pop()
                for n in ((x-1,y,z),(x+1,y,z),(x,y-1,z),(x,y+1,z),(x,y,z-1),(x,y,z+1)):
                    if n in points and n not in seen:seen.add(n);pending.append(n)
            self.assertEqual(seen,points,profile);hashes.add(result['content_sha256'])
        self.assertGreaterEqual(len(hashes),5)
        even=self.call('parametric_compile',dict(kind='pillar',size=[6,12,6],form=dict(base_height=3,capital_height=3,base_profile='bezier',base_curve=[.2,.2,.2,.2])))
        self.assertTrue(any(p[1]==1 for p in self.geometry(even)))
        self.assertEqual(list(self.root.iterdir()),[])
    def test_each_end_has_its_own_four_faces_and_capital_regeneration_preserves_shaft(self):
        pattern=dict(preset='micro-palmette',size_uv=[4,6],material='quartz_block',quality_profile='border',min_quality_score=85)
        args=self.column(base_profile='torus',capital_profile='bell',base_pattern=dict(pattern=pattern),capital_pattern=dict(pattern=dict(pattern,preset='micro-scroll')))
        result=self.call('parametric_compile',args)
        self.assertEqual([len(result['end_decorations'][p]) for p in ('base','capital')],[4,4])
        self.assertTrue(all(not row[4] for row in build(self.root,result['spec'])['blocks']))
        self.assertTrue(any('_stairs[' in s for s in self.geometry(result).values()))
        self.assertTrue(any('_slab[' in s for s in self.geometry(result).values()))
        replacement=copy.deepcopy(args);replacement['form']['capital_profile']='beveled'
        changed=self.call('parametric_regenerate',dict(object_id='test_column',original=args,replacement=replacement,part='capital',original_recipe_sha256=result['recipe_sha256']))
        before,after=self.geometry(result),self.geometry(changed)
        self.assertEqual({p:v for p,v in before.items() if p[1]<22},{p:v for p,v in after.items() if p[1]<22})
        self.assertGreater(changed['changed_blocks'],0)
        self.assertEqual(list(self.root.iterdir()),[])
    def test_pattern_binding_inside_end_parameters_updates_real_scene_objects(self):
        source=load(self.root,'builtin:micro-fleur-de-lis')
        asset=self.call('pattern_assets',dict(action='copy',id=source['id'],image_sha256=source['image_sha256'],name='花冠源'))
        mirrored=self.call('pattern_create',dict(name='反向花冠',resolution=[64,64],layers=[dict(kind='asset',id=asset['id'],image_sha256=asset['image_sha256'],flip_y=True)]))
        pattern=dict(size_uv=[8,8],pattern_ref='flower',material='quartz_block',quality_profile='ornate',min_quality_score=85)
        graph=dict(schema_version=1,name='联动柱头',size=[32,32,16],patterns=[dict(id='flower',asset={k:asset[k] for k in ('id','image_sha256')})],objects=[
            dict(id='left',lo=[0,0,0],recipe=dict(tool='parametric_compile',arguments=self.column(capital_pattern=dict(pattern=pattern)))),
            dict(id='right',lo=[18,0,0],recipe=dict(tool='parametric_compile',arguments=self.column(capital_pattern=dict(pattern=pattern))))])
        compiled=self.call('scene_compile',dict(graph=graph));receipt=self.call('scene_save',{k:compiled[k] for k in ('graph','graph_sha256','content_sha256')})
        changed=self.call('scene_update',dict(id=receipt['id'],revision=receipt['revision'],version=receipt['version'],pattern_changes=[dict(id='flower',asset={k:mirrored[k] for k in ('id','image_sha256')})]))
        self.assertEqual(changed['affected_objects'],['left','right']);self.assertGreater(changed['changed_blocks'],0)
        self.assertEqual(self.call('scene_read',dict(id=receipt['id']))['version'],receipt['version'])
    def test_invalid_end_parameters_and_budget_do_not_write_files(self):
        cases=[self.column(base_curve=[1,.5,.5,1]),self.column(base_profile='bezier'),self.column(base_profile='bezier',base_curve=[1,0,1,1]),
            self.column(base_pattern=dict(pattern=dict(preset='micro-fleur-de-lis',size_uv=[12,12]))),
            self.column(base_pattern=dict(pattern=dict(preset='micro-scroll',size_uv=[4,6]),faces=['north','north'])),
            dict(self.column(base_profile='torus'),max_changed_blocks=1),dict(kind='table',size=[9,12,9],form=dict(base_profile='bell'))]
        for args in cases:
            with self.subTest(args=args),self.assertRaises(ValueError):self.call('parametric_compile',args)
        self.assertEqual(list(self.root.iterdir()),[])
    def test_fft_matches_independent_spatial_convolution_and_does_not_wrap_by_default(self):
        image=np.random.default_rng(47).normal(size=(23,31))
        for kernel in ('disk','gaussian'):
            for boundary in ('reflect','wrap','zero'):
                with self.subTest(kernel=kernel,boundary=boundary):
                    spatial,_=smooth(image,kernel,5,boundary,'spatial');fft,_=smooth(image,kernel,5,boundary,'fft')
                    np.testing.assert_allclose(fft,spatial,atol=1e-12)
        impulse=np.zeros((25,31));impulse[12,0]=1
        bounded,_=smooth(impulse,'disk',3,'zero','fft');wrapped,_=smooth(impulse,'disk',3,'wrap','fft')
        self.assertAlmostEqual(bounded[12,-1],0,places=12);self.assertGreater(wrapped[12,-1],0)
        constant=np.full((17,19),123.);result,_=smooth(constant,'gaussian',4,'reflect','fft');np.testing.assert_allclose(result,constant,atol=1e-12)
        _,small=smooth(np.ones((8,8)),'disk',1);_,large=smooth(np.ones((256,256)),'disk',20)
        self.assertEqual(small['algorithm'],'numpy_spatial_disk_convolution');self.assertEqual(large['algorithm'],'numpy_real_fft_linear_convolution')
    def test_bandpass_and_asset_writes_stay_out_of_pure_sessions(self):
        from nbt_pattern.spectral import filter_values
        source=np.random.default_rng(8).uniform(0,255,(41,37))
        spatial,_=filter_values(source,dict(filter='bandpass',radius=2,outer_radius=7,kernel='disk',method='spatial',normalize=True))
        fft,_=filter_values(source,dict(filter='bandpass',radius=2,outer_radius=7,kernel='disk',method='fft',normalize=True))
        np.testing.assert_array_equal(spatial,fft)
        with self.assertRaisesRegex(ValueError,'工作量'):
            smooth(np.ones((512,512)),'disk',64,method='spatial')
        from io import BytesIO
        from nbt_engine_session import serve
        request=dict(id='no_write',method='agent',params=dict(tool='pattern_filter',arguments={}))
        sink=BytesIO();serve(self.root,BytesIO((json.dumps(request)+'\n').encode()),sink)
        self.assertFalse(json.loads(sink.getvalue())['ok']);self.assertEqual(list(self.root.iterdir()),[])

    def test_filter_creates_a_separate_bound_asset_and_fits_with_original_gates(self):
        source=load(self.root,'builtin:micro-fleur-de-lis');reference={k:source[k] for k in ('id','image_sha256')};before=Path(source['image']).read_bytes()
        request=dict(name='去噪花冠',source=reference,radius=1,method='fft')
        filtered=self.call('pattern_filter',request);self.assertEqual(Path(source['image']).read_bytes(),before)
        self.assertFalse(filtered['source_modified']);self.assertEqual(filtered['processing']['operations'][0]['algorithm'],'numpy_real_fft_linear_convolution')
        again=self.call('pattern_filter',request);self.assertEqual(filtered['image_sha256'],again['image_sha256']);self.assertNotEqual(filtered['id'],again['id'])
        fitted=self.call('pattern_microfit',dict(surface='wall',size_uv=[8,8],pattern_asset={k:filtered[k] for k in ('id','image_sha256')},quality_profile='ornate',min_quality_score=85))
        self.assertTrue(fitted['microfit']['topology_preserved']);self.assertGreaterEqual(fitted['visual_quality']['score'],85)
        files={p:p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        for patch_args in (dict(source=dict(reference,image_sha256='0'*64)),dict(filter='bandpass'),dict(outer_radius=4),dict(filter='bandpass',radius=4,outer_radius=3)):
            with self.assertRaises(ValueError):self.call('pattern_filter',dict(request,**patch_args))
        self.assertEqual(files,{p:p.read_bytes() for p in self.root.rglob('*') if p.is_file()})
    def test_filter_rechecks_image_changed_during_fft_before_creating_an_asset(self):
        import nbt_pattern.spectral as nbt_spectral
        builtin=load(self.root,'builtin:micro-fleur-de-lis');asset=self.call('pattern_assets',dict(action='copy',id=builtin['id'],image_sha256=builtin['image_sha256'],name='测试源'))
        original=nbt_spectral.filter_values;folders=list((self.root/'nbt_models/asset_library/patterns').iterdir())
        def changed(*args):
            result=original(*args);Path(asset['image']).write_bytes(b'changed during filtering');return result
        with patch.object(nbt_spectral,'filter_values',side_effect=changed),self.assertRaisesRegex(ValueError,'图像哈希'):
            self.call('pattern_filter',dict(name='不可保存',source={k:asset[k] for k in ('id','image_sha256')}))
        self.assertEqual(folders,list((self.root/'nbt_models/asset_library/patterns').iterdir()))
    def test_bezier_is_exposed_in_2d_and_3d_and_2d_sampling_is_explicit(self):
        layer=dict(kind='bezier',points=[[.1,.9],[0,0],[1,0],[.9,.9]],stroke=.08)
        args=dict(name='卷叶曲线',resolution=[64,64],layers=[layer]);legacy=self.call('pattern_create',args)
        explicit=self.call('pattern_create',dict(args,layers=[dict(layer,samples=257)]));self.assertEqual(legacy['image_sha256'],explicit['image_sha256'])
        coarse=self.call('pattern_create',dict(args,layers=[dict(layer,samples=16)]));self.assertNotEqual(coarse['image_sha256'],legacy['image_sha256'])
        for bad in (dict(layer,samples=1),dict(kind='rect',samples=32)):
            with self.assertRaises(ValueError):self.call('pattern_create',dict(args,layers=[bad]))
        spec=dict(name='三维曲线构件',size=[24,24,24],operations=[dict(kind='geometry',label='贝塞尔扫掠',lo=[0,0,0],hi=[23,23,23],state='quartz_block',classification='body',
            geometry=dict(shape='bezier',points=[[2.5,2.5,2.5],[2.5,20,8],[20,20,15],[20.5,2.5,20.5]],radius=1.1,samples=96))])
        data=build(self.root,spec);points={tuple(row[:3]) for row in data['blocks']};self.assertIn((2,2,2),points);self.assertIn((20,2,20),points)
        self.assertGreater(max(y for x,y,z in points),10)


if __name__=='__main__':unittest.main(verbosity=2)
