"""Assembly interfaces use real half-cell surfaces and separate contact order."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_structure_agent import dispatch
from nbt_working_model import WorkingModel, model_hash


def solid(size, state='stone'):
    return dict(tool='structure', arguments=dict(name='实体', size=size, operations=[dict(kind='box', label='主体',
        classification='body', lo=[0, 0, 0], hi=[n-1 for n in size], state=state)]))


def assembly(height=5, right_height=None):
    return dict(schema_version=1, name='具名接口柱梁顶', size=[20, 16, 14], objects=[
        dict(id='left', lo=[2, 0, 4], recipe=dict(tool='parametric_compile', arguments=dict(kind='pillar', size=[3, height, 3]))),
        dict(id='right', lo=[12, 0, 4], recipe=dict(tool='parametric_compile', arguments=dict(kind='pillar',
            size=[3, right_height if right_height is not None else dict(object='left', measure='height'), 3]))),
        dict(id='beam', recipe=dict(tool='span_beam', arguments=dict(width=3, height=1, material='quartz_block')),
            span={'axis':'x', 'from':dict(object='left', interface='capital_top'), 'to':dict(object='right', interface='capital_top')},
            interfaces=[dict(id='roof_seat', face='up', lo=[0,0,0], hi=[12,0,2])]),
        dict(id='roof', recipe=solid([13,1,5]), attach=dict(target='beam', face='up', interface='roof_seat'))])


class Interfaces(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    def compile(self, graph):
        return dispatch(self.root, 'scene_compile', dict(graph=graph))

    def test_reciprocal_contacts_do_not_create_generation_cycles(self):
        graph = dict(schema_version=1, name='互相接触', size=[8,8,8], objects=[
            dict(id='a', recipe=solid([2,2,2]), lo=[0,0,0], contacts=['b']),
            dict(id='b', recipe=solid([2,2,2]), lo=[2,0,0], contacts=['a'])])
        result = self.compile(graph)
        self.assertEqual([row['depends_on'] for row in result['objects']], [[], []])
        graph['objects'][1]['lo'][0] = 3
        with self.assertRaisesRegex(ValueError, '未与声明支承面连接'):
            self.compile(graph)

    def test_span_and_named_roof_seat_follow_column_height(self):
        before = {row['id']:row for row in self.compile(assembly())['objects']}
        after = {row['id']:row for row in self.compile(assembly(7))['objects']}
        for key in ('right', 'beam', 'roof'):
            self.assertEqual(after[key]['bounds']['hi'][1], before[key]['bounds']['hi'][1]+2)
        self.assertEqual(before['beam']['origin'], [2,5,4])
        self.assertEqual(before['left']['interfaces']['capital_top']['plane_half'], 10)
        self.assertEqual(len(before['beam']['span_interfaces']), 2)

    def test_unequal_height_missing_interface_and_false_surfaces_are_rejected(self):
        with self.assertRaisesRegex(ValueError, '高度不同'):
            self.compile(assembly(5,7))
        graph = assembly()
        graph['objects'][2]['span']['from']['interface'] = 'missing'
        with self.assertRaisesRegex(ValueError, '接口不存在'):
            self.compile(graph)
        graph = dict(schema_version=1, name='空气接口', size=[8,8,8], objects=[dict(id='air',lo=[0,0,0],
            recipe=dict(tool='structure',arguments=dict(name='小块',size=[4,4,4],operations=[dict(kind='box',label='实体',
                classification='body',lo=[0,0,0],hi=[0,0,0],state='stone')])),
            interfaces=[dict(id='false_top',face='up',lo=[2,2,2],hi=[3,3,3])])])
        with self.assertRaisesRegex(ValueError, '没有实际几何'):
            self.compile(graph)

    def test_half_slab_interface_is_not_rounded_into_full_block_support(self):
        graph = dict(schema_version=1,name='半砖承托',size=[12,8,8],objects=[
            dict(id=name,lo=[x,0,1],recipe=solid([1,1,1],'stone_slab[type=bottom]'),
                interfaces=[dict(id='seat',face='up',lo=[0,0,0],hi=[0,0,0])]) for name,x in (('a',1),('b',6))])
        result = self.compile(graph)
        self.assertEqual(result['objects'][0]['interfaces']['seat']['plane_half'], 1)
        graph['objects'].append(dict(id='beam',recipe=dict(tool='span_beam',arguments=dict(width=1,height=1)),
            span={'axis':'x','from':dict(object='a',interface='seat'),'to':dict(object='b',interface='seat')}))
        with self.assertRaisesRegex(ValueError, '不能舍入半格'):
            self.compile(graph)

    def test_named_side_surface_rotates_with_an_asymmetric_host(self):
        graph = dict(schema_version=1,name='旋转接口',size=[16,12,16],objects=[dict(id='host',lo=[3,1,4],quarter_turns=1,
            recipe=solid([3,4,5]),interfaces=[dict(id='east_side',face='east',lo=[2,0,0],hi=[2,3,4])])])
        interface = self.compile(graph)['objects'][0]['interfaces']['east_side']
        self.assertEqual(interface['face'], 'south')
        self.assertEqual(interface['normal'], [0,0,1])
        self.assertEqual(interface['area'], 20)

    def test_managed_scene_roundtrip_across_48_and_host_protection(self):
        context = dict(mode='standalone',openings=[],reserved_boxes=[dict(lo=[48,8,6],hi=[48,8,6])])
        m = WorkingModel(self.root,[96,20,16],context)
        m.install('portal',dict(tool='scene_compile',arguments=dict(graph=assembly())),[40,1,2])
        original = model_hash(m.model,m.walls)
        objects={row['id']:row for row in m.inspect('portal')['instances']['portal']['objects']}
        self.assertEqual(objects['beam']['bounds']['lo'],[42,6,6])
        self.assertEqual(objects['left']['interfaces']['capital_top']['plane_half'],12)
        saved = m.save_draft('跨格柱梁')
        reopened = WorkingModel.open(self.root,saved['source'])
        with self.assertRaisesRegex(ValueError,'RESERVED_SPACE'):
            reopened.update('portal',dict(tool='scene_compile',arguments=dict(graph=assembly(7))))
        self.assertEqual(model_hash(reopened.model,reopened.walls),original)

    def test_world_queries_follow_mirror_and_rotation_and_recipe_only_updates(self):
        m=WorkingModel(self.root,[64,24,48],kind='component')
        recipe=dict(tool='scene_compile',arguments=dict(graph=assembly()))
        m.install('turned',recipe,[30,1,30],quarter_turns=1,mirror='x')
        children=m.inspect('turned')['instances']['turned']['objects']
        self.assertTrue(m.validate()['assembly']['passed'])
        for child in children:
            self.assertEqual(child['coordinate_space'],'host')
            for interface in child['interfaces'].values():
                for half in interface['faces_half']:
                    p=tuple(v//2 for v in half)
                    self.assertNotEqual(m.model.get(p),'minecraft:air')
        first=dispatch(self.root,'scene_compile',dict(graph=assembly()))
        saved=dispatch(self.root,'scene_save',{key:first[key] for key in ('graph','graph_sha256','content_sha256')})
        # Adding a second name for an existing surface changes semantic intent,
        # while leaving every Minecraft block identical.
        patch_row=dict(id='left',interfaces=[dict(id='alternate_seat',face='up',lo=[0,4,0],hi=[2,4,2])])
        result=dispatch(self.root,'scene_update',dict(id=saved['id'],revision=saved['revision'],version=saved['version'],changes=[patch_row]))
        self.assertEqual(result['changed_blocks'],0)
        self.assertNotEqual(result['graph_sha256'],first['graph_sha256'])

    def test_host_carving_invalidates_actual_interface_instead_of_reusing_old_receipt(self):
        from nbt_working_model import value_at
        m=WorkingModel(self.root,[64,24,48],kind='component')
        m.install('portal',dict(tool='scene_compile',arguments=dict(graph=assembly())),[10,1,2])
        p=(12,5,6)
        m.patch([dict(pos=list(p),before=value_at(m.model,m.walls,p),after=['minecraft:air',False])])
        checks=m.inspect()['assembly_checks']
        self.assertFalse(checks['passed'])
        self.assertTrue(any(item.get('interface')=='capital_top' and not item['passed'] for item in checks['checks']))
        with self.assertRaisesRegex(ValueError,'ASSEMBLY_INVALID'):
            m.save_draft('接口被挖空')

    def test_managed_scene_update_preserves_original_scene_constraints(self):
        graph = dict(schema_version=1,name='场景保护',size=[8,8,8],
            protected_boxes=[dict(lo=[1,1,1],hi=[1,1,1])],
            objects=[dict(id='block',lo=[1,1,1],recipe=solid([1,1,1]))])
        m = WorkingModel(self.root,[12,8,12],kind='component')
        m.install('scene',dict(tool='scene_compile',arguments=dict(graph=graph)),[0,0,0])
        from nbt_working_model import value_at
        with self.assertRaisesRegex(ValueError,'保护'):
            m.patch([dict(pos=[1,1,1],before=value_at(m.model,m.walls,(1,1,1)),after=['minecraft:gold_block',False])])
        with self.assertRaisesRegex(ValueError,'保护'):
            m.update('scene',transform=dict(position=[1,0,0]))
        edited = deepcopy(graph)
        edited['objects'][0]['recipe'] = solid([1,1,1],'gold_block')
        with self.assertRaisesRegex(ValueError,'保护'):
            m.update('scene',dict(tool='scene_compile',arguments=dict(graph=edited)))
        self.assertEqual(m.model.get((1,1,1)),'minecraft:stone')
        edited['protected_boxes'] = []
        with self.assertRaisesRegex(ValueError,'约束'):
            m.update('scene',dict(tool='scene_compile',arguments=dict(graph=edited)))

    def test_buried_slab_surface_is_invalid_after_host_edit(self):
        graph = dict(schema_version=1,name='半砖接口',size=[4,4,4],objects=[
            dict(id='slab',lo=[1,0,1],recipe=solid([1,1,1],'stone_slab[type=bottom]'),
                interfaces=[dict(id='seat',face='up',lo=[0,0,0],hi=[0,0,0])])])
        for turns in (0,1,2,3):
            m = WorkingModel(self.root,[8,8,8],kind='component')
            m.install('slab',dict(tool='scene_compile',arguments=dict(graph=graph)),[3,0,3],quarter_turns=turns,mirror='x')
            p = m.instances['slab']['compiled']['objects'][0]['voxel_positions'][0]
            from nbt_working_model import value_at
            m.patch([dict(pos=p,before=value_at(m.model,m.walls,tuple(p)),after=['minecraft:stone',False])])
            self.assertFalse(m.inspect()['assembly_checks']['passed'])
            with self.assertRaisesRegex(ValueError,'ASSEMBLY'):
                m.save_draft('埋入的接口')

    def test_self_contact_is_rejected_and_free_decorations_remain_supported(self):
        graph = dict(schema_version=1,name='摆件',size=[4,4,4],objects=[
            dict(id='decor',lo=[1,1,1],recipe=solid([1,1,1]),contacts=['decor'])])
        with self.assertRaisesRegex(ValueError,'自己'):
            self.compile(graph)
        graph['objects'][0].pop('contacts')
        graph['objects'][0]['recipe'] = solid([1,1,1],'lantern')
        m = WorkingModel(self.root,[4,4,4],kind='component')
        m.install('decor',dict(tool='scene_compile',arguments=dict(graph=graph)),[0,0,0])
        self.assertTrue(m.validate()['assembly']['passed'])
        m.save_draft('自由摆件')

    def test_scene_reserved_spaces_and_routes_follow_host_rotation(self):
        from nbt_working_model import value_at
        graph = dict(schema_version=1,name='有路的平台',size=[6,4,3],
            objects=[dict(id='floor',lo=[0,0,0],recipe=solid([6,1,3]))],
            reserved_boxes=[dict(lo=[3,1,1],hi=[3,3,1])],
            routes=dict(start=[1.5,1,1.5],targets=[[4.5,1,1.5]]))
        m = WorkingModel(self.root,[12,8,12],kind='component')
        m.install('platform',dict(tool='scene_compile',arguments=dict(graph=graph)),[3,0,8],quarter_turns=1,mirror='x')
        policy = m.instances['platform']['compiled']['policy']
        self.assertEqual(policy['routes']['start'],[2.5,1,7.5])
        self.assertTrue(m.validate()['assembly']['passed'])
        p = policy['reserved_boxes'][0]['lo']
        with self.assertRaisesRegex(ValueError,'RESERVED'):
            m.patch([dict(pos=p,before=value_at(m.model,m.walls,tuple(p)),after=['minecraft:gold_block',False])])
        # An obstacle outside the reserved box can still invalidate the complete route.
        wall = [dict(pos=[x,y,6],before=value_at(m.model,m.walls,(x,y,6)),after=['minecraft:stone',False])
            for x in range(1,4) for y in range(1,4)]
        with self.assertRaisesRegex(ValueError,'ROUTE'):
            m.patch(wall)

    def test_scene_protection_preserves_unowned_host_geometry_and_old_records(self):
        from nbt_working_model import value_at
        graph = dict(schema_version=1,name='宿主保护',size=[6,4,3],
            objects=[dict(id='piece',lo=[0,0,0],recipe=solid([1,1,1]))],
            protected_boxes=[dict(lo=[3,1,1],hi=[3,1,1])])
        m = WorkingModel(self.root,[8,6,8],kind='component')
        m.patch([dict(pos=[3,1,1],before=['minecraft:air',False],after=['minecraft:gold_block',False])])
        m.install('piece',dict(tool='scene_compile',arguments=dict(graph=graph)),[0,0,0])
        m.instances['piece']['compiled'].pop('policy')
        m.instances['piece']['compiled'].pop('protected_values')
        first = m.save_draft('宿主保护')
        reopened = WorkingModel.open(self.root,first['source'])
        with self.assertRaisesRegex(ValueError,'保护'):
            reopened.patch([dict(pos=[3,1,1],before=value_at(reopened.model,reopened.walls,(3,1,1)),after=['minecraft:air',False])])


if __name__ == '__main__':
    unittest.main(verbosity=2)
