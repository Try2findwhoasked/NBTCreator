"""Scoped, route-protected handoffs for hash-bound assembly authoring sources."""
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile

from nbt_assembly import Volume
from nbt_large_assembly import MAX_MANIFEST_BYTES, _part_path, _workspace_path, require_creative_workspace
from nbt_snbt import read_snbt,save_snbt
from nbt_working_model import WorkingModel, ModelConflict, digest, empty_volume, model_hash, point, value_at

MAX_BOXES = 100_000
MAX_PROTECTED_CELLS = 2_000_000
MAX_HANDOFF_BYTES = 16*1024*1024


def _bounds(value, label):
    if not isinstance(value, dict) or set(value) != {'lo','hi'}:
        raise ValueError(label+'须包含 lo 和 hi')
    lo,hi=point(value['lo']),point(value['hi'])
    if any(lo[i]>hi[i] for i in range(3)):
        raise ValueError(label+'下界超过上界')
    return lo,hi


def _route_report(model, context):
    from nbt_collision import check_routes
    start,targets=context.get('start'),context.get('targets')
    legs=context.get('route_legs',[])
    if (start is None) != (not targets) or (legs and (start is None or not targets)) or (context.get('require_routes') and (start is None or not targets)):
        raise ValueError('全局必要路线需要起点和终点')
    if start is None:
        return dict(passed=True,checked=False,targets=[],legs=[])
    report=check_routes(model,start,targets,max_poses=250000)
    if not report['passed']:
        raise ValueError('全局必要路线未通过，不能签发切片')
    reports=[]
    for leg in legs:
        copy=empty_volume(model.size);copy.blocks=dict(model.blocks)
        for barrier in leg.get('validation_only_barriers',[]):
            lo,hi=_bounds(barrier,'路线屏障')
            if not copy.in_bounds(lo) or not copy.in_bounds(hi) or math.prod(hi[i]-lo[i]+1 for i in range(3))>MAX_PROTECTED_CELLS:
                raise ValueError('路线屏障越界或过大')
            copy.box(lo,hi,'stone')
        checked=check_routes(copy,leg['start'],leg['targets'],max_poses=250000)
        if not checked['passed']:
            raise ValueError('全局必要路线段未通过：'+str(leg.get('name','未命名')))
        reports.append(dict(name=leg.get('name'),report=checked))
    return dict(passed=True,checked=True,targets=report['targets'],legs=reports)


def _protected_boxes(model, context, routes, region):
    """Project host protection and exact swept routes into local slice coordinates."""
    origin,end=region
    boxes=set()
    def add(lo,hi):
        clipped_lo=tuple(max(lo[i],origin[i],0) for i in range(3))
        clipped_hi=tuple(min(hi[i],end[i],model.size[i]-1) for i in range(3))
        if any(clipped_lo[i]>clipped_hi[i] for i in range(3)):return
        local_lo=tuple(clipped_lo[i]-origin[i] for i in range(3))
        local_hi=tuple(clipped_hi[i]-origin[i] for i in range(3))
        boxes.add((local_lo,local_hi))
        if len(boxes)>MAX_BOXES:raise ValueError('切片路线保护范围过多')
    for field in ('protected_boxes','reserved_boxes'):
        for value in context.get(field,[]):add(*_bounds(value,'保护或保留范围'))
    if context.get('openings'):
        from nbt_whole_validation import standalone_openings
        standalone_openings(model,context)
        for opening in context['openings']:
            lo,hi=_bounds(dict(lo=opening['lo'],hi=opening['hi']),'开口')
            add(tuple(v-1 for v in lo),tuple(v+1 for v in hi))
    for port in context.get('ports',[]):
        lo,hi=point(port['min']),point(port['max'])
        add(tuple(v-1 for v in lo),tuple(v+1 for v in hi))
    paths=list(context.get('protected_paths',[]))
    paths.extend(target['path'] for target in routes.get('targets',[]) if target.get('path'))
    for leg in routes.get('legs',[]):
        paths.extend(target['path'] for target in leg['report']['targets'] if target.get('path'))
    for path in paths:
        if not isinstance(path,(list,tuple)) or not path:
            raise ValueError('全局保护路线不能为空')
        for a,b in zip(path,list(path[1:])+[path[-1]]):
            if len(a)!=3 or len(b)!=3 or any(type(v) not in (int,float) or not math.isfinite(v) for v in [*a,*b]):
                raise ValueError('全局保护路线坐标无效')
            lo=(math.floor(min(a[0],b[0])-.3),math.floor(min(a[1],b[1])-.01),math.floor(min(a[2],b[2])-.3))
            hi=(math.ceil(max(a[0],b[0])+.3)-1,math.ceil(max(a[1],b[1])+1.8)-1,math.ceil(max(a[2],b[2])+.3)-1)
            add(lo,hi)
    return boxes


def create_slice(workspace,request):
    workspace=require_creative_workspace(workspace)
    if not isinstance(request,dict) or set(request)-{'source','source_sha256','context','region','write_bounds','output'}:
        raise ValueError('组装切片请求字段无效')
    source=_workspace_path(workspace,request.get('source'))
    if not source.is_relative_to(workspace/'nbt_models'):
        raise ValueError('组装切片源须位于工作区 nbt_models')
    expected=request.get('source_sha256')
    if not isinstance(expected,str) or len(expected)!=64:
        raise ValueError('组装切片需要源 SHA256')
    working=WorkingModel.open(workspace,source,request.get('context'),source_sha256=expected)
    if not working._assembly_binding:
        raise ValueError('切片源须为组装制作源')
    lo,hi=_bounds(request.get('region'),'切片范围')
    size=tuple(hi[i]-lo[i]+1 for i in range(3))
    if any(n>294 for n in size):raise ValueError('切片每轴最多294格')
    writable_lo,writable_hi=_bounds(request.get('write_bounds'),'可写范围')
    if any(writable_lo[i]<lo[i] or writable_hi[i]>hi[i] for i in range(3)) or not working.model.in_bounds(writable_lo) or not working.model.in_bounds(writable_hi):
        raise ValueError('可写范围须位于切片和完整主稿内')
    destination=_workspace_path(workspace,request.get('output'))
    handoffs=workspace/'nbt_models/_workspaces/assembly-handoffs'
    if not destination.is_relative_to(handoffs) or destination==handoffs or destination.is_symlink():
        raise ValueError('切片输出须为 assembly-handoffs 下的新目录')
    if destination.exists() and (not destination.is_dir() or not ((destination/'.slice-publication.json').is_file() or (destination/'slice.json').is_file())):
        raise ValueError('切片输出目录已被占用，无法安全重试')
    routes=_route_report(working.model,working.context)
    protected=_protected_boxes(working.model,working.context,routes,(lo,hi))
    writable_local_lo=tuple(writable_lo[i]-lo[i] for i in range(3))
    writable_local_hi=tuple(writable_hi[i]-lo[i] for i in range(3))
    for axis in range(3):
        if writable_local_lo[axis]>0:
            a=[0,0,0];b=[n-1 for n in size];b[axis]=writable_local_lo[axis]-1
            protected.add((tuple(a),tuple(b)))
        if writable_local_hi[axis]<size[axis]-1:
            a=[0,0,0];b=[n-1 for n in size];a[axis]=writable_local_hi[axis]+1
            protected.add((tuple(a),tuple(b)))
    if len(protected)>MAX_BOXES or sum(math.prod(b[i]-a[i]+1 for i in range(3)) for a,b in protected)>MAX_PROTECTED_CELLS:
        raise ValueError('切片保护范围过大，请缩小切片')
    local=Volume(size);walls=set()
    for p,value in working.model.blocks.items():
        if all(lo[i]<=p[i]<=hi[i] for i in range(3)):
            translated=tuple(p[i]-lo[i] for i in range(3));local.blocks[translated]=value
            if p in working.walls:walls.add(translated)
    context=dict(mode='standalone',openings=[],protected_boxes=[dict(lo=list(a),hi=list(b)) for a,b in sorted(protected)])
    destination.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.slice-',dir=destination.parent) as temporary:
        stage=Path(temporary);baseline=stage/'baseline.snbt';saved=save_snbt(baseline,local,walls)
        context_raw=(json.dumps(context,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode('utf8')
        if len(context_raw)>MAX_HANDOFF_BYTES:raise ValueError('切片保护配置过大')
        (stage/'coordinates.json').write_bytes(context_raw)
        record=dict(schema_version=1,kind='nbtcreator-assembly-slice',source=source.relative_to(workspace).as_posix(),
                    source_sha256=expected,source_model_sha256=model_hash(working.model,working.walls),
                    assembly_partitions=[dict(file=name,sha256=sha) for name,sha in working._assembly_binding[2]],
                    origin=list(lo),size=list(size),write_bounds=dict(lo=list(writable_lo),hi=list(writable_hi)),
                    baseline=dict(file='baseline.snbt',sha256=saved['source_sha256']),
                    coordinates=dict(file='coordinates.json',sha256=hashlib.sha256(context_raw).hexdigest()),
                    host_context=working.context,host_context_sha256=digest(working.context),routes=routes)
        raw=(json.dumps(record,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode('utf8')
        if len(raw)>MAX_HANDOFF_BYTES:raise ValueError('切片清单过大，请缩小范围或路线')
        (stage/'slice.json').write_bytes(raw)
        working._unchanged()
        manifest_sha=hashlib.sha256(raw).hexdigest()
        journal=dict(schema_version=1,manifest_sha256=manifest_sha,baseline_sha256=saved['source_sha256'],
                     coordinates_sha256=hashlib.sha256(context_raw).hexdigest())
        journal_raw=(json.dumps(journal,sort_keys=True,separators=(',',':'))+'\n').encode('utf8')
        journal_stage=stage/'.slice-publication.json';journal_stage.write_bytes(journal_raw)
        try:
            destination.mkdir();os.link(journal_stage,destination/'.slice-publication.json')
        except FileExistsError:
            if not destination.is_dir():raise ValueError('切片输出目录已被占用') from None
        journal_file=destination/'.slice-publication.json'
        existing_manifest=destination/'slice.json'
        if journal_file.is_file():
            if journal_file.is_symlink() or journal_file.read_bytes()!=journal_raw:
                raise ValueError('切片发布记录已变化或目录被占用')
        elif not existing_manifest.is_file() or existing_manifest.is_symlink() or _file_sha(existing_manifest)!=manifest_sha:
            raise ValueError('切片输出目录已被占用，无法安全重试')
        for name,sha in [('baseline.snbt',saved['source_sha256']),('coordinates.json',journal['coordinates_sha256'])]:
            target=destination/name
            try:os.link(stage/name,target)
            except FileExistsError:
                if target.is_symlink() or not target.is_file() or _file_sha(target)!=sha:
                    raise ValueError('切片已有文件已变化，未覆盖：'+name) from None
        working._unchanged()
        try:os.link(stage/'slice.json',existing_manifest)
        except FileExistsError:
            if existing_manifest.is_symlink() or not existing_manifest.is_file() or _file_sha(existing_manifest)!=manifest_sha:
                raise ValueError('切片清单已变化，未覆盖') from None
    return dict(manifest=str(destination/'slice.json'),manifest_sha256=manifest_sha,
                baseline=str(destination/'baseline.snbt'),context=str(destination/'coordinates.json'),
                origin=list(lo),size=list(size),write_bounds=record['write_bounds'],routes_checked=routes['checked'],
                protected_boxes=len(protected),approval_created=False)


def _file_sha(path):
    result=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):result.update(chunk)
    return result.hexdigest()


def _box_index(boxes):
    if len(boxes)>MAX_BOXES or sum(math.prod(b[i]-a[i]+1 for i in range(3)) for a,b in boxes)>MAX_PROTECTED_CELLS:
        raise ValueError('切片保护范围过大，请缩小切片')
    index={}
    for a,b in boxes:
        for x in range(a[0]//16,b[0]//16+1):
            for y in range(a[1]//16,b[1]//16+1):
                for z in range(a[2]//16,b[2]//16+1):index.setdefault((x,y,z),[]).append((a,b))
    return index


def _changed_parts(source,expected):
    """Report original partition bounds when a bound part is missing or altered."""
    try:
        if source.stat().st_size>MAX_MANIFEST_BYTES or _file_sha(source)!=expected:return []
        data=json.loads(source.read_bytes())
        if data.get('format')!='nbtcreator-assembly' or not isinstance(data.get('partitions'),list):return []
        changed=[]
        for item in data['partitions']:
            offset=point(item['offset']);size=point(item['size'])
            if any(not 1<=n<=294 for n in size):return []
            try:matches=_file_sha(_part_path(source.parent.resolve(),item['file']))==item['sha256']
            except (OSError,ValueError):matches=False
            if not matches:
                changed.append(dict(partition=item['file'],lo=list(offset),hi=[offset[i]+size[i]-1 for i in range(3)]))
        return changed
    except (OSError,ValueError,KeyError,TypeError):
        return []


def merge_slices(workspace,request):
    """Validate every bound handoff and publish one all-or-nothing draft."""
    workspace=require_creative_workspace(workspace)
    if not isinstance(request,dict) or set(request)-{'source','source_sha256','context','slices','name_zh'}:
        raise ValueError('组装回装请求字段无效')
    source=_workspace_path(workspace,request.get('source'))
    if not source.is_relative_to(workspace/'nbt_models'):
        raise ValueError('组装回装源须位于工作区 nbt_models')
    expected=request.get('source_sha256')
    if not isinstance(expected,str) or len(expected)!=64:
        raise ValueError('组装回装需要源 SHA256')
    slices=request.get('slices')
    if not isinstance(slices,list) or not 1<=len(slices)<=128:
        raise ValueError('组装回装须包含1至128片')
    try:working=WorkingModel.open(workspace,source,request.get('context'),source_sha256=expected)
    except ValueError as error:
        changed=_changed_parts(source,expected)
        if changed:raise ModelConflict('SLICE_STALE_SOURCE',changed) from error
        raise
    if not working._assembly_binding:raise ValueError('回装源须为组装制作源')
    context_sha=digest(working.context);host_hash=model_hash(working.model,working.walls)
    routes=_route_report(working.model,working.context)
    expected_parts=[dict(file=name,sha256=sha) for name,sha in working._assembly_binding[2]]
    checked=[];changes=[];seen={};receipt_slices=[]
    for entry in slices:
        if not isinstance(entry,dict) or set(entry)!={'manifest','manifest_sha256','candidate','candidate_sha256'}:
            raise ValueError('回装切片字段无效')
        manifest=_workspace_path(workspace,entry['manifest']);candidate=_workspace_path(workspace,entry['candidate'])
        if not manifest.is_file() or manifest.stat().st_size>MAX_HANDOFF_BYTES or not candidate.is_file() or candidate.suffix.lower()!='.snbt':
            raise ValueError('切片清单或候选不存在、格式无效或过大')
        manifest_sha=entry['manifest_sha256'];candidate_sha=entry['candidate_sha256']
        if not isinstance(manifest_sha,str) or not isinstance(candidate_sha,str) or _file_sha(manifest)!=manifest_sha or _file_sha(candidate)!=candidate_sha:
            raise ValueError('切片清单或候选哈希不一致')
        raw=manifest.read_bytes()
        if len(raw)>MAX_HANDOFF_BYTES or hashlib.sha256(raw).hexdigest()!=manifest_sha:
            raise ValueError('切片清单读取期间发生变化')
        record=json.loads(raw)
        if not isinstance(record,dict) or record.get('schema_version')!=1 or record.get('kind')!='nbtcreator-assembly-slice':
            raise ValueError('切片清单格式无效')
        if (record.get('source')!=source.relative_to(workspace).as_posix() or record.get('source_sha256')!=expected or
            record.get('source_model_sha256')!=host_hash or record.get('assembly_partitions')!=expected_parts):
            raise ModelConflict('SLICE_STALE_SOURCE',[dict(manifest=str(manifest),write_bounds=record.get('write_bounds'))])
        if record.get('host_context_sha256')!=context_sha or digest(record.get('host_context'))!=context_sha:
            raise ModelConflict('SLICE_STALE_CONTEXT',[dict(manifest=str(manifest))])
        origin=point(record.get('origin'));size=point(record.get('size'))
        if any(not 1<=n<=294 for n in size):raise ValueError('切片尺寸无效')
        end=tuple(origin[i]+size[i]-1 for i in range(3))
        lo,hi=_bounds(record.get('write_bounds'),'可写范围')
        if any(lo[i]<origin[i] or hi[i]>end[i] for i in range(3)) or not working.model.in_bounds(lo) or not working.model.in_bounds(hi):
            raise ValueError('切片可写范围无效')
        baseline_spec=record.get('baseline');context_spec=record.get('coordinates')
        if not isinstance(baseline_spec,dict) or set(baseline_spec)!={'file','sha256'} or baseline_spec['file']!='baseline.snbt' or not isinstance(context_spec,dict) or set(context_spec)!={'file','sha256'} or context_spec['file']!='coordinates.json':
            raise ValueError('切片基线或保护配置无效')
        baseline=_workspace_path(workspace,str(manifest.parent/'baseline.snbt'))
        coordinates=_workspace_path(workspace,str(manifest.parent/'coordinates.json'))
        if _file_sha(baseline)!=baseline_spec['sha256'] or _file_sha(coordinates)!=context_spec['sha256']:
            raise ValueError('切片基线或保护配置哈希不一致')
        before,before_walls=read_snbt(baseline);after,after_walls=read_snbt(candidate)
        if before.size!=size or after.size!=size or not getattr(before,'_wall_mask_declared',False) or not getattr(after,'_wall_mask_declared',False):
            raise ValueError('切片尺寸或显式墙层无效')
        if before._snbt_extras!=after._snbt_extras:
            raise ValueError('切片候选含无法回装的额外 SNBT 数据')
        host_blocks={tuple(p[i]-origin[i] for i in range(3)):v for p,v in working.model.blocks.items()
                     if all(origin[i]<=p[i]<=end[i] for i in range(3))}
        host_walls={tuple(p[i]-origin[i] for i in range(3)) for p in working.walls
                    if all(origin[i]<=p[i]<=end[i] for i in range(3))}
        if before.blocks!=host_blocks or before_walls!=host_walls:
            mismatched={p for p in before.blocks.keys()|host_blocks.keys() if before.get(p)!=host_blocks.get(p,'minecraft:air')} | (before_walls^host_walls)
            raise ModelConflict('SLICE_BASE_MISMATCH',[dict(manifest=str(manifest),pos=[origin[i]+p[i] for i in range(3)]) for p in sorted(mismatched)[:32]])
        protected=_protected_boxes(working.model,working.context,routes,(origin,end))
        protection_index=_box_index(protected)
        changed={p for p in before.blocks.keys()|after.blocks.keys() if before.get(p)!=after.get(p)} | (before_walls^after_walls)
        if len(changes)+len(changed)>working.limits['max_written_positions']:
            raise ValueError('组装回装写入量超过上限')
        slice_positions=[]
        for local in sorted(changed):
            pos=tuple(origin[i]+local[i] for i in range(3))
            if not working.model.in_bounds(pos) or any(pos[i]<lo[i] or pos[i]>hi[i] for i in range(3)):
                raise ModelConflict('SLICE_READ_ONLY',[dict(manifest=str(manifest),pos=list(pos))])
            if any(all(a[i]<=local[i]<=b[i] for i in range(3)) for a,b in protection_index.get(tuple(v//16 for v in local),[])):
                raise ModelConflict('SLICE_PROTECTED',[dict(manifest=str(manifest),pos=list(pos))])
            if pos in seen:
                raise ModelConflict('SLICE_OVERLAP',[dict(manifests=[seen[pos],str(manifest)],pos=list(pos))])
            seen[pos]=str(manifest)
            slice_positions.append(pos)
            changes.append(dict(pos=list(pos),before=value_at(before,before_walls,local),after=value_at(after,after_walls,local)))
        checked.extend([(manifest,manifest_sha),(candidate,candidate_sha),(baseline,baseline_spec['sha256']),(coordinates,context_spec['sha256'])])
        bounds=dict(lo=[min(p[i] for p in slice_positions) for i in range(3)],hi=[max(p[i] for p in slice_positions) for i in range(3)]) if slice_positions else None
        receipt_slices.append(dict(manifest_sha256=manifest_sha,candidate_sha256=candidate_sha,changed_positions=len(changed),changed_bounds=bounds))
    def recheck():
        working._unchanged()
        for path,sha in checked:
            _workspace_path(workspace,str(path))
            if _file_sha(path)!=sha:raise ValueError('回装期间切片或候选发生变化')
    recheck()
    working.patch(changes)
    final_routes=_route_report(working.model,working.context)
    proof=dict(schema_version=1,source_sha256=expected,source_model_sha256=host_hash,
               host_context_sha256=context_sha,slices=receipt_slices,changed_positions=len(changes),changes_file='changes.json',routes=final_routes)
    recheck()
    saved=working.save_draft(name_zh=request.get('name_zh'),attachments={'handoff.json':proof},before_publish=recheck)
    return dict(saved=saved,changed_positions=len(changes),slices=receipt_slices,routes=final_routes,
                approval_created=False,nbt_exported=False)
