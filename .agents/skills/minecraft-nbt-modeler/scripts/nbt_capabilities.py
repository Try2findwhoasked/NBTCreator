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
    parser.add_argument('--routes',action='store_true',help='速查容易混淆的检查、构件、看图和交付入口')
    parser.add_argument('--agent-tool',choices=sorted(data['agent_tools']),help='只读取指定高层工具的完整参数Schema')
    parser.add_argument('--model',action='store_true',help='只读取统一工作模型的请求契约')
    parser.add_argument('--architecture',action='store_true',help='只读取建筑方案与评审工作流契约')
    recipes=data['architecture']['plan']['properties']['parts']['items']['properties']['recipe']['properties']['tool']['enum']
    parser.add_argument('--recipe',choices=recipes,help='查询方案构件或工作模型安装的 recipe.tool 参数。structure 对应 structure_preview.spec')
    parser.add_argument('--operations',action='store_true',help='按用途浏览操作名称和提示，再用 --operation 查询单项字段')
    parser.add_argument('--operation',choices=sorted(data['operation_parameters']),help='查询 operations 中一个 kind 的字段')
    parser.add_argument('--architect-action',choices=sorted(data['architecture']['actions']),help='查询一项 architect 请求')
    parser.add_argument('--field',help='配合 --architect-action 查询字段，例如 plan.parts.interfaces')
    parser.add_argument('--block-state',help='查询 Java 1.20.1 状态、静态通路包络和精确接触支持')
    args=parser.parse_args()
    if sum(map(bool,(args.routes,args.model,args.agent_tool,args.architecture,args.recipe,args.operations,args.operation,
                     args.architect_action,args.block_state)))>1:
        parser.error('一次只选择一种能力查询')
    if args.field and not args.architect_action:
        parser.error('--field 须与 --architect-action 一起使用')
    header=dict(capabilities_sha256=data['capabilities_sha256'],gui_required=False)
    if args.routes:
        data=dict(**header,tool_routes=data['tool_routes'])
    if args.recipe:
        tool='structure_preview' if args.recipe=='structure' else args.recipe
        schema=data['agent_tools'][tool]['parameters']
        if args.recipe=='structure':
            schema=schema['properties']['spec']
        data=dict(**header,tool=args.recipe,arguments=schema,
                  example=data['architecture'].get('recipe_examples',{}).get(args.recipe))
    if args.operations:
        data=dict(**header,operations={kind:dict(title=label,hint=hint) for kind,(label,_,hint) in data['tools'].items()})
    if args.operation:
        data=dict(**header,kind=args.operation,parameters=data['operation_parameters'][args.operation],
                  common_example=data['common'],optional_fields=data['optional_operation_fields'])
    if args.architect_action:
        architecture=data['architecture']
        schema=architecture['actions'][args.architect_action]
        result=dict(**header,action=args.architect_action)
        if args.field:
            keys=args.field.split('.')
            if keys[0]=='plan' and 'plan' in schema.get('properties',{}):
                schema=architecture['plan']
                keys=keys[1:]
            for key in keys:
                if schema.get('type')=='array':
                    schema=schema['items']
                schema=schema.get('properties',{}).get(key)
                if schema is None:
                    parser.error('未知建筑请求字段：'+args.field)
            result['field']=args.field
            example=architecture.get('field_examples',{}).get(args.field)
            if example is not None:
                result['example']=example
        data=dict(**result,parameters=schema)
    if args.block_state:
        from nbt_collision import state_support
        data=dict(**header,state=args.block_state,**state_support(args.block_state))
    if args.architecture:data=dict(architecture=data['architecture'],capabilities_sha256=data['capabilities_sha256'],gui_required=False)
    if args.model:data=dict(working_model=data['working_model'],capabilities_sha256=data['capabilities_sha256'],gui_required=False)
    if args.agent_tool:
        result=dict(**header,agent_tools={args.agent_tool:data['agent_tools'][args.agent_tool]},
                    session_available=args.agent_tool in data.get('agent_session',{}).get('tools',[]))
        if args.agent_tool=='structure_preview':
            result['example']={'spec':data['architecture']['recipe_examples']['structure']['arguments']}
        data=result
    print(json.dumps(data,ensure_ascii=False,indent=2))
