"""Static shape silhouettes at 1/16 or 1/32 block; separate from route collision.

The small box definitions match the vanilla trapdoor/wall model templates.
Texture alpha and game neighbour/redstone updates are deliberately not simulated.
Trusted Python extensions register providers returning FitShape values; public
JSON families still need an explicit tool-catalogue contract.
"""
from dataclasses import dataclass
from itertools import product
import math

import numpy as np

from nbt_collision import collision_cells
from nbt_extensions import HandlerRegistry
from nbt_model import state
from nbt_registry import effective


@dataclass(frozen=True)
class FitShape:
    value: str
    # XYZ pixel bounds, lower inclusive, upper exclusive, within one block.
    boxes: tuple
    requires_below: bool = False
    approximate: bool = False


FIT_SHAPES = HandlerRegistry('fitting_shapes')


class FitOptions(list):
    """Ordinary JSON-compatible choices plus immutable geometric constraints."""
    def __init__(self, choices, geometry, surface):
        super().__init__(choices)
        self.geometry = geometry
        self.surface = surface


@FIT_SHAPES.register('pane')
def panes(material, surface):
    name, props = effective(material)
    if props.get('waterlogged')=='true':raise ValueError('拟合玻璃板不能含水')
    if not name.endswith('_glass_pane') and name != 'minecraft:glass_pane':
        raise ValueError('pane 须使用玻璃板材质')
    return _cross_connections(name, surface)


@FIT_SHAPES.register('bars')
def bars(material, surface):
    name, props = effective(material)
    if props.get('waterlogged')=='true':raise ValueError('拟合铁栏杆不能含水')
    if name != 'minecraft:iron_bars':raise ValueError('bars 须使用 iron_bars')
    return _cross_connections(name, surface, approximate=True)


def _cross_connections(name, surface, approximate=False):
    _, props = effective(name)
    values = []
    for east,west,south in product(('false','true'),repeat=3):
        boxes = [(7,0,7,9,16,9),(7,0,0,9,16,8)]
        if east=='true':boxes.append((8,0,7,16,16,9))
        if west=='true':boxes.append((0,0,7,8,16,9))
        if south=='true':boxes.append((7,0,8,9,16,16))
        value=state(dict(Name=name,Properties=dict(props,north='true',east=east,west=west,south=south,waterlogged='false')))
        values.append(FitShape(value,tuple(boxes),approximate=approximate))
    return values


@FIT_SHAPES.register('fence')
def fences(material, surface):
    name = _material(material,'fence')
    values = []
    for east,west in product(('false','true'),repeat=2):
        boxes=[(6,0,6,10,16,10),(7,6,0,9,9,9),(7,12,0,9,15,9)]
        for connected,x,xx in ((east,8,16),(west,0,8)):
            if connected=='true':boxes.extend(((x,6,7,xx,9,9),(x,12,7,xx,15,9)))
        value=state(f'{name}[north=true,east={east},west={west},south=false,waterlogged=false]')
        values.append(FitShape(value,tuple(boxes)))
    return values


def _floor_only(surface):
    if surface=='ceiling':raise ValueError('雪层、地毯和压力板需要下方支撑，不能吊顶安装')


@FIT_SHAPES.register('snow')
def snow(material, surface):
    _floor_only(surface)
    name, _ = effective(material)
    if name!='minecraft:snow':raise ValueError('snow 须使用 snow')
    return [FitShape(state(f'{name}[layers={layers}]'),((0,0,0,16,layers*2,16),),True) for layers in range(1,9)]


@FIT_SHAPES.register('carpet')
def carpets(material, surface):
    _floor_only(surface)
    name, _ = effective(material)
    if not name.endswith('_carpet'):raise ValueError('carpet 须使用地毯材质')
    return [FitShape(state(name),((0,0,0,16,1,16),),True)]


@FIT_SHAPES.register('pressure_plate')
def pressure_plates(material, surface):
    _floor_only(surface)
    name, props = effective(material)
    if not name.endswith('_pressure_plate'):raise ValueError('pressure_plate 须使用压力板材质')
    props['power' if 'power' in props else 'powered']='0' if 'power' in props else 'false'
    return [FitShape(state(dict(Name=name,Properties=props)),((1,0,1,15,1,15),),True)]


def _orient_box(box, facing):
    def orient(p):
        x,y,z=p
        return dict(up=(x,y,z),down=(x,16-y,z),north=(x,z,16-y),south=(x,z,y),east=(y,z,x),west=(16-y,z,x))[facing]
    corners=[orient(p) for p in product(*((box[i],box[i+3]) for i in range(3)))]
    return tuple(min(p[i] for p in corners) for i in range(3))+tuple(max(p[i] for p in corners) for i in range(3))


@FIT_SHAPES.register('end_rod')
def end_rods(material, surface):
    name, _ = effective(material)
    if name!='minecraft:end_rod':raise ValueError('end_rod 须使用 end_rod')
    boxes=((6,0,6,10,1,10),(7,1,7,9,16,9))
    return [FitShape(state(f'{name}[facing={facing}]'),tuple(_orient_box(box,facing) for box in boxes))
            for facing in ('north','south','up','down','east','west')]


@FIT_SHAPES.register('chain')
def chains(material, surface):
    name, props=effective(material)
    if name!='minecraft:chain' or props['waterlogged']!='false':raise ValueError('chain 须使用未含水 chain')
    box=(6.5,0,6.5,9.5,16,9.5)
    # This is a static thin envelope, not the alpha-cut rotated chain quads.
    return [FitShape(state(f'{name}[axis={axis},waterlogged=false]'),(_orient_box(box,facing),),approximate=True)
            for axis,facing in (('z','south'),('y','up'),('x','east'))]


def _material(value, family):
    name, props = effective(value)
    if not name.endswith('_' + family) or props.get('waterlogged') != 'false':
        raise ValueError('拟合形状须使用对应的未含水原版材质：' + family)
    return name


def _half_shape(value):
    cells, reason = collision_cells(value)
    if reason:
        raise ValueError('拟合形状没有受支持的几何')
    return FitShape(state(value), tuple(tuple(8*n for n in p) + tuple(8*(n+1) for n in p) for p in cells))


@FIT_SHAPES.register('slab')
def slabs(material, surface):
    name = _material(material, 'slab')
    if surface == 'ceiling':
        raise ValueError('吊顶轮廓细分请省略 slab')
    return [_half_shape(f'{name}[type={half},waterlogged=false]') for half in ('bottom', 'top')]


@FIT_SHAPES.register('stairs')
def stairs(material, surface):
    name = _material(material, 'stairs')
    halves = ('top',) if surface == 'ceiling' else ('bottom', 'top')
    directions = ('north', 'east', 'south', 'west') if surface == 'ceiling' else ('east', 'west')
    return [_half_shape(f'{name}[half={half},facing={facing},shape=straight,waterlogged=false]')
            for half in halves for facing in directions]


@FIT_SHAPES.register('trapdoor')
def trapdoors(material, surface):
    name = _material(material, 'trapdoor')
    values = []
    # Open geometry depends on facing; half controls hinge/texture, not its box.
    opened = dict(north=(0,0,13,16,16,16), south=(0,0,0,16,16,3),
                  east=(0,0,0,3,16,16), west=(13,0,0,16,16,16))
    for half in ('bottom', 'top'):
        box = (0,0,0,16,3,16) if half == 'bottom' else (0,13,0,16,16,16)
        values.append(FitShape(state(f'{name}[facing=north,half={half},open=false,powered=false,waterlogged=false]'), (box,)))
    for facing, box in opened.items():
        values.append(FitShape(state(f'{name}[facing={facing},half=bottom,open=true,powered=false,waterlogged=false]'), (box,)))
    return values


@FIT_SHAPES.register('wall')
def walls(material, surface):
    name = _material(material, 'wall')
    if surface == 'ceiling':
        raise ValueError('石墙拟合用于墙面或柱饰，吊顶可使用 trapdoor/stairs')
    values = []
    # A north arm reaches the local backing at Z=0. Side arms are explicit
    # saved states, not a claim that a game neighbour update preserves them.
    for up, north, east, west in product(('true','false'), ('low','tall'), ('none','low','tall'), ('none','low','tall')):
        boxes = [(4,0,4,12,16,12)] if up == 'true' else []
        boxes.append((5,0,0,11,14 if north == 'low' else 16,8))
        if east != 'none': boxes.append((8,0,5,16,14 if east == 'low' else 16,11))
        if west != 'none': boxes.append((0,0,5,8,14 if west == 'low' else 16,11))
        value = state(f'{name}[up={up},north={north},east={east},south=none,west={west},waterlogged=false]')
        values.append(FitShape(value, tuple(boxes)))
    return values


def project_shape(shape, surface, resolution=16):
    """Project visible boxes; attachment is checked on the complete assignment."""
    if (not isinstance(shape, FitShape) or not isinstance(shape.boxes, (list,tuple))
        or not shape.boxes or len(shape.boxes)>32 or type(shape.requires_below) is not bool):
        raise ValueError('形状处理器须返回含有效盒体的 FitShape')
    state(shape.value)
    pixels=np.zeros((resolution,resolution),dtype=bool)
    for box in shape.boxes:
        if (not isinstance(box,(list,tuple)) or len(box)!=6 or
            any(type(n) not in (int,float) or not math.isfinite(n) or n*2!=int(n*2) for n in box) or
            any(not 0<=box[i]<box[i+3]<=16 for i in range(3))):
            raise ValueError('拟合盒体须使用0～16整数或半像素边界')
        if any(n*resolution/16!=int(n*resolution/16) for n in box):
            raise ValueError('拟合盒体需要更高采样精度')
        x,y,z,xx,yy,zz=(int(n*resolution/16) for n in box)
        if surface=='ceiling':
            if y<resolution//2:pixels[z:zz,x:xx]=True
        else:pixels[y:yy,x:xx]=True
    return tuple(bool(n) for n in pixels.flat)


def fine_options(material, shapes, surface):
    if surface not in ('wall','column','ceiling'):
        raise ValueError('精细形状拟合用于 wall/column/ceiling；圆柱仍使用半砖和楼梯')
    candidates=[]
    for family,value in sorted(shapes.items()):
        values=FIT_SHAPES.resolve(family)(value,surface)
        if not isinstance(values,(list,tuple)) or not 1<=len(values)<=256:
            raise ValueError('形状处理器须返回1～256个候选')
        for shape in values:
            project_shape(shape,surface,32)  # Validate before inspecting boxes.
            candidates.append(shape)
    factor=32 if any(n!=int(n) for shape in candidates for box in shape.boxes for n in box) else 16
    empty,full=(False,)*(factor**2),(True,)*(factor**2)
    choices=[(None,empty)];seen={empty,full};geometry={material:FitShape(material,((0,0,0,16,16,16),))}
    for shape in candidates:
        mask=project_shape(shape,surface,factor)
        if mask not in seen:
            value=state(shape.value);choices.append((value,mask));seen.add(mask);geometry[value]=shape
    options=FitOptions(choices+[(material,full)],geometry,surface)
    options.materials=dict(shapes)
    return options,factor


def unsupported_positions(unit, options, surface):
    """Each solid-box component reaches backing; gravity blocks have a real floor.

    This is static connectivity/support, not Minecraft collision or game physics.
    Thin texture quads use their declared envelopes and remain labelled approximate.
    """
    geometry=getattr(options,'geometry',None)
    if geometry is None:return 0
    boxes={p:geometry[value].boxes for p,value in unit.items()}
    axis=2 if surface=='ceiling' else 1
    def touches(a,b,direction_axis,direction):
        for first in a:
            for second in b:
                if direction>0:
                    face=first[direction_axis+3]==16 and second[direction_axis]==0
                else:face=first[direction_axis]==0 and second[direction_axis+3]==16
                if face and all(min(first[i+3],second[i+3])>max(first[i],second[i]) for i in range(3) if i!=direction_axis):return True
        return False
    graph={p:set() for p in boxes};anchored=set();invalid=set()
    for p,value in unit.items():
        shape=geometry[value]
        if any(box[4]==16 if surface=='ceiling' else box[2]==0 for box in shape.boxes):anchored.add(p)
        if shape.requires_below:
            below=unit.get((p[0],p[1]-1))
            cells,reason=collision_cells(below) if below else ((),True)
            if reason or not all((x,1,z) in cells for x in (0,1) for z in (0,1)):invalid.add(p)
        for step,direction_axis,direction in (((1,0),0,1),((-1,0),0,-1),((0,1),axis,1),((0,-1),axis,-1)):
            q=(p[0]+step[0],p[1]+step[1])
            if q in boxes and touches(boxes[p],boxes[q],direction_axis,direction):graph[p].add(q)
    pending=set(graph)
    while pending:
        first=pending.pop();group={first};queue=[first]
        while queue:
            for q in graph[queue.pop()]:
                if q in pending:pending.remove(q);group.add(q);queue.append(q)
        if not group.intersection(anchored):invalid.update(group)
    return len(invalid)
