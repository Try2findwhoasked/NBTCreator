"""Atomic in-memory installation candidates and reusable decorated host recipes."""
from copy import deepcopy
from nbt_surface_mount import NORMALS,_load,_query,_mount,_unchanged,_full,_reject,check_clearance,digest


def surface_on(base,plane,model,walls):
    lo,hi=plane['lo'],plane['hi'];axis,sign=NORMALS[plane['normal']]
    if any(type(v) is not int for p in (lo,hi) for v in p) or any(a<0 or a>b or b>=n for a,b,n in zip(lo,hi,model.size)):
        raise ValueError('批量安装面须位于完整模型的整数边界内')
    if lo[axis]!=hi[axis]:raise ValueError('批量安装面必须是单格厚的平面')
    u,v=(0,2) if axis==1 else (0,1) if axis==2 else (2,1)
    width,height=hi[u]-lo[u]+1,hi[v]-lo[v]+1
    if width*height>4096:raise ValueError('单次安装面最多4096格')
    return dict(base,request=dict(base['request'],**plane),model=model,walls=walls,lo=lo,hi=hi,
                axis=axis,sign=sign,u=u,v=v,width=width,height=height)


def run(workspace,base,args):
    from nbt_structure_agent import _schema,definitions
    from nbt_detail_control import default_settings,compile_plan,simulate_plan
    from nbt_mount_review import compare_routes
    model,walls=base['model'],base['walls'];occupied=set();operations=[];receipts=[];checks=[];ids=set()
    context_budget=base['config'].get('max_changed_blocks',65536)
    if type(context_budget) is not int or context_budget<1:raise ValueError('安装上下文修改预算无效')
    budget=min(args.get('max_changed_blocks',65536),context_budget)
    for item in args['installations']:
        definition=definitions()[item['tool']]['parameters']['properties']
        if set(item)-({'id','tool'}|set(definition)-{'surface_sha256','review','compare_routes','require_routes','max_changed_blocks'}):
            raise ValueError('批量安装包含该工具不适用的字段：'+item['id'])
        _schema(item['object'],definition['object'],'安装对象')
        if item['id'] in ids:raise ValueError('批量安装ID重复：'+item['id'])
        ids.add(item['id']);s=surface_on(base,item['surface'],model,walls);record,safe=_query(s)
        options={k:deepcopy(v) for k,v in item.items() if k not in ('id','tool','surface')}
        options['max_changed_blocks']=budget
        options['reserved_boxes']=args.get('reserved_boxes',[])+options.get('reserved_boxes',[])
        options['surface_sha256']=record['surface_sha256']
        try:result,candidate,mask,support=_mount(workspace,s,item['tool'],options,record,safe)
        except ValueError as error:raise ValueError('批量安装 '+item['id']+' 失败：'+str(error)) from error
        points={tuple(op['lo'][i]+voxel[i] for i in range(3)) for op in result['operations'] for voxel in op['voxels']}
        if occupied&points:raise ValueError('批量安装相互覆盖：'+item['id'])
        if len(occupied|points)>budget:raise ValueError('批量安装超过总修改预算')
        occupied.update(points)
        for operation in result['operations']:
            operation=deepcopy(operation);operation['label']=item['id']+' · '+operation['label'];operations.append(operation)
        if len(operations)>128:raise ValueError('批量安装展开超过128个操作')
        receipts.append(dict(id=item['id'],tool=item['tool'],**{k:v for k,v in result.items() if k!='operations'}))
        used={(p[s['u']]-s['lo'][s['u']],p[s['v']]-s['lo'][s['v']]) for p in points|support}
        diagnostic={k:s[k] for k in ('request','lo','u','v')}
        diagnostic['cell_info']={uv:s['cell_info'][uv] for uv in used if uv in s['cell_info']}
        checks.append((item,diagnostic,support,points));model,walls=candidate,mask
    # Recheck earlier supports and clearance against the final combined model.
    # Disjoint writes alone do not prove that a later recess left backing intact.
    for item,s,support,points in checks:
        for point in sorted(support):
            if not _full(model.get(point)):_reject(s,point,'batch_backing_invalidated','后续安装破坏了已有饰件背衬',installation_id=item['id'],actual_state=model.get(point))
        check_clearance(s,model,points,item.get('min_clearance',0))
    # One complete replay catches cross-step occupancy/protection semantics and
    # ties the returned operations to the exact final candidate and wall mask.
    settings=default_settings();settings.update(operations=operations,max_changed_blocks=budget)
    replay,replay_walls,_=simulate_plan(base['model'],base['walls'],compile_plan(settings,list(model.size)),dict(base['config'],max_changed_blocks=budget))
    if replay.blocks!=model.blocks or replay_walls!=walls:raise ValueError('批量安装最终重放不一致')
    routes='not_checked'
    if args.get('require_routes') or args.get('compare_routes'):
        routes=compare_routes(base['model'],model,base['config'],occupied,required=args.get('require_routes',False))
    # Validate image bindings after the full replay and route calculation.
    for item,_,_,_ in checks:
        if item['tool']=='pattern_mount':
            from nbt_pattern_panel import sample_input
            from nbt_ornament_sample import sample_image
            root,sample=sample_input(workspace,item['object']);sample_image(root,sample)
    if base.get('source'):_unchanged(base)
    clearance_constraints=[]
    for item,s,support,points in checks:
        if item.get('min_clearance'):
            lowest={}
            for x,y,z in points:
                if model.get((x,y,z)) not in ('air','minecraft:air'):lowest[x,z]=min(y,lowest.get((x,z),y))
            clearance_constraints.append(dict(id=item['id'],min_clearance=item['min_clearance'],columns=[[x,y,z] for (x,z),y in sorted(lowest.items())]))
    result=dict(operations=operations,installations=receipts,clearance_constraints=clearance_constraints,changed_blocks=len(occupied),max_changed_blocks=budget,
        source_sha256=base['request']['source_sha256'],geometry_sha256=base['model'].fingerprint(),
        context_sha256=base['request']['context_sha256'],snapshot_sha256=base.get('snapshot_hash'),
        candidate_geometry_sha256=model.fingerprint(),model_modified=False,approval_created=False,
        verification=dict(atomic=True,ordered_in_memory=True,full_replay=True,final_backing=True,final_clearance=True,routes=routes))
    result['plan_sha256']=digest(dict(arguments=args,result=result))
    return result,model,walls


def mount_batch(workspace,args):
    first=args['installations'][0]
    base=_load(workspace,dict(args['target'],**first['surface']))
    return run(workspace,base,args)[0]


def decorate(workspace,args):
    from nbt_structure_agent import dispatch,build
    from nbt_assembly import Volume
    host=args['host']
    data=build(workspace,host['arguments'] if host['tool']=='structure' else dispatch(workspace,host['tool'],host['arguments'])['spec'])
    model=Volume(data['size']);walls=set()
    for x,y,z,index,iswall in data['blocks']:
        model.put((x,y,z),data['palette'][index])
        if iswall:walls.add((x,y,z))
    cfg=dict(mode='standalone',openings=[],protected_boxes=args.get('protected_boxes',[]))
    base=dict(source=None,model=model,walls=walls,config=cfg,snapshot_hash=None,
              request=dict(source_sha256=data['content_sha256'],context_sha256=digest(cfg)))
    result,model,walls=run(workspace,base,args)
    palette=sorted(set(model.blocks.values()));indices={value:i for i,value in enumerate(palette)};operations=[]
    for wall in (False,True):
        voxels=[[*p,indices[value]] for p,value in sorted(model.blocks.items()) if (p in walls)==wall]
        if voxels:operations.append(dict(kind='paste_component',label='受管理宿主与嵌纹',classification='wall' if wall else 'body',
            lo=[0,0,0],hi=[n-1 for n in model.size],palette=palette,voxels=voxels))
    spec=dict(name=args.get('name','参数化嵌纹构件'),size=list(model.size),anchor=data['anchor'],operations=operations,max_changed_blocks=65536)
    compiled=build(workspace,spec)
    return dict(spec=spec,content_sha256=compiled['content_sha256'],host_content_sha256=data['content_sha256'],
                installations=result['installations'],clearance_constraints=result['clearance_constraints'],verification=result['verification'],model_modified=False)
