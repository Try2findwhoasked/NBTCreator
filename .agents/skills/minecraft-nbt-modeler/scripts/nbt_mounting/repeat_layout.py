"""One fitted unit and one phase for an entire installation surface."""
from collections import Counter

from nbt_composition.change_policy import reserved_position
from nbt_collision import collision_cells
from nbt_mounting.cylinder_fit import SIX, half_cells
from nbt_registry import effective
from nbt_tools import transformed_state


def phased_cells(unit, period, size, anchor, u_sign=1):
    width, height = period
    for v in range(size[1]):
        for u in range(size[0]):
            phase = (u_sign*(u-anchor[0]) % width, (v-anchor[1]) % height)
            value = unit.get(phase)
            if value is not None:
                yield (u, v), phase, value


def face_contact(a, b):
    return any((x+dx, y+dy, z+dz) in b for x,y,z in a for dx,dy,dz in SIX)


def solve_repeat_unit(workspace, proposal):
    from nbt_pattern.microfit import solve_micro_unit

    if set(proposal) & {'tile_counts','gap_uv','repeat'} or proposal.get('fit_mode','micro') != 'micro':
        raise ValueError('连续铺排使用微型单元，铺排范围由目标决定，请省略 repeat、tile_counts 和 gap_uv')
    return solve_micro_unit(workspace, {'micro_alignment':'fixed','fit_mode':'micro',**proposal})


def verify_inputs(workspace, proposal):
    from nbt_pattern.ornament_sample import sample_image
    from nbt_pattern.panel import sample_input

    root, sample = sample_input(workspace, dict(proposal,fit_mode='micro'))
    sample_image(root, sample)
    mask = proposal.get('repeat_detection', {}).get('valid_mask')
    if mask is not None:
        sample_image(workspace, mask)


def evidence(model, size, period, anchor, positions, clipped, *, u_sign=1, horizontal=False,
             closed=False, connectors=None, check_u_edges=False, clipped_connectors=()):
    """Compare requested states and exact half-cell contact against model readback."""
    connectors = connectors or {}
    entries = []
    actual = {}
    positions_match = True
    unsupported = []
    for uv, (phase, local, point, expected) in sorted(positions.items()):
        value = model.get(point)
        positions_match &= value == expected
        entries.append(dict(uv=list(uv), phase_uv=list(phase), position=list(point), expected=expected, actual=value))
        cells, reason = collision_cells(value)
        if reason or not cells:
            unsupported.append(list(uv))
        else:
            actual[uv] = {tuple(2*a+b for a,b in zip(point, c)) for c in cells}
    joints = []
    width, height = size
    for u, v in sorted(set(positions) | set(clipped)):
        for axis, end in enumerate((((u+1) % width, v), (u, v+1))):
            start = (u, v)
            wraps = axis == 0 and u+1 == width
            if end == start or end[1] >= height or (wraps and not closed):
                continue
            coordinate = u if axis == 0 else v
            leading = axis != 0 or u_sign > 0
            seam = wraps or (coordinate-anchor[axis]+int(leading)) % period[axis] == 0
            bridge = connectors.get((start, end))
            if not seam and not (check_u_edges and axis == 0):
                continue
            if start in clipped or end in clipped or (start,end) in clipped_connectors:
                if all(uv in positions or uv in clipped for uv in (start, end)):
                    joints.append(dict(a=list(start), b=list(end), seam=seam, wraps=wraps, status='clipped'))
                continue
            if start not in positions or end not in positions:
                continue
            step = (u_sign, 0, 0) if axis == 0 else (0, 0, 1) if horizontal else (0, 1, 0)
            local_a = positions[start][1]
            local_b = positions[end][1]
            if start not in actual or end not in actual:
                joints.append(dict(a=list(start), b=list(end), seam=seam, wraps=wraps, status='unsupported_shape'))
                continue
            expected = face_contact(half_cells({(0,0,0):local_a}), half_cells({step:local_b}))
            connected = face_contact(actual[start], actual[end])
            connector = {}
            if bridge is not None:
                point, value = bridge
                read = model.get(point)
                positions_match &= read == value
                connector = dict(connector_position=list(point),connector_state=value,connector_actual=read)
                if read == value:
                    middle = half_cells({point:value})
                    connected |= face_contact(actual[start], middle) and face_contact(middle, actual[end])
            joints.append(dict(a=list(start), b=list(end), seam=seam, wraps=wraps, expected_contact=expected,
                               actual_contact=connected, status='match' if expected == connected else 'mismatch',
                               **connector))
    joint_counts = Counter(joint['status'] for joint in joints)
    checked_joints = joint_counts['match'] + joint_counts['mismatch']
    return dict(size_uv=list(size), period_uv=list(period), anchor_uv=list(anchor), closed_u=closed,
                position_comparison=entries, positions_match=positions_match,
                clipped=[dict(uv=list(uv), reason=reason) for uv,reason in sorted(clipped.items())],
                half_cell_joints=joints, joint_counts=dict(joint_counts), unsupported_shape_uv=unsupported,
                seam_geometry_matches=(not unsupported and not joint_counts['mismatch']) if checked_joints or unsupported else None,
                game_effects='not_checked')


def planar(workspace, s, arguments, safe, reserved, protected, depth, inlay):
    from nbt_pattern.microfit import shape_family
    from nbt_mounting.surface_mount import _point, _reject, digest

    proposal = arguments['object']
    normal = s['request']['normal']
    turns = {'south':0, 'west':1, 'north':2, 'east':3, 'up':0, 'down':0}[normal]
    surfaces = {'up':('floor',), 'down':('ceiling',)}
    if proposal['surface'] not in surfaces.get(normal, ('wall','column')):
        raise ValueError('纹样单元与安装面法向不匹配')
    unit, quality, _, _, _, sample = solve_repeat_unit(workspace, proposal)
    period = proposal['size_uv']
    size = (s['width'], s['height'])
    anchor = arguments['anchor_uv']
    u_sign = -1 if normal in ('north','east') else 1
    positions = {}
    clipped = {}
    for uv, phase, local in phased_cells(unit, period, size, anchor, u_sign):
        point = _point(s, *uv, 0 if inlay else 1-depth)
        # Use the same carve depths as _plan when screening explicit masks.
        writes = [point] + [_point(s, *uv, -d) for d in range(depth-1)]
        if any(p in protected for p in writes):
            clipped[uv] = 'protected'
        elif any(p in reserved for p in writes) or reserved_position(writes,s['config'].get('reserved_boxes')) is not None:
            clipped[uv] = 'reserved'
        elif uv in s['opening_avoid']:
            clipped[uv] = 'opening_or_margin'
        elif uv not in safe:
            _reject(s, point, s['cell_info'][uv]['status'], '通铺位置的宿主、占用或支承检查失败')
        else:
            value = transformed_state(local, turns, None)
            if not inlay and not depth:
                axis, sign = s['axis'], s['sign']
                cells, reason = collision_cells(value)
                if reason or not any(cell[axis] == (0 if sign > 0 else 1) for cell in cells):
                    _reject(s, point, 'unsupported_half_cell_shape', '通铺状态没有精确半格背衬接触')
            positions[uv] = (phase,local,point,value)
    if not positions:
        raise ValueError('通铺裁切后没有可安装的饰面方块')
    lo = [min(entry[2][i] for entry in positions.values()) for i in range(3)]
    hi = [max(entry[2][i] for entry in positions.values()) for i in range(3)]
    palette = sorted({entry[3] for entry in positions.values()})
    op = dict(kind='paste_component', label='连续纹样铺排', classification='wall' if s['axis']!=1 else 'body',
              lo=lo, hi=hi, palette=palette, overwrite=inlay or depth>0,
              voxels=[[*[point[i]-lo[i] for i in range(3)], palette.index(value)]
                      for _,_,point,value in positions.values()])
    fitted = dict(surface=proposal['surface'], sample_sha256=sample['sha256'], microfit=quality,
                  orientation_policy='fixed_uv_phase_and_surface_normal',
                  shape_counts=dict(Counter(shape_family(effective(value)[0]) for _,_,_,value in positions.values())),
                  visual_quality=quality['visual_quality'],
                  fitting={k:quality[k] for k in ('requested','matched','missing','extra','subcells_per_block')})
    fitted['recipe_sha256'] = digest(dict(parameters=proposal, unit=sorted((u,v,value) for (u,v),value in unit.items())))
    return fitted, dict(operations=[op],lo=lo,hi=hi), positions, clipped, u_sign


def cylinder(workspace, proposal, model, lo, hi, anchor, protected, reserved, context_reserved):
    from nbt_mounting.cylinder_fit import corner_position, corner_state
    from nbt_mounting.cylinder_pattern import cylinder_geometry, touches_backing
    from nbt_model import AIR_NAMES

    diameter = proposal.get('diameter',13)
    core, ring = cylinder_geometry(diameter,proposal.get('seam_degrees',180))
    height = hi[1]-lo[1]+1
    if any(hi[i]-lo[i]+1 != diameter+2 for i in (0,2)) or not 1 <= height <= 64:
        raise ValueError('圆柱通铺目标框须等于外径×高度×外径，高度最多64格')
    size = (len(ring), height)
    period = proposal['size_uv']
    slack = size[0] % period[0]
    if slack:
        raise ValueError(f'圆柱闭合接缝不支持非整周期：周长 {size[0]} 格，U 周期 {period[0]} 格，余 {slack} 格；请另设独立收边方案或更换周期')
    unit,quality,shapes,_,ornament,sample = solve_repeat_unit(workspace,proposal)
    if set(shapes or {}) - {'slab','stairs'}:
        raise ValueError('圆柱连续铺排只支持整方块、楼梯和半砖的精确半格状态')
    def is_reserved(point):
        return point in reserved or reserved_position((point,),context_reserved) is not None

    missing = 0
    for x,z in core:
        for v in range(height):
            p = (lo[0]+x,lo[1]+v,lo[2]+z)
            value = model.get(p)
            cells,reason = collision_cells(value)
            if reason or len(cells) != 8:
                if value in AIR_NAMES and (p in protected or is_reserved(p)):
                    missing += 1
                else:
                    raise ValueError('原柱芯不完整：只有保护或留白范围内的空气开口可裁切连续铺排')
    positions = {}
    clipped = {}
    writes = {}
    for uv,phase,local in phased_cells(unit,period,size,anchor):
        u,v = uv
        face = ring[u]
        point = (lo[0]+face['x'],lo[1]+v,lo[2]+face['z'])
        host = (point[0]-face['dx'],point[1],point[2]-face['dz'])
        if point in protected:
            clipped[uv] = 'protected'
            continue
        if is_reserved(point):
            clipped[uv] = 'reserved'
            continue
        if model.get(host) in AIR_NAMES:
            clipped[uv] = 'masked_opening'
            continue
        if model.get(point) not in AIR_NAMES:
            raise ValueError(f'圆柱外饰位置已有方块，不能覆盖：{point}')
        value = transformed_state(local,face['turns'],None)
        if not touches_backing(value,face):
            raise ValueError(f'圆柱通铺方块未接触相应柱芯面：{point}')
        positions[uv] = (phase,local,point,value)
        writes[point] = value
    if not writes:
        raise ValueError('圆柱通铺裁切后没有可安装的饰面方块')
    connectors = {}
    clipped_connectors = set()
    ring_points = {(face['x'],face['z']) for face in ring}
    for uv,(_,local_a,point_a,value_a) in positions.items():
        u,v = uv
        end = ((u+1) % size[0],v)
        if end not in positions:
            continue
        left,right = ring[u],ring[end[0]]
        if abs(left['x']-right['x'])+abs(left['z']-right['z']) <= 1:
            continue
        _,local_b,point_b,value_b = positions[end]
        value = corner_state(local_a,local_b,value_a,value_b,ornament,shapes,left['turns'])
        if value is None:
            continue
        x,z = corner_position(left,right,core,ring_points)
        point = (lo[0]+x,lo[1]+v,lo[2]+z)
        if point in protected or is_reserved(point):
            clipped_connectors.add((uv,end))
            continue
        if not model.in_bounds(point) or model.get(point) not in AIR_NAMES or writes.get(point,value) != value:
            raise ValueError(f'圆柱转角连接被占用、越界或发生冲突：{point}')
        middle = half_cells({point:value})
        if not face_contact(half_cells({point_a:value_a}),middle) or not face_contact(middle,half_cells({point_b:value_b})):
            raise ValueError(f'圆柱转角半格连接不足：{uv} → {end}')
        writes[point] = value
        connectors[uv,end] = (point,value)
    counts = Counter()
    stairs = Counter()
    slabs = Counter()
    for value in writes.values():
        name,props = effective(value)
        family = 'stairs' if name.endswith('_stairs') else 'slab' if name.endswith('_slab') else 'full'
        counts[family] += 1
        if family == 'stairs':stairs[props['facing']+'/'+props['half']] += 1
        if family == 'slab':slabs[props['type']] += 1
    palette = sorted(set(writes.values()))
    indices = {value:i for i,value in enumerate(palette)}
    voxels = [[*[p[i]-lo[i] for i in range(3)],indices[value]] for p,value in sorted(writes.items())]
    compiled = dict(surface='cylinder', sample_sha256=sample['sha256'], shape_counts=dict(counts),
                    stair_orientations=dict(stairs),slab_orientations=dict(slabs),microfit=quality,
                    orientation_policy='fixed_cyclic_tangent_y_phase_and_surface_normal',
                    fitting={k:quality[k] for k in ('requested','matched','missing','extra','subcells_per_block')},
                    cylinder=dict(diameter=diameter,height=height,circumference_cells=size[0],seam_degrees=proposal.get('seam_degrees',180),
                                  axis='y',backing_blocks=len(core)*height-missing,masked_core_air=missing,
                                  ornament_blocks=len(writes),corner_connector_blocks=len({p for p,_ in connectors.values()})))
    return palette,voxels,writes,compiled,size,positions,clipped,connectors,clipped_connectors
