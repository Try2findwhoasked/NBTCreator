"""Run a reproducible one-round repair comparison on two blocked drafts."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import runpy
import sys
import tempfile
from time import perf_counter
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / '.agents/skills/minecraft-nbt-modeler'
sys.path.insert(0, str(SKILL / 'scripts'))

from nbt_building import quality
from nbt_building.workflow import dispatch
from nbt_composition.change_policy import change_sets
from nbt_composition.working_model import ModelConflict, WorkingModel
from nbt_review.diagnostic_delta import summary
from nbt_runtime.modeling_session import ModellingSession


def write_receipt(path, value):
    raw = (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf8')
    path.write_bytes(raw)
    return dict(path=path.name, sha256=hashlib.sha256(raw).hexdigest())


def failed_baseline(workspace, plan):
    assess = quality.assess
    geometry = {}

    def capture(*args, **kwargs):
        result = assess(*args, **kwargs)
        if kwargs.get('style_geometry'):
            working, _ = kwargs['style_geometry']
            if working.model.fingerprint() != result['binding']['geometry_sha256']:
                raise ValueError('试验基线与失败回执的几何指纹不符')
            geometry.update(blocks=dict(working.model.blocks), walls=set(working.walls))
        return result

    with ModellingSession(workspace), patch.object(quality, 'assess', capture):
        try:
            dispatch(workspace, 'plan-build', dict(plan=plan))
        except ModelConflict as error:
            if not geometry or error.quality['summary']['gate'] != 'blocked':
                raise
            technical = dict(ok=False, code=error.code, conflicts=error.conflicts)
            findings, _ = summary('model', technical)
            return geometry, technical, list(findings.values()), error.quality
    raise AssertionError('预期失败的建筑基线通过了检查')


def identifies_problem(case, packet):
    if 'building_feedback' in packet:
        issues = packet['building_feedback']['issues']
        if case == 'blocked-stair':
            return any(row['severity'] == 'blocker' and row['target'].get('space') == 'stair_landing'
                       for row in issues)
        return any(row['severity'] == 'blocker' and row['reason'] == 'wrong_side'
                   and row['target'].get('part') == 'return_desk' and row['target'].get('interface') == 'intake'
                   for row in issues)
    if case == 'blocked-stair':
        return any(row['code'] == 'ROUTE_FAILED' and row['target'] == 'stair_landing'
                   for row in packet['diagnostics'])
    return any(row['code'] == 'USE_FACE_FAILED' and row['target'] == 'return_desk.intake'
               and row['evidence'].get('reason') == 'wrong_side' for row in packet['diagnostics'])


def repair(workspace, case, packet, baseline, arm):
    start = perf_counter()
    found = identifies_problem(case, packet)
    if not found:
        return dict(localized=False, repaired=False, seconds=round(perf_counter() - start, 3))
    with ModellingSession(workspace):
        layout = dispatch(workspace, 'layout-search',
                          dict(plan=packet['plan'], variables=packet['variables'], limit=1))
        if not layout['candidates']:
            return dict(localized=True, repaired=False, attempts=layout['attempts'],
                        seconds=round(perf_counter() - start, 3))
        candidate, = layout['candidates']
        built = dispatch(workspace, 'plan-build', dict(plan=candidate['plan'],
                         save_draft=dict(name_zh=f'归卷阁-{case}-{arm}')))
    working = WorkingModel.open(workspace, built['saved']['source'],
                                source_sha256=built['saved']['source_sha256'])
    changed, wall_changed = change_sets(baseline['blocks'], working.model.blocks,
                                        baseline['walls'], working.walls)
    checks = built['checks']['architecture']['checks']
    activity = next(row for row in checks if row['kind'] == 'activity_routes' and row['id'] == 'file_books')
    routes = built['checks']['whole_model']['routes']
    gate = built['quality']['summary']['gate']
    changed_positions = len(changed | wall_changed)
    repaired = gate == 'pass' and routes['passed'] and activity['passed'] and changed_positions <= packet['budget']
    return dict(localized=True, repaired=repaired, seconds=round(perf_counter() - start, 3),
                changed_positions=changed_positions, selected_offsets=candidate['offsets'],
                all_required_routes_passed=routes['passed'] and activity['passed'], gate=gate,
                source=built['saved']['source'], source_sha256=built['saved']['source_sha256'],
                plan_sha256=built['plan_sha256'], model_sha256=built['checks']['model_sha256'])


def main():
    reading_loft = runpy.run_path(str(SKILL / 'assets/examples/reading-loft/plan.py'))['reading_loft']
    build = ROOT / 'build'
    build.mkdir(exist_ok=True)
    output = Path(tempfile.mkdtemp(prefix='building-repair-trial-', dir=build))
    cases = {
        'blocked-stair': (reading_loft(blocked=True), [dict(
            id='cabinet', targets=[dict(kind='part', id='archive_cabinet')], offsets=[[0, 0], [0, 5], [1, 5]])]),
        'wrong-side': (reading_loft(wrong_side=True), [dict(
            id='operator', targets=[dict(kind='stop', id='file_books', index=0)], offsets=[[0, 0], [0, -3]])]),
    }
    results = {}
    for case, (plan, variables) in cases.items():
        directory = output / case
        workspace = directory / 'workspace'
        workspace.mkdir(parents=True)
        baseline, technical, diagnostics, building_feedback = failed_baseline(workspace, plan)
        failed = write_receipt(directory / 'failed-build.json', technical)
        common = dict(failed_build=failed, plan=plan, diagnostics=diagnostics,
                      variables=variables, budget=24, rounds=1)
        results[case] = {}
        for arm in ('technical', 'building'):
            packet = deepcopy(common)
            if arm == 'building':
                packet['building_feedback'] = building_feedback
            binding = write_receipt(directory / f'{arm}-input.json', packet)
            result = repair(workspace, case, packet, baseline, arm)
            results[case][arm] = dict(result, input=binding)
        first, second = results[case].values()
        results[case]['same_geometry'] = ('model_sha256' in first
                                          and first['model_sha256'] == second.get('model_sha256'))
    passed = all(row[arm]['repaired'] for row in results.values() for arm in ('technical', 'building'))
    report = dict(passed=passed, output=str(output), operator='scripted_layout_search',
                  budget_per_round=24, rounds=1, visual_preference='unmeasured', cases=results)
    write_receipt(output / 'results.json', report)
    print(json.dumps(report, ensure_ascii=False))
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
