"""Persistent, bounded architectural object graphs compiled by the shared tools."""
from copy import deepcopy
from collections import deque
import hashlib,json,os,re,uuid
from pathlib import Path
from nbt_model import AIR_NAMES
from nbt_modeling_session import canonical,engine_revision

FACES={'up':(1,1),'down':(1,-1),'east':(0,1),'west':(0,-1),'south':(2,1),'north':(2,-1)}
SIX=((1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1))
MAX_BYTES=8*1024*1024
def digest(value):return hashlib.sha256(canonical(value).encode()).hexdigest()
def engine_hash():return digest(engine_revision())
def inside(p,box):return all(a<=v<=b for a,v,b in zip(box['lo'],p,box['hi']))


def pattern_names(value):
    if isinstance(value,dict):return ({value['pattern_ref']} if 'pattern_ref' in value else set())|set().union(*(pattern_names(v) for v in value.values()))
    if isinstance(value,list):return set().union(*(pattern_names(v) for v in value))
    return set()


def bind_patterns(value,bindings):
    if isinstance(value,list):return [bind_patterns(v,bindings) for v in value]
    if not isinstance(value,dict):return value
    result={k:bind_patterns(v,bindings) for k,v in value.items() if k!='pattern_ref'}
    if 'pattern_ref' in value:
        key=value['pattern_ref']
        if key not in bindings:raise ValueError('对象纹样绑定缺失：'+str(key))
        if set(value)&{'preset','sample','pattern_asset'}:raise ValueError('pattern_ref 不能同时指定其他纹样来源')
        result['pattern_asset']=deepcopy(bindings[key])
    return result


def references(value,depth=0):
    if depth>16:raise ValueError('对象表达式嵌套超过16层')
    result=set()
    if isinstance(value,dict):
        if 'measure' in value:
            if set(value)-{'object','measure','offset','multiplier'} or not isinstance(value.get('object'),str):raise ValueError('尺寸引用格式无效')
            result.add(value['object'])
        else:
            for child in value.values():result.update(references(child,depth+1))
    elif isinstance(value,list):
        for child in value:result.update(references(child,depth+1))
    return result


def resolve(value,completed,depth=0):
    if depth>16:raise ValueError('对象表达式嵌套超过16层')
    if isinstance(value,list):return [resolve(v,completed,depth+1) for v in value]
    if not isinstance(value,dict):return value
    if 'measure' in value:
        references(value);item=completed[value['object']];key=value['measure'];lo,hi=item['bounds']['lo'],item['bounds']['hi']
        measures=dict(width=hi[0]-lo[0]+1,height=hi[1]-lo[1]+1,depth=hi[2]-lo[2]+1,
                      min_x=lo[0],min_y=lo[1],min_z=lo[2],max_x=hi[0],max_y=hi[1],max_z=hi[2])
        if key not in measures:raise ValueError('未开放的对象尺寸引用')
        multiplier=value.get('multiplier',1);offset=value.get('offset',0)
        if type(multiplier) is not int or not -16<=multiplier<=16 or type(offset) is not int or not -1024<=offset<=1024:raise ValueError('尺寸引用系数越界')
        return measures[key]*multiplier+offset
    if 'calc' in value:
        if set(value)-{'calc','args','offset'} or value['calc'] not in ('add','subtract','min','max'):raise ValueError('未开放的尺寸运算')
        args=value.get('args');offset=value.get('offset',0)
        if not isinstance(args,list) or not 2<=len(args)<=8 or type(offset) is not int or not -1024<=offset<=1024:raise ValueError('尺寸运算参数无效')
        numbers=resolve(args,completed,depth+1)
        if any(type(n) is not int for n in numbers):raise ValueError('尺寸运算只接受整数')
        if value['calc']=='subtract' and len(numbers)!=2:raise ValueError('subtract恰好接受两个数')
        answer={'add':lambda:sum(numbers),'subtract':lambda:numbers[0]-numbers[1],'min':lambda:min(numbers),'max':lambda:max(numbers)}[value['calc']]()+offset
        if abs(answer)>16384:raise ValueError('尺寸运算结果越界')
        return answer
    return {key:resolve(child,completed,depth+1) for key,child in value.items()}


def order(graph):
    nodes={node['id']:node for node in graph['objects']}
    if len(nodes)!=len(graph['objects']):raise ValueError('建筑对象编号重复')
    dependencies={}
    for key,node in nodes.items():
        if ('lo' in node)==('attach' in node):raise ValueError('对象须在lo或attach中二选一：'+key)
        deps=references(node['recipe'])|references(node.get('lo',[]))|references(node.get('attach',{}))|set(node.get('contacts',[]))
        if 'attach' in node:deps.add(node['attach']['target'])
        if deps-set(nodes):raise ValueError('建筑对象引用缺失：'+key+' → '+','.join(sorted(deps-set(nodes))))
        dependencies[key]=deps
    pending=set(nodes);result=[]
    while pending:
        ready=sorted(key for key in pending if not dependencies[key]&pending)
        if not ready:raise ValueError('建筑对象存在循环依赖：'+','.join(sorted(pending)))
        result.extend(ready);pending.difference_update(ready)
    return nodes,dependencies,result


def halfcells(voxels):
    from nbt_collision import collision_cells
    cells=set()
    for p,(value,_) in voxels.items():
        occupied,reason=collision_cells(value)
        if reason:raise ValueError('对象接触检查遇到未支持的碰撞形状：'+value)
        cells.update(tuple(2*a+b for a,b in zip(p,c)) for c in occupied)
    return cells


def touches(a,b):return any(tuple(x+y for x,y in zip(p,step)) in b for p in a for step in SIX)
def attached(a,b):
    remaining=set(a)
    while remaining:
        p=remaining.pop();queue=deque([p]);contact=False
        while queue:
            p=queue.popleft()
            for step in SIX:
                q=tuple(x+y for x,y in zip(p,step))
                if q in b:contact=True
                if q in remaining:remaining.remove(q);queue.append(q)
        if not contact:return False
    return True


def compile_scene(workspace,graph):
    from nbt_structure_agent import _schema,definitions,dispatch,build
    from nbt_components import placement
    _schema(graph,definitions()['scene_compile']['parameters']['properties']['graph'],'建筑对象图')
    if len(canonical(graph).encode())>512*1024:raise ValueError('建筑对象图超过512KiB')
    for box in [*graph.get('reserved_boxes',[]),*graph.get('protected_boxes',[])]:
        if any(a>b or b>=n for a,b,n in zip(box['lo'],box['hi'],graph['size'])):raise ValueError('保留或保护区域超出对象图范围')
    patterns=graph.get('patterns',[]);bindings={row['id']:row['asset'] for row in patterns}
    if len(bindings)!=len(patterns):raise ValueError('对象图纹样绑定ID重复')
    nodes,deps,sequence=order(graph);completed={};occupancy={};operations=[];geometry={};clearances=[]
    for name in sequence:
        node=nodes[name];recipe=bind_patterns(resolve(node['recipe'],completed),bindings)
        compiled={}
        if recipe['tool']=='structure':
            if recipe['arguments'].get('include_air'):raise ValueError('建筑对象不接受显式空气清除')
            data=build(workspace,recipe['arguments'])
        else:
            compiled=dispatch(workspace,recipe['tool'],recipe['arguments']);data=build(workspace,compiled['spec'])
        turns=node.get('quarter_turns',0)
        if 'attach' in node:
            arguments=recipe['arguments'];host=arguments.get('host',{})
            wall=(recipe['tool'].startswith('pattern_') and arguments.get('surface') in ('wall','column')
                  or recipe['tool']=='parametric_compile' and arguments.get('kind')=='wall'
                  or recipe['tool']=='surface_decorate' and host.get('tool')=='parametric_compile' and host.get('arguments',{}).get('kind')=='wall')
            face=node['attach']['face']
            if wall and face in ('south','west','north','east'):
                if turns:raise ValueError('侧面墙饰由脚本按attach.face定向，不叠加quarter_turns')
                turns={'south':0,'west':1,'north':2,'east':3}[face]
        sx,sy,sz=data['size'];a,b=sx,sz;ax,az=data['anchor'][0],data['anchor'][2]
        for _ in range(turns):ax,az,a,b=b-1-az,ax,b,a
        shape=[a,sy,b];placed=placement(data,[ax,data['anchor'][1],az],shape,turns)
        local={tuple(v[:3]):(op['palette'][v[3]],op['classification']=='wall') for op in placed['operations'] for v in op['voxels'] if op['palette'][v[3]] not in AIR_NAMES}
        low=[min(p[i] for p in local) for i in range(3)];high=[max(p[i] for p in local) for i in range(3)]
        if 'lo' in node:origin=resolve(node['lo'],completed)
        else:
            anchor=node['attach'];target=completed[anchor['target']]['bounds'];axis,sign=FACES[anchor['face']]
            offset=resolve(anchor.get('offset',[0,0,0]),completed)
            if len(offset)!=3 or any(type(v) is not int or abs(v)>1024 for v in offset) or offset[axis]!=0:raise ValueError('贴附偏移须为切向整数，不能沿法向制造间隙')
            origin=[(target['lo'][i]+target['hi'][i]-low[i]-high[i])//2+offset[i] for i in range(3)]
            origin[axis]=(target['hi'][axis]+1-low[axis]) if sign>0 else (target['lo'][axis]-1-high[axis])
        if len(origin)!=3 or any(type(v) is not int for v in origin):raise ValueError('对象lo须解析为三个整数')
        inset=0
        if 'attach' in node:
            anchor=node['attach'];axis,sign=FACES[anchor['face']];other=geometry[anchor['target']]
            if other['cells'] is None:other['cells']=halfcells(other['voxels'])
            for inset in range(anchor.get('max_inset',4)+1):
                trial=list(origin);trial[axis]-=sign*inset
                proposed={tuple(p[i]+trial[i] for i in range(3)):v for p,v in local.items()}
                if not occupancy.keys()&proposed.keys() and attached(halfcells(proposed),other['cells']):origin=trial;break
            else:raise ValueError('对象贴附无法在限定深度内连接真实表面：'+name)
        voxels={tuple(p[i]+origin[i] for i in range(3)):value for p,value in local.items()}
        for constraint in compiled.get('clearance_constraints',[]):
            columns=[]
            for x,y,z in constraint['columns']:
                a,b=sx,sz
                for _ in range(turns):x,z,a,b=b-1-z,x,b,a
                columns.append([x+origin[0],y+origin[1],z+origin[2]])
            clearances.append(dict(object=name,id=constraint['id'],min_clearance=constraint['min_clearance'],columns=columns))
        if any(not all(0<=p[i]<graph['size'][i] for i in range(3)) for p in voxels):raise ValueError('建筑对象超出总尺寸：'+name)
        if occupancy.keys()&voxels.keys():raise ValueError('建筑对象实际体素重叠：'+name)
        if any(inside(p,box) for p in voxels for box in graph.get('reserved_boxes',[])):raise ValueError('建筑对象占用保留空间：'+name)
        required=set(node.get('contacts',[]))|({node['attach']['target']} if 'attach' in node else set())
        cells=halfcells(voxels) if required else None
        for target in sorted(required):
            other=geometry[target]
            if other['cells'] is None:other['cells']=halfcells(other['voxels'])
            ok=attached(cells,other['cells']) if 'attach' in node and node['attach']['target']==target else touches(cells,other['cells'])
            if not ok:raise ValueError('建筑对象未与声明支承面连接：'+name+' → '+target)
        for op in placed['operations']:
            op=deepcopy(op);op['voxels']=[v for v in op['voxels'] if op['palette'][v[3]] not in AIR_NAMES]
            if not op['voxels']:continue
            op['lo']=origin;op['hi']=[origin[i]+shape[i]-1 for i in range(3)];op['label']=name+' · '+op['label'];operations.append(op)
        bounds=dict(lo=[min(p[i] for p in voxels) for i in range(3)],hi=[max(p[i] for p in voxels) for i in range(3)])
        completed[name]=dict(id=name,bounds=bounds,depends_on=sorted(deps[name]),resolved_recipe=recipe,quarter_turns=turns,origin=origin,
                             geometry_sha256=digest([[*p,*value] for p,value in sorted(voxels.items())]),contact_targets=sorted(required))
        completed[name]['surface_inset']=inset
        completed[name]['pattern_refs']=sorted(pattern_names(node['recipe']))
        geometry[name]=dict(voxels=voxels,cells=cells);occupancy.update(voxels)
        if len(occupancy)>graph.get('max_changed_blocks',65536):raise ValueError('建筑对象图超过实际方块预算')
    spec=dict(name=graph['name'],size=graph['size'],anchor=[0,0,0],operations=operations,max_changed_blocks=graph.get('max_changed_blocks',65536))
    data=build(workspace,spec);routes='not_checked'
    if clearances:
        from nbt_assembly import Volume
        from nbt_surface_mount import check_clearance
        whole=Volume(graph['size']);whole.blocks={p:v[0] for p,v in occupancy.items()}
        s=dict(request=dict(normal='down'),lo=[0,0,0],u=0,v=2)
        for constraint in clearances:
            try:check_clearance(s,whole,constraint['columns'],constraint['min_clearance'])
            except ValueError as error:raise ValueError('对象图饰面净空 '+constraint['object']+'/'+constraint['id']+'：'+str(error)) from error
    if graph.get('routes'):
        from nbt_assembly import Volume
        from nbt_collision import check_routes
        model=Volume(graph['size'])
        for p,(value,_) in occupancy.items():model.put(p,value)
        routes=check_routes(model,graph['routes']['start'],graph['routes']['targets'])
        if not routes['passed']:raise ValueError('建筑对象图的声明通路未通过')
    return dict(graph=deepcopy(graph),graph_sha256=digest(graph),content_sha256=data['content_sha256'],spec=spec,objects=[completed[k] for k in sequence],
                compile_order=sequence,engine_sha256=engine_hash(),block_count=len(occupancy),model_modified=False,approval_created=False,
                verification=dict(bounds=True,occupancy=True,reserved_space=True,declared_contacts=True,routes=routes,root_support='not_inferred',structural_load='not_checked'))


def scene_root(workspace,identifier):
    root=Path(workspace).resolve()
    engine=Path(__file__).resolve().parents[1]
    software=engine.parents[2] if engine.parent.name=='skills' and engine.parent.parent.name=='.agents' else None
    if root==engine or root.is_relative_to(engine) or root==software and (root/'desktop/main.cjs').is_file():raise ValueError('建筑对象图保存在创作项目，不写入软件源码或安装目录')
    if not re.fullmatch('[a-f0-9]{32}',identifier):raise ValueError('场景ID无效')
    folder=root/'nbt_models/asset_library/object_scenes'/identifier
    if not folder.resolve().is_relative_to(root):raise ValueError('建筑对象图路径越界')
    return folder


def read_json(file):
    if file.stat().st_size>MAX_BYTES:raise ValueError('建筑对象图文件过大')
    return json.loads(file.read_text(encoding='utf8'))


def read_scene(workspace,arguments):
    folder=scene_root(workspace,arguments['id'])
    if (folder/'head.json').resolve().parent!=folder.resolve():raise ValueError('场景头记录路径越界')
    head=read_json(folder/'head.json');version=arguments.get('version',head['version'])
    if not isinstance(version,str) or not re.fullmatch('[a-f0-9]{64}',version):raise ValueError('场景版本无效')
    file=folder/'versions'/(version+'.json')
    if not file.resolve().is_relative_to(folder.resolve()):raise ValueError('场景版本路径越界')
    raw=file.read_bytes()
    if len(raw)>MAX_BYTES or hashlib.sha256(raw).hexdigest()!=version:raise ValueError('场景版本文件哈希不匹配')
    record=json.loads(raw)
    if record['id']!=arguments['id'] or digest(record['candidate']['graph'])!=record['candidate']['graph_sha256']:raise ValueError('场景身份或对象图已变化')
    if 'version' not in arguments and (record['revision']!=head['revision'] or record['candidate']['graph_sha256']!=head['graph_sha256']):raise ValueError('场景头记录与版本不匹配')
    return dict(record,version=version,file=str(file),current_revision=head['revision'],model_modified=False,approval_created=False)


def atomic(file,raw):
    temporary=file.with_name(uuid.uuid4().hex+'.tmp')
    try:
        with temporary.open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,file)
    finally:temporary.unlink(missing_ok=True)


def save_scene(workspace,arguments):
    from nbt_prompts import index_lock
    candidate=compile_scene(workspace,arguments['graph'])
    if candidate['graph_sha256']!=arguments['graph_sha256'] or candidate['content_sha256']!=arguments['content_sha256']:raise ValueError('对象图或编译内容已变化，请重新检查候选')
    parent=arguments.get('parent');identifier=parent['id'] if parent else uuid.uuid4().hex
    folder=scene_root(workspace,identifier);folder.mkdir(parents=True,exist_ok=True)
    with index_lock(Path(workspace).resolve(),folder):
        if parent:
            previous=read_scene(workspace,dict(id=identifier))
            if previous['revision']!=parent['revision'] or previous['version']!=parent['version']:raise ValueError('建筑对象图版本冲突，请重新读取')
            transition(workspace,previous['candidate'],candidate)
            revision=previous['revision']+1
        else:revision=1
        record=dict(schema_version=1,id=identifier,revision=revision,parent_version=parent['version'] if parent else None,candidate=candidate)
        raw=canonical(record).encode()
        if len(raw)>MAX_BYTES:raise ValueError('场景版本超过8MiB')
        version=hashlib.sha256(raw).hexdigest();versions=folder/'versions';versions.mkdir(exist_ok=True);file=versions/(version+'.json')
        if versions.resolve().parent!=folder.resolve():raise ValueError('场景版本目录越界')
        if file.exists():
            if file.read_bytes()!=raw:raise ValueError('场景版本已变化')
        else:
            with file.open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
        atomic(folder/'head.json',canonical(dict(version=version,revision=revision,graph_sha256=candidate['graph_sha256'])).encode())
    return dict(id=identifier,revision=revision,version=version,graph_sha256=candidate['graph_sha256'],content_sha256=candidate['content_sha256'],file=str(file),model_modified=False,approval_created=False,nbt_exported=False)


def transition(workspace,before,after):
    from nbt_structure_agent import build
    for key in ('size','protected_boxes','reserved_boxes','routes','max_changed_blocks'):
        if before['graph'].get(key)!=after['graph'].get(key):raise ValueError('场景续版须保留原范围、保护、留白、路线和预算约束')
    def voxels(spec):
        data=build(workspace,spec)
        return {tuple(v[:3]):(data['palette'][v[3]],v[4]) for v in data['blocks']}
    old,new=voxels(before['spec']),voxels(after['spec']);writes={p for p in old.keys()|new.keys() if old.get(p)!=new.get(p)}
    if any(inside(p,box) for p in writes for box in before['graph'].get('protected_boxes',[])):raise ValueError('对象联动修改触及保护区域')
    if len(writes)>before['graph'].get('max_changed_blocks',65536):raise ValueError('对象联动超过原图修改预算')
    return writes


def update_scene(workspace,arguments):
    saved=read_scene(workspace,dict(id=arguments['id']))
    if saved['revision']!=arguments['revision'] or saved['version']!=arguments['version']:raise ValueError('建筑对象图版本冲突，请重新读取')
    before=saved['candidate'];graph=deepcopy(before['graph']);nodes={n['id']:n for n in graph['objects']};changed=set()
    pattern_changes=arguments.get('pattern_changes',[])
    if not arguments.get('changes') and not pattern_changes:raise ValueError('对象或纹样绑定变更不能为空')
    bindings={row['id']:row for row in graph.get('patterns',[])};changed_patterns=set()
    for patch in pattern_changes:
        if patch['id'] not in bindings or patch['id'] in changed_patterns:raise ValueError('变更纹样绑定缺失或重复')
        bindings[patch['id']]['asset']=deepcopy(patch['asset']);changed_patterns.add(patch['id'])
    for key,node in nodes.items():
        if pattern_names(node['recipe'])&changed_patterns:changed.add(key)
    patched=set()
    for patch in arguments.get('changes',[]):
        key=patch['id']
        if key not in nodes or key in patched:raise ValueError('变更对象缺失或重复')
        patched.add(key)
        changed.add(key)
        if 'lo' in patch:nodes[key].pop('attach',None)
        if 'attach' in patch:nodes[key].pop('lo',None)
        nodes[key].update(deepcopy(patch))
    _,old_deps,_=order(before['graph']);_,new_deps,_=order(graph);affected=set(changed)
    while True:
        expanded=affected|{key for key in nodes if (old_deps[key]|new_deps[key])&affected}
        if expanded==affected:break
        affected=expanded
    result=compile_scene(workspace,graph)
    old_receipts={n['id']:n for n in before['objects']}
    for node in result['objects']:
        if node['id'] not in affected and node['geometry_sha256']!=old_receipts[node['id']]['geometry_sha256']:raise ValueError('未受影响的对象几何发生变化，请重新审阅完整图')
    writes=transition(workspace,before,result)
    if not writes or len(writes)>arguments.get('max_changed_blocks',65536):raise ValueError('对象联动没有变化或超过修改预算')
    return dict(result,parent=dict(id=saved['id'],revision=saved['revision'],version=saved['version']),changed_objects=sorted(changed),affected_objects=sorted(affected),
                changed_patterns=sorted(changed_patterns),recompiled_objects=result['compile_order'],changed_blocks=len(writes),source_version_unchanged=True)


def dispatch_scene(workspace,tool,args):
    return {'scene_compile':lambda:compile_scene(workspace,args['graph']),'scene_read':lambda:read_scene(workspace,args),
            'scene_save':lambda:save_scene(workspace,args),'scene_update':lambda:update_scene(workspace,args)}[tool]()
