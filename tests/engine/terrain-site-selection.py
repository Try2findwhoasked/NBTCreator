"""Compare joint siting with fixed placement on the same bound terrain."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from time import perf_counter

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.agents/skills/minecraft-nbt-modeler/scripts'))

from nbt_assembly import Volume
from nbt_collision import check_routes
from nbt_composition.working_model import WorkingModel, file_hash, model_hash, write_json
from nbt_extensions import compile_recipe
from nbt_refine import read_master, save_master


def pavilion(workspace):
    def box(lo, hi, material, layer='body'):
        return dict(kind='box', label=material, lo=lo, hi=hi, state=material, classification=layer)

    def roof(y, inset, block):
        return box([inset, y, inset], [6-inset, y, 6-inset], block)

    recipe = dict(tool='structure', arguments=dict(
        name='入口亭', size=[7, 7, 7], anchor=[0, 0, 0], operations=[
            box([0, 0, 0], [6, 0, 6], 'polished_andesite'),
            box([6, 1, 0], [6, 3, 6], 'spruce_planks', 'wall'),
            box([0, 1, 0], [5, 3, 0], 'stripped_spruce_log[axis=x]', 'wall'),
            box([0, 1, 6], [5, 3, 6], 'stripped_spruce_log[axis=x]', 'wall'),
            box([0, 1, 1], [0, 3, 2], 'spruce_planks', 'wall'),
            box([0, 1, 4], [0, 3, 5], 'spruce_planks', 'wall'),
            box([0, 3, 3], [0, 3, 3], 'stripped_spruce_log[axis=z]'),
            box([5, 1, 2], [5, 1, 4], 'dark_oak_planks'),
            roof(4, 0, 'waxed_cut_copper'), roof(5, 1, 'waxed_cut_copper'),
            roof(6, 2, 'waxed_cut_copper_slab[type=bottom]'),
        ],
    ))
    component, _ = compile_recipe(workspace, recipe)
    model, walls = Volume(component['size']), set()
    for x, y, z, index, wall in component['blocks']:
        p = x, y, z
        model.put(p, component['palette'][index])
        if wall:
            walls.add(p)
    source = workspace / 'building/pavilion.snbt'
    source.parent.mkdir()
    save_master(source, model, walls)
    return dict(recipe=recipe, content_sha256=component['content_sha256']), {
        'source': str(source), 'source_sha256': file_hash(source),
    }


def terrain(workspace, kind):
    model = Volume((34, 16, 27))
    for x in range(model.size[0]):
        for z in range(model.size[2]):
            if kind in ('river', 'water') and 8 <= x <= 10:
                model.put((x, 0, z), 'stone')
                model.put((x, 1, z), 'water[level=0]')
                continue
            height = (2 if x <= 8 else 3 if x <= 10 else 4) if kind == 'slope' else 2
            model.box((x, 0, z), (x, height-1, z), 'dirt')
            model.put((x, height, z), 'grass_block')
    model.put((2, 2, 12), 'cobblestone')
    source = workspace / kind / 'terrain.snbt'
    source.parent.mkdir()
    save_master(source, model, set())
    if kind == 'protected':
        write_json(source.parent / 'coordinates.json', dict(
            mode='standalone', openings=[], protected_boxes=[dict(lo=[18, 2, 9], hi=[24, 8, 15])],
        ))
    return {'source': str(source), 'source_sha256': file_hash(source)}


def goal(building, kind):
    return dict(
        building=building, region=dict(lo=[0, 0, 0], hi=[33, 15, 26]), junction=[2, 2, 12],
        entrance=dict(floor=[0, 0, 3], facing='west'), targets=[dict(id='workbench', feet=[4.5, 1, 3.5])],
        anchor_xz=[[18, 9], [13, 9], [16, 11]], floor_ys=[2, 3, 4] if kind == 'slope' else [2, 3],
        quarter_turns=[0, 1], roads=[{}, dict(max_bridge_span=3, bridge_water=True)] if kind == 'river' else [{}],
        max_candidates=36, max_pad_cut=2, max_pad_fill=1,
    )


def cli(workspace, path, data, expected=0):
    write_json(path, data)
    started = perf_counter()
    proc = subprocess.run(
        ['node', str(ROOT / 'scripts/cli.mjs'), '--workspace', str(workspace), 'model', '--request', str(path)],
        cwd=ROOT, capture_output=True, encoding='utf8',
    )
    assert proc.returncode == expected, (proc.stdout, proc.stderr)
    output = json.loads(proc.stdout)
    write_json(path.with_suffix('.response.json'), dict(output, cli_ms=round((perf_counter() - started)*1000, 3)))
    return output.get('result', output)


def search(workspace, name, host, target, preview=None):
    action = dict(method='site_selection', goal=target)
    if preview:
        action['preview'] = preview
    result = cli(workspace, workspace / name / 'search.json', dict(host, actions=[action]))
    report = result['actions'][0]
    assert result['model']['model_sha256'] == report['binding']['host']['model_sha256']
    assert not report['model_modified'] and not report['approval_created']
    return report


def compact(report):
    row = report['best'] or report['candidates'][0]
    earthwork = row.get('earthwork', row.get('pad_earthwork', {}))
    return dict(status=report['status'], evaluated=report['evaluated'], eligible=report['eligible'],
                anchor=row['transform']['position'], turn=row['transform']['quarter_turns'], floor_y=row['floor_y'],
                cut_cells=earthwork.get('cut_cells'), fill_cells=earthwork.get('fill_cells'),
                earthwork_scope='complete_candidate' if row.get('earthwork') else 'pad_only' if earthwork else None,
                road_length_blocks=row.get('road_length_blocks'), check_ms=report['check_ms'], candidate_check_ms=row['check_ms'],
                route_passed=row.get('route', {}).get('passed', False), water_cells=len(row.get('road', {}).get('water_cells', [])),
                problem=row.get('problem'))


def verify_preview(workspace, report, original, target):
    preview, best = report['preview'], report['best']
    receipt = json.loads(Path(preview['receipt']).read_text(encoding='utf8'))
    model, walls = read_master(Path(preview['source']))
    assert receipt['preview_source_sha256'] == file_hash(preview['source'])
    assert receipt['snapshot_sha256'] == file_hash(preview['snapshot'])
    assert model_hash(model, walls) == best['model_sha256']
    assert walls and len(walls) == len(read_master(Path(target['building']['source']))[1])
    assert model.get((2, 2, 12)) == 'minecraft:cobblestone'
    ground, _ = read_master(Path(original['source']))
    cut, fill = (best['earthwork'][f'{key}_positions'] for key in ('cut', 'fill'))
    assert all(ground.get(tuple(p)) != model.get(tuple(p)) for p in cut)
    assert all(ground.get(tuple(p)) == 'minecraft:air' and model.get(tuple(p)) != 'minecraft:air' for p in fill)
    for p in best['road']['water_cells']:
        assert model.get(tuple(p)) == ground.get(tuple(p)) == 'minecraft:water[level=0]'
    route = best['route']
    replay = check_routes(model, route['junction_feet'], {'workbench': route['paths']['workbench'][-1]})
    assert replay['passed'], replay
    write_json(workspace / 'river/preview-route-replay.json', replay)


def verify_adoption(workspace, host, target, best):
    adoption = dict(method='adopt_site_selection', goal=target, candidate_id=best['id'],
                    candidate_sha256=best['candidate_sha256'])
    stale_goal = dict(target, max_candidates=target['max_candidates']-1)
    stale = cli(workspace, workspace / 'river/stale-adoption.json',
                dict(host, actions=[dict(adoption, goal=stale_goal)]), expected=1)
    assert stale['code'] == 'STALE_SITE_CANDIDATE'
    stale_building = dict(target, building=dict(target['building'], source_sha256='0'*64))
    stale = cli(workspace, workspace / 'river/stale-building.json',
                dict(host, actions=[dict(adoption, goal=stale_building)]), expected=1)
    assert stale['code'] == 'STALE_SOURCE'
    result = cli(workspace, workspace / 'river/adopt.json',
                 dict(host, actions=[adoption], save_draft=dict(name_zh='河岸入口亭')))
    saved = result['saved']
    model = WorkingModel.open(workspace, saved['source'], source_sha256=saved['source_sha256'])
    assert model_hash(model.model, model.walls) == best['model_sha256']
    assert model.walls and model.validate()['approval_created'] is False
    edited = cli(workspace, workspace / 'river/continue.json', dict(
        source=saved['source'], source_sha256=saved['source_sha256'], actions=[dict(
            method='patch', changes=[dict(pos=[0, 3, 0], before=['minecraft:air', False],
                                        after=['minecraft:stone_bricks', False])],
        )], save_draft={},
    ))
    assert edited['saved']['revision'] != saved['revision']


def run(workspace):
    recipe, draft = pavilion(workspace)
    comparisons = {}
    for kind in ('flat', 'slope', 'river'):
        original = terrain(workspace, kind)
        target = goal(draft, kind)
        preview = (dict(output='river/preview', cameras=[
            dict(id='overview', eye=[-7, 24, 38], target=[14, 3, 12], fov=49),
            dict(id='entry', eye=[10.5, 4.62, 12.5], target=[17, 4, 12.5], fov=62),
        ]) if kind == 'river' else None)
        joint = search(workspace, kind, original, target, preview)
        assert joint['status'] == 'ranked', compact(joint)
        fixed_target = dict(target, anchor_xz=[[18, 9]], quarter_turns=[0], floor_ys=[2])
        fixed = cli(workspace, workspace / kind / 'fixed.json', dict(original, actions=[
            dict(method='site_selection', goal=fixed_target),
        ]))['actions'][0]
        comparisons[kind] = dict(joint=compact(joint), fixed=compact(fixed))
        assert joint['best']['route']['passed']
        if fixed['best']:
            assert joint['best']['score'] <= fixed['best']['score']
        if kind == 'slope':
            assert joint['best']['floor_y'] != comparisons['flat']['joint']['floor_y'], comparisons
        if kind == 'river':
            assert len(joint['best']['road']['water_cells']) == 3, compact(joint)
            dry_only = [row for row in joint['candidates'] if row['road_option'] == 0]
            assert dry_only and all('problem' in row for row in dry_only)
            assert any('water_requires_dry_bridge_deck' in row['problem'].get('rejections', {}) for row in dry_only)
            verify_preview(workspace, joint, original, target)
            verify_adoption(workspace, original, target, joint['best'])

    original = terrain(workspace, 'protected')
    target = dict(goal(draft, 'protected'), anchor_xz=[[18, 9]], floor_ys=[2], quarter_turns=[0])
    rejected = search(workspace, 'protected', original, target, preview=dict(output='protected/preview'))
    assert rejected['status'] == 'no_legal_candidates' and 'preview' not in rejected
    assert rejected['candidates'][0]['problem']['code'] == 'PROTECTED_SPACE'
    comparisons['protected'] = compact(rejected)

    original = terrain(workspace, 'water')
    target = dict(goal(draft, 'water'), anchor_xz=[[8, 9]], floor_ys=[2], quarter_turns=[0])
    rejected = search(workspace, 'water', original, target)
    assert rejected['candidates'][0]['problem']['code'] == 'BUILDING_WATER_OR_FLUID'
    comparisons['water_foundation'] = compact(rejected)

    host = WorkingModel.open(workspace, workspace / 'flat/terrain.snbt')
    blocked, walls = read_master(Path(draft['source']))
    blocked.put((0, 1, 3), 'spruce_planks')
    blocked_file = workspace / 'building/closed-pavilion.snbt'
    save_master(blocked_file, blocked, walls)
    blocked_draft = dict(source=str(blocked_file), source_sha256=file_hash(blocked_file))
    blocked_target = dict(goal(blocked_draft, 'flat'), anchor_xz=[[18, 9]], floor_ys=[2], quarter_turns=[0])
    rejected = search(workspace, 'clearance', dict(source=str(host.source), source_sha256=host.source_sha256), blocked_target)
    assert rejected['candidates'][0]['problem']['code'] == 'ENTRY_CLEARANCE_OR_SUPPORT'
    comparisons['clearance'] = compact(rejected)

    invalid_corridor = dict(lo=[0, 0, 0], hi=[12, 15, 26])
    corridor_target = dict(blocked_target, building=draft, roads=[dict(corridor=invalid_corridor)])
    rejected = host.site_selection(corridor_target)
    assert rejected['candidates'][0]['problem']['code'] == 'ROAD_ENDPOINT_OUTSIDE_RANGE'
    comparisons['corridor'] = compact(rejected)

    original, walls = read_master(Path(draft['source']))
    padded = Volume((original.size[0], original.size[1] + 1, original.size[2]))
    padded.blocks = {(x, y+1, z): value for (x, y, z), value in original.blocks.items()}
    padded_file = workspace / 'building/padded-pavilion.snbt'
    save_master(padded_file, padded, {(x, y+1, z) for x, y, z in walls})
    padded_target = dict(blocked_target, building=dict(source=str(padded_file), source_sha256=file_hash(padded_file)),
                         entrance=dict(floor=[0, 1, 3], facing='west'),
                         targets=[dict(id='workbench', feet=[4.5, 2, 3.5])])
    report = host.site_selection(padded_target)
    best = report['best']
    assert best['local_foundation_y'] == 1 and best['transform']['position'][1] == 1
    assert best['entrance_floor'] == (18, 2, 12) and best['route']['passed']
    comparisons['padded_building'] = compact(report)

    recipe_target = dict(goal(recipe, 'flat'), anchor_xz=[[18, 9]], floor_ys=[2], quarter_turns=[0])
    candidate = host.site_selection(recipe_target)['best']
    adopted = host.adopt_site_selection(recipe_target, candidate['id'], candidate['candidate_sha256'])
    assert adopted['candidate']['route']['passed'] and 'site-building' in host.instances
    stale_recipe = deepcopy(recipe_target)
    stale_recipe['building']['content_sha256'] = '0'*64
    try:
        host.site_selection(stale_recipe)
    except ValueError as error:
        assert error.code == 'STALE_SITE_BUILDING'
    else:
        raise AssertionError('changed building accepted')
    assert not list(workspace.rglob('*.nbt'))
    write_json(workspace / 'comparison.json', comparisons)
    print(json.dumps(dict(workspace=str(workspace), results=comparisons), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, help='New isolated directory for complete comparison evidence')
    args = parser.parse_args()
    if args.workspace:
        workspace = args.workspace.resolve()
        workspace.mkdir(parents=True, exist_ok=False)
        run(workspace)
    else:
        with TemporaryDirectory(prefix='nbt-site-selection-') as path:
            run(Path(path))
