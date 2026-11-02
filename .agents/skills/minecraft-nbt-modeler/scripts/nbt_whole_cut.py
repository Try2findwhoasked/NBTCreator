"""Whole-building-first pipeline. Cutting is a lossless coordinate operation.

The master has no cell-local builders. Contiguous 48 reassembly reproduces it;
49-stride SAODG placement is a separate compatibility check, not the master.
"""
from pathlib import Path
import gzip
import hashlib
import json
from nbt_model import Model,AIR_NAMES,load
from nbt_assembly import Volume
from nbt_wall_layers import export_wall_layers
from nbt_delivery import export_delivery,validate_file_prefix


def open_master_ports(master,definitions,door_y):
    assert master.stage=='sealed' and master.fingerprint()==master.seal_record['geometry_sha256']
    assert 2<=door_y<=master.size[1]-6 and definitions
    assert len({p['id'] for p in definitions})==len(definitions)
    delta=dict(west=(-1,0),east=(1,0),north=(0,-1),south=(0,1))
    positions=set()
    for p in definitions:
        a,b=p['min'],p['max'];dx,dz=delta[p['facing']]
        assert len(a)==len(b)==3 and all(type(v) is int for v in a+b)
        assert a[1]==door_y and b[1]==door_y+4
        assert master.in_bounds(a) and master.in_bounds(b)
        if dx:
            assert a[0]==b[0]==(0 if dx<0 else master.size[0]-1) and b[2]-a[2]==5
        else:
            assert a[2]==b[2]==(0 if dz<0 else master.size[2]-1) and b[0]-a[0]==5
        for x in range(a[0],b[0]+1):
            for z in range(a[2],b[2]+1):
                assert master.get((x,door_y-1,z)) not in AIR_NAMES
                assert master.get((x-dx,door_y-1,z-dz)) not in AIR_NAMES
                assert all(master.get((x-dx,y,z-dz)) in AIR_NAMES for y in range(door_y,door_y+5))
                positions.update((x,y,z) for y in range(door_y,door_y+5))
    master.stage='opened'
    for p in positions:master.put(p,'air')
    master.opened=positions;master.final_fingerprint=master.fingerprint()
    return dict(passed=True,door_y=door_y,external_air_cells=len(positions))


def reassemble_contiguous(parts,height):
    """Read actual parts at their original 48-grid offsets, with no new geometry."""
    assert parts and 8<=height<=48
    seen=set();loaded=[];sources=[]
    for item in parts:
        a=item['offset'];assert len(a)==3 and all(type(v) is int for v in a)
        assert a[1]==0 and a[0]>=0 and a[2]>=0 and a[0]%48==a[2]%48==0
        cell=(a[0]//48,a[2]//48);assert cell not in seen;seen.add(cell)
        raw=Path(item['file']).read_bytes();m=load(item['file'])
        assert m.size==(48,height,48) and Path(item['file']).read_bytes()==raw
        loaded.append((a,m));sources.append(dict(file=str(Path(item['file']).resolve()),sha256=hashlib.sha256(raw).hexdigest(),offset=a))
    v=Volume((max(c[0] for c in seen)*48+48,height,max(c[1] for c in seen)*48+48))
    for a,m in loaded:
        for p,state in m.blocks.items():v.put((p[0]+a[0],p[1],p[2]+a[2]),state)
    return v,dict(stride=48,added_blocks=0,sources=sources,geometry_sha256=v.fingerprint())


def slice_master(master,output_dir,resource_prefix,wall_positions=None,wall_semantics='Explicit global wall mask',file_prefix=''):
    """Finish+seal+open MASTER first. Then cut exact, full-volume 48xHx48 pieces.

    Full rectangular master only. Sparse footprints need an explicit exclusion
    model, not automatic deletion of anything inconvenient at slice time.
    """
    file_prefix=validate_file_prefix(file_prefix)
    sx,h,sz=master.size
    assert sx%48==sz%48==0 and 8<=h<=48 and sx<=288 and sz<=288
    assert master.seal_record and master.fingerprint()==master.final_fingerprint,'Finish and validate the master before cutting'
    original=dict(master.blocks);fingerprint=master.fingerprint()
    walls=set(tuple(p) for p in ([] if wall_positions is None else wall_positions))
    assert all(len(p)==3 and all(type(v) is int for v in p) and master.in_bounds(p) for p in walls)
    out=Path(output_dir);out.mkdir(parents=True,exist_ok=True)
    # Preserve the actual complete master, not just a conceptual design note.
    master_data=dict(size=list(master.size),blocks=[[list(p),v] for p,v in sorted(original.items())],
                     absent_positions='minecraft:air',geometry_sha256=fingerprint,
                     wall_positions=[list(p) for p in sorted(walls)])
    master_path=out/'master_geometry.json.gz'
    master_path.write_bytes(gzip.compress(json.dumps(master_data,separators=(',',':')).encode(),mtime=0))
    entries=[];layers=[]
    for cx in range(sx//48):
        for cz in range(sz//48):
            part=Model((48,h,48));mask=[]
            # No procedural geometry, portal corrections or decoration in this loop.
            for (x,y,z),value in original.items():
                if x//48==cx and z//48==cz:part.put((x-cx*48,y,z-cz*48),value)
            for x,y,z in walls:
                if x//48==cx and z//48==cz:mask.append((x-cx*48,y,z-cz*48))
            part.seal_record=dict(master.seal_record,scope='whole_master_before_cut')
            part.stage='opened';part.final_fingerprint=part.fingerprint()
            name=f'{file_prefix}p{cx}{cz}';path=out/(name+'.nbt');io=part.save(path)
            entries.append(dict(template=resource_prefix+'/'+name,offset=[cx*48,0,cz*48],file=str(path.resolve()),sha256=io['sha256']))
            if wall_positions is not None:
                layers.append(export_wall_layers(load(path),mask,out/'layers',name,wall_semantics))
    actual,placement=reassemble_contiguous(entries,h)
    assert actual.size==master.size and actual.blocks==original and actual.fingerprint()==fingerprint
    assert master.blocks==original and master.fingerprint()==fingerprint
    report=dict(pipeline='single_global_master_then_lossless_cut',file_prefix=file_prefix,master=str(master_path.resolve()),
                master_file_sha256=hashlib.sha256(master_path.read_bytes()).hexdigest(),master_geometry_sha256=fingerprint,
                parts=entries,layers=layers,contiguous_reassembly=placement,
                exact_master_reconstruction=True,master_unchanged=True,
                runtime='48-contiguous reassembly is exact. SAODG49 placement needs a separate check; no compatibility claim here.')
    if wall_positions is not None:
        report['delivery']=export_delivery(master,[(x,z) for x in range(sx//48) for z in range(sz//48)],
            walls,out/'delivery',wall_semantics,file_prefix=file_prefix)
    (out/'whole_cut_manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    return entries,report
