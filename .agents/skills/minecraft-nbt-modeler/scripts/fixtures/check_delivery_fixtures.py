"""Exact 2N authoring deliveries for single, long and sparse footprints."""
import argparse,json
from pathlib import Path
from nbt_assembly import Volume
from nbt_delivery import export_delivery,verify_delivery


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,default=Path.cwd()/'nbt_models/_tests/delivery_validation')
    out=p.parse_args().output.resolve();checks={}
    for name,cells in [('single',[(0,0)]),('long',[(0,0),(0,1),(0,2)]),('l_shape',[(0,0),(1,0),(0,1)]),
                       ('dated_single',[(0,0)]),('dated_l_shape',[(0,0),(1,0),(0,1)])]:
        prefix='2026-10-31_r001_' if name.startswith('dated_') else ''
        m=Volume((48*(1+max(c[0] for c in cells)),12,48*(1+max(c[1] for c in cells))))
        walls=set();probes=[]
        for cx,cz in cells:
            m.box((48*cx,0,48*cz),(48*cx+47,11,48*cz+47),'stone')
            m.box((48*cx+1,2,48*cz+1),(48*cx+46,9,48*cz+46),'air')
            walls.update((48*cx,y,48*cz+z) for y in range(2,10) for z in range(48))
            probes.append((48*cx+12,3,48*cz+12))
        m.check_sealed(probes)
        d=out/name;r=export_delivery(m,cells,walls,d,'Explicit wall face for file-count fixture',file_prefix=prefix)
        checks[name+'_2N_files']=r['actual_nbt_files']==2*len(cells)
        checks[name+'_roundtrip']=verify_delivery(d)['exact_solid_reconstruction']
        # A duplicated full template must fail, rather than be counted as another part.
        extra=d/'extra_full.nbt';extra.write_bytes((d/f'{prefix}p00_body.nbt').read_bytes())
        try:verify_delivery(d)
        except AssertionError:checks[name+'_extra_rejected']=True
        else:checks[name+'_extra_rejected']=False
        extra.unlink()  # Exact known temporary fixture, not recursive cleanup.
        bad=d/f'{prefix}p00_walls.nbt';original=bad.read_bytes();bad.write_bytes(original+b'corruption')
        try:verify_delivery(d)
        except AssertionError:checks[name+'_tamper_rejected']=True
        else:checks[name+'_tamper_rejected']=False
        bad.write_bytes(original)
        if prefix:
            checks[name+'_date_names']=all(p.name.startswith(prefix) for p in d.glob('*.nbt'))
        else:
            # Old manifests predate the prefix field and must still verify.
            manifest=d/'delivery.json';saved=manifest.read_text(encoding='utf8')
            legacy=json.loads(saved);legacy.pop('file_prefix',None)
            manifest.write_text(json.dumps(legacy),encoding='utf8')
            checks[name+'_legacy_manifest']=verify_delivery(d)['exact_solid_reconstruction']
            manifest.write_text(saved,encoding='utf8')
    for index,prefix in enumerate(('../escape_','folder/name_','C:\\escape_',None)):
        try:export_delivery(m,cells,walls,out/f'invalid_prefix_{index}','Invalid prefix fixture',file_prefix=prefix)
        except ValueError:checks[f'invalid_prefix_{index}_rejected']=not (out/f'invalid_prefix_{index}').exists()
        else:checks[f'invalid_prefix_{index}_rejected']=False
    checks['l_missing_cell_not_exported']=not (out/'l_shape/p11_body.nbt').exists()
    assert all(checks.values()),checks
    (out/'results.json').write_text(json.dumps(dict(passed=True,checks=checks),indent=2)+'\n')
    print(json.dumps(dict(passed=True,checks=len(checks),report=str(out/'results.json'))))


if __name__=='__main__':main()
