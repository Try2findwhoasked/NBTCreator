"""Repair cylinder stair-step corners and verify real half-cube topology."""
from collections import deque
from itertools import product

from nbt_collision import collision_cells
from nbt_model import state
from nbt_registry import effective
from nbt_tools import transformed_state

SIX=((1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1))
ALL=tuple(p for p in product((-1,0,1),repeat=3) if p!=(0,0,0))


def components(points,steps=SIX):
    remaining=set(points);groups=[]
    while remaining:
        first=min(remaining);remaining.remove(first);queue=deque([first]);group=[]
        while queue:
            p=queue.popleft();group.append(p)
            for step in steps:
                q=tuple(a+b for a,b in zip(p,step))
                if q in remaining:remaining.remove(q);queue.append(q)
        groups.append(group)
    return groups


def half_cells(blocks):
    result=set()
    for p,value in blocks.items():
        cells,reason=collision_cells(value)
        if reason:raise ValueError('圆柱转角不支持未知碰撞形状')
        result.update(tuple(2*a+b for a,b in zip(p,c)) for c in cells)
    return result


def topology(cells):
    """Face connectivity and cubical-complex handles, including corner contacts."""
    if not cells:return dict(face_components=0,handles=0,cavities=0,half_cells=0)
    vertices=set();edges=set();faces=set()
    for x,y,z in cells:
        vertices.update((x+a,y+b,z+c) for a,b,c in product((0,1),repeat=3))
        for a,b in product((0,1),repeat=2):
            edges.update(((0,x,y+a,z+b),(1,x+a,y,z+b),(2,x+a,y+b,z)))
        for side in (0,1):faces.update(((0,x+side,y,z),(1,x,y+side,z),(2,x,y,z+side)))
    euler=len(vertices)-len(edges)+len(faces)-len(cells)
    lo=tuple(min(p[i] for p in cells)-1 for i in range(3));hi=tuple(max(p[i] for p in cells)+1 for i in range(3))
    air=set(product(*(range(lo[i],hi[i]+1) for i in range(3))))-cells
    cavities=sum(not any(any(p[i] in (lo[i],hi[i]) for i in range(3)) for p in group) for group in components(air))
    handles=len(components(cells,ALL))+cavities-euler
    if handles<0:raise ValueError('圆柱世界拓扑计算失败')
    return dict(face_components=len(components(cells)),handles=handles,cavities=cavities,half_cells=len(cells))


def prepare_unit(unit,core,ring,offset,width,height,material,shapes,reference):
    """Map one fitted unit, connecting only ink continuous in the source unit."""
    selected=[ring[(offset+u)%len(ring)] for u in range(width)]
    blocks={(selected[u]['x'],v,selected[u]['z']):transformed_state(value,selected[u]['turns'],None)
            for (u,v),value in unit.items()}
    ring_points={(face['x'],face['z']) for face in ring};bridges=set()
    for u in range(width-1):
        left,right=selected[u],selected[u+1]
        if abs(left['x']-right['x'])+abs(left['z']-right['z'])<=1:continue
        choices=[(left['x'],right['z']),(right['x'],left['z'])]
        candidates=[p for p in choices if p not in core and p not in ring_points]
        if len(candidates)!=1:raise ValueError('圆柱转角无法建立唯一外侧连接，请调整单元宽度或直径')
        x,z=candidates[0]
        for v in range(height):
            if (u,v) not in unit or (u+1,v) not in unit:continue
            a=set(collision_cells(unit[u,v])[0]);b=set(collision_cells(unit[u+1,v])[0])
            shared=[any((1,y,depth) in a and (0,y,depth) in b for depth in (0,1)) for y in (0,1)]
            if not any(shared):continue
            if all(shared):
                left_value=blocks[left['x'],v,left['z']];right_value=blocks[right['x'],v,right['z']]
                value=left_value if len(collision_cells(left_value)[0])==8 else right_value if len(collision_cells(right_value)[0])==8 else transformed_state(material,left['turns'],None)
            else:
                if not shapes or 'slab' not in shapes:raise ValueError('圆柱转角连接需要匹配的半砖，请在shapes提供slab或允许自动同材质半砖')
                name,props=effective(shapes['slab'])
                if not name.endswith('_slab') or props.get('waterlogged')!='false':raise ValueError('圆柱转角须使用未含水半砖')
                value=state(f'{name}[type={"bottom" if shared[0] else "top"},waterlogged=false]')
            point=(x,v,z)
            if point in blocks and blocks[point]!=value:raise ValueError('圆柱转角连接发生冲突')
            blocks[point]=value;bridges.add(point)
    cells=half_cells(blocks);actual=topology(cells)
    periodic=width==len(ring)
    if periodic:
        preserved=(actual['face_components']<=reference['face_components'] and actual['handles']>=reference['handles'] and actual['cavities']==reference['cavities'])
    else:
        preserved=all(actual[key]==reference[key] for key in ('face_components','handles','cavities'))
    if not preserved:
        raise ValueError(f'圆柱世界轮廓未保留单元拓扑：连接{reference["face_components"]}→{actual["face_components"]}、环孔{reference["handles"]}→{actual["handles"]}；请调整直径或单元')
    # Each real face-connected ornament group must reach a real core face.
    for group in components(cells):
        if not any(((p[0]+dx)//2,(p[2]+dz)//2) in core for p in group for dx,_,dz in SIX if dx or dz):
            raise ValueError('圆柱外饰存在未与柱芯面连接的孤立部件')
    return blocks,dict(source=reference,result=actual,corner_connector_blocks=len(bridges),
                       topology_preserved=True,periodic_boundary=periodic,
                       support='every_halfcell_face_component_reaches_core')
