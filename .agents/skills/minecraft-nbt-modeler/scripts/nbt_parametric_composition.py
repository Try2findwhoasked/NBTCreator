"""Compose named objects and regenerate a bounded region of a known recipe."""
from nbt_components import placement
from nbt_structure_agent import build
from nbt_parametric import compile_object
from nbt_surface_mount import digest


def compose(workspace, arguments):
    for box in arguments.get('reserved_boxes', []):
        if any(a>b or b>=size for a,b,size in zip(box['lo'],box['hi'],arguments['size'])):
            raise ValueError('保留空间超出组合范围')
    occupied = set()
    operations = []
    receipts = []
    identifiers = set()
    for item in arguments['objects']:
        identifier = item['id']
        if identifier in identifiers:
            raise ValueError('组合对象编号重复')
        identifiers.add(identifier)
        compiled = compile_object(workspace, item['object'])
        component = build(workspace, compiled['spec'])
        placed = placement(component, item['position'], arguments['size'], item.get('quarter_turns', 0))
        for operation in placed['operations']:
            for x, y, z, _ in operation['voxels']:
                point = tuple(a+b for a,b in zip(operation['lo'], (x,y,z)))
                if point in occupied:
                    raise ValueError('组合对象重叠：'+identifier)
                for box in arguments.get('reserved_boxes', []):
                    if all(a<=p<=b for a,p,b in zip(box['lo'],point,box['hi'])):
                        raise ValueError('组合对象占用使用区或通道：'+identifier)
                occupied.add(point)
        operations.extend(placed['operations'])
        receipts.append(dict(id=identifier, bounds=dict(lo=placed['lo'],hi=placed['hi']),
                             recipe_sha256=compiled['recipe_sha256']))
    spec = dict(name=arguments['name'], size=arguments['size'], operations=operations,
                max_changed_blocks=arguments.get('max_changed_blocks',65536))
    data = build(workspace,spec)
    return dict(spec=spec, objects=receipts, recipe_sha256=digest(arguments),
                content_sha256=data['content_sha256'], block_count=len(data['blocks']),
                model_modified=False, approval_created=False,
                verification=dict(bounds=True, reserved_space=True, routes='not_checked'))


def regenerate(workspace, arguments):
    before = compile_object(workspace, arguments['original'])
    if before['recipe_sha256'] != arguments['original_recipe_sha256']:
        raise ValueError('原始配方哈希不匹配')
    candidate = compile_object(workspace, arguments['replacement'])
    part = arguments['part']
    if (arguments['original']['kind'] != arguments['replacement']['kind']
        or before['spec']['size'] != candidate['spec']['size']
        or part not in before['parts'] or part not in candidate['parts']):
        raise ValueError('局部重生成需要同类、同尺寸及双方都支持的部件')
    a,b=before['parts'][part],candidate['parts'][part]
    if a!=b:
        raise ValueError('局部重生成须保持部件边界不变')
    bounds=a
    def inside(point):
        return all(a<=p<=b for a,p,b in zip(bounds['lo'],point,bounds['hi']))
    def voxel_map(spec):
        data=build(workspace,spec)
        return {tuple(voxel[:3]):data['palette'][voxel[3]] for voxel in data['blocks']}
    old,new=voxel_map(before['spec']),voxel_map(candidate['spec'])
    if any(old.get(p)!=new.get(p) for p in old.keys()|new.keys() if not inside(p)):
        raise ValueError('替换参数同时改变所选部件之外的几何')
    merged={p:value for p,value in old.items() if not inside(p)}
    merged.update({p:value for p,value in new.items() if inside(p)})
    changed=sum(old.get(p)!=merged.get(p) for p in old.keys()|merged.keys())
    if not 0<changed<=arguments.get('max_changed_blocks',4096):
        raise ValueError('没有部件变化，或超过局部变化预算')
    palette=sorted(set(merged.values()))
    indices={value:i for i,value in enumerate(palette)}
    spec={**before['spec'],'operations':[dict(kind='paste_component',label='局部重生成 '+part,
          classification='wall' if arguments['original']['kind']=='wall' else 'body',lo=[0,0,0],hi=[n-1 for n in before['spec']['size']],palette=palette,
          voxels=[[*p,indices[value]] for p,value in sorted(merged.items())])]}
    data=build(workspace,spec)
    return dict(spec=spec, part=part, bounds=bounds, changed_blocks=changed,
                object_id=arguments['object_id'], parent_recipe_sha256=before['recipe_sha256'],
                recipe_sha256=digest(dict(parent=before['recipe_sha256'],replacement=candidate['recipe_sha256'],part=part,spec=spec)), content_sha256=data['content_sha256'],
                model_modified=False, approval_created=False)
