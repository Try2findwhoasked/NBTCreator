"""Bind checklist observations and comparisons to recorded review evidence."""
import json

from nbt_building.plan import fingerprint, resolve
from nbt_building.quality import BLOCKING_CODES, SCORES, from_model
from nbt_building.quality_plan import DIMENSIONS, items
from nbt_history import file_hash
from nbt_prompts import inside, relative


def record_quality(workspace, model, pack, request, manifest_file, manifest_sha256):
    scores = request.get('quality_observations', [])
    if not scores:
        return {}
    from nbt_review.blind_review import _render

    # Use the same render verification as anonymous A/B review.
    verified = _render(workspace, dict(manifest=str(manifest_file), sha256=manifest_sha256))
    if verified['report']['source_sha256'] != model.source_sha256:
        raise ValueError('质量观察的实际渲染源不符')
    settings = ('camera', 'cuts', 'layer', 'lighting', 'lighting_options', 'quality', 'pixel_ratio',
                'width', 'height', 'registry_sha256', 'rendering')
    profiles = {row['meta']['id']: {key: row['meta'].get(key) for key in settings} for row in verified['images']}
    plan = resolve(model.architecture['plan'])
    checklist = items(plan)
    observations = {row['image']: row for row in request['observations']}
    data = {}
    for row in scores:
        key, grade = row['item'], row['grade']
        spec = checklist.get(key)
        if not spec or spec.get('not_applicable') or not spec.get('views') or key in data:
            raise ValueError('质量观察项不存在、重复、未登记机位或不适用：' + key)
        observed = row['images']
        if set(observed) - set(spec['views']) or len(set(observed)) != len(observed) or set(observed) - observations.keys():
            raise ValueError('评分须使用已看且属于该项的登记机位：' + key)
        if grade not in SCORES.get(spec['dimension'], range(5)) or not row['observer'].strip() or not row['note'].strip():
            raise ValueError('档位不适用或观察缺少依据：' + key)
        if grade < 4 and not row.get('suggestion', '').strip():
            raise ValueError('待修质量项须记录可执行建议：' + key)
        location = spec.get('location')
        if location and any(location['id'] not in observations[view].get('locations', []) +
                            observations[view].get('manual_locations', []) for view in observed):
            raise ValueError('质量观察须实际核对所引用的审阅位置：' + key)
        data[key] = dict(row, conditions_sha256=fingerprint(spec),
                         render_conditions={view: profiles[view] for view in observed})
    return dict(quality_observations=data, quality_checklist_sha256=fingerprint(checklist),
                quality_render=dict(path=relative(workspace, manifest_file), sha256=manifest_sha256,
                    snapshot=relative(workspace, verified['manifest'].parent / verified['report']['snapshot_file']),
                    snapshot_sha256=verified['report']['snapshot_sha256'],
                    cameras_sha256=pack['cameras_sha256'], geometry_sha256=model.model.fingerprint()))


def read_review(workspace, model, request):
    if not request:
        return None, None
    from nbt_building.review import load_pack
    try:
        pack_file, pack = load_pack(workspace, request)
        if inside(workspace, pack['source']) != model.source or pack['source_sha256'] != model.source_sha256:
            raise ValueError('审阅属于其他制作版')
        file = inside(workspace, pack_file.parent / 'review-notes.json')
        with file.open('rb') as stream:
            raw = stream.read(8 * 1024 * 1024 + 1)
        if len(raw) > 8 * 1024 * 1024:
            raise ValueError('审阅修订超过上限')
        from hashlib import sha256
        if sha256(raw).hexdigest() != request['notes_sha256']:
            raise ValueError('指定审阅修订已过期')
        notes = json.loads(raw)
        history = inside(workspace, file.parent / 'observations' / f"{notes['revision']}-{fingerprint(notes)}.json")
        if file_hash(history) != request['notes_sha256'] or notes['pack_sha256'] != request['pack_sha256']:
            raise ValueError('指定审阅修订与登记不一致')
        render = notes.get('quality_render')
        if not render:
            return None, dict(status='pending', reason='审阅尚无量表观察。')
        if (render['cameras_sha256'] != pack['cameras_sha256'] or
                render['geometry_sha256'] != model.model.fingerprint() or
                file_hash(inside(workspace, render['path'])) != render['sha256'] or
                file_hash(inside(workspace, render['snapshot'])) != render['snapshot_sha256']):
            raise ValueError('渲染清单或快照已变化')
        plan = resolve(model.architecture['plan'])
        checklist = items(plan)
        if fingerprint(checklist) != notes['quality_checklist_sha256']:
            raise ValueError('审阅量表或评估清单已变化')
        valid, stale = {}, []
        for view, info in notes['images'].items():
            try:
                if (file_hash(inside(workspace, info['path'])) == info['sha256'] and
                        file_hash(inside(workspace, info['metadata'])) == info['metadata_sha256']):
                    valid[view] = info
                    continue
            except (OSError, ValueError):
                pass
            stale.append(view)
        binding = dict(revision=notes['revision'], path=relative(workspace, file),
                       **request, render=render, overridden_views=pack.get('overridden_views', []))
        measured, missing = {}, {}
        for key, row in notes['quality_observations'].items():
            spec = checklist[key]
            views = spec.get('views', [])
            absent = sorted(set(views) - (set(row['images']) & valid.keys()))
            if absent:
                missing[key] = absent
                continue
            measured[key] = dict(row, images={name: valid[name] for name in views}, binding=binding,
                                 pointer='/quality_observations/' + key)
        if file_hash(file) != request['notes_sha256']:
            raise ValueError('审阅修订在读取期间变化')
        gap = dict(status='partial', stale_views=stale, missing_items=missing) if stale or missing else None
        return dict(binding=binding, items=measured, missing=missing), gap
    except (KeyError, OSError, TypeError, ValueError) as error:
        return None, dict(status='stale', reason=str(error))


def check(workspace, request):
    from nbt_building.review import load_model
    model = load_model(workspace, request)
    evidence, gap = read_review(workspace, model, request.get('review'))
    return from_model(model, review=evidence, missing_review=gap)


def render_conditions(item):
    return [row['render_conditions'] for row in item['evidence'] if row.get('render_conditions')]


def comparisons(previous, current):
    findings, dimensions = {}, {}
    old_binding, new_binding = previous['binding'], current['binding']
    context = {key: dict(previous=old_binding[key], current=new_binding[key])
               for key in ('rubric', 'checklist_revision', 'checklist_sha256', 'stage', 'comparison_scope', 'route_scope_sha256')
               if old_binding[key] != new_binding[key]}
    same_rubric = not {'rubric', 'comparison_scope'} & context.keys()
    items_by_side = []
    eligible_items = set()
    for report in (previous, current):
        items_by_side.append({row['id']: row for result in report['dimensions'].values() for row in result['items']})
    old_items, new_items = items_by_side
    for dimension in DIMENSIONS:
        a, b = (report['dimensions'][dimension] for report in (previous, current))
        before, after = ({row['id']: row for row in result['items']} for result in (a, b))
        eligible, excluded = {}, {}
        for key in sorted(before.keys() | after.keys()):
            old, new = before.get(key), after.get(key)
            if not old or not new:
                excluded[key] = 'scope_changed'
            elif (not same_rubric or old['conditions_sha256'] != new['conditions_sha256'] or
                  any(old[k] != new[k] for k in ('weight_numerator', 'weight_denominator'))):
                excluded[key] = 'conditions_changed'
            elif old['status'] == new['status'] == 'not_applicable':
                continue
            elif old['status'] != 'measured' or new['status'] != 'measured':
                excluded[key] = 'requires_evidence'
            elif render_conditions(old) != render_conditions(new):
                excluded[key] = 'render_conditions_changed'
            else:
                eligible[key] = dict(previous=old['grade'], current=new['grade'], delta=25 * (new['grade'] - old['grade']))
                eligible_items.add(key)
        delta = None
        if eligible and not excluded and a['score'] is not None and b['score'] is not None:
            delta = round(b['score'] - a['score'], 2)
        dimensions[dimension] = dict(delta=delta, comparable_items=eligible, excluded_items=excluded)
    prior, now = ({row['id']: row for row in report['issues']} for report in (previous, current))
    for key in sorted(prior.keys() | now.keys()):
        before, after = prior.get(key), now.get(key)
        if not before:
            status = 'new'
        elif after:
            same_target = key not in old_items or (key in new_items and
                old_items[key]['conditions_sha256'] == new_items[key]['conditions_sha256'] and
                render_conditions(old_items[key]) == render_conditions(new_items[key]))
            status = 'persistent' if same_rubric and same_target else 'needs_review'
        elif key in eligible_items:
            status = 'resolved_retested'
        elif key.startswith('activity.'):
            name = before['target'].get('activity')
            old_activity = previous['activities'].get(name, {})
            new_activity = current['activities'].get(name, {})
            old_conditions = old_activity.get('conditions_sha256')
            same_activity = old_conditions and old_conditions == new_activity.get('conditions_sha256')
            if not old_conditions:
                criterion = 'circulation.' + name + '.clearance'
                old, new = old_items.get(criterion), new_items.get(criterion)
                same_activity = old and new and old['conditions_sha256'] == new['conditions_sha256']
            if same_rubric and same_activity and new_activity.get('status') == 'pass':
                status = 'resolved_retested'
            else:
                status = 'needs_review'
        elif key.startswith('host.') and same_rubric and 'route_scope_sha256' not in context:
            from nbt_building.quality import route_state
            name = key.split('.')[1]
            report = current['evidence']['host_routes'] if name == 'routes' else next(
                (row['report'] for row in current['evidence']['host_route_legs'] if row['name'] == name), None)
            status = 'resolved_retested' if report and route_state(report) == 'pass' else 'needs_review'
        else:
            status = 'needs_review'
        findings[key] = dict(id=key, status=status, previous=before, current=after)
    priority = {'new': 0, 'persistent': 1, 'resolved_retested': 2, 'needs_review': 3}
    findings = sorted(findings.values(), key=lambda row: (priority[row['status']], row['id']))
    return dict(bindings=dict(previous=old_binding, current=new_binding), binding_changes=context,
                changes=current['checklist_changes'], dimensions=dimensions, issues=findings,
                approval_created=False)


def compare(workspace, request):
    previous = request['previous']
    if 'report' in previous:
        from hashlib import sha256
        file = inside(workspace, previous['report'])
        with file.open('rb') as stream:
            raw = stream.read(16 * 1024 * 1024 + 1)
        if len(raw) > 16 * 1024 * 1024 or sha256(raw).hexdigest() != previous['report_sha256']:
            raise ValueError('建模失败回执已变化或过大')
        receipt = json.loads(raw)
        if receipt.get('ok') is not False or receipt.get('code') not in BLOCKING_CODES:
            raise ValueError('需提供含质量报告的建模失败回执')
        return comparisons(receipt['quality'], check(workspace, request))
    return comparisons(check(workspace, previous), check(workspace, request))
