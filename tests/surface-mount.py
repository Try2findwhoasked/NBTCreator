import json,subprocess,sys,tempfile,unittest
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_assembly import Volume
from nbt_refine import save_master
from nbt_selection_edit import sha
from nbt_structure_agent import dispatch
from nbt_surface_mount import NORMALS

class Mount(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name)
    def fixture(self,normal='south',gap=False,protected=False):
        axis,sign=NORMALS[normal];lo=[3]*3;hi=[17]*3;lo[axis]=hi[axis]=20
        model=Volume((42,42,42));model.box(lo,hi,'stone_bricks')
        if gap:
            model.box([9,3,20],[11,6,20],'air')
            model.put((16,12,20),'stone_brick_slab')
        source=self.root/'master.snbt';save_master(source,model,set(model.blocks))
        context=self.root/'coordinates.json';context.write_text(json.dumps(dict(mode='standalone',openings=[],protected_boxes=[dict(lo=[3,3,21],hi=[8,8,22])] if protected else [])))
        return dict(source=source.name,source_sha256=sha(source),geometry_sha256=model.fingerprint(),context=context.name,context_sha256=sha(context),lo=lo,hi=hi,normal=normal)
    def call(self,tool,**arguments):return dispatch(self.root,'parametric_'+tool,arguments)
    def test_six_normals_contact_correct_side(self):
        for normal,(axis,sign) in NORMALS.items():
            with self.subTest(normal=normal):
                surface=self.fixture(normal);query=self.call('surface',surface=surface)
                kind={'up':'table','down':'ceiling'}.get(normal,'wall')
                plan=self.call('mount',surface=surface,surface_sha256=query['surface_sha256'],object=dict(kind=kind,size=[4,5,3]),anchor_uv=[6,6])
                self.assertFalse(plan['model_modified']);self.assertEqual(sha(self.root/surface['source']),surface['source_sha256'])
                coords=[op['lo'][axis]+xyz[axis] for op in plan['operations'] for xyz in op['voxels']]
                self.assertTrue(all((coordinate-20)*sign>0 for coordinate in coords));self.assertIn(20+sign,coords)
    def test_opening_protection_layout_and_staleness(self):
        surface=self.fixture(gap=True,protected=True);query=self.call('surface',surface=surface)
        self.assertEqual(query['opening_candidates'][0]['cells'],12)
        self.assertTrue(any(c['status']=='unknown_shape' for c in query['cells']))
        args=dict(surface=surface,surface_sha256=query['surface_sha256'],object=dict(kind='wall',size=[3,3,3]))
        with self.assertRaisesRegex(ValueError,'保护'):self.call('mount',**args,anchor_uv=[1,1])
        with self.assertRaisesRegex(ValueError,'开口'):self.call('mount',**args,anchor_uv=[7,1])
        with self.assertRaisesRegex(ValueError,'预算'):self.call('mount',**args,anchor_uv=[2,9],max_changed_blocks=1)
        result=self.call('layout',**args,on_conflict='skip',gap_uv=[1,1])
        self.assertTrue(result['placements']);self.assertTrue(result['skipped'])
        with self.assertRaisesRegex(ValueError,'留白'):self.call('mount',**args,anchor_uv=[2,9],reserved_boxes=[dict(lo=[3,10,21],hi=[8,15,23])])
        with self.assertRaisesRegex(ValueError,'上下文'):self.call('mount',**{**args,'surface_sha256':'0'*64},anchor_uv=[2,9])
        (self.root/'coordinates.json').write_text('{}')
        with self.assertRaisesRegex(ValueError,'上下文'):self.call('mount',**args,anchor_uv=[2,9])

    def test_pattern_mount_six_normals_inlay_and_protection(self):
        for normal,(axis,sign) in NORMALS.items():
            with self.subTest(normal=normal):
                surface=self.fixture(normal)
                query=self.call('surface',surface=surface)
                plane={'up':'floor','down':'ceiling'}.get(normal,'column')
                preset={'floor':'cosmati-floor','ceiling':'coffer-rosette','column':'braided-shaft'}[plane]
                obj=dict(surface=plane,preset=preset,size_uv=[9,9])
                if plane!='floor':obj['shapes']=dict(stairs='quartz_stairs')
                args=dict(surface=surface,surface_sha256=query['surface_sha256'],object=obj,anchor_uv=[7,7 if axis==1 else 3])
                result=dispatch(self.root,'pattern_mount',args)
                coords=[op['lo'][axis]+xyz[axis] for op in result['operations'] for xyz in op['voxels']]
                self.assertEqual(result['pattern']['inlay'],normal=='up')
                if normal=='up':
                    self.assertEqual(set(coords),{20})
                    self.assertTrue(all(op['overwrite'] for op in result['operations']))
                else:
                    self.assertTrue(all((n-20)*sign>0 for n in coords))
                    self.assertIn(20+sign,coords)
                self.assertEqual(sha(self.root/surface['source']),surface['source_sha256'])
                self.assertTrue(result['verification']['protection'])
                self.assertGreater(result['pattern']['fitting']['requested'],0)
                with self.assertRaisesRegex(ValueError,'预算'):
                    dispatch(self.root,'pattern_mount',dict(args,max_changed_blocks=1))
                wrong=dict(obj,surface='floor' if plane!='floor' else 'ceiling')
                with self.assertRaises(ValueError):dispatch(self.root,'pattern_mount',dict(args,object=wrong))
                context=self.root/'coordinates.json'
                point=[10,20,10] if normal=='up' else [10,18,10] if normal=='down' else [10,10,20+sign] if axis==2 else [20+sign,10,10]
                context.write_text(json.dumps(dict(mode='standalone',openings=[],protected_boxes=[dict(lo=point,hi=point)])))
                updated=dict(surface,context_sha256=sha(context))
                bound=self.call('surface',surface=updated)
                with self.assertRaisesRegex(ValueError,'保护'):
                    dispatch(self.root,'pattern_mount',dict(args,surface=updated,surface_sha256=bound['surface_sha256']))

    def test_ceiling_minimum_clearance_and_missing_route_context(self):
        surface=self.fixture('down')
        query=self.call('surface',surface=surface)
        args=dict(surface=surface,surface_sha256=query['surface_sha256'],
                  object=dict(kind='ceiling',size=[5,6,5],form=dict(drop=3)),anchor_uv=[6,6])
        result=self.call('mount',**args,min_clearance=16)
        self.assertEqual(result['verification']['min_clearance'],16)
        with self.assertRaisesRegex(ValueError,'起点和目标'):
            self.call('mount',**args,require_routes=True)
        model=Volume((42,42,42))
        model.box([3,20,3],[17,20,17],'stone_bricks')
        model.put((7,10,7),'stone')
        source=self.root/surface['source']
        save_master(source,model,set())
        updated=dict(surface,source_sha256=sha(source),geometry_sha256=model.fingerprint())
        updated_query=self.call('surface',surface=updated)
        with self.assertRaisesRegex(ValueError,'净空'):
            self.call('mount',**dict(args,surface=updated,surface_sha256=updated_query['surface_sha256']),min_clearance=12)

    def test_fit_gothic_and_write_same_camera_review(self):
        surface=self.fixture()
        query=self.call('surface',surface=surface)
        args=dict(surface=surface,surface_sha256=query['surface_sha256'],anchor_uv=[7,1],
                  object=dict(kind='wall',size=[15,11,4],style='open',
                              ornament=dict(profile='gothic',density=100,border_layers=0,depth=2)))
        with self.assertRaisesRegex(ValueError,'悬空'):
            self.call('mount',**args)
        cameras=self.root/'cameras.json'
        cameras.write_text(json.dumps([dict(id='whole',eye=[24,17,33],target=[10,8,20])]))
        fit=dict(max_gap=2,material='stone_bricks')
        result=self.call('mount',**args,surface_fit=fit,review=dict(cameras=cameras.name))
        connectors=result['placements'][0]['connector_positions']
        self.assertTrue(connectors)
        self.assertTrue(all(point[2]==21 for point in connectors))
        self.assertEqual(result['review']['status'],'complete')
        self.assertEqual(result['review']['sides']['after']['geometry_sha256'],result['candidate_geometry_sha256'])
        self.assertEqual(sha(self.root/surface['source']),surface['source_sha256'])
        with self.assertRaisesRegex(ValueError,'悬空|留白'):
            self.call('mount',**args,surface_fit=fit,reserved_boxes=[
                dict(lo=[3,5,21],hi=[17,12,21])])

    def test_route_comparison_detects_blocked_required_leg_with_alternate_path(self):
        from nbt_mount_review import compare_routes
        before=Volume((12,6,12));before.box([0,0,0],[11,0,11],'stone')
        after=Volume(before.size);after.blocks=dict(before.blocks)
        after.box([5,1,3],[5,2,3],'stone')
        start=[2.5,1,3.5];targets={'end':[8.5,1,3.5]}
        config=dict(start=start,targets=targets,route_legs=[dict(name='侧廊',start=start,targets=targets,
            validation_only_barriers=[dict(lo=[0,1,0],hi=[11,3,2]),dict(lo=[0,1,4],hi=[11,3,11])])])
        result=compare_routes(before,after,config,{(5,1,3),(5,2,3)})
        self.assertTrue(result['comparisons'][0]['after_passed'])
        self.assertTrue(result['comparisons'][1]['before_passed'])
        self.assertFalse(result['comparisons'][1]['after_passed'])
        self.assertTrue(result['comparisons'][1]['targets'][0]['writes_along_previous_path'])
        with self.assertRaisesRegex(ValueError,'侧廊'):
            compare_routes(before,after,config,{(5,1,3)},required=True)

    def test_workspace_cli_and_layout_patterns(self):
        from nbt_exposure import apply
        surface=self.fixture();apply(self.root)
        request=self.root/'request.json'
        facade=self.root/'.agents/skills/nbtcreator-workspace/nbt.py'
        def cli(tool,arguments):
            request.write_text(json.dumps(arguments),encoding='utf8')
            result=subprocess.run([sys.executable,str(facade),'components','agent','--tool','parametric_'+tool,'--request',str(request)],cwd=self.root,capture_output=True,encoding='utf8')
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            return json.loads(result.stdout)['result']
        query=cli('surface',dict(surface=surface))
        params=dict(surface=surface,surface_sha256=query['surface_sha256'],object=dict(kind='wall',size=[3,3,3]))
        center=cli('layout',dict(params,pattern='center'))
        self.assertEqual(len(center['placements']),1)
        border=self.call('layout',**params,pattern='border',gap_uv=[1,1])
        anchors={tuple(item['anchor_uv']) for item in border['placements']}
        self.assertEqual(anchors,{(u,v) for u in (1,5,9,13) for v in (0,4,8,12) if u in (1,13) or v in (0,12)})
        thicker=self.call('surface',surface=dict(surface,min_support=2))
        self.assertEqual(thicker['usable_uv'],[])
        self.assertTrue(all(c['status']=='thin_support' for c in thicker['cells']))

if __name__=='__main__':unittest.main(verbosity=2)
