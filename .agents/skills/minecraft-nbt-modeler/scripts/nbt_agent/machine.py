"""Versioned, strict JSON transport for manually invoked workspace Agents."""
import argparse,json,sys
from pathlib import Path
import nbt_agent.protocol as protocol

def schema():
    return json.loads((Path(__file__).resolve().parents[2]/'tool-catalog.json').read_text(encoding='utf8'))['machine_protocol']

def dispatch(workspace,request,*,session=None):
    request_id=request.get('request_id') if isinstance(request,dict) else None
    try:
        if not isinstance(request,dict) or set(request)-{'protocol_version','request_id','method','params'}:protocol.error('INVALID_REQUEST','请求字段无效')
        if type(request.get('protocol_version')) is not int or request['protocol_version']!=protocol.PROTOCOL_VERSION:protocol.error('PROTOCOL_VERSION_UNSUPPORTED','不支持的机器接口版本')
        protocol.request_key(request)
        method=request.get('method');definition=schema()['methods'].get(method) if isinstance(method,str) else None
        if definition is None:protocol.error('METHOD_NOT_FOUND','未知机器接口方法')
        params=request.get('params',{})
        if session is not None:
            if not method.startswith('authoring.') or not isinstance(session,dict):protocol.error('PACKAGE_ACCESS_DENIED','受限工作包会话仅能使用已开放的制作方法')
            if isinstance(params,dict):
                params=dict(params)
                if any(key in params and params[key]!=session.get(key) for key in ('batch_id','run_id')):protocol.error('PACKAGE_ACCESS_DENIED','请求不属于当前会话的制作运行')
                for key in ('batch_id','run_id','package_id','package_revision','lease_token','fence'):
                    if key in definition['fields'] and key in session:params.setdefault(key,session[key])
                if method in ('authoring.issue','authoring.reissue'):params.setdefault('parent_id',session.get('package_id'))
        if not isinstance(params,dict) or set(params)-set(definition['fields']) or any(key not in params for key in definition['required']):protocol.error('INVALID_REQUEST','参数缺失或包含未知字段',details={'required':definition['required'],'allowed':list(definition['fields'])})
        kinds={'string':str,'integer':int,'object':dict,'array':list}
        for key,value in params.items():
            if type(value) is not kinds[definition['fields'][key]]:protocol.error('INVALID_REQUEST','参数类型无效：'+key)
        if definition['mutation'] and not request_id:protocol.error('REQUEST_ID_REQUIRED','写操作必须提供稳定 request_id；重试使用原编号和原参数')
        args=dict(params)
        if definition['mutation']:args['request_id']=request_id
        namespace,action=method.split('.',1)
        if namespace=='model':
            from nbt_agent import model_actions
            result=model_actions.dispatch(workspace,action,args)
        elif namespace=='tasks':
            import nbt_agent.tasks as nbt_agent_tasks
            result=nbt_agent_tasks.dispatch(workspace,action,args)
        elif namespace=='prompts':
            import nbt_project.prompts as nbt_prompts
            if action=='list':result=nbt_prompts.tasks(workspace,params.get('after',0),params.get('status'))
            elif action=='get':result=nbt_prompts.read_task(workspace,params['id'],view=params.get('view','full'))
            else:result=nbt_prompts.task_action(workspace,action,args)
        elif namespace=='authoring':
            from nbt_project import authoring_runs
            result=authoring_runs.dispatch(workspace,action,args,session=session)
        elif namespace=='annotations':
            import nbt_project.feedback as nbt_feedback
            if action=='scan':result=nbt_feedback.scan(workspace,nbt_feedback_source(workspace,params['version']) if params.get('version') else None)
            else:result=nbt_feedback.collect(nbt_feedback_source(workspace,params['source']),workspace)
        else:
            import nbt_agent.feedback_tasks as nbt_feedback_tasks
            result=nbt_feedback_tasks.dispatch(workspace,action,args)
        return dict(protocol_version=protocol.PROTOCOL_VERSION,request_id=request_id,ok=True,data=result,error=None)
    except (ValueError,OSError,KeyError,TypeError,AttributeError) as failure:
        code=getattr(failure,'code','IO_ERROR' if isinstance(failure,OSError) else 'VALIDATION_ERROR')
        details=getattr(failure,'details',{})
        if hasattr(failure,'conflicts'):details={'conflicts':failure.conflicts[:32]}
        if isinstance(locals().get('method'),str) and method.startswith('authoring.') and isinstance(locals().get('params'),dict):
            from nbt_agent.authoring_feedback import annotate
            details=annotate(method,params,code,details)
        return dict(protocol_version=protocol.PROTOCOL_VERSION,request_id=request_id,ok=False,data=None,error=dict(code=code,message=str(failure),retryable=getattr(failure,'retryable',False),details=details))

def nbt_feedback_source(workspace,source):
    from nbt_project.prompts import inside
    return inside(workspace,source)

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--workspace',type=Path,default=Path.cwd());parser.add_argument('--package-session',type=Path,help='Host-held authoring invitation or lease JSON');group=parser.add_mutually_exclusive_group(required=True);group.add_argument('--schema',action='store_true');group.add_argument('--request',help='JSON file path, or - for stdin');args=parser.parse_args()
    try:
        from nbt_project.request_paths import read_request_json
        session=read_request_json(args.package_session,max_bytes=8192) if args.package_session else None
        if args.schema:
            data=schema()
            if session is not None:
                from nbt_agent.authoring_views import scoped_schema
                allowed=scoped_schema(args.workspace.resolve(),session)
                data['methods']={key:value for key,value in data['methods'].items() if key in allowed}
            print(json.dumps(data,ensure_ascii=False));return 0
        if args.request!='-' and Path(args.request).stat().st_size>2*1024*1024:protocol.error('INVALID_REQUEST','请求超过2MiB')
        raw=sys.stdin.read(2*1024*1024+1) if args.request=='-' else Path(args.request).read_text(encoding='utf-8-sig')
        if len(raw.encode('utf8'))>2*1024*1024:protocol.error('INVALID_REQUEST','请求超过2MiB')
        request=json.loads(raw)
    except (ValueError,OSError,KeyError,TypeError) as failure:
        print(json.dumps(dict(protocol_version=1,request_id=None,ok=False,data=None,error=dict(code=getattr(failure,'code','INVALID_REQUEST'),message=str(failure),retryable=False,details={})),ensure_ascii=False));return 1
    result=dispatch(args.workspace.resolve(),request,session=session);print(json.dumps(result,ensure_ascii=False));return 0 if result['ok'] else 1
