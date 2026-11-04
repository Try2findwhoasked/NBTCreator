"""Atomic snapshot placements shared by alignment and array tools."""
from nbt_model import AIR, AIR_NAMES


def finish_plan(model, operation, edits, protected=(), **report):
    from nbt_tools import xyz
    lo,hi=xyz(operation['lo'],True),xyz(operation['hi'],True)
    for p in edits:
        if not model.in_bounds(p): raise ValueError('Placement exceeds model')
    edits={p:v for p,v in edits.items() if model.get(p)!=v}
    if set(edits) & set(map(tuple,protected)): raise ValueError('Placement touches protected geometry')
    budget=operation.get('max_writes',4096)
    if type(budget) is not int or budget<0 or len(edits)>budget: raise ValueError('Placement write budget exceeded')
    return sorted(edits.items()),dict(kind=operation['kind'],changed=len(edits),**report)


def translated_plan(model, operation, offset, protected=()):
    from nbt_tools import xyz
    lo,hi=xyz(operation['lo'],True),xyz(operation['hi'],True)
    move=operation.get('move',False); air=operation.get('include_air',False); overwrite=operation.get('overwrite',False)
    if any(type(v) is not bool for v in (move,air,overwrite)): raise ValueError('Placement flags must be boolean')
    source={ (x,y,z):model.get((x,y,z)) for x in range(lo[0],hi[0]+1)
             for y in range(lo[1],hi[1]+1) for z in range(lo[2],hi[2]+1)}
    edits={p:AIR for p in source} if move else {}
    for p,v in source.items():
        if v in AIR_NAMES and not air: continue
        q=tuple(p[i]+offset[i] for i in range(3))
        if not model.in_bounds(q): raise ValueError('Placement exceeds model')
        if not overwrite and not (move and q in source) and model.get(q) not in (v,*AIR_NAMES):
            raise ValueError('Placement destination occupied')
        edits[q]=v
    return finish_plan(model,operation,edits,protected,offset=list(offset),eligible=len(source))
