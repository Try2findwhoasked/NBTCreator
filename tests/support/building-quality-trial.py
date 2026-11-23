"""Audit paired building-quality trials from locally recorded model and review evidence."""
import argparse
from collections import Counter
from hashlib import sha256
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.agents/skills/minecraft-nbt-modeler/scripts'))

from nbt_blind_review import verify_review
from nbt_building.review import load_model
from nbt_building.workflow import dispatch
from nbt_prompts import inside, relative
from nbt_working_model import value_at

REVIEW_FIELDS = ('pack', 'pack_sha256', 'notes_sha256')


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def bound_json(root, binding):
    file = (root / binding['path']).resolve()
    if not file.is_relative_to(root):
        raise ValueError('试验记录必须位于试验目录内')
    raw = file.read_bytes()
    if sha256(raw).hexdigest() != binding['sha256']:
        raise ValueError('试验记录哈希不一致：' + binding['path'])
    return json.loads(raw)


def verify_inputs(directory, workspace, case):
    technical = bound_json(directory, case['technical_receipt'])
    if 'quality' in technical or not technical['validation']['architecture']['passed']:
        raise ValueError('共同技术回执须已通过建筑检查，评分作为单独输入')
    packets = {}
    for label, binding in case['arms'].items():
        packet = bound_json(directory, binding)
        feedback = packet.pop('feedback')
        packets[binding['mode']] = (label, feedback, packet)
    if set(packets) != {'room', 'building'} or len(case['arms']) != 2:
        raise ValueError('每例应有房间评分与整栋反馈各一组')
    _, old, old_common = packets['room']
    _, new, common = packets['building']
    if (old_common != common or common['source'] != case['source'] or common['rounds'] != 1 or
            common['technical_receipt'] != case['technical_receipt'] or
            common['max_changed_voxels'] != case['budget'] or common['geometry_sha256'] != case['geometry_sha256']):
        raise ValueError('两组输入条件不一致：' + case['case'])
    baseline = load_model(workspace, case['source'])
    if (baseline.model.fingerprint() != case['geometry_sha256'] or
            technical['validation']['model_sha256'] != baseline.inspect()['model_sha256'] or
            technical['plan_sha256'] != baseline.architecture['sha256'] or
            old['geometry_sha256'] != case['geometry_sha256'] or
            old['source_sha256'] != case['source']['source_sha256']):
        raise ValueError('共同技术回执或房间评分引用了其他制作版')
    request = dict(case['source'], review={key: new['review'][key] for key in REVIEW_FIELDS})
    report = dispatch(workspace, 'quality-check', request)
    if report['summary']['gate'] != 'pass' or report['review'] is None or report['binding'] != new['binding']:
        raise ValueError('初稿的通路、审阅或清单绑定已变化')
    if not case['target_acceptance']:
        raise ValueError('试验须至少登记一项必做修复')
    measured = {item['id']: item['grade'] for dim in report['dimensions'].values() for item in dim['items']}
    for target in case['target_acceptance']:
        item = target['item']
        if (measured[item] is None or measured[item] != case['baseline_grades'][item] or
                measured[item] >= target['grade_at_least']):
            raise ValueError('必做问题的基线等级无法复验：' + item)
    return baseline, request, {mode: row[0] for mode, row in packets.items()}


def verify_round(workspace, case, base, base_request, arm, record):
    if record['input_sha256'] != case['arms'][arm]['sha256'] or record['rounds'] != 1:
        raise ValueError('修改回执没有绑定对应输入和一轮修改')
    if (not record['agent'].strip() or not record['run_id'].strip() or
            type(record['elapsed_seconds']) not in (float, int) or
            not math.isfinite(record['elapsed_seconds']) or record['elapsed_seconds'] < 0):
        raise ValueError('须提供执行 Agent、独立运行编号和耗时')
    request = record['outcome']
    model = load_model(workspace, request)
    if model.source != base.source:
        version = inside(workspace, model.source.parent.parent / 'model-version.json')
        if read(version)['parent_source_sha256'] != base.source_sha256:
            raise ValueError('续版必须直接来自试验初稿')
    if model.context != base.context or model.model.size != base.model.size:
        raise ValueError('试验续版的上下文及画布须一致')
    positions = base.model.blocks.keys() | model.model.blocks.keys() | base.walls | model.walls
    changed = sum(value_at(base.model, base.walls, pos) != value_at(model.model, model.walls, pos)
                  for pos in positions)
    report = dispatch(workspace, 'quality-check', request)
    compare = dispatch(workspace, 'quality-compare', dict(request, previous=base_request))
    if compare['binding_changes']:
        raise ValueError('续版评估清单、量表与路线条件须相同')
    comparable = {item: row for dim in compare['dimensions'].values() for item, row in dim['comparable_items'].items()}
    scored = {item['id']: item for dim in report['dimensions'].values() for item in dim['items']}
    targets = []
    for goal in case['target_acceptance']:
        observation = comparable.get(goal['item'])
        fixed = observation['current'] >= goal['grade_at_least'] if observation else None
        reviewers = sorted({row['observer'] for row in scored[goal['item']]['evidence'] if 'observer' in row})
        targets.append(dict(goal, grade=observation['current'] if observation else None, fixed=fixed, reviewers=reviewers))
    render = report['review']['render'] if report['review'] else None
    return dict(agent=record['agent'], run_id=record['run_id'], elapsed_seconds=record['elapsed_seconds'],
                changed_voxels=changed, within_budget=changed <= case['budget'], targets=targets,
                route_status=report['summary']['gate'], render=render,
                technical_status=report['technical_status'],
                blockers=[row['id'] for row in report['issues'] if row['severity'] == 'blocker'])


def blind_preferences(workspace, certification, outcomes):
    if not certification:
        return []
    if certification['reviewer_knew_groups'] is not False:
        raise ValueError('验收须由不知道反馈分组的评审完成')
    if not all(arm['render'] for arm in outcomes.values()):
        return []
    renders = {(row['render']['path'], row['render']['sha256']): mode for mode, row in outcomes.items()}
    votes = []
    for vote in certification['votes']:
        record = bound_json(workspace, vote['record'])
        binding = inside(workspace, vote['binding']['path'])
        evidence = dict(path=relative(workspace, binding), sha256=vote['binding']['sha256'])
        private = bound_json(workspace, evidence)
        source_renders = [(relative(workspace, inside(workspace, row['manifest'])), row['sha256'])
                          for row in private['renders']]
        if set(source_renders) != set(renders):
            raise ValueError('匿名实际渲染与两组续版不一致')
        vote_path = inside(workspace, vote['record']['path'])
        verify_review(workspace, binding, evidence['sha256'], vote_path, vote['record']['sha256'])
        decision = record['decision']
        shown = [renders[source_renders[i]] for i in private['assignment']]
        selected = shown['AB'.index(decision)] if decision in ('A', 'B') else decision
        votes.append(dict(actor=record['actor'], reviewer=vote['reviewer'], chosen=selected,
                          public_sha256=record['public_sha256'], shown=shown))
    return votes


def order_checks(votes):
    agents = {vote['reviewer'] for vote in votes if vote['actor'] == 'agent'}
    results = {}
    for reviewer in sorted(agents):
        records = [row for row in votes if row['actor'] == 'agent' and row['reviewer'] == reviewer and
                   row['chosen'] != 'inconclusive']
        if len({tuple(row['shown']) for row in records}) == 2:
            results[reviewer] = len({row['chosen'] for row in records}) == 1
    return results


def evaluate(path, records):
    coordinator = read(path)
    directory = path.parent
    workspace = Path(coordinator['workspace']).resolve()
    expected_cases = {case['case'] for case in coordinator['cases']}
    if (coordinator['schema_version'] != 1 or not expected_cases or
            len(expected_cases) != len(coordinator['cases']) or records.keys() - expected_cases):
        raise ValueError('试验样例不匹配')
    cases = {}
    for case in coordinator['cases']:
        baseline, base_request, modes = verify_inputs(directory, workspace, case)
        data = records.get(case['case'], {})
        rounds = data.get('rounds', {})
        if rounds.keys() - modes.values():
            raise ValueError('试验分组不匹配')
        outcomes = {mode: verify_round(workspace, case, baseline, base_request, arm, rounds[arm])
                    for mode, arm in modes.items() if arm in rounds}
        votes = []
        if len(outcomes) == 2:
            old, new = outcomes['room'], outcomes['building']
            if old['agent'] != new['agent'] or old['run_id'] == new['run_id']:
                raise ValueError('两组须由同一 Agent 在独立运行中修改')
            votes = blind_preferences(workspace, data.get('blind'), outcomes)
            if any(vote['reviewer'] == new['agent'] for vote in votes):
                raise ValueError('盲审评审须独立于建模 Agent')
        preference = {actor: dict(Counter(r['chosen'] for r in votes if r['actor'] == actor))
                      for actor in ('human', 'agent')}
        consistency = order_checks(votes)
        judges = {vote['reviewer'] for vote in votes}
        gaps = []
        if len(outcomes) != 2:
            gaps.append('missing_rounds')
        if not all(set(counts) - {'inconclusive'} for counts in preference.values()) or not consistency:
            gaps.append('missing_blind_preferences_or_reversed_order')
        for mode, row in outcomes.items():
            if not row['within_budget']:
                gaps.append(mode + '.budget_exceeded')
            if row['route_status'] not in ('pass', 'blocked'):
                gaps.append(mode + '.missing_route_evidence')
            for target in row['targets']:
                if target['fixed'] is None or set(target['reviewers']) - judges:
                    gaps.append(mode + '.' + target['item'] + '.missing_comparable_blind_grade')
        cases[case['case']] = dict(status='pending' if gaps else 'measured', gaps=gaps, outcomes=outcomes,
                                  preferences=preference, votes=votes, order_consistency=consistency,
                                  legacy_coverage=case['legacy_coverage'])
    if any(row['status'] == 'pending' for row in cases.values()):
        return dict(status='pending', cases=cases)
    counts = {mode: sum(target['fixed'] for row in cases.values() for target in row['outcomes'][mode]['targets'])
              for mode in ('room', 'building')}
    total = sum(len(row['outcomes']['building']['targets']) for row in cases.values())
    building = [row['outcomes']['building'] for row in cases.values()]
    regressions = sum(row['route_status'] == 'blocked' for row in building)
    passing = (counts['building'] > counts['room'] and regressions == 0 and
               all(arm['technical_status'] == 'validated' for arm in building))
    return dict(status='measured', cases=cases, fixed=counts, targets_per_arm=total,
                fix_rates={mode: round(100 * value / total, 2) for mode, value in counts.items()},
                new_necessary_route_regressions=regressions, comparison_gate_passed=passing)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('coordinator', type=Path)
    parser.add_argument('--records', type=Path)
    args = parser.parse_args()
    rounds = read(args.records) if args.records else {}
    result = evaluate(args.coordinator.resolve(), rounds)
    print(json.dumps(result, ensure_ascii=False, indent=2))
