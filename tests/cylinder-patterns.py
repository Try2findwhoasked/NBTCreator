"""Regressions for cyclic geometry, automatic states and bound source fitting."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
SCRIPTS=ROOT/'.agents/skills/minecraft-nbt-modeler/scripts'
sys.path.insert(0,str(SCRIPTS))
from nbt_assembly import Volume
from nbt_collision import collision_cells
from nbt_components import load,placement
from nbt_cylinder_pattern import cylinder_geometry,touches_backing
from nbt_refine import save_master
from nbt_registry import effective
from nbt_selection_edit import sha
from nbt_structure_agent import dispatch,build
from nbt_tools import transformed_state


class CylinderPatterns(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)

    def sample(self,diameter,height,masks):
        _,ring=cylinder_geometry(diameter)
        image=Image.new('L',(2*len(ring),2*height))
        for u in range(len(ring)):
            for y in range(height):
                mask=masks(u,y)
                for a,b in ((0,0),(1,0),(0,1),(1,1)):
                    image.putpixel((2*u+a,2*height-1-(2*y+b)),255*mask[a+2*b])
        file=self.root/'sample.png';image.save(file)
        return dict(path=file.name,sha256=sha(file),noise_strength=0)

    def proposal(self,diameter=9,height=8,masks=None):
        variants=((1,1,1,0),(1,1,0,1),(1,0,1,1),(0,1,1,1))
        return dict(surface='cylinder',size_uv=[diameter,height],
                    sample=self.sample(diameter,height,masks or (lambda u,y:variants[(u+y)%4])),
                    shapes=dict(stairs='quartz_stairs',slab='quartz_slab'))

    def fixture(self,proposal):
        compiled=dispatch(self.root,'pattern_compile',proposal)
        core,_=cylinder_geometry(proposal['size_uv'][0]);height=proposal['size_uv'][1]
        model=Volume((32,20,32));lo=[8,2,8]
        for x,z in core:
            for y in range(height):model.put((lo[0]+x,lo[1]+y,lo[2]+z),'stone_bricks')
        source=self.root/'master.snbt';save_master(source,model,set(model.blocks))
        context=self.root/'coordinates.json';context.write_text(json.dumps(dict(mode='standalone',openings=[])))
        target=dict(source=source.name,source_sha256=sha(source),geometry_sha256=model.fingerprint(),
                    context=context.name,context_sha256=sha(context),lo=lo,
                    hi=[lo[i]+compiled['spec']['size'][i]-1 for i in range(3)])
        return model,target

    def test_geometry_has_no_duplicate_or_unsupported_shell_and_closed_index(self):
        for diameter in (4,5,12,13,30):
            for seam in (-180,-90,0,90,180):
                with self.subTest(diameter=diameter,seam=seam):
                    core,ring=cylinder_geometry(diameter,seam)
                    points={(f['x'],f['z']) for f in ring}
                    self.assertEqual(len(points),len(ring));self.assertFalse(points&core)
                    normals={name:sum(f['normal']==name for f in ring) for name in ('north','east','south','west')}
                    self.assertEqual(len(set(normals.values())),1)
                    self.assertEqual([f['angle'] for f in ring],sorted(f['angle'] for f in ring))
                    for i,face in enumerate(ring):
                        self.assertIn((face['x']-face['dx'],face['z']-face['dz']),core)
                        previous=ring[i-1]
                        self.assertLessEqual(abs(face['x']-previous['x'])+abs(face['z']-previous['z']),2)
                        self.assertTrue(0<=face['x']<diameter+2 and 0<=face['z']<diameter+2)

    def test_contour_inference_rotates_stairs_and_selects_slab_halves(self):
        diameter,height=12,6
        variants=((1,1,1,0),(1,1,0,1),(1,0,1,1),(0,1,1,1))
        args=self.proposal(diameter,height)
        result=dispatch(self.root,'pattern_compile',args);data=build(self.root,result['spec'])
        core,ring=cylinder_geometry(diameter);by_point={tuple(b[:3]):data['palette'][b[3]] for b in data['blocks']}
        self.assertTrue(all(wall==((x,z) not in core) for x,y,z,index,wall in data['blocks']))
        self.assertEqual(result['shape_counts'],dict(stairs=len(ring)*height))
        self.assertEqual(result['fitting']['missing']+result['fitting']['extra'],0)
        self.assertEqual({key.split('/')[0] for key in result['stair_orientations']},{'north','south','east','west'})
        for u,face in enumerate(ring):
            for y in range(height):
                value=by_point[face['x'],y,face['z']]
                self.assertTrue(touches_backing(value,face))
                local=transformed_state(value,(-face['turns'])%4,None)
                projected={(x,y) for x,y,z in collision_cells(local)[0]}
                self.assertEqual(tuple(int(p in projected) for p in ((0,0),(1,0),(0,1),(1,1))),variants[(u+y)%4])
        # The material input's example state does not dictate a world facing.
        other=dict(args,shapes=dict(stairs='quartz_stairs[facing=north,half=top]',slab='quartz_slab[type=top]'))
        self.assertEqual(result['content_sha256'],dispatch(self.root,'pattern_compile',other)['content_sha256'])
        halves=((1,1,0,0),(0,0,1,1))
        slab_args=self.proposal(diameter,height,lambda u,y:halves[y%2])
        slabs=dispatch(self.root,'pattern_compile',slab_args)
        self.assertEqual(slabs['shape_counts'],dict(slab=len(ring)*height))
        self.assertEqual(slabs['slab_orientations'],dict(bottom=len(ring)*height//2,top=len(ring)*height//2))

    def test_preview_save_and_placement_preserve_support_after_rotation_and_mirror(self):
        args=self.proposal()
        preview=dispatch(self.root,'pattern_preview',args)
        self.assertTrue(Path(preview['thumbnail']).is_file())
        saved=dispatch(self.root,'structure_save',{k:preview[k] for k in ('preview_id','preview_sha256')})
        data=load(self.root,saved['id'])
        for turns in range(4):
            for mirror in (None,'x','z'):
                placed=placement(data,[20,1,20],[48,20,48],turns,mirror)
                cells={}
                for op in placed['operations']:
                    for x,y,z,index in op['voxels']:
                        point=tuple(op['lo'][i]+(x,y,z)[i] for i in range(3))
                        cells[point]=op['palette'][index]
                for (x,y,z),value in cells.items():
                    if not effective(value)[0].endswith('_stairs'):continue
                    occupied=collision_cells(value)[0]
                    supported=False
                    for dx,dz in ((1,0),(-1,0),(0,1),(0,-1)):
                        neighbor=cells.get((x+dx,y,z+dz))
                        if neighbor and effective(neighbor)[0]=='minecraft:stone_bricks':
                            axis=0 if dx else 2;side=1 if dx+dz>0 else 0
                            supported|=any(p[axis]==side for p in occupied)
                    self.assertTrue(supported)

    def test_existing_column_mount_writes_only_outer_shell_and_refuses_conflicts(self):
        obj=self.proposal();model,target=self.fixture(obj)
        args=dict(target=target,object=obj)
        result=dispatch(self.root,'pattern_cylinder_mount',args)
        core,ring=cylinder_geometry(obj['size_uv'][0])
        self.assertEqual(result['changed_blocks'],len(ring)*obj['size_uv'][1])
        self.assertFalse(result['model_modified']);self.assertFalse(result['approval_created'])
        self.assertTrue(result['verification']['mount_contact'])
        self.assertEqual(sha(self.root/target['source']),target['source_sha256'])
        op=result['operations'][0]
        self.assertFalse(op['overwrite'])
        self.assertTrue(all((x,z) not in core for x,y,z,index in op['voxels']))
        x,y,z,index=op['voxels'][0];point=[target['lo'][0]+x,target['lo'][1]+y,target['lo'][2]+z]
        with self.assertRaisesRegex(ValueError,'预算'):
            dispatch(self.root,'pattern_cylinder_mount',dict(args,max_changed_blocks=1))
        with self.assertRaisesRegex(ValueError,'留白'):
            dispatch(self.root,'pattern_cylinder_mount',dict(args,reserved_boxes=[dict(lo=point,hi=point)]))
        with self.assertRaisesRegex(ValueError,'起点和目标'):
            dispatch(self.root,'pattern_cylinder_mount',dict(args,require_routes=True))
        context=self.root/target['context']
        context.write_text(json.dumps(dict(mode='standalone',openings=[],protected_boxes=[dict(lo=point,hi=point)])))
        with self.assertRaisesRegex(ValueError,'上下文'):
            dispatch(self.root,'pattern_cylinder_mount',args)
        changed=dict(target,context_sha256=sha(context))
        with self.assertRaisesRegex(ValueError,'保护'):
            dispatch(self.root,'pattern_cylinder_mount',dict(args,target=changed))
        context.write_text(json.dumps(dict(mode='standalone',openings=[])))
        changed=dict(target,context_sha256=sha(context))
        model.put(point,'stone');save_master(self.root/target['source'],model,set(model.blocks))
        changed.update(source_sha256=sha(self.root/target['source']),geometry_sha256=model.fingerprint())
        with self.assertRaisesRegex(ValueError,'已有方块'):
            dispatch(self.root,'pattern_cylinder_mount',dict(args,target=changed))
        model.put(point,'air')
        core_point=next(iter(core));model.put((target['lo'][0]+core_point[0],target['lo'][1],target['lo'][2]+core_point[1]),'air')
        save_master(self.root/target['source'],model,set())
        changed.update(source_sha256=sha(self.root/target['source']),geometry_sha256=model.fingerprint())
        with self.assertRaisesRegex(ValueError,'柱芯不完整'):
            dispatch(self.root,'pattern_cylinder_mount',dict(args,target=changed))

    def test_facade_and_catalog_expose_cylinder_without_electron(self):
        from nbt_exposure import apply
        args=dict(surface='cylinder',preset='braided-shaft',size_uv=[13,24],repeat=[4,1],
                  shapes=dict(stairs='quartz_stairs',slab='quartz_slab'))
        expected=dispatch(self.root,'pattern_compile',args)
        apply(self.root)
        file=self.root/'request.json';file.write_text(json.dumps(args))
        run=subprocess.run([sys.executable,str(self.root/'.agents/skills/nbtcreator-workspace/nbt.py'),
            'components','agent','--tool','pattern_compile','--request',str(file)],cwd=self.root,capture_output=True,text=True,encoding='utf8')
        self.assertEqual(run.returncode,0,(run.stdout+run.stderr)[-2000:])
        result=json.loads(run.stdout)['result']
        self.assertEqual(result['content_sha256'],expected['content_sha256'])
        for patch in (dict(size_uv=[3,8]),dict(size_uv=[31,8]),dict(max_changed_blocks=1),dict(shapes={})):
            with self.assertRaises(ValueError):dispatch(self.root,'pattern_compile',dict(args,**patch))
        with self.assertRaisesRegex(ValueError,'仅适用'):
            dispatch(self.root,'pattern_compile',dict(surface='wall',preset='braided-shaft',size_uv=[13,24],seam_degrees=0))

    def test_mount_binds_snapshot_and_emits_same_camera_before_after_review(self):
        from nbt_task import write_snapshot
        obj=self.proposal();_,target=self.fixture(obj)
        cameras=[dict(id='column',eye=[28,14,28],target=[13,6,13])]
        camera_file=self.root/'cameras.json';camera_file.write_text(json.dumps(cameras))
        snapshot=self.root/'snapshot.json'
        write_snapshot(self.root/target['source'],snapshot,cameras=cameras)
        target.update(snapshot=snapshot.name,snapshot_sha256=sha(snapshot))
        args=dict(target=target,object=obj,review=dict(cameras=camera_file.name))
        result=dispatch(self.root,'pattern_cylinder_mount',args)
        self.assertEqual(result['review']['status'],'complete')
        after=result['review']['sides']['after']
        self.assertEqual(after['geometry_sha256'],result['candidate_geometry_sha256'])
        before=result['review']['sides']['before']
        self.assertEqual(before['geometry_sha256'],target['geometry_sha256'])
        for side in (before,after):
            actual=json.loads(Path(side['snapshot']).read_text(encoding='utf8'))
            self.assertEqual(actual['cameras'],cameras)
        snapshot.write_bytes(snapshot.read_bytes()+b' ')
        with self.assertRaisesRegex(ValueError,'快照已变化'):
            dispatch(self.root,'pattern_cylinder_mount',args)


if __name__=='__main__':unittest.main(verbosity=2)
