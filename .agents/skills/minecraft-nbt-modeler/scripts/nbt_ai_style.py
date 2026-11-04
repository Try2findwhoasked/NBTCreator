"""Shared creative preferences for internal API workflows and external agents."""
import argparse
import json
import os
from pathlib import Path
import uuid

SCHEMA=json.loads((Path(__file__).resolve().parents[1]/'config/ai-style-schema.json').read_text(encoding='utf8'))


def defaults():
    return dict(schema_version=1,workflows={flow:{key:dimension['default'] for key,dimension in SCHEMA['dimensions'].items()} for flow in SCHEMA['workflows']})


def validate(data):
    if not isinstance(data,dict) or type(data.get('schema_version')) is not int or data.get('schema_version')!=1 or not isinstance(data.get('workflows'),dict) or set(data['workflows'])!=set(SCHEMA['workflows']):raise ValueError('AI创作偏好配置无效')
    for values in data['workflows'].values():
        if not isinstance(values,dict) or set(values)!=set(SCHEMA['dimensions']) or any(type(n) is not int or not 0<=n<=100 for n in values.values()):raise ValueError('AI创作偏好参数须为0～100的整数')
    return data


def load(workspace, create=False):
    file=Path(workspace).resolve()/'.nbtcreator/ai-style.json'
    try:
        data=json.loads(file.read_text(encoding='utf-8-sig'))
        previous=set(data.get('workflows',{}))
        if data.get('schema_version')==1 and isinstance(data.get('workflows'),dict) and set(data['workflows'])==set(SCHEMA['workflows'])-{'component'}:
            data['workflows']['component']=dict(data['workflows']['small_structure'])
        if data.get('schema_version')==1 and isinstance(data.get('workflows'),dict) and set(data['workflows'])==set(SCHEMA['workflows'])-{'component','selection_edit'}:
            data['workflows']['component']=dict(data['workflows']['small_structure'])
        if data.get('schema_version')==1 and isinstance(data.get('workflows'),dict) and set(data['workflows'])==set(SCHEMA['workflows'])-{'selection_edit'}:
            data['workflows']['selection_edit']=dict(data['workflows']['structure'])
        data=validate(data)
        if create and previous!=set(data['workflows']):save(workspace,data)
        return data
    except FileNotFoundError:
        data=defaults()
        if create:save(workspace,data)
        return data


def save(workspace, data):
    validate(data);file=Path(workspace).resolve()/'.nbtcreator/ai-style.json';file.parent.mkdir(parents=True,exist_ok=True);temporary=file.with_name(uuid.uuid4().hex+'.tmp')
    temporary.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8');os.replace(temporary,file)
    return data


def prompt(workspace, workflow):
    if workflow not in SCHEMA['workflows']:raise ValueError('未知AI使用区域')
    values=load(workspace)['workflows'][workflow]
    lines=[f"使用区域：{SCHEMA['workflows'][workflow]}。以下为创作偏好；用户本次明确要求优先。"]
    for key,dimension in SCHEMA['dimensions'].items():
        value=values[key];band='low' if value<34 else 'high' if value>66 else 'middle'
        lines.append(f"{dimension['label']} {value}/100（{dimension['left']} ↔ {dimension['right']}）：{dimension[band]}")
    lines.append('创作偏好不改变选区、源文件、保护、预算、返回格式及真实看图确认要求；不得据此声称已执行或已通过验收。')
    return dict(workflow=workflow,values=values,prompt='\n'.join(lines))


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--workspace',type=Path,default=Path.cwd());sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('show');p=sub.add_parser('prompt');p.add_argument('--workflow',choices=list(SCHEMA['workflows']),required=True)
    p=sub.add_parser('set');p.add_argument('--workflow',choices=list(SCHEMA['workflows']),required=True)
    for key in SCHEMA['dimensions']:p.add_argument('--'+key,type=int)
    args=parser.parse_args()
    try:
        if args.command=='show':result=dict(config=load(args.workspace),schema=SCHEMA)
        elif args.command=='prompt':result=prompt(args.workspace,args.workflow)
        else:
            data=load(args.workspace)
            for key in SCHEMA['dimensions']:
                value=getattr(args,key)
                if value is not None:data['workflows'][args.workflow][key]=value
            result=save(args.workspace,data)
        print(json.dumps(dict(ok=True,result=result),ensure_ascii=False));return 0
    except (OSError,ValueError,TypeError,KeyError) as error:
        print(json.dumps(dict(ok=False,error=str(error)),ensure_ascii=False));return 1


if __name__=='__main__':raise SystemExit(main())
