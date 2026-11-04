"""Registered modelling batches: process workspaces, model links and deliveries."""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import time
import uuid
from nbt_prompts import encode, digest, index_lock
from nbt_web_paths import project_paths

STATUSES={'authoring','review','delivered','failed','cancelled'}
ROLES={'gallery','archive','report','script','design','preview','other'}
SHAPES={'single','long','square','l_shape','t_shape','cross','irregular','standalone','bugged'}

def workspace_root(value):
    path=Path(value).resolve();roots=[p.parent for p in [path,*path.parents] if p.name.lower()=='nbt_models']
    return roots[-1] if roots else path

def local(workspace,value):
    path=(workspace/Path(value)).resolve()
    if not path.is_relative_to(workspace/'nbt_models'):
        parts=str(value).replace('\\','/').split('/')
        if 'nbt_models' in parts:path=workspace.joinpath(*parts[parts.index('nbt_models'):]).resolve()
    if not path.is_relative_to(workspace/'nbt_models'):raise ValueError('批次文件须位于当前工作区 nbt_models 内')
    return path

def rel(workspace,path):return Path(path).resolve().relative_to(workspace).as_posix()
def now():return datetime.now(timezone.utc).isoformat()
def sha(file):
    h=hashlib.sha256()
    with Path(file).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def read(file):
    if file.stat().st_size>4*1024*1024:raise ValueError('批次登记超过4MiB')
    return json.loads(file.read_text(encoding='utf-8-sig'))

def index(workspace):
    file=workspace/'nbt_models/_workspaces/batches/index.json'
    data=read(file) if file.is_file() else dict(schema_version=1,revision=0,tasks=[],seen_models=[],seen_tasks=[])
    if data.get('schema_version')!=1 or not isinstance(data.get('tasks'),list):raise ValueError('批次索引格式无效')
    return file,data

def task_document(workspace,entry):
    file=local(workspace,entry['manifest'])
    if file.stat().st_size>4*1024*1024:raise ValueError('批次登记超过4MiB')
    raw=file.read_bytes()
    if digest(raw)!=entry['manifest_sha256']:raise ValueError('批次登记已被修改，请重新导入核对')
    task=json.loads(raw)
    if task.get('schema_version')!=1 or task.get('id')!=entry['id'] or task.get('status') not in STATUSES:raise ValueError('批次登记格式无效')
    directory=local(workspace,task['workspace_dir'])
    if not (file==directory/'task.json' or file.parent==directory/'runs/manifests') or not directory.is_relative_to(workspace/'nbt_models/_workspaces') or directory in (workspace/'nbt_models/_workspaces',workspace/'nbt_models/_workspaces/batches'):raise ValueError('批次应有独立的过程工作目录')
    if any(not isinstance(task.get(key),list) for key in ('models','artifacts','history','runs')):raise ValueError('批次登记列表格式无效')
    for item in task['models']:local(workspace,item['source'])
    for item in task['artifacts']:local(workspace,item['path'])
    return file,task

def current(workspace,item,path_key,verify=False):
    file=local(workspace,item[path_key])
    if not file.is_file():return 'missing'
    stat=file.stat()
    if verify:return 'verified' if sha(file)==item['sha256'] else 'changed'
    return 'unchanged' if str(stat.st_mtime_ns)==item['mtime_ns'] and stat.st_size==item['bytes'] else 'needs_verification'

def summary(workspace,task,file,raw):
    return dict(id=task['id'],name=task['name'],workspace_dir=task['workspace_dir'],manifest=rel(workspace,file),manifest_sha256=digest(raw),status=task['status'],created_at=task['created_at'],updated_at=task['updated_at'],legacy=task.get('legacy',False),model_count=len(task['models']),artifact_count=len(task['artifacts']),revision=task['revision'])

def persist(workspace,index_file,registry,task,action):
    directory=local(workspace,task['workspace_dir']);task['updated_at']=now();task['revision']+=1
    events=directory/'runs/events';events.mkdir(parents=True,exist_ok=True)
    event=encode(dict(action=action,revision=task['revision'],time=task['updated_at'],models=[item['id'] for item in task['models']],artifacts=[item['id'] for item in task['artifacts']]))
    event_file=events/(str(task['revision']).zfill(5)+'_'+uuid.uuid4().hex[:8]+'.json')
    with event_file.open('xb') as stream:stream.write(event)
    task['history'].append(dict(file=rel(workspace,event_file),sha256=digest(event)))
    raw=encode(task)
    if len(raw)>4*1024*1024:raise ValueError('批次登记超过4MiB，请拆分为多个批次')
    manifests=directory/'runs/manifests';manifests.mkdir(exist_ok=True)
    file=manifests/(str(task['revision']).zfill(5)+'_'+uuid.uuid4().hex[:8]+'.json')
    with file.open('xb') as stream:stream.write(raw)
    registry['tasks']=[entry for entry in registry['tasks'] if entry['id']!=task['id']]+[summary(workspace,task,file,raw)]
    write_index(index_file,registry)
    mirror=directory/'task.json';temporary=mirror.with_name(mirror.name+'.'+uuid.uuid4().hex+'.tmp');temporary.write_bytes(raw);temporary.replace(mirror)

def write_index(file,data):
    data['revision']+=1;temporary=file.with_name(file.name+'.'+uuid.uuid4().hex+'.tmp');temporary.write_bytes(encode(data));temporary.replace(file)

def details(workspace,task,registry,verify=False):
    value=copy.deepcopy(task);value['absolute_workspace']=str(local(workspace,task['workspace_dir']))
    for item in value['models']:
        item['absolute_source']=str(local(workspace,item['source']));item['file_status']=current(workspace,item,'source',verify)
        age=time.time_ns()-int(item['added_ns']);key=item['source']+':'+item['sha256']
        item['is_new']=item['kind']=='formal' and item.get('highlight_eligible',False) and 0<=age<=7*86400*10**9 and key not in registry['seen_models'] and item['file_status'] in ('unchanged','verified')
    for item in value['artifacts']:item['absolute_path']=str(local(workspace,item['path']));item['file_status']=current(workspace,item,'path',verify)
    age=time.time_ns()-int(task['created_ns']);value['is_new']=any(item['is_new'] for item in value['models']) or 0<=age<=7*86400*10**9 and task['id'] not in registry['seen_tasks'] and not task.get('legacy',False)
    value['approval']='not_granted_by_registration'
    return value

def add_model(workspace,task,spec,highlight_existing=False):
    from nbt_refine import read_master
    source=local(workspace,spec['source']);kind=spec.get('kind','formal');directory=local(workspace,task['workspace_dir'])
    if kind=='intermediate':
        if not source.is_relative_to(directory):raise ValueError('中间模型应保存在本批次工作目录内')
    elif kind=='formal':
        parts=source.relative_to(workspace/'nbt_models').parts
        if not parts or parts[0] not in SHAPES or any(name in parts[1:] for name in ('delivery','runtime','parts','exports')):raise ValueError('正式关联必须指向作者模型库的完整主模型，不能使用过程稿或交付副本')
    else:raise ValueError('模型类型须为formal或intermediate')
    before=sha(source)
    if spec.get('sha256') and spec['sha256']!=before:raise ValueError('模型文件与登记哈希不一致')
    model,walls=read_master(source);geometry=model.fingerprint()
    if spec.get('geometry_sha256') and spec['geometry_sha256']!=geometry:raise ValueError('模型几何与清单不一致')
    if sha(source)!=before:raise ValueError('读取期间模型已变化')
    source_rel=rel(workspace,source);previous=next((item for item in task['models'] if item['source']==source_rel and item['sha256']==before),None)
    if previous:return previous
    if any(item['source']==source_rel for item in task['models']):raise ValueError('已登记模型被覆盖，请保留原版本并使用新的模型版本或run目录')
    paths=project_paths(source);stat=source.stat();created=time.time_ns();name=spec.get('name') or paths['workdir'].name
    item=dict(id=uuid.uuid4().hex,name=str(name)[:160],source=source_rel,version_dir=rel(workspace,paths['version']),sha256=before,geometry_sha256=geometry,size=list(model.size),kind=kind,bytes=stat.st_size,mtime_ns=str(stat.st_mtime_ns),added_ns=str(created),highlight_eligible=kind=='formal' and (highlight_existing or not task.get('legacy') and stat.st_mtime_ns>=int(task['created_ns'])))
    task['models'].append(item);return item

def add_artifact(workspace,task,spec):
    file=local(workspace,spec['path']);role=spec.get('role','other')
    if role not in ROLES or not file.is_file():raise ValueError('产物角色无效或文件不存在')
    value=sha(file)
    if spec.get('sha256') and spec['sha256']!=value:raise ValueError('交付产物与清单哈希不一致')
    path=rel(workspace,file);previous=next((item for item in task['artifacts'] if item['path']==path),None)
    if previous:
        if previous['sha256']!=value:raise ValueError('已登记产物被覆盖，请使用新的run目录或文件名')
        return previous
    stat=file.stat();item=dict(id=uuid.uuid4().hex,name=str(spec.get('name') or file.name)[:200],role=role,path=path,sha256=value,bytes=stat.st_size,mtime_ns=str(stat.st_mtime_ns));task['artifacts'].append(item);return item

def discover(workspace):
    base=workspace/'nbt_models/_workspaces';_,registry=index(workspace);known={entry['workspace_dir'] for entry in registry['tasks']};candidates=[]
    roots=[base,base/'batches']
    for root in roots:
        if not root.is_dir():continue
        for directory in sorted(root.iterdir()):
            if not directory.is_dir() or directory.is_symlink() or directory.name.startswith('.') or rel(workspace,directory) in known:continue
            catalogs=list(directory.glob('*_catalog.json'));galleries=list(directory.glob('*_gallery.html'))
            if not catalogs and not (directory/'task.json').is_file():continue
            candidates.append(dict(name=directory.name,workspace_dir=rel(workspace,directory),catalog=rel(workspace,catalogs[0]) if catalogs else None,gallery=rel(workspace,galleries[0]) if galleries else None,registered=False,is_new=False))
    nested=[str(base/name) for name in ('.agents','.nbtcreator','nbt_models') if (base/name).is_dir()]
    return dict(candidates=candidates,nested_workspaces=nested,batch_root=str(base/'batches'))

def dispatch(workspace,action,request):
    if not isinstance(request,dict):raise ValueError('批次请求须为JSON对象')
    if action not in ('create','import','list','get','record','run','ack','locate','discover'):raise ValueError('未知批次操作')
    workspace=workspace_root(workspace);index_file,registry=index(workspace);batch_root=index_file.parent
    if action=='discover':return discover(workspace)
    if action=='list':
        tasks=[];errors=[]
        for entry in registry['tasks']:
            try:
                file,task=task_document(workspace,entry);tasks.append(details(workspace,task,registry))
            except (ValueError,OSError,KeyError,TypeError,AttributeError) as error:errors.append(dict(id=entry.get('id'),error=str(error)))
        return dict(tasks=tasks,errors=errors,**discover(workspace))
    if action in ('get','locate'):
        entry=next((entry for entry in registry['tasks'] if entry['id']==request.get('id')),None)
        if not entry:raise ValueError('批次未登记或不存在')
        file,task=task_document(workspace,entry)
        if action=='get':return details(workspace,task,registry,request.get('verify') is True)
        if request.get('kind')=='workspace':return dict(path=str(local(workspace,task['workspace_dir'])),kind='directory')
        key='models' if request.get('kind')=='model' else 'artifacts';item=next((item for item in task[key] if item['id']==request.get('item_id')),None)
        if not item:raise ValueError('批次产物不存在')
        path_key='source' if key=='models' else 'path'
        if current(workspace,item,path_key,True)!='verified':raise ValueError('产物已缺失或变化，请先核对任务登记')
        return dict(path=str(local(workspace,item[path_key])),kind='file',sha256=item['sha256'],role=item.get('role','model'))
    batch_root.mkdir(parents=True,exist_ok=True)
    with index_lock(workspace,batch_root):
        index_file,registry=index(workspace)
        if action in ('create','import'):
            name=request.get('name','')
            if not isinstance(name,str):raise ValueError('批次名称须为文字')
            name=name.strip()
            if not name or len(name)>160:raise ValueError('填写1～160字的批次名称')
            task_id=uuid.uuid4().hex;created_ns=time.time_ns()
            if action=='import':
                directory=local(workspace,request['workspace_dir'])
                if directory in (workspace/'nbt_models/_workspaces',batch_root) or not directory.is_relative_to(workspace/'nbt_models/_workspaces') or not directory.is_dir():raise ValueError('请选择独立的已有批次目录')
                if (directory/'task.json').exists():
                    file=directory/'task.json';recovered=read(file)
                    if any(entry['id']==recovered.get('id') for entry in registry['tasks']):raise ValueError('此批次已登记，请打开已登记任务')
                    _,task=task_document(workspace,dict(manifest=rel(workspace,file),manifest_sha256=sha(file),id=recovered.get('id')))
                    if any(current(workspace,item,'source',True)!='verified' for item in task['models']) or any(current(workspace,item,'path',True)!='verified' for item in task['artifacts']):raise ValueError('待恢复批次的文件已变化，请先核对')
                    persist(workspace,index_file,registry,task,'recover');return details(workspace,task,registry)
            else:
                slug=re.sub(r'[<>:"/\\|?*\x00-\x1f]','_',name).rstrip('. ')[:64] or 'batch';directory=batch_root/(datetime.now().astimezone().strftime('%Y-%m-%d_')+slug+'_'+task_id[:8]);directory.mkdir()
            task=dict(schema_version=1,id=task_id,name=name,workspace_dir=rel(workspace,directory),status='authoring',created_at=now(),created_ns=str(created_ns),updated_at=now(),revision=0,legacy=action=='import',models=[],artifacts=[],runs=[],history=[],approval='not_granted_by_registration')
            for name in ('scripts','design','validation','previews','intermediate','deliverables','runs'):(directory/name).mkdir(exist_ok=True)
            if action=='import' and request.get('catalog'):
                catalog=local(workspace,request['catalog']);rows=read(catalog)
                if not catalog.is_relative_to(directory) or not isinstance(rows,list) or len(rows)>1000:raise ValueError('请选择本批次的模型catalog清单')
                for row in rows:add_model(workspace,task,dict(source=row['master'],name=row.get('name_zh'),sha256=row.get('master_sha256'),geometry_sha256=row.get('geometry_sha256')),request.get('highlight_existing') is True)
                add_artifact(workspace,task,dict(path=str(catalog),role='report'))
            if request.get('gallery'):add_artifact(workspace,task,dict(path=request['gallery'],role='gallery'))
            if action=='import':
                for file in directory.iterdir():
                    if not file.is_file() or file.name=='task.json':continue
                    role='archive' if file.suffix.lower()=='.zip' else 'gallery' if 'gallery' in file.stem and file.suffix.lower() in ('.html','.htm','.png','.jpg','.jpeg') else 'report' if file.suffix.lower()=='.json' else 'preview' if file.suffix.lower() in ('.png','.jpg','.jpeg') else None
                    if role:add_artifact(workspace,task,dict(path=str(file),role=role))
        else:
            entry=next((entry for entry in registry['tasks'] if entry['id']==request.get('id')),None)
            if not entry:raise ValueError('批次不存在')
            file,task=task_document(workspace,entry)
            if action=='ack':
                registry['seen_tasks']=list(set(registry['seen_tasks'])|{task['id']})
                ids=request.get('model_ids',[]);keys={item['source']+':'+item['sha256'] for item in task['models'] if request.get('all') is True or item['id'] in ids};registry['seen_models']=list(set(registry['seen_models'])|keys);write_index(index_file,registry);return details(workspace,task,registry)
            if request.get('revision')!=task['revision']:raise ValueError('批次已更新，请刷新后再登记')
            if action=='run':
                run_id=uuid.uuid4().hex;stage=request.get('stage','attempt')
                if not re.fullmatch('[a-z][a-z0-9_-]{0,39}',stage):raise ValueError('run阶段名无效')
                directory=local(workspace,task['workspace_dir'])/'runs'/(datetime.now().astimezone().strftime('%Y-%m-%d_%H%M%S_')+stage+'_'+run_id[:8]);directory.mkdir();task['runs'].append(dict(id=run_id,stage=stage,directory=rel(workspace,directory),status='authoring',created_at=now(),models=[],artifacts=[]))
            elif action=='record':
                models=request.get('models',[]);artifacts=request.get('artifacts',[])
                if not isinstance(models,list) or len(models)>1000 or not isinstance(artifacts,list) or len(artifacts)>1000:raise ValueError('单次登记最多1000个模型或产物')
                linked_models=[add_model(workspace,task,item) for item in models];linked_artifacts=[add_artifact(workspace,task,item) for item in artifacts]
                if request.get('status'):
                    if request['status'] not in STATUSES:raise ValueError('批次状态无效')
                    task['status']=request['status']
                if request.get('run_id'):
                    run=next((run for run in task['runs'] if run['id']==request['run_id']),None)
                    if not run:raise ValueError('run不存在')
                    run['models']=list(set(run['models'])|{item['id'] for item in linked_models});run['artifacts']=list(set(run['artifacts'])|{item['id'] for item in linked_artifacts});run['status']=task['status']
            else:raise ValueError('未知批次操作')
        persist(workspace,index_file,registry,task,action);return details(workspace,task,registry)

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--workspace',type=Path,default=Path.cwd());parser.add_argument('action',choices=['create','import','list','get','record','run','ack','locate','discover']);parser.add_argument('--request',type=Path);args=parser.parse_args()
    try:print(json.dumps(dispatch(args.workspace,args.action,read(args.request) if args.request else {}),ensure_ascii=False));return 0
    except (ValueError,OSError,KeyError,TypeError,AttributeError) as error:print(json.dumps(dict(error=str(error)),ensure_ascii=False));return 1
if __name__=='__main__':raise SystemExit(main())
