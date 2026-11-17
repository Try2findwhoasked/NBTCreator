"""Explicit aspect distortion, bounded inlay, and measurable fitted detail."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np
from PIL import Image,ImageDraw

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_structure_agent import dispatch,build
from nbt_assembly import Volume
from nbt_refine import save_master
from nbt_selection_edit import sha
from nbt_surface_mount import NORMALS
from nbt_detail_control import compile_plan,simulate_plan,default_settings
from nbt_pattern_quality import assess


class PatternIntegration(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name)

    def test_quality_gate_can_choose_a_second_real_geometric_candidate(self):
        request=dict(surface='wall',preset='micro-scroll',size_uv=[6,6],quality_profile='ornate')
        baseline=dispatch(self.root,'pattern_microfit',request)
        self.assertLess(baseline['visual_quality']['score'],67.5)
        result=dispatch(self.root,'pattern_microfit',dict(request,min_quality_score=67.5))
        selection=result['microfit']['quality_selection']
        self.assertGreater(result['visual_quality']['score'],67.5)
        self.assertGreater(selection['selected_candidate_rank'],1)
        self.assertFalse(selection['assessments'][0]['passed'])
        self.assertTrue(result['microfit']['topology_preserved'])
        self.assertEqual(selection['reference'],'original_mapped_image')
        self.assertEqual(result['visual_quality']['minimum_score'],67.5)
        with self.assertRaisesRegex(ValueError,'量化质量未达标'):
            dispatch(self.root,'pattern_microfit',dict(request,min_quality_score=70))

    def ring(self):
        mask=Image.new('L',(8,8));ImageDraw.Draw(mask).rectangle((0,0,7,7),outline=255,width=2)
        image=Image.new('RGBA',(8,8),(255,0,0,255))
        ImageDraw.Draw(image).rectangle((4,0,7,7),fill=(0,0,255,255));image.putalpha(mask)
        file=self.root/'colored-ring.png';image.save(file)
        return file,dict(path=file.name,sha256=sha(file),noise_strength=0,channel='alpha',fit='stretch',
            colors=[dict(rgb='#ff0000',material='red_concrete'),dict(rgb='#0000ff',material='blue_concrete')])

    def fixture(self,normal='south',thickness=4,protected=None,unknown=False,plane=20):
        axis,sign=NORMALS[normal];lo=[4,4,4];hi=[23,23,23];lo[axis]=hi[axis]=plane
        inner=list(lo);inner[axis]-=(thickness-1)*sign
        model=Volume((36,36,36));model.box([min(a,b) for a,b in zip(lo,inner)],
            [max(a,b) for a,b in zip(hi,inner)],'stone_bricks')
        if unknown:
            q=[14,14,14];q[axis]=plane-sign;model.put(tuple(q),'stone_brick_slab')
        source=self.root/(normal+'.snbt');save_master(source,model,set(model.blocks))
        context=self.root/(normal+'-coordinates.json')
        context.write_text(json.dumps(dict(mode='standalone',openings=[],protected_boxes=protected or [])))
        surface=dict(source=source.name,source_sha256=sha(source),geometry_sha256=model.fingerprint(),
                     context=context.name,context_sha256=sha(context),lo=lo,hi=hi,normal=normal)
        query=dispatch(self.root,'parametric_surface',dict(surface=surface))
        return model,surface,query

    def mount(self,normal='south',depth=1,thickness=4,plane=20,**extra):
        model,surface,query=self.fixture(normal,thickness,plane=plane)
        obj=dict(surface='ceiling' if normal=='down' else 'wall',preset='micro-link',size_uv=[3,3] if normal=='down' else [2,2],fit_mode='micro')
        args=dict(surface=surface,surface_sha256=query['surface_sha256'],object=obj,anchor_uv=[10,10],embed_depth=depth,**extra)
        result=dispatch(self.root,'pattern_mount',args)
        return model,surface,args,result

    def test_explicit_stretch_exceeds_auto_aspect_limit_without_crop_and_aligns_colors(self):
        file,sample=self.ring();before=file.read_bytes()
        result=dispatch(self.root,'pattern_microfit',dict(surface='wall',size_uv=[12,4],sample=sample,micro_alignment='fixed'))
        alignment=result['microfit']['alignment']
        self.assertEqual(alignment['ratio_mode'],'stretch');self.assertEqual(alignment['aspect_adjustment'],3)
        self.assertEqual(result['microfit']['ink_overlap'],1)
        self.assertTrue(result['microfit']['topology_preserved'])
        data=build(self.root,result['spec']);ornament={(x,y):data['palette'][index] for x,y,z,index,wall in data['blocks'] if z==1}
        self.assertEqual(ornament[0,0],'minecraft:red_concrete')
        self.assertEqual(ornament[11,0],'minecraft:blue_concrete')
        self.assertFalse(any((x,2) in ornament for x in range(3,9)))
        self.assertEqual(file.read_bytes(),before)
        # Both fitting modes share the same mask/alpha/colour mapping.
        standard=dispatch(self.root,'pattern_compile',dict(surface='wall',size_uv=[12,4],sample=sample,
            shapes=dict(stairs='quartz_stairs',slab='quartz_slab')))
        self.assertEqual(standard['fitting']['missing'],0);self.assertEqual(standard['fitting']['extra'],0)
        for mode in ('auto','fixed'):
            quality=dispatch(self.root,'pattern_microfit',dict(surface='wall',size_uv=[12,4],sample=sample,micro_alignment=mode))
            self.assertEqual(quality['content_sha256'],result['content_sha256'])

    def test_inlay_and_recess_obey_all_five_plane_normals_and_leave_backing_unchanged(self):
        for normal in ('north','south','east','west','down'):
            for depth in (1,2):
                with self.subTest(normal=normal,depth=depth):
                    model,surface,args,result=self.mount(normal,depth)
                    axis,sign=NORMALS[normal]
                    states={tuple(op['lo'][i]+voxel[i] for i in range(3)):op['palette'][voxel[3]]
                            for op in result['operations'] for voxel in op['voxels']}
                    ink={p:v for p,v in states.items() if v!='minecraft:air'}
                    self.assertEqual({p[axis] for p in ink},{20-(depth-1)*sign})
                    self.assertTrue(all(0<=(20-p[axis])*sign<depth for p in states))
                    self.assertTrue(all(op['overwrite'] for op in result['operations']))
                    self.assertEqual(result['changed_blocks'],len(states))
                    if depth==2:self.assertTrue(any(value=='minecraft:air' for value in states.values()))
                    settings=default_settings();settings.update(operations=result['operations'],max_changed_blocks=4096)
                    candidate,walls,report=simulate_plan(model,set(model.blocks),compile_plan(settings,list(model.size)),dict(mode='standalone',openings=[],max_changed_blocks=4096))
                    for p in ink:
                        behind=list(p);behind[axis]-=sign
                        self.assertEqual(candidate.get(tuple(behind)),'minecraft:stone_bricks')
                    for p,value in states.items():
                        self.assertEqual(candidate.get(p),value)
                        if value=='minecraft:air':self.assertNotIn(p,walls)
                    self.assertEqual(sha(self.root/surface['source']),surface['source_sha256'])
                    self.assertTrue(result['pattern']['inlay'])

    def test_thin_or_unknown_backing_openings_protection_and_carving_budget_refuse(self):
        with self.assertRaisesRegex(ValueError,'厚度|背衬'):self.mount(thickness=1)
        _,surface,args,result=self.mount(depth=2)
        with self.assertRaisesRegex(ValueError,'预算'):
            dispatch(self.root,'pattern_mount',dict(args,max_changed_blocks=result['changed_blocks']-1))
        for plane in (20,19):
            model,surface,query=self.fixture(protected=[dict(lo=[4,4,plane],hi=[23,23,plane])])
            updated=dict(args,surface=surface,surface_sha256=query['surface_sha256'])
            with self.assertRaisesRegex(ValueError,'保护'):dispatch(self.root,'pattern_mount',updated)
        model,surface,query=self.fixture(unknown=True)
        updated=dict(args,surface=surface,surface_sha256=query['surface_sha256'])
        with self.assertRaisesRegex(ValueError,'背衬|厚度'):dispatch(self.root,'pattern_mount',updated)
        with self.assertRaisesRegex(ValueError,'留白'):
            _,surface,args,_=self.mount(depth=2)
            dispatch(self.root,'pattern_mount',dict(args,reserved_boxes=[dict(lo=[4,4,20],hi=[23,23,20])]))
        with self.assertRaisesRegex(ValueError,'地板'):
            dispatch(self.root,'pattern_mount',dict(args,object=dict(args['object'],surface='floor')))

    def test_recessed_ceiling_clearance_counts_ink_not_the_cleared_air_layer(self):
        _,surface,args,result=self.mount('down',2,plane=14,min_clearance=15)
        self.assertEqual(result['verification']['min_clearance'],15)
        with self.assertRaisesRegex(ValueError,'净空'):
            dispatch(self.root,'pattern_mount',dict(args,min_clearance=16))

    def test_standard_panel_embedding_reuses_host_instead_of_pasting_its_backing(self):
        _,_,args,_=self.mount('north',depth=2)
        obj={k:v for k,v in args['object'].items() if k!='fit_mode'}
        result=dispatch(self.root,'pattern_mount',dict(args,object=dict(obj,size_uv=[4,4])))
        ink={tuple(op['lo'][i]+voxel[i] for i in range(3)) for op in result['operations']
             for voxel in op['voxels'] if op['palette'][voxel[3]]!='minecraft:air'}
        self.assertEqual({p[2] for p in ink},{21})
        self.assertEqual(result['pattern']['placement_mode'],'recessed')

    def test_quality_detects_same_topology_detail_collapse_and_does_not_reward_noise(self):
        source=np.zeros((16,16),bool);source[1:15,7:9]=True
        source[2:4,1:15]=True;source[7:9,2:14]=True;source[12:14,1:15]=True
        high=np.repeat(np.repeat(source,8,0),8,1)
        faithful=assess(source,high,'ornate')
        collapsed=assess(np.ones_like(source),high,'ornate')
        self.assertEqual(faithful['source_features']['holes'],collapsed['fitted_features']['holes'])
        self.assertEqual(faithful['source_features']['components'],collapsed['fitted_features']['components'])
        self.assertGreater(faithful['score'],collapsed['score']+40)
        self.assertIn('source_detail_lost',collapsed['warnings'])
        noise=np.indices((16,16)).sum(axis=0)%2==0
        clutter=assess(noise,np.repeat(np.repeat(noise,8,0),8,1),'ornate')
        self.assertLess(clutter['score'],faithful['score'])
        self.assertIn('fragmented_or_visually_cluttered',clutter['warnings'])

    def test_ornate_gate_rejects_a_faithful_simple_ring_and_does_not_loosen_topology(self):
        request=dict(surface='wall',preset='micro-link',size_uv=[2,2],quality_profile='ornate')
        report=dispatch(self.root,'pattern_microfit',request)
        self.assertLess(report['visual_quality']['score'],70)
        self.assertIn('insufficient_ornate_detail',report['visual_quality']['warnings'])
        with self.assertRaisesRegex(ValueError,'量化质量未达标'):
            dispatch(self.root,'pattern_microfit',dict(request,min_quality_score=70))
        with self.assertRaisesRegex(ValueError,'主纹与孔洞|拓扑'):
            dispatch(self.root,'pattern_microfit',dict(request,surface='floor',min_quality_score=0))
        with self.assertRaisesRegex(ValueError,'单元评估'):
            dispatch(self.root,'pattern_compile',request)

    def test_thick_ring_corner_spurs_do_not_become_ornament_when_enlarged(self):
        source=np.zeros((24,24),bool);source[1:23,1:23]=True;source[10:14,10:14]=False
        for factor in (4,6,8):
            raster=np.repeat(np.repeat(source,factor,0),factor,1)
            result=assess(source,raster,'ornate')
            self.assertLess(result['score'],70)
            self.assertEqual(result['fitted_features']['branch_junctions'],0)
            self.assertEqual(result['source_features']['branch_junctions'],0)


if __name__=='__main__':unittest.main()
