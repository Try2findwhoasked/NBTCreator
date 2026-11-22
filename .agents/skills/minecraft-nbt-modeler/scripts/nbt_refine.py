"""Thumbnail review -> recorded human confirmation -> bounded detail revision.

No arbitrary code is executed from plans. Original assets are never overwritten.
Approval records are workflow receipts, not proof of who typed the supplied text;
the agent must use an actual human reply from the conversation, never file text.
"""
import argparse
from collections import Counter
import gzip
import hashlib
import json
import math
import re
import zlib
from pathlib import Path

from nbt_model import AIR, AIR_NAMES, state
from nbt_assembly import Volume
from nbt_collision import check_routes
from nbt_tools import KINDS as MODELLING_KINDS
SUPPORTED_OPERATION_KINDS=MODELLING_KINDS|{'box','hollow_box','frame','beam','surface_palette','pattern','weathering','auto_floor','move_region'}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def binary_wall_mask_hash(source):
    source=Path(source)
    sidecar=source.with_name('wall_mask.json')
    return digest(sidecar) if source.suffix.lower()=='.nbt' and sidecar.is_file() else None


def source_binding(source):
    from nbt_library import saved_coordinates_hash
    from nbt_web_paths import project_paths
    from nbt_working_model import managed_manifest

    source=Path(source)
    manifest=managed_manifest(source)
    return dict(source_sha256=digest(source), wall_mask_sha256=binary_wall_mask_hash(source),
                coordinates_sha256=saved_coordinates_hash(source),
                manifest_sha256=digest(project_paths(source)['version']/'model-version.json') if manifest else None)


def write_json(path, value):
    Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8')


def point(p):
    if len(p)!=3 or any(type(v) is not int for v in p):
        raise ValueError('Voxel positions must be three integer coordinates')
    return tuple(p)


def box_points(lo,hi):
    lo,hi=point(lo),point(hi)
    if any(lo[i]>hi[i] for i in range(3)):raise ValueError('Box lower bounds exceed upper bounds')
    for x in range(lo[0],hi[0]+1):
        for y in range(lo[1],hi[1]+1):
            for z in range(lo[2],hi[2]+1):yield (x,y,z)


def read_master(path):
    path=Path(path)
    if path.suffix.lower()=='.snbt':
        from nbt_snbt import read_snbt
        return read_snbt(path)
    if path.suffix.lower()=='.nbt':
        from nbt_snbt import read_binary
        return read_binary(path)
    raw=path.read_bytes()
    if not raw.startswith(b'\x1f\x8b'):
        detail='无法识别的文件'
        if raw.lstrip().startswith((b'{',b'[')):
            detail='JSON 文件'
            if len(raw)<=4*1024*1024:
                try:sample=json.loads(raw)
                except (ValueError,UnicodeDecodeError):sample=None
                if isinstance(sample,dict):
                    if sample.get('preview_only') is True and isinstance(sample.get('master_blocks'),list):detail='控制候选快照；请改用 --snapshot，仍须通过候选校验'
                    elif 'blocks' in sample and 'size' in sample:detail='普通渲染快照；请从原始制作源重新生成'
                    elif 'parts' in sample or 'partitions' in sample:detail='组装清单；此入口不支持，请使用 assembly inspect、model 或 render'
            else:
                # A large snapshot can take much more memory to parse than its
                # source bytes. These are hints only, never a validation path.
                if re.search(rb'"preview_only"\s*:\s*true\b',raw) and re.search(rb'"master_blocks"\s*:',raw):detail='疑似控制候选快照；请改用 --snapshot，仍须通过候选校验'
                elif re.search(rb'"blocks"\s*:',raw) and re.search(rb'"size"\s*:',raw):detail='疑似普通渲染快照；请从原始制作源重新生成'
                elif re.search(rb'"(?:parts|partitions)"\s*:',raw):detail='疑似组装清单；此入口不支持，请使用 assembly inspect、model 或 render'
        raise ValueError('不支持的制作源格式（'+detail+'）：请使用 SNBT、NBT 或压缩制作主稿；JSON 不能直接作为 --source。')
    try:
        data=json.loads(gzip.decompress(raw))
    except (gzip.BadGzipFile,EOFError,zlib.error,UnicodeDecodeError,json.JSONDecodeError) as error:
        raise ValueError('压缩制作主稿损坏或无效，请检查文件或从历史版本恢复') from error
    model=Volume(data['size'])
    for p,v in data['blocks']:
        p=point(p)
        if p in model.blocks:raise ValueError('Duplicate master voxel')
        model.put(p,v)
    if data.get('geometry_sha256')!=model.fingerprint():raise ValueError('Master fingerprint mismatch')
    walls={point(p) for p in data.get('wall_positions',[])}
    if any(not model.in_bounds(p) for p in walls):raise ValueError('Wall mask exceeds source bounds')
    model._wall_mask_declared='wall_positions' in data
    return model,walls


def resolve_wall_mask(model, walls, context):
    # Legacy geometry can include old wall positions cleared when openings were cut.
    walls=set(walls) & model.blocks.keys()
    if 'wall_positions' not in context:
        return walls
    declared={point(p) for p in context['wall_positions']}
    if not declared <= model.blocks.keys():
        raise ValueError('显式墙层归属越界或指向空气')
    if getattr(model,'_wall_mask_declared',False) and declared!=walls:
        from nbt_working_model import ModelConflict
        raise ModelConflict('WALL_SOURCE_MISMATCH', [dict(source_walls=len(walls), context_walls=len(declared))])
    return declared


def save_master(path,model,walls):
    if Path(path).suffix.lower()=='.snbt':
        from nbt_snbt import save_snbt
        return save_snbt(path,model,walls)
    data=dict(size=list(model.size),blocks=[[list(p),v] for p,v in sorted(model.blocks.items())],
              wall_positions=[list(p) for p in sorted(walls)],absent_positions=AIR,
              geometry_sha256=model.fingerprint())
    Path(path).write_bytes(gzip.compress(json.dumps(data,separators=(',',':')).encode(),mtime=0))
    disk,disk_walls=read_master(path)
    if disk.blocks!=model.blocks or disk_walls!=walls:raise ValueError('Master roundtrip failed')


def layout(model,config):
    from nbt_whole_validation import validation_mode,standalone_cells
    if validation_mode(config)=='standalone':
        return standalone_cells(model,config) or []
    if type(config.get('cell_size',48)) is not int or config.get('cell_size',48)!=48:
        raise ValueError('SAODG requires 48-block footprint cells')
    cells=[tuple(c) for c in config['cells']]
    if not cells or len(set(cells))!=len(cells) or any(len(c)!=2 or any(type(v) is not int or v<0 for v in c) for c in cells):
        raise ValueError('Declare distinct occupied XZ cells')
    if model.size!=(48*(max(c[0] for c in cells)+1),model.size[1],48*(max(c[1] for c in cells)+1)):
        raise ValueError('Source dimensions do not match the complete declared footprint')
    found={cells[0]};pending=[cells[0]]
    while pending:
        x,z=pending.pop()
        for q in ((x-1,z),(x+1,z),(x,z-1),(x,z+1)):
            if q in cells and q not in found:found.add(q);pending.append(q)
    if found!=set(cells):raise ValueError('Occupied cells must be four-neighbour connected')
    if not 8<=model.size[1]<=48:raise ValueError('Height must be 8..48')
    if any((p[0]//48,p[2]//48) not in cells for p in model.blocks):raise ValueError('Source writes into excluded cell')
    return cells


def declared_ports(model,config):
    cells=set(layout(model,config));h=config['door_y']
    if type(h) is not int or not 2<=h<=model.size[1]-6:raise ValueError('Invalid door_y')
    positions=set();definitions=config.get('ports',[])
    if len({p['id'] for p in definitions})!=len(definitions):raise ValueError('Duplicate port id')
    directions=dict(west=(-1,0),east=(1,0),north=(0,-1),south=(0,1))
    for p in definitions:
        a,b=point(p['min']),point(p['max']);f=p['facing'];dx,dz=directions[f]
        cx,cz=a[0]//48,a[2]//48
        expected=dict(west=((cx*48,h,cz*48+21),(cx*48,h+4,cz*48+26)),
                      east=((cx*48+47,h,cz*48+21),(cx*48+47,h+4,cz*48+26)),
                      north=((cx*48+21,h,cz*48),(cx*48+26,h+4,cz*48)),
                      south=((cx*48+21,h,cz*48+47),(cx*48+26,h+4,cz*48+47)))[f]
        if (a,b)!=expected or (cx,cz) not in cells or (cx+dx,cz+dz) in cells:
            raise ValueError('Port must be an exterior, centred 6x5 doorway')
        for x in range(a[0],b[0]+1):
            for z in range(a[2],b[2]+1):
                if model.get((x,h-1,z)) in AIR_NAMES:raise ValueError('Doorstep missing')
                if any(model.get((x,y,z)) not in AIR_NAMES for y in range(h,h+5)):raise ValueError('Door not open')
                positions.update((x,y,z) for y in range(h,h+5))
    return positions


def validate_saodg(model,config):
    if not config.get('targets'):
        raise ValueError('Declare non-empty required route targets; do not remove them to obtain a passing report')
    port_cells=declared_ports(model,config)
    capped=Volume(model.size);capped.blocks=dict(model.blocks)
    for p in port_cells:capped.put(p,'stone_bricks')
    seal=capped.check_sealed(config['interior_probes'])
    routes=check_routes(model,config['start'],config['targets'])
    if not routes['passed']:raise ValueError('Static route validation failed: '+json.dumps({k:v for k,v in routes.items() if k!='targets'}))
    # Extra named legs certify specific authored connections, not just a detour.
    legs=[]
    for leg in config.get('route_legs',[]):
        copy=Volume(model.size);copy.blocks=dict(model.blocks)
        for bounds in leg.get('validation_only_barriers',[]):
            copy.box(bounds['lo'],bounds['hi'],'stone')
        result=check_routes(copy,leg['start'],leg['targets'])
        if not result['passed']:raise ValueError('Required route leg failed: '+leg['name'])
        legs.append(dict(name=leg['name'],report=result))
    return dict(passed=True,legal_port_cells=len(port_cells),recapped_seal=seal,
                routes=routes,route_legs=legs,runtime_verified=False)


def validate(model,config):
    from nbt_whole_validation import validate_whole
    return validate_whole(model,config)


def protections(model,config):
    from nbt_whole_validation import protective_openings
    protected=set()
    protected.update(protective_openings(model,config))
    for bounds in config.get('protected_boxes',[]):protected.update(box_points(bounds['lo'],bounds['hi']))
    # Preserve aperture, adjacent throat, floor and lintel, not just the door air.
    for port in config.get('ports',[]):
        a,b=port['min'],port['max']
        for p in box_points([a[0]-1,a[1]-1,a[2]-1],[b[0]+1,b[1]+1,b[2]+1]):
            if model.in_bounds(p):protected.add(p)
    for path in config.get('protected_paths',[]):
        if not path:raise ValueError('Protected path cannot be empty')
        # Cover full swept player AABB plus the support layer at every edge.
        for a,b in zip(path,path[1:]+path[-1:]):
            if len(a)!=3 or len(b)!=3 or any(not math.isfinite(float(v)) for v in [*a,*b]):raise ValueError('Invalid path pose')
            lo=[math.floor(min(a[0],b[0])-.3),math.floor(min(a[1],b[1])-.01),math.floor(min(a[2],b[2])-.3)]
            hi=[math.ceil(max(a[0],b[0])+.3)-1,math.ceil(max(a[1],b[1])+1.8)-1,math.ceil(max(a[2],b[2])+.3)-1]
            protected.update(p for p in box_points(lo,hi) if model.in_bounds(p))
    return protected


def _render(model,camera,path):
    import numpy as np
    from nbt_preview import make_grid,render
    grid,colors,approx=make_grid(model,cuts=camera.get('cuts',[]))
    eye=np.array(camera['eye'],float);target=np.array(camera['target'],float)
    if not np.all(np.isfinite(eye)) or not np.all(np.isfinite(target)) or np.linalg.norm(eye-target)<1e-6:raise ValueError('Invalid camera')
    if camera['role']=='entry':
        from nbt_collision import _Space
        if camera.get('cuts') or not _Space(model).standing((float(eye[0]),float(eye[1]-1.62),float(eye[2]))):
            raise ValueError('Entry thumbnail must be an uncut, supported player eye at feet+1.62')
    image,visible=render(grid,colors,eye,target,640,400,camera.get('fov',60))
    if visible==0:raise ValueError('Thumbnail contains no model pixels')
    image.save(path)
    return dict(file=path.name,sha256=digest(path),role=camera['role'],camera=camera,
                source_geometry_sha256=model.fingerprint(),approximations=approx)


def refinement_context(source, config, source_hash):
    from nbt_history import source_workspace
    from nbt_working_model import WorkingModel, managed_manifest

    if not managed_manifest(source):
        from nbt_library import inherit_edit_constraints
        return None, inherit_edit_constraints(config,source)
    working = WorkingModel.open(source_workspace(source), source, source_sha256=source_hash)
    options = {'cameras', 'max_changed_blocks', 'wall_positions'}
    if any(key not in options and (key not in working.context or value != working.context[key])
           for key, value in config.items()):
        raise ValueError('审阅配置与受管制作版的坐标或保护约束不一致')
    if 'wall_positions' in config and {point(p) for p in config['wall_positions']} != working.walls:
        raise ValueError('审阅配置与源制作版墙层不一致')
    budget = config.get('max_changed_blocks', 4096)
    if type(budget) is not int or budget < 1:
        raise ValueError('精修改动预算须为正整数')
    effective = dict(working.context, cameras=config.get('cameras', working.context.get('cameras', [])),
                     max_changed_blocks=min(budget, working._budget()))
    return working, effective


def prepare(source,config,review_dir):
    source=Path(source).resolve();review=Path(review_dir).resolve()
    if review.exists():raise FileExistsError('Use a new review directory to preserve previous review')
    binding=source_binding(source)
    source_hash=binding['source_sha256']
    mask_hash=binding['wall_mask_sha256']
    context_hash=binding['coordinates_sha256']
    working,config=refinement_context(source,json.loads(json.dumps(config)),source_hash)
    if working and (working.kind!='building' or working.phase!='opened'):
        raise ValueError('整栋精修需要已完成基础检查的建筑制作版')
    model,walls=(working.model,working.walls) if working else read_master(source)
    cells=layout(model,config)
    walls=resolve_wall_mask(model,walls,config)
    config.pop('wall_positions',None)
    from nbt_whole_validation import validation_mode
    standalone=validation_mode(config)=='standalone'
    if any(not model.in_bounds(p) or (not standalone and (p[0]//48,p[2]//48) not in cells) for p in walls):raise ValueError('Invalid wall mask')
    walls.intersection_update(model.blocks)
    if standalone and not walls and config.get('allow_empty_wall_mask') is not True:
        raise ValueError('An empty standalone wall mask requires an explicit allow_empty_wall_mask=true')
    if not standalone and any(not any((p[0]//48,p[2]//48)==cell and model.get(p) not in AIR_NAMES for p in walls) for cell in cells):
        raise ValueError('Preserve an authored whole-source wall mask for every occupied cell')
    cameras=config['cameras']
    if not cameras or len(cameras)>6 or not {'whole','entry'}.issubset({c['role'] for c in cameras}):
        raise ValueError('Provide whole and entry thumbnails, up to six cameras')
    baseline=validate(model,config)
    review.mkdir(parents=True)
    save_master(review/'source.master.json.gz',model,walls)
    write_json(review/'config.json',config);write_json(review/'baseline_validation.json',baseline)
    thumbs=[_render(model,c,review/f'thumbnail_{i:02}.png') for i,c in enumerate(cameras)]
    from PIL import Image,ImageDraw
    sheet=Image.new('RGB',(640*len(thumbs),438),'#14202b');draw=ImageDraw.Draw(sheet)
    for i,t in enumerate(thumbs):
        sheet.paste(Image.open(review/t['file']),(i*640,32));draw.text((i*640+12,10),t['role'],fill='white')
    sheet.save(review/'thumbnails.png')
    if source_binding(source)!=binding:
        raise ValueError('Original changed while generating thumbnails; prepare a new review')
    workspace=next((parent.parent for parent in source.parents if parent.name=='nbt_models'),None)
    source_path=source.relative_to(workspace).as_posix() if workspace and review.is_relative_to(workspace) else str(source)
    record=dict(stage='awaiting_user_review',source=source_path,source_sha256=source_hash,
                input_binding=binding,
                binary_wall_mask_sha256=mask_hash,
                source_coordinates_sha256=context_hash,
                snapshot_sha256=digest(review/'source.master.json.gz'),source_geometry_sha256=model.fingerprint(),
                config_sha256=digest(review/'config.json'),validation_sha256=digest(review/'baseline_validation.json'),thumbnails=thumbs,
                sheet=dict(file='thumbnails.png',sha256=digest(review/'thumbnails.png')),
                workflow='restore_approved_whole_uncut_master_then_refine_and_save',
                instruction='Show these thumbnails to the human and wait for an explicit request to refine this draft.')
    write_json(review/'review.json',record)
    return record


def review_source(review,value):
    source=Path(value)
    workspace=next((parent for parent in Path(review).resolve().parents if (parent/'nbt_models').is_dir()),None)
    if workspace:
        if source.is_absolute():
            parts=source.parts
            index=next((index for index in range(len(parts)-1,-1,-1) if parts[index]=='nbt_models'),None)
            if index is None:return source
            source=Path(*parts[index:])
        from nbt_web_paths import workspace_path
        resolved=workspace_path(workspace,source)
        if resolved.is_relative_to(workspace/'nbt_models'):return resolved
    if source.is_absolute():return source
    raise ValueError('审阅源路径越界或找不到对应的创作工作区')


def _current_review(review, expected_hash=None):
    from nbt_library import saved_coordinates_hash

    review=Path(review).resolve();raw=(review/'review.json').read_bytes()
    if expected_hash is not None and hashlib.sha256(raw).hexdigest()!=expected_hash:
        raise ValueError('Approval does not match current thumbnails')
    record=json.loads(raw)
    record['source']=str(review_source(review,record['source']))
    if (digest(record['source'])!=record['source_sha256']
            or binary_wall_mask_hash(record['source'])!=record.get('binary_wall_mask_sha256')):
        raise ValueError('Original source or wall mask changed; prepare new thumbnails')
    if ('source_coordinates_sha256' in record
            and saved_coordinates_hash(record['source'])!=record['source_coordinates_sha256']):
        raise ValueError('Original coordinates changed; prepare new thumbnails')
    if 'input_binding' in record and source_binding(record['source'])!=record['input_binding']:
        raise ValueError('Original managed source changed; prepare new thumbnails')
    for name,key in [('source.master.json.gz','snapshot_sha256'),('config.json','config_sha256')]:
        if digest(review/name)!=record[key]:raise ValueError('Review snapshot/config changed')
    if 'validation_sha256' in record and digest(review/'baseline_validation.json')!=record['validation_sha256']:
        raise ValueError('Review validation changed')
    for item in [*record['thumbnails'],record['sheet']]:
        file=(review/item['file']).resolve()
        if not file.is_relative_to(review) or digest(file)!=item['sha256']:raise ValueError('Reviewed thumbnail changed')
    return record


def record_user_approval(review,user_message,user_reviewed_thumbnails=False):
    """Call only with a human's actual conversational authorization, never inferred."""
    review=Path(review);review_hash=digest(review/'review.json')
    _current_review(review,review_hash)
    if not user_reviewed_thumbnails or not isinstance(user_message,str) or not user_message.strip():
        raise ValueError('Explicit human response after thumbnail review is required')
    approval=review/'approval.json'
    result=dict(stage='approved_for_refinement',review_sha256=review_hash,user_message=user_message,
                user_reviewed_thumbnails=True,
                boundary='Agent-provided receipt of actual human consent; not an authentication mechanism.')
    with approval.open('x',encoding='utf8') as file:
        json.dump(result,file,ensure_ascii=False,indent=2)
        file.write('\n')
    return result


def operation_candidates(model,operation,protected=()):
    candidates=_operation_candidates(model,operation,protected)
    from nbt_change_policy import clip_protected
    writable=clip_protected(operation,candidates,protected)
    if operation.get('kind') in ('box','beam','frame') and 'overwrite' in operation and not operation.get('write_group'):
        if type(operation['overwrite']) is not bool:raise ValueError('覆盖现有方块须为布尔开关')
        if not operation['overwrite']:
            occupied=[p for p,value in writable if model.get(p) not in AIR_NAMES and model.get(p)!=value]
            if occupied:
                from nbt_change_policy import WriteConflict
                raise WriteConflict('目标位置已有方块；移动构件，或勾选“允许AI构件覆盖现有方块”：'+str(occupied[:8]), 'occupied', occupied)
    return candidates


def _operation_candidates(model,operation,protected=()):
    kind=operation['kind']
    if type(operation.get('enabled',True)) is not bool:raise ValueError('Operation enabled must be a boolean')
    if not operation.get('enabled',True):return []
    from nbt_tools import KINDS, modelling_plan
    if kind in KINDS:
        return modelling_plan(model,operation,protected)[0]
    if kind=='pattern':
        from nbt_patterns import pattern_plan
        return pattern_plan(model,operation,protected)[0]
    if kind=='weathering':
        from nbt_weathering import weathering_plan
        return weathering_plan(model,operation,protected)[0]
    if kind=='move_region':
        lo,hi=point(operation['lo']),point(operation['hi']);delta=point(operation['offset'])
        if any(lo[i]<0 or hi[i]>=model.size[i] or lo[i]>hi[i] for i in range(3)):raise ValueError('移动范围超出建筑边界')
        source=set(box_points(lo,hi));edits={p:AIR for p in source}
        for p in sorted(source):
            target=tuple(p[i]+delta[i] for i in range(3))
            if not model.in_bounds(target):raise ValueError('移动目标超出建筑边界')
            if target not in source and model.get(target) not in AIR_NAMES and model.get(p) not in AIR_NAMES:
                from nbt_change_policy import WriteConflict
                raise WriteConflict('移动目标已有方块，请先腾空目标区域','occupied',[target])
            if model.get(p) not in AIR_NAMES:edits[target]=model.get(p)
        return sorted(edits.items())
    if kind=='hollow_box':
        lo,hi=point(operation['lo']),point(operation['hi']);thickness=operation.get('thickness',1)
        if type(thickness) is not int or thickness<1:raise ValueError('外壳厚度须为正整数')
        return [(p,state(operation['state']) if any(min(p[i]-lo[i],hi[i]-p[i])<thickness for i in range(3)) else AIR) for p in box_points(lo,hi)]
    if kind in ('box','frame','surface_palette'):
        lo,hi=point(operation['lo']),point(operation['hi'])
        candidates=list(box_points(lo,hi))
        if kind=='frame':
            axes=[i for i in range(3) if lo[i]!=hi[i]]
            if len(axes)!=2:raise ValueError('Frame must lie in one axis-aligned plane')
            thickness=operation.get('thickness',1)
            if type(thickness) is not int or thickness<1:raise ValueError('Invalid frame thickness')
            candidates=[p for p in candidates if any(min(p[i]-lo[i],hi[i]-p[i])<thickness for i in axes)]
        if kind=='surface_palette':
            palette=[state(v) for v in operation['palette']];allowed={state(v) for v in operation['from_states']}
            if not palette or any(v in AIR_NAMES for v in palette):raise ValueError('Surface palette cannot carve air')
            amount=float(operation.get('fraction',.15));seed=operation.get('seed',0)
            if not 0<=amount<=1:raise ValueError('Invalid surface fraction')
            result=[]
            for p in candidates:
                x,y,z=p
                if model.get(p) not in allowed:continue
                if not any(model.get(q) in AIR_NAMES for q in [(x-1,y,z),(x+1,y,z),(x,y-1,z),(x,y+1,z),(x,y,z-1),(x,y,z+1)]):continue
                number=int.from_bytes(hashlib.sha256(f'{seed}:{p}'.encode()).digest()[:8],'big')
                if number/(2**64)<amount:result.append((p,palette[number%len(palette)]))
            return result
        return [(p,state(operation['state'])) for p in candidates]
    if kind=='beam':
        a,b=point(operation['start']),point(operation['end']);width=operation.get('width',1)
        if type(width) is not int or width not in (1,3,5):raise ValueError('Beam width must be 1,3 or5')
        n=max(abs(a[i]-b[i]) for i in range(3));points=set();r=width//2
        for k in range(n+1):
            p=tuple(round(a[i]+(b[i]-a[i])*k/max(n,1)) for i in range(3))
            points.update(box_points([v-r for v in p],[v+r for v in p]))
        return [(p,state(operation['state'])) for p in sorted(points)]
    raise ValueError('Unsupported detail operation: '+str(kind))


def refine(review_dir,plan,output_dir,*,task_session=None,actor='external_agent'):
    review=Path(review_dir).resolve()
    approval_path=review/'approval.json'
    if not approval_path.is_file():raise PermissionError('Waiting for human thumbnail approval; no refinement performed')
    approval_bytes=approval_path.read_bytes();approval=json.loads(approval_bytes)
    review_hash=approval.get('review_sha256')
    if (approval.get('stage')!='approved_for_refinement' or approval.get('user_reviewed_thumbnails') is not True
            or not isinstance(review_hash,str) or not isinstance(approval.get('user_message'),str)
            or not approval['user_message'].strip()):
        raise ValueError('Approval does not match current thumbnails')
    record=_current_review(review,review_hash)
    out=Path(output_dir).resolve()
    if out.exists() or out==review or out in review.parents or review in out.parents:
        raise ValueError('Use a separate, new revision directory; source/review cannot be overwritten')
    model,walls=read_master(review/'source.master.json.gz');original=dict(model.blocks);old_walls=set(walls)
    config=json.loads((review/'config.json').read_text(encoding='utf8'))
    working,effective=refinement_context(Path(record['source']),config,record['source_sha256'])
    if effective!=config or working and (working.kind!='building' or working.phase!='opened'
                                        or working.model.blocks!=original or working.walls!=walls):
        raise ValueError('制作源或约束与审阅快照不一致，请重新生成审阅图')
    cells=layout(model,config)
    from nbt_whole_validation import validation_mode
    standalone=validation_mode(config)=='standalone'
    protected=protections(model,config);operations=plan['operations']
    if not operations or not isinstance(plan.get('style_note'),str) or not plan['style_note'].strip():
        raise ValueError('Detail plan needs operations and a shared whole-building style_note')
    summary=[];write_owners={}
    for operation in operations:
        if not operation.get('label'):raise ValueError('Each operation needs a meaningful node label')
        if type(operation.get('enabled',True)) is not bool:raise ValueError('Operation enabled must be a boolean')
        if not operation.get('enabled',True):
            summary.append(dict(label=operation['label'],kind=operation['kind'],skipped=True,reason='disabled',candidate_writes=0))
            continue
        from nbt_operation_scope import scoped_operation,enforce_scope
        operation,bounds=scoped_operation(operation,model.size)
        classification=operation.get('classification','body' if operation['kind']=='auto_floor' else 'inherit')
        if classification not in ('inherit','wall','body'):raise ValueError('Invalid detail classification')
        weathering_report=None
        pattern_report=None
        floor_report=None
        modelling_report=None
        from nbt_tools import KINDS, modelling_plan
        if operation['kind'] in KINDS:
            edits,modelling_report=modelling_plan(model,operation,protected)
        elif operation['kind']=='weathering':
            from nbt_weathering import weathering_plan
            edits,weathering_report=weathering_plan(model,operation,protected)
        elif operation['kind']=='pattern':
            from nbt_patterns import pattern_plan
            edits,pattern_report=pattern_plan(model,operation,protected)
        elif operation['kind']=='auto_floor':
            from nbt_floors import auto_floor_plan
            edits,floor_report=auto_floor_plan(model,operation,config,protected)
        else:
            edits=operation_candidates(model,operation,protected)
        from nbt_change_policy import enforce_overwrite, clip_protected
        operation=enforce_scope(bounds,operation,edits)
        edits=clip_protected(operation,edits,protected)
        enforce_overwrite(model,walls,operation,edits,write_owners)
        moved_walls={tuple(p[i]+operation['offset'][i] for i in range(3)) for p in walls if all(operation['lo'][i]<=p[i]<=operation['hi'][i] for i in range(3))} if operation['kind']=='move_region' else set()
        for p,value in edits:
            if not model.in_bounds(p) or (not standalone and (p[0]//48,p[2]//48) not in cells):raise ValueError('Detail exceeds approved footprint')
            if p in protected and value!=model.get(p):raise ValueError(f'Detail touches protected doorway/route/node: {p}')
            model.put(p,value)
            if operation['kind']=='move_region':
                if p in moved_walls and value not in AIR_NAMES:walls.add(p)
                else:walls.discard(p)
            elif value in AIR_NAMES or classification=='body':walls.discard(p)
            elif classification=='wall' or p in moved_walls:walls.add(p)
        summary.append(dict(label=operation['label'],kind=operation['kind'],candidate_writes=len(edits)))
        if weathering_report is not None:summary[-1]['weathering']=weathering_report
        if pattern_report is not None:summary[-1]['pattern']=pattern_report
        if floor_report is not None:summary[-1]['auto_floor']=floor_report
        if modelling_report is not None:summary[-1]['modelling']=modelling_report
    from nbt_change_policy import enforce_changes,change_sets
    budget=config.get('max_changed_blocks',4096)
    difference=enforce_changes(original,model.blocks,old_walls,walls,protected=protected,maximum=budget,require_change=True)
    geometry_changed,layers_changed=change_sets(original,model.blocks,old_walls,walls)
    if working:
        working.patch_candidate(model,walls)
        working.context['cameras']=config['cameras']
        checks=working.validate()['whole_model']
    else:
        checks=validate(model,config)
    _current_review(review,review_hash)
    out.mkdir(parents=True)
    write_json(out/'refinement.json',dict(state='writing',source=record['source'],source_geometry_sha256=record['source_geometry_sha256'],runtime_verified=False))
    diff=[dict(pos=list(p),before=original.get(p,AIR),after=model.get(p)) for p in sorted(geometry_changed)]
    write_json(out/'changes.json',dict(changes=diff,wall_membership_changed=[list(p) for p in sorted(layers_changed)],
               wall_changes=[dict(pos=list(p),before_wall=p in old_walls and p in original,after_wall=p in walls and p in model.blocks) for p in sorted(layers_changed)],**difference))
    write_json(out/'plan.json',plan);write_json(out/'validation.json',checks)
    previews=[_render(model,c,out/f'refined_{i:02}.png') for i,c in enumerate(config['cameras'])]
    from PIL import Image,ImageDraw
    comparison=Image.new('RGB',(1280,438*len(previews)),'#14202b');draw=ImageDraw.Draw(comparison)
    for i,(before,after) in enumerate(zip(record['thumbnails'],previews)):
        draw.text((12,i*438+10),'BEFORE | '+before['role'],fill='white')
        draw.text((652,i*438+10),'AFTER | '+after['role'],fill='white')
        with Image.open(review/before['file']) as img:comparison.paste(img,(0,i*438+32))
        with Image.open(out/after['file']) as img:comparison.paste(img,(640,i*438+32))
    comparison.save(out/'comparison.png')
    _current_review(review,review_hash)
    if approval_path.read_bytes()!=approval_bytes:
        raise ValueError('Approval changed while refining')
    approval_hash=hashlib.sha256(approval_bytes).hexdigest()
    if working:
        master=Path(working.save_draft(task_session=task_session,actor=actor,attachments={'refinement.json':dict(
            source_sha256=record['source_sha256'],approval_receipt_sha256=approval_hash,
            plan=plan)})['source'])
    else:
        from contextlib import nullcontext
        from nbt_agent_tasks import publication
        from nbt_snbt import save_snbt
        from nbt_web_paths import project_paths
        source=Path(record['source'])
        baseline=read_master(source)[0] if source.suffix.lower()=='.snbt' else None
        master=out/'master/model.snbt'
        workspace=next((parent.parent for parent in source.parents if parent.name=='nbt_models'),None)
        if task_session and workspace is None:raise ValueError('任务制作源必须位于工作区 nbt_models 内')
        guard=publication(workspace,project_paths(source)['workdir'],source,task_session,actor) if workspace else nullcontext(lambda: None)
        with guard as check_lease:
            producer=check_lease()
            save_snbt(master,model,walls,palette=getattr(baseline,'_snbt_palette',None),extras=getattr(baseline,'_snbt_extras',None))
            write_json(out/'coordinates.json',config)
            if producer:
                from nbt_prompts import relative
                write_json(out/'agent-publication.json',dict(publication=producer,source=relative(workspace,master),binding=source_binding(master)))
    final=dict(source_geometry_sha256=record['source_geometry_sha256'],refined_geometry_sha256=model.fingerprint(),
               approval_receipt_sha256=approval_hash,operations=summary,**difference,
               protected_cells=len(protected),validation_passed=True,master=str(master),
               delivery_nbt_files=0,runtime_templates=[],previews=previews,
               original_source_unchanged=digest(record['source'])==record['source_sha256'],
               state='refined_pending_agent_visual_review',runtime_verified=False,
               workflow='whole_uncut_source_restored_then_global_details_then_save_snbt',
               shared_style_note=plan['style_note'],
               comparison=dict(file='comparison.png',sha256=digest(out/'comparison.png')),
               next_action='Inspect actual refined images; keep original draft and report limitations.')
    write_json(out/'refinement.json',final);return final


def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    a=sub.add_parser('prepare');a.add_argument('--source',type=Path,required=True);a.add_argument('--config',type=Path,required=True);a.add_argument('--review',type=Path,required=True)
    a=sub.add_parser('approve');a.add_argument('--review',type=Path,required=True);a.add_argument('--user-message',required=True);a.add_argument('--user-reviewed-thumbnails',action='store_true',required=True)
    a=sub.add_parser('apply');a.add_argument('--review',type=Path,required=True);a.add_argument('--plan',type=Path,required=True);a.add_argument('--output',type=Path,required=True);a.add_argument('--task-session')
    args=p.parse_args()
    if args.command=='prepare':result=prepare(args.source,json.loads(args.config.read_text(encoding='utf8')),args.review)
    elif args.command=='approve':result=record_user_approval(args.review,args.user_message,args.user_reviewed_thumbnails)
    else:result=refine(args.review,json.loads(args.plan.read_text(encoding='utf8')),args.output,task_session=args.task_session)
    print(json.dumps({k:v for k,v in result.items() if k in ('stage','state','master','changed_blocks','wall_membership_changes','changed_positions','delivery_nbt_files','instruction')},ensure_ascii=False))


if __name__=='__main__':main()
