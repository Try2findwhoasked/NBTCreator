"""Synthetic contracts for website structure tools; no user asset writes."""
import argparse
from pathlib import Path
from copy import deepcopy
from nbt_model import Model
from nbt_refine import save_master, operation_candidates
from nbt_detail_control import default_settings, compile_plan, preview_effect, write_json, read_json, digest

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);out=parser.parse_args().output.resolve();out.mkdir(parents=True,exist_ok=False)
    model=Model((48,16,48));model.put((8,3,8),'oak_stairs[facing=west]');model.put((9,3,8),'stone_bricks')
    source=out/'synthetic.master.json.gz';save_master(source,model,{(8,3,8)});before=digest(source)
    context=out/'context.json';write_json(context,dict(start=[3.5,2,3.5],targets={'exit':[4.5,2,3.5]},interior_probes=[[3,3,3]],ports=[]))
    settings=default_settings();settings['replace']=dict(enabled=True,from_states=['stone_bricks'],state='andesite',scope='volume')
    request=dict(source=str(source),source_sha256=before,context=str(context),settings=settings)
    checks={}
    result=preview_effect(request,out/'replacement');after=read_json(result['snapshot']);lookup={tuple(p):value for p,value in after['blocks']}
    checks['precise_replace_uses_selected_source_only']=lookup[(9,3,8)]=='minecraft:andesite' and 'facing=west' in lookup[(8,3,8)]
    settings=default_settings();settings.update(whole_region=False,lo=[8,3,8],hi=[8,3,8]);settings['structure'].update(enabled=True,mode='move',offset=[2,0,0])
    result=preview_effect(dict(request,settings=settings),out/'moved');after=read_json(result['snapshot']);lookup={tuple(p):value for p,value in after['blocks']}
    checks['moving_preserves_state_and_wall_membership']='facing=west' in lookup[(10,3,8)] and [10,3,8] in after['wall_positions'] and [8,3,8] not in after['wall_positions']
    checks['moving_removes_original_block']=(8,3,8) not in lookup or lookup[(8,3,8)]=='minecraft:air'
    collision=deepcopy(model);collision.put((10,3,8),'stone')
    try:operation_candidates(collision,compile_plan(settings,model.size)['operations'][0]);checks['occupied_target_refused_without_mutation']=False
    except ValueError:checks['occupied_target_refused_without_mutation']='facing=west' in collision.get((8,3,8)) and collision.get((10,3,8))=='minecraft:stone'
    settings['structure'].update(mode='fill',state='andesite');write_json(context,dict(start=[3.5,2,3.5],targets={'exit':[4.5,2,3.5]},interior_probes=[[3,3,3]],protected_boxes=[dict(lo=[8,3,8],hi=[8,3,8])]))
    try:preview_effect(dict(request,settings=settings),out/'protected');checks['protected_region_refused']=False
    except ValueError:checks['protected_region_refused']=not (out/'protected').exists()
    settings.update(whole_region=True)
    try:compile_plan(settings,model.size);checks['structure_requires_explicit_local_region']=False
    except ValueError:checks['structure_requires_explicit_local_region']=True
    settings.update(whole_region=False,lo=[6,2,6],hi=[10,6,10]);settings['structure'].update(mode='hollow',thickness=1)
    edits=dict(operation_candidates(model,compile_plan(settings,model.size)['operations'][0]));checks['hollow_keeps_shell_and_clears_inside']=edits[(6,2,6)]=='minecraft:andesite' and edits[(8,3,8)]=='minecraft:air'
    settings['structure']['mode']='carve';checks['carve_produces_air']=all(value=='minecraft:air' for _,value in operation_candidates(model,compile_plan(settings,model.size)['operations'][0]))
    for mode,count in [('floor',25),('ceiling',25),('walls',80),('frame',44)]:
        settings['structure'].update(mode=mode,thickness=1)
        plan=compile_plan(settings,model.size)
        changes=[(p,v) for op in plan['operations'] for p,v in operation_candidates(model,op)]
        positions=[tuple(p) for p,_ in changes]
        checks[mode+'_unique_geometry']=len(positions)==count and len(set(positions))==count and (8,4,8) not in positions
        settings['structure']['thickness']=0
        try:compile_plan(settings,model.size);checks[mode+'_invalid_thickness']=False
        except ValueError:checks[mode+'_invalid_thickness']=True
    checks['source_unchanged_and_no_approval']=digest(source)==before and not list(out.rglob('approval.json'))
    assert all(checks.values()),checks
    write_json(out/'results.json',dict(passed=True,checks=checks));print(dict(passed=True,checks=len(checks)))

if __name__=='__main__':main()
