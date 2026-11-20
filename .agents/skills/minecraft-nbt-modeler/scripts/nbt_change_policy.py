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
    # Recolouring a cell keeps its existing component owner. It does not
    # claim existing host geometry or opt any following step into overwrite.
    recolour = operation.get('kind') == 'pattern' and operation.get('action', 'replace') == 'replace'
    claimed=[]
    for p,value in edits:
        solid=model.get(p) not in AIR_NAMES
        new_wall=False if value in AIR_NAMES or classification=='body' else True if classification=='wall' else p in walls
        changes=value!=model.get(p) or new_wall!=(p in walls)
        own=group is not None and owners.get(p)==group
        if limited and not overwrite and solid and changes and not own:
            label = operation.get('label') or operation['kind']
            raise ValueError(f'步骤“{label}”({operation["kind"]}) 在 {p} 遇到已有方块或墙层。'
                             '请移动构件，或在确需覆盖时为该步骤设置 overwrite: true。')
        owner = group if group and (not solid or overwrite or own) else None
        if recolour and not limited:
            owner = owners.get(p)
        claimed.append((p, owner))
    for p,owner in claimed:
        if owner:owners[p]=owner
        else:owners.pop(p,None)


def change_sets(before, after, old_walls, walls):
    geometry={p for p in before.keys()|after.keys() if before.get(p,AIR)!=after.get(p,AIR)}
    old={tuple(p) for p in old_walls if tuple(p) in before}
    new={tuple(p) for p in walls if tuple(p) in after}
    return geometry,old^new


def reserved_position(positions, boxes):
    if not boxes:
        return None
    return next((p for p in positions if any(
        all(box['lo'][i] <= p[i] <= box['hi'][i] for i in range(3)) for box in boxes)),None)


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
