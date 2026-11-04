"""Portable data-only operation recipes and material themes. Compile, never write models."""
import argparse
from copy import deepcopy
import json
import math
import os
from pathlib import Path
import re
import uuid

from nbt_model import AIR_NAMES, compound, state

ROOT=Path(__file__).resolve().parents[1]
CATALOG=json.loads((ROOT/'tool-catalog.json').read_text(encoding='utf8'))
MAX_BYTES=8*1024*1024
NAME=re.compile(r'^[a-z][a-z0-9_]{0,39}$')


def plain(value, keys, label):
    if not isinstance(value,dict) or set(value)-set(keys):raise ValueError(label+'字段无效')
    return value


def vector(value, label='XYZ'):
    if not isinstance(value,list) or len(value)!=3 or any(type(n) is not int for n in value):raise ValueError(label+'须为三个整数')
    return value


def json_data(value, depth=0):
    if depth>24:raise ValueError('配方数据嵌套过深')
    if isinstance(value,dict):
        if any(not isinstance(k,str) or len(k)>100 for k in value):raise ValueError('配方键名无效')
        for v in value.values():json_data(v,depth+1)
    elif isinstance(value,list):
        if len(value)>65536:raise ValueError('配方数组过长')
        for v in value:json_data(v,depth+1)
    elif isinstance(value,str):
        if len(value)>4000:raise ValueError('配方文字过长')
    elif type(value) in (int,float):
        if not math.isfinite(value) or abs(value)>1e9:raise ValueError('配方数值无效')
    elif value is not None and type(value) is not bool:raise ValueError('配方仅接受JSON数据')


def parameter_value(spec, value):
    kind=spec['type']
    if kind=='block':return state(value)
    if kind=='boolean':
        if type(value) is not bool:raise ValueError('参数须为布尔值')
    else:
        if type(value) not in ((int,) if kind=='integer' else (int,float)) or not math.isfinite(value):raise ValueError('参数类型不匹配')
        if not spec.get('min',-1000000)<=value<=spec.get('max',1000000):raise ValueError('参数超出声明范围')
    return value


def resolve(value, specs, values):
    if isinstance(value,dict):
        if 'param' in value:
            plain(value,['param','add'],'参数引用');key=value['param']
            if key not in specs:raise ValueError('未知配方参数：'+str(key))
            result=values[key]
            if 'add' in value:
                if specs[key]['type'] not in ('integer','number') or type(value['add']) not in (int,float) or not math.isfinite(value['add']):raise ValueError('只有数值参数支持加减常量')
                result+=value['add']
            return result
        return {k:resolve(v,specs,values) for k,v in value.items()}
    if isinstance(value,list):return [resolve(v,specs,values) for v in value]
    return value


def validate(data):
    json_data(data)
    plain(data,['schema_version','asset_type','name','tags','archived','parameters','operations','mapping','preserve_shape','id'],'可复用资产')
    if 'id' in data and (not isinstance(data['id'],str) or not re.fullmatch(r'[a-f0-9]{32}',data['id'])):raise ValueError('资产编号无效')
    if data.get('schema_version')!=1 or type(data.get('schema_version')) is not int or data.get('asset_type') not in ('recipe','theme'):raise ValueError('配方或主题版本无效')
    if not isinstance(data.get('name'),str) or not data['name'].strip() or len(data['name'])>80:raise ValueError('名称须为1～80字')
    tags=data.get('tags',[])
    if not isinstance(tags,list) or len(tags)>16 or any(not isinstance(t,str) or not t.strip() or len(t)>32 for t in tags):raise ValueError('标签无效')
    if type(data.get('archived',False)) is not bool:raise ValueError('回收状态须为布尔值')
    result=dict(schema_version=1,asset_type=data['asset_type'],name=data['name'].strip(),tags=list(dict.fromkeys(tags)),archived=data.get('archived',False))
    if data['asset_type']=='theme':
        if set(data)&{'parameters','operations'}:raise ValueError('材质主题不能包含工具步骤')
        mapping=data.get('mapping')
        if not isinstance(mapping,dict) or not 1<=len(mapping)<=64 or type(data.get('preserve_shape',True)) is not bool:raise ValueError('主题需要1～64条材质映射')
        normalized={}
        for before,after in mapping.items():
            a,b=state(before),state(after)
            if a in AIR_NAMES or b in AIR_NAMES or a in normalized:raise ValueError('材质映射不可包含空气或重复原材质')
            normalized[a]=b
        result.update(mapping=normalized,preserve_shape=data.get('preserve_shape',True));return result
    if set(data)&{'mapping','preserve_shape'}:raise ValueError('操作配方不能包含主题字段')
    specs=data.get('parameters',{})
    if not isinstance(specs,dict) or len(specs)>32:raise ValueError('配方最多32个参数')
    for key,spec in specs.items():
        if not isinstance(key,str) or not NAME.fullmatch(key):raise ValueError('参数名使用小写字母、数字和下划线')
        plain(spec,['type','label','default','min','max'],'参数')
        if spec.get('type') not in ('integer','number','block','boolean') or not isinstance(spec.get('label',key),str) or len(spec.get('label',key))>100:raise ValueError('参数声明无效')
        for bound in ('min','max'):
            if bound in spec and (type(spec[bound]) not in (int,float) or not math.isfinite(spec[bound]) or abs(spec[bound])>1000000):raise ValueError('参数上下限无效')
        parameter_value(spec,spec.get('default'))
    operations=data.get('operations')
    if not isinstance(operations,list) or not 1<=len(operations)<=128:raise ValueError('配方需要1～128项工具步骤')
    for op in operations:
        if not isinstance(op,dict) or op.get('kind') not in CATALOG['tools']:raise ValueError('配方含未知工具')
        allowed=set(CATALOG['common'])|set(CATALOG['tools'][op['kind']][1])|{'kind','max_writes','include_boxes','mask_positions'}
        if op['kind'] in ('box','beam','frame','hollow_box','geometry'):allowed.add('overwrite')
        if set(op)-allowed or 'write_group' in op:raise ValueError('配方工具字段不在共用接口内')
    json_data(operations)
    resolve(operations,specs,{k:parameter_value(v,v['default']) for k,v in specs.items()})
    result.update(parameters=deepcopy(specs),operations=deepcopy(operations));return result


def asset_file(workspace, identifier):
    if not isinstance(identifier,str) or not re.fullmatch(r'[a-f0-9]{32}',identifier):raise ValueError('配方或主题编号无效')
    root=(Path(workspace).resolve()/'.nbtcreator/reusable').resolve();file=root/f'{identifier}.json'
    if not file.resolve().is_relative_to(root):raise ValueError('资产路径超出资料库')
    return file


def read_json(file):
    if file.stat().st_size>MAX_BYTES:raise ValueError('配方文件超过8MiB')
    return json.loads(file.read_text(encoding='utf-8-sig'))


def load(workspace, identifier):
    file=asset_file(workspace,identifier)
    return dict(validate(read_json(file)),id=identifier)


def store(workspace, data, identifier=None):
    value=validate(data);identifier=identifier or uuid.uuid4().hex;file=asset_file(workspace,identifier);file.parent.mkdir(parents=True,exist_ok=True)
    text=json.dumps(value,ensure_ascii=False,separators=(',',':'))
    if len(text.encode())>MAX_BYTES:raise ValueError('配方文件超过8MiB')
    temporary=file.with_name(uuid.uuid4().hex+'.tmp')
    try:temporary.write_text(text,encoding='utf8');os.replace(temporary,file)
    finally:temporary.unlink(missing_ok=True)
    return dict(value,id=identifier,file=str(file))


def listing(workspace):
    folder=Path(workspace).resolve()/'.nbtcreator/reusable';items=[];errors=[];index=folder/'index/catalog.json'
    try:previous=read_json(index)
    except (ValueError,OSError):previous={}
    if not isinstance(previous,dict):previous={}
    current={}
    for file in sorted(folder.glob('*.json'),key=lambda p:p.stat().st_mtime_ns,reverse=True):
        try:
            asset_file(workspace,file.stem);stat=file.stat();stamp=[stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns];cached=previous.get(file.stem)
            if isinstance(cached,dict) and cached.get('stamp')==stamp:summary=cached['summary']
            else:
                value=load(workspace,file.stem)
                summary={k:v for k,v in value.items() if k not in ('operations','mapping','parameters')}|dict(operation_count=len(value.get('operations',[])),parameter_count=len(value.get('parameters',{})),material_count=len(value.get('mapping',{})))
            current[file.stem]=dict(stamp=stamp,summary=summary);items.append(dict(summary,file=str(file)))
        except (ValueError,OSError,TypeError,KeyError) as e:errors.append(dict(file=file.name,error=str(e)))
    if current!=previous:
        index.parent.mkdir(parents=True,exist_ok=True);temporary=index.with_name(uuid.uuid4().hex+'.tmp')
        try:temporary.write_text(json.dumps(current,ensure_ascii=False),encoding='utf8');os.replace(temporary,index)
        finally:temporary.unlink(missing_ok=True)
    return dict(items=items,errors=errors)


def remap_state(value, theme):
    from nbt_registry import effective,registry
    original=state(value);name,props=effective(original);target=theme['mapping'].get(original,theme['mapping'].get(name))
    if target is None:return original
    data=compound(target);allowed=registry()['blocks'][data['Name']]['properties'];kept={k:v for k,v in props.items() if v in allowed.get(k,())};kept.update(data.get('Properties',{}));after=state(dict(Name=data['Name'],Properties=kept))
    if theme['preserve_shape']:
        from nbt_collision import collision_cells
        a,reason_a=collision_cells(original);b,reason_b=collision_cells(after)
        if reason_a or reason_b or set(a)!=set(b):raise ValueError('主题不能保持碰撞形状：'+original+' → '+after)
    return after


def remap_operations(operations, theme):
    theme=validate(theme)
    if theme['asset_type']!='theme' or theme['archived']:raise ValueError('请选择可用材质主题')
    def walk(value,key=''):
        if key in ('state','slab') and isinstance(value,str):return remap_state(value,theme)
        if key=='slab_overrides' and isinstance(value,dict):return {remap_state(k,theme):remap_state(v,theme) for k,v in value.items()}
        if isinstance(value,dict):return {k:walk(v,k) for k,v in value.items()}
        if isinstance(value,list):return [remap_state(v,theme) if isinstance(v,str) and key in ('palette','from_states') else walk(v,key) for v in value]
        return value
    return walk(operations)


def translate_operation(operation, offset):
    op=deepcopy(operation)
    def shifted(v):
        if not isinstance(v,list) or len(v)!=3 or any(type(n) not in (int,float) or not math.isfinite(n) for n in v):raise ValueError('配方坐标无效')
        return [v[i]+offset[i] for i in range(3)]
    for key in ('lo','hi','start','end','centre','destination','seed_position','source_anchor','target_anchor','target_lo','target_hi'):
        if key in op:op[key]=shifted(op[key])
    for key in ('seeds','mask_positions','points'):
        if key in op:op[key]=[shifted(v) for v in op[key]]
    for key in ('include_boxes','exclude_boxes'):
        if key in op:op[key]=[dict(box,lo=shifted(box['lo']),hi=shifted(box['hi'])) for box in op[key]]
    if 'footprint' in op:op['footprint']=[[x+offset[0],z+offset[2]] for x,z in op['footprint']]
    def geometry(spec):
        result=deepcopy(spec)
        for key in ('min','max','centre'):
            if key in result:result[key]=shifted(result[key])
        if 'points' in result:result['points']=[shifted(p) for p in result['points']]
        if result.get('shape')=='extrude':
            result['vertices']=[[x+offset[0],z+offset[2]] for x,z in result['vertices']];result['bottom']+=offset[1];result['top']+=offset[1]
        if result.get('shape')=='loft':
            result['sections']=[dict(section,y=section['y']+offset[1],vertices=[[x+offset[0],z+offset[2]] for x,z in section['vertices']]) for section in result['sections']]
        if 'children' in result:result['children']=[geometry(child) for child in result['children']]
        return result
    if 'geometry' in op:op['geometry']=geometry(op['geometry'])
    return op


def operation_bounds(operations):
    lows=[];highs=[]
    for op in operations:
        if op['kind']=='auto_floor':
            if not op.get('include_boxes'):raise ValueError('配方自动地面需声明include_boxes局部范围')
            for box in op['include_boxes']:lows.append(vector(box['lo']));highs.append(vector(box['hi']))
        elif op['kind']=='beam':
            a,b=vector(op['start']),vector(op['end']);radius=(op.get('width',1)-1)//2;lows.append([min(a[i],b[i])-radius for i in range(3)]);highs.append([max(a[i],b[i])+radius for i in range(3)])
        else:lows.append(vector(op['lo']));highs.append(vector(op['hi']))
        if op['kind'] in ('copy_region','move_region','repeat_region'):
            delta=vector(op['offset']);count=op.get('count',1) if op['kind']=='repeat_region' else 1
            if type(count) is not int or not 1<=count<=64:raise ValueError('线性阵列数量须为1～64')
            lows.append([op['lo'][i]+delta[i]*count for i in range(3)]);highs.append([op['hi'][i]+delta[i]*count for i in range(3)])
        if op['kind']=='transform_region':
            destination=vector(op['destination']);shape=[op['hi'][i]-op['lo'][i]+1 for i in range(3)]
            if op.get('quarter_turns',0)%2:shape=[shape[2],shape[1],shape[0]]
            lows.append(destination);highs.append([destination[i]+shape[i]-1 for i in range(3)])
    return [min(v[i] for v in lows) for i in range(3)],[max(v[i] for v in highs) for i in range(3)]


def parameter_fields(operations):
    result=[]
    def walk(v,path):
        if isinstance(v,dict):
            for k,item in v.items():
                if k not in ('kind','label','classification','enabled','overwrite','write_group','voxels'):walk(item,path+[k])
        elif isinstance(v,list):
            for i,item in enumerate(v):walk(item,path+[i])
        elif type(v) in (int,float) or isinstance(v,str) and path[-1]=='state':result.append(dict(path=path,value=v))
    for index,op in enumerate(operations):walk(op,[index])
    return result[:1000]


def capture(operations,name,tags=(),bindings=None):
    if not isinstance(operations,list) or not 1<=len(operations)<=128:raise ValueError('请选择1～128项工具步骤')
    if bindings is None:bindings=[]
    ops=deepcopy(operations)
    for op in ops:op.pop('write_group',None)
    lo,hi=operation_bounds(ops);ops=[translate_operation(op,[-n for n in lo]) for op in ops];specs={};available={tuple(field['path']):field['value'] for field in parameter_fields(ops)}
    if not isinstance(bindings,list) or len(bindings)>32:raise ValueError('最多选择32个可调参数')
    used=set()
    for i,binding in enumerate(bindings):
        plain(binding,['path','name','label','min','max'],'参数绑定');route=tuple(binding.get('path',[]))
        if route not in available or route in used:raise ValueError('参数字段不存在或重复')
        used.add(route);key=binding.get('name','p'+str(i+1));value=available[route];kind='block' if isinstance(value,str) else 'integer' if type(value) is int else 'number'
        if key in specs:raise ValueError('参数名重复')
        specs[key]=dict(type=kind,label=binding.get('label',str(route)),default=value,**{k:binding[k] for k in ('min','max') if k in binding})
        target=ops
        for segment in route[:-1]:target=target[segment]
        target[route[-1]]={'param':key}
    data=validate(dict(schema_version=1,asset_type='recipe',name=name,tags=list(tags),parameters=specs,operations=ops))
    return dict(asset=data,origin=lo,fields=parameter_fields([translate_operation(op,[-n for n in lo]) for op in operations]))


def instantiate(data,values,position,size,overwrite=False,theme=None):
    data=validate(data)
    if data['asset_type']!='recipe' or data['archived']:raise ValueError('请选择可用操作配方')
    if not isinstance(values,dict) or set(values)-set(data['parameters']):raise ValueError('未知参数值')
    values={key:parameter_value(spec,values.get(key,spec['default'])) for key,spec in data['parameters'].items()}
    position,size=vector(position),vector(size)
    if any(n<1 for n in size):raise ValueError('模型尺寸须为正整数')
    if type(overwrite) is not bool:raise ValueError('覆盖开关须为布尔值')
    operations=[translate_operation(op,position) for op in resolve(data['operations'],data['parameters'],values)]
    if theme is not None:operations=remap_operations(operations,theme)
    group=str(uuid.uuid4())
    for op in operations:
        if op['kind'] in ('box','beam','frame','hollow_box','geometry','paste_component','copy_region','repeat_region','transform_region'):op['overwrite']=overwrite
        if op['kind'] in ('box','beam','frame','hollow_box','geometry'):op['write_group']=group
    from nbt_detail_control import compile_plan
    compile_plan(dict(operations=operations),size)
    lo,hi=operation_bounds(operations)
    if any(lo[i]<0 or hi[i]>=size[i] for i in range(3)):raise ValueError('配方超出模型边界')
    return dict(name=data['name'],operations=operations,lo=lo,hi=hi,parameters=values,model_modified=False)


def dispatch(workspace, action, data):
    if action=='list':return listing(workspace)
    if action=='get':return load(workspace,data['id'])
    if action=='save':return store(workspace,data['asset'],data.get('id'))
    if action=='capture':return capture(data['operations'],data['name'],data.get('tags',[]),data.get('bindings',[]))
    if action=='archive':
        value=load(workspace,data['id']);value['archived']=data['archived'];return store(workspace,value,data['id'])
    if action=='compile':return instantiate(load(workspace,data['id']),data.get('values',{}),data['position'],data['size'],data.get('overwrite',False),load(workspace,data['theme']) if data.get('theme') else None)
    raise ValueError('未知配方动作')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--workspace',type=Path,default=Path.cwd());sub=parser.add_subparsers(dest='action',required=True)
    sub.add_parser('list');get=sub.add_parser('get');get.add_argument('--id',required=True)
    save=sub.add_parser('save');save.add_argument('--file',type=Path,required=True);save.add_argument('--id')
    update=sub.add_parser('archive');update.add_argument('--id',required=True);update.add_argument('--archived',choices=['true','false'],required=True)
    cap=sub.add_parser('capture');cap.add_argument('--file',type=Path,required=True);cap.add_argument('--name',required=True);cap.add_argument('--bindings',type=Path)
    use=sub.add_parser('compile');use.add_argument('--id',required=True);use.add_argument('--values',type=Path);use.add_argument('--position',required=True);use.add_argument('--size',required=True);use.add_argument('--overwrite',action='store_true');use.add_argument('--theme')
    args=parser.parse_args()
    try:
        if args.action=='list':result=listing(args.workspace)
        elif args.action=='get':result=load(args.workspace,args.id)
        elif args.action=='save':result=store(args.workspace,read_json(args.file),args.id)
        elif args.action=='archive':
            data=load(args.workspace,args.id);data.pop('id');data['archived']=args.archived=='true';result=store(args.workspace,data,args.id)
        elif args.action=='capture':result=capture(read_json(args.file),args.name,bindings=read_json(args.bindings) if args.bindings else [])
        else:result=instantiate(load(args.workspace,args.id),read_json(args.values) if args.values else {},[int(n) for n in args.position.split(',')],[int(n) for n in args.size.split(',')],args.overwrite,load(args.workspace,args.theme) if args.theme else None)
        print(json.dumps(dict(ok=True,result=result),ensure_ascii=False))
    except Exception as error:print(json.dumps(dict(ok=False,error=str(error)),ensure_ascii=False));raise SystemExit(1)


if __name__=='__main__':main()
