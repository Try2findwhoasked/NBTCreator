"""Object dependencies must affect real geometry and preserve saved revisions."""
import json,sys,tempfile,unittest,subprocess
from pathlib import Path
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_structure_agent import dispatch,build

def ref(name,measure,offset=0):return dict(object=name,measure=measure,offset=offset)
def structure(size,hi=None):
    return dict(tool='structure',arguments=dict(name='结构',size=size,operations=[dict(kind='box',label='实体',classification='body',lo=[0,0,0],hi=hi or [n-1 for n in size],state='stone_bricks')]))
def graph():
    span=dict(calc='subtract',args=[ref('right','max_x'),ref('left','min_x')],offset=1)
    last=dict(calc='subtract',args=[ref('right','max_x'),ref('left','min_x')])
    return dict(schema_version=1,name='联动柱梁与吊顶',size=[24,18,20],objects=[
        dict(id='floor',recipe=structure([24,1,20]),lo=[0,0,0]),
        dict(id='left',recipe=dict(tool='parametric_compile',arguments=dict(kind='pillar',size=[3,5,3],material='quartz_block')),lo=[5,1,8],contacts=['floor']),
        dict(id='right',recipe=dict(tool='parametric_compile',arguments=dict(kind='pillar',size=[3,ref('left','height'),3],material='quartz_block')),lo=[15,1,8],contacts=['floor']),
        dict(id='beam',recipe=structure([span,1,3],[last,0,2]),lo=[ref('left','min_x'),ref('left','max_y',1),ref('left','min_z')],contacts=['left','right']),
        dict(id='roof',recipe=structure([13,1,13]),attach=dict(target='beam',face='up')),
        dict(id='ceiling',recipe=dict(tool='pattern_microfit',arguments=dict(surface='ceiling',preset='four-petal',size_uv=[5,5])),attach=dict(target='roof',face='down',offset=[0,0,4])),
        dict(id='wall_ornament',recipe=dict(tool='pattern_microfit',arguments=dict(surface='wall',preset='horizontal-stripes',size_uv=[4,8],micro_alignment='fixed')),attach=dict(target='roof',face='south'))
    ],routes=dict(start=[2.5,1,2.5],targets=[[21.5,1,17.5]]))

class Scenes(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name)
    def call(self,tool,**args):return dispatch(self.root,tool,args)
    def save(self,g,parent=None):
        compiled=self.call('scene_compile',graph=g);args={k:compiled[k] for k in ('graph','graph_sha256','content_sha256')}
        if parent:args['parent']={k:parent[k] for k in ('id','revision','version')}
        return self.call('scene_save',**args)
    def change(self,saved,**kw):
        changes=[dict(id='left',recipe=dict(tool='parametric_compile',arguments=dict(kind='pillar',size=[3,7,3],material='quartz_block')))]
        return self.call('scene_update',**{k:saved[k] for k in ('id','revision','version')},changes=changes,**kw)

    def test_unordered_graph_compiles_with_real_contacts_and_no_files(self):
        g=graph();g['objects'].reverse();result=self.call('scene_compile',graph=g)
        self.assertLess(result['compile_order'].index('left'),result['compile_order'].index('right'))
        self.assertTrue(result['verification']['routes']['passed']);self.assertGreater(result['block_count'],480)
        self.assertEqual(build(self.root,result['spec'])['content_sha256'],result['content_sha256'])
        self.assertEqual(list(self.root.iterdir()),[])

    def test_persistent_edit_updates_dependents_and_preserves_both_snapshots(self):
        first=self.save(graph());original=Path(first['file']).read_bytes();old=self.call('scene_read',id=first['id'])
        next_candidate=self.change(first);old_nodes={n['id']:n for n in old['candidate']['objects']};new_nodes={n['id']:n for n in next_candidate['objects']}
        self.assertEqual(new_nodes['right']['bounds']['hi'][1],7)
        for key in ('beam','roof','ceiling','wall_ornament'):self.assertEqual(new_nodes[key]['bounds']['lo'][1],old_nodes[key]['bounds']['lo'][1]+2)
        self.assertEqual(next_candidate['affected_objects'],['beam','ceiling','left','right','roof','wall_ornament'])
        self.assertEqual(new_nodes['floor']['geometry_sha256'],old_nodes['floor']['geometry_sha256'])
        self.assertEqual(Path(first['file']).read_bytes(),original);self.assertEqual(self.call('scene_read',id=first['id'])['revision'],1)
        second=self.call('scene_save',**{k:next_candidate[k] for k in ('graph','graph_sha256','content_sha256','parent')})
        self.assertEqual(second['revision'],2);self.assertEqual(Path(first['file']).read_bytes(),original)
        self.assertEqual(self.call('scene_read',id=first['id'],version=first['version'])['revision'],1)
        self.assertFalse(second['nbt_exported']);self.assertFalse(second['model_modified'])
        with self.assertRaisesRegex(ValueError,'版本冲突'):self.change(first)
        with self.assertRaisesRegex(ValueError,'版本冲突'):self.call('scene_save',**{k:next_candidate[k] for k in ('graph','graph_sha256','content_sha256','parent')})

    def test_cycle_missing_reference_duplicate_id_and_code_are_rejected(self):
        for kind in ('cycle','missing','duplicate','code','bad_measure','bad_calc'):
            g=graph()
            if kind=='cycle':g['objects'][1]['lo'][0]=ref('right','min_x')
            elif kind=='missing':g['objects'][1]['contacts']=['absent']
            elif kind=='duplicate':g['objects'][1]['id']='floor'
            elif kind=='code':g['objects'][1]['recipe']['tool']='exec'
            elif kind=='bad_measure':g['objects'][1]['lo'][0]=ref('floor','__dict__')
            else:g['objects'][1]['lo'][0]=dict(calc='eval',args=[1,2])
            with self.subTest(kind=kind),self.assertRaises(ValueError):self.call('scene_compile',graph=g)
        self.assertEqual(list(self.root.iterdir()),[])

    def test_overlap_bounds_reserved_space_and_real_contact_are_enforced(self):
        for kind in ('overlap','outside','reserved','disconnected','invalid_box'):
            g=graph()
            if kind=='overlap':g['objects'][1]['lo']=[5,0,8]
            elif kind=='outside':g['objects'][1]['lo']=[25,1,8]
            elif kind=='reserved':g['reserved_boxes']=[dict(lo=[5,1,8],hi=[7,6,10])]
            elif kind=='disconnected':g['objects'][1]['lo'][1]=3
            else:g['reserved_boxes']=[dict(lo=[7,1,8],hi=[5,6,10])]
            with self.subTest(kind=kind),self.assertRaises(ValueError):self.call('scene_compile',graph=g)

    def test_update_and_save_cannot_bypass_original_protection_or_budget(self):
        g=graph();g['protected_boxes']=[dict(lo=[5,6,8],hi=[17,6,10])];first=self.save(g)
        with self.assertRaisesRegex(ValueError,'保护'):self.change(first)
        replacement=graph();replacement['objects'][1]['recipe']['arguments']['size'][1]=7
        replacement['protected_boxes']=g['protected_boxes'];compiled=self.call('scene_compile',graph=replacement)
        with self.assertRaisesRegex(ValueError,'保护'):self.call('scene_save',**{k:compiled[k] for k in ('graph','graph_sha256','content_sha256')},parent={k:first[k] for k in ('id','revision','version')})
        replacement.pop('protected_boxes');compiled=self.call('scene_compile',graph=replacement)
        with self.assertRaisesRegex(ValueError,'约束'):self.call('scene_save',**{k:compiled[k] for k in ('graph','graph_sha256','content_sha256')},parent={k:first[k] for k in ('id','revision','version')})
        other=self.save(graph())
        with self.assertRaisesRegex(ValueError,'预算'):self.change(other,max_changed_blocks=1)

    def test_route_failure_after_edit_is_not_saved(self):
        g=dict(schema_version=1,name='路口',size=[8,6,5],objects=[dict(id='floor',recipe=structure([8,1,5]),lo=[0,0,0]),dict(id='bar',recipe=structure([1,1,5]),lo=[4,5,0])],routes=dict(start=[1.5,1,2.5],targets=[[6.5,1,2.5]]))
        first=self.save(g)
        with self.assertRaisesRegex(ValueError,'通路'):self.call('scene_update',**{k:first[k] for k in ('id','revision','version')},changes=[dict(id='bar',lo=[4,1,0])])
        self.assertEqual(self.call('scene_read',id=first['id'])['revision'],1)

    def test_changed_file_and_forged_candidate_hash_are_rejected(self):
        candidate=self.call('scene_compile',graph=graph())
        with self.assertRaisesRegex(ValueError,'已变化'):self.call('scene_save',graph=candidate['graph'],graph_sha256='0'*64,content_sha256=candidate['content_sha256'])
        first=self.save(graph());Path(first['file']).write_bytes(b'{}')
        with self.assertRaisesRegex(ValueError,'哈希'):self.call('scene_read',id=first['id'])

    def test_side_attachment_finds_recess_and_rotates_stairs_automatically(self):
        g=dict(schema_version=1,name='凹柱贴饰',size=[12,12,12],objects=[dict(id='post',recipe=dict(tool='parametric_compile',arguments=dict(kind='pillar',size=[3,8,3])),lo=[5,0,5]),
          dict(id='trim',recipe=dict(tool='pattern_microfit',arguments=dict(surface='wall',size_uv=[2,2],preset='four-petal')),attach=dict(target='post',face='north'))])
        # Use an exact 2x2 square ring rather than asking four petals to fit it.
        from PIL import Image,ImageDraw
        from nbt_selection_edit import sha
        image=Image.new('L',(16,16));ImageDraw.Draw(image).rectangle([0,0,15,15],outline=255,width=2);file=self.root/'ring.png';image.save(file)
        g['objects'][1]['recipe']['arguments'].pop('preset');g['objects'][1]['recipe']['arguments']['sample']=dict(path=file.name,sha256=sha(file),noise_strength=0)
        result=self.call('scene_compile',graph=g);trim=next(n for n in result['objects'] if n['id']=='trim')
        self.assertEqual(trim['quarter_turns'],2);self.assertEqual(trim['contact_targets'],['post']);self.assertGreaterEqual(trim['surface_inset'],1)
        g['objects'][1]['attach']['max_inset']=0
        with self.assertRaisesRegex(ValueError,'真实表面'):self.call('scene_compile',graph=g)

    def test_actual_cli_and_persistent_transport_share_the_contract(self):
        file=self.root/'request.json';file.write_text(json.dumps(dict(graph=graph())),encoding='utf8')
        process=subprocess.run([sys.executable,'-B',str(ROOT/'.agents/skills/minecraft-nbt-modeler/scripts/nbt_components.py'),'--workspace',str(self.root),'agent','--tool','scene_compile','--request',str(file)],capture_output=True,check=True)
        expected=json.loads(process.stdout)['result']
        line=dict(id='scene-1',method='agent',params=dict(tool='scene_compile',arguments=dict(graph=graph())))
        session=subprocess.run([sys.executable,'-B',str(ROOT/'.agents/skills/minecraft-nbt-modeler/scripts/nbt_engine_session.py'),'--workspace',str(self.root)],input=(json.dumps(line)+'\n').encode(),capture_output=True,check=True)
        self.assertEqual(json.loads(session.stdout)['result'],expected)

    def test_concurrent_saves_keep_one_new_head_and_reject_the_stale_writer(self):
        first=self.save(graph());candidate=self.change(first)
        file=self.root/'save.json';file.write_text(json.dumps({k:candidate[k] for k in ('graph','graph_sha256','content_sha256','parent')}),encoding='utf8')
        command=[sys.executable,'-B',str(ROOT/'.agents/skills/minecraft-nbt-modeler/scripts/nbt_components.py'),'--workspace',str(self.root),'agent','--tool','scene_save','--request',str(file)]
        children=[subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE) for _ in range(2)]
        results=[json.loads(child.communicate(timeout=30)[0]) for child in children]
        self.assertEqual(sorted(r['ok'] for r in results),[False,True]);self.assertEqual(self.call('scene_read',id=first['id'])['revision'],2)
        self.assertIn('版本冲突',next(r['error'] for r in results if not r['ok']))

    def test_frozen_workspace_can_save_while_source_directory_remains_forbidden(self):
        from nbt_exposure import apply
        from nbt_composition.object_scene import scene_root
        apply(self.root,dict(schema_version=1,enabled_groups=['modelling']))
        facade=self.root/'.agents/skills/nbtcreator-workspace/nbt.py';file=self.root/'request.json'
        def invoke(tool,args):
            file.write_text(json.dumps(args),encoding='utf8')
            process=subprocess.run([sys.executable,'-B',str(facade),'components','agent','--tool',tool,'--request',str(file)],cwd=self.root,capture_output=True,check=True)
            return json.loads(process.stdout)['result']
        candidate=invoke('scene_compile',dict(graph=graph()))
        saved=invoke('scene_save',{k:candidate[k] for k in ('graph','graph_sha256','content_sha256')})
        self.assertTrue(Path(saved['file']).is_relative_to(self.root.resolve()));self.assertEqual(invoke('scene_read',dict(id=saved['id']))['revision'],1)
        with self.assertRaisesRegex(ValueError,'软件源码'):scene_root(ROOT,'0'*32)
        query=subprocess.run([sys.executable,'-B',str(ROOT/'.agents/skills/minecraft-nbt-modeler/scripts/nbt_capabilities.py'),'--agent-tool','scene_compile'],capture_output=True,check=True)
        scoped=json.loads(query.stdout);self.assertEqual(list(scoped['agent_tools']),['scene_compile']);self.assertTrue(scoped['session_available'])
        self.assertEqual(scoped['agent_tools']['scene_compile']['parameters']['properties']['graph']['properties']['objects']['maxItems'],32)

if __name__=='__main__':unittest.main(verbosity=2)
