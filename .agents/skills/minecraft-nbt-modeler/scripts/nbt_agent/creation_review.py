"""Source-bound observations, blind comparison, selection and draft publication."""

from pathlib import Path
from uuid import uuid4

from nbt_agent.creation_execution import Execution, prepare_review, read, readback, reference, saved_binding
from nbt_agent.creation_inputs import evidence, fields, gates, text
from nbt_building.workflow import dispatch
from nbt_composition.working_model import ModelConflict, WorkingModel
from nbt_project.prompts import index_lock, inside, task_index
from nbt_project.queues import write
from nbt_review import blind_review


def record_render(workspace, row):
    return blind_review._render(workspace, dict(manifest=row['path'], sha256=row['sha256']))


def review_target(job, state, slot):
    if slot=='published':
        if 'published' not in state:
            raise ValueError('请先保存入选制作版')
        return state['published']
    return job.ready(state, slot)


def observe(job, state, request):
    fields(request,('slot','observations'),('revision','issues','quality_observations'))
    slot=request['slot']
    target=review_target(job,state,slot)
    review=target['review']
    record_render(job.workspace,review['render'])
    if review['architecture']:
        params=dict(pack=review['pack']['path'],pack_sha256=review['pack']['sha256'],
                    render_manifest=review['render']['path'], revision=request.get('revision',0),
                    observations=request['observations'],issues=request.get('issues',[]))
        if 'quality_observations' in request:
            params['quality_observations']=request['quality_observations']
        result=dispatch(job.workspace,'review-record',params)
        path=inside(job.workspace,result['path'])
        result=dict(status=result['status'], review=reference(path), revision=result['revision'],
                    observed=result['observations_complete'],coverage_complete=result['coverage_complete'],
                    missing_locations=result['missing_locations'],
                    quality=result.get('quality',{}).get('summary'),approval_created=False)
    else:
        rows=request['observations']
        expected=review['awaiting_views']
        if not isinstance(rows,list) or len(rows)!=len(expected) or request.get('quality_observations'):
            raise ValueError('请逐张记录真实图片观察；建筑质量量表需要声明式建筑方案')
        for row in rows:
            fields(row,('image','text'))
            text(row['text'])
        if sorted(row['image'] for row in rows)!=sorted(expected):
            raise ValueError('观察记录的机位与实际图像不一致')
        if request.get('revision',0)!=0 or target.get('observations'):
            raise ValueError('已登记当前观察；请保留旧观察并为修改后的候选重新出图')
        path=inside(job.workspace, review['review_dir'])/'image-observations.json'
        write(path,dict(observations=rows, render=review['render'], images=review['images'],
                        issues=request.get('issues',[]), approval_created=False))
        result=dict(observed=True,review=reference(path),approval_created=False)
    target['observations']=result
    job.save(state)
    return result


def aligned_pair(job,state,targets,folder):
    from nbt_project.history import file_hash
    comp=state['options'].get('comparison')
    camera=evidence(job.workspace,comp['cameras'] if comp else targets[0]['review']['camera'])
    entries=[]
    for index,target in enumerate(targets):
        render=target['comparison_render']
        row=record_render(job.workspace,render)
        if row['report']['cameras_sha256']!=file_hash(camera) or bool(row['report'].get('reference_camera_binding'))!=bool(comp and 'bundle' in comp):
            run=Execution(job.workspace,folder,job.live)
            render=run.step(f'aligned-{index}',lambda: run.render(target['source'],camera,comparison=comp))['render']
        entries.append(dict(manifest=render['path'],sha256=render['sha256']))
    return entries


def prepare_blind(job,state,request):
    fields(request,optional=('scope','crop'))
    if state['policy']['mode']!='maximum':
        raise ValueError('双候选匿名审阅适用于极限效果')
    if state.get('blind'):
        if request!=state['blind']['request']:
            raise ValueError('已为本轮保存另一组盲评条件')
        pair=state['blind']
    else:
        targets=[job.ready(state,slot) for slot in ('1','2')]
        folder=job.directory/'pair'
        folder.mkdir(exist_ok=True)
        entries=aligned_pair(job,state,targets,folder)
        scope=request.get('scope') or '比较设计轴：'+'、'.join(state['options']['axes'])
        output=job.workspace/'nbt_models/_workspaces/reference-reviews'/f'{job.id[:12]}-{uuid4().hex[:12]}'
        package=blind_review.prepare_review(job.workspace,dict(renders=entries,scope=scope,crop=request.get('crop'),output=str(output)))
        assignment=read(inside(job.workspace,package['binding']))['assignment']
        geometry=output/'public'/'geometry.json'
        write(geometry,dict(public_sha256=package['public_sha256'],checks={
            label:targets[index]['geometry_checks'] for label,index in zip('AB',assignment)}))
        pair=dict(package,request=request,slots=['1','2'],geometry=reference(geometry))
        state['blind']=pair
        job.save(state)
    blind_review.verify_review(job.workspace,pair['binding'],pair['binding_sha256'])
    evidence(job.workspace,pair['geometry'])
    return {key:pair[key] for key in ('public','public_sha256','geometry','views','approval_created')}


def record_blind(job,state,request):
    fields(request,('decision','actor','observations'))
    pair=state.get('blind')
    if not pair:
        raise ValueError('请先准备匿名 A/B 审阅')
    if state.get('selected'):
        raise ValueError('候选已选定，原比较结论已冻结')
    blind_review.verify_review(job.workspace,pair['binding'],pair['binding_sha256'])
    output=inside(job.workspace,pair['public']).parent.parent/f'observation-{uuid4().hex[:12]}.json'
    result=blind_review.record_review(job.workspace,dict(request,public=pair['public'],public_sha256=pair['public_sha256'],output=str(output)))
    state['blind']['observation']=result
    job.save(state)
    return result


def select(job,state,request):
    fields(request,optional=('tie_choice','reason'))
    if state.get('selected'):
        return state['selected']
    if state['policy']['mode']=='maximum':
        pair=state.get('blind',{})
        observed=pair.get('observation')
        if not observed:
            raise ValueError('极限效果须先登记匿名 A/B 图像观察')
        blind_review.verify_review(job.workspace,pair['binding'],pair['binding_sha256'],observed['record'],observed['record_sha256'])
        choice=read(inside(job.workspace,observed['record']))['decision']
        if choice=='tie':
            choice=request.get('tie_choice')
            text(request.get('reason'))
        if choice not in ('A','B'):
            raise ValueError('请选择对应 A/B；平局需要解释取舍')
        assignment=read(inside(job.workspace,pair['binding']))['assignment']
        slot=pair['slots'][assignment['AB'.index(choice)]]
    else:
        slot='1'
    target=job.ready(state,slot)
    record_render(job.workspace,target['review']['render'])
    WorkingModel.open(job.workspace,**target['source'])._unchanged()
    state['selected']=dict(slot=slot,candidate=target['candidate'],reason=request.get('reason'),approval_created=False)
    job.save(state)
    return state['selected']


def retest(job,state,request):
    fields(request,('slot',),('against',))
    baseline=state['options'].get('retained_review')
    target=review_target(job,state,request['slot'])
    against=request.get('against','retained' if baseline else 'blind')
    if against=='blind':
        return retest_blind(job,state,target)
    if against!='retained' or not baseline:
        raise ValueError('裁定的旧版审阅未登记')
    current=target.get('observations')
    if not current or not target['review']['architecture']:
        raise ValueError('定向回查需当前三尺度观察和建筑方案绑定')
    previous_path=evidence(job.workspace,baseline)
    notes=read(previous_path)
    previous_pack=previous_path.parent/'review-pack.json'
    current_notes=evidence(job.workspace,current['review'])
    current_ref=dict(pack=target['review']['pack']['path'],pack_sha256=target['review']['pack']['sha256'],
                     notes_sha256=current['review']['sha256'])
    binding=dict(pack=str(previous_pack),pack_sha256=notes['pack_sha256'],notes_sha256=baseline['sha256'])
    from nbt_building.review import compare as compare_review
    compared=compare_review(job.workspace,dict(target['source'],**binding,current_review=current_ref),allow_detached=True)
    # Reuse the original exact camera settings for a source-bound side-by-side.
    # These images are independent of observations and remain marked as pending.
    original_cameras=previous_pack.parent/read(previous_pack)['cameras']
    from nbt_building.review import load_pack
    load_pack(job.workspace,binding)
    folder=job.directory/'retests'/current['review']['sha256']
    folder.mkdir(parents=True,exist_ok=True)
    run=Execution(job.workspace,folder,job.live)
    original_image=next(iter(notes['images'].values()))
    metadata=read(evidence(job.workspace,dict(path=original_image['metadata'],sha256=original_image['metadata_sha256'])))
    settings={key:metadata[key] for key in ('width','height','quality')}
    images=run.step('prior-views',lambda: run.render(target['source'],original_cameras,comparison=settings))
    current_notes=evidence(job.workspace,current['review'])
    result=dict(old=baseline, current=reference(current_notes), comparison=compared,
                same_view_render=images['render'], same_view_observation_pending=True, approval_created=False)
    output=folder/'comparison.json'
    write(output,result)
    return dict(result,receipt=reference(output))


def retest_blind(job,state,target):
    pair,selected=state.get('blind',{}),state.get('selected',{})
    observation=pair.get('observation')
    if not observation or selected.get('candidate')!=target['candidate']:
        raise ValueError('定向复验需要旧版审阅或本轮已选中的盲评候选')
    blind_review.verify_review(job.workspace,pair['binding'],pair['binding_sha256'],observation['record'],observation['record_sha256'])
    comparison=read(inside(job.workspace,pair['binding']))
    selected_render=comparison['renders'][pair['slots'].index(selected['slot'])]
    original=record_render(job.workspace,dict(path=selected_render['manifest'],sha256=selected_render['sha256']))
    report=original['report']
    notes=read(inside(job.workspace,observation['record']))['observations']
    view_mapping={f'view-{index:02d}':name for index,name in enumerate(comparison['view_ids'],1)}
    view_ids={view_mapping[row['view']] for row in notes if row.get('recheck') or row.get('remaining')}
    if not view_ids:
        raise ValueError('盲评记录没有待复验机位；可在正式制作版登记正常观察')
    cameras=inside(job.workspace,report['camera_file'])
    comp={key:report[key] for key in ('width','height','quality')}
    folder=job.directory/'retests'/target['candidate']/('published' if target.get('status')=='awaiting_observations' else 'candidate')
    folder.mkdir(parents=True,exist_ok=True)
    if binding:=report.get('reference_camera_binding'):
        comp['bundle']=dict(path=binding['bundle'],sha256=binding['bundle_sha256'])
    else:
        matching=folder/'cameras.json'
        if not matching.exists():
            write(matching,[row for row in read(cameras) if row['id'] in view_ids])
        cameras=matching
    run=Execution(job.workspace,folder,job.live)
    geometry=run.step('readback-check',lambda: readback(job.workspace,target['source'],job.frozen()),diagnostic='model')
    rendered=run.step('retest-render',lambda: run.render(target['source'],cameras,comparison=comp))
    verified=record_render(job.workspace,rendered['render'])
    return dict(observations=notes, readback=run.steps[0], quality=geometry.get('quality',{}).get('summary'),
                images=[reference(row['image']) for row in verified['images'] if row['meta']['id'] in view_ids],
                same_view_render=rendered['render'], observation_pending=True, approval_created=False)


def publish(job,state,request):
    fields(request)
    selected=state.get('selected')
    if not selected:
        raise ValueError('请先选定通过检查的候选')
    if 'published' in state:
        published=state['published']
        record_render(job.workspace,published['review']['render'])
        return published
    target=job.ready(state,selected['slot'])
    workspace=job.workspace
    frozen=job.frozen()
    old=WorkingModel.open(workspace,**target['source'])
    reference_constraints=state['options'].get('reference')
    gates(frozen,old,reference_constraints)
    project=frozen['document']['project']
    actual=inside(workspace,frozen['task']['directory']).parent.parent.parent
    if not actual.is_relative_to(workspace/'nbt_models'):
        raise ValueError('交接的建筑目录无效')
    # Older grouped drafts could be handed off before room registration.
    if actual.is_relative_to(workspace/'nbt_models/_workspaces'):
        actual=None
    folder=job.directory/'publication'
    folder.mkdir(exist_ok=True)
    run=Execution(workspace,folder,job.live)

    def copy_draft():
        draft=WorkingModel(workspace,old.model.size,context=old.context,limits=old.limits)
        draft.model,draft.walls,draft.instances=old.model,old.walls,old.instances
        draft.phase,draft.preopening,draft._closed=old.phase,old.preopening,old._closed
        draft._architecture,draft._palette,draft._extras=old.architecture,old._palette,old._extras
        from nbt_library import shape_of
        shape=shape_of(old.model.size,old.context.get('cells',[]),old.context.get('cell_size',48))

        def check_inputs():
            old._unchanged()
            job.live()

        receipt=dict(task=job.id,revision=state['revision'],candidate=target['candidate'],
                     staged_source=target['source'],working_sha256=old.inspect()['working_sha256'])
        if state['options'].get('reference_roles'):
            refs=read(job.reference_file(state))
            receipt['concept_references']=dict(gallery_sha256=refs['gallery']['sha256'],
                                               reference_pack_sha256=refs['pack']['sha256'],
                                               adopted=refs['choice']['adopted'],
                                               pending_rooms=refs['choice'].get('pending_rooms',[]),
                                               expected_views=refs['choice'].get('expected_views',[]))
        with index_lock(workspace,task_index(workspace).parent):
            return draft.save_draft(name_zh=project['name'],shape=shape,_draft_directory=actual,before_publish=check_inputs,
                                    attachments={'creation.json':receipt})

    saved=run.step('publish-draft',copy_draft)
    run.step('readback-check',lambda: readback(workspace,saved,frozen,reference_constraints),diagnostic='model')
    model=WorkingModel.open(workspace,**saved_binding(saved))
    if model.inspect()['working_sha256']!=old.inspect()['working_sha256']:
        raise ModelConflict('STALE_SOURCE',[dict(reason='正式制作版回读须与入选候选一致')])
    candidate_request=read(job.directory/'attempts'/target['candidate']/'request.json')
    review=prepare_review(run,saved,candidate_request.get('view_overrides'))
    result=dict(status='awaiting_observations',source=saved_binding(saved), review=review,steps=run.steps,
                candidate=target['candidate'], history_pending=saved.get('history_pending',False),
                approval_created=False, nbt_exported=False)
    state['published']=result
    job.save(state)
    return result


def finish(job,state,request):
    fields(request)
    target=review_target(job,state,'published')
    if not target.get('observations',{}).get('observed'):
        raise ValueError('请先实际查看并逐张记录正式制作版的图像')
    record_render(job.workspace,target['review']['render'])
    evidence(job.workspace,target['observations']['review'])
    published=WorkingModel.open(job.workspace,**target['source'])
    published._assert_parent(published._building)
    result=job.client.change('complete',review=target['review']['review_dir'])['completion']
    state['completion']=result
    job.save(state)
    return dict(result,status='completed',approval_created=False, nbt_exported=False)
