"""Transfer selected undecimated detail bands into a straight eave underside."""
from collections import Counter
from copy import copy, deepcopy
from itertools import pairwise
from pathlib import Path

import numpy as np

from nbt_catalog import catalog
from nbt_change_policy import ChangePolicyError
from nbt_collision import FACING, collision_cells
from nbt_model import state
from nbt_model_preflight import bounds
from nbt_object_scene import engine_hash
from nbt_refine import read_master
from nbt_registry import effective
from nbt_structure_agent import _schema
from nbt_working_model import ModelConflict, digest, file_hash, model_hash, value_at, write_json


def detail_bands(curve, levels):
    """Undecimated B3 spline à trous decomposition with even reflection."""
    smooth = np.asarray(curve, dtype=float)
    bands = []
    for level in range(levels):
        step = 2**level
        radius = 2 * step
        reflected = np.pad(smooth, radius, mode='reflect')
        low = sum(weight * reflected[i*step:i*step + len(smooth)]
                  for i, weight in enumerate((1, 4, 6, 4, 1))) / 16
        bands.append(smooth - low)
        smooth = low
    return np.stack(bands), smooth


def offset(pos, direction, count=1):
    dx, dz = FACING[direction]
    return pos[0] + dx * count, pos[1], pos[2] + dz * count


def strip_points(model, strip, adjacent=False):
    along, inward = strip['along'], strip['inward']
    if np.dot(FACING[along], FACING[inward]) != 0:
        raise ValueError('檐口沿线和向内方向须垂直')
    start, count = strip['start'], strip['length']
    extra = 1 if adjacent else 0
    points = [offset(start, along, i) for i in range(-extra, count + extra)]
    if not all(model.in_bounds(p) for p in points):
        raise ValueError('檐口采样须在模型内，目标开间两端须有相邻站点')
    return points


def profile_depth(value, inward):
    """Read the contiguous lower-half depth in half blocks from the inner face."""
    name, props = effective(value)
    cells, reason = collision_cells(value)
    if (reason or len(cells) not in (4, 6, 8) or sum(y == 1 for _, y, _ in cells) != 4
            or props.get('waterlogged') == 'true'):
        return None
    if name.endswith('_stairs') and (props['facing'], props['shape']) != (inward, 'straight'):
        return None
    return (len(cells) - 4) // 2


def read_curve(model, points, inward):
    curve = [profile_depth(model.get(p), inward) for p in points]
    invalid = [dict(pos=list(p), state=model.get(p)) for p, depth in zip(points, curve) if depth is None]
    if invalid:
        raise ModelConflict('INVALID_EAVE_PROFILE', invalid)
    return np.asarray(curve, dtype=int)


def face_contacts(model, first, second, direction):
    axis = 0 if FACING[direction][0] else 2
    facing = int(sum(FACING[direction]) > 0)
    a, a_reason = collision_cells(model.get(first))
    b, b_reason = collision_cells(model.get(second))
    face_a = {tuple(v for i, v in enumerate(cell) if i != axis) for cell in a if cell[axis] == facing}
    face_b = {tuple(v for i, v in enumerate(cell) if i != axis) for cell in b if cell[axis] != facing}
    return face_a, face_a & face_b if not (a_reason or b_reason) else set()


def projection_errors(before, after, edits):
    """Compare all potentially changed half-cell rays along the three axes."""
    added, removed = set(), set()
    for row in edits:
        p = row['pos']
        old, _ = collision_cells(before.get(p))
        new, _ = collision_cells(after.get(p))
        for cells, output in ((set(new) - set(old), added), (set(old) - set(new), removed)):
            output.update(tuple(2*v + h for v, h in zip(p, cell)) for cell in cells)

    reports, failures = {}, []
    for axis, name in enumerate('xyz'):
        def project(cell):
            return cell[:axis] + cell[axis+1:]

        new_rays, old_rays = {project(p) for p in added}, {project(p) for p in removed}
        rays = sorted(new_rays | old_rays)
        report = dict(tested_rays=len(rays), changed_rays=0, uncertain_rays=0, rays_sha256=digest(rays))
        for ray in rays:
            # Unedited occupancy on the ray is identical. Only an exact
            # witness can prove equality when the edited cells alone differ.
            if ray in new_rays and ray in old_rays:
                continue
            unknown = False
            projected_local = tuple(v % 2 for v in ray)
            for depth in range(before.size[axis]):
                p = ray[:axis] + (2*depth,) + ray[axis:]
                block = tuple(v//2 for v in p)
                shape, reason = collision_cells(before.get(block))
                unknown |= reason is not None
                if not reason and any(project(cell) == projected_local
                                      and tuple(2*v+h for v, h in zip(block, cell)) not in removed
                                      for cell in shape):
                    break
            else:
                report['uncertain_rays' if unknown else 'changed_rays'] += 1
                failures.append(dict(axis=name, ray_half=list(ray), uncertain=unknown,
                                     occupied_before=ray in old_rays, occupied_after=ray in new_rays))
        reports[name] = report
    return reports, failures


def stair_conflicts(model, edits):
    """Reject perpendicular same-half neighbors that can reshape a changed stair."""
    def stair(pos):
        name, props = effective(model.get(pos))
        return props if name.endswith('_stairs') else None

    pairs = set()
    for row in edits:
        p = tuple(row['pos'])
        first = stair(p)
        if first is None:
            continue
        for direction in FACING:
            q = offset(p, direction)
            other = stair(q)
            if other and first['half'] == other['half'] and np.dot(FACING[first['facing']], FACING[other['facing']]) == 0:
                pairs.add(tuple(sorted((p, q))))
    return [dict(positions=[list(p), list(q)], states=[model.get(p), model.get(q)])
            for p, q in sorted(pairs)]


class WaveletEave:
    def __init__(self, host, goal):
        schema = catalog()['working_model']['actions']['wavelet_eave']['properties']['goal']
        _schema(goal, schema, '檐口移植目标')
        self.host, self.goal = host, deepcopy(goal)
        host._unchanged()
        target, reference = goal['target'], goal['reference']
        self.inward, self.along = target['inward'], target['along']
        self.with_neighbors = strip_points(host.model, target, adjacent=True)
        self.points = self.with_neighbors[1:-1]
        self.ridge = goal['ridge']
        lo, hi = self.ridge['lo'], self.ridge['hi']
        if not all(host.model.in_bounds(p) for p in (lo, hi)) or any(a > b for a, b in zip(lo, hi)):
            raise ValueError('屋脊范围须为主模型内的有序闭区间')
        if any(self._in_ridge(p) for p in self.points):
            raise ValueError('目标开间与冻结的屋脊区域重叠')
        ridge_values = sorted((p, v, p in host.walls) for p, v in host.model.blocks.items() if self._in_ridge(p))
        if not ridge_values:
            raise ValueError('冻结的屋脊区域须包含实际方块')
        self.frozen_ridge = dict(region=self.ridge, occupied=len(ridge_values), sha256=digest(ridge_values))
        self.envelope = bounds(host.model.blocks)
        self.reference_source = None
        if ('source' in reference) != ('source_sha256' in reference):
            raise ValueError('外部檐口参考须同时提供 source 和 source_sha256')
        if 'source' in reference:
            self.reference_source = (host.workspace / reference['source']).resolve()
            if self.reference_source.suffix.lower() not in ('.snbt', '.nbt'):
                raise ValueError('外部檐口参考须为 SNBT 或 NBT')
            self._unchanged()
            reference_model, _ = read_master(self.reference_source)
        else:
            reference_model = host.model
        reference_points = strip_points(reference_model, reference)
        if len(reference_points) != len(self.points):
            raise ValueError('目标和参考须有相同采样数，每站一格')
        if not self.reference_source and set(reference_points) & set(self.points):
            raise ValueError('同模型内的参考和目标采样坐标须独立')
        self.reference_curve = read_curve(reference_model, reference_points, reference['inward']) / 2
        self.before = read_curve(host.model, self.points, self.inward) / 2
        self.strengths = sorted(set(goal['strengths']))
        self.levels = sorted(set(goal['levels']))
        reference_bands, _ = detail_bands(self.reference_curve, max(self.levels))
        target_bands, _ = detail_bands(self.before, max(self.levels))
        indexes = np.asarray(self.levels) - 1
        i = np.arange(len(self.points))
        distance = np.minimum(i, i[::-1])
        self.taper = (1 - np.cos(np.pi * np.minimum(1, distance / goal['taper']))) / 2
        self.delta = self.taper * (reference_bands[indexes] - target_bands[indexes]).sum(axis=0)
        self.source = dict(working_sha256=host._content_token(), source_sha256=host.source_sha256,
                           parent_revision=host.parent_revision, engine_sha256=engine_hash(),
                           baseline_sha256=model_hash(host._baseline, host._baseline_walls),
                           baseline_phase=host._baseline_phase, limits=dict(host.limits),
                           reference_source=str(self.reference_source) if self.reference_source else None,
                           reference_sha256=reference.get('source_sha256'),
                           assembly_owners_sha256=digest(sorted((host._assembly_owners or {}).items())))
        self.curves = dict(unit='blocks', target_positions=list(map(list, self.points)),
                           reference_positions=list(map(list, reference_points)), before=self.before.tolist(),
                           reference=self.reference_curve.tolist(), tapered_detail_delta=self.delta.tolist(),
                           target=(self.before + self.delta).tolist(),
                           taper=self.taper.tolist(), levels=self.levels, wavelet='undecimated_b3_spline_reflect')
        self.states = self._materials(goal['materials'])
        self.owners = host._owned_positions()
        self._unchanged()

    def _unchanged(self):
        self.host._unchanged()
        if self.reference_source:
            expected = self.goal['reference']['source_sha256']
            if not self.reference_source.is_file() or file_hash(self.reference_source) != expected:
                raise ModelConflict('STALE_EAVE_REFERENCE', [dict(source=str(self.reference_source))])

    def _in_ridge(self, p):
        return all(lo <= v <= hi for v, lo, hi in zip(p, self.ridge['lo'], self.ridge['hi']))

    def _materials(self, materials):
        slab, stair = (effective(state(materials[key]))[0] for key in ('slab', 'stair'))
        if not slab.endswith('_slab') or not stair.endswith('_stairs'):
            raise ValueError('檐口材质须提供原版半砖和楼梯方块 ID')
        values = [state(f'{slab}[type=top,waterlogged=false]'),
                  state(f'{stair}[facing={self.inward},half=top,shape=straight,waterlogged=false]'),
                  state(f'{slab}[type=double,waterlogged=false]')]
        if [profile_depth(value, self.inward) for value in values] != [0, 1, 2]:
            raise ValueError('檐口材质没有预期的半格碰撞形状')
        return values

    def _compile_edits(self, depths):
        host = self.host
        changes = {p: self.states[depth] for p, old, depth in zip(self.points, self.before, depths)
                   if old * 2 != depth}
        if not changes:
            raise ModelConflict('NO_QUANTIZED_DETAIL', [])
        owned = [dict(pos=list(p), owner=self.owners[p]) for p in changes if p in self.owners]
        if owned:
            raise ModelConflict('MANAGED_EAVE_POSITION', owned)
        endpoints = bounds(self.points)
        start, end = endpoints['lo'], endpoints['hi']
        operations = []
        for p, value in changes.items():
            local = [v - a for v, a in zip(p, start)]
            operations.append(dict(kind='box', label='檐底节点', lo=local, hi=local, state=value, classification='body'))
        recipe = dict(tool='structure', arguments=dict(name='檐底局部细节',
                      size=[b - a + 1 for a, b in zip(start, end)], anchor=[0, 0, 0], operations=operations))
        placed, compiled = host._compile(recipe, dict(position=start))
        if {p: pair[0] for p, pair in placed.items()} != changes:
            raise ModelConflict('EAVE_COMPILATION_MISMATCH', [])
        edits = []
        for p, value in changes.items():
            before = value_at(host.model, host.walls, p)
            edits.append(dict(pos=list(p), before=before, after=[value, before[1]]))
        return edits, compiled['content_sha256']

    def _contacts(self, candidate, edits):
        all_depths = read_curve(candidate, self.with_neighbors, self.inward)
        seams, failures = [], []
        height_axis = 1 if FACING[self.along][1] else 0
        for i, (first, second) in enumerate(pairwise(self.with_neighbors)):
            _, contact = face_contacts(candidate, first, second, self.along)
            seam = i in (0, 1, len(self.points) - 1, len(self.points))
            step = int(abs(all_depths[i] - all_depths[i+1]))
            row = dict(positions=[list(first), list(second)], shared_half_faces=len(contact), depth_step_half=step)
            if seam:
                seams.append(row)
            if sum(cell[height_axis] == 1 for cell in contact) != 2 or (seam and step > 1):
                failures.append(row)
        if failures:
            raise ModelConflict('EAVE_SEAM', failures)
        supports = []
        for p in self.with_neighbors:
            backing = offset(p, self.inward)
            face, contact = face_contacts(candidate, p, backing, self.inward)
            supports.append(dict(pos=list(p), backing=list(backing), state=candidate.get(backing),
                                 required_half_faces=len(face), shared_half_faces=len(contact)))
        if missing := [row for row in supports if row['required_half_faces'] != row['shared_half_faces']]:
            raise ModelConflict('EAVE_SUPPORT', missing)
        conflicts = [dict(stage=stage, **row)
                     for stage, model in (('before', self.host.model), ('candidate', candidate))
                     for row in stair_conflicts(model, edits)]
        if conflicts:
            raise ModelConflict('EAVE_STAIR_NEIGHBOR', conflicts)
        return all_depths[1:-1] / 2, seams, supports

    def _evaluate(self, strength):
        host = self.host
        proposed = self.before + strength * self.delta
        quantized = np.clip(np.floor(2 * proposed + 0.5), 0, 2).astype(int)
        row = dict(strength=strength, applicable=False, proposed=proposed.tolist(),
                   quantized=(quantized / 2).tolist())
        try:
            edits, compiled_sha = self._compile_edits(quantized)
            row['edits'] = edits
            staged = host._stage_edits(edits)
            candidate, walls, changes, total = staged
            measured, seams, supports = self._contacts(candidate, edits)
            row['measured'] = measured.tolist()
            if not np.array_equal(measured, quantized / 2):
                raise ModelConflict('EAVE_COMPILATION_MISMATCH', [])
            projections, failures = projection_errors(host.model, candidate, edits)
            row['projections'] = projections
            if failures:
                raise ModelConflict('EAVE_OUTLINE', failures)
            host._check_edit_policies(candidate, walls, host.instances)
            assembly = host._assembly_checks(candidate, host.instances)
            if not assembly['passed']:
                raise ModelConflict('ASSEMBLY_INVALID', [check for check in assembly['checks'] if not check['passed']])
            building = host._check_candidate_building(staged, None)
        except ChangePolicyError as error:
            return dict(row, problem=dict(code=error.kind, message=str(error), total=error.total,
                                          conflicts=[dict(pos=list(p)) for p in error.positions])), None
        except ModelConflict as error:
            if error.code.startswith(('STALE_', 'CONTEXT_')):
                raise
            return dict(row, problem=dict(code=error.code, total=len(error.conflicts),
                                          conflicts=error.conflicts[:32])), None
        except ValueError as error:
            return dict(row, problem=dict(code='HOST_VALIDATION_FAILED', message=str(error))), None

        target = self.before + self.delta
        old_error = float(np.sqrt(np.mean(self.delta**2)))
        new_error = float(np.sqrt(np.mean((measured - target)**2)))
        row.update(error_before=old_error, error_after=new_error)
        if new_error >= old_error - 1e-12:
            return dict(row, problem=dict(code='NO_DETAIL_IMPROVEMENT')), None
        candidate_hash = model_hash(candidate, walls)
        token = digest([self.source, self.goal, strength, compiled_sha, candidate_hash])
        routes = ('required_passed' if host.context.get('require_routes') else
                  'not_required' if host.context.get('start') and host.context.get('targets') else 'not_declared')
        return dict(row, applicable=True, candidate_sha256=token, component_sha256=compiled_sha,
                    model_sha256=candidate_hash, changes=changes, total_changes=total,
                    checks=dict(ridge=self.frozen_ridge, envelope_blocks=self.envelope,
                                outside_selected_positions=0, wall_changes=changes['wall_membership_changes'],
                                ownership_changes=0,
                                protection='passed', reserved='passed', budget='passed',
                                endpoints=[dict(pos=list(p), state=candidate.get(p))
                                           for p in (self.points[0], self.points[-1])],
                                seams=seams, backing_contacts=supports,
                                stair_orientation='checked', structural_load='not_checked',
                                routes=routes, assembly='passed', bound_building=building)), staged

    def search(self, preview):
        requested = None
        if preview is not None:
            schema = catalog()['working_model']['actions']['wavelet_eave']['properties']['preview']
            _schema(preview, schema, '檐口预览')
            requested = preview.get('strength')
            if requested is not None and requested not in self.strengths:
                raise ValueError('预览强度须在候选强度列表中')
        best, selected, preview_problem = None, None, None
        rows = []
        for strength in self.strengths:
            row, staged = self._evaluate(strength)
            rows.append(row)
            if requested == strength:
                if staged is None:
                    preview_problem = row['problem']
                else:
                    selected = row, staged
            if staged is not None:
                rank = (round(row['error_after'], 12), len(row['edits']), strength)
                if best is None or rank < best[0]:
                    best = rank, row
                    if requested is None:
                        selected = row, staged
        report = dict(schema_version=1, status='ranked' if best else 'no_legal_candidates',
                      goal=self.goal, source=self.source, curves=self.curves, best=best[1] if best else None,
                      candidates=rows, rejection_counts=dict(Counter(row['problem']['code'] for row in rows if 'problem' in row)),
                      model_modified=False, asset_written=False, approval_created=False)
        if preview is not None and selected is not None:
            report['preview'] = self._preview(preview, *selected)
        if preview_problem is not None:
            report['preview_problem'] = preview_problem
        self._unchanged()
        return report

    def _preview(self, preview, row, staged):
        candidate = copy(self.host)
        candidate._adopt_edits(staged, None)
        output = (candidate.workspace / Path(preview['output'])).resolve()
        result = candidate.preview(output, preview.get('cameras', []))
        from nbt_large_assembly import is_assembly_source, read_assembly
        source = Path(result['source'])
        disk, walls = read_assembly(source) if is_assembly_source(source) else read_master(source)
        if model_hash(disk, walls) != row['model_sha256']:
            raise ModelConflict('EAVE_PREVIEW_ROUNDTRIP', [])
        measured, seams, backing = self._contacts(disk, row['edits'])
        projections, failures = projection_errors(self.host.model, disk, row['edits'])
        if failures or measured.tolist() != row['measured']:
            raise ModelConflict('EAVE_PREVIEW_ROUNDTRIP', failures)
        receipt = output / 'wavelet-eave.json'
        write_json(receipt, dict(goal=self.goal, source=self.source, curves=self.curves, candidate=row,
                                 readback_measured=measured.tolist(),
                                 readback_checks=dict(seams=seams, backing_contacts=backing, projections=projections),
                                 preview_source_sha256=file_hash(source),
                                 snapshot_sha256=file_hash(result['snapshot']), approval_created=False))
        return dict(result, receipt=str(receipt), candidate_sha256=row['candidate_sha256'])

    def adopt(self, strength, candidate_sha256):
        if type(strength) not in (float, int) or strength not in self.strengths:
            raise ValueError('采用强度须在候选强度列表中')
        # Use the canonical numeric representation used for search and hashing.
        strength = self.strengths[self.strengths.index(strength)]
        row, staged = self._evaluate(strength)
        if staged is None or row['candidate_sha256'] != candidate_sha256:
            raise ModelConflict('STALE_EAVE_CANDIDATE', [dict(strength=strength, problem=row.get('problem'))])
        self._unchanged()
        return dict(self.host._adopt_edits(staged, None), candidate_sha256=candidate_sha256, candidate=row)
