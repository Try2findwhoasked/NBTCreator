"""Compile reusable grayscale masks into supported, oriented architectural panels."""
import json
from pathlib import Path

from nbt_model import state
from nbt_collision import collision_cells
from nbt_registry import effective
from nbt_ornament_sample import fit_sample, silhouette_options, match_silhouette

LIBRARY = Path(__file__).resolve().parents[1] / 'assets/ornament-patterns'


def library():
    return json.loads((LIBRARY / 'manifest.json').read_text(encoding='utf8'))


def sample_input(workspace, args):
    if 'pattern_ref' in args:raise ValueError('pattern_ref 须由对象图 patterns 绑定解析')
    if sum(key in args for key in ('preset','sample','pattern_asset'))!=1:
        raise ValueError('preset、sample 和 pattern_asset 必须选择一种来源')
    if 'preset_options' in args and 'preset' not in args:
        raise ValueError('preset_options 仅用于图库预设；自定义样本请在 sample 中设置')
    if 'asset_options' in args and 'pattern_asset' not in args:raise ValueError('asset_options 仅用于纹样资产')
    if 'pattern_asset' in args:
        from nbt_pattern_assets import load
        reference=args['pattern_asset'];asset=load(workspace,reference['id'])
        if asset['image_sha256']!=reference['image_sha256']:raise ValueError('纹样资产图像已变化，请重新读取绑定')
        if asset['builtin']:raise ValueError('内置纹样请使用preset或先复制为工作区资产')
        return workspace,dict(asset['fitting_input']['sample'],**args.get('asset_options',{}))
    if 'preset' in args:
        preset = library()[args['preset']]
        cyclic_micro=(args['surface']=='cylinder' and args.get('fit_mode')=='micro' and 'column' in preset['surfaces'])
        if args['surface'] not in preset['surfaces'] and not cyclic_micro:
            raise ValueError('该纹样预设未配置此安装面')
        sample = {'path': preset['file'], 'sha256': preset['sha256'], 'noise_strength': 0}
        sample.update(args.get('preset_options', {}))
        return LIBRARY,sample
    return workspace,args['sample']


def panel_materials(args):
    values=tuple(state(args.get(key,default)) for key,default in
                 (('base','stone_bricks'),('material','quartz_block')))
    if any(collision_cells(value)[0] != collision_cells('stone')[0] or collision_cells(value)[1]
           for value in values):
        raise ValueError('底板和纹样材质须为已知完整方块')
    return values


def compile_panel(workspace, args):
    from nbt_modeling_session import current,canonical,engine_revision
    from nbt_ornament_sample import sample_image
    root,sample=sample_input(workspace,args)
    # Verify the real raster hash even on a cache hit. Cached data never
    # replaces installation protection, source or geometry checks.
    sample_image(root,sample)
    parameters={k:v for k,v in args.items() if k!='preview'}
    key=(str(Path(workspace).resolve()),str(Path(root).resolve()),engine_revision(),canonical(sample),canonical(parameters))
    cache=current();hit=cache.get('pattern_compile',key)
    if hit is not None:return hit
    result=_compile_panel(workspace,args)
    cache.put('pattern_compile',key,result)
    return result


def _compile_panel(workspace, args):
    from nbt_structure_agent import build

    if args.get('fit_mode')=='micro':
        from nbt_microfit import compile_microfit
        return compile_microfit(workspace,args)
    if set(args)&{'quality_profile','min_quality_score'}:
        raise ValueError('量化质量配置用于pattern_microfit或fit_mode=micro，按单元评估后再铺排')
    if set(args)&{'tile_counts','gap_uv','micro_max_error','micro_alignment','diameter','full_blocks_only'}:
        raise ValueError('微型铺排参数须使用fit_mode=micro或pattern_microfit')
    if args['surface']=='cylinder':
        from nbt_cylinder_pattern import compile_cylinder
        return compile_cylinder(workspace,args)
    if 'seam_degrees' in args:
        raise ValueError('seam_degrees 仅适用于圆柱环绕')
    surface = args['surface']
    width, height = args['size_uv']
    body,ornament=panel_materials(args)
    sample_root,sample=sample_input(workspace,args)

    repeat = args.get('repeat', [1, 1])
    shapes = args.get('shapes')
    if shapes == {}:
        raise ValueError('shapes 至少须指定一种材质')
    if shapes and surface == 'floor':
        raise ValueError('地板镶嵌保持平齐，请省略 shapes')
    choices = None
    if shapes:
        if surface == 'ceiling' and ('slab' in shapes or 'stairs' not in shapes):
            raise ValueError('吊顶平面细分使用顶半直楼梯，半砖不能细分 XZ 轮廓')
        if surface == 'ceiling':
            name, props = effective(shapes['stairs'])
            if not name.endswith('_stairs') or props.get('waterlogged')!='false':
                raise ValueError('吊顶轮廓须使用未含水原版楼梯')
            choices = [(None, (False,)*4)]
            for direction in ('north','east','south','west'):
                value=state(f'{name}[facing={direction},half=top,shape=straight,waterlogged=false]')
                # Top half touches backing; the lower half supplies visible relief.
                points={(x,z) for x,y,z in collision_cells(value)[0] if y==0}
                choices.append((value,tuple(p in points for p in ((0,0),(1,0),(0,1),(1,1)))))
            choices.append((ornament,(True,)*4))
        else:
            choices = silhouette_options(ornament, shapes)

    sample_at, color_at, coverage_at = fit_sample(sample_root,sample,width,height,args.get('seed',0),
                                     sample.get('mirror',False),repeat,subcells=bool(choices),return_coverage=True)
    horizontal = surface in ('floor','ceiling')
    size = [width, 1 if surface=='floor' else 2, height] if horizontal else [width,height,2]
    blocks = {}
    shape_counts = {}
    stair_orientations = {}
    fit_counts = dict(requested=0, matched=0, missing=0, extra=0)
    for u in range(width):
        for v in range(height):
            # Gray samples map to a plane; the backing remains continuous.
            mask = sample_at(u,v)
            if choices:
                value, projected = match_silhouette(mask,choices,coverage_at(u,v))
            else:
                value, projected = (ornament if mask else None), (bool(mask),)
                mask = (bool(mask),)
            fit_counts['requested'] += sum(mask)
            fit_counts['matched'] += sum(a and b for a,b in zip(mask,projected))
            fit_counts['missing'] += sum(a and not b for a,b in zip(mask,projected))
            fit_counts['extra'] += sum(b and not a for a,b in zip(mask,projected))
            if value == ornament:
                value = color_at(u,v) or ornament
                occupied, reason=collision_cells(value)
                if reason or len(occupied)!=8:
                    raise ValueError('面板样本配色须为已知完整方块')
            if surface=='floor':
                blocks[u,0,v] = value or body
            elif surface=='ceiling':
                blocks[u,1,v] = body
                if value:
                    blocks[u,0,v] = value
            else:
                blocks[u,v,0] = body
                if value:
                    blocks[u,v,1] = value
            if value:
                family='slab' if '_slab[' in value else 'stairs' if '_stairs[' in value else 'full'
                shape_counts[family]=shape_counts.get(family,0)+1
                if family=='stairs':
                    _,props=effective(value)
                    key=props['facing']+'/'+props['half']
                    stair_orientations[key]=stair_orientations.get(key,0)+1
    if not shape_counts:
        raise ValueError('图样没有生成可见纹样，请调整尺寸或阈值')
    palette=sorted(set(blocks.values()))
    indices={value:i for i,value in enumerate(palette)}
    anchor = [width//2,1,height//2] if surface=='ceiling' else [width//2,0,height//2 if horizontal else 0]
    spec=dict(name=args.get('name',args.get('preset',surface)),size=size,anchor=anchor,
              max_changed_blocks=args.get('max_changed_blocks',8192),
              operations=[dict(kind='paste_component',label='纹样面板',
                  classification='wall' if surface in ('wall','column') else 'body',
                  lo=[0,0,0],hi=[n-1 for n in size],palette=palette,
                  voxels=[[*p,indices[value]] for p,value in sorted(blocks.items())])])
    if surface=='ceiling':
        spec['camera']={'azimuth':35,'elevation':-65}
    elif surface=='floor':
        spec['camera']={'azimuth':35,'elevation':65}
    data=build(workspace,spec)
    return dict(spec=spec,content_sha256=data['content_sha256'],block_count=len(data['blocks']),
                sample_sha256=sample['sha256'],surface=surface,shape_counts=shape_counts,
                stair_orientations=stair_orientations,orientation_policy='automatic_contour_and_surface_normal',
                fitting=dict(fit_counts,subcells_per_block=4 if choices else 1,
                             projection='lower_half_xz' if surface=='ceiling' and choices else 'xz' if horizontal else 'xy',
                             reference='resampled_threshold_mask'),
                model_modified=False)
