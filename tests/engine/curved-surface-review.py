"""Build and render the opt-in acceptance sample for curved relief."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.agents/skills/minecraft-nbt-modeler/scripts'))

import nbt_assets.libraries as libraries
from nbt_assembly import Volume
from nbt_review.blind_review import prepare_review
from nbt_assets.components import store
from nbt_mounting.curve_components import compose_curve_mask
from nbt_mounting.curved_surface import plan_curve, verify_curve
from nbt_review.reference_views import register_reference, save_fit
from nbt_snbt import save_snbt
from nbt_agent.structure import build
from nbt_composition.working_model import ModelConflict


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf8')


def build_host(workspace):
    inputs = workspace / 'inputs'
    inputs.mkdir(parents=True)
    stations = [
        (0, 32, 126, 17, 147), (12, 25, 136, 13, 153), (44, 25, 136, 13, 153),
        (45, 28, 133, 16, 150), (49, 34, 125, 20, 143), (56, 39, 117, 25, 136),
    ]
    views = {}
    for name, u, v in [('front', 'x', '-y'), ('side', 'z', '-y'), ('top', 'x', 'z')]:
        file = inputs / f'{name}.png'
        picture = Image.new('RGB', (352, 352), 'white')
        draw = ImageDraw.Draw(picture)
        if name == 'top':
            draw.ellipse((54, 30, 276, 310), outline='black', width=2)
        else:
            low, high = (1, 2) if name == 'front' else (3, 4)
            left = [(4 + 2 * row[low], 336 - 2 * row[0]) for row in stations]
            right = [(4 + 2 * row[high], 336 - 2 * row[0]) for row in reversed(stations)]
            draw.polygon(left + right, outline='black', width=2)
        picture.save(file)
        views[name] = dict(image=str(file), sha256=digest(file), origin=[4, 4 if name == 'top' else 336],
                           pixels_per_block=2, u_axis=u, v_axis=v, origin_type='original',
                           basis='合成轮廓和已知坐标')

    anchors, rows = [], []
    for y, x0, x1, z0, z1 in stations:
        row = {}
        for edge, (x, z) in [('x_min', (x0, 84)), ('x_max', (x1, 84)), ('z_min', (80, z0)), ('z_max', (80, z1))]:
            name = f'{edge}_{y}'
            row[edge] = name
            anchors.append(dict(id=name, part='shell', world=[x, y, z], basis='合成截面坐标',
                                confidence='measured', uncertainty=0,
                                views=dict(front=[4 + 2 * x, 336 - 2 * y], side=[4 + 2 * z, 336 - 2 * y],
                                           top=[4 + 2 * x, 4 + 2 * z])))
        if y in (12, 44, 45):
            row['corner'] = True
        rows.append(row)
    reference = register_reference(workspace, dict(output='nbt_models/_workspaces/reference-views/shell',
                                                   views=views, anchors=anchors, assumptions=[]))
    fitted = save_fit(
        workspace, dict(reference=reference['manifest'], reference_sha256=reference['manifest_sha256'],
                        part='shell', rows=rows, sample_step=1, vertices=128),
        'nbt_models/_workspaces/reference-fits/shell.json',
    )
    sections = json.loads(Path(fitted['output']).read_text(encoding='utf8'))['geometry']['sections']
    model = Volume((165, 59, 165))
    for y, (lower, upper) in enumerate(zip(sections, sections[1:])):
        points = [(round((p[0] + q[0]) / 2 - .5), round((p[1] + q[1]) / 2 - .5))
                  for p, q in zip(lower['vertices'], upper['vertices'])]
        outside = Image.new('L', (165, 165))
        ImageDraw.Draw(outside).polygon(points, fill=255)
        shell = ImageChops.subtract(outside, outside.filter(ImageFilter.MinFilter(21)))
        zz, xx = np.nonzero(np.asarray(shell))
        material = 'deepslate_bricks' if y in (11, 12, 43, 44, 45, 54, 55) else 'stone_bricks'
        for x, z in zip(xx, zz):
            model.put((int(x), y, int(z)), material)
    source = workspace / 'nbt_models/standalone/synthetic-shell/v01/master/model.snbt'
    saved = save_snbt(source, model, set(model.blocks))
    return dict(source=str(source), source_sha256=saved['source_sha256'],
                profile=fitted['output'], profile_sha256=fitted['sha256']), len(model.blocks)


def build_mask(workspace):
    available = {item['id'].split('/')[-1]: item for item in libraries.browse(workspace)['items']
                 if item['source_id'] == 'bundled'}

    def recipe(asset_id, **arguments):
        item = available[asset_id]
        ref = {key: item[key] for key in ('id', 'sha256', 'source_id', 'version', 'manifest_sha256')}
        component, _, _ = libraries.materialize(workspace, libraries.read_asset(workspace, ref), arguments)
        ref.update(arguments=arguments, content_sha256=component['content_sha256'])
        return dict(kind='library', ref=ref), component

    def layer(identifier, template, origin, symbol, action, counts=(1, 1), spacing=(1, 1)):
        source, component = template
        materials = sorted({(block[3], block[4]) for block in component['blocks'] if block[2] == 0})
        return dict(id=identifier, source=source, slice_z=0, origin=origin, counts=list(counts),
                    spacing=list(spacing), palette={symbol: action},
                    mapping=[dict(index=index, wall=wall, symbol=symbol) for index, wall in materials])

    # An open S stroke with space between turns lets the section show all three depths.
    scroll_segments = [(3, 11, 12, 2), (1, 9, 4, 3), (1, 6, 2, 4), (2, 5, 11, 2),
                       (12, 2, 3, 4), (5, 0, 9, 2), (3, 1, 3, 2), (2, 1, 2, 3)]
    points = {(x, y) for u, v, w, h in scroll_segments for x in range(u, u + w) for y in range(v, v + h)}
    scroll = build(workspace, dict(
        name='合成开口卷纹', size=[15, 13, 1], anchor=[0, 0, 0], tags=['curve-sample'],
        operations=[dict(kind='paste_component', label='卷纹轮廓', classification='body', lo=[0, 0, 0],
                         hi=[14, 12, 0], palette=['cut_sandstone'],
                         voxels=[[x, y, 0, 0] for x, y in sorted(points)])],
    ))
    local = store(workspace, scroll)
    scroll_source = dict(kind='local', id=local['id'], content_sha256=scroll['content_sha256'])
    window = recipe('curve-window-column', size=[5, 12, 1], form=dict(
        profile='curve_window_column', curve_width=5, curve_offset=0, curve_start=0,
        curve_window_height=12, curve_count=1, curve_gap=0,
    ))
    band = recipe('curve-diagonal-band', size=[39, 11, 1], form=dict(
        profile='curve_diagonal_band', curve_width=3, curve_start=0, curve_rise=8,
    ))
    groove = recipe('curve-dark-seam', size=[12, 2, 1], form=dict(
        profile='curve_dark_seam', curve_width=2, curve_offset=0,
    ))
    layers = [
        layer('band', band, [4, 20], 'R', dict(kind='raise', state='weathered_cut_copper',
                                             height=1, wall=False, role='band')),
        layer('windows', window, [6, 5], 'W', dict(kind='inlay', state='blackstone', wall=True,
              depth=3, backing=2, max_effective_depth=3, role='window'), (2, 1), (8, 1)),
        layer('groove', groove, [8, 2], 'C', dict(kind='cut', depth=2, backing=2,
              max_effective_depth=3, role='groove')),
        layer('scroll', (scroll_source, scroll), [25, 5], 'S', dict(kind='raise', state='cut_sandstone',
              height=1, wall=False, role='scroll')),
    ]
    return compose_curve_mask(workspace, dict(name='偏心退台外壳样段', size=[48, 31], layers=layers,
        overlaps=[], output='nbt_models/_workspaces/curve-masks/sample'))


def main():
    output_root = ROOT / 'build'
    output_root.mkdir(exist_ok=True)
    output = Path(tempfile.mkdtemp(prefix='curve-review-', dir=output_root))
    workspace = output / 'workspace'
    print(f'Acceptance output: {output}', flush=True)
    source, blocks = build_host(workspace)
    mask = build_mask(workspace)
    cameras = [
        dict(id='front', eye=[260, 28, 84], target=[135, 28, 84], projection='orthographic', ortho_height=42),
        dict(id='oblique', eye=[226, 65, 141], target=[133, 26, 84], projection='orthographic', ortho_height=49),
        dict(id='section', eye=[220, 80, 130], target=[133, 21, 80], projection='orthographic', ortho_height=40,
             cuts=[dict(axis='y', position=23, removed_side='above')]),
        dict(id='far', eye=[285, 150, 212], target=[81, 28, 83], projection='orthographic', ortho_height=155),
    ]
    request = dict(source, mask=mask['mask'], mask_sha256=mask['mask_sha256'], cameras=cameras,
                   mapping=dict(u_start=.944, u_span=.112, y_start=13, max_distance=2, u_subsamples=2,
                                connect_raised=dict(max_new_blocks=32), connect_recess=dict(max_new_blocks=32)),
                   context=dict(mode='standalone', openings=[], protected_boxes=[dict(lo=[132, 10, 75], hi=[137, 12, 95])]),
                   output='nbt_models/_workspaces/curve-samples/sample')
    write_json(output / 'request.json', request)
    result = plan_curve(workspace, request)
    assert verify_curve(workspace, result['plan'], result['plan_sha256'])['valid']
    layers = result['continuity']['layers']
    assert result['continuity']['passed'] and {row['id'] for row in layers} == {'band', 'windows', 'groove', 'scroll'}
    depth = result['summary']['effective_depth']
    assert depth['maximum'] == 3 and depth['max_air_full_voxels'] == 2 and depth['checked_faces'] > 0
    assert result['summary']['connectors_added'] > 0
    assert not result['approval_created'] and not result['nbt_exported']
    write_json(output / 'sample.json', result)

    protected = deepcopy(request)
    coordinate = next(row['host'] for row in result['samples'] if row['layer'] == 'groove')
    protected['context']['protected_boxes'].append(dict(lo=coordinate, hi=coordinate))
    protected['output'] += '-protected'
    try:
        plan_curve(workspace, protected)
    except ModelConflict as error:
        assert error.code == 'CURVE_PROTECTED' and error.conflicts[0]['pos'] == coordinate, error
    else:
        raise AssertionError('The protected groove was changed')
    assert not (workspace / protected['output']).exists()
    assert digest(source['source']) == source['source_sha256']
    print(f'Verified {blocks:,} host blocks and {result["summary"]["changed_positions"]} changes', flush=True)

    renders = []
    for stage, model in [('before', source['source']), ('after', result['candidate'])]:
        folder = workspace / 'render' / stage
        subprocess.run(
            ['node', str(ROOT / 'scripts/cli.mjs'), '--workspace', str(workspace), 'render',
             '--source', model, '--cameras', result['cameras'], '--output', str(folder),
             '--width', '960', '--height', '640'],
            cwd=ROOT, check=True, timeout=180, stdout=subprocess.DEVNULL,
        )
        manifest = folder / 'render_manifest.json'
        renders.append(dict(manifest=str(manifest), sha256=digest(manifest)))
    review = prepare_review(workspace, dict(renders=renders, scope='斜搭板、暗窗、切槽和卷纹的连续性与进深',
                          crop=None, output='nbt_models/_workspaces/reference-reviews/sample'))
    assert review['views'] == 4 and not review['approval_created']
    write_json(output / 'acceptance.json', dict(blocks=blocks, protected_rejection=coordinate,
               summary=result['summary'], renders=renders, review=review, visual_review='pending'))
    print(f'Four matched views and review binding: {output / "acceptance.json"}', flush=True)


if __name__ == '__main__':
    main()
