"""Bounded terrain-following A* road candidates with clearance and cut/fill limits."""
import heapq
from collections import Counter
from nbt_model import AIR,AIR_NAMES,state
from nbt_geometry.placement import finish_plan


class TerrainRoadError(ValueError):
    def __init__(self, message, **details):
        super().__init__(message)
        self.details = details


def terrain_road_plan(model,op,protected=(),*,preserve_endpoints=False,bridge_water=False,excluded_columns=()):
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
    endpoints={start,end} if preserve_endpoints else set()
    excluded_columns=set(excluded_columns)
    rejections=Counter()
    samples={}
    def reject(reason,p):
        rejections[reason]+=1
        examples=samples.setdefault(reason,[])
        if len(examples)<8 and p not in examples:examples.append(p)

    cache={}
    def terrain(x,z):
        if (x,z) in cache:return cache[x,z]
        answer=None
        for y in range(hi[1],lo[1]-1,-1):
            v=model.get((x,y,z))
            if v in AIR_NAMES:continue
            is_water=v.split('[',1)[0]=='minecraft:water'
            fixed_deck=(x,y,z) in endpoints and v.split('[',1)[0].removeprefix('minecraft:') in FULL_CUBES and 'waterlogged=true' not in v
            answer=(y,'terrain' if v in allowed or fixed_deck else 'water' if is_water else 'obstacle');break
        cache[x,z]=answer;return answer
    def valid(x,z):return lo[0]+lower<=x<=hi[0]-(width-1-lower) and lo[2]+lower<=z<=hi[2]-(width-1-lower)
    for p in (start,end):
        if not valid(p[0],p[2]) or not lo[1]<=p[1]<=hi[1]:
            raise TerrainRoadError('Road endpoint is outside the solve bounds',position=p)
        t=terrain(p[0],p[2])
        if t!=(p[1],'terrain'):
            raise TerrainRoadError('Road endpoints must match sampled terrain surface',position=p,surface=t)
    def footprint(x,y,z):
        edits={};bridged=False
        for dx in range(-lower,width-lower):
            for dz in range(-lower,width-lower):
                tx,tz=x+dx,z+dz;t=terrain(tx,tz)
                if (tx,tz) in excluded_columns:
                    return reject('building_footprint',(tx,y,tz))
                if t is None:
                    if span==0:return reject('unsupported_gap',(tx,y,tz))
                    bottom=y;bridged=True
                elif t[1]=='water':
                    if not bridge_water or span==0 or t[0]>=y:
                        return reject('water_requires_dry_bridge_deck',(tx,t[0],tz))
                    bottom=y;bridged=True
                else:
                    gy,kind=t
                    if kind!='terrain':return reject('obstacle',(tx,gy,tz))
                    if gy-y>cut or y-gy>fill:return reject('road_cut_fill_limit',(tx,gy,tz))
                    bottom=min(y,gy+1)
                if y<lo[1] or y+2>=model.size[1] or preserve_endpoints and y+2>hi[1]:
                    return reject('clearance_bounds',(tx,y,tz))
                for yy in range(bottom,y+1):
                    p=(tx,yy,tz)
                    edits[p]=model.get(p) if p in endpoints else value
                if t is not None and t[1]=='terrain':
                    for yy in range(y+1,t[0]+1):
                        if model.get((tx,yy,tz)) not in allowed:return reject('obstacle',(tx,yy,tz))
                        edits[tx,yy,tz]=AIR
                for yy in (y+1,y+2):
                    q=(tx,yy,tz)
                    if edits.get(q,model.get(q)) not in AIR_NAMES:return reject('clearance',q)
        for p,v in edits.items():
            if not model.in_bounds(p) or any(not lo[i]<=p[i]<=hi[i] for i in range(3)):
                return reject('write_bounds',p)
            if p in protected and model.get(p)!=v:return reject('protected_or_reserved',p)
        return edits,bridged
    # Highest eligible terrain defines elevation; gaps use the start deck elevation.
    first=(*start,0);queue=[(0,0,first)];parent={first:None};cost={first:0};found=None;visited=0
    if footprint(*start) is None:
        raise TerrainRoadError('Road start footprint blocked',position=start,rejections=samples,rejection_counts=dict(rejections))
    while queue:
        _,g,node=heapq.heappop(queue)
        if g!=cost.get(node):continue
        visited+=1
        if visited>100000:raise TerrainRoadError('Terrain road search limit reached',search_nodes=visited)
        x,y,z,gap=node
        if (x,y,z)==end:found=node;break
        for dx,dz in ((1,0),(-1,0),(0,1),(0,-1)):
            tx,tz=x+dx,z+dz
            if not valid(tx,tz):continue
            t=terrain(tx,tz)
            ty=t[0] if t and t[1]!='water' else start[1]
            candidate=footprint(tx,ty,tz)
            if candidate is None:continue
            if abs(ty-y)>1:
                reject('slope',(tx,ty,tz));continue
            if ty!=y and ((tx,ty,tz) if ty>y else (x,y,z)) in endpoints:
                reject('fixed_endpoint_needs_level_connection',(tx,ty,tz));continue
            next_gap=gap+1 if candidate[1] else 0
            if next_gap>span:
                reject('bridge_span',(tx,ty,tz));continue
            nxt=(tx,ty,tz,next_gap);ng=g+1+abs(ty-y)*2+(2 if next_gap else 0)
            if ng<cost.get(nxt,float('inf')):
                cost[nxt]=ng;parent[nxt]=node
                h=abs(tx-end[0])+abs(tz-end[2])+abs(ty-end[1])
                heapq.heappush(queue,(ng+h,ng,nxt))
    if found is None:
        raise TerrainRoadError('No terrain road within clearance, protection and slope limits',
                               rejections=samples,rejection_counts=dict(rejections),search_nodes=visited)
    path=[]
    while found is not None:path.append(found[:3]);found=parent[found]
    path.reverse();edits={};bridge=[];water=[]
    for x,y,z in path:
        result=footprint(x,y,z)
        if result is None:raise TerrainRoadError('Road footprint blocked',position=(x,y,z),rejections=samples)
        local,is_bridge=result
        if is_bridge:bridge.append((x,y,z))
        for bx,bz in sorted({(p[0],p[2]) for p in local}):
            surface=terrain(bx,bz)
            if surface and surface[1]=='water':water.append((bx,surface[0],bz))
        for p,v in local.items():
            if p in edits and edits[p]!=v:raise TerrainRoadError('Road width creates conflicting cuts/fills',position=p)
            edits[p]=v
    # A one-block height transition needs the higher row's stair facing uphill.
    facings={};dirs={(1,0):'east',(-1,0):'west',(0,1):'south',(0,-1):'north'}
    for a,b in zip(path,path[1:]):
        if a[1]==b[1]:continue
        high,low=(a,b) if a[1]>b[1] else (b,a)
        dx,dz=high[0]-low[0],high[2]-low[2];facing=dirs[dx,dz]
        for d in range(-lower,width-lower):
            p=(high[0]+(d if dz else 0),high[1],high[2]+(d if dx else 0))
            if p in facings and facings[p]!=facing:raise TerrainRoadError('Terrain peak needs a wider flat landing',position=p)
            facings[p]=facing
    for p,facing in facings.items():
        v=state(dict(Name=name,Properties=dict(props,facing=facing,half='bottom',shape='straight',waterlogged='false')))
        if p in protected and model.get(p)!=v:
            raise TerrainRoadError('Road stairs touch protected geometry',position=p)
        edits[p]=v
    max_writes=op.get('max_writes',4096)
    if type(max_writes) is int and sum(model.get(p)!=v for p,v in edits.items())>max_writes:
        raise TerrainRoadError('Road exceeds write budget',limit=max_writes)
    planned,report=finish_plan(model,op,edits,protected,eligible=len(edits),path=path,bridge_cells=bridge,
                               water_cells=sorted(set(water)),search_nodes=visited,runtime_verified=False)
    from nbt_assembly import Volume
    candidate=Volume(model.size);candidate.blocks=dict(model.blocks)
    for p,v in planned:candidate.put(p,v)
    # Check the actual route segment-by-segment, including every incline.
    walking_path=[]
    for a,b in zip(path,path[1:]):
        feet=lambda p:(p[0]+.5,p[1]+1,p[2]+.5)
        check=check_routes(candidate,feet(a),[feet(b)],max_poses=2000)
        if not check['passed']:
            raise TerrainRoadError('Terrain road actual walking check failed',position=a,next_position=b,route=check)
        if preserve_endpoints:
            leg=check['targets'][0]['path']
            walking_path.extend(leg if not walking_path else leg[1:])
    if preserve_endpoints:
        report['walking_path']=walking_path or [[start[0]+.5,start[1]+1,start[2]+.5]]
    report['walking_checked']=True
    return planned,report
