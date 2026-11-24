"""Preflight and publish one fenced batch of ordinary SNBT edits."""
from pathlib import Path
import tempfile

from nbt_agent import protocol
from nbt_agent.authoring_tasks import check_scope, inside, owned, read_fingerprint
from nbt_composition.object_scene import engine_hash
from nbt_composition.change_policy import ChangePolicyError
from nbt_composition.working_model import ModelConflict, model_hash, point
from nbt_project.authoring_runs import check_references, open_baseline
from nbt_project.batches import sha
from nbt_refine import read_master
from nbt_snbt import save_snbt


def selected_patches(run, selected):
    if not selected or len(selected) > 128:
        raise ValueError('请选择 1～128 个候选')
    packages = {}
    changes = {}
    for row in selected:
        key = row['package_id']
        package = run['packages'].get(key, {})
        candidate = package.get('candidate')
        if (key in packages or package.get('status') not in ('submitted', 'checked') or not candidate or
                protocol.fingerprint('patch_candidate', candidate) != row['sha256']):
            protocol.error('CANDIDATE_CHANGED', '候选不存在、重复或哈希已变化', details={'package_id': key})
        if (candidate['package_revision'] != package['revision'] or candidate['read_sha256'] != read_fingerprint(package)
                or package['source_binding'] != run['baseline']):
            protocol.error('READ_BINDING_CHANGED', '候选来源或读取指纹已变化', details={'package_id': key})
        packages[key] = package
        for patch in candidate['patches']:
            pos = point(patch['pos'])
            check_scope(package, pos)
            if pos in changes:
                protocol.error('PATCH_OVERLAP', '候选修改了相同坐标', details={'pos': list(pos), 'package_id': key,
                                                                              'other': changes[pos][0]})
            changes[pos] = (key, patch)
    dependencies = []
    for key, package in packages.items():
        for pos, (writer, _) in changes.items():
            if writer != key and any(inside(pos, box) for box in package['read_boxes']):
                dependencies.append(dict(pos=list(pos), reader=key, writer=writer))
                if len(dependencies) == 32:
                    break
        if len(dependencies) == 32:
            break
    if dependencies:
        protocol.error('READ_DEPENDENCY_CHANGED', '另一个候选改动了只读邻域，须重读接点后再签发',
                       details={'dependencies': dependencies})
    return packages, changes


def verify_parent_request(run, request):
    if request['parent_source_sha256'] != run['baseline']['source_sha256']:
        protocol.error('STALE_PARENT', '请求中的父源与冻结制作版不同', details={'baseline': run['baseline']})


def build_candidate(workspace, run, selected, *, check_parent):
    working = open_baseline(workspace, run, check_parent=check_parent)
    packages, changes = selected_patches(run, selected)
    if len(changes) > working.limits['max_written_positions']:
        protocol.error('WRITE_BUDGET', '候选并集超出写入上限', details={'count': len(changes)})
    try:
        difference = working.patch(row for _, row in changes.values())
        validation = working.validate()
    except ModelConflict as exc:
        conflicts = [dict(item, package_id=changes.get(tuple(item.get('pos', [])), (None,))[0])
                     for item in exc.conflicts[:32]]
        protocol.error(exc.code, str(exc), details={'conflicts': conflicts})
    except ChangePolicyError as exc:
        protocol.error(exc.kind, str(exc), details={'total': exc.total, 'positions': list(exc.positions)[:32]})
    return working, packages, difference, validation


def plan_merge(workspace, folder, run, request):
    if len(run['merges']) >= 128:
        raise ValueError('该运行最多保留 128 次合模预检')
    working, packages, difference, validation = build_candidate(workspace, run, request['candidates'], check_parent=True)
    specification = dict(parent=run['baseline'], candidates=request['candidates'],
                         references_sha256=(run['references'] or {}).get('sha256'), model_sha256=difference['model_sha256'])
    merge_sha256 = protocol.fingerprint('authoring_merge', specification)
    candidate = folder / ('candidate-' + merge_sha256 + '.snbt')
    with tempfile.TemporaryDirectory(dir=folder) as directory:
        temporary = Path(directory) / 'model.snbt'
        save_snbt(temporary, working.model, working.walls, palette=working._palette, extras=working._extras)
        if model_hash(*read_master(temporary)) != difference['model_sha256']:
            raise ValueError('合模候选回读与实际补丁不一致')
        if candidate.is_file():
            if sha(candidate) != sha(temporary):
                protocol.error('CANDIDATE_CHANGED', '合模候选已被覆盖')
        else:
            temporary.replace(candidate)
    receipt = dict(specification, merge_sha256=merge_sha256, source=candidate.relative_to(workspace).as_posix(),
                   source_sha256=sha(candidate), geometry_sha256=working.model.fingerprint(),
                   validation=validation, difference=difference,
                   visual_review='pending', run_revision=run['revision'])
    run['merges'][merge_sha256] = receipt
    for package in packages.values():
        package['status'] = 'checked'
    return receipt


def save_merged_draft(workspace, run, request):
    merge = run['merges'].get(request['merge_sha256'])
    if merge is None or merge['candidates'] != request['candidates']:
        protocol.error('MERGE_CHANGED', '请选择原预检及同一候选清单')
    if merge['references_sha256'] != (run['references'] or {}).get('sha256'):
        protocol.error('REFERENCE_CHANGED', '预检绑定的参考图已变化')
    from nbt_review.authoring_review import verify_review
    review = verify_review(workspace, run, merge, request.get('review_sha256'))
    if review is None and request.get('technical_trial') != 'pending_visual_review':
        protocol.error('VISUAL_REVIEW_REQUIRED', '请提供完整视觉审阅回执，或显式声明 pending_visual_review 进行技术试用')
    candidate = workspace / merge['source']
    if not candidate.is_file() or sha(candidate) != merge['source_sha256']:
        protocol.error('CANDIDATE_CHANGED', '预检的候选 SNBT 已变化')
    working, packages, difference, _ = build_candidate(workspace, run, merge['candidates'], check_parent=False)
    if difference['model_sha256'] != merge['model_sha256']:
        protocol.error('MERGE_CHANGED', '重新应用候选得到不同模型')
    attachment = dict(merge_sha256=merge['merge_sha256'], batch_id=run['batch_id'], run_id=run['id'],
                      candidates=merge['candidates'], visual_review='candidate_observed' if review else 'pending',
                      request_id=request['request_id'], review_sha256=request.get('review_sha256'))

    def before_publish():
        owned(run, request)
        check_references(workspace, run)
        if engine_hash() != run['baseline']['engine_sha256']:
            protocol.error('SOURCE_BINDING_CHANGED', '发布前引擎已变化')
        if sha(candidate) != merge['source_sha256']:
            protocol.error('CANDIDATE_CHANGED', '发布前合模候选已变化')
        if review:
            verify_review(workspace, run, merge, review['sha256'])

    from nbt_project.web_paths import project_paths
    version = project_paths(working.source)['version']
    name = request.get('name_zh')
    if name is None and not (version / 'room_description.json').is_file():
        name = working._building.name
    saved = working.save_draft(name_zh=name, attachments={'authoring-run.json': attachment},
                               before_publish=before_publish)
    draft = dict(saved, source=Path(saved['source']).relative_to(workspace).as_posix(),
                 output=Path(saved['output']).relative_to(workspace).as_posix(), merge_sha256=merge['merge_sha256'],
                 visual_review='pending', candidate_review_sha256=request.get('review_sha256'),
                 run_revision=run['revision'])
    run.update(phase='draft_saved', draft=draft)
    for package in packages.values():
        package['status'] = 'adopted'
    return draft


def dispatch(workspace, folder, run, action, request):
    root = owned(run, request)
    if root['depth'] != 1:
        protocol.error('LEAD_REQUIRED', '合模预检和发布只授予一级负责人')
    if run['phase'] not in ('baseline_bound', 'review_ready'):
        protocol.error('RUN_PHASE_CONFLICT', '当前阶段无法合模或发布')
    verify_parent_request(run, request)
    check_references(workspace, run)
    if action == 'plan_merge':
        return plan_merge(workspace, folder, run, request)
    return save_merged_draft(workspace, run, request)
