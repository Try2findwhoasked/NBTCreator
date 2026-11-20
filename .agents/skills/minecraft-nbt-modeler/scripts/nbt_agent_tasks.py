"""Hash-bound external Agent task returns and independent human comment reconciliation."""
import argparse
import copy
from contextlib import contextmanager
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import uuid
from nbt_prompts import encode,digest,inside,relative,index_lock
from nbt_web_paths import project_paths
import nbt_agent_protocol as protocol

def now():return datetime.now(timezone.utc).isoformat()
def read(file):
    if file.stat().st_size>8*1024*1024:raise ValueError('Agent任务文件超过8MiB')
    return json.loads(file.read_text(encoding='utf-8-sig'))
def sha(file):
    h=hashlib.sha256()
    with file.open('rb') as stream:
        for raw in iter(lambda:stream.read(1024*1024),b''):h.update(raw)
    return h.hexdigest()
def load_index(workspace):
    file=workspace/'nbt_models/_workspaces/agent_tasks/index.json'
    index=read(file) if file.is_file() else dict(schema_version=1,tasks=[])
    if not isinstance(index,dict) or index.get('schema_version')!=1 or not isinstance(index.get('tasks'),list):raise ValueError('Agent任务索引无效')
    return file,index
def task_for(workspace,index,identifier):
    entry=next((entry for entry in index['tasks'] if entry['id']==identifier),None)
    if not entry:raise ValueError('Agent任务不存在')
    file=inside(workspace,entry['manifest']);raw=file.read_bytes()
    if digest(raw)!=entry['sha256']:raise ValueError('任务登记已变化，请核对来源')
    data=json.loads(raw)
    if data.get('schema_version')!=1 or data.get('id')!=identifier:raise ValueError('Agent任务格式无效')
    return data
def verify_binding(source,expected):
    if expected is None:return
    from nbt_refine import source_binding
    try:
        matches=source_binding(source)==expected
    except (ValueError,OSError):
        matches=False
    if not matches:protocol.error('SOURCE_CHANGED','任务模型、保护配置或墙层已变化，请建立新任务')

def return_parent(workspace,source,target):
    from nbt_working_model import managed_manifest
    source_paths,target_paths=project_paths(source),project_paths(target)
    if target_paths['version']==source_paths['version'] or target_paths['workdir']!=source_paths['workdir']:
        protocol.error('RETURN_LINEAGE_MISMATCH','回传制作版必须是同一建筑的新派生版本')
    manifest=managed_manifest(target)
    if not manifest and not managed_manifest(source):return source
    seen={target};parent=None
    while manifest and manifest.get('parent_source'):
        ancestor=inside(workspace,manifest['parent_source'])
        if (ancestor in seen or project_paths(ancestor)['workdir']!=project_paths(source)['workdir']
                or not ancestor.is_file() or sha(ancestor)!=manifest.get('parent_source_sha256')):break
        previous=managed_manifest(ancestor)
        if previous and previous['revision']!=manifest.get('parent_revision'):break
        if parent is None:parent=ancestor
        if ancestor==source:return parent
        seen.add(ancestor);manifest=previous
    protocol.error('RETURN_LINEAGE_MISMATCH','回传制作版必须从任务原版本派生，不能回传其祖先或其他分支')

def verify(workspace,data):
    source=inside(workspace,data['source'])
    if not source.is_file() or sha(source)!=data['source_sha256']:
        protocol.error('SOURCE_CHANGED','任务原建筑已变化，请保留原版本后重新建立任务')
    verify_binding(source,data.get('input_binding'))
    for origin in data.get('origins',[]):
        path=inside(workspace,origin['path'])
        if not path.is_file() or sha(path)!=origin['sha256']:
            protocol.error('SOURCE_CHANGED','原修改计划或校验包已变化，请核对任务来源')
    for entry in data['returns']:
        path=inside(workspace,entry['source'])
        if not path.is_file() or sha(path)!=entry['source_sha256']:
            protocol.error('SOURCE_CHANGED','已回传版本被覆盖，请使用新版本重新登记')
        verify_binding(path,entry.get('input_binding'))
    return source
def output(workspace,data):
    result=protocol.redact(data);result['absolute_source']=str(inside(workspace,data['source']));result['approval']='not_granted_by_task_registration'
    for entry in result['returns']:entry['absolute_source']=str(inside(workspace,entry['source']))
    return result

def record_return_history(workspace,data,entry):
    from nbt_history import record_produced_version
    source=verify(workspace,data);target=inside(workspace,entry['source'])
    parent=return_parent(workspace,source,target)
    return record_produced_version(workspace,target,parent=parent,message=entry['summary'],actor='external_agent',
                                   tasks=['agent:'+data['id']],set_current=False)

def repair_return_history(workspace,identifier,return_id):
    file,_=load_index(workspace)
    with index_lock(workspace,file.parent):
        _,index=load_index(workspace)
        data=task_for(workspace,index,identifier)
        entry=next((entry for entry in data['returns'] if entry['id']==return_id),None)
        if entry is None:protocol.error('RETURN_NOT_FOUND','任务回传版本不存在')
        return record_return_history(workspace,data,entry)

@contextmanager
def publication(workspace,building,source,session,actor):
    from nbt_working_model import publication_lock

    if session is None and (source is None or actor!='external_agent'):
        with publication_lock(workspace,building):yield lambda: None
        return
    file,_=load_index(workspace)
    file.parent.mkdir(parents=True,exist_ok=True)
    with index_lock(workspace,file.parent),publication_lock(workspace,building):
        _,index=load_index(workspace)
        check=lambda: None
        if session is None:
            for record in index['tasks']:
                if project_paths(inside(workspace,record['source']))['workdir']!=building:continue
                task=task_for(workspace,index,record['id'])
                if task.get('lease_managed') and task['status']!='completed':
                    protocol.error('LEASE_REQUIRED','该建筑有受租约管理的任务，保存制作版须提供 task_session')
        else:
            from nbt_task_client import TaskClient
            client=TaskClient(workspace,session);state=client.load()
            if state['kind']!='tasks' or state['phase']!='active' or state.get('pending'):
                protocol.error('SESSION_NOT_ACTIVE','保存修改任务制作版须使用有效的建筑修改任务会话')
            task=task_for(workspace,index,state['id']);base=verify(workspace,task)
            if source is None or project_paths(base)['workdir']!=building:
                protocol.error('RETURN_LINEAGE_MISMATCH','制作版与会话的原建筑不匹配')
            if source!=base:return_parent(workspace,base,source)
            def check():protocol.check_lease(task,client.lease_params(state),required=True)
        check()
        yield check

def commit(workspace,file,index,data,action,request,extras=None):
    data['revision']+=1;data['updated_at']=now();data['history'].append(dict(action=action,time=data['updated_at'],revision=data['revision']))
    directory=inside(workspace,data['directory']);directory.mkdir(parents=True,exist_ok=True);raw=encode(data)
    if len(raw)>8*1024*1024:raise ValueError('任务记录过大，请拆分任务')
    manifest=directory/('task-r'+str(data['revision']).zfill(4)+'-'+uuid.uuid4().hex[:8]+'.json')
    with manifest.open('xb') as stream:stream.write(raw)
    index['tasks']=[entry for entry in index['tasks'] if entry['id']!=data['id']]+[dict(id=data['id'],name=data['name'],source=data['source'],source_sha256=data['source_sha256'],manifest=relative(workspace,manifest),sha256=digest(raw))]
    result=output(workspace,data);result.update(extras or {})
    if action in ('claim','heartbeat'):result['lease_token']=data['lease']['token']
    protocol.receipt(workspace,index,'agent-tasks.'+action,request,result)
    raw_index=encode(index)
    if len(raw_index)>8*1024*1024:protocol.error('TASK_INDEX_LIMIT','建筑修改任务索引已达容量上限，未写入本次状态变更')
    temp=file.with_suffix('.'+uuid.uuid4().hex+'.tmp');temp.write_bytes(raw_index);temp.replace(file)
    return result
def comment_snapshot(workspace,source):
    from nbt_feedback_tasks import inventory
    _,comments=inventory(workspace,source)
    return [dict(key=entry['key'],content_sha256=entry['content_sha256'],text=entry['text'],anchors=entry['anchors'],verified=entry['verified'],geometry_matches_source=entry['geometry_matches_source']) for entry in comments]
def discover(workspace,data):
    source=verify(workspace,data);root=project_paths(source)['workdir'];base_version=project_paths(source)['version'];known={entry['source'] for entry in data['returns']};items=[]
    for folder,dirs,files in os.walk(root):
        dirs[:]=[name for name in dirs if name not in {'Agent交接','修改意见','delivery','runtime','parts','previews','validation','.git'} and not (Path(folder)/name).is_symlink()]
        for name in files:
            if not (name.lower().endswith(('.master.json.gz','.snbt')) or name in ('master_geometry.json.gz','refined.master.json.gz')):continue
            path=inside(workspace,Path(folder)/name)
            if path==source or project_paths(path)['version']==base_version or relative(workspace,path) in known:continue
            stat=path.stat();items.append(dict(source=relative(workspace,path),absolute_source=str(path),modified_ns=str(stat.st_mtime_ns),bytes=stat.st_size,status='unregistered_candidate',verified=False))
            if len(items)>=1000:return dict(candidates=items,truncated=True)
    return dict(candidates=sorted(items,key=lambda item:int(item['modified_ns']),reverse=True),truncated=False)

def dispatch(workspace,action,request):
    if not isinstance(request,dict) or action not in ('list','create','get','discover','record','review','claim','heartbeat','release'):raise ValueError('Agent任务请求无效')
    workspace=Path(workspace).resolve();file,index=load_index(workspace)
    if action=='list':
        source=relative(workspace,inside(workspace,request['source'])) if request.get('source') else None;tasks=[];errors=[]
        for entry in index['tasks']:
            try:
                data=task_for(workspace,index,entry['id'])
                if source and data['source']!=source and all(item['source']!=source for item in data['returns']):continue
                verify(workspace,data);tasks.append(output(workspace,data))
            except (ValueError,OSError,KeyError) as error:errors.append(dict(id=entry['id'],error=str(error)))
        return dict(tasks=tasks,errors=errors)
    if action in ('get','discover'):
        data=task_for(workspace,index,request['id']);verify(workspace,data)
        return discover(workspace,data) if action=='discover' else output(workspace,data)
    file.parent.mkdir(parents=True,exist_ok=True)
    with index_lock(workspace,file.parent):
        file,index=load_index(workspace)
        replay=protocol.replay(workspace,index,'agent-tasks.'+action,request)
        if replay is not None:return replay
        if action=='create':
            source=inside(workspace,request['source']);source_hash=sha(source)
            if request.get('source_sha256')!=source_hash:raise ValueError('原建筑已变化，请重新打开后交接')
            from nbt_refine import read_master,source_binding
            binding=source_binding(source)
            if binding['source_sha256']!=source_hash:protocol.error('SOURCE_CHANGED','建立任务期间源模型已变化')
            model,_=read_master(source);identifier=uuid.uuid4().hex;name=request.get('name','建筑修改任务')
            if not isinstance(name,str) or not name.strip() or len(name)>160:raise ValueError('任务名称须为1～160字')
            comments=comment_snapshot(workspace,source)
            origins=[]
            if not isinstance(request.get('origins',[]),list) or len(request.get('origins',[]))>8:raise ValueError('任务来源最多8项')
            for spec in request.get('origins',[]):
                file_path=inside(workspace,spec['path']);origins.append(dict(role=str(spec.get('role','plan'))[:80],path=relative(workspace,file_path),sha256=sha(file_path)))
            camera=request.get('camera')
            if camera is not None:
                import math
                if not isinstance(camera,dict) or any(not isinstance(camera.get(key),list) or len(camera[key])!=3 or any(type(n) not in (int,float) or not math.isfinite(n) for n in camera[key]) for key in ('eye','target','up')) or type(camera.get('fov')) not in (int,float) or not 1<=camera['fov']<=120:raise ValueError('任务相机须为有效eye/target/up/fov')
                camera={key:camera[key] for key in ('eye','target','up','fov')}
            data=dict(status='pending',schema_version=1,id=identifier,name=name.strip(),source=relative(workspace,source),source_sha256=source_hash,geometry_sha256=model.fingerprint(),size=list(model.size),directory=relative(workspace,project_paths(source)['version']/'Agent交接'/('task-'+identifier)),revision=0,created_at=now(),comments=comments,camera=camera,origins=origins,returns=[],history=[])
            verify_binding(source,binding);data['input_binding']=binding
        else:
            data=task_for(workspace,index,request['id']);source=verify(workspace,data)
            if action not in ('claim','heartbeat','release') or 'revision' in request:
                if request.get('revision')!=data['revision']:protocol.error('REVISION_CONFLICT','任务已更新，请刷新后核对再提交',retryable=True,details={'current_revision':data['revision']})
            if action in ('claim','heartbeat','release'):protocol.lease_action(data,action,request)
            elif action=='record':
                protocol.check_lease(data,request,required=bool(request.get('request_id')))
                from nbt_refine import read_master,source_binding
                target=inside(workspace,request['new_source']);paths=project_paths(source);new_paths=project_paths(target)
                if target==source or new_paths['version']==paths['version'] or new_paths['workdir']!=paths['workdir'] or any(part in ('delivery','runtime','parts','Agent交接') for part in target.relative_to(paths['workdir']).parts):raise ValueError('请回传同一建筑的新版本完整主模型，不是原稿、过程稿或交付副本')
                target_hash=sha(target)
                if request.get('new_source_sha256')!=target_hash:raise ValueError('回传文件哈希不匹配')
                return_parent(workspace,source,target)
                binding=source_binding(target)
                if binding['source_sha256']!=target_hash:protocol.error('SOURCE_CHANGED','登记期间回传模型已变化')
                if any(entry['source']==relative(workspace,target) for entry in data['returns']):raise ValueError('此版本已登记，不重复覆盖回传')
                model,_=read_master(target);claims=request.get('comments',[]);original={entry['key']:entry for entry in data['comments']}
                if not isinstance(claims,list) or len(claims)>5000 or len({entry['key'] for entry in claims})!=len(claims):raise ValueError('评论处理清单无效')
                current={entry['key']:entry for entry in comment_snapshot(workspace,source)}
                for claim in claims:
                    old=original.get(claim.get('key'))
                    if not old or claim.get('content_sha256')!=old['content_sha256'] or claim.get('status') not in ('addressed','deferred','not_applicable') or not isinstance(claim.get('note'),str) or not 1<=len(claim['note'])<=4000:raise ValueError('逐条处理须引用原评论哈希、状态和具体说明')
                    if not old['verified'] or not old['geometry_matches_source'] or not current.get(claim['key'],{}).get('verified') or current.get(claim['key'],{}).get('content_sha256')!=old['content_sha256']:raise ValueError('原评论证据已变化或未核验，请重新读取')
                summary=request.get('summary','')
                if not isinstance(summary,str) or not 1<=len(summary)<=8000:raise ValueError('请填写1～8000字的真实改动说明')
                if sha(target)!=target_hash or sha(source)!=data['source_sha256']:raise ValueError('登记期间模型已变化')
                verify(workspace,data);verify_binding(target,binding)
                protocol.check_lease(data,request,required=bool(request.get('request_id')))
                data['returns'].append(dict(id=uuid.uuid4().hex,source=relative(workspace,target),source_sha256=target_hash,input_binding=binding,geometry_sha256=model.fingerprint(),size=list(model.size),summary=summary,comments=claims,review={},created_at=now(),acceptance='pending_user_review'))
                data['status']='completed';data.pop('lease',None)
            elif action=='review':
                entry=next((entry for entry in data['returns'] if entry['id']==request.get('return_id')),None)
                if not entry:raise ValueError('回传版本不存在')
                key=request.get('comment_key');comment=next((item for item in data['comments'] if item['key']==key),None)
                if not comment or request.get('state') not in ('pending','accepted','rejected'):raise ValueError('请选择原评论及人工核对状态')
                current={item['key']:item for item in comment_snapshot(workspace,source)}
                if not comment['verified'] or not current.get(key,{}).get('verified') or current[key]['content_sha256']!=comment['content_sha256']:raise ValueError('原评论证据已变化，请先重新核对')
                note=request.get('note','')
                if not isinstance(note,str) or len(note)>4000:raise ValueError('核对备注最多4000字')
                entry['review'][key]=dict(state=request['state'],note=note,updated_at=now())
            else:raise ValueError('未知Agent任务操作')
        extras={}
        if action=='record':
            extras['version_history']=record_return_history(workspace,data,data['returns'][-1])
            extras['history_pending']=extras['version_history'].get('recorded') is False
        return commit(workspace,file,index,data,action,request,extras)

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--workspace',type=Path,default=Path.cwd());parser.add_argument('action',choices=['create','list','get','discover','record','review','claim','heartbeat','release']);parser.add_argument('--request',type=Path,required=True);args=parser.parse_args()
    try:print(json.dumps(dispatch(args.workspace,args.action,read(args.request)),ensure_ascii=False));return 0
    except (ValueError,OSError,KeyError,TypeError) as error:print(json.dumps(dict(error=str(error)),ensure_ascii=False));return 1
if __name__=='__main__':raise SystemExit(main())
