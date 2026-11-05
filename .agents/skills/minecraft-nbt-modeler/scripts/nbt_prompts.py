"""Archive workbench prompts and discover/read them without launching Electron."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import uuid
import copy
import time
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from nbt_web_paths import project_paths

def digest(raw):
    return hashlib.sha256(raw).hexdigest()

def encode(value):
    return (json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode('utf8')

def inside(workspace, value):
    root=Path(workspace).resolve();target=(root/Path(value)).resolve()
    if not target.is_relative_to(root/'nbt_models'):
        raise ValueError('提示词只能存取当前工作区 nbt_models 内的文件；外部模型请切换到对应工作区')
    return target

def relative(workspace, file):
    return Path(file).resolve().relative_to(Path(workspace).resolve()).as_posix()

@contextmanager
def index_lock(workspace,directory):
    target=inside(workspace,directory/'.write.lock')
    with target.open('a+b') as stream:
        if stream.seek(0,2)==0:stream.write(b'0');stream.flush()
        deadline=time.monotonic()+2
        while True:
            try:
                stream.seek(0)
                if os.name=='nt':
                    import msvcrt
                    msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1)
                else:
                    import fcntl
                    fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic()>=deadline:raise ValueError('提示词索引正在写入，请稍后重试') from None
                time.sleep(.01)
        try:yield
        finally:
            stream.seek(0)
            if os.name=='nt':msvcrt.locking(stream.fileno(),msvcrt.LK_UNLCK,1)
            else:fcntl.flock(stream,fcntl.LOCK_UN)

def save(workspace, payload):
    workspace=Path(workspace).resolve()
    session=payload.get('session_id','')
    if not re.fullmatch('[a-f0-9]{32}',session):raise ValueError('提示词任务编号无效')
    document=payload.get('document');text=payload.get('text')
    if not isinstance(document,dict) or not isinstance(document.get('project'),dict):raise ValueError('缺少提示词方案')
    if not isinstance(text,str) or not text.strip() or len(text.encode('utf8'))>512*1024:raise ValueError('提示词正文须非空且不超过512KiB')
    if len(encode(document))>2*1024*1024:raise ValueError('提示词方案超过2MiB')
    document=copy.deepcopy(document);project=document['project'];stage=project.get('stage');source=None;source_hash=None
    if stage not in ('draft','plan','refine'):raise ValueError('提示词阶段无效')
    if stage=='draft':
        catalog=json.loads((Path(__file__).resolve().parents[1]/'tool-catalog.json').read_text(encoding='utf8'))
        shape=project.get('buildingShape');name=project.get('name','')
        if shape not in catalog['building_shapes'] or not isinstance(name,str) or not name.strip():raise ValueError('填写建筑名称与有效形状')
        name=re.sub(r'[<>:"/\\|?*\x00-\x1f]','_',name).rstrip('. ')[:70] or '未命名建筑'
        if name in ('.','..'):raise ValueError('建筑名称无效')
        directory=inside(workspace,Path('nbt_models')/shape/name)/'提示词方案'
    else:
        source=inside(workspace,project.get('source',''))
        if not source.is_file():raise ValueError('源模型不存在，请重新载入当前建筑')
        source_hash=digest(source.read_bytes())
        if document.get('source_sha256') and document['source_sha256']!=source_hash:raise ValueError('源模型已变化，请重新载入当前建筑后导出提示词')
        directory=inside(workspace,project_paths(source)['version'])/'提示词方案'
    for key in ('source','contextPath','reviewPath','output'):
        value=project.get(key)
        if isinstance(value,str) and value and Path(value).is_absolute():
            resolved=Path(value).resolve()
            if resolved.is_relative_to(workspace):
                replacement=relative(workspace,resolved);project[key]=replacement;text=text.replace(value,replacement)
    directory=inside(workspace,directory);directory.mkdir(parents=True,exist_ok=True)
    index_file=directory/'提示词索引.json'
    with index_lock(workspace,directory):
        index=load_index(workspace,index_file)[1] if index_file.exists() else dict(schema_version=1,records=[])
        if index.get('schema_version')!=1 or not isinstance(index.get('records'),list):raise ValueError('提示词索引无效，未覆盖')
        files={'提示词.md':text.encode('utf8'),'方案.json':encode(document),'操作计划.json':encode(payload.get('plan',{})),'上下文草案.json':encode(payload.get('context',{}))}
        hashes={name:digest(raw) for name,raw in files.items()};revision=digest(encode(dict(files=hashes,source_sha256=source_hash)))
        folder=inside(workspace,directory/'修订'/session/revision);folder.mkdir(parents=True,exist_ok=True)
        for name,raw in files.items():
            target=inside(workspace,folder/name)
            try:
                with target.open('xb') as stream:stream.write(raw)
            except FileExistsError:
                if digest(target.read_bytes())!=hashes[name]:raise ValueError('已归档提示词修订被改动；未覆盖')
        if source and digest(source.read_bytes())!=source_hash:raise ValueError('导出期间源模型已变化，未更新提示词索引')
        previous=next((item for item in index['records'] if item.get('id')==session),None)
        record=dict(id=session,name=project.get('name',''),stage=stage,source=relative(workspace,source) if source else None,
                    source_sha256=source_hash,revision=revision,updated_at=datetime.now(timezone.utc).isoformat(),
                    files={name:dict(path=os.path.relpath(folder/name,directory).replace('\\','/'),sha256=hashes[name]) for name in files},
                    approval='not_granted_by_prompt',model_written=False)
        if previous and previous.get('revision')==revision:record=previous
        else:
            index['records']=[item for item in index['records'] if item.get('id')!=session]+[record]
            temporary=index_file.with_name(index_file.name+'.'+uuid.uuid4().hex+'.tmp')
            temporary.write_bytes(encode(index));temporary.replace(index_file)
        return dict(id=session,revision=revision,index=relative(workspace,index_file),directory=relative(workspace,directory),
                    prompt=relative(workspace,folder/'提示词.md'),source_sha256=source_hash,unchanged=bool(previous and previous.get('revision')==revision))

def load_index(workspace, file):
    file=inside(workspace,file)
    if file.name!='提示词索引.json' or file.parent.name!='提示词方案' or file.stat().st_size>4*1024*1024:raise ValueError('请选择扫描返回的提示词索引')
    data=json.loads(file.read_text(encoding='utf-8-sig'))
    if data.get('schema_version')!=1 or not isinstance(data.get('records'),list):raise ValueError('提示词索引格式无效')
    if any(not isinstance(item,dict) or not isinstance(item.get('id'),str) or not re.fullmatch('[a-f0-9]{32}',item['id']) or not isinstance(item.get('updated_at'),str) or not isinstance(item.get('files'),dict) for item in data['records']):raise ValueError('提示词索引记录无效')
    return file,data

def read_prompt(workspace,index,id):
    file,data=load_index(workspace,index);records=[item for item in data['records'] if item.get('id')==id]
    if len(records)!=1:raise ValueError('提示词编号不存在或不唯一，请重新扫描')
    record=records[0];contents={}
    for name in ('提示词.md','方案.json','操作计划.json','上下文草案.json'):
        item=record['files'][name];target=inside(workspace,file.parent/item['path'])
        if not target.is_relative_to(file.parent) or target.stat().st_size>2*1024*1024:raise ValueError('提示词产物路径或大小无效')
        raw=target.read_bytes()
        if digest(raw)!=item['sha256']:raise ValueError('提示词产物已变化，不能按原索引读取：'+name)
        contents[name]=raw.decode('utf8') if name.endswith('.md') else json.loads(raw)
    actual=None
    if record.get('source'):
        source=inside(workspace,record['source']);actual=digest(source.read_bytes()) if source.is_file() else None
    return dict(record=record,index=relative(workspace,file),source_matches=actual==record.get('source_sha256') if record.get('source') else None,
                text=contents['提示词.md'],document=contents['方案.json'],plan=contents['操作计划.json'],context=contents['上下文草案.json'],approval='not_granted_by_prompt')

def read_handoff(workspace,file,expected):
    target=inside(workspace,file)
    if target.name!='交给Agent.md' or 'Agent交接' not in target.parts or target.stat().st_size>512*1024:raise ValueError('请选择扫描返回的 Agent 交接提示词')
    raw=target.read_bytes()
    if digest(raw)!=expected:raise ValueError('交接提示词已变化，请重新扫描')
    return dict(file=relative(workspace,target),sha256=expected,text=raw.decode('utf8'),approval='not_granted_by_prompt')

def scan(workspace, source=None):
    workspace=Path(workspace).resolve();models=workspace/'nbt_models';items=[];errors=[]
    selected=relative(workspace,inside(workspace,source)) if source else None
    for directory,dirs,names in os.walk(models,followlinks=False):
        dirs[:]=[name for name in dirs if name not in {'_workspaces','_migration','修订','修改意见'} and not (Path(directory)/name).is_symlink()]
        if '交给Agent.md' in names and 'Agent交接' in Path(directory).parts:
            file=Path(directory)/'交给Agent.md'
            try:
                if file.stat().st_size>512*1024:raise ValueError('交接提示词过大')
                file=inside(workspace,file);request_file=file.parent/'request.json';request=json.loads(request_file.read_text(encoding='utf-8-sig')) if request_file.is_file() else {};bound_source=request.get('source');bound_source=relative(workspace,inside(workspace,bound_source)) if bound_source else None
                if not selected or selected==bound_source:items.append(dict(kind='handoff',file=relative(workspace,file),sha256=digest(file.read_bytes()),source=bound_source,source_sha256=request.get('source_sha256'),updated_at=datetime.fromtimestamp(file.stat().st_mtime,timezone.utc).isoformat()))
            except (OSError,ValueError) as error:errors.append(dict(file=relative(workspace,file),error=str(error)))
        if '提示词索引.json' not in names:continue
        file=Path(directory)/'提示词索引.json'
        try:
            _,data=load_index(workspace,file)
            for record in data['records']:
                if selected and record.get('source')!=selected:continue
                items.append({key:record.get(key) for key in ('id','name','stage','source','source_sha256','revision','updated_at')}|dict(kind='workbench',index=relative(workspace,file)))
        except (ValueError,OSError,KeyError) as error:errors.append(dict(index=relative(workspace,file),error=str(error)))
    return dict(schema_version=1,items=sorted(items,key=lambda item:item.get('updated_at') or '',reverse=True),errors=errors,full_text_loaded=False)


def task_index(workspace):
    return inside(workspace,'nbt_models/_workspaces/prompt_tasks/任务索引.json')


def load_tasks(workspace):
    file=task_index(workspace)
    if not file.exists():return dict(schema_version=1,records=[])
    if file.stat().st_size>4*1024*1024:raise ValueError('提示词任务索引超过4MiB')
    data=json.loads(file.read_text(encoding='utf8'))
    if data.get('schema_version')!=1 or not isinstance(data.get('records'),list):raise ValueError('提示词任务索引无效')
    for item in data['records']:
        if not isinstance(item,dict) or not re.fullmatch('[a-f0-9]{32}',str(item.get('id',''))) or type(item.get('sequence')) is not int or item['sequence']<1:raise ValueError('提示词任务记录无效')
    return data


def publish(workspace,index,identifier,revision):
    from nbt_project_batch import write
    archived=read_prompt(workspace,index,identifier)
    record=archived['record']
    if record['revision']!=revision:raise ValueError('提示词已更新，请重新保存当前任务')
    if archived['source_matches'] is False:raise ValueError('源模型已变化，不能交接旧提示词')
    task_id=uuid.uuid5(uuid.NAMESPACE_URL,archived['index']+':'+identifier+':'+revision).hex
    global_index=task_index(workspace);global_index.parent.mkdir(parents=True,exist_ok=True)
    with index_lock(workspace,global_index.parent):
        data=load_tasks(workspace)
        previous=next((item for item in data['records'] if item['id']==task_id),None)
        if previous:
            read_task(workspace,task_id)
            return dict(previous,unchanged=True)
        stamp=datetime.now(timezone(timedelta(hours=8))).strftime('%Y%m%d_%H%M%S')
        folder=inside(workspace,Path(index).parent/'任务'/(stamp+'_'+task_id[:12]));folder.mkdir(parents=True,exist_ok=True)
        files={}
        for name in ('提示词.md','方案.json','操作计划.json','上下文草案.json'):
            item=record['files'][name]
            raw=inside(workspace,Path(index).parent/item['path']).read_bytes()
            if digest(raw)!=item['sha256']:raise ValueError('提示词修订已变化，未发布任务')
            target=inside(workspace,folder/name)
            try:
                with target.open('xb') as stream:stream.write(raw)
            except FileExistsError:
                if digest(target.read_bytes())!=item['sha256']:raise ValueError('任务文件已存在不同内容，未覆盖')
            files[name]=dict(path=relative(workspace,target),sha256=item['sha256'])
        task=dict(id=task_id,sequence=max((item['sequence'] for item in data['records']),default=0)+1,
                  name=record['name'],stage=record['stage'],status='pending',created_at=datetime.now(timezone.utc).isoformat(),
                  directory=relative(workspace,folder),prompt=files['提示词.md']['path'],files=files,
                  archive_index=archived['index'],archive_id=identifier,revision=revision,source=record.get('source'),source_sha256=record.get('source_sha256'),
                  approval='not_granted_by_prompt',model_written=False)
        write(inside(workspace,folder/'任务.json'),task)
        data['records'].append(task);write(global_index,data)
        return dict(task,unchanged=False)


def tasks(workspace,after=0,status=None):
    if type(after) is not int or after<0:raise ValueError('任务游标须为非负整数')
    data=load_tasks(workspace)
    items=[{key:item[key] for key in ('id','sequence','name','stage','status','created_at','directory','prompt','revision')} for item in data['records'] if item['sequence']>after and (status is None or item['status']==status)]
    return dict(items=sorted(items,key=lambda item:item['sequence']),cursor=max((item['sequence'] for item in data['records']),default=0),full_text_loaded=False)


def read_task(workspace,identifier):
    record=next((item for item in load_tasks(workspace)['records'] if item['id']==identifier),None)
    if not record:raise ValueError('提示词任务不存在，请先 prompts tasks')
    folder=inside(workspace,record['directory']);contents={}
    for name in ('提示词.md','方案.json','操作计划.json','上下文草案.json'):
        item=record['files'][name];file=inside(workspace,item['path'])
        if not file.is_relative_to(folder) or file.stat().st_size>2*1024*1024:raise ValueError('任务文件路径或大小无效')
        raw=file.read_bytes()
        if digest(raw)!=item['sha256']:raise ValueError('任务文件已变化：'+name)
        contents[name]=raw.decode('utf8') if name.endswith('.md') else json.loads(raw)
    source=inside(workspace,record['source']) if record.get('source') else None
    matches=(digest(source.read_bytes())==record['source_sha256'] if source.is_file() else False) if source else None
    return dict(task=record,directory=str(folder),prompt=str(inside(workspace,record['prompt'])),text=contents['提示词.md'],document=contents['方案.json'],plan=contents['操作计划.json'],context=contents['上下文草案.json'],source_matches=matches,approval='not_granted_by_prompt')


def task_status(workspace,identifier,status):
    from nbt_project_batch import write
    if status not in ('pending','in_progress','completed'):raise ValueError('任务状态无效')
    file=task_index(workspace);file.parent.mkdir(parents=True,exist_ok=True)
    with index_lock(workspace,file.parent):
        data=load_tasks(workspace);item=next((item for item in data['records'] if item['id']==identifier),None)
        if not item:raise ValueError('提示词任务不存在')
        item['status']=status;write(inside(workspace,Path(item['directory'])/'任务.json'),item);write(file,data)
        return dict(id=identifier,status=status,approval='not_granted_by_prompt')

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--workspace',type=Path,default=Path.cwd());sub=parser.add_subparsers(dest='command',required=True)
    cmd=sub.add_parser('save');cmd.add_argument('--request',type=Path,required=True)
    cmd=sub.add_parser('scan');cmd.add_argument('--source')
    cmd=sub.add_parser('read');cmd.add_argument('--index');cmd.add_argument('--id');cmd.add_argument('--file');cmd.add_argument('--sha256')
    cmd=sub.add_parser('publish');cmd.add_argument('--index',required=True);cmd.add_argument('--id',required=True);cmd.add_argument('--revision',required=True)
    cmd=sub.add_parser('tasks');cmd.add_argument('--after',type=int,default=0);cmd.add_argument('--status',choices=['pending','in_progress','completed'])
    cmd=sub.add_parser('task');cmd.add_argument('--id',required=True)
    cmd=sub.add_parser('task-status');cmd.add_argument('--id',required=True);cmd.add_argument('--status',choices=['pending','in_progress','completed'],required=True)
    args=parser.parse_args()
    try:
        if args.command=='read' and not ((args.index and args.id and not args.file) or (args.file and args.sha256 and not args.index)):raise ValueError('read 使用 --index/--id，或交接文件的 --file/--sha256')
        if args.command=='publish':result=publish(args.workspace,args.index,args.id,args.revision)
        elif args.command=='tasks':result=tasks(args.workspace,args.after,args.status)
        elif args.command=='task':result=read_task(args.workspace,args.id)
        elif args.command=='task-status':result=task_status(args.workspace,args.id,args.status)
        else:result=save(args.workspace,json.loads(args.request.read_text(encoding='utf-8-sig'))) if args.command=='save' else scan(args.workspace,args.source) if args.command=='scan' else read_handoff(args.workspace,args.file,args.sha256) if args.file else read_prompt(args.workspace,args.index,args.id)
        print(json.dumps(result,ensure_ascii=False));return 0
    except (ValueError,OSError,KeyError,TypeError) as error:print(json.dumps(dict(error=str(error)),ensure_ascii=False));return 1

if __name__=='__main__':raise SystemExit(main())
