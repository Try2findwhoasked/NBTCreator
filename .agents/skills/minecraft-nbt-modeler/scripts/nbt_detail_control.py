"""Data-only backend for the local detail controller. No inferred human approval."""
import argparse
import gzip
import re
import os
from collections import Counter
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys

from nbt_refine import read_master, prepare, refine, validate, protections, _current_review, operation_candidates
from nbt_model import state
from nbt_request_paths import read_request, metadata_path
from nbt_web_paths import project_paths
from nbt_collision import collision_cells

ROOT = Path(__file__).resolve().parents[1]


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf8')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


def nearby(source, names):
    for parent in list(Path(source).resolve().parents)[:4]:
        for name in names:
            candidate = parent/name
            if candidate.is_file(): return str(candidate)
    return ''


def catalog(workspace, cache_path=None, include_bugged=False, index_only=False):
    selected=Path(workspace).resolve();workspace=selected
    for candidate in [selected,*selected.parents]:
        if candidate.name.lower()=='nbt_models':workspace=candidate.parent
    root=workspace/'nbt_models'
    marker=root/'_migration/active.json'
    if marker.is_file() and read_json(marker).get('status')!='complete':return dict(models=[],skipped=0,scanned=0,cache_hits=0,migration_in_progress=True)
    files = []
    for directory, dirs, names in os.walk(root):
        quarantined=include_bugged and 'bugged' in Path(directory).relative_to(root).parts
        refinement=Path(directory)/'refinement.json'
        if refinement.is_file():
            try:
                state=read_json(refinement).get('state')
                incomplete=state=='writing' or (not quarantined and state in ('failed','cancelled'))
            except (OSError,ValueError):incomplete=not quarantined
            if incomplete:dirs[:]=[];continue
        conversion=Path(directory)/'conversion.json'
        if conversion.is_file():
            try:ready=read_json(conversion).get('status')=='complete'
            except (OSError,ValueError):ready=False
            if not ready and not quarantined:dirs[:]=[];continue
        dirs[:] = [name for name in dirs if not (name.startswith(('.', 'synthetic', 'test_')) or
                    any(word in name.lower() for word in ('validation', 'fixture', 'cache', 'control_web', 'regression')) or
                    (name=='bugged' and not include_bugged) or name in {'_migration','_workspaces','_tests','world', 'worlds', 'saves', 'node_modules', 'previews', 'jobs', 'review','delivery','layers'})]
        files.extend(Path(directory)/name for name in names if (name.lower().endswith('.json.gz') and 'master' in name.lower()) or name.lower().endswith('.nbt'))
    files.sort(key=lambda p: (p.suffix.lower()=='.nbt',-p.stat().st_mtime_ns,str(p)))
    cache_path = Path(cache_path) if cache_path else root/('_workspaces/catalog_metadata_index.json' if index_only else '_workspaces/catalog_metadata_projects.json' if include_bugged else '_workspaces/catalog_metadata.json')
    try: cache = read_json(cache_path)
    except (OSError, ValueError):
        try:cache=read_json(root/'_workspaces/catalog_metadata.json') if include_bugged else {}
        except (OSError,ValueError):cache={}
    next_cache = {}; cache_hits = 0
    models, seen, skipped = [], set(), 0
    descriptions={};description_paths={};errors=[]
    def description_near(source):
        for parent in list(source.parents)[:4]:
            if parent not in description_paths:
                candidate=parent/'room_description.json';description_paths[parent]=candidate if candidate.is_file() else None
            if description_paths[parent]:return description_paths[parent]
        return None
    for p in files:
        bugged='bugged' in p.relative_to(root).parts
        try:
            descriptor=description_near(p)
            if descriptor:
                if descriptor not in descriptions:descriptions[descriptor]=read_json(descriptor)
                declaration=descriptions[descriptor]
                if declaration.get('audit',{}).get('compliant') is False and not bugged:continue
                declared_master=declaration.get('master')
                if declared_master and not bugged and metadata_path(descriptor,declared_master).is_file() and metadata_path(descriptor,declared_master)!=p.resolve():continue
            stat=p.stat(); stamp=[stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns]
            entry=cache.get(str(p))
            if entry and entry.get('stamp')==stamp:
                data=entry['metadata'];cache_hits+=1
            elif bugged:
                # Quarantine can contain thousands of old NBT exports. Index it
                # without constructing every volume; inspect on explicit open.
                with p.open('rb') as stream:
                    if stream.read(2)!=b'\x1f\x8b':raise ValueError('文件不是有效的 gzip NBT / 主模型，无法读取')
                data=dict(geometry_sha256=None,size=declaration.get('size') if descriptor else None,unverified=True)
            elif index_only:
                with p.open('rb') as stream:
                    if stream.read(2)!=b'\x1f\x8b':raise ValueError('文件不是有效的 gzip NBT / 主模型，无法读取')
                data=dict(geometry_sha256=declaration.get('geometry_sha256') if descriptor else None,size=declaration.get('size') if descriptor else None,unverified=True)
            elif descriptor and declaration.get('audit',{}).get('compliant') is True and declaration.get('master_file_sha256') and declaration.get('geometry_sha256') and digest(p)==declaration['master_file_sha256']:
                data={'geometry_sha256':declaration['geometry_sha256'], 'size':declaration.get('size')};cache_hits+=1
            elif p.suffix.lower()=='.nbt':
                loaded,_=read_master(p)
                data={'geometry_sha256':loaded.fingerprint(),'size':list(loaded.size)}
            else:
                with gzip.open(p, 'rt', encoding='utf8') as stream: raw = json.load(stream)
                data = {'geometry_sha256':raw['geometry_sha256'], 'size':raw['size']} if isinstance(raw,dict) and all(key in raw for key in ('size','blocks','geometry_sha256')) else None
            next_cache[str(p)]={'stamp':stamp,'metadata':data}
            if not data: raise ValueError('缺少完整主模型的尺寸、方块或几何哈希')
            relative = p.relative_to(root)
            parts = relative.parts
            building_index = next((i for i, part in enumerate(parts[:-1]) if re.match(r'^(?:[rR]\d{2,3}|[sSlL]\d{2}|\d{2}|cross_\d+|t_\d+)(?:_|$)', part)), None)
            if building_index is not None:
                group = '/'.join(parts[:building_index+1]); name = parts[building_index]
                batch = '/'.join(parts[:building_index])
            else:
                parent_parts = list(relative.parts[:-1])
                if 'versions' in parent_parts: parent_parts = parent_parts[:parent_parts.index('versions')]
                while parent_parts and (parent_parts[-1] in {'parts', 'runtime', 'master', 'masters', 'revision', 'final', 'refined'} or
                                        re.match(r'^(?:v\d+|refined_\d+|refined_v\d+|detail_v\d+)$', parent_parts[-1]) or parent_parts[-1].endswith('_review')):
                    parent_parts.pop()
                group = '/'.join(parent_parts) or '.'; name = parent_parts[-1] if parent_parts else p.name
                batch = '/'.join(parent_parts[:-1])
            description_file=descriptor
            room_description={}
            if description_file:
                try:room_description=descriptions[description_file]
                except (ValueError,OSError):room_description={}
                if room_description.get('audit',{}).get('compliant') is False and not bugged:continue
                recorded_master=room_description.get('master')
                if recorded_master and not bugged and metadata_path(description_file,recorded_master)!=p.resolve() and metadata_path(description_file,recorded_master).is_file():continue
                name=room_description.get('name_zh') or name
                parts=description_file.parent.relative_to(root).parts
                if len(parts)>=3 and parts[0] in {'single','long','square','l_shape','t_shape','cross','standalone','irregular'}:
                    group='/'.join(parts[:2])
                elif 'versions' in parts:group='/'.join(parts[:parts.index('versions')])
                else:group=str(description_file.parent.parent.relative_to(root)) if description_file.parent.name.startswith(('版本_','v_','detail_v','refined_v')) or re.fullmatch(r'v\d+',description_file.parent.name) else str(description_file.parent.relative_to(root))
                batch=room_description.get('shape_zh') or batch
            version_dir=description_file.parent if description_file else p.parent
            if not description_file:
                while version_dir!=root and version_dir.name in {'master','masters','runtime','parts'}:version_dir=version_dir.parent
            key = (group, str(version_dir), data['geometry_sha256'] or str(p))
            if key in seen: continue
            seen.add(key)
            version = ' / '.join(part for part in parts[(building_index+1 if building_index is not None else len(parts)-2):-1]
                                 if part not in {'runtime', 'parts', 'master', 'masters'})
            if description_file:
                canonical_parts=description_file.parent.relative_to(root).parts
                if len(canonical_parts)>=3 and canonical_parts[0] in {'single','long','square','l_shape','t_shape','cross','standalone','irregular'}:
                    version='/'.join(canonical_parts[2:])
            models.append(dict(source=str(p.resolve()), label=room_description.get('display_name') or str(relative), name=name, name_zh=room_description.get('name_zh'), shape=room_description.get('shape'), shape_zh=room_description.get('shape_zh'), group=group, batch=batch,
                               version=room_description.get('version_name') or version or '原稿', intermediate=p.name.startswith(('pre_', 'sealed_', 'source.')), geometry_sha256=data['geometry_sha256'],
                               context=str(description_file.parent/room_description['context_file']) if room_description.get('context_file') else nearby(p, ('coordinates.json', 'config.json', 'context.json')),
                               cameras=nearby(p, ('cameras.json',)), size=room_description.get('size') or data.get('size'),
                               cells=room_description.get('cells'), description_zh=room_description.get('description_zh',''),
                               modified_ns=str(stat.st_mtime_ns), file_size=stat.st_size, relative_path=str(relative),bugged=bugged,unreadable=False,unverified=bool(data.get('unverified'))))
        except (OSError, ValueError, TypeError, KeyError,AssertionError,EOFError) as error:
            skipped+=1
            if len(errors)<10:errors.append(dict(file=str(p.relative_to(root)),reason=str(error) or '不满足当前完整结构格式要求（版本、显式空气、实体或尺寸）'))
            if (bugged and include_bugged) or index_only:
                relative=p.relative_to(root)
                models.append(dict(source=str(p.resolve()),label=str(relative),name=p.parent.name,group=str(relative.parent),version=p.name,
                                   relative_path=str(relative),bugged=bugged,unreadable=True,error=str(error) or '模型格式不完整',size=None,geometry_sha256=None,context='',cameras='',intermediate=False))
    shapes={'single':'单格','long':'长条','square':'方形','l_shape':'L 形','t_shape':'T 形','cross':'十字','standalone':'独立结构','irregular':'不规则','bugged':'bugged（待修复）'}
    for item in models:
        parts=Path(item['relative_path']).parts
        shape_index=next((i for i,part in enumerate(parts[:-1]) if part in shapes),None)
        item['project_key']='/'.join(parts[:shape_index]) if shape_index is not None else ''
        item['project_name']=item['project_key'] or workspace.name
        declared_shape=item.get('shape')
        item['shape_group']='bugged' if item['bugged'] else parts[shape_index] if shape_index is not None else declared_shape if isinstance(declared_shape,str) and declared_shape else 'unclassified'
        item['shape_group_zh']=shapes.get(item['shape_group'],'未分类')
        if not isinstance(item.get('size'),(list,tuple)) or len(item['size'])!=3 or any(type(v) is not int or v<=0 for v in item['size']):item['size']=None
        item['object_key']=item['group'].replace('\\','/')
        item['object_name']=item.get('name_zh') or item['name']
        if not item.get('unreadable'):
            declared=descriptions.get(description_near(Path(item['source'])),{})
            phase=declared.get('workflow_stage',declared.get('status'))
            if phase in {'unrefined','refined','finalized','discarded'} and declared.get('master') and metadata_path(description_near(Path(item['source'])),declared['master'])==Path(item['source']):item['stage']=phase
        item['is_delivery']='_deliveries' in parts or 'delivery' in parts
        if (shape_index is not None and len(parts)==shape_index+2) or len(parts)==1:
            item['object_key']='/'.join(parts)
            item['object_name']=item.get('name_zh') or Path(parts[-1]).stem.removesuffix('.json').removesuffix('.master')
        if isinstance(item.get('name_zh'),str) and item['name_zh'].strip():
            # A delivery and its authoring version belong to one named object.
            item['object_key']=json.dumps([item['project_key'],item['shape_group'],item['name_zh'].strip()],ensure_ascii=False,separators=(',',':'))
    cache_path.parent.mkdir(parents=True,exist_ok=True)
    import uuid
    temporary=cache_path.with_name(cache_path.name+'.'+uuid.uuid4().hex+'.tmp')
    write_json(temporary,next_cache);os.replace(temporary,cache_path)
    return dict(models=models, skipped=skipped, scanned=len(files), cache_hits=cache_hits,workspace=str(workspace),scan_root=str(root),normalized_from=str(selected) if selected!=workspace else None,errors=errors)


def preview_images(source, geometry_hash, image_limit=8):
    """Only existing images bound to this geometry; never render or modify an asset."""
    source = Path(source).resolve()
    images, image_names = [], set()
    for parent in list(source.parents)[:3]:
        image_roots=[path for path in parent.glob('previews*') if path.is_dir()]
        if image_roots or list(parent.glob('*.png')):
            candidates=list(parent.glob('*.png'))
            for image_root in image_roots:candidates.extend(image_root.rglob('*.png'))
            candidates = sorted(set(candidates), key=lambda p: p.stat().st_mtime_ns, reverse=True)
            for candidate in candidates:
                metadata = candidate.with_suffix('.json')
                if metadata.is_file():
                    try:
                        if (read_json(metadata).get('geometry_sha256') == geometry_hash or read_json(metadata).get('source_geometry_sha256')==geometry_hash) and candidate.name not in image_names:
                            images.append(candidate); image_names.add(candidate.name)
                    except (ValueError, OSError): pass
                if len(images) >= image_limit: break
            if images: break
    return list(map(str, images))


def inspect_source(source, image_limit=8):
    source = Path(source).resolve(); model, walls = read_master(source)
    geometry_hash = model.fingerprint()
    counts = Counter(model.blocks.values())
    from nbt_collision import bounded_obstacle, ENVELOPE_VERSION
    unknown = [dict(state=value, count=count, reason=collision_cells(value)[1])
               for value, count in sorted(counts.items()) if collision_cells(value)[1] and not bounded_obstacle(value)]
    conservative = [dict(state=value,count=count) for value,count in sorted(counts.items()) if bounded_obstacle(value)]
    context = nearby(source, ('coordinates.json', 'config.json', 'context.json'))
    cameras = nearby(source, ('cameras.json',))
    images = preview_images(source, geometry_hash, image_limit)
    sx,sy,sz=model.size
    solid=[p for p,value in model.blocks.items() if value.split('[')[0] not in ('minecraft:air','minecraft:cave_air','minecraft:void_air')]
    projections=dict(top=dict(size=[sx,sz],cells=sorted({x+z*sx for x,y,z in solid})),front=dict(size=[sx,sy],cells=sorted({x+y*sx for x,y,z in solid})),side=dict(size=[sz,sy],cells=sorted({z+y*sz for x,y,z in solid})))
    try:
        data = read_json(context) if context else {}
        if not isinstance(data,dict):data={}
    except (OSError,ValueError):data={}
    readiness=context_readiness(model,context)
    return dict(source=str(source), source_sha256=digest(source), workdir=str(project_paths(source)['workdir']), version_dir=str(project_paths(source)['version']), geometry_sha256=model.fingerprint(),
                projections=projections,size=list(model.size), solid_blocks=len(model.blocks), wall_blocks=len(walls),
                context=context, cameras=cameras, images=images, unknown_shapes=unknown,
                conservative_obstacles=conservative,obstacle_envelope_version=ENVELOPE_VERSION if conservative else None,
                editing_ready=readiness['ready'],context_readiness=readiness,
                materials=[dict(state=value,count=count) for value,count in counts.most_common() if value.split('[')[0] not in ('minecraft:air','minecraft:cave_air','minecraft:void_air')],
                suggested_floor=data.get('floor_operation', {}), suggested_budget=data.get('max_changed_blocks', 4096),
                note='Controls describe a new pass from this baseline; existing details cannot be undone without an earlier baseline.')


def context_readiness(model, context):
    """Schema readiness only; never a seal, route or visual acceptance result."""
    from nbt_library import canonical_context
    missing=[];errors=[]
    if not context:return dict(ready=False,missing=['context'],errors=[],scope='schema_only')
    try:data=canonical_context(context)
    except (OSError,ValueError,TypeError) as error:return dict(ready=False,missing=[],errors=[str(error)],scope='schema_only')
    mode=data.get('mode','saodg')
    if mode not in ('saodg','standalone'):errors.append('mode 必须为 saodg 或 standalone')
    for key in ('start','targets','interior_probes'):
        if key not in data or not data[key]:missing.append(key)
    if 'start' not in missing and (not isinstance(data['start'],list) or len(data['start'])!=3 or any(type(v) not in (int,float) or not math.isfinite(v) for v in data['start'])):
        errors.append('start 需要实际玩家脚位XYZ')
    if 'targets' not in missing and not isinstance(data['targets'],(list,dict)):errors.append('targets 需要非空目标列表或命名字典')
    if 'interior_probes' not in missing and not isinstance(data['interior_probes'],list):errors.append('interior_probes 需要室内空气坐标列表')
    def xyz(value,voxel=False):
        return isinstance(value,(list,tuple)) and len(value)==3 and all(type(v) in ((int,) if voxel else (int,float)) and math.isfinite(v) for v in value)
    if isinstance(data.get('targets'),(list,dict)):
        values=data['targets'].values() if isinstance(data['targets'],dict) else data['targets']
        if any(not xyz(p) for p in values):errors.append('targets 每项需要实际玩家脚位XYZ')
    if isinstance(data.get('interior_probes'),list) and any(not xyz(p,True) or not model.in_bounds(p) for p in data['interior_probes']):
        errors.append('interior_probes 每项需要模型内的整数XYZ')
    if mode=='standalone':
        if 'openings' not in data:missing.append('openings')
        elif not isinstance(data['openings'],list):errors.append('openings 需要显式开口列表；无开口填空列表')
        if data.get('ports'):errors.append('独立建筑使用 openings，不混用SAODG ports')
    elif not data.get('cells') and not(model.size[0]==model.size[2]==48):missing.append('cells 或显式 mode=standalone')
    return dict(ready=not missing and not errors,mode=mode,missing=missing,errors=errors,scope='schema_only')


def thumbnails(request_path, cache):
    from PIL import Image
    cache=Path(cache);cache.mkdir(parents=True,exist_ok=True)
    result=[]
    for file in read_json(request_path):
        file=Path(file);fingerprint=digest(file);target=cache/(fingerprint+'.jpg')
        if not target.is_file():
            with Image.open(file) as image:
                image=image.convert('RGB');image.thumbnail((256,160))
                image.save(target,'JPEG',quality=75,optimize=True)
        result.append(dict(image=str(file),image_sha256=fingerprint,thumbnail=str(target),thumbnail_bytes=target.stat().st_size))
    return dict(images=result)


def default_settings():
    return dict(strength=100, seed=2718, style_note='', max_changed_blocks=4096,
        operations=[],structure=dict(enabled=False,mode='fill',state='stone_bricks',offset=[0,0,0],thickness=1,classification='body'),
        replace=dict(enabled=False,from_states=['stone_bricks'],state='andesite',scope='surface'),
        whole_region=True, lo=[0, 0, 0], hi=[47, 15, 47],
        pattern=dict(enabled=False, fraction=.15, mode='independent', scale=6, scope='surface',
                     from_states=['stone_bricks'], palette=[dict(state='stone_bricks', weight=70),
                     dict(state='cracked_stone_bricks', weight=20), dict(state='mossy_stone_bricks', weight=10)]),
        weathering=dict(enabled=False, from_states=['stone_bricks'], moss_fraction=.12, cracks_fraction=.06,
                        moss_state='mossy_stone_bricks', crack_state='cracked_stone_bricks',
                        patch_size=[12, 40], crack_length=[6, 18]),
        floor=dict(enabled=False, profile='worn', fraction=.04, slab_share=.85, patch_size=[2, 4],
                   pit_depth=1, route_margin=.5, exclude_boxes=[], slab_overrides={}))


def _fraction(value, label):
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError(f'{label} must be 0..1; overall strength must not make it exceed 100%')
    return value


def compile_plan(settings, size):
    if not isinstance(settings, dict) or set(settings)-set(default_settings()):
        raise ValueError('Unknown detail settings')
    strength = settings.get('strength', 100)
    if type(strength) not in (int, float) or not math.isfinite(strength) or not 0 <= strength <= 200:
        raise ValueError('Overall strength must be 0..200%')
    seed = settings.get('seed', 0)
    if type(seed) is not int: raise ValueError('seed must be an integer')
    note = settings.get('style_note', '')
    if not isinstance(note, str): raise ValueError('效果备注须为文字')
    note = note.strip() or '网页参数效果调整（依据方块搭配及比例设置）'
    budget = settings.get('max_changed_blocks', 4096)
    if type(budget) is not int or budget < 1: raise ValueError('Change budget must be positive')
    lo = [0, 0, 0] if settings.get('whole_region', True) else settings['lo']
    hi = [n-1 for n in size] if settings.get('whole_region', True) else settings['hi']
    if any(not isinstance(v, list) or len(v) != 3 or any(type(n) is not int for n in v) for v in (lo, hi)):
        raise ValueError('Region requires integer XYZ bounds')
    if any(lo[i] < 0 or hi[i] >= size[i] or lo[i] > hi[i] for i in range(3)):
        raise ValueError('Region exceeds baseline dimensions')
    operations = []
    structure=settings.get('structure',{})
    if not isinstance(structure,dict) or set(structure)-set(default_settings()['structure']):raise ValueError('结构工具字段无效')
    if type(structure.get('enabled',False)) is not bool:raise ValueError('结构工具开关无效')
    if structure.get('enabled'):
        if settings.get('whole_region',True):raise ValueError('结构编辑请先在“修改范围”中指定局部坐标，不能默认作用于整座建筑')
        mode=structure['mode'];target=state(structure['state']);classification=structure['classification']
        if classification not in ('body','wall'):raise ValueError('请选择主体或墙体归属')
        if mode not in ('fill','carve','hollow','move','floor','ceiling','walls','frame'):raise ValueError('结构编辑方式无效')
        kind={'fill':'box','carve':'box','hollow':'hollow_box','move':'move_region'}.get(mode,'box')
        op=dict(kind=kind,label='网页局部结构编辑：'+mode,classification=classification,lo=lo,hi=hi,state='minecraft:air' if mode=='carve' else target)
        if mode=='move':
            delta=structure['offset']
            if not isinstance(delta,list) or len(delta)!=3 or any(type(v) is not int for v in delta) or not any(delta):raise ValueError('移动偏移须为三个整数，且不能全为0')
            if any(lo[i]+delta[i]<0 or hi[i]+delta[i]>=size[i] for i in range(3)):raise ValueError('移动后的区域超出建筑边界')
            op.update(offset=delta,classification='inherit')
        if mode=='hollow':
            thickness=structure['thickness']
            if type(thickness) is not int or thickness<1 or any(hi[i]-lo[i]+1<=2*thickness for i in range(3)):raise ValueError('空心外壳尺寸须大于两倍厚度')
            op['thickness']=thickness
        if mode in ('floor','ceiling','walls','frame'):
            thickness=structure['thickness']
            if type(thickness) is not int or thickness<1 or any(hi[i]-lo[i]+1<2*thickness for i in range(3)):
                raise ValueError('铺面与骨架选区每轴尺寸须至少为厚度的两倍')
            # Partition each axis into disjoint boundary/interior spans, avoiding
            # duplicate edits at corners and retaining everything outside the tool.
            from itertools import product
            spans=[]
            for axis in range(3):
                a,b=lo[axis],hi[axis]
                spans.append([(a,a+thickness-1,True),(a+thickness,b-thickness,False),(b-thickness+1,b,True)])
            for cells in product(*spans):
                if any(a>b for a,b,_ in cells):continue
                edges=[cell[2] for cell in cells]
                selected=(mode=='floor' and cells[1][0]==lo[1] or
                          mode=='ceiling' and cells[1][1]==hi[1] or
                          mode=='walls' and (edges[0] or edges[2]) or
                          mode=='frame' and sum(edges)>=2)
                if selected:
                    operations.append(dict(op,lo=[c[0] for c in cells],hi=[c[1] for c in cells]))
        else:
            operations.append(op)
    factor = strength/100
    for key in ('replace', 'pattern', 'weathering', 'floor'):
        module = settings.get(key, {})
        if not isinstance(module, dict) or set(module)-set(default_settings()[key]): raise ValueError(f'Unknown {key} fields')
        if type(module.get('enabled', False)) is not bool: raise ValueError('Enabled switches must be booleans')
        if not module.get('enabled'): continue
        if key == 'replace':
            if not isinstance(module['from_states'],list) or not module['from_states']: raise ValueError('精确换块需要指定原方块')
            for value in module['from_states']: state(value)
            target=state(module['state'])
            if target.split('[')[0] in ('minecraft:air','minecraft:cave_air','minecraft:void_air'): raise ValueError('换块目标请选择实体方块')
            if module['scope'] not in ('volume','surface'): raise ValueError('替换范围无效')
            operations.append(dict(kind='pattern',label='面板：精确换块',classification='inherit',lo=lo,hi=hi,
                from_states=module['from_states'],palette=[dict(state=target,weight=1)],fraction=1,
                seed=seed,mode='independent',scale=1,scope=module['scope']))
        elif key == 'pattern':
            fraction = _fraction(_fraction(module['fraction'], 'pattern fraction')*factor, 'scaled pattern fraction')
            if module['mode'] not in ('independent', 'clustered') or module['scope'] not in ('volume', 'surface'):
                raise ValueError('Invalid pattern mode/scope')
            palette = module['palette']
            if not isinstance(palette, list) or not palette: raise ValueError('Add palette rows')
            weights = []
            for entry in palette:
                if not isinstance(entry, dict) or set(entry) != {'state', 'weight'}: raise ValueError('Palette rows require state and weight')
                value = state(entry['state']); weight = entry['weight']
                if value.split('[')[0] in ('minecraft:air', 'minecraft:cave_air', 'minecraft:void_air'): raise ValueError('Pattern targets cannot be air')
                if type(weight) not in (int, float) or not math.isfinite(weight) or weight < 0: raise ValueError('Invalid material weight')
                weights.append(weight)
            if not any(weights): raise ValueError('At least one material weight must be positive')
            if type(module['scale']) not in (int, float) or not math.isfinite(module['scale']) or module['scale'] < 1: raise ValueError('Noise scale must be >=1')
            for value in module['from_states']: state(value)
            if fraction > 0:
                operations.append(dict(kind='pattern', label='面板：受控混材', classification='inherit',
                    lo=lo, hi=hi, from_states=module['from_states'], palette=palette, fraction=fraction,
                    seed=seed, mode=module['mode'], scale=module['scale'], scope=module['scope']))
        elif key == 'weathering':
            moss = _fraction(_fraction(module['moss_fraction'], 'moss')*factor, 'scaled moss')
            cracks = _fraction(_fraction(module['cracks_fraction'], 'cracks')*factor, 'scaled cracks')
            for value in [*module['from_states'], module['moss_state'], module['crack_state']]: state(value)
            for interval in (module['patch_size'], module['crack_length']):
                if len(interval) != 2 or any(type(n) is not int for n in interval) or not 2 <= interval[0] <= interval[1] <= 512: raise ValueError('Invalid patch/length range')
            if moss or cracks:
                operations.append(dict(kind='weathering', label='面板：苔痕与连续裂纹', classification='inherit',
                    lo=lo, hi=hi, from_states=module['from_states'], seed=seed,
                    moss=dict(fraction=moss, patch_size=module['patch_size'], state=module['moss_state']),
                    cracks=dict(fraction=cracks, length=module['crack_length'], state=module['crack_state']), floor=dict(fraction=0)))
        else:
            fraction = _fraction(_fraction(module['fraction'], 'floor')*factor, 'scaled floor')
            _fraction(module['slab_share'], 'slab_share')
            if module['profile'] not in ('maintained', 'worn', 'ruined', 'cavern'): raise ValueError('Unknown floor profile')
            if type(module['pit_depth']) is not int or not 1 <= module['pit_depth'] <= 8: raise ValueError('Pit depth must be 1..8')
            if len(module['patch_size']) != 2 or any(type(n) is not int for n in module['patch_size']) or not 2 <= module['patch_size'][0] <= module['patch_size'][1] <= 512: raise ValueError('Invalid floor patch range')
            if fraction:
                op = dict(kind='auto_floor', label='面板：自动地面凹陷与坑洞', classification='body',
                    style_note=note, seed=seed, profile=module['profile'], fraction=fraction,
                    slab_share=module['slab_share'], patch_size=module['patch_size'], pit_depth=module['pit_depth'],
                    route_margin=module['route_margin'], exclude_boxes=module['exclude_boxes'], slab_overrides=module['slab_overrides'])
                if not settings.get('whole_region', True): op['include_boxes'] = [dict(lo=lo, hi=hi)]
                operations.append(op)
    extra=settings.get('operations',[])
    if not isinstance(extra,list) or len(extra)>128:raise ValueError('建模工具序列须为最多128项的数组')
    from nbt_capabilities import capabilities
    supported=set(capabilities()['tools'])
    for op in extra:
        if not isinstance(op,dict) or op.get('kind') not in supported or not isinstance(op.get('label'),str) or not op['label'].strip():raise ValueError('建模工具种类或说明无效')
        if type(op.get('enabled',True)) is not bool:raise ValueError('工具步骤的 enabled 开关须为布尔值')
        if op.get('classification','body') not in ('body','wall','inherit'):raise ValueError('工具归属无效')
        if not op.get('enabled',True):continue
        if op['kind']=='auto_floor':
            if op.get('classification','body')!='body':raise ValueError('自动地面归主体层')
        elif op['kind']=='beam':
            for key in ('start','end'):
                v=op.get(key)
                if not isinstance(v,list) or len(v)!=3 or any(type(n) is not int or n<0 or n>=size[i] for i,n in enumerate(v)):raise ValueError('梁端点超出模型')
        else:
            a,b=op.get('lo'),op.get('hi')
            if any(not isinstance(v,list) or len(v)!=3 or any(type(n) is not int for n in v) for v in (a,b)) or any(a[i]<0 or a[i]>b[i] or b[i]>=size[i] for i in range(3)):raise ValueError('工具选区超出模型')
        operations.append(json.loads(json.dumps(op)))
    return dict(style_note=note, operations=operations)


def normalize_context(model, context_path, camera_path, settings):
    data = read_json(context_path)
    from nbt_library import canonical_context
    data = canonical_context(context_path)
    keys = ('mode', 'openings', 'allow_empty_wall_mask', 'cells', 'door_y', 'ports', 'start', 'targets', 'interior_probes', 'protected_paths',
            'protected_boxes', 'route_legs', 'cameras', 'wall_positions')
    config = {key: data[key] for key in keys if key in data}
    if config.get('mode','saodg')!='standalone':
        if 'cells' not in config and model.size[0] == model.size[2] == 48: config['cells'] = [[0, 0]]
        config.setdefault('ports', []); config.setdefault('door_y', 2)
    config['max_changed_blocks'] = settings.get('max_changed_blocks', 4096)
    for key in ('start', 'targets', 'interior_probes'):
        if key not in config or not config[key]: raise ValueError(f'Context is missing non-empty {key}; choose coordinates/config JSON')
    raw_cameras = read_json(camera_path) if camera_path else config.get('cameras', [])
    if not raw_cameras:
        start = config['start']; targets = config['targets']
        points = list(targets.values()) if isinstance(targets, dict) else targets
        target = next((p for p in points if p != start), [start[0]+3, start[1], start[2]])
        raw_cameras = [dict(role='whole', eye=[model.size[0]+10, model.size[1]+8, model.size[2]+10],
                           target=[n/2 for n in model.size], cuts=[dict(axis='y', position=max(2, model.size[1]-3), removed_side='above')]),
                       dict(role='entry', eye=[start[0], start[1]+1.62, start[2]], target=[target[0], target[1]+1, target[2]])]
    whole = next((c for c in raw_cameras if c.get('id') == 'overview' or c.get('role') == 'whole'), raw_cameras[0])
    entry = next((c for c in raw_cameras if c.get('id') == 'entry' or c.get('role') == 'entry'), None)
    if entry is None: raise ValueError('Camera list must include id=entry or role=entry')
    selected = [(whole, 'whole'), (entry, 'entry')]
    selected.extend((c, 'detail') for c in raw_cameras if c is not whole and c is not entry)
    config['cameras'] = [{k: c[k] for k in ('eye', 'target', 'cuts', 'fov') if k in c} | {'role': role}
                         for c, role in selected[:6]]
    return config


def reserve_output(output):
    output = Path(output).resolve()
    if output == ROOT or ROOT in output.parents: raise ValueError('Do not save jobs inside the skill installation')
    if output.exists(): raise FileExistsError('Use a new job output directory')
    output.mkdir(parents=True)
    return output


def export_plan(request, output):
    source = Path(request['source']).resolve(); model, walls = read_master(source)
    if request.get('source_sha256') and request['source_sha256'] != digest(source):
        raise ValueError('Baseline changed since it was displayed; reload the model before exporting a plan')
    settings = request['settings']; plan = compile_plan(settings, model.size)
    config = normalize_context(model, request['context'], request.get('cameras', ''), settings)
    output = reserve_output(output)
    baseline_hash = digest(source)
    bundle = dict(source=str(source), source_sha256=baseline_hash, geometry_sha256=model.fingerprint(),
                  settings_sha256=canonical(settings), context=config, plan_sha256=canonical(plan), settings=settings)
    write_json(output/'plan.json', plan); write_json(output/'bundle.json', bundle); write_json(output/'settings.json', request)
    estimates, warning, warning_detail = [], '', ''
    try:
        validate(model, config)
        from nbt_assembly import Volume
        from nbt_patterns import pattern_plan
        from nbt_weathering import weathering_plan
        from nbt_floors import auto_floor_plan
        virtual = Volume(model.size); virtual.blocks = dict(model.blocks)
        protected = protections(virtual, config)
        write_owners={};virtual_walls=set(walls)
        for operation in plan['operations']:
            if operation['kind'] == 'pattern': edits, report = pattern_plan(virtual, operation, protected)
            elif operation['kind'] == 'weathering': edits, report = weathering_plan(virtual, operation, protected)
            elif operation['kind']=='auto_floor': edits, report = auto_floor_plan(virtual, operation, config, protected)
            else: edits,report=operation_candidates(virtual,operation,protected),{}
            from nbt_change_policy import enforce_overwrite, clip_protected
            edits=clip_protected(operation,edits,protected)
            enforce_overwrite(virtual,virtual_walls,operation,edits,write_owners)
            conflicts=[p for p,value in edits if p in protected and virtual.get(p)!=value]
            if conflicts:raise ValueError(f'步骤“{operation.get("label",operation["kind"])}”触及保护区：{conflicts[:8]}。请移动构件或缩小范围；允许覆盖不会取消保护。')
            estimates.append(dict(kind=operation['kind'], label=operation['label'], writes=len(edits), report=report))
            for p, value in edits:
                virtual.put(p, value)
                if value in ('minecraft:air','minecraft:cave_air','minecraft:void_air') or operation.get('classification')=='body':virtual_walls.discard(p)
                elif operation.get('classification')=='wall':virtual_walls.add(p)
    except (ValueError, AssertionError, KeyError) as error:
        warning_detail = str(error)
        from nbt_collision import bounded_obstacle
        unsupported = [value for value in sorted(set(model.blocks.values())) if collision_cells(value)[1] and not bounded_obstacle(value)]
        warning = (f'源模型含 {len(unsupported)} 类未支持的碰撞形状（例如 {unsupported[0]}）。已导出参数计划；几何估算与实际应用仍需通过核验。'
                   if unsupported else warning_detail)
    if digest(source) != baseline_hash: raise ValueError('Source changed while planning')
    summary = dict(status='planned_unverified' if warning else 'planned', operations=len(plan['operations']),
                   warning=warning, warning_detail=warning_detail, estimates=estimates, source_unchanged=True,
                   note='Candidate calculations only. No revised model, approval or production file was written.')
    write_json(output/'estimates.json', summary)
    return dict(status=summary['status'], operations=summary['operations'], warning=warning,
                warning_detail=warning_detail,
                estimates=[dict(kind=e['kind'], writes=e['writes']) for e in estimates],
                plan=str(output/'plan.json'), bundle=str(output/'bundle.json'), output=str(output))


def simulate_plan(model, walls, plan, config):
    """The shared data-only candidate engine for model edits and new assets."""
    from nbt_assembly import Volume
    from nbt_patterns import pattern_plan
    from nbt_weathering import weathering_plan
    from nbt_floors import auto_floor_plan
    walls=set(walls);source_walls=set(walls)
    virtual=Volume(model.size);virtual.blocks=dict(model.blocks);protected=protections(virtual,config)
    write_owners={}
    for operation in plan['operations']:
        from nbt_operation_scope import scoped_operation,enforce_scope
        operation,bounds=scoped_operation(operation,model.size)
        if operation['kind']=='pattern': edits,_=pattern_plan(virtual,operation,protected)
        elif operation['kind']=='weathering': edits,_=weathering_plan(virtual,operation,protected)
        elif operation['kind']=='auto_floor': edits,_=auto_floor_plan(virtual,operation,config,protected)
        else: edits=operation_candidates(virtual,operation,protected)
        from nbt_change_policy import enforce_overwrite, clip_protected
        operation=enforce_scope(bounds,operation,edits)
        edits=clip_protected(operation,edits,protected)
        enforce_overwrite(virtual,walls,operation,edits,write_owners)
        outside=[p for p,value in edits if not virtual.in_bounds(p)]
        if outside:raise ValueError(f'步骤“{operation.get("label",operation["kind"])}”超出建筑边界：{outside[:8]}，建筑尺寸为{virtual.size}。请调整构件位置。')
        conflicts=[p for p,value in edits if p in protected and virtual.get(p)!=value]
        if conflicts:
            from nbt_protection_view import ProtectionConflict
            raise ProtectionConflict(operation.get('label',operation['kind']),conflicts)
        moved_walls={tuple(p[i]+operation['offset'][i] for i in range(3)) for p in walls if all(operation['lo'][i]<=p[i]<=operation['hi'][i] for i in range(3))} if operation['kind']=='move_region' else set()
        for position,value in edits:
            virtual.put(position,value)
            if operation['kind']=='move_region':
                if position in moved_walls and value.split('[')[0] not in ('minecraft:air','minecraft:cave_air','minecraft:void_air'):walls.add(position)
                else:walls.discard(position)
            elif value.split('[')[0] in ('minecraft:air','minecraft:cave_air','minecraft:void_air') or operation.get('classification')=='body':walls.discard(position)
            elif operation.get('classification')=='wall' or position in moved_walls:walls.add(position)
    from nbt_change_policy import enforce_changes
    difference=enforce_changes(model.blocks,virtual.blocks,source_walls,walls,protected,maximum=config.get('max_changed_blocks'))
    return virtual,walls,difference


def preview_effect(request, output):
    # User-requested visual experiment only: no master/NBT, approval or delivery.
    from nbt_assembly import Volume
    from nbt_patterns import pattern_plan
    from nbt_weathering import weathering_plan
    from nbt_floors import auto_floor_plan
    from nbt_registry import effective, normalize, registry
    source=Path(request['source']).resolve(); baseline=digest(source)
    if request.get('source_sha256') and request['source_sha256']!=baseline: raise ValueError('原建筑已变化，请重新打开')
    model,walls=read_master(source);settings=request['settings'];plan=compile_plan(settings,model.size)
    config=normalize_context(model,request['context'],request.get('cameras',''),settings)
    if 'wall_positions' in config:
        from nbt_refine import point
        walls={point(p) for p in config['wall_positions']}
        if any(not model.in_bounds(p) for p in walls):raise ValueError('墙mask超出原建筑范围')
    walls={p for p in walls if p in model.blocks};source_walls=set(walls)
    virtual,walls,difference=simulate_plan(model,walls,plan,config)
    changed=difference['changed_blocks']
    output=reserve_output(output)
    def snapshot(current,mask):
        blocks=[]
        for position,value in sorted(current.blocks.items()):
            name,props=effective(value);blocks.append([list(position),normalize(dict(Name=name,Properties=props))])
        return dict(name=source.name,source=str(source),source_sha256=baseline,geometry_sha256=current.fingerprint(),
                    size=list(current.size),blocks=blocks,master_blocks=[[list(p),value] for p,value in sorted(current.blocks.items())],wall_positions=sorted(mask),cameras=config['cameras'],
                    registry_sha256=registry()['blocks_sha256'],preview_only=True,
                    verification=dict(routes='not_checked',game='not_checked',design='pending_visual_review'))
    write_json(output/'before.json',snapshot(model,source_walls));write_json(output/'after.json',snapshot(virtual,walls))
    from nbt_compare import describe
    diff=describe(model,virtual,source_walls,walls)
    diff.update(before_source_sha256=baseline,after_source_sha256=baseline,before_geometry_sha256=model.fingerprint(),after_geometry_sha256=virtual.fingerprint())
    write_json(output/'difference.json',diff)
    if digest(source)!=baseline: raise ValueError('原建筑在计算中变化，请重新打开')
    return dict(status='visual_preview_only',snapshot=str(output/'after.json'),baseline_snapshot=str(output/'before.json'),
                geometry_sha256=virtual.fingerprint(),source_sha256=baseline,size=list(model.size),
                cameras=config['cameras'],changed_blocks=changed,wall_membership_changes=difference['wall_membership_changes'],settings_sha256=canonical(settings),preview_only=True,difference=str(output/'difference.json'))


def create_review(request, output):
    source = Path(request['source']).resolve(); model, _ = read_master(source)
    if request.get('source_sha256') and request['source_sha256'] != digest(source):
        raise ValueError('Baseline changed since it was displayed; reload the model before review')
    compile_plan(request['settings'], model.size)
    config = normalize_context(model, request['context'], request.get('cameras', ''), request['settings'])
    prepare(source, config, output)
    return dict(status='awaiting_user_review', review=str(Path(output).resolve()),
                images=[str(Path(output).resolve()/'thumbnails.png')],
                note='Display thumbnails and obtain the existing skill-required conversational confirmation; the GUI never invents an approval receipt.')


def apply_approved(request, bundle_path, review, output):
    bundle_path = Path(bundle_path).resolve(); bundle = read_json(bundle_path)
    source = Path(request['source']).resolve()
    record = _current_review(review)
    if (str(source) != bundle['source'] or source != Path(record['source']).resolve()
            or digest(source) != bundle['source_sha256'] or canonical(request['settings']) != bundle['settings_sha256']):
        raise ValueError('Source/settings changed since plan export; export a new plan')
    plan = read_json(bundle_path.parent/'plan.json')
    if canonical(plan) != bundle['plan_sha256']: raise ValueError('Plan changed after export')
    review_config = read_json(Path(review)/'config.json')
    expected = {k: v for k, v in bundle['context'].items() if k != 'wall_positions'}
    if canonical(review_config) != canonical(expected): raise ValueError('Reviewed protection/config differs from this plan; use matching context and a new review when needed')
    result = refine(review, plan, output)
    return dict(status=result['state'], output=str(Path(output).resolve()), changed_blocks=result['changed_blocks'],
                wall_membership_changes=result.get('wall_membership_changes',0),changed_positions=result.get('changed_positions',result['changed_blocks']),
                preview_source=str(Path(output).resolve()/'refined.master.json.gz'),
                images=[str(Path(output).resolve()/'comparison.png')])


def render_source(request, output):
    source = Path(request['source']).resolve(); model, _ = read_master(source)
    config = normalize_context(model, request['context'], request.get('cameras', ''), request['settings'])
    output = reserve_output(output); camera_file = output/'cameras.json'
    views = []
    for i, camera in enumerate(config['cameras']):
        view = dict(camera, id=f'view_{i+1:03}'); views.append(view)
    write_json(camera_file, views)
    target = output/'images'
    run = subprocess.run([sys.executable, '-B', str(ROOT/'scripts/nbt_task.py'), 'render', '--source', str(source),
                          '--cameras', str(camera_file), '--output', str(target)], capture_output=True, text=True, encoding='utf8', errors='replace')
    (output/'render.log').write_text(run.stdout+run.stderr, encoding='utf8')
    if run.returncode: raise ValueError('Source rendering failed; see '+str(output/'render.log'))
    manifest = read_json(target/'render_manifest.json')
    return dict(status='source_rendered', output=str(output), images=[str(target/item['image']) for item in manifest['images']])


def source_snapshot(request, output):
    from nbt_task import write_snapshot
    source = Path(request['source']).resolve(); model, _ = read_master(source)
    readiness=context_readiness(model,request.get('context'))
    context_warning=''
    if readiness['ready']:
        try:
            config = normalize_context(model, request['context'], request.get('cameras', ''), request['settings'])
            raw=read_json(request['cameras']) if request.get('cameras') else config['cameras']
        except (ValueError,KeyError,TypeError,OSError) as error:
            readiness=dict(readiness,ready=False,errors=[str(error)])
    if not readiness['ready']:
        sx,sy,sz=model.size
        try:raw=read_json(request['cameras']) if request.get('cameras') else None
        except (OSError,ValueError):raw=None
        raw=raw or [dict(id='whole',role='whole',eye=[sx*1.5,sy*1.5,-sz],target=[sx/2,sy/2,sz/2],cuts=[])]
        context_warning='当前只读查看：坐标配置还需补齐 '+', '.join(readiness['missing']+readiness['errors'])
    views = []
    for i, camera in enumerate(raw):
        view = {k: camera[k] for k in ('eye', 'target', 'up', 'fov', 'role', 'layer', 'lighting', 'cut_y') if k in camera}
        view['id'] = camera.get('id', f'view_{i+1:03}')
        view['cuts'] = [dict(axis=c[0], position=c[1], removed_side=c[2]) if isinstance(c, list) else c for c in camera.get('cuts', [])]
        views.append(view)
    output = reserve_output(output)
    result = write_snapshot(source, output/'snapshot.json', cameras=views)
    return dict(status='baseline_snapshot', snapshot=str(output/'snapshot.json'), source_sha256=result['source_sha256'],
                geometry_sha256=result['geometry_sha256'], size=result['size'], cameras=views,read_only_view=not readiness['ready'],context_warning=context_warning)


def prompt_export(request):
    """Compile current settings for text export only; no effects or approvals."""
    source = Path(request['source']).resolve()
    before = digest(source)
    if request.get('source_sha256') != before:
        raise ValueError('建筑版本已改变，请重新打开建筑后生成提示词')
    model, _ = read_master(source)
    plan = compile_plan(request['settings'], model.size)
    context = read_json(request['context']) if request.get('context') else {}
    if not isinstance(context, dict): raise ValueError('上下文须为JSON对象')
    if request.get('cameras'): context['cameras'] = read_json(request['cameras'])
    if digest(source) != before: raise ValueError('生成期间建筑版本已改变')
    return dict(source=str(source), source_sha256=before, size=model.size,
                plan=plan, context=context, model_modified=False, validation_performed=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    cmd = sub.add_parser('catalog'); cmd.add_argument('--workspace', type=Path, required=True);cmd.add_argument('--include-bugged',action='store_true');cmd.add_argument('--index-only',action='store_true')
    cmd = sub.add_parser('inspect'); cmd.add_argument('--source', type=Path, required=True); cmd.add_argument('--image-limit',type=int,default=8)
    cmd = sub.add_parser('asset-batches');cmd.add_argument('--workspace',type=Path,required=True);cmd.add_argument('--action',choices=['list','import','generate','read','save','organize'],required=True);cmd.add_argument('--request',type=Path,required=True)
    cmd = sub.add_parser('project-repair');cmd.add_argument('--workspace',type=Path,required=True);cmd.add_argument('--source',required=True);cmd.add_argument('--category',default='auto');cmd.add_argument('--source-sha256')
    cmd = sub.add_parser('cover'); cmd.add_argument('--source', type=Path, required=True); cmd.add_argument('--geometry', default=''); cmd.add_argument('--cache',type=Path,required=True); cmd.add_argument('--generate-missing',action='store_true')
    cmd = sub.add_parser('components'); cmd.add_argument('--workspace',type=Path,required=True);cmd.add_argument('--action',choices=['list','save','get','place','batch','import','update','extract','transform','agent'],required=True);cmd.add_argument('--request',type=Path)
    cmd = sub.add_parser('recipes');cmd.add_argument('--workspace',type=Path,required=True);cmd.add_argument('--action',choices=['list','get','save','capture','archive','compile'],required=True);cmd.add_argument('--request',type=Path)
    cmd = sub.add_parser('project-batch');cmd.add_argument('--workspace',type=Path,required=True);cmd.add_argument('--action',choices=['list','create','get','run','retry','cancel'],required=True);cmd.add_argument('--request',type=Path)
    cmd = sub.add_parser('protection-mask');cmd.add_argument('--request',type=Path,required=True)
    cmd = sub.add_parser('walk-inspect');cmd.add_argument('--request',type=Path,required=True);cmd.add_argument('--output',type=Path,required=True);cmd.add_argument('--snapshot',type=Path)
    cmd = sub.add_parser('agent-tasks');cmd.add_argument('--workspace',type=Path,required=True);cmd.add_argument('--action',choices=['create','list','get','discover','record','review'],required=True);cmd.add_argument('--request',type=Path,required=True)
    cmd = sub.add_parser('retrieve');cmd.add_argument('--workspace',type=Path,required=True);cmd.add_argument('--action',choices=['search','source','bundle','read'],required=True);cmd.add_argument('--request',type=Path,required=True)
    cmd = sub.add_parser('selection-edit');cmd.add_argument('--action',choices=['context','compile'],required=True);cmd.add_argument('--request',type=Path,required=True);cmd.add_argument('--snapshot',type=Path)
    cmd = sub.add_parser('thumbnails'); cmd.add_argument('--request',type=Path,required=True);cmd.add_argument('--cache',type=Path,required=True)
    sub.add_parser('defaults')
    cmd = sub.add_parser('prompt'); cmd.add_argument('--request', type=Path, required=True)
    cmd = sub.add_parser('prompt-save');cmd.add_argument('--workspace',type=Path,required=True);cmd.add_argument('--request',type=Path,required=True)
    cmd = sub.add_parser('batches');cmd.add_argument('--workspace',type=Path,required=True);cmd.add_argument('--action',choices=['create','import','list','get','record','run','ack','locate','discover'],required=True);cmd.add_argument('--request',type=Path,required=True)
    cmd = sub.add_parser('feedback-tasks');cmd.add_argument('--workspace',type=Path,required=True);cmd.add_argument('--action',choices=['list','create','update','merge','evidence'],required=True);cmd.add_argument('--request',type=Path,required=True)
    cmd = sub.add_parser('validate'); cmd.add_argument('--request',type=Path,required=True);cmd.add_argument('--snapshot',type=Path,required=True);cmd.add_argument('--output',type=Path,required=True)
    for name in ('plan', 'prepare', 'render', 'snapshot', 'preview', 'revision', 'compare'):
        cmd = sub.add_parser(name); cmd.add_argument('--request', type=Path, required=True); cmd.add_argument('--output', type=Path, required=True)
    cmd = sub.add_parser('apply'); cmd.add_argument('--request', type=Path, required=True)
    cmd.add_argument('--bundle', type=Path, required=True); cmd.add_argument('--review', type=Path, required=True)
    cmd.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == 'catalog': result = catalog(args.workspace,include_bugged=args.include_bugged,index_only=args.index_only)
        elif args.command == 'asset-batches':
            from nbt_asset_batches import dispatch
            result=dispatch(args.workspace,args.action,read_json(args.request))
        elif args.command == 'project-repair':
            from nbt_project_repair import repair
            result=repair(args.workspace,args.source,args.category,args.source_sha256)
        elif args.command == 'cover':
            from nbt_cover import section_cover
            result = section_cover(args.source,args.geometry,args.cache,generate=args.generate_missing)
        elif args.command == 'recipes':
            from nbt_recipes import dispatch
            result=dispatch(args.workspace,args.action,read_request(args.request) if args.request else {})
        elif args.command == 'prompt-save':
            from nbt_prompts import save
            result=save(args.workspace,read_json(args.request))
        elif args.command == 'batches':
            from nbt_batches import dispatch
            result=dispatch(args.workspace,args.action,read_request(args.request))
        elif args.command == 'feedback-tasks':
            from nbt_feedback_tasks import dispatch
            result=dispatch(args.workspace,args.action,read_request(args.request))
        elif args.command == 'project-batch':
            from nbt_project_batch import dispatch
            result=dispatch(args.workspace,args.action,read_request(args.request) if args.request else {})
        elif args.command == 'protection-mask':
            from nbt_protection_view import mask
            result=mask(read_request(args.request))
        elif args.command == 'walk-inspect':
            from nbt_walk_view import inspect_walk
            result=inspect_walk(read_request(args.request),args.snapshot)
            output=reserve_output(args.output)
            write_json(output/'walk-inspection.json',result)
            result['report_file']=str(output/'walk-inspection.json')
        elif args.command == 'agent-tasks':
            from nbt_agent_tasks import dispatch
            result=dispatch(args.workspace,args.action,read_request(args.request))
        elif args.command == 'retrieve':
            from nbt_retrieval import dispatch
            result=dispatch(args.workspace,args.action,read_request(args.request))
        elif args.command == 'selection-edit':
            from nbt_selection_edit import dispatch
            result=dispatch(args.action,read_request(args.request),args.snapshot)
        elif args.command == 'components':
            import nbt_components as components
            data=read_request(args.request) if args.request else {}
            if args.action=='agent':
                from nbt_structure_agent import dispatch
                if set(data)!={'tool','arguments'}:raise ValueError('结构Agent请求须包含tool和arguments')
                result=dispatch(args.workspace,data['tool'],data['arguments'])
            elif args.action=='list':result=components.listing(args.workspace)
            elif args.action=='get':result=components.load(args.workspace,data['id'])
            elif args.action=='save':result=components.capture(args.workspace,data['source'],data['name'],data['lo'],data['hi'],tags=data.get('tags',[]),include_air=data.get('include_air',False),snapshot=data['snapshot'],snapshot_sha256=data['snapshot_sha256'])
            elif args.action=='import':result=components.store(args.workspace,data['component'])
            elif args.action=='update':result=components.update(args.workspace,data['id'],data.get('name'),data.get('tags'),data.get('archived'))
            elif args.action=='extract':result=components.extract(data['source'],data.get('name','选区构件'),data['lo'],data['hi'],snapshot=data['snapshot'],snapshot_sha256=data['snapshot_sha256'])
            elif args.action=='transform':result=components.transform_selection(data['source'],data['lo'],data['hi'],data['position'],snapshot=data['snapshot'],snapshot_sha256=data['snapshot_sha256'],quarter_turns=data.get('quarter_turns',0),mirror=data.get('mirror'),overwrite=data.get('overwrite',False),move=data.get('move',False),name=data.get('name','选区构件'))
            else:
                component=components.load(args.workspace,data['id']) if data.get('id') else components.validate(data['component'])
                if data.get('content_sha256') and data['content_sha256']!=component['content_sha256']:raise ValueError('构件内容已改变，请重新载入')
                if args.action=='batch':
                    from nbt_recipes import load as load_theme
                    result=components.batch_placement(component,data['position'],data['size'],data.get('counts'),data.get('spacing'),data.get('quarter_turns',0),data.get('mirror'),data.get('overwrite',False),load_theme(args.workspace,data['theme']) if data.get('theme') else None)
                else:result=components.placement(component,data['position'],data['size'],data.get('quarter_turns',0),data.get('mirror'),data.get('overwrite',False))
        elif args.command == 'inspect':
            if not 1 <= args.image_limit <= 64: raise ValueError('image-limit must be 1..64')
            result = inspect_source(args.source,args.image_limit)
        elif args.command == 'thumbnails':result=thumbnails(args.request,args.cache)
        elif args.command == 'defaults': result = default_settings()
        elif args.command == 'prompt': result = prompt_export(read_request(args.request))
        elif args.command == 'plan': result = export_plan(read_request(args.request), args.output)
        elif args.command == 'validate':
            from nbt_candidate import validate_candidate
            result=validate_candidate(read_request(args.request),args.snapshot,args.output)
        elif args.command == 'prepare': result = create_review(read_request(args.request), args.output)
        elif args.command == 'render': result = render_source(read_request(args.request), args.output)
        elif args.command == 'revision':
            from nbt_web_revision import convert_web_json
            result=convert_web_json(args.request)
        elif args.command == 'preview': result = preview_effect(read_request(args.request), args.output)
        elif args.command == 'snapshot': result = source_snapshot(read_request(args.request), args.output)
        elif args.command == 'compare':
            from nbt_compare import compare_sources
            result=compare_sources(read_request(args.request),args.output)
        else: result = apply_approved(read_request(args.request), args.bundle, args.review, args.output)
        print(json.dumps(dict(ok=True, result=result), ensure_ascii=False))
        if args.command=='validate' and not result['passed']:return 1
    except Exception as error:
        print(json.dumps(dict(ok=False, error=str(error),**(dict(details=error.details) if hasattr(error,'details') else {})), ensure_ascii=False)); return 1
    return 0


if __name__ == '__main__': raise SystemExit(main())
