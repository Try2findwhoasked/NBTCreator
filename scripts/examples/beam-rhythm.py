"""Create a synthetic host, rank and preview frames through the shared CLI."""
import argparse
import json
from pathlib import Path
import subprocess
from time import perf_counter

ROOT = Path(__file__).resolve().parents[2]


def local_probe_operations():
    """Two aligned frames, a shifted lintel, a partial post and missing members."""
    def box(label, lo, hi, state):
        return dict(kind='box', label=label, lo=lo, hi=hi, state=state)

    operations = []
    for z in (10, 16, 22, 28):
        left_top = 4 if z == 28 else 8
        operations.extend([
            box('既有左柱', [5, 2, z], [5, left_top, z], 'stripped_spruce_log[axis=y]'),
            box('既有右柱', [17, 2, z], [17, 8, z], 'stripped_spruce_log[axis=y]'),
        ])
    for z in (10, 16, 23):
        operations.append(box('既有横梁', [5, 9, z], [17, 10, z], 'dark_oak_log[axis=x]'))
    return operations


def run(workspace, *, adopt=False, local_probe=False):
    workspace = Path(workspace).resolve()
    workspace.mkdir(parents=True, exist_ok=False)

    def model(name, request):
        file = workspace / f'{name}.json'
        file.write_text(json.dumps(request, ensure_ascii=False, indent=2), encoding='utf-8')
        result = subprocess.run(
            ['node', str(ROOT / 'scripts/cli.mjs'), '--workspace', str(workspace), 'model', '--request', str(file)],
            capture_output=True, encoding='utf-8', cwd=ROOT,
        )
        if result.returncode:
            raise RuntimeError(result.stdout or result.stderr)
        return json.loads(result.stdout)['result']

    protected_z = 11 if local_probe else 9
    operations = [dict(kind='box', label='合成宿主地面', lo=[0, 1, 0], hi=[23, 1, 71], state='smooth_stone')]
    if local_probe:
        operations.extend(local_probe_operations())
    saved = model('setup', dict(
        size=[24, 12, 72],
        context=dict(mode='standalone', protected_boxes=[
                         dict(lo=[4, 2, protected_z], hi=[7, 8, protected_z])],
                     reserved_boxes=[dict(lo=[10, 2, 0], hi=[12, 3, 71])],
                     require_routes=True, start=[11.5, 2, 4.5], targets=[[11.5, 2, 65.5]],
                     max_changed_blocks=2000),
        actions=[dict(method='apply_operations', operations=operations)],
        save_draft=dict(name_zh='梁架节奏样例'),
    ))['saved']
    source = dict(source=saved['source'], source_sha256=saved['source_sha256'])
    goal = dict(id='hall_frames', region=dict(lo=[4, 2, 0], hi=[17, 10, 71]),
                origin_xy=[5, 2], span_x=13, post_height=7, beam_height=2,
                count=9, target_pitch=6, pitches=[5, 6, 7], starts=list(range(9, 15)),
                materials=dict(post='stripped_spruce_log', beam='dark_oak_log'), anchor_z=10)
    comparison = {}
    if local_probe:
        goal.update(anchor_z=9, clearance_height=2)
        started = perf_counter()
        baseline = model('search-baseline', dict(source, actions=[dict(method='beam_rhythm', goal=goal)]))['actions'][0]
        baseline_ms = (perf_counter() - started) * 1000
        baseline_file = workspace / 'beam-rhythm-baseline.json'
        baseline_file.write_text(json.dumps(baseline, ensure_ascii=False, indent=2), encoding='utf-8')
        goal['local_match'] = True
        started = perf_counter()
        probe = model('search-local-score', dict(source, actions=[dict(method='beam_rhythm', goal=goal)]))['actions'][0]
        local_ms = (perf_counter() - started) * 1000
        comparison.update(baseline_report=str(baseline_file), baseline_start_z=baseline['best']['start_z'],
                          local_start_z=probe['best']['start_z'],
                          cli_ms=dict(baseline=round(baseline_ms, 1), local=round(local_ms, 1)))
    selection = dict(method='beam_rhythm', goal=goal, preview=dict(output='beam-rhythm-preview', cameras=[
        dict(role='overview', eye=[37, 23, -19], target=[11, 4, 33]),
        dict(role='frame', eye=[21, 12, 4], target=[11, 5, 15]),
    ]))
    report = model('search', dict(source, actions=[selection]))['actions'][0]
    report_file = workspace / 'beam-rhythm-report.json'
    report_file.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    best = report['best']
    if best is None:
        raise RuntimeError(f'梁架示例没有合法候选。详见 {report_file}')
    chosen = dict(pitch=best['pitch'], start_z=best['start_z'])
    adopted = dict(method='adopt_beam_rhythm', goal=goal, candidate_sha256=best['candidate_sha256'], **chosen)
    adopt_request = dict(source, actions=[adopted], validate=True, save_draft={})
    adoption_file = workspace / 'adopt.json'
    adoption_file.write_text(json.dumps(adopt_request, ensure_ascii=False, indent=2), encoding='utf-8')
    result = dict(evaluated=report['evaluated'], eligible=report['eligible'], rejected=report['rejection_counts'],
                  selection=chosen, starts_z=best['measured']['starts_z'], report=str(report_file),
                  preview=report['preview'], adoption_request=str(adoption_file))
    if local_probe:
        result['comparison'] = comparison
    if adopt:
        production = model('adopt', adopt_request)['saved']
        result['saved_source'] = production['source']
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, required=True, help='新建的合成创作工作区')
    parser.add_argument('--adopt', action='store_true', help='显式采用并保存合成示例的制作版')
    parser.add_argument('--local-probe', action='store_true', help='对照同一宿主启用局部匹配前后的结果')
    args = parser.parse_args()
    print(json.dumps(run(args.workspace, adopt=args.adopt, local_probe=args.local_probe), ensure_ascii=False, indent=2))
