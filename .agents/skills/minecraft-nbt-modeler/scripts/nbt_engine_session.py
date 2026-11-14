"""Bounded JSON-lines transport for candidate tools; no code execution or writes."""
import argparse
from contextlib import redirect_stdout
import json
from pathlib import Path
import re
import sys
from time import perf_counter
from nbt_modeling_session import ModellingSession,engine_revision

MAX_REQUEST=8*1024*1024
MAX_RESPONSE=32*1024*1024
def tools():
    return json.loads((Path(__file__).resolve().parents[1]/'tool-catalog.json').read_text(encoding='utf8'))['agent_session']['tools']


def serve(workspace,source,sink):
    session=ModellingSession(workspace);revision=engine_revision()
    while True:
        raw=source.readline(MAX_REQUEST+2)
        if not raw:return
        # An oversized line cannot be safely resynchronised; do not consume a
        # partial tail as another request. The parent receives EOF and can restart.
        if len(raw)>MAX_REQUEST:return
        identity=None;started=perf_counter()
        try:
            request=json.loads(raw)
            if not isinstance(request,dict) or set(request)!={'id','method','params'}:raise ValueError('请求须包含id、method和params')
            identity=request['id']
            if not isinstance(identity,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}',identity):raise ValueError('请求编号无效')
            if engine_revision()!=revision:
                response=dict(id=identity,ok=False,error='引擎已更新，请重新启动会话',code='STALE_ENGINE')
            else:
                params=request['params']
                if not isinstance(params,dict):raise ValueError('params须为对象')
                with redirect_stdout(sys.stderr):
                    if request['method']=='agent':
                        if set(params)!={'tool','arguments'} or params['tool'] not in tools():raise ValueError('会话仅开放候选编译与只读查询工具')
                        if not isinstance(params['arguments'],dict) or params['arguments'].get('preview') or params['arguments'].get('review'):raise ValueError('会话不生成预览或审阅文件，请使用单次预览命令')
                        result=session.call(params['tool'],params['arguments'])
                    elif request['method']=='validate':
                        if set(params)!={'mode','result','context'} or params['mode'] not in ('component','workbench','structure','small_structure','selection_edit'):raise ValueError('AI预检请求无效')
                        if not isinstance(params['result'],dict) or not isinstance(params['context'],dict):raise ValueError('AI预检结果和上下文须为对象')
                        from nbt_ai_validate import validate
                        result=validate(dict(params,workspace=str(session.workspace)))
                    else:raise ValueError('未开放的会话方法')
                response=dict(id=identity,ok=True,result=result)
        except (ValueError,KeyError,TypeError,OSError,AssertionError) as error:
            response=dict(id=identity,ok=False,error=str(error)[:1000],code='VALIDATION_ERROR')
        response['metrics']=dict(engine_ms=round((perf_counter()-started)*1000,3),cache=dict(session.stats))
        payload=json.dumps(response,ensure_ascii=False,allow_nan=False).encode('utf8')
        if len(payload)>MAX_RESPONSE:payload=json.dumps(dict(id=identity,ok=False,error='会话结果超过32MiB',code='RESPONSE_TOO_LARGE')).encode()
        sink.write(payload+b'\n');sink.flush()


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--workspace',type=Path,default=Path.cwd());args=parser.parse_args()
    if hasattr(sys.stderr,'reconfigure'):sys.stderr.reconfigure(encoding='utf8')
    serve(args.workspace.resolve(),sys.stdin.buffer,sys.stdout.buffer)


if __name__=='__main__':main()
