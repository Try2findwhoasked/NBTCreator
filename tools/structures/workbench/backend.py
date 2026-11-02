"""Manage registered SAODG room definitions and pools; geometry stays read-only."""
import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import uuid

from toolkit import TOOLKIT
from generate_sealed_models import read_nbt
from nbt_assembly import Volume
from nbt_model import AIR_NAMES, state

SHAPES = {'single':'单格','long':'长条','square':'方形','l_shape':'L形','t_shape':'T形','cross':'十字形','irregular':'不规则'}
KINDS = {'entrance':'入口','combat':'战斗','elite':'精英','puzzle':'谜题','outpost':'封印大厅','boss':'首领','safe':'安全房'}


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf8')


def resource(workspace, resource_id, category, extension):
    if not isinstance(resource_id, str) or not re.fullmatch(r'[a-z0-9_.-]+:[a-z0-9_/.-]+', resource_id):
        raise ValueError('无效资源ID')
    namespace, name = resource_id.split(':')
    if any(part in {'', '.', '..'} for part in name.split('/')):
        raise ValueError('资源ID包含不安全路径')
    root = Path(workspace).resolve()/'src/main/resources/data'
    target = root/namespace/category/(name+extension)
    target.resolve().relative_to(root.resolve())
    if target.is_symlink():
        raise ValueError('不支持符号链接资源')
    return target


def shape(cells):
    cells = {tuple(p) for p in cells}
    if len(cells) == 1: return 'single'
    xs={p[0] for p in cells}; zs={p[1] for p in cells}
    if len(xs)==1 or len(zs)==1: return 'long'
    if len(cells)==3: return 'l_shape'
    degree=max((sum((x+dx,z+dz) in cells for dx,dz in ((1,0),(-1,0),(0,1),(0,-1))) for x,z in cells),default=0)
    if len(cells)==5 and degree==4: return 'cross'
    if len(cells)==4 and degree==3: return 't_shape'
    if len(cells)==len(xs)*len(zs) and len(xs)==len(zs): return 'square'
    return 'irregular'


def room_parts(data):
    parts=data.get('parts',[])
    if data.get('template'):
        if parts: raise ValueError('template 与 parts 互斥')
        parts=[dict(template=data['template'],offset=[0,0,0])]
    if not isinstance(parts,list) or not parts: raise ValueError('缺少结构分片')
    result=[]
    for index, part in enumerate(parts):
        layered='body_template' in part or 'wall_template' in part
        if layered and (data.get('schema_version',0)<5 or 'template' in part or not all(k in part for k in ('body_template','wall_template'))):
            raise ValueError('分层项必须为 schema 5 的主体/墙面配对')
        keys=('body_template','wall_template') if layered else ('template',)
        offset=part.get('offset',[0,0,0])
        if not isinstance(offset,list) or len(offset)!=3 or any(type(n) is not int or n<0 for n in offset): raise ValueError('分片偏移无效')
        for key in keys:
            result.append(dict(part=index,layer={'template':'完整','body_template':'主体','wall_template':'墙面'}[key],id=part[key],offset=offset))
    return result


def catalog(workspace):
    workspace=Path(workspace).resolve(); root=workspace/'src/main/resources/data/saodg'
    language_file=workspace/'src/main/resources/assets/saodg/lang/zh_cn.json'
    language=read(language_file) if language_file.is_file() else {}
    rooms=[]; dungeons=[]; fingerprints={}; referenced=set()
    for file in sorted((root/'dungeons').rglob('*.json')):
        rid='saodg:'+file.relative_to(root/'dungeons').with_suffix('').as_posix(); resource(workspace,rid,'dungeons','.json')
        data=read(file); fingerprints[str(file)]=sha(file)
        dungeons.append(dict(id=rid,name=language.get(data.get('display_name'),rid),file=str(file),pool=data['layout']['room_pool'],
                             sequences={k:v['sequence'] for k,v in data['difficulties'].items()},grid=data['layout'].get('grid')))
    for file in sorted((root/'rooms').rglob('*.json')):
        rid='saodg:'+file.relative_to(root/'rooms').with_suffix('').as_posix(); resource(workspace,rid,'rooms','.json')
        fingerprints[str(file)]=sha(file); errors=[]
        try:
            data=read(file); size=data['size']; cells=data.get('cells') or [[x,z] for x in range(data.get('footprint',[1,1])[0]) for z in range(data.get('footprint',[1,1])[1])]
            identity=data.get('identity',{}); name_key=identity.get('display_name') or 'room.'+rid.replace(':','.').replace('/','.')
            templates=room_parts(data)
            for template in templates:
                target=resource(workspace,template['id'],'structures','.nbt'); template['file']=str(target); template['exists']=target.is_file()
                template['sha256']=sha(target) if target.is_file() else None
                if target.is_file(): fingerprints[str(target)]=template['sha256']
                else: errors.append('模板缺失：'+template['id'])
                referenced.add(str(target))
            room_shape=shape(cells)
            rooms.append(dict(id=rid,name=language.get(name_key,rid),type=data['type'],type_name=KINDS.get(data['type'],data['type']),shape=room_shape,shape_name=SHAPES[room_shape],
                              cells=cells,size=size,file=str(file),sha256=fingerprints[str(file)],templates=templates,parts=len({t['part'] for t in templates}),
                              priority=data.get('selection_priority',0),schema=data.get('schema_version'),door_y=data.get('door_y',2),rotations=data.get('rotations',[]),ports=data.get('ports',[]),
                              encounter=data.get('encounter'),puzzle=data.get('puzzle'),boss=data.get('boss'),errors=errors))
        except (ValueError,TypeError,KeyError) as error:
            rooms.append(dict(id=rid,name=rid,type='invalid',type_name='定义错误',shape='irregular',shape_name='未识别',file=str(file),templates=[],parts=0,priority=0,cells=[],size=[],errors=[str(error)]))
    ids={r['id'] for r in rooms}
    inventory=[]
    for file in sorted((root/'structures').rglob('*.nbt')):
        if 'beta' in file.relative_to(root/'structures').parts:continue
        inventory.append(dict(file=str(file),referenced=str(file) in referenced))
    revision=hashlib.sha256(json.dumps(fingerprints,sort_keys=True).encode()).hexdigest()
    return dict(rooms=rooms,dungeons=dungeons,revision=revision,root=str(root),templates=len(inventory),
                unbound_templates=[i['file'] for i in inventory if not i['referenced']],
                missing_rooms=sorted({rid for dungeon in dungeons for rid in dungeon['pool'] if rid not in ids}))


def assemble(workspace, room_id):
    file=resource(workspace,room_id,'rooms','.json'); definition=read(file)
    size=definition['size']; model=Volume(size); walls=set(); occupied=set(); inputs={str(file):sha(file)}; part_sizes={}
    for part in room_parts(definition):
        template=resource(workspace,part['id'],'structures','.nbt'); before=sha(template); tag=read_nbt(template)
        if tag.get('DataVersion')!=3465 or tag.get('entities') or 'palettes' in tag: raise ValueError('模板版本/实体格式不支持')
        dims=tag['size']
        if len(dims)!=3 or any(type(n) is not int or not 1<=n<=48 for n in dims):raise ValueError('分片尺寸无效')
        if part['part'] in part_sizes and part_sizes[part['part']]!=dims:raise ValueError('同分片主体与墙面尺寸不同')
        part_sizes[part['part']]=dims
        palette=[state(value) for value in tag['palette']];seen=set()
        for block in tag['blocks']:
            p=tuple(block['pos']);index=block['state']
            if len(p)!=3 or any(type(n) is not int or not 0<=n<dims[i] for i,n in enumerate(p)) or p in seen or 'nbt' in block: raise ValueError('模板坐标/方块实体无效')
            if type(index) is not int or not 0<=index<len(palette):raise ValueError('模板palette索引无效')
            seen.add(p); value=palette[index]; pos=tuple(n+offset for n,offset in zip(p,part['offset']))
            if not model.in_bounds(pos): raise ValueError('分片超出房间尺寸')
            if value in AIR_NAMES: continue
            if pos in occupied:raise ValueError('模板非空气方块重叠')
            occupied.add(pos);model.put(pos,value)
            if part['layer']=='墙面':walls.add(pos)
        if sha(template)!=before:raise ValueError('读取中模板发生变化，请刷新')
        inputs[str(template)]=before
    if sha(file)!=inputs[str(file)]:raise ValueError('读取中房间定义发生变化，请刷新')
    source_hash=hashlib.sha256(json.dumps(inputs,sort_keys=True).encode()).hexdigest()
    return model,walls,source_hash


def snapshot(workspace, room_id, output):
    model,walls,source_hash=assemble(workspace,room_id)
    if output.exists():raise ValueError('保留已有预览，请使用新路径')
    output.parent.mkdir(parents=True,exist_ok=True)
    dump(output,dict(name=room_id+'（模组实际NBT）',size=list(model.size),blocks=[[list(p),v] for p,v in model.blocks.items()],wall_positions=sorted(walls),cameras=[],
                     source_sha256=source_hash,geometry_sha256=model.fingerprint(),source=str(resource(workspace,room_id,'rooms','.json')),
                     verification=dict(scope='48连续坐标只读预览；未验证49运行、碰撞或游戏')))
    return dict(snapshot=str(output),geometry_sha256=model.fingerprint(),size=list(model.size))


def thumbnail(workspace, room_id, cache):
    import numpy as np
    from nbt_preview import make_grid,render
    model,walls,source_hash=assemble(workspace,room_id);cache.mkdir(parents=True,exist_ok=True);target=cache/(source_hash+'.png')
    if not target.is_file():
        sx,sy,sz=model.size; cut=min(sy-2,max(6,int(sy*.6)))
        grid,colors,approx=make_grid(model,'y',cut,'above')
        center=np.array([sx/2,min(cut/2,sy/3),sz/2],dtype=float);distance=max(sx,sz)*1.18
        eye=center+np.array([distance,distance*.85,distance])
        image,visible=render(grid,colors,eye,center,320,210)
        temp=target.with_name(target.stem+'.'+uuid.uuid4().hex+'.png');image.save(temp);os.replace(temp,target)
    return dict(image=str(target),source_sha256=source_hash)


def plan(workspace, request):
    current=catalog(workspace)
    if current['revision']!=request.get('revision'):raise ValueError('模组资源已被其他操作修改，请刷新后重新选择')
    dungeon=next((d for d in current['dungeons'] if d['id']==request.get('dungeon')),None)
    if not dungeon:raise ValueError('未知地牢')
    pool=request.get('pool'); priorities=request.get('priorities',{})
    if not isinstance(pool,list) or not 1<=len(pool)<=256 or any(not isinstance(rid,str) for rid in pool) or len(pool)!=len(set(pool)):raise ValueError('房间池需要1～256个不重复房间')
    rooms={r['id']:r for r in current['rooms']}
    if not set(pool)<=rooms.keys():raise ValueError('房间池引用未登记的房间')
    for rid in pool:
        if rooms[rid]['errors']:raise ValueError('房间定义/模板错误：'+rid+'；'+'；'.join(rooms[rid]['errors']))
    available=Counter(rooms[rid]['type'] for rid in pool)
    required={kind for sequence in dungeon['sequences'].values() for kind in sequence}
    missing=required-available.keys()
    if missing:raise ValueError('不能移除最后一个必要用途房间：'+'、'.join(KINDS.get(kind,kind) for kind in sorted(missing)))
    if not isinstance(priorities,dict):raise ValueError('优先级必须按房间ID填写')
    files=[]
    if pool!=dungeon['pool']:
        file=Path(dungeon['file']);data=read(file);data['layout']['room_pool']=pool
        files.append(dict(file=str(file),before=sha(file),data=data))
    for rid,value in priorities.items():
        if rid not in rooms or type(value) is not int or not 0<=value<=100:raise ValueError('选择优先级必须为0～100整数，且房间已登记')
        if value!=rooms[rid]['priority']:
            file=Path(rooms[rid]['file']);data=read(file);data['selection_priority']=value
            files.append(dict(file=str(file),before=sha(file),data=data))
    return dict(files=files,added=[rid for rid in pool if rid not in dungeon['pool']],removed=[rid for rid in dungeon['pool'] if rid not in pool],priorities=priorities)


def apply_changes(workspace, request, output):
    lock=Path(workspace).resolve()/'build/structure_workbench/mod_structures.lock';lock.parent.mkdir(parents=True,exist_ok=True)
    try:fd=os.open(lock,os.O_WRONLY|os.O_CREAT|os.O_EXCL)
    except FileExistsError:raise ValueError('另一个结构保存正在进行；若进程已退出，请检查并移除 mod_structures.lock')
    os.close(fd);temporaries=[];replaced=[]
    try:
        change=plan(workspace,request)
        if not change['files']:return dict(status='unchanged',changed_files=0)
        output.mkdir(parents=True,exist_ok=False)
        originals={}
        for index,item in enumerate(change['files']):
            file=Path(item['file']);originals[file]=file.read_bytes();backup=output/f'{index:03d}_before.json';backup.write_bytes(originals[file]);item['backup']=str(backup)
            temp=file.with_name(file.name+'.'+uuid.uuid4().hex+'.tmp');dump(temp,item['data']);temporaries.append((file,temp,item['before']))
        # Recheck all resources after preparing the exact backups and temporary files.
        if catalog(workspace)['revision']!=request['revision']:raise ValueError('保存前资源发生变化，未应用，请刷新')
        dump(output/'changes.json',dict(status='prepared',request=request,changes=change))
        for file,temp,before in temporaries:
            if sha(file)!=before:raise ValueError('保存时文件发生变化：'+str(file))
            os.replace(temp,file);replaced.append(file)
        dump(output/'result.json',dict(status='applied',files=[str(file) for file in replaced],note='仅修改源码房间池/优先级；NBT原样保留，未部署、未验证布局或游戏。'))
        return dict(status='applied',changed_files=len(replaced),backup=str(output),catalog=catalog(workspace))
    except Exception as error:
        for file in reversed(replaced):
            rollback=file.with_name(file.name+'.rollback.'+uuid.uuid4().hex);rollback.write_bytes(originals[file]);os.replace(rollback,file)
        if output.is_dir():dump(output/'result.json',dict(status='rolled_back' if replaced else 'rejected',error=str(error),files=[str(file) for file in replaced]))
        raise
    finally:
        for file,temp,before in temporaries:temp.unlink(missing_ok=True)
        lock.unlink(missing_ok=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('command',choices=['catalog','snapshot','thumbnail','apply']);parser.add_argument('--workspace',type=Path,required=True)
    parser.add_argument('--room');parser.add_argument('--output',type=Path);parser.add_argument('--cache',type=Path);parser.add_argument('--request',type=Path);args=parser.parse_args()
    try:
        if args.command=='catalog':result=catalog(args.workspace)
        elif args.command=='snapshot':result=snapshot(args.workspace,args.room,args.output)
        elif args.command=='thumbnail':result=thumbnail(args.workspace,args.room,args.cache)
        else:result=apply_changes(args.workspace,read(args.request),args.output)
        print(json.dumps(dict(ok=True,result=result),ensure_ascii=False))
    except Exception as error:
        print(json.dumps(dict(ok=False,error=str(error)),ensure_ascii=False));return 1
    return 0


if __name__=='__main__':raise SystemExit(main())
