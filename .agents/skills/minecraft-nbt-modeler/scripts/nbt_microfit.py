"""Fit small ornament units before placement; preserve visible topology."""
from collections import deque
from math import prod

import numpy as np
from PIL import Image,ImageOps

from nbt_collision import collision_cells
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
    for family in ('stairs','slab'):
        if surface=='ceiling' and family=='slab':continue
        try:
            value=state(stem+'_'+family);cells,reason=collision_cells(value)
            if cells and not reason:result[family]=value
        except (ValueError,KeyError):pass
    return result or None


def options_for(material,shapes,surface):
    if shapes is None:return [(None,(False,)),(material,(True,))],1
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
    if sample.get('noise_strength',0):raise ValueError('微型单元优先保留主轮廓，请设noise_strength=0')
    image=sample_image(root,sample) if raster is None else raster
    mask=image.getchannel('A') if sample.get('channel')=='alpha' else image.convert('L')
    if sample.get('invert'):mask=ImageOps.invert(mask)
    oversample=8;size=(width*factor*oversample,height*factor*oversample)
    mask=resize_sample(mask,size,sample.get('fit','contain'))
    alpha=resize_sample(image.getchannel('A'),size,sample.get('fit','contain'))
    gray=np.flipud(np.asarray(mask,dtype=float)/255)*np.flipud(np.asarray(alpha)>0)
    if sample.get('mirror'):
        gray=gray[:,np.minimum(np.arange(size[0]),size[0]-1-np.arange(size[0]))]
    binary=gray>=sample.get('threshold',50)/100
    coverage=binary.reshape(height*factor,oversample,width*factor,oversample).mean(axis=(1,3))
    all_ink=regions(binary);all_holes=regions(binary,False)
    ink=[g for g in all_ink if len(g)>=oversample**2/2]
    holes=[g for g in all_holes if len(g)>=oversample**2/2]
    if not ink:raise ValueError('微型单元内没有可辨认主纹，请裁取单个基础图形或加粗源纹样')
    required_ink=set();required_void=set()
    for group in ink:
        # Retain each component's four extrema, preventing a thin glyph from
        # collapsing to an isolated dot while keeping the same component count.
        for axis,reverse in ((0,False),(0,True),(1,False),(1,True)):
            edge=(max if reverse else min)(p[axis] for p in group)
            candidates=[p for p in group if p[axis]==edge]
            center=sum(p[1-axis] for p in candidates)/len(candidates)
            point=min(candidates,key=lambda p:abs(p[1-axis]-center))
            required_ink.add((point[0]//oversample,point[1]//oversample))
    for group in holes:
        center=np.mean(group,axis=0)
        cells={(y//oversample,x//oversample) for y,x in group}
        members=set(group)
        interior=[p for p in cells if (int((p[0]+.5)*oversample),int((p[1]+.5)*oversample)) in members]
        point=min(interior or cells,key=lambda p:(coverage[p],sum(((p[i]+.5)*oversample-center[i])**2 for i in range(2)),p))
        required_void.add(point)
    return coverage,required_ink,required_void,dict(components=len(ink),holes=len(holes),
        discarded_ink_components=len(all_ink)-len(ink),discarded_small_holes=len(all_holes)-len(holes))


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


def fit_reference(data,sample,width,height,options,factor,max_error,*,joint=True,strict=True):
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
    def evaluate(assignments,threshold,baseline=False):
        rendered=np.zeros(coverage.shape,dtype=bool);states={};requested=matched=missing=extra=0
        for x,y,pixels,(value,shape) in assignments:
            mask=tuple(bool(coverage[p]>=threshold and coverage[p]>0) for p in pixels)
            for pixel,occupied in zip(pixels,shape):rendered[pixel]=occupied
            if value is not None:states[x,y]=value
            requested+=sum(mask);matched+=sum(a and b for a,b in zip(mask,shape))
            missing+=sum(a and not b for a,b in zip(mask,shape));extra+=sum(b and not a for a,b in zip(mask,shape))
        key=rendered.tobytes()
        if key in seen and not baseline:return
        seen.add(key)
        actual=dict(components=len(regions(rendered)),holes=len(regions(rendered,False)))
        topology_error=4*abs(actual['components']-topology['components'])+8*abs(actual['holes']-topology['holes'])
        error=float(np.abs(rendered.astype(float)-coverage).mean())
        overlap=float(np.minimum(rendered,coverage).sum()/max(1e-9,float(np.maximum(rendered,coverage).sum())))
        candidates.append((topology_error,error,threshold,states,actual,dict(requested=requested,matched=matched,missing=missing,extra=extra,
            ink_overlap=overlap,contour_error=contour_error(rendered,coverage),
            selection_method='coverage_threshold' if baseline else 'joint_shapes',
            source_ink_area=float(coverage.sum()),fitted_ink_area=int(rendered.sum()))))
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
    baseline=best_available(lambda item:(item[0],1-item[5]['ink_overlap'],item[1],
                            item[5]['missing']+item[5]['extra'],abs(item[2]-.5)))
    combinations,search=joint_candidates(coverage,orbits) if joint else ([],dict(method='threshold_probe',beam_width=None))
    for assignments in combinations:evaluate(assignments,.5)
    best=best_available(baseline=baseline)
    topology_error,error,threshold,states,actual,counts=best
    if strict and (topology_error or error>max_error):
        raise ValueError(f'微型单元{width}×{height}未保留可辨认轮廓（孔洞{topology["holes"]}→{actual["holes"]}，连通分量{topology["components"]}→{actual["components"]}，覆盖误差{error:.3f}）；请裁取单个基础图形或尝试增加1～2格，仍建议控制在8格以内')
    return states,dict(unit_size_uv=[width,height],subcells_per_block=factor**2,
        selected_coverage_threshold=threshold,source_threshold=sample.get('threshold',50)/100,source_topology=topology,result_topology=actual,
        preserved_symmetry_axes=symmetry,
        shape_search=dict(search,candidates_evaluated=len(seen),
                          baseline_ink_overlap=baseline[5]['ink_overlap'],
                          baseline_contour_error=baseline[5]['contour_error'],
                          baseline_raw_coverage_error=baseline[1],
                          baseline_topology_preserved=baseline[0]==0,
                          improved=rank(best)[:4]<rank(baseline)[:4]),
        topology_preserved=topology_error==0,raw_coverage_error=error,
        stylized=error>.15 or counts['ink_overlap']<.75 or bool(topology['discarded_ink_components']+topology['discarded_small_holes']),
        max_error=max_error,placement='fit_once_then_copy',threshold_candidates=len(thresholds),**counts)


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
    from nbt_micro_alignment import adaptive_fit
    unit,quality,color_at=adaptive_fit(root,sample,width,height,options,factor,
                                     args.get('micro_max_error',.65),args.get('micro_alignment','auto'),
                                     quality_profile=args.get('quality_profile','balanced'),min_quality_score=args.get('min_quality_score',0))
    for (u,v),value in list(unit.items()):
        if value==ornament:
            value=color_at(u,v) or ornament
            cells,reason=collision_cells(value)
            if reason or len(cells)!=8:raise ValueError('微型样本配色须使用完整方块')
            unit[u,v]=value
    columns,rows=args.get('tile_counts',[1,1]);gap_u,gap_v=args.get('gap_uv',[1,1])
    blocks={};counts={};stairs={};slabs={}
    def decorate(point,value,turns=0):
        value=transformed_state(value,turns,None) if turns else value
        blocks[point]=value;name,props=effective(value)
        family='stairs' if name.endswith('_stairs') else 'slab' if name.endswith('_slab') else 'full'
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
