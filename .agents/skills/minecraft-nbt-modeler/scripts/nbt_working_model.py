"""Whole-model composition, bound host patches and managed instance updates.

This module owns in-memory candidates, not an execution daemon. Generators use
the existing structure contract; every host write passes the same diff policy.
Saving publishes a complete SNBT authoring version, never a binary NBT export.
"""
from copy import deepcopy
from contextlib import contextmanager
from contextvars import ContextVar
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile

from nbt_assembly import Volume
from nbt_model import AIR, AIR_NAMES, state
from nbt_modeling_session import canonical
from nbt_change_policy import ChangePolicyError, change_sets, enforce_changes, reserved_position
from nbt_request_paths import read_request_json

_publication_locks = ContextVar('working_model_publication_locks', default=frozenset())


@contextmanager
def publication_lock(workspace, building):
    """The CLI and desktop publisher use the same reentrant building lock."""
    from nbt_prompts import index_lock
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
    return hashlib.sha256(Path(file).read_bytes()).hexdigest()


def write_json(file, value):
    file = Path(file)
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(canonical(value) + '\n', encoding='utf8')


def managed_manifest(source):
    """Recognize managed drafts even when their manifest has been lost."""
    from nbt_web_paths import project_paths
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
    from nbt_object_scene import atomic
    from nbt_web_paths import project_paths
    source = Path(source).resolve()
    manifest = managed_manifest(source)
    head = dict(revision=manifest['revision'] if manifest else None,
        source=source.relative_to(Path(workspace).resolve()).as_posix())
    file = head_file(workspace, project_paths(source)['workdir'])
    file.parent.mkdir(parents=True, exist_ok=True)
    atomic(file, canonical(head).encode('utf8'))
    return head


def constraint_context(context):
    # Camera changes carry no permission to relax modelling constraints.
    return {key: value for key, value in context.items() if key != 'cameras'}


def model_hash(model, walls):
    """Unlike the legacy geometry hash, this also binds wall ownership."""
    return digest([model.size, sorted(model.blocks.items()), sorted(walls)])


def value_at(model, walls, position):
    value = model.get(position)
    return [value, value not in AIR_NAMES and position in walls]


def point(value):
    if not isinstance(value, (list, tuple)) or len(value) != 3 or any(type(v) is not int for v in value):
        raise ValueError('模型坐标须为三个整数')
    return tuple(value)


def empty_volume(size):
    if any(n > 294 for n in size):
        from nbt_large_assembly import AssemblyVolume
        return AssemblyVolume(size)
    return Volume(size)


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


class WorkingModel:
    """An explicit, process-local working copy of a complete authoring model."""

    def __init__(self, workspace, size, context=None, kind='building', limits=None):
        if kind not in ('building', 'component'):
            raise ValueError('模型类型须为 building 或 component')
        if kind == 'component' and any(n > 64 for n in size):
            raise ValueError('独立构件每轴最多64格；完整建筑使用 building')
        self.workspace = Path(workspace).resolve()
        self.model, self.walls = empty_volume(size), set()
        self._baseline, self._baseline_walls = empty_volume(size), set()
        context_binding = None
        if isinstance(context, (str, Path)):
            context_file = (self.workspace / context).resolve()
            from nbt_library import coordinate_snapshot
            context, context_hash = coordinate_snapshot(context_file)
            context_binding = (context_file, context_hash)
        self.context = deepcopy(context if context is not None else dict(mode='standalone', openings=[]))
        from nbt_library import adapt_coordinates
        self.context = adapt_coordinates(self.context)
        for box in [*self.context.get('protected_boxes', []), *self.context.get('reserved_boxes', [])]:
            lo, hi = point(box['lo']), point(box['hi'])
            if not self.model.in_bounds(lo) or not self.model.in_bounds(hi) or any(lo[i] > hi[i] for i in range(3)):
                raise ValueError('保护或保留范围超出完整模型')
        for path in self.context.get('protected_paths', []):
            for pose in path:
                if len(pose) != 3 or any(type(v) not in (int,float) or not math.isfinite(v) or not 0 <= v <= size[i] for i,v in enumerate(pose)):
                    raise ValueError('保护路径须为模型内的有限脚位')
        self.kind = kind
        self.limits = dict(max_changed_positions=65536, max_written_positions=262144, max_component_blocks=65536)
        if limits:
            if set(limits) - set(self.limits):
                raise ValueError('未知模型预算')
            self.limits.update(limits)
        if any(type(v) is not int or v < 1 for v in self.limits.values()):
            raise ValueError('模型预算须为正整数')
        self.instances = {}
        self._architecture = None
        self.phase, self.preopening = 'design', None
        self._baseline_phase = 'design'
        self.source, self.source_sha256, self.context_binding = None, None, context_binding
        self._version_binding = None
        self._bound_context = None
        self._source_coordinates_hash = None
        self._source_sidecars = {}
        self._assembly_binding = None
        self._assembly_layout = None
        self._assembly_owners = None
        self._assembly_metadata = None
        self._palette, self._extras, self._closed = None, None, None
        self.parent_revision = None
        self._opened_head = None
        self._opened_history_source = None
        self._building = None
        self._saved = None

    @classmethod
    def open(cls, workspace, source, context=None, source_sha256=None, **options):
        from nbt_refine import read_master, resolve_wall_mask
        from nbt_web_paths import project_paths
        workspace = Path(workspace).resolve()
        source = (workspace / source).resolve()
        source_hash = file_hash(source)
        if source_sha256 and source_hash != source_sha256:
            raise ModelConflict('STALE_SOURCE', [dict(source=str(source))])
        sidecars = {}
        if source.suffix.lower() == '.nbt':
            sidecar = source.parent / 'wall_mask.json'
            sidecars[sidecar] = file_hash(sidecar) if sidecar.is_file() else None
        from nbt_large_assembly import is_assembly_source, read_assembly
        assembly = is_assembly_source(source)
        model, walls = read_assembly(source) if assembly else read_master(source)
        if any((file_hash(file) if file.is_file() else None) != expected for file,expected in sidecars.items()):
            raise ModelConflict('STALE_SOURCE', [dict(source=str(source))])
        if file_hash(source) != source_hash:
            raise ModelConflict('STALE_SOURCE', [dict(source=str(source))])
        version = project_paths(source)['version']
        manifest_file = version / 'model-version.json'
        manifest = managed_manifest(source)
        from nbt_library import adapt_coordinates,canonical_context,coordinate_snapshot,inherit_edit_constraints,saved_coordinates,saved_coordinates_hash
        coordinates = saved_coordinates(source)
        source_coordinates_hash = None if manifest else saved_coordinates_hash(source)
        if context is None:
            context = coordinates
        binding = None
        if isinstance(context, (str, Path)):
            path = (workspace / context).resolve()
            data, context_hash = coordinate_snapshot(path)
            binding = (path, context_hash)
        else:
            data = deepcopy(context or dict(mode='standalone', openings=[]))
        data = adapt_coordinates(data)
        if manifest:
            bound = canonical_context(version / 'coordinates.json')
            bound.pop('wall_positions', None)
            supplied = deepcopy(data)
            supplied.pop('wall_positions', None)
            if constraint_context(supplied) != constraint_context(bound):
                raise ModelConflict('CONTEXT_CONSTRAINT_MISMATCH', [dict(version=str(version))])
        else:
            data=inherit_edit_constraints(data,source)
        walls = resolve_wall_mask(model, walls, data)
        data.pop('wall_positions', None)
        working = cls(workspace, model.size, data, **options)
        working.model, working.walls = model, walls
        working._baseline.blocks = dict(model.blocks)
        working._baseline_walls = set(walls)
        working.source, working.source_sha256 = source, source_hash
        working._palette = getattr(model, '_snbt_palette', None)
        working._extras = getattr(model, '_snbt_extras', None)
        working.context_binding = binding
        working._bound_context = deepcopy(constraint_context(working.context))
        working._source_coordinates_hash = source_coordinates_hash
        working._source_sidecars = sidecars
        working._assembly_binding = getattr(model, '_assembly_binding', None)
        working._assembly_layout = deepcopy(getattr(model, '_assembly_layout', None))
        working._assembly_owners = dict(model._assembly_owners) if assembly else None
        working._assembly_metadata = deepcopy(getattr(model, '_assembly_metadata', None))
        working.phase = manifest['phase'] if manifest else 'design' if assembly else 'opened'
        working._baseline_phase = working.phase
        if manifest:
            if model_hash(model, walls) != manifest['model_sha256']:
                raise ValueError('制作版本主模型与清单不一致')
            record = json.loads((version / 'model-instances.json').read_text(encoding='utf8'))
            working.instances = record['instances']
            working._architecture = record.get('architecture')
            from nbt_refine import box_points
            for instance in working.instances.values():
                if instance['recipe']['tool'] == 'scene_compile' and 'policy' not in instance['compiled']:
                    graph = instance['recipe']['arguments']['graph']
                    policy = world_policy(graph,dict(size=graph['size'],anchor=[0,0,0]),instance['transform'])
                    instance['compiled']['policy'] = policy
                    baseline = {point(row['pos']):row['after'] for row in instance['baseline']}
                    protected = {p for box in policy.get('protected_boxes',[]) for p in box_points(box['lo'],box['hi'])}
                    instance['compiled']['protected_values'] = [dict(pos=list(p),value=baseline.get(p,value_at(model,walls,p))) for p in sorted(protected)]
            for key, maximum in record.get('limits', {}).items():
                working.limits[key] = min((options.get('limits') or {}).get(key, maximum), maximum)
            working.preopening = record.get('preopening')
            working.parent_revision = manifest['revision']
            working.kind = manifest['kind']
            working._version_binding = (version, file_hash(manifest_file))
            if (version / 'master/preopening.snbt').is_file():
                working._closed = read_master(version / 'master/preopening.snbt')
        if working.phase == 'sealed':
            if not working.preopening or working.preopening.get('geometry_sha256') != model.fingerprint():
                raise ValueError('封闭制作版缺少匹配的开洞前证据')
            model.check_sealed(working.context.get('interior_probes', []))
            if not working._closed or working._closed[0].fingerprint() != model.fingerprint():
                raise ValueError('封闭制作版与开洞前主模型不一致')
        if source.is_relative_to(workspace / 'nbt_models'):
            working._building = project_paths(source)['workdir']
            working._opened_head = working._read_head(working._building)
            working._opened_history_source = working._history_source(working._building)
        return working

    def _unchanged(self):
        from nbt_library import coordinates_hash,saved_coordinates_hash

        if self._assembly_binding:
            from nbt_large_assembly import verify_assembly_files
            try:verify_assembly_files(self._assembly_binding)
            except (ValueError,OSError) as error:raise ModelConflict('STALE_SOURCE', [dict(source=str(self.source),reason=str(error))]) from error
        if self._bound_context is not None and constraint_context(self.context) != self._bound_context:
            raise ModelConflict('CONTEXT_CONSTRAINT_MISMATCH', [])
        for file, expected in self._source_sidecars.items():
            actual = file_hash(file) if file.is_file() else None
            if actual != expected:
                raise ModelConflict('STALE_SOURCE', [dict(source=str(file))])
        if self.source and file_hash(self.source) != self.source_sha256:
            raise ModelConflict('STALE_SOURCE', [dict(source=str(self.source))])
        if self.context_binding and coordinates_hash(self.context_binding[0]) != self.context_binding[1]:
            raise ModelConflict('STALE_CONTEXT', [dict(context=str(self.context_binding[0]))])
        if self.source and self._version_binding is None and saved_coordinates_hash(self.source)!=self._source_coordinates_hash:
            raise ModelConflict('STALE_CONTEXT', [dict(source=str(self.source))])
        if self._version_binding:
            version, expected = self._version_binding
            if file_hash(version / 'model-version.json') != expected:
                raise ModelConflict('STALE_VERSION', [dict(version=str(version))])
            verify_version(version)

    def _budget(self):
        maximum = self.context.get('max_changed_blocks', self.limits['max_changed_positions'])
        if type(maximum) is not int or maximum < 1:
            raise ValueError('宿主上下文修改预算无效')
        return min(maximum, self.limits['max_changed_positions'])

    def _protection_context(self, phase=None):
        context = deepcopy(self.context)
        if (phase or self.phase) != 'opened':
            # In a new design these describe future openings, not existing air
            # apertures. Explicit paths/boxes remain protected in every phase.
            context.update(openings=[], ports=[], openings_policy='optional')
        return context

    def _stage_edits(self, edits):
        """Build a candidate and check the host's diff, protection and budget."""
        from nbt_refine import protections
        self._unchanged()
        edits = list(edits)
        if len(edits) > self.limits['max_written_positions']:
            raise ChangePolicyError('操作写入量超过上限', 'WRITE_BUDGET', total=len(edits))
        candidate = empty_volume(self.model.size)
        candidate.blocks = dict(self.model.blocks)
        walls, seen, conflicts = set(self.walls), set(), []
        for row in edits:
            p = point(row['pos'])
            if p in seen or not candidate.in_bounds(p):
                raise ValueError('修改坐标重复或超出完整模型')
            seen.add(p)
            for key in ('before', 'after'):
                pair = row[key]
                if not isinstance(pair, (list,tuple)) or len(pair) != 2 or not isinstance(pair[0],str) or type(pair[1]) is not bool:
                    raise ValueError('修改前后须为[方块状态字符串, 是否墙层布尔值]')
            previous = value_at(self.model, self.walls, p)
            if row['before'] != previous:
                conflicts.append(dict(pos=list(p), expected=row['before'], current=previous, proposed=row['after']))
                continue
            after = row['after']
            if not isinstance(after, (list, tuple)) or len(after) != 2 or type(after[1]) is not bool:
                raise ValueError('修改结果须为[方块状态, 是否墙层]')
            value = state(after[0])
            candidate.put(p, value)
            if value in AIR_NAMES or not after[1]:
                walls.discard(p)
            else:
                walls.add(p)
        if conflicts:
            raise ModelConflict('PATCH_BASE_MISMATCH', conflicts)
        protected = protections(self.model, self._protection_context())
        for instance in self.instances.values():
            for box in instance['compiled'].get('policy', {}).get('protected_boxes', []):
                from nbt_refine import box_points
                protected.update(box_points(box['lo'], box['hi']))
        difference = enforce_changes(self.model.blocks, candidate.blocks, self.walls, walls, protected, self._budget())
        total = enforce_changes(self._baseline.blocks, candidate.blocks, self._baseline_walls, walls,
                                protections(self._baseline, self._protection_context(self._baseline_phase)), self._budget())
        changed, layer_changed = change_sets(self.model.blocks, candidate.blocks, self.walls, walls)
        conflict = reserved_position((changed | layer_changed) & candidate.blocks.keys(), self.context.get('reserved_boxes'))
        if conflict is not None:
            raise ModelConflict('RESERVED_SPACE', [dict(pos=list(conflict))])
        return candidate, walls, difference, total

    def _commit_edits(self, edits, instances=None):
        """Check every expected old state, then swap one complete candidate."""
        staged = self._stage_edits(edits)
        candidate, walls, _, _ = staged
        self._check_edit_policies(candidate, walls, self.instances if instances is None else instances)
        return self._adopt_edits(staged, instances)

    def _check_edit_policies(self, candidate, walls, instances):
        # Declared routes are checked against the entire host, including free voxels.
        if self.context.get('require_routes'):
            self._routes(candidate)
        self._instance_policy(candidate, walls, instances)

    def _adopt_edits(self, staged, instances):
        candidate, walls, difference, total = staged
        self._unchanged()
        if not difference['changed_blocks']:
            candidate.stage = self.model.stage
            candidate.seal_record = deepcopy(self.model.seal_record)
            candidate.final_fingerprint = self.model.final_fingerprint
            candidate.opened = set(self.model.opened)
        self.model, self.walls = candidate, walls
        if instances is not None:
            self.instances = deepcopy(instances)
        self._saved = None
        if self.phase == 'sealed' and difference['changed_blocks']:
            self.phase, self.preopening = 'design', None
            self._closed = None
        return dict(difference, total_changes=total, model_sha256=model_hash(candidate, walls), model_modified=True,
                    asset_written=False, approval_created=False)

    def patch(self, changes):
        """Host-dependent patches require explicit expected state AND wall layer."""
        return self._commit_edits(changes)

    def patch_candidate(self, candidate, walls):
        if candidate.size != self.model.size:
            raise ValueError('候选与制作源的完整尺寸不一致')
        changed, layers = change_sets(self.model.blocks, candidate.blocks, self.walls, walls)
        edits = [dict(pos=list(p), before=value_at(self.model, self.walls, p),
                      after=value_at(candidate, walls, p)) for p in sorted(changed | layers)]
        return self.patch(edits)

    def apply_operations(self, operations):
        from nbt_detail_control import default_settings, compile_plan, simulate_plan
        settings = default_settings()
        settings.update(operations=operations, max_changed_blocks=self._budget())
        candidate, walls, _ = simulate_plan(self.model, self.walls,
            compile_plan(settings, self.model.size), dict(self._protection_context(), max_changed_blocks=self._budget(),
                max_written_positions=self.limits['max_written_positions']))
        changed, layers = change_sets(self.model.blocks, candidate.blocks, self.walls, walls)
        edits = [dict(pos=list(p), before=value_at(self.model, self.walls, p), after=value_at(candidate, walls, p)) for p in sorted(changed | layers)]
        return self._commit_edits(edits)

    def _compile(self, recipe, transform):
        from nbt_extensions import compile_recipe
        component, result = compile_recipe(self.workspace, recipe)
        return self._place_compiled(recipe, transform, component, result)

    def _place_compiled(self, recipe, transform, component, result):
        from nbt_components import placement
        if len(component['blocks']) > self.limits['max_component_blocks']:
            raise ChangePolicyError('构件方块数超过上限', 'COMPONENT_BUDGET', total=len(component['blocks']))
        if set(transform) - {'position', 'quarter_turns', 'mirror'}:
            raise ValueError('未知构件变换字段')
        placed = placement(component, transform['position'], self.model.size,
            transform.get('quarter_turns', 0), transform.get('mirror'), overwrite=True)
        values = {}
        for operation in placed['operations']:
            for x, y, z, index in operation['voxels']:
                p = tuple(operation['lo'][i] + v for i, v in enumerate((x, y, z)))
                value = operation['palette'][index]
                values[p] = [value, value not in AIR_NAMES and operation['classification'] == 'wall']
        from nbt_object_scene import engine_hash
        compiled = dict(content_sha256=component['content_sha256'], engine_sha256=engine_hash(),
            compile_order=result.get('compile_order'), objects=world_objects(result.get('objects'), component, transform),
            verification=result.get('verification', {}),
            placement_bounds=dict(lo=placed['lo'], hi=placed['hi']),
            policy=world_policy(recipe['arguments'].get('graph'), component, transform) if recipe['tool']=='scene_compile' else {})
        from nbt_refine import box_points
        protected = {p for box in compiled['policy'].get('protected_boxes',[]) for p in box_points(box['lo'],box['hi'])}
        compiled['protected_values'] = [dict(pos=list(p),value=values.get(p,value_at(self.model,self.walls,p))) for p in sorted(protected)]
        return values, compiled

    def install(self, identifier, recipe, position, *, quarter_turns=0, mirror=None, overwrite=False):
        if not isinstance(identifier, str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}', identifier) or identifier in self.instances:
            raise ValueError('实例ID无效或已存在')
        if type(overwrite) is not bool:
            raise ValueError('覆盖开关须为布尔值')
        transform = dict(position=list(point(position)), quarter_turns=quarter_turns, mirror=mirror)
        values, compiled = self._compile(recipe, transform)
        instance, edits = self._install_rows(identifier, recipe, transform, values, compiled, self._owned_positions(), overwrite)
        return self._commit_edits(edits, self.instances | {identifier: instance})

    def _owned_positions(self):
        return {point(row['pos']): name for name, item in self.instances.items() for row in item['baseline'] if row['owned']}

    def _install_rows(self, identifier, recipe, transform, values, compiled, occupied, overwrite=False):
        rows, edits, conflicts = [], [], []
        for p, after in sorted(values.items()):
            before = value_at(self.model, self.walls, p)
            if p in occupied or before[0] not in AIR_NAMES and before != after and not overwrite:
                conflicts.append(dict(pos=list(p), incoming=identifier, owner=occupied.get(p),
                                      current=before, proposed=after))
            rows.append(dict(pos=list(p), after=after, underlay=before, owned=before != after))
            edits.append(dict(pos=list(p), before=before, after=after))
        if conflicts:
            raise ModelConflict('INSTALL_OCCUPIED', conflicts)
        return dict(recipe=recipe, transform=transform, baseline=rows, compiled=compiled), edits

    def beam_rhythm(self, goal, preview=None):
        from nbt_beam_rhythm import BeamRhythm
        return BeamRhythm(self, goal).search(preview)

    def adopt_beam_rhythm(self, goal, pitch, start_z, candidate_sha256):
        from nbt_beam_rhythm import BeamRhythm
        return BeamRhythm(self, goal).adopt(pitch, start_z, candidate_sha256)

    def _stage_update(self, identifier, recipe, transform):
        if identifier not in self.instances:
            raise ValueError('受管实例不存在')
        if recipe is None and transform is None:
            raise ValueError('实例更新需要新配方或变换')
        previous = self.instances[identifier]
        recipe = deepcopy(recipe if recipe is not None else previous['recipe'])
        transform = deepcopy(transform if transform is not None else previous['transform'])
        values, compiled = self._compile(recipe, transform)
        if previous['recipe']['tool'] == 'scene_compile':
            from nbt_object_scene import compile_scene, transition
            if recipe['tool'] != 'scene_compile':
                raise ValueError('受管场景续版须保留对象图约束')
            before_scene = compile_scene(self.workspace, previous['recipe']['arguments']['graph'])
            after_scene = compile_scene(self.workspace, recipe['arguments']['graph'])
            transition(self.workspace, before_scene, after_scene)
        old = {point(row['pos']): row for row in previous['baseline']}
        others = {point(row['pos']): name for name, item in self.instances.items() if name != identifier for row in item['baseline'] if row['owned']}
        edits, rows, conflicts = [], [], []
        for p in sorted(old.keys() | values.keys()):
            current = value_at(self.model, self.walls, p)
            row = old.get(p)
            base = row['after'] if row else current
            after = values.get(p, row['underlay'] if row and row['owned'] else current)
            if p in others or current != base and current != after:
                conflicts.append(dict(instance=identifier, pos=list(p), baseline=base, current=current, proposed=after, owner=others.get(p)))
                continue
            if row is None and current[0] not in AIR_NAMES and current != after:
                conflicts.append(dict(instance=identifier, pos=list(p), baseline=None, current=current, proposed=after))
                continue
            if row and not row['owned'] and p in values and current != after:
                conflicts.append(dict(instance=identifier,pos=list(p),baseline=base,current=current,proposed=after,
                    reason='原安装未取得宿主同值方块的归属'))
                continue
            edits.append(dict(pos=list(p), before=current, after=after))
            if p in values:
                underlay = row['underlay'] if row and row['owned'] else current
                rows.append(dict(pos=list(p), after=after, underlay=underlay, owned=underlay != after))
        proposed = dict(recipe=recipe, transform=transform, baseline=rows, compiled=compiled)
        return previous, proposed, values, edits, conflicts

    def preflight_update(self, identifier, recipe=None, transform=None):
        from nbt_model_preflight import evaluate_update
        report, _, _ = evaluate_update(self, identifier, recipe, transform)
        return report

    def update(self, identifier, recipe=None, transform=None, preflight_sha256=None):
        if preflight_sha256 is not None:
            from nbt_model_preflight import evaluate_update
            if not isinstance(preflight_sha256, str) or not re.fullmatch('[a-f0-9]{64}', preflight_sha256):
                raise ValueError('装配预检哈希无效')
            report, staged, instances = evaluate_update(self, identifier, recipe, transform)
            if not report['applicable'] or report['preflight_sha256'] != preflight_sha256:
                raise ModelConflict('STALE_UPDATE_PREFLIGHT', [dict(instance=identifier, problems=report['problems'])])
            previous = self.instances[identifier]
            instances[identifier]['preflight'] = dict(
                sha256=preflight_sha256, source_working_sha256=report['source']['working_sha256'],
                candidate_model_sha256=report['candidate_model_sha256'], candidate_state_sha256=report['candidate_state_sha256'],
            )
            result = self._adopt_edits(staged, instances)
            result['preflight_sha256'] = preflight_sha256
        else:
            previous, proposed, _, edits, conflicts = self._stage_update(identifier, recipe, transform)
            if conflicts:
                raise ModelConflict('INSTANCE_EDIT_CONFLICT', conflicts)
            instances = self.instances | {identifier: proposed}
            result = self._commit_edits(edits, instances)
        old_objects = {item['id']:item for item in previous['compiled'].get('objects') or []}
        result['affected_objects'] = [item['id'] for item in instances[identifier]['compiled'].get('objects') or []
                                      if item != old_objects.get(item['id'])]
        result['instance'] = identifier
        return result

    def remove(self, identifier):
        if identifier not in self.instances:
            raise ValueError('受管实例不存在')
        edits, conflicts = [], []
        for row in self.instances[identifier]['baseline']:
            if not row['owned']:
                continue
            p = point(row['pos'])
            current = value_at(self.model, self.walls, p)
            if current != row['after'] and current != row['underlay']:
                conflicts.append(dict(instance=identifier, pos=list(p), baseline=row['after'], current=current, proposed=row['underlay']))
            edits.append(dict(pos=list(p), before=current, after=row['underlay']))
        if conflicts:
            raise ModelConflict('INSTANCE_EDIT_CONFLICT', conflicts)
        instances = deepcopy(self.instances)
        instances.pop(identifier)
        return self._commit_edits(edits, instances)

    def detach(self, identifier):
        if identifier not in self.instances:
            raise ValueError('受管实例不存在')
        instances = deepcopy(self.instances)
        instances.pop(identifier)
        return self._commit_edits([], instances)

    def _declared_host_routes(self, model):
        from nbt_collision import check_routes
        if not self.context.get('start') or not self.context.get('targets'):
            raise ValueError('通路检查需要实际 start 和 targets')
        yield 'host', check_routes(model, self.context['start'], self.context['targets'])
        for leg in self.context.get('route_legs', []):
            copy = empty_volume(model.size)
            copy.blocks = dict(model.blocks)
            for box in leg.get('validation_only_barriers', []):
                copy.box(box['lo'], box['hi'], 'stone')
            yield leg['name'], check_routes(copy, leg['start'], leg['targets'])

    def _routes(self, model):
        reports = self._declared_host_routes(model)
        _, report = next(reports)
        if not report['passed']:
            raise ModelConflict('ROUTE_FAILED', [report])
        for name, result in reports:
            if not result['passed']:
                raise ModelConflict('ROUTE_LEG_FAILED', [dict(name=name, report=result)])
        return report

    def _instance_policy(self, model, walls, instances):
        from nbt_collision import check_routes
        for identifier, instance in instances.items():
            policy = instance['compiled'].get('policy', {})
            baseline = {point(row['pos']):row['after'] for row in instance['baseline']}
            protected_values = {point(row['pos']):row['value'] for row in instance['compiled'].get('protected_values',[])}
            for box in policy.get('protected_boxes', []):
                from nbt_refine import box_points
                for p in box_points(box['lo'],box['hi']):
                    if value_at(model,walls,p) != protected_values.get(p,baseline.get(p,[AIR,False])):
                        raise ModelConflict('INSTANCE_PROTECTED', [dict(instance=identifier,pos=list(p))])
            for p in model.blocks:
                if any(all(box['lo'][i]<=p[i]<=box['hi'][i] for i in range(3)) for box in policy.get('reserved_boxes', [])):
                    raise ModelConflict('RESERVED_SPACE',[dict(instance=identifier,pos=list(p))])
            if policy.get('routes'):
                route = policy['routes']
                report = check_routes(model,route['start'],route['targets'])
                if not report['passed']:
                    raise ModelConflict('ROUTE_FAILED',[dict(instance=identifier,report=report)])
            changed = sum(value_at(model,walls,p) != value for p,value in baseline.items())
            if changed > policy.get('max_changed_blocks',65536):
                raise ValueError('宿主修改超过原对象图预算')

    def _assembly_checks(self, model=None, instances=None):
        """Recheck declared interfaces after host carving and manual edits."""
        from nbt_collision import collision_cells
        from nbt_object_scene import attached, touches
        from nbt_scene_interfaces import check_interface_geometry, interface_contact
        model = self.model if model is None else model
        instances = self.instances if instances is None else instances
        checks = []
        for identifier, instance in instances.items():
            nodes = {item['id']:item for item in instance['compiled'].get('objects') or []}
            actual = {}
            required = {name for name,node in nodes.items() if node.get('contact_targets') or node.get('span_interfaces')}
            required.update(target for node in nodes.values() for target in node.get('contact_targets', [])
                            if not (node.get('attach_target') == target and node.get('attachment_interface')))
            used_surfaces = {(node.get('attach_target'),node.get('attachment_interface'))
                             for node in nodes.values() if node.get('attachment_interface')}
            used_surfaces.update((surface['object'],surface['id']) for node in nodes.values()
                                 for surface in node.get('span_interfaces', []))
            for name, node in nodes.items():
                positions = set(map(tuple,node.get('voxel_positions', [])))
                for surface in node.get('interfaces', {}).values():
                    geometry = check_interface_geometry(model,positions,surface,
                        check_external=(name,surface['id']) in used_surfaces)
                    checks.append(dict(instance=identifier,object=name,interface=surface['id'],**geometry))
                if name not in required:
                    continue
                cells = set()
                unknown = []
                for p in sorted(positions):
                    value = model.get(p)
                    if value in AIR_NAMES:
                        continue
                    shape, reason = collision_cells(value)
                    if reason:
                        unknown.append(dict(pos=list(p), state=value, reason=reason))
                        continue
                    cells.update(tuple(2*p[i]+half[i] for i in range(3)) for half in shape)
                actual[name] = cells
                if unknown:
                    checks.append(dict(instance=identifier,object=name,passed=False,unknown_shapes=unknown))
            for name, node in nodes.items():
                cells = actual.get(name, set())
                for target in node.get('contact_targets', []):
                    surface_name = node.get('attachment_interface')
                    if node.get('attach_target') == target and surface_name:
                        ok = bool(cells) and interface_contact(cells,nodes[target]['interfaces'][surface_name])
                    elif node.get('attach_target') == target:
                        ok = bool(cells) and attached(cells,actual[target])
                    else:
                        ok = bool(cells) and touches(cells,actual[target])
                    checks.append(dict(instance=identifier,object=name,target=target,passed=ok))
                for surface in node.get('span_interfaces', []):
                    ok = bool(cells) and interface_contact(cells,surface)
                    checks.append(dict(instance=identifier,object=name,interface=surface['id'],
                        target=surface.get('object'),passed=ok))
        return dict(passed=all(item['passed'] for item in checks),checks=checks,structural_load='not_checked')

    def validate(self):
        self._unchanged()
        from nbt_refine import protections
        for p, value in self.model.blocks.items():
            if not self.model.in_bounds(point(p)) or state(value) != value:
                raise ValueError('主模型含越界坐标或未标准化方块状态')
        if any(p not in self.model.blocks for p in self.walls):
            raise ValueError('显式墙层指向空气或越界')
        enforce_changes(self._baseline.blocks, self.model.blocks, self._baseline_walls, self.walls,
                        protections(self._baseline, self._protection_context(self._baseline_phase)), self._budget())
        conflict = reserved_position(self.model.blocks, self.context.get('reserved_boxes'))
        if conflict is not None:
            raise ModelConflict('RESERVED_SPACE', [dict(pos=list(conflict))])
        if self.context.get('require_routes'):
            self._routes(self.model)
        if self.kind == 'component' and len(self.model.blocks) > self.limits['max_component_blocks']:
            raise ValueError('独立构件方块数超过上限')
        report = dict(block_states=True, bounds=True, model_sha256=model_hash(self.model, self.walls),
            phase=self.phase, design='pending_visual_review', game='not_checked', approval_created=False)
        self._instance_policy(self.model,self.walls,self.instances)
        report['assembly'] = self._assembly_checks()
        if not report['assembly']['passed']:
            raise ModelConflict('ASSEMBLY_INVALID', [item for item in report['assembly']['checks'] if not item['passed']])
        if self.kind == 'building' and self.phase == 'opened':
            from nbt_whole_validation import validate_whole
            report['whole_model'] = validate_whole(self.model, self.context)
        elif self.phase == 'sealed':
            if not self.preopening or self.preopening['geometry_sha256'] != self.model.fingerprint():
                raise ValueError('封闭检查后模型已经变化')
            report['preopening'] = self.preopening
        else:
            report['whole_model'] = 'not_checked_in_design_phase' if self.kind == 'building' else 'not_applicable_to_component'
        if self._architecture is not None:
            from nbt_building.plan import check_model
            report['architecture'] = check_model(self,self._architecture)
            if self.phase == 'opened' and not report['architecture']['passed']:
                raise ModelConflict('DESIGN_INVALID',[item for item in report['architecture']['checks'] if not item['passed']])
        return report

    def seal(self):
        if self._assembly_binding or any(n > 294 for n in self.model.size):
            raise ValueError('大型组装主稿暂不支持密闭封装')
        self._unchanged()
        copy = Volume(self.model.size)
        copy.blocks = dict(self.model.blocks)
        proof = copy.check_sealed(self.context.get('interior_probes', []))
        self.model, self.phase, self.preopening = copy, 'sealed', proof
        closed = Volume(copy.size)
        closed.blocks = dict(copy.blocks)
        self._closed = (closed, set(self.walls))
        return deepcopy(proof)

    def open_declared(self):
        if self._assembly_binding or any(n > 294 for n in self.model.size):
            raise ValueError('大型组装主稿暂不支持开洞发布')
        from nbt_openings import open_declared_openings
        from nbt_whole_validation import check_opening_policy, requires_enclosure, standalone_openings, validation_mode
        required = requires_enclosure(self.context)
        if self.phase not in ('design', 'sealed') or required and self.phase != 'sealed':
            raise ValueError('该阶段不能开洞；要求密闭的项目须先完成真实封闭检查')
        if validation_mode(self.context) != 'standalone':
            raise ValueError('此入口使用独立建筑 openings，SAODG 使用其专用端口流程')
        self._unchanged()
        openings = self.context.get('openings', [])
        check_opening_policy(self.context, openings)
        candidate = Volume(self.model.size)
        candidate.blocks = dict(self.model.blocks)
        candidate.stage, candidate.seal_record = self.model.stage, deepcopy(self.model.seal_record)
        walls = set(self.walls)
        proof, closed = self.preopening, self._closed
        if openings:
            report = open_declared_openings(candidate, openings, wall_positions=walls, require_enclosure=required)
        else:
            report = dict(passed=True, openings=[], opened_positions=[], changes=[], removed_wall_positions=[],
                          validation=dict(sealed_before_opening=None))
        standalone_openings(candidate, self.context)
        changed, layers = change_sets(self.model.blocks, candidate.blocks, self.walls, walls)
        self._commit_edits([dict(pos=list(p),before=value_at(self.model,self.walls,p),after=value_at(candidate,walls,p)) for p in sorted(changed|layers)])
        candidate.stage = 'opened'
        self.model, self.phase, self.preopening, self._closed = candidate, 'opened', proof, closed
        return report

    @property
    def architecture(self):
        return deepcopy(self._architecture)

    def inspect(self, identifier=None, positions=None):
        self._unchanged()
        items = self.instances if identifier is None else {identifier: self.instances[identifier]}
        samples = []
        owners = {point(row['pos']):name for name,item in self.instances.items() for row in item['baseline'] if row['owned']}
        for position in positions or []:
            p = point(position)
            if not self.model.in_bounds(p):
                raise ValueError('查询坐标超出完整模型')
            samples.append(dict(pos=list(p), value=value_at(self.model,self.walls,p), owner=owners.get(p)))
        return dict(size=list(self.model.size), phase=self.phase, kind=self.kind,
            geometry_sha256=self.model.fingerprint(), model_sha256=model_hash(self.model, self.walls),
            working_sha256=self._content_token(), architecture_sha256=(self._architecture or {}).get('sha256'),
            block_count=len(self.model.blocks), wall_blocks=len(self.walls),
            instances={name: dict(recipe=deepcopy(row['recipe']), transform=deepcopy(row['transform']),
                footprint_positions=len(row['baseline']), owned_positions=sum(p['owned'] for p in row['baseline']),
                objects=[{key:deepcopy(value) for key,value in item.items() if key!='voxel_positions'} for item in row['compiled']['objects']] if row['compiled'].get('objects') is not None else None,
                **({'preflight': deepcopy(row['preflight'])} if 'preflight' in row else {})) for name, row in items.items()},
            assembly_checks=self._assembly_checks(),
            samples=samples,
            asset_written=False, approval_created=False)

    def preview(self, output, cameras):
        if not self._assembly_binding and any(n > 294 for n in self.model.size):
            raise ValueError('大型模型预览须先绑定组装制作源')
        from nbt_refine import save_master
        from nbt_task import write_snapshot
        output = Path(output)
        output.mkdir(parents=True, exist_ok=False)
        if self._assembly_binding:
            from nbt_large_assembly import save_assembly
            source = Path(save_assembly(output / 'candidate', self.model, self.walls, self._assembly_layout,
                                        ownership=self._assembly_owners, metadata=self._assembly_metadata,
                                        before_publish=self._unchanged)['source'])
        else:
            source = output / 'candidate.snbt'
            save_master(source, self.model, self.walls)
        snapshot = output / 'snapshot.json'
        write_snapshot(source, snapshot, cameras=cameras)
        write_json(output / 'cameras.json', cameras)
        candidate_sha = model_hash(self.model, self.walls)
        result = dict(source=str(source.resolve()), snapshot=str(snapshot.resolve()), cameras=str((output / 'cameras.json').resolve()),
                      model_sha256=candidate_sha, visual_review='pending', asset_written=False)
        decisions = {name: row['preflight'] for name, row in self.instances.items() if 'preflight' in row}
        if decisions:
            from nbt_model_preflight import candidate_state_sha256
            state_sha = candidate_state_sha256(self, candidate_sha, self.instances)
            decisions = {name: decision for name, decision in decisions.items()
                         if decision.get('candidate_state_sha256') == state_sha}
        if decisions:
            receipt = output / 'assembly-preflight.json'
            write_json(receipt, dict(source_sha256=file_hash(source), snapshot_sha256=file_hash(snapshot),
                                     model_sha256=candidate_sha, decisions=decisions, approval_created=False))
            result['assembly_preflight'] = dict(file=str(receipt.resolve()), sha256=file_hash(receipt))
        return result

    def _head_file(self, building):
        return head_file(self.workspace, building)

    def _read_head(self, building):
        from nbt_web_paths import prior_workspace_paths,workspace_path
        candidates=[building,*prior_workspace_paths(self.workspace,building)]
        files=[file for folder in candidates if (file:=self._head_file(folder)).is_file()]
        if not files:return None
        file=max(files,key=lambda current:current.stat().st_mtime_ns)
        head=json.loads(file.read_text(encoding='utf8'))
        return dict(head,source=workspace_path(self.workspace,head['source']).relative_to(self.workspace).as_posix())

    def _history_source(self, building):
        from nbt_history import History, digest as history_digest
        from nbt_web_paths import prior_workspace_paths,workspace_path
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

    def _assert_parent(self, building):
        from nbt_web_paths import workspace_path
        head = self._read_head(building)
        history_source = self._history_source(building)
        source = self.source.relative_to(self.workspace).as_posix() if self.source else None
        if head != self._opened_head or history_source != self._opened_history_source:
            raise ModelConflict('STALE_PARENT', [dict(expected=self._opened_head, current=head)])
        current = head['source'] if head else history_source
        if current is not None and current != source:
            raise ModelConflict('STALE_PARENT', [dict(source=source, current=current)])
        # History can lag only along the selected draft's verified parent chain.
        ancestor = source
        seen = set()
        while history_source and ancestor != history_source and ancestor not in seen:
            seen.add(ancestor)
            manifest = managed_manifest(workspace_path(self.workspace,ancestor)) if ancestor else None
            ancestor = manifest.get('parent_source') if manifest else None
            if ancestor:ancestor=workspace_path(self.workspace,ancestor).relative_to(self.workspace).as_posix()
        if history_source and ancestor != history_source:
            raise ModelConflict('STALE_PARENT', [dict(source=source, history=history_source)])
        return head, history_source

    def _content_token(self):
        return digest([model_hash(self.model, self.walls), self.instances, self.context, self.phase, self.preopening, self.kind, self._architecture])

    def _history_receipt(self, target, manifest, building):
        master = manifest.get('master','master/model.snbt')
        source = target / master
        receipt = dict(source=str(source.resolve()), source_sha256=manifest['files'][master],
            revision=manifest['revision'], output=str(target.resolve()),
            draft_only=True, nbt_exported=False, approval_created=False)
        head = self._read_head(building)
        try:
            from nbt_history import record_produced_version
            parent = self.workspace / manifest['parent_source'] if manifest.get('parent_source') else None
            receipt['history'] = record_produced_version(self.workspace, source, parent=parent, actor=manifest.get('actor', 'external_agent'),
                message='保存受管组合制作版', set_current=bool(head and head['source'] == source.relative_to(self.workspace).as_posix()))
            if receipt['history'].get('recorded') is False:
                raise ValueError(receipt['history'].get('error', '历史登记未完成'))
            receipt['history_pending'] = False
        except (OSError, ValueError) as error:
            receipt.update(history_pending=True, history_error=str(error))
        return receipt

    def save_draft(self, name_zh=None, shape='standalone', attachments=None, actor='external_agent', task_session=None, before_publish=None):
        if not self._assembly_binding and any(n > 294 for n in self.model.size):
            raise ValueError('大型模型保存须先绑定组装制作源')
        from nbt_library import LABELS, shape_of
        from nbt_refine import save_master, read_master
        from nbt_object_scene import atomic
        from nbt_agent_tasks import publication
        from nbt_whole_validation import interior_probe_error
        self._unchanged()
        probe_error = interior_probe_error(self.model, self.context)
        if probe_error:
            raise ValueError(probe_error)
        if actor not in ('human', 'external_agent', 'internal_ai', 'import'):
            raise ValueError('制作版来源无效')
        report = self.validate()
        if self._saved and self._saved['token'] == self._content_token() and not attachments:
            target = Path(self._saved['receipt']['output'])
            manifest = verify_version(target)
            with publication(self.workspace,self._building,self.source,task_session,actor):
                if before_publish is not None:before_publish()
                receipt = self._history_receipt(target, manifest, self._building)
            self._saved['receipt'] = receipt
            head = self._read_head(self._building)
            if head and head.get('source') == self.source.relative_to(self.workspace).as_posix():
                self._opened_history_source = self._history_source(self._building)
            return receipt
        engine = Path(__file__).resolve().parents[1]
        software = engine.parents[2] if engine.parent.name == 'skills' else None
        if self.workspace == software or self.workspace == engine or self.workspace.is_relative_to(engine):
            raise ValueError('制作版保存在实际创作工作区，不写入软件源码或安装目录')
        if self._building:
            building = self._building
            from nbt_web_paths import project_paths
            description = project_paths(self.source)['version'] / 'room_description.json'
            old = json.loads(description.read_text(encoding='utf8')) if description.is_file() else {}
            name_zh = name_zh or old.get('name_zh')
            shape = old.get('shape', shape)
        else:
            if shape not in LABELS:
                raise ValueError('未知建筑形状')
            building = self.workspace / 'nbt_models' / shape / str(name_zh)
        if not isinstance(name_zh, str) or not re.search('[\u4e00-\u9fff]', name_zh) or any(c in name_zh for c in '<>:"/\\|?*'):
            raise ValueError('建筑名须含中文且不能包含路径符号')
        if shape != 'standalone' and shape_of(self.model.size,self.context.get('cells',[]), self.context.get('cell_size',48)) != shape:
            raise ValueError('保存目录形状与完整主模型不一致')
        if not building.resolve().is_relative_to(self.workspace / 'nbt_models'):
            raise ValueError('制作版本须位于工作区 nbt_models')
        building.mkdir(parents=True, exist_ok=True)
        staging = self.workspace / '.nbtcreator/model-staging'
        staging.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=staging) as temporary:
            stage = Path(temporary)
            master = 'master/assembly.json' if self._assembly_binding else 'master/model.snbt'
            if self._assembly_binding:
                from nbt_large_assembly import read_assembly, save_assembly
                save_assembly(stage / 'master', self.model, self.walls, self._assembly_layout,
                              ownership=self._assembly_owners, metadata=self._assembly_metadata,
                              before_publish=self._unchanged)
                disk, mask = read_assembly(stage / master)
            else:
                from nbt_snbt import save_snbt
                save_snbt(stage / master, self.model, self.walls, palette=self._palette, extras=self._extras)
                disk, mask = read_master(stage / master)
            if self._closed:
                save_master(stage / 'master/preopening.snbt', *self._closed)
            if model_hash(disk, mask) != model_hash(self.model, self.walls):
                raise ValueError('制作版回读不一致')
            write_json(stage / 'model-instances.json', dict(instances=self.instances, preopening=self.preopening, limits=self.limits, architecture=self._architecture))
            write_json(stage / 'coordinates.json', self.context)
            write_json(stage / 'validation/working-model.json', report)
            changed, layers = change_sets(self._baseline.blocks, self.model.blocks, self._baseline_walls, self.walls)
            write_json(stage / 'changes.json', dict(changes=[dict(pos=list(p), before=value_at(self._baseline,self._baseline_walls,p),
                after=value_at(self.model,self.walls,p)) for p in sorted(changed | layers)]))
            for name, content in (attachments or {}).items():
                if not re.fullmatch(r'[a-z][a-z0-9_-]{0,63}\.json', name):
                    raise ValueError('制作附属资料须为具名JSON，不接收任意输出路径')
                write_json(stage / 'editing' / name, content)
            from nbt_object_scene import engine_hash
            files = {p.relative_to(stage).as_posix(): file_hash(p) for p in stage.rglob('*') if p.is_file()}
            manifest = dict(schema_version=1, kind=self.kind, phase=self.phase, actor=actor, model_sha256=model_hash(self.model, self.walls),
                parent_revision=self.parent_revision, parent_source=self.source.relative_to(self.workspace).as_posix() if self.source and self.source.is_relative_to(self.workspace / 'nbt_models') else None,
                parent_source_sha256=self.source_sha256, engine_sha256=engine_hash(), files=files)
            if self._assembly_binding:
                manifest.update(master=master,source_kind='assembly')
            with publication(self.workspace,building,self.source,task_session,actor) as check_lease:
                producer = check_lease()
                if producer:
                    manifest['agent_publication'] = producer
                manifest['revision'] = digest(manifest)
                target = building / ('v_model_' + manifest['revision'][:24])
                write_json(stage / 'model-version.json', manifest)
                write_json(stage / 'room_description.json', dict(schema_version=1, name_zh=name_zh, shape=shape, shape_zh=LABELS[shape],
                    display_name=name_zh + '-' + LABELS[shape], description_zh=name_zh + '-' + LABELS[shape],
                    master=master, master_file_sha256=files[master], geometry_sha256=self.model.fingerprint(),
                    size=list(self.model.size), cells=self.context.get('cells', []), cell_size=self.context.get('cell_size',48), mode=self.context.get('mode'), context_file='coordinates.json',
                    status='authoring', model_revision=manifest['revision']))
                self._unchanged()
                if before_publish is not None:before_publish()
                head = self._read_head(building)
                history_source = self._history_source(building)
                # Retrying the same immutable result may repair history, but never
                # moves a newer head backwards.
                existing_target = target.exists()
                if not existing_target:
                    self._assert_parent(building)
                    check_lease()
                    os.rename(stage, target)
                actual_manifest = verify_version(target)
                if actual_manifest['revision'] != manifest['revision']:
                    raise ValueError('制作版本目录已被其他内容占用')
                # Recover an interrupted rename→head publication, provided its
                # parent is still current. A retry cannot rewind a newer head.
                current = head['source'] if head else history_source
                if (head == self._opened_head and history_source == self._opened_history_source
                        and (current == manifest.get('parent_source') or current is None)):
                    if existing_target:check_lease()
                    new_head = dict(revision=manifest['revision'], source=(target / master).relative_to(self.workspace).as_posix())
                    head_file = self._head_file(building)
                    head_file.parent.mkdir(parents=True, exist_ok=True)
                    atomic(head_file, canonical(new_head).encode('utf8'))
                receipt = self._history_receipt(target, manifest, building)
                self.source, self.source_sha256 = target / master, files[master]
                self._building, self._opened_head = building, self._read_head(building)
                self._opened_history_source = self._history_source(building)
                self.parent_revision = manifest['revision']
                from nbt_library import coordinates_hash
                self.context_binding = (target / 'coordinates.json', coordinates_hash(target / 'coordinates.json'))
                self._version_binding = (target, file_hash(target / 'model-version.json'))
                self._bound_context = deepcopy(constraint_context(self.context))
                self._source_sidecars = {}
                self._baseline = empty_volume(self.model.size)
                self._baseline.blocks = dict(self.model.blocks)
                self._baseline_walls = set(self.walls)
                self._baseline_phase = self.phase
                self._palette = getattr(disk, '_snbt_palette', None)
                self._extras = getattr(disk, '_snbt_extras', None)
                if self._assembly_binding:
                    disk, _ = read_assembly(self.source)
                    self._assembly_binding = disk._assembly_binding
                    self._assembly_layout = deepcopy(disk._assembly_layout)
                    self._assembly_owners = dict(disk._assembly_owners)
                    self._assembly_metadata = deepcopy(disk._assembly_metadata)
                self._saved = dict(token=self._content_token(), receipt=receipt)
                return receipt


def world_position(p, component, transform, scale=1, continuous=False):
    def rotated(value, unit, offset):
        x,y,z = value
        a,b = component['size'][0]*unit,component['size'][2]*unit
        if transform.get('mirror') == 'x':
            x = a-offset-x
        if transform.get('mirror') == 'z':
            z = b-offset-z
        for _ in range(transform.get('quarter_turns',0)%4):
            x,z,a,b = b-offset-z,x,b,a
        return [x,y,z]
    anchor = rotated(component['anchor'],1,1)
    value = rotated(p,scale,0 if continuous else 1)
    return [value[i]+scale*(transform['position'][i]-anchor[i]) for i in range(3)]


def world_policy(graph, component, transform):
    if not graph:
        return {}
    policy = dict(max_changed_blocks=graph.get('max_changed_blocks',65536))
    for field in ('protected_boxes','reserved_boxes'):
        objects = [dict(id=str(i),bounds=box,origin=box['lo']) for i,box in enumerate(graph.get(field,[]))]
        policy[field] = [item['bounds'] for item in world_objects(objects,component,transform)]
    if graph.get('routes'):
        def pose(p):
            return world_position(p,component,transform,continuous=True)
        routes = graph['routes']
        targets = routes['targets']
        policy['routes'] = dict(start=pose(routes['start']),
            targets={name:pose(p) for name,p in targets.items()} if isinstance(targets,dict) else [pose(p) for p in targets])
    return policy


def world_objects(objects, component, transform):
    """Expose child bounds and contact surfaces in the complete host frame."""
    if objects is None:
        return None
    from itertools import product
    turns, mirror = transform.get('quarter_turns', 0) % 4, transform.get('mirror')
    def position(p, scale=1):
        return world_position(p,component,transform,scale)
    def surface(record):
        output = deepcopy(record)
        normal = list(record['normal'])
        if mirror == 'x':
            normal[0] *= -1
        if mirror == 'z':
            normal[2] *= -1
        for _ in range(turns):
            normal[0], normal[2] = -normal[2], normal[0]
        faces = sorted(position(p, 2) for p in record['faces_half'])
        axis = next(i for i, v in enumerate(normal) if v)
        sign = normal[axis]
        direction = {(0,1):'east',(0,-1):'west',(1,1):'up',(1,-1):'down',(2,1):'south',(2,-1):'north'}[(axis,sign)]
        output.update(normal=normal, face=direction, faces_half=faces,
            plane_half=faces[0][axis] + (1 if sign > 0 else 0),
            lo_half=[min(p[i] for p in faces) for i in range(3)],
            hi_half=[max(p[i] for p in faces) for i in range(3)], tangent_axes=[i for i in range(3) if i != axis])
        if record.get('region_half'):
            region=record['region_half']
            corners=[position(p,2) for p in product(*zip(region['lo'],region['hi']))]
            output['region_half']=dict(lo=[min(p[i] for p in corners) for i in range(3)],
                                       hi=[max(p[i] for p in corners) for i in range(3)])
        return output
    result = deepcopy(objects)
    for item in result:
        bounds = item['bounds']
        corners = [position(p) for p in product(*zip(bounds['lo'], bounds['hi']))]
        item['local_bounds'] = deepcopy(bounds)
        item['bounds'] = dict(lo=[min(p[i] for p in corners) for i in range(3)], hi=[max(p[i] for p in corners) for i in range(3)])
        item['origin'] = position(item['origin'])
        item['coordinate_space'] = 'host'
        item['voxel_positions'] = [position(p) for p in item.get('voxel_positions', [])]
        item['interfaces'] = {key:surface(value) for key, value in item.get('interfaces', {}).items()}
        item['span_interfaces'] = [surface(value) for value in item.get('span_interfaces', [])]
    return result


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
        from nbt_large_assembly import assembly_manifest
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, default=Path.cwd())
    parser.add_argument('--request', type=Path, required=True,
                        help='UTF-8 JSON 文件，相对于命令工作目录。JSON 内的 source 和 context 路径相对于创作工作区。')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        request = read_request_json(args.request, max_bytes=8*1024*1024)
        from nbt_catalog import catalog
        from nbt_structure_agent import _schema
        _schema(request, catalog()['working_model']['parameters'], '工作模型请求')
        if request.get('source'):
            if not request.get('source_sha256'):
                raise ValueError('已有模型请求须绑定 source_sha256')
            model = WorkingModel.open(args.workspace, request['source'], request.get('context'),
                source_sha256=request['source_sha256'], kind=request.get('kind', 'building'), limits=request.get('limits'))
        else:
            if 'size' not in request:
                raise ValueError('新建工作模型须提供 size（XYZ 格数）；打开已有制作版须提供 source 和 source_sha256。')
            model = WorkingModel(args.workspace, request['size'], request.get('context'), request.get('kind', 'building'), request.get('limits'))
        results = []
        from nbt_extensions import MODEL_ACTIONS
        for action in request.get('actions', []):
            action = dict(action)
            method = action.get('method')
            schema = catalog()['working_model']['actions'].get(method)
            if schema is None or method not in MODEL_ACTIONS:
                raise ValueError('未知工作模型操作')
            _schema(action,schema,'工作模型操作')
            action.pop('method')
            results.append(MODEL_ACTIONS.resolve(method)(model, action))
        result = dict(model=model.inspect(positions=request.get('positions')), actions=results)
        if request.get('validate'):
            result['validation'] = model.validate()
        if 'save_draft' in request:
            result['saved'] = model.save_draft(**request['save_draft'])
        if args.output:
            result['preview'] = model.preview(args.output, request.get('cameras', []))
        print(json.dumps(dict(ok=True, result=result), ensure_ascii=False))
        return 0
    except (ValueError, OSError, KeyError, TypeError, AssertionError) as error:
        reply = dict(ok=False, error=str(error), code=getattr(error, 'code', 'MODEL_INVALID'),
                     conflicts=getattr(error, 'conflicts', []))
        if recovery := getattr(error, 'recovery', None):
            reply['recovery'] = recovery
        print(json.dumps(reply, ensure_ascii=False))
        return 1


if __name__ == '__main__':
    # Keep the lock ContextVar shared with history's imports in CLI processes.
    from nbt_working_model import main as run
    raise SystemExit(run())
