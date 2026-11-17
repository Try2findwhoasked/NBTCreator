"""Fancy windows preserve apertures, panes, depth and actual member contact."""
import copy,sys,tempfile,unittest
from pathlib import Path
from itertools import product
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_structure_agent import dispatch,build
from nbt_registry import effective
from nbt_components import placement,paste_plan
from nbt_assembly import Volume
from nbt_snbt import save_snbt,read_snbt
from nbt_object_scene import halfcells,SIX


def connected(values):
    remaining=halfcells({p:(value,False) for p,value in values.items()});pending=[remaining.pop()]
    while pending:
        p=pending.pop()
        for step in SIX:
            q=tuple(a+b for a,b in zip(p,step))
            if q in remaining:remaining.remove(q);pending.append(q)
    return not remaining


class WindowFrames(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.root=Path(tmp.name)
    def call(self,args,tool='parametric_compile'):return dispatch(self.root,tool,args)
    def values(self,result):
        data=build(self.root,result['spec'])
        return {tuple(row[:3]):data['palette'][row[3]] for row in data['blocks']}
    def requests(self):
        for profile,size,form in [('sash_window',[10,13,4],{}),('classical_window',[13,21,4],{}),
          ('classical_window',[13,24,4],dict(head='triangular')),
          ('round_arch_window',[15,23,4],dict(border=2,lights=2)),
          ('pointed_arch_window',[19,27,4],dict(glass_palette=['blue_stained_glass','cyan_stained_glass','yellow_stained_glass']))]:
            yield dict(kind='frame',size=size,material='smooth_sandstone',accent='cut_sandstone',form=dict(profile=profile,recess=2,**form))

    def test_five_architectural_forms_are_deterministic_connected_and_pure(self):
        hashes=set()
        for args in self.requests():
            result=self.call(args);values=self.values(result)
            self.assertEqual(result,self.call(args));self.assertTrue(connected(values))
            self.assertFalse(result['approval_created']);self.assertFalse(result['model_modified'])
            self.assertGreater(result['construction']['glass_blocks'],0);hashes.add(result['content_sha256'])
            for face in result['interfaces']:
                self.assertTrue(all(p in values for p in product(*(range(a,b+1) for a,b in zip(face['lo'],face['hi'])))))
        self.assertEqual(len(hashes),5);self.assertEqual(list(self.root.iterdir()),[])

    def test_sash_has_twelve_real_lights_and_two_sash_depths(self):
        args=next(self.requests());result=self.call(args);values=self.values(result)
        glass={p for p,v in values.items() if effective(v)[0]=='minecraft:glass'}
        self.assertEqual(len(glass),48);self.assertEqual({p[2] for p in glass},{2,3})
        for x in (3,6):self.assertTrue(all(not any((x,y,z) in glass for z in (2,3)) for y in range(1,12)))
        self.assertTrue(all((x,6,z) in values and (x,6,z) not in glass for x in range(1,9) for z in (2,3)))
        self.assertTrue(all([x,6] in result['construction']['apertures'][0]['cells_xy'] for x in range(1,9)))

    def test_unGlazing_keeps_mouldings_and_dividers_and_can_regenerate_locally(self):
        for args in self.requests():
            before=self.call(args);a=self.values(before);replacement=copy.deepcopy(args);replacement['form']['glazing']=False
            result=dispatch(self.root,'parametric_regenerate',dict(object_id='window',part='glazing',original=args,replacement=replacement,original_recipe_sha256=before['recipe_sha256']))
            b=self.values(result);glass={p for p,v in a.items() if 'glass' in effective(v)[0]}
            self.assertEqual(b,{p:v for p,v in a.items() if p not in glass});self.assertTrue(connected(b))
            plain=self.call(replacement)
            for x,y in plain['construction']['apertures'][0]['clear_cells_xy']:
                self.assertTrue(all((x,y,z) not in b for z in range(args['size'][2])))

    def test_arch_spandrels_remain_air_and_there_is_no_opaque_back_plate(self):
        for args in list(self.requests())[-2:]:
            result=self.call(args);v=self.values(result);w,h,d=args['size']
            self.assertTrue(all((0,h-1,z) not in v and (w-1,h-1,z) not in v for z in range(d)))
            without=copy.deepcopy(args);without['form']['glazing']=False
            clear=self.call(without)['construction']['apertures'][0]['clear_cells_xy']
            self.assertGreater(len(clear),30)

    def test_classical_layers_dentils_and_pediment_have_real_depth(self):
        args=list(self.requests())[1];result=self.call(args);a=self.values(result)
        other=copy.deepcopy(args);other['form']['dentils']=False;b=self.values(self.call(other))
        self.assertGreater(len(a),len(b));self.assertTrue(connected(b))
        self.assertEqual(effective(a[(0,0,0)])[1]['type'],'top')
        roof=self.values(self.call(list(self.requests())[2]))
        self.assertNotIn((0,23,0),roof);self.assertIn((6,23,0),roof)

    def test_all_quarter_turns_and_mirrors_preserve_actual_geometry_roundtrip(self):
        args=list(self.requests())[-1];result=self.call(args);data=build(self.root,result['spec'])
        for turns,mirror in product(range(4),(None,'x','z')):
            plan=placement(data,[32,0,32],[64,48,64],turns,mirror);volume=Volume((64,48,64))
            edits,_=paste_plan(volume,plan['operations'][0],set())
            for p,v in edits:volume.put(p,v)
            self.assertTrue(connected(volume.blocks));file=self.root/f'{turns}-{mirror}.snbt'
            save_snbt(file,volume,set());disk,_=read_snbt(file);self.assertEqual(disk.blocks,volume.blocks)

    def test_invalid_underresolved_or_cross_profile_requests_leave_no_previews(self):
        base=next(self.requests());bad=[]
        for patch in (dict(size=[5,7,4]),dict(form=dict(profile='sash_window',panes=[3,3])),
                      dict(form=dict(profile='sash_window',recess=3)),dict(form=dict(profile='classical_window',head='scroll')),
                      dict(form=dict(profile='round_arch_window',panes=[2,2])),
                      dict(form=dict(profile='pointed_arch_window',border=2)),
                      dict(form=dict(profile='sash_window',glass_material='stone')),
                      dict(form=dict(profile='sash_window',glass_material='glass',glass_palette=['glass'])),
                      dict(ornament=dict(profile='gothic'))):bad.append({**base,**patch})
        for args in bad:
            with self.subTest(args=args),self.assertRaises(ValueError):self.call(args,'parametric_preview')
        self.assertEqual(list(self.root.iterdir()),[])
        invalid=dict(kind='frame',size=[13,24,4],form=dict(profile='classical_window',head='triangular',cornice_material='smooth_quartz_slab[type=bottom]'))
        with self.assertRaisesRegex(ValueError,'cornice_material'):self.call(invalid,'parametric_preview')


if __name__=='__main__':unittest.main(verbosity=2)
