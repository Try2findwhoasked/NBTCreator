"""Hash-bound external Agent task returns and independent human comment reconciliation."""
import argparse
import copy
from contextlib import contextmanager,nullcontext
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
def index_entry(index,identifier):
    entry=next((entry for entry in index['tasks'] if entry['id']==identifier),None)
    if not entry:protocol.error('TASK_NOT_FOUND','建筑修改任务不存在，请先 task-client list')
    return entry

def manifest_bytes(file):
    with file.open('rb') as stream:
        raw=stream.read(8*1024*1024+1)
    if len(raw)>8*1024*1024:raise ValueError('任务登记超过8MiB')
    return raw

def task_for(workspace,index,identifier):
    entry=index_entry(index,identifier)
    file=inside(workspace,entry['manifest'])
    try:raw=manifest_bytes(file)
    except (ValueError,OSError):raw=None
    if raw is None or digest(raw)!=entry['sha256']:
        protocol.error('TASK_INVALID','任务登记已变化或无法读取，请按索引哈希恢复',
                       details=dict(manifest=entry['manifest'],expected_sha256=entry['sha256'],
                                    recovery=f"task-client recover-registration {identifier} --expected {entry['sha256']}"))
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

def registered_building(workspace,record):
    if record.get('building'):return inside(workspace,record['building'])
    source=inside(workspace,record['source'])
    version=(inside(workspace,record['directory']).parents[1] if 'directory' in record else
             inside(workspace,record['manifest']).parents[2])
    root=project_paths(source)['workdir']
    if root==version and version.name.startswith(('版本_','v_')):return version.parent
    return root

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

def verify_source(workspace,data):
    source=inside(workspace,data['source'])
    if not source.is_file() or sha(source)!=data['source_sha256']:
        protocol.error('SOURCE_CHANGED','任务原建筑已变化，请保留原版本后重新建立任务',details={'path':data['source']})
    verify_binding(source,data.get('input_binding'))
    return source

def check_publication_owner(workspace,index,task,target,request):
    from nbt_working_model import managed_manifest
    manifest=managed_manifest(target)
    expected=dict(task_id=task['id'],fence=request.get('fence'),source_sha256=task['source_sha256'])
    if manifest:
        matches=manifest.get('agent_publication')==expected
    else:
        receipt=inside(workspace,project_paths(target)['version']/'agent-publication.json')
        if receipt.is_file():
            from nbt_refine import source_binding
            matches=read(receipt)==dict(publication=expected,source=relative(workspace,target),binding=source_binding(target))
        else:
            # Historical standalone tools can produce a new raw model for a
            # first handoff. Once there are competing handoffs/lease epochs,
            # a raw file cannot establish which assignment produced it.
            root=registered_building(workspace,task)
            prior=task.get('existing_raw_candidates',{})
            matches=(not prior.get('truncated') and relative(workspace,target) not in prior.get('paths',[])
                     and task.get('lease_epoch',0)<=1) and not any(
                entry['id']!=task['id'] and registered_building(workspace,entry)==root for entry in index['tasks'])
    if not matches:
        protocol.error('CANDIDATE_REVALIDATION_REQUIRED','候选缺少本次领取的制作凭据。请用 check-candidate 核对旧候选，或从任务原稿用当前会话另存制作版。')

def verify(workspace,data):
    source=verify_source(workspace,data)
    for origin in data.get('origins',[]):
        path=inside(workspace,origin['path'])
        if not path.is_file() or sha(path)!=origin['sha256']:
            protocol.error('SOURCE_CHANGED','原修改计划或校验包已变化，请核对任务来源',
                           details={'path':origin['path'],'role':origin['role']})
    for entry in data['returns']:
        path=inside(workspace,entry['source'])
        if not path.is_file() or sha(path)!=entry['source_sha256']:
            protocol.error('SOURCE_CHANGED','已回传版本被覆盖，请使用新版本重新登记',details={'path':entry['source'],'return_id':entry['id']})
        verify_binding(path,entry.get('input_binding'))
    return source
def output(workspace,data):
    result=protocol.redact(data);result['absolute_source']=str(inside(workspace,data['source']));result['approval']='not_granted_by_task_registration'
    result.pop('existing_raw_candidates',None)
    for entry in result['returns']:entry['absolute_source']=str(inside(workspace,entry['source']))
    return result

def record_return_history(workspace,data,entry):
    from nbt_history import record_produced_version
    source=verify(workspace,data);target=inside(workspace,entry['source'])
    parent=return_parent(workspace,source,target)
    return record_produced_version(workspace,target,parent=parent,message=entry['summary'],actor='external_agent',
                                   tasks=['agent:'+data['id']],set_current=False)

def repair_return_history(workspace,identifier,return_id):
    file,initial=load_index(workspace)
    with task_building_lock(workspace,initial,identifier),index_lock(workspace,file.parent):
        _,index=load_index(workspace)
        data=task_for(workspace,index,identifier)
        entry=next((entry for entry in data['returns'] if entry['id']==return_id),None)
        if entry is None:protocol.error('RETURN_NOT_FOUND','任务回传版本不存在')
        return record_return_history(workspace,data,entry)

def task_building_lock(workspace,index,identifier):
    from nbt_working_model import publication_lock
    return publication_lock(workspace,registered_building(workspace,index_entry(index,identifier)))

@contextmanager
def publication(workspace,building,source,session,actor):
    from nbt_working_model import publication_lock
    workspace,building=Path(workspace).resolve(),Path(building).resolve()

    if session is None and source is None:
        with publication_lock(workspace,building):yield lambda: None
        return
    file,_=load_index(workspace)
    file.parent.mkdir(parents=True,exist_ok=True)
    # Desktop conversion may already own the reentrant building lock. Writers
    # take it before the registry so a waiting CLI never blocks its publisher.
    with publication_lock(workspace,building),index_lock(workspace,file.parent):
        _,index=load_index(workspace)
        check=lambda: None
        if session is None:
            for record in index['tasks']:
                if registered_building(workspace,record)!=building:continue
                task=task_for(workspace,index,record['id'])
                if protocol.lease_active(task):
                    protocol.error('LEASE_REQUIRED','该建筑有有效租约；使用领取会话保存，或释放租约后重试',
                                   details={'id':task['id'],'lease':protocol.public_lease(task)})
        else:
            from nbt_task_client import TaskClient
            client=TaskClient(workspace,session);state=client.load()
            if state['kind']!='tasks' or state['phase']!='active' or state.get('pending'):
                protocol.error('SESSION_NOT_ACTIVE','保存修改任务制作版须使用有效的建筑修改任务会话')
            task=task_for(workspace,index,state['id']);base=verify(workspace,task)
            if source is None or project_paths(base)['workdir']!=building:
                protocol.error('RETURN_LINEAGE_MISMATCH','制作版与会话的原建筑不匹配')
            if source!=base:return_parent(workspace,base,source)
            def check():
                params=client.lease_params(state)
                protocol.check_lease(task,params,required=True)
                return dict(task_id=task['id'],fence=params['fence'],source_sha256=task['source_sha256'])
        check()
        yield check

def checkpoint(workspace,file,expected):
    return inside(workspace,file.parent/'checkpoints'/(expected+'.json'))

def persist_index(file,index):
    raw_index=encode(index)
    if len(raw_index)>8*1024*1024:protocol.error('TASK_INDEX_LIMIT','建筑修改任务索引已达容量上限，未写入本次状态变更')
    temp=file.with_suffix('.'+uuid.uuid4().hex+'.tmp')
    try:
        temp.write_bytes(raw_index)
        temp.replace(file)
    finally:temp.unlink(missing_ok=True)

def recover_registration(workspace,file,index,request):
    entry=index_entry(index,request['id'])
    expected=entry['sha256']
    if expected!=request.get('expected_sha256'):
        protocol.error('REVISION_CONFLICT','索引已指向不同的任务修订，请重新定位')
    original=inside(workspace,entry['manifest'])
    sources=[original,checkpoint(workspace,file,expected)]
    if request.get('backup'):sources.append(inside(workspace,request['backup']))
    for source in sources:
        try:
            raw=manifest_bytes(source)
            if digest(raw)!=expected:raw=encode(json.loads(raw))
            if digest(raw)==expected:break
        except (OSError,ValueError,RecursionError):pass
    else:
        protocol.error('TASK_RECOVERY_UNPROVEN','未找到匹配当前索引的登记原文。请提供该修订的备份；写入仍受阻。',
                       details=dict(manifest=entry['manifest'],expected_sha256=expected))
    # Publish a new pointer while preserving the damaged artifact. Never derive
    # a lease, epoch or status from unverified data or from an older revision.
    new_file=inside(workspace,original.with_name('task-restored-'+uuid.uuid4().hex+'.json'))
    new_file.parent.mkdir(parents=True,exist_ok=True)
    with new_file.open('xb') as stream:stream.write(raw)
    previous=entry['manifest']
    entry['manifest']=relative(workspace,new_file)
    restored=task_for(workspace,index,entry['id'])
    result=dict(id=entry['id'],revision=restored['revision'],sha256=expected,
                manifest=entry['manifest'],previous_manifest=previous,active_lease=protocol.lease_active(restored))
    protocol.receipt(workspace,index,'agent-tasks.recover',request,result)
    persist_index(file,index)
    return result

def commit(workspace,file,index,data,action,request,extras=None):
    data['revision']+=1;data['updated_at']=now();data['history'].append(dict(action=action,time=data['updated_at'],revision=data['revision']))
    directory=inside(workspace,data['directory']);directory.mkdir(parents=True,exist_ok=True);raw=encode(data)
    if len(raw)>8*1024*1024:raise ValueError('任务记录过大，请拆分任务')
    manifest=directory/('task-r'+str(data['revision']).zfill(4)+'-'+uuid.uuid4().hex[:8]+'.json')
    with manifest.open('xb') as stream:stream.write(raw)
    backup=checkpoint(workspace,file,digest(raw))
    backup.parent.mkdir(parents=True,exist_ok=True)
    try:
        with backup.open('xb') as stream:stream.write(raw)
    except FileExistsError:
        if manifest_bytes(backup)!=raw:raise ValueError('任务恢复副本已损坏')
    index['tasks']=[entry for entry in index['tasks'] if entry['id']!=data['id']]+[dict(id=data['id'],name=data['name'],building=relative(workspace,registered_building(workspace,data)),source=data['source'],source_sha256=data['source_sha256'],manifest=relative(workspace,manifest),sha256=digest(raw))]
    result=output(workspace,data);result.update(extras or {})
    if action in ('claim','heartbeat'):result['lease_token']=data['lease']['token']
    protocol.receipt(workspace,index,'agent-tasks.'+action,request,result)
    persist_index(file,index)
    return result
def comment_snapshot(workspace,source):
    from nbt_feedback_tasks import inventory
    _,comments=inventory(workspace,source)
    return [dict(key=entry['key'],content_sha256=entry['content_sha256'],text=entry['text'],anchors=entry['anchors'],verified=entry['verified'],geometry_matches_source=entry['geometry_matches_source']) for entry in comments]
def discover(workspace,data):
    source=inside(workspace,data['source'])
    base_version=inside(workspace,data['directory']).parents[1]
    root=registered_building(workspace,data)
    known={entry['source'] for entry in data['returns']};items=[]
    for folder,dirs,files in os.walk(root):
        dirs[:]=[name for name in dirs if name not in {'Agent交接','修改意见','delivery','runtime','parts','previews','validation','.git'}
                 and not (Path(folder)/name).is_symlink() and (Path(folder)/name).resolve()==Path(folder)/name]
        for name in files:
            if not (name.lower().endswith(('.master.json.gz','.snbt')) or name in ('master_geometry.json.gz','refined.master.json.gz')):continue
            path=Path(folder)/name
            if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root):continue
            if path==source or project_paths(path)['version']==base_version or relative(workspace,path) in known:continue
            stat=path.stat();items.append(dict(source=relative(workspace,path),absolute_source=str(path),modified_ns=str(stat.st_mtime_ns),bytes=stat.st_size,status='unregistered_candidate',verified=False))
            if len(items)>=1000:return dict(candidates=items,truncated=True)
    return dict(candidates=sorted(items,key=lambda item:int(item['modified_ns']),reverse=True),truncated=False)

def candidate_evidence(workspace,index,data,request):
    from nbt_building.plan import fingerprint,normalize
    from nbt_prompts import completion_evidence
    from nbt_working_model import managed_manifest,WorkingModel

    old=task_for(workspace,index,request['from_task'])
    target=inside(workspace,request['new_source'])
    base=verify(workspace,data)
    origin=verify_source(workspace,old)
    if old['id']==data['id'] or protocol.lease_active(old):
        protocol.error('TASK_CLAIMED','旧任务须已释放或到期，并明确选择另一项当前任务')
    if any(inside(workspace,row['source'])==target for row in old['returns']+data['returns']):
        protocol.error('CANDIDATE_REGISTERED','该候选已在所选任务中登记')
    if sha(target)!=request['new_source_sha256']:protocol.error('SOURCE_CHANGED','候选内容已变化')
    manifest=managed_manifest(target)
    if not manifest or not manifest.get('parent_source'):
        protocol.error('RETURN_LINEAGE_MISMATCH','候选缺少可验证的父版本。请从当前任务源重新派生制作版并准备审阅。')
    producer=manifest.get('agent_publication')
    if producer and (producer['task_id']!=old['id'] or producer['source_sha256']!=old['source_sha256']):
        protocol.error('RETURN_LINEAGE_MISMATCH','候选登记的制作任务与所选旧任务不符，请核对 from_task')
    return_parent(workspace,origin,target)
    parent=return_parent(workspace,base,target)
    model=WorkingModel.open(workspace,target,source_sha256=request['new_source_sha256'])
    model.validate()
    plans=[row for row in data['origins'] if row['role'] in ('plan','architecture_plan')]
    if not plans:protocol.error('PLAN_REQUIRED','请在目标任务 origins 中绑定当前计划（role=plan）')
    review_kind=request.get('review_kind','architecture')
    if model.architecture and review_kind!='architecture':
        protocol.error('EVIDENCE_INVALID','有建筑方案绑定的候选须提供三尺度审阅')
    evidence=completion_evidence(workspace,dict(stage='draft'),dict(request,review_kind=review_kind))
    if inside(workspace,evidence['source'])!=target or evidence['source_sha256']!=request['new_source_sha256']:
        protocol.error('EVIDENCE_INVALID','图像与观察记录必须来自候选自身的制作版本')
    if review_kind=='architecture':
        if not evidence['coverage_complete']:protocol.error('EVIDENCE_INVALID','请补全建筑三尺度覆盖及观察记录')
        matched=False
        for row in plans:
            spec=read(inside(workspace,row['path']))
            if isinstance(spec,dict):
                try:matched |= fingerprint(normalize(spec.get('plan',spec)))==evidence['plan_sha256']
                except (ValueError,KeyError,TypeError):pass
        if not matched:protocol.error('PLAN_MISMATCH','目标任务须绑定该候选三尺度审阅中核验的建筑方案')
    else:
        previous={row['sha256'] for row in old['origins'] if row['role'] in ('plan','architecture_plan')}
        if previous!={row['sha256'] for row in plans}:
            protocol.error('PLAN_MISMATCH','普通缩略图候选需要与原交接相同的计划。计划变化时请重新制作并审阅。')
        review=inside(workspace,request['review'])
        images={row['sha256'] for row in read(review/'review.json')['thumbnails']}
        observations=request.get('observations',[])
        if (not isinstance(observations,list) or len(observations)!=len(images) or
            any(not isinstance(row,dict) or set(row)!={'image_sha256','note'} or
                not isinstance(row['image_sha256'],str) or not isinstance(row['note'],str) or not 1<=len(row['note'].strip())<=2000 for row in observations) or
            {row['image_sha256'] for row in observations}!=images):
            protocol.error('EVIDENCE_INVALID','请针对每张候选缩略图提供 image_sha256 和具体观察 note')
        evidence['observations']=observations
    binding=dict(from_task=old['id'],from_revision=old['revision'],old_source=old['source'],
                 old_source_sha256=old['source_sha256'],task=data['id'],source=data['source'],
                 source_sha256=data['source_sha256'],old_origins=old['origins'],origins=data['origins'],
                 candidate=relative(workspace,target),candidate_sha256=request['new_source_sha256'],
                 candidate_revision=manifest['revision'],publication=producer,parent=relative(workspace,parent),
                 parent_revision=manifest['parent_revision'],parent_sha256=manifest['parent_source_sha256'],evidence=evidence)
    verify(workspace,data);verify_source(workspace,old)
    return dict(binding=binding,binding_sha256=fingerprint(binding),acceptance='pending_user_review')

def remember_existing_candidates(workspace,data):
    # Managed models already have an immutable parent chain and require a
    # publication stamp. Some first-handoff legacy editors only emit raw SNBT.
    if (data.get('input_binding') or {}).get('manifest_sha256'):return
    found=discover(workspace,data)
    data['existing_raw_candidates']=dict(paths=[row['source'] for row in found['candidates']],truncated=found['truncated'])

def dispatch(workspace,action,request):
    if not isinstance(request,dict) or action not in ('list','create','get','discover','revalidate','reuse','recover','record','review','claim','heartbeat','release'):raise ValueError('Agent任务请求无效')
    workspace=Path(workspace).resolve();file,index=load_index(workspace)
    if action=='list':
        source=relative(workspace,inside(workspace,request['source'])) if request.get('source') else None;tasks=[];errors=[]
        for entry in index['tasks']:
            try:
                data=task_for(workspace,index,entry['id'])
                if source and data['source']!=source and all(item['source']!=source for item in data['returns']):continue
                verify(workspace,data);tasks.append(output(workspace,data))
            except (ValueError,OSError,KeyError) as error:
                errors.append(dict(id=entry['id'],name=entry['name'],source=entry['source'],error=str(error),
                                   code=getattr(error,'code','TASK_INVALID'),details=getattr(error,'details',{})))
        return dict(tasks=tasks,errors=errors)
    if action in ('get','discover','revalidate'):
        data=task_for(workspace,index,request['id'])
        if action=='revalidate':return candidate_evidence(workspace,index,data,request)
        if action=='discover':
            candidates=discover(workspace,data)
            try:verify(workspace,data)
            except protocol.ProtocolError as failure:
                return dict(candidates,ready_for_execution=False,issue=dict(code=failure.code,error=str(failure),details=failure.details))
            return dict(candidates,ready_for_execution=True)
        verify(workspace,data)
        return output(workspace,data)
    file.parent.mkdir(parents=True,exist_ok=True)
    # Recording a return also writes building history under the building lock.
    building_lock=nullcontext()
    if action in ('record','reuse'):
        replay=protocol.replay(workspace,index,'agent-tasks.'+action,request)
        if replay is not None:return replay
        building_lock=task_building_lock(workspace,index,request['id'])
    with building_lock,index_lock(workspace,file.parent):
        file,index=load_index(workspace)
        replay=protocol.replay(workspace,index,'agent-tasks.'+action,request)
        if replay is not None:return replay
        if action=='recover':return recover_registration(workspace,file,index,request)
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
            data['building']=relative(workspace,project_paths(source)['workdir'])
            verify_binding(source,binding);data['input_binding']=binding
            remember_existing_candidates(workspace,data)
        else:
            data=task_for(workspace,index,request['id'])
            # Releasing an owned lease writes no model or evidence. It must
            # remain possible after a bound input has changed or disappeared.
            if action!='release':
                source=verify(workspace,data)
            if action not in ('claim','heartbeat','release') or 'revision' in request:
                if request.get('revision')!=data['revision']:protocol.error('REVISION_CONFLICT','任务已更新，请刷新后核对再提交',retryable=True,details={'current_revision':data['revision']})
            if action in ('claim','heartbeat','release'):
                protocol.lease_action(data,action,request)
                if action=='claim':remember_existing_candidates(workspace,data)
            elif action in ('record','reuse'):
                require_lease=action=='reuse' or bool(request.get('request_id'))
                protocol.check_lease(data,request,required=require_lease)
                from nbt_refine import read_master,source_binding
                target=inside(workspace,request['new_source']);paths=project_paths(source);new_paths=project_paths(target)
                if target==source or new_paths['version']==paths['version'] or new_paths['workdir']!=paths['workdir'] or any(part in ('delivery','runtime','parts','Agent交接') for part in target.relative_to(paths['workdir']).parts):raise ValueError('请回传同一建筑的新版本完整主模型，不是原稿、过程稿或交付副本')
                target_hash=sha(target)
                if request.get('new_source_sha256')!=target_hash:raise ValueError('回传文件哈希不匹配')
                return_parent(workspace,source,target)
                if action=='record':
                    check_publication_owner(workspace,index,data,target,request)
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
                reuse={}
                if action=='reuse':
                    checked=candidate_evidence(workspace,index,data,request)
                    if checked['binding_sha256']!=request.get('binding_sha256'):
                        protocol.error('CANDIDATE_CHANGED','候选或绑定证据已变化，请重新执行 check-candidate')
                    reuse['reuse']=checked
                protocol.check_lease(data,request,required=require_lease)
                data['returns'].append(dict(id=uuid.uuid4().hex,source=relative(workspace,target),source_sha256=target_hash,input_binding=binding,geometry_sha256=model.fingerprint(),size=list(model.size),summary=summary,comments=claims,review={},created_at=now(),acceptance='pending_user_review',**reuse))
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
        if action in ('record','reuse'):
            extras['version_history']=record_return_history(workspace,data,data['returns'][-1])
            extras['history_pending']=extras['version_history'].get('recorded') is False
        return commit(workspace,file,index,data,action,request,extras)

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--workspace',type=Path,default=Path.cwd());parser.add_argument('action',choices=['create','list','get','discover','revalidate','reuse','recover','record','review','claim','heartbeat','release']);parser.add_argument('--request',type=Path,required=True);args=parser.parse_args()
    try:print(json.dumps(dispatch(args.workspace,args.action,read(args.request)),ensure_ascii=False));return 0
    except (ValueError,OSError,KeyError,TypeError) as error:print(json.dumps(dict(error=str(error)),ensure_ascii=False));return 1
if __name__=='__main__':raise SystemExit(main())
