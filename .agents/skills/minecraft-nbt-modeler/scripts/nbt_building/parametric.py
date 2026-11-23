"""Deterministic, data-only architectural objects for the shared structure API."""
import hashlib
import json
from nbt_model import state, AIR_NAMES

KINDS = {'pillar':'装饰柱','stairs':'楼梯','table':'桌子','wall':'墙面装饰','ceiling':'吊顶装饰',
         'plant':'盆栽','shelf':'置物架','bench':'长凳','planter':'长花槽','lantern':'灯架',
         'curve_stencil':'曲面 UV 平面模板'}
from nbt_building.modular_objects import KINDS as MODULAR_KINDS
KINDS.update(MODULAR_KINDS)
STYLES = {'classic':'框架与收边','stepped':'层叠与加厚','open':'减少封闭面并保留骨架'}

def listing(arguments=None, workspace=None):
    from nbt_structure_agent import definitions
    from nbt_pattern.ornament import PROFILES
    from nbt_pattern.ornament_sample import ARCHITECTURAL_SAMPLES
    from nbt_building.object_forms import THEMES, FORM_FIELDS
    from nbt_building.classical_column import ORDERS
    from nbt_assets.object_library import library
    from nbt_building.object_forms import PROFILES as FORM_PROFILES
    arguments=arguments or {}
    return dict(schema_version=1,column_orders=ORDERS,object_library=library(arguments.get('kind'), workspace=workspace),form_profiles=FORM_PROFILES,architectural_samples=ARCHITECTURAL_SAMPLES,themes=THEMES,form_fields=FORM_FIELDS,parameters=definitions()['parametric_compile']['parameters'],
                kinds=[dict(kind=k,name=v,styles={} if k=='curve_stencil' else STYLES,mount='curve_uv_xy' if k=='curve_stencil' else 'wall_back_z0' if k=='wall' else 'back_z0_top_support' if k=='bracket' else 'span_end_supports' if k=='beam' else 'ceiling_top' if k=='ceiling' else 'floor') for k,v in KINDS.items() if not arguments.get('kind') or arguments['kind']==k],
                ornament_profiles={k:v for k,v in PROFILES.items() if not arguments.get('ornament_profile') or arguments['ornament_profile']==k},
                coordinates='局部XYZ，包含两端；曲面模板位于XY平面且Z=0；墙饰背面Z=0，楼梯沿+Z上升；放置旋转、镜像由structure_place处理',
                model_modified=False)

def compile_object(workspace, arguments):
    from nbt_structure_agent import _schema, definitions, build
    _schema(arguments,definitions()['parametric_compile']['parameters'],'参数化构件')
    if arguments['kind']=='curve_stencil':
        from nbt_building.curve_stencils import compile_stencil
        return compile_stencil(workspace,arguments)
    original_arguments=arguments
    from nbt_building.window_frames import PROFILES as WINDOW_PROFILES
    if arguments.get('form',{}).get('profile') in WINDOW_PROFILES and arguments.get('ornament',{}).get('profile','none')!='none':
        raise ValueError('花式窗型使用自身窗棂与线脚，不叠加会覆盖玻璃的通用ornament')
    from nbt_building.object_forms import THEMES
    theme=arguments.get('theme')
    if theme:
        arguments={**THEMES[theme],**arguments}
        if arguments['kind']=='ceiling' and 'form' in arguments:
            arguments['form']={'pitch':arguments['spacing'],**arguments['form']}
    kind=arguments['kind'];style=arguments.get('style','classic');w,h,d=arguments['size'];x,y,z=w-1,h-1,d-1
    slender_beam=kind=='beam' and arguments.get('form',{}).get('profile')=='rectangular'
    if w<3 or min(h,d)<(1 if slender_beam else 3):
        raise ValueError('矩形梁跨度至少3格、截面至少1格；其他构件每轴至少3格')
    from nbt_building.structural_members import selected
    if selected(kind,arguments.get('form',{})):
        if style!='classic' or set(original_arguments)&{'spacing','thickness'}:
            raise ValueError('新结构截面由form.profile决定；style仅接受classic，壁厚用form.border，不使用spacing/thickness')
    if max(w,d)>32 or h>(64 if kind=='pillar' else 32):raise ValueError('柱子高度最多64格，其余构件和柱子宽深最多32格')
    if kind=='pillar' and 'form' in arguments:
        from nbt_building.classical_column import resolve
        arguments=dict(arguments,form=resolve(arguments['form'],arguments['size']))
        if arguments['form'].get('capital_profile') in ('tuscan','doric','ionic','corinthian','composite'):arguments['form'].setdefault('detail_material',arguments.get('material','stone_bricks'))
    spacing=arguments.get('spacing',3);t=arguments.get('thickness',1)
    if not slender_beam and 2*t>=min(w,d):raise ValueError('厚度须小于宽度与深度的一半')
    primary=state(arguments.get('material','stone_bricks'));accent=state(arguments.get('accent','polished_andesite'))
    if primary in AIR_NAMES or accent in AIR_NAMES:raise ValueError('构件材质不能为空气')
    foliage=state(arguments.get('foliage','oak_leaves[persistent=true]'))
    if kind in ('plant','planter') and foliage in AIR_NAMES:raise ValueError('植物叶片不能为空气')
    cx,cz=x//2,z//2;ops=[]
    def box(lo,hi,material=primary):
        if any(lo[i]>hi[i] for i in range(3)):return
        if any(lo[i]<0 or hi[i]>=arguments['size'][i] for i in range(3)):raise ValueError('参数导致构件越界')
        ops.append(dict(kind='box',label=KINDS[kind]+' '+str(len(ops)+1),classification='wall' if kind=='wall' else 'body',lo=lo,hi=hi,state=material))
    def frame(level):
        box([0,level,0],[x,level,t-1],accent);box([0,level,d-t],[x,level,z],accent)
        box([0,level,t],[t-1,level,d-t-1],accent);box([w-t,level,t],[x,level,d-t-1],accent)
    def legs(top):
        for a,b in [(0,0),(w-t,0),(0,d-t),(w-t,d-t)]:box([a,0,b],[a+t-1,top,b+t-1])
    parts={}
    modular_receipt={}
    if 'form' in arguments or kind in MODULAR_KINDS:
        from nbt_building.object_forms import generate
        from itertools import product
        blocks={}
        def paint(lo,hi,value=primary):
            if any(a>b for a,b in zip(lo,hi)):return
            if any(a<0 or b>=limit for a,b,limit in zip(lo,hi,arguments['size'])):
                raise ValueError('专用构造超出尺寸')
            if value in AIR_NAMES:raise ValueError('专用构造材质不能是空气')
            for point in product(*(range(a,b+1) for a,b in zip(lo,hi))):
                blocks[point]=value
        if kind=='stairs' and 'handrail' in arguments.get('form',{}):
            from nbt_building.modular_objects import stairs
            modular_receipt=stairs(arguments['form'],arguments['size'],paint,primary,accent)
        else:
            parts=generate(kind,arguments.get('form',{}),arguments['size'],paint,primary,accent,foliage,style)
        palette=sorted(set(blocks.values()))
        index={value:i for i,value in enumerate(palette)}
        ops.append(dict(kind='paste_component',label=KINDS[kind],classification='wall' if kind=='wall' else 'body',
                        lo=[0,0,0],hi=[x,y,z],palette=palette,voxels=[[*point,index[value]] for point,value in sorted(blocks.items())]))
    elif kind=='pillar':
        box([0,0,0],[x,0,z],accent);box([0,y,0],[x,y,z],accent)
        if style=='open':legs(y-1)
        else:
            box([t,1,t],[x-t,y-1,z-t])
            if style=='stepped':frame(1);frame(y-1)
    elif kind=='stairs':
        from nbt_registry import effective
        stair=state(arguments.get('stair_material','stone_brick_stairs[facing=south,half=bottom,shape=straight,waterlogged=false]'))
        block,properties=effective(stair)
        if not block.endswith('_stairs') or properties.get('facing')!='south' or properties.get('half')!='bottom' or properties.get('shape')!='straight' or properties.get('waterlogged')!='false':raise ValueError('楼梯材质须为沿south上升的干燥底部直楼梯')
        if d<h:raise ValueError('楼梯深度须不小于高度')
        # Vanilla stair blocks provide half-height collision steps; no jump claim.
        for b in range(d):
            level=min(y,b*h//d)
            if style!='open' and level:box([0,0,b],[x,level-1,b],accent)
            box([0,level,b],[x,level,b],stair)
        if style=='stepped':
            for b in range(d):
                level=min(y,b*h//d)
                if level<y:box([0,level+1,b],[0,level+1,b],accent)
    elif kind=='wall':
        # Added relief only: never carve an existing wall or assume openings.
        for level in (0,y):box([0,level,0],[x,level,t-1],accent)
        for a in sorted(set([0,x]+list(range(0,w,spacing)))):box([a,1,0],[min(x,a+t-1),y-1,t-1])
        if style=='stepped':box([0,y//2,0],[x,y//2,min(z,t)],accent)
        elif style=='classic':box([t,1,0],[x-t,y-1,0],accent)
    elif kind=='ceiling':
        for a in sorted(set([0,x]+list(range(0,w,spacing)))):box([a,y-1,0],[a,y,z])
        for b in sorted(set([0,z]+list(range(0,d,spacing)))):box([0,y,b],[x,y,b],accent)
        if style=='stepped':frame(max(0,y-2))
        elif style=='classic':frame(y-1)
    elif kind in ('plant','planter'):
        box([0,0,0],[x,0,z],accent);frame(1);box([t,1,t],[x-t,1,z-t],'dirt')
        centers=[cx] if kind=='plant' else list(range(t,w-t,spacing))
        for a in centers:
            box([a,2,cz],[a,y,cz],primary)
            radius=0 if style=='open' else 1
            box([max(t,a-radius),max(2,y-1),max(t,cz-radius)],[min(x-t,a+radius),y,min(z-t,cz+radius)],foliage)
        if style=='stepped':frame(0)
    elif kind=='lantern':
        box([0,0,0],[x,0,z],accent);box([cx,1,cz],[cx,y-1,cz]);box([cx,y,cz],[cx,y,cz],'glowstone')
        if style!='open':frame(y)
        if style=='stepped':box([cx,y-1,0],[cx,y-1,z],accent)
    elif kind=='shelf':
        legs(y)
        for level in sorted(set([y]+list(range(1,h,spacing)))):box([0,level,0],[x,level,z],accent)
        if style!='open':box([0,0,z],[x,y,z])
        if style=='stepped':frame(0)
    else:
        level=y if kind=='table' else y//2
        legs(level-1);box([0,level,0],[x,level,z],accent)
        if kind=='table' and style=='classic':
            box([0,max(0,level-1),0],[x,max(0,level-1),0]);box([0,max(0,level-1),z],[x,max(0,level-1),z])
        if kind=='bench' and style!='open':box([0,level+1,z],[x,y,z])
        if style=='stepped':frame(0)
    name=arguments.get('name',KINDS[kind]+' · '+style)
    spec=dict(name=name,size=list(arguments['size']),anchor=[cx,y,cz] if kind=='ceiling' else [cx,0,0] if kind=='wall' else [cx,0,cz],
              tags=['parametric',kind,style],operations=ops,max_changed_blocks=arguments.get('max_changed_blocks',65536))
    data=build(workspace,spec)
    from nbt_pattern.ornament import decorate
    ornament=decorate(spec,data,arguments,workspace)
    if ornament['added_or_recolored_blocks']:data=build(workspace,spec)
    end_decorations={}
    if kind=='pillar' and parts:
        from nbt_building.pillar_ends import decorate_ends
        spec,data,end_decorations=decorate_ends(workspace,spec,data,arguments,parts)
    mount='背面Z=0贴实墙；凸出方向+Z；不挖墙，不自动避让开口' if kind=='wall' else '顶面Y=max贴承托结构；向下悬挂，不自动证明支承' if kind=='ceiling' else '底部Y=0置于已有支撑面'
    if kind=='beam':mount='沿+X跨接；两端底部须贴真实承托，安装后另验接触'
    if kind=='bracket':mount='背面Z=0贴承托，顶面Y=max承接上部；侧装须显式设置quarter_turns'
    identity=dict(generator='nbt_parametric',revision=8 if 'sample_shape_fit' in arguments.get('ornament',{}) else 6 if set(arguments.get('ornament',{})) & {'edge_trim','sample_repeat'} else 5 if set(arguments.get('ornament',{})) & {'sample','richness','highlight'} else 4 if 'form' in arguments or theme or set(arguments.get('ornament',{})) & {'layout','center_clear'} else 3,parameters=original_arguments,spec=spec)
    if kind=='pillar' and set(arguments.get('form',{}))&{'base_profile','capital_profile','base_curve','capital_curve','base_pattern','capital_pattern'}:identity['revision']=9
    if kind=='pillar' and ('order' in arguments.get('form',{}) or arguments.get('form',{}).get('section')=='round'):identity['revision']=10
    if kind in MODULAR_KINDS or 'handrail' in arguments.get('form',{}) or arguments.get('form',{}).get('section') in ('octagonal','bundled') or 'band_spacing' in arguments.get('form',{}):identity['revision']=11
    if kind=='railing' or 'handrail' in arguments.get('form',{}):identity['revision']=13
    if kind=='pillar' and 'shaft_inset' in arguments.get('form',{}):identity['revision']=14
    interfaces=[]
    if kind=='pillar':
        interfaces=[dict(id='base',face='down',lo=[0,0,0],hi=[x,0,z]),
                    dict(id='capital_top',face='up',lo=[0,y,0],hi=[x,y,z])]
    if kind=='railing':
        from nbt_collision import collision_cells
        slope=arguments.get('form',{}).get('slope',0)
        if all(collision_cells(value)[1] is None for value in data['palette']):
            interfaces=[dict(id='start',face='west',lo=[0,0,cz],hi=[0,h-slope-1,cz]),dict(id='end',face='east',lo=[x,slope,cz],hi=[x,y,cz])]
    if kind=='beam':
        interfaces=[dict(id='support_start',face='down',lo=[0,0,cz],hi=[0,0,cz]),dict(id='support_end',face='down',lo=[x,0,cz],hi=[x,0,cz])]
    if kind=='bracket':
        interfaces=[dict(id='back',face='north',lo=[0,0,0],hi=[x,y,0]),dict(id='top',face='up',lo=[0,y,0],hi=[x,y,z])]
    from nbt_building.structural_members import selected,describe
    if selected(kind,arguments.get('form',{})):
        modular_receipt=describe(kind,arguments['form'],arguments['size'])
        interfaces=modular_receipt['interfaces'];identity['revision']=15
    return dict(spec=spec,ornament=ornament,parts=parts,construction=modular_receipt,end_decorations=end_decorations,resolved_form=arguments.get('form',{}),revision=identity['revision'],recipe_sha256=hashlib.sha256(json.dumps(identity,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest(),
                content_sha256=data['content_sha256'],block_count=len(data['blocks']),mount=mount,
                verification=dict(block_states=True,bounds=True,design='pending_visual_review',routes='not_checked',support='not_checked',game='not_checked'),
                interfaces=interfaces,interface_scope='fine_rail_faces_not_halfcell_certified' if kind=='railing' and not interfaces else 'exact_halfcells',model_modified=False,approval_created=False)
