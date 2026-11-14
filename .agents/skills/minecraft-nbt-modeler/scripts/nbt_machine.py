"""Versioned, strict JSON transport for manually invoked workspace Agents."""
import argparse,json,sys
from pathlib import Path
import nbt_agent_protocol as protocol

def schema():
    return json.loads((Path(__file__).resolve().parents[1]/'tool-catalog.json').read_text(encoding='utf8'))['machine_protocol']

def dispatch(workspace,request):
    request_id=request.get('request_id') if isinstance(request,dict) else None
    try:
        if not isinstance(request,dict) or set(request)-{'protocol_version','request_id','method','params'}:protocol.error('INVALID_REQUEST','请求字段无效')
        if type(request.get('protocol_version')) is not int or request['protocol_version']!=protocol.PROTOCOL_VERSION:protocol.error('PROTOCOL_VERSION_UNSUPPORTED','不支持的机器接口版本')
        protocol.request_key(request)
        method=request.get('method');definition=schema()['methods'].get(method) if isinstance(method,str) else None
        if definition is None:protocol.error('METHOD_NOT_FOUND','未知机器接口方法')
        params=request.get('params',{})
        if not isinstance(params,dict) or set(params)-set(definition['fields']) or any(key not in params for key in definition['required']):protocol.error('INVALID_REQUEST','参数缺失或包含未知字段',details={'required':definition['required'],'allowed':list(definition['fields'])})
        kinds={'string':str,'integer':int,'object':dict,'array':list}
        for key,value in params.items():
            if type(value) is not kinds[definition['fields'][key]]:protocol.error('INVALID_REQUEST','参数类型无效：'+key)
        if definition['mutation'] and not request_id:protocol.error('REQUEST_ID_REQUIRED','写操作必须提供稳定 request_id；重试使用原编号和原参数')
        args=dict(params)
        if definition['mutation']:args['request_id']=request_id
        namespace,action=method.split('.',1)
        if namespace=='tasks':
            import nbt_agent_tasks
            result=nbt_agent_tasks.dispatch(workspace,action,args)
        elif namespace=='prompts':
            import nbt_prompts
            if action=='list':result=nbt_prompts.tasks(workspace,params.get('after',0),params.get('status'))
            elif action=='get':result=nbt_prompts.read_task(workspace,params['id'])
            else:result=nbt_prompts.task_action(workspace,action,args)
        elif namespace=='annotations':
            import nbt_feedback
            if action=='scan':result=nbt_feedback.scan(workspace,nbt_feedback_source(workspace,params['version']) if params.get('version') else None)
            else:result=nbt_feedback.collect(nbt_feedback_source(workspace,params['source']),workspace)
        else:
            import nbt_feedback_tasks
            result=nbt_feedback_tasks.dispatch(workspace,action,args)
        return dict(protocol_version=protocol.PROTOCOL_VERSION,request_id=request_id,ok=True,data=result,error=None)
    except (ValueError,OSError,KeyError,TypeError) as failure:
        code=getattr(failure,'code','IO_ERROR' if isinstance(failure,OSError) else 'VALIDATION_ERROR')
        return dict(protocol_version=protocol.PROTOCOL_VERSION,request_id=request_id,ok=False,data=None,error=dict(code=code,message=str(failure),retryable=getattr(failure,'retryable',False),details=getattr(failure,'details',{})))

def nbt_feedback_source(workspace,source):
    from nbt_prompts import inside
    return inside(workspace,source)

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--workspace',type=Path,default=Path.cwd());group=parser.add_mutually_exclusive_group(required=True);group.add_argument('--schema',action='store_true');group.add_argument('--request',help='JSON file path, or - for stdin');args=parser.parse_args()
    if args.schema:print(json.dumps(schema(),ensure_ascii=False));return 0
    try:
        if args.request!='-' and Path(args.request).stat().st_size>2*1024*1024:protocol.error('INVALID_REQUEST','请求超过2MiB')
        raw=sys.stdin.read(2*1024*1024+1) if args.request=='-' else Path(args.request).read_text(encoding='utf-8-sig')
        if len(raw.encode('utf8'))>2*1024*1024:protocol.error('INVALID_REQUEST','请求超过2MiB')
        request=json.loads(raw)
    except (ValueError,OSError) as failure:
        print(json.dumps(dict(protocol_version=1,request_id=None,ok=False,data=None,error=dict(code='INVALID_REQUEST',message=str(failure),retryable=False,details={})),ensure_ascii=False));return 1
    result=dispatch(args.workspace.resolve(),request);print(json.dumps(result,ensure_ascii=False));return 0 if result['ok'] else 1

if __name__=='__main__':raise SystemExit(main())
