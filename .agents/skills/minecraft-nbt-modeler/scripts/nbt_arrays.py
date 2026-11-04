"""Snapshot radial and arc-length path arrays; no arbitrary state rotations."""
import math
from nbt_model import AIR_NAMES
from nbt_placement import finish_plan


def array_placements(operation):
    from nbt_tools import xyz,positive
    mode=operation.get('mode','path'); orient=operation.get('orientation','fixed')
    if orient not in ('fixed','cardinal'): raise ValueError('Array orientation must be fixed or cardinal')
    result=[]
    if mode=='radial':
        centre=xyz(operation['centre']);radius=positive(operation['radius']);count=operation.get('count',8)
        angle=operation.get('start_angle',0);sweep=operation.get('sweep_angle',360)
        if type(count) is not int or not 1<=count<=128 or any(type(v) not in (int,float) or not math.isfinite(v) for v in (angle,sweep)) or not 0<abs(sweep)<=360:
            raise ValueError('Invalid radial array count or angles')
        denominator=count if abs(sweep)==360 else max(count-1,1)
        for i in range(count):
            a=math.radians(angle+sweep*i/denominator)
            p=(round(centre[0]+radius*math.sin(a)),round(centre[1]),round(centre[2]-radius*math.cos(a)))
            result.append((p,round(a/(math.pi/2))%4 if orient=='cardinal' else 0))
    elif mode=='path':
        points=[xyz(p) for p in operation['points']]
        if not 2<=len(points)<=128: raise ValueError('Array path needs 2..128 points')
        spacing=positive(operation.get('spacing',4)); margins=operation.get('end_margins',[0,0])
        if len(margins)!=2 or any(type(v) not in (int,float) or not math.isfinite(v) or v<0 for v in margins): raise ValueError('Invalid path end margins')
        lengths=[math.dist(a,b) for a,b in zip(points,points[1:])]
        if any(v<1e-8 for v in lengths): raise ValueError('Path has coincident points')
        total=sum(lengths); distance=margins[0]; limit=total-margins[1]
        if distance>limit: raise ValueError('Margins consume array path')
        while distance<=limit+1e-8:
            if len(result)>=128: raise ValueError('Array exceeds 128 placements')
            remaining=distance
            for a,b,length in zip(points,points[1:],lengths):
                if remaining<=length+1e-8:
                    t=min(1,remaining/length);p=tuple(round(a[j]+(b[j]-a[j])*t) for j in range(3))
                    turns=round(math.atan2(b[0]-a[0],-(b[2]-a[2]))/(math.pi/2))%4 if orient=='cardinal' else 0
                    if orient=='cardinal' and a[0]==b[0] and a[2]==b[2]: raise ValueError('Vertical path has no horizontal facing')
                    result.append((p,turns));break
                remaining-=length
            distance+=spacing
    else: raise ValueError('Invalid array mode')
    if len({p for p,_ in result})!=len(result): raise ValueError('Spacing produces duplicate voxel anchors')
    return result


def array_plan(model,operation,protected=()):
    from nbt_tools import xyz,transformed_state
    lo,hi=xyz(operation['lo'],True),xyz(operation['hi'],True)
    anchor=xyz(operation.get('source_anchor',lo),True)
    if any(not lo[i]<=anchor[i]<=hi[i] for i in range(3)): raise ValueError('Array source anchor outside source')
    overwrite=operation.get('overwrite',False); air=operation.get('include_air',False)
    if type(overwrite) is not bool or type(air) is not bool: raise ValueError('Array switches must be boolean')
    placements=array_placements(operation);edits={}
    source={(x,y,z):model.get((x,y,z)) for x in range(lo[0],hi[0]+1) for y in range(lo[1],hi[1]+1) for z in range(lo[2],hi[2]+1)}
    for destination,turns in placements:
        for p,v in source.items():
            if v in AIR_NAMES and not air: continue
            x,y,z=(p[i]-anchor[i] for i in range(3))
            for _ in range(turns): x,z=-z,x
            q=(destination[0]+x,destination[1]+y,destination[2]+z)
            value=transformed_state(v,turns,None) if turns else v
            if not model.in_bounds(q): raise ValueError('Array exceeds model')
            if q in edits and edits[q]!=value: raise ValueError('Array instances conflict')
            if not overwrite and model.get(q) not in (value,*AIR_NAMES): raise ValueError('Array destination occupied')
            edits[q]=value
    return finish_plan(model,operation,edits,protected,placements=[dict(anchor=p,quarter_turns=t) for p,t in placements],orientation=operation.get('orientation','fixed'))
