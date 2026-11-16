"""Write reproducible design inputs into a dedicated creative test project."""
from copy import deepcopy
import json
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_exposure import apply

workspace = Path(sys.argv[1]).resolve()
workspace.mkdir(parents=True, exist_ok=True)
factory = runpy.run_path(str(ROOT / 'tests/architecture-workflow.py'))['plan']
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
apply(workspace, dict(schema_version=1, enabled_groups=['core', 'architecture', 'modelling', 'rendering']))
print(json.dumps(dict(cases=cases), ensure_ascii=False))
