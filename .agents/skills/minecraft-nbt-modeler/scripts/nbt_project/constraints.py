"""Revisioned workspace constraints shared by project management and prompt authoring."""
import copy, hashlib, json, re, uuid
from functools import lru_cache
from pathlib import Path
from nbt_project.prompts import inside, relative, index_lock, encode
from nbt_project.history import now
from nbt_project.queues import write
from nbt_runtime.catalog import catalog

ACTIONS=('constraints-registry','constraints-list','constraints-save','constraints-delete')
RULES=set(catalog()['project_constraints']['rules']['properties'])
SHAPES=set(catalog()['building_shapes'])

def integer(value,maximum):return type(value) is int and 0<value<=maximum

def valid_constraint_id(value):return isinstance(value,str) and re.fullmatch(r'constraint-[a-f0-9]{32}',value) is not None

def validate_rules(rules):
    if not isinstance(rules,dict) or not rules or set(rules)-RULES:raise ValueError('约束规则为空或包含未知字段')
    if 'buildingShape' in rules and (not isinstance(rules['buildingShape'],str) or rules['buildingShape'] not in SHAPES):raise ValueError('约束的归档形状无效')
    if 'size' in rules and (not isinstance(rules['size'],list) or len(rules['size'])!=3 or not all(integer(n,4096) for n in rules['size'])):raise ValueError('约束尺寸须为三个1～4096的整数')
    if 'size_policy' in rules and (rules['size_policy'] not in ('fixed','reference') or 'size' not in rules):raise ValueError('尺寸约束方式需要同时指定尺寸')
    for key in ('footprint','requirements'):
        if key in rules and (not isinstance(rules[key],str) or not rules[key].strip() or len(rules[key])>4000):raise ValueError('约束说明须为1～4000字')
    if 'cell_size' in rules and not integer(rules['cell_size'],512):raise ValueError('网格边长须为1～512的整数')
    if 'cells' in rules:
        cells=rules['cells']
        if not integer(rules.get('cell_size'),512) or not isinstance(cells,list) or not 1<=len(cells)<=256 or any(not isinstance(cell,list) or len(cell)!=2 or any(type(n) is not int or not 0<=n<4096 for n in cell) for cell in cells):raise ValueError('有效网格须为非负整数XZ坐标，并指定网格边长')
        if len({tuple(cell) for cell in cells})!=len(cells):raise ValueError('有效网格不能重复')
        if 'size' in rules and any((x+1)*rules['cell_size']>rules['size'][0] or (z+1)*rules['cell_size']>rules['size'][2] for x,z in cells):raise ValueError('有效网格超出约束尺寸')
    if 'integration' in rules and rules['integration'] not in ('standalone', 'saodg'):
        raise ValueError('接入扩展无效')
    from nbt_composition.whole_validation import opening_policy, requires_enclosure
    context = {key: rules[key] for key in ('require_enclosure', 'openings_policy', 'opening_size') if key in rules}
    context['mode'] = rules.get('integration', 'standalone')
    requires_enclosure(context)
    opening_policy(context)
    if context['mode'] == 'saodg' and rules.get('cell_size', 48) != 48:
        raise ValueError('SAODG 接入要求 48 格网格')
    return rules

FOLDER_FILE='项目约束.json'

def folder_parts(value):
    if not isinstance(value,str) or len(value)>500:
        raise ValueError('请选择 nbt_models 下的项目文件夹')
    parts=value.split('/')
    if parts[0]!='nbt_models' or any(not part or part.startswith(('.', '_')) or re.search(r'[<>:"\\|?*\x00-\x1f]',part) or part.endswith((' ','.')) or part in {'bugged','未分类','项目约束.json'} for part in parts[1:]):
        raise ValueError('请选择 nbt_models 下的项目文件夹')
    return parts

def content(item):
    keys=('schema_version','id','revision','name','rules')
    return {key:item[key] for key in (*keys,'folder') if key in item}

def checksum(item):return hashlib.sha256(json.dumps(content(item),ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf8')).hexdigest()

def validate_snapshot(item):
    if not isinstance(item,dict) or set(item)-set(catalog()['project_constraints']['snapshot_fields']) or item.get('schema_version')!=1 or not valid_constraint_id(item.get('id')) or not integer(item.get('revision'),2**53-1) or not isinstance(item.get('name'),str) or not item['name'].strip() or len(item['name'])>80:raise ValueError('项目约束快照无效')
    if 'actor' in item and item['actor'] not in ('human','agent') or 'updated_at' in item and (not isinstance(item['updated_at'],str) or len(item['updated_at'])>80):raise ValueError('项目约束修订信息无效')
    if 'folder' in item:folder_parts(item['folder'])
    validate_rules(item.get('rules'))
    if checksum(item)!=item.get('sha256'):raise ValueError('项目约束快照内容与哈希不符')

def validate_selection(items,project=None):
    if not isinstance(items,list) or len(items)>16:raise ValueError('每个方案最多引用16项项目约束')
    merged={};seen=set()
    for item in items:
        validate_snapshot(item)
        if item['id'] in seen:raise ValueError('不能重复引用同一项目约束')
        seen.add(item['id'])
        normalized=dict(item['rules'])
        if 'size' in normalized and 'size_policy' not in normalized:normalized['size_policy']='fixed'
        for key,value in normalized.items():
            if key=='requirements':continue
            if key in merged and merged[key]!=value:raise ValueError('项目约束冲突：'+key)
            merged[key]=value
    if merged:validate_rules(merged)
    if project:
        integration = merged.get('integration', project.get('integration', 'standalone'))
        if project.get('source'):
            from nbt_composition.whole_validation import validation_mode
            source_mode = validation_mode(project.get('context') or {})
            if 'integration' in merged and source_mode != integration:
                raise ValueError('接入约束与已有建筑不符')
            integration = source_mode
        if integration == 'saodg' and merged:
            validate_rules(dict(merged, integration=integration))
        effective=dict(project,**{key:value for key,value in merged.items() if key in ('size','buildingShape')})
        if project.get('source') and any(key in merged and merged[key]!=project.get(key) for key in ('size','buildingShape')):raise ValueError('项目约束与已有建筑不符')
        if 'cells' in merged and any((x+1)*merged['cell_size']>effective['size'][0] or (z+1)*merged['cell_size']>effective['size'][2] for x,z in merged['cells']):raise ValueError('项目约束的有效网格超出当前尺寸')
    return merged


def list_result(data, request):
    items=data['items']
    if 'id' in request:items=[item for item in items if item['id']==request['id']]
    if request.get('summary'):
        items=[{key:item[key] for key in ('id','name','revision','sha256','folder') if key in item} for item in items]
    return dict(data,items=items)


def read_legacy_library(file, folder):
    try:info=file.stat()
    except FileNotFoundError:return dict(schema_version=1,revision=0,items=[])
    return legacy_library(file,folder,info.st_size,info.st_mtime_ns,info.st_ctime_ns)


@lru_cache(maxsize=1024)
def legacy_library(file, folder, size, modified_ns, changed_ns):
    if size>4*1024*1024:raise ValueError('项目约束库超过4MiB')
    data=json.loads(file.read_text(encoding='utf-8-sig'))
    if not isinstance(data,dict) or data.get('schema_version')!=1 or type(data.get('revision')) is not int or data['revision']<0 or not isinstance(data.get('items'),list) or len(data['items'])>256:raise ValueError('项目约束库无效')
    for item in data['items']:
        validate_snapshot(item)
        if item.get('folder','')!=folder:raise ValueError('约束所属文件夹与文件位置不一致')
    if len({item['id'] for item in data['items']})!=len(data['items']) or len({item['name'] for item in data['items']})!=len(data['items']):raise ValueError('项目约束库含重复条目')
    return data


@lru_cache(maxsize=4096)
def read_rule(file, size, modified_ns, changed_ns):
    from nbt_project.rooms import read_small
    record=read_small(file)
    if not isinstance(record,dict) or record.get('schema_version')!=1 or type(record.get('change')) is not int or record['change']<1:
        raise ValueError('约束目录中的规则记录无效')
    validate_snapshot(record.get('snapshot'))
    if type(record.get('archived',False)) is not bool:
        raise ValueError('约束归档状态无效')
    return record


def directory_records(project):
    from nbt_project.rooms import constraint_dirs, enclosed, RULE_FILE
    for directory in constraint_dirs(project):
        file=enclosed(directory,directory/RULE_FILE)
        info=file.stat()
        record=read_rule(file,info.st_size,info.st_mtime_ns,info.st_ctime_ns)
        if not directory.name.endswith('--'+record['snapshot']['id']):
            raise ValueError('约束编号与目录不符')
        yield directory,record


def save_directory_rule(project, snapshot, *, change=1, archived=False, scoped_room=None):
    from nbt_project.rooms import enclosed, numbered_directory, GROUPS, RULE_FILE
    validate_snapshot(snapshot)
    group=numbered_directory(Path(project)/GROUPS,snapshot['id'],snapshot['name'])
    archive_directory_revision(group,snapshot)
    write(enclosed(group,group/RULE_FILE),dict(schema_version=1,change=change,snapshot=snapshot,archived=archived,room_id=scoped_room))
    return group


def archive_directory_revision(group,snapshot):
    from nbt_project.rooms import enclosed
    validate_snapshot(snapshot)
    history=enclosed(group,group/'历史版本'/(str(snapshot['revision'])+'-'+snapshot['sha256']+'.json'))
    if history.exists():
        if content(json.loads(history.read_text(encoding='utf-8-sig')))!=content(snapshot):
            raise ValueError('约束历史版本已变化')
    else:
        write(history,snapshot)


def new_snapshot(folder,request,previous,items):
    name=request.get('name');rules=copy.deepcopy(request.get('rules'));validate_rules(rules)
    if not isinstance(name,str) or not 1<=len(name.strip())<=80:raise ValueError('约束名称须为1～80字')
    name=name.strip()
    identifier=request.get('id')
    if any(item['id']!=identifier and item['name']==name for item in items):raise ValueError('项目内已有同名约束')
    if previous and previous['name']==name and previous['rules']==rules:return previous
    if not previous and len(items)>=256:raise ValueError('每个项目最多256项约束')
    actor=request.get('actor','human')
    if actor not in ('human','agent'):raise ValueError('约束创建来源无效')
    item=dict(schema_version=1,id=identifier or 'constraint-'+uuid.uuid4().hex,revision=(previous['revision']+1 if previous else 1),name=name,rules=rules,updated_at=now(),actor=actor)
    if folder:item['folder']=folder
    item['sha256']=checksum(item)
    return item


def directory_dispatch(workspace,project,folder,action,request):
    from nbt_project.rooms import enclosing_room, GROUPS, SHAPE_NAMES
    scope_path=inside(workspace,folder) if folder else project
    room=enclosing_room(project,scope_path) if folder else None
    room_id=room[1]['id'] if room else None
    if folder and not scope_path.is_dir() and not (scope_path.parent==project and scope_path.name in SHAPE_NAMES):
        raise ValueError('找不到约束适用目录')

    def load(include_references=False):
        from nbt_project.rooms import enclosed
        all_records=[record for _,record in directory_records(project)]
        known={record['snapshot']['id'] for record in all_records}
        legacy=read_legacy_library(enclosed(project,scope_path/(FOLDER_FILE if folder else 'constraints.json')),folder) if room is None else dict(revision=0,items=[])
        records=[record for record in all_records
                 if (record['room_id']==room_id if record.get('room_id') else record['snapshot'].get('folder','')==folder)]
        visible=records
        if include_references and room:
            refs=set(room[1]['constraint_ids'])
            visible=[record for record in all_records if record in records or record['snapshot']['id'] in refs]
        items=[record['snapshot'] for record in visible if not record.get('archived',False)]
        items.extend(item for item in legacy['items'] if item['id'] not in known)
        return records,dict(schema_version=1,revision=legacy['revision']+sum(record['change'] for record in records),items=items)

    if action=='constraints-list':
        return list_result(load(include_references=request.get('include_references',False))[1],request)
    with index_lock(workspace,project/GROUPS):
        records,data=load()
        if type(request.get('revision')) is not int or request['revision']!=data['revision']:
            raise ValueError('项目约束已更新，请刷新后再保存')
        identifier=request.get('id')
        previous=next((item for item in data['items'] if item['id']==identifier),None)
        if identifier and not previous:raise ValueError('项目约束不存在，请刷新')
        if action=='constraints-delete':
            if not previous:raise ValueError('请选择要移除的项目约束')
            change=next((record['change'] for record in records if record['snapshot']['id']==identifier),0)
            save_directory_rule(project,previous,change=change+1,archived=True,scoped_room=room_id)
            return load()[1]
        item=new_snapshot(folder,request,previous,data['items'])
        if item!=previous:
            change=next((record['change'] for record in records if record['snapshot']['id']==identifier),0)
            save_directory_rule(project,item,change=change+1,scoped_room=room_id)
        return dict(load()[1],saved=item)


def dispatch(workspace,action,request):
    workspace=Path(workspace).resolve()
    if action=='constraints-registry':
        from nbt_project.constraint_registry import query
        return query(workspace,request)
    folder=request.get('folder','')
    fields={'constraints-list':{'folder','summary','id','include_references'},'constraints-save':{'folder','revision','id','name','rules','actor'},'constraints-delete':{'folder','revision','id'}}
    if action not in fields or set(request)-fields[action]:raise ValueError('未知项目约束操作或字段')
    if action=='constraints-list' and (any(type(request.get(key,False)) is not bool for key in ('summary','include_references')) or
                                      'id' in request and not valid_constraint_id(request['id'])):
        raise ValueError('规则查询参数无效')
    from nbt_project.rooms import empty_project, has_layout, init_layout, layout_project
    if folder!='':
        folder_parts(folder)
        source=inside(workspace,folder)
        grouped=layout_project(workspace,folder)
        if grouped is None and action=='constraints-save' and source.is_dir() and empty_project(source):
            # An existing shape directory remains a legacy scope.
            if source.name not in SHAPES:
                init_layout(source)
                grouped=source
        if grouped is not None:
            return directory_dispatch(workspace,grouped,folder,action,request)
        if relative(workspace,source)!=folder or not source.is_dir():
            raise ValueError('找不到项目文件夹，请刷新建筑库')
        file=inside(workspace,source/FOLDER_FILE)
        directory=inside(workspace,source/'.project-constraints')
        if file!=source/FOLDER_FILE or directory!=source/'.project-constraints':
            raise ValueError('项目约束路径不可使用链接')
    else:
        directory=inside(workspace,'nbt_models/_workspaces/project_design')
        if has_layout(directory):
            return directory_dispatch(workspace,directory,folder,action,request)
        file=inside(workspace,directory/'constraints.json')
    if action=='constraints-list':return list_result(read_legacy_library(file,folder),request)
    directory.mkdir(parents=True,exist_ok=True)
    with index_lock(workspace,directory):
        data=copy.deepcopy(read_legacy_library(file,folder))
        if type(request.get('revision')) is not int or request['revision']!=data['revision']:raise ValueError('项目约束已更新，请刷新后再保存')
        identifier=request.get('id');previous=next((item for item in data['items'] if item['id']==identifier),None)
        if identifier and not previous:raise ValueError('项目约束不存在，请刷新')
        if action=='constraints-delete':
            if not previous:raise ValueError('请选择要移除的项目约束')
            data['items'].remove(previous)
        else:
            item=new_snapshot(folder,request,previous,data['items'])
            if item==previous:return dict(data,saved=previous)
            archive=inside(workspace,directory/'constraint-revisions'/item['id']);archive.mkdir(parents=True,exist_ok=True)
            archived=inside(workspace,archive/(str(item['revision'])+'-'+item['sha256']+'.json'))
            if archived.exists():
                recovered=json.loads(archived.read_text(encoding='utf8'));validate_snapshot(recovered)
                if content(recovered)!=content(item):raise ValueError('项目约束修订归档已变化')
                item=recovered
            else:
                with archived.open('xb') as stream:stream.write(encode(item))
            data['items']=[item if old['id']==item['id'] else old for old in data['items']] if previous else [*data['items'],item]
        data['revision']+=1;write(file,data)
        return dict(data,**({'saved':item} if action=='constraints-save' else {}))
