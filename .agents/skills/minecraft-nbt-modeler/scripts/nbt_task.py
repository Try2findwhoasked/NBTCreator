"""Shared inspection, snapshot, preview and regression entrypoint; no approval shortcut."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def inspect_source(source, provenance=None, cameras=None):
    from nbt_refine import read_master
    from nbt_registry import effective, normalize, registry
    source = Path(source).resolve()
    model, walls = read_master(source)
    effective_blocks = []
    for p, value in sorted(model.blocks.items()):
        name, props = effective(value)
        effective_blocks.append([list(p), normalize(dict(Name=name, Properties=props))])
    result = dict(name=source.name, source=str(source), source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                  geometry_sha256=model.fingerprint(), size=list(model.size), blocks=effective_blocks,
                  wall_positions=sorted(walls), cameras=cameras or [],
                  registry_sha256=registry()['blocks_sha256'],
                  state_semantics='Version defaults applied for display only; source is unchanged',
                  verification=dict(block_states=True, seal='not_checked', routes='not_checked',
                                    saodg49='not_checked', game='not_checked', design='pending_visual_review'))
    if provenance:
        trace = json.loads(Path(provenance).read_text(encoding='utf8'))
        if trace['geometry_sha256'] != model.fingerprint():
            raise ValueError('Provenance belongs to another geometry version')
        result['owners'] = [[','.join(map(str, p)), op] for p, op in trace['owners']]
        result['operations'] = trace['operations']
    return result


def write_snapshot(source, output, provenance=None, cameras=None):
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError('Keep reviewed snapshots; choose a new output')
    result = inspect_source(source, provenance, cameras)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf8')
    return result


def regress(output):
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError('Regression output must be a new directory')
    output.mkdir(parents=True)
    results = []
    # Each existing probe has a distinct --output contract.
    files = {'check_collision_fixtures.py': 'collision.json'}
    for script in sorted((ROOT / 'scripts').glob('check_*_fixtures.py')):
        destination = output / files.get(script.name, script.stem)
        cmd = [sys.executable, '-B', str(script), '--output', str(destination)]
        run = subprocess.run(cmd, capture_output=True, text=True, encoding='utf8', errors='replace')
        results.append(dict(script=script.name, passed=run.returncode == 0, stdout=run.stdout, stderr=run.stderr))
    report = dict(passed=all(r['passed'] for r in results), suites=len(results), results=results,
                  scope='Skill synthetic fixtures only; no game, production assets or human approval')
    (output / 'regression.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    inspect = sub.add_parser('inspect')
    snapshot = sub.add_parser('snapshot')
    preview = sub.add_parser('preview')
    render = sub.add_parser('render', help='Batch texture PNGs and metadata, without computer use or download dialogs')
    for command in (inspect, snapshot, preview, render):
        command.add_argument('--source', required=True, type=Path)
        command.add_argument('--provenance', type=Path)
        command.add_argument('--cameras', type=Path, required=command is render,
                             help='View JSON array: role/eye/target with optional fov, cuts, layer and lighting')
    for command in (snapshot, preview, render):
        command.add_argument('--output', required=True, type=Path, help='New directory for render; new snapshot JSON for snapshot/preview')
    preview.add_argument('--port', type=int, default=5173)
    preview.add_argument('--no-open', action='store_true')
    render.add_argument('--width', type=int, default=960)
    render.add_argument('--height', type=int, default=640)
    render.add_argument('--quality', choices=('balanced', 'high'), default='balanced')
    render.add_argument('--timeout-ms', type=int, default=60000)
    render.add_argument('--file-prefix', default='')
    render.add_argument('--browser-executable', type=Path)
    regression = sub.add_parser('regress')
    regression.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if args.command == 'regress':
        report = regress(args.output)
        print(json.dumps(dict(passed=report['passed'], suites=report['suites'], report=str(args.output / 'regression.json'))))
        return 0 if report['passed'] else 1
    viewer = ROOT / 'assets/viewer'
    if args.command in ('preview', 'render') and not (viewer/'web-dist/frontend-manifest.json').is_file() and not (viewer / 'node_modules/@mattzh72/lodestone').exists():
        raise RuntimeError(f'Optional viewer dependencies missing. Run npm ci --prefix "{viewer}"')
    cameras = json.loads(args.cameras.read_text(encoding='utf8')) if args.cameras else None
    if args.command == 'render':
        if not (viewer / 'node_modules/playwright').exists():
            raise RuntimeError(f'Batch renderer dependencies missing. Run npm ci --prefix "{viewer}"')
        if not cameras:
            raise ValueError('render requires --cameras with a non-empty view array')
        if args.output.exists():
            raise FileExistsError('Batch output must be a new directory; preserve reviewed images')
        with tempfile.TemporaryDirectory(prefix='nbt-render-') as temporary:
            source_snapshot = Path(temporary) / 'snapshot.json'
            write_snapshot(args.source, source_snapshot, args.provenance, cameras)
            cmd = ['node', str(viewer / 'render-batch.mjs'), '--model', str(source_snapshot),
                   '--cameras', str(args.cameras.resolve()), '--output', str(args.output.resolve()),
                   '--width', str(args.width), '--height', str(args.height), '--quality', args.quality,
                   '--timeout', str(args.timeout_ms)]
            if args.file_prefix:
                cmd.extend(['--file-prefix', args.file_prefix])
            if args.browser_executable:
                cmd.extend(['--browser-executable', str(args.browser_executable.resolve())])
            return subprocess.call(cmd)
    if args.command == 'inspect':
        result = inspect_source(args.source, args.provenance, cameras)
    else:
        result = write_snapshot(args.source, args.output, args.provenance, cameras)
    print(json.dumps({k: v for k, v in result.items() if k not in ('blocks', 'wall_positions', 'owners', 'operations')}, ensure_ascii=False))
    if args.command == 'preview':
        cmd = ['node', str(viewer / 'server.mjs'), '--model', str(args.output.resolve()), '--port', str(args.port)]
        if args.no_open:
            cmd.append('--no-open')
        return subprocess.call(cmd)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
