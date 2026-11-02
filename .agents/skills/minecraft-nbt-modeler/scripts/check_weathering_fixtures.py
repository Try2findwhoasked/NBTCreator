"""Synthetic connected-weathering regression; never edits an existing asset.

Writes a new temporary fixture run under --output. Synthetic approval receipts
below apply exclusively to this generated regression room.
"""
import argparse
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from nbt_assembly import Volume
from nbt_collision import check_routes
from nbt_delivery import verify_delivery
from nbt_model import AIR_NAMES, state
from nbt_refine import (operation_candidates, prepare, protections, read_master,
                        record_user_approval, refine, save_master)
from nbt_weathering import components, neighbors, weathering_plan


def rejected(action):
    try:
        action()
    except (ValueError,PermissionError,FileExistsError,AssertionError):
        return True
    return False


def fixture():
    model=Volume((96,14,48));model.box((0,0,0),(95,13,47),'stone_bricks')
    model.box((2,4,2),(93,11,45),'air')
    walls={p for p in model.blocks if 4<=p[1]<=11}
    operation=dict(kind='weathering',label='Synthetic weathered masonry',classification='inherit',
        lo=[1,1,1],hi=[94,11,46],seed=2718,from_states=['stone_bricks'],
        moss=dict(fraction=.16,patch_size=[16,45]),
        cracks=dict(fraction=.14,length=[8,22],straightness=.86,branch_chance=.06),
        floor=dict(fraction=.055,levels=[3],slab_share=.6,patch_size=[3,7],pit_depth=1,rim_width=1))
    return model,walls,operation


def patched(model,edits):
    result=Volume(model.size);result.blocks=dict(model.blocks)
    for p,value in edits:
        result.put(p,value)
    return result


def diagnostic(model,operation,path):
    from PIL import Image,ImageDraw
    palette={'minecraft:stone_bricks':'#8b8a7f','minecraft:mossy_stone_bricks':'#49723d',
             'minecraft:cracked_stone_bricks':'#b86f48',
             state('stone_brick_slab[type=bottom,waterlogged=false]'):'#c3b397',
             'minecraft:air':'#222530'}
    image=Image.new('RGB',(96*9,48*9+136),'#14202b');draw=ImageDraw.Draw(image)
    draw.text((12,12),'SYNTHETIC WEATHERING | floor plan at block Y=3',fill='white')
    draw.text((12,32),'green: moss  orange: cracks  beige: lowered slab  dark: full-block pit',fill='white')
    draw.text((12,52),'Diagnostic colors, not Minecraft textures. Vertical line marks author cut X=48.',fill='white')
    for x in range(96):
        for z in range(48):
            v=model.get((x,3,z));color=palette.get(v,'#60646c')
            draw.rectangle((x*9,z*9+80,x*9+7,z*9+87),fill=color)
    draw.line((48*9-1,80,48*9-1,48*9+80),fill='#77bfff')
    # True whole-wall front elevation, without flattening multiple faces.
    for x in range(2,94):
        for y in range(4,12):
            v=model.get((x,y,1))
            draw.rectangle((x*9,(11-y)*5+48*9+88,x*9+7,(11-y)*5+48*9+91),fill=palette.get(v,'#60646c'))
    image.save(path)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path.cwd()/'nbt_models/_tests/weathering_validation')
    parser.add_argument('--skip-workflow',action='store_true',help='Only planner tests; no review/render/export regression')
    parser.add_argument('--hash-probe',action='store_true',help=argparse.SUPPRESS)
    args=parser.parse_args()
    model,walls,operation=fixture()
    if args.hash_probe:
        print(patched(model,weathering_plan(model,operation)[0]).fingerprint())
        return
    root=args.output.resolve();root.mkdir(parents=True,exist_ok=True)
    out=Path(tempfile.mkdtemp(prefix='synthetic_',dir=root));checks={}
    original=model.fingerprint();edits,report=weathering_plan(model,operation)
    revised=patched(model,edits)
    checks['planner_does_not_mutate_source']=model.fingerprint()==original
    checks['same_seed_same_plan']=weathering_plan(model,operation)==(edits,report)
    alternate=copy.deepcopy(operation);alternate['seed']+=1
    checks['different_seed_changes_pattern']=weathering_plan(model,alternate)[0]!=edits
    probes=[]
    for hash_seed in ('1','23'):
        env=dict(os.environ,PYTHONHASHSEED=hash_seed)
        probes.append(subprocess.check_output([sys.executable,__file__,'--hash-probe'],env=env,text=True).strip())
    checks['cross_process_hash_seed_independent']=probes==[revised.fingerprint()]*2
    reverse=Volume(model.size);reverse.blocks=dict(reversed(list(model.blocks.items())))
    checks['source_iteration_order_independent']=weathering_plan(reverse,operation)==(edits,report)
    checks['unified_dispatch']=operation_candidates(model,operation)==edits
    moss={p for p,v in edits if v=='minecraft:mossy_stone_bricks'}
    crack={p for p,v in edits if v=='minecraft:cracked_stone_bricks'}
    slab={p for p,v in edits if '_slab[' in v}
    pits={p for p,v in edits if v in AIR_NAMES}
    checks['all_four_results_present']=all((moss,crack,slab,pits))
    checks['moss_has_no_singletons']=min(map(len,components(moss)))>=operation['moss']['patch_size'][0]
    checks['cracks_have_no_singletons']=all(any(q in crack for q in neighbors(p)) for p in crack)
    checks['combined_effect_includes_free_crack_extensions']=report['cracks']['extended_blocks']>0
    checks['floor_damage_is_grouped']=all(any(q in slab|pits for q in neighbors(p,True)) for p in slab|pits)
    checks['moss_budget_within_one_group_without_scatter']=0<=report['moss']['shortfall']<operation['moss']['patch_size'][0]
    checks['floor_budget_within_one_group']=0<=report['floor']['shortfall']<operation['floor']['patch_size'][0]*2
    checks['surface_crack_budget_or_required_rim']=report['cracks']['shortfall']<operation['cracks']['length'][0]
    checks['slabs_lower_surface_half_block']=all(revised.get(p)==state('stone_brick_slab[type=bottom,waterlogged=false]') for p in slab)
    checks['pit_bottom_not_removed']=all(revised.get((p[0],p[1]-1,p[2]))=='minecraft:stone_bricks' for p in pits)
    checks['damaged_floor_has_cracked_rim']=all(revised.get(q)=='minecraft:cracked_stone_bricks'
        for p in slab|pits for q in neighbors(p,True) if q not in slab|pits)
    checks['all_writes_inside_box']=all(all(operation['lo'][i]<=p[i]<=operation['hi'][i] for i in range(3)) for p,v in edits)
    checks['effects_cross_author_cut']=any(p[0]==47 and (48,p[1],p[2]) in moss for p in moss)
    # No features enabled means no edits, including no mandatory rim.
    zero=copy.deepcopy(operation)
    for key in ('moss','cracks','floor'):zero[key]['fraction']=0
    checks['zero_ratios_no_edits']=weathering_plan(model,zero)[0]==[]
    high=copy.deepcopy(zero);high['moss']['fraction']=.7
    low=copy.deepcopy(high);low['moss']['fraction']=.07
    checks['fraction_controls_actual_coverage']=len(weathering_plan(model,high)[0])>len(weathering_plan(model,low)[0])*5
    # Dedicated wall makes a long nonbranching crack: connectivity and straight
    # segments must survive, rather than only comparing a seed to itself.
    wall=Volume((96,14,48));wall.box((2,2,20),(93,11,20),'stone_bricks')
    linear=copy.deepcopy(zero);linear['cracks'].update(fraction=.15,length=[20,30],straightness=1,branch_chance=0)
    wall_edits,wall_report=weathering_plan(wall,linear)
    wall_points={p for p,v in wall_edits}
    straight=sum((x+1,y,z) in wall_points and (x+2,y,z) in wall_points or
                 (x,y+1,z) in wall_points and (x,y+2,z) in wall_points for x,y,z in wall_points)
    checks['cracks_form_long_contiguous_runs']=bool(wall_points) and min(map(len,components(wall_points)))>=20 and straight>len(wall_points)*.5
    # Thin floor is not dug through; a missing side seal also forbids a pit.
    thin=Volume((96,14,48));thin.box((1,3,1),(94,3,46),'stone_bricks')
    damage=copy.deepcopy(zero);damage['floor'].update(fraction=.2,slab_share=0)
    checks['thin_floor_not_excavated']=weathering_plan(thin,damage)[0]==[]
    cavity=copy.deepcopy(model);cavity.box((0,2,0),(95,2,47),'air')
    checks['underfloor_open_cavity_not_breached']=weathering_plan(cavity,damage)[0]==[]
    # A bounded existing cavity can be exposed if its full bottom and sides fit.
    pocket=copy.deepcopy(model);pocket.box((35,2,20),(36,2,20),'air')
    pocket_op=copy.deepcopy(damage);pocket_op.update(lo=[34,1,19],hi=[37,6,21])
    pocket_op['floor'].update(fraction=1,patch_size=[2,2],pit_depth=2)
    pocket_edits,_=weathering_plan(pocket,pocket_op)
    checks['bounded_existing_pocket_supported']=any(p[1]==3 and v in AIR_NAMES for p,v in pocket_edits)
    checks['already_empty_pocket_not_counted_as_change']=all(pocket.get(p)!=v for p,v in pocket_edits)
    deep=copy.deepcopy(damage);deep['floor']['pit_depth']=2
    deep_edits,_=weathering_plan(model,deep)
    deep_result=patched(model,deep_edits)
    deep_columns={p for p,v in deep_edits if p[1]==3 and v in AIR_NAMES}
    checks['pit_depth_two_retains_bottom']=bool(deep_columns) and all(
        deep_result.get((p[0],1,p[2]))=='minecraft:stone_bricks' and
        deep_result.get((p[0],2,p[2])) in AIR_NAMES and deep_result.get(p) in AIR_NAMES for p in deep_columns)
    protected={(x,y,z) for x in range(44,52) for y in range(0,14) for z in range(48)}
    protected_edits,_=weathering_plan(model,operation,protected)
    checks['protected_route_and_support_unchanged']=not ({p for p,v in protected_edits}&protected)
    below=copy.deepcopy(damage);below['floor']['pit_depth']=2
    below_protected={(x,2,z) for x in range(96) for z in range(48)}
    checks['protected_buried_voxels_prevent_excavation']=weathering_plan(model,below,below_protected)[0]==[]
    isolated=Volume((96,14,48))
    for x in range(3,90,3):isolated.put((x,6,20),'stone_bricks')
    isolated_op=copy.deepcopy(high)
    checks['no_singleton_fallback_on_disconnected_input']=weathering_plan(isolated,isolated_op)[0]==[]
    failures=[]
    for field,value in [('fraction',-1),('fraction',float('nan')),('patch_size',[1,5]),('fraction',True)]:
        bad=copy.deepcopy(operation);bad['moss'][field]=value
        failures.append(rejected(lambda:weathering_plan(model,bad)))
    for change in [dict(from_states=['stone_brick_stairs']),dict(lo=[-1,1,1]),dict(seed='seed'),dict(floor={'fraction':.1}),
                   dict(floor={'fraction':.1,'levels':[3],'slab_state':'cracked_stone_brick_slab[type=bottom,waterlogged=false]'}),
                   dict(moss={'state':'air'}),dict(moss={'fractions':.1})]:
        bad=copy.deepcopy(operation);bad.update(change)
        failures.append(rejected(lambda:weathering_plan(model,bad)))
    checks['invalid_ratios_materials_bounds_and_floor_config_rejected']=all(failures)
    # Repaint only the explicit source family, leave stateful detail intact.
    decorated=copy.deepcopy(model);decorated.put((20,3,20),'chiseled_stone_bricks')
    decorated.put((21,3,20),'stone_brick_stairs[facing=east,half=bottom,shape=straight,waterlogged=false]')
    detail_edits,_=weathering_plan(decorated,operation)
    checks['other_materials_and_stair_states_preserved']=not ({(20,3,20),(21,3,20)}&{p for p,v in detail_edits})
    diagnostic(revised,operation,out/'weathering_diagnostic.png')
    save_master(out/'synthetic.master.json.gz',model,walls)
    save_master(out/'weathered.master.json.gz',revised,walls-{p for p,v in edits if v in AIR_NAMES})
    workflow=None
    if not args.skip_workflow:
        source=out/'synthetic.master.json.gz';source_bytes=source.read_bytes()
        routes=check_routes(model,(5.5,4,24.5),{'exit':(89.5,4,24.5)})
        config=dict(cells=[[0,0],[1,0]],door_y=4,ports=[],interior_probes=[[12,7,12],[78,7,12]],
            start=[5.5,4,24.5],targets={'exit':[89.5,4,24.5]},
            protected_paths=[routes['targets'][0]['path']],max_changed_blocks=4000,
            cameras=[dict(role='whole',eye=[112,66,-30],target=[48,6,24],cuts=[['y',11,'above']]),
                     dict(role='entry',eye=[5.5,5.62,24.5],target=[30,4,28])])
        review=out/'review';prepare(source,config,review)
        plan=dict(style_note='Synthetic fixture: clustered moss, connected cracks and bounded floor decay.',operations=[operation])
        checks['unapproved_weathering_rejected']=rejected(lambda:refine(review,plan,out/'unapproved')) and not (out/'unapproved').exists()
        record_user_approval(review,'SYNTHETIC FIXTURE ONLY: reviewed generated regression thumbnails.',True)
        operation_path=out/'operation.json';operation_path.write_text(json.dumps(operation),encoding='utf8')
        command=[sys.executable,str(Path(__file__).with_name('nbt_weathering.py')),'--review',str(review),
                 '--operation',str(operation_path),'--output',str(out/'revision'),'--style-note',plan['style_note']]
        subprocess.run(command,check=True,capture_output=True,text=True)
        workflow=json.loads((out/'revision/refinement.json').read_text(encoding='utf8'))
        final,final_walls=read_master(out/'revision/refined.master.json.gz')
        expected_edits,expected_report=weathering_plan(model,operation,protections(model,config))
        checks['cli_runs_full_review_validation_export']=workflow['validation_passed'] and verify_delivery(out/'revision/delivery')['actual_nbt_files']==4
        checks['workflow_uses_protections_and_reports_ratios']=final.blocks==patched(model,expected_edits).blocks and workflow['operations'][0]['weathering']==expected_report
        checks['wall_layer_membership_preserved']=final_walls==walls-{p for p,v in expected_edits if v in AIR_NAMES}
        checks['original_file_unchanged']=source.read_bytes()==source_bytes
        checks['cannot_overwrite_revision']=subprocess.run(command,capture_output=True).returncode!=0
        bad=copy.deepcopy(plan);bad['operations'][0]['moss']['fraction']=1
        budget_config=json.loads((review/'config.json').read_text(encoding='utf8'))
        # A fresh synthetic review binds the smaller budget, rather than editing
        # an already-approved configuration and accidentally testing hash checks.
        budget_config['max_changed_blocks']=1
        budget_review=out/'budget_review';prepare(source,budget_config,budget_review)
        record_user_approval(budget_review,'SYNTHETIC FIXTURE ONLY: reviewed budget regression.',True)
        checks['weathering_budget_enforced']=rejected(lambda:refine(budget_review,bad,out/'overbudget')) and not (out/'overbudget').exists()
    result=dict(passed=all(checks.values()),checks=checks,fixture_only=True,planner_report=report,
                output=str(out),workflow_tested=not args.skip_workflow,runtime_verified=False)
    (out/'results.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
    print(json.dumps(dict(passed=result['passed'],checks=len(checks),failed=[k for k,v in checks.items() if not v],
                          report=str(out/'results.json')),ensure_ascii=False))
    if not result['passed']:
        raise AssertionError({k:v for k,v in checks.items() if not v})


if __name__=='__main__':
    main()
