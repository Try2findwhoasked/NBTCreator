"""Replay versioned whole-building tasks on the shared authoring engine."""

import argparse
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
from unittest.mock import patch
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / '.agents/skills/minecraft-nbt-modeler'
sys.path.insert(0, str(SKILL / 'scripts'))

from nbt_building import quality
from nbt_building.plan import fingerprint, normalize
from nbt_building.review import load_model
from nbt_building.workflow import dispatch
from nbt_composition.change_policy import change_sets
from nbt_composition.object_scene import engine_hash
from nbt_composition.working_model import ModelConflict
from nbt_review.blind_review import prepare_review
from nbt_review.diagnostic_delta import summary
from nbt_runtime.modeling_session import ModellingSession

SPEC_FILE = Path(__file__).with_name('building-generation-cases.json')
FIXTURE = SKILL / 'assets/examples/reading-loft/plan.py'
ARMS = ('technical', 'building')
SCRIPTED = dict(kind='fixture', id='scripted-diagnostic-replay-v1')
FIXED_FIELDS = ('size', 'context', 'spaces', 'requirements', 'quality')
MOVABLE_STOPS = {'open-activity': (0, 3), 'blocked-stair': (3,), 'wrong-side': (0,), 'cabinet-trim': ()}
RENDER_SIZE = (800, 520)


def read(path):
    return json.loads(path.read_bytes())


def write(path, value, root=None):
    raw = (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + '\n').encode('utf8')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return dict(path=path.relative_to(root).as_posix() if root else path.name, sha256=sha256(raw).hexdigest())


def binding(workspace, built):
    saved = built['saved']
    source = (workspace / saved['source']).resolve().relative_to(workspace.resolve()).as_posix()
    return dict(source=source, source_sha256=saved['source_sha256'])


def geometry(model):
    return dict(blocks=dict(model.model.blocks), walls=set(model.walls))


def build(workspace, request):
    # The production engine deliberately rejects these broken drafts before saving.
    # Capture only the detached geometry that produced the failure receipt.
    rejected = None
    assess = quality.assess

    def capture(*args, **kwargs):
        nonlocal rejected
        result = assess(*args, **kwargs)
        if kwargs.get('style_geometry'):
            model, _ = kwargs['style_geometry']
            if model.model.fingerprint() == result['binding']['geometry_sha256']:
                rejected = geometry(model)
        return result

    try:
        with ModellingSession(workspace), patch.object(quality, 'assess', capture):
            built = dispatch(workspace, 'plan-build', request)
        model = load_model(workspace, binding(workspace, built))
        return built, geometry(model), None, built.get('quality')
    except ModelConflict as error:
        return None, rejected, dict(ok=False, code=error.code, conflicts=error.conflicts), getattr(error, 'quality', None)


def diagnoses(technical):
    issues, _ = summary('model', technical)
    return list(issues.values())


def locates(case, packet):
    if case not in ('blocked-stair', 'wrong-side'):
        return None
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


def scripted_plan(case, packet, attempt):
    plan = deepcopy(packet['starting_plan'] or packet['fixture_plan'])
    cabinet = next(part for part in plan['parts'] if part['id'] == 'archive_cabinet')
    if case == 'cabinet-trim':
        cabinet['recipe']['arguments']['operations'][-1]['state'] = packet['task']['edit']['state']
    if attempt == 2 and locates(case, packet):
        if case == 'blocked-stair':
            cabinet['position'][2] += 5
        if case == 'wrong-side':
            plan['activities'][0]['stops'][0]['feet'][2] -= 3
    return plan


def prepare(output, workspace, spec):
    reading_loft = runpy.run_path(str(FIXTURE))['reading_loft']
    reference = reading_loft()
    open_model, open_geometry, _, open_quality = build(workspace, dict(plan=reference, save_draft=dict(name_zh='归卷阁基线')))
    if not open_model or open_quality['summary']['gate'] != 'pass':
        raise ValueError('归卷阁基线未通过')
    review = dispatch(workspace, 'review-prepare', dict(binding(workspace, open_model),
                      output='nbt_models/_workspaces/benchmark-camera-source'))
    views = {row['id']: row for row in read(Path(review['cameras']))}
    cameras = workspace / 'nbt_models/_workspaces/benchmark-cameras.json'
    camera_ref = write(cameras, [views[view] for view in spec['review_views']], output)
    budget = dict(candidate_attempts_per_case=spec['candidate_budget'], candidates_per_round=1,
                  repair_rounds_per_case=spec['candidate_budget'] - 1)
    cases = {}
    for case, task in spec['cases'].items():
        starting = None if case == 'open-activity' else reading_loft(
            blocked=case == 'blocked-stair', wrong_side=case == 'wrong-side')
        before = open_geometry if starting else None
        technical, feedback = None, None
        initial_ref = None
        if case in ('blocked-stair', 'wrong-side'):
            _, before, technical, feedback = build(workspace, dict(plan=starting))
            if not before or not technical or not feedback or feedback['summary']['gate'] != 'blocked':
                raise ValueError(f'失败基线无法重演 {case}')
            initial_ref = write(output / 'inputs' / case / 'initial-check.json', technical, output)
        if 'edit' in task and any(before['blocks'].get(tuple(pos)) != task['edit']['previous_state']
                                  for pos in task['edit']['positions']):
            raise ValueError('局部修改基线的材料或方块位置已变化')
        case_budget = dict(budget, max_changed_positions=task['max_changed_positions'])
        common = dict(case=case, benchmark_version=spec['version'], task=task, budget=case_budget,
                      starting_plan=starting, diagnostics=diagnoses(technical) if technical else [],
                      initial_check=initial_ref,
                      starting_geometry_sha256=(feedback['binding']['geometry_sha256'] if feedback else
                                               open_quality['binding']['geometry_sha256'] if starting else None),
                      starting_source=binding(workspace, open_model) if case == 'cabinet-trim' else None,
                      contract=dict(fixed_plan={key: reference[key] for key in (*FIXED_FIELDS, 'activities')},
                                    movable_stop_indices=MOVABLE_STOPS[case], required_stair='archive_stair'),
                      review=dict(cameras=camera_ref, width=RENDER_SIZE[0], height=RENDER_SIZE[1]))
        packets, inputs = {}, {}
        for arm in ARMS:
            packet = dict(common, feedback_mode=arm)
            if arm == 'building':
                packet['building_feedback'] = feedback or None
            inputs[arm] = write(output / 'inputs' / case / f'{arm}.json', packet, output)
            packets[arm] = packet
        if technical and not all(locates(case, packet) for packet in packets.values()):
            raise ValueError(f'失败基线缺少固定问题的诊断 {case}')
        cases[case] = dict(packets=packets, inputs=inputs, before=before, budget=case_budget)
    return reference, cameras, camera_ref, cases


def fixed_conditions(plan, reference, case):
    actual, expected = normalize(plan), normalize(reference)
    fixed = {name: actual[name] == expected[name] for name in FIXED_FIELDS}
    actual_activities = deepcopy(actual['activities'])
    expected_activities = expected['activities']
    expected_by_id = {row['id']: row for row in expected_activities}
    for row in actual_activities:
        # Operating poses may move with a working face on the same floor.
        desired = expected_by_id.get(row['id'], {}).get('stops', [])
        for index, (stop, base) in enumerate(zip(row['stops'], desired)):
            if index in MOVABLE_STOPS[case] and stop['feet'][1] == base['feet'][1]:
                stop['feet'] = base['feet']
    fixed['activity_contract'] = actual_activities == expected_activities
    fixed['required_stair'] = any(row['id'] == 'archive_stair' for row in actual['stairs'])
    return fixed


def local_conditions(task, before, after):
    if after is None:
        return dict(local_edit=None), dict(untouched_outside_edit=None, wall_membership_unchanged=None)
    cells = {tuple(pos) for pos in task['edit']['positions']}
    blocks, walls = change_sets(before['blocks'], after['blocks'], before['walls'], after['walls'])
    return (dict(local_edit=all(after['blocks'].get(pos) == task['edit']['state'] for pos in cells)),
            dict(untouched_outside_edit=not ((blocks | walls) - cells), wall_membership_unchanged=not walls))


def measured(build_result, technical, feedback):
    if feedback is None:
        return dict(entrance_routes=None, activity_segments=None, use_faces=None, building_gate=None)
    evidence = feedback['evidence']
    activity = next((row for row in evidence['checks'] + evidence['conflicts']
                     if row.get('kind') == 'activity_routes' and row.get('id') == 'file_books'), None)
    routes = build_result['checks']['whole_model']['routes']['passed'] if build_result else None
    if technical and technical['code'] == 'ROUTE_FAILED':
        routes = False
    return dict(entrance_routes=routes,
                activity_segments=[row['passed'] for row in activity['segments']] if activity else None,
                use_faces={f"{row['part']}.{row['interface']}": dict(passed=row['passed'], reason=row.get('reason'))
                           for row in activity['use_faces']} if activity else None,
                building_gate=feedback['summary']['gate'])


def evaluate_candidate(workspace, case, arm, attempt, plan, reference, row):
    task = row['packets'][arm]['task']
    local = 'edit' in task
    receipt = dict(attempt=attempt, plan_sha256=fingerprint(plan), passed=False, changed_positions=None,
                   within_change_budget=None, hits=measured(None, None, None), preservation={}, source=None)
    try:
        receipt['preservation'] = fixed_conditions(plan, reference, case)
        if local:
            hits, preservation = local_conditions(task, row['before'], None)
            receipt['hits'].update(hits)
            receipt['preservation'].update(preservation)
        if False in receipt['preservation'].values():
            return dict(receipt, error='fixed_task_contract_changed')
        label = f'归卷阁-{case}-{arm}-{attempt}'
        parent = {}
        if local:
            # Independent histories with byte-identical masters let both arms
            # edit the same baseline without racing the engine's head check.
            base, baseline, _, _ = build(workspace, dict(plan=reference, save_draft=dict(name_zh=label)))
            origin = row['packets'][arm]['starting_source']
            if base is None or baseline != row['before'] or binding(workspace, base)['source_sha256'] != origin['source_sha256']:
                raise RuntimeError('局部修改的独立初稿与共同制作源不一致')
            parent = base['revision_request']
        built, after, technical, feedback = build(workspace, dict(plan=plan, save_draft=dict(name_zh=label), **parent))
    except (ValueError, TypeError, KeyError) as error:
        return dict(receipt, error=str(error))
    receipt['hits'].update(measured(built, technical, feedback))
    if local:
        hits, preservation = local_conditions(task, row['before'], after)
        receipt['hits'].update(hits)
        receipt['preservation'].update(preservation)
    if row['before'] is not None and after is not None:
        changed, walls = change_sets(row['before']['blocks'], after['blocks'], row['before']['walls'], after['walls'])
        receipt['changed_positions'] = len(changed | walls)
        receipt['within_change_budget'] = receipt['changed_positions'] <= task['max_changed_positions']
    if case == 'wrong-side':
        receipt['preservation']['existing_blocks_and_walls'] = (
            receipt['changed_positions'] == 0 if receipt['changed_positions'] is not None else None)
    if technical:
        receipt.update(error=technical['code'], diagnostics=diagnoses(technical))
        return receipt
    revision = dict(binding(workspace, built), model_sha256=built['checks']['model_sha256'],
                    geometry_sha256=feedback['binding']['geometry_sha256'])
    hits = receipt['hits']
    checks_passed = (hits['building_gate'] == 'pass' and hits['entrance_routes'] is True and
                     hits['activity_segments'] == [True] * 3 and
                     set(hits['use_faces'] or ()) == {'return_desk.intake', 'archive_cabinet.shelves'} and
                     all(face['passed'] for face in hits['use_faces'].values()))
    receipt.update(source=revision, passed=checks_passed and
                   receipt['within_change_budget'] is not False and all(receipt['preservation'].values()) and
                   (not local or receipt['hits']['local_edit']))
    if local:
        receipt['parent_source_sha256'] = parent['source_sha256']
    return receipt


def external_candidates(manifest, cases):
    if manifest is None:
        return dict.fromkeys(ARMS)
    manifest = manifest.resolve()
    data = read(manifest)
    if data.get('schema_version') != 1 or set(data.get('arms', {})) != set(ARMS):
        raise ValueError('候选清单须为版本 1，指定 technical 和 building 两组')
    for arm, group in data['arms'].items():
        if group is None:
            continue
        operator = group['operator']
        if operator['kind'] not in ('agent', 'layout', 'fixture', 'human') or not operator['id'].strip():
            raise ValueError(f'候选操作者无效 {arm}')
        if set(group['cases']) != set(cases):
            raise ValueError(f'候选清单的案例集合不匹配 {arm}')
        for case, record in group['cases'].items():
            row = cases[case]
            if record['input_sha256'] != row['inputs'][arm]['sha256']:
                raise ValueError(f'候选清单引用了其他输入 {case}/{arm}')
            files = record['candidates']
            if not isinstance(files, list) or len(files) > row['budget']['candidate_attempts_per_case']:
                raise ValueError(f'候选数量超预算或格式错误 {case}/{arm}')
            plans = []
            for file in files:
                path = (manifest.parent / file).resolve()
                if not path.is_relative_to(manifest.parent):
                    raise ValueError('候选文件须位于清单目录内')
                raw = path.read_bytes()
                plan = json.loads(raw)
                if not isinstance(plan, dict):
                    raise ValueError(f'候选文件须包含建筑方案对象 {file}')
                plans.append((plan.get('plan', plan), dict(path=file, sha256=sha256(raw).hexdigest())))
            record['candidates'] = plans
    return data['arms']


def run_arm(workspace, case, arm, reference, row, external):
    packet = row['packets'][arm]
    candidates = external['cases'][case]['candidates'] if external else None
    attempts = []
    for index in range(row['budget']['candidate_attempts_per_case'] if candidates is None else len(candidates)):
        if candidates is None:
            plan = scripted_plan(case, dict(packet, fixture_plan=reference), index + 1)
            submission = None
        else:
            plan, submission = candidates[index]
        result = evaluate_candidate(workspace, case, arm, index + 1, plan, reference, row)
        attempts.append(dict(result, submission=submission))
        if result['passed']:
            break
    return dict(operator=external['operator'] if external else SCRIPTED, input=row['inputs'][arm],
                submitted_candidates=len(candidates) if candidates is not None else None,
                candidates_evaluated=len(attempts), first_pass=bool(attempts and attempts[0]['passed']),
                repair_rounds=max(0, len(attempts) - 1), passed=bool(attempts and attempts[-1]['passed']),
                initial_diagnostic_match=locates(case, packet), attempts=attempts)


def blind_pair(workspace, case, task, cameras, arms):
    manifests = []
    for arm, outcome in arms.items():
        source = outcome['attempts'][-1]['source']
        destination = workspace / 'nbt_models/_workspaces/benchmark-renders' / case / arm
        subprocess.run(['node', str(ROOT / 'scripts/cli.mjs'), '--workspace', str(workspace), 'render',
                        '--source', source['source'], '--cameras', str(cameras), '--output', str(destination),
                        '--width', str(RENDER_SIZE[0]), '--height', str(RENDER_SIZE[1])],
                       check=True, timeout=180, stdout=subprocess.DEVNULL)
        path = destination / 'render_manifest.json'
        report = read(path)
        if (report['source_sha256'] != source['source_sha256'] or report['geometry_sha256'] != source['geometry_sha256']):
            raise ValueError('实景出图与验收制作源不一致')
        manifests.append(dict(manifest=path.relative_to(workspace).as_posix(), sha256=sha256(path.read_bytes()).hexdigest()))
    result = prepare_review(workspace, dict(renders=manifests, scope=task['review_question'], crop=None,
                                           output=f'nbt_models/_workspaces/reference-reviews/{case}'))
    changed = [row['changed_pixels'] for row in read(Path(result['public']))['views']]
    for key in ('public', 'binding'):
        result[key] = Path(result[key]).relative_to(workspace).as_posix()
    return dict(result, status='pending_human_review', scores=None, changed_pixels=changed, renders=manifests)


def run(output, *, render=False, manifest=None, prepare_only=False):
    output = output.resolve()
    workspace = output / 'workspace'
    workspace.mkdir(parents=True)
    spec = read(SPEC_FILE)
    reference, cameras, camera_ref, cases = prepare(output, workspace, spec)
    meta = dict(schema_version=1, benchmark_version=spec['version'],
                task_suite_sha256=sha256(SPEC_FILE.read_bytes()).hexdigest(), fixture_plan_sha256=fingerprint(reference),
                fixture_file_sha256=sha256(FIXTURE.read_bytes()).hexdigest(),
                engine_sha256=engine_hash(),
                app_version=read(ROOT / 'package.json')['version'], workspace='workspace',
                review=dict(cameras=camera_ref, views=spec['review_views'], width=RENDER_SIZE[0], height=RENDER_SIZE[1]),
                approval_created=False, nbt_exported=False)
    if prepare_only:
        return write(output / 'prepared.json', dict(meta, cases={case: row['inputs'] for case, row in cases.items()}))
    external = external_candidates(manifest, cases)
    results = {}
    for case, row in cases.items():
        arms = {arm: run_arm(workspace, case, arm, reference, row, external[arm]) for arm in ARMS}
        both_passed = all(arm['passed'] for arm in arms.values())
        visual = dict(status='render_not_requested' if both_passed else 'no_passed_pair', scores=None)
        if render and both_passed:
            visual = blind_pair(workspace, case, spec['cases'][case], cameras, arms)
        results[case] = dict(task=spec['cases'][case], budget=row['budget'], arms=arms, visual=visual)
    counts = {arm: dict(first_pass_count=sum(row['arms'][arm]['first_pass'] for row in results.values()),
                        final_pass_count=sum(row['arms'][arm]['passed'] for row in results.values()),
                        repair_rounds=sum(row['arms'][arm]['repair_rounds'] for row in results.values()),
                        candidates_evaluated=sum(row['arms'][arm]['candidates_evaluated'] for row in results.values()))
              for arm in ARMS}
    archive = None
    public = {case: workspace / row['visual']['public'] for case, row in results.items() if 'public' in row['visual']}
    if public:
        path = output / 'blind-review.zip'
        with ZipFile(path, 'x', compression=ZIP_DEFLATED) as pack:
            for case, manifest_path in public.items():
                for file in sorted(manifest_path.parent.rglob('*')):
                    if file.is_file():
                        pack.write(file, f'{case}/{file.relative_to(manifest_path.parent).as_posix()}')
        archive = dict(path=path.name, sha256=sha256(path.read_bytes()).hexdigest())
    return write(output / 'report.json', dict(meta, case_count=len(results), counts=counts, cases=results,
                                               public_review_archive=archive))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='New directory for the report and isolated workspace')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--prepare', action='store_true', help='Write frozen task inputs for external operators')
    mode.add_argument('--candidates', type=Path, help='Replay an external candidate manifest')
    parser.add_argument('--render', action='store_true', help='Render passed pairs with production Chromium for blind review')
    args = parser.parse_args()
    if args.prepare and args.render:
        parser.error('--prepare cannot render candidate pairs')
    if args.output is None:
        build_root = ROOT / 'build'
        build_root.mkdir(exist_ok=True)
        output = Path(tempfile.mkdtemp(prefix='building-generation-', dir=build_root))
    else:
        output = args.output.resolve()
        output.mkdir(parents=True, exist_ok=False)
    result = run(output, render=args.render, manifest=args.candidates, prepare_only=args.prepare)
    print(json.dumps(dict(result, path=str(output / result['path'])), ensure_ascii=False))


if __name__ == '__main__':
    main()
