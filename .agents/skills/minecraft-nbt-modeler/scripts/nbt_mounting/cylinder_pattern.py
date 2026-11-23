"""Cyclic mask fitting around a voxel cylinder with automatic block states."""
from math import atan2, pi, radians

from nbt_collision import collision_cells
from nbt_pattern.ornament_sample import fit_sample, silhouette_options, match_silhouette
from nbt_registry import effective
from nbt_tools import transformed_state

# Positive local U follows the unwrapped circumference. These rotations map
# both the tangent and the backing normal, including on the seam's two sides.
FACES=(('south',0,1,0),('east',1,0,3),('north',0,-1,2),('west',-1,0,1))


def cylinder_geometry(diameter,seam_degrees=180):
    if not 4<=diameter<=30:
        raise ValueError('圆柱柱芯直径须为4～30格；外饰另占两格')
    center=(diameter+1)/2
    core={(x,z) for x in range(1,diameter+1) for z in range(1,diameter+1)
          if (x-center)**2+(z-center)**2<=(diameter/2)**2}
    shell={(x+dx,z+dz) for x,z in core for _,dx,dz,_ in FACES}-core
    ring=[]
    for x,z in shell:
        angle=(atan2(x-center,z-center)-radians(seam_degrees))%(2*pi)
        supports=[(name,dx,dz,turns) for name,dx,dz,turns in FACES if (x-dx,z-dz) in core]
        normal,dx,dz,turns=max(supports,key=lambda f:((x-center)*f[1]+(z-center)*f[2],
                                                     f[1]*(z-center)-f[2]*(x-center)))
        ring.append(dict(x=x,z=z,angle=angle,normal=normal,dx=dx,dz=dz,turns=turns))
    return core,sorted(ring,key=lambda p:(p['angle'],p['x'],p['z']))


def touches_backing(value,face):
    cells,reason=collision_cells(value)
    axis=0 if face['dx'] else 2
    inward=0 if face['dx']+face['dz']>0 else 1
    return not reason and any(p[axis]==inward for p in cells)


def compile_cylinder(workspace,args):
    from nbt_pattern.panel import sample_input,panel_materials
    from nbt_structure_agent import build

    diameter,height=args['size_uv']
    core,ring=cylinder_geometry(diameter,args.get('seam_degrees',180))
    body,ornament=panel_materials(args)
    root,sample=sample_input(workspace,args)
    shapes=args.get('shapes')
    if shapes=={}:
        raise ValueError('shapes 至少须指定一种材质')
    choices=silhouette_options(ornament,shapes) if shapes else None
    sample_at,color_at,coverage_at=fit_sample(root,sample,len(ring),height,args.get('seed',0),
        sample.get('mirror',False),args.get('repeat',[1,1]),subcells=bool(choices),return_coverage=True)
    blocks={(x,y,z):body for x,z in core for y in range(height)}
    counts={};stairs={};slabs={};normals={};errors=dict(requested=0,matched=0,missing=0,extra=0)
    for u,face in enumerate(ring):
        normals[face['normal']]=normals.get(face['normal'],0)+1
        for y in range(height):
            mask=sample_at(u,y)
            if choices:
                value,projected=match_silhouette(mask,choices,coverage_at(u,y))
            else:
                value=ornament if mask else None
                mask=(bool(mask),);projected=mask
            errors['requested']+=sum(mask)
            errors['matched']+=sum(a and b for a,b in zip(mask,projected))
            errors['missing']+=sum(a and not b for a,b in zip(mask,projected))
            errors['extra']+=sum(b and not a for a,b in zip(mask,projected))
            if value is None:
                continue
            if value==ornament:
                value=color_at(u,y) or ornament
                cells,reason=collision_cells(value)
                if reason or len(cells)!=8:
                    raise ValueError('圆柱样本配色须使用已知完整方块')
            value=transformed_state(value,face['turns'],None)
            if not touches_backing(value,face):
                raise ValueError('圆柱拟合方块未接触柱芯')
            blocks[face['x'],y,face['z']]=value
            name,props=effective(value)
            family='stairs' if name.endswith('_stairs') else 'slab' if name.endswith('_slab') else 'full'
            counts[family]=counts.get(family,0)+1
            if family=='stairs':
                key=props['facing']+'/'+props['half'];stairs[key]=stairs.get(key,0)+1
            elif family=='slab':
                key=props['type'];slabs[key]=slabs.get(key,0)+1
    if not counts:
        raise ValueError('圆柱没有生成可见纹样，请调整尺寸、重复数或阈值')
    size=[diameter+2,height,diameter+2]
    palette=sorted(set(blocks.values()));indices={value:i for i,value in enumerate(palette)}
    spec=dict(name=args.get('name',args.get('preset','圆柱环绕纹样')),size=size,
              anchor=[size[0]//2,0,size[2]//2],max_changed_blocks=args.get('max_changed_blocks',65536),
              operations=[dict(kind='paste_component',label=label,classification=classification,
                  lo=[0,0,0],hi=[n-1 for n in size],palette=palette,
                  voxels=[[*p,indices[value]] for p,value in sorted(blocks.items()) if ((p[0],p[2]) in core)==is_core])
                  for label,classification,is_core in (('圆柱柱芯','body',True),('圆柱环绕纹样','wall',False))])
    data=build(workspace,spec)
    return dict(spec=spec,surface='cylinder',content_sha256=data['content_sha256'],block_count=len(blocks),
                sample_sha256=sample['sha256'],shape_counts=counts,stair_orientations=stairs,slab_orientations=slabs,
                orientation_policy='automatic_cyclic_tangent_and_surface_normal',
                cylinder=dict(diameter=diameter,height=height,circumference_cells=len(ring),
                              seam_degrees=args.get('seam_degrees',180),normal_counts=normals,
                              backing_blocks=len(core)*height,ornament_blocks=sum(counts.values()),
                              uv_mapping='cyclic_contour_index',axis='y'),
                fitting=dict(errors,subcells_per_block=4 if choices else 1,projection='local_tangent_y',
                             reference='resampled_threshold_mask'),
                model_modified=False)


def mount_cylinder(workspace,args):
    """Fit only the exterior ornament to a hash-bound column core."""
    from pathlib import Path
    from nbt_model import AIR_NAMES
    from nbt_selection_edit import load_selection,sha
    from nbt_mounting.surface_mount import digest,_unchanged
    from nbt_library import canonical_context
    from nbt_refine import protections,box_points
    from nbt_detail_control import default_settings,compile_plan,simulate_plan
    from nbt_structure_agent import build

    request=dict(args['target'])
    for key in ('source','context','snapshot'):
        if request.get(key):request[key]=str((Path(workspace)/request[key]).resolve())
    if bool(request.get('snapshot'))!=bool(request.get('snapshot_sha256')):
        raise ValueError('候选快照须同时提供路径和SHA256')
    if sha(request['context'])!=request['context_sha256']:
        raise ValueError('保护上下文已变化')
    source,_,model,walls,lo,hi,snapshot_hash=load_selection(request,request.get('snapshot'))
    if snapshot_hash!=request.get('snapshot_sha256'):
        raise ValueError('候选快照已变化')
    config=canonical_context(request['context'])
    binding=dict(request=request,source=source,model=model,walls=walls,config=config,snapshot_hash=snapshot_hash)
    proposal=args['object']
    if proposal['surface']!='cylinder':
        raise ValueError('圆柱环绕安装须使用surface=cylinder')
    protected=protections(model,config);reserved=set()
    for bounds in args.get('reserved_boxes',[]):
        if any(bounds['lo'][i]>bounds['hi'][i] or bounds['hi'][i]>=model.size[i] for i in range(3)):
            raise ValueError('留白范围无效或超出模型')
        if (bounds['hi'][0]-bounds['lo'][0]+1)*(bounds['hi'][1]-bounds['lo'][1]+1)*(bounds['hi'][2]-bounds['lo'][2]+1)>65536:
            raise ValueError('单个留白范围超过65536格')
        reserved.update(box_points(bounds['lo'],bounds['hi']))
    anchor=args.get('repeat_anchor_uv')
    if anchor is not None:
        from nbt_mounting.repeat_layout import cylinder, evidence, verify_inputs
        palette,voxels,changes,compiled,size,positions,clipped,connectors,clipped_connectors=cylinder(
            workspace,proposal,model,lo,hi,anchor,protected,reserved,config.get('reserved_boxes'))
        written=set(changes)
        content_hash=digest(sorted(changes.items()))
    else:
        from nbt_pattern.panel import compile_panel
        compiled=compile_panel(workspace,proposal)
        data=build(workspace,compiled['spec'])
        if [hi[i]-lo[i]+1 for i in range(3)]!=data['size']:
            raise ValueError('目标框须等于圆柱外径×高度×外径，外径为柱芯直径加2格')
        core,_=cylinder_geometry(compiled['cylinder']['diameter'],proposal.get('seam_degrees',180))
        for x,z in core:
            for y in range(data['size'][1]):
                cells,reason=collision_cells(model.get((lo[0]+x,lo[1]+y,lo[2]+z)))
                if reason or len(cells)!=8:
                    raise ValueError('原柱芯不完整或不是受支持的完整方块，不能确认环绕接触')
        palette=data['palette'];content_hash=compiled['content_sha256']
        voxels=[];written=set()
        for x,y,z,index,_ in data['blocks']:
            if (x,z) in core:
                continue
            point=(lo[0]+x,lo[1]+y,lo[2]+z)
            if point in protected:raise ValueError('圆柱外饰触及保护区域或声明开口')
            if point in reserved:raise ValueError('圆柱外饰占用显式留白')
            if model.get(point) not in AIR_NAMES:raise ValueError('圆柱外饰位置已有方块，不能覆盖')
            voxels.append([x,y,z,index]);written.add(point)
    budget=args.get('max_changed_blocks',4096)
    if len(written)>budget:raise ValueError('圆柱候选超过总变化预算')
    operations=[dict(kind='paste_component',label='既有圆柱环绕外饰',classification='wall',
                     lo=lo,hi=hi,palette=palette,voxels=voxels,overwrite=False)]
    settings=default_settings();settings.update(operations=operations,max_changed_blocks=budget)
    plan=compile_plan(settings,list(model.size))
    candidate,candidate_walls,_=simulate_plan(model,walls,plan,dict(config,max_changed_blocks=budget))
    routes='not_checked'
    if args.get('require_routes') or args.get('compare_routes') or args.get('review'):
        from nbt_mounting.review import compare_routes
        routes=compare_routes(model,candidate,config,written,required=args.get('require_routes',False))
    _unchanged(binding)
    pattern={k:compiled[k] for k in ('surface','sample_sha256','shape_counts','fitting','cylinder','stair_orientations','slab_orientations','orientation_policy')}
    if 'microfit' in compiled:pattern['microfit']=compiled['microfit']
    if anchor is not None:
        verify_inputs(workspace,proposal)
        repeat=evidence(candidate,size,proposal['size_uv'],anchor,positions,clipped,closed=True,
            connectors=connectors,check_u_edges=True,clipped_connectors=clipped_connectors)
        if repeat['seam_geometry_matches'] is False:
            mismatches=[joint for joint in repeat['half_cell_joints'] if joint['status'] in ('mismatch','unsupported_shape')]
            raise ValueError(f'圆柱通铺的实际半格接缝与单元不符：{mismatches[:4]}')
        pattern['repeat_tiling']=repeat
    result=dict(operations=operations,placements=[dict(lo=lo,hi=hi,
        connector_positions=sorted({p for p,_ in connectors.values()}) if anchor is not None else [])],skipped=[],
        source_sha256=request['source_sha256'],geometry_sha256=model.fingerprint(),context_sha256=request['context_sha256'],
        snapshot_sha256=snapshot_hash,candidate_geometry_sha256=candidate.fingerprint(),
        recipe_sha256=digest(dict(parameters=proposal,content_sha256=content_hash)),pattern=pattern,
        changed_blocks=len(written),max_changed_blocks=budget,model_modified=False,approval_created=False,
        verification=dict(mount_contact=True,intact_core=not compiled['cylinder'].get('masked_core_air'),protection=True,occupancy=True,budget=True,
                          routes=routes,structural_load='not_checked',design='pending_visual_review'))
    result['plan_sha256']=digest(dict(result=result,arguments=args))
    if args.get('review'):
        from nbt_mounting.review import write_review
        result['review']=write_review(workspace,binding,candidate,candidate_walls,result,args['review'])
        _unchanged(binding)
        if anchor is not None:verify_inputs(workspace,proposal)
    return result
