"""Connected masonry weathering; plans edits without mutating the whole master.

The CLI delegates to nbt_refine's reviewed-master workflow. This module never
infers user approval, writes to a world, or processes individual delivery parts.
"""
import argparse
from collections import deque
import hashlib
import json
import math
from pathlib import Path
import random

from nbt_collision import collision_cells
from nbt_model import AIR, AIR_NAMES, compound, state


DELTAS = ((1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1))
HORIZONTAL = tuple(d for d in DELTAS if d[1] == 0)


def neighbors(p, horizontal=False):
    return [tuple(p[i]+d[i] for i in range(3)) for d in (HORIZONTAL if horizontal else DELTAS)]


def _point(value):
    if not isinstance(value,(list,tuple)) or len(value)!=3 or any(type(v) is not int for v in value):
        raise ValueError('Weathering bounds need three integer coordinates')
    return tuple(value)


def _fraction(config,key,default):
    value=config.get(key,default)
    if type(value) not in (float,int) or not math.isfinite(value) or not 0<=value<=1:
        raise ValueError(f'{key} must be a finite fraction in [0,1]')
    return value


def _integer(config,key,default,lo,hi):
    value=config.get(key,default)
    if type(value) is not int or not lo<=value<=hi:
        raise ValueError(f'{key} must be an integer in [{lo},{hi}]')
    return value


def _range(config,key,default):
    value=config.get(key,default)
    if (not isinstance(value,(list,tuple)) or len(value)!=2 or
            any(type(v) is not int for v in value) or not 2<=value[0]<=value[1]<=512):
        raise ValueError(f'{key} must be [minimum,maximum], 2 <= minimum <= maximum <= 512')
    return tuple(value)


def _full(value):
    cells,reason=collision_cells(value)
    return reason is None and len(cells)==8


def _material(value):
    result=state(value)
    # Restrict weathering materials to known vanilla full cubes without states.
    # Stateful stairs/slabs must not silently lose their shape in a repaint.
    if '[' in result or not _full(result):
        raise ValueError('Weathering source/moss/crack materials must be known plain full cubes')
    return result


def _rng(seed,channel):
    digest=hashlib.sha256(f'{seed}:{channel}'.encode()).digest()
    return random.Random(int.from_bytes(digest,'big'))


def _ring(group,width):
    grown=set(group)
    for _ in range(width):
        # Include corner blocks so the cracked rim is a connected contour,
        # rather than four disconnected strips around a rectangular depression.
        grown.update((x+dx,y,z+dz) for x,y,z in tuple(grown)
                     for dx in (-1,0,1) for dz in (-1,0,1))
    return grown-set(group)


def components(points,horizontal=False):
    """Observable connected components, also used by the synthetic regression."""
    remaining=set(points);result=[]
    while remaining:
        start=min(remaining);remaining.remove(start);group={start};pending=deque([start])
        while pending:
            for q in neighbors(pending.popleft(),horizontal):
                if q in remaining:
                    remaining.remove(q);group.add(q);pending.append(q)
        result.append(group)
    return result


def _groups(pool,target,sizes,rng,*,linear=False,horizontal=False,
            straightness=.8,branch_chance=.12,accept=None):
    """Connected frontier growth or persistent walks; never scatter a remainder.

    Each accepted group has >= minimum size. Failed anchors are exhausted once;
    tiny disconnected islands/blocked remnants are reported as a shortfall.
    """
    available=set(pool);anchors=sorted(pool);rng.shuffle(anchors)
    chosen=[];count=0
    for anchor in anchors:
        if count+sizes[0]>target:
            break
        if anchor not in available:
            continue
        size=min(rng.randint(*sizes),target-count)
        group={anchor};order=[anchor];current=anchor;previous=None
        frontier=set(neighbors(anchor,horizontal)) & available - group
        while len(group)<size and frontier:
            if linear:
                options=sorted(set(neighbors(current,horizontal)) & available - group)
                if (not options or rng.random()<branch_chance) and len(group)>1:
                    branches=[p for p in order if set(neighbors(p,horizontal)) & available - group]
                    if branches:
                        current=rng.choice(branches);previous=None
                        options=sorted(set(neighbors(current,horizontal)) & available - group)
                if not options:
                    break
                ahead=None if previous is None else tuple(2*current[i]-previous[i] for i in range(3))
                q=ahead if ahead in options and rng.random()<straightness else rng.choice(options)
                previous,current=current,q
            else:
                # Favor shared edges over tendrils, with irregular boundaries.
                q=max(sorted(frontier),key=lambda p:
                      sum(n in group for n in neighbors(p,horizontal)) + rng.random()*1.8
                      - .06*sum((p[i]-anchor[i])**2 for i in range(3)))
            group.add(q);order.append(q);frontier.discard(q)
            frontier.update(set(neighbors(q,horizontal)) & available - group)
        if len(group)<sizes[0]:
            available.discard(anchor)
            continue
        reserved=accept(group) if accept else set()
        if reserved is None:
            continue
        chosen.append(group);count+=len(group)
        available.difference_update(group|reserved)
    return chosen


def weathering_plan(model,operation,protected=()):
    """Return (sorted edits, measured report), leaving model/wall mask untouched.

    Ratios are budgets over the original eligible surface/floor. Floors run
    first, then connected cracks, then moss; mandatory damaged-floor rims take
    precedence over a smaller crack budget. All random channels share global
    coordinates and are independent of dict/set order or NBT storage cuts.
    """
    supported={'kind','label','classification','lo','hi','from_states','seed','moss','cracks','floor'}
    if set(operation)-supported:
        raise ValueError('Unknown weathering fields: '+str(sorted(set(operation)-supported)))
    if operation.get('kind','weathering')!='weathering':
        raise ValueError('Expected kind=weathering')
    lo,hi=_point(operation['lo']),_point(operation['hi'])
    if any(lo[i]>hi[i] for i in range(3)) or not model.in_bounds(lo) or not model.in_bounds(hi):
        raise ValueError('Weathering box must be ordered and inside the whole master')
    seed=operation.get('seed',0)
    if type(seed) is not int:
        raise ValueError('seed must be an integer')
    raw_states=operation.get('from_states',['stone_bricks'])
    if not isinstance(raw_states,list) or not raw_states:
        raise ValueError('from_states must be a nonempty list of full-cube states')
    allowed={_material(v) for v in raw_states}
    configs={}
    keys=dict(moss={'fraction','patch_size','state'},
              cracks={'fraction','length','straightness','branch_chance','state'},
              floor={'fraction','levels','slab_share','patch_size','pit_depth','rim_width','slab_state'})
    for name in keys:
        value=operation.get(name,{})
        if not isinstance(value,dict) or set(value)-keys[name]:
            raise ValueError(f'Invalid {name} configuration or unknown fields')
        configs[name]=value
    moss,cracks,floor=(configs[k] for k in ('moss','cracks','floor'))
    moss_fraction=_fraction(moss,'fraction',.12);crack_fraction=_fraction(cracks,'fraction',.06)
    floor_fraction=_fraction(floor,'fraction',0)
    moss_sizes=_range(moss,'patch_size',(12,40));crack_sizes=_range(cracks,'length',(6,18))
    floor_sizes=_range(floor,'patch_size',(2,6))
    straightness=_fraction(cracks,'straightness',.8);branch_chance=_fraction(cracks,'branch_chance',.12)
    slab_share=_fraction(floor,'slab_share',.65)
    depth=_integer(floor,'pit_depth',1,1,8);rim_width=_integer(floor,'rim_width',1,1,3)
    moss_state=_material(moss.get('state','mossy_stone_bricks'))
    crack_state=_material(cracks.get('state','cracked_stone_bricks'))
    if moss_state in allowed or crack_state in allowed or moss_state==crack_state:
        raise ValueError('Source, moss and cracked states must be distinct to measure ratios')
    slab_state=state(floor.get('slab_state','stone_brick_slab[type=bottom,waterlogged=false]'))
    slab=compound(slab_state)
    # An explicit vanilla slab allowlist avoids inventing nonexistent cracked slabs.
    valid_slabs={'stone_brick_slab','mossy_stone_brick_slab','stone_slab','smooth_stone_slab',
                 'cobblestone_slab','mossy_cobblestone_slab','andesite_slab','polished_andesite_slab',
                 'deepslate_brick_slab','deepslate_tile_slab','cobbled_deepslate_slab',
                 'polished_deepslate_slab','brick_slab','mud_brick_slab','nether_brick_slab',
                 'red_nether_brick_slab','polished_blackstone_brick_slab','polished_blackstone_slab',
                 'blackstone_slab','end_stone_brick_slab','sandstone_slab','cut_sandstone_slab',
                 'smooth_sandstone_slab','red_sandstone_slab','cut_red_sandstone_slab',
                 'smooth_red_sandstone_slab','quartz_slab','smooth_quartz_slab','prismarine_slab',
                 'prismarine_brick_slab','dark_prismarine_slab'}
    if (slab['Name'].removeprefix('minecraft:') not in valid_slabs or
            slab.get('Properties')!={'type':'bottom','waterlogged':'false'}):
        raise ValueError('slab_state must be a supported dry bottom slab with explicit properties')
    levels=floor.get('levels',[])
    if (not isinstance(levels,list) or any(type(y) is not int or not lo[1]<=y<=hi[1] for y in levels)
            or len(set(levels))!=len(levels) or (floor_fraction>0 and not levels)):
        raise ValueError('Nonzero floor fraction requires explicit floor block Y levels inside the box')
    protected={_point(p) for p in protected}
    inside=lambda p: model.in_bounds(p) and all(lo[i]<=p[i]<=hi[i] for i in range(3))
    surface={p for p,v in model.blocks.items() if inside(p) and p not in protected and v in allowed
             and any(model.in_bounds(q) and model.get(q) in AIR_NAMES for q in neighbors(p))}
    floors={p for p in surface if p[1] in levels and
            all(model.in_bounds((p[0],p[1]+dy,p[2])) and
                model.get((p[0],p[1]+dy,p[2])) in AIR_NAMES for dy in (1,2))}
    edits={};damaged=set();rims=set();floor_groups={'slabs':[],'pits':[]}
    floor_target=round(len(floors)*floor_fraction)
    slab_target=round(floor_target*slab_share);pit_target=floor_target-slab_target

    def floor_accept(group,pit):
        rim=_ring(group,rim_width)
        if not rim<=floors or (group|rim)&(damaged|rims):
            return None
        pending={}
        for p in sorted(group):
            x,y,z=p
            if pit:
                bottom=(x,y-depth,z)
                if not model.in_bounds(bottom) or not _full(model.get(bottom)):
                    return None
                for d in range(depth):
                    q=(x,y-d,z)
                    if not inside(q) or q in protected or (model.get(q) not in allowed|AIR_NAMES):
                        return None
                    if any(n not in {(v[0],y-d,v[2]) for v in group if v[1]==y}
                           and (not model.in_bounds(n) or not _full(model.get(n))) for n in neighbors(q,True)):
                        return None
                    pending[q]=AIR
            else:
                bottom=(x,y-1,z)
                if (not model.in_bounds(bottom) or not _full(model.get(bottom)) or
                        any(not model.in_bounds(n) or not _full(model.get(n)) for n in neighbors(p,True))):
                    return None
                pending[p]=slab_state
        edits.update(pending);damaged.update(group);rims.update(rim)
        edits.update({p:crack_state for p in rim})
        return rim

    floor_pool={p for p in floors if _ring({p},rim_width)<=floors}
    for key,target in (('pits',pit_target),('slabs',slab_target)):
        floor_groups[key]=_groups(floor_pool-damaged-rims,target,floor_sizes,_rng(seed,key),horizontal=True,
                                 accept=lambda group,pit=(key=='pits'):floor_accept(group,pit))
    crack_target=round(len(surface)*crack_fraction)
    crack_groups=_groups(surface-damaged-rims,max(0,crack_target-len(rims)),crack_sizes,
                         _rng(seed,'cracks'),linear=True,straightness=straightness,branch_chance=branch_chance)
    crack_points=set().union(*crack_groups) if crack_groups else set()
    edits.update({p:crack_state for p in crack_points})
    moss_target=round(len(surface)*moss_fraction)
    moss_groups=_groups(surface-damaged-rims-crack_points,moss_target,moss_sizes,_rng(seed,'moss'))
    moss_points=set().union(*moss_groups) if moss_groups else set()
    edits.update({p:moss_state for p in moss_points})
    # No support/base voxel is changed, including when another floor level is
    # present beneath an upper deck. Check the combined plan, not only each pit.
    for p in damaged:
        support=(p[0],p[1]-(depth if edits[p] in AIR_NAMES else 1),p[2])
        if support in edits and not _full(edits[support]):
            raise ValueError('Combined floor damage would remove another depression support')
    if any(p in protected or not inside(p) for p in edits):
        raise ValueError('Weathering exceeded its box/protection mask')
    edits={p:v for p,v in edits.items() if model.get(p)!=v}

    def measured(target,actual,denominator,groups):
        return dict(target_blocks=target,actual_blocks=actual,eligible_blocks=denominator,
                    actual_fraction=actual/denominator if denominator else 0,
                    shortfall=max(0,target-actual),group_sizes=[len(g) for g in groups])

    report=dict(seed=seed,surface_blocks=len(surface),floor_blocks=len(floors),
        moss=measured(moss_target,len(moss_points),len(surface),moss_groups),
        cracks=measured(crack_target,len(crack_points|rims),len(surface),crack_groups),
        floor=measured(floor_target,len(damaged),len(floors),floor_groups['slabs']+floor_groups['pits']),
        changed_blocks=len(edits),runtime_verified=False,
        ratio_policy='original_eligible_surface_or_floor; rim_cracks_are_a_mandatory_lower_bound; no_scattered_fill')
    report['cracks'].update(rim_blocks=len(rims),extended_blocks=len(crack_points),
                            rim_excess=max(0,len(rims)-crack_target))
    report['floor'].update(slab_blocks=sum(map(len,floor_groups['slabs'])),
                           pit_columns=sum(map(len,floor_groups['pits'])),pit_depth=depth,
                           slab_target=slab_target,pit_target=pit_target)
    return sorted(edits.items()),report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--review',type=Path,required=True)
    parser.add_argument('--operation',type=Path,required=True,help='One weathering operation JSON')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--style-note',required=True)
    args=parser.parse_args()
    operation=json.loads(args.operation.read_text(encoding='utf-8-sig'))
    operation.setdefault('kind','weathering');operation.setdefault('label','Connected masonry weathering')
    from nbt_refine import refine
    result=refine(args.review,dict(style_note=args.style_note,operations=[operation]),args.output)
    print(json.dumps(dict(state=result['state'],changed_blocks=result['changed_blocks'],
                          operations=result['operations']),ensure_ascii=False))


if __name__=='__main__':
    main()
