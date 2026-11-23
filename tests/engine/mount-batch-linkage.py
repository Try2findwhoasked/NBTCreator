"""Atomic installations and immutable pattern bindings survive real scene edits."""
import copy,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_assembly import Volume
from nbt_refine import save_master,read_master
from nbt_agent.structure import dispatch,build
from nbt_selection_edit import sha
from nbt_detail_control import default_settings,compile_plan,simulate_plan
from nbt_pattern.assets import load
from nbt_runtime.modeling_session import ModellingSession
import nbt_selection_edit


class BatchLinkage(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);self.root=Path(temporary.name)

    def call(self,tool,args):return dispatch(self.root,tool,args)

    def fixture(self,thickness=4):
        model=Volume((28,26,28));model.box([2,2,11-thickness+1],[25,23,11],'stone_bricks')
        return self.bind(model,set(model.blocks))

    def bind(self,model,walls):
        source=self.root/'model.snbt';save_master(source,model,walls)
        context=self.root/'coordinates.json';context.write_text(json.dumps(dict(mode='standalone',openings=[])))
        return model,walls,dict(source=str(source),source_sha256=sha(source),geometry_sha256=model.fingerprint(),
            context=str(context),context_sha256=sha(context))

    def entry(self,id,x=4,normal='south',plane=11,depth=1):
        return dict(id=id,tool='pattern_mount',surface=dict(lo=[x,4,plane],hi=[x+3,7,plane],normal=normal),
            object=dict(surface='wall',preset='micro-link',size_uv=[2,2],fit_mode='micro'),anchor_uv=[2,0],embed_depth=depth)

    def replay(self,model,walls,result):
        settings=default_settings();settings.update(operations=result['operations'],max_changed_blocks=65536)
        return simulate_plan(model,walls,compile_plan(settings,list(model.size)),dict(mode='standalone',openings=[],max_changed_blocks=65536))[:2]

    def test_one_read_matches_two_real_sequential_mounts_and_never_writes_the_source(self):
        model,walls,target=self.fixture();before=Path(target['source']).read_bytes();items=[self.entry('left'),self.entry('right',15)]
        with patch.object(nbt_selection_edit,'read_master',wraps=nbt_selection_edit.read_master) as reader:
            result=self.call('mount_batch',dict(target=target,installations=items));self.assertEqual(reader.call_count,1)
        combined,mask=self.replay(model,walls,result)
        self.assertEqual(combined.fingerprint(),result['candidate_geometry_sha256'])
        current=model;current_walls=walls
        for i,item in enumerate(items):
            source=self.root/f'step_{i}.snbt';save_master(source,current,current_walls)
            surface=dict(target,source=str(source),source_sha256=sha(source),geometry_sha256=current.fingerprint(),**item['surface'])
            query=self.call('parametric_surface',dict(surface=surface))
            args={k:v for k,v in item.items() if k not in ('id','tool','surface')}
            single=self.call(item['tool'],dict(args,surface=surface,surface_sha256=query['surface_sha256']))
            current,current_walls=self.replay(current,current_walls,single)
        self.assertEqual(combined.blocks,current.blocks);self.assertEqual(mask,current_walls)
        self.assertEqual(Path(target['source']).read_bytes(),before)

    def test_asset_replaced_during_final_replay_is_rejected(self):
        import nbt_detail_control
        _,_,target=self.fixture();_,asset,_=self.asset_graph()
        item=self.entry('one')
        item['object'].pop('preset')
        item['object']['pattern_asset']=dict(id=asset['id'],image_sha256=asset['image_sha256'])
        original=nbt_detail_control.simulate_plan;replaced=[]
        def simulate(*args,**kwargs):
            result=original(*args,**kwargs)
            if any(op['label'].startswith('one · ') for op in args[2]['operations']):
                Path(asset['image']).write_bytes(b'replaced during replay');replaced.append(True)
            return result
        with patch.object(nbt_detail_control,'simulate_plan',side_effect=simulate):
            with self.assertRaisesRegex(ValueError,'图像哈希'):
                self.call('mount_batch',dict(target=target,installations=[item]))
        self.assertEqual(replaced,[True]);self.assertEqual(sha(target['source']),target['source_sha256'])

    def test_budget_duplicate_ids_overlap_and_late_failure_leave_all_files_unchanged(self):
        _,_,target=self.fixture();items=[self.entry('one'),self.entry('two',15)]
        good=self.call('mount_batch',dict(target=target,installations=items))
        files={p:p.read_bytes() for p in self.root.iterdir()}
        floor=dict(id='floor',tool='pattern_mount',surface=dict(lo=[4,23,8],hi=[7,23,11],normal='up'),
            object=dict(surface='floor',preset='micro-link',size_uv=[3,3],fit_mode='micro'),anchor_uv=[1,1])
        for bad,extra,reason in [([floor,dict(floor,id='two')],{},'覆盖'),
            ([items[0],dict(items[1],id='one')],{},'ID重复'),(items,dict(max_changed_blocks=good['changed_blocks']-1),'预算')]:
            with self.assertRaisesRegex(ValueError,reason):self.call('mount_batch',dict(target=target,installations=bad,**extra))
        self.assertEqual({p:p.read_bytes() for p in self.root.iterdir()},files)

    def test_later_opposite_recess_cannot_destroy_an_earlier_nonoverlapping_backing(self):
        _,_,target=self.fixture(2)
        first=dict(id='outer',tool='parametric_mount',surface=dict(lo=[5,2,11],hi=[12,9,11],normal='south'),
            object=dict(kind='wall',size=[3,3,3]),anchor_uv=[3,1])
        second=dict(id='inner',tool='pattern_mount',surface=dict(lo=[5,2,10],hi=[12,9,10],normal='north'),
            object=dict(surface='wall',preset='micro-link',size_uv=[2,2],fit_mode='micro'),anchor_uv=[3,1],embed_depth=2)
        with self.assertRaisesRegex(ValueError,'batch_backing_invalidated'):
            self.call('mount_batch',dict(target=target,installations=[first,second]))

    def test_later_furniture_must_preserve_the_first_ceiling_clearance(self):
        model=Volume((28,26,28));model.box([0,0,0],[27,0,27],'stone');model.box([2,20,2],[25,21,25],'stone')
        _,_,target=self.bind(model,set(model.blocks))
        ceiling=dict(id='ceiling',tool='parametric_mount',surface=dict(lo=[5,20,5],hi=[14,20,14],normal='down'),
            object=dict(kind='ceiling',size=[3,3,3]),anchor_uv=[4,4],min_clearance=8)
        pillar=dict(id='furniture',tool='parametric_mount',surface=dict(lo=[5,0,5],hi=[14,0,14],normal='up'),
            object=dict(kind='pillar',size=[3,14,3]),anchor_uv=[4,4])
        with self.assertRaisesRegex(ValueError,'clearance_obstruction'):
            self.call('mount_batch',dict(target=target,installations=[ceiling,pillar]))

    def test_combined_budget_cannot_exceed_the_bound_context_limit(self):
        _,_,target=self.fixture();items=[self.entry('one'),self.entry('two',15)]
        context=Path(target['context']);context.write_text(json.dumps(dict(mode='standalone',openings=[],max_changed_blocks=1)))
        target['context_sha256']=sha(context)
        with self.assertRaisesRegex(ValueError,'预算'):
            self.call('mount_batch',dict(target=target,installations=items,max_changed_blocks=65536))

    def test_scene_rechecks_decorator_clearance_after_adding_other_objects(self):
        host=dict(tool='structure',arguments=dict(name='顶板与地板',size=[16,24,16],operations=[
            dict(kind='box',label='地板',lo=[0,0,0],hi=[15,0,15],state='stone'),
            dict(kind='box',label='顶板',lo=[2,20,2],hi=[13,21,13],state='stone')]))
        ceiling=dict(id='ring',tool='parametric_mount',surface=dict(lo=[2,20,2],hi=[13,20,13],normal='down'),
            object=dict(kind='ceiling',size=[3,3,3]),anchor_uv=[6,6],min_clearance=8)
        graph=dict(schema_version=1,name='跨对象净空',size=[16,24,16],objects=[
            dict(id='roof',lo=[0,0,0],recipe=dict(tool='surface_decorate',arguments=dict(host=host,installations=[ceiling]))),
            dict(id='pillar',lo=[7,1,7],recipe=dict(tool='parametric_compile',arguments=dict(kind='pillar',size=[3,14,3])))])
        for turns in range(4):
            rotated=copy.deepcopy(graph);rotated['size']=[20,24,20]
            rotated['objects'][0].update(lo=[2,0,2],quarter_turns=turns)
            x,z=7,7
            for _ in range(turns):x,z=15-z,x
            rotated['objects'][1]['lo']=[x+2,1,z+2]
            with self.subTest(turns=turns),self.assertRaisesRegex(ValueError,'对象图饰面净空.*clearance_obstruction'):
                self.call('scene_compile',dict(graph=rotated))

    def test_json_lines_session_executes_new_candidates_without_writing_files(self):
        from io import BytesIO
        from nbt_engine_session import serve
        _,_,target=self.fixture();graph,_,_=self.asset_graph()
        requests=[dict(id='batch',method='agent',params=dict(tool='mount_batch',arguments=dict(target=target,installations=[self.entry('one')]))),
                  dict(id='linked',method='agent',params=dict(tool='scene_compile',arguments=dict(graph=graph)))]
        files={p:p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        output=BytesIO();serve(self.root,BytesIO(('\n'.join(json.dumps(v) for v in requests)+'\n').encode()),output)
        replies=[json.loads(v) for v in output.getvalue().splitlines()]
        self.assertEqual([v['id'] for v in replies],['batch','linked'])
        self.assertTrue(all(v['ok'] for v in replies),replies)
        self.assertEqual({p:p.read_bytes() for p in self.root.rglob('*') if p.is_file()},files)

    def asset_graph(self):
        source=load(self.root,'builtin:micro-scroll')
        asset=self.call('pattern_assets',dict(action='copy',id=source['id'],image_sha256=source['image_sha256'],name='原卷纹'))
        mirror=self.call('pattern_create',dict(name='反向卷纹',resolution=[32,32],layers=[dict(kind='asset',id=asset['id'],image_sha256=asset['image_sha256'],flip_x=True)]))
        def reference(a):return dict(id=a['id'],image_sha256=a['image_sha256'])
        host=dict(tool='structure',arguments=dict(name='宿主',size=[8,8,6],operations=[dict(kind='box',label='宿主',lo=[1,0,1],hi=[6,7,4],state='stone_bricks',classification='body')]))
        ornament=dict(id='inlay',tool='pattern_mount',surface=dict(lo=[2,1,4],hi=[5,6,4],normal='south'),anchor_uv=[2,0],embed_depth=1,
            object=dict(surface='wall',pattern_ref='cloud',asset_options=dict(fit='stretch'),size_uv=[4,6],fit_mode='micro',material='waxed_cut_copper'))
        recipe=dict(tool='surface_decorate',arguments=dict(host=host,installations=[ornament]))
        graph=dict(schema_version=1,name='共享纹样联动',size=[24,12,8],patterns=[dict(id='cloud',asset=reference(asset))],objects=[
            dict(id='left',recipe=recipe,lo=[0,0,0]),dict(id='right',recipe=copy.deepcopy(recipe),lo=[12,0,0]),
            dict(id='cap',recipe=dict(tool='structure',arguments=dict(name='顶帽',size=[6,1,4],operations=[dict(kind='box',label='顶帽',lo=[0,0,0],hi=[5,0,3],state='gold_block')])),
                lo=[1,dict(object='left',measure='max_y',offset=1),1],contacts=['left']),
            dict(id='marker',recipe=dict(tool='structure',arguments=dict(name='不受影响标记',size=[1,1,1],operations=[dict(kind='box',label='标记',lo=[0,0,0],hi=[0,0,0],state='quartz_block')])),lo=[22,0,6])])
        return graph,asset,mirror

    def test_one_pattern_binding_refits_two_objects_and_preserves_both_scene_versions(self):
        graph,asset,mirror=self.asset_graph();candidate=self.call('scene_compile',dict(graph=graph))
        receipt=self.call('scene_save',{k:candidate[k] for k in ('graph','graph_sha256','content_sha256')})
        before=Path(asset['image']).read_bytes()
        request={k:receipt[k] for k in ('id','revision','version')};request['pattern_changes']=[dict(id='cloud',asset=dict(id=mirror['id'],image_sha256=mirror['image_sha256']))]
        with self.assertRaisesRegex(ValueError,'预算'):self.call('scene_update',dict(request,max_changed_blocks=1))
        self.assertEqual(self.call('scene_read',dict(id=receipt['id']))['version'],receipt['version'])
        changed=self.call('scene_update',request)
        self.assertEqual(changed['changed_patterns'],['cloud']);self.assertEqual(changed['affected_objects'],['cap','left','right'])
        self.assertNotEqual(changed['content_sha256'],candidate['content_sha256'])
        self.assertEqual(self.call('scene_read',dict(id=receipt['id']))['version'],receipt['version'])
        saved=self.call('scene_save',{k:changed[k] for k in ('graph','graph_sha256','content_sha256','parent')})
        self.assertEqual(saved['revision'],2)
        self.assertEqual(self.call('scene_read',dict(id=receipt['id'],version=receipt['version']))['candidate']['content_sha256'],candidate['content_sha256'])
        self.assertEqual(Path(asset['image']).read_bytes(),before)
        self.assertEqual(changed['graph']['objects'][0]['recipe']['arguments']['installations'][0]['object']['pattern_ref'],'cloud')

    def test_asset_hash_and_unknown_binding_fail_even_with_warm_compilation_cache(self):
        graph,asset,_=self.asset_graph()
        with ModellingSession(self.root):
            self.call('scene_compile',dict(graph=graph));Path(asset['image']).write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'图像哈希'):self.call('scene_compile',dict(graph=graph))
        graph['patterns'][0]['id']='missing'
        with self.assertRaisesRegex(ValueError,'绑定缺失'):self.call('scene_compile',dict(graph=graph))


if __name__=='__main__':unittest.main(verbosity=2)
