"""Bounded connected/surface selection; planners never mutate the model."""
from collections import deque
from nbt_model import AIR_NAMES, state

DIRECTIONS = {'east': (1,0,0), 'west': (-1,0,0), 'up': (0,1,0),
              'down': (0,-1,0), 'south': (0,0,1), 'north': (0,0,-1)}


def select_voxels(model, operation):
    from nbt_tools import xyz
    lo, hi = xyz(operation['lo'], True), xyz(operation['hi'], True)
    if not model.in_bounds(lo) or not model.in_bounds(hi) or any(a>b for a,b in zip(lo,hi)):
        raise ValueError('Selection bounds exceed model')
    import math
    if math.prod(b-a+1 for a,b in zip(lo,hi)) > 2_000_000:
        raise ValueError('Selection exceeds 2 million cells')
    mode = operation.get('selection', 'connected')
    match = operation.get('match', 'state')
    thickness = operation.get('thickness', 1)
    if mode not in ('connected','surface','connected_surface') or match not in ('state','solid'):
        raise ValueError('Invalid selection mode or matching rule')
    if type(thickness) is not int or not 1 <= thickness <= 16:
        raise ValueError('Selection thickness must be 1..16')
    faces = operation.get('faces', list(DIRECTIONS))
    if not isinstance(faces, list) or not faces or any(f not in DIRECTIONS for f in faces):
        raise ValueError('Selection faces must be nonempty direction names')
    seed = xyz(operation['seed_position'], True) if mode != 'surface' else None
    inside = lambda p: all(lo[i] <= p[i] <= hi[i] for i in range(3))
    if seed is not None and (not inside(seed) or model.get(seed) in AIR_NAMES):
        raise ValueError('Selection seed must be a solid inside bounds')
    allowed = {state(v) for v in operation['from_states']} if 'from_states' in operation else None
    source = model.get(seed) if seed is not None else None
    eligible = set()
    for x in range(lo[0],hi[0]+1):
        for y in range(lo[1],hi[1]+1):
            for z in range(lo[2],hi[2]+1):
                p=(x,y,z); value=model.get(p)
                if value in AIR_NAMES or (allowed is not None and value not in allowed): continue
                if seed is not None and match == 'state' and value != source: continue
                eligible.add(p)
    candidates = eligible
    if mode != 'connected':
        candidates = {p for p in eligible if any(
            not model.in_bounds(q) or model.get(q) in AIR_NAMES
            for d in (DIRECTIONS[f] for f in faces)
            for q in [tuple(p[i]+d[i] for i in range(3))])}
    if seed is not None:
        if seed not in candidates: raise ValueError('Selection seed is not on an eligible surface')
        chosen={seed}; queue=deque([seed])
        while queue:
            p=queue.popleft()
            for d in DIRECTIONS.values():
                q=tuple(p[i]+d[i] for i in range(3))
                if q in candidates and q not in chosen: chosen.add(q); queue.append(q)
    else: chosen=set(candidates)
    # Thicken only within the selected source solids; never bridge across air.
    frontier=set(chosen)
    if mode != 'connected':
        for _ in range(thickness-1):
            frontier={tuple(p[i]+d[i] for i in range(3)) for p in frontier for d in DIRECTIONS.values()} & eligible - chosen
            chosen.update(frontier)
    return sorted(chosen)


def selection_plan(model, operation, protected=()):
    points=select_voxels(model,operation)
    value=state(operation.get('state','stone_bricks'))
    edits=[(p,value) for p in points if model.get(p)!=value]
    if set(p for p,_ in edits) & set(map(tuple,protected)):
        raise ValueError('Selection touches protected geometry')
    budget=operation.get('max_writes',4096)
    if type(budget) is not int or budget<0 or len(edits)>budget:
        raise ValueError('Selection write budget exceeded')
    return edits,dict(kind='selection_replace',eligible=len(points),changed=len(edits))
