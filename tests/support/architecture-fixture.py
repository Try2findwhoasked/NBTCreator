"""Write reproducible design inputs into a dedicated creative test project."""
from copy import deepcopy
import json
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_exposure import apply

workspace = Path(sys.argv[1]).resolve()
workspace.mkdir(parents=True, exist_ok=True)
factory = runpy.run_path(str(ROOT / 'tests/engine/architecture-workflow.py'))['plan']
stone, wood = factory(), factory(True)
stone['stairs'][0]['railing'] = dict(state='stone_brick_wall', kerb_material='stone_bricks')
wood['stairs'][0]['railing'] = dict(state='spruce_fence', kerb_material='spruce_planks')
wood['stairs'][0]['operation'].update(state='spruce_planks', slab_state='spruce_slab[type=bottom]')
polygon = deepcopy(stone)
polygon['name'] = '折角铜顶展馆'
polygon['envelope']['volumes'][0]['polygon'] = [[2, 2], [26, 2], [26, 25], [20, 25], [20, 28], [2, 28]]
polygon['envelope']['volumes'][0]['roof'].update(kind='hip', rise=4)
polygon['envelope']['interfaces'][0].update(lo=[21, 11, 21], hi=[23, 16, 23])
polygon['style']['materials']['roof'] = 'oxidized_cut_copper'
polygon['style']['name'] = '折角平面与铜顶石构'
cases = []
for identifier, plan in [('stone', stone), ('wood', wood), ('polygon', polygon)]:
    # A player on the gallery looks through the new railing. Review the bearing
    # from an unobstructed standing pose instead of treating uncertain rays as a pass.
    plan['views'][2].update(id='bearing', feet=[18.5, 2, 13.5], target_part='right')
    folder = workspace / 'nbt_models/_workspaces/inputs' / identifier
    folder.mkdir(parents=True)
    for name, value in [('save', dict(plan=plan, revision=0)), ('build', dict(plan=plan, save_draft={}))]:
        (folder / (name + '.json')).write_text(json.dumps(value, ensure_ascii=False), encoding='utf8')
    cases.append(dict(id=identifier, plan=plan, input=str(folder)))

loft_path = ROOT / '.agents/skills/minecraft-nbt-modeler/assets/examples/reading-loft/plan.py'
loft = runpy.run_path(str(loft_path))['reading_loft'](blocked=True, wrong_side=True)
coarse = deepcopy(loft)
coarse['envelope']['glazing'] = []
coarse['parts'] = [part for part in coarse['parts']
                   if part['id'] in ('threshold', 'loft', 'return_desk', 'archive_cabinet')]
coarse['views'] = [view for view in coarse['views']
                   if view['id'] in ('outside', 'entry_player', 'counter')]
coarse['review_locations'] = []
coarse['requirements'][0].pop('review_locations')
coarse.pop('quality')
folder = workspace / 'nbt_models/_workspaces/inputs/loft'
folder.mkdir()
layout = dict(plan=coarse, variables=[
    dict(id='cabinet', targets=[dict(kind='part', id='archive_cabinet')], offsets=[[0, 0], [0, 5], [1, 5]]),
    dict(id='operator', targets=[dict(kind='stop', id='file_books', index=0)], offsets=[[0, 0], [0, -3]]),
    dict(id='stair', targets=[
        dict(kind='stair', id='archive_stair'),
        dict(kind='stop', id='file_books', index=1),
        dict(kind='stop', id='file_books', index=2),
        dict(kind='route-target', id='stair_landing'),
    ], offsets=[[0, 0], [-1, 0]]),
], areas=[dict(space='hall', minimum=250, maximum=280), dict(space='loft', minimum=70, maximum=70)],
    adjacency=[dict(spaces=['hall', 'loft'], max_gap=0)])
cases.append(dict(id='loft', plan=loft, layout=layout, input=str(folder)))
apply(workspace, dict(schema_version=1, enabled_groups=['core', 'architecture', 'modelling', 'rendering']))
print(json.dumps(dict(cases=cases), ensure_ascii=False))
