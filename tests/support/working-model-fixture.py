"""Synthetic managed assembly for real shared-renderer regression only."""
import json
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_working_model import WorkingModel, verify_version
from nbt_assembly import Volume
from nbt_refine import save_master
from nbt_large_assembly import AssemblyVolume, save_assembly
from nbt_reference_views import register_reference
from nbt_review.reference_camera import prepare_cameras
from nbt_snbt import save_snbt
from PIL import Image
import hashlib


def main():
    workspace, output = map(Path, sys.argv[1:3])
    assembly = runpy.run_path(str(ROOT / 'tests/engine/scene-interfaces.py'))['assembly']
    model = WorkingModel(workspace, [48, 20, 30], kind='component')
    model.apply_operations([dict(kind='box', label='合成测试地面', classification='body', lo=[0,0,0], hi=[47,0,29], state='smooth_sandstone')])
    model.install('portal', dict(tool='scene_compile', arguments=dict(graph=assembly())), [10,1,8])
    cameras = [dict(id='assembly', role='合成组合前后同机位', eye=[40,19,-15], target=[20,4,14], fov=48)]
    before = model.preview(output / 'before', cameras)
    first = model.save_draft('合成组合渲染回归')
    model.update('portal', dict(tool='scene_compile', arguments=dict(graph=assembly(7))))
    after = model.preview(output / 'after', cameras)
    second = model.save_draft()
    assert verify_version(Path(first['output']))['revision'] != verify_version(Path(second['output']))['revision']
    assert model.validate()['assembly']['passed']
    sky_cameras = output / 'sky-cameras.json'
    sky_cameras.write_text(json.dumps([dict(id='sky', role='背景回归', eye=[12,10,-14], target=[2,2,2], fov=48)]), encoding='utf8')
    ortho_cameras = output / 'orthographic-cameras.json'
    ortho_cameras.write_text(json.dumps([
        dict(id='near',role='正交近距',eye=[2.5,2.5,-10],target=[2.5,2.5,2.5],up=[0,1,0],projection='orthographic',ortho_height=8),
        dict(id='far',role='正交远距',eye=[2.5,2.5,-30],target=[2.5,2.5,2.5],up=[0,1,0],projection='orthographic',ortho_height=8),
        dict(id='perspective',role='透视切换',eye=[2.5,2.5,-10],target=[2.5,2.5,2.5],up=[0,1,0]),
        dict(id='near-again',role='正交返回',eye=[2.5,2.5,-10],target=[2.5,2.5,2.5],up=[0,1,0],projection='orthographic',ortho_height=8),
        dict(id='warm',role='暖光',eye=[2.5,2.5,-10],target=[2.5,2.5,2.5],up=[0,1,0],projection='orthographic',ortho_height=8,
             lighting_options=dict(direction=[.3,.8,-.8],temperature_kelvin=2800,background=[.15,.2,.25],exposure=1)),
        dict(id='temp-only',role='同背景冷色温',eye=[2.5,2.5,-10],target=[2.5,2.5,2.5],up=[0,1,0],projection='orthographic',ortho_height=8,
             lighting_options=dict(direction=[.3,.8,-.8],temperature_kelvin=8000,background=[.15,.2,.25],exposure=1)),
        dict(id='cool',role='冷光',eye=[2.5,2.5,-10],target=[2.5,2.5,2.5],up=[0,1,0],projection='orthographic',ortho_height=8,
             lighting_options=dict(direction=[-.3,.8,.2],temperature_kelvin=8000,background=[.6,.5,.4],exposure=1.4))
    ]), encoding='utf8')
    sky_sources = {}
    for label in ('empty', 'block'):
        volume = Volume((5,5,5))
        if label == 'block': volume.put((2,2,2), 'stone_bricks')
        source = output / f'sky-{label}.master.json.gz'
        save_master(source, volume, set())
        sky_sources[label] = str(source)
    large = AssemblyVolume((300, 384, 300))
    large.put((2, 2, 2), 'stone_bricks')
    for x in range(296, 300):
        for z in range(296, 300):
            large.put((x, 295, z), 'gold_block')
    assembled = save_assembly(output / 'large-assembly', large, {(2, 2, 2)},
                              [dict(offset=[0, 0, 0], size=[6, 6, 6]),
                               dict(offset=[294, 294, 294], size=[6, 90, 6])])
    large_cameras = output / 'large-cameras.json'
    large_cameras.write_text(json.dumps([dict(id='large', role='跨分区渲染回归', eye=[308,303,285], target=[298,295,298], fov=48)]), encoding='utf8')
    ref_dir=workspace/'reference-input';ref_dir.mkdir()
    views={}
    for name,u,v in [('front','x','-y'),('side','z','-y'),('top','x','z')]:
        file=ref_dir/(name+'.png');Image.new('RGB',(128,128),'white').save(file)
        views[name]=dict(image=file.relative_to(workspace).as_posix(),sha256=hashlib.sha256(file.read_bytes()).hexdigest(),
            origin=[24,24] if name=='top' else [24,104],pixels_per_block=16,u_axis=u,v_axis=v,origin_type='original',basis='合成参考')
    anchor=dict(id='anchor',part='fixture',world=[2,2,2],basis='合成方块',confidence='measured',uncertainty=0,
                views=dict(front=[56,72],side=[56,72],top=[56,56]))
    reference=register_reference(workspace,dict(output='nbt_models/_workspaces/reference-views/render',views=views,anchors=[anchor],assumptions=[]))
    reference_sources={}
    for label in ('empty','block'):
        source=workspace/('reference-'+label+'.snbt');volume=Volume((8,8,8))
        if label=='block':volume.put((2,2,2),'stone')
        receipt=save_snbt(source,volume,set());reference_sources[label]=receipt
    registered=prepare_cameras(workspace,dict(source=reference_sources['block']['source'],source_sha256=reference_sources['block']['source_sha256'],
        reference=reference['manifest'],reference_sha256=reference['manifest_sha256'],output='nbt_models/_workspaces/reference-cameras/render',
        lighting_options=dict(direction=[.3,.8,.2],temperature_kelvin=4200,background=[.2,.3,.4],exposure=1.1)))
    (output / 'fixture.json').write_text(json.dumps(dict(before=before, after=after, first=first, second=second, sky_cameras=str(sky_cameras), sky_sources=sky_sources, ortho_cameras=str(ortho_cameras), large=assembled, large_cameras=str(large_cameras),registered=registered,reference_sources=reference_sources)), encoding='utf8')


if __name__ == '__main__':
    main()
