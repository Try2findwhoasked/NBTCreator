"""Compile, render and compare frozen Minecraft Java 1.20.1 furniture designs."""
import argparse
import hashlib
import itertools
import json
import math
import re
import subprocess
import sys
from pathlib import Path


HERE = Path(__file__).resolve()
DEFAULT_ENGINE = HERE.parents[2] / 'minecraft-nbt-modeler'
DIRECTIONS = ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))


def read(path):
    def unique(pairs):
        result = dict(pairs)
        if len(result) != len(pairs):
            raise ValueError(f'{path}: duplicate JSON key')
        return result

    return json.loads(path.read_text(encoding='utf-8-sig'), object_pairs_hook=unique)


def write(path, data):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def identifier(value):
    require(isinstance(value, str) and re.fullmatch('[a-z][a-z0-9_-]{0,47}', value),
            f'Invalid id: {value!r}')
    return value


def text(value, label):
    require(isinstance(value, str) and value.strip(), f'{label} must be nonempty text')


def fields(obj, required, optional=()):
    require(isinstance(obj, dict) and set(required) <= obj.keys() <= set(required) | set(optional),
            f'Expected fields {required}; optional {optional}')


def triplet(value, label):
    require(isinstance(value, list) and len(value) == 3 and all(type(x) is int for x in value),
            f'{label} must be three integers in XYZ order')
    return tuple(value)


def box(data, size):
    fields(data, ('lo', 'hi'))
    lo, hi = (triplet(data[key], key) for key in ('lo', 'hi'))
    require(all(0 <= a <= b < n for a, b, n in zip(lo, hi, size)), 'Box is outside the model')
    return lo, hi


def points(lo, hi):
    return itertools.product(*(range(a, b + 1) for a, b in zip(lo, hi)))


def neighbors(position):
    for delta in DIRECTIONS:
        yield tuple(a + b for a, b in zip(position, delta))


def connected_cells(occupancy):
    pending = [next(iter(occupancy))]
    seen = set(pending)
    while pending:
        for pos in neighbors(pending.pop()):
            if pos in occupancy and pos not in seen:
                pending.append(pos)
                seen.add(pos)
    return len(seen) == len(occupancy)


def intent(spec, photo):
    fields(spec, ('schema_version', 'name', 'category', 'source', 'size', 'front',
                  'parts', 'joins', 'cameras', 'candidates', 'gameplay'))
    require(type(spec['schema_version']) is int and spec['schema_version'] == 1,
            'Expected furniture spec v1')
    text(spec['name'], 'name')
    text(spec['gameplay'], 'gameplay')
    require(spec['category'] in ('chair', 'table', 'cabinet'), 'Expected chair, table or cabinet')
    require(spec['front'] == 'north', 'Local front must face north (-Z)')
    size = triplet(spec['size'], 'size')
    require(all(1 <= n <= 64 for n in size), 'Component axes must be 1..64')
    require(size[1] <= 2, 'Interior furniture must fit within two blocks in Y')
    source = spec['source']
    fields(source, ('kind', 'title'), ('url', 'image_url', 'license', 'credit', 'sha256'))
    text(source['title'], 'source.title')
    require(source['kind'] in ('photo', 'synthetic'), 'Expected photo or synthetic source')
    if source['kind'] == 'photo':
        for key in ('url', 'license', 'credit'):
            text(source.get(key), f'source.{key}')
        require(re.fullmatch('[a-f0-9]{64}', source.get('sha256') or ''),
                'Freeze the original image SHA256')
        if photo is not None:
            require(sha(photo) == source['sha256'], 'Reference photo SHA256 mismatch')
    else:
        require(photo is None, 'A synthetic fixture has no reference photo')
    parts = {}
    require(isinstance(spec['parts'], list) and spec['parts'], 'Provide part intent')
    for part in spec['parts']:
        fields(part, ('id', 'role', 'material', 'evidence', 'feature'), ('repeat_group',))
        name = identifier(part['id'])
        require(name not in parts, f'Duplicate part: {name}')
        require(part['evidence'] in ('visible', 'inferred', 'synthetic'), f'Invalid evidence for {name}')
        require((part['evidence'] == 'synthetic') == (source['kind'] == 'synthetic'),
                f'Evidence and source type disagree for {name}')
        for key in ('role', 'material', 'feature'):
            text(part[key], key)
        if 'repeat_group' in part:
            identifier(part['repeat_group'])
        parts[name] = part
    require(isinstance(spec['joins'], list), 'joins must be a list')
    joins = set()
    for pair in spec['joins']:
        require(isinstance(pair, list) and len(pair) == 2 and all(p in parts for p in pair)
                and pair[0] != pair[1], f'Invalid part join: {pair!r}')
        edge = tuple(sorted(pair))
        require(edge not in joins, f'Duplicate part join: {pair!r}')
        joins.add(edge)
    require(isinstance(spec['cameras'], list) and spec['cameras'], 'Provide shared camera views')
    for view in spec['cameras']:
        eye = view.get('eye') if isinstance(view, dict) else None
        require(isinstance(eye, list) and len(eye) == 3 and
                all(type(v) in (int, float) and math.isfinite(v) for v in eye) and 0 < eye[1] <= 2,
                'Review camera eye must be finite XYZ with Y above 0 and at most 2 blocks')
    require(isinstance(spec['candidates'], dict) and 1 <= len(spec['candidates']) <= 2,
            'Provide one or two candidates')
    return size, parts, joins


def join_evidence(owners, values, declared):
    """Check declared interfaces using exact half-cells where the engine has them."""
    from nbt_collision import collision_cells

    result = {edge: 'no_half_cell_contact' for edge in declared}
    for pos, part in owners.items():
        for other in neighbors(pos):
            if other not in owners or part == owners[other]:
                continue
            edge = tuple(sorted((part, owners[other])))
            if edge not in result or result[edge] == 'exact_half_cell_contact':
                continue
            left, left_reason = collision_cells(values[pos])
            right, right_reason = collision_cells(values[other])
            if left_reason or right_reason:
                result[edge] = 'grid_face_only_unsupported_shape'
                continue
            delta = tuple(2 * (b - a) for a, b in zip(pos, other))
            shifted = {tuple(a + b for a, b in zip(cell, delta)) for cell in right}
            if any(touch in shifted for cell in left for touch in neighbors(cell)):
                result[edge] = 'exact_half_cell_contact'
    return [dict(parts=edge, contact=status) for edge, status in sorted(result.items())]


def compile_candidate(spec, name, data, size, parts, joins):
    from nbt_assets.components import validate
    from nbt_collision import state_support
    from nbt_model import AIR_NAMES, state

    fields(data, ('design', 'regions'))
    text(data['design'], 'design')
    require(isinstance(data['regions'], list) and data['regions'], f'{name}: missing regions')
    owners, values = {}, {}
    for row in data['regions']:
        fields(row, ('part', 'lo', 'hi', 'state'))
        part = row['part']
        require(part in parts, f'{name}: unknown part {part}')
        lo, hi = box({k: row[k] for k in ('lo', 'hi')}, size)
        text(row['state'], 'state')
        value = state(row['state'])
        require(value.startswith('minecraft:') and value not in AIR_NAMES,
                f'{name}: regions must place vanilla non-air blocks')
        for pos in points(lo, hi):
            require(pos not in owners, f'{name}: overlapping regions at {pos}')
            owners[pos], values[pos] = part, value
        require(len(owners) <= 65536, f'{name}: component block budget exceeded')
    require(set(owners.values()) == set(parts), f'{name}: every part needs geometry')
    require(any(y == 0 for _, y, _ in owners), f'{name}: no ground-plane cells')
    require(connected_cells(owners), f'{name}: disconnected occupied cells')
    actual = {tuple(sorted((a, owners[q]))) for p, a in owners.items()
              for q in neighbors(p) if q in owners and owners[q] != a}
    require(joins <= actual, f'{name}: missing grid-face joins {sorted(joins - actual)}')
    evidence = join_evidence(owners, values, joins)
    require(all(row['contact'] != 'no_half_cell_contact' for row in evidence),
            f'{name}: a declared join has no exact half-cell contact: {evidence}')
    palette = sorted(set(values.values()))
    indexes = {value: index for index, value in enumerate(palette)}
    component = validate(dict(schema_version=1, name=f"{spec['name']} · {name}",
                              size=list(size), anchor=[0, 0, 0], palette=palette,
                              blocks=[[*p, indexes[values[p]], False] for p in sorted(values)]))
    return component, dict(grid_face_joins=sorted(actual), declared_joins=evidence,
                           ground_plane_positions=[list(p) for p in sorted(values) if p[1] == 0],
                           collision_by_state={value: state_support(value) for value in palette})


def load_spec(path, photo):
    spec = read(path)
    size, parts, joins = intent(spec, photo)
    candidates = {identifier(name): compile_candidate(spec, name, data, size, parts, joins)
                  for name, data in spec['candidates'].items()}
    return spec, candidates


def reserve(output):
    output.mkdir(parents=True, exist_ok=False)


def build(args, engine):
    from nbt_assets.components import placement
    from nbt_composition.object_scene import engine_hash
    from nbt_composition.working_model import WorkingModel
    from nbt_paths import paths, python_versions
    from nbt_refine import read_master
    from nbt_snbt import save_snbt

    spec, candidates = load_spec(args.spec, args.photo)
    output = args.output.resolve()
    reserve(output)
    # Freeze the already parsed input and verify the reference before writing it.
    write(output / 'spec.json', spec)
    reference = None
    if args.photo:
        reference = output / ('reference' + args.photo.suffix.lower())
        data = args.photo.read_bytes()
        require(hashlib.sha256(data).hexdigest() == spec['source']['sha256'],
                'Reference photo changed while reading it')
        with reference.open('xb') as stream:
            stream.write(data)
    cameras = output / 'cameras.json'
    write(cameras, spec['cameras'])
    viewer_package = read(engine / 'assets/viewer/package.json')
    runtime = dict(engine_sha256=engine_hash(), workflow_sha256=sha(HERE), python=python_versions(),
                   runtime_bundle_sha256=paths()['runtime_bundle_sha256'],
                   playwright=viewer_package['dependencies']['playwright'],
                   renderer_sha256=sha(engine / 'assets/viewer/render-batch.mjs'))
    if args.render:
        from nbt_runtime.render import render_environment

        env = render_environment(engine)
        runtime['renderer_node'] = subprocess.check_output(
            [env.get('NBTCREATOR_NODE', 'node'), '--version'], env=env,
            encoding='utf-8', timeout=15).strip()
    frontend = engine / 'assets/viewer/web-dist/frontend-manifest.json'
    if frontend.is_file():
        runtime['frontend_manifest_sha256'] = sha(frontend)
    report = dict(schema_version=1, minecraft='Java 1.20.1', data_version=3465,
                  spec_sha256=sha(output / 'spec.json'), cameras_sha256=sha(cameras),
                  source=spec['source'], reference_file=reference.name if reference else None,
                  reference_verified=reference is not None, runtime=runtime, candidates={},
                  gameplay_intent=spec['gameplay'], in_game_verified=False)
    for name, (component, checks) in candidates.items():
        folder = output / name
        folder.mkdir()
        working = WorkingModel(output, component['size'], kind='component')
        plan = placement(component, component['anchor'], component['size'])
        working.apply_operations(plan['operations'])
        validation = working.validate()
        source = folder / 'model.snbt'
        saved = save_snbt(source, working.model, working.walls)
        disk, walls = read_master(source)
        require(disk.size == working.model.size and disk.blocks == working.model.blocks
                and walls == working.walls, 'Saved model differs from WorkingModel')
        ledger = dict(size=list(disk.size),
                      states=[[*p, value] for p, value in sorted(disk.blocks.items())],
                      wall_positions=sorted(walls), geometry_sha256=disk.fingerprint())
        write(folder / 'component.json', component)
        write(folder / 'ledger.json', ledger)
        result = dict(checks=checks, validation=validation, block_count=len(disk.blocks),
                      component_sha256=sha(folder / 'component.json'),
                      source_sha256=saved['source_sha256'], ledger_sha256=sha(folder / 'ledger.json'),
                      geometry_sha256=ledger['geometry_sha256'], render=None)
        if args.render:
            target = folder / 'render'
            command = [sys.executable, '-B', str(engine / 'scripts/nbt_task.py'), 'render',
                       '--source', str(source), '--cameras', str(cameras), '--output', str(target),
                       '--width', '720', '--height', '640']
            run = subprocess.run(command, capture_output=True, encoding='utf-8', errors='replace',
                                 cwd=output, timeout=300)
            (folder / 'render.log').write_text(run.stdout + run.stderr, encoding='utf-8')
            require(run.returncode == 0, f'Render failed: {folder / "render.log"}')
            manifest_path = target / 'render_manifest.json'
            manifest = read(manifest_path)
            require(manifest['status'] == 'complete' and manifest['source_sha256'] == saved['source_sha256']
                    and manifest['cameras_sha256'] == report['cameras_sha256']
                    and manifest['geometry_sha256'] == disk.fingerprint(), 'Render binding mismatch')
            images = {row['image']: row['sha256'] for row in manifest['images']}
            require(len(images) == len(spec['cameras']) and
                    all(sha(target / image) == digest for image, digest in images.items()),
                    'Rendered image set or hash mismatch')
            result['render'] = dict(browser=manifest['browser_version'], images=images,
                                    manifest_sha256=sha(manifest_path))
        report['candidates'][name] = result
    write(output / 'receipt.json', report)
    print(output / 'receipt.json')


def verify_run(folder, receipt):
    for filename, key in (('spec.json', 'spec_sha256'), ('cameras.json', 'cameras_sha256')):
        require(sha(folder / filename) == receipt[key], f'Run file differs from receipt: {filename}')
    if receipt['reference_file']:
        require(sha(folder / receipt['reference_file']) == receipt['source']['sha256'],
                'Run reference differs from receipt')
    for name, candidate in receipt['candidates'].items():
        target = folder / identifier(name)
        for filename, key in (('model.snbt', 'source_sha256'), ('component.json', 'component_sha256'),
                              ('ledger.json', 'ledger_sha256')):
            require(sha(target / filename) == candidate[key], f'Run file differs from receipt: {target / filename}')
        if render := candidate['render']:
            render_folder = target / 'render'
            require(sha(render_folder / 'render_manifest.json') == render['manifest_sha256'],
                    'Run render manifest differs from receipt')
            for image, digest in render['images'].items():
                require(sha(render_folder / image) == digest, f'Run image differs from receipt: {image}')


def pixel_difference(first, second):
    from PIL import Image, ImageChops

    with Image.open(first) as a, Image.open(second) as b:
        require(a.size == b.size, 'Render image dimensions differ')
        diff = ImageChops.difference(a.convert('RGB'), b.convert('RGB'))
        r, g, blue = diff.split()
        max_channel = ImageChops.lighter(ImageChops.lighter(r, g), blue)
        return dict(total_pixels=a.width * a.height,
                    changed_pixels=a.width * a.height - max_channel.histogram()[0])


def compare(args):
    first, second = args.first.resolve(), args.second.resolve()
    require(first != second, 'Compare two separate runs')
    a, b = (read(folder / 'receipt.json') for folder in (first, second))
    verify_run(first, a)
    verify_run(second, b)
    require(all(a[key] == b[key] for key in ('spec_sha256', 'cameras_sha256', 'runtime', 'minecraft'))
            and a['candidates'].keys() == b['candidates'].keys(), 'Run inputs or runtime differ')
    results = {}
    for name, left in a['candidates'].items():
        right = b['candidates'][name]
        require(all(left[key] == right[key] for key in ('source_sha256', 'component_sha256',
                                                        'ledger_sha256', 'geometry_sha256')),
                f'{name}: saved geometry, state or wall layer changed')
        ra, rb = left['render'], right['render']
        require(bool(ra) == bool(rb), f'{name}: missing render in one run')
        views = {}
        if ra:
            require(ra['browser'] == rb['browser'] and ra['images'].keys() == rb['images'].keys(),
                    f'{name}: renderer browser or image set changed')
            for image, digest in ra['images'].items():
                views[image] = dict(sha256_equal=digest == rb['images'][image],
                                    **pixel_difference(first / name / 'render' / image,
                                                       second / name / 'render' / image))
        results[name] = dict(coordinates_states_wall_layer_equal=True, snbt_sha256_equal=True,
                             geometry_sha256=left['geometry_sha256'], rendered_views=views)
    candidate_views = {}
    if len(results) == 2 and all(c['render'] for c in a['candidates'].values()):
        name_a, name_b = a['candidates']
        for image in a['candidates'][name_a]['render']['images']:
            candidate_views[image] = pixel_difference(first / name_a / 'render' / image,
                                                       first / name_b / 'render' / image)
    write(args.output, dict(spec_sha256=a['spec_sha256'], candidates=results,
                            between_candidates=candidate_views))


def host_check(args):
    from nbt_assets.components import placement
    from nbt_collision import check_routes, collision_cells
    from nbt_composition.working_model import WorkingModel
    from nbt_model import AIR_NAMES

    _, candidates = load_spec(args.spec, None)
    component, _ = candidates[args.candidate]
    request = read(args.host)
    fields(request, ('source', 'source_sha256', 'position', 'writable_box',
                     'route_start', 'route_targets'), ('quarter_turns',))
    source = (args.workspace / request['source']).resolve()
    require(re.fullmatch('[a-f0-9]{64}', request['source_sha256']), 'Host requires an expected source SHA256')
    require(isinstance(request['route_targets'], dict) and request['route_targets'],
            'Declare named passage and required standing poses')
    working = WorkingModel.open(args.workspace, source, source_sha256=request['source_sha256'])
    lo, hi = box(request['writable_box'], working.model.size)
    plan = placement(component, request['position'], working.model.size, request.get('quarter_turns', 0))
    require(all(a <= b <= c <= d for a, b, c, d in zip(lo, plan['lo'], plan['hi'], hi)),
            'Furniture envelope is outside the host writable box')
    before = check_routes(working.model, request['route_start'], request['route_targets'])
    require(before['passed'], 'Declared host route or standing pose failed before placement')
    supports = []
    for op in plan['operations']:
        for x, y, z, index in op['voxels']:
            pos = tuple(a + b for a, b in zip(op['lo'], (x, y, z)))
            require(working.model.get(pos) in AIR_NAMES, f'Host coordinate already occupied: {pos}')
            if y != 0:
                continue
            below = (pos[0], pos[1] - 1, pos[2])
            require(working.model.in_bounds(below), f'Missing host floor under {pos}')
            upper, upper_reason = collision_cells(op['palette'][index])
            lower_state = working.model.get(below)
            lower, lower_reason = collision_cells(lower_state)
            require(not upper_reason and not lower_reason and
                    any((cx, 1, cz) in lower for cx, cy, cz in upper if cy == 0),
                    f'Exact floor contact unavailable under {pos}')
            supports.append(dict(furniture=list(pos), host=list(below), state=lower_state))
    working.apply_operations(plan['operations'])
    after = check_routes(working.model, request['route_start'], request['route_targets'])
    validation = working.validate()
    require(after['passed'], 'Declared host route or standing pose failed after placement')
    write(args.output, dict(status='host_preflight', source=str(source), source_sha256=working.source_sha256,
                            proposal=request, placement=plan, exact_floor_supports=supports,
                            before=before, after=after, validation=validation, source_modified=False,
                            in_game_verified=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine', type=Path, default=DEFAULT_ENGINE, help='Active or frozen minecraft-nbt-modeler directory')
    sub = parser.add_subparsers(dest='command', required=True)
    build_cmd = sub.add_parser('build', help='Compile, save, read back and optionally render a new run')
    build_cmd.add_argument('--spec', type=Path, required=True)
    build_cmd.add_argument('--photo', type=Path)
    build_cmd.add_argument('--output', type=Path, required=True)
    build_cmd.add_argument('--render', action='store_true')
    compare_cmd = sub.add_parser('compare', help='Verify receipt files and compare two runs')
    compare_cmd.add_argument('first', type=Path)
    compare_cmd.add_argument('second', type=Path)
    compare_cmd.add_argument('--output', type=Path, required=True)
    host_cmd = sub.add_parser('host-check', help='Simulate non-overwriting placement and verify floor and routes')
    host_cmd.add_argument('--spec', type=Path, required=True)
    host_cmd.add_argument('--candidate', required=True)
    host_cmd.add_argument('--workspace', type=Path, required=True)
    host_cmd.add_argument('--host', type=Path, required=True)
    host_cmd.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == 'compare':
            compare(args)
        else:
            engine = args.engine.resolve()
            require((engine / 'scripts/nbt_task.py').is_file(), 'Select the active NBTCreator skill with --engine')
            sys.path.insert(0, str(engine / 'scripts'))
            if args.command == 'build':
                build(args, engine)
            else:
                host_check(args)
        return 0
    except (ValueError, OSError, KeyError, TypeError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(f'furniture: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
