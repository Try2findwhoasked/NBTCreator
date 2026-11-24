"""Persist an authoring workflow inside a registered modelling batch run."""
from pathlib import Path
import json

from nbt_agent import protocol
from nbt_composition.object_scene import atomic, engine_hash
from nbt_composition.working_model import WorkingModel, model_hash
from nbt_project import batches
from nbt_project.prompts import index_lock, inside
from nbt_review.reference_pack import IDENTIFIER, bound_file, reference_issues, register_pack


def identifier(value):
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise ValueError('需要有效的工作包或空间 ID')
    return value


def check_revision(record, expected):
    if record['revision'] != expected:
        protocol.error('REVISION_CONFLICT', '记录已更新，请先读取当前修订', details={'current': record['revision']})


def check_references(workspace, run):
    issues = reference_issues(workspace, run['references'])
    if issues:
        protocol.error('REFERENCE_CHANGED', '参考图已变化，请重新绑定', details={'images': issues})
    layout = run.get('layout')
    if layout and batches.sha(bound_file(workspace, layout['path'])) != layout['sha256']:
        protocol.error('EVIDENCE_CHANGED', '冻结的布局回执已变化')


def create_run(workspace, request):
    mode = request['mode']
    if mode not in ('image_guided', 'existing_draft', 'text_only') or not request['task'].strip():
        raise ValueError('需要有效的制作模式和任务说明')
    return dict(schema_version=1, id=request['run_id'], batch_id=request['batch_id'], mode=mode,
                task=request['task'], revision=1, phase='planned' if mode == 'image_guided' else 'references_bound',
                references=None, baseline=None, spaces=[], packages={}, merges={}, draft=None,
                operation_receipts={})


def inspect_run(workspace, run, view='compact'):
    from nbt_agent.authoring_tasks import public_package
    if view not in ('compact', 'full'):
        raise ValueError('运行视图须为 compact 或 full')
    result = {key: run[key] for key in ('schema_version', 'id', 'batch_id', 'mode', 'task', 'phase', 'revision', 'baseline', 'draft')}
    result['reference_issues'] = reference_issues(workspace, run['references'])
    result['reference_status'] = ('changed' if result['reference_issues'] else 'bound' if run['references']
                                  else 'required' if run['mode'] == 'image_guided' else 'not_applicable')
    result['next_action'] = (('replace_reference_or_start_new_run' if run['baseline'] else 'bind_reference') if result['reference_issues'] else
                             {'planned': 'bind_reference', 'references_bound': 'bind_baseline',
                              'baseline_bound': 'inspect_packages', 'review_ready': 'save_draft',
                              'draft_saved': 'inspect_draft'}[run['phase']])
    packages = []
    for package in run['packages'].values():
        redacted = public_package(package)
        if view == 'compact':
            redacted = {key: redacted[key] for key in ('id', 'parent_id', 'depth', 'revision', 'status')}
        else:
            redacted.pop('candidate', None)
        packages.append(redacted)
    result['packages'] = packages
    if view == 'full':
        result.update(references=run['references'], spaces=run['spaces'], layout=run.get('layout'),
                      interfaces=run.get('interfaces', []), merges=list(run['merges'].values()),
                      reviews=list(run.get('reviews', {}).values()))
    return result


def source_binding(workspace, working):
    return dict(source=working.source.relative_to(workspace).as_posix(), source_sha256=working.source_sha256,
                model_sha256=model_hash(working.model, working.walls),
                context_sha256=protocol.fingerprint('coordinates', working.context), engine_sha256=engine_hash())


def open_baseline(workspace, run, *, check_parent=True):
    binding = run['baseline']
    if binding is None:
        protocol.error('BASELINE_REQUIRED', '请先绑定制作源')
    context = binding.get('coordinates')
    file = bound_file(workspace, context['path']) if context else None
    if file and batches.sha(file) != context['sha256']:
        protocol.error('SOURCE_BINDING_CHANGED', '冻结的坐标文件已变化')
    working = WorkingModel.open(workspace, inside(workspace, binding['source']), context=file, source_sha256=binding['source_sha256'])
    actual = source_binding(workspace, working)
    if context:
        actual['coordinates'] = context
    if actual != binding:
        protocol.error('SOURCE_BINDING_CHANGED', '制作源、坐标上下文或引擎已变化', details={'actual': actual})
    if check_parent:
        working._assert_parent(working._building)
    return working


def bind_baseline(workspace, run, request):
    from nbt_agent.authoring_tasks import boxes, new_package

    if run['phase'] != 'references_bound':
        protocol.error('RUN_PHASE_CONFLICT', '请先完成参考图阶段')
    check_references(workspace, run)
    source = inside(workspace, request['source'])
    if source.suffix.lower() != '.snbt':
        raise ValueError('制作运行需要普通完整 SNBT')
    context = request.get('coordinates')
    context_file = bound_file(workspace, context['path']) if context else None
    if context_file and batches.sha(context_file) != context['sha256']:
        protocol.error('SOURCE_BINDING_CHANGED', '坐标文件哈希与登记不一致')
    working = WorkingModel.open(workspace, source, context=context_file, source_sha256=request['source_sha256'])
    working._assert_parent(working._building)
    root = dict(lo=[0, 0, 0], hi=[n - 1 for n in working.model.size])
    layout = request.get('layout')
    if layout:
        file = bound_file(workspace, layout['path'])
        if batches.sha(file) != layout['sha256']:
            protocol.error('EVIDENCE_INVALID', '布局回执哈希不一致')
        layout = dict(path=file.relative_to(workspace).as_posix(), sha256=layout['sha256'])
    spaces = request['spaces']
    if not spaces or len(spaces) > 128:
        raise ValueError('请登记 1～128 个有明确用途的空间')
    seen = set()
    for space in spaces:
        key = identifier(space['id'])
        if key in seen or not isinstance(space['purpose'], str) or not space['purpose'].strip():
            raise ValueError('空间 ID 须唯一且须说明用途')
        boxes([space['box']], [root])
        seen.add(key)
    interfaces = request.get('interfaces', [])
    interface_ids = set()
    for interface in interfaces:
        key = identifier(interface['id'])
        sides = interface['spaces']
        if key in interface_ids or len(sides) != 2 or len(set(sides)) != 2 or not set(sides) <= seen:
            raise ValueError('共享接口须有唯一 ID，并关联两个不同空间')
        boxes([interface['box']], [root])
        interface_ids.add(key)
    binding = source_binding(workspace, working)
    if context_file:
        if batches.sha(context_file) != context['sha256']:
            protocol.error('SOURCE_BINDING_CHANGED', '读取期间坐标文件已变化')
        binding['coordinates'] = dict(path=context_file.relative_to(workspace).as_posix(), sha256=context['sha256'])
    run.update(phase='baseline_bound', baseline=binding, spaces=spaces,
               layout=layout, interfaces=interfaces)
    run['packages']['root'] = new_package('root', None, run['baseline'], [root], [root],
                                          boxes(request.get('protected_boxes', []), [root]))
    return inspect_run(workspace, run)


def run_folder(workspace, request):
    _, registry = batches.index(workspace)
    entry = next((item for item in registry['tasks'] if item['id'] == request['batch_id']), None)
    if not entry:
        protocol.error('BATCH_NOT_FOUND', '制作批次不存在')
    _, batch = batches.task_document(workspace, entry)
    attempt = next((item for item in batch['runs'] if item['id'] == request['run_id'] and item['stage'] == 'authoring'), None)
    if not attempt:
        protocol.error('RUN_NOT_FOUND', '批次内的制作运行不存在')
    directory = inside(workspace, attempt['directory'])
    if not directory.is_relative_to(inside(workspace, batch['workspace_dir']) / 'runs'):
        raise ValueError('批次运行路径无效')
    return directory


def dispatch(workspace, action, request, *, session=None):
    from nbt_agent import authoring_tasks
    from nbt_composition import authoring_merge

    workspace = Path(workspace).resolve()
    folder = run_folder(workspace, request)
    file = inside(workspace, folder / 'authoring.json')
    with index_lock(workspace, folder, timeout=15):
        run = json.loads(file.read_bytes()) if file.is_file() else None
        if run is None and action != 'create':
            protocol.error('RUN_NOT_FOUND', '请先创建制作运行')
        if session is not None:
            from nbt_agent.authoring_views import scoped_request
            action, request = scoped_request(workspace, run, action, request, session)
        if action == 'inspect':
            return inspect_run(workspace, run, request.get('view', 'compact'))
        if action == 'context':
            return authoring_tasks.package_context(workspace, run, request)
        if action == 'brief':
            from nbt_agent.authoring_views import projection
            return projection(workspace, folder, run, request)
        if action == 'block_state':
            from nbt_agent.authoring_views import block_state
            return block_state(workspace, run, request)
        cached = protocol.replay(workspace, run or {}, action, request)
        if cached is not None:
            return cached
        if len((run or {}).get('operation_receipts', {})) >= 20000:
            protocol.error('RECEIPT_LIMIT', '制作运行的操作回执已达上限')
        if action == 'create':
            if run is not None:
                protocol.error('RUN_EXISTS', '该制作运行已创建')
            run = create_run(workspace, request)
            result = inspect_run(workspace, run)
        else:
            if action in ('bind_reference', 'bind_baseline', 'issue', 'reissue', 'plan_merge', 'save_draft',
                          'prepare_review', 'record_observation'):
                check_revision(run, request['run_revision'])
                run['revision'] += 1
            if action == 'bind_reference':
                if run['phase'] == 'draft_saved' or run['mode'] == 'text_only':
                    protocol.error('RUN_PHASE_CONFLICT', '当前运行无法绑定图像参考')
                references = register_pack(workspace, request['pack'])
                if run['baseline'] and references != run['references']:
                    protocol.error('REFERENCE_CHANGED', '基线已冻结；不同参考图须另开制作运行并重新签发工作包')
                run['references'] = references
                if run['phase'] == 'planned':
                    run['phase'] = 'references_bound'
                result = inspect_run(workspace, run, 'full')
            elif action == 'bind_baseline':
                result = bind_baseline(workspace, run, request)
            elif action in ('plan_merge', 'save_draft'):
                result = authoring_merge.dispatch(workspace, folder, run, action, request)
            elif action in ('prepare_review', 'record_observation'):
                from nbt_review import authoring_review
                result = authoring_review.dispatch(workspace, folder, run, action, request)
            elif action == 'report_region':
                from nbt_agent.authoring_views import report_region
                check_references(workspace, run)
                open_baseline(workspace, run)
                result = report_region(run, request)
            else:
                result = authoring_tasks.dispatch(workspace, run, action, request)
        protocol.receipt(workspace, run, action, request, result)
        atomic(file, protocol.canonical(run))
        return result
