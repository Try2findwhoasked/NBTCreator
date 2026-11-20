"""Half-step stair/ramp candidates with flat turns and real collision checks."""
import math
from nbt_model import AIR_NAMES,state
from nbt_placement import finish_plan


def stair_plan(model,op,protected=()):
    from nbt_tools import xyz
    start=xyz(op['start'],True);end=xyz(op['end'],True)
    width=op.get('width',1);mode=op.get('mode','straight')
    if type(width) is not int or not 1<=width<=7: raise ValueError('Stair width must be 1..7')
    if end[1]<=start[1]: raise ValueError('Stair end feet must be above start feet')
    if mode=='straight': vertices=[start,end]
    elif mode=='switchback':
        flight=op.get('flight_length',10);gap=width+2
        if type(flight) is not int or flight<width+2: raise ValueError('Switchback flight too short')
        vertices=[start,(start[0]+flight,start[1],start[2]),(start[0]+flight,start[1],start[2]+gap),(start[0],end[1],start[2]+gap)]
        if end[0]!=vertices[-1][0] or end[2]!=vertices[-1][2]: raise ValueError('Switchback end XZ must match return flight')
    elif mode=='spiral':
        centre=xyz(op['centre'],True);radius=op.get('radius',4);turns=op.get('turns',1)
        if type(radius) is not int or radius<width+1 or type(turns) is not int or not 1<=turns<=8: raise ValueError('Invalid square spiral radius/turns')
        cx,_,cz=centre;corners=[(cx-radius,start[1],cz-radius),(cx+radius,start[1],cz-radius),(cx+radius,start[1],cz+radius),(cx-radius,start[1],cz+radius)]
        vertices=[corners[0]]+[corners[i%4] for i in range(1,4*turns+1)]
        if (start[0],start[2])!=(vertices[0][0],vertices[0][2]) or (end[0],end[2])!=(vertices[-1][0],vertices[-1][2]): raise ValueError('Spiral starts and ends at northwest ring corner')
    else: raise ValueError('Invalid stair mode')
    path=[];corners=set()
    for a,b in zip(vertices,vertices[1:]):
        dx,dz=b[0]-a[0],b[2]-a[2]
        if (dx==0)==(dz==0): raise ValueError('Stair flights must be nonzero and axis-aligned')
        n=abs(dx)+abs(dz); direction=(0 if dx==0 else (1 if dx>0 else -1),0 if dz==0 else (1 if dz>0 else -1))
        if path: corners.add(len(path)-1)
        else:path.append((a[0],a[2]))
        path.extend((a[0]+direction[0]*k,a[2]+direction[1]*k) for k in range(1,n+1))
    # A width-sized flat landing surrounds every turn. Endpoints are flat too.
    flat={i for c in corners|{0,len(path)-1} for i in range(max(0,c-width),min(len(path),c+width+1))}
    rising=[i for i in range(1,len(path)) if i not in flat]
    half_rise=2*(end[1]-start[1])
    if len(rising)<half_rise: raise ValueError('Insufficient run for half-step rise and flat landings')
    # Distribute rises evenly; never more than half a block per row.
    rise_at={rising[math.ceil(k*len(rising)/half_rise)-1] for k in range(1,half_rise+1)}
    cube=state(op.get('state','stone_bricks'));slab=state(op.get('slab_state','stone_brick_slab[type=bottom,waterlogged=false]'))
    from nbt_collision import FULL_CUBES,collision_cells,check_routes
    from nbt_registry import effective
    if effective(cube)[0].removeprefix('minecraft:') not in FULL_CUBES: raise ValueError('Stair full steps require known full cubes')
    cells,reason=collision_cells(slab)
    if reason or set(cells)!={(x,0,z) for x in (0,1) for z in (0,1)}: raise ValueError('Stair slab must be a supported bottom half slab')
    edits={};feet=[];height=start[1];lower=(width-1)//2
    for i,(x,z) in enumerate(path):
        if i in rise_at:height+=.5
        feet.append((x+.5,height,z+.5))
        a=path[max(0,i-1)];b=path[min(len(path)-1,i+1)]
        offsets=[(dx,dz) for dx in range(-lower,width-lower) for dz in range(-lower,width-lower)] if i in corners else ([(0,d) for d in range(-lower,width-lower)] if a[0]!=b[0] else [(d,0) for d in range(-lower,width-lower)])
        y=math.ceil(height)-1;v=cube if height==int(height) else slab
        for dx,dz in offsets:
            q=(x+dx,y,z+dz)
            if q in edits and edits[q]!=v: raise ValueError('Stair flights overlap; increase spacing or run')
            edits[q]=v
    lo,hi=xyz(op['lo'],True),xyz(op['hi'],True)
    if any(any(not lo[j]<=p[j]<=hi[j] for j in range(3)) for p in edits): raise ValueError('Complete stair exceeds selection')
    overwrite=op.get('overwrite',False)
    if type(overwrite) is not bool: raise ValueError('Overwrite must be boolean')
    if not overwrite and any(model.get(p) not in (v,*AIR_NAMES) for p,v in edits.items()): raise ValueError('Stair destination occupied')
    planned,report=finish_plan(model,op,edits,protected,eligible=len(edits),feet=feet,mode=mode)
    from nbt_assembly import Volume
    candidate=Volume(model.size);candidate.blocks=dict(model.blocks)
    for p,v in planned:candidate.put(p,v)
    # Verify each consecutive segment, so a shortcut cannot stand in for a flight.
    checks=[]
    for a,b in zip(feet,feet[1:]):
        check=check_routes(candidate,a,[b],max_poses=1000)
        if not check['passed']: raise ValueError('Stair clearance/support check failed at '+str(a)+' -> '+str(b))
        checks.append(dict(start=a,end=b,passed=True))
    report.update(route_segments=checks,runtime_verified=False)
    return planned,report
