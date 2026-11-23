"""Run a claimed prompt through NBTCreator's local creation and review workflow."""

import argparse
import json
from pathlib import Path

from nbt_agent.creation import Creation
from nbt_agent.creation_execution import StageError
from nbt_agent.protocol import ProtocolError
from nbt_composition.working_model import ModelConflict
from nbt_project.queues import read_json


def submit_working_model(session, request, model):
    """Stage an already-built in-memory draft from the Agent's local Python script."""
    return Creation(model.workspace, session).act('candidate', request, working=model)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace',type=Path,default=Path.cwd())
    parser.add_argument('--session',default='default')
    actions=parser.add_subparsers(dest='action',required=True)
    for name, help_text in (
        ('start','冻结本轮的候选范围和比较条件'),('escalate','用已配置的强模型处理语义问题'),
        ('candidate','编译、回读、检查并渲染方案'),('retry','重放原请求并续跑本机失败步骤'),
        ('observe','登记真实三尺度图片观察'),('prepare-blind','生成同机位匿名 A/B 包'),
        ('record-blind','登记匿名图像比较和选择'),('select','根据观察选定一个候选'),
        ('retest','按留存审阅记录定向复验'),('publish','把入选候选另存为正式制作版并出图'),
        ('finish','回传制作版和实际观察，等待用户审阅')):
        actions.add_parser(name,help=help_text).add_argument('--request',type=Path)
    actions.add_parser('brief',help='读取冻结的创作简报和下一阶段模型请求').add_argument('--expand',action='store_true')
    actions.add_parser('status',help='读取阶段、回执和用量指标')
    args=parser.parse_args()
    try:
        job=Creation(args.workspace,args.session)
        if args.action=='status':
            result=job.status()
        elif args.action=='brief':
            result=job.brief(expand=args.expand)
        else:
            request=read_json(args.request) if args.request else {}
            result=job.start(request) if args.action=='start' else job.act(args.action.replace('-','_'),request)
        ok=result.get('status')!='failed'
        print(json.dumps(dict(ok=ok,data=result),ensure_ascii=False))
        return 0 if ok else 1
    except (ProtocolError,ModelConflict,StageError,OSError,ValueError) as failure:
        from nbt_agent.creation_execution import STALE_CODES
        if isinstance(failure,StageError):
            result=failure.outcome
        else:
            code=getattr(failure,'code','IO_ERROR' if isinstance(failure,OSError) else 'INVALID_REQUEST')
            result=dict(status='failed',code=code,message=str(failure),
                        category='stale' if code in STALE_CODES else 'local_execution' if isinstance(failure,OSError) else 'request',
                        conflicts=getattr(failure,'conflicts',[]),details=getattr(failure,'details',{}))
        print(json.dumps(dict(ok=False,data=result),ensure_ascii=False))
        return 1


if __name__=='__main__':
    raise SystemExit(main())
