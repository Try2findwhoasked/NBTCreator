"""Geometry-field regressions, not a room template. Outputs only to --output."""
import argparse
import json
from pathlib import Path
import numpy as np
from nbt_fields import Grid, bezier, union, difference, intersection, smooth_union, apply_mask, connectivity, air_components
from nbt_model import Model, load


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path.cwd()/'nbt_models/_tests/field_validation')
    out=parser.parse_args().output.resolve();out.mkdir(parents=True,exist_ok=True)
    g=Grid((48,32,48));checks={}
    a=g.ellipsoid((12.5,12.5,12.5),(6,6,5))
    b=g.ellipsoid((33.5,18.5,30.5),(6,8,6))
    path=bezier([(12.5,12.5,12.5),(14,7,31),(28,24,14),(33.5,18.5,30.5)],48)
    tunnel=g.tube(path,np.linspace(2.5,3.5,len(path)))
    interior=g.mask(union(a,b,tunnel),boundary_margin=2)
    joined=connectivity(interior,[(12,12,12),(33,18,30)])
    checks['curved_multichamber_connected']=joined['passed'] and joined['all_selected_cells_connected']
    isolated=g.mask(union(a,b))
    checks['unlinked_chambers_detected']=not connectivity(isolated,[(12,12,12),(33,18,30)])['passed']
    checks['csg_commutative']=np.array_equal(g.mask(union(a,b)),g.mask(union(b,a)))
    checks['difference_excludes_subtraction']=not np.any(g.mask(difference(a,b)) & (b<0))
    checks['intersection_subset']=np.all(~g.mask(intersection(a,b)) | (g.mask(a)&g.mask(b)))
    angle=np.pi/4;rot=np.array([[np.cos(angle),0,np.sin(angle)],[0,1,0],[-np.sin(angle),0,np.cos(angle)]])
    elongated=g.mask(g.ellipsoid((24,16,24),(14,6,4)))
    rotated=g.mask(g.ellipsoid((24,16,24),(14,6,4),rot))
    checks['rotated_ellipsoid_changes_geometry']=not np.array_equal(elongated,rotated) and abs(int(elongated.sum())-int(rotated.sum()))<70
    ring=g.mask(g.torus((24,16,24),11,3))
    checks['torus_has_centre_void']=not ring[24,16,24] and ring[34,16,24]
    poly=g.mask(g.extruded_polygon([(5,5),(28,5),(28,12),(12,12),(12,29),(5,29)],3,10))
    checks['concave_extrusion_preserves_notch']=bool(poly[8,5,20] and poly[20,5,8] and not poly[20,5,20])
    w1=g.warped(1.5,15,9).ellipsoid((24,16,24),(12,9,15))
    w2=g.warped(1.5,15,9).ellipsoid((24,16,24),(12,9,15))
    checks['warp_reproducible']=np.array_equal(w1,w2)
    checks['smooth_blend_contains_inputs']=np.all(smooth_union(a,b,3)<=union(a,b)+1e-8)
    m=Model(g.size);m.box((0,0,0),(47,31,47),'stone')
    apply_mask(m,interior,'air')
    sealed=m.check_sealed([(12,12,12),(33,18,30)])
    disk=m.save(out/'curved_connectivity_fixture.nbt')
    checks['carved_cave_sealed_before_ports']=sealed['passed']
    checks['field_geometry_nbt_roundtrip']=load(out/'curved_connectivity_fixture.nbt').blocks==m.blocks
    checks['envelope_margin_preserved']=not any(interior[0,:,:].flat) and not any(interior[:,-1,:].flat)
    # Air around a non-box outer shell is valid; it must not reach the interior.
    small=Grid((12,12,12));shell=Model(small.size)
    apply_mask(shell,small.mask(difference(small.ellipsoid((6,6,6),(5,5,5)),
                                         small.ellipsoid((6,6,6),(3,3,3)))),'calcite')
    checks['nonbox_shell_has_exterior_air']=shell.get((0,0,0))=='minecraft:air'
    checks['nonbox_shell_interior_sealed']=shell.check_sealed([(6,6,6)])['passed']
    inventory=air_components(shell,[(6,6,6)])
    checks['exterior_air_not_false_leak']=not inventory['leaking_design_probes'] and any(c['touches_exterior'] for c in inventory['components'])
    shell.save(out/'nonbox_shell_fixture.nbt')
    shell.begin_redesign()
    shell.box((6,6,8),(6,6,11),'air')
    try:
        shell.check_sealed([(6,6,6)])
    except AssertionError:
        checks['nonbox_shell_breach_detected']=True
    else:
        checks['nonbox_shell_breach_detected']=False
    bubbles=Model((12,12,12));bubbles.box((0,0,0),(11,11,11),'stone')
    bubbles.box((2,2,2),(5,5,5),'air');bubbles.put((9,9,9),'air')
    inventory=air_components(bubbles,[(3,3,3)])
    checks['unprobed_microbubble_reported']=len(inventory['undeclared_enclosed_components'])==1 and inventory['undeclared_enclosed_components'][0]['cells']==1
    checks={name:bool(value) for name,value in checks.items()}
    assert all(checks.values()),checks
    report=dict(passed=True,checks=checks,interior_topology=joined,nbt=disk,
                caveat='Synthetic geometry fixture only; no walking or artistic acceptance claimed.')
    (out/'results.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print(json.dumps(dict(passed=True,checks=len(checks),report=str(out/'results.json'))))


if __name__=='__main__':main()
