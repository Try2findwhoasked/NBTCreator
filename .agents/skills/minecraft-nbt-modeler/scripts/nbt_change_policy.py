"""Shared geometry/layer diff policy for candidates and final writers."""
from nbt_model import AIR
from nbt_model import AIR_NAMES
import re


def enforce_overwrite(model, walls, operation, edits, owners):
    """A new component may layer its own writes, but cannot claim old solids."""
    group=operation.get('write_group')
    if group is not None and (not isinstance(group,str) or not re.fullmatch(r'[a-f0-9-]{36}',group)):
        raise ValueError('构件写入组编号无效')
    limited='overwrite' in operation or group is not None
    overwrite=operation.get('overwrite',False)
    if limited and type(overwrite) is not bool:raise ValueError('覆盖现有方块须为布尔开关')
    classification=operation.get('classification','inherit')
    claimed=[]
    for p,value in edits:
        solid=model.get(p) not in AIR_NAMES
        new_wall=False if value in AIR_NAMES or classification=='body' else True if classification=='wall' else p in walls
        changes=value!=model.get(p) or new_wall!=(p in walls)
        own=group is not None and owners.get(p)==group
        if limited and not overwrite and solid and changes and not own:
            raise ValueError('目标位置已有方块或墙层；移动构件，或勾选“允许AI构件覆盖现有方块”：'+str(p))
        claimed.append((p,group if group and (not solid or overwrite or own) else None))
    for p,owner in claimed:
        if owner:owners[p]=owner
        else:owners.pop(p,None)


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


def clip_protected(operation, edits, protected):
    """Crop candidate writes only; protected geometry and wall ownership stay intact."""
    flag=operation.get('skip_protected',False)
    if type(flag) is not bool:raise ValueError('自动裁剪保护冲突须为布尔开关')
    if flag and operation.get('kind') not in ('box','beam','frame'):
        raise ValueError('保护裁剪仅支持方块、梁和边框')
    return [(p,value) for p,value in edits if p not in protected] if flag else edits
