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


def catalog(workspace, cache_path=None):
    root = Path(workspace).resolve()/'nbt_models'
    marker=root/'_migration/active.json'
    if marker.is_file() and read_json(marker).get('status')!='complete':return dict(models=[],skipped=0,scanned=0,cache_hits=0,migration_in_progress=True)
    files = []
    for directory, dirs, names in os.walk(root):
        conversion=Path(directory)/'conversion.json'
        if conversion.is_file():
            try:ready=read_json(conversion).get('status')=='complete'
            except (OSError,ValueError):ready=False
            if not ready:dirs[:]=[];continue
        dirs[:] = [name for name in dirs if not (name.startswith(('.', 'synthetic', 'test_')) or
                    any(word in name.lower() for word in ('validation', 'fixture', 'cache', 'control_web', 'regression')) or
                    name in {'bugged','_migration','_workspaces','_tests','world', 'worlds', 'saves', 'node_modules', 'previews', 'jobs', 'review'})]
        files.extend(Path(directory)/name for name in names if name.endswith('.json.gz') and 'master' in name.lower())
    files.sort(key=lambda p: (p.stat().st_mtime_ns, str(p)), reverse=True)
    cache_path = Path(cache_path) if cache_path else root/'_workspaces/catalog_metadata.json'
    try: cache = read_json(cache_path)
    except (OSError, ValueError): cache = {}
    next_cache = {}; cache_hits = 0
    models, seen, skipped = [], set(), 0
    descriptions={}
    for p in files:
        try:
            descriptor=next((parent/'room_description.json' for parent in [p.parent,*list(p.parents)[:4]] if (parent/'room_description.json').is_file()),None)
            if descriptor:
                if descriptor not in descriptions:descriptions[descriptor]=read_json(descriptor)
                declaration=descriptions[descriptor]
                if declaration.get('audit',{}).get('compliant') is False:continue
                declared_master=declaration.get('master')
                if declared_master and Path(declared_master).is_file() and Path(declared_master).resolve()!=p.resolve():continue
            stat=p.stat(); stamp=[stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns]
            entry=cache.get(str(p))
            if entry and entry.get('stamp')==stamp:
                data=entry['metadata'];cache_hits+=1
            elif descriptor and declaration.get('audit',{}).get('compliant') is True and declaration.get('master_file_sha256') and declaration.get('geometry_sha256') and digest(p)==declaration['master_file_sha256']:
                data={'geometry_sha256':declaration['geometry_sha256'], 'size':declaration.get('size')};cache_hits+=1
            else:
                with gzip.open(p, 'rt', encoding='utf8') as stream: raw = json.load(stream)
                data = {'geometry_sha256':raw['geometry_sha256'], 'size':raw['size']} if isinstance(raw,dict) and all(key in raw for key in ('size','blocks','geometry_sha256')) else None
            next_cache[str(p)]={'stamp':stamp,'metadata':data}
            if not data: skipped += 1; continue
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
            description_file=next((parent/'room_description.json' for parent in [p.parent,*list(p.parents)[:4]] if (parent/'room_description.json').is_file()),None)
            room_description={}
            if description_file:
                try:room_description=read_json(description_file)
                except (ValueError,OSError):room_description={}
                if room_description.get('audit',{}).get('compliant') is False:continue
                recorded_master=room_description.get('master')
                if recorded_master and Path(recorded_master).resolve()!=p.resolve() and Path(recorded_master).is_file():continue
                name=room_description.get('name_zh') or name
                parts=description_file.parent.relative_to(root).parts
                if len(parts)>=3 and parts[0] in {'single','long','square','l_shape','t_shape','cross','standalone','irregular'}:
                    group='/'.join(parts[:2])
                elif 'versions' in parts:group='/'.join(parts[:parts.index('versions')])
                else:group=str(description_file.parent.parent.relative_to(root)) if description_file.parent.name.startswith(('版本_','v_','detail_v','refined_v')) or re.fullmatch(r'v\d+',description_file.parent.name) else str(description_file.parent.relative_to(root))
                batch=room_description.get('shape_zh') or batch
            key = (group, data['geometry_sha256'])
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
                               modified_ns=stat.st_mtime_ns, file_size=stat.st_size, relative_path=str(relative)))
        except (OSError, ValueError, TypeError, KeyError): skipped += 1
    cache_path.parent.mkdir(parents=True,exist_ok=True)
    import uuid
    temporary=cache_path.with_name(cache_path.name+'.'+uuid.uuid4().hex+'.tmp')
    write_json(temporary,next_cache);os.replace(temporary,cache_path)
    return dict(models=models, skipped=skipped, scanned=len(files), cache_hits=cache_hits)


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
    unknown = [dict(state=value, count=count, reason=collision_cells(value)[1])
               for value, count in sorted(counts.items()) if collision_cells(value)[1]]
    context = nearby(source, ('coordinates.json', 'config.json', 'context.json'))
    cameras = nearby(source, ('cameras.json',))
    images = preview_images(source, geometry_hash, image_limit)
    sx,sy,sz=model.size
    solid=[p for p,value in model.blocks.items() if value.split('[')[0] not in ('minecraft:air','minecraft:cave_air','minecraft:void_air')]
    projections=dict(top=dict(size=[sx,sz],cells=sorted({x+z*sx for x,y,z in solid})),front=dict(size=[sx,sy],cells=sorted({x+y*sx for x,y,z in solid})),side=dict(size=[sz,sy],cells=sorted({z+y*sz for x,y,z in solid})))
    data = read_json(context) if context else {}
    return dict(source=str(source), source_sha256=digest(source), workdir=str(project_paths(source)['workdir']), geometry_sha256=model.fingerprint(),
                projections=projections,size=list(model.size), solid_blocks=len(model.blocks), wall_blocks=len(walls),
                context=context, cameras=cameras, images=images, unknown_shapes=unknown,
                materials=[dict(state=value,count=count) for value,count in counts.most_common() if value.split('[')[0] not in ('minecraft:air','minecraft:cave_air','minecraft:void_air')],
                suggested_floor=data.get('floor_operation', {}), suggested_budget=data.get('max_changed_blocks', 4096),
                note='Controls describe a new pass from this baseline; existing details cannot be undone without an earlier baseline.')


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
        structure=dict(enabled=False,mode='fill',state='stone_bricks',offset=[0,0,0],thickness=1,classification='body'),
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
    return dict(style_note=note, operations=operations)


def normalize_context(model, context_path, camera_path, settings):
    data = read_json(context_path)
    from nbt_library import canonical_context
    data = canonical_context(context_path)
    keys = ('cells', 'door_y', 'ports', 'start', 'targets', 'interior_probes', 'protected_paths',
            'protected_boxes', 'route_legs', 'cameras', 'wall_positions')
    config = {key: data[key] for key in keys if key in data}
    if 'cells' not in config and model.size[0] == model.size[2] == 48: config['cells'] = [[0, 0]]
    config.setdefault('ports', []); config.setdefault('door_y', 2)
    config['max_changed_blocks'] = settings.get('max_changed_blocks', 4096)
    for key in ('start', 'targets', 'interior_probes'):
        if key not in config: raise ValueError(f'Context is missing {key}; choose coordinates/config JSON')
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
                         for c, role in selected[:4]]
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
        for operation in plan['operations']:
            if operation['kind'] == 'pattern': edits, report = pattern_plan(virtual, operation, protected)
            elif operation['kind'] == 'weathering': edits, report = weathering_plan(virtual, operation, protected)
            elif operation['kind']=='auto_floor': edits, report = auto_floor_plan(virtual, operation, config, protected)
            else: edits,report=operation_candidates(virtual,operation,protected),{}
            if any(p in protected and virtual.get(p)!=value for p,value in edits):raise ValueError('结构编辑触及保护区，请调整范围')
            estimates.append(dict(kind=operation['kind'], label=operation['label'], writes=len(edits), report=report))
            for p, value in edits: virtual.put(p, value)
    except (ValueError, AssertionError, KeyError) as error:
        warning_detail = str(error)
        unsupported = [value for value in sorted(set(model.blocks.values())) if collision_cells(value)[1]]
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


def preview_effect(request, output):
    # User-requested visual experiment only: no master/NBT, approval or delivery.
    from nbt_assembly import Volume
    from nbt_patterns import pattern_plan
    from nbt_weathering import weathering_plan
    from nbt_floors import auto_floor_plan
    from nbt_registry import effective, normalize, registry
    source=Path(request['source']).resolve(); baseline=digest(source)
    if request.get('source_sha256') and request['source_sha256']!=baseline: raise ValueError('原建筑已变化，请重新打开')
    model,walls=read_master(source);source_walls=set(walls);settings=request['settings'];plan=compile_plan(settings,model.size)
    config=normalize_context(model,request['context'],request.get('cameras',''),settings)
    virtual=Volume(model.size);virtual.blocks=dict(model.blocks);protected=protections(virtual,config)
    for operation in plan['operations']:
        if operation['kind']=='pattern': edits,_=pattern_plan(virtual,operation,protected)
        elif operation['kind']=='weathering': edits,_=weathering_plan(virtual,operation,protected)
        elif operation['kind']=='auto_floor': edits,_=auto_floor_plan(virtual,operation,config,protected)
        else: edits=operation_candidates(virtual,operation,protected)
        if any(not virtual.in_bounds(p) or p in protected and virtual.get(p)!=value for p,value in edits):raise ValueError('结构编辑超出边界或触及保护区，请调整范围')
        moved_walls={tuple(p[i]+operation['offset'][i] for i in range(3)) for p in walls if all(operation['lo'][i]<=p[i]<=operation['hi'][i] for i in range(3))} if operation['kind']=='move_region' else set()
        for position,value in edits:
            virtual.put(position,value)
            if operation['kind']=='move_region':
                if position in moved_walls and value.split('[')[0] not in ('minecraft:air','minecraft:cave_air','minecraft:void_air'):walls.add(position)
                else:walls.discard(position)
            elif value.split('[')[0] in ('minecraft:air','minecraft:cave_air','minecraft:void_air') or operation.get('classification')=='body':walls.discard(position)
            elif operation.get('classification')=='wall' or position in moved_walls:walls.add(position)
    changed=sum(model.get(p)!=virtual.get(p) for p in set(model.blocks)|set(virtual.blocks))
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
    if digest(source)!=baseline: raise ValueError('原建筑在计算中变化，请重新打开')
    return dict(status='visual_preview_only',snapshot=str(output/'after.json'),baseline_snapshot=str(output/'before.json'),
                geometry_sha256=virtual.fingerprint(),source_sha256=baseline,size=list(model.size),
                cameras=config['cameras'],changed_blocks=changed,settings_sha256=canonical(settings),preview_only=True)


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
    config = normalize_context(model, request['context'], request.get('cameras', ''), request['settings'])
    raw = read_json(request['cameras']) if request.get('cameras') else config['cameras']
    views = []
    for i, camera in enumerate(raw):
        view = {k: camera[k] for k in ('eye', 'target', 'up', 'fov', 'role', 'layer', 'lighting', 'cut_y') if k in camera}
        view['id'] = camera.get('id', f'view_{i+1:03}')
        view['cuts'] = [dict(axis=c[0], position=c[1], removed_side=c[2]) if isinstance(c, list) else c for c in camera.get('cuts', [])]
        views.append(view)
    output = reserve_output(output)
    result = write_snapshot(source, output/'snapshot.json', cameras=views)
    return dict(status='baseline_snapshot', snapshot=str(output/'snapshot.json'), source_sha256=result['source_sha256'],
                geometry_sha256=result['geometry_sha256'], size=result['size'], cameras=views)


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
    cmd = sub.add_parser('catalog'); cmd.add_argument('--workspace', type=Path, required=True)
    cmd = sub.add_parser('inspect'); cmd.add_argument('--source', type=Path, required=True); cmd.add_argument('--image-limit',type=int,default=8)
    cmd = sub.add_parser('cover'); cmd.add_argument('--source', type=Path, required=True); cmd.add_argument('--geometry', required=True); cmd.add_argument('--cache',type=Path,required=True)
    cmd = sub.add_parser('thumbnails'); cmd.add_argument('--request',type=Path,required=True);cmd.add_argument('--cache',type=Path,required=True)
    sub.add_parser('defaults')
    cmd = sub.add_parser('prompt'); cmd.add_argument('--request', type=Path, required=True)
    for name in ('plan', 'prepare', 'render', 'snapshot', 'preview', 'revision'):
        cmd = sub.add_parser(name); cmd.add_argument('--request', type=Path, required=True); cmd.add_argument('--output', type=Path, required=True)
    cmd = sub.add_parser('apply'); cmd.add_argument('--request', type=Path, required=True)
    cmd.add_argument('--bundle', type=Path, required=True); cmd.add_argument('--review', type=Path, required=True)
    cmd.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == 'catalog': result = catalog(args.workspace)
        elif args.command == 'cover':
            images = preview_images(args.source,args.geometry,1)
            if images:
                from PIL import Image
                cache=args.cache;cache.mkdir(parents=True,exist_ok=True)
                image=Path(images[0]);fingerprint=digest(image);target=cache/(fingerprint+'.jpg')
                if not target.is_file():
                    with Image.open(image) as original:
                        thumb=original.convert('RGB');thumb.thumbnail((320,200));thumb.save(target,'JPEG',quality=78)
                result=dict(image=str(image),thumbnail=str(target))
            else: result=dict(image=None,thumbnail=None)
        elif args.command == 'inspect':
            if not 1 <= args.image_limit <= 64: raise ValueError('image-limit must be 1..64')
            result = inspect_source(args.source,args.image_limit)
        elif args.command == 'thumbnails':result=thumbnails(args.request,args.cache)
        elif args.command == 'defaults': result = default_settings()
        elif args.command == 'prompt': result = prompt_export(read_json(args.request))
        elif args.command == 'plan': result = export_plan(read_json(args.request), args.output)
        elif args.command == 'prepare': result = create_review(read_json(args.request), args.output)
        elif args.command == 'render': result = render_source(read_json(args.request), args.output)
        elif args.command == 'revision':
            from nbt_web_revision import convert_web_json
            result=convert_web_json(args.request)
        elif args.command == 'preview': result = preview_effect(read_json(args.request), args.output)
        elif args.command == 'snapshot': result = source_snapshot(read_json(args.request), args.output)
        else: result = apply_approved(read_json(args.request), args.bundle, args.review, args.output)
        print(json.dumps(dict(ok=True, result=result), ensure_ascii=False))
    except Exception as error:
        print(json.dumps(dict(ok=False, error=str(error)), ensure_ascii=False)); return 1
    return 0


if __name__ == '__main__': raise SystemExit(main())
