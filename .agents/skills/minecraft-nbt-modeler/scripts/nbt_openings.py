"""Declared rectangular apertures for newly authored standalone models, after a real seal check."""
from itertools import product
from nbt_model import AIR, AIR_NAMES


def _point(value):
    if not isinstance(value, (list, tuple)) or len(value)!=3 or any(type(n) is not int for n in value):
        raise ValueError('Opening bounds must be integer XYZ triples')
    return tuple(value)


def open_declared_openings(model, openings, wall_positions=None):
    """Preflight all apertures, then carve only them, preserving the accepted seal.

    lo/hi are inclusive and may cover a thick wall away from the model boundary.
    facing is the direction from interior towards exterior. Both adjacent faces
    that lie inside the model must have an air throat and non-air floor voxels.
    This does not certify collision support, minimum width or route reachability.
    wall_positions, when supplied, is the explicit mutable set from authoring.
    No files are read/written; no confirmation is created for existing assets.
    """
    before = model.fingerprint()
    seal = model.seal_record
    if model.stage!='sealed' or not seal or not seal.get('passed') or seal.get('geometry_sha256')!=before:
        raise ValueError('Check the unchanged closed master before carving declared openings')
    if not isinstance(openings, (list, tuple)) or not openings:
        raise ValueError('Declare at least one opening')
    if wall_positions is not None and (not isinstance(wall_positions, set) or any(not model.in_bounds(_point(p)) for p in wall_positions)):
        raise ValueError('wall_positions must be an explicit in-bounds set')
    directions = dict(north=(2,-1), south=(2,1), west=(0,-1), east=(0,1))
    ids, allowed, checked = set(), set(), []
    for item in openings:
        if not isinstance(item, dict) or set(item)!={'id','lo','hi','facing'}:
            raise ValueError('Opening fields: id, lo, hi, facing')
        name = item['id']
        if not isinstance(name,str) or not name.strip() or name in ids or not isinstance(item['facing'],str) or item['facing'] not in directions:
            raise ValueError('Opening needs a unique id and north/south/east/west facing')
        ids.add(name)
        lo, hi = _point(item['lo']), _point(item['hi'])
        if any(lo[i]>hi[i] for i in range(3)) or lo[1]<1 or not model.in_bounds(lo) or not model.in_bounds(hi):
            raise ValueError('Opening exceeds bounds or removes the base floor')
        positions = set(product(*(range(a,b+1) for a,b in zip(lo,hi))))
        if positions & allowed:
            raise ValueError('Opening declarations overlap')
        if not any(model.get(p) not in AIR_NAMES for p in positions):
            raise ValueError('Declared aperture contains no closed wall')
        for x,z in product(range(lo[0],hi[0]+1),range(lo[2],hi[2]+1)):
            if model.get((x,lo[1]-1,z)) in AIR_NAMES:
                raise ValueError('Missing floor voxel under aperture')
        axis, sign = directions[item['facing']]
        across = 2 if axis==0 else 0
        faces = []
        for role, coordinate in [('interior',lo[axis]-1 if sign>0 else hi[axis]+1),
                                 ('exterior',hi[axis]+1 if sign>0 else lo[axis]-1)]:
            if not 0<=coordinate<model.size[axis]:
                if role=='interior':
                    raise ValueError('Opening has no interior throat within the master')
                faces.append(dict(role=role,checked=False,reason='outside_model_bounds'))
                continue
            for cross in range(lo[across],hi[across]+1):
                floor=[0,lo[1]-1,0];floor[axis]=coordinate;floor[across]=cross
                if model.get(floor) in AIR_NAMES:
                    raise ValueError('Missing '+role+' landing floor voxel')
                for y in range(lo[1],hi[1]+1):
                    p=list(floor);p[1]=y
                    if model.get(p) not in AIR_NAMES:
                        raise ValueError('Blocked '+role+' doorway throat')
            faces.append(dict(role=role,checked=True))
        checked.append(dict(id=name,lo=list(lo),hi=list(hi),facing=item['facing'],adjacent_faces=faces))
        allowed.update(positions)
    changes = [dict(pos=list(p),before=model.get(p),after=AIR) for p in sorted(allowed) if model.get(p) not in AIR_NAMES]
    removed_walls = sorted(allowed & wall_positions) if wall_positions is not None else []
    # No Model writes happen until every declaration, landing and throat passed.
    model.stage='opened'
    for p in allowed:
        model.put(p,AIR)
    model.opened=set(allowed)
    model.final_fingerprint=model.fingerprint()
    if wall_positions is not None:
        wall_positions.difference_update(allowed)
    return dict(passed=True,before_geometry_sha256=before,after_geometry_sha256=model.final_fingerprint,
                openings=checked,opened_positions=[list(p) for p in sorted(allowed)],changes=changes,
                removed_wall_positions=[list(p) for p in removed_walls],
                validation=dict(sealed_before_opening=True,floor_voxels_present=True,
                                collision_support='not_checked',routes='not_checked',game='not_checked'),
                note='Only declared apertures were carved. Keep seal/diff evidence; reclose a copy and validate routes before delivery.')
