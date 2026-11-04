"""Plan connected, flat road footprints without changing the source model."""
from nbt_model import AIR_NAMES, state


def road_plan(model, operation, protected=()):
    from nbt_tools import xyz
    lo, hi = xyz(operation['lo'], True), xyz(operation['hi'], True)
    start, end = xyz(operation['start'], True), xyz(operation['end'], True)
    width, depth = operation.get('width', 3), operation.get('depth', 1)
    route = operation.get('route', 'straight')
    overwrite = operation.get('overwrite', False)
    if type(width) is not int or not 1 <= width <= 16 or type(depth) is not int or not 1 <= depth <= 8:
        raise ValueError('道路宽度须为1～16格，厚度须为1～8格')
    if route not in ('straight', 'x_first', 'z_first') or type(overwrite) is not bool:
        raise ValueError('道路路线或覆盖开关无效')
    if start[1] != end[1]:
        raise ValueError('平面道路起终点的Y须相同；Y表示路面方块高度')
    if any(not lo[i] <= p[i] <= hi[i] for p in (start, end) for i in range(3)):
        raise ValueError('道路起终点超出选区')
    value = state(operation.get('state', 'stone_bricks'))
    if value in AIR_NAMES:
        raise ValueError('道路材质须为实体方块')
    lower = (width-1)//2
    upper = width-1-lower
    footprint_lo = (min(start[0],end[0])-lower, start[1]-depth+1, min(start[2],end[2])-lower)
    footprint_hi = (max(start[0],end[0])+upper, start[1], max(start[2],end[2])+upper)
    if any(footprint_lo[i] < lo[i] or footprint_hi[i] > hi[i] for i in range(3)):
        raise ValueError('完整道路超出选区或模型边界；请增大选区或减小宽度、厚度')
    vertices = [start, end]
    if route != 'straight':
        corner = (end[0], start[1], start[2]) if route == 'x_first' else (start[0], start[1], end[2])
        vertices = [start, corner, end]
    centers = {start}
    for a, b in zip(vertices, vertices[1:]):
        count = max(abs(b[0]-a[0]), abs(b[2]-a[2]))
        previous = a
        for k in range(1, count+1):
            p = (round(a[0]+(b[0]-a[0])*k/count), a[1], round(a[2]+(b[2]-a[2])*k/count))
            # Include an elbow when both coordinates change, keeping width=1 connected.
            centers.add((p[0], p[1], previous[2])); centers.add(p); previous = p
    cells = {(x+dx, y-dy, z+dz) for x,y,z in centers
             for dx in range(-lower, width-lower) for dz in range(-lower, width-lower) for dy in range(depth)}
    if any(not model.in_bounds(p) or any(not lo[i] <= p[i] <= hi[i] for i in range(3)) for p in cells):
        raise ValueError('完整道路超出选区或模型边界；请增大选区或减小宽度、厚度')
    edits = [(p,value) for p in sorted(cells) if model.get(p) != value]
    protected = set(map(tuple, protected))
    if any(p in protected for p,_ in edits):
        raise ValueError('道路触及保护区，请调整路线')
    if not overwrite and any(model.get(p) not in AIR_NAMES for p,_ in edits):
        raise ValueError('道路位置已有方块；调整路线或显式允许覆盖路面')
    budget = operation.get('max_writes', 4096)
    if type(budget) is not int or budget < 0 or len(edits) > budget:
        raise ValueError('道路改动超过上限')
    return edits, dict(kind='auto_road', eligible=len(cells), changed=len(edits), route=route, width=width, depth=depth)
