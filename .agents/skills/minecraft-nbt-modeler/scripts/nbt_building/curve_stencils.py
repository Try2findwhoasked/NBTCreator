"""Parameterized planar UV stencils; actual curved placement is a separate candidate."""
import hashlib
import json

from nbt_model import AIR_NAMES,state
from nbt_mounting.surface_mount import _full

PROFILES=('curve_ring_segment','curve_dark_seam','curve_rib','curve_window_column','curve_diagonal_band','curve_skirt_segment')
CAPS=('square','low_step','high_step')
COMMON={'profile','curve_cap_start','curve_cap_end','curve_cap_length'}
FIELDS={
    'curve_ring_segment':{'curve_width','curve_offset'},
    'curve_dark_seam':{'curve_width','curve_offset'},
    'curve_rib':{'curve_width','curve_offset'},
    'curve_window_column':{'curve_width','curve_offset','curve_window_height','curve_gap','curve_count','curve_start'},
    'curve_diagonal_band':{'curve_width','curve_start','curve_rise'},
    'curve_skirt_segment':{'curve_left_bottom','curve_right_bottom','curve_left_top','curve_right_top'},
}


def _integer(value,label,lo,hi):
    if type(value) is not int or not lo<=value<=hi:raise ValueError(label+'超出允许范围')
    return value


def _lerp(a,b,index,last):
    if not last:
        if a!=b:raise ValueError('单格长度不能表达不同的两端')
        return a
    delta=b-a;amount=(2*abs(delta)*index+last)//(2*last)
    return a+(amount if delta>=0 else -amount)


def _caps(points,axis,start,end,length):
    if start not in CAPS or end not in CAPS or type(length) is not int or not 0<=length<=32:
        raise ValueError('曲面模板端部参数无效')
    if (start!='square' or end!='square') and length==0:raise ValueError('阶梯端部须指定正的收头长度')
    if start==end=='square':
        if length:raise ValueError('两端均为平端时不使用收头长度')
        return points
    first=min(p[axis] for p in points);last=max(p[axis] for p in points);span=last-first+1
    if length>=span or start!='square' and end!='square' and 2*length>span:
        raise ValueError('曲面模板两端收头超出有效跨度')
    result=set(points);cross=1-axis
    for coordinate in range(first,last+1):
        column=[point for point in points if point[axis]==coordinate]
        if not column:continue
        lower=min(point[cross] for point in column);upper=max(point[cross] for point in column)
        for style,distance in ((start,coordinate-first),(end,last-coordinate)):
            if style=='square' or distance>=length:continue
            trim=((upper-lower)*(length-distance)+length-1)//length
            for point in column:
                if style=='low_step' and point[cross]<lower+trim or style=='high_step' and point[cross]>upper-trim:
                    result.discard(point)
    if not result:raise ValueError('曲面模板收头不能移除全部内容')
    if result==points:raise ValueError('曲面模板收头没有可裁切的宽度')
    return result


def compile_stencil(workspace,arguments):
    allowed={'kind','size','name','material','form','max_changed_blocks'}
    if set(arguments)-allowed:raise ValueError('曲面模板不使用样式、主题、装饰或其他构件参数')
    size=arguments['size']
    if not isinstance(size,list) or len(size)!=3 or any(type(value) is not int for value in size):raise ValueError('曲面模板尺寸无效')
    width,height,depth=size
    if not 1<=width<=64 or not 1<=height<=64 or depth!=1:raise ValueError('曲面模板须为1～64格的 XY 平面，Z 厚度为1')
    form=arguments.get('form')
    if not isinstance(form,dict) or form.get('profile') not in PROFILES:raise ValueError('须选择受支持的曲面模板类型')
    profile=form['profile'];required=FIELDS[profile]
    if not required<=set(form) or set(form)-COMMON-required:raise ValueError('曲面模板缺少或包含不适用的构造参数')
    material=state(arguments.get('material','stone_bricks'))
    if material in AIR_NAMES or not _full(material):raise ValueError('曲面模板标记材质须为已知完整方块')
    points=set();axis=0
    if profile in ('curve_ring_segment','curve_dark_seam','curve_rib','curve_window_column'):
        cross_limit=width if profile in ('curve_rib','curve_window_column') else height
        band=_integer(form['curve_width'],'模板宽度',1,64);offset=_integer(form['curve_offset'],'模板偏移',0,63)
        if offset+band>cross_limit:raise ValueError('模板宽度和偏移超出画布')
        if profile in ('curve_ring_segment','curve_dark_seam'):
            points={(x,y) for x in range(width) for y in range(offset,offset+band)}
        elif profile=='curve_rib':
            axis=1;points={(x,y) for x in range(offset,offset+band) for y in range(height)}
        else:
            axis=1;window=_integer(form['curve_window_height'],'窗格高度',1,64);gap=_integer(form['curve_gap'],'窗格间距',0,63)
            count=_integer(form['curve_count'],'窗格数量',1,16);start=_integer(form['curve_start'],'窗列起点',0,63)
            if start+(count-1)*(window+gap)+window>height:raise ValueError('窗列超出画布，不自动裁切')
            points={(x,y) for x in range(offset,offset+band) for index in range(count)
                    for y in range(start+index*(window+gap),start+index*(window+gap)+window)}
    elif profile=='curve_diagonal_band':
        band=_integer(form['curve_width'],'斜带宽度',1,64);start=_integer(form['curve_start'],'斜带起点',0,63)
        rise=_integer(form['curve_rise'],'斜带升降',-63,63)
        if min(start,start+rise)<0 or max(start,start+rise)+band>height:raise ValueError('斜带超出画布，不自动裁切')
        points={(x,y) for x in range(width) for y in range(_lerp(start,start+rise,x,width-1),_lerp(start,start+rise,x,width-1)+band)}
    else:
        left0=_integer(form['curve_left_bottom'],'左下收分',0,63);right0=_integer(form['curve_right_bottom'],'右下收分',0,63)
        left1=_integer(form['curve_left_top'],'左上收分',0,63);right1=_integer(form['curve_right_top'],'右上收分',0,63)
        if max(left0+right0,left1+right1)>=width:raise ValueError('裙边收分超出画布')
        for y in range(height):
            left=_lerp(left0,left1,y,height-1);right=_lerp(right0,right1,y,height-1)
            if left+right>=width:raise ValueError('裙边插值收分没有留下有效宽度')
            points.update((x,y) for x in range(left,width-right))
    caps=(form.get('curve_cap_start','square'),form.get('curve_cap_end','square'),form.get('curve_cap_length',0))
    points=_caps(points,axis,*caps)
    name=arguments.get('name','曲面 UV 模板')
    if not isinstance(name,str) or not 1<=len(name.strip())<=80:raise ValueError('曲面模板名称无效')
    limit=arguments.get('max_changed_blocks',65536)
    if type(limit) is not int or not 1<=limit<=65536 or len(points)>limit:raise ValueError('曲面模板超过方块预算')
    voxels=[[x,y,0,0] for x,y in sorted(points)]
    spec=dict(name=name.strip(),size=list(size),anchor=[0,0,0],tags=['parametric','curve-stencil',profile],
              operations=[dict(kind='paste_component',label='曲面 UV 模板',classification='body',lo=[0,0,0],
                               hi=[width-1,height-1,0],palette=[material],voxels=voxels)],max_changed_blocks=limit)
    from nbt_structure_agent import build
    component=build(workspace,spec)
    identity=dict(generator='nbt_curve_stencil',revision=1,parameters=arguments,spec=spec)
    return dict(spec=spec,ornament={},parts={},construction=dict(profile=profile,axis='uv',caps=list(caps),cells=len(points)),
        end_decorations={},resolved_form=dict(form),revision=1,
        recipe_sha256=hashlib.sha256(json.dumps(identity,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest(),
        content_sha256=component['content_sha256'],block_count=len(component['blocks']),
        mount='平面 UV 模板；须结合实际曲面宿主与动作映射生成候选',
        verification=dict(block_states=True,bounds=True,design='pending_visual_review',routes='not_checked',support='not_checked',game='not_checked'),
        interfaces=[],interface_scope='not_applicable_to_stencil',model_modified=False,approval_created=False)
