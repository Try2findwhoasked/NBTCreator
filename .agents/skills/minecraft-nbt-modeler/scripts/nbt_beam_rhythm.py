"""Rank Z-repeated, recipe-built beam frames against one explicit rhythm goal."""
from collections import Counter
from copy import copy, deepcopy
from pathlib import Path

import numpy as np

from nbt_building.structural_members import full, grain
from nbt_catalog import catalog
from nbt_change_policy import ChangePolicyError
from nbt_collision import collision_cells
from nbt_extensions import compile_recipe
from nbt_model import AIR_NAMES
from nbt_model_preflight import route_summary
from nbt_object_scene import engine_hash
from nbt_structure_agent import _schema
from nbt_working_model import ModelConflict, digest, file_hash, model_hash, write_json


def z_amplitudes(occupancy, depth):
    """Keep the fixed XY traces independent. The last axis is Z."""
    return np.abs(np.fft.rfft(occupancy, n=depth, axis=-1))


def frame_recipe(goal):
    span, posts, lintel = (goal[k] for k in ('span_x', 'post_height', 'beam_height'))
    post = grain(full(goal['materials']['post']), 'y')
    beam = full(goal['materials']['beam'])
    post_recipe = dict(tool='structure', arguments=dict(name='梁架立柱', size=[1, posts, 1], anchor=[0, 0, 0],
        operations=[dict(kind='box', label='梁架立柱', lo=[0, 0, 0], hi=[0, posts - 1, 0],
                         state=post, classification='body')]))
    members = [
        dict(id='left_post', lo=[0, 0, 0], recipe=post_recipe),
        dict(id='right_post', lo=[span - 1, 0, 0], recipe=post_recipe),
        dict(id='beam', lo=[0, posts, 0], contacts=['left_post', 'right_post'],
             recipe=dict(tool='parametric_compile', arguments=dict(
                 kind='beam', size=[span, lintel, 1], material=beam, accent=beam, form=dict(profile='rectangular')))),
    ]
    return dict(tool='scene_compile', arguments=dict(graph=dict(
        schema_version=1, name='横梁与双柱', size=[span, posts + lintel, 1], objects=members)))


def problem(error):
    if isinstance(error, ChangePolicyError):
        return dict(code=error.kind, message=str(error), total=error.total,
                    conflicts=[dict(pos=list(p)) for p in error.positions])
    if error.code == 'ROUTE_FAILED':
        conflicts = [route_summary(row, True) if 'passed' in row else
                     dict(instance=row['instance'], report=route_summary(row['report'], True))
                     for row in error.conflicts]
    elif error.code == 'ROUTE_LEG_FAILED':
        conflicts = [dict(name=row['name'], report=route_summary(row['report'], True)) for row in error.conflicts]
    else:
        conflicts = error.conflicts[:20]
    return dict(code=error.code, total=len(error.conflicts), conflicts=conflicts)


class BeamRhythm:
    def __init__(self, host, goal):
        schema = catalog()['working_model']['actions']['beam_rhythm']['properties']['goal']
        _schema(goal, schema, '梁架目标')
        self.host = host
        self.goal = deepcopy(goal)
        self.pitches = sorted(set(goal['pitches']))
        self.starts = sorted(set(goal['starts']))
        if len(self.pitches) * len(self.starts) > 64:
            raise ValueError('梁架间距与起点组合最多64个')
        self.lo, self.hi = goal['region']['lo'], goal['region']['hi']
        if (not all(host.model.in_bounds(p) for p in (self.lo, self.hi))
                or any(a > b for a, b in zip(self.lo, self.hi))):
            raise ValueError('梁架修改区域须为主模型内的有序闭区间')
        self.origin_x, self.origin_y = goal['origin_xy']
        self.depth = self.hi[2] - self.lo[2] + 1
        self.width = goal['span_x']
        self.height = goal['post_height'] + goal['beam_height']
        if self.height > 64:
            raise ValueError('单榀梁架总高最多64格')

        host._unchanged()
        self.source = dict(source_sha256=host.source_sha256, parent_revision=host.parent_revision,
                           working_sha256=host._content_token(), limits=dict(host.limits),
                           baseline_sha256=model_hash(host._baseline, host._baseline_walls),
                           baseline_phase=host._baseline_phase, engine_sha256=engine_hash())
        self.recipe = frame_recipe(goal)
        self.component, self.compilation = compile_recipe(host.workspace, self.recipe)
        self.template = {(x, y): self.component['palette'][index]
                         for x, y, _, index, _ in self.component['blocks']}
        self.occupied = host._owned_positions()
        self.placements = {}

        pitch = goal['target_pitch']
        ideal = np.arange(goal['count']) * pitch
        self.fft_depth = max(self.depth, int(ideal[-1]) + 1, 2 * pitch)
        # Both the finite target train and the measured traces use the same padding.
        target = np.zeros(self.fft_depth, dtype=bool)
        target[ideal] = True
        self.bins = sorted({index for order in range(1, pitch // 2 + 1)
                            for index in range(round(order * self.fft_depth / pitch) - 1,
                                               round(order * self.fft_depth / pitch) + 2)
                            if 1 <= index <= self.fft_depth // 2})
        self.target_band = z_amplitudes(target, self.fft_depth)[self.bins]
        self.band_norm = np.linalg.norm(self.target_band) * np.sqrt(len(self.template))

    def _placement(self, z):
        if z not in self.placements:
            transform = dict(position=[self.origin_x, self.origin_y, z], quarter_turns=0, mirror=None)
            values, compiled = self.host._place_compiled(self.recipe, transform, self.component, self.compilation)
            self.placements[z] = transform, values, compiled
        return self.placements[z]

    def _support(self, candidate, starts):
        checks = []
        for z in starts:
            for x in (self.origin_x, self.origin_x + self.width - 1):
                foot = (x, self.origin_y, z)
                below = (x, self.origin_y - 1, z)
                state = candidate.get(below)
                shape, reason = collision_cells(state)
                passed = not reason and any(y == 1 for _, y, _ in shape)
                checks.append(dict(pos=list(foot), support_pos=list(below), state=state, passed=passed))
        missing = [row for row in checks if not row['passed']]
        if missing:
            raise ModelConflict('UNSUPPORTED_FRAME', missing)
        return checks

    def _measure(self, candidate, starts):
        # Trace the compiled frame footprint in each candidate's actual geometry.
        # Unrelated host blocks and existing supports are outside this component mask.
        occupancy = np.zeros((len(self.template), self.depth), dtype=bool)
        mismatches = []
        for trace, ((x, y), expected) in enumerate(self.template.items()):
            for z in starts:
                pos = (self.origin_x + x, self.origin_y + y, z)
                actual = candidate.get(pos)
                occupancy[trace, z - self.lo[2]] = actual not in AIR_NAMES
                if actual != expected:
                    mismatches.append(dict(pos=list(pos), expected=expected, actual=actual))
        measured_starts = (np.flatnonzero(occupancy.any(axis=0)) + self.lo[2]).tolist()
        gaps = np.diff(measured_starts).tolist()
        expected_count = self.goal['count'] * len(self.template)
        present = int(occupancy.sum())
        material_mismatches = sum(row['actual'] not in AIR_NAMES for row in mismatches)
        target_pitch = self.goal['target_pitch']
        gaps_delta = [gap - target_pitch for gap in gaps]
        spectrum = z_amplitudes(occupancy, self.fft_depth)[:, self.bins]
        spectrum_error = float(np.linalg.norm(spectrum - self.target_band) / self.band_norm)
        measured = dict(starts_z=measured_starts, gaps=gaps, gap_delta=gaps_delta,
                        expected_voxels=expected_count, occupied_voxels=present, missing_voxels=expected_count - present,
                        material_mismatches=material_mismatches, state_differences=mismatches[:20])
        errors = dict(spectrum=spectrum_error,
                      pitch=sum(map(abs, gaps_delta)) / max(1, len(gaps)) / target_pitch,
                      geometry=(expected_count - present) / expected_count,
                      material=material_mismatches / expected_count)
        return measured, errors

    def _check_bound_building(self, staged, instances):
        host = self.host
        if host.phase != 'opened' and host._architecture is None:
            return 'not_declared'
        candidate = copy(host)
        candidate._adopt_edits(staged, instances)
        if candidate.phase == 'opened':
            candidate.validate()
            return 'opened_passed'
        from nbt_building.plan import check_model
        checks = check_model(candidate, candidate._architecture)['checks']
        blocking = ('retained_constraints', 'activity_routes', 'sample_routes', 'stair_segments', 'bearing_contact')
        failed = [dict(id=row['id'], kind=row['kind']) for row in checks if row['kind'] in blocking and not row['passed']]
        if failed:
            raise ModelConflict('DESIGN_INVALID', failed)
        return 'architecture_routes_and_contacts_passed'

    def _evaluate(self, pitch, start):
        host = self.host
        starts = [start + i * pitch for i in range(self.goal['count'])]
        low = [self.origin_x, self.origin_y, start]
        high = [self.origin_x + self.width - 1, self.origin_y + self.height - 1, starts[-1]]
        frames = [dict(id=f'{self.goal["id"]}-{z}', origin=[self.origin_x, self.origin_y, z]) for z in starts]
        row = dict(pitch=pitch, start_z=start, frames=frames, bounds=dict(lo=low, hi=high), applicable=False)
        try:
            if any(a < b or c > d for a, b, c, d in zip(low, self.lo, high, self.hi)):
                raise ModelConflict('OUTSIDE_EDIT_REGION', [row['bounds']])
            instances = dict(host.instances)
            edits = []
            for frame in frames:
                identifier = frame['id']
                if identifier in instances:
                    raise ModelConflict('INSTANCE_ID_EXISTS', [frame])
                transform, values, compiled = self._placement(frame['origin'][2])
                instance, writes = host._install_rows(identifier, self.recipe, transform, values, compiled, self.occupied)
                instances[identifier] = instance
                edits.extend(writes)
            staged = host._stage_edits(edits)
            candidate, walls, changes, total_changes = staged
            support = self._support(candidate, starts)
            host._check_edit_policies(candidate, walls, instances)
            assembly = host._assembly_checks(candidate, instances)
            if not assembly['passed']:
                raise ModelConflict('ASSEMBLY_INVALID', [check for check in assembly['checks'] if not check['passed']])
            building_checks = self._check_bound_building(staged, instances)
        except (ModelConflict, ChangePolicyError) as error:
            if getattr(error, 'code', '').startswith(('STALE_', 'CONTEXT_')):
                raise
            return dict(row, problem=problem(error)), None
        except ValueError as error:
            return dict(row, problem=dict(code='HOST_VALIDATION_FAILED', message=str(error))), None

        host._unchanged()
        routes = ('required_passed' if host.context.get('require_routes') else
                  'not_required' if host.context.get('start') and host.context.get('targets') else 'not_declared')
        measured, errors = self._measure(candidate, starts)
        selection = dict(pitch=pitch, start_z=start)
        candidate_hash = model_hash(candidate, walls)
        token = digest([self.source, self.goal, selection, self.component['content_sha256'], candidate_hash])
        row.update(applicable=True, measured=measured, errors=errors, score=round(sum(errors.values()), 12),
                   anchor_delta=abs(start - self.goal.get('anchor_z', start)), changes=changes, total_changes=total_changes,
                   checks=dict(protection='passed', reserved='passed', budget='passed', supports=support,
                               routes=routes, bound_building=building_checks, managed_policies='passed',
                               assembly='passed', structural_load='not_checked'),
                   model_sha256=candidate_hash, candidate_sha256=token)
        return row, (staged, instances)

    @staticmethod
    def _rank(row):
        return row['score'], row['anchor_delta'], row['changes']['changed_positions'], row['pitch'], row['start_z']

    def search(self, preview):
        selected = None
        best = None
        accepted, rejected = [], []
        preview_selection = None
        if preview is not None:
            schema = catalog()['working_model']['actions']['beam_rhythm']['properties']['preview']
            _schema(preview, schema, '梁架预览')
            if ('pitch' in preview) != ('start_z' in preview):
                raise ValueError('指定预览对象时须同时提供 pitch 和 start_z')
            if 'pitch' in preview:
                preview_selection = preview['pitch'], preview['start_z']
                if preview_selection[0] not in self.pitches or preview_selection[1] not in self.starts:
                    raise ValueError('预览对象的间距与起点须在目标的允许列表中')
        for pitch in self.pitches:
            for start in self.starts:
                row, state = self._evaluate(pitch, start)
                if state is None:
                    rejected.append(row)
                    continue
                accepted.append(row)
                if best is None or self._rank(row) < self._rank(best):
                    best = row
                    if preview is not None and preview_selection is None:
                        selected = row, state
                if preview_selection == (pitch, start):
                    selected = row, state

        report = dict(schema_version=1, status='ranked' if accepted else 'no_legal_candidates',
                      goal=self.goal, source=self.source, component_sha256=self.component['content_sha256'],
                      spectrum=dict(axis='z', lo_z=self.lo[2], depth=self.depth, fft_depth=self.fft_depth,
                                    bins=self.bins, units='cycles_per_block', target_frequency=1 / self.goal['target_pitch']),
                      evaluated=len(accepted) + len(rejected), eligible=len(accepted), rejected=len(rejected), best=best,
                      candidates=sorted(accepted, key=self._rank) + rejected,
                      rejection_counts=dict(Counter(row['problem']['code'] for row in rejected)),
                      model_modified=False, asset_written=False, approval_created=False)
        if selected is not None:
            row, state = selected
            candidate = copy(self.host)
            candidate._adopt_edits(*state)
            output = (candidate.workspace / Path(preview['output'])).resolve()
            rendered = candidate.preview(output, preview.get('cameras', []))
            receipt = output / 'beam-rhythm.json'
            write_json(receipt, dict(source=self.source, candidate=row, goal=self.goal,
                                     preview_source_sha256=file_hash(rendered['source']),
                                     snapshot_sha256=file_hash(rendered['snapshot']), approval_created=False))
            report['preview'] = dict(rendered, candidate_sha256=row['candidate_sha256'], receipt=str(receipt))
        elif preview_selection is not None:
            report['preview_problem'] = next(row['problem'] for row in rejected
                                             if (row['pitch'], row['start_z']) == preview_selection)
        self.host._unchanged()
        return report

    def adopt(self, pitch, start_z, candidate_sha256):
        if type(pitch) is not int or type(start_z) is not int or pitch not in self.pitches or start_z not in self.starts:
            raise ValueError('采用对象的间距与起点须在目标的允许列表中')
        row, state = self._evaluate(pitch, start_z)
        if state is None or row['candidate_sha256'] != candidate_sha256:
            raise ModelConflict('STALE_BEAM_RHYTHM_CANDIDATE', [dict(pitch=pitch, start_z=start_z, problem=row.get('problem'))])
        return dict(self.host._adopt_edits(*state), candidate_sha256=candidate_sha256, candidate=row)
