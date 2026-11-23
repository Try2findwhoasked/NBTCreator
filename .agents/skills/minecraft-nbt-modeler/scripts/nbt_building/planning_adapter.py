"""Carry one reviewed layout into the existing building-plan compiler."""
from copy import deepcopy
from math import ceil, floor

from nbt_building.planning import PlanningLayout
from nbt_building.plan import normalize
from nbt_composition.working_model import ModelConflict


def prepare(workspace, request):
    planning = dict(program=request['program'], layout=request['layout'])
    layout = PlanningLayout(planning['program'], planning['layout'])
    report = layout.assess()
    if not report['passed']:
        raise ModelConflict('LAYOUT_INVALID', [row for row in report['checks'] if not row['passed']])
    plan = deepcopy(request['plan'])
    if plan.get('size') != layout.size:
        raise ValueError('候选布局与建筑方案的画布不一致')
    prior_spaces = {slot['id']: slot for slot in plan.get('spaces', ())}
    planned_spaces = []
    for key, room in layout.spaces.items():
        region = layout.regions[key]
        level = layout.levels[room['level']]
        elevation = level['feet_y']
        x, z = zip(*region)
        prior = prior_spaces.get(key, {})
        samples = [sample for sample in prior.get('samples', ())
                   if isinstance(sample, list) and len(sample) == 3 and
                   all(type(value) in (int, float) for value in sample) and layout.contains(key, sample)]
        if not samples:
            samples = [layout.feet(key)]
        planned_spaces.append(dict(id=key, purpose=room['purpose'], feet_y=elevation,
            lo=[min(x), floor(elevation), min(z)], hi=[max(x), ceil(level['ceiling_y']) - 1, max(z)],
            samples=samples, **({'min_clearance': prior['min_clearance']} if 'min_clearance' in prior else {})))
        plan.setdefault('levels', {}).setdefault(room['level'], {})['feet_y'] = elevation
    plan['spaces'] = planned_spaces + [row for key, row in prior_spaces.items() if key not in layout.spaces]
    plan['planning'] = deepcopy(planning)
    # Draft targets are useful for a new template; preserve authored verification on revisions.
    context = plan.setdefault('context', {})
    context.setdefault('start', planning['program']['entry'])
    context.setdefault('targets', {room['id']: room['samples'][0] for room in planned_spaces})
    return dict(plan=normalize(plan), report=report, read_only=True)
