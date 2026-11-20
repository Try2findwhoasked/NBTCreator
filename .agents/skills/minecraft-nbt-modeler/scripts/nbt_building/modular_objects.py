"""Reusable architectural members and stairs with external, continuous rails.

These are voxel design candidates. Support, player routes and game behaviour
still need checking in the installed model, just like other parametric objects.
"""
from collections import deque
from math import sqrt
from nbt_model import state
from nbt_collision import collision_cells


KINDS = {'railing': '栏杆与扶手', 'beam': '梁与檐带', 'bracket': '托架',
         'arch': '拱框', 'frame': '门窗框', 'pedestal': '基座'}
PROFILES = {'railing': ('baluster', 'panel', 'lattice', 'horizontal'),
            'beam': ('solid', 'coffered', 'braced'),
            'bracket': ('stepped', 'curved', 'diagonal'),
            'arch': ('round', 'pointed', 'flat'),
            'frame': ('rectangular', 'crosslight', 'mullioned'),
            'pedestal': ('square', 'stepped', 'round')}
FIELDS = {kind: ('profile', 'pitch', 'border') for kind in KINDS}
FIELDS['railing'] = ('profile', 'pitch', 'slope', 'rail_material', 'post_material')
FIELDS['bracket'] = ('profile', 'pitch')
FIELDS['arch'] = ('profile', 'border')
FIELDS['pedestal'] = ('profile', 'pitch')
from nbt_building.structural_members import PROFILES as STRUCTURAL_PROFILES
for _kind,_profiles in STRUCTURAL_PROFILES.items():PROFILES[_kind]+=_profiles
FIELDS['bracket']+=('border',)
FIELDS['frame']+=('recess','glazing','glass_material','sill_material','frame_depth')
from nbt_building.window_frames import FIELDS as WINDOW_FIELDS
FIELDS['frame']+=WINDOW_FIELDS


def solid(value):
    value = state(value)
    cells, reason = collision_cells(value)
    if reason or len(cells) != 8:
        raise ValueError('楼梯平台与踏步支承须为已知完整方块')
    return value


def generate(kind, form, size, box, primary, accent, style):
    w, h, d = size
    x, y, z = w-1, h-1, d-1
    profile = form.get('profile', PROFILES[kind][1 if style == 'stepped' else 0])
    if profile not in PROFILES[kind] or set(form)-set(FIELDS[kind]):
        raise ValueError('form 含不适用于该模块的参数')
    if profile in STRUCTURAL_PROFILES.get(kind,()):
        from nbt_building.structural_members import generate as generate_member
        return generate_member(kind,form,size,box,primary,accent)
    if kind=='bracket' and 'border' in form or kind=='frame' and set(form)&{'recess','glazing','glass_material','sill_material','frame_depth'}:
        raise ValueError('这些参数需要选择新的结构托架或洞口框profile')
    pitch = form.get('pitch', 3)
    border = form.get('border', 1)
    parts = {}
    if kind == 'railing':
        slope = form.get('slope', 0)
        if h-slope < 3:
            raise ValueError('栏杆高度须容纳坡升和至少3格栏体')
        level = lambda a: a*slope//x
        points = {(a, z//2): level(a) for a in range(w)}
        from nbt_building.railings import compile_rails
        compile_rails(points,h-slope,pitch,profile,box,form.get('post_material'),form.get('rail_material'),open_infill=style=='open')
        parts['railing'] = dict(lo=[0, 0, z//2], hi=[x, y, z//2])
    elif kind == 'beam':
        box([0, y, 0], [x, y, z], accent)
        if style != 'open':
            box([0, max(0, y-border), 0], [x, y, z], primary)
        if profile == 'solid':
            box([0, 0, z//2], [x, y, z//2], primary)
        else:
            for a in sorted({0, x, *range(0, w, pitch)}):
                box([a, 0, 0], [a, y, z], primary)
            if profile == 'braced':
                for a in range(w):
                    b = min(y, a % pitch)
                    box([a, b, z//2], [a, y, z//2], accent)
        parts['cornice'] = dict(lo=[0, y, 0], hi=[x, y, z])
    elif kind == 'bracket':
        box([0, 0, 0], [x, y, 0], primary)
        box([0, y, 0], [x, y, z], accent)
        for level in range(h):
            t = (level+1)/h
            reach = round(z*(sqrt(t) if profile == 'curved' else t))
            if profile == 'stepped':
                reach = min(z, (level//max(1, pitch))*max(1, pitch))
            if style == 'open':
                box([x//2, level, 0], [x//2, level, reach], primary)
            else:
                box([0, level, 0], [x, level, reach], primary)
    elif kind == 'arch':
        if 2*border >= min(w, h):
            raise ValueError('拱框边厚没有留下净开口')
        spring = max(border, h//3)
        tops=[]
        for a in range(w):
            t = abs(2*a/x-1)
            top = y if profile == 'flat' else spring+round((y-spring)*(1-t if profile == 'pointed' else sqrt(max(0, 1-t*t))))
            tops.append(top)
        for a,top in enumerate(tops):
            bottom = 0 if a < border or a >= w-border else min(tops[max(0,a-1):min(w,a+2)])-border+1
            bottom=max(0,bottom)
            box([a, bottom, 0], [a, top, z], accent if style == 'stepped' and a == x//2 else primary)
        if style != 'open':
            for a in (0, w-border):
                box([a, 0, 0], [a+border-1, 0, z], accent)
    elif kind == 'frame':
        if 2*border >= min(w, h):
            raise ValueError('门窗框边厚没有留下净开口')
        for a in (0, w-border):
            box([a, 0, 0], [a+border-1, y, z], primary)
        for level in (0, h-border):
            box([0, level, 0], [x, level+border-1, z], accent)
        if profile == 'crosslight':
            box([border, y//2, z//2], [x-border, y//2, z//2], primary)
            box([x//2, border, z//2], [x//2, y-border, z//2], primary)
        elif profile == 'mullioned':
            for a in range(pitch, w-border, pitch):
                box([a, border, z//2], [a, y-border, z//2], primary)
        if style == 'stepped':
            box([0, y, 0], [x, y, z], primary)
    else:
        for level in range(h):
            inset = min((min(w, d)-1)//2, 1 if 0 < level < y else 0)
            if profile == 'stepped':
                inset = min((min(w, d)-1)//2, level//max(1, pitch))
            for a in range(inset, w-inset):
                for b in range(inset, d-inset):
                    if profile == 'round' and ((a-x/2)/max(.5, x/2))**2+((b-z/2)/max(.5, z/2))**2 > 1.01:
                        continue
                    if style == 'open' and 0 < level < y and (a, b) != (x//2, z//2):
                        continue
                    box([a, level, b], [a, level, b], accent if level in (0, y) else primary)
    return parts


def stairs(form, size, box, primary, accent):
    """New handrail requests use a clear-width path and external rail margins.

    Legacy form.rail requests remain in nbt_building.object_forms._stairs unchanged.
    """
    from nbt_registry import effective
    from nbt_building.object_forms import FORM_FIELDS
    if set(form)-set(FORM_FIELDS['stairs']):
        raise ValueError('form 含不适用于楼梯的参数')
    width, rise, landing = form.get('run_width', 2), form.get('rise', 4), form.get('landing', 2)
    profile = form.get('profile', 'straight')
    rail = form['handrail']
    if not rail or 'rail' in form:
        raise ValueError('handrail 须提供参数，且不能与旧 rail 同时使用')
    tread = state(form.get('tread', 'stone_brick_stairs'))
    block, props = effective(tread)
    if not block.endswith('_stairs') or props.get('waterlogged') != 'false' or props.get('half')!='bottom' or props.get('shape')!='straight' or ('facing=' in tread and props['facing']!='south'):
        raise ValueError('踏步须使用干燥底部直楼梯；朝向由跑段决定，显式facing只接受south')
    height = rail.get('height', 2)
    style = rail.get('style', 'baluster')
    primary, accent = solid(primary), solid(accent)
    footprint = {}
    entrance = exit_ = None
    def flight(x, z, dx, dz, count, level):
        nonlocal entrance, exit_
        # Left-facing width vector for south/east/north/west respectively.
        px, pz = dz, -dx
        rows = []
        for i in range(count):
            row = [(x+dx*i+px*j, z+dz*i+pz*j) for j in range(width)]
            for q in row:
                if q in footprint:
                    raise ValueError('楼梯跑段重叠，请增加平台或尺寸')
                footprint[q] = (level+i, (dx, dz))
            rows.append(row)
        if entrance is None:
            entrance = (rows[0], (-dx, -dz), (px, pz))
        exit_ = (rows[-1], (dx, dz), (px, pz))
    def platform(x, z, a, b, level):
        for i in range(x, x+a):
            for j in range(z, z+b):
                if (i, j) in footprint:
                    raise ValueError('楼梯平台重叠')
                footprint[(i, j)] = (level, None)
    a, b = (rise+1)//2, rise//2
    length = max(width, landing)
    if profile == 'straight':
        flight(0, 0, 0, 1, rise, 0)
        platform(0, rise, width, landing, rise-1)
        exit_ = ([(j, rise+landing-1) for j in range(width)], (0, 1), (1, 0))
    elif profile == 'quarter_turn':
        flight(0, 0, 0, 1, a, 0)
        platform(0, a, length, length, a-1)
        flight(length, a+width-1, 1, 0, b, a)
        platform(length+b, a, landing, width, rise-1)
        exit_ = ([(length+b+landing-1, a+j) for j in range(width)], (1, 0), (0, -1))
    elif profile == 'switchback':
        flight(0, landing, 0, 1, a, 0)
        platform(0, landing+a, 2*width+3, length, a-1)
        flight(2*width+2, landing+a-1, 0, -1, b, a)
        platform(width+3, a-b, width, landing, rise-1)
        exit_ = ([(width+3+j, a-b) for j in range(width)], (0, -1), (-1, 0))
    elif profile == 'spiral':
        if rise < 4:
            raise ValueError('带扶手的方形旋梯至少需要4级')
        counts = [rise//4+(i < rise % 4) for i in range(4)]
        r0, r1, r2, r3 = counts
        # Extend the first turn horizontally so the upper west exit and its
        # rails cannot touch or obstruct the lower south entrance.
        offset = length+width+3
        flight(0, length, 0, 1, r0, 0)
        platform(0, length+r0, offset, length, r0-1)
        flight(offset, length+r0+width-1, 1, 0, r1, r0)
        platform(offset+r1, length+r0, length, length, r0+r1-1)
        flight(offset+r1+width-1, length+r0-1, 0, -1, r2, r0+r1)
        north = length+r0-r2-length
        platform(offset+r1, north, length, length, r0+r1+r2-1)
        flight(offset+r1-1, north, -1, 0, r3, r0+r1+r2)
        platform(offset+r1-r3-landing, north, landing, width, rise-1)
        exit_ = ([(offset+r1-r3-landing, north+j) for j in range(width)], (-1, 0), (0, 1))
    else:
        raise ValueError('未知楼梯形态')

    # Reserve a full voxel margin for rails, independent of tread clear width.
    min_x = min(q[0] for q in footprint)-1
    min_z = min(q[1] for q in footprint)-1
    shift = lambda q: (q[0]-min_x, q[1]-min_z)
    footprint = {shift(q): value for q, value in footprint.items()}
    entrance = ([shift(q) for q in entrance[0]], *entrance[1:])
    exit_ = ([shift(q) for q in exit_[0]], *exit_[1:])
    openings = {(q[0]+direction[0], q[1]+direction[1]) for row, direction, _ in (entrance, exit_) for q in row}
    points = {}
    for (x, z), (level, _) in footprint.items():
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            q = (x+dx, z+dz)
            if q not in footprint and q not in openings:
                points[q] = max(points.get(q, 0), level+1)
    # Fill convex elbows so successive rail caps meet by a face, not a corner.
    boundary=dict(points)
    for x, z in boundary:
        for dx, dz in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
            q = (x+dx, z+dz)
            if q not in boundary:
                continue
            elbows=((x+dx,z),(x,z+dz))
            # A concave turn already has its inside elbow. Adding the other
            # one thickens it into a two-column cage and can propagate inward.
            if any(elbow in boundary for elbow in elbows):continue
            for elbow in elbows:
                if elbow not in footprint and elbow not in openings:
                    points[elbow] = max(points.get(elbow, 0), boundary[(x,z)], boundary[q])
    side = rail.get('side', 'both')
    def side_end(end, sign):
        row, _, normal = end
        q = max(row, key=lambda p: sign*(p[0]*normal[0]+p[1]*normal[1]))
        return (q[0]+sign*normal[0], q[1]+sign*normal[1])
    selections = {}
    for name, sign in (('left', 1), ('right', -1)):
        seed = side_end(entrance, sign)
        selected = {seed} if seed in points else set()
        queue = deque(selected)
        while queue:
            x, z = queue.popleft()
            for q in ((x-1, z), (x+1, z), (x, z-1), (x, z+1)):
                if q in points and q not in selected:
                    selected.add(q)
                    queue.append(q)
        if side_end(exit_, sign) not in selected:
            raise ValueError('扶手未连续连接所选侧的上下端点，请调整楼梯参数')
        selections[name] = selected
    if selections['left'] & selections['right']:
        raise ValueError('楼梯两侧扶手意外相交，请增加平台或跑段间距')
    if side != 'both':
        points = {q: points[q] for q in selections[side]}
    directions={(0,1):'south',(1,0):'east',(0,-1):'north',(-1,0):'west'}
    for (x, z), (level, direction) in sorted(footprint.items()):
        box([x, 0, z], [x, level-1, z], accent)
        value = primary if direction is None else f'{block}[facing={directions[direction]},half=bottom,shape=straight,waterlogged=false]'
        box([x, level, z], [x, level, z], value)
    from nbt_building.railings import compile_rails
    detail=compile_rails(points,height,rail.get('post_spacing',3),style,box,
                         rail.get('material'),rail.get('cap_material'),lower_to_tread=True)
    seats={(x,z):bottom for x,bottom,z in detail['support_seats']}
    for (x,z),own_bottom in sorted(seats.items()):
        # Only mounting seats at regular posts and turns; no decorative skirt.
        box([x,own_bottom-1,z],[x,own_bottom-1,z],detail['support_material'])
    return dict(clear_width=width, rail_side=side, rail_columns=len(points),
                footprint=[list(q) for q in sorted(footprint)],
                walk_columns=[[q[0], value[0], q[1]] for q,value in sorted(footprint.items())],
                rail_bases=[[x,level,z] for (x,z),level in sorted(points.items())],
                entrance=[[q[0],footprint[q][0],q[1]] for q in entrance[0]],
                exit=[[q[0],footprint[q][0],q[1]] for q in exit_[0]],
                handrail=detail,rail_height=height,routes='not_checked', support='not_checked')
