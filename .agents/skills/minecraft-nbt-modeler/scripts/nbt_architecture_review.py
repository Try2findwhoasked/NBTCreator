"""Source-bound three-scale review, issue localization and explicit game handoff."""
from copy import deepcopy
import json
import math
from pathlib import Path

from nbt_architecture_plan import fingerprint,resolve,actual_part
from nbt_prompts import inside,relative,index_lock
from nbt_project_batch import write
from nbt_history import file_hash


def load_model(workspace,request):
    from nbt_working_model import WorkingModel
    model=WorkingModel.open(workspace,inside(workspace,request['source']),source_sha256=request['source_sha256'])
    if not model.architecture:raise ValueError('制作源没有建筑方案绑定，请先通过plan-build建立可追踪方案')
    return model


def bounds(points):
    if not points:raise ValueError('目标构件没有实际几何')
    return dict(lo=[min(p[i] for p in points) for i in range(3)],hi=[max(p[i] for p in points)+1 for i in range(3)])


def visibility(model,eye,targets,look_at,fov):
    """Estimated visibility; unsupported fine shapes remain explicitly uncertain."""
    from nbt_collision import collision_cells
    from nbt_registry import effective
    ordered=sorted(targets,key=lambda p:sum((p[i]+.5-eye[i])**2 for i in range(3)))
    samples=ordered[::max(1,len(ordered)//32)][:32];visible=uncertain=framed=0;blockers={}
    forward=[look_at[i]-eye[i] for i in range(3)];length=math.sqrt(sum(v*v for v in forward));forward=[v/length for v in forward]
    cone=math.cos(math.radians(fov/2))
    for cell in samples:
        target=[v+.5 for v in cell];delta=[target[i]-eye[i] for i in range(3)];distance=math.sqrt(sum(v*v for v in delta));maybe=False;outcome='missing'
        if distance and sum(delta[i]/distance*forward[i] for i in range(3))<cone:continue
        framed+=1
        for step in range(1,max(2,math.ceil(distance*8))+1):
            t=min(1,step/max(1,math.ceil(distance*8)));point=[eye[i]+t*delta[i] for i in range(3)];p=tuple(math.floor(v) for v in point)
            value=model.get(p)
            if value.endswith(':air'):continue
            name,_=effective(value);half,reason=collision_cells(value)
            if p in targets:
                outcome='uncertain' if maybe or reason else 'visible';break
            if name.endswith(('_glass','_glass_pane')) or name in ('minecraft:glass','minecraft:glass_pane','minecraft:tinted_glass'):continue
            if reason:maybe=True;continue
            local=tuple(math.floor(2*(point[i]-p[i])) for i in range(3))
            if local in half:
                outcome='occluded';blockers[p]=blockers.get(p,0)+1;break
        visible+=outcome=='visible';uncertain+=outcome=='uncertain'
    count=max(1,len(samples))
    return dict(visible_fraction=visible/count,uncertain_fraction=uncertain/count,framing_fraction=framed/count,samples=len(samples),
        blockers=[dict(pos=list(p),rays=count) for p,count in sorted(blockers.items(),key=lambda item:-item[1])[:16]],
        scope='sampled_halfcell_geometry_with_glass_exceptions; not material_alpha_or_game_light')


def delivery_summary(validation, pack, observed, covered, issues):
    """Describe the evidence available at this revision, including gaps in coverage."""
    whole = validation['whole_model']
    routes = whole['routes']
    targets = [row['name'] for row in routes['targets'] if row['reachable']]
    lines = [f"静态通路可达 {len(targets)}/{len(routes['targets'])} 个目标（{'、'.join(targets)}）。"]
    legs = [row['name'] for row in whole.get('route_legs', []) if row['report']['passed']]
    if legs:
        lines.append('专项通路已复验 ' + '、'.join(legs) + '。')
    if routes.get('conservative_obstacles'):
        lines.append('部分细件采用保守障碍包络。')
    activities = [row for row in validation['architecture']['checks'] if row['kind'] == 'activity_routes']
    for activity in activities:
        faces = [f"第{f['stop_index'] + 1}站 {f['part']}.{f['interface']}" for f in activity['use_faces'] if f['passed']]
        result = '已核对操作侧与净距（' + '、'.join(faces) + '）' if faces else '未声明操作面'
        segments = activity['segments']
        lines.append(f"活动 {activity['id']} 可达 {sum(s['passed'] for s in segments)}/{len(segments)} 段，{result}。")
    if not activities:
        lines.append('本方案未声明分段活动与操作面。')
    views = [row['id'] for row in pack['views']]
    locations = [row['id'] for row in pack.get('review_locations', [])]
    for label, names, seen in [('机位', views, observed), ('审阅位置', locations, covered)]:
        if not names:
            lines.append('本方案未声明' + label + '。')
            continue
        missing = [name for name in names if name not in seen]
        suffix = '，待看 ' + '、'.join(missing) if missing else ''
        lines.append(f"{label}已记录观察 {len(names) - len(missing)}/{len(names)}{suffix}。")
    failed = [row['id'] for row in pack['views'] + pack.get('review_locations', []) if not row['passed']]
    if failed:
        lines.append('取景检查未通过 ' + '、'.join(failed) + '。')
    if observed:
        lines.append('本次观察有待回查问题 ' + '、'.join(row['id'] for row in issues) + '。' if issues
                     else '本次观察未登记问题。')
    lines.append('搬运净空与游戏内操作未在本次静态检查中验证。')
    return lines


def prepare(workspace,request):
    from nbt_collision import _Space
    model=load_model(workspace,request);validation=model.validate();binding=model.architecture;plan=resolve(binding['plan']);space=_Space(model.model)
    output=inside(workspace,request['output'])
    if output.is_relative_to(model.source.parent.parent):raise ValueError('审阅包不能写入已发布制作版目录')
    cameras=[];checks=[]
    for view in plan['views']:
        if ('feet' in view)==('eye' in view):raise ValueError('视角须选择真实脚位feet或外部eye之一：'+view['id'])
        pose=view.get('feet');eye=[pose[0],pose[1]+1.62,pose[2]] if pose else view['eye']
        if view.get('target_part'):
            _,points=actual_part(model,binding,view['target_part']);box=bounds(points)
            target=view.get('target') or [(box['lo'][i]+box['hi'][i])/2 for i in range(3)]
        else:
            points=set(model.model.blocks);target=view.get('target') or [v/2 for v in model.model.size]
        if sum((eye[i]-target[i])**2 for i in range(3))<.01:raise ValueError('视角方向长度为零')
        seen=visibility(model.model,eye,points,target,view.get('fov',60))
        standing=space.standing(pose) if pose else None
        eye_clear=space.clear_box([v-.01 for v in eye],[v+.01 for v in eye]) if all(0<=eye[i]<model.model.size[i] for i in range(3)) else True
        passed=(eye_clear and standing is not False and seen['visible_fraction']>=view.get('minimum_visible',.2))
        checks.append(dict(id=view['id'],layer=view['layer'],part=view.get('target_part'),feet=pose,standing=standing,eye_clear=eye_clear,passed=passed,visibility=seen))
        cameras.append(dict(id=view['id'],role=view['layer'],eye=eye,target=target,fov=view.get('fov',60)))
    from nbt_architecture_intent import prepare_locations
    locations = prepare_locations(model.model, plan, cameras, checks)
    output.mkdir(parents=True,exist_ok=False)
    write(output/'cameras.json',cameras)
    data=dict(schema_version=1,source=relative(workspace,model.source),source_sha256=model.source_sha256,
        model_sha256=model.inspect()['model_sha256'],plan_sha256=binding['sha256'],
        cameras='cameras.json',cameras_sha256=file_hash(output/'cameras.json'),views=checks,
        coverage_passed=all(row['passed'] for row in checks) and all(row['passed'] for row in locations),
        review_locations=locations,required_layers=['massing','structure','detail'],
        visual_status='awaiting_actual_images_and_observations',aesthetics='not_certified',approval_created=False)
    data['delivery_summary'] = delivery_summary(validation, data, set(), set(), [])
    write(output/'review-pack.json',data)
    return dict(pack=relative(workspace,output/'review-pack.json'),pack_sha256=file_hash(output/'review-pack.json'),
        source=str(model.source),cameras=str(output/'cameras.json'),coverage=data,
        render_command=['render','--source',str(model.source),'--cameras',str(output/'cameras.json'),'--output',str(output/'render')])


def load_pack(workspace,request):
    file=inside(workspace,request['pack'])
    if file_hash(file)!=request['pack_sha256']:raise ValueError('审阅包已变化')
    pack=json.loads(file.read_text(encoding='utf8'));source=inside(workspace,pack['source'])
    cameras=(file.parent/pack['cameras']).resolve()
    if not cameras.is_relative_to(file.parent.resolve()):raise ValueError('审阅机位路径越界')
    if file_hash(source)!=pack['source_sha256'] or file_hash(cameras)!=pack['cameras_sha256']:raise ValueError('审阅源或机位已变化')
    model=load_model(workspace,dict(source=pack['source'],source_sha256=pack['source_sha256']))
    if model.architecture['sha256']!=pack['plan_sha256'] or model.inspect()['model_sha256']!=pack['model_sha256']:raise ValueError('审阅包与制作源的方案或几何身份不符')
    return file,pack


def record(workspace,request):
    file,pack=load_pack(workspace,request);manifest_file=inside(workspace,request['render_manifest'])
    manifest=json.loads(manifest_file.read_text(encoding='utf8'))
    if manifest.get('status')!='complete' or manifest.get('source_sha256')!=pack['source_sha256'] or manifest.get('cameras_sha256')!=pack['cameras_sha256']:
        raise ValueError('实际出图未完成或源/相机绑定不一致')
    snapshot_file=(manifest_file.parent/manifest.get('snapshot_file','snapshot.json')).resolve()
    if not snapshot_file.is_relative_to(manifest_file.parent.resolve()) or file_hash(snapshot_file)!=manifest.get('snapshot_sha256'):raise ValueError('出图快照指纹不符')
    snapshot=json.loads(snapshot_file.read_text(encoding='utf8'))
    if snapshot.get('source_sha256')!=pack['source_sha256']:raise ValueError('出图快照引用了其他制作源')
    views={row['id']:row for row in pack['views']};images={}
    requested={row['id']:row for row in json.loads((file.parent/pack['cameras']).read_text(encoding='utf8'))}
    for image in manifest['images']:
        path=inside(workspace,manifest_file.parent/image['image']);metadata_file=inside(workspace,manifest_file.parent/image['metadata'])
        if not path.is_relative_to(manifest_file.parent.resolve()) or not metadata_file.is_relative_to(manifest_file.parent.resolve()):raise ValueError('出图文件路径越界')
        metadata=json.loads(metadata_file.read_text(encoding='utf8'));identifier=metadata['id']
        if identifier not in views or file_hash(path)!=image['sha256'] or metadata.get('image_sha256')!=image['sha256']:raise ValueError('图像缺失、变化或与机位不符')
        if identifier in images:raise ValueError('出图机位ID重复')
        expected=requested[identifier];actual=metadata.get('requested_view',{})
        if metadata.get('snapshot_sha256')!=manifest['snapshot_sha256'] or metadata.get('image')!=image['image'] or any(actual.get(key)!=value for key,value in expected.items()):raise ValueError('图片元数据与实际快照或请求机位不一致')
        content=path.read_bytes()
        if not content.startswith(b'\x89PNG\r\n\x1a\n') or len(content)<24 or int.from_bytes(content[16:20],'big')!=manifest['width'] or int.from_bytes(content[20:24],'big')!=manifest['height']:raise ValueError('图片格式或分辨率与出图回执不一致')
        images[identifier]=dict(path=relative(workspace,path),sha256=image['sha256'],metadata=relative(workspace,metadata_file),metadata_sha256=file_hash(metadata_file))
    if set(images)!=set(views):raise ValueError('实际图像未完整覆盖审阅机位')
    observed={row['image'] for row in request['observations']}
    if len(observed)!=len(request['observations']):raise ValueError('图像观察重复')
    if not observed<=set(images):raise ValueError('观察记录引用了不存在的实际图像')
    from nbt_architecture_intent import observed_locations
    covered_locations, missing_locations = observed_locations(pack, request['observations'])
    if len({row['id'] for row in request['issues']})!=len(request['issues']):raise ValueError('问题ID重复')
    model=load_model(workspace,dict(source=pack['source'],source_sha256=pack['source_sha256']));binding=model.architecture
    if snapshot.get('geometry_sha256')!=model.model.fingerprint() or manifest.get('geometry_sha256')!=snapshot['geometry_sha256']:raise ValueError('渲染几何指纹与制作源不符')
    issues=[]
    for issue in request['issues']:
        if any(views[name]['layer']!=issue['layer'] for name in issue['images'] if name in views):raise ValueError('问题层级与图像层级不一致')
        if not set(issue['images'])<=observed:raise ValueError('问题必须绑定已记录观察的图像')
        row=deepcopy(issue);row['state']='needs_review';row['source_sha256']=pack['source_sha256']
        if issue.get('part'):
            _,points=actual_part(model,binding,issue['part']);row['part_bounds']=bounds(points)
        if any(any(not 0<=p[i]<model.model.size[i] for i in range(3)) for p in issue.get('positions',[])):raise ValueError('问题坐标越界')
        issues.append(row)
    summary = delivery_summary(model.validate(), pack, observed, covered_locations, issues)
    notes_file=file.parent/'review-notes.json'
    load_pack(workspace,request)
    for row in images.values():
        if file_hash(inside(workspace,row['path']))!=row['sha256'] or file_hash(inside(workspace,row['metadata']))!=row['metadata_sha256']:raise ValueError('图像证据在记录期间变化')
    with index_lock(workspace,file.parent):
        old=json.loads(notes_file.read_text(encoding='utf8')) if notes_file.exists() else dict(revision=0)
        if request['revision']!=old['revision']:raise ValueError('观察记录修订已变化')
        layers={views[name]['layer'] for name in observed}
        data=dict(schema_version=1,revision=old['revision']+1,pack_sha256=request['pack_sha256'],source=pack['source'],source_sha256=pack['source_sha256'],plan_sha256=pack['plan_sha256'],
            observations=request['observations'],images=images,issues=issues,covered_layers=sorted(layers),
            covered_locations=covered_locations,missing_locations=missing_locations,delivery_summary=summary,
            coverage_complete=set(pack['required_layers'])<=layers and pack['coverage_passed'] and not missing_locations,
            status='observations_recorded',aesthetics='requires_agent_and_user_judgment',approval_created=False,game='not_checked')
        history=file.parent/'observations'/f"{data['revision']}-{fingerprint(data)}.json"
        if history.exists():raise ValueError('观察修订已存在，未覆盖')
        write(history,data);write(notes_file,data)
    return dict(data,path=relative(workspace,notes_file),sha256=file_hash(notes_file))


def compare(workspace,request):
    from nbt_web_paths import project_paths
    file,pack=load_pack(workspace,request);model=load_model(workspace,request)
    if project_paths(inside(workspace,pack['source']))['workdir']!=project_paths(model.source)['workdir']:raise ValueError('问题回查需要同一建筑的新制作版')
    notes_file=file.parent/'review-notes.json'
    if file_hash(notes_file)!=request['notes_sha256']:raise ValueError('待回查的问题记录已变化')
    notes=json.loads(notes_file.read_text(encoding='utf8'));binding=model.architecture;results=[]
    if notes.get('pack_sha256')!=request['pack_sha256'] or notes.get('source_sha256')!=pack['source_sha256'] or notes.get('plan_sha256')!=pack['plan_sha256']:raise ValueError('问题记录与原审阅包不一致')
    for row in notes['images'].values():
        if file_hash(inside(workspace,row['path']))!=row['sha256'] or file_hash(inside(workspace,row['metadata']))!=row['metadata_sha256']:raise ValueError('原图像证据已变化')
    for issue in notes['issues']:
        row=dict(id=issue['id'],state='needs_new_visual_observation',old_source_sha256=pack['source_sha256'],new_source_sha256=model.source_sha256,
            old_positions_are_current=False,layer=issue['layer'],text=issue['text'])
        if issue.get('part'):
            try:
                _,points=actual_part(model,binding,issue['part']);row.update(part=issue['part'],current_bounds=bounds(points),previous_bounds=issue.get('part_bounds'))
            except ValueError:row.update(part=issue['part'],current_bounds=None,target_removed=True)
        results.append(row)
    return dict(issues=results,approval_created=False,original_issues_unchanged=True,requires_same_view_comparison=True)


GAME_CHECKS=['placement','neighbors','rotation','walking','lighting']


def game_checklist(workspace,request):
    model=load_model(workspace,request)
    return dict(source=relative(workspace,model.source),source_sha256=model.source_sha256,minecraft_version='1.20.1',data_version=3465,
        checks=[dict(id=name,state='not_checked',evidence=[]) for name in GAME_CHECKS],
        prerequisites=['明确要求定稿后导出，或使用已明确提供的测试NBT','在隔离的目标游戏环境中按源版本放置'],
        status='awaiting_external_game_test',game_execution_witnessed=False,approval_created=False,nbt_exported=False)


def game_record(workspace,request):
    model=load_model(workspace,request)
    if {row['id'] for row in request['checks']}!=set(GAME_CHECKS):raise ValueError('游戏验收项缺失或重复')
    checks=[]
    for row in request['checks']:
        evidence=[]
        if row['state']!='not_checked' and not row['evidence']:raise ValueError('已报告的游戏检查须提供实际证据文件')
        for name in row['evidence']:
            file=inside(workspace,name)
            if not file.is_file():raise ValueError('游戏验收证据文件不存在')
            evidence.append(dict(path=relative(workspace,file),sha256=file_hash(file)))
        checks.append(dict(id=row['id'],reported_state=row['state'],note=row['note'],evidence=evidence))
    directory=inside(workspace,'nbt_models/_workspaces/project_design/game_observations');directory.mkdir(parents=True,exist_ok=True)
    data=dict(source=relative(workspace,model.source),source_sha256=model.source_sha256,runtime_build=request['runtime_build'],minecraft_version='1.20.1',
        checks=checks,status='external_observation_recorded',game_execution_witnessed=False,approval_created=False)
    load_model(workspace,request)
    for row in checks:
        for item in row['evidence']:
            if file_hash(inside(workspace,item['path']))!=item['sha256']:raise ValueError('游戏验收证据在记录期间变化')
    target=directory/(fingerprint(data)+'.json')
    if target.exists() and json.loads(target.read_text(encoding='utf8'))!=data:raise ValueError('游戏观察记录指纹冲突')
    if not target.exists():write(target,data)
    return dict(data,path=relative(workspace,target))
