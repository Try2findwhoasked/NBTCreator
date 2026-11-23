"""Executable building plans bind spatial intent and style to actual managed geometry."""
from copy import deepcopy
from math import isfinite
from pathlib import Path
import json
import uuid

from nbt_extensions import HandlerRegistry
from nbt_model import AIR_NAMES, state
from nbt_prompts import inside, relative, index_lock, encode, digest
from nbt_project_batch import write

DESIGN_CHECKS=HandlerRegistry('building_design_checks')


def fingerprint(value):return digest(encode(value))


def contract():
    from nbt_catalog import catalog
    return catalog()['architecture']


def normalize(plan):
    from nbt_structure_agent import _schema
    from nbt_whole_validation import check_opening_policy, requires_enclosure, validation_mode
    if len(json.dumps(plan,ensure_ascii=False,allow_nan=False).encode())>1024*1024:raise ValueError('建筑方案超过1MiB')
    _schema(plan,contract()['plan'],'建筑方案')
    plan=deepcopy(plan)
    context = plan['context']
    if validation_mode(context) != 'standalone':
        raise ValueError('当前建筑方案入口使用独立建筑上下文')
    if not context.get('start') or not context.get('targets'):
        raise ValueError('完整建筑方案需要路线起点与目标')
    if requires_enclosure(context) and not context.get('interior_probes'):
        raise ValueError('要求密闭时须提供实际室内探针')
    check_opening_policy(context, context.get('openings', []))
    if 'standards_snapshot' in plan:
        from nbt_architect import validate_standard
        validate_standard(plan['standards_snapshot'])
    for field in ('parts','stairs','connections','rules'):
        plan.setdefault(field,[])
    plan.setdefault('levels',{})
    names=[row['id'] for field in ('parts','stairs','connections') for row in plan[field]]
    if len(names)!=len(set(names)) or 'envelope' in names:raise ValueError('建筑构件和构造系统的ID必须唯一且不使用保留名envelope')
    spaces=[row['id'] for row in plan['spaces']]
    if len(spaces)!=len(set(spaces)):raise ValueError('建筑空间ID重复')
    views=[row['id'] for row in plan['views']]
    if len(views)!=len(set(views)):raise ValueError('视角ID重复')
    if set(row['layer'] for row in plan['views'])!={'massing','structure','detail'}:raise ValueError('建筑方案须覆盖整体、构造和近景三个评审层次')
    for field in ('rules',):
        ids=[row['id'] for row in plan[field]]
        if len(ids)!=len(set(ids)):raise ValueError('设计规则ID重复')
    valid_parts=set(names)|({'envelope'} if plan.get('envelope') else set())
    native_parts={row['id'] for row in plan['parts']}
    for view in plan['views']:
        if ('feet' in view)==('eye' in view):raise ValueError('视角须选择feet或eye之一：'+view['id'])
        if view.get('target_part') and view['target_part'] not in valid_parts:raise ValueError('视角目标构件不存在')
        if 'sample_box' in view:
            if not view.get('target_part') or view['layer']=='massing':
                raise ValueError('局部取景范围须绑定构造或细节视角的 target_part：'+view['id'])
            box=view['sample_box']
            if any(not 0<=a<=b<n for a,b,n in zip(box['lo'],box['hi'],plan['size'])):
                raise ValueError('局部取景范围越界或倒置：'+view['id'])
    if plan.get('envelope'):
        ids=[row['id'] for row in plan['envelope']['volumes']]
        if len(ids)!=len(set(ids)):raise ValueError('围护体积ID重复')
    for relation in plan['connections']:
        applicable={'beam_link':{'axis','width','height'},'bearing_block':{'width','depth','max_gap'}}[relation['kind']]
        if set(relation)-({'id','kind','from','to','material'}|applicable):raise ValueError('连接含不适用字段：'+relation['id'])
        for end in ('from','to'):
            if relation[end]['part'] not in native_parts|({'envelope'} if plan.get('envelope') else set()):raise ValueError('承托端必须引用已有构件或围护')
        if relation['kind']=='beam_link' and 'axis' not in relation:raise ValueError('跨梁需要声明轴')
    required={'palette':('parts','roles'),'argument':('parts','argument_path','value'),'ratio':('parts','numerator','denominator','minimum','maximum'),'extent':('parts','expected_size'),'proportion':('parts','numerator_axis','denominator_axis','minimum','maximum')}
    for rule in plan['rules']:
        if any(key not in rule for key in required[rule['kind']]):raise ValueError('设计规则缺少适用字段：'+rule['id'])
        if set(rule)-({'id','kind'}|set(required[rule['kind']])):raise ValueError('设计规则含不适用字段：'+rule['id'])
        allowed=native_parts if rule['kind'] in ('argument','ratio') else valid_parts
        if not set(rule['parts'])<=allowed or len(set(rule['parts']))!=len(rule['parts']):raise ValueError('规则构件引用不存在或重复')
        if rule['kind'] in ('ratio','proportion') and rule['minimum']>rule['maximum']:raise ValueError('比例规则上下限倒置')
    for row in plan['parts']:
        if row.get('space') and row['space'] not in spaces:raise ValueError('构件引用的功能空间不存在：'+row['id'])
    from nbt_building.intent import validate_intent
    validate_intent(plan, valid_parts)
    from nbt_building.quality_plan import items
    items(plan)
    return plan


def resolve(plan):
    root=deepcopy(plan)
    spaces={row['id']:row for row in root['spaces']}
    def lookup(path,stack):
        if path in stack or len(stack)>32:raise ValueError('建筑设计参数引用循环：'+path)
        keys=path.split('.')
        if not keys or keys[0] not in ('style','levels','spaces'):raise ValueError('设计参数只能引用style、levels或spaces')
        value=spaces if keys[0]=='spaces' else root[keys[0]]
        for key in keys[1:]:
            if not isinstance(value,dict) or key not in value:raise ValueError('设计参数不存在：'+path)
            value=value[key]
        return visit(value,stack+(path,))
    def visit(value,stack=()):
        if isinstance(value,list):return [visit(item,stack) for item in value]
        if not isinstance(value,dict):return value
        if 'design_ref' in value:
            if set(value)-{'design_ref','add'} or not isinstance(value['design_ref'],str):raise ValueError('设计引用只接收design_ref和可选add')
            result=lookup(value['design_ref'],stack)
            if 'add' in value:
                if type(result) not in (int,float) or type(value['add']) not in (int,float):raise ValueError('设计引用add仅用于有限数值')
                result+=value['add']
            return deepcopy(result)
        return {key:visit(item,stack) for key,item in value.items()}
    result=visit(root)
    from nbt_structure_agent import _schema
    _schema(result,contract()['plan'],'解析后的建筑方案')
    def vector(value,integer=False):
        if not isinstance(value,list) or len(value)!=3 or any(type(v) not in ((int,) if integer else (int,float)) or not isfinite(v) for v in value):raise ValueError('建筑坐标需要三个有限数值')
    for rule in result['rules']:
        if rule['kind']=='extent':
            vector(rule['expected_size'],True)
            if any(not 1<=v<=294 for v in rule['expected_size']):raise ValueError('实际尺寸规则需要正整数尺寸')
    for part in result['parts']:
        vector(part['position'],True)
    for view in result['views']:
        for field in ('feet','eye','target'):
            if field in view:vector(view[field])
    for patch in result.get('envelope',{}).get('glazing',[]):
        vector(patch['lo'],True);vector(patch['hi'],True)
        if any(not 0<=patch['lo'][i]<=patch['hi'][i]<result['size'][i] for i in range(3)):raise ValueError('玻璃范围越界或倒置')
    for room in result['spaces']:
        if any(type(v) is not int for v in room['lo']+room['hi']) or any(not 0<=room['lo'][i]<=room['hi'][i]<result['size'][i] for i in range(3)):
            raise ValueError('功能空间范围须为画布内的整数包围盒：'+room['id'])
        if type(room['feet_y']) not in (int,float) or not isfinite(room['feet_y']):raise ValueError('空间脚位必须是有限数值')
        for pose in room['samples']:
            if pose[1]!=room['feet_y'] or any(not room['lo'][i]<=pose[i]<=room['hi'][i]+1 for i in range(3)):
                raise ValueError('空间站位与声明层级或范围不一致：'+room['id'])
    measured_roles = {
        role for feature in result.get('quality', {}).get('style', []) for site in feature['sites']
        for member in site.get('quantitative', {}).get('members', []) for role in member['roles']
    }
    for role in sorted(measured_roles):
        material = result['style']['materials'][role]
        if not isinstance(material, str) or state(material) in AIR_NAMES:
            raise ValueError('风格量化材质角色须为可放置的方块状态：' + role)
    return result


def root(workspace):
    workspace=Path(workspace).resolve();engine=Path(__file__).resolve().parents[2]
    if (workspace==engine.parents[2] and (workspace/'desktop/main.cjs').is_file()) or workspace==engine or workspace.is_relative_to(engine):raise ValueError('建筑方案保存在实际创作项目，不写软件或安装目录')
    return inside(workspace,'nbt_models/_workspaces/project_design/plans')


def plan_file(directory,*parts):
    file=directory.joinpath(*parts).resolve()
    if not file.is_relative_to(directory.resolve()):raise ValueError('建筑方案文件路径越界')
    return file


def stored(workspace,request):
    base=root(workspace).resolve();directory=(base/request['id']).resolve()
    if not directory.is_relative_to(base):raise ValueError('建筑方案目录越界')
    if request.get('revision'):
        files=list(plan_file(directory,'versions').glob(str(request['revision'])+'-*.json'))
        if len(files)!=1:raise ValueError('建筑方案修订不存在或不唯一')
        file=plan_file(directory,'versions',files[0].name)
    else:file=plan_file(directory,'head.json')
    data=json.loads(file.read_text(encoding='utf8'))
    normalize(data['plan'])
    if data.get('id')!=request['id'] or type(data.get('revision')) is not int or data['revision']<1:raise ValueError('建筑方案身份无效')
    if data['sha256']!=fingerprint(data['plan']):raise ValueError('建筑方案内容指纹不符')
    if request.get('revision') and (data['revision']!=request['revision'] or file.name!=str(data['revision'])+'-'+data['sha256']+'.json'):raise ValueError('建筑方案修订与版本文件不符')
    return data


def save(workspace,request):
    plan=normalize(request['plan']);resolve(plan)
    identifier=request.get('id') or 'p'+uuid.uuid4().hex[:24]
    base=root(workspace).resolve();directory=(base/identifier).resolve()
    if not directory.is_relative_to(base):raise ValueError('建筑方案目录越界')
    directory.mkdir(parents=True,exist_ok=True)
    with index_lock(workspace,directory):
        head=plan_file(directory,'head.json')
        old=stored(workspace,dict(id=identifier)) if head.is_file() else dict(revision=0)
        if request['revision']!=old['revision']:raise ValueError('建筑方案父修订已变化')
        sha=fingerprint(plan)
        if old.get('sha256')==sha:return old
        data=dict(schema_version=1,id=identifier,revision=old['revision']+1,sha256=sha,plan=plan)
        target=plan_file(directory,'versions',f"{data['revision']}-{sha}.json")
        if target.exists():raise ValueError('建筑方案版本已存在，未覆盖')
        write(target,data);write(head,data)
        return data


def select(workspace,request):
    if ('plan' in request)==('plan_id' in request):raise ValueError('内联plan与plan_id必须选择一种')
    if 'plan' in request:return normalize(request['plan'])
    return stored(workspace,dict(id=request['plan_id'],**({'revision':request['revision']} if request.get('revision') else {})))['plan']


def part_id(name):return 'part_'+name


def actual_part(model,binding,name):
    if name=='envelope' or name in binding.get('connections',{}) or name in binding.get('stairs',{}):
        identifiers=binding.get('envelope_groups',[]) if name=='envelope' else binding.get('connections',{}).get(name,binding.get('stairs',{}).get(name,[]))
        points={tuple(row['pos']) for identifier in identifiers if identifier in model.instances for row in model.instances[identifier]['baseline'] if model.model.get(tuple(row['pos'])) not in AIR_NAMES}
        points.update(tuple(p) for p in binding.get('systems',{}).get(name,{}).get('positions',[]) if model.model.get(tuple(p)) not in AIR_NAMES)
        return {},points
    identifier=binding['parts'].get(name)
    if not identifier or identifier not in model.instances:raise ValueError('建筑方案构件实例缺失：'+name)
    row=model.instances[identifier]
    return row,{tuple(item['pos']) for item in row['baseline'] if model.model.get(tuple(item['pos'])) not in AIR_NAMES}


def view_sample_points(points, view):
    box=view.get('sample_box')
    if box is None:
        return points
    selected={p for p in points if all(a<=v<=b for v,a,b in zip(p,box['lo'],box['hi']))}
    if not selected:
        raise ValueError('局部取景范围内没有目标构件的实际方块：'+view['id']+' / '+view['target_part'])
    return selected


def surface(model,binding,reference):
    if reference['part']=='envelope':
        from nbt_scene_interfaces import compile_interfaces
        _,points=actual_part(model,binding,'envelope')
        definitions=resolve(binding['plan']).get('envelope',{}).get('interfaces',[])
        interfaces=compile_interfaces(definitions,{p:(model.model.get(p),p in model.walls) for p in points},model.model.size,0,[0,0,0])
        if reference['interface'] not in interfaces:raise ValueError('围护命名接口不存在')
        return dict(interfaces[reference['interface']],object='envelope')
    row,_=actual_part(model,binding,reference['part'])
    name=reference.get('object','body')
    node=next((item for item in row['compiled'].get('objects',[]) if item['id']==name),None)
    from nbt_scene_interfaces import InterfaceError, check_interface_geometry
    interface=reference['interface'];owner=reference['part']+'.'+name
    if node is None or interface not in node.get('interfaces',{}):
        raise InterfaceError('INTERFACE_MISSING','构件接口不存在',interface,owner)
    result=deepcopy(node['interfaces'][interface]);result['object']=owner
    geometry=check_interface_geometry(model.model,set(map(tuple,node.get('voxel_positions',[]))),result,check_external=True)
    if geometry['unknown_shapes']:
        raise InterfaceError('INTERFACE_UNSUPPORTED_SHAPE','接口当前形状无法精确核验',interface,owner,
                             **geometry['unknown_shapes'][0],coordinate_space='world')
    if not geometry['passed']:
        raise InterfaceError('INTERFACE_REMOVED','承托接口的当前几何已移除或被遮挡',interface,owner,
                             missing_faces_half=geometry['missing_faces_half'])
    return result


def cells(model,positions):
    from nbt_collision import collision_cells
    result=set()
    for p in positions:
        half,reason=collision_cells(model.get(p))
        if reason:raise ValueError('构造接触需要受支持的精确形状，不能用保守包络认证')
        result.update(tuple(2*p[i]+q[i] for i in range(3)) for q in half)
    return result


def install_geometry(model,prefix,voxels):
    """Partition an already designed global result without regenerating its seams."""
    groups={}
    owned={tuple(row['pos']) for instance in model.instances.values() for row in instance['baseline'] if row['owned']}
    for p,value in voxels.items():
        if p in owned and model.model.get(p)==value[0] and (p in model.walls)==value[1]:continue
        if not model.model.in_bounds(p):raise ValueError('生成构造越出完整画布')
        key=tuple(v//32 for v in p);groups.setdefault(key,{})[p]=value
    identifiers=[]
    for key,group in sorted(groups.items()):
        origin=[v*32 for v in key];size=[min(32,model.model.size[i]-origin[i]) for i in range(3)]
        palette=sorted({value for value,_ in group.values()});indices={v:i for i,v in enumerate(palette)};operations=[]
        for wall in (False,True):
            rows=[[*[p[i]-origin[i] for i in range(3)],indices[value]] for p,(value,is_wall) in sorted(group.items()) if is_wall==wall]
            if rows:operations.append(dict(kind='paste_component',label='建筑全局构造',classification='wall' if wall else 'body',lo=[0,0,0],hi=[v-1 for v in size],palette=palette,voxels=rows))
        name=prefix+'_'+'_'.join(map(str,key))
        model.install(name,dict(tool='structure',arguments=dict(name='建筑构造',size=size,anchor=[0,0,0],operations=operations,max_changed_blocks=65536)),origin)
        identifiers.append(name)
    return identifiers


def wrapped_recipe(workspace,part):
    from nbt_extensions import compile_recipe
    from nbt_collision import collision_cells
    recipe=part['recipe']
    if recipe['tool']=='scene_compile':return recipe
    try:
        data, metadata = compile_recipe(workspace, recipe)
    except ValueError as error:
        from nbt_working_model import ModelConflict
        if getattr(error, 'conflicts', None):
            raise ModelConflict(error.code, [
                {'coordinate_space': 'recipe', **row, 'part': part['id']} for row in error.conflicts
            ]) from error
        raise ValueError(f"构件 {part['id']} 的配方失败：{error}") from error
    interfaces=part.get('interfaces',[])
    if 'interfaces' not in part and not metadata.get('interfaces') and all(not collision_cells(value)[1] for value in data['palette']):
        interfaces=[dict(id=face,face=face,lo=[0,0,0],hi=[v-1 for v in data['size']]) for face in ('up','down','north','south','east','west')]
    node=dict(id='body',recipe=recipe,lo=[0,0,0])
    if interfaces:node['interfaces']=interfaces
    return dict(tool='scene_compile',arguments=dict(graph=dict(schema_version=1,name=part['id'],size=data['size'],objects=[node])))


def preflight(workspace,request):
    from nbt_collision import state_support
    from nbt_scene_interfaces import InterfaceError
    from nbt_working_model import WorkingModel
    resolved=resolve(select(workspace,request))
    model=WorkingModel(workspace,resolved['size'])
    parts=[]
    underside_xz = request.get('underside_xz', [])
    if underside_xz and not request.get('part'):
        raise ValueError('查询底部高度时须指定 part 和世界坐标 underside_xz')
    wanted = {tuple(point) for point in underside_xz}
    if any(not (0 <= x < resolved['size'][0] and 0 <= z < resolved['size'][2]) for x, z in wanted):
        raise ValueError('underside_xz 世界坐标超出建筑范围')
    for part in resolved['parts']:
        if request.get('part') and request['part']!=part['id']:
            continue
        transform=dict(position=part['position'],quarter_turns=part.get('quarter_turns',0),mirror=part.get('mirror'))
        issues=[]
        try:
            values,compiled=model._compile(wrapped_recipe(workspace,part),transform)
        except InterfaceError as error:
            issues=[dict(row,code=error.code,error=str(error)) for row in error.conflicts]
            # For ordinary recipes, report states even when an interface failed.
            if part['recipe']['tool']=='scene_compile':
                parts.append(dict(id=part['id'],interface_issues=issues,states=None))
                continue
            values,compiled=model._compile(part['recipe'],transform)
        states={}
        underside = {}
        for pos,(state,_) in values.items():
            if state in AIR_NAMES:
                continue
            x, y, z = pos
            column = (x, z)
            if column in wanted and (column not in underside or y < underside[column]['bottom_y']):
                underside[column] = dict(bottom_y=y, state=state)
            row=states.setdefault(state,dict(count=0,positions=[]))
            row['count']+=1
            if len(row['positions'])<8:
                row['positions'].append(list(pos))
        part_result = dict(id=part['id'], interface_issues=issues,
                           interfaces=[dict(object=obj['id'], ids=sorted(obj['interfaces'])) for obj in compiled.get('objects') or []],
                           states=[dict(state=state, **state_support(state), **row) for state, row in sorted(states.items())])
        if underside_xz:
            part_result['underside'] = dict(coordinate_space='world', structural_support_verified=False,
                samples=[dict(xz=column, **underside.get(tuple(column), dict(bottom_y=None, state=None)))
                         for column in underside_xz])
        parts.append(part_result)
    if request.get('part') and not parts:
        raise ValueError('预检构件不存在：'+request['part'])
    return dict(parts=parts,read_only=True,scope='individual_parts',asset_written=False)


def build(workspace,request):
    from nbt_working_model import ModelConflict,WorkingModel,value_at,model_hash
    from nbt_building.construction_systems import CONSTRUCTION_SYSTEMS
    from nbt_building.quality import BLOCKING_CODES, assess, from_model
    plan=select(workspace,request);resolved=resolve(plan);workspace=Path(workspace).resolve()
    source=request.get('source')
    if source:
        if not request.get('source_sha256'):raise ValueError('已有制作源须提供source_sha256')
        original=WorkingModel.open(workspace,source,source_sha256=request['source_sha256'])
        previous=original.architecture
        if previous and request.get('expected_plan_sha256')!=previous['sha256']:raise ValueError('建筑方案父指纹不一致')
        if list(original.model.size)!=resolved['size']:raise ValueError('续版建筑方案不能隐式改变画布')
        normalized=WorkingModel(workspace,resolved['size'],context=resolved['context']).context
        if normalized!=original.context:raise ValueError('续版方案不能替换原保护、预算、开口和路线上下文')
    else:
        original=WorkingModel(workspace,resolved['size'],context=resolved['context'],limits=request.get('limits'));previous=None
    # Compile in a detached scratch candidate. The original bound model enforces
    # every protection, reserved region, aggregate budget and route at commit.
    scratch_context = {key: resolved['context'][key] for key in (
        'openings', 'opening_size', 'openings_policy', 'require_enclosure', 'interior_probes',
        'start', 'targets') if key in resolved['context']}
    scratch=WorkingModel(workspace,resolved['size'],context=dict(scratch_context, mode='standalone'),
        limits=dict(original.limits,max_changed_positions=original.limits['max_written_positions']+len(original.model.blocks)))
    scratch.model.blocks=deepcopy(original.model.blocks);scratch.walls=set(original.walls);scratch.instances=deepcopy(original.instances)
    previous_ids=set((previous or {}).get('generated_instances',[]))
    # Intermediate removal is not the proposed edit. Old policies are enforced
    # against the final candidate below, including protections on removed parts.
    # Clearing only this detached copy permits an unchanged protected rebuild.
    for instance in scratch.instances.values():instance['compiled']['policy']={}
    if previous:
        for identifier in reversed(previous['generated_instances']):
            if identifier in scratch.instances:scratch.remove(identifier)
    binding=dict(schema_version=1,sha256=fingerprint(plan),plan=plan,parts={},generated_instances=[],systems={},connections={},stairs={},envelope_groups=[],retained_policies=deepcopy((previous or {}).get('retained_policies',{})))
    for identifier,instance in original.instances.items():
        policy=instance['compiled'].get('policy',{})
        if any(policy.get(key) for key in ('protected_boxes','reserved_boxes','routes')):
            retained=deepcopy(instance);retained['baseline']=[row for row in instance['baseline'] if any(all(box['lo'][i]<=row['pos'][i]<=box['hi'][i] for i in range(3)) for box in policy.get('protected_boxes',[]))];retained['compiled']['policy'].pop('max_changed_blocks',None)
            binding['retained_policies'][fingerprint([policy,instance['compiled'].get('protected_values',[])])]=retained
    budget=original.limits['max_written_positions']
    if resolved.get('envelope'):
        voxels,receipt=CONSTRUCTION_SYSTEMS.resolve('enclosure')(scratch.model,resolved['envelope'],budget)
        binding['envelope_groups']=install_geometry(scratch,'env',voxels);binding['generated_instances']+=binding['envelope_groups'];binding['systems']['envelope']=receipt
    for part in resolved['parts']:
        identifier=part_id(part['id'])
        scratch.install(identifier,wrapped_recipe(workspace,part),part['position'],quarter_turns=part.get('quarter_turns',0),mirror=part.get('mirror'))
        binding['parts'][part['id']]=identifier;binding['generated_instances'].append(identifier)
    for stair in resolved['stairs']:
        try:
            voxels,receipt=CONSTRUCTION_SYSTEMS.resolve('stair_system')(scratch.model,stair,budget)
        except ModelConflict as error:
            if error.code == 'STAIR_ROUTE_FAILED':
                geometry = error.conflicts[0]['report']['geometry_sha256']
                error.quality = assess(resolved, binding['sha256'], geometry,
                                       conflicts=error.conflicts, code=error.code)
            raise
        identifiers=install_geometry(scratch,'stair_'+stair['id'],voxels)
        binding['generated_instances']+=identifiers;binding['systems'][stair['id']]=receipt;binding['stairs'][stair['id']]=identifiers
    for relation in resolved['connections']:
        spec=dict(relation,_surfaces=[surface(scratch,binding,relation[key]) for key in ('from','to')])
        voxels,receipt=CONSTRUCTION_SYSTEMS.resolve(relation['kind'])(scratch.model,spec,budget)
        identifiers=install_geometry(scratch,'joint_'+relation['id'],voxels)
        binding['generated_instances']+=identifiers;binding['systems'][relation['id']]=receipt;binding['connections'][relation['id']]=identifiers
    for identifier,instance in original.instances.items():
        if identifier not in previous_ids:
            scratch.instances[identifier]['compiled']['policy']=deepcopy(instance['compiled'].get('policy',{}))
    from nbt_whole_validation import requires_enclosure
    if requires_enclosure(scratch.context):
        scratch.seal()
    try:
        scratch.open_declared()
    except ModelConflict as error:
        if error.code in BLOCKING_CODES:
            geometry = error.conflicts[0].get('report', error.conflicts[0]).get('geometry_sha256')
            error.quality = assess(resolved, binding['sha256'], geometry,
                                   conflicts=error.conflicts, code=error.code)
        raise
    # Engine-declared carving updates every generated part's current baseline.
    # Retain owned-air records so the next rebuild can safely remove the same group.
    for identifier in binding['generated_instances']:
        for row in scratch.instances[identifier]['baseline']:
            row['after']=value_at(scratch.model,scratch.walls,tuple(row['pos']))
    positions=set(original.model.blocks)|set(scratch.model.blocks)|original.walls|scratch.walls
    edits=[dict(pos=list(p),before=value_at(original.model,original.walls,p),after=value_at(scratch.model,scratch.walls,p)) for p in sorted(positions)
        if value_at(original.model,original.walls,p)!=value_at(scratch.model,scratch.walls,p)]
    original._instance_policy(scratch.model,scratch.walls,original.instances)
    try:
        original._commit_edits(edits,instances=scratch.instances)
    except ModelConflict as error:
        if error.code in BLOCKING_CODES:
            from nbt_building.intent import check_intent
            from nbt_collision import _Space
            error.quality = assess(resolved, binding['sha256'], scratch.model.fingerprint(),
                validation=dict(architecture=dict(checks=check_intent(scratch, binding, resolved, _Space(scratch.model)))),
                conflicts=error.conflicts,
                code=error.code, volume=scratch.model, style_geometry=(scratch, binding))
        raise
    original.phase='opened';original.model.stage='opened';original.preopening=deepcopy(scratch.preopening);original._closed=deepcopy(scratch._closed)
    original._architecture=binding;original._saved=None
    try:
        # Standalone validation always checks these routes. Obtain its
        # structured witness even when the edit-time route policy is disabled.
        if not original.context.get('require_routes'):
            original._routes(original.model)
        report=original.validate()
    except ModelConflict as error:
        if error.code in BLOCKING_CODES:
            error.quality = assess(resolved, binding['sha256'], original.model.fingerprint(),
                validation=dict(architecture=check_model(original, binding)), conflicts=error.conflicts,
                code=error.code, volume=original.model, style_geometry=(original, binding))
        raise
    if not report['architecture']['passed']:raise ValueError('建筑方案实际检查未通过：'+json.dumps(report['architecture'],ensure_ascii=False))
    result=dict(plan_sha256=binding['sha256'],checks=report,model=original.inspect(),asset_written=False,approval_created=False,nbt_exported=False)
    if request.get('output'):
        output=inside(workspace,request['output']);result['preview']=original.preview(output,[])
    if 'save_draft' in request:
        saved = original.save_draft(name_zh=request['save_draft'].get('name_zh', plan['name']))
        result['saved'] = saved
        result['revision_request'] = dict(source=saved['source'], source_sha256=saved['source_sha256'],
                                          expected_plan_sha256=result['plan_sha256'])
    if 'quality' in plan:
        result['quality'] = from_model(original, validation=report)
    return result


def argument(value,path):
    for key in path:
        if isinstance(value,list) and key.isdecimal() and int(key)<len(value):value=value[int(key)]
        elif isinstance(value,dict) and key in value:value=value[key]
        else:raise ValueError('规则参数路径不存在：'+'.'.join(path))
    return value


@DESIGN_CHECKS.register('palette')
def palette_rule(model,binding,resolved,rule):
    allowed=material_role_names(resolved,rule['roles'])
    violations=[]
    for name in rule['parts']:
        _,positions=actual_part(model,binding,name)
        violations.extend(dict(part=name,pos=list(p),state=model.model.get(p)) for p in sorted(positions) if effective_name(model.model.get(p)) not in allowed)
    return dict(id=rule['id'],kind='palette',passed=not violations,violations=violations[:32])


def material_role_names(resolved, roles):
    from nbt_microfit import companions,options_for

    allowed = set()
    for role in roles:
        if role not in resolved['style']['materials']:
            raise ValueError('材质角色不存在：' + role)
        value = state(resolved['style']['materials'][role])
        allowed.add(effective_name(value))
        for shaped, _ in options_for(value, companions(value, 'wall', None), 'wall')[0]:
            if shaped:
                allowed.add(effective_name(shaped))
    return allowed


def effective_name(value):
    from nbt_registry import effective
    return effective(value)[0]


@DESIGN_CHECKS.register('argument')
def argument_rule(model,binding,resolved,rule):
    parts={row['id']:row for row in resolved['parts']};violations=[]
    for name in rule['parts']:
        actual=argument(parts[name]['recipe']['arguments'],rule['argument_path'])
        # Also check current instance recipe, not merely the original plan text.
        instance,_=actual_part(model,binding,name);current=instance['recipe']
        if current['tool']=='scene_compile' and parts[name]['recipe']['tool']!='scene_compile':current=current['arguments']['graph']['objects'][0]['recipe']
        actual=argument(current['arguments'],rule['argument_path'])
        if actual!=rule['value']:violations.append(dict(part=name,actual=actual,expected=rule['value']))
    return dict(id=rule['id'],kind='argument',passed=not violations,violations=violations)


def actual_size(model,binding,name):
    _,positions=actual_part(model,binding,name)
    if not positions:raise ValueError('设计规则目标没有实际方块')
    return [max(p[i] for p in positions)-min(p[i] for p in positions)+1 for i in range(3)]


@DESIGN_CHECKS.register('extent')
def extent_rule(model,binding,resolved,rule):
    violations=[]
    for name in rule['parts']:
        size=actual_size(model,binding,name)
        if size!=rule['expected_size']:violations.append(dict(part=name,actual=size,expected=rule['expected_size']))
    return dict(id=rule['id'],kind='extent',passed=not violations,violations=violations)


@DESIGN_CHECKS.register('proportion')
def proportion_rule(model,binding,resolved,rule):
    violations=[]
    for name in rule['parts']:
        size=actual_size(model,binding,name);ratio=size['xyz'.index(rule['numerator_axis'])]/size['xyz'.index(rule['denominator_axis'])]
        if not rule['minimum']<=ratio<=rule['maximum']:violations.append(dict(part=name,ratio=ratio))
    return dict(id=rule['id'],kind='proportion',passed=not violations,violations=violations)


@DESIGN_CHECKS.register('ratio')
def ratio_rule(model,binding,resolved,rule):
    violations=[];parts={row['id']:row for row in resolved['parts']}
    for name in rule['parts']:
        instance,_=actual_part(model,binding,name);recipe=instance['recipe']
        if recipe['tool']=='scene_compile' and parts[name]['recipe']['tool']!='scene_compile':recipe=recipe['arguments']['graph']['objects'][0]['recipe']
        numerator=argument(recipe['arguments'],rule['numerator']);denominator=argument(recipe['arguments'],rule['denominator'])
        if type(numerator) not in (int,float) or type(denominator) not in (int,float) or denominator<=0:raise ValueError('比例规则需要有效数值和正分母')
        ratio=numerator/denominator
        if not rule['minimum']<=ratio<=rule['maximum']:violations.append(dict(part=name,ratio=ratio))
    return dict(id=rule['id'],kind='ratio',passed=not violations,violations=violations)


def check_model(model,binding):
    from nbt_collision import _Space
    from nbt_scene_interfaces import interface_contact
    plan=normalize(binding['plan']);resolved=resolve(plan)
    if fingerprint(plan)!=binding['sha256']:raise ValueError('建筑方案绑定指纹不符')
    normalized=model.__class__(model.workspace,resolved['size'],context=resolved['context']).context
    if normalized!=model.context or list(model.model.size)!=resolved['size']:raise ValueError('建筑方案与制作源画布或上下文绑定不符')
    checks=[];space=_Space(model.model)
    for view in resolved['views']:
        if 'sample_box' in view:
            try:
                _,points=actual_part(model,binding,view['target_part'])
                view_sample_points(points,view)
                checks.append(dict(id=view['id'],kind='review_sample_box',passed=True))
            except ValueError as error:
                checks.append(dict(id=view['id'],kind='review_sample_box',passed=False,error=str(error)))
    try:
        model._instance_policy(model.model,model.walls,binding.get('retained_policies',{}))
        checks.append(dict(id='retained_constraints',kind='source_policy',passed=True))
    except (ValueError,KeyError) as error:checks.append(dict(id='retained_constraints',kind='source_policy',passed=False,error=str(error)))
    for room in resolved['spaces']:
        bad=[]
        for pose in room['samples']:
            clearance=room.get('min_clearance',1.8)
            clear=space.standing(pose) and space.clear_box((pose[0]-.3,pose[1],pose[2]-.3),(pose[0]+.3,pose[1]+clearance,pose[2]+.3))
            if not clear:bad.append(pose)
        checks.append(dict(id=room['id'],kind='space_samples',passed=not bad,failed_samples=bad,extent='declared',net_clearance='sampled'))
    from nbt_building.intent import check_intent
    checks.extend(check_intent(model, binding, resolved, space))
    for part in resolved['parts']:
        try:
            _,positions=actual_part(model,binding,part['id']);ok=bool(positions)
            checks.append(dict(id=part['id'],kind='part_presence',passed=ok))
        except ValueError as error:checks.append(dict(id=part['id'],kind='part_presence',passed=False,error=str(error)))
    from nbt_collision import check_routes
    room_targets={room['id']+'_'+str(i):pose for room in resolved['spaces'] for i,pose in enumerate(room['samples'])}
    routes=check_routes(model.model,resolved['context']['start'],room_targets)
    checks.append(dict(id='space_circulation',kind='sample_routes',passed=routes['passed'],report=routes))
    for stair in resolved['stairs']:
        receipt=binding.get('systems',{}).get(stair['id'],{});feet=receipt.get('feet',[]);failed=[]
        for a,b in zip(feet,feet[1:]):
            if not check_routes(model.model,a,[b],max_poses=1000)['passed']:failed.append(dict(start=a,end=b))
        checks.append(dict(id=stair['id'],kind='stair_segments',passed=len(feet)>1 and not failed,failed_segments=failed[:16]))
        # Attached supports and rails are part of this system, not optional decor.
        missing=[p for p in receipt.get('accessory_positions',[]) if model.model.get(tuple(p)) in AIR_NAMES]
        checks.append(dict(id=stair['id']+'_accessories',kind='stair_accessories',passed=not missing,missing=missing[:16]))
    for relation in resolved['connections']:
        positions={tuple(row['pos']) for name in binding['connections'].get(relation['id'],[]) if name in model.instances for row in model.instances[name]['baseline'] if model.model.get(tuple(row['pos'])) not in AIR_NAMES}
        try:
            actual=cells(model.model,positions)
            ok=bool(actual) and all(interface_contact(actual,surface(model,binding,relation[key])) for key in ('from','to'))
            checks.append(dict(id=relation['id'],kind='bearing_contact',passed=ok))
        except ValueError as error:checks.append(dict(id=relation['id'],kind='bearing_contact',passed=False,error=str(error)))
    for rule in resolved['rules']:
        try:checks.append(DESIGN_CHECKS.resolve(rule['kind'])(model,binding,resolved,rule))
        except (ValueError,KeyError,TypeError) as error:checks.append(dict(id=rule['id'],kind=rule['kind'],passed=False,error=str(error)))
    return dict(passed=all(row['passed'] for row in checks),plan_sha256=binding['sha256'],checks=checks,
        style='declared_rules_checked' if resolved['rules'] else 'not_machine_verified',
        textual_standards='bound_snapshot_only' if plan.get('standards_snapshot') else 'not_bound',
        aesthetics='requires_visual_review',structural_load='not_checked',game='not_checked')
