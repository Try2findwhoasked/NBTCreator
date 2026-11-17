"""Roman/classical order cues are distinct, connected and truly fluted."""
import copy,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_structure_agent import dispatch,build
from nbt_classical_column import ORDERS


class ClassicalColumns(unittest.TestCase):
    def setUp(self):
        directory=tempfile.TemporaryDirectory();self.addCleanup(directory.cleanup);self.root=Path(directory.name)
    def call(self,args):return dispatch(self.root,'parametric_compile',args)
    def request(self,order,**patch):return dict(kind='pillar',size=[13,56,13],material='quartz_block',accent='smooth_sandstone',form=dict(order=order,**patch))
    def points(self,result):return {tuple(row[:3]) for row in build(self.root,result['spec'])['blocks']}
    def test_five_orders_have_actual_distinct_connected_capitals_and_public_discovery(self):
        listing=dispatch(self.root,'parametric_list',dict(kind='pillar'));self.assertEqual(set(listing['column_orders']),set(ORDERS))
        hashes=set()
        for order in ORDERS:
            result=self.call(self.request(order));self.assertEqual(result['spec']['size'],[13,56,13]);self.assertEqual(result['resolved_form']['section'],'round')
            self.assertEqual(result['content_sha256'],self.call(self.request(order))['content_sha256']);hashes.add(result['content_sha256'])
            points=self.points(result);seen={next(iter(points))};pending=list(seen)
            while pending:
                x,y,z=pending.pop()
                for n in ((x-1,y,z),(x+1,y,z),(x,y-1,z),(x,y+1,z),(x,y,z-1),(x,y,z+1)):
                    if n in points and n not in seen:seen.add(n);pending.append(n)
            self.assertEqual(points,seen,order)
        self.assertEqual(len(hashes),5);self.assertEqual(list(self.root.iterdir()),[])
    def test_flutes_remove_geometry_and_round_corners_are_empty(self):
        smooth=self.call(self.request('roman_doric',flutes=False));fluted=self.call(self.request('roman_doric',flutes=True,flute_count=12,flute_depth=.8))
        a={p for p in self.points(smooth) if 10<=p[1]<=35};b={p for p in self.points(fluted) if 10<=p[1]<=35}
        self.assertTrue(b<a);self.assertNotIn((1,12,1),a)
        for x,z in ((6,6),(5,6),(6,5)):self.assertIn((x,12,z),b)
    def test_leaf_and_neck_patterns_change_real_geometry(self):
        for key,first,second in [('leaf_count',4,12),('leaf_layers',1,3),('neck_pattern','none','egg_dart'),('volute_turns',.75,1.5)]:
            with self.subTest(key=key):
                a=self.call(self.request('composite',**{key:first}));b=self.call(self.request('composite',**{key:second}))
                self.assertNotEqual(a['content_sha256'],b['content_sha256'])
        cap=self.call(self.request('corinthian'));bounds=cap['parts']['capital'];points=self.points(cap)
        self.assertTrue(any(p[0] in (1,11) and bounds['lo'][1]+1<=p[1]<bounds['hi'][1] for p in points))
    def test_capital_regeneration_preserves_the_long_round_shaft(self):
        original=self.request('composite',leaf_count=6);first=self.call(original);replacement=copy.deepcopy(original);replacement['form']['leaf_count']=10
        result=dispatch(self.root,'parametric_regenerate',dict(object_id='roman-column',part='capital',original=original,replacement=replacement,original_recipe_sha256=first['recipe_sha256']))
        cap_start=first['parts']['capital']['lo'][1]
        def lower(value):
            data=build(self.root,value['spec']);return {tuple(row[:3]):data['palette'][row[3]] for row in data['blocks'] if row[1]<cap_start}
        self.assertEqual(lower(first),lower(result));self.assertGreater(result['changed_blocks'],0)
    def test_too_small_or_irrelevant_parameters_are_rejected_without_writes(self):
        for args in [dict(self.request('corinthian'),size=[5,16,5]),self.request('ionic',volute_scale=.3,capital_height=7),
            dict(self.request('ionic'),material='quartz_slab'),self.request('ionic',detail_material='quartz_slab'),self.request('tuscan',leaf_count=8),self.request('ionic',capital_curve=[1,.5,.5,1]),self.request('tuscan',flute_count=16),self.request('ionic',capital_height=3),
            self.request('composite',capital_pattern=dict(pattern=dict(preset='micro-scroll',size_uv=[4,4]))),
            dict(kind='wall',size=[12,40,4]),dict(kind='pillar',size=[33,56,13]),
            dict(kind='pillar',size=[9,32,9],form=dict(section='round',inset=0,shaft_ratio=1,entasis=.2))]:
            with self.subTest(args=args),self.assertRaises(ValueError):self.call(args)
        # Padding for a 64-high decorated pillar must not create a 66-high host.
        args=dict(kind='pillar',size=[9,64,9],form=dict(base_height=6,capital_height=8,base_pattern=dict(pattern=dict(preset='micro-scroll',size_uv=[4,2]))))
        self.assertEqual(self.call(args)['spec']['size'],[9,64,9]);self.assertEqual(list(self.root.iterdir()),[])


if __name__=='__main__':unittest.main(verbosity=2)
