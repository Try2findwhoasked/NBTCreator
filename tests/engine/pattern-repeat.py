"""Reference detection, phase continuity and model readback on three surfaces."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT/'.agents/skills/minecraft-nbt-modeler/scripts'
sys.path[:0] = [str(SCRIPTS), str(ROOT/'tests/support')]
from curved_surface_fixture import create_curve_fixture
from nbt_assembly import Volume
from nbt_curved_surface import plan_curve,verify_curve
from nbt_cylinder_pattern import cylinder_geometry
from nbt_microfit import fit_colored_unit
from nbt_refine import read_master,save_master
from nbt_selection_edit import sha
from nbt_structure_agent import dispatch
from nbt_tools import transformed_state


OUTPUT = None
RENDER = False
WHITE = [255,255,255]
GOLD = [240,174,47]
INK = dict(threshold=40, colors=[dict(rgb='#ffffff',material='quartz_block'),
                                dict(rgb='#f0ae2f',material='gold_block')])
SHAPES = dict(stairs='quartz_stairs',slab='quartz_slab')


class PatternRepeat(unittest.TestCase):
    def setUp(self):
        if OUTPUT is None:
            temp = tempfile.TemporaryDirectory()
            self.addCleanup(temp.cleanup)
            self.root = Path(temp.name)
        else:
            self.root = OUTPUT/self._testMethodName.removeprefix('test_')
            self.root.mkdir()

    def raster(self,name,pixels,**sample):
        path = self.root/name
        Image.fromarray(np.array(pixels,dtype=np.uint8)).save(path)
        return dict(path=name,sha256=sha(path),**sample)

    def call(self,tool,args):
        return dispatch(self.root,tool,args)

    def sample(self):
        # Rows here are the raster's upper-left origin. This gives a full
        # upper course and a lower course containing one straight stair.
        unit = np.asarray([[WHITE,WHITE,GOLD,GOLD],[WHITE,WHITE,GOLD,GOLD],
                           [WHITE,WHITE,WHITE,[0,0,0]],[WHITE,WHITE,WHITE,WHITE]])
        sample = self.raster('repeat.png',np.tile(unit,(4,5,1)),**INK)
        return dict(surface='wall',size_uv=[2,2],sample=sample,repeat_detection={},shapes=SHAPES)

    def bound(self,model,lo,hi,**context):
        source = self.root/'master.snbt'
        save_master(source,model,set(model.blocks))
        context_path = self.root/'coordinates.json'
        context_path.write_text(json.dumps(dict(mode='standalone',openings=[],**context)),encoding='utf8')
        return dict(source=source.name,source_sha256=sha(source),geometry_sha256=model.fingerprint(),
                    context=context_path.name,context_sha256=sha(context_path),lo=lo,hi=hi)

    def cameras(self,*views):
        path = self.root/'cameras.json'
        path.write_text(json.dumps([dict(id=name,eye=eye,target=target) for name,eye,target in views]),encoding='utf8')
        return dict(cameras=path.name,render=RENDER)

    def assert_readback(self,evidence,model):
        self.assertTrue(evidence['positions_match'])
        self.assertEqual(evidence['game_effects'],'not_checked')
        for entry in evidence['position_comparison']:
            self.assertEqual(model.get(tuple(entry['position'])),entry['expected'])
            self.assertEqual(entry['actual'],entry['expected'])
            self.assertEqual(entry['phase_uv'],[(a-b)%n for a,b,n in zip(
                entry['uv'],evidence['anchor_uv'],evidence['period_uv'])])

    def test_fft_masked_rectangular_fundamental_and_linear_overlap(self):
        tile = np.zeros((6,8),dtype=np.int8)
        tile[2:4,:] = 1
        tile[:,3:5] = 1
        tile[2:4,3:5] = 2
        tile[0,6] = tile[5,1] = 2
        yy,xx = np.indices((31,45))
        truth = tile[(yy-3)%6,(xx-4)%8]
        valid = np.ones_like(truth,dtype=bool)
        valid[4:16,12:27] = valid[22:31,:12] = valid[11:18,37:45] = False
        rgb = np.array([[0,0,0],WHITE,GOLD])
        observed = truth.copy()
        observed[~valid] = 0
        sample = self.raster('reference.png',rgb[observed],**INK)
        settings = dict(valid_mask=self.raster('valid.png',255*valid),max_period_uv=[16,16])
        request = dict(sample=sample,detection=settings)
        report = self.call('pattern_repeat_detect',request)
        if OUTPUT:
            (self.root/'detect-request.json').write_text(json.dumps(request),encoding='utf8')
            self.save_report('detection',report)
        self.assertTrue(report['detected'])
        self.assertEqual(report['period_uv'],[8,6])
        self.assertEqual(report['spatial_verification']['agreement'],1)
        self.assertEqual(report['valid_pixels'],1051)
        for lag in (8,16):
            entry = report['candidates']['u'][lag-1]
            self.assertTrue(entry['eligible'])
            self.assertEqual(entry['valid_pairs'],int((valid[:,:-lag] & valid[:,lag:]).sum()))
        from nbt_pattern_repeat import detect
        _,unit = detect(self.root,sample,settings)
        np.testing.assert_array_equal(np.tile(np.asarray(unit)[:,:,:3],(6,6,1))[:31,:45],rgb[truth])
        settings['valid_mask']['sha256'] = '0'*64
        with self.assertRaisesRegex(ValueError,'SHA256'):
            self.call('pattern_repeat_detect',dict(sample=sample,detection=settings))

    def test_insufficient_evidence_and_explicit_manual_unit(self):
        pixels = np.random.default_rng(24).integers(0,2,(32,41),dtype=np.uint8)*255
        sample = self.raster('random.png',pixels)
        report = self.call('pattern_repeat_detect',dict(sample=sample))
        self.assertFalse(report['detected'])
        self.assertEqual(report['reason'],'no_supported_axis_periods')
        pixels[:] = 0
        pixels[8,15] = 255
        speck = self.raster('speck.png',pixels)
        self.assertEqual(self.call('pattern_repeat_detect',dict(sample=speck))['reason'],'no_supported_axis_periods')
        sparse_unit = np.zeros((16,16),dtype=np.uint8)
        sparse_unit[3,8] = 255
        sparse = self.raster('sparse.png',np.tile(sparse_unit,(4,4)))
        sparse_result = self.call('pattern_repeat_detect',dict(sample=sparse))
        self.assertEqual(sparse_result['period_uv'],[16,16])
        weak = sparse_result['candidates']['u'][0]
        self.assertGreater(weak['agreement'],.99)
        self.assertFalse(weak['eligible'])
        manual = self.raster('manual.png',[[255,0],[0,0]])
        fit = self.call('pattern_microfit',dict(surface='wall',size_uv=[2,2],sample=manual,
                                                   full_blocks_only=True,micro_alignment='fixed'))
        self.assertEqual(fit['microfit']['placement'],'fit_once_then_copy')
        with self.assertRaisesRegex(ValueError,'手工'):
            self.call('pattern_microfit',dict(surface='wall',size_uv=[2,2],sample=sample,repeat_detection={}))

    def test_plane_opening_protection_reservation_and_single_fit(self):
        model = Volume((18,12,16))
        opening = {(x,y,7) for x in (8,9,10) for y in (1,2,3)}
        model.box([0,0,0],[17,0,15],'stone')
        for x in range(2,16):
            for y in range(1,7):
                if (x,y,7) not in opening:
                    model.put((x,y,7),'stone_bricks')
        protected = [5,5,8];reserved = [13,5,8];context_reserved = [7,5,8]
        surface = self.bound(model,[2,1,7],[15,6,7],protected_boxes=[dict(lo=protected,hi=protected)],
                             reserved_boxes=[dict(lo=context_reserved,hi=context_reserved)],
                             start=[9.5,1,4.5],targets=dict(door=[9.5,1,10.5]))
        surface.update(normal='south',opening_margin=0)
        query = self.call('parametric_surface',dict(surface=surface))
        proposal = self.sample()
        review = self.cameras(('plane',[13,9,22],[9,3,7]),('opening',[9,3,21],[9,3,8]))
        args = dict(surface=surface,surface_sha256=query['surface_sha256'],object=proposal,anchor_uv=[1,1],
                    repeat_tiling=True,reserved_boxes=[dict(lo=reserved,hi=reserved)],review=review,require_routes=True)
        with patch('nbt_microfit.fit_colored_unit',wraps=fit_colored_unit) as fit:
            result = self.call('pattern_mount',args)
            self.assertEqual(fit.call_count,1)
        self.assertTrue(result['verification']['routes']['passed'])
        self.assertFalse(result['approval_created'])
        actual,_ = read_master(result['review']['sides']['after']['source'])
        proof = result['pattern']['repeat_tiling']
        self.assert_readback(proof,actual)
        self.assertTrue(proof['seam_geometry_matches'])
        self.assertGreater(len(proof['half_cell_joints']),10)
        self.assertEqual({x['reason'] for x in proof['clipped']},{'protected','reserved','opening_or_margin'})
        self.assertEqual(result['pattern']['microfit']['repeat_detection']['period_uv'],[4,4])
        for x,y,z in opening:
            self.assertEqual(actual.get((x,y,z+1)),'minecraft:air')
        for point in (protected,reserved,context_reserved):
            self.assertEqual(actual.get(tuple(point)),'minecraft:air')
        self.assertEqual(sha(self.root/surface['source']),surface['source_sha256'])
        with self.assertRaisesRegex(ValueError,'预算'):
            self.call('pattern_mount',dict(args,max_changed_blocks=1))
        with self.assertRaisesRegex(ValueError,'源'):
            self.call('pattern_mount',dict(args,surface=dict(surface,source_sha256='0'*64)))
        preview = self.call('pattern_microfit',dict(proposal,tile_counts=[2,2],gap_uv=[0,0],
                                                       preview=True,micro_alignment='fixed'))
        self.assertTrue(Path(preview['thumbnail']).is_file())
        self.assertEqual(preview['microfit']['tile_counts'],[2,2])
        if OUTPUT:
            self.save_report('plane',result)
            self.save_report('unit-preview',preview)

    def test_cylinder_closed_corner_states_and_interrupted_phase(self):
        diameter = 12
        height = 6
        core,ring = cylinder_geometry(diameter,164)
        self.assertEqual(len(ring),36)
        model = Volume((24,12,24))
        lo = [5,2,5]
        cut = ring[8]
        hole = [lo[0]+cut['x']-cut['dx'],lo[1]+2,lo[2]+cut['z']-cut['dz']]
        for x,z in core:
            for v in range(height):
                point = (lo[0]+x,lo[1]+v,lo[2]+z)
                if list(point)!=hole:
                    model.put(point,'stone_bricks')
        target = self.bound(model,lo,[lo[0]+diameter+1,lo[1]+height-1,lo[2]+diameter+1])
        obj = dict(self.sample(),surface='cylinder',diameter=diameter,seam_degrees=164)
        shell = [lo[0]+cut['x'],lo[1]+2,lo[2]+cut['z']]
        gap_view = ('gap',[shell[0]+12*cut['dx'],shell[1]+3,shell[2]+12*cut['dz']],shell)
        args = dict(target=target,object=obj,repeat_anchor_uv=[1,1],reserved_boxes=[dict(lo=hole,hi=hole)],
                    review=self.cameras(('wrap',[27,15,-9],[12,5,12]),('shell',[26,11,25],[12,5,12]),gap_view))
        result = self.call('pattern_cylinder_mount',args)
        proof = result['pattern']['repeat_tiling']
        self.assertTrue(proof['closed_u'])
        self.assertTrue(proof['seam_geometry_matches'],[j for j in proof['half_cell_joints'] if j['status']=='mismatch'])
        actual,_ = read_master(result['review']['sides']['after']['source'])
        self.assert_readback(proof,actual)
        self.assertEqual(result['pattern']['cylinder']['masked_core_air'],1)
        self.assertFalse(result['verification']['intact_core'])
        self.assertTrue(any(j['wraps'] and j['actual_contact'] for j in proof['half_cell_joints'] if j['status']=='match'))
        self.assertTrue(any(j['wraps'] and j.get('connector_position') for j in proof['half_cell_joints']))
        self.assertTrue(any(j['seam'] and j.get('connector_position') for j in proof['half_cell_joints']))
        self.assertTrue(any(item['uv']==[8,2] for item in proof['clipped']))
        self.assertEqual(actual.get(tuple(hole)),'minecraft:air')
        local_stairs = set()
        world_facings = set()
        for record in proof['position_comparison']:
            if 'stairs[' in record['actual']:
                u,_ = record['uv']
                cell = ring[u]
                local_stairs.add(transformed_state(record['actual'],-cell['turns'],None))
                from nbt_registry import effective
                world_facings.add(effective(record['actual'])[1]['facing'])
        self.assertEqual(len(local_stairs),1)
        self.assertEqual(len(world_facings),4)
        self.assertGreater(result['pattern']['cylinder']['corner_connector_blocks'],0)
        self.assertEqual(sum(result['pattern']['shape_counts'].values()),result['changed_blocks'])
        self.assertEqual(sha(self.root/target['source']),target['source_sha256'])
        with self.assertRaisesRegex(ValueError,'周长 36 格.*余 1 格'):
            self.call('pattern_cylinder_mount',dict(args,object=dict(obj,size_uv=[5,2])))
        with self.assertRaisesRegex(ValueError,'柱芯不完整'):
            self.call('pattern_cylinder_mount',dict(args,reserved_boxes=[]))
        if OUTPUT:
            self.save_report('cylinder',result)

    def test_open_curved_segment_and_frozen_replay(self):
        request = create_curve_fixture(self.root)
        mask = Path(request['mask'])
        obj = self.sample()
        mask.write_text(json.dumps(dict(schema_version=3,name='repeat',size_uv=[6,4],anchor_uv=[1,1],
                                        object=obj,clip_uv=[dict(lo=[2,1],hi=[2,2])])),encoding='utf8')
        request['mask_sha256'] = sha(mask)
        request['mapping'] = dict(u_start=.19,u_span=.072,y_start=0,max_distance=1.)
        request['cameras'] = [dict(id='detail',eye=[31,7,43],target=[25.5,2,30]),request['cameras'][0]]
        result = plan_curve(self.root,request)
        proof = result['summary']['repeat_tiling']
        actual,_ = read_master(result['candidate'])
        self.assert_readback(proof,actual)
        self.assertTrue(proof['seam_geometry_matches'],[j for j in proof['half_cell_joints'] if j['status']=='mismatch'])
        self.assertEqual({tuple(x['uv']) for x in proof['clipped']},{(2,1),(2,2)})
        self.assertTrue(verify_curve(self.root,result['plan'],result['plan_sha256'])['valid'])
        self.assertFalse(result['nbt_exported'])
        if RENDER:
            subprocess.run([sys.executable,'-B',str(SCRIPTS/'nbt_task.py'),'render','--source',result['candidate'],
                            '--cameras',result['cameras'],'--output',str(self.root/'after-images')],check=True)
        if OUTPUT:
            self.save_report('open-curve',result)
        sample = self.root/obj['sample']['path']
        baseline = sample.read_bytes()
        try:
            sample.write_bytes(baseline+b'changed')
            with self.assertRaisesRegex(ValueError,'SHA256'):
                verify_curve(self.root,result['plan'],result['plan_sha256'])
        finally:
            sample.write_bytes(baseline)

    def save_report(self,name,result):
        (self.root/(name+'-result.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output',type=Path)
    parser.add_argument('--render',action='store_true')
    options,remaining = parser.parse_known_args()
    OUTPUT = options.output.resolve() if options.output else None
    RENDER = options.render
    if OUTPUT:
        OUTPUT.mkdir(parents=True)
    unittest.main(argv=[sys.argv[0],*remaining],verbosity=2)
