"""Thin, explicitly oriented rail details; never floor-to-cap retaining walls."""
from collections import deque
from nbt_model import state
from nbt_registry import effective
from nbt_collision import collision_cells

DIRECTIONS={'north':(0,-1),'east':(1,0),'south':(0,1),'west':(-1,0)}
DEFAULT_POSTS={'baluster':'andesite_wall','lattice':'dark_oak_fence',
               'horizontal':'spruce_fence','panel':'stone_bricks'}


def material(value, role):
    value=state(value)
    name,props=effective(value)
    if props.get('waterlogged')=='true':
        raise ValueError('扶手细部不能含水')
    cells,reason=collision_cells(value)
    if not reason and len(cells)==8:return value
    if role=='cap' and name.endswith('_slab') and props['type']=='bottom':return value
    if role=='post' and (name.endswith(('_fence','_wall')) or name=='minecraft:iron_bars'):return value
    raise ValueError('扶手立柱使用完整方块、栅栏、石墙或铁栏杆；顶栏使用完整方块或底部半砖')


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


def compile_rails(points,height,pitch,profile,box,post=None,cap=None,open_infill=False):
    default_post=post is None
    post=material(post or DEFAULT_POSTS[profile],'post')
    cap=material(cap or 'smooth_stone_slab[type=bottom,waterlogged=false]','cap')
    blocks={};post_cells=set();horizontal_cells={};cap_cells=set()
    for distances in _components(points):
        for (x,z),index in sorted(distances.items()):
            base=points[(x,z)];top=base+height-1
            neighbors=[q for dx,dz in DIRECTIONS.values() if (q:=(x+dx,z+dz)) in points]
            straight=len(neighbors)==2 and neighbors[0][0]+neighbors[1][0]==2*x and neighbors[0][1]+neighbors[1][1]==2*z
            flat=all(points[q]==base for q in neighbors)
            newel=not straight or index%pitch==0
            # Sloping columns each get their own spindle and cap support. Flat
            # horizontal bays keep only the newels, leaving long thin rails.
            spindle=profile!='horizontal' or not flat or newel or open_infill
            if profile=='panel' and not open_infill:
                for y in range(base,top):blocks[(x,y,z)]=post
            elif spindle:
                for y in range(base,top):
                    if profile=='lattice' and flat and not newel and y<top-1 and (index+y-base)%pitch!=0:
                        continue
                    value='dark_oak_fence' if default_post and profile=='baluster' and not newel else post
                    blocks[(x,y,z)]=value;post_cells.add((x,y,z))
            elif not open_infill:
                axis='east' if neighbors[0][0]!=x else 'south'
                for y in sorted({base,top-1}):
                    blocks[(x,y,z)]=state(f'end_rod[facing={axis}]')
                    horizontal_cells[(x,y,z)]=axis
            blocks[(x,top,z)]=cap;cap_cells.add((x,top,z))
    # Connection fields are explicit and rotate with the component. Balusters
    # intentionally have no lateral arms; lattice and horizontal newels join
    # only material actually present at the same height.
    for p in post_cells:
        x,y,z=p;connected=[]
        if profile!='baluster' and not open_infill:
            for direction,(dx,dz) in DIRECTIONS.items():
                q=(x+dx,y,z+dz)
                if q in post_cells or q in horizontal_cells:connected.append(direction)
        blocks[p]=_post(blocks[p],connected)
    for p,value in sorted(blocks.items()):box(list(p),list(p),value)
    return dict(generator='thin_rails_v1',post_material=post,cap_material=cap,
                post_columns=len({(x,z) for x,_,z in post_cells}),
                cap_blocks=len(cap_cells),horizontal_detail_blocks=len(horizontal_cells),
                top='stepped_slab_segments',connections='explicit_authored_states',
                game_updates='not_checked')
