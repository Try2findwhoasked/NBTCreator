"""Complex legal-shape refinement retains original topology and quality gates."""
import sys,tempfile,unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_agent.structure import dispatch,build
from nbt_runtime.modeling_session import current


class OrnateFitting(unittest.TestCase):
    def setUp(self):
        directory=tempfile.TemporaryDirectory();self.addCleanup(directory.cleanup);self.root=Path(directory.name)
    def fit(self,size,**extra):
        return dispatch(self.root,'pattern_microfit',dict(surface='wall',preset='gothic-rose',size_uv=[size,size],micro_alignment='fixed',quality_profile='ornate',**extra))
    def test_complex_rose_edges_and_detail_improve_at_the_same_size(self):
        for size in (8,10):
            with self.subTest(size=size):
                result=self.fit(size);q=result['microfit'];trace=q['shape_search']['refinement']
                guard=trace['quality_guard']
                self.assertGreater(q['ink_overlap'],trace['previous_ink_overlap'])
                self.assertLess(q['contour_error'],trace['previous_contour_error'])
                self.assertGreater(q['visual_quality']['score'],guard['previous_score'])
                self.assertGreaterEqual(guard['candidate_detail_retention'],guard['previous_detail_retention'])
                self.assertTrue(q['topology_preserved']);self.assertEqual(q['source_topology']['holes'],q['result_topology']['holes'])
                self.assertTrue(trace['improved']);self.assertTrue(guard['accepted']);self.assertLessEqual(trace['proposals'],384)
                self.assertGreater(result['shape_counts'].get('stairs',0),0);self.assertGreater(result['shape_counts'].get('slab',0),0)
                current().clear();self.assertEqual(result['content_sha256'],self.fit(size)['content_sha256'])
                with self.assertRaisesRegex(ValueError,'纹样量化质量未达标'):
                    self.fit(size,min_quality_score=q['visual_quality']['score']+1)

    def test_better_coverage_cannot_replace_preserved_detail(self):
        result=self.fit(12,min_quality_score=80);q=result['microfit'];guard=q['shape_search']['refinement']['quality_guard']
        self.assertFalse(guard['accepted'])
        self.assertTrue(guard['candidate_score']<guard['previous_score'] or
            guard['candidate_detail_retention']<guard['previous_detail_retention'])
        self.assertEqual(q['visual_quality']['score'],guard['previous_score'])
        repair=q['shape_search']['repair']
        self.assertGreater(repair['initial_error'],repair['final_error'])
        self.assertTrue(repair['feasible']);self.assertLessEqual(repair['proposals'],repair['proposal_budget'])
        self.assertEqual(q['result_topology']['holes'],17)
        current().clear();self.assertEqual(result['content_sha256'],self.fit(12,min_quality_score=80)['content_sha256'])

    def test_original_area_budget_is_retained_even_when_local_search_can_repair_it(self):
        result=self.fit(10,micro_max_error=.218);self.assertLessEqual(result['microfit']['raw_coverage_error'],.218)
        with self.assertRaisesRegex(ValueError,'覆盖误差'):self.fit(10,micro_max_error=.21)
    def test_quality_failure_creates_no_files_and_does_not_relax_threshold(self):
        with self.assertRaisesRegex(ValueError,'纹样量化质量未达标'):self.fit(10,min_quality_score=100)
        self.assertEqual(list(self.root.iterdir()),[])
    def test_copies_reuse_the_solved_shape_and_keep_automatic_orientation(self):
        result=self.fit(10,tile_counts=[2,1]);data=build(self.root,result['spec'])
        points={(x,y):data['palette'][i] for x,y,z,i,_ in data['blocks'] if z==1}
        left={p:v for p,v in points.items() if p[0]<10};right={(x-11,y):v for (x,y),v in points.items() if x>=11}
        self.assertEqual(left,right);self.assertEqual(result['microfit']['unit_size_uv'],[10,10])

    def test_column_preset_can_wrap_only_through_the_real_micro_cylinder_checks(self):
        listed=dispatch(self.root,'pattern_list',{})
        self.assertEqual(listed['micro_cylinder_policy']['source_surface'],'column')
        result=dispatch(self.root,'pattern_microfit',dict(surface='cylinder',preset='micro-link',size_uv=[2,2],diameter=7,tile_counts=[6,3],gap_uv=[0,1]))
        world=result['microfit']['world_geometry'];self.assertTrue(world['topology_preserved'])
        self.assertEqual(world['checked_instances'],18);self.assertGreater(world['corner_connector_blocks'],0)
        with self.assertRaisesRegex(ValueError,'未配置此安装面'):
            dispatch(self.root,'pattern_compile',dict(surface='cylinder',preset='micro-link',size_uv=[7,8]))


if __name__=='__main__':unittest.main(verbosity=2)
