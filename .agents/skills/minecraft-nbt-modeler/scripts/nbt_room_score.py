"""Versioned, explainable room quality rubric; no inferred visual approval."""
import argparse,hashlib,json,math
from collections import Counter,deque
from pathlib import Path
from nbt_refine import read_master
from nbt_assembly import Volume
from nbt_collision import _Space,PLAYER_HEIGHT,RADIUS
from nbt_walk_view import inspect_walk

PLAYER_SCALE=dict(unit='block',edition='Java 1.20.1',pose='standing',width=2*RADIUS,height=PLAYER_HEIGHT,comfort_width=4*RADIUS,comfort_height=2.5,grid=0.5,minimum_full_block_opening=[1,2],notes=['按实际碰撞形状检查，不按方块名称或外观判断','舒适宽度与净高为设计建议，不是通行硬门槛','仅验证普通站立步行，不代表潜行、跳跃或游泳可达'])

PROFILES={'room':dict(headroom=12,headroom_comfort=6,connectivity=10,reachable_space=12,comfort=10,stable_support=8,edge_safety=8,hazard_safety=8,routes=14,route_directness=4,route_comfort=5,target_standing=3),'corridor':dict(headroom=15,headroom_comfort=3,connectivity=12,reachable_space=8,comfort=5,stable_support=10,edge_safety=8,hazard_safety=8,routes=18,route_directness=5,route_comfort=5,target_standing=3)}
VISUAL={'interior':['functional_completeness','spatial_hierarchy','material_coherence','detail_logic','structural_readability','human_scale','circulation_legibility','lighting_atmosphere','theme_identity','maintenance_finish'],'exterior':['silhouette','facade_rhythm','entrance_legibility','roof_wall_transition','mass_proportion','material_weathering','site_integration','multi_view_composition']}
LABELS=dict(headroom='玩家净空满足率',headroom_comfort='2.5格宽裕净高比例',connectivity='最大连通步行区占比',reachable_space='起点可达活动区比例',comfort='1.2格宽裕活动区比例',stable_support='完整踏足支撑比例',edge_safety='无临空暴露采样比例',hazard_safety='无潜在危险近邻采样比例',routes='声明目标可达率',route_directness='路线直达效率',route_comfort='沿途宽裕比例',target_standing='目标站位有效率')
FORMULAS=dict(headroom='可容纳0.6×1.8玩家的采样/暴露支持面采样',headroom_comfort='净高至少2.5格的有效采样/有效站位采样',connectivity='最大半格步行连通分量/有效站位采样',reachable_space='可与声明起点连接的连通分量采样/有效站位采样',comfort='可容纳1.2格宽、1.8格高活动体积的采样/有效站位采样',stable_support='玩家0.6格脚印下方支持半格全部覆盖的采样/有效站位采样',edge_safety='四个界内相邻方向无可进入但缺支撑落脚点的采样/有效站位采样；不模拟坠落',hazard_safety='脚下、脚边和头部近邻无已列明潜在危险状态的采样/有效站位采样；不模拟伤害',routes='可达声明目标/声明目标总数',route_directness='各可达目标同网格无障碍距离下界总和/实际路径长度总和，上限100%；仅效率参考，探索迷宫不应单独追高',route_comfort='路线中可容纳1.2格宽活动体积的站位/可达路线站位',target_standing='有支撑且玩家占位无碰撞的目标/目标总数')
GROUPS={key:('净空' if key in ('headroom','headroom_comfort') else '活动空间' if key=='comfort' else '踏足与风险' if key in ('stable_support','edge_safety','hazard_safety') else '连通与动线') for key in LABELS}

def rubric():return dict(player_scale=PLAYER_SCALE,model_version='room-quality-v0.2-heuristic',profiles=PROFILES,functions={key:dict(label=LABELS[key],formula=FORMULAS[key],group=GROUPS[key]) for key in LABELS},visual_criteria=VISUAL,overall_weights=dict(without_exterior=dict(engineering=65,interior=35),with_exterior=dict(engineering=55,interior=25,exterior=20)),calibrated=False)

def comprehensive(metrics, interior, exterior):
    definitions=[
        ('功能完整性',20,['routes','target_standing'],['functional_completeness']),
        ('空间与动线',20,['headroom','headroom_comfort','connectivity','reachable_space','comfort','route_directness','route_comfort'],['spatial_hierarchy','human_scale','circulation_legibility']),
        ('安全性',15,['stable_support','edge_safety','hazard_safety'],[]),
        ('比例与构图',15,[],['structural_readability']),
        ('材质与光照',15,[],['material_coherence','lighting_atmosphere']),
        ('细节与主题',15,[],['detail_logic','theme_identity','maintenance_finish'])]
    outside={'比例与构图':['silhouette','facade_rhythm','entrance_legibility','roof_wall_transition','mass_proportion','multi_view_composition'],'材质与光照':['material_weathering'],'细节与主题':['site_integration']}
    dimensions={};priorities=[];earned=coverage=0
    for label,weight,automatic,visual in definitions:
        items=[dict(key=k,score=metrics[k]['score'],source='geometry',evidence=metrics[k]['formula']) for k in automatic]
        items += [dict(key=k,score=interior['scores'][k] if interior else None,source='visual',evidence=interior['evidence'] if interior else None) for k in visual]
        if exterior:
            items += [dict(key=k,score=exterior['scores'][k],source='visual',evidence=exterior['evidence']) for k in outside.get(label,[])]
        measured=[i for i in items if i['score'] is not None]
        fraction=len(measured)/len(items)
        value=sum(i['score'] for i in measured)/len(measured) if measured else None
        dimensions[label]=dict(weight=weight,score=round(value,2) if value is not None else None,coverage_percent=round(fraction*100,2),criteria=items)
        coverage+=weight*fraction
        earned+=sum(i['score'] for i in measured)*weight/len(items)/100
        for item in items:
            loss=(100-item['score'])*weight/len(items)/100 if item['score'] is not None else None
            if loss is None or loss>0:
                priorities.append(dict(dimension=label,metric=item['key'],lost_points=round(loss,2) if loss is not None else None,action='补充评价证据' if loss is None else '改进此项后重新评估'))
    priorities.sort(key=lambda i:(i['lost_points'] is None,-(i['lost_points'] or 0)))
    return dict(version='six-dimension-v1',dimensions=dimensions,coverage_percent=round(coverage,2),score=round(earned,2) if abs(coverage-100)<1e-8 else None,score_interval=[round(earned,2),round(earned+100-coverage,2)],priorities=priorities,calibrated=False)

def sha(file):return hashlib.sha256(Path(file).read_bytes()).hexdigest()

def visual_rating(data,kind):
    if data is None:return None
    if not isinstance(data,dict) or set(data)-{'scores','evidence','reviewer'}:raise ValueError('视觉评价字段无效')
    scores=data.get('scores');evidence=data.get('evidence');reviewer=data.get('reviewer','human')
    if not isinstance(scores,dict) or set(scores)!=set(VISUAL[kind]) or any(type(v) not in (int,float) or not math.isfinite(v) or not 0<=v<=100 for v in scores.values()):raise ValueError(f'视觉评分须完整填写{len(VISUAL[kind])}个0～100分指标')
    if not isinstance(evidence,str) or not 5<=len(evidence.strip())<=4000 or reviewer not in ('human','external_ai'):raise ValueError('视觉评价须注明人工/外部AI来源，并给出5～4000字证据')
    return dict(score=round(sum(scores.values())/len(scores),2),scores=scores,evidence=evidence.strip(),reviewer=reviewer,automatically_measured=False)

def score_room(request,snapshot=None):
    source=Path(request['source']).resolve();source_hash=sha(source)
    if request.get('source_sha256') and request['source_sha256']!=source_hash:raise ValueError('原模型已变化，请重新评分')
    model,walls=read_master(source);snapshot_hash=sha(snapshot) if snapshot else None
    if snapshot:
        data=json.loads(Path(snapshot).read_text(encoding='utf-8-sig'))
        if data.get('source_sha256')!=source_hash or data.get('size')!=list(model.size):raise ValueError('候选快照不属于此模型')
        if data.get('preview_only'):
            if not isinstance(data.get('master_blocks'),list):raise ValueError('候选快照缺少完整主模型')
            candidate=Volume(model.size);seen=set()
            for p,value in data['master_blocks']:
                p=tuple(p)
                if p in seen:raise ValueError('候选快照有重复坐标')
                seen.add(p);candidate.put(p,value)
            model=candidate
        if data.get('geometry_sha256')!=model.fingerprint():raise ValueError('候选快照哈希不一致')
    geometry=model.fingerprint()
    if request.get('geometry_sha256') and request['geometry_sha256']!=geometry:raise ValueError('画面已变化，请重新评分')
    profile=request.get('profile','room')
    if profile not in PROFILES:raise ValueError('评分场景须为room或corridor')
    exterior=request.get('include_exterior',False)
    if type(exterior) is not bool:raise ValueError('外观评分开关须为布尔值')
    context=Path(request['context']).resolve() if request.get('context') else None;context_hash=sha(context) if context else None
    space=_Space(model);samples=set()
    for y in range(1,space.sy):
        if y*.5+PLAYER_HEIGHT>model.size[1]:break
        for z in range(space.sz):
            exposed=space.support_rows[(y-1)*space.sz+z]&~space.rows[y*space.sz+z]
            while exposed:
                bit=exposed&-exposed;x=bit.bit_length()-1;exposed-=bit;node=(x+1,y,z+1);p=tuple(n*.5 for n in node)
                if space.supported(p) and space.clear_box((p[0]-RADIUS,p[1],p[2]-RADIUS),(p[0]+RADIUS,p[1]+.1,p[2]+RADIUS)):
                    samples.add(node)
                    if len(samples)>100000:raise ValueError('可评估地面超过10万采样点，请拆分房间模型')
    valid={node for node in samples if space.standing(tuple(n*.5 for n in node))}
    remaining=set(valid);largest=0;components=0;component_of={};component_sizes={}
    for start in sorted(valid):
        if start not in remaining:continue
        remaining.remove(start);queue=deque([start]);count=0;components+=1
        while queue:
            a=queue.popleft();count+=1;component_of[a]=components
            for dx,dz in ((1,0),(-1,0),(0,1),(0,-1)):
                for dy in (0,1,-1):
                    b=(a[0]+dx,a[1]+dy,a[2]+dz)
                    if b in remaining and space.move(tuple(v*.5 for v in a),tuple(v*.5 for v in b)):remaining.remove(b);queue.append(b)
        largest=max(largest,count);component_sizes[components]=count
    comfortable=sum(space.clear_box((x*.5-2*RADIUS,y*.5,z*.5-2*RADIUS),(x*.5+2*RADIUS,y*.5+PLAYER_HEIGHT,z*.5+2*RADIUS)) for x,y,z in valid)
    roomy_height=stable=edge_safe=hazard_safe=0;edge_positions=[];hazard_positions=[]
    def wide(p):return space.clear_box((p[0]-2*RADIUS,p[1],p[2]-2*RADIUS),(p[0]+2*RADIUS,p[1]+PLAYER_HEIGHT,p[2]+2*RADIUS))
    for node in sorted(valid):
        p=tuple(v*.5 for v in node);roomy_height+=space.clear_box((p[0]-RADIUS,p[1],p[2]-RADIUS),(p[0]+RADIUS,p[1]+2.5,p[2]+RADIUS))
        x0,x1=space._span(p[0]-RADIUS,p[0]+RADIUS);z0,z1=space._span(p[2]-RADIUS,p[2]+RADIUS);mask=((1<<(x1-x0))-1)<<x0;below=node[1]-1
        stable+=all(space.support_rows[below*space.sz+z]&mask==mask for z in range(z0,z1))
        exposed=any(space.clear_player_sweep(p,(p[0]+dx,p[1],p[2]+dz)) and not space.supported((p[0]+dx,p[1],p[2]+dz)) for dx,dz in ((.5,0),(-.5,0),(0,.5),(0,-.5)))
        edge_safe+=not exposed
        if exposed and len(edge_positions)<32:edge_positions.append(list(p))
        x,y,z=map(math.floor,p);danger=False
        for dx,dz in ((0,0),(1,0),(-1,0),(0,1),(0,-1)):
            for dy in (-1,0,1):
                value=model.get((x+dx,y+dy,z+dz));name=value.split('[')[0].split(':')[-1]
                if name in ('lava','fire','soul_fire','cactus','magma_block') or name in ('campfire','soul_campfire') and 'lit=false' not in value:danger=True
        hazard_safe+=not danger
        if danger and len(hazard_positions)<32:hazard_positions.append(list(p))
    route=None;route_error=None
    try:route=inspect_walk(dict(request,source_sha256=source_hash),snapshot)['report']
    except ValueError as error:route_error=str(error)
    ratio=lambda a,b:round(100*a/b,2) if b else 0.0
    counts={'headroom':(len(valid),len(samples)),'headroom_comfort':(roomy_height,len(valid)),'connectivity':(largest,len(valid)),'comfort':(comfortable,len(valid)),'stable_support':(stable,len(valid)),'edge_safety':(edge_safe,len(valid)),'hazard_safety':(hazard_safe,len(valid))}
    if route:
        targets=route['targets'];counts['routes']=(sum(item['reachable'] for item in targets),len(targets));counts['target_standing']=(sum(item['standing'] for item in targets),len(targets));paths=[item['path'] for item in targets if item.get('path')];points=[p for path in paths for p in path]
        if points:counts['route_comfort']=(sum(wide(p) for p in points),len(points))
        straight=sum(max(abs(path[0][0]-path[-1][0])+abs(path[0][2]-path[-1][2]),abs(path[0][1]-path[-1][1])) for path in paths);length=sum(sum(math.dist(a,b) for a,b in zip(path,path[1:])) for path in paths);
        if paths:counts['route_directness']=(min(straight,length),length) if length else (1,1)
        start=tuple(route['start']);groups=set()
        for node in valid:
            p=tuple(v*.5 for v in node)
            if all(abs(a-b)<=.5 for a,b in zip(start,p)) and space.connector(start,p):groups.add(component_of[node])
        counts['reachable_space']=(sum(component_sizes[g] for g in groups),len(valid))
    metrics={key:dict(label=LABELS[key],score=ratio(*counts[key]) if key in counts else None,numerator=counts[key][0] if key in counts else None,denominator=counts[key][1] if key in counts else None,weight=weight,group=GROUPS[key],formula=FORMULAS[key]) for key,weight in PROFILES[profile].items()}
    measured=[v for v in metrics.values() if v['score'] is not None];available=sum(item['weight'] for item in measured);diagnostic=round(sum(item['score']*item['weight'] for item in measured)/available,2)
    gate='evaluated_static';issues=[]
    if not valid:gate='blocked';issues.append('未找到满足玩家尺寸的可站立地面')
    if space.unknown:gate='unsupported';issues.append('存在未知碰撞形状，不能给出可靠总分')
    elif route is None:gate='incomplete';issues.append('路线项未评估：'+str(route_error))
    elif route.get('search_limit_reached'):gate='incomplete';issues.append('路线搜索达到上限，不能当作已验证连通')
    elif not route['passed']:gate='blocked';issues.append('声明的起点/目标或路线未通过静态步行检查')
    if not valid and gate!='unsupported':gate='blocked'
    visual=request.get('visual',{})
    if not isinstance(visual,dict) or set(visual)-{'interior','exterior'}:raise ValueError('视觉评价格式无效')
    interior=visual_rating(visual.get('interior'),'interior');outside=visual_rating(visual.get('exterior'),'exterior') if exterior else None
    weights=dict(engineering=55,interior=25,exterior=20) if exterior else dict(engineering=65,interior=35)
    missing=[]
    if interior is None:missing.append('内部视觉评价')
    if exterior and outside is None:missing.append('外部外观评价')
    engineering=diagnostic if gate=='evaluated_static' else None
    total=None
    if engineering is not None and not missing:total=round((engineering*weights['engineering']+interior['score']*weights['interior']+(outside['score']*weights.get('exterior',0) if outside else 0))/100,2)
    low=sorted(((k,v) for k,v in metrics.items() if v['score'] is not None),key=lambda row:row[1]['score']);deductions=[dict(metric=k,label=v['label'],lost_points=round((100-v['score'])*v['weight']/100,2)) for k,v in low if v['score']<100]
    if sha(source)!=source_hash or snapshot and sha(snapshot)!=snapshot_hash or context and sha(context)!=context_hash:raise ValueError('评分期间模型或坐标资料发生变化')
    group_scores={}
    for group in sorted(set(GROUPS.values())):
        values=[v for v in measured if v['group']==group];weight=sum(v['weight'] for v in values);group_scores[group]=dict(score=round(sum(v['score']*v['weight'] for v in values)/weight,2) if weight else None,available_weight=weight,total_weight=sum(PROFILES[profile][key] for key in GROUPS if GROUPS[key]==group))
    materials=Counter(value.split('[')[0] for value in model.blocks.values())
    quality=comprehensive(metrics,interior,outside)
    if gate!='evaluated_static' or missing:quality['score']=None
    return dict(player_scale=PLAYER_SCALE,comprehensive=quality,schema_version=1,model_version='room-quality-v0.2-heuristic',scope='whole_model',profile=profile,source_sha256=source_hash,geometry_sha256=geometry,context_sha256=context_hash,include_exterior=exterior,total_score=total,engineering_score=engineering,diagnostic_score=diagnostic,coverage_percent=available,gate=gate,issues=issues,missing=missing,metrics=metrics,group_scores=group_scores,deductions=deductions,visual=dict(interior=interior,exterior=outside),overall_weights=weights,evidence=dict(sample_count=len(samples),standing_count=len(valid),walk_components=components,blocked_samples=[list(n*.5 for n in p) for p in sorted(samples-valid)[:32]],unknown_shapes=[dict(state=s,reason=r,count=n) for (s,r),n in space.unknown.items()],edge_positions=edge_positions,hazard_positions=hazard_positions,conservative_obstacles=len(space.conservative),materials=materials.most_common(12)),route_report=route,limitations=['启发式权重，尚未用人类偏好数据校准','完整模型范围，不自动分割多个房间','不把材料种数或装饰数量当作美观分','视觉项来自有证据的外部输入，脚本不声称已看图','普通步行与半格台阶，不模拟跳跃、游泳、动态机关和游戏内体验'],asset_written=False,approval_created=False,runtime_verified=False)

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--request',type=Path);parser.add_argument('--snapshot',type=Path);parser.add_argument('--output',type=Path);parser.add_argument('--rubric',action='store_true');args=parser.parse_args()
    try:
        if args.rubric:print(json.dumps(dict(ok=True,result=rubric()),ensure_ascii=False));return 0
        if not args.request or not args.output:raise ValueError('请提供--request和新的--output目录，或用--rubric读取评价函数')
        from nbt_request_paths import read_request
        report=score_room(read_request(args.request),args.snapshot);args.output.mkdir(parents=True,exist_ok=False);file=args.output/'room-score.json';file.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(dict(ok=True,result=dict(report,report_file=str(file.resolve()))),ensure_ascii=False));return 0
    except Exception as error:print(json.dumps(dict(ok=False,error=str(error)),ensure_ascii=False));return 1

if __name__=='__main__':raise SystemExit(main())
