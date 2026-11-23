"""Bind declared design intent, ordered activities and review locations to geometry."""
import math


def validate_intent(plan, parts):
    spaces = {row['id']: row for row in plan['spaces']}
    views = {row['id'] for row in plan['views']}
    locations = {row['id'] for row in plan.get('review_locations', [])}
    components = {row['id'] for row in plan['parts']}
    for field in ('requirements', 'activities', 'review_locations'):
        rows = plan.get(field, [])
        if len({row['id'] for row in rows}) != len(rows):
            raise ValueError('建筑设计记录ID重复：' + field)
    for requirement in plan.get('requirements', []):
        references = (
            ('spaces', set(spaces)), ('parts', parts),
            ('review_locations', locations),
        )
        if not any(requirement.get(key) for key, _ in references):
            raise ValueError('需求需要关联空间、构件或审阅位置：' + requirement['id'])
        for key, allowed in references:
            values = requirement.get(key, [])
            if len(set(values)) != len(values) or not set(values) <= allowed:
                raise ValueError('需求引用不存在或重复：' + requirement['id'])
    for activity in plan.get('activities', []):
        for stop in activity['stops']:
            room = spaces.get(stop['space'])
            if room is None:
                raise ValueError('活动引用的空间不存在：' + activity['id'])
            if any(not room['lo'][i] <= stop['feet'][i] < room['hi'][i] + 1 for i in range(3)):
                raise ValueError('活动脚位超出所声明空间：' + activity['id'])
            face = stop.get('use_face')
            if face and face['part'] not in components:
                raise ValueError('活动操作面引用了不存在的普通构件：' + face['part'])
    for location in plan.get('review_locations', []):
        selected = location['views']
        if len(set(selected)) != len(selected) or not set(selected) <= views:
            raise ValueError('审阅位置引用的机位不存在或重复：' + location['id'])
        if any(not 0 <= location['position'][i] < plan['size'][i] for i in range(3)):
            raise ValueError('审阅位置超出完整画布：' + location['id'])


def check_use_face(model, binding, space, stop):
    """Check a horizontal approach to the actual, transformed working face."""
    from nbt_building.plan import surface
    from nbt_composition.scene_interfaces import FACES
    spec, feet = stop['use_face'], stop['feet']
    result = dict(**spec, feet=feet, passed=False)
    if not space.standing(feet):
        return dict(result, reason='invalid_standing_pose')
    try:
        contact = surface(model, binding, spec)
    except ValueError as error:
        return dict(result, reason='missing_or_unverified_interface', detail=str(error),
                    interface_code=getattr(error, 'code', None))
    axis, sign = FACES[contact['face']]
    if axis == 1:
        return dict(result, reason='horizontal_approach_requires_vertical_face')
    probe = [feet[0], feet[1] + spec['height'], feet[2]]
    plane = contact['plane_half'] / 2
    distance = (feet[axis] - plane) * sign
    result.update(face=contact['face'], distance=distance, plane=plane)
    if distance <= 0:
        return dict(result, reason='wrong_side')
    if distance > spec['max_distance']:
        return dict(result, reason='too_far')
    # Choose the half-cell at the operator's lateral position and working height.
    cell = [math.floor(2 * value) for value in probe]
    cell[axis] = contact['plane_half'] - int(sign > 0)
    if cell not in contact['faces_half']:
        return dict(result, reason='outside_working_face')
    lo = [value / 2 for value in cell]
    hi = [value + .5 for value in lo]
    lo[axis], hi[axis] = sorted((feet[axis], plane))
    if not space.clear_box(lo, hi):
        return dict(result, reason='approach_obstructed')
    return dict(result, passed=True, face_cell_half=cell)


def check_intent(model, binding, plan, space):
    from nbt_building.plan import actual_part
    from nbt_collision import check_routes
    checks = []
    for requirement in plan.get('requirements', []):
        missing = []
        for name in requirement.get('parts', []):
            try:
                _, positions = actual_part(model, binding, name)
                if not positions:
                    missing.append(name)
            except ValueError:
                missing.append(name)
        checks.append(dict(
            id=requirement['id'], kind='requirement_targets', passed=not missing,
            missing_parts=missing, spaces=requirement.get('spaces', []),
            review_locations=requirement.get('review_locations', []),
            scope='declared_references_and_part_presence', meaning='requires_visual_review',
        ))
    for activity in plan.get('activities', []):
        segments = []
        for index, (start, end) in enumerate(zip(activity['stops'], activity['stops'][1:])):
            report = check_routes(model.model, start['feet'], {end['space']: end['feet']})
            segments.append(dict(index=index, start=start, end=end, passed=report['passed'], report=report))
        faces = [dict(stop_index=i, **check_use_face(model, binding, space, stop))
                 for i, stop in enumerate(activity['stops']) if 'use_face' in stop]
        checks.append(dict(
            id=activity['id'], kind='activity_routes', actor=activity['actor'],
            passed=all(segment['passed'] for segment in segments) and all(face['passed'] for face in faces),
            segments=segments, use_faces=faces,
            scope='ordered_player_routes', cargo_clearance='not_checked',
            use_face_scope='horizontal_half_cell_clearance_to_named_interface',
            functional_relationships='requires_design_review',
        ))
    return checks


def visible_location(model, eye, target, look_at, fov):
    """Sample one authored target point, including targets in doorway air."""
    from nbt_collision import collision_cells
    from nbt_registry import effective
    target_cell = tuple(math.floor(value) for value in target)
    target_state = model.get(target_cell)
    occupied, reason = collision_cells(target_state)
    target_inside = not reason and tuple(math.floor(2*(value-cell)) for value,cell in zip(target,target_cell)) in occupied
    evidence = dict(target_cell=list(target_cell), target_state=target_state,
                    target_inside_solid=target_inside, target_shape_uncertain=bool(reason))
    delta = [target[i] - eye[i] for i in range(3)]
    forward = [look_at[i] - eye[i] for i in range(3)]
    distance = math.sqrt(sum(value * value for value in delta))
    length = math.sqrt(sum(value * value for value in forward))
    framed = bool(distance and length and sum(delta[i] * forward[i] for i in range(3)) /
                  (distance * length) >= math.cos(math.radians(fov / 2)))
    if not framed:
        return dict(passed=False, framed=False, uncertain=False, blocker=None,
                    failure='target_outside_view', **evidence)
    uncertain = False
    steps = max(1, math.ceil(distance * 8))
    for step in range(1, steps):
        point = [eye[i] + delta[i] * step / steps for i in range(3)]
        position = tuple(math.floor(value) for value in point)
        value = model.get(position)
        name, _ = effective(value)
        if name in ('minecraft:air', 'minecraft:cave_air', 'minecraft:void_air'):
            continue
        if name.endswith(('_glass', '_glass_pane')) or name in ('minecraft:glass', 'minecraft:glass_pane'):
            continue
        occupied, reason = collision_cells(value)
        if reason:
            uncertain = True
            continue
        local = tuple(math.floor(2 * (point[i] - position[i])) for i in range(3))
        if local in occupied:
            failure = 'target_inside_solid' if target_inside and position == target_cell else 'occluded'
            return dict(passed=False, framed=True, uncertain=uncertain, blocker=list(position),
                        blocker_state=value, failure=failure, **evidence)
    return dict(passed=not uncertain, framed=True, uncertain=uncertain, blocker=None,
                failure='uncertain_collision' if uncertain else None, **evidence)


def prepare_locations(model, plan, cameras, view_checks):
    camera_map = {row['id']: row for row in cameras}
    checks = {row['id']: row for row in view_checks}
    result = []
    for location in plan.get('review_locations', []):
        candidates = []
        for identifier in location['views']:
            camera = camera_map[identifier]
            visibility = visible_location(model, camera['eye'], location['position'], camera['target'], camera['fov'])
            candidates.append(dict(view=identifier, passed=checks[identifier]['passed'] and visibility['passed'], visibility=visibility))
        result.append(dict(
            **location, candidates=candidates, passed=any(row['passed'] for row in candidates),
            scope='sampled_point_visibility', visual_status='awaiting_actual_observation',
        ))
    return result


def observed_locations(pack, observations):
    locations = {row['id']: row for row in pack.get('review_locations', [])}
    covered, manual = set(), []
    for observation in observations:
        verified = observation.get('locations', [])
        manual_ids = observation.get('manual_locations', [])
        identifiers = verified + manual_ids
        if len(set(identifiers)) != len(identifiers):
            raise ValueError('同一图像的审阅位置重复')
        image = observation['image']
        for identifier in identifiers:
            location = locations.get(identifier)
            if location is None or image not in location['views']:
                raise ValueError(f'图像 {image} 未绑定审阅位置 {identifier}')
            candidate = next(row for row in location['candidates'] if row['view'] == image)
            failure = candidate.get('visibility', {}).get('failure')
            if identifier in manual_ids:
                if candidate['passed'] or failure != 'uncertain_collision':
                    raise ValueError(f'位置 {identifier} 仅在碰撞取景不确定时可用 manual_locations')
                manual.append(dict(id=identifier, image=image, auto_framing=failure))
            elif not candidate['passed']:
                hint = '，实际看清后可用 manual_locations 登记' if failure == 'uncertain_collision' else '，请补拍'
                raise ValueError(f'图像 {image} 的位置 {identifier} 尚未通过取景检查{hint}')
            covered.add(identifier)
    return sorted(covered), sorted(set(locations) - covered), manual
