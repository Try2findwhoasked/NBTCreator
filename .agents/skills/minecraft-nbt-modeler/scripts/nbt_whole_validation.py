"""Explicit standalone aperture validation; legacy SAODG validation stays strict."""
from itertools import product
from nbt_assembly import Volume
from nbt_model import AIR_NAMES
from nbt_collision import check_routes


def validation_mode(config):
    mode = config.get('mode', 'saodg')
    if mode not in ('saodg', 'standalone'):
        raise ValueError('Unknown validation mode; choose saodg or standalone explicitly')
    return mode


def _point(value):
    if not isinstance(value, (list, tuple)) or len(value)!=3 or any(type(n) is not int for n in value):
        raise ValueError('Opening bounds must be integer XYZ triples')
    return tuple(value)


def active_xz_cells(size, cells=None):
    """Optional standalone XZ footprint; absent/empty means the full free-size box."""
    if cells is None or cells==[] or cells==():return None
    if not isinstance(cells,(list,tuple)):
        raise ValueError('Standalone cells must be an explicit XZ array')
    result=[]
    for cell in cells:
        if not isinstance(cell,(list,tuple)) or len(cell)!=2 or any(type(v) is not int or v<0 for v in cell):
            raise ValueError('Standalone cells must contain integer non-negative XZ pairs')
        pair=tuple(cell)
        if pair in result or pair[0]*48>=size[0] or pair[1]*48>=size[2]:
            raise ValueError('Duplicate or out-of-bounds standalone cell')
        result.append(pair)
    found={result[0]};pending=[result[0]];allowed=set(result)
    while pending:
        x,z=pending.pop()
        for p in ((x-1,z),(x+1,z),(x,z-1),(x,z+1)):
            if p in allowed and p not in found:found.add(p);pending.append(p)
    if found!=allowed:raise ValueError('Standalone cells must be four-neighbour connected')
    return sorted(result)


def standalone_cells(model, config):
    cells=active_xz_cells(model.size,config.get('cells'))
    if cells is not None and any((p[0]//48,p[2]//48) not in cells for p in model.blocks):
        raise ValueError('Standalone source writes into an excluded footprint cell')
    return cells


def standalone_openings(model, config):
    if validation_mode(config) != 'standalone':
        raise ValueError('Standalone apertures require mode=standalone')
    if 'ports' in config and config['ports'] != []:
        raise ValueError('Standalone mode uses openings, not SAODG ports')
    if 'openings' not in config or not isinstance(config['openings'], list):
        raise ValueError('Standalone context must explicitly declare openings (an empty list means no openings)')
    directions = dict(north=(2,-1),south=(2,1),west=(0,-1),east=(0,1))
    positions, names, definitions = set(), set(), []
    for item in config['openings']:
        if not isinstance(item, dict) or set(item)!={'id','lo','hi','facing'}:
            raise ValueError('Opening fields must be id, lo, hi, facing')
        name=item['id'];facing=item['facing']
        if not isinstance(name,str) or not name.strip() or name in names or not isinstance(facing,str) or facing not in directions:
            raise ValueError('Opening needs unique id and horizontal facing')
        names.add(name);lo,hi=_point(item['lo']),_point(item['hi'])
        if lo[1]<1 or any(lo[i]>hi[i] for i in range(3)) or not model.in_bounds(lo) or not model.in_bounds(hi):
            raise ValueError('Opening exceeds model bounds or removes the floor')
        aperture=set(product(*(range(a,b+1) for a,b in zip(lo,hi))))
        if aperture & positions:
            raise ValueError('Opening declarations overlap')
        if any(model.get(p) not in AIR_NAMES for p in aperture):
            raise ValueError('Declared standalone aperture is not open')
        for x,z in product(range(lo[0],hi[0]+1),range(lo[2],hi[2]+1)):
            if model.get((x,lo[1]-1,z)) in AIR_NAMES:
                raise ValueError('Standalone opening doorstep is missing')
        axis,sign=directions[facing];across=2 if axis==0 else 0
        adjacent=[]
        for role,coord in [('interior',lo[axis]-1 if sign>0 else hi[axis]+1),
                           ('exterior',hi[axis]+1 if sign>0 else lo[axis]-1)]:
            if not 0<=coord<model.size[axis]:
                if role=='interior':raise ValueError('Standalone aperture has no interior throat')
                adjacent.append(dict(role=role,checked=False,reason='outside_model_bounds'));continue
            for cross in range(lo[across],hi[across]+1):
                p=[0,lo[1]-1,0];p[axis]=coord;p[across]=cross
                if model.get(p) in AIR_NAMES:raise ValueError('Standalone '+role+' landing floor is missing')
                for y in range(lo[1],hi[1]+1):
                    p[1]=y
                    if model.get(p) not in AIR_NAMES:raise ValueError('Standalone '+role+' throat is blocked')
            adjacent.append(dict(role=role,checked=True))
        positions.update(aperture)
        definitions.append(dict(id=name,lo=list(lo),hi=list(hi),facing=facing,adjacent_faces=adjacent))
    return positions, definitions


def protective_openings(model, config):
    """Protect every declared aperture, adjacent throat, support and top edge."""
    if validation_mode(config) != 'standalone':return set()
    # Validate declaration syntax and actual existing aperture before deriving a mask.
    standalone_openings(model, config)
    protected=set()
    for opening in config['openings']:
        lo,hi=opening['lo'],opening['hi']
        for p in product(*(range(lo[i]-1,hi[i]+2) for i in range(3))):
            if model.in_bounds(p):protected.add(p)
    return protected


def validate_whole(model, config):
    if validation_mode(config) != 'standalone':
        from nbt_refine import validate_saodg
        return validate_saodg(model,config)
    cells=standalone_cells(model,config)
    positions,definitions=standalone_openings(model,config)
    for key in ('interior_probes','start','targets'):
        if key not in config:raise ValueError('Standalone context missing '+key)
    if not config['targets']:
        raise ValueError('Standalone building validation needs explicit route targets; do not remove required routes')
    capped=Volume(model.size);capped.blocks=dict(model.blocks)
    for p in positions:capped.put(p,'stone_bricks')
    seal=capped.check_sealed(config['interior_probes'])
    seal=dict(seal,scope='validation_copy_with_declared_standalone_openings_recapped',
              original_preopening_proof=False,source_geometry_sha256=model.fingerprint())
    routes=check_routes(model,config['start'],config['targets'])
    if not routes['passed']:
        import json
        raise ValueError('Standalone static route validation failed: '+json.dumps({k:v for k,v in routes.items() if k!='targets'}))
    legs=[]
    for leg in config.get('route_legs',[]):
        copy=Volume(model.size);copy.blocks=dict(model.blocks)
        for bounds in leg.get('validation_only_barriers',[]):copy.box(bounds['lo'],bounds['hi'],'stone')
        result=check_routes(copy,leg['start'],leg['targets'])
        if not result['passed']:raise ValueError('Required standalone route leg failed: '+str(leg.get('name')))
        legs.append(dict(name=leg['name'],report=result))
    return dict(passed=True,mode='standalone',active_cells=[list(c) for c in cells] if cells is not None else None,legal_port_cells=len(positions),openings=definitions,
                recapped_seal=seal,routes=routes,route_legs=legs,runtime_verified=False,
                original_preopening_proof=False,saodg49='not_applicable',
                note='Declared apertures recapped only in a validation copy; this is not an initial pre-opening receipt or game acceptance.')
