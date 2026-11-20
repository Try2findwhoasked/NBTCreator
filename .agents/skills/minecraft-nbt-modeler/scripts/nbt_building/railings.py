"""Thin, explicitly oriented rail details; never floor-to-cap retaining walls."""
from collections import deque
from nbt_model import state
from nbt_registry import effective
from nbt_collision import collision_cells

DIRECTIONS={'north':(0,-1),'east':(1,0),'south':(0,1),'west':(-1,0)}
DEFAULT_POSTS={'baluster':'dark_oak_fence','lattice':'iron_bars',
               'horizontal':'nether_brick_fence','panel':'stone_bricks'}


def material(value, role):
    value=state(value)
    name,props=effective(value)
    if props.get('waterlogged')=='true':
        raise ValueError('扶手细部不能含水')
    cells,reason=collision_cells(value)
    if not reason and len(cells)==8:return value
    if role=='cap' and name.endswith('_slab') and props['type']=='bottom':return value
    if role=='cap' and name.endswith('_trapdoor') and props['half']=='bottom' and props['open']=='false' and props['powered']=='false':return value
    if role=='post' and (name.endswith(('_fence','_wall')) or name=='minecraft:iron_bars'):return value
    raise ValueError('扶手立柱使用完整方块、栅栏、石墙或铁栏杆；顶栏使用完整方块、底部半砖或关闭的底部活板门')


def _components(points):
    remaining=set(points)
    while remaining:
        seed=min(remaining);remaining.remove(seed)
        distances={seed:0};queue=deque([seed])
        while queue:
            x,z=queue.popleft()
            for dx,dz in DIRECTIONS.values():
                q=(x+dx,z+dz)
                if q in remaining:
                    remaining.remove(q);distances[q]=distances[(x,z)]+1;queue.append(q)
        yield distances


def _post(value, connected):
    name,props=effective(value)
    if name.endswith(('_fence','_wall')) or name=='minecraft:iron_bars':
        wall=name.endswith('_wall')
        props.update({key:('low' if wall else 'true') if key in connected else ('none' if wall else 'false') for key in DIRECTIONS})
        props['waterlogged']='false'
        if wall:props['up']='true'
    return state(dict(Name=name,Properties=props))


def compile_rails(points,height,pitch,profile,box,post=None,cap=None,open_infill=False,lower_to_tread=False):
    post=material(post or DEFAULT_POSTS[profile],'post')
    caps_enabled=cap is not None or profile not in ('lattice',)
    default_cap={'baluster':'dark_oak_trapdoor[half=bottom,open=false,powered=false,waterlogged=false]',
                 'horizontal':'iron_trapdoor[half=bottom,open=false,powered=false,waterlogged=false]',
                 'panel':'smooth_stone_slab','lattice':'smooth_stone_slab'}[profile]
    cap=material(cap or default_cap,'cap')
    blocks={};post_cells=set();horizontal_cells={};cap_cells=set();tops={};seats=[]
    for distances in _components(points):
        for (x,z),index in sorted(distances.items()):
            base=points[(x,z)];top=base+height-1
            tops[(x,z)]=top
            neighbors=[q for dx,dz in DIRECTIONS.values() if (q:=(x+dx,z+dz)) in points]
            bottom=max(1,min([base,*[points[q] for q in neighbors]])-1) if lower_to_tread else base
            straight=len(neighbors)==2 and neighbors[0][0]+neighbors[1][0]==2*x and neighbors[0][1]+neighbors[1][1]==2*z
            flat=all(points[q]==base for q in neighbors)
            newel=not straight or index%pitch==0
            if newel:seats.append([x,bottom,z])
            # Sloping columns each get their own spindle and cap support. Flat
            # horizontal bays keep only the newels, leaving long thin rails.
            spindle=profile!='horizontal' or not flat or newel or open_infill
            if profile=='panel' and not open_infill:
                for y in range(bottom,top):blocks[(x,y,z)]=post
            elif spindle:
                for y in range(bottom,top):
                    if profile=='baluster' and flat and not newel and y<top-1:
                        continue
                    blocks[(x,y,z)]=post;post_cells.add((x,y,z))
            elif not open_infill:
                axis='x' if neighbors[0][0]!=x else 'z'
                for y in sorted({bottom,top-1}):
                    blocks[(x,y,z)]=state(f'chain[axis={axis},waterlogged=false]')
                    horizontal_cells[(x,y,z)]=axis
            # One rail line follows the flights; light coping is confined to
            # level landings instead of adding a separate hat on every step.
            if caps_enabled and (not lower_to_tread or flat or profile=='panel'):
                blocks[(x,top,z)]=cap;cap_cells.add((x,top,z))
    # Explicit connection fields rotate with the component. Only connect members
    # actually present at this height; flat pickets leave the lower tier open.
    for p in post_cells:
        x,y,z=p;connected=[]
        if not open_infill:
            for direction,(dx,dz) in DIRECTIONS.items():
                q=(x+dx,y,z+dz)
                neighbor=(x+dx,z+dz)
                if q in post_cells or q in horizontal_cells:
                    if profile!='baluster' or y==tops[(x,z)]-1 or tops.get(neighbor)!=tops[(x,z)]:
                        connected.append(direction)
        blocks[p]=_post(blocks[p],connected)
    for p,value in sorted(blocks.items()):box(list(p),list(p),value)
    seat=state(('dark_oak_trapdoor' if profile=='baluster' else 'iron_trapdoor')+'[half=top,open=false,powered=false,waterlogged=false]')
    return dict(generator='reference_rails_v3',post_material=post,cap_material=cap if caps_enabled else None,support_material=seat,
                support_seats=seats,
                post_columns=len({(x,z) for x,_,z in post_cells}),
                cap_blocks=len(cap_cells),horizontal_detail_blocks=len(horizontal_cells),
                top='connected_arms_with_landing_caps' if lower_to_tread else 'level_coping',connections='explicit_authored_states',
                game_updates='not_checked')
