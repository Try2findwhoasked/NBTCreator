"""Architectural recipes must preserve physical openings, relief and linkage."""
import copy,json,sys,tempfile,unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_structure_agent import dispatch,build
from nbt_collision import collision_cells
from nbt_engine_session import serve
from nbt_pattern_assets import load


def components(points):
    remaining=set(points);count=0
    while remaining:
        count+=1;pending=[remaining.pop()]
        while pending:
            x,y,z=pending.pop()
            for q in ((x-1,y,z),(x+1,y,z),(x,y-1,z),(x,y+1,z),(x,y,z-1),(x,y,z+1)):
                if q in remaining:remaining.remove(q);pending.append(q)
    return count


class ArchitecturalBay(unittest.TestCase):
    def setUp(self):
        directory=tempfile.TemporaryDirectory();self.addCleanup(directory.cleanup);self.root=Path(directory.name)
    def call(self,tool,**args):return dispatch(self.root,tool,args)
    def voxels(self,result):
        data=build(self.root,result['spec'])
        return {tuple(v[:3]):data['palette'][v[3]] for v in data['blocks']}
    def solid(self,voxels):
        cells=set()
        for p,value in voxels.items():
            occupied,reason=collision_cells(value);self.assertIsNone(reason)
            cells.update(tuple(2*p[i]+c[i] for i in range(3)) for c in occupied)
        return cells
    def vault(self,**patches):return dict(size_xz=[22,22],spring_y=14,rise=12,**patches)
    def graph(self,args,**extra):
        return dict(schema_version=1,name='联动单跨',size=[48,48,48],objects=[dict(id='bay',lo=[0,0,0],recipe=dict(tool='bay_compile',arguments=args))],**extra)

    def test_facade_openings_are_recessed_and_remain_open_without_glass(self):
        args = dict(bays=2, storeys=2, opening=[3, 4], recess=2)
        unglazed = self.call('facade_compile', **args, glazing=False)
        glazed = self.call('facade_compile', **args)
        a, b = self.voxels(unglazed), self.voxels(glazed)
        self.assertEqual(len(unglazed['openings']), 4)
        for opening in unglazed['openings']:
            x, y, _ = opening['lo']
            self.assertTrue(all((x, y, z) not in a for z in range(4)))
            self.assertNotIn((x, y, 0), b)
            self.assertNotIn((x, y, 1), b)
            self.assertIn('glass', b[x, y, 2])
            self.assertIn('slab', b[x, y - 1, 0])
        self.assertEqual(components(self.solid(a)), 1)
        larger = self.call('facade_compile', **dict(args, bays=3))
        self.assertGreater(larger['spec']['size'][0], unglazed['spec']['size'][0])
        self.assertEqual(larger['spec']['size'][1:], unglazed['spec']['size'][1:])

    def test_facade_recipe_uses_the_shared_scene_and_working_model_entry(self):
        from nbt_working_model import WorkingModel
        recipe = dict(tool='facade_compile', arguments=dict(bays=2, storeys=1))
        graph = dict(schema_version=1, name='窗墙试件', size=[32, 16, 8],
                     objects=[dict(id='front', lo=[0, 0, 0], recipe=recipe)])
        candidate = self.call('scene_compile', graph=graph)
        self.assertGreater(candidate['block_count'], 0)
        model = WorkingModel(self.root, [32, 16, 8], context=dict(mode='standalone', openings=[]))
        model.install('facade', recipe, position=[6, 0, 0])
        self.assertGreater(model.inspect('facade')['block_count'], 0)
        with self.assertRaises(ValueError):
            self.call('facade_compile', bays=8, opening=[12, 12])
        with self.assertRaises(ValueError):
            self.call('facade_compile', sill_material='stone')

    def test_real_open_tracery_and_glazing_do_not_create_opaque_backing(self):
        for profile in ('round','pointed'):
            for depth in (1,3):
                a=self.call('tracery_compile',size_uv=[19,27],depth=depth,profile=profile,glazing=False)
                b=self.call('tracery_compile',size_uv=[19,27],depth=depth,profile=profile,glazing=True)
                stone=self.voxels(a);glazed=self.voxels(b)
                self.assertGreater(a['tracery']['open_cells'],150)
                self.assertEqual({p:v for p,v in glazed.items() if 'glass' not in v},stone)
                self.assertTrue(all('glass' in v for p,v in glazed.items() if p not in stone))
                self.assertEqual(b['tracery']['open_cells'],0)
                self.assertEqual(components(self.solid(stone)),1)
                self.assertEqual(components(self.solid(glazed)),1)
        self.assertEqual(list(self.root.iterdir()),[])

    def test_vault_recess_changes_the_physical_underside_and_retains_half_steps(self):
        plain=self.call('vault_compile',**self.vault(recess_depth=1,ribs=False))
        deep=self.call('vault_compile',**self.vault(recess_depth=3,ribs=False))
        a=self.solid(self.voxels(plain));b=self.solid(self.voxels(deep))
        def underside(pts):
            result={}
            for x,y,z in pts:result[x,z]=min(y,result.get((x,z),y))
            return result
        # Read occupied half-cubes, not the compiler's claimed depth receipt.
        aa=underside(a);bb=underside(b)
        self.assertTrue(any(bb[p]>aa[p] for p in aa))
        self.assertTrue(any(y%2 for y in bb.values()))
        self.assertEqual(components(b),1)

    def test_bay_resize_drives_all_major_components_and_real_contacts(self):
        small=self.call('bay_compile',span=20,depth=20)
        large=self.call('bay_compile',span=26,depth=24,spring_height=14,rise=14)
        for name in ('vault','window','floor_inlay','front_arch','back_arch','right_arch'):
            self.assertNotEqual(small['parts'][name],large['parts'][name],name)
        self.assertNotEqual(small['resolved_form']['window_size'],large['resolved_form']['window_size'])
        for result in (small,large):
            self.assertEqual(components(self.solid(self.voxels(result))),1)
            self.assertTrue(all(v['face_contact'] for v in result['construction_graph']['joints']))
        self.assertEqual(list(self.root.iterdir()),[])

    def test_round_profile_is_inherited_by_window_and_vault(self):
        pointed=self.call('bay_compile',profile='pointed')
        rounded=self.call('bay_compile',profile='round')
        self.assertNotEqual(pointed['content_sha256'],rounded['content_sha256'])
        for key in ('vault','window'):self.assertEqual(rounded['recipes'][key]['profile'],'round')
        self.assertEqual(components(self.solid(self.voxels(rounded))),1)

    def test_scene_update_recompiles_bay_but_preserves_saved_revision(self):
        first=self.call('scene_compile',graph=self.graph(dict(span=20,depth=20)))
        saved=self.call('scene_save',**{k:first[k] for k in ('graph','graph_sha256','content_sha256')})
        original=Path(saved['file']).read_bytes()
        changed=self.call('scene_update',**{k:saved[k] for k in ('id','revision','version')},changes=[dict(id='bay',recipe=dict(tool='bay_compile',arguments=dict(span=26,depth=24)))])
        self.assertEqual(changed['affected_objects'],['bay'])
        self.assertNotEqual(changed['content_sha256'],first['content_sha256'])
        self.assertEqual(Path(saved['file']).read_bytes(),original)
        self.assertEqual(self.call('scene_read',id=saved['id'])['revision'],1)

    def test_named_pattern_binding_changes_only_the_flat_floor(self):
        source=load(self.root,'builtin:byzantine-cross-mosaic')
        source2=load(self.root,'builtin:ottoman-eight-point-star')
        source=self.call('pattern_assets',action='copy',id=source['id'],image_sha256=source['image_sha256'],name='拜占庭地砖')
        source2=self.call('pattern_assets',action='copy',id=source2['id'],image_sha256=source2['image_sha256'],name='八角地砖')
        g=self.graph(dict(floor_pattern=dict(pattern_ref='floor')),patterns=[dict(id='floor',asset=dict(id=source['id'],image_sha256=source['image_sha256']))])
        a=self.call('scene_compile',graph=g)
        g['patterns'][0]['asset']=dict(id=source2['id'],image_sha256=source2['image_sha256'])
        b=self.call('scene_compile',graph=g)
        aa=self.voxels(a);bb=self.voxels(b)
        changes={p for p in aa.keys()|bb.keys() if aa.get(p)!=bb.get(p)}
        self.assertGreater(len(changes),20);self.assertEqual({p[1] for p in changes},{1})

    def test_source_changed_during_compile_is_rejected(self):
        asset=self.call('pattern_create',name='试件',resolution=[16,16],layers=[dict(kind='preset',preset='four-petal')])
        # A local author asset can change while geometry is being constructed.
        # The final receipt must verify the original binding again.
        bound=load(self.root,asset['id']);image=Path(bound['image'])
        import nbt_architectural_bay
        original=nbt_architectural_bay.Writer.put;mutated=[]
        def put(writer,*args,**kw):
            if not mutated:image.write_bytes(b'changed while compiling');mutated.append(True)
            return original(writer,*args,**kw)
        with patch.object(nbt_architectural_bay.Writer,'put',new=put):
            with self.assertRaises(ValueError):
                self.call('vault_compile',**self.vault(coffer_pattern=dict(pattern_asset=dict(id=bound['id'],image_sha256=bound['image_sha256']))))
        self.assertEqual(mutated,[True])

    def test_invalid_inputs_and_budget_reject_without_writing_candidates(self):
        for tool,args in [('bay_compile',dict(max_changed_blocks=10)),('bay_compile',dict(profile='invalid')),
            ('bay_compile',dict(span=float('nan'))),('bay_compile',dict(script='anything')),
            ('tracery_compile',dict(size_uv=[11,11])),('tracery_compile',dict(size_uv=[19,27],glass_palette=['stone'])),
            ('vault_compile',self.vault(slab_material='smooth_quartz_slab[type=bottom]')),
            ('vault_compile',self.vault(coffer_counts=[8,8]))]:
            with self.subTest(tool=tool,args=args),self.assertRaises(ValueError):self.call(tool,**args)
        self.assertEqual(list(self.root.iterdir()),[])

    def test_three_public_tools_work_through_json_lines_session_deterministically(self):
        requests=[('tracery_compile',dict(size_uv=[19,27])),('vault_compile',self.vault()),('bay_compile',{})]
        data=[dict(id=str(i),method='agent',params=dict(tool=tool,arguments=args)) for i,(tool,args) in enumerate(requests)]
        output=BytesIO();serve(self.root,BytesIO(('\n'.join(json.dumps(v) for v in data)+'\n').encode()),output)
        replies=[json.loads(v) for v in output.getvalue().splitlines()]
        self.assertTrue(all(v['ok'] for v in replies),replies)
        for reply,(tool,args) in zip(replies,requests):self.assertEqual(reply['result'],self.call(tool,**args))
        self.assertEqual(list(self.root.iterdir()),[])


if __name__=='__main__':unittest.main()
