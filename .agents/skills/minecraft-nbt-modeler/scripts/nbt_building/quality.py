"""Evaluate an authored building checklist against static and recorded visual evidence."""
from fractions import Fraction

from nbt_building.plan import fingerprint
from nbt_building.quality_plan import DIMENSIONS, RUBRIC, items

ROUTE_CODES = ('ROUTE_FAILED', 'ROUTE_LEG_FAILED', 'STAIR_ROUTE_FAILED')
BLOCKING_CODES = (*ROUTE_CODES, 'DESIGN_INVALID')
SCORES = {'completion': (0, 2, 4), 'circulation': (0, 2, 4)}
SEVERITY = {'blocker': 0, 'required': 1, 'gap': 2, 'improvement': 3}


def route_state(report):
    if report.get('unknown_shapes'):
        return 'unsupported'
    if report.get('passed'):
        return 'pass'
    if not report.get('targets') or report.get('start') is None or report.get('search_limit_reached'):
        return 'pending'
    # A verified solid envelope may reject a real thin gap.
    if report.get('conservative_obstacles') and report.get('start_standing') and all(
        row['standing'] for row in report['targets']
    ):
        return 'pending'
    return 'blocked'


def issue(identifier, dimension, severity, target, reason, evidence, suggestion, recheck, related=()):
    return dict(id=identifier, dimension=dimension, severity=severity, target=target, reason=reason,
                evidence=evidence, suggestion=suggestion, recheck=recheck, related_items=list(related))


def route_finding(identifier, spec, report, pointer, state, target=None):
    target = target or {}
    reason = target.get('reason') or report.get('failure') or state
    position = target.get('feet', report.get('start'))
    if not report.get('start_standing', True) and target.get('standing', True):
        position = report.get('start')
    return issue(identifier, 'circulation', 'blocker' if state == 'blocked' else 'gap',
                 dict(activity=spec.get('id'), space=target.get('name'), position=position), reason,
                 dict(pointer=pointer, collision_mode=report.get('collision_mode')),
                 '检查起终点脚下支撑、脚位净空和沿途碰撞。' if state == 'blocked' else '复核碰撞能力和搜索条件，必要时补充游戏证据。',
                 '按原脚位复查该路段、相邻路段和操作面。', spec.get('related', []))


def activity_findings(activity, check, pointer, required, related, segment_ids):
    if check is None:
        return 'pending', []
    findings, states = [], []
    identifier = activity['id']
    for i, segment in enumerate(check['segments']):
        report = segment['report']
        state = route_state(report)
        states.append(state)
        if state != 'pass':
            target = next((row for row in report['targets'] if not row['reachable']), None)
            leg = segment_ids[i] if segment_ids else i
            row = route_finding(f'activity.{identifier}.segment.{leg}', dict(id=identifier, related=related),
                                report, f'{pointer}/segments/{i}/report', state, target)
            row['target'].update(segment_index=i, segment=leg)
            if state == 'blocked' and not required:
                row['severity'] = 'improvement'
            findings.append(row)
    for i, face in enumerate(check['use_faces']):
        if face['passed']:
            continue
        reason = face['reason']
        unknown_route = any(route_state(segment['report']) == 'unsupported' for segment in check['segments'])
        uncertain = (face.get('interface_code') == 'INTERFACE_UNSUPPORTED_SHAPE' or
                     unknown_route and reason in ('invalid_standing_pose', 'approach_obstructed'))
        state = 'unsupported' if uncertain else 'blocked'
        states.append(state)
        severity = 'gap' if uncertain else 'blocker' if required else 'improvement'
        findings.append(issue(f'activity.{identifier}.stop.{face["stop_index"]}.{face["part"]}.{face["interface"]}',
            'circulation', severity,
            dict(activity=identifier, stop_index=face['stop_index'], part=face['part'],
                 interface=face['interface'], position=face['feet']),
            reason, dict(pointer=f'{pointer}/use_faces/{i}'),
            '核对该站的脚位、柜台朝向及到操作面的净空。',
            '以同一活动条件复查所有路段及该操作面。', related))
    return next((s for s in ('blocked', 'unsupported', 'pending') if s in states), 'pass'), findings


def comfort(segments, space):
    measurements = []
    for segment in segments:
        report = segment['report']
        if route_state(report) != 'pass':
            continue
        for target in report['targets']:
            path = target.get('path', [])
            narrow = [p for p in path if not space.clear_box(
                (p[0] - .6, p[1], p[2] - .6), (p[0] + .6, p[1] + 1.8, p[2] + .6))]
            measurements.append(dict(segment=segment['index'], samples=len(path), wide=len(path) - len(narrow),
                                     narrow_positions=narrow, collision_mode=report['collision_mode']))
    total = sum(row['samples'] for row in measurements)
    wide = sum(row['wide'] for row in measurements)
    evidence = dict(width=1.2, height=1.8, segments=measurements, samples=total, wide=wide)
    if total:
        evidence['wide_percent'] = round(100 * wide / total, 2)
    # Partial path measurements remain useful in a failed activity.
    if not total or len(measurements) != len(segments):
        return None, evidence
    ratio = Fraction(wide, total)
    return (4 if ratio >= Fraction(4, 5) else 2 if ratio >= Fraction(1, 2) else 0), evidence


def aggregate(rows, defined, gate=None):
    applicable = [r for r in rows if r['status'] != 'not_applicable']
    if not applicable:
        return dict(status=gate if gate and gate != 'pass' else 'not_applicable' if defined else 'undefined', score=None, interval=None,
                    coverage=None, items=rows)
    weight = sum(Fraction(r['weight_numerator'], r['weight_denominator']) for r in applicable)
    measured = [(Fraction(r['weight_numerator'], r['weight_denominator']), Fraction(r['grade'], 4))
                for r in applicable if r['status'] == 'measured']
    m = sum(w for w, _ in measured)
    earned = sum(w * normalized for w, normalized in measured)
    return dict(status=gate if gate and gate != 'pass' else
                'measured' if m == weight else 'partial' if m else 'pending',
                score=round(float(100 * earned / weight), 2) if m == weight and gate in (None, 'pass') else None,
                interval=[round(float(100 * earned / weight), 2), round(float(100 * (earned + weight - m) / weight), 2)]
                if 0 < m < weight and gate in (None, 'pass') else None,
                coverage=round(float(100 * m / weight), 2), items=rows)


def ordered_route(report):
    if report is None:
        return None
    return dict(report, targets=sorted(report['targets'], key=lambda target: target['name']))


def completion(item, checks, missing_part_locations, review):
    requirement = item['requirement']
    name = requirement['id']
    expected = requirement.get('parts', [])
    parts = checks.get(('requirement_targets', name))
    reasons = []
    if parts and parts[0]['missing_parts']:
        missing = parts[0]['missing_parts']
        reasons = [dict(reason='missing_part', part=key, pointer=parts[1],
                        position=missing_part_locations.get(key)) for key in missing]
        if len(missing) == len(expected):
            return 0, reasons
    declared = [(row['kind'], row['id']) for row in item.get('checks', [])]
    measured = [checks.get(key) for key in declared]
    # A failing declared check proves partial implementation only when a
    # distinct part or condition supplies evidence of the implemented portion.
    implemented = bool(parts and expected and len(reasons) < len(expected))
    failed = []
    missing = False
    for key, row in zip(declared, measured):
        if row is None:
            missing = True
            continue
        check, pointer = row
        if key[0] == 'activity_routes' and not check['passed']:
            # Route feasibility is already scored and tracked by circulation.
            missing = True
            continue
        if check['passed']:
            implemented = True
        else:
            failed.append(dict(reason='condition_failed', check=key[1], kind=key[0], pointer=pointer,
                               failed_segments=check.get('failed_segments', [])))
    if reasons or failed:
        proof = reasons + failed
        if review:
            proof.append(review)
            if review['grade'] == 0:
                return 0, proof
        return (2 if implemented or review else None), proof
    if item.get('views'):
        if review:
            return (None if missing and review['grade'] == 4 else review['grade']), [review]
        return None, []
    if declared and not missing and all(row[0]['passed'] for row in measured):
        return 4, [dict(pointer=row[1]) for row in measured]
    return None, []


def assess(plan, plan_sha256, geometry_sha256, *, source=None, source_sha256=None, validation=None,
           conflicts=(), code=None, volume=None, review=None, missing_review=None, style_geometry=None):
    checklist = items(plan)
    quality = plan.get('quality', {})
    binding = dict(rubric=RUBRIC, plan_sha256=plan_sha256, geometry_sha256=geometry_sha256,
                   source=source, source_sha256=source_sha256, checklist_revision=quality.get('revision'),
                   stage=quality.get('stage'), checklist_sha256=fingerprint(dict(
                       revision=quality.get('revision'), stage=quality.get('stage'), items=checklist)))
    whole = (validation or {}).get('whole_model', {})
    host = whole if isinstance(whole, dict) else {}
    route_context = {key: plan['context'].get(key) for key in ('start', 'targets', 'route_legs')}
    binding.update(route_scope_sha256=fingerprint(route_context),
                   comparison_scope=quality.get('comparison_scope', plan['name']))
    evidence = dict(checks=(validation or {}).get('architecture', {}).get('checks', []), conflicts=list(conflicts),
                    host_routes=ordered_route(host.get('routes')), host_route_legs=[
                        dict(row, report=ordered_route(row['report'])) for row in host.get('route_legs', [])])
    raw_checks = evidence['checks']
    prefix = '/evidence/checks'
    if code == 'DESIGN_INVALID' and not raw_checks:
        raw_checks = evidence['conflicts']
        prefix = '/evidence/conflicts'
    checks = {(row['kind'], row['id']): (row, f'{prefix}/{index}')
              for index, row in enumerate(raw_checks)}
    weighted = {dimension: [] for dimension in DIMENSIONS}
    finding_rows, activities = [], {}
    space = None
    if volume is not None and plan.get('activities'):
        from nbt_collision import _Space
        space = _Space(volume, conservative_obstacles=True)
    for index, raw in enumerate(conflicts if code in ROUTE_CODES else ()):
        report = raw.get('report', raw)
        state = route_state(report)
        for target in [row for row in report.get('targets', []) if not row['reachable']] or [None]:
            # Activity diagnostics provide the more precise location when available.
            name = target['name'] if target else 'start'
            pointer = f'/evidence/conflicts/{index}' + ('/report' if 'report' in raw else '')
            scope = f'instance.{raw["instance"]}' if 'instance' in raw else f'host.{raw.get("name", "routes")}'
            if 'segment' in raw:
                scope += f'.segment.{raw["segment"]}'
            finding = route_finding(f'{scope}.{name}', {}, report, pointer, state, target)
            if 'instance' in raw:
                finding['target']['part'] = raw['instance']
            finding_rows.append(finding)
    review_items = review.get('items', {}) if review else {}
    part_positions = {part['id']: part['position'] for part in plan.get('parts', [])}
    activity_segments = {row['id']: [leg['id'] for leg in row.get('segments', [])]
                         for row in quality.get('activities', [])}
    for identifier, spec in checklist.items():
        dimension, group = spec['dimension'], spec['group']
        observed = review_items.get(identifier)
        segment_index = spec.get('segment_index')
        grade, proof = None, []
        state = 'pending'
        if spec.get('not_applicable'):
            state = 'not_applicable'
        elif dimension == 'completion':
            grade, proof = completion(spec, checks, part_positions, observed)
        elif dimension == 'circulation':
            check, pointer = checks.get(('activity_routes', group), (None, None))
            if group not in activities:
                related = ['completion.' + name for name in spec['linked_requirements']]
                status, findings = activity_findings(spec['activity'], check, pointer, spec['required'], related,
                                                     activity_segments.get(group))
                activities[group] = dict(status=status, required=spec['required'], evidence=pointer,
                                         actor=spec['activity']['actor'], purpose=spec['activity']['purpose'],
                                         conditions_sha256=fingerprint(spec['activity']))
                finding_rows.extend(findings)
            status = activities[group]['status']
            segments = check['segments'] if check else []
            if segment_index is not None and segments:
                segments = [segments[segment_index]]
                pointer = f'{pointer}/segments/{segment_index}'
                status = route_state(segments[0]['report'])
            state = status if status != 'pass' else state
            if identifier.endswith('.clearance') and segments and space is not None:
                grade, measured = comfort(segments, space)
                proof = [dict(measured, pointer=pointer)]
            elif status == 'pass' and observed:
                grade, proof = observed['grade'], [observed, dict(pointer=pointer)]
        elif dimension == 'style' and spec.get('quantitative'):
            if style_geometry is not None:
                from nbt_building import style_measurement
                measurement = style_measurement.measure(*style_geometry, plan, spec['quantitative'])
                measurement['pointer'] = f'/dimensions/style/items/{len(weighted[dimension])}/evidence/0'
                proof = [measurement]
                if observed:
                    proof.append(observed)
                if measurement['missing'] or observed or not spec.get('views'):
                    grade = style_measurement.grade(measurement, observed)
                if spec.get('rule'):
                    rule = spec['rule_condition']
                    check = checks.get((rule['kind'], rule['id']))
                    if check and not check[0].get('error'):
                        proof.append(dict(pointer=check[1], passed=check[0]['passed']))
                        if grade is not None and not check[0]['passed']:
                            grade = min(grade, 2)
                    elif not measurement['missing']:
                        grade = None
        elif dimension == 'style' and spec.get('rule'):
            rule = spec['rule_condition']
            check = checks.get((rule['kind'], rule['id']))
            if check:
                proof = [dict(pointer=check[1], passed=check[0]['passed'])]
                if not check[0].get('error'):
                    if observed:
                        grade = observed['grade'] if check[0]['passed'] else min(observed['grade'], 2)
                        proof.append(observed)
                    elif not spec.get('views'):
                        grade = 4 if check[0]['passed'] else 0
        elif observed:
            grade, proof = observed['grade'], [observed]
        if grade is not None:
            state = 'measured'
        target = dict(spec.get('target') or {})
        if spec.get('location'):
            target['position'] = spec['location']['position']
        elif dimension == 'completion':
            target = dict(parts=spec['requirement'].get('parts', []), spaces=spec['requirement'].get('spaces', []))
        elif dimension == 'circulation':
            target = dict(activity=group, stops=spec['activity']['stops'])
            if segment_index is not None:
                target.update(segment_index=segment_index, stops=target['stops'][segment_index:segment_index + 2])
        needed = spec.get('views', [])
        local_spec = dict(spec, activity=dict(spec['activity'], stops=target['stops'])) if segment_index is not None else spec
        conditions = fingerprint(local_spec)
        next_evidence = None
        if grade is None and state != 'not_applicable':
            next_evidence = f'按登记机位补拍并核对：{", ".join(needed)}' if needed else spec['goal']
            if spec.get('quantitative') and style_geometry is None:
                next_evidence = '从绑定建筑方案的制作源回读量化部位的实际构件。'
        weighted[dimension].append(dict(id=identifier, group=group, status=state, grade=grade, evidence=proof,
            goal=spec['goal'], target=target, conditions_sha256=conditions,
            views=needed, missing_views=(review or {}).get('missing', {}).get(identifier, needed if not observed else []),
            next_evidence=next_evidence,
            not_applicable=spec.get('not_applicable')))
        if grade is not None and grade < 4:
            positions = [point for row in proof for segment in row.get('segments', []) for point in segment['narrow_positions']]
            positions += [row['position'] for row in proof if row.get('position') is not None]
            if positions:
                target = dict(target, positions=positions[:16])
            affected = next((row['part'] for row in proof if row.get('method') and row.get('part')), None)
            if affected:
                target = dict(target, part=affected)
            finding_rows.append(issue(identifier, dimension, 'required' if
                dimension == 'completion' and spec['required'] else 'improvement',
                target, next((row.get('note') for row in proof if row.get('note')), spec['goal']),
                proof, next((row['suggestion'] for row in proof if row.get('suggestion')),
                            '按目标调整此部位后复查：' + spec['goal']),
                '在相同条件下复查：' + (', '.join(needed) if needed else spec['goal'])))
    required_states = [row['status'] for row in activities.values() if row['required']]
    required_states += [route_state(raw.get('report', raw)) for raw in conflicts
                        if code in ROUTE_CODES]
    gate = next((name for name in ('blocked', 'unsupported', 'pending') if name in required_states), 'pass')
    dimensions = {}
    for dimension, rows in weighted.items():
        counts = {}
        for row in rows:
            if row['status'] != 'not_applicable':
                counts[row['group']] = counts.get(row['group'], 0) + 1
        for row in rows:
            if row['status'] == 'not_applicable':
                weight = Fraction(0)
            elif dimension == 'completion':
                weight = Fraction(2 if checklist[row['id']]['required'] else 1)
            else:
                weight = Fraction(1, counts[row['group']])
            row.update(weight_numerator=weight.numerator, weight_denominator=weight.denominator)
        result = aggregate(rows, bool(rows) or bool(quality), gate if dimension == 'circulation' else None)
        if dimension == 'style':
            result['sites_at_standard'] = sum(r['status'] == 'measured' and r['grade'] >= 3 for r in rows)
            result['applicable_sites'] = sum(r['status'] != 'not_applicable' for r in rows)
        dimensions[dimension] = result
    primary = []
    for row in finding_rows:
        if row['dimension'] == 'completion':
            # A missing interface part or the same broken stair should be fixed
            # once. Both dimensions still retain their evidence and scores.
            parts = {proof['part'] for proof in row['evidence'] if proof.get('reason') == 'missing_part'}
            stair_endpoints = [segment[key] for proof in row['evidence'] if proof.get('kind') == 'stair_segments'
                               for segment in proof['failed_segments'] for key in ('start', 'end')]
            blocker = next((other for other in finding_rows if other['severity'] == 'blocker' and
                row['id'] in other['related_items'] and (
                    other['target'].get('part') in parts or other['target'].get('position') in stair_endpoints)), None)
            if blocker:
                blocker.setdefault('related_evidence', {})[row['id']] = row['evidence']
                continue
        primary.append(row)
    finding_rows = sorted(primary, key=lambda row: (SEVERITY[row['severity']], row['id']))
    for row in finding_rows:
        row['binding'] = binding
    priorities = []
    for row in finding_rows[:3]:
        if isinstance(row['evidence'], list) and any(item.get('method') and item.get('family_fits')
                                                     for item in row['evidence']):
            row = dict(row, evidence=[dict(method=item['method'], pointer=item['pointer'])
                                     if item.get('family_fits') else item for item in row['evidence']])
        priorities.append(row)
    summary = dict(gate=gate, priority_issues=priorities, dimensions={
        key: {field: value[field] for field in ('status', 'score', 'interval', 'coverage')}
        for key, value in dimensions.items()})
    if review is None and missing_review is None and any(row['views'] and row['status'] == 'pending'
        for rows in weighted.values() for row in rows):
        missing_review = dict(status='pending', reason='请提供当前制作版的实际审阅绑定。')
    return dict(binding=binding, dimensions=dimensions, issues=finding_rows, activities=activities,
                summary=summary, evidence=evidence, review=review.get('binding') if review else None,
                review_gap=missing_review, checklist_changes=quality.get('changes', []),
                technical_status=code or ('validated' if validation else 'pending'),
                feedback_mode='opt_in', approval_created=False)


def from_model(model, *, validation=None, review=None, missing_review=None):
    binding = model.architecture
    code, conflicts = None, []
    if validation is None:
        from nbt_composition.working_model import ModelConflict
        try:
            if model.phase == 'opened' and not model.context.get('require_routes'):
                model._routes(model.model)
            validation = model.validate()
        except ModelConflict as error:
            if error.code not in BLOCKING_CODES:
                raise
            code, conflicts = error.code, error.conflicts
            from nbt_building.plan import check_model
            validation = dict(architecture=check_model(model, binding))
    from nbt_building.plan import resolve
    from nbt_project.prompts import relative
    return assess(resolve(binding['plan']), binding['sha256'], model.model.fingerprint(),
                  source=relative(model.workspace, model.source) if model.source else None,
                  source_sha256=model.source_sha256, validation=validation, conflicts=conflicts, code=code,
                  volume=model.model, review=review, missing_review=missing_review, style_geometry=(model, binding))
