"""Named half-cell contact surfaces and bounded horizontal beam relations."""
from copy import deepcopy
from itertools import product

FACES = {'up': (1, 1), 'down': (1, -1), 'east': (0, 1), 'west': (0, -1), 'south': (2, 1), 'north': (2, -1)}


class InterfaceError(ValueError):
    def __init__(self, code, message, interface, owner, **evidence):
        super().__init__(f'{owner}.{interface}：{message}')
        self.code = code
        self.conflicts = [dict(instance=owner, interface=interface, **evidence)]


def obstacle_height(value):
    from nbt_collision import bounded_obstacle, effective, TALL_OBSTACLES
    if not bounded_obstacle(value):
        return None
    return 3 if effective(value)[0].removeprefix('minecraft:') in TALL_OBSTACLES else 2


def obstacle_cells(pos, height):
    return ((2*pos[0]+x, 2*pos[1]+y, 2*pos[2]+z)
            for x in range(2) for y in range(height) for z in range(2))


def check_interface_geometry(model, positions, surface, *, check_external=False):
    """Check the bound faces against current geometry without using envelopes as support."""
    from nbt_collision import collision_cells

    faces = set(map(tuple, surface['faces_half']))
    normal = surface['normal']
    outward = {p: tuple(p[i]+normal[i] for i in range(3)) for p in faces}
    adjacent = set(outward.values())
    bounds = surface.get('region_half')
    relevant = {tuple(v//2 for v in p) for p in faces | adjacent}
    candidates = positions
    if check_external:
        candidates = positions | relevant | {(x,y-1,z) for x,y,z in relevant}
    cells = set()
    uncertain = []
    for pos in sorted(candidates):
        value = model.get(pos)
        shape, reason = collision_cells(value)
        if not reason:
            if pos in positions and pos in relevant:
                cells.update(tuple(2*p+h for p,h in zip(pos, half)) for half in shape)
            continue
        height = obstacle_height(value)
        if (height is None and (pos in positions or pos in relevant)
                or height is not None and any(
                    p in faces or p in adjacent or
                    (pos in positions and bounds and all(a<=v<=b for v,a,b in zip(p,bounds['lo'],bounds['hi'])))
                    for p in obstacle_cells(pos,height))):
            uncertain.append(dict(pos=list(pos),state=value,reason=reason))
    missing = sorted(p for p in faces if p not in cells or outward[p] in cells)
    return dict(passed=not missing and not uncertain,
                missing_faces_half=[list(p) for p in missing[:32]], unknown_shapes=uncertain)


def compile_interfaces(definitions, local_voxels, size, turns, origin, owner='envelope'):
    from nbt_composition.object_scene import halfcells
    from nbt_collision import collision_cells
    if not definitions:
        return {}
    exact = {}
    uncertain = {}
    for pos, voxel in local_voxels.items():
        value = voxel[0]
        _, reason = collision_cells(value)
        if reason:
            uncertain[pos] = (value, reason, obstacle_height(value))
        else:
            exact[pos] = voxel
    cells = halfcells(exact)
    result = {}
    for definition in definitions:
        name, face = definition['id'], definition['face']
        if name in result:
            raise InterfaceError('INTERFACE_DUPLICATE', '安装接口ID重复', name, owner)
        lo, hi = definition['lo'], definition['hi']
        if any(type(a) is not int or type(b) is not int or a < 0 or a > b or b >= n for a, b, n in zip(lo, hi, size)):
            raise InterfaceError('INTERFACE_BOUNDS', '安装接口范围超出构件', name, owner, bounds=dict(lo=lo, hi=hi))
        # Regions are authored in the original local frame. Transform their
        # half-cells with exactly the same rotation as actual block placement.
        def in_region(p):
            x, y, z = p
            a, b = 2 * size[0], 2 * size[2]
            if turns % 2:
                a, b = b, a
            # local_voxels have already been rotated; invert to test the region.
            for _ in range((-turns) % 4):
                x, z, a, b = b - 1 - z, x, b, a
            return all(2 * lo[i] <= v < 2 * (hi[i] + 1) for i, v in enumerate((x, y, z)))
        region = {p for p in cells if in_region(p)}
        direction = face
        for _ in range(turns):
            direction = {'north': 'east', 'east': 'south', 'south': 'west', 'west': 'north'}.get(direction, direction)
        axis, sign = FACES[direction]
        adjacent = {tuple(v + (sign if i == axis else 0) for i, v in enumerate(p)) for p in region} - cells
        for pos, (value, reason, height) in uncertain.items():
            if height is None or any(
                in_region(q) or q in adjacent
                for q in obstacle_cells(pos,height)
            ):
                raise InterfaceError('INTERFACE_UNSUPPORTED_SHAPE', '精确接口遇到未支持的碰撞形状',
                                     name, owner, pos=[pos[i]+origin[i] for i in range(3)],
                                     state=value, reason=reason, bounds=dict(lo=lo, hi=hi), coordinate_space='scene')
        if not region:
            raise InterfaceError('INTERFACE_EMPTY', '安装接口没有实际几何', name, owner, bounds=dict(lo=lo, hi=hi))
        extreme = (max if sign > 0 else min)(p[axis] for p in region)
        faces = {p for p in region if p[axis] == extreme and tuple(v + (sign if i == axis else 0) for i, v in enumerate(p)) not in cells}
        if not faces:
            raise InterfaceError('INTERFACE_OCCLUDED', '安装接口没有真实暴露面', name, owner, bounds=dict(lo=lo, hi=hi))
        world = sorted([p[i] + 2 * origin[i] for i in range(3)] for p in faces)
        corners = []
        for x,y,z in product(*zip((2*v for v in lo),(2*v+1 for v in hi))):
            a,b=2*size[0],2*size[2]
            for _ in range(turns):
                x,z,a,b=b-1-z,x,b,a
            corners.append((x+2*origin[0],y+2*origin[1],z+2*origin[2]))
        region_half=dict(lo=[min(p[i] for p in corners) for i in range(3)],
                         hi=[max(p[i] for p in corners) for i in range(3)])
        plane = extreme + (1 if sign > 0 else 0) + 2 * origin[axis]
        normal = [sign if i == axis else 0 for i in range(3)]
        result[name] = dict(id=name, face=direction, normal=normal, plane_half=plane, faces_half=world,region_half=region_half,
            area=len(world) / 4, tangent_axes=[i for i in range(3) if i != axis],
            lo_half=[min(p[i] for p in world) for i in range(3)], hi_half=[max(p[i] for p in world) for i in range(3)])
    return result


def interface_contact(cells, interface):
    """Every child component must touch the specified face along its normal."""
    from nbt_composition.object_scene import SIX
    normal = interface['normal']
    required = {tuple(p[i] + normal[i] for i in range(3)) for p in interface['faces_half']}
    remaining = set(cells)
    while remaining:
        first = remaining.pop()
        queue, found = [first], first in required
        while queue:
            p = queue.pop()
            for step in SIX:
                q = tuple(p[i] + step[i] for i in range(3))
                if q in remaining:
                    remaining.remove(q)
                    queue.append(q)
                    found |= q in required
        if not found:
            return False
    return True


def selected_interface(completed, reference):
    target, name = reference['object'], reference['interface']
    try:
        return dict(deepcopy(completed[target]['interfaces'][name]), object=target)
    except KeyError:
        raise InterfaceError('INTERFACE_MISSING', '安装接口不存在', name, target) from None


def span_recipe(node, recipe, completed):
    """Resolve an explicit horizontal rectangular beam; never stretch an asset."""
    relation = node['span']
    left = selected_interface(completed, relation['from'])
    right = selected_interface(completed, relation['to'])
    if recipe['tool'] != 'span_beam' or node.get('quarter_turns', 0):
        raise ValueError('跨接使用 span_beam 配方和显式世界轴，不叠加旋转')
    args = recipe['arguments']
    if set(args) - {'width', 'height', 'material', 'name'}:
        raise ValueError('跨梁含未知参数')
    width, height = args.get('width', 3), args.get('height', 1)
    if any(type(v) is not int or not 1 <= v <= 32 for v in (width, height)):
        raise ValueError('跨梁宽高须为1～32格')
    if left['face'] != 'up' or right['face'] != 'up':
        raise ValueError('水平跨梁需要两个朝上的承托接口')
    if left['plane_half'] != right['plane_half']:
        raise ValueError('跨梁两端承托面高度不同：' + relation['from']['object'] + ' → ' + relation['to']['object'])
    if left['plane_half'] % 2:
        raise ValueError('此整块跨梁需要整数高度承托面，不能舍入半格接口')
    axis = 0 if relation['axis'] == 'x' else 2
    tangent = 2 if axis == 0 else 0
    center_left = (left['lo_half'][tangent] + left['hi_half'][tangent] + 1) / 2
    center_right = (right['lo_half'][tangent] + right['hi_half'][tangent] + 1) / 2
    if center_left != center_right:
        raise ValueError('跨梁承托面未沿声明轴对齐')
    low = min(left['lo_half'][axis], right['lo_half'][axis]) // 2
    high = max(left['hi_half'][axis], right['hi_half'][axis]) // 2
    side = (center_left - width) / 2
    if side != int(side):
        raise ValueError('跨梁截面无法在整数方块网格中居中')
    size = [1, height, 1]
    size[axis], size[tangent] = high - low + 1, width
    origin = [0, left['plane_half'] // 2, 0]
    origin[axis], origin[tangent] = low, int(side)
    arguments = dict(name=args.get('name', '接口跨梁'), size=size, anchor=[0, 0, 0], operations=[dict(
        kind='box', label='双端接口跨梁', classification='body', lo=[0, 0, 0], hi=[n-1 for n in size], state=args.get('material', 'stone_bricks'))])
    # Both seats are validated against their designated surfaces after assembly.
    return dict(tool='structure', arguments=arguments), origin, [left, right]
