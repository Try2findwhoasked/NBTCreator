"""Connect sampled relief at bounded, unambiguous local surface corners."""
from nbt_mounting.cylinder_fit import SIX,half_cells,topology
from nbt_model import AIR_NAMES
from nbt_mounting.surface_mount import _full
from nbt_working_model import ModelConflict,value_at

MAX_TOPOLOGY_VOLUME=500000
MAX_BRIDGE_EDGES=65536


def _touch(left,right):
    return bool(left&right) or any(tuple(pos[i]+step[i] for i in range(3)) in right for pos in left for step in SIX)


def _neighbors(pos):
    return {tuple(pos[i]+step[i] for i in range(3)) for step in SIX}


def _shortest_paths(left,right,max_bridge_steps):
    remaining=tuple(abs(right[i]-left[i]) for i in range(3));distance=sum(remaining)
    if distance<2 or distance>max_bridge_steps+1:return []
    directions=tuple(1 if right[i]>left[i] else -1 if right[i]<left[i] else 0 for i in range(3));paths=[]
    def walk(pos,counts,path):
        if not any(counts):paths.append(path[:-1]);return
        for axis in range(3):
            if not counts[axis]:continue
            next_pos=list(pos);next_pos[axis]+=directions[axis];next_counts=list(counts);next_counts[axis]-=1
            walk(tuple(next_pos),tuple(next_counts),path+[tuple(next_pos)])
    walk(left,remaining,[])
    return paths


def _component_groups(cells):
    remaining=set(cells);groups=[]
    while remaining:
        first=remaining.pop();stack=[first];group=[first]
        while stack:
            for pos in _neighbors(stack.pop())&remaining:
                remaining.remove(pos);stack.append(pos);group.append(pos)
        groups.append(group)
    return groups


def _choices(working,values,max_bridge_steps):
    if values is None:return {}
    if not isinstance(values,list) or len(values)>64:raise ValueError('曲面指定路径须为至多64项')
    result={}
    for item in values:
        if not isinstance(item,dict) or set(item)!={'endpoints','path'} or not isinstance(item['endpoints'],list) or len(item['endpoints'])!=2 or not isinstance(item['path'],list) or not 1<=len(item['path'])<=max_bridge_steps:
            raise ValueError('曲面指定路径字段无效')
        def point(value):
            if (not isinstance(value,list) or len(value)!=3 or any(type(part) is not int for part in value) or
                not working.model.in_bounds(tuple(value))):raise ValueError('曲面指定路径坐标无效')
            return tuple(value)
        endpoints=[point(value) for value in item['endpoints']];path=[point(value) for value in item['path']]
        if endpoints[0]==endpoints[1] or len(set(path))!=len(path) or any(pos in endpoints for pos in path):
            raise ValueError('曲面指定路径坐标重复')
        key=tuple(sorted(endpoints));canonical=path if endpoints[0]==key[0] else list(reversed(path))
        if key in result:raise ValueError('曲面指定路径端点重复')
        result[key]=canonical
    return result


def _bounded_topology(cells):
    if not cells:return topology(cells)
    volume=1
    for axis in range(3):volume*=max(pos[axis] for pos in cells)-min(pos[axis] for pos in cells)+3
    if volume>MAX_TOPOLOGY_VOLUME:raise ValueError('曲面连接拓扑范围过大，请缩小样段')
    return topology(cells)


def _strokes(samples,rows,wrap):
    by_uv={tuple(sample['uv']):sample for sample in samples};remaining=set(by_uv);groups=[];width=len(rows[0])
    while remaining:
        first=min(remaining);remaining.remove(first);stack=[first];members=[];symbol=by_uv[first]['symbol']
        while stack:
            uv=stack.pop();members.append(uv)
            for du in (-1,0,1):
                for dv in (-1,0,1):
                    if not du and not dv:continue
                    u=uv[0]+du
                    if wrap:u%=width
                    neighbor=(u,uv[1]+dv)
                    if neighbor in remaining and by_uv[neighbor]['symbol']==symbol:
                        remaining.remove(neighbor);stack.append(neighbor)
        groups.append((symbol,sorted(members)))
    return by_uv,groups


def _endpoints(working,sample):
    result=[]
    for face in sample['faces']:
        host=tuple(face['host']);normal=tuple(face['face_normal'])
        if len(host)!=3 or len(normal)!=3 or sum(abs(x) for x in normal)!=1 or normal[1]!=0:
            raise ValueError('曲面连接端点法向无效')
        pos=tuple(host[i]+normal[i] for i in range(3))
        if not working.model.in_bounds(host) or not _full(working.model.get(host)) or not working.model.in_bounds(pos) or working.model.get(pos) not in AIR_NAMES:
            raise ValueError('曲面连接端点没有实际宿主侧面')
        result.append((pos,host))
    return result


def connect_raised(working,mask,samples,changes,owners,protected,supports,max_new_blocks,wrap,max_bridge_steps=1,path_choices=None):
    """Stage unique one-block connectors and prove their topology before committing."""
    if type(max_new_blocks) is not int or not 0<=max_new_blocks<=64:raise ValueError('曲面连接预算须为0至64')
    if type(max_bridge_steps) is not int or not 1<=max_bridge_steps<=3:raise ValueError('曲面连接最多支持1至3个中间格')
    choices=_choices(working,path_choices,max_bridge_steps);used_choices=set()
    rows=mask['rows'];by_uv,groups=_strokes(samples,rows,wrap)
    staged=dict(changes);added=[];updates=[]
    for symbol,members in groups:
        spec=mask['palette'][symbol]
        if spec['kind']!='raise':continue
        if spec['height']!=1:raise ValueError('曲面自动连接仅支持单层凸饰')
        endpoints={uv:_endpoints(working,by_uv[uv]) for uv in members}
        positions={pos for values in endpoints.values() for pos,_ in values}
        block_states={pos:staged[pos]['after'][0] for pos in positions}
        cells=half_cells(block_states)
        if len(_component_groups(cells))<=1:continue
        if wrap:raise ValueError('曲面周期接缝的自动连接尚不支持，请拆分为非周期样段')
        source=_bounded_topology({(u,v,0) for u,v in members})
        if source['handles'] or source['cavities']:
            raise ValueError('带孔洞的曲面笔画暂不支持自动连接')
        member_set=set(members)
        foreign_blocks={tuple(change['pos']):change['after'][0] for uv,sample in by_uv.items()
                        if uv not in member_set and sample['symbol']==symbol for change in sample['changes']}
        foreign_blocks.update({tuple(change['pos']):change['after'][0] for uv,change,item in updates
                               if uv not in member_set and item['symbol']==symbol})
        foreign_cells=half_cells(foreign_blocks)
        cell_cache={pos:half_cells({pos:spec['state']}) for pos in positions}
        edges=[]
        for uv in members:
            own=endpoints[uv]
            for index,left in enumerate(own):
                for right in own[index+1:]:edges.append((uv,uv,left,right))
            for du in (-1,0,1):
                for dv in (-1,0,1):
                    other=(uv[0]+du,uv[1]+dv)
                    if other<=uv or other not in member_set:continue
                    for left in own:
                        for right in endpoints[other]:edges.append((uv,other,left,right))
            if len(edges)>MAX_BRIDGE_EDGES:raise ValueError('曲面连接候选超过预算，请缩小样段')
        while True:
            current=half_cells(block_states);world_groups=_component_groups(current)
            if len(world_groups)<=1:break
            component_by_cell={cell:index for index,group in enumerate(world_groups) for cell in group}
            progress=False
            for uv,other,(left,left_host),(right,right_host) in edges:
                left_cells=cell_cache[left];right_cells=cell_cache[right]
                if {component_by_cell[cell] for cell in left_cells}&{component_by_cell[cell] for cell in right_cells}:continue
                choice_key=tuple(sorted((left,right)));explicit=choice_key in choices
                candidates=[]
                for path in _shortest_paths(left,right,max_bridge_steps):
                    if any(not working.model.in_bounds(pos) or working.model.get(pos) not in AIR_NAMES for pos in path):continue
                    shapes=[half_cells({pos:spec['state']}) for pos in path];chain=[left_cells,*shapes,right_cells]
                    if all(_touch(a,b) for a,b in zip(chain,chain[1:])):
                        candidates.append((path,shapes,sum(pos not in block_states for pos in path)))
                if explicit:
                    selected=choices[choice_key] if left==choice_key[0] else list(reversed(choices[choice_key]))
                    candidates=[item for item in candidates if item[0]==selected]
                    if not candidates:raise ValueError('指定曲面连接路径无效或不再可行：'+str(list(choice_key)))
                    used_choices.add(choice_key)
                else:
                    if not candidates:continue
                    minimum=min(item[2] for item in candidates);candidates=[item for item in candidates if item[2]==minimum]
                    if len(candidates)>1:
                        raise ModelConflict('CURVE_CONNECT_AMBIGUOUS',[dict(reason='路径存在歧义',from_uv=list(uv),to_uv=list(other),
                            endpoints=[list(left),list(right)],paths=[[list(pos) for pos in item[0]] for item in candidates])])
                path,shapes,_=candidates[0];new_points=[pos for pos in path if pos not in block_states]
                if not new_points:continue
                if len(added)+len(new_points)>max_new_blocks:raise ValueError('曲面连接超过新增方块预算')
                for pos,shape in zip(path,shapes):
                    if pos in block_states:continue
                    if pos in protected:raise ModelConflict('CURVE_PROTECTED',[dict(pos=list(pos),uv=list(uv))])
                    if pos in staged:raise ModelConflict('CURVE_OVERLAP',[dict(pos=list(pos),uv=list(uv))])
                    if _touch(shape,foreign_cells):raise ValueError('曲面连接会合并不同来源笔画：'+str(pos))
                for pos,shape in zip(path,shapes):
                    if pos in block_states:continue
                    change=dict(pos=list(pos),before=value_at(working.model,working.walls,pos),after=[spec['state'],spec['wall']])
                    item=dict(pos=list(pos),symbol=symbol,from_uv=list(uv),to_uv=list(other),
                              endpoints=[list(left),list(right)],endpoint_hosts=[list(left_host),list(right_host)],
                              state=spec['state'],wall=spec['wall'])
                    if max_bridge_steps>1:
                        item['path']=[list(point) for point in path]
                        item['reused']=[list(point) for point in path if point not in new_points]
                    if explicit:item['selection']='explicit'
                    staged[pos]=change;block_states[pos]=spec['state'];cell_cache[pos]=shape
                    added.append(item);updates.append((uv,change,item))
                progress=True;break
            if not progress:raise ValueError('曲面笔画无法连接：'+str(dict(symbol=symbol,uv=list(members[0]),components=len(world_groups))))
        actual=_bounded_topology(half_cells(block_states))
        if any(source[key]!=actual[key] for key in ('handles','cavities')):
            raise ValueError('曲面连接未保留来源笔画孔洞或空腔')
    if set(choices)!=used_choices:raise ValueError('指定曲面连接路径未使用，输入可能已经过期')
    for uv,change,item in updates:
        pos=tuple(change['pos']);changes[pos]=change;owners[pos]=item['symbol'];sample=by_uv[uv]
        sample['changes'].append(change);sample.setdefault('connectors',[]).append(item)
        sample['effective_writes']+=change['before']!=change['after']
        supports.extend(tuple(host) for host in item['endpoint_hosts'])
    return added
