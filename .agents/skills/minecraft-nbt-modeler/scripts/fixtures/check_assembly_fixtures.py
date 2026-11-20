"""Real-part/49-stride regressions, including sparse missing-cell protection."""
from pathlib import Path
import argparse,json
from nbt_assembly import LogicalAssembly,Volume,assemble,expand
from nbt_collision import check_routes


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path.cwd()/'nbt_models/_tests/assembly_validation')
    out=parser.parse_args().output.resolve();out.mkdir(parents=True,exist_ok=True)
    h=10;m=LogicalAssembly([(0,0),(1,0),(0,1)],24);checks={}
    for cx,cz in m.cells:
        m.box((48*cx,0,48*cz),(48*cx+47,23,48*cz+47),'stone_bricks')
        m.box((48*cx+1,h,48*cz+1),(48*cx+46,22,48*cz+46),'air')
    try:m.put((70,10,70),'air')
    except AssertionError:checks['sparse_missing_cell_write_rejected']=True
    else:checks['sparse_missing_cell_write_rejected']=False
    m.box((47,h,21),(48,h+4,26),'air');m.box((21,h,47),(26,h+4,48),'air')
    sealed=m.check_sealed([(24,h,24),(72,h,24),(24,h,72)])
    checks['whole_logical_envelope_sealed']=sealed['passed']
    definitions=[dict(id='west',facing='west',min=[0,h,21],max=[0,h+4,26]),
                 dict(id='east',facing='east',min=[95,h,21],max=[95,h+4,26]),
                 dict(id='south',facing='south',min=[21,h,95],max=[26,h+4,95])]
    internal=dict(id='bad',facing='east',min=[47,h,21],max=[47,h+4,26])
    try:m.open_external_ports([internal],h)
    except AssertionError:checks['internal_seam_as_external_port_rejected']=True
    else:checks['internal_seam_as_external_port_rejected']=False
    m.open_external_ports(definitions,h)
    parts=m.export_parts(out/'parts','saodg:assembly_fixture')
    v,placement=assemble(parts,24,h)
    checks['three_bounded_parts_no_missing_corner']=len(parts)==3 and len(placement['internal_connectors'])==2
    checks['physical_bounds_97']=v.size==(97,24,97)
    checks['expand_marker_48_to_49']=expand((72.5,10,24.5))==(73.5,10,24.5)
    checks['gap_air_and_floor']=v.get((48,h,24))=='minecraft:air' and v.get((48,h-1,24))=='minecraft:stone_bricks'
    checks['gap_roof_and_side']=v.get((48,h+5,24))=='minecraft:stone_bricks' and v.get((48,h,20))=='minecraft:stone_bricks'
    checks['missing_corner_remains_unwritten']=v.get((70,10,70))=='minecraft:air'
    capped=Volume(v.size);capped.blocks=dict(v.blocks)
    for port in definitions:
        lo,hi=port['min'],port['max']
        for x in range(lo[0],hi[0]+1):
            for z in range(lo[2],hi[2]+1):
                for y in range(h,h+5):capped.put(expand((x,y,z)),'stone')
    probes=[expand(p) for p in [(24,h,24),(72,h,24),(24,h,72)]]
    checks['assembled_envelope_resealed']=capped.check_sealed(probes)['passed']
    capped.begin_redesign();capped.put((47,h+8,24),'air')
    try:capped.check_sealed(probes)
    except AssertionError:checks['unsupported_upper_seam_aperture_leaks']=True
    else:checks['unsupported_upper_seam_aperture_leaks']=False
    routes=check_routes(v,(5.5,h,24.5),{'east':(90.5,h,24.5),'south':(24.5,h,90.5)})
    checks['actual_49_stride_two_connections']=routes['passed']
    try:v.save(out/'invalid_giant.nbt')
    except ValueError:checks['giant_diagnostic_nbt_export_rejected']=True
    else:checks['giant_diagnostic_nbt_export_rejected']=False
    # A one-cell gap with no bridge is a real floor discontinuity, not a harmless offset.
    unbridged,_=assemble(parts,24,h,bridges=False)
    checks['unbridged_49_stride_rejected']=not check_routes(unbridged,(5.5,h,24.5),{'east':(90.5,h,24.5)})['passed']
    # Proof must come from files, not an idealized author mesh: obstruct the bridge in a copy.
    for y in range(h,h+5):
        for z in range(21,27):v.put((48,y,z),'stone')
    checks['blocked_actual_connector_rejected']=not check_routes(v,(5.5,h,24.5),{'east':(90.5,h,24.5)})['passed']
    assert all(checks.values()),checks
    (out/'results.json').write_text(json.dumps(dict(passed=True,checks=checks,placement=placement,routes=routes),indent=2)+'\n')
    print(json.dumps(dict(passed=True,checks=len(checks),report=str(out/'results.json'))))


if __name__=='__main__':main()
