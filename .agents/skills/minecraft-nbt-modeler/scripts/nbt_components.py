"""Portable, data-only voxel component library shared by the UI and agents."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import uuid

from nbt_model import AIR_NAMES, state

MAX_BLOCKS = 65536
MAX_BYTES = 8*1024*1024


def vector(value, label='XYZ'):
    if not isinstance(value, (list, tuple)) or len(value)!=3 or any(type(n) is not int for n in value):
        raise ValueError(label+' 必须是三个整数')
    return list(value)


def content_hash(data):
    body={key:data[key] for key in ('size','anchor','palette','blocks')}
    return hashlib.sha256(json.dumps(body,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def validate(data):
    if not isinstance(data,dict) or type(data.get('schema_version')) is not int or data['schema_version']!=1:
        raise ValueError('不支持的构件格式')
    name=data.get('name')
    if not isinstance(name,str) or not name.strip() or len(name)>80:
        raise ValueError('构件名称须为1～80字')
    size=vector(data.get('size'),'尺寸');anchor=vector(data.get('anchor'),'放置锚点')
    if any(not 1<=n<=64 for n in size) or any(not 0<=anchor[i]<size[i] for i in range(3)):
        raise ValueError('构件每轴尺寸须为1～64格，锚点须位于构件内')
    palette=data.get('palette');blocks=data.get('blocks')
    if not isinstance(palette,list) or not 1<=len(palette)<=4096 or not isinstance(blocks,list) or not 1<=len(blocks)<=MAX_BLOCKS:
        raise ValueError('构件须包含有效材质与1～65536个方块')
    palette=[state(v) for v in palette];seen=set();normalized=[]
    for block in blocks:
        if not isinstance(block,list) or len(block)!=5:
            raise ValueError('构件方块格式须为[x,y,z,材质编号,是否墙层]')
        p=tuple(vector(block[:3]));index,wall=block[3:]
        if p in seen or any(not 0<=p[i]<size[i] for i in range(3)) or type(index) is not int or not 0<=index<len(palette) or type(wall) is not bool:
            raise ValueError('构件包含重复、越界坐标或无效材质/墙层')
        seen.add(p);normalized.append([*p,index,wall and palette[index] not in AIR_NAMES])
    tags=data.get('tags',[])
    if not isinstance(tags,list) or len(tags)>16 or any(not isinstance(t,str) or not t.strip() or len(t)>32 for t in tags):
        raise ValueError('最多16个标签，每个标签1～32字')
    if type(data.get('archived',False)) is not bool:raise ValueError('回收站状态无效')
    result=dict(schema_version=1,name=name.strip(),tags=list(dict.fromkeys(tags)),size=size,anchor=anchor,palette=palette,blocks=sorted(normalized),archived=data.get('archived',False))
    if 'review_status' in data:
        if data['review_status']!='pending_visual_review':raise ValueError('不能通过资产资料声明已经看图验收')
        result['review_status']=data['review_status']
    result['content_sha256']=content_hash(result)
    if data.get('content_sha256') and data['content_sha256']!=result['content_sha256']:
        raise ValueError('构件内容哈希不匹配')
    return result


def library_root(workspace):
    return Path(workspace).resolve()/'.nbtcreator/components'


def component_file(workspace, identifier):
    if not isinstance(identifier,str) or not re.fullmatch(r'[a-f0-9]{32}',identifier):
        raise ValueError('构件编号无效')
    root=library_root(workspace).resolve();file=root/(identifier+'.json')
    if not file.resolve().is_relative_to(root):raise ValueError('构件路径超出资料库')
    return file


def load(workspace, identifier):
    file=component_file(workspace,identifier)
    if file.stat().st_size>MAX_BYTES:raise ValueError('构件文件过大')
    data=json.loads(file.read_text(encoding='utf-8-sig'));valid=validate(data)
    return {**valid,'id':identifier}


def thumbnail(data, target):
    from nbt_assembly import Volume
    from nbt_preview import make_grid,render
    import numpy as np
    model=Volume(data['size'])
    for x,y,z,index,_ in data['blocks']:model.put((x,y,z),data['palette'][index])
    grid,colors,_=make_grid(model)
    size=np.array(data['size'],float);center=size/2;span=float(size.max())
    image,_=render(grid,colors,center+np.array([span,span*.8,-span]),center,384,240)
    image.save(target,'JPEG',quality=85)


def store(workspace, data):
    data=validate(data);data['archived']=False;identifier=uuid.uuid4().hex;file=component_file(workspace,identifier)
    file.parent.mkdir(parents=True,exist_ok=True)
    image=file.with_suffix('.jpg');temporary=file.with_suffix('.tmp')
    try:
        thumbnail(data,image)
        temporary.write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')),encoding='utf8')
        os.replace(temporary,file)
    except Exception:
        image.unlink(missing_ok=True);raise
    finally:temporary.unlink(missing_ok=True)
    return {**{k:v for k,v in data.items() if k not in ('palette','blocks')},'id':identifier,'block_count':len(data['blocks']),'thumbnail':str(image),'file':str(file)}


def listing(workspace):
    root=library_root(workspace);items=[];errors=[]
    index=root/'index/catalog.json'
    try:previous=json.loads(index.read_text(encoding='utf8'))
    except (OSError,ValueError):previous={}
    if not isinstance(previous,dict):previous={}
    current={}
    for file in sorted(root.glob('*.json'),key=lambda p:p.stat().st_mtime_ns,reverse=True):
        try:
            stat=file.stat();stamp=[stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns];cached=previous.get(file.stem)
            if cached and cached.get('stamp')==stamp:summary=cached['summary']
            else:
                data=load(workspace,file.stem)
                summary={**{k:v for k,v in data.items() if k not in ('palette','blocks')},'block_count':len(data['blocks'])}
            current[file.stem]=dict(stamp=stamp,summary=summary)
            items.append({**summary,'thumbnail':str(file.with_suffix('.jpg')) if file.with_suffix('.jpg').is_file() else None,'file':str(file)})
        except (ValueError,OSError,TypeError,KeyError) as error:errors.append(dict(file=file.name,error=str(error)))
    if current!=previous:
        index.parent.mkdir(parents=True,exist_ok=True);temporary=index.with_name(uuid.uuid4().hex+'.tmp')
        temporary.write_text(json.dumps(current,ensure_ascii=False),encoding='utf8');os.replace(temporary,index)
    return dict(items=items,errors=errors)


def update(workspace, identifier, name=None, tags=None, archived=None):
    data=load(workspace,identifier)
    if name is not None:data['name']=name
    if tags is not None:data['tags']=tags
    if archived is not None:data['archived']=archived
    data=validate(data);file=component_file(workspace,identifier);temporary=file.with_name(uuid.uuid4().hex+'.tmp')
    try:
        temporary.write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')),encoding='utf8');os.replace(temporary,file)
    finally:temporary.unlink(missing_ok=True)
    return dict(id=identifier,name=data['name'],tags=data['tags'],archived=data['archived'])


def extract(source, name, lo, hi, tags=(), anchor=None, include_air=False, snapshot=None, snapshot_sha256=None):
    from nbt_refine import read_master
    if type(include_air) is not bool:raise ValueError('是否包含空气须为勾选状态')
    source=Path(source).resolve();baseline=hashlib.sha256(source.read_bytes()).hexdigest()
    model,walls=read_master(source)
    if snapshot:
        file=Path(snapshot);raw=file.read_bytes()
        if not snapshot_sha256 or hashlib.sha256(raw).hexdigest()!=snapshot_sha256:raise ValueError('3D快照已改变，请重新打开')
        view=json.loads(raw)
        if Path(view.get('source','')).resolve()!=source or view.get('source_sha256')!=baseline:raise ValueError('快照不属于当前源版本')
        if view.get('preview_only'):
            from nbt_task import checked_preview_snapshot
            checked_preview_snapshot(file)
            from nbt_assembly import Volume
            model=Volume(view['size'])
            for p,value in view['master_blocks']:model.put(p,value)
            walls={tuple(p) for p in view['wall_positions']}
        elif view.get('geometry_sha256')!=model.fingerprint():raise ValueError('源几何已改变')
    lo,hi=vector(lo),vector(hi);size=[hi[i]-lo[i]+1 for i in range(3)]
    if any(lo[i]<0 or lo[i]>hi[i] or hi[i]>=model.size[i] or size[i]>64 for i in range(3)):
        raise ValueError('请选择模型内每轴不超过64格的构件范围')
    if include_air and math.prod(size)>MAX_BLOCKS:raise ValueError('包含空气的选区超过65536格')
    positions=((x,y,z) for x in range(lo[0],hi[0]+1) for y in range(lo[1],hi[1]+1) for z in range(lo[2],hi[2]+1)) if include_air else (p for p in sorted(model.blocks) if all(lo[i]<=p[i]<=hi[i] for i in range(3)))
    palette=[];indices={};blocks=[]
    for p in positions:
        value=state(model.get(p))
        if value in AIR_NAMES and not include_air:continue
        if value not in indices:indices[value]=len(palette);palette.append(value)
        blocks.append([*[p[i]-lo[i] for i in range(3)],indices[value],p in walls])
        if len(blocks)>MAX_BLOCKS:raise ValueError('构件方块数超过65536')
    data=dict(schema_version=1,name=name,tags=list(tags),size=size,anchor=anchor if anchor is not None else [size[0]//2,0,size[2]//2],palette=palette,blocks=blocks)
    if hashlib.sha256(source.read_bytes()).hexdigest()!=baseline:raise ValueError('保存期间源文件发生变化')
    return dict(component=validate(data),source=str(source),source_sha256=baseline,geometry_sha256=model.fingerprint(),lo=lo,hi=hi,model_size=list(model.size))


def capture(workspace, source, name, lo, hi, tags=(), anchor=None, include_air=False, snapshot=None, snapshot_sha256=None):
    result=extract(source,name,lo,hi,tags,anchor,include_air,snapshot,snapshot_sha256)
    return store(workspace,result['component'])


def placement(data, position, size, quarter_turns=0, mirror=None, overwrite=False):
    data=validate(data);position=vector(position,'放置位置');size=vector(size,'模型尺寸')
    if data['archived']:raise ValueError('构件位于回收站，请先恢复')
    if type(quarter_turns) is not int or mirror not in (None,'x','z') or type(overwrite) is not bool:raise ValueError('旋转、镜像或覆盖配置无效')
    turns=quarter_turns%4;sx,sy,sz=data['size']
    def transformed(p):
        x,y,z=p;a,b=sx,sz
        if mirror=='x':x=a-1-x
        if mirror=='z':z=b-1-z
        for _ in range(turns):x,z,a,b=b-1-z,x,b,a
        return [x,y,z]
    anchor=transformed(data['anchor']);lo=[position[i]-anchor[i] for i in range(3)]
    shape=[sz,sy,sx] if turns%2 else [sx,sy,sz];hi=[lo[i]+shape[i]-1 for i in range(3)]
    if any(lo[i]<0 or hi[i]>=size[i] for i in range(3)):raise ValueError('放置后的构件超出模型边界，请调整锚点位置')
    palette=data['palette']
    if turns or mirror:
        from nbt_tools import transformed_state
        palette=[transformed_state(value,turns,mirror) for value in palette]
    operations=[]
    for wall in (False,True):
        voxels=[[*transformed(b[:3]),b[3]] for b in data['blocks'] if b[4]==wall]
        if voxels:operations.append(dict(kind='paste_component',label=data['name']+(' · 墙层' if wall else ' · 主体'),classification='wall' if wall else 'body',lo=lo,hi=hi,palette=palette,voxels=voxels,overwrite=overwrite))
    return dict(operations=operations,lo=lo,hi=hi,name=data['name'],content_sha256=data['content_sha256'])


def transform_selection(source, lo, hi, position, *, snapshot, snapshot_sha256, quarter_turns=0, mirror=None, overwrite=False, move=False, name='选区构件'):
    """Compile a bound selection transform; the caller still previews/exports it."""
    if type(move) is not bool:raise ValueError('移动开关须为布尔值')
    selected=extract(source,name,lo,hi,snapshot=snapshot,snapshot_sha256=snapshot_sha256)
    placed=placement(selected['component'],position,selected['model_size'],quarter_turns,mirror,overwrite)
    if move:
        # Clear exactly the captured non-air voxels before pasting, so overlap is
        # supported without deleting unrelated contents in the target bounds.
        component=selected['component']
        clear=dict(kind='paste_component',label=name+' · 清除原位置',classification='body',lo=selected['lo'],hi=selected['hi'],
                   palette=['minecraft:air'],voxels=[[*b[:3],0] for b in component['blocks']],overwrite=True)
        placed['operations'].insert(0,clear)
    return dict(placed,source_sha256=selected['source_sha256'],source_geometry_sha256=selected['geometry_sha256'],mode='move' if move else 'copy',model_modified=False)


def batch_placement(data,position,size,counts=None,spacing=None,quarter_turns=0,mirror=None,overwrite=False,theme=None):
    """Grid copies use one immutable component, never copies of previous copies."""
    import itertools
    data=validate(data);counts=vector([1,1,1] if counts is None else counts,'阵列数量');spacing=vector([0,0,0] if spacing is None else spacing,'阵列间距');position=vector(position)
    total=counts[0]*counts[1]*counts[2]
    if any(n<1 or n>64 for n in counts) or total>64 or any(counts[i]>1 and spacing[i]==0 for i in range(3)):raise ValueError('每轴数量须为1～64，总数最多64，重复轴的间距不能为0')
    if len(data['blocks'])*total>MAX_BLOCKS:raise ValueError('阵列合计最多65536格记录，请减少数量或构件大小')
    original_hash=data['content_sha256']
    if theme is not None:
        from nbt_recipes import validate as validate_theme,remap_state
        theme=validate_theme(theme)
        if theme['asset_type']!='theme' or theme['archived']:raise ValueError('请选择可用材质主题')
        data['palette']=[remap_state(value,theme) for value in data['palette']];data.pop('content_sha256');data=validate(data)
    operations=[];seen=set();low=[];high=[]
    for number,cell in enumerate(itertools.product(*(range(n) for n in counts)),1):
        anchor=[position[i]+cell[i]*spacing[i] for i in range(3)]
        patch=placement(data,anchor,size,quarter_turns,mirror,overwrite);low.append(patch['lo']);high.append(patch['hi'])
        for op in patch['operations']:
            points={tuple(op['lo'][i]+v[i] for i in range(3)) for v in op['voxels']}
            if seen&points:raise ValueError('阵列副本的实际方块发生重叠，请增加间距')
            seen.update(points);op['label']=f'{data["name"]} #{number} · '+('墙层' if op['classification']=='wall' else '主体');operations.append(op)
    return dict(name=data['name']+' · 阵列' if total>1 else data['name'],operations=operations,lo=[min(v[i] for v in low) for i in range(3)],hi=[max(v[i] for v in high) for i in range(3)],copies=total,source_component_sha256=original_hash,model_modified=False)


def paste_plan(model, operation, protected):
    lo,hi=vector(operation.get('lo')),vector(operation.get('hi'))
    palette=operation.get('palette');voxels=operation.get('voxels');overwrite=operation.get('overwrite',False)
    if not isinstance(palette,list) or not 1<=len(palette)<=4096 or not isinstance(voxels,list) or not 1<=len(voxels)<=MAX_BLOCKS or type(overwrite) is not bool:raise ValueError('构件粘贴数据无效')
    palette=[state(value) for value in palette];edits={};protected=set(protected)
    for v in voxels:
        if not isinstance(v,list) or len(v)!=4:raise ValueError('构件体素须为[x,y,z,材质编号]')
        p=vector(v[:3]);index=v[3]
        if type(index) is not int or not 0<=index<len(palette) or any(p[i]<0 or p[i]>hi[i]-lo[i] for i in range(3)):raise ValueError('构件体素越界或材质编号无效')
        target=tuple(p[i]+lo[i] for i in range(3));value=palette[index]
        if target in edits:raise ValueError('构件体素重复')
        if target in protected and value!=model.get(target):raise ValueError('构件触及保护区')
        if not overwrite and model.get(target) not in AIR_NAMES and model.get(target)!=value:raise ValueError('构件与已有方块冲突；移动位置或明确勾选允许覆盖')
        edits[target]=value
    budget=operation.get('max_writes',100000)
    if type(budget) is not int or budget<0 or len(edits)>budget:raise ValueError('构件超过写入上限')
    return sorted(edits.items()),dict(kind='paste_component',eligible=len(edits),changed=sum(model.get(p)!=v for p,v in edits.items()))


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--workspace',type=Path,default=Path.cwd());sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('list')
    agent=sub.add_parser('agent');agent.add_argument('--tool',required=True);agent.add_argument('--request',type=Path,required=True)
    save=sub.add_parser('save');save.add_argument('--source',type=Path,required=True);save.add_argument('--name',required=True);save.add_argument('--lo',required=True);save.add_argument('--hi',required=True);save.add_argument('--tags',default='');save.add_argument('--include-air',action='store_true');save.add_argument('--snapshot',type=Path);save.add_argument('--snapshot-sha256')
    imp=sub.add_parser('import');imp.add_argument('--file',type=Path,required=True)
    get=sub.add_parser('get');get.add_argument('--id',required=True)
    ext=sub.add_parser('extract');ext.add_argument('--source',type=Path,required=True);ext.add_argument('--lo',required=True);ext.add_argument('--hi',required=True);ext.add_argument('--name',default='选区构件');ext.add_argument('--snapshot',type=Path);ext.add_argument('--snapshot-sha256')
    trans=sub.add_parser('transform');trans.add_argument('--source',type=Path,required=True);trans.add_argument('--lo',required=True);trans.add_argument('--hi',required=True);trans.add_argument('--name',default='选区构件');trans.add_argument('--snapshot',type=Path,required=True);trans.add_argument('--snapshot-sha256',required=True);trans.add_argument('--position',required=True);trans.add_argument('--quarter-turns',type=int,default=0);trans.add_argument('--mirror',choices=['x','z']);trans.add_argument('--overwrite',action='store_true');trans.add_argument('--move',action='store_true')
    edit=sub.add_parser('update');edit.add_argument('--id',required=True);edit.add_argument('--name');edit.add_argument('--tags');edit.add_argument('--archived',choices=['true','false'])
    place=sub.add_parser('place');place.add_argument('--id',required=True);place.add_argument('--position',required=True);place.add_argument('--size',required=True);place.add_argument('--quarter-turns',type=int,default=0);place.add_argument('--mirror',choices=['x','z']);place.add_argument('--overwrite',action='store_true')
    batch=sub.add_parser('batch',parents=[],help='编译XYZ网格阵列，不直接修改模型');batch.add_argument('--id',required=True);batch.add_argument('--position',required=True);batch.add_argument('--size',required=True);batch.add_argument('--counts',default='1,1,1');batch.add_argument('--spacing',default='0,0,0');batch.add_argument('--quarter-turns',type=int,default=0);batch.add_argument('--mirror',choices=['x','z']);batch.add_argument('--overwrite',action='store_true');batch.add_argument('--theme')
    args=parser.parse_args()
    try:
        xyz=lambda text:[int(v) for v in text.split(',')]
        if args.command=='agent':
            from nbt_structure_agent import dispatch
            if args.request.stat().st_size>MAX_BYTES:raise ValueError('结构参数超过8 MiB')
            result=dispatch(args.workspace,args.tool,json.loads(args.request.read_text(encoding='utf-8-sig')))
        elif args.command=='list':result=listing(args.workspace)
        elif args.command=='get':result=load(args.workspace,args.id)
        elif args.command=='extract':result=extract(args.source,args.name,xyz(args.lo),xyz(args.hi),snapshot=args.snapshot,snapshot_sha256=args.snapshot_sha256)
        elif args.command=='transform':result=transform_selection(args.source,xyz(args.lo),xyz(args.hi),xyz(args.position),snapshot=args.snapshot,snapshot_sha256=args.snapshot_sha256,quarter_turns=args.quarter_turns,mirror=args.mirror,overwrite=args.overwrite,move=args.move,name=args.name)
        elif args.command=='update':result=update(args.workspace,args.id,args.name,args.tags.split(',') if args.tags is not None else None,None if args.archived is None else args.archived=='true')
        elif args.command=='save':result=capture(args.workspace,args.source,args.name,xyz(args.lo),xyz(args.hi),tags=[t.strip() for t in args.tags.split(',') if t.strip()],include_air=args.include_air,snapshot=args.snapshot,snapshot_sha256=args.snapshot_sha256)
        elif args.command=='import':
            if args.file.stat().st_size>MAX_BYTES:raise ValueError('构件文件超过8 MiB')
            result=store(args.workspace,json.loads(args.file.read_text(encoding='utf-8-sig')))
        elif args.command=='batch':
            from nbt_recipes import load as load_theme
            result=batch_placement(load(args.workspace,args.id),xyz(args.position),xyz(args.size),xyz(args.counts),xyz(args.spacing),args.quarter_turns,args.mirror,args.overwrite,load_theme(args.workspace,args.theme) if args.theme else None)
        else:result=placement(load(args.workspace,args.id),xyz(args.position),xyz(args.size),args.quarter_turns,args.mirror,args.overwrite)
        print(json.dumps(dict(ok=True,result=result),ensure_ascii=False));return 0
    except (ValueError,OSError,TypeError,KeyError,AssertionError) as error:
        print(json.dumps(dict(ok=False,error=str(error)),ensure_ascii=False));return 1


if __name__=='__main__':raise SystemExit(main())
