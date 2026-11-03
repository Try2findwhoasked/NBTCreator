"""Shared geometry/layer diff policy for candidates and final writers."""
from nbt_model import AIR


def change_sets(before, after, old_walls, walls):
    geometry={p for p in before.keys()|after.keys() if before.get(p,AIR)!=after.get(p,AIR)}
    old={tuple(p) for p in old_walls if tuple(p) in before}
    new={tuple(p) for p in walls if tuple(p) in after}
    return geometry,old^new


def enforce_changes(before,after,old_walls,walls,protected=(),maximum=None,require_change=False):
    geometry,layers=change_sets(before,after,old_walls,walls)
    changed=geometry|layers;touched=sorted(changed&set(protected))
    if touched:raise ValueError('几何或墙层归属触及保护区：'+str(touched[:20]))
    if maximum is not None:
        if type(maximum) is not int or maximum<0:raise ValueError('变化上限必须为非负整数')
        if len(changed)>maximum:raise ValueError(f'几何或层归属共变化{len(changed)}格，超过上限{maximum}')
    if require_change and not changed:raise ValueError('没有实际几何或层归属变化')
    return dict(changed_blocks=len(geometry),wall_membership_changes=len(layers),changed_positions=len(changed))
