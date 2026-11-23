"""Versioned predicates over a scene's compiled positions and exact contact."""

from copy import deepcopy


class SceneCheckError(ValueError):
    def __init__(self, code, message, conflicts, **evidence):
        super().__init__(message)
        self.fields = dict(code=code, conflicts=conflicts, **evidence)


def scene_error_fields(error):
    from nbt_composition.scene_interfaces import InterfaceError

    if isinstance(error, SceneCheckError):
        return error.fields
    if isinstance(error, InterfaceError):
        return dict(code=error.code, conflicts=error.conflicts)
    return {}


def locks_by_id(graph):
    locks = graph.get('relation_locks', [])
    indexed = {lock['id']: lock for lock in locks}
    if len(indexed) != len(locks):
        raise ValueError('对象图关系锁ID重复')
    return indexed


def edit_locks(graph, additions, releases):
    locks = locks_by_id(graph)
    if len(set(releases)) != len(releases) or set(releases) - locks.keys():
        raise ValueError('解除的关系锁缺失或重复')
    for lock in additions:
        if lock['id'] in locks:
            raise ValueError('新增的关系锁ID已存在：' + lock['id'])
        locks[lock['id']] = deepcopy(lock)
    for identifier in releases:
        del locks[identifier]
    if locks:
        graph['relation_locks'] = list(locks.values())
    elif releases:
        graph.pop('relation_locks', None)


def check_lock_transition(before, after, releases):
    old, new = locks_by_id(before), locks_by_id(after)
    removed = sorted(old.keys() - new.keys())
    changed = sorted(key for key in old.keys() & new.keys() if old[key] != new[key])
    if sorted(releases) != removed or changed:
        raise SceneCheckError(
            'SCENE_LOCK_TRANSITION', '续版须保留原关系锁定义，并明确列出要解除的锁',
            [dict(removed_locks=removed, changed_locks=changed, release_locks=releases)])


def check_locks(locks, objects, geometry, *, checkpoint=None, preview=None):
    from nbt_composition.scene_interfaces import FACES, facing_cells, interface_contact
    from nbt_composition.object_scene import halfcells

    completed = {node['id']: node for node in objects}
    checks = []
    for lock in locks.values():
        if checkpoint:
            checkpoint('relation_locks')
        name = lock['object']
        node = completed.get(name)
        row = dict(lock_id=lock['id'], kind=lock['kind'], object=name,
                   status='failed', coordinate_space='scene')
        checks.append(row)
        if lock['kind'] == 'fixed_position':
            interface = lock.get('interface')
            row.update(expected_half=lock['position_half'], interface=interface)
            if node is None:
                row['reason'] = 'object_missing'
                continue
            if interface:
                surface = node['interfaces'].get(interface)
                if surface is None:
                    row['reason'] = 'interface_missing'
                    continue
                axis, _ = FACES[surface['face']]
                position = list(surface['lo_half'])
                position[axis] = surface['plane_half']
            else:
                position = [2 * value for value in node['bounds']['lo']]
            row['actual_half'] = position
            if position == lock['position_half']:
                row['status'] = 'passed'
            else:
                row['reason'] = 'position_changed'
            continue

        target = lock['target']
        row['target'] = target
        if name == target['object']:
            raise ValueError('关系锁不能要求对象与自身接口接合：' + lock['id'])
        owner = completed.get(target['object'])
        if node is None or owner is None:
            row['reason'] = 'object_missing'
            continue
        surface = owner['interfaces'].get(target['interface'])
        if surface is None:
            row['reason'] = 'interface_missing'
            continue
        row.update(face=surface['face'], plane_half=surface['plane_half'],
                   surface_lo_half=surface['lo_half'], surface_hi_half=surface['hi_half'])
        current = geometry[name]
        try:
            if current['cells'] is None:
                current['cells'] = halfcells(current['voxels'], name)
        except SceneCheckError as error:
            row.update(status='unknown', reason='unsupported_shape',
                       unknown_shapes=error.fields['conflicts'])
            continue
        cells = current['cells']
        row['contact_face_count'] = len(cells & facing_cells(surface))
        if interface_contact(cells, surface):
            row['status'] = 'passed'
        else:
            row['reason'] = 'contact_missing'

    if checkpoint:
        checkpoint('relation_locks')
    failures = [row for row in checks if row['status'] != 'passed']
    if not failures:
        return checks

    unknown = any(row['status'] == 'unknown' for row in failures)
    evidence = {}
    if preview is not None:
        evidence['preview'] = preview
        if not unknown:
            # Update has already checked every mandatory condition on the one
            # deterministically compiled candidate. Removing locks does not
            # change geometry. Check the singleton and its sole proper subset.
            singleton = [failures[0]['lock_id']]
            passed = {row['lock_id']: row['status'] == 'passed' for row in checks}
            subsets = [singleton, []]
            consistency = [dict(lock_ids=subset, consistent=all(passed[key] for key in subset)) for subset in subsets]
            if [row['consistent'] for row in consistency] == [False, True]:
                evidence['conflict_proof'] = dict(
                    status='verified_inclusion_minimal', scope='deterministic_candidate',
                    lock_ids=singleton, checks=consistency)
    raise SceneCheckError(
        'SCENE_RELATION_UNKNOWN' if unknown else 'SCENE_RELATION_LOCK_CONFLICT',
        '对象图关系锁无法验证' if unknown else '对象图违反关系锁：' + failures[0]['lock_id'],
        failures, **evidence)
