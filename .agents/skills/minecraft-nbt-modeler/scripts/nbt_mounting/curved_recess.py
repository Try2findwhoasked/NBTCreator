"""Bridge sampled recesses only through exposed, backed original host faces."""
import math

from nbt_mounting.curved_connect import MAX_BRIDGE_EDGES,_bounded_topology,_component_groups,_neighbors,_strokes,_touch
from nbt_mounting.cylinder_fit import half_cells
from nbt_model import AIR_NAMES
from nbt_mounting.surface_mount import _full
from nbt_composition.working_model import ModelConflict,value_at


def _voxel_cells(positions):
    return {(2*p[0]+x,2*p[1]+y,2*p[2]+z) for p in positions for x in (0,1) for y in (0,1) for z in (0,1)}


def _face_plan(working,host,normal,spec):
    if len(host)!=3 or len(normal)!=3 or sum(abs(x) for x in normal)!=1 or normal[1]!=0:
        raise ValueError('曲面切槽连接面法向无效')
    outside=tuple(host[i]+normal[i] for i in range(3))
    if (not working.model.in_bounds(host) or not _full(working.model.get(host)) or
        not working.model.in_bounds(outside) or working.model.get(outside) not in AIR_NAMES):
        return None,'surface'
    writes=[];backing=[]
    for depth in range(spec['depth']+spec['backing']):
        pos=tuple(host[i]-normal[i]*depth for i in range(3))
        if not working.model.in_bounds(pos) or not _full(working.model.get(pos)):return None,'backing'
        if depth>=spec['depth']:backing.append(pos);continue
        after=[spec['state'],spec['wall']] if spec['kind']=='inlay' and depth==spec['depth']-1 else ['minecraft:air',False]
        writes.append((pos,after))
    cut=_voxel_cells(pos for pos,_ in writes)
    material=half_cells({pos:after[0] for pos,after in writes if after[0] not in AIR_NAMES})
    return dict(host=host,normal=normal,writes=writes,backing=backing,cut=cut,material=material),None


def _endpoints(working,sample,spec,maximum):
    result=[]
    for face in sample['faces']:
        plan,reason=_face_plan(working,tuple(face['host']),tuple(face['face_normal']),spec)
        if plan is None:raise ValueError('曲面切槽端点缺少实际外露面或足够背衬：'+reason)
        expected=face.get('expected_xz');analytic=face.get('analytic_normal_xz');normal=plan['normal'];host=plan['host']
        if (not isinstance(expected,list) or len(expected)!=2 or not isinstance(analytic,list) or len(analytic)!=2 or
            any(type(value) not in (int,float) or not math.isfinite(value) for value in expected+analytic) or
            normal[0]*analytic[0]+normal[2]*analytic[1]<.25):
            raise ValueError('曲面切槽端点与拟合法向不一致')
        actual=(host[0]+.5+normal[0]*.5,host[2]+.5+normal[2]*.5)
        if math.dist(actual,expected)>maximum:raise ValueError('曲面切槽端点超出拟合面的搜索距离')
        plan.update(expected=expected,analytic=analytic)
        result.append(plan)
    return result


def _component_map(cells):
    groups=_component_groups(cells)
    return groups,{cell:index for index,group in enumerate(groups) for cell in group}


def _disconnected_endpoints(edges,cut_index,material_index,inlay):
    """Describe nearby source-sample gaps without treating them as valid bridges."""
    gaps={}
    for uv,other,left,right in edges:
        cut_connected=bool({cut_index[cell] for cell in left['cut']}&{cut_index[cell] for cell in right['cut']})
        material_connected=(bool({material_index[cell] for cell in left['material']}&
                                 {material_index[cell] for cell in right['material']}) if inlay else None)
        if cut_connected and material_connected is not False:continue
        hosts=(left['host'],right['host']);normals=(left['normal'],right['normal'])
        key=(uv,other,hosts,normals)
        gaps[key]=dict(from_uv=list(uv),to_uv=list(other),hosts=[list(host) for host in hosts],
                       normals=[list(normal) for normal in normals],
                       host_distance=sum(abs(hosts[0][i]-hosts[1][i]) for i in range(3)),
                       cut_connected=cut_connected,material_connected=material_connected)
    ordered=sorted(gaps.values(),key=lambda item:(item['host_distance'],item['from_uv'],item['to_uv'],item['hosts'],item['normals']))
    return ordered[:16],len(ordered)>16


def connect_recesses(working,mask,samples,changes,owners,protected,supports,max_new_blocks,wrap,maximum=2):
    """Stage unique backed recess links and independently verify inlay contact."""
    if type(max_new_blocks) is not int or not 0<=max_new_blocks<=64:raise ValueError('曲面凹槽连接预算须为0至64')
    rows=mask['rows'];by_uv,groups=_strokes(samples,rows,wrap)
    staged=dict(changes);staged_supports=set(supports);added=[];updates=[];new_writes=0
    for symbol,members in groups:
        spec=mask['palette'][symbol]
        if spec['kind'] not in ('cut','inlay'):continue
        endpoints={uv:_endpoints(working,by_uv[uv],spec,maximum) for uv in members}
        block_after={pos:after for values in endpoints.values() for endpoint in values for pos,after in endpoint['writes']}
        cut_groups,_=_component_map(_voxel_cells(block_after))
        material_groups,_=_component_map(half_cells({pos:value[0] for pos,value in block_after.items() if value[0] not in AIR_NAMES}))
        if len(cut_groups)<=1 and (spec['kind']!='inlay' or len(material_groups)<=1):continue
        if wrap:raise ValueError('曲面周期接缝的凹槽自动连接尚不支持')
        source=_bounded_topology({(u,v,0) for u,v in members})
        if source['handles'] or source['cavities']:raise ValueError('带孔洞的曲面笔画暂不支持自动连接')
        member_set=set(members)
        foreign_positions={tuple(change['pos']) for uv,sample in by_uv.items() if uv not in member_set and sample['symbol']==symbol
                           for change in sample['changes']}
        foreign_positions.update(tuple(change['pos']) for uv,edits,item in updates if uv not in member_set and item['symbol']==symbol for change in edits)
        foreign_cells=_voxel_cells(foreign_positions)
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
            if len(edges)>MAX_BRIDGE_EDGES:raise ValueError('曲面凹槽连接候选超过预算，请缩小样段')
        while True:
            cut_groups,cut_index=_component_map(_voxel_cells(block_after))
            material_groups,material_index=_component_map(half_cells({pos:value[0] for pos,value in block_after.items() if value[0] not in AIR_NAMES}))
            if len(cut_groups)<=1 and (spec['kind']!='inlay' or len(material_groups)<=1):break
            progress=False;backing_failed=False
            for uv,other,left,right in edges:
                if sum(abs(left['host'][i]-right['host'][i]) for i in range(3))!=2:continue
                cut_joined=bool({cut_index[cell] for cell in left['cut']}&{cut_index[cell] for cell in right['cut']})
                material_joined=(spec['kind']!='inlay' or bool({material_index[cell] for cell in left['material']}&
                                                                 {material_index[cell] for cell in right['material']}))
                if cut_joined and material_joined:continue
                candidates=[]
                for host in sorted(_neighbors(left['host'])&_neighbors(right['host'])):
                    for normal in sorted({left['normal'],right['normal']}):
                        if any(normal[0]*endpoint['analytic'][0]+normal[2]*endpoint['analytic'][1]<.25 for endpoint in (left,right)):continue
                        candidate,reason=_face_plan(working,host,normal,spec)
                        if reason=='backing':backing_failed=True
                        if candidate is None:continue
                        expected=[(left['expected'][i]+right['expected'][i])/2 for i in range(2)]
                        actual=(host[0]+.5+normal[0]*.5,host[2]+.5+normal[2]*.5);distance=math.dist(actual,expected)
                        if distance>maximum:continue
                        candidate['distance']=distance
                        if not (_touch(candidate['cut'],left['cut']) and _touch(candidate['cut'],right['cut'])):continue
                        if spec['kind']=='inlay' and not (_touch(candidate['material'],left['material']) and _touch(candidate['material'],right['material'])):continue
                        candidates.append(candidate)
                if len(candidates)>1:raise ValueError('曲面凹槽连接位置或面存在歧义')
                if not candidates:continue
                candidate=candidates[0];edits=[]
                if new_writes+len(candidate['writes'])>max_new_blocks:raise ValueError('曲面凹槽连接超过新增方块预算')
                for pos,after in candidate['writes']:
                    if pos in protected:raise ModelConflict('CURVE_PROTECTED',[dict(pos=list(pos),uv=list(uv))])
                    if pos in staged_supports:raise ModelConflict('CURVE_BACKING_CONFLICT',[dict(pos=list(pos))])
                    if pos in staged:raise ModelConflict('CURVE_OVERLAP',[dict(pos=list(pos),uv=list(uv))])
                    edits.append(dict(pos=list(pos),before=value_at(working.model,working.walls,pos),after=after))
                for pos in candidate['backing']:
                    before=value_at(working.model,working.walls,pos);after=staged[pos]['after'] if pos in staged else before
                    if after!=before or not _full(after[0]):raise ModelConflict('CURVE_BACKING_CONFLICT',[dict(pos=list(pos))])
                if _touch(candidate['cut'],foreign_cells):raise ValueError('曲面凹槽连接会合并不同来源笔画')
                item=dict(pos=list(candidate['host']),symbol=symbol,kind=spec['kind'],from_uv=list(uv),to_uv=list(other),
                    face_normal=list(candidate['normal']),depth=spec['depth'],backing=[list(pos) for pos in candidate['backing']],
                    endpoint_hosts=[list(left['host']),list(right['host'])],distance=candidate['distance'],writes=edits)
                for edit in edits:
                    pos=tuple(edit['pos']);staged[pos]=edit;block_after[pos]=edit['after']
                staged_supports.update(candidate['backing']);new_writes+=len(edits)
                added.append(item);updates.append((uv,edits,item));progress=True;break
            if not progress:
                if backing_failed:raise ValueError('曲面凹槽连接的宿主厚度或保留背衬不足')
                gaps,truncated=_disconnected_endpoints(edges,cut_index,material_index,spec['kind']=='inlay')
                raise ModelConflict('CURVE_RECESS_DISCONNECTED',[dict(reason='曲面凹槽笔画无法连接',symbol=symbol,
                    uv=list(members[0]),cut_components=len(cut_groups),material_components=len(material_groups) if spec['kind']=='inlay' else None,
                    endpoints=gaps,endpoints_truncated=truncated)])
        shapes=[_voxel_cells(block_after)]
        if spec['kind']=='inlay':shapes.append(half_cells({pos:value[0] for pos,value in block_after.items() if value[0] not in AIR_NAMES}))
        for shape in shapes:
            actual=_bounded_topology(shape)
            if any(source[key]!=actual[key] for key in ('handles','cavities')):
                raise ValueError('曲面凹槽连接未保留笔画孔洞或空腔')
    for uv,edits,item in updates:
        sample=by_uv[uv]
        for change in edits:
            pos=tuple(change['pos']);changes[pos]=change;owners[pos]=item['symbol'];sample['changes'].append(change)
            sample['effective_writes']+=change['before']!=change['after']
        sample.setdefault('connectors',[]).append(item);supports.extend(tuple(pos) for pos in item['backing'])
    return added
