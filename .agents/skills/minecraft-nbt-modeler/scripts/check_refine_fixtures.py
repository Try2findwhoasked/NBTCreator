"""Synthetic refinement workflow tests; does NOT approve any user's real model.

All receipt text below is explicitly synthetic test data. Output stays in a new
fixture run under --output. No existing generated model or world is modified.
"""
import argparse
import copy
import json
from pathlib import Path
import tempfile

from nbt_assembly import Volume
from nbt_collision import check_routes
from nbt_refine import prepare,record_user_approval,refine,save_master,read_master,operation_candidates
from nbt_delivery import verify_delivery


def rejected(action,types=(ValueError,PermissionError,FileExistsError,AssertionError)):
    try:action()
    except types:return True
    return False


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path.cwd()/'nbt_models/_tests/refine_validation')
    root=parser.parse_args().output.resolve();root.mkdir(parents=True,exist_ok=True)
    out=Path(tempfile.mkdtemp(prefix='synthetic_',dir=root));checks={}
    m=Volume((48,16,144));m.box((0,0,0),(47,15,143),'stone_bricks')
    m.box((2,4,2),(45,13,141),'air')
    for z in (1,142):m.box((21,4,z),(26,8,z),'air')
    walls={p for p in m.blocks if 4<=p[1]<=13 and (p[0] in (0,1,46,47) or p[2] in (0,1,142,143))}
    for z in (0,143):m.box((21,4,z),(26,8,z),'air')
    source=out/'whole.master.json.gz';save_master(source,m,walls);source_bytes=source.read_bytes()
    routes=check_routes(m,(23.5,4,3.5),{'exit':(23.5,4,140.5)})
    config=dict(cells=[[0,0],[0,1],[0,2]],door_y=4,
        ports=[dict(id='north',facing='north',min=[21,4,0],max=[26,8,0]),
               dict(id='south',facing='south',min=[21,4,143],max=[26,8,143])],
        start=[23.5,4,3.5],targets={'exit':[23.5,4,140.5]},interior_probes=[[12,8,12],[24,8,72],[24,8,120]],
        protected_boxes=[dict(lo=[10,4,60],hi=[13,8,63])],
        protected_paths=[routes['targets'][0]['path']],max_changed_blocks=512,
        cameras=[dict(role='whole',eye=[78,50,-20],target=[24,8,70],cuts=[['x',42,'above'],['y',13,'above']]),
                 dict(role='entry',eye=[23.5,5.62,3.5],target=[15,7,28]),
                 dict(role='detail',eye=[10.5,9,57.5],target=[1,8.5,48])])
    plan=dict(style_note='One restrained masonry language across the complete long building; shared trim and stone palette.',
        operations=[dict(label='Synthetic supported cylinder in whole-source coordinates',kind='geometry',lo=[5,4,10],hi=[8,6,13],geometry=dict(shape='cylinder',centre=[7,5.5,12],radius=1.5,height=3),state='stone_bricks',classification='body'),
                    dict(label='Continuous west-wall inset frame straddling the storage cut',kind='frame',lo=[1,6,42],hi=[1,11,54],state='chiseled_stone_bricks',classification='wall'),
                    dict(label='Recessed wall niche with intact outer wall',kind='box',lo=[1,7,44],hi=[1,10,52],state='air',classification='body'),
                    dict(label='Small supported diagonal wall corbel',kind='beam',start=[2,6,44],end=[5,9,47],width=1,state='stone_brick_slab[type=top,waterlogged=false]',classification='body'),
                    dict(label='Localized reproducible weathering of the same west wall',kind='surface_palette',lo=[0,4,1],hi=[0,12,142],from_states=['stone_bricks'],palette=['cracked_stone_bricks','mossy_stone_bricks'],fraction=.1,seed=17,classification='inherit'),
                    dict(label='Explicit weighted-pattern integration on the whole approved wall',kind='pattern',lo=[1,9,68],hi=[1,11,74],from_states=['stone_bricks'],palette=[dict(state='granite',weight=1)],seed=74,classification='inherit'),
                    dict(label='Automatically recognized floors with protected original routes',kind='auto_floor',profile='worn',style_note='Synthetic older maintenance corridor; sparse shallow depressions.',fraction=.01,seed=91)])
    for i in (0,5):plan['operations'][i]['write_bounds']=dict(lo=plan['operations'][i]['lo'],hi=plan['operations'][i]['hi'],allow_overwrite=True)
    review=out/'review';p=prepare(source,config,review)
    checks['draft_stops_awaiting_user']=p['stage']=='awaiting_user_review' and not (review/'approval.json').exists()
    checks['unapproved_apply_rejected']=rejected(lambda:refine(review,plan,out/'unapproved'))
    checks['unapproved_no_revision_created']=not (out/'unapproved').exists()
    checks['blank_confirmation_rejected']=rejected(lambda:record_user_approval(review,'',True))
    checks['unreviewed_confirmation_rejected']=rejected(lambda:record_user_approval(review,'SYNTHETIC test',False))
    record_user_approval(review,'SYNTHETIC FIXTURE ONLY: thumbnails reviewed; refine this test whole master.',True)
    thumb=review/'thumbnails.png';original=thumb.read_bytes();thumb.write_bytes(original+b'changed')
    checks['stale_thumbnail_rejected']=rejected(lambda:refine(review,plan,out/'bad_thumb'))
    thumb.write_bytes(original)
    source.write_bytes(source_bytes+b'changed')
    checks['changed_original_rejected']=rejected(lambda:refine(review,plan,out/'bad_source'))
    source.write_bytes(source_bytes)
    cfg=review/'config.json';original=cfg.read_bytes();cfg.write_bytes(original+b' ')
    checks['changed_protections_rejected']=rejected(lambda:refine(review,plan,out/'bad_config'));cfg.write_bytes(original)
    def small(kind,lo,hi,value='stone_bricks'):
        return dict(style_note='synthetic bounded detail',operations=[dict(label=kind,kind='box',lo=lo,hi=hi,state=value)])
    checks['protected_walk_volume_rejected']=rejected(lambda:refine(review,small('blocking route',[23,4,60],[24,6,62]),out/'blocked'))
    checks['protected_node_rejected']=rejected(lambda:refine(review,small('protected fixture',[10,4,60],[10,4,60]),out/'node'))
    checks['protected_door_rejected']=rejected(lambda:refine(review,small('door',[23,4,0],[23,4,0]),out/'door'))
    checks['out_of_footprint_rejected']=rejected(lambda:refine(review,small('outside',[48,4,60],[48,4,60]),out/'outside'))
    checks['budget_overrun_rejected']=rejected(lambda:refine(review,small('too much',[1,6,1],[18,12,18]),out/'budget'))
    checks['seal_breach_rejected']=rejected(lambda:refine(review,small('breach',[0,6,80],[1,6,80],'air'),out/'leak'))
    checks['missing_shared_style_rejected']=rejected(lambda:refine(review,{'operations':plan['operations']},out/'nostyle'))
    escape=small('outside explicit selection',[5,4,10],[5,4,10]);escape['operations'][0]['write_bounds']=dict(lo=[6,4,10],hi=[8,6,13],allow_overwrite=True)
    checks['final_writer_rejects_selection_escape']=rejected(lambda:refine(review,escape,out/'scope_escape'))
    checks['selection_escape_writes_no_nbt']=not list((out/'scope_escape').rglob('*.nbt')) and source.read_bytes()==source_bytes
    final=refine(review,plan,out/'revision_01')
    checks['whole_master_revision_succeeded']=final['validation_passed'] and final['workflow'].startswith('whole_uncut')
    revised,revised_walls=read_master(out/'revision_01/refined.master.json.gz')
    checks['modelling_integrated_into_reviewed_refinement']=revised.get((6,4,11))=='minecraft:stone_bricks' and final['operations'][0]['modelling']['changed']>0
    checks['pattern_integrated_into_reviewed_refinement']=revised.get((1,10,70))=='minecraft:granite' and (1,10,70) in revised_walls and final['operations'][-2]['pattern']['changed']==21
    checks['auto_floor_integrated_into_reviewed_refinement']=final['operations'][-1]['auto_floor']['actual_blocks']>0 and final['operations'][-1]['auto_floor']['original_necessary_paths_preserved']
    checks['dimensions_and_source_preserved']=revised.size==m.size and source.read_bytes()==source_bytes
    checks['details_span_cut_in_one_master']=revised.get((1,6,47))=='minecraft:chiseled_stone_bricks' and revised.get((1,6,48))=='minecraft:chiseled_stone_bricks'
    checks['three_cell_delivery_exactly_six']=verify_delivery(out/'revision_01/delivery')['actual_nbt_files']==6
    checks['runtime_composites_separate']=len(list((out/'revision_01/runtime').glob('*.nbt')))==3
    checks['before_after_manifest_exists']=(out/'revision_01/changes.json').is_file() and len(final['previews'])==3 and (out/'revision_01/comparison.png').is_file()
    checks['existing_revision_not_overwritten']=rejected(lambda:refine(review,plan,out/'revision_01'))
    checks['review_dir_not_overwritten']=rejected(lambda:refine(review,plan,review))
    palette_operation=next(op for op in plan['operations'] if op['kind']=='surface_palette')
    checks['deterministic_global_surface_palette']=operation_candidates(m,palette_operation)==operation_candidates(m,palette_operation)
    # Whole revalidation must catch failures even where no saved path was protected.
    config2=copy.deepcopy(config);config2['protected_paths']=[]
    review2=out/'review_without_path_mask';prepare(source,config2,review2)
    record_user_approval(review2,'SYNTHETIC FIXTURE ONLY: reviewed and approved test.',True)
    checks['post_detail_collision_recheck']=rejected(lambda:refine(review2,small('full corridor block',[1,4,70],[46,7,70]),out/'collision'))
    checks['rejected_plan_has_no_output']=not any((out/n).exists() for n in ['blocked','node','door','outside','budget','leak','nostyle','collision'])
    # Same workflow on a single room and a sparse L master; no individual-part
    # refinement is used. These are geometry-only fixtures, not art examples.
    shape_revisions={}
    for name,cells in [('single',[(0,0)]),('l_shape',[(0,0),(1,0),(0,1)])]:
        size=(48*(max(c[0] for c in cells)+1),16,48*(max(c[1] for c in cells)+1))
        whole=Volume(size);wall=set();probes=[]
        for cx,cz in cells:
            whole.box((cx*48,0,cz*48),(cx*48+47,15,cz*48+47),'stone_bricks')
            whole.box((cx*48+2,4,cz*48+2),(cx*48+45,13,cz*48+45),'air')
            wall.update(p for p in whole.blocks if 4<=p[1]<=13)
            probes.append([cx*48+12,8,cz*48+12])
        if name=='l_shape':
            whole.box((44,4,21),(51,8,26),'air')
            whole.box((21,4,44),(26,8,51),'air')
        sub=out/name;sub.mkdir()
        shape_source=sub/'whole.master.json.gz';save_master(shape_source,whole,wall)
        c=dict(cells=[list(p) for p in cells],door_y=4,ports=[],interior_probes=probes,
            start=[3.5,4,23.5],targets={'same_room':[20.5,4,24.5]},
            max_changed_blocks=100,cameras=[dict(role='whole',eye=[75,44,-20],target=[24,8,24],cuts=[['y',13,'above']]),
                                           dict(role='entry',eye=[3.5,5.62,23.5],target=[10,8,18])])
        if name=='l_shape':c['targets'].update(east=[72.5,4,24.5],south=[24.5,4,72.5])
        prepare(shape_source,c,sub/'review')
        record_user_approval(sub/'review','SYNTHETIC fixture only: reviewed; refine test.',True)
        detail=dict(style_note='Same planar stone detail in the complete source.',operations=[
            dict(label='West source trim',kind='frame',lo=[1,6,10],hi=[1,10,20],state='chiseled_stone_bricks',classification='wall')])
        r=refine(sub/'review',detail,sub/'revision')
        checks[name+'_whole_master_resliced']=r['validation_passed'] and r['delivery_nbt_files']==2*len(cells)
        checks[name+'_no_source_overwrite']=r['original_source_unchanged']
        if name=='l_shape':checks['l_shape_missing_cell_not_exported']=not (sub/'revision/delivery/p11_body.nbt').exists()
        shape_revisions[name]=str(sub/'revision')
    if not all(checks.values()):raise AssertionError(checks)
    report=dict(passed=True,checks=checks,fixture_only=True,review=str(review),revision=str(out/'revision_01'),
                shape_revisions=shape_revisions,
                caution='Synthetic consent records authorize only these synthetic tests, never real user assets.')
    (root/'results.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print(json.dumps(dict(passed=True,checks=len(checks),report=str(root/'results.json'),revision=report['revision'])))


if __name__=='__main__':main()
