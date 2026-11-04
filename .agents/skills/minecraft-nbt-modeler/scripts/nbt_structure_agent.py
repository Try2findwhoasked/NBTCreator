"""One data-only structure contract for API assistants, CLI agents and the UI."""
import hashlib
import json
import math
import re
import uuid
from pathlib import Path

import nbt_components as library

ROOT=Path(__file__).resolve().parents[1]
SUPPORTED_AGENT_TOOLS={'structure_list','structure_read','structure_view','structure_preview','structure_write','structure_place'}


def definitions():
    tools=json.loads((ROOT/'tool-catalog.json').read_text(encoding='utf8'))['agent_tools']
    if set(tools)!=SUPPORTED_AGENT_TOOLS:raise ValueError('结构Agent目录与Python实现不一致')
    return tools


def _schema(value, schema, label='参数'):
    kind=schema.get('type')
    if isinstance(kind,list):
        if value is None and 'null' in kind:return
        kind=next(k for k in kind if k!='null')
    valid={'object':lambda:isinstance(value,dict),'array':lambda:isinstance(value,list),'string':lambda:isinstance(value,str),
           'integer':lambda:type(value) is int,'number':lambda:type(value) in (int,float) and math.isfinite(value),
           'boolean':lambda:type(value) is bool,'null':lambda:value is None}
    if kind in valid and not valid[kind]():raise ValueError(label+' 类型无效')
    if 'enum' in schema and value not in schema['enum']:raise ValueError(label+' 不在允许列表')
    if kind=='object':
        props=schema.get('properties',{})
        if any(k not in value for k in schema.get('required',[])):raise ValueError(label+' 缺少必需字段')
        if schema.get('additionalProperties') is False and set(value)-set(props):raise ValueError(label+' 含未开放字段')
        for key,child in value.items():
            if key in props:_schema(child,props[key],label+'.'+key)
    if kind=='array':
        if len(value)<schema.get('minItems',0) or len(value)>schema.get('maxItems',1000000):raise ValueError(label+' 数量越界')
        for child in value:_schema(child,schema.get('items',{}),label+'[]')
    if kind=='string':
        if not schema.get('minLength',0)<=len(value)<=schema.get('maxLength',1000000):raise ValueError(label+' 长度越界')
        if 'pattern' in schema and not re.fullmatch(schema['pattern'],value):raise ValueError(label+' 格式无效')
    if kind in ('integer','number') and not schema.get('minimum',-math.inf)<=value<=schema.get('maximum',math.inf):raise ValueError(label+' 越界')


def build(workspace, spec):
    from nbt_assembly import Volume
    from nbt_detail_control import compile_plan,default_settings,simulate_plan
    schema=definitions()['structure_preview']['parameters']['properties']['spec']
    _schema(spec,schema,'结构方案')
    size=library.vector(spec['size']);operations=[]
    catalog=json.loads((ROOT/'tool-catalog.json').read_text(encoding='utf8'))
    group=str(uuid.uuid4())
    for op in spec.get('operations',[]):
        if not isinstance(op,dict) or op.get('kind') not in catalog['tools']:raise ValueError('未知结构工具')
        allowed=set(catalog['common'])|set(catalog['operation_parameters'][op['kind']]['properties'])|{'kind','overwrite'}
        if set(op)-allowed:raise ValueError('结构步骤含未开放字段（不接收代码、路径或写入组）')
        from nbt_operation_parameters import validate_operation
        validate_operation(op)
        operations.append(dict(op,write_group=group) if op['kind'] in ('box','beam','frame','hollow_box','geometry') else dict(op))
    for placed in spec.get('placements',[]):
        data=library.load(workspace,placed['id'])
        if placed['content_sha256']!=data['content_sha256']:raise ValueError('引用构件已变化，请重新读取')
        mapping=placed.get('material_map',{})
        if not isinstance(mapping,dict) or len(mapping)>32 or any(not isinstance(k,str) or not isinstance(v,str) for k,v in mapping.items()):raise ValueError('材质映射须为至多32项的状态名称映射')
        if mapping:
            from nbt_model import state
            replacements={state(k):state(v) for k,v in mapping.items()};data={**data,'palette':[replacements.get(value,value) for value in data['palette']]};data.pop('content_sha256',None);data=library.validate(data)
        compiled=library.placement(data,placed['position'],size,placed.get('quarter_turns',0),placed.get('mirror'),placed.get('overwrite',False))
        operations.extend(compiled['operations'])
    if not operations:raise ValueError('独立结构须包含工具步骤或已有构件放置')
    if len(operations)>128:raise ValueError('展开后的结构步骤超过128项')
    settings=default_settings();settings.update(operations=operations,max_changed_blocks=spec.get('max_changed_blocks',library.MAX_BLOCKS))
    plan=compile_plan(settings,size)
    model,walls,_=simulate_plan(Volume(size),set(),plan,dict(mode='standalone',openings=[],max_changed_blocks=settings['max_changed_blocks']))
    if not model.blocks:raise ValueError('独立结构没有实体方块')
    if spec.get('include_air') and math.prod(size)>library.MAX_BLOCKS:raise ValueError('包含空气时最多65536格')
    values=dict(model.blocks)
    if spec.get('include_air'):
        from itertools import product
        values={p:values.get(p,'minecraft:air') for p in product(*(range(n) for n in size))}
    palette=sorted(set(values.values()));indexes={v:i for i,v in enumerate(palette)}
    return library.validate(dict(schema_version=1,name=spec['name'],size=size,tags=spec.get('tags',[]),
        anchor=spec.get('anchor',[size[0]//2,0,size[2]//2]),palette=palette,blocks=[[*p,indexes[v],p in walls] for p,v in values.items()]))


def _draft_root(workspace):return Path(workspace).resolve()/'nbt_models/_workspaces/structure_agent'


def _preview_fingerprint(directory):
    names=('draft.json','draft.master.json.gz','snapshot.json','thumbnail.jpg','cameras.json')
    if any(not (directory/name).resolve().is_relative_to(directory.resolve()) for name in names):raise ValueError('预览文件超出本次目录')
    record={name:hashlib.sha256((directory/name).read_bytes()).hexdigest() for name in names}
    return hashlib.sha256(json.dumps(record,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def _camera(data,hint):
    _schema(hint,definitions()['structure_preview']['parameters']['properties']['spec']['properties']['camera'],'相机')
    points=[b[:3] for b in data['blocks'] if data['palette'][b[3]] not in ('minecraft:air','minecraft:cave_air','minecraft:void_air')]
    lo=[min(p[i] for p in points) for i in range(3)] if points else [0,0,0]
    hi=[max(p[i] for p in points) for i in range(3)] if points else [n-1 for n in data['size']]
    target=[(lo[i]+hi[i]+1)/2 for i in range(3)];radius=math.sqrt(sum((hi[i]-lo[i]+1)**2 for i in range(3)))/2
    a=math.radians(hint.get('azimuth',45));e=math.radians(hint.get('elevation',25));distance=max(2,radius/math.sin(math.radians(27.5))*1.15)
    direction=[math.sin(a)*math.cos(e),math.sin(e),math.cos(a)*math.cos(e)]
    return dict(id='component',role=data['name'],eye=[target[i]+direction[i]*distance for i in range(3)],target=target,
                up=[0,0,-1] if abs(hint.get('elevation',25))>89 else [0,1,0],fov=55)


def preview(workspace,data,spec=None,reference_sources=None):
    from nbt_assembly import Volume
    from nbt_refine import save_master
    from nbt_task import write_snapshot
    data=library.validate(data)
    directory=_draft_root(workspace)/uuid.uuid4().hex;directory.mkdir(parents=True)
    model=Volume(data['size']);walls=set()
    for x,y,z,index,wall in data['blocks']:
        model.put((x,y,z),data['palette'][index])
        if wall:walls.add((x,y,z))
    camera=_camera(data,(spec or {}).get('camera',{}));source=directory/'draft.master.json.gz';save_master(source,model,walls)
    snapshot=directory/'snapshot.json';view=write_snapshot(source,snapshot,cameras=[camera]);view['name']=data['name']
    snapshot.write_text(json.dumps(view,ensure_ascii=False,separators=(',',':')),encoding='utf8')
    cameras=directory/'cameras.json';cameras.write_text(json.dumps([camera],ensure_ascii=False),encoding='utf8')
    image=directory/'thumbnail.jpg';library.thumbnail(data,image)
    draft=directory/'draft.json';raw=json.dumps(dict(component=data,spec=spec,reference_sources=reference_sources or []),ensure_ascii=False,separators=(',',':')).encode('utf8');draft.write_bytes(raw)
    return dict(preview_id=directory.name,preview_sha256=_preview_fingerprint(directory),content_sha256=data['content_sha256'],name=data['name'],size=data['size'],
                block_count=len(data['blocks']),source=str(source),snapshot=str(snapshot),thumbnail=str(image),cameras=[camera],cameras_file=str(cameras),
                verification=dict(block_states=True,bounds=True,design='pending_visual_review',routes='not_checked',game='not_checked'),model_modified=False,reference_sources=reference_sources or [])


def dispatch(workspace,tool,arguments):
    definition=definitions().get(tool)
    if not definition:raise ValueError('未开放的结构Agent工具')
    _schema(arguments,definition['parameters'])
    if tool=='structure_list':return library.listing(workspace)
    if tool=='structure_read':return library.load(workspace,arguments['id'])
    if tool=='structure_view':
        data=library.load(workspace,arguments['id']);sources=[]
        recipe=library.library_root(workspace)/'recipes'/(arguments['id']+'.json')
        if recipe.is_file():
            if recipe.stat().st_size>library.MAX_BYTES:raise ValueError('资产来源记录过大')
            record=json.loads(recipe.read_text(encoding='utf-8-sig'))
            if record.get('content_sha256')!=data['content_sha256']:raise ValueError('资产来源记录与当前内容不一致')
            sources=record.get('reference_sources',[])
            if not isinstance(sources,list) or len(sources)>16:raise ValueError('资产来源记录无效')
        result=preview(workspace,data,reference_sources=sources);result['reference_history']=True;return result
    if tool=='structure_preview':
        sources=[]
        if arguments.get('reference_bundle'):
            from nbt_retrieval import dispatch as retrieve
            sources=retrieve(workspace,'read',dict(arguments['reference_bundle'],workflow='component'))['sources']
        return preview(workspace,build(workspace,arguments['spec']),arguments['spec'],sources)
    if tool=='structure_write':
        root=_draft_root(workspace).resolve();directory=(root/arguments['preview_id']).resolve();draft=(directory/'draft.json').resolve()
        if not directory.is_relative_to(root) or not draft.is_relative_to(root) or draft.stat().st_size>library.MAX_BYTES:raise ValueError('结构预览路径或大小无效')
        raw=draft.read_bytes()
        if _preview_fingerprint(directory)!=arguments['preview_sha256']:raise ValueError('预览已改变，请重新生成并查看')
        data=json.loads(raw);result=library.store(workspace,data['component'])
        recipes=library.library_root(workspace)/'recipes';recipes.mkdir(exist_ok=True)
        (recipes/(result['id']+'.json')).write_text(json.dumps(dict(spec=data.get('spec'),reference_sources=data.get('reference_sources',[]),preview_sha256=arguments['preview_sha256'],content_sha256=result['content_sha256']),ensure_ascii=False),encoding='utf8')
        return result
    data=library.load(workspace,arguments['id'])
    if arguments['content_sha256']!=data['content_sha256']:raise ValueError('构件内容已变化，请重新读取')
    return dict(library.placement(data,arguments['position'],arguments['size'],arguments.get('quarter_turns',0),arguments.get('mirror'),arguments.get('overwrite',False)),model_modified=False)
