"""Structural sections, open braces, clear apertures and real assembly faces."""
import copy
import sys
import tempfile
import unittest
from pathlib import Path
from itertools import product

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_structure_agent import dispatch,build
from nbt_object_library import library
from nbt_object_scene import halfcells,SIX
from nbt_components import placement,paste_plan
from nbt_assembly import Volume
from nbt_collision import check_routes
from nbt_registry import effective
from nbt_snbt import save_snbt,read_snbt
from nbt_structural_members import selected


def connected(voxels):
    remaining=halfcells({p:(value,False) for p,value in voxels.items()})
    first=remaining.pop();queue=[first]
    while queue:
        p=queue.pop()
        for step in SIX:
            q=tuple(a+b for a,b in zip(p,step))
            if q in remaining:remaining.remove(q);queue.append(q)
    return not remaining


class StructuralMembers(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.root=Path(tmp.name)
    def call(self,tool='parametric_compile',**args):return dispatch(self.root,tool,args)
    def voxels(self,result):
        data=build(self.root,result['spec'])
        return {tuple(row[:3]):data['palette'][row[3]] for row in data['blocks']}
    def recipe(self,identifier):return copy.deepcopy(next(row['arguments'] for row in library() if row['id']==identifier))

    def test_eight_recipes_have_real_material_contacts_and_pure_interfaces(self):
        from nbt_window_frames import PROFILES as WINDOW_PROFILES
        rows=[row for row in library() if selected(row['arguments']['kind'],row['arguments'].get('form',{}))
              and row['arguments'].get('form',{}).get('profile') not in WINDOW_PROFILES]
        self.assertEqual(len(rows),8)
        for row in rows:
            with self.subTest(id=row['id']):
                self.assertEqual(row['controls'],dict(style=False,spacing=False))
                result=self.call(**row['arguments']);v=self.voxels(result)
                self.assertEqual(result,self.call(**row['arguments']))
                self.assertEqual(result['revision'],15);self.assertTrue(connected(v))
                self.assertFalse(result['model_modified']);self.assertFalse(result['approval_created'])
                self.assertEqual(result['construction']['support'],'not_checked')
                for interface in result['interfaces']:
                    points=product(*(range(a,b+1) for a,b in zip(interface['lo'],interface['hi'])))
                    self.assertTrue(all(p in v for p in points),interface['id'])
        self.assertEqual(list(self.root.iterdir()),[])

    def test_i_beam_web_and_tube_void_stay_open_through_both_ends(self):
        for profile in ('i_section','box_section'):
            args=dict(kind='beam',size=[11,5,5],material='gray_concrete',accent='gray_concrete',form=dict(profile=profile,border=1))
            v=self.voxels(self.call(**args))
            for x in range(11):
                for z in range(5):
                    self.assertIn((x,0,z),v);self.assertIn((x,4,z),v)
                self.assertNotIn((x,2,1),v)
                if profile=='i_section':
                    self.assertIn((x,2,2),v);self.assertNotIn((x,2,0),v)
                else:
                    self.assertNotIn((x,2,2),v)
                    self.assertIn((x,2,0),v);self.assertIn((x,2,4),v)
        thick=self.call(kind='beam',size=[11,7,7],form=dict(profile='i_section',border=2))
        self.assertTrue(connected(self.voxels(thick)))

    def test_knee_has_an_open_triangle_and_a_face_connected_diagonal(self):
        a=self.voxels(self.call(**self.recipe('bracket-timber-knee')))
        self.assertIn((1,0,0),a);self.assertIn((1,6,6),a)
        self.assertIn((1,3,3),a);self.assertNotIn((1,1,5),a);self.assertNotIn((1,4,2),a)
        self.assertEqual({p[0] for p in a},{1});self.assertTrue(connected(a))
        b=self.voxels(self.call(**self.recipe('bracket-steel-angle')))
        self.assertNotIn((1,2,2),b);self.assertTrue(connected(b))

    def test_door_is_clear_at_floor_and_infers_only_unspecified_wood_axes(self):
        args=self.recipe('frame-timber-doorway');v=self.voxels(self.call(**args))
        self.assertNotIn((1,0,0),v);self.assertNotIn((1,1,0),v)
        self.assertEqual({p[2] for p in v},{0})
        self.assertEqual(effective(v[(0,0,0)])[1]['axis'],'y')
        self.assertEqual(effective(v[(1,2,0)])[1]['axis'],'x')
        args['material']='stripped_dark_oak_log[axis=z]'
        self.assertEqual(effective(self.voxels(self.call(**args))[(0,0,0)])[1]['axis'],'z')

    def test_window_recess_top_sill_and_glazing_only_regeneration(self):
        args=self.recipe('frame-recessed-window');before=self.call(**args);v=self.voxels(before)
        glass={p for p,value in v.items() if effective(value)[0]=='minecraft:glass'}
        self.assertEqual(glass,set(product(range(1,4),range(1,4),[2])))
        self.assertTrue(all(effective(v[(x,0,0)])[1]['type']=='top' for x in range(5)))
        replacement=copy.deepcopy(args);replacement['form']['glazing']=False
        changed=self.call('parametric_regenerate',object_id='window',part='glazing',original=args,replacement=replacement,
                          original_recipe_sha256=before['recipe_sha256'])
        self.assertEqual(self.voxels(changed),{p:value for p,value in v.items() if p not in glass})

    def test_only_doorway_claims_passage_and_the_real_player_route_passes(self):
        for identifier,passage in [('frame-timber-doorway',True),('frame-recessed-window',False)]:
            args=self.recipe(identifier);args['size']=[5,6,3];result=self.call(**args)
            model=Volume((12,10,12));frame=self.voxels(result)
            for x,z in product(range(12),repeat=2):model.put((x,0,z),'stone')
            for x,y,z in product(range(12),range(1,10),range(12)):
                if x<3 or x>5:model.put((x,y,z),'stone')
            for (x,y,z),value in frame.items():model.put((x+2,y+1,z+4),value)
            route=check_routes(model,[4.5,1,2.5],[[4.5,1,9.5]],max_poses=4000)
            self.assertEqual(route['passed'],passage)
            self.assertEqual(result['construction']['apertures'][0]['passage_candidate'],passage)

    def test_column_height_and_beam_span_link_through_the_object_scene(self):
        def ref(object,measure,offset=0):return dict(object=object,measure=measure,offset=offset)
        column=dict(kind='pillar',size=[3,5,3],form=dict(section='square',shaft_inset=0))
        graph=dict(schema_version=1,name='柱与工字梁',size=[22,14,12],objects=[
            dict(id='left',lo=[2,1,4],recipe=dict(tool='parametric_compile',arguments=column)),
            dict(id='right',lo=[12,1,4],recipe=dict(tool='parametric_compile',arguments={**column,'size':[3,ref('left','height'),3]})),
            dict(id='beam',lo=[ref('left','min_x'),ref('left','max_y',1),ref('left','min_z')],
                 contacts=['left','right'],recipe=dict(tool='parametric_compile',arguments=dict(kind='beam',
                    size=[dict(calc='subtract',args=[ref('right','max_x'),ref('left','min_x')],offset=1),3,3],form=dict(profile='i_section'))))])
        first=self.call('scene_compile',graph=graph)
        graph['objects'][0]['recipe']['arguments']['size'][1]=7
        second=self.call('scene_compile',graph=graph)
        get=lambda result:next(row for row in result['objects'] if row['id']=='beam')
        self.assertEqual(get(second)['bounds']['lo'][1],get(first)['bounds']['lo'][1]+2)
        self.assertEqual(set(get(second)['interfaces']),{'support_start','support_end','end_start','end_end','top'})

    def test_rotations_mirrors_roundtrip_and_host_protection(self):
        for identifier in ('beam-timber-rectangular','bracket-timber-knee','frame-recessed-window'):
            compiled=self.call(**self.recipe(identifier));data=build(self.root,compiled['spec'])
            for turns,mirror in ((0,None),(1,None),(2,'x'),(3,'z')):
                placed=placement(data,[20,1,20],[48,24,48],turns,mirror)
                volume=Volume((48,24,48));op=placed['operations'][0];edits,_=paste_plan(volume,op,set())
                for p,value in edits:volume.put(p,value)
                self.assertTrue(connected(volume.blocks))
                path=self.root/f'{identifier}-{turns}.snbt';save_snbt(path,volume,set());disk,_=read_snbt(path)
                self.assertEqual(disk.blocks,volume.blocks)
                with self.assertRaisesRegex(ValueError,'保护'):paste_plan(Volume((48,24,48)),op,{edits[0][0]})

    def test_invalid_members_refuse_before_preview_writes(self):
        cases=[dict(kind='beam',size=[11,3,3],form=dict(profile='i_section',border=2)),
               dict(kind='beam',size=[11,3,3],spacing=3,form=dict(profile='i_section')),
               dict(kind='beam',size=[11,3,3],style='open',form=dict(profile='i_section')),
               dict(kind='beam',size=[11,3,3],form=dict(profile='rectangular',pitch=3)),
               dict(kind='beam',size=[11,3,3],material='stone_slab',form=dict(profile='rectangular')),
               dict(kind='bracket',size=[3,5,5],form=dict(profile='knee_brace',border=3)),
               dict(kind='frame',size=[5,6,3],form=dict(profile='doorway',frame_depth=4)),
               dict(kind='frame',size=[5,6,3],form=dict(profile='recessed_window',recess=3)),
               dict(kind='frame',size=[5,6,3],form=dict(profile='recessed_window',glass_material='stone')),
               dict(kind='frame',size=[5,6,3],form=dict(profile='recessed_window',sill_material='stone_slab[type=bottom]')),
               dict(kind='frame',size=[5,6,3],form=dict(profile='rectangular',glazing=False))]
        for args in cases:
            with self.subTest(args=args),self.assertRaises(ValueError):self.call('parametric_preview',**args)
        self.assertEqual(list(self.root.iterdir()),[])


if __name__=='__main__':unittest.main(verbosity=2)
