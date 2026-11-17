"""Shared application/CLI capability description; no GUI dependency."""
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def _checked_catalog():
    from nbt_catalog import snapshot
    data,digest=snapshot()
    from nbt_refine import SUPPORTED_OPERATION_KINDS
    if set(data['tools'])!=SUPPORTED_OPERATION_KINDS:raise ValueError('Engine and shared catalogue differ')
    from nbt_structure_agent import SUPPORTED_AGENT_TOOLS
    if set(data.get('agent_tools',{}))!=SUPPORTED_AGENT_TOOLS:raise ValueError('Structure agent tools and catalogue differ')
    from nbt_walk_view import SUPPORTED_INSPECTION_TOOLS
    if set(data.get('inspection_tools',{}))!=SUPPORTED_INSPECTION_TOOLS:raise ValueError('Inspection tools and catalogue differ')
    from nbt_architecture import ARCHITECT_ACTIONS
    if set(data.get('architecture',{}).get('actions',{}))!=set(ARCHITECT_ACTIONS):raise ValueError('Architecture workflow and catalogue differ')
    from nbt_constraints import ACTIONS
    if set(data.get('project_constraints',{}).get('actions',[]))!=set(ACTIONS):raise ValueError('Project constraints and catalogue differ')
    return data,digest


def operation_names():
    return frozenset(_checked_catalog()[0]['tools'])


def capabilities():
    from copy import deepcopy
    data,digest=_checked_catalog()
    return dict(deepcopy(data),capabilities_sha256=digest,gui_required=False,
                default_workspace='agent_cwd',default_assets='nbt_models',skill_entry='.agents/skills/nbtcreator-workspace/SKILL.md',knowledge_config='.nbtcreator/skill-exposure.json',path_policy='request_relative_with_absolute_legacy_compatibility')

if __name__=='__main__':
    import argparse
    data=capabilities();parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--agent-tool',choices=sorted(data['agent_tools']),help='只读取指定高层工具的完整参数Schema')
    parser.add_argument('--model',action='store_true',help='只读取统一工作模型的请求契约')
    parser.add_argument('--architecture',action='store_true',help='只读取建筑方案与评审工作流契约')
    args=parser.parse_args()
    if sum(map(bool,(args.model,args.agent_tool,args.architecture)))>1:parser.error('--model、--architecture 与 --agent-tool 只能选一个')
    if args.architecture:data=dict(architecture=data['architecture'],capabilities_sha256=data['capabilities_sha256'],gui_required=False)
    if args.model:data=dict(working_model=data['working_model'],capabilities_sha256=data['capabilities_sha256'],gui_required=False)
    if args.agent_tool:
        data=dict(agent_tools={args.agent_tool:data['agent_tools'][args.agent_tool]},
                  capabilities_sha256=data['capabilities_sha256'],gui_required=False,
                  session_available=args.agent_tool in data.get('agent_session',{}).get('tools',[]))
    print(json.dumps(data,ensure_ascii=False,indent=2))
