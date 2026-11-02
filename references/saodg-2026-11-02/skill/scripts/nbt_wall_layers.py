"""Export explicitly marked wall surfaces separately, without changing runtime NBT.

Wall/interior layers are SPARSE vanilla structure templates: omitted positions
are untouched when placed. They are authoring assets, not SAODG full-volume parts.
Their disjoint union reconstructs the source solid blocks on an empty volume.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import struct
from nbt_model import AIR, AIR_NAMES, Model, state, compound, load
from generate_sealed_models import read_nbt


class WallMask:
    """Keep wall classification in sync with post-wall construction writes.

    All subsequent geometry must use model.put/box, not direct blocks mutation.
    A write removes that coordinate from walls even when the material is equal.
    Use mark() after an intentional wall repaint, then finish() before export.
    """
    def __init__(self,model,positions):
        self.model=model;self.positions=set();self.mark(positions)
        self._original=model.put
        def tracked(p,material):
            self._original(p,material)
            self.positions.discard(tuple(p))
        self._tracked=tracked;model.put=tracked

    def mark(self,positions):
        for p in positions:
            p=tuple(p)
            assert len(p)==3 and all(type(v) is int for v in p) and self.model.in_bounds(p)
            if self.model.get(p) not in AIR_NAMES:self.positions.add(p)

    def finish(self):
        if self.model.put is self._tracked:self.model.put=self._original
        return set(self.positions)

    def finish_vertical_skin(self):
        """Surviving authored enclosure with horizontal air-facing surfaces.

        Capture the enclosure/geology before details. Later writes are excluded,
        even for matching materials. Floor and top two saved layers excluded;
        sloped rock with horizontal exposure is classified as cave wall skin.
        """
        candidates=self.finish();result=set();height=self.model.size[1]
        for x,y,z in candidates:
            if not 2<=y<height-2:continue
            if any(not self.model.in_bounds(p) or self.model.get(p) in AIR_NAMES
                   for p in ((x-1,y,z),(x+1,y,z),(x,y,z-1),(x,y,z+1))):
                result.add((x,y,z))
        return result

    def __iter__(self):return iter(self.positions)


def _write_sparse(path,size,blocks):
    def integer(n):return struct.pack('>i',n)
    def string(s):
        b=s.encode('utf8');return struct.pack('>H',len(b))+b
    def tag(t,n,p):return bytes([t])+string(n)+p
    palette=sorted({AIR,*blocks.values()});index={v:i for i,v in enumerate(palette)}
    assert len(palette)<=4096
    entries=[]
    for value in palette:
        data=compound(value);payload=tag(8,'Name',string(data['Name']))
        if data.get('Properties'):
            payload+=tag(10,'Properties',b''.join(tag(8,k,string(v)) for k,v in data['Properties'].items())+b'\0')
        entries.append(payload+b'\0')
    payload=bytearray()
    for p,value in sorted(blocks.items()):
        payload+=tag(9,'pos',b'\x03'+integer(3)+b''.join(map(integer,p)))
        payload+=tag(3,'state',integer(index[value]))+b'\0'
    raw=b'\x0a\0\0'+tag(3,'DataVersion',integer(3465))
    raw+=tag(9,'size',b'\x03'+integer(3)+b''.join(map(integer,size)))
    raw+=tag(9,'palette',b'\x0a'+integer(len(palette))+b''.join(entries))
    raw+=tag(9,'blocks',b'\x0a'+integer(len(blocks))+payload)
    raw+=tag(9,'entities',b'\x0a'+integer(0))+b'\0'
    packed=gzip.compress(raw,mtime=0);assert len(packed)<=2*1024*1024
    path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(packed)
    actual=read_nbt(path)
    assert actual['size']==list(size) and actual['entities']==[] and actual['DataVersion']==3465
    values=[state(v) for v in actual['palette']]
    decoded={tuple(b['pos']):values[b['state']] for b in actual['blocks']}
    assert len(decoded)==len(actual['blocks']) and decoded==blocks
    return dict(file=str(path.resolve()),sha256=hashlib.sha256(packed).hexdigest(),
                size=list(size),explicit_blocks=len(blocks),sparse=True,saodg_runtime_part=False,saodg_schema5_layer=True),decoded


def read_sparse(path):
    """Read an editing layer into an in-memory Model; no full-volume claim."""
    data=read_nbt(Path(path));assert data['DataVersion']==3465 and not data['entities'] and 'palettes' not in data
    m=Model(data['size']);palette=[state(v) for v in data['palette']]
    assert 1<=len(palette)<=4096
    seen=set()
    for block in data['blocks']:
        p=tuple(block['pos']);assert p not in seen and 'nbt' not in block
        assert 0<=block['state']<len(palette)
        seen.add(p);m.put(p,palette[block['state']])
    return m


def export_wall_layers(model,wall_positions,output_dir,stem='model',semantics='Explicit author-marked wall surfaces'):
    """Mask must be authored before decoration, never inferred by material name.

    Air positions in the mask (e.g. opened doorways) are dropped, not written as
    air: placing the wall layer must not erase the separately placed interior.
    """
    assert len(model.size)==3 and all(type(n) is int and 1<=n<=48 for n in model.size)
    assert stem and Path(stem).name==stem and stem not in ('.','..')
    mask={tuple(p) for p in wall_positions}
    assert all(len(p)==3 and all(type(v) is int for v in p) and model.in_bounds(p) for p in mask),'Invalid wall coordinate'
    original=dict(model.blocks);before=model.fingerprint()
    walls={p:v for p,v in original.items() if p in mask and v not in AIR_NAMES}
    interior={p:v for p,v in original.items() if p not in mask and v not in AIR_NAMES}
    out=Path(output_dir)
    wall_report,wall_disk=_write_sparse(out/(stem+'_walls.nbt'),model.size,walls)
    interior_report,inside_disk=_write_sparse(out/(stem+'_interior.nbt'),model.size,interior)
    assert not wall_disk.keys()&inside_disk.keys()
    assert {**wall_disk,**inside_disk}==original
    assert model.blocks==original and model.fingerprint()==before
    report=dict(source_geometry_sha256=before,wall_semantics=semantics,wall_mask_positions=len(mask),
                ignored_air_positions=sum(model.get(p) in AIR_NAMES for p in mask),
                walls=wall_report,interior=interior_report,disjoint=True,
                reconstructed_on_empty_volume_matches_source=True,source_unchanged=True,
                placement='Place both sparse layers at the identical origin in an empty volume; omissions do not clear existing blocks.',
                runtime='Keep original full-volume NBT for SAODG. Do not put overlapping wall/interior layers in room.parts.')
    out.mkdir(parents=True,exist_ok=True)
    (out/(stem+'_layers.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--nbt',type=Path,required=True)
    parser.add_argument('--wall-mask',type=Path,required=True,help='JSON list of integer [x,y,z] positions')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--stem',default='model')
    args=parser.parse_args()
    source=args.nbt.read_bytes();model=load(args.nbt)
    result=export_wall_layers(model,json.loads(args.wall_mask.read_text(encoding='utf8')),args.output,args.stem)
    assert args.nbt.read_bytes()==source
    print(json.dumps(dict(walls=result['walls']['file'],interior=result['interior']['file'],reconstructed=True)))


if __name__=='__main__':main()
