"""Sparse author-space assemblies and diagnostic 49-stride placement.

Mirrors RoomGeometry.expand and StructurePlacer.bridge for rotation 0.
Author-space cells use 48, diagnostic placement uses 49. Only <=48 NBT parts
are exported. The diagnostic volume can be passed to collision/preview tools.
"""
from pathlib import Path
import hashlib
import json
from nbt_model import Model, AIR_NAMES, load


class Volume(Model):
    """In-memory diagnostic volume; deliberately cannot export one giant NBT."""
    def __init__(self, size):
        assert len(size)==3 and all(type(n) is int and 1<=n<=294 for n in size)
        self.size=tuple(size);self.blocks={};self.stage='design'
        self.seal_record=None;self.opened=set();self.final_fingerprint=None

    def save(self, path):
        raise ValueError('Diagnostic assemblies cannot be exported as one NBT; export bounded parts')


class LogicalAssembly(Volume):
    def __init__(self,cells,height):
        self.cells=frozenset(tuple(p) for p in cells)
        assert self.cells and 8<=height<=48
        assert all(len(c)==2 and all(type(v) is int and 0<=v<6 for v in c) for c in self.cells)
        pending=[next(iter(self.cells))];seen=set(pending)
        while pending:
            x,z=pending.pop()
            for p in ((x-1,z),(x+1,z),(x,z-1),(x,z+1)):
                if p in self.cells and p not in seen:seen.add(p);pending.append(p)
        assert seen==self.cells,'Occupied cells must be four-neighbour connected'
        self.footprint=(max(c[0] for c in self.cells)+1,max(c[1] for c in self.cells)+1)
        super().__init__((48*self.footprint[0],height,48*self.footprint[1]))

    def put(self,p,material):
        assert (p[0]//48,p[2]//48) in self.cells,'Cannot write an absent footprint cell, even as air'
        super().put(p,material)

    def open_external_ports(self,definitions,door_y):
        assert self.stage=='sealed' and self.fingerprint()==self.seal_record['geometry_sha256']
        assert 2<=door_y<=self.size[1]-6
        assert definitions and len({p['id'] for p in definitions})==len(definitions)
        delta=dict(west=(-1,0),east=(1,0),north=(0,-1),south=(0,1))
        positions=set()
        for p in definitions:
            lo,hi=p['min'],p['max'];f=p['facing'];dx,dz=delta[f]
            assert len(lo)==len(hi)==3 and all(type(v) is int for v in lo+hi)
            cell=(lo[0]//48,lo[2]//48);cx,cz=cell
            assert cell in self.cells and (cx+dx,cz+dz) not in self.cells,'Internal cell seams are not external ports'
            expected=dict(west=([cx*48,door_y,cz*48+21],[cx*48,door_y+4,cz*48+26]),
                          east=([cx*48+47,door_y,cz*48+21],[cx*48+47,door_y+4,cz*48+26]),
                          north=([cx*48+21,door_y,cz*48],[cx*48+26,door_y+4,cz*48]),
                          south=([cx*48+21,door_y,cz*48+47],[cx*48+26,door_y+4,cz*48+47]))[f]
            assert (lo,hi)==expected
            for x in range(lo[0],hi[0]+1):
                for z in range(lo[2],hi[2]+1):
                    assert self.get((x,door_y-1,z)) not in AIR_NAMES
                    assert self.get((x-dx,door_y-1,z-dz)) not in AIR_NAMES
                    assert all(self.get((x-dx,y,z-dz)) in AIR_NAMES for y in range(door_y,door_y+5))
                    positions.update((x,y,z) for y in range(door_y,door_y+5))
        self.stage='opened'
        for p in positions:self.put(p,'air')
        self.opened=positions;self.final_fingerprint=self.fingerprint()
        return dict(passed=True,ports=len(definitions),external_air_cells=len(positions),door_y=door_y)

    def export_parts(self,directory,resource_prefix):
        assert self.seal_record and self.fingerprint()==self.final_fingerprint,'Geometry changed since validation'
        directory=Path(directory);entries=[]
        for cx,cz in sorted(self.cells):
            part=Model((48,self.size[1],48))
            for (x,y,z),state in self.blocks.items():
                if (x//48,z//48)==(cx,cz):part.put((x-cx*48,y,z-cz*48),state)
            # Certification belongs to the whole logical envelope, not each cut.
            part.seal_record=dict(self.seal_record,scope='whole_logical_assembly_before_external_ports')
            part.stage='opened' if self.stage=='opened' else 'sealed';part.final_fingerprint=part.fingerprint()
            name=f'p{cx}{cz}';path=directory/(name+'.nbt');io=part.save(path)
            entries.append(dict(template=resource_prefix+'/'+name,offset=[cx*48,0,cz*48],
                                cell=[cx,cz],file=str(path.resolve()),sha256=io['sha256']))
        return entries


def expand(point):
    """Author block indices or player feet XYZ -> physical local coordinates."""
    import math
    x,y,z=point
    return (x+math.floor(x/48),y,z+math.floor(z/48))


def assemble(parts,height,door_y,bridges=True):
    """Load actual disk parts, translate by49, reproduce internal bridge writes.

    parts entries need file and offset=[cellX*48,0,cellZ*48]. Neighboring template
    faces are NOT cleared by runtime bridge; author must prepare them at H.
    Physical local Y remains author Y; world Y=(66-door_y)+localY.
    """
    assert parts and 8<=height<=48 and 2<=door_y<=height-6
    cells={};sources=[]
    for entry in parts:
        offset=entry['offset']
        assert len(offset)==3 and all(type(v) is int for v in offset)
        assert offset[1]==0 and offset[0]%48==offset[2]%48==0
        cell=(offset[0]//48,offset[2]//48)
        assert cell not in cells and all(0<=c<6 for c in cell)
        source=Path(entry['file']).read_bytes()
        m=load(entry['file']);assert m.size==(48,height,48)
        assert Path(entry['file']).read_bytes()==source,'Part changed while loading'
        cells[cell]=m
        sources.append(dict(file=str(Path(entry['file']).resolve()),sha256=hashlib.sha256(source).hexdigest(),cell=list(cell)))
    LogicalAssembly(list(cells),height)  # Validate sparse footprint connectivity.
    volume=Volume((max(c[0] for c in cells)*49+48,height,max(c[1] for c in cells)*49+48))
    for (cx,cz),m in cells.items():
        for (x,y,z),state in m.blocks.items():volume.put((cx*49+x,y,cz*49+z),state)
    connections=[]
    if bridges:
        for cx,cz in sorted(cells):
            for dx,dz in ((1,0),(0,1)):
                if (cx+dx,cz+dz) not in cells:continue
                axis=cx*49+48 if dx else cz*49+48
                start=cz*49+20 if dx else cx*49+20
                for tangent in range(start,start+8):
                    for y in range(door_y-2,door_y+6):
                        p=(axis,y,tangent) if dx else (tangent,y,axis)
                        solid=y<=door_y-1 or y==door_y+5 or tangent in (start,start+7)
                        volume.put(p,'stone_bricks' if solid else 'air')
                connections.append(dict(a=[cx,cz],b=[cx+dx,cz+dz],gap_axis='x' if dx else 'z',
                                        gap_coordinate=axis,feet_y=door_y,air_tangent=[start+1,start+6]))
    return volume,dict(sources=sources,template_stride=48,physical_stride=49,door_y=door_y,
                       physical_size=list(volume.size),internal_connectors=connections,
                       world_origin_y=66-door_y,rotation=0,
                       scope='Offline mirror of RoomGeometry.expand and StructurePlacer.bridge; not Forge execution')
