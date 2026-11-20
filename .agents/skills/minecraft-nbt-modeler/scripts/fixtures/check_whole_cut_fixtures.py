"""Whole-first cut/reassembly, wall splitting and 48-versus49 distinction."""
import argparse,gzip,json
from pathlib import Path
from nbt_assembly import Volume,assemble
from nbt_whole_cut import open_master_ports,slice_master,reassemble_contiguous
from nbt_model import load
from nbt_collision import check_routes


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,default=Path.cwd()/'nbt_models/_tests/whole_cut_validation')
    out=p.parse_args().output.resolve()
    master=Volume((96,16,48))
    # One global envelope and void; no cell-local geometry construction.
    master.box((0,0,0),(95,15,47),'stone_bricks')
    master.box((1,2,1),(94,13,46),'air')
    master.put((47,2,10),'stone_slab[type=bottom,waterlogged=false]')
    walls={p for p in master.blocks if p[1] not in (0,1,15) and (p[0] in (0,95) or p[2] in (0,47))}
    master.check_sealed([(12,2,12),(72,2,12)])
    definitions=[dict(id='west',facing='west',min=[0,2,21],max=[0,6,26]),dict(id='east',facing='east',min=[95,2,21],max=[95,6,26])]
    open_master_ports(master,definitions,2)
    frozen=dict(master.blocks)
    parts,report=slice_master(master,out,'saodg:whole_fixture',walls)
    actual,placement=reassemble_contiguous(parts,16)
    checks=dict(two_bounded_parts=len(parts)==2,exact_contiguous_reconstruction=actual.blocks==frozen,
                source_master_unchanged=master.blocks==frozen,
                no_cut_partition_wall=actual.get((48,4,12))=='minecraft:air',
                states_cross_cut_preserved=load(parts[0]['file']).get((47,2,10))==master.get((47,2,10)),
                global_wall_mask_cut=len(report['layers'])==2 and all(v['reconstructed_on_empty_volume_matches_source'] for v in report['layers']))
    saved=json.loads(gzip.decompress(Path(report['master']).read_bytes()))
    decoded={tuple(p):v for p,v in saved['blocks']}
    checks['complete_master_saved_before_parts']=decoded==frozen and saved['geometry_sha256']==master.fingerprint()
    dated_parts,dated_report=slice_master(master,out/'dated','saodg:dated_fixture',walls,
                                        file_prefix='2026-10-31_r002_')
    dated_actual,_=reassemble_contiguous(dated_parts,16)
    checks['dated_full_parts_reconstruct']=dated_actual.blocks==frozen
    checks['dated_full_and_delivery_names']=all(Path(v['file']).name.startswith('2026-10-31_r002_') for v in dated_parts) and (
        dated_report['delivery']['file_prefix']=='2026-10-31_r002_' and
        all(p.name.startswith('2026-10-31_r002_') for p in (out/'dated/delivery').glob('*.nbt')))
    # Restrict traversal to the authored non-central route; no detour to engine port.
    physical,_=assemble(parts,16,2)
    for model in (actual,physical):
        for x in range(model.size[0]):
            for y in range(16):model.put((x,y,16),'stone')
    checks['continuous_48_noncentral_crossing']=check_routes(actual,(10.5,2,10.5),[(85.5,2,10.5)])['passed']
    checks['49_not_falsely_claimed_compatible']=not check_routes(physical,(10.5,2,10.5),[(86.5,2,10.5)])['passed']
    assert all(checks.values()),checks
    (out/'results.json').write_text(json.dumps(dict(passed=True,checks=checks,manifest=report),indent=2)+'\n')
    print(json.dumps(dict(passed=True,checks=len(checks),report=str(out/'results.json'))))


if __name__=='__main__':main()
