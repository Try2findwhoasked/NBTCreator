"""Lossless XYZ tiling for explicit standalone masters, with real edge dimensions."""
import hashlib
import json
from itertools import product
from pathlib import Path

from nbt_assembly import Volume
from nbt_model import Model, load, AIR_NAMES
from nbt_wall_layers import _write_sparse, read_sparse
from nbt_delivery import validate_file_prefix
from nbt_whole_validation import active_xz_cells, standalone_cells


def _sha(file):return hashlib.sha256(Path(file).read_bytes()).hexdigest()
def _json(file,data):Path(file).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def _wall_hash(walls):return hashlib.sha256(json.dumps(sorted(walls),separators=(',',':')).encode()).hexdigest()
def _tiles(size,cells=None):
    if cells is None:return list(product(*(range((n+47)//48) for n in size)))
    return [(x,y,z) for x,z in cells for y in range((size[1]+47)//48)]
def _geometry(size,blocks):
    model=Volume(size);model.blocks=dict(blocks);return model.fingerprint()


def verify_standalone(directory):
    root=Path(directory);runtime=root/'runtime';delivery=root/'delivery'
    report=json.loads((delivery/'delivery.json').read_text(encoding='utf8'))
    parts=json.loads((runtime/'parts.json').read_text(encoding='utf8'))
    if report.get('kind')!='standalone_xyz_tiles' or parts.get('kind')!='standalone_xyz_tiles':
        raise ValueError('Not a standalone XYZ tile delivery')
    size=report['master_size']
    if len(size)!=3 or any(type(n) is not int or not 1<=n<=294 for n in size):raise ValueError('Invalid standalone master size')
    if parts['master_size']!=size or parts['geometry_sha256']!=report['source_geometry_sha256']:raise ValueError('Standalone manifests disagree')
    cells=active_xz_cells(size,report.get('active_cells'))
    runtime_cells=active_xz_cells(size,parts.get('active_cells'))
    if runtime_cells!=cells:raise ValueError('Standalone active footprints disagree')
    if len(parts['parts'])!=len(report['parts']):raise ValueError('Standalone manifest part count differs')
    prefix=validate_file_prefix(report.get('file_prefix',''))
    seen=set();solid={};runtime_solid={};global_walls=set();expected_runtime=set();expected_layers=set()
    runtime_by_index={tuple(item['index']):item for item in parts['parts']}
    if len(runtime_by_index)!=len(parts['parts']):raise ValueError('Duplicate runtime tile')
    for item in report['parts']:
        index=tuple(item['index'])
        if len(index)!=3 or any(type(n) is not int or n<0 for n in index) or index in seen:raise ValueError('Duplicate/invalid standalone tile')
        seen.add(index);offset=[n*48 for n in index]
        dimensions=[min(48,size[i]-offset[i]) for i in range(3)]
        if any(n<1 for n in dimensions) or item['offset']!=offset or item['size']!=dimensions:raise ValueError('Incorrect standalone offset/edge dimensions')
        stem=prefix+'p'+''.join(f'{n:02}' for n in index)
        runtime_entry=runtime_by_index.get(index)
        if not runtime_entry or runtime_entry['offset']!=offset or runtime_entry['size']!=dimensions:raise ValueError('Runtime tile metadata differs')
        runtime_name=stem+'.nbt';expected_runtime.add(runtime_name)
        runtime_file=runtime/'parts'/runtime_name
        if runtime_entry['file']!='parts/'+runtime_name or _sha(runtime_file)!=runtime_entry['sha256']:raise ValueError('Runtime tile hash/path differs')
        actual=load(runtime_file)
        if list(actual.size)!=dimensions:raise ValueError('Runtime tile dimensions differ')
        for p,value in actual.blocks.items():runtime_solid[tuple(p[i]+offset[i] for i in range(3))]=value
        pair=[]
        for layer in ('body','walls'):
            name=stem+'_'+layer+'.nbt';expected_layers.add(name);file=delivery/name;entry=item[layer]
            if entry['file']!=name or _sha(file)!=entry['sha256']:raise ValueError('Sparse layer hash/path differs')
            model=read_sparse(file)
            if list(model.size)!=dimensions or len(model.blocks)!=entry['explicit_blocks']:raise ValueError('Sparse dimensions/count differ')
            if any(value in AIR_NAMES for value in model.blocks.values()):raise ValueError('Standalone editing layers must omit air')
            pair.append(model.blocks)
        if pair[0].keys() & pair[1].keys():raise ValueError('Standalone body/wall layers overlap')
        if item.get('empty_wall_layer') is not (not bool(pair[1])):raise ValueError('Standalone empty-wall declaration differs from actual layer')
        if {**pair[0],**pair[1]}!=actual.blocks:raise ValueError('Standalone pair differs from full runtime tile')
        for p,value in {**pair[0],**pair[1]}.items():solid[tuple(p[i]+offset[i] for i in range(3))]=value
        global_walls.update(tuple(p[i]+offset[i] for i in range(3)) for p in pair[1])
    if seen!=set(_tiles(size,cells)):raise ValueError('Missing or excluded standalone footprint tile')
    if {p.relative_to(runtime/'parts').as_posix() for p in (runtime/'parts').rglob('*.nbt')}!=expected_runtime:raise ValueError('Extra/missing runtime NBT')
    if {p.relative_to(delivery).as_posix() for p in delivery.rglob('*.nbt')}!=expected_layers:raise ValueError('Extra/missing editing NBT')
    if solid!=runtime_solid or _geometry(size,solid)!=report['source_geometry_sha256']:raise ValueError('Standalone full reconstruction differs')
    if _wall_hash(global_walls)!=report['wall_positions_sha256']:raise ValueError('Standalone wall ownership reconstruction differs')
    if not global_walls and report.get('allow_empty_wall_mask') is not True:raise ValueError('Empty standalone wall mask has no explicit declaration')
    if len(expected_layers)!=report['actual_nbt_files'] or len(expected_runtime)!=parts['runtime_parts']:raise ValueError('Standalone NBT count differs')
    return report


def export_standalone(master,wall_positions,directory,file_prefix='',allow_empty_wall_mask=False,active_cells=None):
    """Every bounding-box tile has full runtime and two disjoint editing layers.

    Empty walls are an explicit standalone authoring policy, never inferred by
    material. Edge tiles retain their real dimensions; no SAODG cells are implied.
    """
    prefix=validate_file_prefix(file_prefix);root=Path(directory)
    if not master.seal_record or not master.seal_record.get('passed') or master.final_fingerprint!=master.fingerprint():
        raise ValueError('Validate the complete standalone source before export')
    if wall_positions is None:raise ValueError('Declare standalone wall mask explicitly')
    walls=set(tuple(p) for p in wall_positions)
    if any(len(p)!=3 or any(type(n) is not int for n in p) or not master.in_bounds(p) or master.get(p) in AIR_NAMES for p in walls):
        raise ValueError('Invalid standalone wall ownership')
    if not walls and allow_empty_wall_mask is not True:raise ValueError('An empty standalone wall mask requires allow_empty_wall_mask=true')
    if (root/'delivery').exists() or (root/'runtime').exists():raise FileExistsError('Preserve existing standalone exports; choose a new destination')
    cells=standalone_cells(master,dict(cells=active_cells))
    original=dict(master.blocks);geometry=master.fingerprint();size=list(master.size)
    runtime=root/'runtime';layers=root/'delivery';(runtime/'parts').mkdir(parents=True);layers.mkdir()
    part_records=[];layer_records=[];runtime_files=[]
    buckets={index:{} for index in _tiles(size,cells)}
    for p,value in original.items():buckets[tuple(v//48 for v in p)][p]=value
    for index,blocks in sorted(buckets.items()):
        offset=[v*48 for v in index];dimensions=[min(48,size[i]-offset[i]) for i in range(3)]
        local={tuple(p[i]-offset[i] for i in range(3)):value for p,value in blocks.items()}
        wall={tuple(p[i]-offset[i] for i in range(3)):value for p,value in blocks.items() if p in walls}
        body={p:value for p,value in local.items() if p not in wall}
        stem=prefix+'p'+''.join(f'{n:02}' for n in index);file=runtime/'parts'/(stem+'.nbt')
        part=Model(dimensions);part.blocks=dict(local);part.seal_record=dict(master.seal_record,scope='validated_standalone_master_before_mechanical_xyz_cut')
        part.stage='opened';part.final_fingerprint=part.fingerprint();part.save(file)
        entry=dict(index=list(index),offset=offset,size=dimensions,file='parts/'+file.name,sha256=_sha(file))
        part_records.append(entry);runtime_files.append(str(file.resolve()))
        pair={}
        for layer,data in [('body',body),('walls',wall)]:
            layer_file=layers/(stem+'_'+layer+'.nbt');info,_=_write_sparse(layer_file,dimensions,data)
            info.update(file=layer_file.name,saodg_schema5_layer=False,standalone_editing_layer=True)
            pair[layer]=info
        layer_records.append(dict(index=list(index),offset=offset,size=dimensions,
                                  empty_wall_layer=not bool(wall),body=pair['body'],walls=pair['walls']))
    cell_data=[list(c) for c in cells] if cells is not None else None
    report=dict(format_version=2,kind='standalone_xyz_tiles',file_prefix=prefix,master_size=size,active_cells=cell_data,
                source_geometry_sha256=geometry,wall_positions_sha256=_wall_hash(walls),
                actual_nbt_files=2*len(part_records),expected_nbt_files=2*len(part_records),parts=layer_records,
                allow_empty_wall_mask=allow_empty_wall_mask,empty_wall_layers_explicit=True,
                exact_solid_reconstruction=True,wall_ownership_explicit=True,source_unchanged=True,
                placement=dict(tile_stride=[48,48,48],authoring_offsets=True,real_edge_dimensions=True,added_geometry=0),
                saodg_schema5=False,game_verified=False)
    _json(layers/'delivery.json',report)
    _json(runtime/'parts.json',dict(format_version=2,kind='standalone_xyz_tiles',master_size=size,active_cells=cell_data,
                                  geometry_sha256=geometry,parts=part_records,runtime_parts=len(part_records),
                                  exact_reassembly=True,added_geometry=0,game_verified=False,saodg49_verified=False))
    verify_standalone(root)
    if master.blocks!=original or master.fingerprint()!=geometry:raise ValueError('Standalone source changed while slicing')
    return dict(delivery=report,actual_nbt_files=report['actual_nbt_files'],runtime_parts=len(part_records),
                runtime_files=runtime_files,runtime_templates=[dict(file=f,path=f,sha256=_sha(f)) for f in runtime_files],
                source_unchanged=True)
