"""Fit small ornament units before placement; preserve visible topology."""
from collections import deque
from math import prod
from pathlib import Path

import numpy as np
from PIL import Image,ImageOps

from nbt_collision import collision_cells
from nbt_bitmap_topology import topology as bitmap_topology
from nbt_model import state
from nbt_ornament_sample import sample_image,silhouette_options,resize_sample
from nbt_registry import effective
from nbt_tools import transformed_state


def regions(mask,foreground=True):
    """Use complementary 8-connected ink and 4-connected background."""
    height,width=mask.shape;points=list(zip(*np.nonzero(mask if foreground else ~mask)));remaining=set(points)
    steps=((-1,0),(1,0),(0,-1),(0,1))
    if foreground:steps+=((-1,-1),(-1,1),(1,-1),(1,1))
    groups=[]
    for first in points:
        if first not in remaining:continue
        remaining.remove(first);queue=deque([first]);group=[];edge=False
        while queue:
            y,x=queue.popleft();group.append((int(y),int(x)));edge|=y in (0,height-1) or x in (0,width-1)
            for dy,dx in steps:
                neighbor=(y+dy,x+dx)
                if neighbor in remaining:remaining.remove(neighbor);queue.append(neighbor)
        if foreground or not edge:groups.append(group)
    return groups


def companions(material,surface,provided):
    if provided is not None:
        if not provided:raise ValueError('微型拟合shapes不能为空')
        if surface=='floor':raise ValueError('平齐地板微型镶嵌使用整块，请省略shapes')
        return provided
    if surface=='floor':return None
    name,_=effective(material);short=name.split(':',1)[-1]
    aliases={'quartz_block':'quartz','stone_bricks':'stone_brick','bricks':'brick',
             'deepslate_bricks':'deepslate_brick','deepslate_tiles':'deepslate_tile',
             'nether_bricks':'nether_brick','red_nether_bricks':'red_nether_brick',
             'polished_blackstone_bricks':'polished_blackstone_brick','purpur_block':'purpur'}
    stem=aliases.get(short,short.removesuffix('_planks'))
    result={}
    for family in ('stairs','slab','wall'):
        if surface=='ceiling' and family=='slab':continue
        if family=='wall' and surface not in ('wall','column'):continue
        try:
            value=state(stem+'_'+family)
            if family=='wall':
                result[family]=value
                continue
            cells,reason=collision_cells(value)
            if cells and not reason:result[family]=value
        except (ValueError,KeyError):pass
    return result or None


def options_for(material,shapes,surface):
    if shapes is None:return [(None,(False,)),(material,(True,))],1
    from nbt_fit_shapes import fine_options
    if set(shapes)-{'slab','stairs'}:return fine_options(material,shapes,surface)
    if surface!='ceiling':return silhouette_options(material,shapes),2
    if 'slab' in shapes or 'stairs' not in shapes:raise ValueError('微型吊顶使用顶半楼梯细分，半砖不能细分水平轮廓')
    name,props=effective(shapes['stairs'])
    if not name.endswith('_stairs') or props.get('waterlogged')!='false':raise ValueError('须提供未含水的原版楼梯材质')
    options=[(None,(False,)*4)]
    for direction in ('north','east','south','west'):
        value=state(f'{name}[facing={direction},half=top,shape=straight,waterlogged=false]')
        cells={(x,z) for x,y,z in collision_cells(value)[0] if y==0}
        options.append((value,tuple(p in cells for p in ((0,0),(1,0),(0,1),(1,1)))))
    return options+[(material,(True,)*4)],2


def reference(root,sample,width,height,factor,*,raster=None):
    """One physical source analysis, shared by every block-palette resolution."""
    from hashlib import sha256
    from nbt_bitmap_topology import component_masks
    from nbt_modeling_session import current,canonical,engine_revision
    if sample.get('noise_strength',0):raise ValueError('微型单元优先保留主轮廓，请设noise_strength=0')
    if type(factor) is not int or factor not in (1,2,16,32):raise ValueError('不支持的拟合采样精度')
    image=sample_image(root,sample) if raster is None else raster
    resolution=64;stride=resolution//factor
    key=(engine_revision(),width,height,resolution,image.size,image.mode,
         sha256(image.tobytes()).hexdigest(),canonical(sample))
    cache=current();analysis=cache.get('ornament_reference',key)
    if analysis is None:
        mask=image.getchannel('A') if sample.get('channel')=='alpha' else image.convert('L')
        if sample.get('invert'):mask=ImageOps.invert(mask)
        size=(width*resolution,height*resolution)
        mask=resize_sample(mask,size,sample.get('fit','contain'))
        alpha=resize_sample(image.getchannel('A'),size,sample.get('fit','contain'))
        gray=np.flipud(np.asarray(mask,dtype=float)/255)*np.flipud(np.asarray(alpha)>0)
        if sample.get('mirror'):
            gray=gray[:,np.minimum(np.arange(size[0]),size[0]-1-np.arange(size[0]))]
        binary=gray>=sample.get('threshold',50)/100
        byte_count=(binary.size+7)//8;feature_area=resolution**2/8
        ink_points=set();void_points=set();counts={}
        for label,foreground in (('ink',True),('void',False)):
            retained=discarded=0
            for bits in component_masks(binary if foreground else ~binary,foreground,not foreground):
                if bits.bit_count()<feature_area:discarded+=1;continue
                retained+=1
                flat=np.unpackbits(np.frombuffer(bits.to_bytes(byte_count,'little'),dtype=np.uint8),bitorder='little')[:binary.size]
                yy,xx=np.nonzero(flat.reshape(binary.shape));points=np.column_stack((yy,xx))
                if foreground:
                    for axis,reverse in ((0,False),(0,True),(1,False),(1,True)):
                        edge=(np.max if reverse else np.min)(points[:,axis])
                        candidates=points[points[:,axis]==edge]
                        center=float(candidates[:,1-axis].mean())
                        point=candidates[np.argmin(np.abs(candidates[:,1-axis]-center))]
                        ink_points.add(tuple(int(n) for n in point))
                else:
                    center=points.mean(axis=0)
                    point=points[np.argmin(np.square(points-center).sum(axis=1))]
                    void_points.add(tuple(int(n) for n in point))
            counts[label]=(retained,discarded)
        if not counts['ink'][0]:raise ValueError('微型单元内没有可辨认主纹，请裁取单个基础图形或加粗源纹样')
        analysis=dict(binary=binary,ink=ink_points,void=void_points,topology=dict(
            components=counts['ink'][0],holes=counts['void'][0],
            discarded_ink_components=counts['ink'][1],discarded_small_holes=counts['void'][1]))
        cache.put('ornament_reference',key,analysis,weight=binary.nbytes+128*(len(ink_points)+len(void_points))+1024)
    binary=analysis['binary']
    coverage=binary.reshape(height*factor,stride,width*factor,stride).mean(axis=(1,3))
    ink={(y//stride,x//stride) for y,x in analysis['ink']}
    void={(y//stride,x//stride) for y,x in analysis['void']}
    return coverage,ink,void,analysis['topology']


def joint_candidates(coverage,orbits):
    """Search legal shape combinations, rather than thresholding each block.

    Small units are exhaustive. Larger ones retain a bounded beam of whole
    symmetry-orbit assignments. An optimistic ink overlap orders the beam;
    the final topology/contour checks always use complete, real half-cell masks.
    """
    exhaustive=prod(len(orbit) for orbit in orbits)<=4096
    limit=4096 if exhaustive else 96
    source_area=float(coverage.sum());remaining=source_area
    beam=[(0,0.,0,())]
    stride=coverage.shape[1]
    for assignments in orbits:
        prepared=[]
        for assignment in assignments:
            bits=0;intersection=0.;area=0
            for x,y,pixels,(_,shape) in assignment:
                for (v,u),occupied in zip(pixels,shape):
                    if occupied:
                        bits|=1<<(v*stride+u);intersection+=float(coverage[v,u]);area+=1
            prepared.append((bits,intersection,area))
        remaining-=sum(float(coverage[p]) for _,_,pixels,_ in assignments[0] for p in pixels)
        remaining=max(0.,remaining)
        expanded=[(mask|bits,intersection+ink,area+count,path+(index,))
                  for mask,intersection,area,path in beam for index,(bits,ink,count) in enumerate(prepared)]
        if len(expanded)>limit:
            expanded.sort(key=lambda item:(-(item[1]+remaining)/max(1e-9,source_area+item[2]-item[1]),
                                            abs(item[2]-(source_area-remaining)),item[3]))
            del expanded[limit:]
        beam=expanded
    return [[assignment for orbit,index in zip(orbits,path) for assignment in orbit[index]]
            for _,_,_,path in beam],dict(method='exhaustive' if exhaustive else 'bounded_beam',
                                         beam_width=None if exhaustive else limit)


def contour_error(rendered,coverage):
    """Compare edges, including the outside border and interior stroke gaps."""
    actual=np.pad(rendered.astype(float),1);expected=np.pad(coverage,1)
    difference=total=0.
    for axis in (0,1):
        source=np.abs(np.diff(expected,axis=axis))
        difference+=float(np.abs(np.abs(np.diff(actual,axis=axis))-source).sum())
        total+=float(source.sum())
    return difference/max(1.,total)


def fit_unit(root,sample,width,height,options,factor,max_error):
    return fit_reference(reference(root,sample,width,height,factor),sample,width,height,options,factor,max_error)


def fit_reference(data,sample,width,height,options,factor,max_error,*,joint=True,strict=True,refinement_accept=None):
    coverage,ink,void,topology=data
    symmetry=[]
    if np.allclose(coverage,np.fliplr(coverage),atol=1e-9):symmetry.append('x')
    if np.allclose(coverage,np.flipud(coverage),atol=1e-9):symmetry.append('y')
    def reflect_points(points):
        result=set(points)
        if 'x' in symmetry:result|={(y,coverage.shape[1]-1-x) for y,x in result.copy()}
        if 'y' in symmetry:result|={(coverage.shape[0]-1-y,x) for y,x in result.copy()}
        return result
    ink,void=reflect_points(ink),reflect_points(void)
    thresholds=sorted({.12,.2,.3,.4,.5,.6,.7,.8,sample.get('threshold',50)/100})
    choices={}
    for y in range(height):
        for x in range(width):
            pixels=[(y*factor+dy,x*factor+dx) for dy in range(factor) for dx in range(factor)]
            allowed=[option for option in options if all((p not in ink or occupied) and (p not in void or not occupied)
                     for p,occupied in zip(pixels,option[1]))]
            if not allowed:raise ValueError('该微型尺寸无法同时保留主纹与孔洞，请增加1～2格或裁取更简单的单元')
            choices[x,y]=(pixels,allowed)
    # Solve a reflection orbit together. Independent tie-breaking can make a
    # symmetric four-block motif choose conflicting stair/slab halves.
    orbits=[];remaining=set(choices)
    for x,y in sorted(choices):
        if (x,y) not in remaining:continue
        positions={(x,y)}
        if 'x' in symmetry:positions|={(width-1-a,b) for a,b in positions.copy()}
        if 'y' in symmetry:positions|={(a,height-1-b) for a,b in positions.copy()}
        positions=sorted(positions);remaining-=set(positions)
        assignments=[]
        for base in choices[x,y][1]:
            grid=np.asarray(base[1]).reshape(factor,factor)
            if 'x' in symmetry and width-1-x==x and not np.array_equal(grid,np.fliplr(grid)):continue
            if 'y' in symmetry and height-1-y==y and not np.array_equal(grid,np.flipud(grid)):continue
            assignment=[]
            for a,b in positions:
                projected=grid
                if a!=x:projected=np.fliplr(projected)
                if b!=y:projected=np.flipud(projected)
                mask=tuple(bool(n) for n in projected.flat)
                match=next((option for option in choices[a,b][1] if option[1]==mask),None)
                if match is None:break
                assignment.append((a,b,choices[a,b][0],match))
            else:assignments.append(assignment)
        if not assignments:raise ValueError('该微型尺寸无法同时保留主纹、孔洞和对称性，请增加1～2格或裁取更简单的单元')
        orbits.append(assignments)
    candidates=[];seen=set()
    stride=coverage.shape[1];pixel_count=coverage.size;byte_count=(pixel_count+7)//8
    # Candidate assignments use the same legal local projections. Pack each
    # once, then accumulate bitmasks rather than recounting four pixels and
    # four Python sums for every block of every refinement proposal.
    option_bits={(x,y,value):sum(1<<(v*stride+u) for (v,u),occupied in zip(pixels,shape) if occupied)
        for (x,y),(pixels,allowed) in choices.items() for value,shape in allowed}
    threshold_masks={threshold:(coverage>=threshold)&(coverage>0) for threshold in thresholds}
    def evaluate(assignments,threshold,baseline=False):
        bits=0;states={}
        for x,y,_,(value,_) in assignments:
            bits|=option_bits[x,y,value]
            if value is not None:states[x,y]=value
        from nbt_fit_shapes import unsupported_positions
        unsupported=unsupported_positions(states,options,getattr(options,'surface','wall'))
        key=(bits,unsupported)
        if key in seen and not baseline:return
        seen.add(key)
        rendered=np.unpackbits(np.frombuffer(bits.to_bytes(byte_count,'little'),dtype=np.uint8),bitorder='little')[:pixel_count].reshape(coverage.shape).astype(bool)
        mask=threshold_masks[threshold];requested=int(mask.sum());matched=int((mask&rendered).sum())
        missing=requested-matched;extra=int(rendered.sum())-matched
        actual=bitmap_topology(rendered)
        topology_error=4*abs(actual['components']-topology['components'])+8*abs(actual['holes']-topology['holes'])
        topology_error+=100*unsupported
        error=float(np.abs(rendered.astype(float)-coverage).mean())
        overlap=float(np.minimum(rendered,coverage).sum()/max(1e-9,float(np.maximum(rendered,coverage).sum())))
        candidates.append((topology_error,error,threshold,states,actual,dict(requested=requested,matched=matched,missing=missing,extra=extra,
            ink_overlap=overlap,contour_error=contour_error(rendered,coverage),
            selection_method='coverage_threshold' if baseline else 'joint_shapes',
            source_ink_area=float(coverage.sum()),fitted_ink_area=int(rendered.sum()))))
        if hasattr(options,'geometry'):
            candidates[-1][5].update(unsupported_positions=unsupported,geometry_constraints_passed=unsupported==0)
        return candidates[-1]
    def rank(item):
        return (item[0],1-item[5]['ink_overlap'],item[5]['contour_error'],item[1],
                item[5]['missing']+item[5]['extra'],abs(item[2]-.5))
    for threshold in thresholds:
        assignments=[]
        for orbit in orbits:
            def score(assignment):
                lost=added=gray_error=0
                for x,y,pixels,(_,shape) in assignment:
                    gray=tuple(float(coverage[p]) for p in pixels);mask=tuple(p>=threshold and p>0 for p in gray)
                    lost+=sum(a and not b for a,b in zip(mask,shape));added+=sum(b and not a for a,b in zip(mask,shape))
                    gray_error+=sum((float(b)-a)**2 for a,b in zip(gray,shape))
                return 2*lost+added,gray_error,added
            assignments.extend(min(orbit,key=score))
        evaluate(assignments,threshold,baseline=True)
    def best_available(key=rank,baseline=None):
        # A sharper candidate outside the caller's area-error budget must not
        # displace an otherwise valid, topology-preserving fit.
        admissible=[item for item in candidates if item[0]==0 and item[1]<=max_error]
        if baseline is not None and baseline[0]==0 and baseline[1]<=max_error:
            # Extra filled half-cells can raise IoU while damaging fine edges.
            # Keep the old fit unless both ink overlap and contour hold up.
            admissible=[item for item in admissible
                        if item[5]['ink_overlap']+1e-12>=baseline[5]['ink_overlap']
                        and item[5]['contour_error']<=baseline[5]['contour_error']+1e-12]
        return min(admissible or candidates,key=key)
    seeded=0
    for seed in getattr(options,'seeds',()):
        assignments=[]
        for (x,y),(pixels,allowed) in choices.items():
            match=next((option for option in allowed if option[0]==seed.get((x,y))),None)
            if match is None:break
            assignments.append((x,y,pixels,match))
        else:
            evaluate(assignments,.5);seeded+=1
    baseline=best_available(lambda item:(item[0],1-item[5]['ink_overlap'],item[1],
                            item[5]['missing']+item[5]['extra'],abs(item[2]-.5)))
    combinations,search=joint_candidates(coverage,orbits) if joint else ([],dict(method='threshold_probe',beam_width=None))
    for assignments in combinations:evaluate(assignments,.5)
    best=best_available(baseline=baseline)
    repair=None
    if joint and best[0]:
        # A coverage beam can discard the last open channel of a hole. Repair
        # complete legal assignments before requiring a feasible topology; the
        # ordinary visual refinement below starts only after feasibility.
        proposals=accepted=0;budget=512;initial_error=best[0]
        repair_seeds=[];seen_states=set()
        for item in sorted(candidates,key=rank):
            signature=tuple(sorted(item[3].items()))
            if signature not in seen_states:repair_seeds.append(item);seen_states.add(signature)
            if len(repair_seeds)==3:break
        for seed in repair_seeds:
            current=seed
            path=[next(i for i,assignment in enumerate(orbit)
                if all(current[3].get((x,y))==option[0] for x,y,_,option in assignment)) for orbit in orbits]
            for _ in range(2):
                changed=False
                def uncertainty(index):
                    return -sum(abs(float(coverage[p])-occupied) for _,_,pixels,(_,shape) in orbits[index][path[index]] for p,occupied in zip(pixels,shape))
                for index in sorted(range(len(orbits)),key=uncertainty):
                    winner=current;choice=path[index]
                    for alternative in range(len(orbits[index])):
                        if alternative==path[index]:continue
                        if proposals>=budget:break
                        trial=path.copy();trial[index]=alternative;proposals+=1
                        item=evaluate([entry for orbit,selected in zip(orbits,trial) for entry in orbit[selected]],.5)
                        if item is not None and item[1]<=max_error and rank(item)<rank(winner):winner=item;choice=alternative
                    if winner is not current:
                        current=winner;path[index]=choice;accepted+=1;changed=True
                    if not current[0] or proposals>=budget:break
                if not changed or not current[0] or proposals>=budget:break
            if not current[0] or proposals>=budget:break
        best=best_available(baseline=baseline)
        repair=dict(method='bounded_topology_orbit_repair',proposal_budget=budget,proposals=proposals,
            accepted_moves=accepted,initial_error=initial_error,final_error=best[0],feasible=best[0]==0)
    refinement=None
    if joint and best[0]==0 and best[5]['ink_overlap']<1-1e-12:
        # A finite IoU beam can discard a useful fine edge early. Revisit legal
        # symmetry-orbit choices around its best solutions, without changing
        # source extrema/holes, shape families or the existing acceptance gate.
        initial_candidates_evaluated=len(seen)
        seeds=[];seed_states=set()
        for item in sorted((item for item in candidates if item[0]==0),key=rank):
            signature=tuple(sorted(item[3].items()))
            if signature not in seed_states:seeds.append(item);seed_states.add(signature)
            if len(seeds)==2:break
        proposals=accepted=0;budget=384
        for seed in seeds:
            current=seed
            path=[]
            for orbit in orbits:
                path.append(next(i for i,assignment in enumerate(orbit)
                    if all(current[3].get((x,y))==option[0] for x,y,_,option in assignment)))
            for _ in range(2):
                changed=False
                def uncertainty(index):
                    return -sum(abs(float(coverage[p])-occupied) for _,_,pixels,(_,shape) in orbits[index][path[index]] for p,occupied in zip(pixels,shape))
                for index in sorted(range(len(orbits)),key=uncertainty):
                    winner=current;choice=path[index]
                    for alternative in range(len(orbits[index])):
                        if alternative==path[index]:continue
                        if proposals>=budget:break
                        trial=path.copy();trial[index]=alternative;proposals+=1
                        assignments=[entry for orbit,selected in zip(orbits,trial) for entry in orbit[selected]]
                        item=evaluate(assignments,.5)
                        if item is not None and item[0]==0 and item[1]<=max(max_error,current[1]) and rank(item)<rank(winner) and item[5]['contour_error']<=current[5]['contour_error']+1e-12:
                            winner=item;choice=alternative
                    if winner is not current:
                        current=winner;path[index]=choice;accepted+=1;changed=True
                    if proposals>=budget:break
                if not changed or proposals>=budget:break
            if proposals>=budget:break
        eligible=[item for item in candidates if item[0]==0 and item[1]<=max_error
            and item[5]['ink_overlap']+1e-12>=best[5]['ink_overlap']
            and item[5]['contour_error']<=best[5]['contour_error']+1e-12]
        refined=min(eligible,key=rank) if eligible else best
        guard=None
        if rank(refined)<rank(best) and refinement_accept is not None:
            guard=refinement_accept(best[3],refined[3])
            if not guard['accepted']:refined=best
        refinement=dict(method='bounded_topology_preserving_orbit_refinement',initial_candidates_evaluated=initial_candidates_evaluated,proposal_budget=budget,proposals=proposals,
            accepted_moves=accepted,improved=rank(refined)<rank(best),previous_ink_overlap=best[5]['ink_overlap'],
            previous_contour_error=best[5]['contour_error'],quality_guard=guard,source_modified=False)
        best=refined
    topology_error,error,threshold,states,actual,counts=best
    if strict and (topology_error or error>max_error):
        if counts.get('unsupported_positions'):raise ValueError('微型拟合存在缺少支撑或未连接背板的方块，请增加实体承托或更换形状')
        raise ValueError(f'微型单元{width}×{height}未保留可辨认轮廓（孔洞{topology["holes"]}→{actual["holes"]}，连通分量{topology["components"]}→{actual["components"]}，覆盖误差{error:.3f}）；请裁取单个基础图形或尝试增加1～2格，仍建议控制在8格以内')
    return states,dict(unit_size_uv=[width,height],subcells_per_block=factor**2,source_sampling_resolution=64,
        selected_coverage_threshold=threshold,source_threshold=sample.get('threshold',50)/100,source_topology=topology,result_topology=actual,
        preserved_symmetry_axes=symmetry,
        shape_search=dict(search,candidates_evaluated=len(seen),
                          seed_candidates_evaluated=seeded,
                          baseline_ink_overlap=baseline[5]['ink_overlap'],
                          baseline_contour_error=baseline[5]['contour_error'],
                          baseline_raw_coverage_error=baseline[1],
                          baseline_topology_preserved=baseline[0]==0,
                          improved=rank(best)[:4]<rank(baseline)[:4],**({'repair':repair} if repair else {}),**({'refinement':refinement} if refinement else {})),
        topology_preserved=topology_error==0,raw_coverage_error=error,
        stylized=error>.15 or counts['ink_overlap']<.75 or bool(topology['discarded_ink_components']+topology['discarded_small_holes']),
        max_error=max_error,placement='fit_once_then_copy',threshold_candidates=len(thresholds),**counts)


def fit_colored_unit(root,sample,width,height,options,factor,ornament,args):
    from nbt_modeling_session import current,canonical,engine_revision
    # Reuse the solved unit across names, backing materials and tile layouts.
    # Verify real image bytes before a hit; store only detached data, not a
    # closure or transformed/world geometry from an earlier installation.
    sample_image(root,sample)
    settings={key:args.get(key,default) for key,default in (
        ('micro_max_error',.65),('micro_alignment','auto'),('quality_profile','balanced'),('min_quality_score',0))}
    key=(str(Path(root).resolve()),engine_revision(),canonical(sample),width,height,
         canonical(options),factor,ornament,canonical(settings))
    cache=current();hit=cache.get('micro_unit',key)
    if hit is not None:return {(u,v):value for u,v,value in hit['unit']},hit['quality']
    from nbt_micro_alignment import adaptive_fit
    if factor>=16:
        # Adding choices must not discard a representable old solution merely
        # because the bounded beam spends its slots on new local silhouettes.
        coarse_shapes={key:value for key,value in getattr(options,'materials',args.get('shapes',{})).items() if key in ('slab','stairs')}
        coarse_options,coarse_factor=options_for(ornament,coarse_shapes or None,args['surface'])
        try:
            seed,_,_=adaptive_fit(root,sample,width,height,coarse_options,coarse_factor,
                args.get('micro_max_error',.65),'fixed',quality_profile=args.get('quality_profile','balanced'),min_quality_score=0)
            options.seeds=(seed,)
        except ValueError:
            options.seeds=()
    unit,quality,color_at=adaptive_fit(root,sample,width,height,options,factor,
                                     args.get('micro_max_error',.65),args.get('micro_alignment','auto'),
                                     quality_profile=args.get('quality_profile','balanced'),min_quality_score=args.get('min_quality_score',0))
    for (u,v),value in list(unit.items()):
        if value==ornament:
            value=color_at(u,v) or ornament
            cells,reason=collision_cells(value)
            if reason or len(cells)!=8:raise ValueError('微型样本配色须使用完整方块')
            unit[u,v]=value
    cache.put('micro_unit',key,dict(unit=[[*p,value] for p,value in sorted(unit.items())],quality=quality))
    return unit,quality


def compile_microfit(workspace,args):
    from nbt_pattern_panel import sample_input,panel_materials
    from nbt_structure_agent import build

    width,height=args['size_uv']
    if not all(1<=n<=12 for n in (width,height)):raise ValueError('微型单元每轴须为1～12格，主纹建议2～8格')
    if 'repeat' in args:raise ValueError('微型纹样先拟合单元，再使用tile_counts铺排；不对整张图片重复缩放')
    surface=args['surface'];root,sample=sample_input(workspace,args);body,ornament=panel_materials(args)
    if args.get('full_blocks_only') and 'shapes' in args:raise ValueError('full_blocks_only不能同时指定shapes')
    shapes=None if args.get('full_blocks_only') else companions(ornament,surface,args.get('shapes'))
    options,factor=options_for(ornament,shapes,surface)
    auto_wall=bool(shapes and 'wall' in shapes and 'shapes' not in args)
    try:
        unit,quality=fit_colored_unit(root,sample,width,height,options,factor,ornament,args)
    except ValueError as error:
        if not auto_wall:raise
        fallback={key:value for key,value in shapes.items() if key!='wall'}
        options,factor=options_for(ornament,fallback or None,surface)
        unit,quality=fit_colored_unit(root,sample,width,height,options,factor,ornament,args)
        quality['auto_wall_search']=dict(attempted=True,fallback=True,reason=str(error))
    else:
        if auto_wall:quality['auto_wall_search']=dict(attempted=True,fallback=False)
    if factor>=16:
        quality.update(projection_resolution=factor,geometry_basis='static_shape_envelopes_texture_alpha_excluded',
                       state_policy='explicit_states_no_neighbor_or_redstone_simulation',collision_validated=False)
        quality['approximate_states']=sorted({value for value in unit.values() if getattr(options,'geometry',{}).get(value) and options.geometry[value].approximate})
    columns,rows=args.get('tile_counts',[1,1]);gap_u,gap_v=args.get('gap_uv',[1,1])
    blocks={};counts={};stairs={};slabs={}
    def decorate(point,value,turns=0):
        value=transformed_state(value,turns,None) if turns else value
        blocks[point]=value;name,props=effective(value)
        family=next((family for family in ('stairs','slab','trapdoor','wall','pane','bars','fence','carpet','pressure_plate','end_rod','chain','snow') if name.endswith('_'+family) or name=='minecraft:'+family),'full')
        counts[family]=counts.get(family,0)+1
        if family=='stairs':key=props['facing']+'/'+props['half'];stairs[key]=stairs.get(key,0)+1
        if family=='slab':key=props['type'];slabs[key]=slabs.get(key,0)+1
    total_height=height*rows+gap_v*(rows-1)
    if surface=='cylinder':
        from nbt_cylinder_pattern import cylinder_geometry
        diameter=args.get('diameter',13);core,ring=cylinder_geometry(diameter,args.get('seam_degrees',180))
        if 'tile_counts' not in args:columns=max(1,len(ring)//(width+gap_u))
        if width*columns>len(ring):raise ValueError('微型纹样单元总宽超过圆周，不会压缩或截断单元')
        if total_height>64:raise ValueError('微型单元铺排后高度超过64格')
        size=[diameter+2,total_height,diameter+2]
        blocks={(x,y,z):body for x,z in core for y in range(total_height)}
        slack=len(ring)-width*columns;base_gap,remainder=divmod(slack,columns);offset=0
        from nbt_cylinder_fit import prepare_unit,half_cells,topology
        reference_topology=topology(half_cells({(u,v,0):value for (u,v),value in unit.items()}))
        world_units=[];corner_points=set();ring_points={(face['x'],face['z']) for face in ring}
        for column in range(columns):
            wrapped,world_quality=prepare_unit(unit,core,ring,offset,width,height,ornament,shapes,reference_topology)
            world_units.append(world_quality)
            for row in range(rows):
                for (x,v,z),value in wrapped.items():
                    point=(x,row*(height+gap_v)+v,z)
                    if point in blocks:
                        if blocks[point]!=value:raise ValueError('圆柱相邻单元的转角连接冲突')
                        continue
                    decorate(point,value)
                    if (x,z) not in ring_points:corner_points.add(point)
            offset+=width+base_gap+(column<remainder)
        quality.update(tile_counts=[columns,rows],circumference_gap_cells=slack)
        quality['world_geometry']=dict(topology_preserved=True,columns=world_units,
            checked_instances=columns*rows,corner_connector_blocks=len(corner_points),
            validation='actual_halfcube_face_connectivity_and_cubical_handles',
            support='every_ornament_component_face_connected_to_intact_core')
        anchor=[size[0]//2,0,size[2]//2]
        unit_positions={(x,z) for x,z in core}
        wall=lambda p:(p[0],p[2]) not in unit_positions
        cylinder=dict(diameter=diameter,height=total_height,circumference_cells=len(ring),
            seam_degrees=args.get('seam_degrees',180),axis='y',backing_blocks=len(core)*total_height,ornament_blocks=sum(counts.values()))
    else:
        if 'diameter' in args or 'seam_degrees' in args:raise ValueError('diameter与seam_degrees仅用于圆柱')
        total_width=width*columns+gap_u*(columns-1)
        if max(total_width,total_height)>64:raise ValueError('微型单元铺排后每轴最多64格')
        horizontal=surface in ('floor','ceiling')
        size=[total_width,1 if surface=='floor' else 2,total_height] if horizontal else [total_width,total_height,2]
        for u in range(total_width):
            for v in range(total_height):
                blocks[(u,1 if surface=='ceiling' else 0,v) if horizontal else (u,v,0)]=body
        for column in range(columns):
            for row in range(rows):
                for (u,v),value in unit.items():
                    x=column*(width+gap_u)+u;y=row*(height+gap_v)+v
                    decorate((x,0,y) if horizontal else (x,y,1),value)
        quality.update(tile_counts=[columns,rows],gap_uv=[gap_u,gap_v])
        anchor=[total_width//2,1,total_height//2] if surface=='ceiling' else [total_width//2,0,total_height//2 if horizontal else 0]
        wall=lambda p:surface in ('wall','column')
        cylinder=None
    palette=sorted(set(blocks.values()));indices={value:i for i,value in enumerate(palette)}
    operations=[]
    for is_wall in (False,True):
        voxels=[[*p,indices[value]] for p,value in sorted(blocks.items()) if wall(p)==is_wall]
        if voxels:operations.append(dict(kind='paste_component',label='微型纹样铺排',classification='wall' if is_wall else 'body',lo=[0,0,0],hi=[n-1 for n in size],palette=palette,voxels=voxels))
    spec=dict(name=args.get('name',args.get('preset','微型纹样')),size=size,anchor=anchor,
              max_changed_blocks=args.get('max_changed_blocks',65536 if cylinder else 8192),operations=operations)
    if surface in ('floor','ceiling'):spec['camera']=dict(azimuth=35,elevation=65 if surface=='floor' else -65)
    data=build(workspace,spec)
    result=dict(spec=spec,content_sha256=data['content_sha256'],block_count=len(blocks),surface=surface,
        sample_sha256=sample['sha256'],shape_counts=counts,stair_orientations=stairs,slab_orientations=slabs,
        orientation_policy='automatic_micro_unit_and_surface_normal',microfit=quality,visual_quality=quality['visual_quality'],
        fitting={k:quality[k] for k in ('requested','matched','missing','extra','subcells_per_block')},model_modified=False)
    result['mount_object']=dict({k:v for k,v in args.items() if k!='preview'},fit_mode='micro')
    result['fitting'].update(reference='adaptive_micro_unit_mask',projection='local_tangent_y' if cylinder else 'xz' if surface in ('floor','ceiling') else 'xy')
    if cylinder:result['cylinder']=cylinder
    return result
