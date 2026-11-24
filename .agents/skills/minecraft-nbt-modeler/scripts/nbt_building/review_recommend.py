"""Find bounded, source-bound supplemental cameras for declared review locations."""
from collections import Counter, deque
from functools import lru_cache
from hashlib import sha256
from itertools import product
import json
from math import dist
from time import perf_counter

from nbt_building.intent import observed_locations, visible_location
from nbt_building.plan import resolve
from nbt_building.review import camera_eye, load_observations, load_pack_model, view_geometry, visibility
from nbt_collision import _Space
from nbt_project.prompts import inside, relative


# Probe nearby support heights and a horizontal radius of 2.5 blocks.
OFFSETS = sorted(
    ((x, y, z) for x, y, z in product(range(-5, 6), range(-2, 3), range(-5, 6))
     if x*x + z*z <= 25),
    key=lambda p: (sum(value*value for value in p), abs(p[1]), p),
)
MAX_ANCHORS = 8
MIN_DISTANCE, PREFERRED_DISTANCE, MAX_DISTANCE = 1.5, 4, 16


def pose_candidates(view, old, locations, stops):
    anchors = []
    if old and old['feet']:
        anchors.append(old['feet'])
    if 'feet' in view:
        anchors.append(view['feet'])
    for location in locations:
        target = location['position']
        nearby = sorted((feet for feet in stops if dist(feet, target) <= 12), key=lambda feet: dist(feet, target))
        anchors.extend(nearby[:2])
        anchors.append((target[0], target[1] - 1.62, target[2]))
    centers = list(dict.fromkeys(tuple(round(2*value) for value in feet) for feet in anchors))[:MAX_ANCHORS]
    seen = set()
    for offset in OFFSETS:
        for center in centers:
            feet = tuple((value + delta) / 2 for value, delta in zip(center, offset))
            if feet not in seen:
                seen.add(feet)
                yield feet


def camera_key(eye, target, fov):
    length = dist(eye, target)
    direction = tuple(round((a-b) / length, 6) for a, b in zip(target, eye))
    return tuple(round(v, 6) for v in eye), direction, fov


def camera_candidates(view, old, locations, stops, default_target, standing, prior, stats):
    aims = (old['look_at'] if old else default_target, *(row['position'] for row in locations))
    fov = view.get('fov', 60)
    seen = set()
    for feet in pose_candidates(view, old, locations, stops):
        stats['pose_probes'] += 1
        if not standing(feet):
            continue
        stats['standable_poses'] += 1
        eye = camera_eye({'feet': feet})
        for target in aims:
            if not MIN_DISTANCE <= dist(eye, target) <= MAX_DISTANCE:
                continue
            key = camera_key(eye, target, fov)
            if key in prior or key in seen:
                stats['duplicate_candidates'] += 1
                continue
            seen.add(key)
            yield key, feet, eye, target


def estimate(model, view, locations, points, eye, target, diagnostics):
    fov = view.get('fov', 60)
    clear = []
    for row in locations:
        identifier = row['id']
        distance = dist(eye, row['position'])
        stats, blockers = diagnostics[identifier]
        if not MIN_DISTANCE <= distance <= MAX_DISTANCE:
            stats['outside_review_distance'] += 1
            continue
        ray = visible_location(model, eye, row['position'], target, fov)
        if ray['passed'] and not ray['target_shape_uncertain']:
            clear.append((identifier, abs(distance - PREFERRED_DISTANCE)))
            continue
        stats[ray['failure'] or 'uncertain_collision'] += 1
        if ray['blocker'] is not None:
            blockers[tuple(ray['blocker']), ray['blocker_state']] += 1
    if not clear:
        return None
    seen = visibility(model, eye, points, target, fov)
    if seen['visible_fraction'] < view.get('minimum_visible', .2):
        for identifier, _ in clear:
            stats, blockers = diagnostics[identifier]
            stats['view_visibility_below_minimum'] += 1
            if seen['uncertain_fraction']:
                stats['view_uncertain_collision'] += 1
            for blocker in seen['blockers']:
                pos = tuple(blocker['pos'])
                blockers[pos, model.get(pos)] += blocker['rays']
        return None
    return dict(clear), seen['visible_fraction']


def select(candidates, limit):
    covered, used_views, used_cameras, used_feet, shots = set(), set(), set(), set(), []
    for _ in range(limit):
        ranked = []
        for key, view, eye, locations, visible_fraction in candidates:
            fresh = set(locations) - covered
            if not fresh or view['id'] in used_views or key in used_cameras:
                continue
            score = (len(fresh), tuple(view['feet']) not in used_feet,
                     -sum(locations[name] for name in sorted(fresh)), visible_fraction)
            ranked.append((score, key, view, eye, locations, visible_fraction, fresh))
        if not ranked:
            break
        _, key, view, eye, locations, visible_fraction, fresh = max(ranked, key=lambda row: row[0])
        shots.append(dict(view=view, eye=eye, direction=list(key[1]),
                          estimated_locations=sorted(locations), newly_estimated_locations=sorted(fresh),
                          view_visible_fraction=visible_fraction))
        covered.update(fresh)
        used_views.add(view['id'])
        used_cameras.add(key)
        used_feet.add(tuple(view['feet']))
    return shots, covered


def recommend(workspace, request):
    started = perf_counter()
    file, pack, model = load_pack_model(workspace, request)
    plan = resolve(model.architecture['plan'])
    locations = {row['id']: row for row in plan.get('review_locations', [])}
    requested = request.get('locations', list(locations))
    if len(set(requested)) != len(requested) or not set(requested) <= locations.keys():
        raise ValueError('补拍位置须引用不同的原方案审阅位置 ID')
    old_locations = {row['id']: row for row in pack['review_locations']}
    observed = []
    if 'notes_sha256' in request:
        notes = load_observations(workspace, file, pack, request['pack_sha256'], request['notes_sha256'])
        observed, _, _ = observed_locations(pack, notes['observations'])
    pending = {name: locations[name] for name in sorted(set(requested) - set(observed))}
    output = inside(workspace, request['output'])
    if output.exists() or output.is_relative_to(model.source.parent.parent):
        raise ValueError('补拍须使用全新审阅目录，不能写入已发布制作版目录')

    old_views = {view['id']: view for view in pack['views']}
    raw_cameras = (file.parent / pack['cameras']).read_bytes()
    if sha256(raw_cameras).hexdigest() != pack['cameras_sha256']:
        raise ValueError('原审阅机位已变化')
    prior = {camera_key(row['eye'], row['target'], row.get('fov', 60)) for row in json.loads(raw_cameras)}
    stops = [stop['feet'] for activity in plan.get('activities', []) for stop in activity['stops']]
    stops.extend([plan['context']['start'], *plan['context']['targets'].values()])
    stats = Counter(pose_probes=0, standable_poses=0, duplicate_candidates=0, evaluated_candidates=0)
    diagnostics = {name: (Counter(), Counter()) for name in pending}
    max_images = request.get('max_images', 3)
    max_candidates = request.get('max_candidates', 128)
    queues = deque()
    if pending:
        space = _Space(model.model)
        standing = lru_cache(maxsize=None)(space.standing)
        for view in plan['views']:
            targets = [row for row in pending.values() if view['id'] in row['views']]
            if targets:
                points, default_target = view_geometry(model, model.architecture, view)
                candidates = camera_candidates(view, old_views.get(view['id']), targets, stops,
                                               default_target, standing, prior, stats)
                queues.append((view, targets, points, candidates))

    eligible = []
    while queues and stats['evaluated_candidates'] < max_candidates:
        view, targets, points, candidates = queues.popleft()
        pose = next(candidates, None)
        if pose is None:
            continue
        queues.append((view, targets, points, candidates))
        key, feet, eye, target = pose
        stats['evaluated_candidates'] += 1
        coverage = estimate(model.model, view, targets, points, eye, target, diagnostics)
        if coverage:
            override = dict(view, feet=list(feet), target=target)
            override.pop('eye', None)
            eligible.append((key, override, eye, *coverage))

    shots, covered = select(eligible, max_images)
    budget_reached = stats['evaluated_candidates'] == max_candidates
    eligible_locations = {name for _, _, _, clear, _ in eligible for name in clear}
    missing = []
    for name, row in pending.items():
        if name in covered:
            continue
        failures, blockers = diagnostics[name]
        if name in eligible_locations:
            reason = 'view_id_or_image_budget'
        elif failures:
            reason = failures.most_common(1)[0][0]
        elif budget_reached:
            reason = 'candidate_budget_reached'
        else:
            reason = 'no_distinct_legal_candidate'
        missing.append(dict(id=name, position=row['position'], views=row['views'], reason=reason,
                            failed_tests=dict(failures),
                            blockers=[dict(pos=list(pos), state=state, hits=count)
                                      for (pos, state), count in blockers.most_common(4)]))
    overrides = [row['view'] for row in shots]
    source = dict(source=pack['source'], source_sha256=pack['source_sha256'])
    next_step = None
    if overrides:
        next_step = dict(action='review-prepare', request=dict(
            **source, output=relative(workspace, output), view_overrides=overrides,
            view_ids=[view['id'] for view in overrides]))
    return dict(**source, plan_sha256=pack['plan_sha256'], model_sha256=pack['model_sha256'],
                original_review={key: request[key] for key in ('pack', 'pack_sha256', 'notes_sha256') if key in request},
                prior_location_estimates=[old_locations[name] for name in pending if name in old_locations],
                already_observed_locations=sorted(set(observed) & set(requested)),
                estimated_covered_locations=sorted(covered), pending_locations=missing, recommendations=shots,
                search=dict(**stats, max_candidates=max_candidates, max_images=max_images,
                            candidate_budget_reached=budget_reached, eligible_candidates=len(eligible),
                            elapsed_ms=round((perf_counter()-started)*1000, 1)),
                visual_status='awaiting_actual_images_and_observations', approval_created=False, next=next_step)
