"""Theme-free voxel authoring and validation for Java 1.20.1 structures.

Coordinates are x,y,z; all boxes use inclusive bounds. No room shell or style is
chosen here. Supports string states such as stone_brick_stairs[facing=east,...].
"""
from collections import deque
import gzip
import hashlib
import json
from pathlib import Path
import struct
from nbt_registry import normalize

AIR = 'minecraft:air'
AIR_NAMES = {'minecraft:air', 'minecraft:cave_air', 'minecraft:void_air'}


def state(value):
    return normalize(value)


def compound(value):
    name, _, suffix = value.partition('[')
    result = {'Name': name}
    if suffix:
        result['Properties'] = dict(item.split('=',1) for item in suffix.rstrip(']').split(','))
    return result


class Model:
    def __init__(self, size):
        self.size = tuple(size)
        assert len(size) == 3 and all(isinstance(n,int) and 1 <= n <= 48 for n in size)
        self.blocks = {}
        self.stage = 'design'
        self.seal_record = None
        self.opened = set()
        self.final_fingerprint = None

    def in_bounds(self, p):
        return all(0 <= p[i] < self.size[i] for i in range(3))

    def get(self, p):
        return self.blocks.get(tuple(p), AIR)

    def put(self, p, material):
        p = tuple(p)
        assert len(p) == 3 and all(type(v) is int for v in p), 'Voxel coordinates must be integer x,y,z'
        assert self.in_bounds(p), f'Out of bounds: {p}'
        assert self.stage != 'sealed', 'Seal accepted: open_ports or explicitly begin a redesign first'
        value = state(material)
        if value in AIR_NAMES:
            self.blocks.pop(p, None)
        else:
            self.blocks[p] = value

    def box(self, lo, hi, material):
        assert all(lo[i] <= hi[i] for i in range(3))
        for x in range(lo[0],hi[0]+1):
            for y in range(lo[1],hi[1]+1):
                for z in range(lo[2],hi[2]+1):
                    self.put((x,y,z),material)

    def begin_redesign(self):
        """Invalidate checks before changing a sealed model.

        For already-opened models, explicitly restore all intended boundary
        openings before checking sealing again. Do not hide existing leaks.
        """
        self.stage = 'design'
        self.seal_record = None
        self.final_fingerprint = None
        self.opened = set()

    def fingerprint(self):
        return hashlib.sha256(json.dumps([self.size, sorted(self.blocks.items())],separators=(',',':')).encode()).hexdigest()

    def check_sealed(self, interior_points):
        """Exterior flood on a one-voxel padded domain, using all air as passable.

        Caller supplies points covering every intended chamber, not ornamental
        hollow blocks. This is a topology check, not Minecraft collision physics.
        """
        probes = [tuple(p) for p in interior_points]
        assert all(len(p)==3 and all(type(v) is int for v in p) for p in probes), 'Interior probes use integer voxel coordinates, not player feet coordinates'
        assert probes and all(self.in_bounds(p) and self.get(p) in AIR_NAMES for p in probes)
        origin = (-1,-1,-1)
        seen = {origin}
        queue = deque([origin])
        while queue:
            x,y,z = queue.popleft()
            for p in ((x-1,y,z),(x+1,y,z),(x,y-1,z),(x,y+1,z),(x,y,z-1),(x,y,z+1)):
                if (p not in seen and all(-1 <= p[i] <= self.size[i] for i in range(3))
                        and self.get(p) in AIR_NAMES):
                    seen.add(p)
                    queue.append(p)
        leaks = [list(p) for p in probes if p in seen]
        assert not leaks, f'Exterior leak into intended interior: {leaks}'
        self.seal_record = dict(passed=True, probes=[list(p) for p in probes],
                                geometry_sha256=self.fingerprint(), method='padded_six_neighbor_air_flood')
        self.stage = 'sealed'
        self.final_fingerprint = self.fingerprint()
        return self.seal_record

    def open_ports(self, ports, door_y):
        """Carve standard SAODG face openings only after successful sealing.

        Any inward vestibules must already be hollow but capped at the boundary
        during design. This prevents a tunnelling operation breaching a second wall.
        """
        assert self.stage == 'sealed' and self.seal_record['geometry_sha256'] == self.fingerprint()
        assert self.size[0] == self.size[2] == 48
        assert 2 <= door_y <= self.size[1]-6
        assert ports and len({p['id'] for p in ports}) == len(ports)
        allowed = set()
        for port in ports:
            f = port['facing']
            expected = {
                'west': ([0,door_y,21],[0,door_y+4,26]),
                'east': ([47,door_y,21],[47,door_y+4,26]),
                'north': ([21,door_y,0],[26,door_y+4,0]),
                'south': ([21,door_y,47],[26,door_y+4,47]),
            }[f]
            assert (port['min'],port['max']) == expected, f'Nonstandard port: {port}'
            a,b = expected
            for x in range(a[0],b[0]+1):
                for z in range(a[2],b[2]+1):
                    assert self.get((x,door_y-1,z)) not in AIR_NAMES, 'Missing doorstep'
                    for y in range(door_y,door_y+5):
                        allowed.add((x,y,z))
        self.stage = 'opened'
        for p in allowed:
            self.put(p,AIR)
        self.opened = allowed
        # Check the entire throat immediately inside each declared doorway.
        inward = dict(west=(1,0,0), east=(-1,0,0), north=(0,0,1), south=(0,0,-1))
        for port in ports:
            dx,_,dz = inward[port['facing']]
            lo,hi = port['min'],port['max']
            for x in range(lo[0],hi[0]+1):
                for z in range(lo[2],hi[2]+1):
                    assert self.get((x+dx,door_y-1,z+dz)) not in AIR_NAMES, 'No inner doorway floor'
                    assert all(self.get((x+dx,y,z+dz)) in AIR_NAMES for y in range(door_y,door_y+5)), 'Blocked inner doorway throat'
        self.final_fingerprint = self.fingerprint()
        return dict(passed=True, air_blocks=len(allowed), door_y=door_y)

    def save(self, path):
        path = Path(path)
        # Geometry changes made after carving require explicit revalidation.
        assert self.seal_record is not None, 'Run check_sealed before export'
        assert self.fingerprint() == self.final_fingerprint, 'Geometry changed after validation; redesign and revalidate'
        palette = sorted({AIR, *self.blocks.values()})
        assert len(palette) <= 4096
        mapping = {v:i for i,v in enumerate(palette)}
        def integer(n): return struct.pack('>i',n)
        def string(s):
            data = s.encode('utf8')
            return struct.pack('>H',len(data))+data
        def tag(t,n,p): return bytes([t])+string(n)+p
        entries = []
        for v in palette:
            data = compound(v)
            raw = tag(8,'Name',string(data['Name']))
            if 'Properties' in data:
                raw += tag(10,'Properties',b''.join(tag(8,k,string(v)) for k,v in data['Properties'].items())+b'\0')
            entries.append(raw+b'\0')
        body = bytearray()
        sx,sy,sz = self.size
        for y in range(sy):
            for z in range(sz):
                for x in range(sx):
                    body += tag(9,'pos',b'\x03'+integer(3)+integer(x)+integer(y)+integer(z))
                    body += tag(3,'state',integer(mapping[self.get((x,y,z))]))+b'\0'
        raw = b'\x0a\0\0'+tag(3,'DataVersion',integer(3465))
        raw += tag(9,'size',b'\x03'+integer(3)+b''.join(map(integer,self.size)))
        raw += tag(9,'palette',b'\x0a'+integer(len(palette))+b''.join(entries))
        raw += tag(9,'blocks',b'\x0a'+integer(sx*sy*sz)+body)
        raw += tag(9,'entities',b'\x0a'+integer(0))+b'\0'
        packed = gzip.compress(raw,mtime=0)
        assert len(packed) <= 2*1024*1024
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(packed)
        # Separate parser, compare actual disk state including Properties.
        recovered = load(path)
        assert recovered.size == self.size and recovered.blocks == self.blocks
        return dict(path=str(path.resolve()), sha256=hashlib.sha256(packed).hexdigest(),
                    size=list(self.size), palette_states=len(palette), full_volume=sx*sy*sz,
                    before_opening=self.seal_record, disk_roundtrip=True)


def load(path):
    from generate_sealed_models import read_nbt
    data = read_nbt(Path(path))
    assert data['DataVersion'] == 3465 and not data['entities'] and 'palettes' not in data
    model = Model(data['size'])
    palette = [state(v) for v in data['palette']]
    assert 1 <= len(palette) <= 4096
    positions = set()
    for block in data['blocks']:
        p = tuple(block['pos'])
        assert p not in positions and model.in_bounds(p) and 'nbt' not in block
        assert 0 <= block['state'] < len(palette)
        model.put(p,palette[block['state']])
        positions.add(p)
    assert len(positions) == model.size[0]*model.size[1]*model.size[2]
    return model


def ports(facings, door_y):
    edges = dict(west=([0,door_y,21],[0,door_y+4,26]), east=([47,door_y,21],[47,door_y+4,26]),
                 north=([21,door_y,0],[26,door_y+4,0]), south=([21,door_y,47],[26,door_y+4,47]))
    return [dict(id=f,facing=f,min=edges[f][0],max=edges[f][1]) for f in facings]


def check_full_block_routes(model, start, targets, allow_jump=False):
    """Conservative full-cube-only route check; no invented stair/half-block physics.

    Positions are integer feet locations at voxel centers x+.5,z+.5. Full blocks
    require jumps on +1 transitions unless proper stairs are used; default False
    deliberately refuses that. Non-cubic blocks are rejected, not counted as air.
    For stairs/slabs use a collision-aware checker or in-game acceptance instead.
    """
    assert all('[' not in v for v in model.blocks.values()), 'Stateful geometry needs collision-aware route validation'
    from nbt_collision import collision_cells
    assert all(v in AIR_NAMES or (collision_cells(v)[1] is None and len(collision_cells(v)[0]) == 8)
               for v in set(model.blocks.values())), 'Non-cubic geometry needs collision-aware route validation'
    start = tuple(start)
    targets = [tuple(p) for p in targets]
    def standing(p):
        x,y,z = p
        return (model.in_bounds(p) and y >= 1 and model.in_bounds((x,y+1,z))
                and model.get(p) in AIR_NAMES and model.get((x,y+1,z)) in AIR_NAMES
                and model.get((x,y-1,z)) not in AIR_NAMES)
    assert standing(start)
    seen = {start}
    queue = deque([start])
    while queue:
        x,y,z = queue.popleft()
        for dx,dz in ((1,0),(-1,0),(0,1),(0,-1)):
            for dy in ((0,-1,1) if allow_jump else (0,-1)):
                p = (x+dx,y+dy,z+dz)
                if p in seen or not standing(p):
                    continue
                if dy > 0 and model.get((x,y+2,z)) not in AIR_NAMES:
                    continue
                if dy < 0 and model.get((p[0],y+1,p[2])) not in AIR_NAMES:
                    continue
                seen.add(p)
                queue.append(p)
    missing = [list(p) for p in targets if p not in seen]
    assert not missing, f'Unreachable route targets: {missing}'
    return dict(passed=True, reachable_poses=len(seen), targets=[list(p) for p in targets],
                method='full_cube_two_air_headspace_cardinal', full_block_jumps_allowed=allow_jump,
                runtime_verified=False)
