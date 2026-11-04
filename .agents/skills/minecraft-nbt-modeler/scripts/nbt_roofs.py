"""Parametric gable, hip, gambrel and elliptical dome roof skins."""
import math
from nbt_model import AIR_NAMES,state
from nbt_placement import finish_plan


def roof_plan(model,op,protected=()):
    from nbt_tools import xyz
    from nbt_registry import effective
    from nbt_collision import FULL_CUBES,collision_cells
    lo,hi=xyz(op['lo'],True),xyz(op['hi'],True)
    footprint=op.get('footprint',[[lo[0],lo[2]],[hi[0],hi[2]]])
    if not isinstance(footprint,list) or len(footprint)!=2 or any(not isinstance(p,list) or len(p)!=2 or any(type(v) is not int for v in p) for p in footprint):raise ValueError('Roof footprint needs two integer XZ corners')
    eaves=op.get('eaves',0);thickness=op.get('thickness',1);rise=op.get('rise',4);axis=op.get('ridge_axis','z');kind=op.get('roof','gable');finish=op.get('finish','slabs')
    if type(eaves) is not int or not 0<=eaves<=8 or type(thickness) is not int or not 1<=thickness<=8 or type(rise) not in (int,float) or not math.isfinite(rise) or rise<=0:raise ValueError('Invalid roof eaves/thickness/rise')
    if axis not in ('x','z') or kind not in ('gable','hip','gambrel','dome') or finish not in ('blocks','slabs','stairs'):raise ValueError('Invalid roof profile or finish')
    x0,z0=footprint[0];x1,z1=footprint[1]
    if x0>=x1 or z0>=z1:raise ValueError('Roof footprint must have positive area')
    x0-=eaves;z0-=eaves;x1+=eaves;z1+=eaves
    if x0<lo[0] or z0<lo[2] or x1>hi[0] or z1>hi[2]:raise ValueError('Roof eaves exceed selection')
    cube=state(op.get('state','stone_bricks'));slab=state(op.get('slab_state','stone_brick_slab[type=bottom,waterlogged=false]'))
    if effective(cube)[0].removeprefix('minecraft:') not in FULL_CUBES:raise ValueError('Roof base material must have full-cube collision')
    cells,reason=collision_cells(slab)
    if reason or set(cells)!={(x,0,z) for x in (0,1) for z in (0,1)}:raise ValueError('Roof slab must be a supported bottom slab')
    stair_name,stair_props=effective(state(op.get('stair_state','stone_brick_stairs')))
    if not stair_name.endswith('_stairs'):raise ValueError('Roof stair material must be stairs')
    bf=op.get('break_fraction',.5);bh=op.get('break_height',.75)
    if any(type(v) not in (int,float) or not math.isfinite(v) or not 0<v<1 for v in (bf,bh)):raise ValueError('Gambrel break parameters must be (0,1)')
    cx,cz=(x0+x1+1)/2,(z0+z1+1)/2;rx,rz=(x1-x0+1)/2,(z1-z0+1)/2
    tops={}
    for x in range(x0,x1+1):
        for z in range(z0,z1+1):
            nx,nz=abs((x+.5-cx)/rx),abs((z+.5-cz)/rz)
            if kind=='dome':
                d=nx*nx+nz*nz
                if d>1:continue
                t=math.sqrt(max(0,1-d))
            else:
                t=1-(max(nx,nz) if kind=='hip' else nx if axis=='z' else nz)
                if kind=='gambrel':t=t/bf*bh if t<=bf else bh+(t-bf)/(1-bf)*(1-bh)
            height=lo[1]+1+rise*t
            tops[x,z]=math.ceil(height) if finish in ('blocks','stairs') else math.ceil(height*2)/2
    edits={};directions=[('north',0,-1),('east',1,0),('south',0,1),('west',-1,0)]
    for (x,z),top in tops.items():
        y=math.ceil(top)-1;value=cube if top==int(top) else slab
        if finish=='stairs':
            higher=[i for i,(_,dx,dz) in enumerate(directions) if tops.get((x+dx,z+dz),top)>top]
            if kind=='hip' and not higher:
                dx=1 if x+.5<cx else -1;dz=1 if z+.5<cz else -1
                if tops.get((x+dx,z+dz),top)>top:
                    higher=[1 if dx>0 else 3,2 if dz>0 else 0]
            if len(higher)==1 or len(higher)==2 and (higher[0]-higher[1])%2:
                index=higher[0];shape='straight'
                if len(higher)==2:shape='outer_left' if higher[1]==(index-1)%4 else 'outer_right'
                value=state(dict(Name=stair_name,Properties=dict(stair_props,facing=directions[index][0],half='bottom',shape=shape,waterlogged='false')))
        edits[x,y,z]=value
        for depth in range(1,thickness):edits[x,y-depth,z]=cube
    if any(any(not lo[i]<=p[i]<=hi[i] for i in range(3)) for p in edits):raise ValueError('Complete roof exceeds selection height')
    overwrite=op.get('overwrite',False)
    if type(overwrite) is not bool:raise ValueError('Roof overwrite must be boolean')
    if not overwrite and any(model.get(p) not in (v,*AIR_NAMES) for p,v in edits.items()):raise ValueError('Roof destination occupied')
    return finish_plan(model,op,edits,protected,eligible=len(edits),roof=kind,finish=finish,runtime_verified=False,structural_support_verified=False)
