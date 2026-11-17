"""Reuse must preserve geometry, bindings, cache isolation and route limits."""
import json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_modeling_session import ModellingSession
from nbt_structure_agent import dispatch,build
from nbt_selection_edit import sha
from nbt_assembly import Volume
from nbt_refine import save_master
from nbt_collision import check_routes
import nbt_micro_alignment,nbt_pattern_panel,nbt_collision


class TransportTests(unittest.TestCase):
    def test_changed_engine_and_oversized_input_never_execute_a_tool(self):
        from io import BytesIO
        from nbt_engine_session import serve,MAX_REQUEST
        request=dict(id='version-check',method='agent',params=dict(tool='pattern_list',arguments={}))
        with tempfile.TemporaryDirectory() as workspace,patch('nbt_engine_session.engine_revision',side_effect=['before','after']),patch('nbt_structure_agent.dispatch') as dispatched:
            output=BytesIO();serve(workspace,BytesIO((json.dumps(request)+'\n').encode()),output)
            self.assertEqual(json.loads(output.getvalue())['code'],'STALE_ENGINE');dispatched.assert_not_called()
        with tempfile.TemporaryDirectory() as workspace,patch('nbt_structure_agent.dispatch') as dispatched:
            output=BytesIO();serve(workspace,BytesIO(b'x'*(MAX_REQUEST+1)),output)
            self.assertEqual(output.getvalue(),b'');dispatched.assert_not_called()


class SessionTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name)
        image=self.root/'source.png';Image.new('L',(16,16),255).save(image)
        self.sample=dict(path=image.name,sha256=sha(image),noise_strength=0)
        self.proposal=dict(surface='wall',size_uv=[2,2],sample=self.sample)

    def test_unit_fit_is_reused_across_layouts_but_not_colours_or_changed_bytes(self):
        with ModellingSession(self.root),patch.object(nbt_micro_alignment,'adaptive_fit',wraps=nbt_micro_alignment.adaptive_fit) as fitted:
            single=dispatch(self.root,'pattern_microfit',self.proposal)
            tiled=dispatch(self.root,'pattern_microfit',dict(self.proposal,name='另一个铺排',base='stone',tile_counts=[2,2],gap_uv=[2,1]))
            self.assertEqual(fitted.call_count,1)
            self.assertEqual(tiled['shape_counts']['full'],4*single['shape_counts']['full'])
            tiled['microfit']['quality_selection']['assessments'][0]['score']=-1
            another=dispatch(self.root,'pattern_microfit',dict(self.proposal,tile_counts=[3,1]))
            self.assertGreater(another['microfit']['visual_quality']['score'],0)
            for material in ('red_concrete','blue_concrete'):
                sample=dict(self.sample,colors=[dict(rgb='#ffffff',material=material)])
                result=dispatch(self.root,'pattern_microfit',dict(self.proposal,sample=sample))
                self.assertIn('minecraft:'+material,result['spec']['operations'][0]['palette'])
            self.assertEqual(fitted.call_count,3)
            Image.new('L',(16,16),0).save(self.root/'source.png')
            with self.assertRaisesRegex(ValueError,'SHA256'):
                dispatch(self.root,'pattern_microfit',dict(self.proposal,tile_counts=[4,1]))
            self.assertEqual(fitted.call_count,3)

    def test_fit_then_mount_reuses_compilation_without_mutable_aliases(self):
        model=Volume((16,12,16));model.box([2,2,8],[13,10,8],'stone')
        source=self.root/'wall.snbt';save_master(source,model,set());before=source.read_bytes()
        context=self.root/'context.json';context.write_text(json.dumps(dict(mode='standalone',openings=[])))
        surface=dict(source=source.name,source_sha256=sha(source),geometry_sha256=model.fingerprint(),
                     context=context.name,context_sha256=sha(context),lo=[2,2,8],hi=[13,10,8],normal='south')
        with ModellingSession(self.root) as session,patch.object(nbt_micro_alignment,'adaptive_fit',wraps=nbt_micro_alignment.adaptive_fit) as fitted:
            compiled=session.call('pattern_microfit',self.proposal)
            expected=compiled['content_sha256'];compiled['spec']['name']='must not poison cache'
            query=session.call('parametric_surface',dict(surface=surface))
            mounted=session.call('pattern_mount',dict(surface=surface,surface_sha256=query['surface_sha256'],
                            object=dict(self.proposal,fit_mode='micro'),anchor_uv=[5,2]))
            again=session.call('pattern_microfit',self.proposal)
            self.assertEqual(fitted.call_count,1);self.assertEqual(again['content_sha256'],expected)
            self.assertNotEqual(again['spec']['name'],compiled['spec']['name'])
            self.assertTrue(mounted['pattern']['microfit']['backing_reused'])
            self.assertGreater(session.stats['hits'],0)
            Image.new('L',(16,16),0).save(self.root/'source.png')
            with self.assertRaisesRegex(ValueError,'SHA256'):session.call('pattern_microfit',self.proposal)
        self.assertEqual(source.read_bytes(),before)

    def test_changed_preset_raster_and_hash_invalidate_unchanged_arguments(self):
        file=self.root/'preset.png';Image.new('L',(16,16),255).save(file)
        manifest={'horizontal-stripes':dict(file=file.name,sha256=sha(file),surfaces=['wall'])}
        args=dict(surface='wall',size_uv=[1,1],preset='horizontal-stripes',micro_alignment='fixed')
        with ModellingSession(self.root),patch.object(nbt_pattern_panel,'LIBRARY',self.root),patch.object(nbt_pattern_panel,'library',return_value=manifest):
            full=dispatch(self.root,'pattern_microfit',args)
            image=Image.new('L',(16,16));image.paste(255,(0,8,16,16));image.save(file)
            manifest['horizontal-stripes']['sha256']=sha(file)
            half=dispatch(self.root,'pattern_microfit',args)
            self.assertNotEqual(full['content_sha256'],half['content_sha256'])
            self.assertEqual(half['shape_counts'],dict(slab=1))

    def test_route_hits_do_not_hide_mutations_limits_or_target_order(self):
        model=Volume((12,6,5));model.box([0,0,0],[11,0,4],'stone')
        model.box([0,1,0],[11,4,1],'stone');model.box([0,1,3],[11,4,4],'stone')
        with ModellingSession(),patch.object(nbt_collision,'_check_routes',wraps=nbt_collision._check_routes) as searched:
            first=check_routes(model,[1.5,1,2.5],{'far':[10.5,1,2.5]});first['passed']=False
            self.assertTrue(check_routes(model,[1.5,1,2.5],{'far':[10.5,1,2.5]})['passed'])
            self.assertEqual(searched.call_count,1)
            limited=check_routes(model,[1.5,1,2.5],{'far':[10.5,1,2.5]},max_poses=1)
            self.assertTrue(limited['search_limit_reached']);self.assertEqual(searched.call_count,2)
            targets={'near':[2.5,1,2.5],'far':[10.5,1,2.5]}
            a=check_routes(model,[1.5,1,2.5],targets)
            b=check_routes(model,[1.5,1,2.5],dict(reversed(list(targets.items()))))
            self.assertEqual([r['name'] for r in a['targets']],['near','far'])
            self.assertEqual([r['name'] for r in b['targets']],['far','near'])
            model.box([6,1,2],[6,3,2],'stone')
            self.assertFalse(check_routes(model,[1.5,1,2.5],targets)['passed'])

    def test_collision_index_reused_for_different_route_starts(self):
        model=Volume((10,5,10));model.box([0,0,0],[9,0,9],'stone')
        with ModellingSession(),patch.object(nbt_collision,'_Space',wraps=nbt_collision._Space) as indexed:
            self.assertTrue(check_routes(model,[1.5,1,1.5],[[7.5,1,7.5]])['passed'])
            self.assertTrue(check_routes(model,[7.5,1,7.5],[[1.5,1,1.5]])['passed'])
            self.assertEqual(indexed.call_count,1)

    def test_bounded_sessions_do_not_leak_results_between_contexts(self):
        first=ModellingSession(max_entries=1);second=ModellingSession()
        first.put('test','a',{'value':[1]});value=first.get('test','a');value['value'].append(2)
        self.assertEqual(first.get('test','a'),{'value':[1]})
        self.assertIsNone(second.get('test','a'))
        first.put('test','b',{'value':3});self.assertIsNone(first.get('test','a'))
        first.clear();self.assertIsNone(first.get('test','b'))


if __name__=='__main__':unittest.main(verbosity=2)
