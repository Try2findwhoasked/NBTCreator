"""Building-scale envelope, circulation and bearing geometry; no load analysis."""
from math import ceil, floor, sqrt

from nbt_extensions import HandlerRegistry
from nbt_model import state, AIR_NAMES
from nbt_registry import effective
from nbt_collision import FULL_CUBES

CONSTRUCTION_SYSTEMS=HandlerRegistry('construction_systems')


def full(value):
    value=state(value)
    if effective(value)[0].removeprefix('minecraft:') not in FULL_CUBES:
        raise ValueError('围护与承托材料须为已支持的完整方块')
    return value


def polygon_contains(x,z,vertices):
    inside=False
    for a,b in zip(vertices,vertices[1:]+vertices[:1]):
        if (a[1]>z)!=(b[1]>z) and x<(b[0]-a[0])*(z-a[1])/(b[1]-a[1])+a[0]:inside=not inside
    return inside


@CONSTRUCTION_SYSTEMS.register('enclosure')
def enclosure(model, specification, budget):
    """Generate one union of designed air volumes, then its closed boundary."""
    wall=full(specification['wall']);roof_material=full(specification['roof']);floor_material=full(specification['floor'])
    air=set();analysed=0
    for volume in specification['volumes']:
        x0,z0=volume['lo_xz'];x1,z1=volume['hi_xz'];bottom=volume['feet_y'];eaves=volume['eaves_y']
        if not (0<x0<=x1<model.size[0]-1 and 0<z0<=z1<model.size[2]-1 and 1<=bottom<eaves<model.size[1]-1):
            raise ValueError('室内体积须在画布内保留一层围护余量')
        if type(bottom) is not int or type(eaves) is not int:raise ValueError('围护的脚位与檐口须为整数高度')
        polygon=volume.get('polygon')
        if polygon:
            if len(set(map(tuple,polygon)))!=len(polygon) or any(not x0<=p[0]<=x1+1 or not z0<=p[1]<=z1+1 for p in polygon):raise ValueError('多边形顶点重复或超出围护范围')
            def orient(a,b,c):return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
            edges=list(zip(polygon,polygon[1:]+polygon[:1]))
            for i,(a,b) in enumerate(edges):
                for j,(c,d) in enumerate(edges):
                    if j<=i or j==i+1 or (i==0 and j==len(edges)-1):continue
                    # Inclusive intersection also rejects touching nonadjacent edges.
                    if max(min(a[0],b[0]),min(c[0],d[0]))<=min(max(a[0],b[0]),max(c[0],d[0])) and max(min(a[1],b[1]),min(c[1],d[1]))<=min(max(a[1],b[1]),max(c[1],d[1])) and orient(a,b,c)*orient(a,b,d)<=0 and orient(c,d,a)*orient(c,d,b)<=0:raise ValueError('围护多边形自交')
            if not sum(a[0]*b[1]-b[0]*a[1] for a,b in edges):raise ValueError('围护多边形面积为零')
        profile=volume.get('roof',{});kind=profile.get('kind','flat');rise=profile.get('rise',0)
        if kind not in ('flat','gable','hip','dome'):raise ValueError('未注册的围护屋面类型')
        axis=profile.get('axis','z');cx,cz=(x0+x1+1)/2,(z0+z1+1)/2;rx,rz=(x1-x0+1)/2,(z1-z0+1)/2
        for x in range(x0,x1+1):
            for z in range(z0,z1+1):
                if volume.get('polygon') and not polygon_contains(x+.5,z+.5,volume['polygon']):continue
                nx,nz=abs((x+.5-cx)/rx),abs((z+.5-cz)/rz)
                t=0 if kind=='flat' else sqrt(max(0,1-nx*nx-nz*nz)) if kind=='dome' else 1-(max(nx,nz) if kind=='hip' else nx if axis=='z' else nz)
                if kind=='dome' and nx*nx+nz*nz>1:continue
                top=eaves+ceil(rise*t)
                if top>=model.size[1]-1:raise ValueError('屋面与围护超过画布高度')
                analysed+=top-bottom
                if analysed>budget*4:raise ValueError('建筑体积分析超过本次生成预算')
                for y in range(bottom,top):air.add((x,y,z))
    if not air:raise ValueError('围护没有生成室内体积')
    directions=((1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1))
    boundary={tuple(a+b for a,b in zip(p,d)) for p in air for d in directions}-air
    if len(boundary)>budget:raise ValueError('围护方块数超过生成预算')
    voxels={}
    for p in boundary:
        x,y,z=p
        lateral=any((x+dx,y,z+dz) in air for dx,_,dz in (directions[0],directions[1],directions[4],directions[5]))
        value=wall if lateral else floor_material if (x,y+1,z) in air else roof_material
        voxels[p]=(value,lateral)
    for patch in specification.get('glazing',[]):
        value=full(patch['state']);changed=0
        for p in voxels:
            if all(patch['lo'][i]<=p[i]<=patch['hi'][i] for i in range(3)):voxels[p]=(value,True);changed+=1
        if not changed:raise ValueError('玻璃范围没有匹配实际围护')
    return voxels,dict(kind='enclosure',air_voxels=len(air),boundary_voxels=len(voxels),
        generated_from='union_of_air_volumes',seal='requires_actual_check',structural_load='not_checked')


@CONSTRUCTION_SYSTEMS.register('stair_system')
def stair_system(model, specification, budget):
    from nbt_building.stairs import stair_plan
    operation=specification['operation']
    if operation.get('kind')!='auto_stairs':raise ValueError('完整梯段须使用 auto_stairs 操作')
    from nbt_assembly import Volume
    from nbt_collision import collision_cells,check_routes
    planned,report=stair_plan(Volume(model.size),operation)
    voxels={};borrowed=[];all_positions=[]
    for p,value in planned:
        p=tuple(p);all_positions.append(list(p));current=model.get(p)
        if current not in AIR_NAMES and not operation.get('overwrite',False):
            a,ra=collision_cells(current);b,rb=collision_cells(value)
            if ra or rb or set(a)!=set(b):raise ValueError('梯段目标与已有占用不兼容')
            borrowed.append(dict(pos=list(p),state=current));continue
        voxels[p]=(value,False)
    tread_positions=set(voxels)
    foundation=specification.get('foundation_y')
    if foundation is not None:
        material=full(specification.get('support_material',operation.get('state','stone_bricks')))
        # Landing ends and regular intermediate supports have actual contact.
        feet=report['feet']
        for index,pose in enumerate(feet):
            if index not in (0,len(feet)-1) and index%specification.get('support_spacing',4):continue
            x,top,z=floor(pose[0]),ceil(pose[1])-1,floor(pose[2])
            if foundation>top:
                if model.get((x,top,z)) not in AIR_NAMES:continue
                raise ValueError('梯段支承基底高于无承托踏步')
            for y in range(foundation,top):
                p=(x,y,z)
                if model.get(p) not in AIR_NAMES and model.get(p)!=material:raise ValueError('梯段支承与已有几何冲突')
                voxels.setdefault(p,(material,False))
    railing=specification.get('railing')
    if railing:
        if operation.get('mode','straight')!='straight':raise ValueError('当前自动护栏支持直梯；转弯梯请显式设计平台护栏')
        material=state(railing['state']);kerb=full(railing.get('kerb_material',operation.get('state','stone_bricks')))
        name,props=effective(material)
        if not (name.endswith(('_fence','_wall')) or name=='minecraft:iron_bars'):raise ValueError('梯段护栏须使用栅栏、墙或铁栏杆')
        feet=report['feet'];width=operation.get('width',1);lower=(width-1)//2
        rail_points={}
        for i,pose in enumerate(feet):
            a=feet[max(0,i-1)];b=feet[min(len(feet)-1,i+1)]
            sides=((0,-lower-1),(0,width-lower)) if a[0]!=b[0] else ((-lower-1,0),(width-lower,0))
            for dx,dz in sides:
                p=(floor(pose[0])+dx,ceil(pose[1]),floor(pose[2])+dz)
                rail_points[p]=True
                voxels.setdefault((p[0],p[1]-1,p[2]),(kerb,False))
        for p in rail_points:
            connections={}
            for direction,(dx,dz) in dict(north=(0,-1),east=(1,0),south=(0,1),west=(-1,0)).items():
                neighbor=(p[0]+dx,p[1],p[2]+dz)
                connected=neighbor in rail_points or voxels.get(neighbor,(None,))[0]==kerb
                connections[direction]=('low' if connected else 'none') if name.endswith('_wall') else str(connected).lower()
            if name.endswith('_wall'):connections['up']='true'
            voxels[p]=(state(dict(Name=name,Properties=dict(props,**connections))),False)
    if len(voxels)>budget:raise ValueError('完整梯段超过生成预算')
    borrowed_accessories=[]
    for p,(value,_) in list(voxels.items()):
        if not model.in_bounds(p):raise ValueError('梯段护栏或支承越界')
        if model.get(p) not in AIR_NAMES and model.get(p)!=value:
            a,ra=collision_cells(model.get(p));b,rb=collision_cells(value)
            if railing and value==kerb and not ra and not rb and set(a)==set(b):
                borrowed_accessories.append(list(p));del voxels[p]
            else:raise ValueError('梯段附属构造占用已有方块：'+str(p))
    candidate=Volume(model.size);candidate.blocks=dict(model.blocks)
    for p,(value,_) in voxels.items():candidate.put(p,value)
    if foundation is not None:
        from nbt_collision import _Space
        support_space=_Space(model)
        for p in set(voxels)-tread_positions:
            if p[1]==foundation and not support_space.supported((p[0]+.5,foundation,p[2]+.5)):raise ValueError('梯段支承基底没有实际支撑')
    for index,(a,b) in enumerate(zip(report['feet'],report['feet'][1:]),1):
        route=check_routes(candidate,a,[b],max_poses=1000)
        if not route['passed']:
            from nbt_composition.working_model import ModelConflict
            raise ModelConflict('STAIR_ROUTE_FAILED',[dict(instance=specification.get('id'),segment=index,
                start=a,end=b,report=route)])
    return voxels,dict(kind='stair_system',feet=report['feet'],route_segments=report['route_segments'],positions=all_positions+[list(p) for p in voxels],borrowed_floor=borrowed,
        accessory_positions=[list(p) for p in set(voxels)-tread_positions]+borrowed_accessories,supports_generated=foundation is not None,railings_generated=bool(railing),structural_load='not_checked')


@CONSTRUCTION_SYSTEMS.register('beam_link')
def beam_link(model, specification, budget):
    """A connected stepped beam between actual upward, integer-height seats."""
    left,right=specification['_surfaces'];axis=0 if specification['axis']=='x' else 2;tangent=2-axis
    if left['face']!='up' or right['face']!='up' or left['plane_half']%2 or right['plane_half']%2:
        raise ValueError('跨接需要真实朝上整数高度承托面，不舍入半格接口')
    centers=[(surface['lo_half'][tangent]+surface['hi_half'][tangent]+1)/2 for surface in (left,right)]
    width=specification.get('width',1);height=specification.get('height',1)
    if centers[0]!=centers[1] or (centers[0]-width)%2:raise ValueError('承托接口未沿声明轴整数居中')
    side=int((centers[0]-width)/2)
    if left['lo_half'][axis]>right['lo_half'][axis]:left,right=right,left
    low=left['lo_half'][axis]//2;high=right['hi_half'][axis]//2
    if high<=low:raise ValueError('跨接两端没有正跨度')
    ya,yb=left['plane_half']//2,right['plane_half']//2
    inner_left=left['hi_half'][axis]//2;inner_right=right['lo_half'][axis]//2
    if inner_right<=inner_left or abs(yb-ya)>inner_right-inner_left:raise ValueError('跨高梁净跨不足，先设计托座或独立转接')
    def base(u):
        if u<=inner_left:return ya
        if u>=inner_right:return yb
        return ya+floor((yb-ya)*(u-inner_left)/(inner_right-inner_left))
    material=full(specification['material']);voxels={}
    for u in range(low,high+1):
        y=base(u);top=max(y,base(max(low,u-1)),base(min(high,u+1)))+height
        for v in range(side,side+width):
            for yy in range(y,top):
                p=(u,yy,v) if axis==0 else (v,yy,u)
                if not model.in_bounds(p):raise ValueError('跨接构造越界')
                if model.get(p) not in AIR_NAMES and model.get(p)!=material:raise ValueError('跨接构造占用已有几何')
                voxels[p]=(material,False)
    if len(voxels)>budget:raise ValueError('跨接构造超过生成预算')
    return voxels,dict(kind='beam_link',rise=yb-ya,span=high-low+1,stepped=True,structural_load='not_checked')


@CONSTRUCTION_SYSTEMS.register('bearing_block')
def bearing_block(model,specification,budget):
    lower,upper=specification['_surfaces']
    if lower['face']!='up' or upper['face']!='down' or lower['plane_half']%2 or upper['plane_half']%2:
        raise ValueError('托座需要真实朝上承托和朝下被托面，不能舍入半格')
    y0,y1=lower['plane_half']//2,upper['plane_half']//2
    if not 0<y1-y0<=specification.get('max_gap',8):raise ValueError('托座高度无效或超过声明最大间隙')
    lo=[max(lower['lo_half'][i],upper['lo_half'][i]) for i in (0,2)]
    hi=[min(lower['hi_half'][i],upper['hi_half'][i]) for i in (0,2)]
    if any(a>b or a%2 or b%2!=1 for a,b in zip(lo,hi)):raise ValueError('承托面没有共同的整格截面')
    widths=[specification.get('width',(hi[0]-lo[0]+1)//2),specification.get('depth',(hi[1]-lo[1]+1)//2)]
    starts=[]
    for i,width in enumerate(widths):
        available=(hi[i]-lo[i]+1)//2
        if width>available or (available-width)%2:raise ValueError('托座截面无法在两个承托面的交集中居中')
        starts.append(lo[i]//2+(available-width)//2)
    material=full(specification['material']);voxels={}
    for x in range(starts[0],starts[0]+widths[0]):
        for z in range(starts[1],starts[1]+widths[1]):
            for y in range(y0,y1):
                p=(x,y,z)
                if not model.in_bounds(p) or model.get(p) not in AIR_NAMES:raise ValueError('托座越界或占用已有几何')
                voxels[p]=(material,False)
    if len(voxels)>budget:raise ValueError('托座超过生成预算')
    return voxels,dict(kind='bearing_block',height=y1-y0,structural_load='not_checked')
