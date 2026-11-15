"""Bulk writes and cached validation retain strict geometry/layer semantics."""
import copy,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_assembly import Volume
from nbt_model import Model,state
from nbt_structure_agent import build,definitions,dispatch
from nbt_capabilities import capabilities
from nbt_detail_control import default_settings,compile_plan,simulate_plan


class Materialization(unittest.TestCase):
    def setUp(self):
        directory=tempfile.TemporaryDirectory();self.addCleanup(directory.cleanup);self.root=Path(directory.name)
    def test_batch_matches_serial_with_air_duplicates_and_mutable_states(self):
        edits=[([1,2,3],'stone'),([2,2,3],dict(Name='oak_log',Properties=dict(axis='x'))),([1,2,3],'air'),([1,2,3],'quartz_block')]
        a=Volume([8]*3);b=Volume([8]*3)
        for p,v in edits:a.put(p,v)
        b.put_many(edits);self.assertEqual(a.blocks,b.blocks)
        mutable=dict(Name='oak_log',Properties=dict(axis='z'));b.put_many([([4,2,3],mutable)])
        mutable['Properties']['axis']='invalid'
        with self.assertRaises(ValueError):b.put_many([([5,2,3],mutable)])
        self.assertNotIn((5,2,3),b.blocks)
    def test_batch_late_invalid_coordinate_or_state_is_atomic_and_seal_remains_enforced(self):
        model=Volume([8]*3);model.put([0,0,0],'stone');before=dict(model.blocks)
        for bad in [([8,2,2],'stone'),([True,2,2],'stone'),([2.0,2,2],'stone'),([2,2,2],'not_a_block')]:
            with self.assertRaises((ValueError,AssertionError)):model.put_many([([1,1,1],'gold_block'),bad])
            self.assertEqual(model.blocks,before)
        model.stage='sealed'
        with self.assertRaises(AssertionError):model.put_many([([1,1,1],'stone')])
    def test_custom_put_and_provenance_observe_batch_writes(self):
        from nbt_provenance import OperationTrace
        model=Volume([8]*3);trace=OperationTrace(model);self.addCleanup(trace.close)
        with trace.operation('batch','批量落点'):model.put_many([([1,1,1],'stone'),([2,1,1],'quartz_block')])
        self.assertEqual(trace.owners,{(1,1,1):'batch',(2,1,1):'batch'})
        class Restricted(Volume):
            def put(self,p,v):
                if p[0]>3:raise ValueError('custom footprint')
                super().put(p,v)
        custom=Restricted([8]*3)
        with self.assertRaisesRegex(ValueError,'custom footprint'):custom.put_many([([6,1,1],'stone')])
    def test_public_catalogue_results_cannot_mutate_cached_internal_schemas(self):
        a=definitions();a['field_compile']['parameters']['properties']['size']['items']['maximum']=999
        b=capabilities();b['agent_tools'].clear();b['tools'].clear()
        self.assertEqual(definitions()['field_compile']['parameters']['properties']['size']['items']['maximum'],64)
        self.assertIn('box',capabilities()['tools'])
        with self.assertRaises(ValueError):dispatch(self.root,'field_compile',dict(size=[999]*3,root='x',nodes=[]))
    def test_face_components_match_independent_pairwise_connectivity(self):
        from nbt_architectural_bay import component_count
        import random
        rng=random.Random(438)
        for _ in range(24):
            points=list({tuple(rng.randrange(-3,4) for _ in range(3)) for i in range(rng.randrange(50))})
            parent=list(range(len(points)))
            def root(i):
                while parent[i]!=i:i=parent[i]
                return i
            for i in range(len(points)):
                for j in range(i):
                    if sum(abs(a-b) for a,b in zip(points[i],points[j]))==1:parent[root(i)]=root(j)
            self.assertEqual(component_count(points),len({root(i) for i in range(len(points))}))
    def test_catalogue_snapshot_refreshes_when_file_changes(self):
        import nbt_catalog
        file=self.root/'catalog.json';file.write_text('{"value":1}')
        with patch.object(nbt_catalog,'FILE',file):
            self.assertEqual(nbt_catalog.snapshot()[0]['value'],1);old=nbt_catalog.snapshot()[1]
            file.write_text('{"value":200}');self.assertEqual(nbt_catalog.snapshot()[0]['value'],200)
            self.assertNotEqual(nbt_catalog.snapshot()[1],old)
    def test_component_rows_still_reject_bool_float_duplicate_and_bad_layers(self):
        import nbt_components
        fixture=dict(schema_version=1,name='fixture',size=[4]*3,anchor=[0]*3,palette=['stone'],blocks=[[1,1,1,0,True]])
        for row in [[True,1,1,0,True],[1.,1,1,0,True],[4,1,1,0,True],[1,1,1,True,True],[1,1,1,0,1]]:
            with self.subTest(row=row),self.assertRaises(ValueError):nbt_components.validate(dict(fixture,blocks=[row]))
        with self.assertRaises(ValueError):nbt_components.validate(dict(fixture,blocks=fixture['blocks']*2))
    def test_mixed_palette_pastes_match_original_serial_candidate_path(self):
        spec=dict(name='分层试件',size=[8]*3,operations=[
            dict(kind='paste_component',label='墙',classification='wall',lo=[1,1,1],hi=[4,4,4],palette=['stone','quartz_block'],voxels=[[0,0,0,0],[1,0,0,1],[2,0,0,0]]),
            dict(kind='paste_component',label='主体覆盖',classification='body',overwrite=True,lo=[1,1,1],hi=[4,4,4],palette=['stone','air'],voxels=[[0,0,0,0],[1,0,0,1]])])
        current=build(self.root,spec)
        def serial(model,edits):
            for p,v in edits:model.put(p,v)
        with patch.object(Model,'put_many',new=serial):legacy=build(self.root,spec)
        self.assertEqual(current,legacy)
        self.assertEqual(current['blocks'],[[1,1,1,0,False],[3,1,1,0,True]])
    def test_protection_layer_conflict_budget_and_invalid_voxel_refuse_unchanged(self):
        model=Volume([8]*3);model.put([2,2,2],'stone');walls={(2,2,2)}
        op=dict(kind='paste_component',label='覆盖',classification='body',overwrite=False,lo=[2,2,2],hi=[3,3,3],palette=['stone'],voxels=[[0,0,0,0]])
        settings=default_settings();settings.update(operations=[op],max_changed_blocks=32);plan=compile_plan(settings,model.size)
        with self.assertRaisesRegex(ValueError,'墙层|已有'):simulate_plan(model,walls,plan,dict(mode='standalone',openings=[],max_changed_blocks=32))
        plan['operations'][0]['overwrite']=True
        with self.assertRaises(ValueError):simulate_plan(model,walls,plan,dict(mode='standalone',openings=[],max_changed_blocks=0))
        with self.assertRaises(ValueError):simulate_plan(model,walls,plan,dict(mode='standalone',openings=[],protected_boxes=[dict(lo=[2,2,2],hi=[2,2,2])],max_changed_blocks=32))
        self.assertEqual(model.blocks,{(2,2,2):'minecraft:stone'});self.assertEqual(walls,{(2,2,2)})
        for voxels in [[[True,0,0,0]],[[0.,0,0,0]],[[0,0,0,1]],[[0,0,0,0],[0,0,0,0]]]:
            spec=dict(name='拒绝',size=[8]*3,operations=[dict(op,voxels=voxels)])
            with self.assertRaises(ValueError):build(self.root,spec)


if __name__=='__main__':unittest.main(verbosity=2)
