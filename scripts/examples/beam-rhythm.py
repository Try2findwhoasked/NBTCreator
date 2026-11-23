"""Create a synthetic host, rank and preview frames through the shared CLI."""
import argparse
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def run(workspace, *, adopt=False):
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

    saved = model('setup', dict(
        size=[24, 12, 72],
        context=dict(mode='standalone', protected_boxes=[dict(lo=[4, 2, 9], hi=[7, 8, 9])],
                     reserved_boxes=[dict(lo=[10, 2, 0], hi=[12, 3, 71])],
                     require_routes=True, start=[11.5, 2, 4.5], targets=[[11.5, 2, 65.5]],
                     max_changed_blocks=2000),
        actions=[dict(method='apply_operations', operations=[
            dict(kind='box', label='合成宿主地面', lo=[0, 1, 0], hi=[23, 1, 71], state='smooth_stone'),
        ])],
        save_draft=dict(name_zh='梁架节奏样例'),
    ))['saved']
    source = dict(source=saved['source'], source_sha256=saved['source_sha256'])
    goal = dict(id='hall_frames', region=dict(lo=[4, 2, 0], hi=[17, 10, 71]),
                origin_xy=[5, 2], span_x=13, post_height=7, beam_height=2,
                count=9, target_pitch=6, pitches=[5, 6, 7], starts=list(range(9, 15)),
                materials=dict(post='stripped_spruce_log', beam='dark_oak_log'), anchor_z=10)
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
    if adopt:
        production = model('adopt', adopt_request)['saved']
        result['saved_source'] = production['source']
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, required=True, help='新建的合成创作工作区')
    parser.add_argument('--adopt', action='store_true', help='显式采用并保存合成示例的制作版')
    args = parser.parse_args()
    print(json.dumps(run(args.workspace, adopt=args.adopt), ensure_ascii=False, indent=2))
