"""Immutable model versions, current heads, and history reconciliation."""

from contextlib import contextmanager
from contextvars import ContextVar
import hashlib
import json
import os
from pathlib import Path

from nbt_runtime.modeling_session import canonical

_publication_locks = ContextVar('working_model_publication_locks', default=frozenset())


@contextmanager
def publication_lock(workspace, building):
    """The CLI and desktop publisher use the same reentrant building lock."""
    from nbt_project.prompts import index_lock
    workspace, building = Path(workspace).resolve(), Path(building).resolve()
    key = str(building)
    if key in _publication_locks.get():
        yield
        return
    building.mkdir(parents=True, exist_ok=True)
    with index_lock(workspace, building, timeout=30):
        token = _publication_locks.set(_publication_locks.get() | {key})
        try:
            yield
        finally:
            _publication_locks.reset(token)


def digest(value):
    return hashlib.sha256(canonical(value).encode('utf8')).hexdigest()


def file_hash(file):
    with Path(file).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def require_authoring_workspace(workspace):
    engine = Path(__file__).resolve().parents[2]
    software = engine.parents[2] if engine.parent.name == 'skills' else None
    if workspace == software or workspace.is_relative_to(engine):
        raise ValueError('制作版保存在实际创作工作区，不写入软件源码或安装目录')


def write_json(file, value):
    file = Path(file)
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(canonical(value) + '\n', encoding='utf8')


def managed_manifest(source):
    """Recognize managed drafts even when their manifest has been lost."""
    from nbt_project.web_paths import project_paths
    source = Path(source).resolve()
    version = project_paths(source)['version']
    description = version / 'room_description.json'
    metadata = json.loads(description.read_text(encoding='utf8')) if description.is_file() else {}
    managed = ((version / 'model-version.json').exists() or version.name.startswith('v_model_')
        or (version / 'model-instances.json').exists() or metadata.get('model_revision'))
    if not managed:
        return None
    if not (version / 'model-version.json').is_file():
        raise ValueError('受管制作版本缺少清单')
    manifest = verify_version(version)
    if source != version / manifest.get('master', 'master/model.snbt'):
        raise ModelConflict('MODEL_SOURCE_MISMATCH', [dict(source=str(source))])
    return manifest


def head_file(workspace, building):
    workspace = Path(workspace).resolve()
    key = digest(Path(building).resolve().relative_to(workspace).as_posix())
    return workspace / '.nbtcreator/model-heads' / (key + '.json')


def publish_head(workspace, source):
    from nbt_project.web_paths import project_paths
    source = Path(source).resolve()
    manifest = managed_manifest(source)
    return _write_head(workspace, project_paths(source)['workdir'], source, manifest['revision'] if manifest else None)


def _write_head(workspace, building, source, revision):
    head = dict(revision=revision, source=source.relative_to(Path(workspace).resolve()).as_posix())
    _store_head(workspace, building, head)
    return head


def _store_head(workspace, building, data):
    from nbt_composition.object_scene import atomic
    file = head_file(workspace, building)
    file.parent.mkdir(parents=True, exist_ok=True)
    atomic(file, canonical(data).encode('utf8'))


def prepare_history_head(workspace, source, node, history_state):
    """Make a selection visible when the Git ref selects its history node."""
    from nbt_project.web_paths import project_paths
    building = project_paths(source)['workdir']
    current = VersionStore(workspace).read_head(building, history_state=history_state)
    manifest = managed_manifest(source)
    selection = dict(source=source.relative_to(workspace).as_posix(),
                     revision=manifest['revision'] if manifest else None)
    if current == selection:
        return False
    _store_head(workspace, building, dict(previous=current, selection=selection,
                                         history_building=node['building'], history_id=node['id']))
    return True


def parent_binding(workspace, source):
    """Read parent evidence from managed versions and new legacy conversions."""
    from nbt_project.web_paths import project_paths, workspace_path
    manifest = managed_manifest(source)
    if manifest:
        return manifest
    receipt = project_paths(source)['version'] / 'conversion.json'
    if not receipt.is_file():
        return {}
    data = json.loads(receipt.read_text(encoding='utf8'))
    if (data.get('status') != 'complete' or not data.get('parent_source') or not data.get('master_source')
            or not data.get('master_sha256') or workspace_path(workspace, data['master_source']) != source):
        return {}
    if file_hash(source) != data['master_sha256']:
        raise ValueError('旧版转换的制作源已变化')
    return dict(parent_source=data['parent_source'], parent_source_sha256=data['source_sha256'])


class ModelConflict(ValueError):
    def __init__(self, code, conflicts):
        self.code, self.conflicts = code, conflicts
        super().__init__(code + ': ' + canonical(conflicts[:32]))

    @property
    def recovery(self):
        if self.code == 'STALE_SOURCE':
            return dict(input='source, source_sha256',
                        next_check='重新打开任务所指制作源，核对版本、保护与审阅绑定后再生成请求。')
        if self.code == 'STALE_PARENT':
            return dict(input='source, source_sha256',
                        next_check='读取当前制作版及父版本记录，确认改动仍适用于任务后，从当前版本重建续版请求。')
        return None


def verify_version(version):
    """Verify immutable authoring inputs; previews and exports are derived."""
    version = Path(version).resolve()
    data = json.loads((version / 'model-version.json').read_text(encoding='utf8'))
    body = {key: value for key, value in data.items() if key != 'revision'}
    if data.get('schema_version') != 1 or digest(body) != data.get('revision'):
        raise ValueError('制作版本清单指纹不一致')
    master = data.get('master','master/model.snbt')
    if master not in ('master/model.snbt','master/assembly.json') or (master=='master/assembly.json') != (data.get('source_kind')=='assembly'):
        raise ValueError('制作版本主稿类型无效')
    required = {master, 'model-instances.json', 'coordinates.json', 'validation/working-model.json'}
    if data.get('phase') not in ('design','sealed','opened') or data.get('kind') not in ('building','component'):
        raise ValueError('制作版本阶段或类型无效')
    if data['phase'] == 'sealed':
        required.add('master/preopening.snbt')
    if not required.issubset(data.get('files', {})):
        raise ValueError('制作版本清单缺少必要文件')
    for name, expected in data['files'].items():
        file = version / name
        if not file.resolve().is_relative_to(version) or file.is_symlink() or not file.is_file() or file_hash(file) != expected:
            raise ValueError('制作版本文件已变化：' + name)
    if master == 'master/assembly.json':
        from nbt_composition.large_assembly import assembly_manifest
        path,raw,_,parts = assembly_manifest(version / master)
        if hashlib.sha256(raw).hexdigest()!=data['files'][master]:
            raise ValueError('制作版本组装清单已变化')
        for file,sha,_,_ in parts:
            name = file.relative_to(version).as_posix()
            if data['files'].get(name) != sha or file_hash(file)!=sha:
                raise ValueError('制作版本清单缺少组装分区或哈希不一致：'+name)
        if file_hash(path)!=data['files'][master]:
            raise ValueError('校验期间制作版本组装清单已变化')
    return data


class VersionStore:
    def __init__(self, workspace):
        self.workspace = Path(workspace).resolve()

    def read_head(self, building, *, history_state=None):
        from nbt_project.web_paths import prior_workspace_paths,workspace_path
        candidates=[building,*prior_workspace_paths(self.workspace,building)]
        files=[file for folder in candidates if (file:=head_file(self.workspace, folder)).is_file()]
        if not files:return None
        file=max(files,key=lambda current:current.stat().st_mtime_ns)
        head=json.loads(file.read_text(encoding='utf8'))
        if 'selection' in head:
            from nbt_project.history import History
            if history_state is None:
                history_state, _ = History(self.workspace).state()
            selected = history_state['current'].get(head['history_building']) == head['history_id']
            head = head['selection'] if selected else head['previous']
        if head is None:
            return None
        return dict(head,source=workspace_path(self.workspace,head['source']).relative_to(self.workspace).as_posix())

    def history_source(self, building):
        from nbt_project.history import History, digest as history_digest
        from nbt_project.web_paths import prior_workspace_paths,workspace_path
        try:
            history = History(self.workspace)
            data, _ = history.state()
            for folder in [building,*prior_workspace_paths(self.workspace,building)]:
                key=history_digest(Path(folder).relative_to(self.workspace).as_posix().encode())[:24]
                current=data['current'].get(key)
                if current:return workspace_path(self.workspace,data['versions'][current]['source']).relative_to(self.workspace).as_posix()
            return None
        except (OSError, ValueError):
            return None

    def assert_parent(self, building, source, opened_head, opened_history_source):
        from nbt_project.web_paths import workspace_path
        head = self.read_head(building)
        history_source = self.history_source(building)
        source = source.relative_to(self.workspace).as_posix() if source else None
        if head != opened_head or history_source != opened_history_source:
            raise ModelConflict('STALE_PARENT', [dict(expected=opened_head, current=head)])
        current = head['source'] if head else history_source
        if current is not None and current != source:
            raise ModelConflict('STALE_PARENT', [dict(source=source, current=current)])
        # History can lag only along the selected draft's verified parent chain.
        ancestor = source
        seen = set()
        while history_source and ancestor != history_source and ancestor not in seen:
            seen.add(ancestor)
            binding = parent_binding(self.workspace, workspace_path(self.workspace, ancestor)) if ancestor else {}
            parent = binding.get('parent_source')
            ancestor = workspace_path(self.workspace, parent).relative_to(self.workspace).as_posix() if parent else None
        if history_source and ancestor != history_source:
            raise ModelConflict('STALE_PARENT', [dict(source=source, history=history_source)])
        return head, history_source

    def history_receipt(self, target, manifest, building):
        master = manifest.get('master','master/model.snbt')
        source = target / master
        receipt = dict(source=str(source.resolve()), source_sha256=manifest['files'][master],
            revision=manifest['revision'], output=str(target.resolve()),
            draft_only=True, nbt_exported=False, approval_created=False)
        head = self.read_head(building)
        try:
            from nbt_project.history import record_produced_version
            parent = self.workspace / manifest['parent_source'] if manifest.get('parent_source') else None
            receipt['history'] = record_produced_version(self.workspace, source, parent=parent, actor=manifest.get('actor', 'external_agent'),
                message='保存受管组合制作版', set_current=bool(head and head['source'] == source.relative_to(self.workspace).as_posix()))
            if receipt['history'].get('recorded') is False:
                raise ValueError(receipt['history'].get('error', '历史登记未完成'))
            receipt['history_pending'] = False
        except (OSError, ValueError) as error:
            receipt.update(history_pending=True, history_error=str(error))
        return receipt

    def advance_head(self, building, target, manifest, opened_head, opened_history_source, head_guard):
        head = self.read_head(building)
        history_source = self.history_source(building)
        current = head['source'] if head else history_source
        if (head == opened_head and history_source == opened_history_source
                and current in (None, manifest.get('parent_source'))):
            master = manifest.get('master', 'master/model.snbt')
            with head_guard():
                _write_head(self.workspace, building, target / master, manifest['revision'])

    def recover_commit(self, target, intent, task_session=None):
        """Complete a remembered publication without recompiling the candidate."""
        from nbt_agent.protocol import error
        from nbt_agent.tasks import publication
        from nbt_project.web_paths import project_paths, workspace_path

        building = target.parent
        with publication_lock(self.workspace, building):
            try:
                manifest = verify_version(target)
            except (OSError, ValueError, KeyError, TypeError) as failure:
                error('RECEIPT_CHANGED', '原操作的制作版验证失败', details={'reason': str(failure)})
            if manifest['revision'] != intent['revision']:
                error('RECEIPT_CHANGED', '原操作的制作版清单已变化')
            parent = workspace_path(self.workspace, manifest['parent_source']) if manifest.get('parent_source') else None

            @contextmanager
            def confirm_parent():
                if parent is not None:
                    if (project_paths(parent)['workdir'] != building or not parent.is_file()
                            or file_hash(parent) != manifest['parent_source_sha256']):
                        raise ModelConflict('STALE_SOURCE', [dict(source=str(parent))])
                    managed_manifest(parent)
                with publication(self.workspace, building, parent, task_session, manifest['actor']) as check_lease:
                    check_lease()
                    yield

            self.advance_head(building, target, manifest, intent['opened_head'], intent['opened_history_source'], confirm_parent)
            return self.history_receipt(target, manifest, building)

    @contextmanager
    def commit(self, stage, building, manifest, description, *, source, opened_head, opened_history_source,
               task_session, recheck_source, before_publish=None, staged=False, remember_target=None):
        from nbt_agent.tasks import publication

        master = manifest.get('master', 'master/model.snbt')
        with publication_lock(self.workspace, building):
            if before_publish is not None:
                before_publish()
            with publication(self.workspace, building, source, task_session, manifest['actor']) as check_lease:
                producer = check_lease()
                if producer:
                    manifest['agent_publication'] = producer
                manifest['revision'] = digest(manifest)
                target = building / ('v_model_' + manifest['revision'][:24])
                write_json(stage / 'model-version.json', manifest)
                write_json(stage / 'room_description.json', dict(description, model_revision=manifest['revision']))
                recheck_source()
                existing = target.exists()
                if not existing:
                    self.assert_parent(building, source, opened_head, opened_history_source)
                    check_lease()
                    if remember_target is not None:
                        remember_target(target, manifest['revision'], opened_head, opened_history_source)
                    os.rename(stage, target)
                if verify_version(target)['revision'] != manifest['revision']:
                    raise ValueError('制作版本目录已被其他内容占用')
                if existing and remember_target is not None:
                    remember_target(target, manifest['revision'], opened_head, opened_history_source)

                @contextmanager
                def confirm_publication():
                    if existing:
                        check_lease()
                    yield

                # Recover an interrupted rename to head update only while the parent is current.
                self.advance_head(building, target, manifest, opened_head, opened_history_source, confirm_publication)
            receipt = (dict(output=str(target), source=str(target / master), source_sha256=manifest['files'][master],
                            revision=manifest['revision'], model_sha256=manifest['model_sha256'],
                            geometry_sha256=description['geometry_sha256'], staged=True)
                       if staged else self.history_receipt(target, manifest, building))
            yield target, receipt
