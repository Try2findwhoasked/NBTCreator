"""Synthetic GUI backend contracts and approved application; no user asset approval."""
import argparse
import copy
import json
from pathlib import Path

from nbt_model import Model, ports
from nbt_refine import save_master, record_user_approval
from nbt_detail_control import (default_settings, compile_plan, export_plan, create_review,
                                apply_approved, inspect_source, digest, read_json, write_json, catalog, preview_effect)


def refuses(fn):
    try: fn()
    except (ValueError, FileExistsError, PermissionError, AssertionError, KeyError): return True
    return False


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    out=parser.parse_args().output.resolve();out.mkdir(parents=True)
    m=Model((48,16,48));m.box((0,0,0),(47,15,47),'stone_bricks');m.box((1,2,1),(46,13,46),'air')
    walls={p for p in m.blocks if 2<=p[1]<=13 and (p[0] in (0,47) or p[2] in (0,47))}
    m.check_sealed([(24,8,24)]);m.open_ports(ports(['west','east'],2),2)
    source=out/'基线 空格.master.json.gz';save_master(source,m,walls);original=digest(source)
    context=dict(cells=[[0,0]],door_y=2,ports=ports(['west','east'],2),start=[3.5,2,24],targets={'exit':[44.5,2,24]},
                 interior_probes=[[24,8,24]],cameras=[dict(role='whole',eye=[64,30,64],target=[24,5,24],cuts=[dict(axis='y',position=12,removed_side='above')]),
                                                  dict(role='entry',eye=[3.5,3.62,24],target=[24,4,24])])
    write_json(out/'context.json',context)
    settings=default_settings();settings['pattern']['enabled']=True;settings['pattern']['fraction']=.03
    request=dict(source=str(source),context=str(out/'context.json'),cameras='',review='',settings=settings)
    checks={}
    checks['default_modules_are_off']=not compile_plan(default_settings(),m.size)['operations']
    weighted=copy.deepcopy(settings);weighted['strength']=200
    plan=compile_plan(weighted,m.size)
    checks['overall_strength_scales_coverage_not_material_weights']=plan['operations'][0]['fraction']==.06 and plan['operations'][0]['palette']==settings['pattern']['palette']
    weighted['strength']=0
    checks['zero_strength_is_noop']=compile_plan(weighted,m.size)['operations']==[]
    invalid=copy.deepcopy(settings);invalid['pattern']['palette'][0]['state']='not_a_real_slab'
    checks['invalid_materials_rejected']=refuses(lambda:compile_plan(invalid,m.size))
    invalid=copy.deepcopy(settings);invalid['pattern']['fraction']=.75;invalid['strength']=200
    checks['coverage_overflow_is_not_silently_clamped']=refuses(lambda:compile_plan(invalid,m.size))
    checks['source_inspection_preserves_geometry']=inspect_source(source)['geometry_sha256']==m.fingerprint() and digest(source)==original
    exported=export_plan(request,out/'plan')
    checks['plan_exports_without_revised_asset']=exported['status']=='planned' and not list((out/'plan').glob('*.nbt')) and not list((out/'plan').glob('*.gz'))
    checks['no_fake_approval_from_planning']=not list((out/'plan').glob('approval.json'))
    checks['plan_has_estimates']=len(read_json(out/'plan/estimates.json')['estimates'])==1
    review=out/'review';create_review(request,review)
    checks['review_stops_before_confirmation']=not (review/'approval.json').exists()
    checks['apply_without_real_receipt_refused']=refuses(lambda:apply_approved(request,exported['bundle'],review,out/'unauthorized')) and not (out/'unauthorized').exists()
    # This receipt is exclusively for this synthetic test, never a user's model.
    record_user_approval(review,'SYNTHETIC FIXTURE ONLY: reviewed generated test thumbnails.',True)
    result=apply_approved(request,exported['bundle'],review,out/'revision')
    checks['approved_application_outputs_new_version']=result['changed_blocks']>0 and (out/'revision/comparison.png').is_file()
    checks['original_baseline_never_overwritten']=digest(source)==original
    altered=copy.deepcopy(request);altered['settings']['seed']=77
    checks['stale_settings_cannot_apply_old_bundle']=refuses(lambda:apply_approved(altered,exported['bundle'],review,out/'stale'))
    saved=(out/'plan/plan.json').read_bytes();modified=read_json(out/'plan/plan.json');modified['style_note']='changed'
    write_json(out/'plan/plan.json',modified)
    checks['changed_plan_is_refused']=refuses(lambda:apply_approved(request,exported['bundle'],review,out/'modified'))
    (out/'plan/plan.json').write_bytes(saved)
    checks['no_output_overwrite']=refuses(lambda:export_plan(request,out/'plan'))
    workspace=out/'catalog_workspace';root=workspace/'nbt_models'
    for index in range(205):
        target=root/f'r{index:03}_building'/'v01/runtime/parts/master_geometry.json.gz'
        target.parent.mkdir(parents=True);target.write_bytes(source.read_bytes())
    duplicate=root/'r000_building/v01/master/whole.master.json.gz';duplicate.parent.mkdir();duplicate.write_bytes(source.read_bytes())
    hidden=root/'route_validation/r999_synthetic/master_geometry.json.gz';hidden.parent.mkdir(parents=True);hidden.write_bytes(source.read_bytes())
    invalid=root/'r998_bad/master_geometry.json.gz';invalid.parent.mkdir(parents=True);invalid.write_bytes(b'not gzip')
    listing=catalog(workspace)
    checks['catalog_no_200_item_cutoff']=len(listing['models'])==205
    checks['catalog_deduplicates_same_building_geometry']=sum(item['name']=='r000_building' for item in listing['models'])==1
    checks['catalog_excludes_validation_and_invalid_models']=listing['skipped']==1 and not any('validation' in item['label'] for item in listing['models'])
    cached=catalog(workspace)
    checks['catalog_cache_reuses_unchanged_metadata']=cached['cache_hits']>=205
    rewritten=root/'r001_building/v01/runtime/parts/master_geometry.json.gz';rewritten.write_bytes(source.read_bytes())
    updated=catalog(workspace)
    checks['catalog_cache_invalidates_changed_file']=updated['cache_hits']<cached['cache_hits'] and len(updated['models'])==205
    empty_note=copy.deepcopy(settings);empty_note['style_note']=''
    checks['effect_note_is_optional']=bool(compile_plan(empty_note,m.size)['operations'])
    preview=preview_effect(request,out/'effect_preview')
    checks['live_preview_changes_only_snapshot']=preview['preview_only'] and preview['changed_blocks']>0 and digest(source)==original and not list((out/'effect_preview').glob('*.gz')) and not list((out/'effect_preview').glob('*.nbt'))
    checks['preview_not_an_approval']=not (out/'effect_preview/approval.json').exists()
    assert all(checks.values()),checks
    write_json(out/'results.json',dict(passed=True,checks=checks))
    print(json.dumps(dict(passed=True,checks=len(checks),report=str(out/'results.json'))))


if __name__=='__main__': main()
