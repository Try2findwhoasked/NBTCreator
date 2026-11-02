"""Final authoring delivery: exactly one body and one wall NBT per occupied cell.

Full-volume runtime templates belong outside this directory. Each sparse pair
is disjoint and reconstructs the complete source on an empty volume at stride48.
"""
import hashlib
import json
import re
from pathlib import Path
from nbt_wall_layers import _write_sparse,read_sparse


def validate_file_prefix(value):
    """One portable basename prefix; never a directory or absolute path."""
    if not isinstance(value,str) or (value and not re.fullmatch(r'[a-z0-9][a-z0-9_-]*_',value)):
        raise ValueError('file_prefix must be empty or lowercase letters/digits/hyphens/underscores ending in underscore')
    return value


def export_delivery(master,cells,wall_positions,output_dir,semantics,file_prefix=''):
    file_prefix=validate_file_prefix(file_prefix)
    if not master.seal_record or master.fingerprint()!=master.final_fingerprint:
        raise ValueError('Finish and validate the whole source before delivery export')
    cells=[tuple(c) for c in cells]
    if not cells or len(set(cells))!=len(cells):raise ValueError('Occupied cells must be explicit and unique')
    if any(len(c)!=2 or any(type(v) is not int or v<0 for v in c) for c in cells):raise ValueError('Invalid cell')
    sx,h,sz=master.size
    if not 8<=h<=48 or any((x+1)*48>sx or (z+1)*48>sz for x,z in cells):raise ValueError('Cells exceed master bounds')
    footprint=set(cells)
    if any((p[0]//48,p[2]//48) not in footprint for p in master.blocks):raise ValueError('Source writes into an excluded cell')
    walls=set(tuple(p) for p in wall_positions)
    if any(len(p)!=3 or any(type(v) is not int for v in p) or not master.in_bounds(p)
           or (p[0]//48,p[2]//48) not in footprint for p in walls):raise ValueError('Invalid wall mask')
    original=dict(master.blocks);source_hash=master.fingerprint()
    out=Path(output_dir);out.mkdir(parents=True,exist_ok=True)
    expected={f'{file_prefix}p{x}{z}_{layer}.nbt' for x,z in cells for layer in ('body','walls')}
    unexpected={p.name for p in out.rglob('*.nbt') if p.parent!=out or p.name not in expected}
    if unexpected:raise ValueError(f'Delivery has extra/stale NBT; choose clean directory or explicitly archive them: {sorted(unexpected)}')
    entries=[];recovered={}
    for cx,cz in sorted(cells):
        local={};wall={}
        for (x,y,z),value in original.items():
            if (x//48,z//48)==(cx,cz):
                target=wall if (x,y,z) in walls else local
                target[(x-cx*48,y,z-cz*48)]=value
        if not wall:raise ValueError(f'No explicitly authored walls in cell {(cx,cz)}; do not silently export an empty wall placeholder')
        body_info,body_disk=_write_sparse(out/f'{file_prefix}p{cx}{cz}_body.nbt',(48,h,48),local)
        wall_info,wall_disk=_write_sparse(out/f'{file_prefix}p{cx}{cz}_walls.nbt',(48,h,48),wall)
        assert not body_disk.keys()&wall_disk.keys()
        for p,value in {**body_disk,**wall_disk}.items():recovered[(p[0]+cx*48,p[1],p[2]+cz*48)]=value
        entries.append(dict(cell=[cx,cz],offset=[cx*48,0,cz*48],body=body_info,walls=wall_info))
    assert recovered==original and master.fingerprint()==source_hash and master.blocks==original
    assert {p.name for p in out.glob('*.nbt')}==expected
    report=dict(format_version=1,file_prefix=file_prefix,occupied_cells=[list(c) for c in sorted(cells)],master_size=list(master.size),
                source_geometry_sha256=source_hash,expected_nbt_files=2*len(cells),actual_nbt_files=len(expected),
                wall_semantics=semantics,parts=entries,exact_solid_reconstruction=True,source_unchanged=True,
                placement=dict(stride=48,same_origin_for_each_pair=True,sparse_omissions_do_not_clear_old_blocks=True),
                runtime='Schema 5 may reference each pair as body_template/wall_template in one part. Full-volume legacy/runtime templates are separate and not counted here.')
    (out/'delivery.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    return verify_delivery(out)


def verify_delivery(directory):
    out=Path(directory);report=json.loads((out/'delivery.json').read_text(encoding='utf8'))
    file_prefix=validate_file_prefix(report.get('file_prefix',''))
    expected=set();blocks={};seen_cells=set()
    for item in report['parts']:
        cx,cz=item['cell'];assert (cx,cz) not in seen_cells;seen_cells.add((cx,cz))
        assert item['offset']==[cx*48,0,cz*48]
        pair=[]
        for layer in ('body','walls'):
            name=f'{file_prefix}p{cx}{cz}_{layer}.nbt';expected.add(name);p=out/name
            assert hashlib.sha256(p.read_bytes()).hexdigest()==item[layer]['sha256']
            m=read_sparse(p);assert m.size==(48,report['master_size'][1],48)
            assert len(m.blocks)==item[layer]['explicit_blocks']
            pair.append(m.blocks)
        assert pair[1] and not pair[0].keys()&pair[1].keys()
        for p,v in {**pair[0],**pair[1]}.items():blocks[(p[0]+cx*48,p[1],p[2]+cz*48)]=v
    actual={str(p.relative_to(out)).replace('\\','/') for p in out.rglob('*.nbt')}
    assert actual==expected,(actual,expected)
    assert len(expected)==report['expected_nbt_files']==report['actual_nbt_files']==2*len(seen_cells)
    assert seen_cells=={tuple(c) for c in report['occupied_cells']}
    canonical=json.dumps([tuple(report['master_size']),sorted(blocks.items())],separators=(',',':')).encode()
    assert hashlib.sha256(canonical).hexdigest()==report['source_geometry_sha256']
    return report


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('directory',type=Path)
    report=verify_delivery(parser.parse_args().directory)
    print(json.dumps(dict(passed=True,nbt_files=report['actual_nbt_files'],cells=report['occupied_cells'])))
