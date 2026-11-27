"""Validate the frozen creative brief, model requests and deterministic gates."""

from nbt_building.plan import fingerprint
from nbt_composition.working_model import ModelConflict
from nbt_project.constraints import validate_selection
from nbt_project.history import file_hash
from nbt_project.prompts import inside


def fields(value, required=(), optional=()):
    required, optional = set(required), set(optional)
    if not isinstance(value, dict) or not required <= value.keys() or value.keys() - required - optional:
        raise ValueError('请求缺少必填字段或含未知字段')
    return value


def text(value, maximum=2000):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(f'需要有效文字，最多 {maximum} 字')
    return value


def evidence(workspace, value):
    fields(value, ('path', 'sha256'))
    import re
    if not isinstance(value['path'],str) or not isinstance(value['sha256'],str) or not re.fullmatch(r'[0-9a-f]{64}',value['sha256']):
        raise ValueError('证据需要有效路径和 SHA256')
    path = inside(workspace, value['path'])
    if not path.is_file() or file_hash(path) != value['sha256']:
        raise ModelConflict('STALE_SOURCE', [dict(path=str(path), reason='证据文件缺失或哈希已变化')])
    return path


def options(workspace, policy, value):
    fields(value, optional=('axes', 'reference', 'comparison', 'retained_review', 'reference_roles'))
    if 'reference_roles' in value:
        from nbt_agent.creation_policy import validate_reference_roles
        validate_reference_roles(value['reference_roles'])
    axes = value.get('axes', [])
    if not isinstance(axes, list) or len(axes) > 8:
        raise ValueError('最多登记 8 个要探索的设计轴')
    for axis in axes:
        text(axis, 160)
    if len(axes) != len(set(axes)):
        raise ValueError('设计轴不能重复')
    if policy['mode'] == 'maximum' and not axes:
        raise ValueError('极限效果须先登记候选之间要比较的设计轴')
    if 'reference' in value:
        from nbt_review.reference_views import load_reference
        ref = fields(value['reference'], ('manifest', 'fixed', 'explore'), ('canvas_size',))
        if 'canvas_size' in ref and (not isinstance(ref['canvas_size'],list) or len(ref['canvas_size'])!=3
                or any(type(value) is not int or value<1 for value in ref['canvas_size'])):
            raise ValueError('已知参考画布须给出三个正整数尺寸')
        for key in ('fixed', 'explore'):
            if not isinstance(ref[key], list) or not 1 <= len(ref[key]) <= 16:
                raise ValueError('分别列出参考图的已知条件和可探索部位')
            for item in ref[key]:
                text(item, 300)
        manifest=evidence(workspace, ref['manifest'])
        load_reference(manifest, ref['manifest']['sha256'])
    if 'comparison' in value:
        from nbt_review.reference_camera import checked_registered_camera
        comp=fields(value['comparison'], ('cameras', 'width', 'height'), ('bundle',))
        if any(type(comp[key]) is not int or not 64 <= comp[key] <= 4096 for key in ('width','height')):
            raise ValueError('比较图尺寸须为 64–4096 像素')
        cameras=evidence(workspace, comp['cameras'])
        if 'bundle' in comp:
            binding=checked_registered_camera(workspace,evidence(workspace,comp['bundle']),comp['bundle']['sha256'],
                                               cameras,comp['width'],comp['height'])
            if 'reference' not in value or binding['reference_sha256']!=value['reference']['manifest']['sha256']:
                raise ValueError('登记相机须与本轮参考图绑定')
    if 'retained_review' in value:
        from nbt_building.review import verify_for_return
        previous=evidence(workspace,value['retained_review'])
        if previous.name!='review-notes.json':
            raise ValueError('旧版对照须绑定真实审阅记录 review-notes.json')
        verify_for_return(workspace,previous.parent,value['retained_review']['sha256'])
    return value


def gates(frozen, model, reference=None):
    doc, context = frozen['document'], frozen['context']
    project = doc['project']
    rules = validate_selection(doc.get('constraints', []), project)
    size = rules.get('size', project.get('size'))
    if reference and reference.get('canvas_size') and list(model.model.size)!=reference['canvas_size']:
        raise ModelConflict('HANDOFF_CONSTRAINT',[dict(reason='参考图的已知画布尺寸不同',
            expected=reference['canvas_size'],actual=list(model.model.size))])
    fixed_size = rules.get('size_policy', 'fixed' if 'size' in rules else project.get('size_policy', 'fixed'))
    mode = rules.get('integration', context.get('mode', project.get('integration', 'standalone')))
    if mode == 'saodg' or fixed_size == 'fixed':
        if size is not None and list(model.model.size) != size:
            raise ModelConflict('HANDOFF_CONSTRAINT', [dict(reason='固定画布尺寸不同', expected=size, actual=list(model.model.size))])
    from nbt_composition.whole_validation import opening_policy, requires_enclosure, validation_mode
    if validation_mode(model.context) != mode:
        raise ModelConflict('HANDOFF_CONSTRAINT', [dict(reason='接入模式与交接不同')])
    combined = project.get('context', {}) | context | rules
    for key in ('require_enclosure','openings_policy','opening_size','cells','cell_size','openings','ports',
                'protected_boxes','reserved_boxes','protected_paths','start','targets','route_legs','interior_probes'):
        expected = combined.get(key)
        if expected is None or expected in ([], {}):
            continue
        actual = model.context.get(key)
        if key == 'require_enclosure':
            actual = requires_enclosure(model.context)
        if key == 'openings_policy':
            actual = opening_policy(model.context)
        if expected != actual and fingerprint(expected) != fingerprint(actual):
            raise ModelConflict('HANDOFF_CONSTRAINT', [dict(reason=key, expected=expected, actual=actual)])
    for key in ('buildingShape',):
        if key in rules:
            from nbt_library import shape_of
            if shape_of(model.model.size, model.context.get('cells', []), model.context.get('cell_size', 48)) != rules[key]:
                raise ModelConflict('HANDOFF_CONSTRAINT', [dict(reason='实际形状与已选约束不同', expected=rules[key])])


def model_request(policy, slot, role, phase, **evidence_refs):
    return dict(slot=slot, role=role, phase=phase,
                model=policy['quality_model' if role=='strong' else 'economy_model'] or None,
                dispatch='external_host', **evidence_refs)


def local_repair(before, after):
    """Keep the original programme and limit geometry changes to a few authored targets."""
    if not isinstance(before,dict) or not isinstance(after,dict):
        return
    from nbt_building.plan import normalize
    try:
        old=normalize(before)
    except ValueError:
        return  # An unparseable first proposal has no valid structure to preserve.
    new=normalize(after)
    frozen=('size','context','requirements','review_locations','quality','standards_snapshot','style','levels')
    changed_frozen=[key for key in frozen if old.get(key)!=new.get(key)]
    if changed_frozen:
        raise ModelConflict('REPAIR_SCOPE',[dict(reason='局部修复须保留方案条件', violations=changed_frozen)])
    changed=[]
    for section in ('parts','stairs','connections','spaces','activities','rules','views','surface_patterns'):
        original={row['id']:row for row in old.get(section,[])}
        updated={row['id']:row for row in new.get(section,[])}
        changed.extend(f'{section}/{key}' for key in sorted(original.keys()|updated.keys()) if original.get(key)!=updated.get(key))
    if old.get('envelope')!=new.get('envelope'):
        changed.append('envelope')
    if len(changed)>3:
        raise ModelConflict('REPAIR_SCOPE',[dict(reason='局部修复最多调整三处具名目标，可升级处理共享构造', violations=changed)])


def routes(strategy):
    return [model_request(strategy, str(number), strategy['initial_role'], 'global_design' if strategy['blind_review'] else 'draft')
            for number in range(1, strategy['initial_candidates']+1)]
