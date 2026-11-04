"""Workspace project queues: read-only covers and checks, no modelling/export approval."""
import argparse
from contextlib import contextmanager
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import re
import uuid


def now():return datetime.now(timezone.utc).isoformat()


def root(workspace):return Path(workspace).resolve()/'.nbtcreator/project-queues'


def folder(workspace,identifier):
    if not isinstance(identifier,str) or not re.fullmatch(r'[a-f0-9]{32}',identifier):raise ValueError('批量任务编号无效')
    base=root(workspace).resolve();target=base/identifier
    if not target.resolve().is_relative_to(base):raise ValueError('批量任务路径越界')
    return target


def source_path(workspace,value):
    if not isinstance(value,str) or not value:raise ValueError('模型路径无效')
    source=(Path(workspace).resolve()/value).resolve();models=(Path(workspace).resolve()/'nbt_models').resolve()
    if not source.is_relative_to(models) or not source.is_file():raise ValueError('请选择当前工作区建筑库中的文件')
    return source


def stamp(source):
    stat=source.stat();return [stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns]


def read_json(file):
    if file.stat().st_size>4*1024*1024:raise ValueError('批量任务资料超过4MiB')
    return json.loads(file.read_text(encoding='utf-8-sig'))


def write(file,value):
    file.parent.mkdir(parents=True,exist_ok=True);temporary=file.with_name(uuid.uuid4().hex+'.tmp')
    try:temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8');os.replace(temporary,file)
    finally:temporary.unlink(missing_ok=True)


@contextmanager
def runner_lock(workspace):
    file=root(workspace)/'runner.lock';file.parent.mkdir(parents=True,exist_ok=True)
    with file.open('a+b') as handle:
        if file.stat().st_size==0:handle.write(b'0');handle.flush()
        handle.seek(0)
        try:
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:raise ValueError('当前工作区已有批量任务运行，请先等待或停止它') from None
        try:yield
        finally:
            handle.seek(0)
            if os.name=='nt':msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
            else:fcntl.flock(handle.fileno(),fcntl.LOCK_UN)


def load(workspace,identifier):
    value=read_json(folder(workspace,identifier)/'queue.json')
    if not isinstance(value,dict) or value.get('schema_version')!=1 or value.get('id')!=identifier or not isinstance(value.get('items'),list) or not 1<=len(value['items'])<=100:raise ValueError('批量任务格式无效')
    if value.get('actions') not in (['preview'],['check'],['preview','check']):raise ValueError('批量任务操作无效')
    for item in value['items']:
        if not isinstance(item,dict) or not isinstance(item.get('source'),str) or Path(item['source']).is_absolute() or set(item.get('steps',{}))!=set(value['actions']):raise ValueError('批量条目格式无效')
        if any(not isinstance(v,dict) for v in item['steps'].values()):raise ValueError('批量步骤无效')
        if any(v.get('status') not in ('pending','running','complete','failed','cancelled') or type(v.get('attempts')) is not int or not 0<=v['attempts']<=10000 for v in item['steps'].values()):raise ValueError('批量步骤状态无效')
    return value


def counts(queue):
    steps=[step for item in queue['items'] for step in item['steps'].values()]
    return {key:sum(step['status']==key for step in steps) for key in ('pending','running','complete','failed','cancelled')}|dict(total=len(steps))


def exposed(queue):return dict(queue,progress=counts(queue),asset_written=False,approval_created=False)


def recover(workspace,identifier):
    queue=load(workspace,identifier)
    if queue['status']=='running':
        try:
            with runner_lock(workspace):
                queue=load(workspace,identifier)
                if queue['status']=='running':
                    queue['status']='cancelled' if (folder(workspace,identifier)/'cancel.request').exists() else 'interrupted'
                    queue['updated_at']=now()
                    for item in queue['items']:
                        for step in item['steps'].values():
                            if step['status']=='running':step.update(status='cancelled',error='任务中断，已完成项保留；可重试未完成项')
                    write(folder(workspace,identifier)/'queue.json',queue)
        except ValueError as error:
            if '已有批量任务' not in str(error):raise
    return exposed(queue)


def create(workspace,data):
    sources=data.get('sources');actions=data.get('actions')
    if not isinstance(sources,list) or not 1<=len(sources)<=100 or actions not in (['preview'],['check'],['preview','check']):raise ValueError('选择1～100个版本，以及预览、检查或两项任务')
    identifier=uuid.uuid4().hex;items=[];seen=set();workspace=Path(workspace).resolve()
    for entry in sources:
        if not isinstance(entry,dict):raise ValueError('模型条目无效')
        source=source_path(workspace,entry.get('source'));key=os.path.normcase(str(source))
        if key in seen:continue
        seen.add(key);label=entry.get('label',source.stem)
        if not isinstance(label,str) or len(label)>200:raise ValueError('模型名称过长')
        items.append(dict(source=source.relative_to(workspace).as_posix(),label=label,stamp=stamp(source),steps={action:dict(status='pending',attempts=0) for action in actions}))
    queue=dict(schema_version=1,id=identifier,status='pending',actions=actions,created_at=now(),updated_at=now(),items=items)
    write(folder(workspace,identifier)/'queue.json',queue);return exposed(queue)


def check_source(source):
    from nbt_detail_control import inspect_source,normalize_context,default_settings
    from nbt_refine import read_master
    from nbt_whole_validation import validate_whole
    before=hashlib.sha256(source.read_bytes()).hexdigest()
    try:info=inspect_source(source,1)
    except (ValueError,AssertionError,KeyError,TypeError,IndexError,OSError) as error:return dict(passed=False,source_sha256=before,checks=dict(file=dict(passed=False,error=str(error))),asset_written=False,approval_created=False,runtime_verified=False)
    report=dict(passed=False,source_sha256=before,geometry_sha256=info['geometry_sha256'],size=info['size'],checks=dict(file=dict(passed=True,solid_blocks=info['solid_blocks'],wall_blocks=info['wall_blocks'])),runtime_verified=False,design='pending_visual_review',asset_written=False,approval_created=False)
    if not info['editing_ready']:report['checks']['context']=dict(passed=False,error='缺少或无效的坐标资料',details=info['context_readiness'])
    else:
        model,_=read_master(source)
        try:
            config=normalize_context(model,info['context'],info['cameras'],default_settings());details=validate_whole(model,config);report['checks']['geometry_routes']=dict(passed=True,details=details)
        except (ValueError,AssertionError,KeyError,TypeError,IndexError,OSError) as error:report['checks']['geometry_routes']=dict(passed=False,error=str(error))
    if hashlib.sha256(source.read_bytes()).hexdigest()!=before:raise ValueError('检查期间源文件已改变，请重新加入队列')
    report['passed']=all(item['passed'] for item in report['checks'].values());return report


def run(workspace,identifier):
    directory=folder(workspace,identifier);file=directory/'queue.json'
    with runner_lock(workspace):
        queue=load(workspace,identifier)
        if queue['status']!='pending':raise ValueError('任务已运行过；请使用重试，不会重复执行已完成项')
        queue['status']='running';queue['updated_at']=now();write(file,queue)
        try:
            for number,item in enumerate(queue['items']):
                for action,step in item['steps'].items():
                    if step['status']!='pending':continue
                    if (directory/'cancel.request').exists():queue['status']='cancelled';return exposed(queue)
                    step.update(status='running',attempts=step.get('attempts',0)+1,started_at=now());queue['current']=dict(index=number,action=action);queue['updated_at']=now();write(file,queue)
                    try:
                        source=source_path(workspace,item['source'])
                        if stamp(source)!=item['stamp']:raise ValueError('源文件在排队后发生变化，请按当前文件重试')
                        if action=='preview':
                            from nbt_cover import section_cover
                            result=dict(section_cover(source,'',Path(workspace)/'.nbtcreator/cache/section-covers',generate=True))
                            if not result.get('image'):raise ValueError('未生成当前版本预览')
                        else:result=check_source(source)
                        for key in ('image','thumbnail'):
                            if result.get(key):
                                image=Path(result[key]).resolve()
                                if not image.is_relative_to(Path(workspace).resolve()):raise ValueError('预览产物不在当前工作区内')
                                result[key]=image.relative_to(Path(workspace).resolve()).as_posix()
                        if stamp(source)!=item['stamp']:raise ValueError('处理期间源文件已改变，结果未采用')
                        report=directory/f'{number:03d}-{action}-attempt{step["attempts"]}.json';write(report,result)
                        summary=result if action=='preview' else {k:v for k,v in result.items() if k!='checks'}|dict(checks={k:{field:v[field] for field in ('passed','error') if field in v} for k,v in result['checks'].items()})
                        step.update(status='complete' if result.get('passed',True) else 'failed',result=summary,report=report.relative_to(Path(workspace).resolve()).as_posix())
                        step.pop('error',None)
                        if step['status']=='failed':step['error']='检查未通过：'+'；'.join(v.get('error','检查未通过') for v in result.get('checks',{}).values() if not v.get('passed'))
                    except (ValueError,AssertionError,KeyError,TypeError,IndexError,OSError) as error:step.update(status='failed',error=str(error)[:4000]);step.pop('result',None)
                    step['completed_at']=now();queue['updated_at']=now();write(file,queue)
            queue['status']='complete';return exposed(queue)
        finally:
            if queue['status']=='running':queue['status']='interrupted'
            queue.pop('current',None);queue['updated_at']=now();write(file,queue)


def retry(workspace,identifier):
    with runner_lock(workspace):
        queue=load(workspace,identifier)
        for item in queue['items']:
            if any(step['status']!='complete' for step in item['steps'].values()):
                try:item['stamp']=stamp(source_path(workspace,item['source']))
                except (ValueError,OSError):pass
                for step in item['steps'].values():
                    if step['status']!='complete':
                        step['status']='pending'
                        for key in ('error','result','report'):step.pop(key,None)
        queue['status']='pending';queue['updated_at']=now();(folder(workspace,identifier)/'cancel.request').unlink(missing_ok=True);write(folder(workspace,identifier)/'queue.json',queue)
        return exposed(queue)


def dispatch(workspace,action,data):
    if action=='create':return create(workspace,data)
    if action=='list':
        items=[]
        for directory in sorted(root(workspace).glob('*/queue.json'),key=lambda p:p.stat().st_mtime_ns,reverse=True)[:50]:
            try:
                queue=recover(workspace,directory.parent.name);items.append({k:v for k,v in queue.items() if k not in ('items','current')}|dict(item_count=len(queue['items'])))
            except (ValueError,OSError,KeyError,TypeError):continue
        return dict(items=items)
    if action=='get':return recover(workspace,data['id'])
    if action=='run':return run(workspace,data['id'])
    if action=='retry':return retry(workspace,data['id'])
    if action=='cancel':
        directory=folder(workspace,data['id']);load(workspace,data['id']);(directory/'cancel.request').write_text(now(),encoding='utf8');return recover(workspace,data['id'])
    raise ValueError('未知批量操作')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--workspace',type=Path,default=Path.cwd());sub=parser.add_subparsers(dest='action',required=True)
    sub.add_parser('list');create_parser=sub.add_parser('create');create_parser.add_argument('--request',type=Path,required=True)
    for name in ('get','run','retry','cancel'):sub.add_parser(name).add_argument('--id',required=True)
    args=parser.parse_args()
    try:result=dispatch(args.workspace,args.action,read_json(args.request) if args.action=='create' else dict(id=args.id) if args.action!='list' else {});print(json.dumps(dict(ok=True,result=result),ensure_ascii=False));return 0
    except Exception as error:print(json.dumps(dict(ok=False,error=str(error)),ensure_ascii=False));return 1


if __name__=='__main__':raise SystemExit(main())
