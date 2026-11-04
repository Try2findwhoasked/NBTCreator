"""Integer-grid alignment, anchor snapping and conservative ground snapping."""
import math
from nbt_model import AIR_NAMES
from nbt_placement import translated_plan


def alignment_plan(model, operation, protected=()):
    from nbt_tools import xyz
    lo,hi=xyz(operation['lo'],True),xyz(operation['hi'],True)
    mode=operation.get('mode','align')
    if mode=='anchor':
        anchor=xyz(operation['source_anchor'],True); target=xyz(operation['target_anchor'],True)
        if any(not lo[i]<=anchor[i]<=hi[i] for i in range(3)): raise ValueError('Source anchor outside source region')
        offset=tuple(target[i]-anchor[i] for i in range(3))
    elif mode=='align':
        target_lo,target_hi=xyz(operation['target_lo'],True),xyz(operation['target_hi'],True)
        axes=operation.get('axes',['center','min','center'])
        if len(axes)!=3 or any(a not in ('min','center','max','keep') for a in axes): raise ValueError('Invalid alignment axes')
        if any(a>b for a,b in zip(target_lo,target_hi)): raise ValueError('Invalid target box')
        offset=[]
        for i,a in enumerate(axes):
            d=0 if a=='keep' else target_lo[i]-lo[i] if a=='min' else target_hi[i]-hi[i] if a=='max' else (target_lo[i]+target_hi[i]-lo[i]-hi[i])/2
            if d!=int(d): raise ValueError('Center alignment falls between voxel cells; use a compatible target or anchor')
            offset.append(int(d))
    elif mode=='ground':
        destination=xyz(operation['destination'],True)
        offset=[destination[0]-lo[0],0,destination[2]-lo[2]]
        bottom=[]
        for x in range(lo[0],hi[0]+1):
            for z in range(lo[2],hi[2]+1):
                ys=[y for y in range(lo[1],hi[1]+1) if model.get((x,y,z)) not in AIR_NAMES]
                if ys: bottom.append((x,min(ys),z))
        if not bottom: raise ValueError('Ground snapping needs solid geometry')
        from nbt_registry import effective
        from nbt_collision import FULL_CUBES
        heights=[]
        for x,y,z in bottom:
            tx,tz=x+offset[0],z+offset[2]
            if not 0<=tx<model.size[0] or not 0<=tz<model.size[2]: raise ValueError('Ground destination exceeds model')
            found=None
            for gy in range(min(destination[1],model.size[1]-1),-1,-1):
                q=(tx,gy,tz)
                if operation.get('move',False) and all(lo[i]<=q[i]<=hi[i] for i in range(3)): continue
                value=model.get(q)
                if value in AIR_NAMES: continue
                name,_=effective(value)
                if name.removeprefix('minecraft:') not in FULL_CUBES: raise ValueError('Ground snapping requires known full-cube support')
                found=gy+1-y;break
            if found is None: raise ValueError('Ground support missing')
            heights.append(found)
        if len(set(heights))!=1: raise ValueError('Uneven ground would leave unsupported geometry; prepare a foundation')
        offset[1]=heights[0]
    else: raise ValueError('Invalid alignment mode')
    return translated_plan(model,operation,offset,protected)
