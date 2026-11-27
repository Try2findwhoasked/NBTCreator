"""Machine actions over the shared WorkingModel and version publisher."""

from contextlib import contextmanager, nullcontext
import hashlib
import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from nbt_agent import protocol
from nbt_agent.structure import _schema
from nbt_composition.change_policy import ChangePolicyError
from nbt_composition.working_model import prepare_request
from nbt_project.model_versions import VersionStore, file_hash, publication_lock, require_authoring_workspace, verify_version
from nbt_project.prompts import index_lock, inside, relative
from nbt_project.web_paths import project_paths, workspace_path
from nbt_runtime.catalog import catalog


def source_evidence(workspace, working):
    if working.source is None:
        return None
    return dict(source=relative(workspace, working.source), absolute_source=str(working.source),
                source_sha256=working.source_sha256, revision=working.parent_revision,
                source_kind='assembly' if working._assembly_binding else 'master')


def prepare(workspace, request, *, inspect_only=False):
    if set(request) & {'save_draft', 'validate', 'cameras'}:
        protocol.error('INVALID_REQUEST', 'model 只接收工作模型输入；制作版和预览使用各自的入口')
    _schema(request, catalog()['working_model']['parameters'], '工作模型请求')
    if inspect_only and request.get('actions'):
        protocol.error('INVALID_REQUEST', 'model.inspect 不接收模型操作；候选使用 model.candidate')
    if any('preview' in action for action in request.get('actions', [])):
        protocol.error('INVALID_REQUEST', '机器接口中的模型操作不写预览目录')

    inputs = dict(request)
    if 'source' in inputs:
        source = inside(workspace, workspace_path(workspace, inputs['source']))
        if not source.is_file():
            protocol.error('STALE_SOURCE', '原制作源不存在', details={'source': relative(workspace, source)})
        inputs['source'] = str(source)
    if isinstance(inputs.get('context'), str):
        context = (workspace / inputs['context']).resolve()
        if not context.is_relative_to(workspace):
            protocol.error('INVALID_REQUEST', '坐标上下文须位于当前工作区')
        inputs['context'] = str(context)
    return prepare_request(workspace, inputs)


def candidate_token(request, working):
    return protocol.fingerprint('model.candidate', [request, working.source_sha256, working.parent_revision,
                                                     working.limits, working._content_token()])


def checked_candidate(workspace, args):
    candidate = args['candidate_sha256']
    if not re.fullmatch(r'[a-f0-9]{64}', candidate):
        protocol.error('INVALID_REQUEST', 'candidate_sha256 须为 64 位小写十六进制指纹')
    working, _ = prepare(workspace, args['model'])
    if candidate_token(args['model'], working) != candidate:
        protocol.error('STALE_CANDIDATE', '候选与当前输入不符，请重新生成候选',
                       details={'candidate_sha256': candidate})
    return working


@contextmanager
def operation(workspace, action, args):
    require_authoring_workspace(workspace)
    key = protocol.request_key(args)
    directory = inside(workspace, Path('nbt_models/_workspaces/agent_protocol/model') / hashlib.sha256(key.encode()).hexdigest())
    directory.mkdir(parents=True, exist_ok=True)
    marker = inside(workspace, directory / 'operation.json')
    fingerprint = protocol.fingerprint('model.'+action, args)
    with index_lock(workspace, directory, timeout=30):
        index = {'fingerprint': fingerprint}
        if marker.is_file():
            try:
                with marker.open('rb') as stream:
                    raw = stream.read(16 * 1024 + 1)
                if len(raw) > 16 * 1024:
                    raise ValueError('模型操作登记过大')
                index = json.loads(raw)
            except ValueError:
                protocol.error('RECEIPT_CHANGED', '模型操作登记无法读取')
            if not isinstance(index, dict) or 'fingerprint' not in index:
                protocol.error('RECEIPT_CHANGED', '模型操作登记无效')
        if index.get('fingerprint') != fingerprint:
            protocol.error('IDEMPOTENCY_CONFLICT', '相同 request_id 不能用于不同请求')
        yield directory, marker, index


def saved_version(workspace, receipt):
    source = Path(receipt['source'])
    return dict(receipt, source=relative(workspace, source), absolute_source=str(source),
                output=relative(workspace, receipt['output']))


def repair_history(workspace, result):
    source = inside(workspace, workspace_path(workspace, result['source']))
    paths = project_paths(source)
    with publication_lock(workspace, paths['workdir']):
        try:
            manifest = verify_version(paths['version'])
        except (OSError, ValueError, KeyError, TypeError) as failure:
            protocol.error('RECEIPT_CHANGED', '原操作的制作版验证失败', details={'reason': str(failure)})
        if manifest['revision'] != result['revision']:
            protocol.error('RECEIPT_CHANGED', '原操作的制作版清单已变化')
        return saved_version(workspace, VersionStore(workspace).history_receipt(paths['version'], manifest, paths['workdir']))


def commit(workspace, args):
    from nbt_composition.object_scene import atomic

    session = args.get('task_session')
    if 'task_lease' in args:
        if session is not None:
            protocol.error('INVALID_REQUEST', 'task_session 和 task_lease 只能提供其中一项')
        session = args['task_lease']
        if (not isinstance(session, dict) or set(session) != {'id', 'lease_token', 'fence'}
                or type(session['fence']) is not int or session['fence'] < 1
                or any(not isinstance(session[key], str) or not re.fullmatch(r'[a-f0-9]{32}', session[key])
                       for key in ('id', 'lease_token'))):
            protocol.error('INVALID_REQUEST', 'task_lease 须包含任务 id、lease_token 和 fence')
    model_contract = catalog()['working_model']['parameters']['properties']
    with operation(workspace, 'commit', args) as (_, marker, index):
        _schema(args['save'], model_contract['save_draft'], '制作版信息')
        result = protocol.replay(workspace, index, 'model.commit', args)
        if result is not None and not result['history_pending']:
            return result
        if result is not None:
            result = repair_history(workspace, result)
            index.pop('operation_receipts')
        else:
            intent = index.get('publication')
            target = inside(workspace, workspace_path(workspace, intent['target'])) if intent else None

            def remember_target(path, revision, opened_head, opened_history_source):
                index['publication'] = dict(target=relative(workspace, path), revision=revision,
                                            opened_head=opened_head, opened_history_source=opened_history_source)
                atomic(marker, protocol.canonical(index))

            if target is not None and target.exists():
                saved = VersionStore(workspace).recover_commit(target, intent, session)
            else:
                working = checked_candidate(workspace, args)
                saved = working.save_draft(**args['save'], task_session=session, _remember_target=remember_target)
            result = saved_version(workspace, saved)
        protocol.receipt(workspace, index, 'model.commit', args, result)
        atomic(marker, protocol.canonical(index))
        return result


def check_preview(workspace, result):
    from nbt_task import preview_source_matches

    source = inside(workspace, result['source'])
    snapshot = inside(workspace, result['snapshot'])
    cameras = inside(workspace, result['cameras'])
    try:
        if (file_hash(source) == result['source_sha256'] and file_hash(snapshot) == result['snapshot_sha256']
                and file_hash(cameras) == result['cameras_sha256']
                and preview_source_matches(source, json.loads(snapshot.read_bytes()))):
            return result
    except (OSError, ValueError):
        pass
    protocol.error('RECEIPT_CHANGED', '原预览主稿、分区、快照或相机文件已变化')


def preview(workspace, args):
    from nbt_composition.object_scene import atomic

    camera_schema = catalog()['working_model']['parameters']['properties']['cameras']
    with operation(workspace, 'preview', args) as (directory, marker, index):
        _schema(args['cameras'], camera_schema, '预览相机')
        working = checked_candidate(workspace, args)
        building = working._building
        target = inside(workspace, directory / 'preview')
        def lock():
            return publication_lock(workspace, building) if building else nullcontext()

        def recheck():
            working._unchanged()
            if building:
                working._assert_parent(building)

        with lock():
            recheck()
            if target.exists():
                result = protocol.replay(workspace, index, 'model.preview', args)
                if result is None:
                    protocol.error('RECEIPT_CHANGED', '原预览回执缺失')
                return check_preview(workspace, result)

        working.validate_for_save()
        with TemporaryDirectory(dir=directory) as temporary:
            stage = Path(temporary) / 'preview'
            materialized = working.preview(stage, args['cameras'], published_output=target)
            result = dict(candidate_sha256=args['candidate_sha256'], model_sha256=materialized['model_sha256'],
                          source_kind='assembly' if working._assembly_binding else 'master', visual_review='pending',
                          approval_created=False, nbt_exported=False, asset_written=False)
            for field in ('source', 'snapshot', 'cameras'):
                file = Path(materialized[field])
                result[field] = relative(workspace, target / file.relative_to(stage))
                result[field+'_sha256'] = file_hash(file)
            with lock():
                recheck()
                protocol.receipt(workspace, index, 'model.preview', args, result)
                atomic(marker, protocol.canonical(index))
                stage.rename(target)
        return result


def dispatch(workspace, action, args):
    workspace = Path(workspace).resolve()
    try:
        if action == 'commit':
            return commit(workspace, args)
        if action == 'preview':
            return preview(workspace, args)
        request = args['model']
        working, actions = prepare(workspace, request, inspect_only=action == 'inspect')
        result = dict(model=working.inspect(positions=request.get('positions')),
                      source=source_evidence(workspace, working))
        if action == 'candidate':
            result.update(candidate_sha256=candidate_token(request, working), actions=actions,
                          diff=working.diff_summary(), validation=working.validate_for_save())
        return result
    except ChangePolicyError as failure:
        protocol.error(failure.kind, str(failure), details=dict(positions=list(failure.positions), total=failure.total))
