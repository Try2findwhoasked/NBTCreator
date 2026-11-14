"""Fit small ornament units before placement; preserve visible topology."""
from collections import deque

import numpy as np
from PIL import Image,ImageOps

from nbt_collision import collision_cells
from nbt_model import state
from nbt_ornament_sample import sample_image,fit_sample,silhouette_options
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


def reference(root,sample,width,height,factor):
    if sample.get('noise_strength',0):raise ValueError('微型单元优先保留主轮廓，请设noise_strength=0')
    image=sample_image(root,sample)
    mask=image.getchannel('A') if sample.get('channel')=='alpha' else image.convert('L')
    if sample.get('invert'):mask=ImageOps.invert(mask)
    oversample=8;size=(width*factor*oversample,height*factor*oversample)
    resize=ImageOps.fit if sample.get('fit','contain')=='cover' else ImageOps.pad
    mask=resize(mask,size,Image.Resampling.BOX)
    alpha=resize(image.getchannel('A'),size,Image.Resampling.BOX)
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


def fit_unit(root,sample,width,height,options,factor,max_error):
    coverage,ink,void,topology=reference(root,sample,width,height,factor)
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
    candidates=[]
    for threshold in thresholds:
        rendered=np.zeros(coverage.shape,dtype=bool);states={};requested=matched=missing=extra=0
        for assignments in orbits:
            def score(assignment):
                lost=added=gray_error=0
                for x,y,pixels,(_,shape) in assignment:
                    gray=tuple(float(coverage[p]) for p in pixels);mask=tuple(p>=threshold and p>0 for p in gray)
                    lost+=sum(a and not b for a,b in zip(mask,shape));added+=sum(b and not a for a,b in zip(mask,shape))
                    gray_error+=sum((float(b)-a)**2 for a,b in zip(gray,shape))
                return 2*lost+added,gray_error,added
            for x,y,pixels,(value,shape) in min(assignments,key=score):
                mask=tuple(bool(coverage[p]>=threshold and coverage[p]>0) for p in pixels)
                for pixel,occupied in zip(pixels,shape):rendered[pixel]=occupied
                if value is not None:states[x,y]=value
                requested+=sum(mask);matched+=sum(a and b for a,b in zip(mask,shape))
                missing+=sum(a and not b for a,b in zip(mask,shape));extra+=sum(b and not a for a,b in zip(mask,shape))
        actual=dict(components=len(regions(rendered)),holes=len(regions(rendered,False)))
        topology_error=4*abs(actual['components']-topology['components'])+8*abs(actual['holes']-topology['holes'])
        error=float(np.abs(rendered.astype(float)-coverage).mean())
        overlap=float(np.minimum(rendered,coverage).sum()/max(1e-9,float(np.maximum(rendered,coverage).sum())))
        candidates.append((topology_error,error,threshold,states,actual,dict(requested=requested,matched=matched,missing=missing,extra=extra,
            ink_overlap=overlap,source_ink_area=float(coverage.sum()),fitted_ink_area=int(rendered.sum()))))
    best=min(candidates,key=lambda item:(item[0],1-item[5]['ink_overlap'],item[1],
             item[5]['missing']+item[5]['extra'],abs(item[2]-.5)))
    topology_error,error,threshold,states,actual,counts=best
    if topology_error or error>max_error:
        raise ValueError(f'微型单元{width}×{height}未保留可辨认轮廓（孔洞{topology["holes"]}→{actual["holes"]}，连通分量{topology["components"]}→{actual["components"]}，覆盖误差{error:.3f}）；请裁取单个基础图形或尝试增加1～2格，仍建议控制在8格以内')
    return states,dict(unit_size_uv=[width,height],subcells_per_block=factor**2,
        selected_coverage_threshold=threshold,source_threshold=sample.get('threshold',50)/100,source_topology=topology,result_topology=actual,
        preserved_symmetry_axes=symmetry,
        topology_preserved=True,raw_coverage_error=error,
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
    unit,quality=fit_unit(root,sample,width,height,options,factor,args.get('micro_max_error',.65))
    # Colour choice remains independent of the micro-unit's contour reduction.
    _,color_at=fit_sample(root,dict(sample,noise_strength=0),width,height,0,sample.get('mirror',False),subcells=factor==2)
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
        from nbt_cylinder_pattern import cylinder_geometry,touches_backing
        diameter=args.get('diameter',13);core,ring=cylinder_geometry(diameter,args.get('seam_degrees',180))
        if 'tile_counts' not in args:columns=max(1,len(ring)//(width+gap_u))
        if width*columns>len(ring):raise ValueError('微型纹样单元总宽超过圆周，不会压缩或截断单元')
        if total_height>64:raise ValueError('微型单元铺排后高度超过64格')
        size=[diameter+2,total_height,diameter+2]
        blocks={(x,y,z):body for x,z in core for y in range(total_height)}
        slack=len(ring)-width*columns;base_gap,remainder=divmod(slack,columns);offset=0
        for column in range(columns):
            for row in range(rows):
                for (u,v),value in unit.items():
                    face=ring[(offset+u)%len(ring)];rotated=transformed_state(value,face['turns'],None)
                    if not touches_backing(rotated,face):raise ValueError('微型柱饰未贴合柱芯')
                    decorate((face['x'],row*(height+gap_v)+v,face['z']),value,face['turns'])
            offset+=width+base_gap+(column<remainder)
        quality.update(tile_counts=[columns,rows],circumference_gap_cells=slack)
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
        orientation_policy='automatic_micro_unit_and_surface_normal',microfit=quality,
        fitting={k:quality[k] for k in ('requested','matched','missing','extra','subcells_per_block')},model_modified=False)
    result['mount_object']=dict({k:v for k,v in args.items() if k!='preview'},fit_mode='micro')
    result['fitting'].update(reference='adaptive_micro_unit_mask',projection='local_tangent_y' if cylinder else 'xz' if surface in ('floor','ceiling') else 'xy')
    if cylinder:result['cylinder']=cylinder
    return result
