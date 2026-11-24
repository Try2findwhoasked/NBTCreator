"""Exercise the public replay command with real Reading Loft geometry."""
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


ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / '.agents/skills/minecraft-nbt-modeler'
sys.path.insert(0, str(SKILL / 'scripts'))

from nbt_building import failure_replay
from nbt_building.failure_replay import coverage, reduce_groups


ROUTE = dict(kind='route_segment', activity='file_books', index=1, reason='invalid_or_obstructed_feet_pose')
FACE = dict(kind='use_face', activity='file_books', index=0, part='return_desk', interface='intake',
            reason='wrong_side')


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf8')


def checksum(file):
    return sha256(file.read_bytes()).hexdigest()


def replace(group, field, value, row_id=None):
    edit = dict(field=field, value=value)
    if row_id is not None:
        edit['id'] = row_id
    return dict(id=group, edits=[edit])


def assert_nonmonotone_search():
    full = (0, 1, 2, 3)
    attempts = {}

    def check(indices):
        failed = indices in (full, (0, 2))
        return attempts.setdefault(indices, dict(status='same_failure' if failed else 'pass', groups=indices))

    assert all(check(tuple(i for i in full if i != j))['status'] == 'pass' for j in full)
    best = reduce_groups(full, check)
    assert best == (0, 2)
    assert coverage(best, attempts)['inclusion_minimal']


def verify_bundle(workspace, result):
    bundle = result['bundle']
    target = workspace / bundle['path']
    report_file = target / 'report.json'
    assert checksum(report_file) == bundle['report_sha256']
    report = json.loads(report_file.read_text(encoding='utf8'))
    assert report == {key: value for key, value in result.items() if key != 'bundle'}
    for entry in report['files'].values():
        assert checksum(target / entry['path']) == entry['sha256']
    for role in ('original', 'reduced'):
        if role not in report['files'] or f'{role}_check' not in report:
            continue
        attempt = report['checks'][report[f'{role}_check'] - 1]
        if attempt['observation'] is None:
            continue
        raw = json.loads((target / report['files'][role]['path']).read_text(encoding='utf8'))
        item = raw
        for part in attempt['observation']['pointer'].split('/')[1:]:
            item = item[int(part)] if isinstance(item, list) else item[part]
        if attempt['status'] == 'same_failure':
            assert not item['passed']
    return target / 'replay.json'


def assert_bundle_publish_is_retryable(workspace):
    output = failure_replay.output_path(workspace, 'retry')
    replay = dict(max_checks=3)
    report = dict(status='same_failure')
    receipts = dict(original=dict(code='ROUTE_FAILED'))
    with patch.object(failure_replay, 'atomic', side_effect=OSError('simulated report write failure')):
        try:
            failure_replay.publish(workspace, output, replay, report, receipts)
        except OSError as error:
            assert str(error) == 'simulated report write failure'
        else:
            raise AssertionError('expected the report write to fail')
    assert not output.exists()
    assert list(output.parent.iterdir()) == []

    retry = failure_replay.output_path(workspace, 'retry')
    result = failure_replay.publish(workspace, retry, replay, report, receipts)
    assert json.loads(verify_bundle(workspace, result).read_bytes()) == replay
    before = {file.name: checksum(file) for file in retry.iterdir()}
    try:
        failure_replay.publish(workspace, retry, dict(max_checks=1), report, receipts)
    except FileExistsError:
        pass
    else:
        raise AssertionError('a competing writer replaced the published bundle')
    assert {file.name: checksum(file) for file in retry.iterdir()} == before
    assert list(retry.parent.iterdir()) == [retry]


def exercise(output):
    output = output.resolve()
    assert_nonmonotone_search()
    workspace = output / 'workspace'
    workspace.mkdir(parents=True)

    def cli(action, name, request=None, request_file=None, exit_code=0):
        if request_file is None:
            request_file = output / (name + '-request.json')
            write(request_file, request)
        command = ['node', str(ROOT / 'scripts/cli.mjs'), '--workspace', str(workspace),
                   'architect', action, '--request', str(request_file)]
        process = subprocess.run(command, text=True, encoding='utf8', capture_output=True,
                                 timeout=180)
        assert process.returncode == exit_code, (command, process.stdout, process.stderr)
        result = json.loads(process.stdout)
        write(output / (name + '-result.json'), result)
        return result

    reading_loft = runpy.run_path(str(SKILL / 'assets/examples/reading-loft/plan.py'))['reading_loft']
    baseline = reading_loft()
    built = cli('plan-build', 'baseline', dict(plan=baseline, save_draft={}))
    assert built['checks']['architecture']['passed']
    assert built['checks']['whole_model']['routes']['passed']
    revision = built['revision_request']
    model_path = Path(revision['source'])
    if not model_path.is_absolute():
        model_path = workspace / model_path
    parent = model_path.parent.parent
    immutable_files = {p: checksum(p) for p in workspace.rglob('*') if p.is_file()}

    def replay(name, failure, max_checks=12, exit_code=0, **arguments):
        return cli('failure-replay', name, dict(revision, failure=failure, max_checks=max_checks,
                                                output=name, **arguments), exit_code=exit_code)

    blocked = reading_loft(blocked=True)
    blocked['name'] += '（无关命名）'
    purlin = next(row for row in blocked['parts'] if row['id'] == 'ridge_purlin')
    purlin['recipe']['arguments']['operations'][0]['state'] = 'stripped_oak_log[axis=z]'
    stair = replay('blocked-stair', ROUTE, failed_plan=blocked)
    assert stair['status'] == 'same_failure' and stair['remaining_groups'] == ['parts.archive_cabinet'], stair
    assert set(stair['group_ids']) == {'name', 'parts.archive_cabinet', 'parts.ridge_purlin'}
    stair_anchor = stair['checks'][stair['reduced_check'] - 1]
    assert stair_anchor['code'] == 'ROUTE_FAILED'
    assert stair_anchor['observation']['evidence']['end'] == [5.5, 5, 19.5]
    assert stair['minimality']['inclusion_minimal']

    wrong = reading_loft(wrong_side=True)
    wrong_edit = replace('operator-side', 'activities', wrong['activities'][0], 'file_books')
    name_edit = replace('unrelated-name', 'name', '归卷阁别名')
    face = replay('wrong-side', FACE, groups=[wrong_edit, name_edit])
    assert face['status'] == 'same_failure' and face['remaining_groups'] == ['operator-side'], face
    face_anchor = face['checks'][face['reduced_check'] - 1]
    assert face_anchor['code'] == 'DESIGN_INVALID'
    assert face_anchor['observation']['reason'] == 'wrong_side' and face['minimality']['inclusion_minimal']

    for result in (stair, face):
        assert result['baseline_checks'] == 1 and result['candidate_checks'] == len(result['checks'])
        replay_file = verify_bundle(workspace, result)
        repeated = cli('failure-replay', replay_file.parent.name + '-repeat', request_file=replay_file)
        for key in ('binding_sha256', 'trace_sha256', 'candidate_checks', 'checks', 'remaining_groups', 'minimality'):
            assert repeated[key] == result[key], (key, repeated[key], result[key])

    other = replay('other-failure', FACE, failed_plan=blocked)
    assert other['status'] == 'different_failure' and other['remaining_groups'] is None, other
    assert other['checks'][-1]['observation']['state'] == 'pass'
    passing = replay('passing-edit', FACE, groups=[name_edit])
    assert passing['status'] == 'pass' and passing['remaining_groups'] is None

    cabinet = next(row for row in blocked['parts'] if row['id'] == 'archive_cabinet')
    both = replay('other-failure-present', FACE, groups=[
        wrong_edit, replace('ladder-obstruction', 'parts', cabinet, cabinet['id'])])
    assert both['status'] == 'same_failure' and both['remaining_groups'] == ['operator-side'], both
    assert both['checks'][both['original_check'] - 1]['code'] == 'ROUTE_FAILED'

    locations = deepcopy(baseline['review_locations'])
    locations.append(dict(locations[0], id='additional_location'))
    required = dict(baseline['requirements'][0], review_locations=['additional_location'])
    dependent = deepcopy(wrong_edit)
    dependent['edits'].append(dict(field='requirements', id=required['id'], value=required))
    invalid = replay('invalid-intermediate', FACE, groups=[dependent, replace('location', 'review_locations', locations)])
    assert invalid['status'] == 'same_failure' and invalid['remaining_groups'] == ['operator-side', 'location']
    assert invalid['minimality']['unresolved_proper_subsets'] == 1
    assert not invalid['minimality']['inclusion_minimal']
    unresolved = next(row for row in invalid['checks'] if row['status'] == 'unreplayable')
    assert unresolved['groups'] == ['operator-side'] and '引用不存在' in unresolved['detail']

    limited = replay('budget-exhausted', ROUTE, max_checks=2, failed_plan=blocked)
    assert limited['status'] == 'budget_exhausted' and limited['candidate_checks'] == 2
    assert limited['remaining_groups'] == stair['group_ids'] and not limited['minimality']['inclusion_minimal']
    never_reached = replay('budget-before-failure', ROUTE, max_checks=1, failed_plan=blocked)
    assert never_reached['status'] == 'budget_exhausted' and never_reached['remaining_groups'] is None
    assert never_reached['candidate_checks'] == 1

    stale = cli('failure-replay', 'stale-source', dict(revision, source_sha256='0' * 64, failure=FACE,
                                                       max_checks=3, groups=[wrong_edit]))
    assert stale['status'] == 'unreplayable' and stale['error']['code'] == 'STALE_SOURCE'
    assert stale['baseline_checks'] == 0 and stale['candidate_checks'] == 0
    replay_file = verify_bundle(workspace, face)
    tampered = json.loads(replay_file.read_text(encoding='utf8'))
    tampered['max_checks'] -= 1
    mismatch = cli('failure-replay', 'binding-mismatch', tampered)
    assert mismatch['status'] == 'unreplayable' and mismatch['candidate_checks'] == 0
    overlapping = replay('overlap-rejected', FACE, groups=[wrong_edit, dict(wrong_edit, id='duplicate-edit')])
    assert overlapping['status'] == 'unreplayable' and '重叠' in overlapping['error']['error']
    conflict = cli('failure-replay', 'output-conflict', dict(
        revision, failure=FACE, max_checks=3, groups=[wrong_edit], output='wrong-side'), exit_code=1)
    assert '目录已存在' in conflict['error']
    verify_bundle(workspace, face)

    assert not (workspace / 'nbt_models/_exports').exists()
    assert {p: checksum(p) for p in immutable_files} == immutable_files
    assert set(p for p in parent.rglob('*') if p.is_file()) <= immutable_files.keys()
    assert set(workspace.rglob('model-version.json')) == {parent / 'model-version.json'}
    results = dict(passed=True, workspace=str(workspace), output=str(output), parent_preserved=True,
                   baseline=revision, cases={name: dict(status=row['status'], checks=row['candidate_checks'],
                       bundle=row['bundle']['path'], remaining_groups=row['remaining_groups'])
                       for name, row in [('blocked-stair', stair), ('wrong-side', face), ('other-failure', other),
                                         ('pass', passing), ('other-failure-present', both),
                                         ('invalid-intermediate', invalid), ('budget-exhausted', limited)]})
    write(output / 'results.json', results)
    print(json.dumps(results, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='Retain evidence in a new isolated output directory')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='nbt-replay-publish-') as workspace:
        assert_bundle_publish_is_retryable(Path(workspace).resolve())
    if args.output is None:
        with tempfile.TemporaryDirectory(prefix='nbt-building-replay-') as output:
            exercise(Path(output))
    else:
        output = args.output.resolve()
        output.mkdir(parents=True)
        exercise(output)


if __name__ == '__main__':
    main()
