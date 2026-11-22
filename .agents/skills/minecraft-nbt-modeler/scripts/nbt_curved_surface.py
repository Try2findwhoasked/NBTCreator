"""Plan bounded relief on an actual host using hash-bound loft sections."""
from bisect import bisect_right
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile

from nbt_collision import collision_cells
from nbt_large_assembly import MAX_AXIS,_workspace_path,is_assembly_source,read_assembly,require_creative_workspace
from nbt_model import AIR_NAMES,state
from nbt_reference_views import MAX_MANIFEST,verify_fit
from nbt_refine import protections
from nbt_surface_mount import _full
from nbt_working_model import ModelConflict,WorkingModel,digest,model_hash,value_at

MAX_MASK=4*1024*1024
MAX_FACE_SAMPLES=8192
ROLE=re.compile(r'^[a-z][a-z0-9_-]{0,31}$')


def _sha(file):
    result=hashlib.sha256()
    with Path(file).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):result.update(chunk)
    return result.hexdigest()


def _mask(file,expected,workspace=None):
    if not isinstance(expected,str) or not re.fullmatch('[a-f0-9]{64}',expected):raise ValueError('纹样掩模哈希无效')
    if not file.is_file() or file.stat().st_size>MAX_MASK:raise ValueError('纹样掩模不存在或过大')
    with file.open('rb') as stream:raw=stream.read(MAX_MASK+1)
    if len(raw)>MAX_MASK or hashlib.sha256(raw).hexdigest()!=expected:raise ValueError('纹样掩模哈希不一致')
    try:data=json.loads(raw)
    except (ValueError,UnicodeDecodeError):raise ValueError('纹样掩模 JSON 无效') from None
    if isinstance(data,dict) and 'composition' in data:
        if workspace is None:raise ValueError('来源绑定的曲面掩模须提供创作工作区')
        workspace=Path(workspace).resolve();file=_workspace_path(workspace,str(file));base=workspace/'nbt_models/_workspaces/curve-masks'
        if file.name!='mask.json' or not file.parent.is_relative_to(base) or file.parent==base:
            raise ValueError('来源绑定的曲面掩模路径无效')
        from nbt_curve_components import _verify_data
        data,_=_verify_data(workspace,file,data,expected)
    if isinstance(data,dict) and type(data.get('schema_version')) is int and data['schema_version']==2:
        return _layered_mask(data),raw
    return _single_mask(data),raw


def _single_mask(data):
    if not isinstance(data,dict) or set(data)!={'schema_version','name','rows','palette'} or type(data['schema_version']) is not int or data['schema_version']!=1:
        raise ValueError('纹样掩模格式无效')
    if not isinstance(data['name'],str) or not 1<=len(data['name'].strip())<=120:raise ValueError('纹样掩模名称无效')
    rows,palette=data['rows'],data['palette']
    if not isinstance(rows,list) or not 1<=len(rows)<=64 or any(not isinstance(row,str) or not 1<=len(row)<=64 for row in rows):
        raise ValueError('纹样掩模每轴须为1至64')
    width=len(rows[0])
    if any(len(row)!=width for row in rows) or not isinstance(palette,dict):raise ValueError('纹样掩模须为等宽行与符号表')
    symbols=set(''.join(rows))-{'.'}
    if not symbols or any(not re.fullmatch('[A-Z0-9]',symbol) for symbol in symbols) or set(palette)!=symbols:
        raise ValueError('纹样掩模符号与符号表不一致')
    normalized={}
    for symbol,entry in palette.items():
        if not isinstance(entry,dict) or entry.get('kind') not in ('raise','cut','inlay'):
            raise ValueError('纹样动作无效')
        kind=entry['kind'];required={'kind','role'}|({'height','state','wall'} if kind=='raise' else {'depth','backing'}|({'state','wall'} if kind=='inlay' else set()))
        optional=set() if kind=='raise' else {'max_effective_depth'}
        if not required<=set(entry) or set(entry)-required-optional or not isinstance(entry['role'],str) or not ROLE.fullmatch(entry['role']):raise ValueError('纹样动作字段或用途无效')
        if kind=='raise':
            if type(entry['height']) is not int or not 1<=entry['height']<=3:raise ValueError('凸饰高度须为1至3格')
        else:
            if type(entry['depth']) is not int or type(entry['backing']) is not int or not 1<=entry['depth']<=6 or not 1<=entry['backing']<=8 or entry['depth']+entry['backing']>8:
                raise ValueError('切深与保留背衬须合计不超过8格')
            if 'max_effective_depth' in entry and (type(entry['max_effective_depth']) is not int or
                not entry['depth']<=entry['max_effective_depth']<=6 or entry['max_effective_depth']+entry['backing']>8):
                raise ValueError('最大实际切深与保留背衬须合计不超过8格')
        item=dict(entry)
        if kind in ('raise','inlay'):
            if type(entry['wall']) is not bool or not isinstance(entry['state'],str):raise ValueError('纹样状态或墙层无效')
            item['state']=state(entry['state']);cells,reason=collision_cells(item['state'])
            if item['state'] in AIR_NAMES or reason or not cells:raise ValueError('纹样仅接受已知实体、半砖或楼梯状态')
        normalized[symbol]=item
    return dict(name=data['name'].strip(),rows=rows,palette=normalized)


def _layered_mask(data):
    if (set(data)!={'schema_version','name','layers','overlaps'} or not isinstance(data['name'],str) or
        not 1<=len(data['name'].strip())<=120 or not isinstance(data['layers'],list) or not 1<=len(data['layers'])<=8 or
        not isinstance(data['overlaps'],list) or len(data['overlaps'])>28):
        raise ValueError('分层纹样掩模格式无效')
    layers=[];ids=set();size=None
    for entry in data['layers']:
        if (not isinstance(entry,dict) or not {'id','rows','palette'}<=set(entry) or
            set(entry)-{'id','rows','palette','support_expectations','connections'} or not isinstance(entry['id'],str) or
            not ROLE.fullmatch(entry['id']) or entry['id'] in ids):
            raise ValueError('分层纹样编号或字段无效')
        ids.add(entry['id'])
        pattern=_single_mask(dict(schema_version=1,name=entry['id'],rows=entry['rows'],palette=entry['palette']))
        current=(len(pattern['rows'][0]),len(pattern['rows']))
        if size is not None and current!=size:raise ValueError('分层纹样须共用相同的 UV 尺寸')
        size=current;expectations=entry.get('support_expectations',{})
        if not isinstance(expectations,dict) or set(expectations)-set(pattern['palette']):raise ValueError('分层支承声明无效')
        normalized={}
        for symbol,expected in expectations.items():
            if (pattern['palette'][symbol]['kind']!='raise' or not isinstance(expected,dict) or set(expected)!={'state','wall'} or
                not isinstance(expected['state'],str) or type(expected['wall']) is not bool):
                raise ValueError('分层支承声明须属于凸饰并指定状态与墙层')
            block=state(expected['state']);cells,reason=collision_cells(block)
            if not _full(block) or reason or len(cells)!=8:raise ValueError('分层支承声明须为已知完整方块')
            normalized[symbol]=[block,expected['wall']]
        connections=entry.get('connections',{})
        if (not isinstance(connections,dict) or set(connections)-{'raised','recess'} or
            any(type(value) is not bool for value in connections.values())):
            raise ValueError('分层连接范围须为 raised／recess 的布尔值')
        layers.append(dict(id=entry['id'],rows=pattern['rows'],palette=pattern['palette'],support_expectations=normalized,connections=dict(connections)))
    pairs=set()
    for pair in data['overlaps']:
        if not isinstance(pair,list) or len(pair)!=2 or any(not isinstance(item,str) or item not in ids for item in pair) or pair[0]==pair[1]:
            raise ValueError('分层重叠声明无效')
        key=tuple(sorted(pair))
        if key in pairs:raise ValueError('分层重叠声明重复')
        pairs.add(key)
    overlap_uv=set();overlap_details=[];overlap_pairs=0
    for index,left in enumerate(layers):
        for right in layers[index+1:]:
            pair=tuple(sorted((left['id'],right['id'])))
            for v,(a,b) in enumerate(zip(left['rows'],right['rows'])):
                for u,(x,y) in enumerate(zip(a,b)):
                    if x=='.' or y=='.':continue
                    if pair not in pairs:raise ValueError('分层 UV 重叠未声明：'+str(dict(layers=list(pair),uv=[u,v])))
                    overlap_uv.add((u,v));overlap_pairs+=1
                    if len(overlap_details)<256:overlap_details.append(dict(layers=list(pair),uv=[u,v]))
    return dict(name=data['name'].strip(),layers=layers,overlaps=sorted(pairs),overlapping_uv=len(overlap_uv),
                overlap_pairs=overlap_pairs,overlap_details=overlap_details,overlap_details_truncated=overlap_pairs>len(overlap_details))


def _surface_point(sections,y,u):
    heights=[section['y'] for section in sections]
    if not heights[0]<=y<=heights[-1]:raise ValueError('纹样高度超出放样截面')
    index=min(len(heights)-2,max(0,bisect_right(heights,y)-1))
    a,b=sections[index],sections[index+1];t=(y-a['y'])/(b['y']-a['y'])
    vertices=[[a['vertices'][j][i]*(1-t)+b['vertices'][j][i]*t for i in range(2)] for j in range(len(a['vertices']))]
    area=sum(vertices[j][0]*vertices[(j+1)%len(vertices)][1]-vertices[(j+1)%len(vertices)][0]*vertices[j][1] for j in range(len(vertices)))
    if abs(area)<1e-8:raise ValueError('曲面截面退化')
    position=(u%1)*len(vertices);segment=int(math.floor(position))%len(vertices);fraction=position-math.floor(position)
    p,q=vertices[segment],vertices[(segment+1)%len(vertices)]
    tangent=[q[0]-p[0],q[1]-p[1]];length=math.hypot(*tangent)
    if length<1e-8:raise ValueError('曲面截面存在退化边')
    sign=1 if area>0 else -1
    return [p[i]+(q[i]-p[i])*fraction for i in range(2)],[sign*tangent[1]/length,-sign*tangent[0]/length]


def _actual_face(model,expected,normal,y,maximum):
    candidates=[];cx,cz=map(math.floor,expected);radius=math.ceil(maximum)+2
    for x in range(cx-radius,cx+radius+1):
        for z in range(cz-radius,cz+radius+1):
            p=(x,y,z)
            if not model.in_bounds(p) or not _full(model.get(p)):continue
            for dx,dz in ((1,0),(-1,0),(0,1),(0,-1)):
                outward=(x+dx,y,z+dz);alignment=dx*normal[0]+dz*normal[1]
                if alignment<.25 or not model.in_bounds(outward) or model.get(outward) not in AIR_NAMES:continue
                face=(x+.5+dx*.5,z+.5+dz*.5);distance=math.dist(face,expected)
                if distance<=maximum:
                    candidates.append((distance*distance+(1-alignment)*.25,-alignment,p,(dx,0,dz),distance))
    if not candidates:raise ValueError('找不到与截面法向一致的实际外露支承面')
    candidates.sort();best=candidates[0]
    if len(candidates)>1 and abs(candidates[1][0]-best[0])<1e-9 and candidates[1][2:4]!=best[2:4]:
        raise ValueError('实际外露面存在等距歧义，请调整采样位置')
    return best[2],best[3],best[4]


def _components(points):
    remaining=set(points);components=0
    while remaining:
        components+=1;frontier=[remaining.pop()]
        while frontier:
            pos=frontier.pop()
            for axis in range(3):
                for step in (-1,1):
                    neighbor=list(pos);neighbor[axis]+=step;neighbor=tuple(neighbor)
                    if neighbor in remaining:remaining.remove(neighbor);frontier.append(neighbor)
    return components


def _sample_cells(sample):
    cells=set()
    for change in sample['changes']:
        pos=change['pos'];value=change['after'][0]
        if value in AIR_NAMES:shape=[(x,y,z) for x in (0,1) for y in (0,1) for z in (0,1)]
        else:
            shape,reason=collision_cells(value)
            if reason or not shape:raise ValueError('曲面纹样包含不支持的半格碰撞形状')
        cells.update(tuple(2*pos[i]+cell[i] for i in range(3)) for cell in shape)
    return cells


def _continuity(samples,rows,wrap):
    by_uv={tuple(item['uv']):item for item in samples};pairs=[];broken=0;fragmented=[];total=0
    geometry={uv:_sample_cells(sample) for uv,sample in by_uv.items()}
    height,width=len(rows),len(rows[0])
    for (u,v),sample in sorted(by_uv.items()):
        components=_components(geometry[(u,v)])
        if components>1:fragmented.append(dict(uv=[u,v],components=components))
        neighbors=[]
        if u+1<width:neighbors.append((u+1,v))
        elif wrap and width>2:neighbors.append((0,v))
        if v+1<height:neighbors.append((u,v+1))
        # Diagonal-only mask cells are a stroke too. When an intermediate
        # same-symbol cell exists its two face-adjacency checks suffice.
        if v+1<height:
            for step in (-1,1):
                next_u=u+step
                if wrap:next_u%=width
                if not 0<=next_u<width or next_u==u:continue
                diagonal=by_uv.get((next_u,v+1))
                side=by_uv.get((next_u,v));above=by_uv.get((u,v+1))
                if (diagonal and diagonal['symbol']==sample['symbol'] and
                    not (side and side['symbol']==sample['symbol']) and
                    not (above and above['symbol']==sample['symbol']) and (next_u,v+1) not in neighbors):
                    neighbors.append((next_u,v+1))
        for next_uv in neighbors:
            other=by_uv.get(next_uv)
            if not other or other['symbol']!=sample['symbol']:continue
            total+=1
            left,right=geometry[(u,v)],geometry[next_uv]
            connected=bool(left&right) or any(tuple(pos[i]+(step if i==axis else 0) for i in range(3)) in right
                for pos in left for axis in range(3) for step in (-1,1))
            if not connected:broken+=1
            if len(pairs)<256:
                distance=(min(sum(abs(a[i]-b[i]) for i in range(3)) for a in left for b in right)
                          if len(left)*len(right)<=65536 else None)
                pairs.append(dict(from_uv=[u,v],to_uv=list(next_uv),connected=connected,minimum_halfcell_manhattan=distance))
    remaining=set(by_uv);strokes=[]
    while remaining:
        first=min(remaining);remaining.remove(first);frontier=[first];members=[];symbol=by_uv[first]['symbol']
        while frontier:
            uv=frontier.pop();members.append(uv)
            for du in (-1,0,1):
                for dv in (-1,0,1):
                    if not du and not dv:continue
                    nu=uv[0]+du;nv=uv[1]+dv
                    if wrap:nu%=width
                    neighbor=(nu,nv)
                    if neighbor in remaining and by_uv[neighbor]['symbol']==symbol:
                        remaining.remove(neighbor);frontier.append(neighbor)
        positions=set().union(*(geometry[uv] for uv in members))
        count=_components(positions)
        if count>1:strokes.append(dict(symbol=symbol,first_uv=list(first),pixels=len(members),components=count))
    return dict(passed=not strokes,pairs=total,broken_pairs=broken,details=pairs,details_truncated=total>len(pairs),
                fragmented_pixels=len(fragmented),fragmented_details=fragmented[:256],fragmented_details_truncated=len(fragmented)>256,
                disconnected_strokes=len(strokes),stroke_details=strokes[:256],stroke_details_truncated=len(strokes)>256,
                scope='Half-cell collision shapes and cut volumes per eight-neighbor mask stroke; not structural or game certification')


def _mapping(value):
    required={'u_start','u_span','y_start','max_distance'}
    if not isinstance(value,dict) or not required<=set(value) or set(value)-required-{'u_subsamples','connect_raised','connect_recess'}:
        raise ValueError('曲面 UV 映射字段无效')
    start,span,y_start,maximum=(value[key] for key in ('u_start','u_span','y_start','max_distance'))
    subsamples=value.get('u_subsamples',1)
    connection=value.get('connect_raised')
    recess=value.get('connect_recess')
    if (type(start) not in (int,float) or not math.isfinite(start) or not 0<=start<1 or
        type(span) not in (int,float) or not math.isfinite(span) or not 0<span<=1 or
        type(y_start) is not int or type(maximum) not in (int,float) or not math.isfinite(maximum) or not .5<=maximum<=3 or
        type(subsamples) is not int or not 1<=subsamples<=8):
        raise ValueError('曲面 UV 位置、跨度或搜索距离无效')
    if 'connect_raised' in value and (not isinstance(connection,dict) or 'max_new_blocks' not in connection or
        set(connection)-{'max_new_blocks','max_bridge_steps','path_choices'} or type(connection['max_new_blocks']) is not int or
        not 1<=connection['max_new_blocks']<=64 or type(connection.get('max_bridge_steps',1)) is not int or
        not 1<=connection.get('max_bridge_steps',1)<=3):
        raise ValueError('曲面连接须设置1至64格预算及1至3个中间格')
    if connection is not None and 'path_choices' in connection:
        choices=connection['path_choices']
        if not isinstance(choices,list) or len(choices)>64:raise ValueError('曲面指定路径须为至多64项')
        for choice in choices:
            if (not isinstance(choice,dict) or not {'endpoints','path'}<=set(choice) or set(choice)-{'endpoints','path','layer'} or
                'layer' in choice and (not isinstance(choice['layer'],str) or not ROLE.fullmatch(choice['layer'])) or
                not isinstance(choice['endpoints'],list) or len(choice['endpoints'])!=2 or
                not isinstance(choice['path'],list) or not 1<=len(choice['path'])<=connection.get('max_bridge_steps',1)):
                raise ValueError('曲面指定路径字段无效')
            for point in choice['endpoints']+choice['path']:
                if not isinstance(point,list) or len(point)!=3 or any(type(value) is not int or not 0<=value<MAX_AXIS for value in point):
                    raise ValueError('曲面指定路径坐标无效')
    if 'connect_recess' in value and (not isinstance(recess,dict) or set(recess)!={'max_new_blocks'} or
        type(recess['max_new_blocks']) is not int or not 1<=recess['max_new_blocks']<=64):
        raise ValueError('曲面凹槽连接须显式设置1至64格的新增预算')
    return start,span,y_start,maximum,subsamples,connection,recess


def _review_feedback(workspace,source,source_sha256,value):
    """Bind a candidate to one actual observation on a review of its source."""
    from nbt_blind_review import _json,_pair,verify_review
    keys={'binding','binding_sha256','record','record_sha256','observation'}
    if not isinstance(value,dict) or set(value)!=keys or type(value['observation']) is not int or value['observation']<0:
        raise ValueError('曲面审阅意见绑定无效')
    binding=_workspace_path(workspace,value['binding']);record=_workspace_path(workspace,value['record'])
    verify_review(workspace,binding,value['binding_sha256'],record,value['record_sha256'])
    evidence=_json(binding,value['binding_sha256']);observation=_json(record,value['record_sha256'])
    if value['observation']>=len(observation['observations']):raise ValueError('曲面审阅意见序号超出范围')
    reviewed=_pair(workspace,evidence['renders'])
    if not any(item['source']==source and item['report']['source_sha256']==source_sha256 for item in reviewed):
        raise ValueError('曲面宿主不属于该审阅包的制作源')
    verify_review(workspace,binding,value['binding_sha256'],record,value['record_sha256'])
    return dict(binding=binding.relative_to(workspace).as_posix(),binding_sha256=value['binding_sha256'],
                record=record.relative_to(workspace).as_posix(),record_sha256=value['record_sha256'],
                observation=value['observation'])


def _calculate_single(working,sections,mask,mapping):
    start,span,y_start,maximum,subsamples,connection,recess=_mapping(mapping)
    if sum(len(row)-row.count('.') for row in mask['rows'])*subsamples>MAX_FACE_SAMPLES:
        raise ValueError('曲面实际面采样超过8192次上限，请缩小样段或减少采样')
    protected=protections(working.model,working._protection_context());changes={};owners={};samples=[];supports=[];recess_checks=[]
    merged_writes=0;raw_writes=0;collapsed_pixels=0
    rows=mask['rows'];width=len(rows[0])
    for row_index,row in enumerate(rows):
        y=y_start+row_index
        if not 0<=y<working.model.size[1]:raise ValueError('纹样高度超出宿主')
        for column,symbol in enumerate(row):
            if symbol=='.':continue
            spec=mask['palette'][symbol];kind=spec['kind'];faces=[];rows_changed=[];local_seen=set();new_positions=0;local_merged=0
            for sub in range(subsamples):
                u=(start+span*(column+(sub+.5)/subsamples)/width)%1
                expected,normal=_surface_point(sections,y+.5,u)
                try:host,face,distance=_actual_face(working.model,expected,normal,y,maximum)
                except ValueError as error:raise ValueError(str(error)+'：'+json.dumps(dict(uv=[column,row_index],subsample=sub,y=y),ensure_ascii=False)) from error
                planned=[];backing=[]
                if kind=='raise':
                    for depth in range(1,spec['height']+1):
                        p=tuple(host[i]+face[i]*depth for i in range(3))
                        if not working.model.in_bounds(p) or working.model.get(p) not in AIR_NAMES:raise ValueError('凸饰外侧被占用或越界：'+str(p))
                        planned.append((p,[spec['state'],spec['wall']]))
                    supports.append(host)
                else:
                    for depth in range(spec['depth']+spec['backing']):
                        p=tuple(host[i]-face[i]*depth for i in range(3))
                        if not working.model.in_bounds(p) or not _full(working.model.get(p)):
                            raise ValueError('切槽宿主厚度或保留背衬不足：'+str(p))
                        if depth<spec['depth']:
                            after=[spec['state'],spec['wall']] if kind=='inlay' and depth==spec['depth']-1 else ['minecraft:air',False]
                            planned.append((p,after))
                        else:backing.append(p)
                    if 'max_effective_depth' not in spec:supports.extend(backing)
                face_record=dict(u=u,expected_xz=expected,analytic_normal_xz=normal,host=list(host),face_normal=list(face),
                                 distance=distance,backing_verified=len(backing) if kind!='raise' else 1)
                faces.append(face_record)
                if kind!='raise' and 'max_effective_depth' in spec:recess_checks.append((symbol,spec,host,face,face_record))
                for pos,after in planned:
                    raw_writes+=1
                    if pos in protected:raise ModelConflict('CURVE_PROTECTED',[dict(pos=list(pos),uv=[column,row_index])])
                    if pos in changes:
                        if owners[pos]!=symbol or changes[pos]['after']!=after:
                            raise ModelConflict('CURVE_OVERLAP',[dict(pos=list(pos),uv=[column,row_index])])
                        change=changes[pos];merged_writes+=1;local_merged+=1
                    else:
                        before=value_at(working.model,working.walls,pos)
                        change=dict(pos=list(pos),before=before,after=after);changes[pos]=change;owners[pos]=symbol;new_positions+=1
                    if pos not in local_seen:rows_changed.append(change);local_seen.add(pos)
            if not new_positions:collapsed_pixels+=1
            primary=faces[0]
            samples.append(dict(uv=[column,row_index],symbol=symbol,u=primary['u'],kind=kind,role=spec['role'],expected_xz=primary['expected_xz'],
                analytic_normal_xz=primary['analytic_normal_xz'],host=primary['host'],face_normal=primary['face_normal'],distance=primary['distance'],
                depth=spec.get('depth',0),height=spec.get('height',0),backing_required=spec.get('backing',1),
                backing_verified=min(face['backing_verified'] for face in faces),faces=faces,merged_writes=local_merged,
                effective_writes=sum(item['before']!=item['after'] for item in rows_changed),changes=rows_changed))
    connectors=[]
    if connection is not None:
        from nbt_curved_connect import connect_raised
        choices=connection.get('path_choices')
        if choices is not None and any('layer' in item for item in choices):raise ValueError('单层曲面指定路径不使用 layer 字段')
        connectors=connect_raised(working,mask,samples,changes,owners,protected,supports,connection['max_new_blocks'],
                                  math.isclose(span,1.0,rel_tol=0,abs_tol=1e-12),connection.get('max_bridge_steps',1),choices)
        raw_writes+=len(connectors)
    recess_connectors=[]
    if recess is not None:
        from nbt_curved_recess import connect_recesses
        recess_connectors=connect_recesses(working,mask,samples,changes,owners,protected,supports,recess['max_new_blocks'],
                                            math.isclose(span,1.0,rel_tol=0,abs_tol=1e-12),maximum)
        raw_writes+=sum(len(item['writes']) for item in recess_connectors)
    for symbol,spec,host,normal,face_record in recess_checks:
        depth=spec['depth'];limit=spec['max_effective_depth']
        while True:
            pos=tuple(host[i]-normal[i]*depth for i in range(3))
            if not working.model.in_bounds(pos):raise ModelConflict('CURVE_BACKING_CONFLICT',[dict(pos=list(pos),symbol=symbol)])
            before=value_at(working.model,working.walls,pos);after=changes[pos]['after'] if pos in changes else before
            if after==before and _full(after[0]):break
            if depth>=limit or pos not in changes or owners[pos]!=symbol:
                raise ModelConflict('CURVE_BACKING_CONFLICT',[dict(pos=list(pos),symbol=symbol,max_effective_depth=limit)])
            depth+=1
        backing=[]
        for offset in range(spec['backing']):
            pos=tuple(host[i]-normal[i]*(depth+offset) for i in range(3))
            if not working.model.in_bounds(pos):raise ModelConflict('CURVE_BACKING_CONFLICT',[dict(pos=list(pos),symbol=symbol)])
            before=value_at(working.model,working.walls,pos);after=changes[pos]['after'] if pos in changes else before
            if after!=before or not _full(after[0]):raise ModelConflict('CURVE_BACKING_CONFLICT',[dict(pos=list(pos),symbol=symbol)])
            backing.append(pos)
        air_depth=0
        for offset in range(depth):
            pos=tuple(host[i]-normal[i]*offset for i in range(3))
            value=changes[pos]['after'][0] if pos in changes else working.model.get(pos)
            if value not in AIR_NAMES:break
            air_depth+=1
        supports.extend(backing);face_record.update(effective_depth=depth,air_depth_full_voxels=air_depth,
                                                   backing_positions=[list(pos) for pos in backing])
    for pos in supports:
        before=value_at(working.model,working.walls,pos)
        after=changes[pos]['after'] if pos in changes else before
        if after!=before or not _full(after[0]):raise ModelConflict('CURVE_BACKING_CONFLICT',[dict(pos=list(pos))])
    continuity=_continuity(samples,rows,math.isclose(span,1.0,rel_tol=0,abs_tol=1e-12))
    summary=dict(pixels=len(samples),raw_writes=raw_writes,requested_positions=len(changes),merged_writes=merged_writes,
                 changed_positions=sum(item['before']!=item['after'] for item in changes.values()),unmapped=0,truncated=collapsed_pixels)
    if recess_checks:
        summary['effective_depth']=dict(maximum=max(record['effective_depth'] for _,_,_,_,record in recess_checks),
            max_air_full_voxels=max(record['air_depth_full_voxels'] for _,_,_,_,record in recess_checks),
            extended_faces=sum(record['effective_depth']>spec['depth'] for _,spec,_,_,record in recess_checks),checked_faces=len(recess_checks))
    if connection is not None or recess is not None:summary['connectors_added']=len(connectors)+len(recess_connectors)
    if recess is not None:summary['recess_connectors_added']=len(recess_connectors)
    return samples,list(changes.values()),continuity,summary


def _calculate_layers(working,sections,mask,mapping):
    _,_,_,_,subsamples,connection,recess=_mapping(mapping)
    active=sum(sum(len(row)-row.count('.') for row in layer['rows']) for layer in mask['layers'])
    if active*subsamples>MAX_FACE_SAMPLES:raise ValueError('分层曲面实际面采样超过8192次上限')
    samples=[];changes={};owners={};layer_results=[];shared=0;raised_count=0;recess_writes=0;skips=[]
    choices=connection.get('path_choices',[]) if connection is not None else []
    layer_ids={layer['id'] for layer in mask['layers']}
    if any('layer' not in item or item['layer'] not in layer_ids for item in choices):
        raise ValueError('分层曲面指定路径须绑定现有 layer')
    for layer in mask['layers']:
        local_mapping=dict(mapping)
        for kind,key,global_setting in (('raised','connect_raised',connection),('recess','connect_recess',recess)):
            flag=layer['connections'].get(kind)
            if flag is True and global_setting is None:raise ValueError('分层连接已启用但缺少全局预算：'+kind)
            if flag is False and global_setting is not None:
                local_mapping.pop(key,None);skips.append(dict(layer=layer['id'],kind=kind))
        selected=[{key:value for key,value in item.items() if key!='layer'} for item in choices if item['layer']==layer['id']]
        if selected and 'connect_raised' not in local_mapping:raise ValueError('已跳过的凸饰层不能指定连接路径')
        if 'connect_raised' in local_mapping and choices:
            local_mapping['connect_raised']=dict(connection,path_choices=selected)
        try:
            local_samples,local_changes,local_continuity,local_summary=_calculate_single(working,sections,layer,local_mapping)
        except ModelConflict as error:
            if error.code!='CURVE_RECESS_DISCONNECTED':raise
            raise ModelConflict(error.code,[dict(item,layer=layer['id']) for item in error.conflicts]) from error
        for sample in local_samples:
            sample['layer']=layer['id']
            for connector in sample.get('connectors',[]):
                if connector.get('kind') in ('cut','inlay'):recess_writes+=len(connector['writes'])
                else:raised_count+=1
        samples.extend(local_samples);layer_results.append(dict(id=layer['id'],continuity=local_continuity,summary=local_summary))
        for change in local_changes:
            pos=tuple(change['pos'])
            if pos in changes:
                if (any(tuple(sorted((owner,layer['id']))) not in mask['overlaps'] for owner in owners[pos]) or
                    change['before']!=changes[pos]['before'] or change['after']!=changes[pos]['after']):
                    raise ModelConflict('CURVE_LAYER_CONFLICT',[dict(pos=list(pos),layers=sorted(owners[pos]|{layer['id']}))])
                owners[pos].add(layer['id']);shared+=1
            else:changes[pos]=change;owners[pos]={layer['id']}
    if connection is not None and raised_count>connection['max_new_blocks']:raise ValueError('分层凸饰连接超过总预算')
    if recess is not None and recess_writes>recess['max_new_blocks']:raise ValueError('分层凹槽连接超过总预算')
    by_id={layer['id']:layer for layer in mask['layers']};replacements=[];checked=set()
    def check_support(layer,symbol,pos,kind):
        key=(layer['id'],symbol,pos,kind)
        if key in checked:return
        checked.add(key);before=value_at(working.model,working.walls,pos)
        after=changes[pos]['after'] if pos in changes else before
        if after==before and _full(after[0]):return
        expectation=layer['support_expectations'].get(symbol) if kind=='raise' else None
        writers=owners.get(pos,set())
        if (expectation is None or after!=expectation or not _full(after[0]) or not writers or
            any(writer==layer['id'] or tuple(sorted((writer,layer['id']))) not in mask['overlaps'] for writer in writers)):
            raise ModelConflict('CURVE_LAYER_SUPPORT',[dict(pos=list(pos),layer=layer['id'],kind=kind,before=before,after=after,expected=expectation)])
        replacements.append(dict(layer=layer['id'],symbol=symbol,pos=list(pos),before=before,after=after,
                                 expected=expectation,writer_layers=sorted(writers)))
    for sample in samples:
        layer=by_id[sample['layer']];symbol=sample['symbol'];spec=layer['palette'][symbol]
        for face in sample['faces']:
            host=tuple(face['host']);normal=tuple(face['face_normal'])
            if spec['kind']=='raise':check_support(layer,symbol,host,'raise')
            else:
                actual_depth=face.get('effective_depth',spec['depth'])
                for depth in range(actual_depth,actual_depth+spec['backing']):
                    check_support(layer,symbol,tuple(host[i]-normal[i]*depth for i in range(3)),'backing')
        for connector in sample.get('connectors',[]):
            if connector.get('kind') in ('cut','inlay'):
                for pos in connector['backing']:check_support(layer,symbol,tuple(pos),'backing')
            else:
                for pos in connector['endpoint_hosts']:check_support(layer,symbol,tuple(pos),'raise')
    continuity=dict(passed=all(item['continuity']['passed'] for item in layer_results),
                    layers=[dict(id=item['id'],result=item['continuity']) for item in layer_results],
                    scope='Each layer checked separately; cross-layer support checked against final blocks')
    summary=dict(layers=len(layer_results),overlapping_uv=mask['overlapping_uv'],overlap_pairs=mask['overlap_pairs'],
        overlap_details=mask['overlap_details'],overlap_details_truncated=mask['overlap_details_truncated'],
        pixels=sum(item['summary']['pixels'] for item in layer_results),
        raw_writes=sum(item['summary']['raw_writes'] for item in layer_results),requested_positions=len(changes),
        merged_writes=shared+sum(item['summary']['merged_writes'] for item in layer_results),
        changed_positions=sum(item['before']!=item['after'] for item in changes.values()),
        unmapped=sum(item['summary']['unmapped'] for item in layer_results),truncated=sum(item['summary']['truncated'] for item in layer_results),
        cross_layer_shared_writes=shared,support_replacements=replacements)
    if connection is not None or recess is not None:
        summary['connectors_added']=sum(item['summary'].get('connectors_added',0) for item in layer_results)
    if recess is not None:summary['recess_connectors_added']=sum(item['summary'].get('recess_connectors_added',0) for item in layer_results)
    if skips:summary['connection_skips']=skips
    depth_reports=[item['summary']['effective_depth'] for item in layer_results if 'effective_depth' in item['summary']]
    if depth_reports:
        summary['effective_depth']=dict(maximum=max(item['maximum'] for item in depth_reports),
            max_air_full_voxels=max(item['max_air_full_voxels'] for item in depth_reports),
            extended_faces=sum(item['extended_faces'] for item in depth_reports),checked_faces=sum(item['checked_faces'] for item in depth_reports))
    return samples,list(changes.values()),continuity,summary


def _calculate(working,sections,mask,mapping):
    return _calculate_layers(working,sections,mask,mapping) if 'layers' in mask else _calculate_single(working,sections,mask,mapping)


def plan_curve(workspace,request):
    workspace=require_creative_workspace(workspace)
    required={'source','source_sha256','profile','profile_sha256','mask','mask_sha256','mapping','output','cameras'}
    if not isinstance(request,dict) or not required<=set(request) or set(request)-required-{'context','review_feedback'}:
        raise ValueError('曲面候选请求字段无效')
    source=_workspace_path(workspace,request['source']);profile=_workspace_path(workspace,request['profile']);mask_file=_workspace_path(workspace,request['mask'])
    if not source.is_relative_to(workspace/'nbt_models'):raise ValueError('曲面宿主须位于工作区 nbt_models')
    verify_fit(workspace,profile,request['profile_sha256'])
    fit=json.loads(profile.read_text(encoding='utf8'));sections=fit['geometry']['sections']
    mask,mask_raw=_mask(mask_file,request['mask_sha256'],workspace)
    mapping=request['mapping'];_mapping(mapping)
    cameras=request['cameras']
    if not isinstance(cameras,list) or not 1<=len(cameras)<=16:raise ValueError('曲面候选须提供1至16个审阅机位')
    destination=_workspace_path(workspace,request['output']);base=workspace/'nbt_models/_workspaces/curve-samples'
    if not destination.is_relative_to(base) or destination==base or destination.exists() or destination.is_symlink():raise ValueError('曲面候选输出须为 curve-samples 下的新目录')
    working=WorkingModel.open(workspace,source,request.get('context'),source_sha256=request['source_sha256'])
    feedback=_review_feedback(workspace,source,request['source_sha256'],request['review_feedback']) if 'review_feedback' in request else None
    samples,changes,continuity,summary=_calculate(working,sections,mask,mapping)
    # Reject oversized evidence before creating a candidate directory. Paths and
    # fixed receipt fields are included conservatively because preview generates
    # several paths underneath the requested output directory.
    estimate=dict(request=request,host_context=working.context,samples=samples,continuity=continuity,summary=summary)
    estimate_size=len(json.dumps(estimate,ensure_ascii=False,separators=(',',':')).encode('utf8'))
    if estimate_size+8*len(str(destination).encode('utf8'))+8192>MAX_MANIFEST:
        raise ValueError('曲面候选报告过大，请缩小样段或减少采样')
    working.patch(changes)
    def recheck():
        working._unchanged();verify_fit(workspace,profile,request['profile_sha256'])
        _mask(mask_file,request['mask_sha256'],workspace)
        if feedback is not None:_review_feedback(workspace,source,request['source_sha256'],feedback)
    recheck();destination.parent.mkdir(parents=True,exist_ok=True)
    try:destination.mkdir()
    except FileExistsError:raise ValueError('曲面候选输出已存在') from None
    preview=working.preview(destination/'preview',cameras)
    recheck()
    candidate=Path(preview['source']);snapshot=Path(preview['snapshot']);camera_file=Path(preview['cameras'])
    candidate_sha=_sha(candidate);snapshot_sha=_sha(snapshot);camera_sha=_sha(camera_file)
    proof=dict(schema_version=1,kind='nbtcreator-curved-candidate',source=source.relative_to(workspace).as_posix(),
        source_sha256=request['source_sha256'],profile=profile.relative_to(workspace).as_posix(),profile_sha256=request['profile_sha256'],
        mask=mask_file.relative_to(workspace).as_posix(),mask_sha256=request['mask_sha256'],mapping=mapping,
        host_context=working.context,host_context_sha256=digest(working.context),source_model_sha256=model_hash(working._baseline,working._baseline_walls),
        candidate=candidate.resolve().relative_to(workspace).as_posix(),candidate_sha256=candidate_sha,candidate_model_sha256=preview['model_sha256'],
        snapshot=snapshot.resolve().relative_to(workspace).as_posix(),snapshot_sha256=snapshot_sha,
        cameras=camera_file.resolve().relative_to(workspace).as_posix(),cameras_sha256=camera_sha,
        samples=samples,continuity=continuity,summary=summary,
        approval_created=False,nbt_exported=False)
    if feedback is not None:proof['review_feedback']=feedback
    raw=(json.dumps(proof,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode('utf8')
    if len(raw)>MAX_MANIFEST:raise ValueError('曲面候选报告过大')
    with (destination/'curve-plan.json').open('xb') as stream:stream.write(raw)
    return dict(plan=str(destination/'curve-plan.json'),plan_sha256=hashlib.sha256(raw).hexdigest(),candidate=preview['source'],
        candidate_sha256=candidate_sha,snapshot=preview['snapshot'],snapshot_sha256=snapshot_sha,cameras=preview['cameras'],cameras_sha256=camera_sha,
        samples=samples,continuity=continuity,summary=proof['summary'],approval_created=False,nbt_exported=False)


def verify_curve(workspace,plan,expected_sha256):
    """Recheck evidence and replay the bound voxel changes without publishing."""
    from nbt_task import preview_source_matches
    from nbt_refine import read_master
    workspace=Path(workspace).resolve();plan=_workspace_path(workspace,str(plan))
    if not isinstance(expected_sha256,str) or not re.fullmatch('[a-f0-9]{64}',expected_sha256) or not plan.is_file() or plan.stat().st_size>MAX_MANIFEST:
        raise ValueError('曲面候选报告或哈希无效')
    with plan.open('rb') as stream:raw=stream.read(MAX_MANIFEST+1)
    if len(raw)>MAX_MANIFEST or hashlib.sha256(raw).hexdigest()!=expected_sha256:raise ValueError('曲面候选报告哈希不一致')
    try:proof=json.loads(raw)
    except (ValueError,UnicodeDecodeError):raise ValueError('曲面候选报告格式无效') from None
    fields={'schema_version','kind','source','source_sha256','profile','profile_sha256','mask','mask_sha256','mapping',
            'host_context','host_context_sha256','source_model_sha256','candidate','candidate_sha256','candidate_model_sha256',
            'snapshot','snapshot_sha256','cameras','cameras_sha256','samples','continuity','summary','approval_created','nbt_exported'}
    if (not isinstance(proof,dict) or not fields<=set(proof) or set(proof)-fields-{'review_feedback'} or proof.get('schema_version')!=1 or proof.get('kind')!='nbtcreator-curved-candidate' or
        proof.get('approval_created') is not False or proof.get('nbt_exported') is not False):
        raise ValueError('曲面候选报告类型或批准字段无效')
    source=_workspace_path(workspace,proof['source']);profile=_workspace_path(workspace,proof['profile']);mask_file=_workspace_path(workspace,proof['mask'])
    candidate=_workspace_path(workspace,proof['candidate']);snapshot=_workspace_path(workspace,proof['snapshot']);cameras=_workspace_path(workspace,proof['cameras'])
    preview_root=(plan.parent/'preview').resolve()
    if not candidate.is_relative_to(preview_root) or snapshot!=preview_root/'snapshot.json' or cameras!=preview_root/'cameras.json':
        raise ValueError('曲面候选证据路径不一致')
    verify_fit(workspace,profile,proof['profile_sha256']);mask,_=_mask(mask_file,proof['mask_sha256'],workspace)
    working=WorkingModel.open(workspace,source,proof['host_context'],source_sha256=proof['source_sha256'])
    if 'review_feedback' in proof:_review_feedback(workspace,source,proof['source_sha256'],proof['review_feedback'])
    if digest(working.context)!=proof['host_context_sha256'] or model_hash(working.model,working.walls)!=proof['source_model_sha256']:
        raise ValueError('曲面宿主或保护上下文已变化')
    fit=json.loads(profile.read_text(encoding='utf8'))
    samples,changes,continuity,summary=_calculate(working,fit['geometry']['sections'],mask,proof['mapping'])
    if samples!=proof['samples'] or continuity!=proof['continuity'] or summary!=proof['summary']:
        raise ValueError('曲面采样、背衬或连续性与绑定输入不一致')
    working.patch(changes)
    if _sha(candidate)!=proof['candidate_sha256']:raise ValueError('曲面候选源哈希已变化')
    candidate_model,candidate_walls=read_assembly(candidate) if is_assembly_source(candidate) else read_master(candidate)
    if (candidate_model.blocks!=working.model.blocks or candidate_walls!=working.walls or
        model_hash(candidate_model,candidate_walls)!=proof['candidate_model_sha256']):
        raise ValueError('曲面候选与已校验修改不一致')
    if _sha(snapshot)!=proof['snapshot_sha256'] or _sha(cameras)!=proof['cameras_sha256']:
        raise ValueError('曲面快照或相机哈希已变化')
    snap=json.loads(snapshot.read_text(encoding='utf8'))
    if (Path(snap['source']).resolve()!=candidate or snap.get('geometry_sha256')!=candidate_model.fingerprint() or
        not preview_source_matches(candidate,snap)):
        raise ValueError('曲面候选快照绑定不一致')
    working._unchanged();verify_fit(workspace,profile,proof['profile_sha256']);_mask(mask_file,proof['mask_sha256'],workspace)
    if 'review_feedback' in proof:_review_feedback(workspace,source,proof['source_sha256'],proof['review_feedback'])
    if _sha(plan)!=expected_sha256 or _sha(candidate)!=proof['candidate_sha256'] or _sha(snapshot)!=proof['snapshot_sha256'] or _sha(cameras)!=proof['cameras_sha256'] or not preview_source_matches(candidate,snap):
        raise ValueError('核对期间曲面候选证据发生变化')
    return dict(valid=True,plan=str(plan),plan_sha256=expected_sha256,candidate=str(candidate),
                candidate_sha256=proof['candidate_sha256'],approval_created=False,nbt_exported=False,
                scope='Recomputes UV sampling and replays bound voxel changes; no visual approval or game validation')


def _followup_inputs(workspace,plan,plan_sha256,feedback):
    from nbt_blind_review import _json,_pair,verify_review
    candidate=verify_curve(workspace,plan,plan_sha256)
    plan_file=_workspace_path(workspace,str(plan));proof=_json(plan_file,plan_sha256)
    if 'review_feedback' not in proof:raise ValueError('曲面候选没有绑定原始审阅意见')
    normalized=_review_feedback(workspace,Path(candidate['candidate']),candidate['candidate_sha256'],feedback)
    previous=proof['review_feedback']
    old_binding=_json(_workspace_path(workspace,previous['binding']),previous['binding_sha256'])
    new_binding=_json(_workspace_path(workspace,normalized['binding']),normalized['binding_sha256'])
    old_report=_pair(workspace,old_binding['renders'])[0]['report']
    new_report=_pair(workspace,new_binding['renders'])[0]['report']
    settings=('width','height','quality','pixel_ratio','cameras_sha256','views','reference_camera_binding')
    if old_binding['crop']!=new_binding['crop'] or any(old_report.get(key)!=new_report.get(key) for key in settings):
        raise ValueError('曲面前后复核的相机、光照、画幅或裁切不一致')
    for item in (previous,normalized):
        verify_review(workspace,item['binding'],item['binding_sha256'],item['record'],item['record_sha256'])
    verify_curve(workspace,plan_file,plan_sha256)
    if _sha(plan_file)!=plan_sha256:raise ValueError('复核期间曲面候选计划发生变化')
    return plan_file,normalized


def record_curve_followup(workspace,request):
    """Record a new observation about a candidate without creating approval."""
    workspace=require_creative_workspace(workspace)
    fields={'plan','plan_sha256','review_feedback','status','remaining','output'}
    if (not isinstance(request,dict) or set(request)!=fields or request['status'] not in ('improved','unresolved','inconclusive') or
        not isinstance(request['remaining'],str) or len(request['remaining'])>4000 or
        (request['status']!='improved' and not request['remaining'].strip())):
        raise ValueError('曲面复核状态或未解决项无效')
    plan,feedback=_followup_inputs(workspace,request['plan'],request['plan_sha256'],request['review_feedback'])
    target=_workspace_path(workspace,request['output']);base=workspace/'nbt_models/_workspaces/reference-reviews'
    if not target.is_relative_to(base) or target==base or target.suffix.lower()!='.json' or target.exists() or target.is_symlink():
        raise ValueError('曲面复核须使用 reference-reviews 下的新 JSON 文件')
    proof=dict(schema_version=1,kind='nbtcreator-curve-followup',plan=plan.relative_to(workspace).as_posix(),
        plan_sha256=request['plan_sha256'],review_feedback=feedback,status=request['status'],remaining=request['remaining'],
        approval_created=False,boundary='Observation only; no human approval or game validation')
    raw=(json.dumps(proof,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode('utf8')
    if len(raw)>MAX_MANIFEST:raise ValueError('曲面复核记录过大')
    target.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.curve-followup-',dir=target.parent) as temporary:
        staged=Path(temporary)/'record.json';staged.write_bytes(raw)
        _followup_inputs(workspace,plan,request['plan_sha256'],feedback)
        try:os.link(staged,target)
        except FileExistsError:raise ValueError('曲面复核记录已存在，未覆盖') from None
    return dict(record=str(target),record_sha256=hashlib.sha256(raw).hexdigest(),approval_created=False)


def verify_curve_followup(workspace,record,expected_sha256):
    from nbt_blind_review import _json
    workspace=Path(workspace).resolve();record=_workspace_path(workspace,str(record));proof=_json(record,expected_sha256)
    fields={'schema_version','kind','plan','plan_sha256','review_feedback','status','remaining','approval_created','boundary'}
    if (not isinstance(proof,dict) or set(proof)!=fields or type(proof['schema_version']) is not int or proof['schema_version']!=1 or
        proof['kind']!='nbtcreator-curve-followup' or proof['approval_created'] is not False or
        proof['boundary']!='Observation only; no human approval or game validation' or
        proof['status'] not in ('improved','unresolved','inconclusive') or not isinstance(proof['remaining'],str) or
        len(proof['remaining'])>4000 or (proof['status']!='improved' and not proof['remaining'].strip())):
        raise ValueError('曲面复核记录无效')
    plan,feedback=_followup_inputs(workspace,proof['plan'],proof['plan_sha256'],proof['review_feedback'])
    if plan.relative_to(workspace).as_posix()!=proof['plan'] or feedback!=proof['review_feedback']:
        raise ValueError('曲面复核记录路径不一致')
    _json(record,expected_sha256)
    return dict(valid=True,record=str(record),record_sha256=expected_sha256,status=proof['status'],
                approval_created=False,scope='Binds prior feedback, candidate and new observation; no approval or game validation')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace',type=Path,default=Path.cwd())
    sub=parser.add_subparsers(dest='action',required=True)
    create=sub.add_parser('plan');create.add_argument('--request',type=Path,required=True);create.add_argument('--compact',action='store_true')
    verify=sub.add_parser('verify');verify.add_argument('--plan',type=Path,required=True);verify.add_argument('--sha256',required=True)
    compose=sub.add_parser('compose');compose.add_argument('--request',type=Path,required=True)
    mask_check=sub.add_parser('verify-mask');mask_check.add_argument('--mask',type=Path,required=True);mask_check.add_argument('--sha256',required=True)
    followup=sub.add_parser('review-record');followup.add_argument('--request',type=Path,required=True)
    checked=sub.add_parser('review-verify');checked.add_argument('--record',type=Path,required=True);checked.add_argument('--sha256',required=True)
    args=parser.parse_args()
    try:
        if args.action=='plan':
            if args.request.stat().st_size>MAX_MANIFEST:raise ValueError('曲面候选请求过大')
            request=json.loads(args.request.read_text(encoding='utf-8-sig'));result=plan_curve(args.workspace,request)
            if args.compact:result={key:value for key,value in result.items() if key!='samples'}
        elif args.action=='verify':result=verify_curve(args.workspace,args.plan,args.sha256)
        elif args.action=='compose':
            from nbt_curve_components import compose_curve_mask
            if args.request.stat().st_size>MAX_MANIFEST:raise ValueError('曲面构件组合请求过大')
            result=compose_curve_mask(args.workspace,json.loads(args.request.read_text(encoding='utf-8-sig')))
        elif args.action=='verify-mask':
            from nbt_curve_components import verify_curve_mask
            result=verify_curve_mask(args.workspace,args.mask,args.sha256)
        elif args.action=='review-record':
            if args.request.stat().st_size>MAX_MANIFEST:raise ValueError('曲面复核请求过大')
            result=record_curve_followup(args.workspace,json.loads(args.request.read_text(encoding='utf-8-sig')))
        else:result=verify_curve_followup(args.workspace,args.record,args.sha256)
        print(json.dumps(result,ensure_ascii=False));return 0
    except (ValueError,OSError,KeyError,TypeError) as error:
        print(json.dumps(dict(error=str(error),code=getattr(error,'code','CURVE_INVALID'),
                              conflicts=getattr(error,'conflicts',[])),ensure_ascii=False));return 1


if __name__=='__main__':raise SystemExit(main())
