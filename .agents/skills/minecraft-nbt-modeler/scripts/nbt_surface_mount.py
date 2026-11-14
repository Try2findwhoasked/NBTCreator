"""Bound planar installation and layout; all building operations remain candidates."""
from collections import deque
import hashlib,json
from pathlib import Path
from nbt_model import AIR_NAMES
from nbt_registry import effective
from nbt_collision import FULL_CUBES
from nbt_selection_edit import load_selection,sha
from nbt_components import placement

NORMALS={'south':(2,1),'north':(2,-1),'east':(0,1),'west':(0,-1),'up':(1,1),'down':(1,-1)}

def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
def _full(value):return effective(value)[0].split(':',1)[-1] in FULL_CUBES

def _load(workspace,raw):
    request=dict(raw)
    for key in ('source','context','snapshot'):
        if request.get(key):request[key]=str((Path(workspace)/request[key]).resolve())
    if bool(request.get('snapshot'))!=bool(request.get('snapshot_sha256')):raise ValueError('候选快照必须同时提供snapshot和snapshot_sha256')
    context=Path(request['context'])
    if sha(context)!=request['context_sha256']:raise ValueError('保护上下文已变化')
    source,source_hash,model,walls,lo,hi,snapshot_hash=load_selection(request,request.get('snapshot'))
    if snapshot_hash!=request.get('snapshot_sha256'):raise ValueError('候选快照已变化')
    axis,sign=NORMALS[request['normal']]
    if lo[axis]!=hi[axis]:raise ValueError('安装区域必须是沿法向厚度为一格的平面')
    u,v=(0,2) if axis==1 else (0,1) if axis==2 else (2,1)
    width,height=hi[u]-lo[u]+1,hi[v]-lo[v]+1
    if width*height>4096:raise ValueError('单次安装面最多4096格，不能截断查询')
    from nbt_library import canonical_context
    config=canonical_context(context)
    return dict(request=request,source=source,model=model,walls=walls,lo=lo,hi=hi,axis=axis,sign=sign,u=u,v=v,width=width,height=height,config=config,snapshot_hash=snapshot_hash)

def _point(s,u,v,offset=0):
    p=list(s['lo']);p[s['u']]+=u;p[s['v']]+=v;p[s['axis']]+=offset*s['sign'];return tuple(p)

def _unchanged(s):
    r=s['request']
    if sha(s['source'])!=r['source_sha256'] or sha(r['context'])!=r['context_sha256'] or r.get('snapshot') and sha(r['snapshot'])!=s['snapshot_hash']:raise ValueError('计算期间源、候选或保护资料已变化')

def _query(s):
    model=s['model'];r=s['request'];cells=[];gaps=set();safe=set();status={}
    for v in range(s['height']):
        for u in range(s['width']):
            p=_point(s,u,v);value=model.get(p);thickness=0
            if value in AIR_NAMES:kind='air_gap';gaps.add((u,v))
            elif not _full(value):kind='unknown_shape';gaps.add((u,v))
            elif not model.in_bounds(_point(s,u,v,1)) or model.get(_point(s,u,v,1)) not in AIR_NAMES:kind='outward_blocked'
            else:
                for distance in range(8):
                    q=_point(s,u,v,-distance)
                    if not model.in_bounds(q) or not _full(model.get(q)):break
                    thickness+=1
                kind='mountable' if thickness>=r.get('min_support',1) else 'thin_support'
                if kind=='mountable':safe.add((u,v))
            status[u,v]=kind;cells.append(dict(uv=[u,v],status=kind,known_thickness=thickness,wall=p in s['walls']))
    components=[];remaining={uv for uv in gaps if status[uv]=='air_gap'}
    while remaining:
        seed=min(remaining);queue=deque([seed]);remaining.remove(seed);group=[]
        while queue:
            uv=queue.popleft();group.append(uv)
            for step in ((1,0),(-1,0),(0,1),(0,-1)):
                nxt=(uv[0]+step[0],uv[1]+step[1])
                if nxt in remaining:remaining.remove(nxt);queue.append(nxt)
        components.append(dict(lo_uv=[min(p[i] for p in group) for i in range(2)],hi_uv=[max(p[i] for p in group) for i in range(2)],cells=len(group),touches_edge=any(u in (0,s['width']-1) or v in (0,s['height']-1) for u,v in group),classification='unclassified_air_gap'))
    margin=r.get('opening_margin',1);avoid=set()
    for u,v in gaps:
        for du in range(-margin,margin+1):
            for dv in range(-margin,margin+1):avoid.add((u+du,v+dv))
    safe-=avoid
    record=dict(schema_version=1,source_sha256=r['source_sha256'],geometry_sha256=s['model'].fingerprint(),context_sha256=r['context_sha256'],snapshot_sha256=s['snapshot_hash'],
                lo=s['lo'],hi=s['hi'],normal=r['normal'],size_uv=[s['width'],s['height']],min_support=r.get('min_support',1),opening_margin=margin,cells=cells,opening_candidates=components,
                usable_uv=[list(uv) for uv in sorted(safe)],model_modified=False,
                limitations='只确认白名单完整方块的局部接触与几何厚度（最多8格），不推断门窗语义、真实承重或完整玩家路径')
    record['surface_sha256']=digest(record);return record,safe

def _object(workspace,proposal,normal,pattern=False,reuse_backing=False):
    from nbt_parametric import compile_object
    from nbt_structure_agent import build
    kind=proposal['surface'] if pattern else proposal['kind']
    if kind=='cylinder' and pattern:
        raise ValueError('圆柱环绕请使用pattern_cylinder_mount及三维目标框')
    if normal in ('north','south','east','west'):
        if kind not in (('wall','column') if pattern else ('wall',)):raise ValueError('侧墙接口只接受墙饰或柱饰')
        turns={'south':0,'west':1,'north':2,'east':3}[normal]
    elif normal=='down':
        if kind!='ceiling':raise ValueError('顶面下挂接口只接受kind=ceiling')
        turns=0
    else:
        if kind in ('wall','ceiling','column') or pattern and kind!='floor':raise ValueError('地面接口不接受墙饰或吊顶')
        turns=0
    if pattern:
        from nbt_pattern_panel import compile_panel
        compiled=compile_panel(workspace,proposal)
        compiled['recipe_sha256']=digest(dict(parameters=proposal,sample_sha256=compiled['sample_sha256'],content_sha256=compiled['content_sha256']))
    else:
        compiled=compile_object(workspace,proposal)
    data=build(workspace,compiled['spec'])
    if pattern and ('microfit' in compiled or reuse_backing) and kind in ('wall','column','ceiling'):
        # Existing walls/ceilings provide the backing of a micro ornament.
        # Keep only its relief, so a small glyph does not add another wall layer.
        from nbt_components import validate
        data={k:v for k,v in data.items() if k!='content_sha256'}
        axis=1 if kind=='ceiling' else 2;layer=0 if kind=='ceiling' else 1
        data['blocks']=[[*b[:axis],0,*b[axis+1:]] for b in data['blocks'] if b[axis]==layer]
        data['size'][axis]=1;data['anchor'][axis]=0
        data=validate(data)
        if 'microfit' in compiled:compiled['microfit']=dict(compiled['microfit'],backing_reused=True)
    # Anchor and support rectangle in positive-global plane UV coordinates.
    if normal in ('north','east'):anchor=[data['size'][0]-1-data['anchor'][0],data['anchor'][1]]
    elif normal in ('south','west'):anchor=[data['anchor'][0],data['anchor'][1]]
    else:anchor=[data['anchor'][0],data['anchor'][2]]
    dims=[data['size'][0],data['size'][2] if normal in ('up','down') else data['size'][1]]
    return compiled,data,turns,anchor,dims

def _plan(s,data,turns,uv,safe,reserved,protected,fit=None,inlay=False,embed_depth=0):
    if not 0<=uv[0]<s['width'] or not 0<=uv[1]<s['height']:
        raise ValueError('安装锚点超出所选平面')
    position=list(_point(s,*uv,0 if inlay else 1-embed_depth));placed=placement(data,position,list(s['model'].size),turns,overwrite=inlay or embed_depth>0)
    # Every projected written voxel requires a supported backing cell. This is
    # deliberately stricter than a few contact points on arbitrary furniture.
    edits=[];carved=set()
    materials={}
    def check_point(p):
        face=(p[s['u']]-s['lo'][s['u']],p[s['v']]-s['lo'][s['v']])
        if face not in safe or not s['model'].in_bounds(p):raise ValueError('安装面、厚度或开口边距不足')
        if p in reserved:raise ValueError('占用显式留白或使用空间')
        if p in protected:raise ValueError('触及保护区域')
        if embed_depth:
            if p[s['axis']]!=position[s['axis']]:raise ValueError('嵌入纹样只允许一层可见外饰')
            support=s['request'].get('min_support',1)
            if embed_depth+support>8:raise ValueError('嵌入深度与保留支承总厚度超过8格查询上限')
            for distance in range(embed_depth+support):
                q=list(p);q[s['axis']]=s['lo'][s['axis']]-distance*s['sign'];q=tuple(q)
                if not s['model'].in_bounds(q) or not _full(s['model'].get(q)):
                    raise ValueError('嵌入厚度不足，须保留原完整背衬，不能穿透墙或顶壳')
                if distance<embed_depth:
                    if q in reserved:raise ValueError('嵌入或开槽占用显式留白')
                    if q in protected:raise ValueError('嵌入或开槽触及保护区域')
                    if distance<embed_depth-1:carved.add(q)
        elif inlay:
            if p[s['axis']]!=s['lo'][s['axis']]:raise ValueError('地板镶嵌只允许替换安装面一层')
        elif s['model'].get(p) not in AIR_NAMES:raise ValueError('安装空间已有方块，不能覆盖')
    for op in placed['operations']:
        for x,y,z,index in op['voxels']:
            p=tuple(op['lo'][i]+(x,y,z)[i] for i in range(3))
            check_point(p)
            edits.append(p)
            materials[p]=op['palette'][index]
    if carved:
        low=[min(p[i] for p in carved) for i in range(3)]
        high=[max(p[i] for p in carved) for i in range(3)]
        placed['operations'].insert(0,dict(kind='paste_component',label='纹样浅槽',classification='body',
            lo=low,hi=high,palette=['minecraft:air'],
            voxels=[[*[p[i]-low[i] for i in range(3)],0] for p in sorted(carved)],overwrite=True))
        placed['lo']=[min(a,b) for a,b in zip(placed['lo'],low)]
        placed['hi']=[max(a,b) for a,b in zip(placed['hi'],high)]
    connectors={}
    remaining=set(edits)
    contact_coordinate=position[s['axis']]
    for first in sorted(remaining):
        if first not in remaining:
            continue
        remaining.remove(first)
        queue=deque([first])
        touches_surface=False
        group=[]
        while queue:
            point=queue.popleft()
            group.append(point)
            touches_surface |= point[s['axis']]==contact_coordinate
            for axis in range(3):
                for step in (-1,1):
                    neighbor=list(point)
                    neighbor[axis]+=step
                    neighbor=tuple(neighbor)
                    if neighbor in remaining:
                        remaining.remove(neighbor)
                        queue.append(neighbor)
        if touches_surface:
            continue
        if fit is None:
            raise ValueError('构件有未连到安装面的悬空部分')
        axis,sign=s['axis'],s['sign']
        for point in sorted(group,key=lambda p:((p[axis]-contact_coordinate)*sign,p)):
            gap=(point[axis]-contact_coordinate)*sign
            if gap>fit['max_gap']:
                break
            path=[]
            for step in range(gap):
                voxel=list(point)
                voxel[axis]=contact_coordinate+step*sign
                path.append(tuple(voxel))
            try:
                for voxel in path:
                    check_point(voxel)
            except ValueError:
                continue
            for voxel in path:
                if voxel not in materials:
                    connectors.setdefault(voxel,fit.get('material',materials[point]))
            break
        else:
            raise ValueError('悬空部分到安装面的连接被阻挡')
        if gap>fit['max_gap']:
            raise ValueError('悬空部分超出允许连接距离')
    if connectors:
        from nbt_model import state
        connectors={point:state(value) for point,value in connectors.items()}
        palette=sorted(set(connectors.values()))
        if any(not _full(value) for value in palette):
            raise ValueError('贴面连接使用已知完整方块材质，请指定surface_fit.material')
        lo=placed['lo']
        placed['operations'].append(dict(kind='paste_component',label='贴面连接',
            classification='wall' if s['axis']!=1 else 'body',lo=lo,hi=placed['hi'],
            palette=palette,voxels=[
                [*[point[i]-lo[i] for i in range(3)],palette.index(value)]
                for point,value in sorted(connectors.items())],overwrite=False))
    return placed,edits+list(carved)+list(connectors),sorted(connectors)

def dispatch(workspace,tool,arguments):
    s=_load(workspace,arguments['surface']);record,safe=_query(s)
    if tool=='parametric_surface':_unchanged(s);return record
    if arguments['surface_sha256']!=record['surface_sha256']:raise ValueError('安装面上下文已变化，请重新查询')
    from nbt_refine import protections,box_points
    from nbt_detail_control import default_settings,compile_plan,simulate_plan
    is_pattern=tool=='pattern_mount'
    embed_depth=arguments.get('embed_depth',0)
    if type(embed_depth) is not int or not 0<=embed_depth<=6:raise ValueError('embed_depth 须为0～6的整数格')
    if embed_depth and (not is_pattern or arguments['object']['surface']=='floor'):
        raise ValueError('embed_depth 用于平面墙饰、柱饰或吊顶；地板已经平齐镶嵌')
    if embed_depth and arguments.get('surface_fit'):raise ValueError('嵌入使用完整原背衬，不叠加悬空贴面连接')
    compiled,data,turns,anchor,dims=_object(workspace,arguments['object'],s['request']['normal'],is_pattern,embed_depth>0)
    inlay=is_pattern and arguments['object']['surface']=='floor'
    protected=protections(s['model'],s['config']);reserved=set()
    for bounds in arguments.get('reserved_boxes',[]):
        if any(bounds['lo'][i]>bounds['hi'][i] or bounds['hi'][i]>=s['model'].size[i] for i in range(3)):raise ValueError('留白范围无效或超出模型')
        volume=1
        for i in range(3):volume*=bounds['hi'][i]-bounds['lo'][i]+1
        if volume>65536:raise ValueError('单个留白范围超过65536格')
        reserved.update(box_points(bounds['lo'],bounds['hi']))
    if tool in ('parametric_mount','pattern_mount'):anchors=[arguments['anchor_uv']];policy='reject'
    else:
        edge=arguments.get('edge_margin',0);gaps=arguments.get('gap_uv',[2,2]);axes=[]
        for i,n in enumerate((s['width'],s['height'])):
            low=edge+anchor[i];high=n-1-edge-(dims[i]-1-anchor[i])
            if low>high:raise ValueError('对象和边距无法容纳于安装面')
            if arguments.get('pattern','grid')=='center':axes.append([(low+high)//2]);continue
            count=(high-low)//(dims[i]+gaps[i])+1;slack=high-low-(count-1)*(dims[i]+gaps[i]);axes.append([low+slack//2+j*(dims[i]+gaps[i]) for j in range(count)])
        anchors=[[u,v] for v in axes[1] for u in axes[0] if arguments.get('pattern','grid')!='border' or u in (axes[0][0],axes[0][-1]) or v in (axes[1][0],axes[1][-1])]
        if len(anchors)>arguments.get('max_instances',32):raise ValueError('布局实例超过上限；不会静默截断')
        policy=arguments.get('on_conflict','reject')
    operations=[];accepted=[];skipped=[];occupied=set();budget=arguments.get('max_changed_blocks',4096)
    for uv in anchors:
        try:
            placed,points,connections=_plan(s,data,turns,uv,safe,reserved,protected,arguments.get('surface_fit'),inlay,embed_depth)
            if occupied.intersection(points):raise ValueError('布局构件互相重叠')
        except ValueError as error:
            if policy=='reject':raise ValueError(f'安装锚点{uv}失败：{error}') from error
            skipped.append(dict(anchor_uv=uv,reason=str(error)));continue
        if len(occupied)+len(points)>budget:raise ValueError('候选超过总变化预算')
        occupied.update(points);operations.extend(placed['operations']);accepted.append(dict(anchor_uv=uv,lo=placed['lo'],hi=placed['hi'],connector_positions=[list(p) for p in connections]))
    if not operations:raise ValueError('布局没有可安装的对象；'+json.dumps(skipped[:8],ensure_ascii=False))
    if len(operations)>128:raise ValueError('布局展开超过128个操作')
    settings=default_settings();settings.update(operations=operations,max_changed_blocks=budget)
    plan=compile_plan(settings,list(s['model'].size));config=dict(s['config'],max_changed_blocks=budget)
    candidate,candidate_walls,_=simulate_plan(s['model'],s['walls'],plan,config)
    clearance=arguments.get('min_clearance',0)
    if clearance:
        if s['request']['normal']!='down':
            raise ValueError('min_clearance 适用于吊顶')
        lowest={}
        for x,y,z in occupied:
            if candidate.get((x,y,z)) in AIR_NAMES:continue
            lowest[x,z]=min(y,lowest.get((x,z),y))
        for (x,z),y in lowest.items():
            if y<clearance or any(candidate.get((x,y-step,z)) not in AIR_NAMES for step in range(1,clearance+1)):
                raise ValueError('吊顶下方净空不足')
    routes='not_checked'
    if arguments.get('require_routes') or arguments.get('compare_routes') or arguments.get('review'):
        from nbt_mount_review import compare_routes
        routes=compare_routes(s['model'],candidate,config,occupied,required=arguments.get('require_routes',False))
    _unchanged(s)
    result=dict(operations=operations,placements=accepted,skipped=skipped,source_sha256=s['request']['source_sha256'],geometry_sha256=s['model'].fingerprint(),surface_sha256=record['surface_sha256'],context_sha256=s['request']['context_sha256'],snapshot_sha256=s['snapshot_hash'],candidate_geometry_sha256=candidate.fingerprint(),recipe_sha256=compiled['recipe_sha256'],changed_blocks=len(occupied),max_changed_blocks=budget,model_modified=False,approval_created=False,
                verification=dict(mount_contact=True,opening_margin=True,protection=True,occupancy=True,budget=True,routes=routes,min_clearance=clearance,structural_load='not_checked',design='pending_visual_review'))
    if is_pattern:
        orientations={}
        for op in operations:
            for *_,index in op['voxels']:
                name,props=effective(op['palette'][index])
                if name.endswith('_stairs'):
                    key=props['facing']+'/'+props['half']
                    orientations[key]=orientations.get(key,0)+1
        result['pattern']=dict(surface=compiled['surface'],sample_sha256=compiled['sample_sha256'],
                               shape_counts=compiled['shape_counts'],fitting=compiled['fitting'],inlay=inlay or embed_depth>0,
                               embed_depth=embed_depth,placement_mode='inlay' if inlay or embed_depth==1 else 'recessed' if embed_depth>1 else 'raised',
                               world_stair_orientations=orientations,orientation_policy=compiled['orientation_policy'])
        if 'microfit' in compiled:result['pattern']['microfit']=compiled['microfit']
        if 'visual_quality' in compiled:result['pattern']['visual_quality']=compiled['visual_quality']
    result['plan_sha256']=digest(dict(result=result,arguments=arguments))
    if arguments.get('review'):
        from nbt_mount_review import write_review
        result['review']=write_review(workspace,s,candidate,candidate_walls,result,arguments['review'])
        _unchanged(s)
    return result
