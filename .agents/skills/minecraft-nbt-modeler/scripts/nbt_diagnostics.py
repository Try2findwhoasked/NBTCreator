"""Explain deterministic engine evidence without inventing blockers or applying repairs."""
import argparse
import hashlib
import json
from pathlib import Path

def bounds(points,padding=0.5):
    if not points:return None
    return dict(lo=[min(p[i] for p in points)-padding for i in range(3)],hi=[max(p[i] for p in points)+padding for i in range(3)])

def item(code,title,explanation,suggestions,*,severity='error',certainty='observed',location=None,evidence=None,target=None):
    data=dict(code=code,title=title,severity=severity,certainty=certainty,explanation=explanation,suggestions=suggestions,bounds=location,evidence=evidence or {},target=target,automatic_repair=False)
    data['id']=hashlib.sha256(json.dumps(data,sort_keys=True,ensure_ascii=False).encode()).hexdigest()[:16]
    return data

def walk(result):
    report=result['report'];issues=[]
    for pose in result['poses']:
        name=pose['name'];location=dict(lo=pose['lo'],hi=pose['hi']);evidence=dict(feet=pose['feet'],collisions=pose['collisions'][:32],collision_cells=len(pose['collisions']))
        if pose['outside']:issues.append(item('pose_bounds',name+'：玩家身体超出边界','脚底坐标虽然在模型内，宽0.6、高1.8格的身体仍可能越界。',['将脚底点往建筑内部移动，给身体留出边缘距离。','重新检查实际脚底高度；不必为错误坐标改动建筑。'],location=location,evidence=evidence,target=name))
        if not pose['clear']:issues.append(item('pose_collision',name+'：玩家身体与方块相交','红色小格是碰撞形状与玩家占位的实际交集；它们不是应自动删除的方块清单。',['先确认脚底点是否落在地面顶面，而不是落在地板内部。','若坐标正确，再局部调整顶构、突出物或通路宽度；保留承重与保护区。','完成修改后重新检查，再在游戏中验证。'],location=bounds(pose['collisions'],.5) or location,evidence=evidence,target=name))
        if not pose['supported']:issues.append(item('pose_support',name+'：脚下没有可靠支撑','碰撞引擎未在这个脚底高度确认可站立的地面；悬空点或不匹配的半砖高度也会导致此结果。',['把脚底Y设为真实地面顶面高度；半砖可能需要半格高度。','若设计确实缺地面，先规划连续平台、台阶及承托，保留必要路线。'],location=location,evidence=evidence,target=name))
    for target in report.get('targets',[]):
        if target.get('reachable'):continue
        reason=target.get('reason');name=target['name'];location=bounds([report['start'],target['feet']]);evidence=dict(reason=reason,feet=target['feet'],reachable_poses=report.get('reachable_poses'))
        if reason=='invalid_or_obstructed_feet_pose':continue  # Specific pose evidence already explains it.
        if reason=='search_limit_reached':
            issues.append(item('route_search_limit','到“'+name+'”：搜索尚未完成','已达到本次站姿搜索上限，不能据此认定通路不存在。',['使用中间平台作为新的起终点，分段检查。','核对大空间的目标和实际移动方式；本工具不模拟跳跃、游泳或攀爬。'],severity='warning',certainty='incomplete',location=location,evidence=evidence,target=name))
        elif reason=='no_safe_half_grid_connector':
            issues.append(item('route_connector','到“'+name+'”：无法接入采样网格','终点附近没有找到安全的半格采样连接；不等于整条路不存在。',['在同一真实地面上稍微调整脚底X/Z，再检查。','核对窄边缘、台阶高度和实际净空。'],severity='warning',certainty='incomplete',location=bounds([target['feet']]),evidence=evidence,target=name))
        else:
            issues.append(item('route_not_found','到“'+name+'”：本次未找到步行路径','起终点之间未求得普通步行与半格台阶路径；这份证据没有给出哪一堵墙是唯一阻挡。',['先处理已列出的起终点站姿问题，再复查。','在门洞、转角和中间平台增加分段终点，缩小问题区间。','检查连续支撑、低顶和陡坎；需要特殊移动的路线应在游戏中另行验证。'],severity='warning',certainty='incomplete',location=location,evidence=evidence,target=name))
    if report.get('unknown_shapes'):
        issues.append(item('collision_unknown','存在尚未支持的碰撞形状','引擎按保守方式处理这些状态，当前结果不足以证明通路或设计通过。',['查看报告中的方块状态，优先核对它们附近的真实游戏碰撞。','需要可靠工具验收时，先使用引擎已支持的结构表达；不要删除必需构件来制造通过。'],severity='warning',certainty='unknown',evidence=dict(states=report['unknown_shapes'])))
    return issues

def protection(details):
    points=details.get('positions',[])
    return [item('protected_write','步骤“'+str(details.get('label','当前修改'))+'”触及保护区','该操作试图改变受保护方块或通路体积。允许覆盖不会取消保护。',['移动、缩小或重新安排构件，使实际写入避开红色冲突位置。','保护体积可能包含空气和玩家路线，不按可见材质判断。','若保护配置与设计不符，先核对来源和用途，不自动删除或放宽保护。'],location=bounds(points,0.5),evidence=dict(total=details.get('total'),shown=len(points),truncated=details.get('truncated',False)))]

CHECKS={
 'inputs':('候选输入未能核对',['重新打开源建筑，核对坐标资料和当前参数，再生成预览。']),
 'preview_matches_request':('画面与当前参数不一致',['更新效果预览，检查当前源与参数，再运行检查。不要套用旧报告。']),
 'change_budget':('改动量不满足当前预算',['缩小修改范围、关闭不必要步骤或降低密度。','先看实际变化统计；不为凑效果自动放宽保护或预算。']),
 'protected_geometry':('候选改变了受保护内容',['返回当前候选，移动或缩小相关构件；检查保护区与必要路线。']),
 'wall_ownership':('墙层归属未能确认',['提供完整主模型或坐标资料中的显式墙mask。','核对墙层是否越界、指向空气或遗漏有效分片；不要按材质猜墙。']),
 'whole_building':('整体建筑检查未通过',['结合原始检查原因核对开口、密闭、连续通路和坐标资料。','可用“玩家／通路”增加分段终点定位具体站姿；没有坐标证据时不要猜故障方块。']),
 'stable_inputs':('检查期间输入发生变化',['等待当前写入完成后，重新打开建筑并更新预览，再检查。'])}

CHECKS['baseline_geometry']=('原建筑的整体检查未通过',['先核对源建筑的密闭、声明开口、坐标资料和必要路线。','原建筑的问题不一定由本次参数造成；用玩家／通路检查实际站姿，再分段定位。'])
CHECKS['candidate_geometry']=CHECKS['whole_building']
CHECKS['inputs_unchanged']=CHECKS['stable_inputs']

def candidate(report):
    result=[]
    for name,value in report.get('checks',{}).items():
        if value.get('passed'):continue
        title,steps=CHECKS.get(name,('检查“'+name+'”未通过',['查看原始检查原因，先核对当前源与参数；修复后重新检查。']))
        result.append(item('candidate_'+name,title,'此项检查未通过。若没有具体位置证据，只展示原始原因，不从错误文字推断坐标。',steps,evidence=dict(check=name,error=value.get('error','未提供详细原因'))))
    return result

def explain(kind,report):
    if not isinstance(report,dict):raise ValueError('检查报告须为JSON对象')
    if kind=='walk':issues=walk(report)
    elif kind=='protection':issues=protection(report)
    elif kind=='candidate':issues=candidate(report)
    else:raise ValueError('支持walk、protection或candidate报告')
    return dict(schema_version=1,kind=kind,issues=issues,source_sha256=report.get('source_sha256'),geometry_sha256=report.get('geometry_sha256'),context_sha256=report.get('context_sha256'),asset_written=False,approval_created=False,report_reverified=False,note='解释来自报告字段；复制旧报告不重新验证当前建筑。原生检查流程绑定源与当前画面，定位前须核对绑定。')

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--kind',choices=['walk','protection','candidate'],required=True);parser.add_argument('--report',type=Path,required=True);args=parser.parse_args()
    try:
        raw=args.report.read_bytes()
        if len(raw)>32*1024*1024:raise ValueError('报告超过32MiB')
        result=explain(args.kind,json.loads(raw.decode('utf-8-sig')));result['input_report_sha256']=hashlib.sha256(raw).hexdigest();print(json.dumps(result,ensure_ascii=False));return 0
    except (ValueError,OSError,KeyError,TypeError) as error:print(json.dumps(dict(error=str(error)),ensure_ascii=False));return 1
if __name__=='__main__':raise SystemExit(main())
