"""Bounded terrain-following A* road candidates with clearance and cut/fill limits."""
import heapq
from nbt_model import AIR,AIR_NAMES,state
from nbt_placement import finish_plan


def terrain_road_plan(model,op,protected=()):
    from nbt_tools import xyz
    from nbt_collision import FULL_CUBES,check_routes
    from nbt_registry import effective
    lo,hi=xyz(op['lo'],True),xyz(op['hi'],True)
    start,end=xyz(op['start'],True),xyz(op['end'],True)
    width=op.get('width',1);cut=op.get('max_cut',0);fill=op.get('max_fill',0);span=op.get('max_bridge_span',0)
    if type(width) is not int or not 1<=width<=7 or any(type(v) is not int or not 0<=v<=16 for v in (cut,fill,span)):
        raise ValueError('Invalid terrain road width/cut/fill/bridge limit')
    allowed={state(v) for v in op.get('terrain_states',['grass_block','dirt','stone'])}
    if not allowed or any(effective(v)[0].removeprefix('minecraft:') not in FULL_CUBES for v in allowed): raise ValueError('Terrain states must be known full cubes')
    value=state(op.get('state','stone_bricks'))
    if effective(value)[0].removeprefix('minecraft:') not in FULL_CUBES: raise ValueError('Road state must be a known full cube')
    stair_base=op.get('stair_state','stone_brick_stairs')
    # Validate supported stairs once, including actual registry defaults.
    name,props=effective(state(stair_base))
    if not name.endswith('_stairs'): raise ValueError('Road transition material must be stairs')
    protected=set(map(tuple,protected));lower=(width-1)//2
    cache={}
    def terrain(x,z):
        if (x,z) in cache:return cache[x,z]
        answer=None
        for y in range(hi[1],lo[1]-1,-1):
            v=model.get((x,y,z))
            if v in AIR_NAMES:continue
            answer=(y,v in allowed);break
        cache[x,z]=answer;return answer
    def valid(x,z):return lo[0]+lower<=x<=hi[0]-(width-1-lower) and lo[2]+lower<=z<=hi[2]-(width-1-lower)
    for p in (start,end):
        t=terrain(p[0],p[2])
        if not valid(p[0],p[2]) or not lo[1]<=p[1]<=hi[1] or t is None or not t[1] or t[0]!=p[1]:raise ValueError('Road endpoints must match sampled terrain surface')
    def footprint(x,y,z):
        edits={};bridged=False
        for dx in range(-lower,width-lower):
            for dz in range(-lower,width-lower):
                tx,tz=x+dx,z+dz;t=terrain(tx,tz)
                if t is None:
                    if span==0:return None
                    bottom=y;bridged=True
                else:
                    gy,ok=t
                    if not ok or gy-y>cut or y-gy>fill:return None
                    bottom=min(y,gy+1)
                if y<lo[1] or y+2>=model.size[1]:return None
                for yy in range(bottom,y+1):edits[tx,yy,tz]=value
                if t is not None:
                    for yy in range(y+1,t[0]+1):
                        if model.get((tx,yy,tz)) not in allowed:return None
                        edits[tx,yy,tz]=AIR
                for yy in (y+1,y+2):
                    q=(tx,yy,tz)
                    if edits.get(q,model.get(q)) not in AIR_NAMES:return None
        if any(not model.in_bounds(p) or any(not lo[i]<=p[i]<=hi[i] for i in range(3)) or p in protected and model.get(p)!=v for p,v in edits.items()):return None
        return edits,bridged
    # Highest eligible terrain defines elevation; gaps use the start deck elevation.
    first=(*start,0);queue=[(0,0,first)];parent={first:None};cost={first:0};found=None;visited=0
    while queue:
        _,g,node=heapq.heappop(queue)
        if g!=cost.get(node):continue
        visited+=1
        if visited>100000:raise ValueError('Terrain road search limit reached')
        x,y,z,gap=node
        if (x,y,z)==end:found=node;break
        for dx,dz in ((1,0),(-1,0),(0,1),(0,-1)):
            tx,tz=x+dx,z+dz
            if not valid(tx,tz):continue
            t=terrain(tx,tz)
            if t is not None and not t[1]:continue
            ty=t[0] if t else start[1]
            if abs(ty-y)>1:continue
            candidate=footprint(tx,ty,tz)
            if candidate is None:continue
            next_gap=gap+1 if candidate[1] else 0
            if next_gap>span:continue
            nxt=(tx,ty,tz,next_gap);ng=g+1+abs(ty-y)*2+(2 if next_gap else 0)
            if ng<cost.get(nxt,float('inf')):
                cost[nxt]=ng;parent[nxt]=node
                h=abs(tx-end[0])+abs(tz-end[2])+abs(ty-end[1])
                heapq.heappush(queue,(ng+h,ng,nxt))
    if found is None:raise ValueError('No terrain road within clearance, protection and slope limits')
    path=[]
    while found is not None:path.append(found[:3]);found=parent[found]
    path.reverse();edits={};bridge=[]
    for x,y,z in path:
        result=footprint(x,y,z)
        if result is None:raise ValueError('Road start footprint blocked')
        local,is_bridge=result
        if is_bridge:bridge.append((x,y,z))
        for p,v in local.items():
            if p in edits and edits[p]!=v:raise ValueError('Road width creates conflicting cuts/fills')
            edits[p]=v
    # A one-block height transition needs the higher row's stair facing uphill.
    facings={};dirs={(1,0):'east',(-1,0):'west',(0,1):'south',(0,-1):'north'}
    for a,b in zip(path,path[1:]):
        if a[1]==b[1]:continue
        high,low=(a,b) if a[1]>b[1] else (b,a)
        dx,dz=high[0]-low[0],high[2]-low[2];facing=dirs[dx,dz]
        for d in range(-lower,width-lower):
            p=(high[0]+(d if dz else 0),high[1],high[2]+(d if dx else 0))
            if p in facings and facings[p]!=facing:raise ValueError('Terrain peak needs a wider flat landing')
            facings[p]=facing
    for p,facing in facings.items():edits[p]=state(dict(Name=name,Properties=dict(props,facing=facing,half='bottom',shape='straight',waterlogged='false')))
    planned,report=finish_plan(model,op,edits,protected,eligible=len(edits),path=path,bridge_cells=bridge,search_nodes=visited,runtime_verified=False)
    from nbt_assembly import Volume
    candidate=Volume(model.size);candidate.blocks=dict(model.blocks)
    for p,v in planned:candidate.put(p,v)
    # Check the actual route segment-by-segment, including every incline.
    for a,b in zip(path,path[1:]):
        feet=lambda p:(p[0]+.5,p[1]+1,p[2]+.5)
        check=check_routes(candidate,feet(a),[feet(b)],max_poses=2000)
        if not check['passed']:raise ValueError('Terrain road actual walking check failed near '+str(a))
    report['walking_checked']=True
    return planned,report
