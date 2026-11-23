"""Independent numeric oracles, source boundaries and actual optional CUDA parity."""
import copy,json,sys,tempfile,unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_structure_agent import dispatch,build
from nbt_compute import execute,gpu,info
from nbt_geometry.deform import coordinates,warp_pixels
from nbt_geometry.field_compute import sample
from nbt_pattern.spectral import smooth

REQUIRE_GPU='--require-gpu' in sys.argv
if REQUIRE_GPU:sys.argv.remove('--require-gpu')


def request(**patches):
    return dict(dict(size=[32,32,32],root='shape',nodes=[dict(id='shape',shape='superellipsoid',centre=[16,16,16],radii=[6,10,4],power=4)],backend='cpu'),**patches)


class ComputeTransforms(unittest.TestCase):
    def setUp(self):
        directory=tempfile.TemporaryDirectory();self.addCleanup(directory.cleanup);self.root=Path(directory.name)
    def call(self,tool,**args):return dispatch(self.root,tool,args)
    def asset(self):
        from PIL import Image
        from nbt_pattern.assets import store
        image=Image.new('RGBA',(64,64),(0,0,0,0))
        image.paste((138,197,244,117),(12,8,37,52))
        return store(self.root,image,'彩色试件',[],dict(generator='test_fixture'))
    def bound(self,a):return dict(id=a['id'],image_sha256=a['image_sha256'])
    def files(self):return {str(p.relative_to(self.root)):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}

    def test_missing_gpu_auto_falls_back_but_explicit_gpu_refuses(self):
        with patch('nbt_compute.gpu',return_value=(None,'fixture unavailable')):
            out,receipt=execute('auto',True,lambda xp:xp.arange(3))
            self.assertEqual(out.tolist(),[0,1,2]);self.assertEqual(receipt['actual'],'cpu');self.assertIn('unavailable',receipt['reason'])
            with self.assertRaisesRegex(ValueError,'GPU不可用'):execute('gpu',True,lambda xp:xp.ones(3))
        with patch('nbt_compute.gpu',side_effect=AssertionError('small tasks must not initialize GPU')):
            _,receipt=execute('auto',False,lambda xp:xp.ones(3));self.assertEqual(receipt['actual'],'cpu')

    def test_cpu_ellipsoid_matches_independent_analytic_grid_and_affine_translation(self):
        args=request();args['nodes'][0].update(shape='ellipsoid');args['nodes'][0].pop('power')
        mask,_=sample(args);x,y,z=np.indices(args['size'])+.5
        expected=((x-16)/6)**2+((y-16)/10)**2+((z-16)/4)**2<=1
        np.testing.assert_array_equal(mask,expected)
        moved=copy.deepcopy(args);moved['transforms']=[dict(kind='affine',matrix=np.eye(3).tolist(),offset=[2,0,0])]
        after,_=sample(moved);np.testing.assert_array_equal(after[2:],mask[:-2]);self.assertFalse(after[:2].any())

    def test_inverse_transforms_recover_forward_landmarks_in_declared_order(self):
        point=[np.array([2.]),np.array([3.]),np.array([4.])]
        theta=np.pi/3;forward=[np.cos(theta)*2-np.sin(theta)*4,3,np.sin(theta)*2+np.cos(theta)*4]
        back=coordinates([np.array([p]) for p in forward],[dict(kind='twist',axis='y',degrees=60,length=3)],np)
        np.testing.assert_allclose(np.array(back),point,atol=1e-12)
        radius=20;a,b=2,3;forward=[(radius+b)*np.sin(a/radius),(radius+b)*np.cos(a/radius)-radius,4]
        back=coordinates([np.array([p]) for p in forward],[dict(kind='bend',radius=radius,plane='xy')],np)
        np.testing.assert_allclose(np.array(back),point,atol=1e-12)
        transforms=[dict(kind='shear',axis='x',driver='y',amount=2),dict(kind='affine',matrix=np.eye(3).tolist(),offset=[1,0,0])]
        back=coordinates([np.array([9.]),point[1],point[2]],transforms,np)
        np.testing.assert_allclose(np.array(back),point)

    def test_each_volume_deformation_changes_geometry_and_returns_no_files(self):
        args=request();baseline=self.call('field_compile',**args)
        transforms=[dict(kind='twist',degrees=120,length=20,centre=[16,16,16]),dict(kind='bend',radius=30,plane='xy',centre=[16,16,16]),
            dict(kind='taper',amount=.5,length=20,centre=[16,16,16]),dict(kind='shear',axis='x',driver='y',amount=.3,centre=[16,16,16]),
            dict(kind='wave',axis='x',driver='y',amplitude=2,wavelength=12)]
        for t in transforms:
            candidate=self.call('field_compile',**dict(args,transforms=[t]))
            self.assertNotEqual(candidate['content_sha256'],baseline['content_sha256'],t['kind'])
            self.assertEqual(build(self.root,candidate['spec'])['content_sha256'],candidate['content_sha256'])
        self.assertEqual(self.files(),{})

    def test_boolean_gyroid_is_real_open_geometry_and_graph_rejects_cycles_or_excessive_work(self):
        args=request(root='cut',nodes=[dict(id='solid',shape='box',min=[4,4,4],max=[28,28,28]),dict(id='holes',shape='gyroid',wavelength=12,thickness=.35),dict(id='cut',shape='intersection',children=['solid','holes'])])
        result=self.call('field_compile',**args);self.assertLess(result['block_count'],24**3);self.assertGreater(result['block_count'],1000)
        bad=copy.deepcopy(args);bad['nodes'][-1]['children']=['cut','holes']
        with self.assertRaisesRegex(ValueError,'循环'):self.call('field_compile',**bad)
        # Shared children in a DAG cannot multiply the sampling work unboundedly.
        nodes=[dict(id='n0',shape='box',min=[0,0,0],max=[64,64,64])]+[dict(id=f'n{i}',shape='union',children=[f'n{i-1}']*8) for i in range(1,10)]
        with self.assertRaisesRegex(ValueError,'工作量'):self.call('field_compile',size=[64]*3,root='n9',nodes=nodes)

    def test_invalid_transform_material_budget_or_payload_never_creates_files(self):
        for patch_args in [dict(max_changed_blocks=1),dict(material='oak_stairs'),dict(script='run'),dict(backend='unknown'),
            dict(transforms=[dict(kind='twist')]),dict(transforms=[dict(kind='affine',matrix=[[0]*3]*3)]),
            dict(transforms=[dict(kind='wave',axis='y',driver='y',amplitude=2,wavelength=3)]),
            dict(transforms=[dict(kind='taper',amount=8,length=1,centre=[16,16,16])])]:
            with self.subTest(patch_args=patch_args),self.assertRaises(ValueError):self.call('field_compile',**dict(request(),**patch_args))
        self.assertEqual(self.files(),{})

    def test_image_identity_and_half_pixel_shift_match_linear_interpolation_oracle(self):
        values=np.arange(9*9,dtype=float).reshape(9,9)
        out,_=warp_pixels(values,dict(transforms=[dict(kind='affine',matrix=np.eye(3).tolist())],backend='cpu'))
        np.testing.assert_array_equal(out,values)
        matrix=[[1,0,1/16],[0,1,0],[0,0,1]]
        out,_=warp_pixels(values,dict(transforms=[dict(kind='affine',matrix=matrix)],backend='cpu',boundary='clamp'))
        np.testing.assert_array_equal(out[:,1:],np.rint((values[:,:-1]+values[:,1:])/2))
        # A horizon between sample columns must also reject, even when no
        # sampled denominator is exactly zero.
        with self.assertRaisesRegex(ValueError,'无穷远'):
            warp_pixels(values,dict(transforms=[dict(kind='affine',matrix=[[1,0,0],[0,1,0],[3,0,-1]])],backend='cpu'))

    def test_pattern_warp_preserves_source_rgba_and_changed_source_is_rejected_before_store(self):
        from PIL import Image
        a=self.asset();before=Path(a['image']).read_bytes();source=np.asarray(Image.open(a['image']).convert('RGBA'))
        warped=self.call('pattern_warp',name='变形试件',source=self.bound(a),transforms=[dict(kind='affine',matrix=np.eye(3).tolist())],backend='cpu')
        actual=np.asarray(Image.open(warped['image']).convert('RGBA'))
        np.testing.assert_array_equal(actual[source[...,3]>0],source[source[...,3]>0]);self.assertEqual(Path(a['image']).read_bytes(),before)
        import nbt_geometry.deform as nbt_deform
        original=nbt_deform.warp_pixels;files=self.files()
        def change(*args,**kwargs):
            result=original(*args,**kwargs);Path(a['image']).write_bytes(b'concurrent change');return result
        with patch.object(nbt_deform,'warp_pixels',side_effect=change),self.assertRaisesRegex(ValueError,'哈希|变化'):
            self.call('pattern_warp',name='拒绝',source=self.bound(a),transforms=[dict(kind='swirl',radius=.5,degrees=90)],backend='cpu')
        self.assertEqual(set(self.files()),set(files))

    def test_scene_and_session_accept_field_candidates_but_session_refuses_asset_creation(self):
        from nbt_engine_session import serve
        graph=dict(schema_version=1,name='扭柱对象',size=[40]*3,objects=[dict(id='column',lo=[0,0,0],recipe=dict(tool='field_compile',arguments=request()))])
        scene=self.call('scene_compile',graph=graph);self.assertGreater(scene['block_count'],0)
        requests=[dict(id='a',method='agent',params=dict(tool='field_compile',arguments=request())),dict(id='b',method='agent',params=dict(tool='pattern_warp',arguments={}))]
        output=BytesIO();serve(self.root,BytesIO(('\n'.join(json.dumps(v) for v in requests)+'\n').encode()),output)
        replies=[json.loads(v) for v in output.getvalue().splitlines()];self.assertTrue(replies[0]['ok']);self.assertFalse(replies[1]['ok']);self.assertEqual(self.files(),{})

    def test_real_gpu_fft_and_deformations_match_cpu_including_voxel_boundaries(self):
        if not info()['gpu_available']:
            if REQUIRE_GPU:self.fail(info()['reason'])
            self.skipTest('optional CuPy/CUDA environment unavailable')
        image=np.random.default_rng(42).uniform(0,255,(128,161))
        for boundary in ('zero','reflect','wrap'):
            cpu,_=smooth(image,'disk',9,boundary,'fft','cpu');actual,report=smooth(image,'disk',9,boundary,'fft','gpu')
            self.assertEqual(report['compute']['actual'],'gpu');np.testing.assert_allclose(actual,cpu,atol=1e-9,rtol=1e-10)
        args=request(transforms=[dict(kind='twist',degrees=135,length=20,centre=[16]*3),dict(kind='taper',length=20,amount=.4,centre=[16]*3),dict(kind='wave',axis='x',driver='y',amplitude=1.5,wavelength=12)])
        cpu,_=sample(args);actual,report=sample(dict(args,backend='gpu'));self.assertEqual(report['actual'],'gpu');np.testing.assert_array_equal(actual,cpu)
        # An exact plane through voxel centres exercises CPU tie resolution.
        args=request(nodes=[dict(id='shape',shape='box',min=[3.5]*3,max=[25.5]*3)])
        cpu,_=sample(args);actual,report=sample(dict(args,backend='gpu'));np.testing.assert_array_equal(actual,cpu);self.assertGreater(report['cpu_boundary_samples'],0)
        large=request(size=[64]*3,transforms=[dict(kind='twist',degrees=120,length=32),dict(kind='shear',axis='x',driver='y',amount=.2),dict(kind='wave',axis='z',driver='y',amplitude=1,wavelength=12)])
        _,report=sample(dict(large,backend='auto'));self.assertEqual(report['actual'],'gpu')
        for transform in [dict(kind='bend',radius=30,plane='xy',centre=[16]*3),dict(kind='shear',axis='x',driver='y',amount=.25),dict(kind='affine',matrix=[[1,.1,0],[0,1,0],[0,0,1]],offset=[1,0,0])]:
            a=request(transforms=[transform]);cpu,_=sample(a);actual,_=sample(dict(a,backend='gpu'));np.testing.assert_array_equal(actual,cpu)

    def test_real_gpu_image_composition_matches_cpu_colors_and_all_new_maps(self):
        if not info()['gpu_available']:
            if REQUIRE_GPU:self.fail(info()['reason'])
            self.skipTest('optional CuPy/CUDA environment unavailable')
        image=np.random.default_rng(11).uniform(0,255,(117,129,4))
        transforms=[dict(kind='affine',matrix=[[1,.15,-.05],[0,1,.02],[.05,0,1]]),dict(kind='swirl',radius=.7,degrees=120),dict(kind='wave',amplitude=.04,wavelength=.3),dict(kind='polar_repeat',sectors=8,mirror=True)]
        for boundary in ('clamp','wrap','zero'):
            a=dict(transforms=transforms,resolution=[160,144],boundary=boundary,backend='cpu')
            cpu,_=warp_pixels(image,a,False);actual,report=warp_pixels(image,dict(a,backend='gpu'),False)
            self.assertEqual(report['actual'],'gpu');np.testing.assert_allclose(actual,cpu,atol=1e-8,rtol=1e-10)
        _,report=warp_pixels(np.zeros((512,512)),dict(transforms=[dict(kind='swirl',radius=.7,degrees=90)],backend='auto'))
        self.assertEqual(report['actual'],'gpu')


if __name__=='__main__':unittest.main(verbosity=2)
