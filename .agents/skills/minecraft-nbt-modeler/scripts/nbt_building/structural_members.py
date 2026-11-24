"""Plain structural members, open braces and usable door/window apertures.

These voxel sections describe geometry and assembly faces, not load capacity.
Legacy member profiles remain in nbt_building.modular_objects.
"""
from nbt_model import state
from nbt_registry import effective
from nbt_collision import collision_cells

PROFILES={'beam':('rectangular','i_section','box_section'),
          'bracket':('knee_brace','angle_bracket'),
          'frame':('doorway','recessed_window')}
from nbt_building.window_frames import PROFILES as WINDOW_PROFILES
PROFILES['frame']+=WINDOW_PROFILES


def selected(kind,form):
    return form.get('profile') in PROFILES.get(kind,())


def full(value):
    value=state(value)
    cells,reason=collision_cells(value)
    if reason or len(cells)!=8:raise ValueError('梁、托架和洞口框主体须使用已知完整方块')
    return value


def grain(value,axis):
    """Infer grain only for bare material IDs; preserve explicitly authored axes."""
    name,props=effective(value)
    if 'axis' in props and 'axis=' not in value:
        return state(dict(Name=name,Properties=dict(props,axis=axis)))
    return value


def generate(kind,form,size,box,primary,accent,*,window_sill=None):
    """A composite may supply its own validated recessed-window sill state."""
    if kind=='frame' and form['profile'] in WINDOW_PROFILES:
        from nbt_building.window_frames import generate as generate_window
        return generate_window(form,size,box,primary,accent)
    profile=form['profile'];w,h,d=size;x,y,z=w-1,h-1,d-1
    allowed={'profile','border'}
    if profile=='recessed_window':allowed|={'recess','glazing','glass_material','sill_material'}
    if profile=='doorway':allowed.add('frame_depth')
    if set(form)-allowed:raise ValueError('当前结构截面不使用这些form参数')
    b=form.get('border',1)
    primary,accent=full(primary),full(accent)
    parts={}
    def part(name,lo,hi):parts[name]=dict(lo=lo,hi=hi)
    if kind=='beam':
        if profile=='rectangular':
            box([0,0,0],[x,y,z],grain(primary,'x'))
            for a in (0,x):box([a,0,0],[a,y,z],grain(accent,'x'))
            part('span',[1,0,0],[x-1,y,z])
            part('end_start',[0,0,0],[0,y,z]);part('end_end',[x,0,0],[x,y,z])
            if 'border' in form:raise ValueError('实心矩形梁没有壁厚border参数')
        else:
            if 2*b>=min(h,d):raise ValueError('梁壁厚没有留下腹板净高或箱梁内腔')
            box([0,0,0],[x,b-1,z],grain(accent,'x'))
            box([0,h-b,0],[x,y,z],grain(accent,'x'))
            part('bottom_flange',[0,0,0],[x,b-1,z]);part('top_flange',[0,h-b,0],[x,y,z])
            if profile=='i_section':
                low=(d-b)//2
                box([0,b,low],[x,h-b-1,low+b-1],grain(primary,'x'))
                part('web',[0,b,low],[x,h-b-1,low+b-1])
            else:
                for side,low in (('near_web',0),('far_web',d-b)):
                    box([0,b,low],[x,h-b-1,low+b-1],grain(primary,'x'))
                    part(side,[0,b,low],[x,h-b-1,low+b-1])
    elif kind=='bracket':
        if 2*b>=min(h,d) or b>w:raise ValueError('托架杆件过厚，没有留下有效净空')
        a=(w-b)//2;c=a+b-1
        box([a,0,0],[c,y,b-1],grain(primary,'y'))
        box([a,h-b,b],[c,y,z],grain(primary,'z'))
        part('back',[a,0,0],[c,h-b-1,b-1]);part('arm',[a,h-b,0],[c,y,z])
        if profile=='knee_brace':
            previous=0
            for depth in range(d):
                level=depth*y//z
                if depth>=b:
                    bottom=min(previous,level);top=min(h-b-1,level+b-1)
                    box([a,bottom,depth],[c,top,depth],grain(accent,'z' if d>=h else 'y'))
                previous=level
            part('brace',[a,0,b],[c,h-b-1,z])
    elif kind=='frame':
        if 2*b>=min(w,h):raise ValueError('洞口框边厚没有留下有效开口')
        front=1 if profile=='recessed_window' else 0
        back=z
        if profile=='doorway':
            depth=form.get('frame_depth',1)
            if not 1<=depth<=d:raise ValueError('门框厚度frame_depth须位于画布深度内')
            back=depth-1
        for name,low in (('jamb_left',0),('jamb_right',w-b)):
            box([low,0,front],[low+b-1,h-b-1,back],grain(primary,'y'))
            part(name,[low,0,front],[low+b-1,h-b-1,back])
        box([0,h-b,front],[x,y,back],grain(accent,'x'))
        part('lintel',[0,h-b,front],[x,y,back])
        if profile=='recessed_window':
            recess=form.get('recess',min(2,z))
            if not 1<=recess<d:raise ValueError('玻璃退进须位于框体内，recess为1到深度-1')
            glazing=form.get('glazing',True)
            glass=full(form.get('glass_material','glass'))
            name,_=effective(glass)
            if name not in ('minecraft:glass','minecraft:tinted_glass') and not name.endswith('_stained_glass'):
                raise ValueError('玻璃材质须使用原版完整玻璃方块')
            sill=window_sill
            if sill is None:
                sill=state(form.get('sill_material','smooth_quartz_slab[type=top,waterlogged=false]'))
                name,props=effective(sill)
                if not name.endswith('_slab') or props.get('type')!='top' or props.get('waterlogged')!='false':
                    raise ValueError('前挑窗台须为未含水的顶部半砖')
            box([b,0,front],[x-b,b-1,z],grain(accent,'x'))
            box([0,0,0],[x,0,0],sill)
            part('sill',[0,0,0],[x,b-1,z])
            if glazing:box([b,b,recess],[x-b,y-b,recess],glass)
            # Keep this region even for glazing=false, so local regeneration
            # can remove a glass panel without changing the surrounding frame.
            part('glazing',[b,b,recess],[x-b,y-b,recess])
    return parts


def describe(kind,form,size):
    """Return only planes containing actual material in these member profiles."""
    if kind=='frame' and form['profile'] in WINDOW_PROFILES:
        from nbt_building.window_frames import describe as describe_window
        return describe_window(form,size)
    w,h,d=size;x,y,z=w-1,h-1,d-1;b=form.get('border',1);profile=form['profile']
    interfaces=[];apertures=[]
    def face(name,direction,lo,hi):interfaces.append(dict(id=name,face=direction,lo=lo,hi=hi))
    if kind=='beam':
        for name,a in (('support_start',0),('support_end',x)):
            face(name,'down',[a,0,0],[a,0,z])
        if profile=='rectangular':low,high=0,z
        elif profile=='i_section':low=(d-b)//2;high=low+b-1
        else:low,high=0,b-1
        face('end_start','west',[0,0,low],[0,y,high])
        face('end_end','east',[x,0,low],[x,y,high])
        face('top','up',[0,y,0],[x,y,z])
    elif kind=='bracket':
        a=(w-b)//2;c=a+b-1
        face('back','north',[a,0,0],[c,y,0]);face('top','up',[a,y,0],[c,y,z])
    else:
        front=1 if profile=='recessed_window' else 0
        back=z if profile=='recessed_window' else form.get('frame_depth',1)-1
        face('left_seat','down',[0,0,front],[b-1,0,back])
        face('right_seat','down',[w-b,0,front],[x,0,back])
        face('head_top','up',[0,y,front],[x,y,back])
        apertures=[dict(id='opening',lo=[b,0 if profile=='doorway' else b,0],hi=[x-b,y-b,z],
                        glazed=profile=='recessed_window' and form.get('glazing',True),
                        passage_candidate=profile=='doorway')]
    return dict(profile=profile,interfaces=interfaces,apertures=apertures,
                front='north_-z' if kind=='frame' else None,
                support='not_checked',routes='not_checked',game='not_checked')
