"""Index current diagnostic evidence by issue identity rather than report revision."""

import hashlib
import json
import re


def load(path):
    with path.open('rb') as stream:
        raw = stream.read(32 * 1024 * 1024 + 1)
    if len(raw) > 32 * 1024 * 1024:
        raise ValueError('报告超过32MiB')
    report = json.loads(raw.decode('utf-8-sig'))
    if not isinstance(report, dict):
        raise ValueError('检查报告须为JSON对象')
    return report, dict(path=str(path.resolve()), sha256=hashlib.sha256(raw).hexdigest())


def summary(kind, report):
    issues = {}
    legacy_error = False

    if kind == 'model' and 'ok' not in report and isinstance(report.get('error'), str):
        legacy_error = True
        code, _, payload = report['error'].partition(': ')
        conflicts = []
        if re.fullmatch(r'[A-Z][A-Z_]+', code):
            try:
                rows = json.loads(payload)
                if isinstance(rows, list) and all(isinstance(row, dict) for row in rows):
                    conflicts = rows
            except ValueError:
                pass
        else:
            code = 'ARCHITECT_INVALID'
        report = dict(report, ok=False, code=code, conflicts=conflicts)

    def add(code, target, path, row, *, scope=None):
        key = (code, scope, target)
        if key not in issues:
            fields = ('reason','feet','pos','positions','bounds','part','interface','face','distance','stop_index',
                      'failed_samples','missing','missing_parts','severity','certainty','error','detail','title','state',
                      'coordinate_space','sampling','failures','eye','eye_cell','target_bounds',
                      'instance','object','unknown_shapes','missing_faces_half','violations','position','view','failure',
                      'blocker','blockers','blocker_state','target_cell','target_state','target_inside_solid')
            evidence = {field: row[field][:8] if isinstance(row[field], list) else row[field][:240]
                        if isinstance(row[field], str) else row[field] for field in fields if field in row}
            issues[key] = dict(code=code, scope=scope, target=target, evidence_pointer='/error' if legacy_error else path,
                               evidence=evidence, occurrences=0)
        issues[key]['occurrences'] += 1

    def routes(report, path, scope=None, code='ROUTE_FAILED'):
        for index, row in enumerate(report.get('unknown_shapes', [])):
            add('ROUTE_UNSUPPORTED_SHAPE', row['state'], f'{path}/unknown_shapes/{index}', row, scope=scope)
        for index, row in enumerate(report.get('targets', [])):
            if row.get('reachable') is False:
                add(code, row['name'], f'{path}/targets/{index}', row, scope=scope)
        if report.get('passed') is False and not any(row.get('reachable') is False for row in report.get('targets', [])):
            add(code, None, path, report, scope=scope)

    def checks(rows, path, default):
        for index, row in enumerate(rows):
            if row.get('passed') is True:
                continue
            pointer = f'{path}/{index}'
            identifier, check = row.get('id'), row.get('kind', default)
            scope = row.get('instance') or row.get('owner')
            target = '.'.join(str(row[key]) for key in ('object','interface') if row.get(key))
            target = target or identifier or row.get('name') or row.get('part')
            if check == 'activity_routes':
                for i, face in enumerate(row['use_faces']):
                    if not face['passed']:
                        add('USE_FACE_FAILED', f"{face['part']}.{face['interface']}",
                            f'{pointer}/use_faces/{i}', face, scope=identifier)
                for i, leg in enumerate(row['segments']):
                    if not leg['passed']:
                        routes(leg['report'], f'{pointer}/segments/{i}/report', identifier, 'ACTIVITY_ROUTE_FAILED')
            elif 'report' in row and 'targets' in row['report']:
                routes(row['report'], pointer + '/report', scope or target)
            else:
                add(check, target, pointer, row, scope=scope)

    review = None
    if kind == 'review':
        coverage = report.get('result', report)
        path = '/result' if 'result' in report else ''
        if 'coverage' in coverage:
            coverage, path = coverage['coverage'], path + '/coverage'
        if 'views' in coverage:
            views = {view['id']: (index, view) for index, view in enumerate(coverage['views'])}
            for key in ('views', 'review_locations'):
                for index, row in enumerate(coverage.get(key, [])):
                    if not row['passed']:
                        pointer = f'{path}/{key}/{index}'
                        candidates = [(i, candidate) for i, candidate in enumerate(row.get('candidates', []))
                                      if not candidate['passed']]
                        if candidates:
                            for i, candidate in candidates:
                                candidate_pointer = f'{pointer}/candidates/{i}/visibility'
                                evidence = dict(candidate['visibility'], view=candidate['view'], position=row.get('position'))
                                if not evidence.get('failure') and candidate['view'] in views:
                                    view_index, view = views[candidate['view']]
                                    evidence.update(view)
                                    evidence['blockers'] = view.get('visibility', {}).get('blockers', [])
                                    candidate_pointer = f'{path}/views/{view_index}'
                                add('REVIEW_FRAMING_FAILED', row['id'], candidate_pointer,
                                    evidence, scope=f"{key}/{candidate['view']}")
                        else:
                            evidence = dict(row)
                            if key == 'views':
                                evidence['blockers'] = row.get('visibility', {}).get('blockers', [])
                            add('REVIEW_FRAMING_FAILED', row['id'], pointer, evidence, scope=key)
            pending = [row['id'] for row in coverage['views']]
        elif 'observations' in coverage and 'images' in coverage:
            observed = {row['image'] for row in coverage['observations']}
            pending = sorted(coverage['images'].keys() - observed)
            for index, row in enumerate(coverage.get('issues', [])):
                add('NEEDS_REVIEW', row['id'], f'{path}/issues/{index}', row)
        else:
            raise ValueError('需要 review-pack 或 review-notes 记录')
        review = dict(pending_views=pending, delivery_summary=coverage.get('delivery_summary', []), evidence_pointer=path)
    elif kind == 'model':
        if report.get('ok') is False:
            code, conflicts = report['code'], report.get('conflicts', [])
            if code in ('DESIGN_INVALID', 'ASSEMBLY_INVALID') and conflicts:
                checks(conflicts, '/conflicts', code)
            elif conflicts:
                for index, row in enumerate(conflicts):
                    path = f'/conflicts/{index}'
                    data = row.get('report', row)
                    target = row.get('instance') or row.get('name') or row.get('owner')
                    if target and row.get('interface'):
                        target += '.'+row['interface']
                    if 'targets' in data:
                        routes(data, path + ('/report' if 'report' in row else ''), target, code)
                    else:
                        add(code, target, path, row)
            else:
                add(code, None, '', report)
        else:
            data, path = (report['result'], '/result') if 'result' in report else (report, '')
            for key in ('validation', 'checks'):
                if isinstance(data.get(key), dict):
                    data, path = data[key], f'{path}/{key}'
                    break
            if not any(key in data for key in ('whole_model', 'architecture', 'assembly', 'block_states')):
                raise ValueError('需要包含验证结果或结构化失败的建模回执')
            for key in ('assembly', 'architecture'):
                checks(data.get(key, {}).get('checks', []), f'{path}/{key}/checks', key)
            whole = data.get('whole_model')
            if isinstance(whole, dict):
                routes(whole.get('routes', {}), path + '/whole_model/routes')
                for index, row in enumerate(whole.get('route_legs', [])):
                    routes(row['report'], f'{path}/whole_model/route_legs/{index}/report', row['name'])
    else:
        from nbt_diagnostics import explain
        for row in explain(kind, report)['issues']:
            # These explanations derive from the raw record rather than one stable JSON field.
            add(row['code'], row['target'], '', row)
    return issues, review


def delta(kind, current, baseline=None):
    report, input_ref = load(current)
    issues, review = summary(kind, report)
    previous, baseline_ref = {}, None
    if baseline is not None:
        old_report, baseline_ref = load(baseline)
        previous, _ = summary(kind, old_report)
    new, ongoing = [], []
    for key, issue in issues.items():
        (ongoing if key in previous else new).append(issue)
    limit = 40
    return dict(schema_version=1, kind=kind, report=input_ref, baseline=baseline_ref,
                new=new[:limit], ongoing=ongoing[:limit], new_count=len(new), ongoing_count=len(ongoing),
                truncated=len(new)>limit or len(ongoing)>limit, review=review,
                report_reverified=False, approval_created=False)
