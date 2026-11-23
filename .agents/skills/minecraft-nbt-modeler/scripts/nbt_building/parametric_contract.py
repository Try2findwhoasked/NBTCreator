"""Acceptance constraints retained by the caller, never trusted from a model reply."""
from copy import deepcopy
import hashlib,json
from nbt_model import state, AIR_NAMES
from nbt_pattern.ornament import PROFILES

def contract(constraints):
    from nbt_structure_agent import _schema,definitions
    _schema(constraints,definitions()['parametric_contract']['parameters']['properties']['constraints'],'硬约束')
    c=constraints
    if c.get('min_density',0)>c.get('max_density',100):raise ValueError('最小装饰密度不能大于最大值')
    profiles=c.get('profiles',list(PROFILES))
    if c.get('require_decoration') and not any(p!='none' for p in profiles):raise ValueError('必须装饰与只允许none冲突')
    if c.get('motifs') and not any(m in PROFILES[p]['motifs'] for p in profiles for m in c['motifs']):raise ValueError('允许的风格与纹样没有交集')
    if 'materials' in c:
        materials=[state(s) for s in c['materials']]
        if any(s in AIR_NAMES for s in materials):raise ValueError('材质白名单不能含空气')
    else:materials=None
    schema=deepcopy(definitions()['parametric_compile']['parameters']);props=schema['properties']
    for key in ('kind','size'):
        if key in c:props[key]['enum']=[c[key]]
    ornament=props['ornament'];op=ornament['properties']
    if c.get('require_decoration'):
        profiles=[p for p in profiles if p!='none'];schema['required'].append('ornament');ornament['required']=['profile']
    op['profile']['enum']=profiles
    if 'motifs' in c:op['motif']['enum']=['auto',*c['motifs']]
    op['density']['minimum']=c.get('min_density',0);op['density']['maximum']=c.get('max_density',100);op['depth']['maximum']=c.get('max_depth',3)
    if materials:
        for key in ('material','accent','foliage','stair_material'):props[key]['enum']=materials
        op['material']['enum']=materials
    if 'max_blocks' in c:props['max_changed_blocks']['maximum']=c['max_blocks']
    return dict(response_schema=schema,constraints=deepcopy(c),constraints_sha256=hashlib.sha256(json.dumps(c,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest(),
                semantic_checks=['resolved_profile_and_motif','resolved_defaults_and_materials','shared_geometry_bounds_and_budget','actual_block_and_operation_counts','nonzero_decoration_if_required'],
                trust='constraints必须来自调用方保留的用户要求；禁止从模型返回对象中取回constraints。JSON Schema不替代本地语义验收。',model_modified=False)

def validate(workspace,proposal,constraints):
    from nbt_structure_agent import _schema
    from nbt_building.parametric import compile_object
    checked=contract(constraints);_schema(proposal,checked['response_schema'],'模型方案')
    # Impose the trusted budget when the model omits it; never accept an explicit excess.
    proposal=deepcopy(proposal)
    if 'max_blocks' in constraints:proposal.setdefault('max_changed_blocks',constraints['max_blocks'])
    result=compile_object(workspace,proposal);c=constraints;o=result['ornament']
    if 'profiles' in c and o['profile'] not in c['profiles']:raise ValueError('解析后的装饰风格违反硬约束')
    if c.get('require_decoration') and (o['profile']=='none' or o['added_or_recolored_blocks']==0):raise ValueError('硬约束要求产生实际装饰')
    if o['profile']!='none':
        if 'motifs' in c and o['motif'] not in c['motifs']:raise ValueError('解析后的纹样违反硬约束')
        if not c.get('min_density',0)<=o['density']<=c.get('max_density',100) or o['depth']>c.get('max_depth',3):raise ValueError('默认或显式装饰参数违反硬约束')
    spec=result['spec']
    if result['block_count']>c.get('max_blocks',65536) or len(spec['operations'])>c.get('max_operations',128):raise ValueError('实际方块或操作数量违反硬约束')
    if 'materials' in c:
        from nbt_structure_agent import build
        allowed={state(s) for s in c['materials']};actual=set(build(workspace,spec)['palette'])
        if actual-allowed:raise ValueError('实际材质违反白名单（含默认材质和工具生成材质）')
    return dict(result,accepted=True,constraints=deepcopy(c),constraints_sha256=checked['constraints_sha256'],approval_created=False)
