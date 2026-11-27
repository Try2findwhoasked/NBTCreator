"""Shared inspection, snapshot, preview and regression entrypoint; no approval shortcut."""
import os
import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class SnapshotSource:
    path: Path
    model: object
    walls: set
    binding: dict
    geometry_sha256: str

    @property
    def assembly(self):
        return self.binding.get('source_kind') == 'assembly'

    def verify(self):
        if not preview_source_matches(self.path, self.binding):
            raise ValueError('Source or wall mask changed while preparing the snapshot')


def load_snapshot_source(source):
    from nbt_refine import binary_wall_mask_hash, digest, read_master
    from nbt_large_assembly import is_assembly_source, read_assembly

    source = Path(source)
    assembly = is_assembly_source(source)
    if assembly and source.is_symlink():
        raise ValueError('组装清单不能是符号链接')
    source = source.resolve()
    binding = dict(source_sha256=digest(source), binary_wall_mask_sha256=binary_wall_mask_hash(source))
    model, walls = read_assembly(source) if assembly else read_master(source)
    if assembly:
        binding['source_kind'] = 'assembly'
        binding['assembly_partitions'] = [dict(file=name, sha256=sha) for name, sha in model._assembly_binding[2]]
    return SnapshotSource(source, model, walls, binding, model.fingerprint())


def inspect_source(source, provenance=None, cameras=None, *, loaded=None):
    from nbt_registry import effective, normalize, registry

    loaded = loaded or load_snapshot_source(source)
    source = loaded.path
    model, walls = loaded.model, loaded.walls
    effective_blocks = []
    for p, value in sorted(model.blocks.items()):
        name, props = effective(value)
        effective_blocks.append([list(p), normalize(dict(Name=name, Properties=props))])
    result = dict(name=source.name, source=str(source), source_sha256=loaded.binding['source_sha256'],
                  binary_wall_mask_sha256=loaded.binding['binary_wall_mask_sha256'],
                  geometry_sha256=loaded.geometry_sha256, size=list(model.size), blocks=effective_blocks,
                  wall_positions=sorted(walls), cameras=cameras or [],
                  registry_sha256=registry()['blocks_sha256'],
                  state_semantics='Version defaults applied for display only; source is unchanged',
                  verification=dict(block_states=True, seal='not_checked', routes='not_checked',
                                    saodg49='not_checked', game='not_checked', design='pending_visual_review'))
    if loaded.assembly:
        result['source_kind'] = 'assembly'
        result['assembly_partitions'] = loaded.binding['assembly_partitions']
    if provenance:
        trace = json.loads(Path(provenance).read_text(encoding='utf8'))
        if trace['geometry_sha256'] != loaded.geometry_sha256:
            raise ValueError('Provenance belongs to another geometry version')
        result['owners'] = [[','.join(map(str, p)), op] for p, op in trace['owners']]
        result['operations'] = trace['operations']
    loaded.verify()
    return result


def write_snapshot(source, output, provenance=None, cameras=None, *, loaded=None, published_source=None):
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError('Keep reviewed snapshots; choose a new output')
    result = inspect_source(source, provenance, cameras, loaded=loaded)
    if published_source is not None:
        result['source'] = str(Path(published_source).resolve())
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf8')
    return result


def preview_source_matches(source, data):
    from nbt_refine import binary_wall_mask_hash, digest
    from nbt_large_assembly import assembly_source_matches, is_assembly_source

    if digest(source) != data['source_sha256'] or binary_wall_mask_hash(source) != data.get('binary_wall_mask_sha256'):
        return False
    if is_assembly_source(source):
        return data.get('source_kind') == 'assembly' and assembly_source_matches(source, data['source_sha256'], data.get('assembly_partitions'))
    return data.get('source_kind') != 'assembly'


def checked_preview_snapshot(file):
    """Validate a data-only control preview before rendering it, never as an NBT source."""
    from nbt_assembly import Volume
    from nbt_refine import read_master
    from nbt_registry import effective, normalize
    file = Path(file).resolve()
    raw = file.read_bytes()
    data = json.loads(raw)
    source = Path(data['source']).resolve()
    if not preview_source_matches(source,data):
        raise ValueError('Preview source or wall mask has changed; calculate a new preview')
    if not data.get('preview_only') or not isinstance(data.get('master_blocks'), list):
        raise ValueError('--snapshot requires a control preview with preview_only and master_blocks')
    baseline, _ = read_master(source)
    if list(baseline.size) != data['size']:
        raise ValueError('Preview dimensions do not match source')
    model = Volume(data['size'])
    seen = set()
    for p, value in data['master_blocks']:
        p = tuple(p)
        if len(p)!=3 or any(type(n) is not int for n in p) or not model.in_bounds(p) or p in seen:
            raise ValueError('Invalid or duplicate preview voxel')
        seen.add(p)
        model.put(p, value)
    if model.fingerprint() != data['geometry_sha256']:
        raise ValueError('Preview geometry fingerprint mismatch')
    expected = []
    for p, value in sorted(model.blocks.items()):
        name, props = effective(value)
        expected.append([list(p), normalize(dict(Name=name, Properties=props))])
    if data['blocks'] != expected:
        raise ValueError('Preview display states do not match raw geometry')
    for p in data.get('wall_positions', []):
        if len(p)!=3 or any(type(n) is not int for n in p) or not model.in_bounds(p):
            raise ValueError('Invalid preview wall mask')
    return source, raw


def publish_render_manifest(output, source, snapshot_data, preview=None, preview_bytes=None, *,
                            camera_file=None, camera_bundle=None, camera_bundle_sha256=None, workspace=None):
    from nbt_composition.object_scene import atomic
    from nbt_refine import digest

    manifest = output / 'render_manifest.json'
    report = json.loads(manifest.read_text(encoding='utf8'))
    if report['status'] not in ('awaiting_input_check', 'complete'):
        raise ValueError('Renderer did not finish the requested batch')
    try:
        preview_matches = preview is None or preview.read_bytes() == preview_bytes
        if not preview_matches or not preview_source_matches(source, snapshot_data):
            raise ValueError('Preview/source changed while rendering; output cannot be accepted')
        if camera_file is not None and digest(camera_file)!=report.get('cameras_sha256'):
            raise ValueError('相机文件在渲染期间发生变化，不能接受输出')
        for item in report.get('images',[]):
            for field,hash_field in (('image','sha256'),('metadata','metadata_sha256')):
                name=item.get(field)
                if not isinstance(name,str) or Path(name).name!=name or '/' in name or '\\' in name or digest(output/name)!=item.get(hash_field):
                    raise ValueError('渲染图片或元数据在发布前发生变化')
        binding=None
        if camera_bundle is not None or camera_bundle_sha256 is not None:
            if camera_bundle is None or camera_bundle_sha256 is None or camera_file is None or workspace is None:
                raise ValueError('参考相机清单、哈希和相机文件须同时提供')
            from nbt_review.reference_camera import checked_registered_camera
            binding=checked_registered_camera(workspace,camera_bundle,camera_bundle_sha256,camera_file,report.get('width'),report.get('height'))
        if not preview_source_matches(source,snapshot_data) or (preview is not None and preview.read_bytes()!=preview_bytes):
            raise ValueError('Preview/source changed while finalizing render evidence')
        if camera_file is not None and digest(camera_file)!=report.get('cameras_sha256'):
            raise ValueError('相机文件在发布期间发生变化，不能接受输出')
    except (OSError, ValueError, KeyError, TypeError) as error:
        report.update(status='failed', error=str(error))
        raise
    else:
        report['status'] = 'complete'
        if camera_file is not None:report['camera_file']=str(Path(camera_file).resolve())
        if snapshot_data.get('source_kind') == 'assembly':
            report['source_kind'] = 'assembly'
            report['assembly_partitions'] = snapshot_data['assembly_partitions']
        if binding is not None:report['reference_camera_binding']=binding
    finally:
        atomic(manifest, (json.dumps(report, ensure_ascii=False, indent=2) + '\n').encode('utf8'))
    print(json.dumps(dict(status=report['status'], images=len(report['images']),
                          duration_ms=report['duration_ms'], manifest=str(manifest))))


def regress(output):
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError('Regression output must be a new directory')
    output.mkdir(parents=True)
    results = []
    # Each existing probe has a distinct --output contract.
    files = {'check_collision_fixtures.py': 'collision.json'}
    fixture_dir = ROOT / 'scripts' / 'fixtures'
    suites = sorted(fixture_dir.glob('check_*_fixtures.py'))
    if not suites:
        raise FileNotFoundError(f'No regression fixtures in {fixture_dir}')
    for script in suites:
        destination = output / files.get(script.name, script.stem)
        cmd = [sys.executable, '-B', str(fixture_dir / 'run.py'), script.name, '--output', str(destination)]
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
        if command is render:
            input_group = command.add_mutually_exclusive_group(required=True)
            input_group.add_argument('--source', type=Path)
            input_group.add_argument('--snapshot', type=Path, help='Verified control preview before/after JSON; rendering only')
        else:
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
    render.add_argument('--camera-bundle', type=Path, help='Registered reference camera bundle')
    render.add_argument('--camera-bundle-sha256', help='SHA256 of the registered camera bundle')
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
        from nbt_runtime.render import render_environment
        render_env = render_environment(ROOT)
        if args.snapshot and args.provenance:
            raise ValueError('Preview already binds its geometry; do not attach source provenance')
        if not cameras:
            raise ValueError('render requires --cameras with a non-empty view array')
        if bool(args.camera_bundle)!=bool(args.camera_bundle_sha256):
            raise ValueError('参考相机清单和哈希须同时提供')
        if args.camera_bundle:
            from nbt_review.reference_camera import checked_registered_camera
            checked_registered_camera(Path.cwd(),args.camera_bundle,args.camera_bundle_sha256,args.cameras,args.width,args.height)
        if args.output.exists():
            raise FileExistsError('Batch output must be a new directory; preserve reviewed images')
        with tempfile.TemporaryDirectory(prefix='nbt-render-') as temporary:
            source_snapshot = Path(temporary) / 'snapshot.json'
            preview_source, preview_bytes = (checked_preview_snapshot(args.snapshot) if args.snapshot else (None, None))
            if preview_bytes is not None:
                source_snapshot.write_bytes(preview_bytes)
                snapshot_data = json.loads(preview_bytes)
            else:
                snapshot_data = write_snapshot(args.source, source_snapshot, args.provenance, cameras)
            cmd = [render_env.get('NBTCREATOR_NODE','node'), str(viewer / 'render-batch.mjs'), '--model', str(source_snapshot),
                   '--cameras', str(args.cameras.resolve()), '--output', str(args.output.resolve()),
                   '--width', str(args.width), '--height', str(args.height), '--quality', args.quality,
                   '--timeout', str(args.timeout_ms), '--defer-completion']
            if args.file_prefix:
                cmd.extend(['--file-prefix', args.file_prefix])
            if args.browser_executable:
                cmd.extend(['--browser-executable', str(args.browser_executable.resolve())])
            code = subprocess.call(cmd,env=render_env)
            if code == 0:
                publish_render_manifest(args.output.resolve(), preview_source or Path(snapshot_data['source']),
                                        snapshot_data, args.snapshot, preview_bytes,camera_file=args.cameras.resolve(),
                                        camera_bundle=args.camera_bundle,camera_bundle_sha256=args.camera_bundle_sha256,workspace=Path.cwd())
            return code
    if args.command == 'inspect':
        result = inspect_source(args.source, args.provenance, cameras)
    else:
        result = write_snapshot(args.source, args.output, args.provenance, cameras)
    print(json.dumps({k: v for k, v in result.items() if k not in ('blocks', 'wall_positions', 'owners', 'operations')}, ensure_ascii=False))
    if args.command == 'preview':
        cmd = [os.environ.get('NBTCREATOR_NODE','node'), str(viewer / 'server.mjs'), '--model', str(args.output.resolve()), '--port', str(args.port)]
        if args.no_open:
            cmd.append('--no-open')
        return subprocess.call(cmd,env=dict(os.environ,**({'ELECTRON_RUN_AS_NODE':'1'} if os.environ.get('NBTCREATOR_NODE_IS_ELECTRON')=='1' else {})))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
