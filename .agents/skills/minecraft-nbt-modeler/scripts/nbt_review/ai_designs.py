"""Check explicitly requested roof and stair constructions in the finished candidate."""
from nbt_building.roofs import roof_bounds, roof_surface
from nbt_collision import collision_cells


def xieshan(model, lower, upper):
    """Check the inset roof, both continuous eave seams and the two gable faces."""
    outer = roof_bounds(lower)
    inner = roof_bounds(upper)
    if not all(outer[i] < inner[i] and inner[i+2] < outer[i+2] for i in (0, 1)):
        return False
    across, along = (0, 1) if upper.get('ridge_axis', 'z') == 'z' else (1, 0)
    left, right = inner[across], inner[across+2]
    front, back = inner[along], inner[along+2]
    if right-left < 2 or back-front < 2:
        return False
    hip, gable = roof_surface(lower), roof_surface(upper)

    def xz(side, span):
        return (side, span) if across == 0 else (span, side)

    def face(point, half_y):
        x, z = point
        cells, reason = collision_cells(model.get((x, half_y//2, z)))
        return None if reason else {(a,c) for a,b,c in cells if b == half_y%2}

    def skin(point, surface):
        top = int(2*surface(*point))
        return bool(face(point, top-1)) and face(point, top)==set()

    def joined(point, bottom, top):
        # One vertical half-cell column must reach from the lower skin into the
        # upper one. A floating slab or an unknown collision cannot bridge it.
        columns = {(0,0),(0,1),(1,0),(1,1)}
        for y in range(int(2*bottom)-1, int(2*top)):
            columns &= face(point, y) or set()
            if not columns:
                return False
        return True

    # Outer hipped slopes must remain visible outside all four inset edges.
    mid = [(inner[i]+inner[i+2])//2 for i in (0,1)]
    for axis in (0,1):
        for end in (axis,axis+2):
            edge, inset = list(mid), list(mid)
            edge[axis], inset[axis] = outer[end], inner[end]
            if hip(*edge) >= hip(*inset) or not skin(edge, hip):
                return False
    for side in (left,right):
        for span in range(front,back+1):
            point = xz(side,span)
            bottom, top = hip(*point), gable(*point)
            if not 0 <= top-bottom <= upper.get('thickness',1) or not joined(point,bottom,top):
                return False
    # Closed triangular end faces below a raised ridge. Test each column, not
    # just the roof operation labels or a single centre support.
    for span in (front,back):
        ridge = xz((left+right)//2,span)
        if gable(*ridge) <= max(gable(*xz(left,span)),hip(*ridge)+.5):
            return False
        for side in range(left,right+1):
            point = xz(side,span)
            bottom, top = hip(*point), gable(*point)
            if top < bottom or not skin(point,gable) or not joined(point,bottom,top):
                return False
    # Later steps may have removed the panel or cut through the ridge.
    return all(skin(xz(side,span),gable) for span in range(front,back+1)
               for side in range(left,right+1))


def check_designs(model, operations, required, context):
    active = [op for op in operations if op.get('enabled',True)]
    if 'xieshan_roof' in required:
        roofs = [op for op in active if op['kind']=='auto_roof']
        hips = [op for op in roofs if op.get('roof') in ('hip','curved_hip')]
        ends = [op for op in roofs if op.get('roof','gable') in ('gable','gambrel')]
        if not any(xieshan(model,lower,upper) for lower in hips for upper in ends):
            raise ValueError('歇山顶几何未通过：上部双坡须四面内收，两侧檐边连续接触下部四坡，两端山花从下坡填至双坡屋脊。请在完整候选中核对。')
    if 'spiral_stair' in required:
        from nbt_building.stairs import stair_plan
        error = '缺少有效的方环旋梯及起止脚位'
        defaults = dict(radius=4,width=1,turns=1)
        for op in active:
            if op['kind']!='auto_stairs' or op.get('mode')!='spiral':
                continue
            if any(op.get(key,default)!=value for key,default in defaults.items()
                   if (value:=context.get('spiral_parameters',{}).get(key)) is not None):
                continue
            try:
                edits, _ = stair_plan(model,op)
                if not edits:
                    break
                error = '后续步骤改变了踏步'
            except ValueError as failure:
                error = str(failure)
        else:
            raise ValueError('螺旋梯最终踏步或逐段静态通路未通过：'+error)
